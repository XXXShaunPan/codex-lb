from datetime import timedelta
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import func, select

from app.core.balancer import select_account
from app.core.clients.usage import UsageFetchError
from app.core.crypto import TokenEncryptor
from app.core.usage.models import SpendControlSnapshot, UsagePayload
from app.core.utils.time import utcnow
from app.db.models import Account, AccountStatus, ProviderSpendControl, UsageHistory
from app.db.session import SessionLocal
from app.modules.accounts.repository import AccountsRepository
from app.modules.proxy.load_balancer import RuntimeState, _state_from_account
from app.modules.relay_routing.selection import effective_weight
from app.modules.usage import updater as updater_module
from app.modules.usage.repository import UsageRepository
from app.modules.usage.updater import UsageUpdater

pytestmark = pytest.mark.integration


def payload(limit="200.00", remaining="116.66873848438263", *, reached=False):
    return UsagePayload.model_validate(
        {
            "plan_type": "ent26",
            "rate_limit": None,
            "credits": {"has_credits": True, "unlimited": False, "balance": None},
            "spend_control": {
                "reached": reached,
                "individual_limit": {
                    "unit": "usd",
                    "limit": limit,
                    "remaining": remaining,
                    "used": "83.33126151561737",
                    "remaining_percent": 58,
                    "reset_at": 1793491200,
                },
            },
        }
    )


async def seed(account_id):
    encryptor = TokenEncryptor()
    async with SessionLocal() as session:
        account = Account(
            id=account_id,
            chatgpt_account_id="shared-workspace",
            email=f"{account_id}@example.test",
            plan_type="ent26",
            status=AccountStatus.ACTIVE,
            last_refresh=utcnow(),
            access_token_encrypted=encryptor.encrypt("fake-access"),
            refresh_token_encrypted=encryptor.encrypt("fake-refresh"),
            id_token_encrypted=encryptor.encrypt("fake-id"),
        )
        session.add(account)
        await session.commit()


async def refresh(account_id):
    async with SessionLocal() as session:
        accounts = AccountsRepository(session)
        account = await accounts.get_by_id(account_id)
        return await UsageUpdater(UsageRepository(session), accounts).force_refresh_result(account)


@pytest.fixture(autouse=True)
def mock_route(monkeypatch):
    updater_module._clear_usage_refresh_state()
    monkeypatch.setattr(updater_module, "_resolve_upstream_route_for_account", AsyncMock(return_value=None))
    yield
    updater_module._clear_usage_refresh_state()


@pytest.mark.asyncio
async def test_budget_only_poll_reaches_accounts_api_persists_and_is_seat_scoped(async_client, monkeypatch):
    await seed("budget-a")
    await seed("budget-b")
    fetch = AsyncMock(side_effect=[payload(), payload("50.00", "28.31")])
    monkeypatch.setattr(updater_module, "fetch_usage", fetch)
    assert (await refresh("budget-a")).usage_written
    assert (await refresh("budget-b")).usage_written
    async with SessionLocal() as session:
        assert await session.scalar(select(func.count()).select_from(UsageHistory)) == 0
        assert await session.scalar(select(func.count()).select_from(ProviderSpendControl)) == 2
        accounts = AccountsRepository(session)
        account = await accounts.get_by_id("budget-a")
        assert not await UsageUpdater(UsageRepository(session), accounts).refresh_accounts([account], {})
    assert fetch.await_count == 2
    response = await async_client.get("/api/accounts")
    assert response.status_code == 200
    rows = {a["accountId"]: a for a in response.json()["accounts"]}
    assert rows["budget-a"]["spendControl"]["remaining"] == "116.66873848438263"
    assert rows["budget-a"]["spendControl"]["limit"] == "200.00"
    assert rows["budget-b"]["spendControl"]["limit"] == "50.00"
    assert rows["budget-a"]["spendControl"]["observedAt"].endswith("Z")
    assert rows["budget-a"]["spendControl"]["resetAt"] == "2026-11-01T00:00:00Z"
    assert rows["budget-a"]["usage"]["primaryRemainingPercent"] is None
    assert rows["budget-a"]["usage"]["secondaryRemainingPercent"] is None
    assert rows["budget-a"]["usage"]["monthlyRemainingPercent"] == 58
    assert rows["budget-a"]["resetAtMonthly"] == "2026-11-01T00:00:00Z"
    assert rows["budget-a"]["windowMinutesMonthly"] is None
    assert rows["budget-a"]["remainingCreditsMonthly"] is None
    assert rows["budget-b"]["usage"]["monthlyRemainingPercent"] == 58


@pytest.mark.asyncio
async def test_failure_and_omission_preserve_snapshot_but_explicit_null_clears(async_client, monkeypatch):
    await seed("budget-a")
    async with SessionLocal() as session:
        await UsageRepository(session).add_entry("budget-a", 0, window="primary", window_minutes=0)
    fetch = AsyncMock(return_value=payload())
    monkeypatch.setattr(updater_module, "fetch_usage", fetch)
    assert (await refresh("budget-a")).usage_written
    fetch.side_effect = UsageFetchError(503, "unavailable")
    assert not (await refresh("budget-a")).fetch_succeeded
    fetch.side_effect = None
    fetch.return_value = UsagePayload(plan_type="ent26", rate_limit=None)
    assert not (await refresh("budget-a")).usage_written
    rows = (await async_client.get("/api/accounts")).json()["accounts"]
    assert rows[0]["spendControl"]["limit"] == "200.00"
    fetch.return_value = UsagePayload.model_validate({"plan_type": "ent26", "rate_limit": None, "spend_control": None})
    assert (await refresh("budget-a")).usage_written
    rows = (await async_client.get("/api/accounts")).json()["accounts"]
    assert rows[0]["spendControl"] is None
    assert rows[0]["usage"]["primaryRemainingPercent"] is None


@pytest.mark.asyncio
async def test_older_observation_cannot_replace_new_budget_and_account_delete_cascades(db_setup):
    await seed("budget-a")
    now = utcnow()
    newer = SpendControlSnapshot(control=payload().spend_control)
    older = SpendControlSnapshot(control=payload("50.00").spend_control)
    async with SessionLocal() as session:
        repo = UsageRepository(session)
        assert await repo.save_spend_control("budget-a", newer, now)
        assert not await repo.save_spend_control("budget-a", older, now - timedelta(seconds=1))
    async with SessionLocal() as session:
        account = await AccountsRepository(session).get_by_id("budget-a")
        assert account.spend_control_snapshot.payload_json == newer.model_dump_json()
        await session.delete(account)
        await session.commit()
        assert await session.scalar(select(func.count()).select_from(ProviderSpendControl)) == 0


@pytest.mark.asyncio
async def test_routing_uses_monthly_budget_without_priority_runtime(async_client, monkeypatch):
    await seed("budget-a")
    monkeypatch.setattr(updater_module, "fetch_usage", AsyncMock(return_value=payload()))
    await refresh("budget-a")
    async with SessionLocal() as session:
        account = await AccountsRepository(session).get_by_id("budget-a")
        state = _state_from_account(
            account=account,
            primary_entry=None,
            secondary_entry=None,
            runtime=RuntimeState(),
            now=1793181600,
            soft_drain_enabled=False,
        )
        assert effective_weight(state) == 0.58
        assert select_account([state], routing_strategy="custom_weighted_quota").account is not None


@pytest.mark.asyncio
async def test_native_and_mixed_source_pool_share_ent26_percentage_scores(async_client, monkeypatch):
    from types import SimpleNamespace

    from app.dependencies import get_proxy_service_for_app
    from app.main import app
    from app.modules.virtual_accounts.routing import _choose_virtual_candidate

    for name, limit in [("budget-a", "200.00"), ("budget-b", "50.00")]:
        await seed(name)
        monkeypatch.setattr(updater_module, "fetch_usage", AsyncMock(return_value=payload(limit)))
        await refresh(name)
    assert (
        await async_client.put("/api/settings", json={"routingStrategy": "custom_weighted_quota"})
    ).status_code == 200
    assert (await async_client.put("/api/relay-routing/weights/budget-b", json={"weight": 3})).status_code == 200
    balancer = get_proxy_service_for_app(app)._load_balancer
    expected = {"budget-a": 0.58, "budget-b": 1.74, "model-source:compass": 2.0}
    observed = []

    def draw(population, weights, k):
        scores = {state.account_id: weight for state, weight in zip(population, weights)}
        observed.append(scores)
        assert scores == pytest.approx({key: expected[key] for key in scores})
        # Even the smallest positive score can receive this allocation.
        return [next(state for state in population if state.account_id == "budget-a")]

    monkeypatch.setattr("app.modules.relay_routing.selection.random.choices", draw)
    selected = await balancer.select_account(
        routing_strategy="custom_weighted_quota",
        account_ids={"budget-a", "budget-b"},
    )
    assert selected.account.id == "budget-a"
    inputs = await balancer._load_selection_inputs(model=None, service_tier=None, account_ids={"budget-a", "budget-b"})
    monkeypatch.setattr(balancer, "_load_selection_inputs", AsyncMock(return_value=inputs))
    source = SimpleNamespace(id="compass", routing_weight=2)
    assert await _choose_virtual_candidate(model="gpt-6", api_key=None, sources=[(source, "gpt-6")]) is None
    assert observed[-1] == pytest.approx(expected)

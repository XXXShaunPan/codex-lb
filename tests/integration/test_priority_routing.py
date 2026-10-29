from datetime import timedelta

import pytest
from sqlalchemy import select

from app.core.utils.time import utcnow
from app.db.models import Account, AccountStatus, ModelSource, UsageHistory
from app.db.session import get_background_session
from app.dependencies import get_proxy_service_for_app
from app.main import app
from app.modules.relay_routing.models import RoutingQuotaBand
from app.modules.visitor_access.repository import VisitorStore


async def seed():
    async with get_background_session() as session:
        for name, plan in [("plus-a", "plus"), ("plus-b", "plus"), ("pro-a", "pro")]:
            session.add(
                Account(
                    id=name,
                    email=name + "@example.test",
                    plan_type=plan,
                    status=AccountStatus.ACTIVE,
                    access_token_encrypted=b"test",
                    refresh_token_encrypted=b"test",
                    id_token_encrypted=b"test",
                    last_refresh=utcnow(),
                )
            )
        session.add(ModelSource(id="compass", name="Compass", base_url="https://example.invalid/v1"))
        await session.commit()


async def usage(name, remaining, tick=0):
    async with get_background_session() as session:
        for window, minutes in [("primary", 300), ("secondary", 10080)]:
            session.add(
                UsageHistory(
                    account_id=name,
                    window=window,
                    window_minutes=minutes,
                    used_percent=100 * (1 - remaining),
                    recorded_at=utcnow() + timedelta(seconds=tick),
                )
            )
        await session.commit()
    from app.modules.proxy.account_cache import get_account_selection_cache

    get_account_selection_cache().invalidate()


async def pick(ids, **kwargs):
    return await get_proxy_service_for_app(app)._load_balancer.select_account(
        routing_strategy="custom_weighted_quota",
        account_ids=set(ids),
        **kwargs,
    )


@pytest.mark.asyncio
async def test_legacy_rules_are_inert_but_weight_changes_affect_new_selection(async_client, monkeypatch):
    await seed()
    for name in ["plus-a", "plus-b", "pro-a"]:
        await usage(name, 0.6)
    response = await async_client.get("/api/relay-routing/rules")
    assert response.status_code == 200
    plans = {entry["planType"]: entry["rule"] for entry in response.json()["plans"]}
    assert plans["plus"]["normalPriority"] == 10 and plans["plus"]["lowPriority"] == 30
    assert plans["other"]["normalPriority"] == 20
    assert next(row for row in response.json()["accounts"] if row["name"] == "Compass")["quotaPlaceholder"]
    from unittest.mock import AsyncMock

    from app.modules.relay_routing.rules_repository import RoutingRulesRepository

    decisions = AsyncMock(side_effect=AssertionError("Routing must not read priority/hysteresis rules"))
    monkeypatch.setattr(RoutingRulesRepository, "decisions", decisions)

    def draw(population, weights, k):
        assert weights == pytest.approx([0.6] * len(population))
        return [next((s for s in population if s.account_id == "pro-a"), population[0])]

    monkeypatch.setattr("app.modules.relay_routing.selection.random.choices", draw)
    assert (await pick(["plus-a", "pro-a"])).account.id == "pro-a"
    override = {**plans["pro"], "normalPriority": 5}
    assert (
        await async_client.put("/api/relay-routing/rules/accounts/pro-a", json={"override": override})
    ).status_code == 200
    assert (await pick(["plus-a", "pro-a"])).account.id == "pro-a"
    assert (
        await async_client.put("/api/relay-routing/rules/accounts/pro-a", json={"override": None})
    ).status_code == 200
    assert (await pick(["plus-a", "pro-a"])).account.id == "pro-a"
    assert (await async_client.put("/api/relay-routing/rules/plans/pro", json=override)).status_code == 200
    assert (await pick(["plus-a", "pro-a"])).account.id == "pro-a"
    await async_client.put("/api/relay-routing/weights/pro-a", json={"weight": 0})
    assert (await pick(["plus-a", "pro-a"])).account.id == "plus-a"
    decisions.assert_not_awaited()


@pytest.mark.asyncio
async def test_saved_low_band_and_disabled_fallback_no_longer_gate_assignment(async_client):
    await seed()
    await usage("pro-a", 0.6)
    await usage("plus-a", 0.19)
    async with get_background_session() as session:
        session.add(RoutingQuotaBand(account_id="plus-a", low_quota=True, fingerprint="legacy", sample_at=123))
        await session.commit()
    assert (await pick(["plus-a"])).account.id == "plus-a"
    await usage("plus-a", 0.22, 1)
    # A new LoadBalancer has no process-local quota band to inherit.
    from app.modules.proxy.load_balancer import LoadBalancer

    restarted = LoadBalancer(get_proxy_service_for_app(app)._load_balancer._repo_factory)
    assert (
        await restarted.select_account(routing_strategy="custom_weighted_quota", account_ids={"plus-a"})
    ).account.id == "plus-a"
    async with get_background_session() as session:
        assert (await session.get(RoutingQuotaBand, "plus-a")).low_quota
    await usage("plus-a", 0.25, 2)
    assert (await pick(["plus-a"])).account.id == "plus-a"
    await usage("plus-a", 0.1, 3)
    assert (await pick(["plus-a"])).account.id == "plus-a"
    response = await async_client.put(
        "/api/relay-routing/rules/plans/plus", json={"normalPriority": 10, "lowPriority": 30, "allowLowQuota": False}
    )
    assert response.status_code == 200, response.text
    assert (await pick(["plus-a"])).account.id == "plus-a"
    owner = await pick(["plus-a"], required_account_id="plus-a", required_continuity_owner=True)
    assert owner.account.id == "plus-a"
    async with get_background_session() as session:
        band = await session.get(RoutingQuotaBand, "plus-a")
        assert band.low_quota and band.fingerprint == "legacy" and band.sample_at == 123


@pytest.mark.asyncio
async def test_unknown_quota_and_virtual_mixed_pool(async_client, monkeypatch):
    from app.modules.virtual_accounts.routing import _choose_virtual_candidate

    await seed()
    await async_client.put("/api/settings", json={"routingStrategy": "custom_weighted_quota"})
    async with get_background_session() as session:
        source = await session.scalar(select(ModelSource).where(ModelSource.id == "compass"))
        session.expunge(source)
    assert await _choose_virtual_candidate(model="gpt-6", api_key=None, sources=[(source, "gpt-6")]) == (
        source,
        "gpt-6",
    )
    assert (await pick(["plus-a"])).account is None
    # Use unrestricted model selection so native eligibility is not registry-dependent.
    await usage("plus-a", 0.6)
    from unittest.mock import AsyncMock

    balancer = get_proxy_service_for_app(app)._load_balancer
    inputs = await balancer._load_selection_inputs(model=None, service_tier=None, account_ids={"plus-a"})
    from unittest.mock import patch

    with patch.object(balancer, "_load_selection_inputs", AsyncMock(return_value=inputs)):

        def draw(population, weights, k):
            assert {state.account_id: weight for state, weight in zip(population, weights)} == {
                "plus-a": 0.6,
                "model-source:compass": 1.0,
            }
            return [next(state for state in population if state.account_id == "plus-a")]

        with monkeypatch.context() as m:
            m.setattr("app.modules.relay_routing.selection.random.choices", draw)
            assert await _choose_virtual_candidate(model="gpt-6", api_key=None, sources=[(source, "gpt-6")]) is None
        # A saturated real account must not hide an available source.
        from app.modules.proxy._load_balancer.types import RuntimeState

        balancer._runtime["plus-a"] = RuntimeState(inflight_streams=1_000_000)
        assert await _choose_virtual_candidate(
            model="gpt-6",
            api_key=None,
            sources=[(source, "gpt-6")],
            lease_kind="stream",
        ) == (source, "gpt-6")


@pytest.mark.asyncio
async def test_stale_observation_cannot_undo_persisted_low_band(async_client):
    from app.modules.relay_routing.policy import QuotaCandidate
    from app.modules.relay_routing.rules_repository import RoutingRulesRepository

    await seed()

    async def evaluate(remaining, sample_at):
        async with get_background_session() as session:
            return (
                await RoutingRulesRepository(session).decisions(
                    [
                        QuotaCandidate("plus-a", "plus", remaining, remaining, sample_at=sample_at),
                    ]
                )
            )["plus-a"]

    assert (await evaluate(0.1, 200)).priority == 30
    assert (await evaluate(0.8, 100)).priority == 30
    assert (await evaluate(0.22, 300)).priority == 30
    assert (await evaluate(0.25, 400)).priority == 10


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "payload",
    [
        {"normalPriority": True},
        {"lowPriority": -1},
        {"normalPriority": 1.5},
        {"downgradePercent": 25, "recoveryPercent": 20},
        {"downgradePercent": 20, "recoveryPercent": 20},
        {"quotaBasis": "bogus"},
        {"allowLowQuota": "false"},
        {"recoveryPercent": 101},
    ],
)
async def test_invalid_rules(async_client, payload):
    response = await async_client.put("/api/relay-routing/rules/plans/plus", json=payload)
    assert response.status_code == 422, response.text


@pytest.mark.asyncio
async def test_rules_do_not_leak_to_visitors_and_missing_targets_fail(async_client):
    await seed()
    assert (
        await async_client.put("/api/relay-routing/rules/accounts/missing", json={"override": None})
    ).status_code == 404
    visitor = await VisitorStore().create(
        username="rules-visitor", display_name="Visitor", password="test-pass-123", active=True, api_key_ids=[]
    )
    assert (
        await async_client.post("/api/visitor/login", json={"username": visitor.username, "password": "test-pass-123"})
    ).status_code == 200
    assert (await async_client.get("/api/relay-routing/rules")).status_code == 403
    assert (await async_client.put("/api/relay-routing/rules/plans/plus", json={})).status_code == 403
    assert (
        await async_client.put("/api/relay-routing/rules/accounts/plus-a", json={"override": None})
    ).status_code == 403

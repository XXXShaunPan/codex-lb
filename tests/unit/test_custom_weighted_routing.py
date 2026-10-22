from dataclasses import replace
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.core.balancer.logic import AccountState, RoutingCost, select_account
from app.db.models import Account, AccountStatus, UsageHistory
from app.modules.proxy._load_balancer.sticky_selection import (
    _probing_result_requires_recovery_reservation,
    _select_account_preferring_budget_safe,
)
from app.modules.proxy._load_balancer.types import RuntimeState
from app.modules.proxy.load_balancer import _build_states
from app.modules.relay_routing.selection import effective_weight


@pytest.mark.asyncio
async def test_existing_owner_survives_zero_weight_and_burn_first_peer():
    from app.core.clock import REAL_CLOCK
    from app.db.models import StickySessionKind
    from app.modules.proxy._load_balancer.sticky_selection import _select_with_stickiness

    owner = account("owner", routing_weight=0, used_percent=97, routing_policy="preserve")
    peer = account("peer", routing_weight=100, routing_policy="burn_first")
    outcome = await _select_with_stickiness(
        states=[owner, peer],
        account_map={},
        sticky_key="existing",
        sticky_kind=StickySessionKind.CODEX_SESSION,
        reallocate_sticky=False,
        sticky_max_age_seconds=None,
        prefer_earlier_reset_accounts=True,
        prefer_earlier_reset_window="secondary",
        routing_strategy="custom_weighted_quota",
        sticky_repo=AsyncMock(),
        sticky_existing_account_id="owner",
        clock=REAL_CLOCK,
    )
    assert outcome.selection.account is not None
    assert outcome.selection.account.account_id == "owner"


def account(name="a", **kwargs):
    return AccountState(account_id=name, status=AccountStatus.ACTIVE, **kwargs)


@pytest.mark.parametrize(
    "weight,primary,secondary,expected",
    [
        (2, 50, 10, 1),
        (1, 0, 0, 1),
        (3, None, 0, 3),
        (0, 0, 0, 0),
        (2, 100, 0, 0),
        (2, 0, 100, 0),
        (1, None, None, 0),
        (4, -5, 75, 1),
        (1, float("nan"), 0, 0),
    ],
)
def test_weight_times_tightest_quota(weight, primary, secondary, expected):
    assert (
        effective_weight(account(routing_weight=weight, used_percent=primary, secondary_used_percent=secondary))
        == expected
    )


def test_ranking_factors_do_not_change_draw_weights(monkeypatch):
    a = account(
        "a",
        routing_weight=2,
        used_percent=50,
        secondary_used_percent=0,
        plan_type="prolite",
        capacity_credits=1,
        routing_policy="preserve",
        health_tier=2,
        selection_weight_multiplier=0.01,
        last_selected_at=999,
        secondary_reset_at=999999,
    )
    b = account(
        "b",
        routing_weight=1,
        used_percent=0,
        secondary_used_percent=0,
        plan_type="pro",
        capacity_credits=100000,
        routing_policy="burn_first",
        health_tier=0,
        selection_weight_multiplier=1,
        last_selected_at=0,
        secondary_reset_at=1,
    )

    def draw(population, weights, k):
        assert population == [a, b]
        assert weights == [1, 1]
        assert k == 1
        return [a]

    monkeypatch.setattr("app.modules.relay_routing.selection.random.choices", draw)
    chosen = _select_account_preferring_budget_safe(
        [a, b],
        routing_strategy="custom_weighted_quota",
        prefer_earlier_reset=True,
        budget_threshold_pct=5,
        secondary_budget_threshold_pct=5,
        apply_secondary_budget_threshold=True,
        routing_costs_by_account_id={"a": RoutingCost(total=999), "b": RoutingCost(total=0)},
    )
    assert chosen.account is a
    assert not _probing_result_requires_recovery_reservation(
        [a, b],
        a,
        routing_strategy="custom_weighted_quota",
        traffic_class="foreground",
        now=1000,
    )


def test_reported_quota_is_used_instead_of_synthetic_pressure():
    state = account(
        routing_weight=3,
        used_percent=100,
        secondary_used_percent=100,
        quota_used_percent=20,
        quota_secondary_used_percent=50,
        inflight_streams=40,
        leased_tokens=100000,
    )
    assert effective_weight(state) == 1.5


@pytest.mark.parametrize(
    "blocked",
    [
        {"status": AccountStatus.PAUSED},
        {"status": AccountStatus.DEACTIVATED},
        {"status": AccountStatus.RATE_LIMITED, "reset_at": 2000},
        {"status": AccountStatus.QUOTA_EXCEEDED, "reset_at": 2000},
        {"cooldown_until": 2000},
        {"error_count": 3, "last_error_at": 999},
    ],
)
def test_unavailable_high_weight_cannot_win(blocked):
    unavailable = replace(account("blocked", routing_weight=1_000_000), **blocked)
    available = account("available", routing_weight=1, used_percent=0, secondary_used_percent=0)
    assert (
        select_account([unavailable, available], routing_strategy="custom_weighted_quota", now=1000).account
        is available
    )


def test_zero_pool_does_not_fall_back_and_old_strategy_is_unchanged():
    states = [account("a", routing_weight=0), account("b", used_percent=100)]
    chosen = select_account(states, routing_strategy="custom_weighted_quota")
    assert chosen.account is None and chosen.error_code == "no_weighted_capacity"
    assert select_account([states[0]], routing_strategy="capacity_weighted").account is states[0]


def test_state_builder_retains_operator_weight_and_reported_usage():
    row = Account(id="a", email="a@example.test", plan_type="plus", status=AccountStatus.ACTIVE, routing_weight=4)
    usage = UsageHistory(account_id="a", window="primary", used_percent=25, window_minutes=300)
    states, _ = _build_states(
        accounts=[row],
        latest_primary={"a": usage},
        latest_secondary={},
        latest_monthly={},
        runtime={"a": RuntimeState(inflight_streams=50, leased_tokens=10000)},
        now=1000,
    )
    assert states[0].routing_weight == 4
    assert states[0].quota_used_percent == 25
    assert effective_weight(states[0]) == 3


@pytest.mark.asyncio
async def test_virtual_zero_weight_never_uses_first_source_fallback(monkeypatch, async_client):
    from app.dependencies import get_proxy_service_for_app
    from app.main import app
    from app.modules.virtual_accounts.routing import _choose_virtual_candidate

    proxy = get_proxy_service_for_app(app)

    async def inputs(**kwargs):
        return SimpleNamespace(
            accounts=[],
            latest_primary={},
            latest_secondary={},
            latest_monthly={},
            routing_policy_override=None,
            ignore_standard_quota_account_ids=frozenset(),
        )

    async def settings():
        return SimpleNamespace(routing_strategy="custom_weighted_quota")

    from app.core.config.settings_cache import get_settings_cache

    monkeypatch.setattr(proxy._load_balancer, "_load_selection_inputs", inputs)
    monkeypatch.setattr(get_settings_cache(), "get", settings)
    source = SimpleNamespace(id="source", routing_weight=0)
    assert await _choose_virtual_candidate(model="test", api_key=None, sources=[(source, "test")]) is None
    source.routing_weight = 3
    result = await _choose_virtual_candidate(model="test", api_key=None, sources=[(source, "test")])
    assert result == (source, "test")

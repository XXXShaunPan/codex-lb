from dataclasses import replace

import pytest

from app.core.balancer.logic import AccountState, select_account
from app.db.models import AccountStatus
from app.modules.relay_routing.policy import (
    QuotaCandidate,
    default_rule,
    make_decision,
    quota_band,
    threshold_remaining,
)
from app.modules.relay_routing.schemas import PriorityRule


def state(name, plan="plus", remaining=0.5, weight=1, **kwargs):
    return AccountState(
        account_id=name,
        plan_type=plan,
        status=AccountStatus.ACTIVE,
        used_percent=100 * (1 - remaining),
        secondary_used_percent=100 * (1 - remaining),
        routing_weight=weight,
        **kwargs,
    )


def choose(states):
    return select_account(states, routing_strategy="custom_weighted_quota").account


def test_non_plus_total_weight_cannot_outvote_healthy_plus(monkeypatch):
    plus = state("plus")
    others = [state(f"pro-{i}", "pro", weight=1_000_000) for i in range(100)]

    def draw(population, weights, k):
        assert population == [plus]
        assert weights == [0.5]
        return [plus]

    monkeypatch.setattr("app.modules.relay_routing.selection.random.choices", draw)
    assert choose([*others, plus]) is plus


def test_default_group_order_and_disabled_zero_exhausted_plus():
    healthy, low, other = state("healthy"), state("low", remaining=0.19), state("other", "other")
    assert choose([low, other, healthy]) is healthy
    assert choose([low, other]) is other
    assert choose([low]) is low
    assert choose([replace(healthy, routing_weight=0), other]) is other
    assert choose([state("empty", remaining=0), other]) is other
    assert choose([replace(healthy, status=AccountStatus.PAUSED), other]) is other


def test_same_group_uses_only_weight_times_remaining(monkeypatch):
    a, b = state("a", remaining=0.5, weight=2), state("b", remaining=1, weight=1)

    def draw(population, weights, k):
        assert population == [a, b] and weights == [1, 1]
        return [b]

    monkeypatch.setattr("app.modules.relay_routing.selection.random.choices", draw)
    assert choose([a, b]) is b


@pytest.mark.parametrize(
    "sequence,expected",
    [
        ([0.20, 0.199, 0.21, 0.249, 0.25], [False, True, True, True, False]),
        ([None, 0.22, 0.25], [True, True, False]),
    ],
)
def test_threshold_boundaries_and_hysteresis(sequence, expected):
    low = None
    result = []
    for remaining in sequence:
        low = quota_band(remaining, default_rule("plus"), low)
        result.append(low)
    assert result == expected


@pytest.mark.parametrize("basis,expected", [("weekly", 0.6), ("five_hour", 0.1), ("minimum", 0.1)])
def test_threshold_basis(basis, expected):
    candidate = QuotaCandidate("a", "plus", 0.1, 0.6)
    assert threshold_remaining(candidate, PriorityRule(quota_basis=basis)) == expected


def test_unknown_and_confirmed_absent_windows_are_different():
    unknown = QuotaCandidate("a", "plus", None, 0.6)
    rule = default_rule("plus")
    assert threshold_remaining(unknown, rule) is None
    assert threshold_remaining(replace(unknown, primary_applicable=False), rule) == 0.6
    absent = replace(unknown, primary_applicable=False, primary_remaining=0)
    assert make_decision(absent, rule, False).remaining == 0.6
    assert threshold_remaining(replace(unknown, placeholder=True), rule) == 1
    assert make_decision(replace(unknown, weekly_remaining=None), rule, True).allow_new is False
    ordinary_unknown = AccountState(account_id="unknown", status=AccountStatus.ACTIVE, plan_type="plus")
    assert choose([ordinary_unknown]) is None
    partial = replace(ordinary_unknown, used_percent=10)
    other = state("other", "pro")
    assert choose([partial, other]) is other


def test_fallback_disabled_does_not_break_continuity():
    low = state(
        "owner", remaining=0.1, weight=0, routing_priority=30, routing_remaining_fraction=0.1, routing_allow_new=False
    )
    assert choose([low]) is None
    assert choose([replace(low, routing_continuity_owner=True)]).account_id == "owner"

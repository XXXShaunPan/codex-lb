from __future__ import annotations

import math
import random
from typing import TYPE_CHECKING

from app.modules.relay_routing.policy import (
    QuotaCandidate,
    RoutingDecision,
    default_rule,
    make_decision,
    quota_band,
    remaining_fraction,
    threshold_remaining,
)

if TYPE_CHECKING:
    from app.core.balancer.logic import AccountState

STRATEGY = "custom_weighted_quota"


def _candidate(state: AccountState) -> QuotaCandidate:
    primary, secondary = (
        state.quota_used_percent if state.quota_used_percent is not None else state.used_percent,
        state.quota_secondary_used_percent
        if state.quota_secondary_used_percent is not None
        else state.secondary_used_percent,
    )
    return QuotaCandidate(
        account_id=state.account_id,
        plan_type=state.plan_type or "other",
        primary_remaining=remaining_fraction(primary),
        weekly_remaining=remaining_fraction(secondary),
        primary_applicable=state.plan_type != "free",
        placeholder=state.account_id.startswith("model-source:"),
        invalid_quota=any(value is not None and not math.isfinite(value) for value in (primary, secondary)),
        budget_remaining=(
            state.spend_control_remaining_percent / 100 if state.spend_control_remaining_percent is not None else None
        ),
        budget_only=state.spend_control_budget_only,
    )


def _decision(state: AccountState) -> RoutingDecision:
    if state.routing_priority is not None and state.routing_remaining_fraction is not None:
        return RoutingDecision(state.routing_priority, state.routing_remaining_fraction, state.routing_allow_new, False)
    candidate = _candidate(state)
    rule = default_rule(candidate.plan_type)
    return make_decision(candidate, rule, quota_band(threshold_remaining(candidate, rule), rule, None))


def effective_weight(state: AccountState) -> float:
    """Priorities/admission select the group; only weight and quota affect its draw."""
    if state.spend_control_exhausted:
        return 0.0
    if state.routing_continuity_owner:
        candidate = _candidate(state)
        known = [value for value in (candidate.primary_remaining, candidate.weekly_remaining) if value is not None]
        return 0.0 if any(value <= 0 for value in known) and not state.ignore_standard_quota else 1.0
    weight = state.routing_weight
    if not math.isfinite(weight) or weight <= 0:
        return 0.0
    decision = _decision(state)
    return weight * decision.remaining if decision.allow_new else 0.0


def select_weighted_quota(
    states: list[AccountState],
    *,
    deterministic: bool = False,
) -> AccountState | None:
    weighted = [(state, effective_weight(state)) for state in states]
    weighted = [(state, weight) for state, weight in weighted if weight > 0]
    if not weighted:
        return None
    priority = min(_decision(state).priority for state, _ in weighted)
    weighted = [(state, weight) for state, weight in weighted if _decision(state).priority == priority]
    if deterministic:
        return max(weighted, key=lambda candidate: candidate[1])[0]
    return random.choices([state for state, _ in weighted], weights=[weight for _, weight in weighted], k=1)[0]

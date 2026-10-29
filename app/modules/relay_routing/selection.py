from __future__ import annotations

import math
import random
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.core.balancer.logic import AccountState

STRATEGY = "custom_weighted_quota"


def remaining_quota_fraction(state: AccountState) -> float:
    """Use the tightest known quota, never plan capacity or a saved priority band."""
    if state.account_id.startswith("model-source:"):
        return 1.0  # Explicit placeholder until provider quota polling is available.
    primary, secondary = (
        state.quota_used_percent if state.quota_used_percent is not None else state.used_percent,
        state.quota_secondary_used_percent
        if state.quota_secondary_used_percent is not None
        else state.secondary_used_percent,
    )
    remaining: list[float] = []
    if not state.spend_control_budget_only:
        used_windows = [secondary] if state.plan_type == "free" else [primary, secondary]
        remaining.extend(100.0 - used for used in used_windows if used is not None)
    if state.spend_control_remaining_percent is not None:
        remaining.append(state.spend_control_remaining_percent)
    if any(not math.isfinite(value) for value in remaining):
        return 0.0
    return max(0.0, min(1.0, min(remaining, default=0.0) / 100.0))


def effective_weight(state: AccountState) -> float:
    """Square the tightest quota fraction, keeping operator weight linear."""
    if state.spend_control_exhausted:
        return 0.0
    if state.routing_continuity_owner:
        # Ownership is not a new draw: unknown quota or a zero operator weight
        # alone cannot move an established session. Hard exhaustion still wins.
        primary = state.quota_used_percent if state.quota_used_percent is not None else state.used_percent
        secondary = (
            state.quota_secondary_used_percent
            if state.quota_secondary_used_percent is not None
            else state.secondary_used_percent
        )
        applicable = [secondary] if state.plan_type == "free" else [primary, secondary]
        exhausted = not state.spend_control_budget_only and any(used is not None and used >= 100 for used in applicable)
        return 0.0 if exhausted and not state.ignore_standard_quota else 1.0
    weight = state.routing_weight
    if not math.isfinite(weight) or weight <= 0:
        return 0.0
    return weight * remaining_quota_fraction(state) ** 2


def select_weighted_quota(
    states: list[AccountState],
    *,
    deterministic: bool = False,
) -> AccountState | None:
    weighted = [(state, effective_weight(state)) for state in states]
    weighted = [(state, weight) for state, weight in weighted if weight > 0]
    if not weighted:
        return None
    if deterministic:
        # Availability probes do not allocate requests or consume randomness.
        return max(weighted, key=lambda candidate: candidate[1])[0]
    return random.choices([state for state, _ in weighted], weights=[weight for _, weight in weighted], k=1)[0]

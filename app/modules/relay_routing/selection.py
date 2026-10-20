from __future__ import annotations

import math
import random
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.core.balancer.logic import AccountState

STRATEGY = "custom_weighted_quota"


def effective_weight(state: AccountState) -> float:
    """Only configured weight and reported quota participate in the draw."""
    weight = state.routing_weight
    if not math.isfinite(weight) or weight <= 0:
        return 0.0
    remaining = 1.0
    for used in (
        state.quota_used_percent if state.quota_used_percent is not None else state.used_percent,
        state.quota_secondary_used_percent
        if state.quota_secondary_used_percent is not None
        else state.secondary_used_percent,
    ):
        if used is None:
            continue
        if not math.isfinite(used):
            return 0.0
        remaining = min(remaining, max(0.0, min(1.0, 1.0 - used / 100.0)))
    return weight * remaining


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
        return max(weighted, key=lambda candidate: candidate[1])[0]
    return random.choices([state for state, _ in weighted], weights=[weight for _, weight in weighted], k=1)[0]

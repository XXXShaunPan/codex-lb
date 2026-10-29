"""Pure priority, quota and hysteresis rules. Smaller priority numbers win."""

from __future__ import annotations

import math
from dataclasses import dataclass

from app.modules.relay_routing.schemas import PriorityRule


@dataclass(frozen=True, slots=True)
class QuotaCandidate:
    account_id: str
    plan_type: str
    primary_remaining: float | None
    weekly_remaining: float | None
    primary_applicable: bool = True
    sample_at: float = 0.0
    placeholder: bool = False
    invalid_quota: bool = False
    budget_remaining: float | None = None
    budget_only: bool = False


@dataclass(frozen=True, slots=True)
class RoutingDecision:
    priority: int
    remaining: float
    allow_new: bool
    low_quota: bool


def default_rule(plan: str) -> PriorityRule:
    return PriorityRule(normal_priority=10, low_priority=30) if plan.lower() == "plus" else PriorityRule()


def remaining_fraction(used: float | None) -> float | None:
    if used is None or not math.isfinite(used):
        return None
    return max(0.0, min(1.0, 1.0 - used / 100.0))


def threshold_remaining(candidate: QuotaCandidate, rule: PriorityRule) -> float | None:
    if candidate.budget_only:
        return candidate.budget_remaining
    if candidate.placeholder:
        return 1.0
    if rule.quota_basis == "weekly":
        windows = [candidate.weekly_remaining]
    elif rule.quota_basis == "five_hour":
        windows = [candidate.primary_remaining if candidate.primary_applicable else None]
    else:
        windows = [candidate.weekly_remaining]
        if candidate.primary_applicable:
            windows.append(candidate.primary_remaining)
    if candidate.budget_remaining is not None:
        windows.append(candidate.budget_remaining)
    if any(value is None for value in windows):
        return None
    return min(value for value in windows if value is not None)


def quota_band(remaining: float | None, rule: PriorityRule, was_low: bool | None) -> bool:
    if remaining is None:
        return True
    # Round percentage noise: exactly 20% is not below 20%; 25% recovers.
    percent = round(remaining * 100, 10)
    if percent < rule.downgrade_percent:
        return True
    if percent >= rule.recovery_percent:
        return False
    return was_low if was_low is not None else False


def make_decision(candidate: QuotaCandidate, rule: PriorityRule, low: bool) -> RoutingDecision:
    # Admission threshold basis never bypasses exhaustion of another known window.
    windows = [candidate.weekly_remaining]
    if candidate.primary_applicable:
        windows.append(candidate.primary_remaining)
    if candidate.budget_only:
        windows = [candidate.budget_remaining]
    elif candidate.budget_remaining is not None:
        windows.append(candidate.budget_remaining)
    known = [value for value in windows if value is not None]
    remaining = 0.0 if candidate.invalid_quota else (1.0 if candidate.placeholder else min(known, default=0.0))
    return RoutingDecision(
        priority=rule.low_priority if low else rule.normal_priority,
        remaining=remaining,
        allow_new=remaining > 0 and (not low or rule.allow_low_quota),
        low_quota=low,
    )


def band_fingerprint(rule: PriorityRule) -> str:
    return f"{rule.quota_basis}:{rule.downgrade_percent:g}:{rule.recovery_percent:g}"

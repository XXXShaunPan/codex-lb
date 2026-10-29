from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from datetime import timezone
from typing import TYPE_CHECKING

from app.core import usage as usage_core
from app.core.usage.spend_controls import account_spend_control, spend_control_remaining_percent
from app.db.models import Account, AdditionalUsageHistory, ModelSource, UsageHistory
from app.db.session import get_background_session
from app.modules.relay_routing.policy import QuotaCandidate, RoutingDecision, remaining_fraction
from app.modules.relay_routing.rules_repository import RoutingRulesRepository
from app.modules.virtual_accounts.identity import virtual_account_id

if TYPE_CHECKING:
    from app.core.balancer.logic import AccountState


async def load_priority_decisions(
    *,
    accounts: Sequence[Account],
    latest_primary: Mapping[str, UsageHistory | AdditionalUsageHistory],
    latest_secondary: Mapping[str, UsageHistory | AdditionalUsageHistory],
    latest_monthly: Mapping[str, UsageHistory],
    now: float,
    sources: Sequence[ModelSource] = (),
) -> dict[str, RoutingDecision]:
    from app.modules.proxy.load_balancer import _normalize_usage_inputs, _select_long_window_entry

    candidates: list[QuotaCandidate] = []
    for account in accounts:
        primary = latest_primary.get(account.id)
        secondary = _select_long_window_entry(
            account=account,
            monthly_entry=latest_monthly.get(account.id),
            secondary_entry=latest_secondary.get(account.id),
        )
        normalized = _normalize_usage_inputs(
            account=account,
            primary_entry=primary,
            secondary_entry=secondary,
            now_epoch=int(now),
        )
        effective_secondary = normalized.effective_secondary_entry
        # Weekly-only/free accounts have no short window. A missing Plus short
        # sample, however, is unknown rather than evidence of an absent window.
        primary_applicable = usage_core.capacity_for_plan(account.plan_type, "primary") != 0 and not (
            primary is not None and effective_secondary is primary and normalized.primary_used is None
        )
        observed_rows = [row for row in (primary, effective_secondary) if row is not None]
        sample_at = sum(row.recorded_at.replace(tzinfo=timezone.utc).timestamp() for row in observed_rows)
        snapshot = account_spend_control(account)
        control = snapshot.control if snapshot is not None else None
        budget_only = control is not None and snapshot is not None and not snapshot.rate_limit_present
        budget_percent = spend_control_remaining_percent(control) if control is not None else None
        if account.spend_control_snapshot is not None:
            budget_sample = account.spend_control_snapshot.observed_at.replace(tzinfo=timezone.utc).timestamp()
            sample_at = budget_sample if budget_only else sample_at + budget_sample
        candidates.append(
            QuotaCandidate(
                account_id=account.id,
                plan_type=account.plan_type,
                primary_remaining=remaining_fraction(normalized.primary_used) if primary_applicable else None,
                weekly_remaining=remaining_fraction(normalized.secondary_used),
                primary_applicable=primary_applicable,
                sample_at=sample_at,
                budget_remaining=budget_percent / 100 if budget_percent is not None else None,
                budget_only=budget_only,
                invalid_quota=not budget_only
                and any(
                    value is not None and not math.isfinite(value)
                    for value in (
                        normalized.primary_used,
                        normalized.secondary_used,
                    )
                ),
            )
        )
    candidates.extend(
        QuotaCandidate(
            account_id=virtual_account_id(source.id),
            plan_type="other",
            primary_remaining=None,
            weekly_remaining=1.0,
            primary_applicable=False,
            placeholder=True,
        )
        for source in sources
    )
    async with get_background_session() as session:
        return await RoutingRulesRepository(session).decisions(candidates)


def apply_priority_decisions(states: list[AccountState], decisions: Mapping[str, RoutingDecision]) -> None:
    for state in states:
        decision = decisions.get(state.account_id)
        if decision is not None:
            state.routing_priority = decision.priority
            state.routing_remaining_fraction = decision.remaining
            state.routing_allow_new = decision.allow_new

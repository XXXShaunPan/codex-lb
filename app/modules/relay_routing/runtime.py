from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from datetime import timezone
from typing import TYPE_CHECKING

from app.core import usage as usage_core
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
        candidates.append(
            QuotaCandidate(
                account_id=account.id,
                plan_type=account.plan_type,
                primary_remaining=remaining_fraction(normalized.primary_used) if primary_applicable else None,
                weekly_remaining=remaining_fraction(normalized.secondary_used),
                primary_applicable=primary_applicable,
                sample_at=sample_at,
                invalid_quota=any(
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

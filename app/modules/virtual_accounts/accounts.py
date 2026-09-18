from __future__ import annotations

import functools
from typing import Any

from app.modules.virtual_accounts.identity import (
    _DEFAULT_SOURCE_CAPACITY_CREDITS,
    virtual_account_id,
)


async def _virtual_account_summaries() -> list[Any]:
    from app.db.session import detach_session_objects, get_background_session
    from app.modules.accounts.schemas import AccountSummary, AccountUsage
    from app.modules.model_sources.repository import ModelSourcesRepository

    async with get_background_session() as session:
        sources = await ModelSourcesRepository(session).list_sources()
        detach_session_objects(session)
    return [
        AccountSummary(
            account_id=virtual_account_id(source.id),
            chatgpt_account_id=None,
            email=source.name,
            alias=source.name,
            display_name=source.name,
            workspace_id=source.id,
            workspace_label="Model Source",
            seat_type=None,
            plan_type="other",
            routing_policy="normal",
            status="active" if source.is_enabled else "paused",
            usage=AccountUsage(
                primary_remaining_percent=None,
                secondary_remaining_percent=100.0,
                monthly_remaining_percent=None,
            ),
            reset_at_primary=None,
            reset_at_secondary=None,
            reset_at_monthly=None,
            window_minutes_primary=None,
            window_minutes_secondary=10080,
            window_minutes_monthly=None,
            capacity_credits_primary=0.0,
            remaining_credits_primary=0.0,
            capacity_credits_secondary=_DEFAULT_SOURCE_CAPACITY_CREDITS,
            remaining_credits_secondary=_DEFAULT_SOURCE_CAPACITY_CREDITS,
            capacity_credits_monthly=0.0,
            remaining_credits_monthly=0.0,
            credits_has=False,
            credits_unlimited=True,
            credits_balance=None,
            request_usage=None,
            auth=None,
            additional_quotas=[],
            limit_warmup_enabled=False,
            limit_warmup=None,
            is_email_duplicate=False,
            available_reset_credits=0,
            reset_credit_nearest_expires_at=None,
        )
        for source in sources
    ]


def with_source_accounts(native):
    @functools.wraps(native)
    async def list_accounts_with_sources(*args, **kwargs):
        response = await native(*args, **kwargs)
        existing = {item.account_id for item in response.accounts}
        response.accounts.extend(item for item in await _virtual_account_summaries() if item.account_id not in existing)
        return response

    import inspect

    list_accounts_with_sources.__dict__["__signature__"] = inspect.signature(native, eval_str=True)
    return list_accounts_with_sources


async def project_dashboard(response):
    from app.modules.usage.schemas import UsageHistoryItem, UsageWindow, UsageWindowResponse

    existing = {item.account_id for item in response.accounts}
    sources = [item for item in await _virtual_account_summaries() if item.account_id not in existing]
    response.accounts.extend(sources)
    if not sources:
        return response
    if response.windows.secondary is None:
        response.windows.secondary = UsageWindowResponse(window_key="secondary", window_minutes=10080)
    response.windows.secondary.accounts.extend(
        UsageHistoryItem(
            account_id=source.account_id,
            remaining_percent_avg=100.0,
            capacity_credits=source.capacity_credits_secondary,
            remaining_credits=source.remaining_credits_secondary,
        )
        for source in sources
    )
    capacity = sum(source.capacity_credits_secondary for source in sources)
    remaining = sum(source.remaining_credits_secondary for source in sources)
    summary = response.summary.secondary_window
    if summary is None:
        summary = UsageWindow(remaining_percent=100, capacity_credits=0, remaining_credits=0, window_minutes=10080)
        response.summary.secondary_window = summary
    summary.capacity_credits += capacity
    summary.remaining_credits += remaining
    summary.remaining_percent = summary.remaining_credits / summary.capacity_credits * 100
    pace = response.weekly_credit_pace
    if pace is not None:
        pace.total_full_credits += capacity
        pace.total_actual_remaining_credits += remaining
        pace.total_expected_remaining_credits += remaining
        pace.actual_used_percent = (1 - pace.total_actual_remaining_credits / pace.total_full_credits) * 100
        pace.account_count += len(sources)
    return response

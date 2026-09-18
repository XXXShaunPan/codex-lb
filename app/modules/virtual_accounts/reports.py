from __future__ import annotations

import dataclasses
import functools
import statistics
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from typing import Any, Iterable, Sequence, TypedDict

from app.modules.virtual_accounts.identity import (
    split_virtual_account_ids,
    virtual_account_id,
)


class ReportQuery(TypedDict):
    account_ids: list[str] | None
    model: str | None
    useragent_group: str | None
    api_key_ids: list[str] | None


def _virtual_filter_clause(account_ids: Sequence[str] | None):
    from sqlalchemy import and_, false, func, or_, select

    from app.db.models import ApiKeyModelSourceAssignment, RequestLog

    real_ids, source_ids = split_virtual_account_ids(account_ids)
    clauses = []
    if real_ids:
        clauses.append(RequestLog.account_id.in_(real_ids))
    if source_ids:
        source_scoped_key_ids = select(ApiKeyModelSourceAssignment.api_key_id).where(
            ApiKeyModelSourceAssignment.source_id.in_(source_ids)
        )
        assignment_count = (
            select(func.count())
            .select_from(ApiKeyModelSourceAssignment)
            .where(ApiKeyModelSourceAssignment.api_key_id == RequestLog.api_key_id)
            .correlate(RequestLog)
            .scalar_subquery()
        )
        clauses.append(
            or_(
                RequestLog.model_source_id.in_(source_ids),
                and_(
                    RequestLog.account_id.is_(None),
                    RequestLog.model_source_id.is_(None),
                    RequestLog.error_code == "no_accounts",
                    RequestLog.api_key_id.in_(source_scoped_key_ids),
                    assignment_count == 1,
                ),
            )
        )
    return or_(*clauses) if clauses else false()


async def _query_report_logs(
    session: Any,
    *,
    start_at: datetime | None,
    end_at: datetime | None,
    account_ids: list[str] | None,
    model: str | None,
    useragent_group: str | None,
    api_key_ids: list[str] | None,
):
    from sqlalchemy import and_, select

    from app.db.models import RequestLog
    from app.modules.reports import repository as report_repository

    conditions = [report_repository._normal_traffic_clause()]
    if start_at is not None:
        conditions.append(RequestLog.requested_at >= start_at)
    if end_at is not None:
        conditions.append(RequestLog.requested_at < end_at)
    if account_ids:
        conditions.append(_virtual_filter_clause(account_ids))
    if model:
        conditions.append(RequestLog.model == model)
    useragent_clause = report_repository._useragent_group_filter_clause(useragent_group)
    if useragent_clause is not None:
        conditions.append(useragent_clause)
    if api_key_ids:
        conditions.append(RequestLog.api_key_id.in_(api_key_ids))
    result = await session.execute(select(RequestLog).where(and_(*conditions)))
    return list(result.scalars().all())


def _log_identity(log: Any) -> str | None:
    if log.account_id:
        return log.account_id
    if log.model_source_id:
        return virtual_account_id(log.model_source_id)
    return None


def _output_tokens(log: Any) -> int:
    if log.output_tokens is not None:
        return int(log.output_tokens)
    return int(log.reasoning_tokens or 0)


def _median(values: Iterable[float]) -> float:
    data = list(values)
    return float(statistics.median(data)) if data else 0.0


async def _build_reports(
    service: Any,
    *,
    start_date: date | None,
    end_date: date | None,
    report_timezone: str | None,
    account_ids: list[str] | None,
    model: str | None,
    useragent_group: str | None,
    api_key_ids: list[str] | None,
):
    from sqlalchemy import select

    from app.core.usage.logs import CANCELLED_STATUS, NON_ERROR_STATUSES
    from app.core.utils.time import utcnow
    from app.db.models import Account, ModelSource
    from app.modules.reports import service as report_service
    from app.modules.reports.schemas import (
        AccountCostEntry,
        DailyReportRow,
        ModelCostEntry,
        ReportComparison,
        ReportComparisonPrevious,
        ReportsResponse,
        ReportSummary,
        UserAgentCostEntry,
    )

    tz = report_service._resolve_timezone(report_timezone)
    now = utcnow().replace(tzinfo=timezone.utc).astimezone(tz)
    effective_end = end_date or now.date()
    effective_start = start_date or (effective_end - timedelta(days=6))
    if effective_start > effective_end:
        raise report_service.InvalidReportDateRangeError("start_date must be on or before end_date")
    window_days = (effective_end - effective_start).days + 1
    if window_days > 730:
        from app.modules.reports.repository import DailyReportRangeTooLargeError

        raise DailyReportRangeTooLargeError("report date range must be 730 days or less")

    start_at = report_service._local_midnight_to_utc_naive(effective_start, tz)
    end_at = report_service._local_midnight_to_utc_naive(effective_end + timedelta(days=1), tz)
    previous_end_date = effective_start - timedelta(days=1)
    previous_start_date = previous_end_date - timedelta(days=window_days - 1)
    previous_start_at = report_service._local_midnight_to_utc_naive(previous_start_date, tz)
    previous_end_at = report_service._local_midnight_to_utc_naive(previous_end_date + timedelta(days=1), tz)
    session = service._repository._session
    query_kwargs = ReportQuery(
        account_ids=account_ids,
        model=model,
        useragent_group=useragent_group,
        api_key_ids=api_key_ids,
    )
    logs = await _query_report_logs(session, start_at=start_at, end_at=end_at, **query_kwargs)
    previous_logs = await _query_report_logs(
        session,
        start_at=previous_start_at,
        end_at=previous_end_at,
        **query_kwargs,
    )
    all_matching_logs = await _query_report_logs(session, start_at=None, end_at=None, **query_kwargs)

    account_rows = (await session.execute(select(Account.id, Account.alias, Account.email))).all()
    source_rows = (await session.execute(select(ModelSource.id, ModelSource.name))).all()
    labels = {row.id: (row.alias or row.email) for row in account_rows}
    labels.update({virtual_account_id(row.id): row.name for row in source_rows})

    def total_cost(items):
        return sum(float(item.cost_usd or 0.0) for item in items)

    def total_tokens(items):
        return sum(int(item.input_tokens or 0) + _output_tokens(item) for item in items)

    by_day: dict[date, list[Any]] = defaultdict(list)
    for log in logs:
        instant = log.requested_at.replace(tzinfo=timezone.utc).astimezone(tz)
        by_day[instant.date()].append(log)

    daily: list[DailyReportRow] = []
    cursor = effective_start
    while cursor <= effective_end:
        items = by_day.get(cursor, [])
        ttfts = [float(item.latency_first_token_ms) for item in items if item.latency_first_token_ms is not None]
        queue_values = [float(item.latency_queue_ms) for item in items if item.latency_queue_ms is not None]
        tps_values = []
        for item in items:
            generated = _output_tokens(item) - int(item.reasoning_tokens or 0)
            duration = (
                int(item.latency_ms) - int(item.latency_first_token_ms)
                if item.latency_ms is not None and item.latency_first_token_ms is not None
                else 0
            )
            if generated > 0 and duration > 0:
                tps_values.append(generated * 1000.0 / duration)
        conversations = {
            item.conversation_id.strip()
            for item in items
            if isinstance(item.conversation_id, str) and item.conversation_id.strip()
        }
        daily.append(
            DailyReportRow(
                date=cursor.isoformat(),
                requests=len(items),
                input_tokens=sum(int(item.input_tokens or 0) for item in items),
                output_tokens=sum(_output_tokens(item) for item in items),
                reasoning_tokens=(
                    sum(int(item.reasoning_tokens or 0) for item in items)
                    if any(item.reasoning_tokens is not None for item in items)
                    else None
                ),
                cached_input_tokens=sum(int(item.cached_input_tokens or 0) for item in items),
                cost_usd=round(total_cost(items), 4),
                active_accounts=len({_log_identity(item) for item in items if _log_identity(item)}),
                conversations=len(conversations),
                error_count=sum(1 for item in items if item.status not in NON_ERROR_STATUSES),
                cancelled_count=sum(1 for item in items if item.status == CANCELLED_STATUS),
                median_ttft_ms=round(_median(ttfts), 2),
                median_tps=round(_median(tps_values), 2),
                median_queue_ms=round(_median(queue_values), 2),
            )
        )
        cursor += timedelta(days=1)

    by_model_raw: dict[str, list[Any]] = defaultdict(list)
    by_account_raw: dict[str | None, list[Any]] = defaultdict(list)
    by_useragent_raw: dict[str, list[Any]] = defaultdict(list)
    for log in logs:
        by_model_raw[log.model or "Unknown"].append(log)
        by_account_raw[_log_identity(log)].append(log)
        by_useragent_raw[log.useragent_group or "Missing User-Agent"].append(log)
    model_total = total_cost(logs)
    by_model = [
        ModelCostEntry(
            model=name,
            cost_usd=round(total_cost(items), 4),
            requests=len(items),
            percentage=round(total_cost(items) / model_total * 100, 1) if model_total > 0 else 0,
        )
        for name, items in sorted(by_model_raw.items(), key=lambda pair: total_cost(pair[1]), reverse=True)
    ]
    by_account = [
        AccountCostEntry(
            account_id=identity,
            alias=labels.get(identity),
            cost_usd=round(total_cost(items), 4),
            requests=len(items),
        )
        for identity, items in sorted(by_account_raw.items(), key=lambda pair: total_cost(pair[1]), reverse=True)
    ]
    by_useragent = [
        UserAgentCostEntry(
            useragent=name,
            cost_usd=round(total_cost(items), 4),
            requests=len(items),
            percentage=round(total_cost(items) / model_total * 100, 1) if model_total > 0 else 0,
        )
        for name, items in sorted(by_useragent_raw.items(), key=lambda pair: total_cost(pair[1]), reverse=True)
    ]

    conversations = {
        item.conversation_id.strip()
        for item in logs
        if isinstance(item.conversation_id, str) and item.conversation_id.strip()
    }
    previous_cost = total_cost(previous_logs)
    earliest = min((item.requested_at for item in all_matching_logs), default=None)
    return ReportsResponse(
        summary=ReportSummary(
            total_cost_usd=round(model_total, 4),
            total_input_tokens=sum(int(item.input_tokens or 0) for item in logs),
            total_output_tokens=sum(_output_tokens(item) for item in logs),
            total_reasoning_tokens=sum(int(item.reasoning_tokens or 0) for item in logs),
            reasoning_usage_known_requests=sum(1 for item in logs if item.reasoning_tokens is not None),
            total_cached_tokens=sum(int(item.cached_input_tokens or 0) for item in logs),
            total_requests=len(logs),
            total_errors=sum(1 for item in logs if item.status not in NON_ERROR_STATUSES),
            total_cancelled=sum(1 for item in logs if item.status == CANCELLED_STATUS),
            active_accounts=len({_log_identity(item) for item in logs if _log_identity(item)}),
            total_conversations=len(conversations),
            avg_cost_per_day=round(model_total / window_days, 4),
            avg_requests_per_day=round(len(logs) / window_days, 2),
        ),
        comparison=ReportComparison(
            can_compare=earliest is not None and earliest <= previous_start_at,
            previous=ReportComparisonPrevious(
                total_cost_usd=round(previous_cost, 4),
                total_tokens=total_tokens(previous_logs),
                total_requests=len(previous_logs),
            ),
        ),
        daily=daily,
        by_model=by_model,
        by_account=by_account,
        by_useragent=by_useragent,
    )


def with_virtual_reports(native):
    native = native

    async def get_reports(
        self,
        start_date=None,
        end_date=None,
        report_timezone=None,
        account_ids=None,
        model=None,
        useragent_group=None,
        api_key_ids=None,
    ):
        return await _build_reports(
            self,
            start_date=start_date,
            end_date=end_date,
            report_timezone=report_timezone,
            account_ids=account_ids,
            model=model,
            useragent_group=useragent_group,
            api_key_ids=api_key_ids,
        )

    return functools.wraps(native)(get_reports)


def with_source_cost_breakdown(native):
    native = native

    async def usage_7d(self, key_id, since, until):
        from sqlalchemy import func, select

        from app.db.models import ModelSource, RequestLog
        from app.modules.api_keys import repository as repository_module

        totals = await native(self, key_id, since, until)
        rows = (
            await self._session.execute(
                select(
                    RequestLog.model_source_id,
                    ModelSource.name,
                    func.coalesce(func.sum(RequestLog.cost_usd), 0.0).label("cost_usd"),
                )
                .outerjoin(ModelSource, ModelSource.id == RequestLog.model_source_id)
                .where(
                    RequestLog.api_key_id == key_id,
                    RequestLog.requested_at >= since,
                    RequestLog.requested_at < until,
                    RequestLog.model_source_id.is_not(None),
                    self._exclude_warmup_clause(),
                )
                .group_by(RequestLog.model_source_id, ModelSource.name)
            )
        ).all()
        source_total = sum((float(row.cost_usd or 0.0) for row in rows))
        adjusted = []
        remaining_to_remove = source_total
        for item in totals.account_costs:
            if item.account_id is None and (not item.is_deleted) and (remaining_to_remove > 0):
                residual = max(0.0, item.cost_usd - remaining_to_remove)
                remaining_to_remove = max(0.0, remaining_to_remove - item.cost_usd)
                if residual > 0:
                    adjusted.append(dataclasses.replace(item, cost_usd=round(residual, 6)))
            else:
                adjusted.append(item)
        for row in rows:
            cost = round(float(row.cost_usd or 0.0), 6)
            if cost <= 0:
                continue
            adjusted.append(
                repository_module.ApiKeyAccountCost(
                    account_id=virtual_account_id(row.model_source_id),
                    email=row.name or row.model_source_id,
                    cost_usd=cost,
                    is_deleted=False,
                )
            )
        adjusted.sort(key=lambda item: item.cost_usd, reverse=True)
        return dataclasses.replace(totals, account_costs=adjusted)

    return functools.wraps(native)(usage_7d)

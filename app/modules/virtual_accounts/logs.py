from __future__ import annotations

import dataclasses
import functools
from collections import defaultdict

from app.modules.virtual_accounts.identity import (
    source_id_from_virtual,
    virtual_account_id,
)
from app.modules.virtual_accounts.reports import _virtual_filter_clause


def with_virtual_identity(native):
    native_mapper = native

    def to_request_log_entry(log, *, api_key_name=None, include_sensitive_metadata):
        entry = native_mapper(log, api_key_name=api_key_name, include_sensitive_metadata=include_sensitive_metadata)
        if entry.account_id is None and entry.model_source_id:
            return entry.model_copy(
                update={"account_id": virtual_account_id(entry.model_source_id), "plan_type": "other"}
            )
        return entry

    return functools.wraps(native)(to_request_log_entry)


def with_virtual_filters(native):
    native_build_filters = native

    def build_filters(self, **kwargs):
        account_ids = kwargs.get("account_ids")
        if not account_ids:
            return native_build_filters(self, **kwargs)
        translated = dict(kwargs)
        translated["account_ids"] = None
        filters = native_build_filters(self, **translated)
        return dataclasses.replace(filters, conditions=[*filters.conditions, _virtual_filter_clause(account_ids)])

    return functools.wraps(native)(build_filters)


def with_virtual_pagination(native):
    native_list_recent = native

    async def list_recent(self, *args, **kwargs):
        account_ids = kwargs.get("account_ids")
        if account_ids and any((source_id_from_virtual(item) is not None for item in account_ids)):
            kwargs = dict(kwargs)
            if kwargs.get("search") is None:
                kwargs["search"] = ""
        return await native_list_recent(self, *args, **kwargs)

    return functools.wraps(native)(list_recent)


def with_virtual_options(native):
    native_list_filter_options = native

    async def list_filter_options(self, *args, **kwargs):
        account_ids, model_options, api_key_ids, statuses = await native_list_filter_options(self, *args, **kwargs)
        from sqlalchemy import select

        from app.db.models import ApiKey, RequestLog

        existing_api_key_ids = set()
        if api_key_ids:
            existing_api_key_ids = set(
                (await self._session.execute(select(ApiKey.id).where(ApiKey.id.in_(api_key_ids)))).scalars()
            )
        api_key_ids = [key_id for key_id in api_key_ids if key_id in existing_api_key_ids]
        source_ids = [
            value
            for value in (
                await self._session.execute(
                    select(RequestLog.model_source_id)
                    .where(RequestLog.model_source_id.is_not(None), RequestLog.deleted_at.is_(None))
                    .distinct()
                )
            ).scalars()
            if value
        ]
        combined = list(dict.fromkeys([*account_ids, *(virtual_account_id(item) for item in source_ids)]))
        return (combined, model_options, api_key_ids, statuses)

    return functools.wraps(native)(list_filter_options)


def with_historical_control_identity(native):
    native_service_list_recent = native

    async def service_list_recent(self, *args, **kwargs):
        from sqlalchemy import select

        from app.db.models import ApiKeyModelSourceAssignment

        page = await native_service_list_recent(self, *args, **kwargs)
        key_ids = {
            item.api_key_id
            for item in page.requests
            if item.account_id is None
            and item.model_source_id is None
            and (item.error_code == "no_accounts")
            and item.api_key_id
        }
        if not key_ids:
            return page
        rows = (
            await self._repo._session.execute(
                select(ApiKeyModelSourceAssignment.api_key_id, ApiKeyModelSourceAssignment.source_id).where(
                    ApiKeyModelSourceAssignment.api_key_id.in_(key_ids)
                )
            )
        ).all()
        sources_by_key: dict[str, list[str]] = defaultdict(list)
        for key_id, source_id in rows:
            sources_by_key[key_id].append(source_id)
        projected = []
        for item in page.requests:
            assigned_sources = sources_by_key.get(item.api_key_id or "", [])
            if (
                item.account_id is None
                and item.model_source_id is None
                and (item.error_code == "no_accounts")
                and (len(assigned_sources) == 1)
            ):
                source_id = assigned_sources[0]
                item = item.model_copy(
                    update={
                        "account_id": virtual_account_id(source_id),
                        "model_source_id": source_id,
                        "model_source_kind": "virtual_control_fallback",
                        "plan_type": "other",
                    }
                )
            projected.append(item)
        return dataclasses.replace(page, requests=projected)

    return functools.wraps(native)(service_list_recent)

from __future__ import annotations

import dataclasses
import functools
from typing import Any

from app.modules.virtual_accounts.continuity import _invalidate_api_key_continuity
from app.modules.virtual_accounts.identity import (
    _notice,
    split_virtual_account_ids,
    virtual_account_id,
)
from app.modules.virtual_accounts.routing import _route_affinity


async def _set_unified_scope(service: Any, key_id: str, enabled: bool) -> None:
    from app.core.cache.invalidation import NAMESPACE_API_KEY, get_cache_invalidation_poller

    await service._repository.update(
        key_id,
        account_assignment_scope_enabled=enabled,
        source_assignment_scope_enabled=enabled,
        commit=True,
    )
    poller = get_cache_invalidation_poller()
    if poller is not None:
        await poller.bump(NAMESPACE_API_KEY)


def create_with_unified_assignments(native):
    native_create = native

    async def create_key(self, payload):
        real_ids, virtual_source_ids = split_virtual_account_ids(payload.assigned_account_ids)
        explicit_source_ids = list(payload.assigned_source_ids or ())
        source_ids = list(dict.fromkeys([*virtual_source_ids, *explicit_source_ids]))
        unified_ids = list(payload.assigned_account_ids or ())
        translated = dataclasses.replace(payload, assigned_account_ids=real_ids, assigned_source_ids=source_ids)
        result = await native_create(self, translated)
        unified_scope = bool(unified_ids or explicit_source_ids)
        if unified_scope != (result.account_assignment_scope_enabled and result.source_assignment_scope_enabled):
            await _set_unified_scope(self, result.id, unified_scope)
            result = dataclasses.replace(
                result, account_assignment_scope_enabled=unified_scope, source_assignment_scope_enabled=unified_scope
            )
        return result

    return functools.wraps(native)(create_key)


def update_with_unified_assignments(native):
    native_update = native

    async def update_key(self, key_id, payload):
        assignment_changed = bool(payload.assigned_account_ids_set or payload.assigned_source_ids_set)
        unified_scope: bool | None = None
        translated = payload
        if payload.assigned_account_ids_set:
            real_ids, virtual_source_ids = split_virtual_account_ids(payload.assigned_account_ids)
            explicit_source_ids = list(payload.assigned_source_ids or ()) if payload.assigned_source_ids_set else []
            source_ids = list(dict.fromkeys([*virtual_source_ids, *explicit_source_ids]))
            unified_scope = bool(payload.assigned_account_ids or explicit_source_ids)
            translated = dataclasses.replace(
                payload, assigned_account_ids=real_ids, assigned_source_ids=source_ids, assigned_source_ids_set=True
            )
        result = await native_update(self, key_id, translated)
        if unified_scope is not None:
            await _set_unified_scope(self, key_id, unified_scope)
            result = dataclasses.replace(
                result, account_assignment_scope_enabled=unified_scope, source_assignment_scope_enabled=unified_scope
            )
        if assignment_changed:
            try:
                closed, inflight, durable = await _invalidate_api_key_continuity(key_id)
                _notice(
                    f"API key assignment continuity invalidated key_id={key_id} "
                    f"live={closed} inflight={inflight} durable={durable}"
                )
            except Exception as exc:
                _route_affinity.clear()
                _notice(
                    "API key assignment was saved, but continuity invalidation fell back to startup sweep: "
                    f"{type(exc).__name__}: {exc}"
                )
        return result

    return functools.wraps(native)(update_key)


def unified_key_response(native):
    native_to_response = native

    def to_response(row):
        response = native_to_response(row)
        combined_ids = [*row.assigned_account_ids, *(virtual_account_id(item) for item in row.assigned_source_ids)]
        updates = {
            "assigned_account_ids": combined_ids,
            "assigned_source_ids": [],
            "account_assignment_scope_enabled": bool(
                row.account_assignment_scope_enabled or row.source_assignment_scope_enabled
            ),
            "source_assignment_scope_enabled": False,
        }
        if row.assigned_source_ids and (not row.assigned_account_ids):
            updates.update(
                pooled_remaining_percent_primary=None,
                pooled_remaining_percent_secondary=100.0,
                pooled_capacity_credits_primary=0.0,
            )
        return response.model_copy(update=updates)

    return functools.wraps(native)(to_response)

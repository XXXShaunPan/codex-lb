from __future__ import annotations

import asyncio
import functools
import logging
from typing import Any

from app.modules.virtual_accounts.identity import (
    _notice,
)
from app.modules.virtual_accounts.routing import _route_affinity


async def _evict_http_bridge_sessions_for_api_key(proxy: Any, key_id: str) -> tuple[int, int]:
    """Detach live HTTP bridge generations created under an older key policy."""

    from app.core.clients.proxy import ProxyResponseError
    from app.core.errors import openai_error

    sessions_to_close: list[Any] = []
    scheduled_ids: set[int] = set()
    inflight_futures: list[asyncio.Future[Any]] = []
    invalidated = ProxyResponseError(
        503,
        openai_error(
            "api_key_assignment_changed",
            "API key account assignment changed; retry on the new route",
            error_type="server_error",
        ),
    )
    async with proxy._http_bridge_lock:
        for key, session in tuple(proxy._http_bridge_sessions.items()):
            if getattr(key, "api_key_id", None) != key_id:
                continue
            detached = proxy._detach_http_bridge_session_locked(key, expected_session=session)
            if detached is None:
                continue
            sessions_to_close.append(detached)
            scheduled_ids.add(id(detached))
        for session in tuple(proxy._http_bridge_detached_sessions.values()):
            if getattr(getattr(session, "key", None), "api_key_id", None) != key_id:
                continue
            if id(session) in scheduled_ids:
                continue
            close_task = getattr(session, "resource_close_task", None)
            if close_task is not None and (
                not close_task.done() or (not close_task.cancelled() and close_task.exception() is None)
            ):
                continue
            session.closed = True
            sessions_to_close.append(session)
            scheduled_ids.add(id(session))
        for key, future in tuple(proxy._http_bridge_inflight_sessions.items()):
            if getattr(key, "api_key_id", None) != key_id or getattr(future, "_http_bridge_handoff", False):
                continue
            proxy._http_bridge_inflight_sessions.pop(key, None)
            inflight_futures.append(future)
            if not future.done():
                future.set_exception(invalidated)
                future.exception()

    for session in sessions_to_close:
        await proxy._close_http_bridge_session_bounded(session, reason="api_key_assignment_changed")
    return len(sessions_to_close), len(inflight_futures)


async def _reset_durable_http_bridge_scope(key_id: str) -> int:
    """Delete persisted continuity so a new assignment can select a new owner.

    A CLOSED row with ``account_id=NULL`` is still a durable lookup hit for a
    hard Codex thread header.  Native bridge safety then correctly treats the
    missing owner as fatal.  Assignment changes intentionally invalidate that
    conversation scope, so remove the canonical rows as well as their aliases
    and operation journal instead of leaving ownerless tombstones.
    """

    from sqlalchemy import delete, select

    from app.db.models import HttpBridgeSessionAlias, HttpBridgeSessionRecord
    from app.db.session import get_background_session, sqlite_writer_section

    async with get_background_session() as session:
        session_ids = list(
            (
                await session.execute(
                    select(HttpBridgeSessionRecord.id).where(HttpBridgeSessionRecord.api_key_scope == key_id)
                )
            ).scalars()
        )
        if not session_ids:
            return 0
        async with sqlite_writer_section():
            await session.execute(
                delete(HttpBridgeSessionAlias).where(HttpBridgeSessionAlias.session_id.in_(session_ids))
            )
            result = await session.execute(
                delete(HttpBridgeSessionRecord).where(HttpBridgeSessionRecord.id.in_(session_ids))
            )
            await session.commit()
        return int(getattr(result, "rowcount", 0) or 0)


async def _invalidate_api_key_continuity(key_id: str) -> tuple[int, int, int]:
    """Invalidate all route state whose policy identity is the API key."""

    from app.dependencies import get_proxy_service_for_app
    from app.main import app

    _route_affinity.clear()
    proxy = get_proxy_service_for_app(app)
    closed, inflight = await _evict_http_bridge_sessions_for_api_key(proxy, key_id)
    durable = await _reset_durable_http_bridge_scope(key_id)
    return closed, inflight, durable


async def _sweep_ineligible_durable_continuity() -> None:
    """Clear pre-existing owners that no longer belong to an API key scope."""

    from sqlalchemy import exists, or_, select

    from app.db.models import ApiKey, ApiKeyAccountAssignment, HttpBridgeSessionRecord
    from app.db.session import get_background_session

    async with get_background_session() as session:
        assigned_owner = exists().where(
            ApiKeyAccountAssignment.api_key_id == HttpBridgeSessionRecord.api_key_scope,
            ApiKeyAccountAssignment.account_id == HttpBridgeSessionRecord.account_id,
        )
        key_ids = list(
            (
                await session.execute(
                    select(HttpBridgeSessionRecord.api_key_scope)
                    .join(ApiKey, ApiKey.id == HttpBridgeSessionRecord.api_key_scope)
                    .where(
                        ApiKey.account_assignment_scope_enabled.is_(True),
                        or_(
                            # Compatibility cleanup for the first assignment-
                            # invalidation release, which closed rows after
                            # clearing account_id.  Those hard-key tombstones
                            # make native lookup fail before current-policy
                            # account selection can run.
                            HttpBridgeSessionRecord.account_id.is_(None),
                            ~assigned_owner,
                        ),
                    )
                    .distinct()
                )
            ).scalars()
        )
    reset_rows = 0
    for key_id in key_ids:
        reset_rows += await _reset_durable_http_bridge_scope(key_id)
    if key_ids:
        _notice(f"startup cleared stale HTTP continuity for {len(key_ids)} API key scope(s), rows={reset_rows}")


def _empty_closed_durable_lookup_can_be_ignored(
    lookup: Any,
    *,
    previous_response_id: str | None,
) -> bool:
    """Identify an ownerless bridge shell that carries no continuity proof.

    Early versions of the assignment invalidation closed bridge rows after
    clearing their owner and anchor fields.  A hard thread key still resolves
    those rows, so a later model transition mistakes an empty historical shell
    for required owner evidence.  Do not soften real response continuity: an
    explicit previous_response_id, live/owned row, response/turn anchor, input
    fingerprint, or pending tool call keeps the native fail-closed behavior.
    """

    state = getattr(lookup, "state", None)
    state_value = getattr(state, "value", state)
    return bool(
        previous_response_id is None
        and state_value == "closed"
        and getattr(lookup, "account_id", None) is None
        and getattr(lookup, "owner_instance_id", None) is None
        and getattr(lookup, "lease_expires_at", None) is None
        and getattr(lookup, "latest_response_id", None) is None
        and getattr(lookup, "latest_turn_state", None) is None
        and getattr(lookup, "latest_input_item_count", None) is None
        and getattr(lookup, "latest_input_full_fingerprint", None) is None
        and not getattr(lookup, "latest_pending_tool_calls", None)
    )


def ignore_empty_tombstones(native):
    native = native

    async def lookup_request_targets(self, *args, **kwargs):
        from app.modules.proxy.durable_bridge_repository import durable_bridge_hash

        lookup = await native(self, *args, **kwargs)
        previous_response_id = kwargs.get("previous_response_id")
        if lookup is None or not _empty_closed_durable_lookup_can_be_ignored(
            lookup, previous_response_id=previous_response_id
        ):
            return lookup
        logging.getLogger("app.modules.proxy.service").info(
            "Ignoring context-free closed HTTP bridge tombstone bridge_kind=%s "
            "bridge_key=sha256:%s api_key_scope=%s model=%s",
            getattr(lookup, "canonical_kind", None),
            durable_bridge_hash(str(getattr(lookup, "canonical_key", "")))[:12],
            getattr(lookup, "api_key_scope", None),
            getattr(lookup, "model", None),
        )
        return None

    return functools.wraps(native)(lookup_request_targets)

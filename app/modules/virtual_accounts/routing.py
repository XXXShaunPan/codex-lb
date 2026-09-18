from __future__ import annotations

import contextvars
import dataclasses
import functools
import hashlib
import statistics
import time
from typing import Any, Sequence

from app.modules.virtual_accounts.identity import (
    _DEFAULT_SOURCE_CAPACITY_CREDITS,
    virtual_account_id,
)

_source_last_selected: dict[str, float] = {}
_ROUTE_AFFINITY_TTL_SECONDS = 6 * 60 * 60
_route_affinity_context: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "relay_route_affinity", default=None
)
_route_affinity: dict[str, tuple[float, str]] = {}


async def _eligible_sources(
    *,
    route: str,
    model: str,
    api_key: Any | None,
    raw_model: str | None = None,
    require_streaming: bool = False,
) -> list[tuple[Any, str]]:
    from app.db.session import detach_session_objects, get_background_session
    from app.modules.model_sources.repository import ModelSourcesRepository

    if api_key is not None and api_key.account_assignment_scope_enabled:
        allowed_source_ids: set[str] | None = set(api_key.assigned_source_ids)
    elif api_key is not None and api_key.source_assignment_scope_enabled:
        allowed_source_ids = set(api_key.assigned_source_ids)
    else:
        allowed_source_ids = None
    exact_allowed_models = set(api_key.allowed_models) if api_key and api_key.allowed_models else None
    candidates = list(dict.fromkeys(candidate for candidate in (raw_model, model) if candidate))
    if not candidates or allowed_source_ids == set():
        return []

    async with get_background_session() as session:
        sources = await ModelSourcesRepository(session).list_enabled_sources()
        detach_session_objects(session)

    result: list[tuple[Any, str]] = []
    for source in sorted(sources, key=lambda item: (item.name, item.id)):
        if allowed_source_ids is not None and source.id not in allowed_source_ids:
            continue
        if route == "responses" and not source.supports_responses:
            continue
        if route == "chat" and not source.supports_chat_completions:
            continue
        if route == "audio" and not source.supports_audio_transcriptions:
            continue
        for candidate in candidates:
            if exact_allowed_models is not None and candidate not in exact_allowed_models:
                continue
            entry = next(
                (
                    item
                    for item in source.models
                    if item.model == candidate
                    and item.is_enabled
                    and (not require_streaming or item.supports_streaming)
                ),
                None,
            )
            if entry is not None:
                result.append((source, candidate))
                break
    return result


def _source_capacity(real_states: Sequence[Any]) -> float:
    capacities = [float(state.capacity_credits) for state in real_states if (state.capacity_credits or 0.0) > 0.0]
    if not capacities:
        return _DEFAULT_SOURCE_CAPACITY_CREDITS
    return float(statistics.median(capacities))


async def _choose_virtual_candidate(
    *,
    model: str,
    api_key: Any | None,
    sources: Sequence[tuple[Any, str]],
) -> tuple[Any, str] | None:
    """Return a selected source, or None when the shared strategy chose an account."""

    affinity_key = _route_affinity_context.get()
    if affinity_key is not None:
        now = time.monotonic()
        cutoff = now - _ROUTE_AFFINITY_TTL_SECONDS
        for key, (selected_at, _target) in list(_route_affinity.items()):
            if selected_at < cutoff:
                _route_affinity.pop(key, None)
        cached = _route_affinity.get(affinity_key)
        if cached is not None:
            _selected_at, target = cached
            if target == "account":
                _route_affinity[affinity_key] = (now, target)
                return None
            for source, selected_model in sources:
                if source.id == target:
                    _route_affinity[affinity_key] = (now, target)
                    return source, selected_model
            _route_affinity.pop(affinity_key, None)

    from app.core.balancer.logic import AccountState
    from app.core.config.settings_cache import get_settings_cache
    from app.db.models import AccountStatus
    from app.dependencies import get_proxy_service_for_app
    from app.main import app
    from app.modules.proxy import load_balancer as lb_module
    from app.modules.proxy import service as proxy_service_module
    from app.modules.proxy._load_balancer.sticky_selection import _select_account_preferring_budget_safe

    proxy = get_proxy_service_for_app(app)
    load_balancer = proxy._load_balancer
    scoped_account_ids = (
        set(api_key.assigned_account_ids) if api_key is not None and api_key.account_assignment_scope_enabled else None
    )
    selection_inputs = await load_balancer._load_selection_inputs(
        model=model,
        service_tier=None,
        account_ids=scoped_account_ids,
    )
    settings = await get_settings_cache().get()

    async with load_balancer._runtime_lock:
        real_states, _account_map = lb_module._build_states(
            accounts=selection_inputs.accounts,
            latest_primary=selection_inputs.latest_primary,
            latest_secondary=selection_inputs.latest_secondary,
            latest_monthly=selection_inputs.latest_monthly,
            runtime=load_balancer._runtime,
            routing_policy_override=selection_inputs.routing_policy_override,
            ignore_standard_quota_account_ids=selection_inputs.ignore_standard_quota_account_ids,
        )

    capacity = _source_capacity(real_states)
    source_by_virtual_id: dict[str, tuple[Any, str]] = {}
    virtual_states: list[AccountState] = []
    for source, selected_model in sources:
        account_id = virtual_account_id(source.id)
        source_by_virtual_id[account_id] = (source, selected_model)
        virtual_states.append(
            AccountState(
                account_id=account_id,
                status=AccountStatus.ACTIVE,
                used_percent=None,
                secondary_used_percent=0.0,
                plan_type="other",
                capacity_credits=capacity,
                last_selected_at=_source_last_selected.get(source.id),
                routing_policy="normal",
            )
        )

    all_states = [*real_states, *virtual_states]
    if not all_states:
        return None
    traffic_class = getattr(api_key, "traffic_class", "foreground") if api_key is not None else "foreground"
    selection = _select_account_preferring_budget_safe(
        all_states,
        prefer_earlier_reset=bool(getattr(settings, "prefer_earlier_reset_accounts", False)),
        prefer_earlier_reset_window=proxy_service_module._prefer_earlier_reset_window(settings),
        routing_strategy=proxy_service_module._routing_strategy(settings),
        relative_availability_power=proxy_service_module._relative_availability_power(settings),
        relative_availability_top_k=proxy_service_module._relative_availability_top_k(settings),
        budget_threshold_pct=float(getattr(settings, "sticky_primary_threshold_pct", 95.0)),
        secondary_budget_threshold_pct=float(getattr(settings, "sticky_secondary_threshold_pct", 100.0)),
        apply_secondary_budget_threshold=True,
        traffic_class=traffic_class,
    )
    if selection.account is None:
        fallback = sources[0] if not real_states else None
        if affinity_key is not None and fallback is not None:
            _route_affinity[affinity_key] = (time.monotonic(), fallback[0].id)
        return fallback
    selected = source_by_virtual_id.get(selection.account.account_id)
    if selected is None:
        if affinity_key is not None:
            _route_affinity[affinity_key] = (time.monotonic(), "account")
        return None
    _source_last_selected[selected[0].id] = time.time()
    if affinity_key is not None:
        _route_affinity[affinity_key] = (time.monotonic(), selected[0].id)
    return selected


def unified_responses(native):
    native_responses = native
    native_responses_supports_only_disabled = True

    async def select_responses_model_source(
        model: str,
        api_key: Any | None,
        *,
        raw_model: str | None = None,
        require_streaming: bool = False,
        only_disabled: bool = False,
    ):
        if only_disabled:
            if not native_responses_supports_only_disabled:
                return None
            return await native_responses(
                model, api_key, raw_model=raw_model, require_streaming=require_streaming, only_disabled=True
            )
        sources = await _eligible_sources(
            route="responses",
            model=model,
            raw_model=raw_model,
            api_key=api_key,
            require_streaming=require_streaming,
        )
        if not sources:
            return None
        return await _choose_virtual_candidate(model=model, api_key=api_key, sources=sources)

    return functools.wraps(native)(select_responses_model_source)


def unified_chat(native):
    native_chat = native
    native_chat_supports_only_disabled = True

    async def select_chat_model_source(
        model: str,
        api_key: Any | None,
        *,
        raw_model: str | None = None,
        require_streaming: bool = False,
        only_disabled: bool = False,
    ):
        if only_disabled:
            if not native_chat_supports_only_disabled:
                return None
            return await native_chat(
                model, api_key, raw_model=raw_model, require_streaming=require_streaming, only_disabled=True
            )
        sources = await _eligible_sources(
            route="chat", model=model, raw_model=raw_model, api_key=api_key, require_streaming=require_streaming
        )
        if not sources:
            return None
        return await _choose_virtual_candidate(model=model, api_key=api_key, sources=sources)

    return functools.wraps(native)(select_chat_model_source)


def unified_audio(native):

    async def select_audio_model_source(model: str, api_key: Any | None):
        sources = await _eligible_sources(route="audio", model=model, api_key=api_key)
        if not sources:
            return None
        selected = await _choose_virtual_candidate(model=model, api_key=api_key, sources=sources)
        return selected[0] if selected is not None else None

    return functools.wraps(native)(select_audio_model_source)


def with_route_affinity(native):
    async def with_virtual_route_affinity(*args, **kwargs):
        from app.modules.proxy.api import _request_log_client_fields

        request = kwargs.get("request")
        payload = kwargs.get("payload")
        api_key = kwargs.get("api_key")
        token = None
        if request is not None:
            try:
                conversation_id = _request_log_client_fields(request.headers)[2]
            except Exception:
                conversation_id = None
            if not conversation_id:
                for header in ("x-codex-turn-state", "x-codex-session-id", "session_id", "conversation_id"):
                    value = request.headers.get(header)
                    if value and value.strip():
                        conversation_id = value.strip()
                        break
            model = payload.get("model") if isinstance(payload, dict) else getattr(payload, "model", None)
            key_id = getattr(api_key, "id", None) or "anonymous"
            if conversation_id:
                material = f"{key_id}\x00{conversation_id}\x00{model or ''}".encode("utf-8", errors="ignore")
                token = _route_affinity_context.set(hashlib.sha256(material).hexdigest())
        try:
            return await native(*args, **kwargs)
        finally:
            if token is not None:
                _route_affinity_context.reset(token)

    wrapped = functools.wraps(native)(with_virtual_route_affinity)
    import inspect

    wrapped.__dict__["__signature__"] = inspect.signature(native, eval_str=True)
    return wrapped


def account_control_fallback(native):
    native = native

    async def select_account_with_virtual_control_fallback(self, deadline, **kwargs):
        api_key = kwargs.get("api_key")
        kind = str(kwargs.get("kind") or "")
        model = kwargs.get("model")
        source_only_scope = bool(
            api_key is not None
            and api_key.account_assignment_scope_enabled
            and (not api_key.assigned_account_ids)
            and api_key.assigned_source_ids
        )
        account_only_control = model is None or kind.startswith("codex_control_")
        if source_only_scope and account_only_control:
            kwargs = dict(kwargs)
            kwargs["api_key"] = dataclasses.replace(api_key, account_assignment_scope_enabled=False)
        return await native(self, deadline, **kwargs)

    return functools.wraps(native)(select_account_with_virtual_control_fallback)

"""Scoped API-key regeneration for native Codex configuration generation."""

from __future__ import annotations

import asyncio
import time
from typing import Any

from app.modules.visitor_access.service import _json_response, _require_admin, _visitor_from_cookie

_codex_config_rotate_lock = asyncio.Lock()
_recent_codex_config_rotations: dict[str, float] = {}


async def _regenerate_api_key_for_codex(key_id: str) -> dict[str, Any]:
    from app.db.session import get_background_session
    from app.modules.api_keys.repository import ApiKeysRepository
    from app.modules.api_keys.service import ApiKeyNotFoundError, ApiKeysService
    from app.modules.usage.repository import UsageRepository

    async with get_background_session() as session:
        repository = ApiKeysRepository(session)
        current = await repository.get_by_id(key_id)
        if current is None:
            raise LookupError(f"API key not found: {key_id}")
        if not bool(current.is_active):
            raise ValueError("Inactive API keys cannot be configured for Codex")
        service = ApiKeysService(repository, usage_repository=UsageRepository(session))
        try:
            regenerated = await service.regenerate_key(key_id)
        except ApiKeyNotFoundError as exc:
            raise LookupError(str(exc)) from exc
    return {
        "id": regenerated.id,
        "name": regenerated.name,
        "key": regenerated.key,
        "keyPrefix": regenerated.key_prefix,
        "allowedModels": regenerated.allowed_models,
        "enforcedModel": regenerated.enforced_model,
    }


async def _codex_config_endpoint(request: Any):
    if request.method.upper() != "POST":
        return _json_response({"error": {"code": "method_not_allowed", "message": "Method not allowed"}}, 405)
    try:
        payload = await request.json()
    except Exception:
        return _json_response({"error": {"code": "invalid_payload", "message": "A JSON payload is required"}}, 422)
    key_id = str(payload.get("apiKeyId") or "").strip()
    if not key_id or len(key_id) > 128:
        return _json_response(
            {"error": {"code": "invalid_api_key_id", "message": "A valid API key id is required"}}, 422
        )
    if payload.get("confirmReset") is not True:
        return _json_response(
            {
                "error": {
                    "code": "reset_confirmation_required",
                    "message": "Confirm that the existing API key and all previous configurations will stop working",
                }
            },
            409,
        )

    visitor = await _visitor_from_cookie(request)
    actor = "admin"
    if visitor is not None:
        if key_id not in visitor.api_key_ids:
            return _json_response(
                {"error": {"code": "visitor_key_denied", "message": "API key is not assigned to this visitor"}},
                403,
            )
        actor = f"visitor:{visitor.id}"
    else:
        try:
            await _require_admin(request)
        except Exception:
            return _json_response(
                {
                    "error": {
                        "code": "admin_access_required",
                        "message": "Administrator or assigned visitor access is required",
                    }
                },
                403,
            )

    now = time.monotonic()
    for stale_key, rotated_at in list(_recent_codex_config_rotations.items()):
        if now - rotated_at > 60:
            _recent_codex_config_rotations.pop(stale_key, None)
    if now - _recent_codex_config_rotations.get(key_id, -60.0) < 10:
        return _json_response(
            {
                "error": {
                    "code": "api_key_recently_reset",
                    "message": "This API key was just reset. Use the newly generated command.",
                }
            },
            409,
        )
    if _codex_config_rotate_lock.locked():
        return _json_response(
            {"error": {"code": "api_key_reset_in_progress", "message": "Another API key reset is in progress"}},
            409,
        )

    async with _codex_config_rotate_lock:
        try:
            result = await _regenerate_api_key_for_codex(key_id)
        except LookupError as exc:
            return _json_response({"error": {"code": "api_key_not_found", "message": str(exc)}}, 404)
        except ValueError as exc:
            return _json_response({"error": {"code": "api_key_inactive", "message": str(exc)}}, 409)
        _recent_codex_config_rotations[key_id] = time.monotonic()

    try:
        from app.core.audit.service import AuditService

        AuditService.log_async(
            "api_key_regenerated_for_codex",
            actor_ip=request.client.host if request.client else None,
            details={"key_id": key_id, "actor": actor},
        )
    except Exception:
        pass
    return _json_response({"apiKey": result})

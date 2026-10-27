"""Scoped reuse or explicitly confirmed rotation of persisted API tokens."""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import time
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, StrictBool, ValidationError
from starlette.requests import Request

from app.core.exceptions import DashboardAuthError, DashboardPermissionError
from app.core.utils.time import utcnow
from app.db.models import ApiKey
from app.db.session import get_background_session
from app.modules.api_keys.repository import ApiKeysRepository
from app.modules.api_keys.service import ApiKeysService
from app.modules.codex_config.models import CodexApiToken
from app.modules.usage.repository import UsageRepository
from app.modules.visitor_access.service import _json_response, _require_admin, _visitor_from_cookie

_codex_config_rotate_lock = asyncio.Lock()
_recent_codex_config_rotations: dict[str, float] = {}


class ConfigRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    api_key_id: str = Field(alias="apiKeyId", min_length=1, max_length=128)
    reset_key: StrictBool = Field(default=False, alias="resetKey")
    confirm_reset: StrictBool = Field(default=False, alias="confirmReset")


def _validate_active(row: ApiKey | None) -> ApiKey:
    if row is None:
        raise LookupError("API key not found")
    if not row.is_active:
        raise ValueError("Inactive API keys cannot be configured for Codex")
    if row.expires_at is not None and row.expires_at <= utcnow():
        raise ValueError("Expired API keys cannot be configured for Codex")
    return row


async def _stored_key(key_id: str) -> dict[str, Any] | None:
    async with get_background_session() as session:
        row = _validate_active(await ApiKeysRepository(session).get_by_id(key_id))
        saved = await session.get(CodexApiToken, key_id)
        if saved is None or not hmac.compare_digest(hashlib.sha256(saved.token.encode()).hexdigest(), row.key_hash):
            return None
        return {
            "id": row.id,
            "name": row.name,
            "key": saved.token,
            "keyPrefix": row.key_prefix,
            "enforcedModel": row.enforced_model,
        }


async def _regenerate_api_key_for_codex(key_id: str) -> dict[str, Any]:
    async with get_background_session() as session:
        repo = ApiKeysRepository(session)
        _validate_active(await repo.get_by_id(key_id))
        service = ApiKeysService(repo, usage_repository=UsageRepository(session))
        regenerated = await service.regenerate_key(key_id)
        return {
            "id": regenerated.id,
            "name": regenerated.name,
            "key": regenerated.key,
            "keyPrefix": regenerated.key_prefix,
            "enforcedModel": regenerated.enforced_model,
        }


async def _actor(request: Request, key_id: str) -> str:
    visitor = await _visitor_from_cookie(request)
    if visitor is not None:
        if key_id not in visitor.api_key_ids:
            raise PermissionError("API key is not assigned to this visitor")
        return f"visitor:{visitor.id}"
    try:
        await _require_admin(request)
    except (DashboardAuthError, DashboardPermissionError) as exc:
        raise PermissionError("Administrator or assigned visitor access is required") from exc
    return "admin"


async def _codex_config_endpoint(request: Request):
    status_only = request.url.path.rstrip("/").endswith("/status")
    if request.method != ("GET" if status_only else "POST"):
        return _json_response({"error": {"code": "method_not_allowed", "message": "Method not allowed"}}, 405)
    try:
        payload = ConfigRequest.model_validate(
            {"apiKeyId": request.query_params.get("apiKeyId")} if status_only else await request.json()
        )
    except (ValidationError, ValueError):
        return _json_response({"error": {"code": "invalid_payload", "message": "A valid API key id is required"}}, 422)
    try:
        actor = await _actor(request, payload.api_key_id)
        saved = await _stored_key(payload.api_key_id)
    except PermissionError as exc:
        return _json_response({"error": {"code": "visitor_key_denied", "message": str(exc)}}, 403)
    except LookupError as exc:
        return _json_response({"error": {"code": "api_key_not_found", "message": str(exc)}}, 404)
    except ValueError as exc:
        return _json_response({"error": {"code": "api_key_inactive", "message": str(exc)}}, 409)

    if status_only:
        return _json_response(
            {"apiKeyId": payload.api_key_id, "tokenAvailable": saved is not None, "resetRequired": saved is None}
        )
    reset = payload.reset_key or saved is None or request.url.path.rstrip("/").endswith("/regenerate")
    if reset and not payload.confirm_reset:
        code = "key_reset_required" if saved is None else "reset_confirmation_required"
        return _json_response(
            {
                "error": {
                    "code": code,
                    "message": "Confirm resetting this key; configurations using the old token will stop working",
                },
                "resetRequired": True,
            },
            409,
        )
    if not reset:
        return _json_response({"apiKey": saved, "reset": False})

    async with _codex_config_rotate_lock:
        now = time.monotonic()
        for key_id, instant in list(_recent_codex_config_rotations.items()):
            if now - instant > 60:
                _recent_codex_config_rotations.pop(key_id, None)
        if now - _recent_codex_config_rotations.get(payload.api_key_id, -60) < 10:
            return _json_response(
                {
                    "error": {
                        "code": "api_key_recently_reset",
                        "message": "This key was just reset. Generate without resetting to reuse it.",
                    }
                },
                409,
            )
        try:
            result = await _regenerate_api_key_for_codex(payload.api_key_id)
        except LookupError as exc:
            return _json_response({"error": {"code": "api_key_not_found", "message": str(exc)}}, 404)
        except ValueError as exc:
            return _json_response({"error": {"code": "api_key_inactive", "message": str(exc)}}, 409)
        _recent_codex_config_rotations[payload.api_key_id] = time.monotonic()
    from app.core.audit.service import AuditService

    AuditService.log_async(
        "api_key_regenerated_for_codex",
        actor_ip=request.client.host if request.client else None,
        details={"key_id": payload.api_key_id, "actor": actor},
    )
    return _json_response({"apiKey": result, "reset": True})

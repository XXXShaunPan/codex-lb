"""Native visitor authentication and server-side request isolation."""

from __future__ import annotations

import json
import re
import threading
import time
from typing import Any, Iterable
from urllib.parse import parse_qsl, urlencode

import bcrypt
from sqlalchemy.exc import IntegrityError

from app.modules.visitor_access.repository import VisitorStore
from app.modules.visitor_access.schemas import Visitor

_COOKIE = "codex_lb_visitor_session"
_UI_COOKIE = "codex_lb_visitor_ui"
_SESSION_TTL_SECONDS = 7 * 24 * 60 * 60
_USERNAME_RE = re.compile(r"^[a-zA-Z0-9_.-]{3,64}$")
_ADMIN_AUTH_RECOVERY_PATHS = frozenset(
    {
        "/api/dashboard-auth/password/login",
        "/api/dashboard-auth/password/setup",
        "/api/dashboard-auth/totp/verify",
        "/api/dashboard-auth/logout",
    }
)
_CODEX_CONFIG_REGENERATE_PATH = "/api/codex-config/regenerate"


_store = VisitorStore()
_codec: VisitorSessionCodec | None = None
_login_attempts: dict[str, list[float]] = {}
_attempt_lock = threading.Lock()
_DUMMY_PASSWORD_HASH = bcrypt.hashpw(b"codex-lb-invalid-visitor", bcrypt.gensalt()).decode("ascii")


def _utc_epoch() -> int:
    return int(time.time())


def _normalize_username(value: str) -> str:
    username = value.strip().lower()
    if not _USERNAME_RE.fullmatch(username):
        raise ValueError("Username must be 3-64 characters using letters, numbers, dot, dash, or underscore")
    return username


def _validate_password(value: str) -> str:
    password = value.strip()
    encoded = password.encode("utf-8")
    if len(password) < 8:
        raise ValueError("Password must be at least 8 characters")
    if len(encoded) > 72:
        raise ValueError("Password must be no more than 72 UTF-8 bytes")
    return password


def _hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("ascii")


def _check_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("ascii"))
    except (ValueError, TypeError):
        return False


class VisitorSessionCodec:
    def __init__(self) -> None:
        from app.core.crypto import TokenEncryptor

        self._encryptor = TokenEncryptor()

    def encode(self, visitor: Visitor) -> str:
        payload = json.dumps(
            {
                "id": visitor.id,
                "sv": visitor.session_version,
                "exp": _utc_epoch() + _SESSION_TTL_SECONDS,
            },
            separators=(",", ":"),
        )
        return self._encryptor.encrypt(payload).decode("ascii")

    def decode(self, value: str | None) -> tuple[str, int] | None:
        if not value:
            return None
        try:
            raw = self._encryptor.decrypt(value.encode("ascii"))
            payload = json.loads(raw)
        except Exception:
            return None
        visitor_id = payload.get("id")
        session_version = payload.get("sv")
        expires_at = payload.get("exp")
        if not isinstance(visitor_id, str) or not isinstance(session_version, int) or not isinstance(expires_at, int):
            return None
        if expires_at < _utc_epoch():
            return None
        return visitor_id, session_version


def _session_codec() -> VisitorSessionCodec:
    global _codec
    if _codec is None:
        _codec = VisitorSessionCodec()
    return _codec


async def _visitor_from_cookie(request: Any) -> Visitor | None:
    decoded = _session_codec().decode(request.cookies.get(_COOKIE))
    if decoded is None:
        return None
    visitor = await _store.get(decoded[0])
    if visitor is None or not visitor.active or visitor.session_version != decoded[1]:
        return None
    return visitor


def _rate_limit_keys(request: Any, username: str) -> tuple[str, str]:
    host = request.client.host if request.client else "unknown"
    return f"ip:{host}", f"identity:{host}:{username.lower()}"


def _check_login_rate_limit(key: str) -> int | None:
    now = time.monotonic()
    with _attempt_lock:
        attempts = [value for value in _login_attempts.get(key, []) if now - value < 60]
        if len(attempts) >= 8:
            _login_attempts[key] = attempts
            return max(1, int(60 - (now - attempts[0])))
        attempts.append(now)
        _login_attempts[key] = attempts
    return None


def _clear_login_attempts(key: str) -> None:
    with _attempt_lock:
        _login_attempts.pop(key, None)


def _auth_session_payload() -> dict[str, Any]:
    return {
        "authenticated": True,
        # Visitors must log out before switching to the administrator. This
        # prevents the native guest header from rendering an Admin sign-in
        # shortcut inside the visitor session.
        "passwordRequired": False,
        "totpRequiredOnLogin": False,
        "totpConfigured": False,
        "bootstrapRequired": False,
        "bootstrapTokenConfigured": False,
        "authMode": "standard",
        "passwordManagementEnabled": False,
        "passwordSessionActive": False,
        "role": "guest",
        "permissions": ["read"],
        "guestAccessEnabled": True,
        "guestPasswordRequired": True,
    }


def _unauthenticated_session_payload() -> dict[str, Any]:
    payload = _auth_session_payload()
    # Match the native unauthenticated administrator state. Reporting "guest"
    # here makes the React login form call /guest/login with the administrator
    # password, which the visitor access module disables.
    payload.update(
        authenticated=False,
        passwordRequired=True,
        passwordManagementEnabled=True,
        role="admin",
        permissions=["read", "write"],
    )
    return payload


def _safe_settings_payload() -> dict[str, Any]:
    return {
        "stickyThreadsEnabled": False,
        "preferEarlierResetAccounts": False,
        "importWithoutOverwrite": False,
        "totpRequiredOnLogin": False,
        "totpConfigured": False,
        "apiKeyAuthEnabled": True,
        "weeklyPaceWorkingDays": "0,1,2,3,4,5,6",
        "showResetCreditBadges": False,
        "showResetCreditExpiryBadge": False,
        "guestAccessEnabled": True,
        "guestPasswordConfigured": True,
        "routingStrategy": "capacity_weighted",
    }


def _safe_overview_payload(request: Any) -> dict[str, Any]:
    timeframe = request.query_params.get("timeframe", "7d")
    minutes = {"1d": 1440, "7d": 10080, "30d": 43200}.get(timeframe, 10080)
    return {
        "lastSyncAt": None,
        "timeframe": {
            "key": timeframe if timeframe in {"1d", "7d", "30d"} else "7d",
            "windowMinutes": minutes,
            "bucketSeconds": 3600,
            "bucketCount": max(1, minutes // 60),
        },
        "accounts": [],
        "summary": {
            "primaryWindow": {
                "remainingPercent": 100,
                "capacityCredits": 0,
                "remainingCredits": 0,
                "resetAt": None,
                "windowMinutes": None,
            },
            "secondaryWindow": None,
            "cost": {"currency": "USD", "totalUsd": 0},
            "metrics": None,
        },
        "windows": {"primary": {"windowKey": "primary", "windowMinutes": None, "accounts": []}, "secondary": None},
        "trends": {"requests": [], "tokens": [], "cost": [], "errorRate": [], "conversations": []},
        "additionalQuotas": [],
        "depletionPrimary": None,
        "depletionSecondary": None,
        "weeklyCreditPace": None,
    }


def _rewrite_api_key_query(request: Any, api_key_ids: Iterable[str]) -> None:
    supplied = parse_qsl(request.scope.get("query_string", b"").decode("utf-8"), keep_blank_values=True)
    requested = {value for key, value in supplied if key in {"api_key_id", "apiKeyId"}}
    assigned = set(api_key_ids)
    pairs = [
        (key, value) for key, value in supplied if key not in {"api_key_id", "apiKeyId", "account_id", "accountId"}
    ]
    key_ids = sorted(assigned & requested if requested else assigned) or ["__visitor_without_assigned_keys__"]
    pairs.extend(("api_key_id", key_id) for key_id in key_ids)
    request.scope["query_string"] = urlencode(pairs, doseq=True).encode("utf-8")


def _secure_cookie(request: Any) -> bool:
    forwarded = request.headers.get("x-forwarded-proto", "").split(",", 1)[0].strip().lower()
    return request.url.scheme == "https" or forwarded == "https"


def _set_visitor_cookies(response: Any, request: Any, token: str) -> None:
    secure = _secure_cookie(request)
    response.set_cookie(
        _COOKIE, token, max_age=_SESSION_TTL_SECONDS, httponly=True, secure=secure, samesite="lax", path="/"
    )
    response.set_cookie(
        _UI_COOKIE, "1", max_age=_SESSION_TTL_SECONDS, httponly=False, secure=secure, samesite="lax", path="/"
    )


def _clear_visitor_cookies(response: Any) -> None:
    response.delete_cookie(_COOKIE, path="/")
    response.delete_cookie(_UI_COOKIE, path="/")


async def _valid_api_key_ids(values: Iterable[str]) -> list[str]:
    from sqlalchemy import select

    from app.db.models import ApiKey
    from app.db.session import get_background_session

    requested = sorted({value.strip() for value in values if value and value.strip()})
    if not requested:
        return []
    async with get_background_session() as session:
        existing = (await session.execute(select(ApiKey.id).where(ApiKey.id.in_(requested)))).scalars().all()
    return [value for value in requested if value in set(existing)]


async def _api_key_options(visitor: Visitor) -> list[dict[str, Any]]:
    from sqlalchemy import select

    from app.db.models import ApiKey
    from app.db.session import get_background_session

    if not visitor.api_key_ids:
        return []
    async with get_background_session() as session:
        rows = (
            await session.execute(
                select(ApiKey.id, ApiKey.name, ApiKey.key_prefix).where(ApiKey.id.in_(visitor.api_key_ids))
            )
        ).all()
    return [{"id": row.id, "name": row.name, "keyPrefix": row.key_prefix} for row in rows]


async def _require_admin(request: Any) -> None:
    from app.core.auth.dashboard_access import DashboardRole
    from app.core.auth.dependencies import validate_dashboard_session
    from app.core.exceptions import DashboardPermissionError

    if await _visitor_from_cookie(request) is not None:
        raise DashboardPermissionError("Admin access is required", code="admin_access_required")
    principal = await validate_dashboard_session(request)
    if principal.role != DashboardRole.ADMIN:
        raise DashboardPermissionError("Admin access is required", code="admin_access_required")


def _json_response(payload: Any, status_code: int = 200):
    from starlette.responses import JSONResponse

    return JSONResponse(payload, status_code=status_code, headers={"Cache-Control": "no-store"})


async def _admin_endpoint(request: Any):
    try:
        await _require_admin(request)
    except Exception:
        return _json_response({"error": {"code": "admin_access_required", "message": "Admin access is required"}}, 403)
    method = request.method.upper()
    path = request.url.path.rstrip("/")
    visitor_id = path.rsplit("/", 1)[-1] if path != "/api/visitor/admin/visitors" else None
    if method == "GET" and visitor_id is None:
        return _json_response({"visitors": [item.public() for item in await _store.list()]})
    payload = await request.json() if method in {"POST", "PATCH"} else {}
    if method == "POST" and visitor_id is None:
        key_ids = await _valid_api_key_ids(payload.get("apiKeyIds") or [])
        try:
            visitor = await _store.create(
                username=str(payload.get("username") or ""),
                display_name=str(payload.get("displayName") or ""),
                password=str(payload.get("password") or ""),
                active=bool(payload.get("active", True)),
                api_key_ids=key_ids,
            )
        except IntegrityError:
            return _json_response(
                {"error": {"code": "visitor_exists", "message": "Visitor username already exists"}}, 409
            )
        except ValueError as exc:
            return _json_response({"error": {"code": "invalid_visitor", "message": str(exc)}}, 422)
        return _json_response(visitor.public(), 201)
    if visitor_id is None:
        return _json_response({"error": {"code": "not_found", "message": "Visitor not found"}}, 404)
    if method == "PATCH":
        key_ids = await _valid_api_key_ids(payload.get("apiKeyIds") or []) if "apiKeyIds" in payload else None
        try:
            visitor = await _store.update(
                visitor_id,
                username=str(payload["username"]) if "username" in payload else None,
                display_name=str(payload["displayName"]) if "displayName" in payload else None,
                password=str(payload.get("password") or "") or None,
                active=bool(payload["active"]) if "active" in payload else None,
                api_key_ids=key_ids,
            )
        except IntegrityError:
            return _json_response(
                {"error": {"code": "visitor_exists", "message": "Visitor username already exists"}}, 409
            )
        except ValueError as exc:
            return _json_response({"error": {"code": "invalid_visitor", "message": str(exc)}}, 422)
        return (
            _json_response(visitor.public())
            if visitor
            else _json_response({"error": {"code": "not_found", "message": "Visitor not found"}}, 404)
        )
    if method == "DELETE":
        return (
            _json_response({"status": "deleted"})
            if await _store.delete(visitor_id)
            else _json_response({"error": {"code": "not_found", "message": "Visitor not found"}}, 404)
        )
    return _json_response({"error": {"code": "method_not_allowed", "message": "Method not allowed"}}, 405)


def _sanitize_reports(payload: dict[str, Any]) -> dict[str, Any]:
    payload["byAccount"] = []
    summary = payload.get("summary")
    if isinstance(summary, dict):
        summary["activeAccounts"] = 0
    for row in payload.get("daily") or []:
        if isinstance(row, dict):
            row["activeAccounts"] = 0
    return payload


class VisitorPortalMiddleware:
    def __init__(self, app: Any) -> None:
        self.app = app

    async def __call__(self, scope: dict[str, Any], receive: Any, send: Any) -> None:
        from starlette.requests import Request

        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        if scope["path"].startswith("/__visitor/"):
            canonical = scope["path"].replace("/__visitor/", "/api/visitor/", 1)
            if canonical.rstrip("/") == "/api/visitor/codex-config/regenerate":
                canonical = _CODEX_CONFIG_REGENERATE_PATH
            scope = {**scope, "path": canonical}
        request = Request(scope, receive=receive)
        path = request.url.path.rstrip("/") or "/"
        if path == _CODEX_CONFIG_REGENERATE_PATH:
            from app.modules.codex_config.service import _codex_config_endpoint

            response = await _codex_config_endpoint(request)
            await response(scope, receive, send)
            return
        if path.startswith("/api/visitor/admin/visitors"):
            response = await _admin_endpoint(request)
            await response(scope, receive, send)
            return
        if path == "/api/dashboard-auth/guest/login":
            await _json_response(
                {
                    "error": {
                        "code": "legacy_guest_login_disabled",
                        "message": "Legacy shared guest password login has been replaced by visitor accounts",
                    }
                },
                410,
            )(scope, receive, send)
            return
        if path == "/api/visitor/login" and request.method == "POST":
            payload = await request.json()
            username = str(payload.get("username") or "").strip().lower()
            password = str(payload.get("password") or "")
            rate_keys = _rate_limit_keys(request, username)
            retry_values = [value for value in (_check_login_rate_limit(key) for key in rate_keys) if value is not None]
            retry_after = max(retry_values) if retry_values else None
            if retry_after is not None:
                response = _json_response(
                    {
                        "error": {
                            "code": "visitor_rate_limited",
                            "message": f"Too many attempts. Try again in {retry_after} seconds.",
                        }
                    },
                    429,
                )
                response.headers["Retry-After"] = str(retry_after)
            else:
                visitor = await _store.get_by_username(username)
                password_hash = visitor.password_hash if visitor is not None else _DUMMY_PASSWORD_HASH
                password_valid = _check_password(password, password_hash)
                if visitor is None or not visitor.active or not password_valid:
                    response = _json_response(
                        {"error": {"code": "invalid_credentials", "message": "Invalid credentials"}}, 401
                    )
                else:
                    for key in rate_keys:
                        _clear_login_attempts(key)
                    response = _json_response(_auth_session_payload())
                    _set_visitor_cookies(response, request, _session_codec().encode(visitor))
            await response(scope, receive, send)
            return

        visitor = await _visitor_from_cookie(request)
        if path == "/api/visitor/self" and visitor is None:
            await _json_response(
                {"error": {"code": "visitor_auth_required", "message": "Visitor authentication is required"}}, 401
            )(scope, receive, send)
            return
        if visitor is not None:
            from app.core.auth.dashboard_access import (
                DashboardAuthMode,
                DashboardPermission,
                DashboardPrincipal,
                DashboardRole,
            )

            request.state.dashboard_principal = DashboardPrincipal(
                role=DashboardRole.GUEST,
                permissions=frozenset({DashboardPermission.READ}),
                auth_mode=DashboardAuthMode.STANDARD,
                actor=f"visitor:{visitor.id}",
            )
            request.state.codex_lb_visitor = visitor
            if path == "/api/dashboard-auth/session" and request.method == "GET":
                await _json_response(_auth_session_payload())(scope, receive, send)
                return
            if path == "/api/dashboard-auth/logout" and request.method == "POST":
                from app.modules.dashboard_auth.service import DASHBOARD_SESSION_COOKIE

                response = _json_response({"status": "ok"})
                _clear_visitor_cookies(response)
                response.delete_cookie(DASHBOARD_SESSION_COOKIE, path="/")
                await response(scope, receive, send)
                return
            if path == "/api/visitor/self" and request.method == "GET":
                await _json_response({**visitor.public(), "apiKeys": await _api_key_options(visitor)})(
                    scope, receive, send
                )
                return
            if path == "/api/settings" and request.method == "GET":
                await _json_response(_safe_settings_payload())(scope, receive, send)
                return
            if path.rstrip("/") == "/api/accounts" and request.method == "GET":
                await _json_response({"accounts": []})(scope, receive, send)
                return
            if path == "/api/dashboard/overview" and request.method == "GET":
                await _json_response(_safe_overview_payload(request))(scope, receive, send)
                return
            if path == "/api/settings/upstream-proxy" and request.method == "GET":
                await _json_response(
                    {"routingEnabled": False, "defaultPoolId": None, "endpoints": [], "pools": [], "bindings": []}
                )(scope, receive, send)
                return
            if path == "/api/settings/telemetry" and request.method == "GET":
                await _json_response({"state": "disabled", "source": "default", "active": False, "preview": None})(
                    scope, receive, send
                )
                return
            if path == "/api/request-logs/options" and request.method == "GET":
                await _json_response(
                    {"accountIds": [], "modelOptions": [], "apiKeys": await _api_key_options(visitor), "statuses": []}
                )(scope, receive, send)
                return
            if path == "/api/request-logs" and request.method == "GET":
                await _json_response({"requests": [], "total": 0, "hasMore": False, "conversation": None})(
                    scope, receive, send
                )
                return
            if path.startswith("/api/request-logs"):
                await _json_response(
                    {
                        "error": {
                            "code": "visitor_scope_denied",
                            "message": "Request logs are not available to visitors",
                        }
                    },
                    403,
                )(scope, receive, send)
                return
            allowed_read = request.method == "GET" and (
                path in {"/api/reports", "/api/reports/options"}
                or path.rstrip("/") == "/api/api-keys"
                or (path.startswith("/api/api-keys/") and (path.endswith("/usage-7d") or path.endswith("/trends")))
                or path == "/api/runtime/version"
            )
            if path.startswith("/api/") and not allowed_read:
                await _json_response(
                    {
                        "error": {
                            "code": "visitor_scope_denied",
                            "message": "This resource is not available to visitors",
                        }
                    },
                    403,
                )(scope, receive, send)
                return
            if path in {"/api/reports", "/api/reports/options"}:
                _rewrite_api_key_query(request, visitor.api_key_ids)
            if path.startswith("/api/api-keys/") and path.rstrip("/") != "/api/api-keys":
                key_id = path.split("/")[3] if len(path.split("/")) > 3 else ""
                if key_id not in visitor.api_key_ids:
                    await _json_response(
                        {"error": {"code": "visitor_key_denied", "message": "API key is not assigned to this visitor"}},
                        403,
                    )(scope, receive, send)
                    return

        if visitor is None:
            from app.core.auth.dashboard_access import DashboardRole
            from app.core.auth.dependencies import validate_dashboard_session
            from app.modules.dashboard_auth.service import DASHBOARD_SESSION_COOKIE, get_dashboard_session_store

            legacy_guest_principal = False
            if path.startswith("/api/"):
                try:
                    principal = await validate_dashboard_session(request)
                    legacy_guest_principal = principal.role == DashboardRole.GUEST
                except Exception:
                    legacy_guest_principal = False
            if legacy_guest_principal:
                if path == "/api/dashboard-auth/session" and request.method == "GET":
                    response = _json_response(_unauthenticated_session_payload())
                    response.delete_cookie(DASHBOARD_SESSION_COOKIE, path="/")
                    await response(scope, receive, send)
                    return
                if path.startswith("/api/") and path not in _ADMIN_AUTH_RECOVERY_PATHS:
                    await _json_response(
                        {
                            "error": {
                                "code": "legacy_guest_session_disabled",
                                "message": "Legacy shared guest access is disabled",
                            }
                        },
                        403,
                    )(scope, receive, send)
                    return

            dashboard_state = get_dashboard_session_store().get(request.cookies.get(DASHBOARD_SESSION_COOKIE))
            if dashboard_state is not None and dashboard_state.role == DashboardRole.GUEST:
                if path == "/api/dashboard-auth/session" and request.method == "GET":
                    response = _json_response(_unauthenticated_session_payload())
                    response.delete_cookie(DASHBOARD_SESSION_COOKIE, path="/")
                    await response(scope, receive, send)
                    return
                if path.startswith("/api/") and path not in _ADMIN_AUTH_RECOVERY_PATHS:
                    await _json_response(
                        {
                            "error": {
                                "code": "legacy_guest_session_disabled",
                                "message": "Legacy shared guest sessions are disabled",
                            }
                        },
                        403,
                    )(scope, receive, send)
                    return

        if visitor is None:
            await self.app(scope, receive, send)
            return

        needs_json_sanitization = (
            path.rstrip("/") == "/api/api-keys"
            or path in {"/api/reports", "/api/reports/options"}
            or path.endswith("/usage-7d")
        )
        if not needs_json_sanitization:
            await self.app(scope, receive, send)
            return

        # The outer visitor layer must inspect JSON. Prevent the native
        # dashboard gzip middleware from encoding the body first.
        scope["headers"] = [
            (key, value) for key, value in scope.get("headers", []) if key.lower() != b"accept-encoding"
        ]

        status_code: int | None = None
        headers: list[tuple[bytes, bytes]] = []
        body_parts: list[bytes] = []
        allowed_key_ids = frozenset(visitor.api_key_ids)

        async def capture(message: dict[str, Any]) -> None:
            nonlocal status_code, headers
            if message["type"] == "http.response.start":
                status_code = message["status"]
                headers = list(message.get("headers", []))
            elif message["type"] == "http.response.body":
                body_parts.append(message.get("body", b""))
                if not message.get("more_body", False):
                    content_type = next(
                        (value for key, value in headers if key.lower() == b"content-type"), b""
                    ).decode("latin1")
                    body = b"".join(body_parts)
                    if visitor is not None and "application/json" in content_type and status_code and status_code < 400:
                        try:
                            payload = json.loads(body.decode("utf-8"))
                            if path.rstrip("/") == "/api/api-keys" and isinstance(payload, list):
                                payload = [item for item in payload if item.get("id") in allowed_key_ids]
                                for item in payload:
                                    item["assignedAccountIds"] = []
                                    item["assignedSourceIds"] = []
                            elif path in {"/api/reports", "/api/reports/options"} and isinstance(payload, dict):
                                payload = _sanitize_reports(payload)
                            elif path.endswith("/usage-7d") and isinstance(payload, dict):
                                payload["accountCosts"] = []
                            body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
                        except Exception:
                            status_code = 502
                            body = b'{"error":{"code":"visitor_response_invalid","message":"Unable to scope response"}}'
                    final_headers = [(key, value) for key, value in headers if key.lower() != b"content-length"]
                    final_headers.append((b"content-length", str(len(body)).encode("ascii")))
                    await send({"type": "http.response.start", "status": status_code or 200, "headers": final_headers})
                    await send({"type": "http.response.body", "body": body, "more_body": False})

        await self.app(scope, receive, capture)

from __future__ import annotations

import json
import logging
from unittest.mock import AsyncMock

import pytest
from fastapi.exceptions import RequestValidationError

from app.modules.proxy import api as proxy_api

pytestmark = pytest.mark.integration

_REQUEST_ID = "ab1f7450-abda-4bf9-9d64-7f2fa0f5c9e8"
_LOGGER = "app.core.validation_diagnostics"
_ROUTES = ["/backend-api/codex/responses", "/v1/responses"]


@pytest.mark.asyncio
@pytest.mark.parametrize("route", _ROUTES)
@pytest.mark.parametrize("trailing_slash", [False, True])
@pytest.mark.parametrize("field", ["tools", "include"])
async def test_responses_rejection_has_private_diagnostic(
    async_client, monkeypatch, caplog, route, trailing_slash, field
):
    secret = "PRIVATE_CONVERSATION_AND_TOOL_VALUE"
    selection = AsyncMock(side_effect=AssertionError("invalid requests must not select an upstream"))
    stream = AsyncMock(side_effect=AssertionError("invalid requests must not stream upstream"))
    monkeypatch.setattr(proxy_api, "_select_responses_model_source_with_continuity", selection)
    monkeypatch.setattr(proxy_api, "_stream_responses", stream)
    payload = {"model": "gpt-5.1", "instructions": secret, "input": secret}
    payload[field] = {"private": secret} if field == "tools" else [secret]

    with caplog.at_level(logging.WARNING):
        response = await async_client.post(
            route + ("/" if trailing_slash else ""),
            json=payload,
            headers={"x-request-id": _REQUEST_ID},
            follow_redirects=True,
        )

    assert response.status_code == 400
    assert response.json() == {
        "error": {
            "code": "invalid_request_error",
            "type": "invalid_request_error",
            "message": "Invalid request payload",
            "param": field,
        }
    }
    assert response.headers["x-request-id"] == _REQUEST_ID
    diagnostics = [
        record.getMessage()
        for record in caplog.records
        if record.name == _LOGGER and record.getMessage().startswith("request_validation_diagnostic ")
    ]
    assert len(diagnostics) == 1
    assert f"request_id={_REQUEST_ID} stage=local_validation" in diagnostics[0]
    assert f"field={field} error_type=value_error" in diagnostics[0]
    assert secret not in caplog.text
    selection.assert_not_called()
    stream.assert_not_called()


@pytest.mark.asyncio
async def test_framework_json_rejection_has_private_diagnostic(async_client, caplog):
    secret = "PRIVATE_MALFORMED_JSON_BODY"
    with caplog.at_level(logging.WARNING):
        response = await async_client.post(
            "/backend-api/codex/responses",
            content='{"input":"' + secret,
            headers={"content-type": "application/json", "x-request-id": _REQUEST_ID},
        )

    assert response.status_code == 400
    assert response.json()["error"]["message"] == "Invalid request payload"
    assert "source=framework" in caplog.text
    assert "error_type=json_invalid" in caplog.text
    assert secret not in caplog.text


@pytest.mark.asyncio
async def test_framework_summary_does_not_log_validator_message(async_client, monkeypatch, caplog):
    secret = "PRIVATE_VALIDATOR_MESSAGE_AND_CONTEXT"

    def reject(*args, **kwargs):
        raise RequestValidationError(
            [
                {
                    "type": "value_error",
                    "loc": ("body", "tools"),
                    "msg": secret,
                    "input": secret,
                    "ctx": {"error": secret},
                }
            ]
        )

    monkeypatch.setattr(proxy_api, "normalize_responses_request_payload", reject)
    with caplog.at_level(logging.WARNING):
        response = await async_client.post(
            "/backend-api/codex/responses",
            json={"model": "gpt-5.1", "instructions": "", "input": "hello"},
        )

    assert response.status_code == 400
    assert response.json()["error"]["param"] == "tools"
    assert "source=framework field=tools error_type=value_error" in caplog.text
    assert secret not in caplog.text


@pytest.mark.asyncio
@pytest.mark.parametrize("route", _ROUTES)
@pytest.mark.parametrize(
    "option, displayed, trimmed",
    [
        ("web_search_call.diagnostic_probe", "web_search_call.diagnostic_probe", False),
        ("sk-clb-PRIVATE_INCLUDE_CREDENTIAL", "[redacted]", False),
        (" web_search_call.results ", "web_search_call.results", True),
    ],
)
async def test_include_option_diagnostic_preserves_rejection_and_privacy(
    async_client, monkeypatch, caplog, route, option, displayed, trimmed
):
    secret = "PRIVATE_BODY_HEADER_AND_TOOL_PARAMETER"
    selection = AsyncMock(side_effect=AssertionError("invalid requests must not select an upstream"))
    stream = AsyncMock(side_effect=AssertionError("invalid requests must not stream upstream"))
    monkeypatch.setattr(proxy_api, "_select_responses_model_source_with_continuity", selection)
    monkeypatch.setattr(proxy_api, "_stream_responses", stream)
    with caplog.at_level(logging.WARNING):
        response = await async_client.post(
            route,
            json={
                "model": "gpt-5.1",
                "instructions": secret,
                "input": secret,
                "tools": [{"type": "function", "name": "weather", "parameters": {"private": secret}}],
                "include": [option, "web_search_call.second_rejected"],
            },
            headers={"x-request-id": _REQUEST_ID, "x-test-private": secret},
        )

    assert response.status_code == 400
    assert response.json() == {
        "error": {
            "code": "invalid_request_error",
            "type": "invalid_request_error",
            "message": "Invalid request payload",
            "param": "include",
        }
    }
    entries = [
        record.getMessage()
        for record in caplog.records
        if record.getMessage().startswith("request_include_diagnostic ")
    ]
    assert len(entries) == 1
    assert f"request_id={_REQUEST_ID}" in entries[0]
    assert f"option={json.dumps(displayed)} whitespace_trimmed={str(trimmed).lower()}" in entries[0]
    assert secret not in caplog.text
    assert "PRIVATE_INCLUDE_CREDENTIAL" not in caplog.text
    assert "second_rejected" not in caplog.text
    selection.assert_not_called()
    stream.assert_not_called()

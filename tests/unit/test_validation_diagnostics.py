from __future__ import annotations

import hashlib
import json
import logging

import pytest
from pydantic import ValidationError

from app.core.openai.exceptions import ClientPayloadError
from app.core.openai.requests import ResponsesRequest
from app.core.utils.request_id import reset_request_id, set_request_id
from app.core.validation_diagnostics import log_validation_diagnostic
from app.modules.proxy.request_policy import openai_client_payload_error, openai_validation_error

pytestmark = pytest.mark.unit

_REQUEST_ID = "ab1f7450-abda-4bf9-9d64-7f2fa0f5c9e8"
_LOGGER = "app.core.validation_diagnostics"


def test_pydantic_diagnostic_keeps_metadata_not_values(caplog):
    secret = "PRIVATE_INPUT_AND_VALIDATOR_MESSAGE"
    with pytest.raises(ValidationError) as caught:
        ResponsesRequest.model_validate(
            {"model": "gpt-5.1", "instructions": secret, "input": secret, "include": [secret]}
        )
    token = set_request_id(_REQUEST_ID)
    try:
        with caplog.at_level(logging.WARNING, logger=_LOGGER):
            error = openai_validation_error(caught.value)
    finally:
        reset_request_id(token)

    assert error["error"]["message"] == "Invalid request payload"
    assert error["error"]["param"] == "include"
    assert f"request_id={_REQUEST_ID}" in caplog.text
    assert "source=pydantic field=include error_type=value_error" in caplog.text
    assert secret not in caplog.text
    assert len(caplog.records) == 1
    assert caplog.records[0].exc_info is None


def test_diagnostic_redacts_dynamic_paths_types_and_non_uuid_ids(caplog):
    secret = "PRIVATE_DYNAMIC_KEY_AND_REQUEST_ID\nforged_line"
    token = set_request_id(secret)
    try:
        with caplog.at_level(logging.WARNING, logger=_LOGGER):
            log_validation_diagnostic(("body", "tools", 2, "parameters", secret), secret, source="pydantic")
    finally:
        reset_request_id(token)

    digest = hashlib.sha256(secret.encode()).hexdigest()[:16]
    assert f"request_id=sha256:{digest}" in caplog.text
    assert "field=tools.2.parameters.[redacted] error_type=validation_error" in caplog.text
    assert secret not in caplog.text
    assert "forged_line" not in caplog.text


def test_diagnostic_bounds_paths_and_large_indices(caplog):
    with caplog.at_level(logging.WARNING, logger=_LOGGER):
        log_validation_diagnostic(("tools", 10**30, *("properties",) * 30), "missing", source="framework")

    message = caplog.records[0].getMessage()
    path = message.split(" field=", 1)[1].split(" error_type=", 1)[0]
    assert path.startswith("tools.[redacted].properties")
    assert len(path.split(".")) == 12
    assert str(10**30) not in message


def test_client_payload_diagnostic_preserves_envelope_and_redacts_message(caplog):
    secret = "PRIVATE_TOOL_ARGUMENT"
    param = "tools[2].parameters." + secret
    with caplog.at_level(logging.WARNING, logger=_LOGGER):
        error = openai_client_payload_error(ClientPayloadError(secret, param=param))

    assert error["error"]["param"] == param
    assert error["error"]["message"] == "Invalid request payload"
    assert "source=client_payload field=tools.2.parameters.[redacted] error_type=client_payload_error" in caplog.text
    assert secret not in caplog.text


def test_multiple_validation_errors_emit_only_the_first_failure(caplog):
    with pytest.raises(ValidationError) as caught:
        ResponsesRequest.model_validate({"model": 123, "instructions": 123, "input": "hello"})
    with caplog.at_level(logging.WARNING, logger=_LOGGER):
        openai_validation_error(caught.value)

    assert len(caplog.records) == 1
    assert "field=model error_type=string_type" in caplog.text


@pytest.mark.parametrize(
    "option, displayed, trimmed",
    [
        ("web_search_call.diagnostic_probe", "web_search_call.diagnostic_probe", False),
        ("tool_search_call.results", "tool_search_call.results", False),
        ("message.output_text.*", "message.output_text.*", False),
        ("*", "*", False),
        ("Web_Search_Call.Results", "Web_Search_Call.Results", False),
        (" web_search_call.results\t", "web_search_call.results", True),
    ],
)
def test_include_diagnostic_only_exposes_first_protocol_option(caplog, option, displayed, trimmed):
    token = set_request_id(_REQUEST_ID)
    try:
        with caplog.at_level(logging.WARNING, logger=_LOGGER), pytest.raises(ValidationError):
            ResponsesRequest.model_validate(
                {
                    "model": "gpt-5.1",
                    "instructions": "PRIVATE_INSTRUCTIONS",
                    "input": "PRIVATE_CONVERSATION",
                    "include": ["reasoning.encrypted_content", option, "web_search_call.second_rejected"],
                }
            )
    finally:
        reset_request_id(token)

    assert len(caplog.records) == 1
    message = caplog.records[0].getMessage()
    assert f"request_include_diagnostic request_id={_REQUEST_ID}" in message
    assert f"option={json.dumps(displayed)} whitespace_trimmed={str(trimmed).lower()}" in message
    assert "PRIVATE_" not in message
    assert "second_rejected" not in message
    assert caplog.records[0].exc_info is None


@pytest.mark.parametrize(
    "option",
    [
        "sk-clb-PRIVATE_CREDENTIAL",
        "Bearer PRIVATE_CREDENTIAL",
        "PRIVATE_CONVERSATION with spaces",
        "获取广州未来七天的天气状况",
        "private.person.name",
        "web_search_call.result\nforged_line",
        "web_search_call.result\n",
        "message.api_key",
        "web_search_call.sk_clb_demo",
        "message.password_value",
        "message.eyJhbGciOiJIUzI1NiJ9.payload.signature",
        "web_search_call." + "a" * 49,
        "web_search_call." + ".".join(["a" * 30] * 4),
    ],
)
def test_include_diagnostic_redacts_sensitive_or_malformed_options(caplog, option):
    token = set_request_id(_REQUEST_ID)
    try:
        with caplog.at_level(logging.WARNING, logger=_LOGGER), pytest.raises(ValidationError):
            ResponsesRequest.model_validate({"model": "gpt-5.1", "instructions": "", "input": [], "include": [option]})
    finally:
        reset_request_id(token)

    assert len(caplog.records) == 1
    assert 'option="[redacted]"' in caplog.text
    assert option not in caplog.text
    assert "forged_line" not in caplog.text


def test_include_diagnostic_is_silent_without_request_context(caplog):
    token = set_request_id(None)
    try:
        with caplog.at_level(logging.WARNING, logger=_LOGGER), pytest.raises(ValidationError):
            ResponsesRequest.model_validate(
                {"model": "gpt-5.1", "instructions": "", "input": [], "include": ["web_search_call.diagnostic_probe"]}
            )
    finally:
        reset_request_id(token)
    assert not caplog.records


def test_include_diagnostic_is_silent_for_valid_options(caplog):
    token = set_request_id(_REQUEST_ID)
    try:
        with caplog.at_level(logging.WARNING, logger=_LOGGER):
            ResponsesRequest.model_validate(
                {
                    "model": "gpt-5.1",
                    "instructions": "",
                    "input": [],
                    "include": ["web_search_call.results", "reasoning.encrypted_content"],
                }
            )
    finally:
        reset_request_id(token)
    assert not caplog.records

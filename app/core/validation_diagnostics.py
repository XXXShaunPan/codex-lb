from __future__ import annotations

import hashlib
import json
import logging
import re
from collections.abc import Sequence
from typing import Literal, get_args
from uuid import UUID

from pydantic_core import ErrorType

from app.core.utils.request_id import get_request_id

logger = logging.getLogger(__name__)

# Locations can contain arbitrary dictionary keys, not just schema field names.
# Keep only structural vocabulary; never emit a validator's input/msg/ctx.
_SAFE_PATH_COMPONENTS = frozenset(
    "body query path model instructions input messages tools additional_tools tool_choice parallel_tool_calls "
    "reasoning effort summary store stream include service_tier conversation previous_response_id truncation "
    "prompt_cache_key prompt_cache_retention text format type name schema strict parameters properties required "
    "additionalProperties items anyOf oneOf allOf enum role content function arguments call_id output "
    "description metadata context_management compaction_trigger verbosity max_output_tokens temperature top_p "
    "stream_options include_usage background user safety_identifier file image size quality n response_format".split()
)
_SAFE_ERROR_TYPES = frozenset(get_args(ErrorType)) | {"client_payload_error"}
_MAX_PATH_COMPONENTS = 12
_INCLUDE_NAME = re.compile(r"[A-Za-z][A-Za-z0-9_]{0,47}(?:\.(?:[A-Za-z][A-Za-z0-9_]{0,47}|\*)){0,7}")
_INCLUDE_ROOTS = frozenset({"message", "reasoning", "response", "input", "output", "text"})
_INCLUDE_SENSITIVE = re.compile(
    r"password|passwd|secret|token|authorization|bearer|api_key|cookie|(?:^|[._])sk(?:[._]|$)|(?:^|\.)eyj",
    re.IGNORECASE,
)


def log_rejected_include(option: str) -> None:
    """Temporary incident trace: expose protocol names, never arbitrary values."""
    if get_request_id() is None:
        return
    displayed = "[redacted]"
    trimmed = False
    if len(option) <= 128:
        candidate = option.strip(" \t")
        trimmed = candidate != option
        root = candidate.split(".", 1)[0].lower()
        protocol_family = root in _INCLUDE_ROOTS or root.endswith(("_call", "_output"))
        if candidate == "*" or (
            protocol_family and _INCLUDE_NAME.fullmatch(candidate) and not _INCLUDE_SENSITIVE.search(candidate)
        ):
            displayed = candidate
    logger.warning(
        "request_include_diagnostic request_id=%s stage=local_validation field=include option=%s whitespace_trimmed=%s",
        _safe_request_id(),
        json.dumps(displayed),
        str(trimmed).lower(),
    )


def _safe_path(location: Sequence[str | int] | str) -> str:
    parts = re.split(r"[.\[\]]", location, maxsplit=_MAX_PATH_COMPONENTS) if isinstance(location, str) else location
    safe_parts: list[str] = []
    for part in parts[:_MAX_PATH_COMPONENTS]:
        if part == "body" or part == "":
            continue
        if isinstance(part, str) and part in _SAFE_PATH_COMPONENTS:
            safe_parts.append(part)
        elif type(part) is int and 0 <= part <= 1_000_000_000:
            safe_parts.append(str(part))
        elif isinstance(part, str) and len(part) <= 9 and part.isascii() and part.isdecimal():
            safe_parts.append(part)
        else:
            safe_parts.append("[redacted]")
    return ".".join(safe_parts) or "$"


def _safe_request_id() -> str:
    request_id = get_request_id()
    if request_id is None:
        return "-"
    try:
        if len(request_id) == 36 and str(UUID(request_id)) == request_id.lower():
            return request_id.lower()
    except ValueError:
        pass
    # Inbound request IDs are caller-controlled and may themselves contain secrets.
    return "sha256:" + hashlib.sha256(request_id.encode("utf-8", errors="replace")).hexdigest()[:16]


def log_validation_diagnostic(
    location: Sequence[str | int] | str,
    error_type: str,
    *,
    source: Literal["pydantic", "framework", "client_payload"],
) -> None:
    logger.warning(
        "request_validation_diagnostic request_id=%s stage=local_validation source=%s field=%s error_type=%s",
        _safe_request_id(),
        source,
        _safe_path(location),
        error_type if error_type in _SAFE_ERROR_TYPES else "validation_error",
    )

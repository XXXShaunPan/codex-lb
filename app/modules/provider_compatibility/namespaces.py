"""Source metadata owns protocol compatibility; core streaming stays native."""

from __future__ import annotations

import json
from typing import Any
from urllib.parse import urlsplit

_MODEL_METADATA_FLAG = "preserve_tool_call_namespaces"


def _source_host(source: Any) -> str | None:
    value = getattr(source, "base_url", None)
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        return urlsplit(value.strip()).hostname
    except ValueError:
        return None


def _model_metadata_policy(source: Any, model: str | None) -> bool | None:
    if not isinstance(model, str) or not model:
        return None
    for entry in getattr(source, "models", ()) or ():
        if getattr(entry, "model", None) != model or getattr(entry, "is_enabled", True) is False:
            continue
        raw = getattr(entry, "raw_metadata_json", None)
        if not isinstance(raw, str) or not raw:
            return None
        try:
            metadata = json.loads(raw)
        except (TypeError, ValueError):
            return None
        if not isinstance(metadata, dict):
            return None
        value = metadata.get(_MODEL_METADATA_FLAG)
        return value if isinstance(value, bool) else None
    return None


def source_preserves_tool_call_namespaces(source: Any, model: str | None) -> bool:
    policy = _model_metadata_policy(source, model)
    if policy is not None:
        return policy
    host = _source_host(source)
    return isinstance(host, str) and host.lower().rstrip(".") == "compass.llm.shopee.io"

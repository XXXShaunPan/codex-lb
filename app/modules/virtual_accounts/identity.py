from __future__ import annotations

import logging
from typing import Iterable

VIRTUAL_PREFIX = "model-source:"
_DEFAULT_SOURCE_CAPACITY_CREDITS = 7560.0


def _notice(message: str) -> None:
    logging.getLogger(__name__).info(message)


def virtual_account_id(source_id: str) -> str:
    return f"{VIRTUAL_PREFIX}{source_id}"


def source_id_from_virtual(value: str) -> str | None:
    if not isinstance(value, str) or not value.startswith(VIRTUAL_PREFIX):
        return None
    source_id = value[len(VIRTUAL_PREFIX) :].strip()
    return source_id or None


def split_virtual_account_ids(values: Iterable[str] | None) -> tuple[list[str], list[str]]:
    real: list[str] = []
    sources: list[str] = []
    for raw in values or ():
        source_id = source_id_from_virtual(raw)
        target = sources if source_id is not None else real
        value = source_id if source_id is not None else str(raw).strip()
        if value and value not in target:
            target.append(value)
    return real, sources

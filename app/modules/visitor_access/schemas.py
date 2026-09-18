from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class Visitor:
    id: str
    username: str
    display_name: str
    password_hash: str
    active: bool
    session_version: int
    created_at: int
    updated_at: int
    api_key_ids: tuple[str, ...]

    def public(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "username": self.username,
            "displayName": self.display_name,
            "active": self.active,
            "apiKeyIds": list(self.api_key_ids),
            "createdAt": self.created_at,
            "updatedAt": self.updated_at,
        }

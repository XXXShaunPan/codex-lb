from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.models import Base


class CodexApiToken(Base):
    """Recoverable tokens are exposed only by the scoped configuration endpoint."""

    __tablename__ = "codex_config_api_tokens"

    api_key_id: Mapped[str] = mapped_column(String, ForeignKey("api_keys.id", ondelete="CASCADE"), primary_key=True)
    token: Mapped[str] = mapped_column(Text, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)

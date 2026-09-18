from __future__ import annotations

from sqlalchemy import Boolean, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.models import Base


class VisitorAccount(Base):
    __tablename__ = "visitor_accounts"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    username: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    display_name: Mapped[str] = mapped_column(String, nullable=False)
    password_hash: Mapped[str] = mapped_column(String, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    session_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[int] = mapped_column(Integer, nullable=False)
    updated_at: Mapped[int] = mapped_column(Integer, nullable=False)


class VisitorApiKey(Base):
    __tablename__ = "visitor_api_keys"

    visitor_id: Mapped[str] = mapped_column(
        String, ForeignKey("visitor_accounts.id", ondelete="CASCADE"), primary_key=True
    )
    api_key_id: Mapped[str] = mapped_column(String, primary_key=True, index=True)

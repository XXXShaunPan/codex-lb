from __future__ import annotations

from sqlalchemy import Boolean, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.models import Base


class RoutingRuleRecord(Base):
    __tablename__ = "relay_routing_rules"

    scope: Mapped[str] = mapped_column(String, primary_key=True)
    target: Mapped[str] = mapped_column(String, primary_key=True)
    normal_priority: Mapped[int] = mapped_column(Integer, nullable=False)
    low_priority: Mapped[int] = mapped_column(Integer, nullable=False)
    downgrade_percent: Mapped[float] = mapped_column(Float, nullable=False)
    recovery_percent: Mapped[float] = mapped_column(Float, nullable=False)
    quota_basis: Mapped[str] = mapped_column(String, nullable=False)
    allow_low_quota: Mapped[bool] = mapped_column(Boolean, nullable=False)


class RoutingQuotaBand(Base):
    __tablename__ = "relay_routing_quota_bands"

    account_id: Mapped[str] = mapped_column(String, ForeignKey("accounts.id", ondelete="CASCADE"), primary_key=True)
    low_quota: Mapped[bool] = mapped_column(Boolean, nullable=False)
    fingerprint: Mapped[str] = mapped_column(String, nullable=False)
    sample_at: Mapped[float] = mapped_column(Float, nullable=False)

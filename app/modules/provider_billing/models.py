from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.models import Base


class ProviderBillingEntry(Base):
    __tablename__ = "provider_billing_entries"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    request_log_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("request_logs.id", ondelete="SET NULL"), nullable=True, unique=True
    )
    request_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    api_key_id: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    source_id: Mapped[str | None] = mapped_column(String, nullable=True)
    model: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False)
    pricing_source: Mapped[str] = mapped_column(String, nullable=False)
    pricing_version: Mapped[str] = mapped_column(String, nullable=False)
    rates_json: Mapped[str] = mapped_column(Text, nullable=False)
    uncached_input_tokens: Mapped[int] = mapped_column(Integer, nullable=False)
    cached_read_tokens: Mapped[int] = mapped_column(Integer, nullable=False)
    cache_write_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    output_tokens: Mapped[int] = mapped_column(Integer, nullable=False)
    service_tier: Mapped[str] = mapped_column(String, nullable=False)
    input_usd: Mapped[float] = mapped_column(Float, nullable=False)
    cached_read_usd: Mapped[float] = mapped_column(Float, nullable=False)
    output_usd: Mapped[float] = mapped_column(Float, nullable=False)
    cache_write_usd: Mapped[float | None] = mapped_column(Float, nullable=True)
    tool_call_cost: Mapped[float | None] = mapped_column(Float, nullable=True)
    provider_cost_usd: Mapped[float | None] = mapped_column(Float, nullable=True)
    cost_usd: Mapped[float] = mapped_column(Float, nullable=False)
    charged_usd: Mapped[float] = mapped_column(Float, nullable=False)
    usage_basis: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)

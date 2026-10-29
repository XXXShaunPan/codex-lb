from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class UsageWindow(BaseModel):
    model_config = ConfigDict(extra="ignore")

    used_percent: float | None = None
    reset_at: int | None = None
    limit_window_seconds: int | None = None
    reset_after_seconds: int | None = None


class RateLimitPayload(BaseModel):
    model_config = ConfigDict(extra="ignore")

    primary_window: UsageWindow | None = None
    secondary_window: UsageWindow | None = None


class CreditsPayload(BaseModel):
    model_config = ConfigDict(extra="ignore")

    has_credits: bool | None = None
    unlimited: bool | None = None
    balance: str | None = None


class RateLimitResetCreditsPayload(BaseModel):
    model_config = ConfigDict(extra="ignore")

    available_count: int | None = None


class AdditionalRateLimitPayload(BaseModel):
    model_config = ConfigDict(extra="ignore")

    limit_name: str
    metered_feature: str
    rate_limit: RateLimitPayload | None = None


class IndividualSpendLimit(BaseModel):
    model_config = ConfigDict(extra="ignore", allow_inf_nan=False)

    source: str | None = None
    unit: str | None = None
    limit: Decimal | None = Field(default=None, ge=0)
    used: Decimal | None = Field(default=None, ge=0)
    remaining: Decimal | None = None
    used_percent: float | None = Field(default=None, ge=0)
    remaining_percent: float | None = None
    reset_at: int | None = None
    reset_after_seconds: int | None = Field(default=None, ge=0)


class SpendControlPayload(BaseModel):
    model_config = ConfigDict(extra="ignore")

    reached: bool | None = None
    individual_limit: IndividualSpendLimit | None = None


class SpendControlSnapshot(BaseModel):
    control: SpendControlPayload | None = None
    credits: CreditsPayload | None = None
    rate_limit_present: bool = False


class UsagePayload(BaseModel):
    model_config = ConfigDict(extra="ignore")

    plan_type: str | None = None
    workspace_id: str | None = None
    workspace_label: str | None = None
    seat_type: str | None = None
    rate_limit: RateLimitPayload | None = None
    credits: CreditsPayload | None = None
    rate_limit_reset_credits: RateLimitResetCreditsPayload | None = None
    additional_rate_limits: list[AdditionalRateLimitPayload] | None = None
    spend_control: SpendControlPayload | None = None

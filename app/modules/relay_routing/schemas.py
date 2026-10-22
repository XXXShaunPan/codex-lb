from __future__ import annotations

from typing import Literal, Self

from pydantic import ConfigDict, Field, model_validator

from app.modules.shared.schemas import DashboardModel


class RoutingWeightUpdate(DashboardModel):
    weight: float = Field(strict=True, ge=0, le=1_000_000, allow_inf_nan=False)


class RoutingWeightEntry(DashboardModel):
    account_id: str
    name: str
    kind: Literal["account", "model_source"]
    weight: float


class RoutingWeightsResponse(DashboardModel):
    accounts: list[RoutingWeightEntry]


class PriorityRule(DashboardModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)

    normal_priority: int = Field(default=20, strict=True, ge=0, le=10000)
    low_priority: int = Field(default=20, strict=True, ge=0, le=10000)
    downgrade_percent: float = Field(default=20, strict=True, ge=0, lt=100, allow_inf_nan=False)
    recovery_percent: float = Field(default=25, strict=True, gt=0, le=100, allow_inf_nan=False)
    quota_basis: Literal["weekly", "five_hour", "minimum"] = "minimum"
    allow_low_quota: bool = Field(default=True, strict=True)

    @model_validator(mode="after")
    def validate_thresholds(self) -> Self:
        if self.recovery_percent <= self.downgrade_percent:
            raise ValueError("Recovery threshold must exceed downgrade threshold")
        return self


class AccountRuleUpdate(DashboardModel):
    model_config = ConfigDict(extra="forbid")
    override: PriorityRule | None


class PlanRuleEntry(DashboardModel):
    plan_type: str
    rule: PriorityRule


class AccountRuleEntry(RoutingWeightEntry):
    plan_type: str
    override: PriorityRule | None
    effective_rule: PriorityRule
    quota_placeholder: bool


class RoutingRulesResponse(DashboardModel):
    plans: list[PlanRuleEntry]
    accounts: list[AccountRuleEntry]

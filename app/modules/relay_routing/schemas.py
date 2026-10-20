from __future__ import annotations

from typing import Literal

from pydantic import Field

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

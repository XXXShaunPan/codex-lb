from __future__ import annotations

from app.core.audit.service import AuditService
from app.core.exceptions import DashboardNotFoundError
from app.modules.proxy.account_cache import get_account_selection_cache
from app.modules.relay_routing.repository import RoutingWeightsRepository
from app.modules.relay_routing.schemas import RoutingWeightEntry, RoutingWeightsResponse


class RoutingWeightsService:
    def __init__(self, repository: RoutingWeightsRepository) -> None:
        self._repository = repository

    async def list_weights(self) -> RoutingWeightsResponse:
        return RoutingWeightsResponse(
            accounts=[
                RoutingWeightEntry(account_id=row.account_id, name=row.name, kind=row.kind, weight=row.weight)
                for row in await self._repository.list_weights()
            ]
        )

    async def update_weight(self, account_id: str, weight: float) -> None:
        if not await self._repository.update_weight(account_id, weight):
            raise DashboardNotFoundError("Account not found", code="account_not_found")
        get_account_selection_cache().invalidate()
        AuditService.log_async("routing_weight_updated", details={"account_id": account_id, "weight": weight})

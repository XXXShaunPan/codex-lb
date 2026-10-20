from __future__ import annotations

from fastapi import APIRouter, Depends

from app.core.auth.dependencies import require_dashboard_admin_access
from app.dependencies import RoutingWeightsContext, get_routing_weights_context
from app.modules.relay_routing.schemas import RoutingWeightsResponse, RoutingWeightUpdate

router = APIRouter(
    prefix="/api/relay-routing/weights",
    tags=["relay-routing"],
    dependencies=[Depends(require_dashboard_admin_access)],
)


@router.get("", response_model=RoutingWeightsResponse)
async def list_weights(context: RoutingWeightsContext = Depends(get_routing_weights_context)) -> RoutingWeightsResponse:
    return await context.service.list_weights()


@router.put("/{account_id}", response_model=RoutingWeightUpdate)
async def update_weight(
    account_id: str,
    payload: RoutingWeightUpdate,
    context: RoutingWeightsContext = Depends(get_routing_weights_context),
) -> RoutingWeightUpdate:
    await context.service.update_weight(account_id, payload.weight)
    return payload

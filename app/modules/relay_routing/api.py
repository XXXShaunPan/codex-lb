from __future__ import annotations

from fastapi import APIRouter, Depends, Path

from app.core.auth.dependencies import require_dashboard_admin_access
from app.dependencies import RoutingWeightsContext, get_routing_weights_context
from app.modules.relay_routing.schemas import (
    AccountRuleUpdate,
    PriorityRule,
    RoutingRulesResponse,
    RoutingWeightsResponse,
    RoutingWeightUpdate,
)

router = APIRouter(
    prefix="/api/relay-routing",
    tags=["relay-routing"],
    dependencies=[Depends(require_dashboard_admin_access)],
)


@router.get("/weights", response_model=RoutingWeightsResponse)
async def list_weights(context: RoutingWeightsContext = Depends(get_routing_weights_context)) -> RoutingWeightsResponse:
    return await context.service.list_weights()


@router.put("/weights/{account_id}", response_model=RoutingWeightUpdate)
async def update_weight(
    account_id: str,
    payload: RoutingWeightUpdate,
    context: RoutingWeightsContext = Depends(get_routing_weights_context),
) -> RoutingWeightUpdate:
    await context.service.update_weight(account_id, payload.weight)
    return payload


@router.get("/rules", response_model=RoutingRulesResponse, deprecated=True)
async def list_rules(context: RoutingWeightsContext = Depends(get_routing_weights_context)) -> RoutingRulesResponse:
    """Legacy configuration only; priority rules no longer affect assignment."""
    return await context.service.list_rules()


@router.put("/rules/plans/{plan_type}", response_model=PriorityRule, deprecated=True)
async def update_plan_rule(
    payload: PriorityRule,
    plan_type: str = Path(pattern=r"^(\*|[a-z][a-z0-9_-]{0,63})$"),
    context: RoutingWeightsContext = Depends(get_routing_weights_context),
) -> PriorityRule:
    await context.service.update_rule("plan", plan_type, payload)
    return payload


@router.put("/rules/accounts/{account_id}", response_model=AccountRuleUpdate, deprecated=True)
async def update_account_rule(
    account_id: str,
    payload: AccountRuleUpdate,
    context: RoutingWeightsContext = Depends(get_routing_weights_context),
) -> AccountRuleUpdate:
    await context.service.update_rule("account", account_id, payload.override)
    return payload

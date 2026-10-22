from __future__ import annotations

from app.core.audit.service import AuditService
from app.core.exceptions import DashboardNotFoundError
from app.core.plan_types import ACCOUNT_PLAN_TYPES
from app.modules.proxy.account_cache import get_account_selection_cache
from app.modules.relay_routing.repository import RoutingWeightsRepository
from app.modules.relay_routing.rules_repository import RoutingRulesRepository, plan_rule, resolve_rule
from app.modules.relay_routing.schemas import (
    AccountRuleEntry,
    PlanRuleEntry,
    PriorityRule,
    RoutingRulesResponse,
    RoutingWeightEntry,
    RoutingWeightsResponse,
)


class RoutingWeightsService:
    def __init__(self, repository: RoutingWeightsRepository, rules_repository: RoutingRulesRepository) -> None:
        self._repository = repository
        self._rules = rules_repository

    async def list_rules(self) -> RoutingRulesResponse:
        rows = await self._repository.list_weights()
        rules = await self._rules.load_rules()
        plans = {"*", "other", *ACCOUNT_PLAN_TYPES, *(row.plan_type for row in rows)}
        plans.update(target for scope, target in rules if scope == "plan")
        return RoutingRulesResponse(
            plans=[PlanRuleEntry(plan_type=plan, rule=plan_rule(rules, plan)) for plan in sorted(plans)],
            accounts=[
                AccountRuleEntry(
                    account_id=row.account_id,
                    name=row.name,
                    kind=row.kind,
                    weight=row.weight,
                    plan_type=row.plan_type,
                    override=rules.get(("account", row.account_id)),
                    effective_rule=resolve_rule(rules, row.account_id, row.plan_type),
                    quota_placeholder=row.kind == "model_source",
                )
                for row in rows
            ],
        )

    async def update_rule(self, scope: str, target: str, rule: PriorityRule | None) -> None:
        if not await self._rules.save_rule(scope, target, rule):
            raise DashboardNotFoundError("Account not found", code="account_not_found")
        get_account_selection_cache().invalidate()
        AuditService.log_async(
            "routing_rule_updated",
            details={
                "scope": scope,
                "target": target,
                "rule": rule.model_dump() if rule is not None else None,
            },
        )

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

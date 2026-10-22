from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Account, ModelSource
from app.db.session import sqlite_writer_section
from app.modules.relay_routing.models import RoutingQuotaBand, RoutingRuleRecord
from app.modules.relay_routing.policy import (
    QuotaCandidate,
    RoutingDecision,
    band_fingerprint,
    default_rule,
    make_decision,
    quota_band,
    threshold_remaining,
)
from app.modules.relay_routing.schemas import PriorityRule
from app.modules.virtual_accounts.identity import source_id_from_virtual

RuleMap = dict[tuple[str, str], PriorityRule]


def resolve_rule(rules: RuleMap, account_id: str, plan_type: str) -> PriorityRule:
    plan = plan_type.lower()
    return rules.get(("account", account_id)) or plan_rule(rules, plan)


def plan_rule(rules: RuleMap, plan: str) -> PriorityRule:
    return rules.get(("plan", plan)) or (
        default_rule("plus") if plan == "plus" else rules.get(("plan", "*"), default_rule(plan))
    )


class RoutingRulesRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def load_rules(self) -> RuleMap:
        rows = (await self._session.scalars(select(RoutingRuleRecord))).all()
        return {(row.scope, row.target): PriorityRule.model_validate(row) for row in rows}

    def _insert(self, model):
        dialect = self._session.get_bind().dialect.name
        if dialect == "postgresql":
            return pg_insert(model)
        if dialect == "sqlite":
            return sqlite_insert(model)
        raise RuntimeError(f"Routing rules do not support dialect={dialect!r}")

    async def save_rule(self, scope: str, target: str, rule: PriorityRule | None) -> bool:
        async with sqlite_writer_section():
            if scope == "account":
                source_id = source_id_from_virtual(target)
                exists = (
                    select(ModelSource.id).where(ModelSource.id == source_id)
                    if source_id is not None
                    else select(Account.id).where(Account.id == target, Account.delete_requested_at.is_(None))
                )
                if await self._session.scalar(exists) is None:
                    return False
            if rule is None:
                await self._session.execute(
                    delete(RoutingRuleRecord).where(
                        RoutingRuleRecord.scope == scope,
                        RoutingRuleRecord.target == target,
                    )
                )
            else:
                values = rule.model_dump()
                statement = self._insert(RoutingRuleRecord).values(scope=scope, target=target, **values)
                await self._session.execute(
                    statement.on_conflict_do_update(
                        index_elements=[RoutingRuleRecord.scope, RoutingRuleRecord.target],
                        set_=values,
                    )
                )
            await self._session.commit()
        return True

    async def decisions(self, candidates: Sequence[QuotaCandidate]) -> dict[str, RoutingDecision]:
        if not candidates:
            return {}
        result: dict[str, RoutingDecision] = {}
        # Serialize SQLite read/transition/write; row locks serialize PostgreSQL.
        # One owned session, no runtime locks, no tasks or deferred writes.
        async with sqlite_writer_section():
            rules = await self.load_rules()
            ids = sorted(candidate.account_id for candidate in candidates if not candidate.placeholder)
            # Ignore deleted rows observed through an older account-selection cache.
            live_ids = (
                set(
                    (
                        await self._session.scalars(
                            select(Account.id).where(
                                Account.id.in_(ids),
                                Account.delete_requested_at.is_(None),
                            )
                        )
                    ).all()
                )
                if ids
                else set()
            )
            if live_ids:
                statement = (
                    self._insert(RoutingQuotaBand)
                    .values(
                        [
                            {"account_id": account_id, "low_quota": False, "fingerprint": "", "sample_at": 0}
                            for account_id in sorted(live_ids)
                        ]
                    )
                    .on_conflict_do_nothing(index_elements=[RoutingQuotaBand.account_id])
                )
                await self._session.execute(statement)
            bands = (
                {
                    row.account_id: row
                    for row in (
                        await self._session.scalars(
                            select(RoutingQuotaBand)
                            .where(RoutingQuotaBand.account_id.in_(ids))
                            .order_by(RoutingQuotaBand.account_id)
                            .with_for_update()
                        )
                    ).all()
                }
                if ids
                else {}
            )
            for candidate in candidates:
                rule = resolve_rule(rules, candidate.account_id, candidate.plan_type)
                remaining = threshold_remaining(candidate, rule)
                if candidate.placeholder:
                    low = quota_band(remaining, rule, None)
                elif candidate.account_id not in live_ids:
                    result[candidate.account_id] = RoutingDecision(rule.low_priority, 0, False, True)
                    continue
                else:
                    band = bands[candidate.account_id]
                    fingerprint = band_fingerprint(rule)
                    same_rule = band.fingerprint == fingerprint
                    low = quota_band(remaining, rule, band.low_quota if same_rule else None)
                    if same_rule and candidate.sample_at < band.sample_at:
                        # An older cached observation cannot reverse a newer transition.
                        low = band.low_quota or remaining is None
                    else:
                        band.low_quota = low
                        band.fingerprint = fingerprint
                        band.sample_at = candidate.sample_at
                result[candidate.account_id] = make_decision(candidate, rule, low)
            await self._session.commit()
        return result

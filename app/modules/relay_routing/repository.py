from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Account, ModelSource
from app.db.session import sqlite_writer_section
from app.modules.virtual_accounts.identity import source_id_from_virtual, virtual_account_id


@dataclass(frozen=True, slots=True)
class RoutingWeightData:
    account_id: str
    name: str
    kind: Literal["account", "model_source"]
    weight: float
    plan_type: str


class RoutingWeightsRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_weights(self) -> list[RoutingWeightData]:
        accounts = (
            await self._session.execute(
                select(Account.id, Account.alias, Account.email, Account.routing_weight, Account.plan_type)
                .where(Account.delete_requested_at.is_(None))
                .order_by(Account.id)
            )
        ).all()
        sources = (
            await self._session.execute(
                select(ModelSource.id, ModelSource.name, ModelSource.routing_weight).order_by(ModelSource.id)
            )
        ).all()
        return [
            RoutingWeightData(row.id, row.alias or row.email, "account", row.routing_weight, row.plan_type.lower())
            for row in accounts
        ] + [
            RoutingWeightData(virtual_account_id(row.id), row.name, "model_source", row.routing_weight, "other")
            for row in sources
        ]

    async def update_weight(self, account_id: str, weight: float) -> bool:
        source_id = source_id_from_virtual(account_id)
        if source_id is None:
            statement = (
                update(Account)
                .where(Account.id == account_id, Account.delete_requested_at.is_(None))
                .values(routing_weight=weight)
                .returning(Account.id)
            )
        else:
            statement = (
                update(ModelSource)
                .where(ModelSource.id == source_id)
                .values(routing_weight=weight)
                .returning(ModelSource.id)
            )
        async with sqlite_writer_section():
            result = await self._session.execute(statement)
            changed = result.scalar_one_or_none() is not None
            await self._session.commit()
            return changed

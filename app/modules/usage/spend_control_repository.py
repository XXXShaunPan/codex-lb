from __future__ import annotations

from datetime import datetime

from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.usage.models import SpendControlSnapshot
from app.db.models import ProviderSpendControl
from app.db.session import sqlite_writer_section


async def save_spend_control(
    session: AsyncSession,
    account_id: str,
    snapshot: SpendControlSnapshot,
    observed_at: datetime,
) -> bool:
    """Upsert by local seat identity; an older poll cannot overwrite newer evidence."""
    dialect = session.get_bind().dialect.name
    if dialect == "sqlite":
        insert = sqlite_insert(ProviderSpendControl)
    elif dialect == "postgresql":
        insert = pg_insert(ProviderSpendControl)
    else:
        raise ValueError(f"Unsupported spend-control database dialect: {dialect}")
    values = dict(account_id=account_id, payload_json=snapshot.model_dump_json(), observed_at=observed_at)
    stmt = (
        insert.values(**values)
        .on_conflict_do_update(
            index_elements=[ProviderSpendControl.account_id],
            set_={"payload_json": values["payload_json"], "observed_at": observed_at},
            where=ProviderSpendControl.observed_at <= observed_at,
        )
        .returning(ProviderSpendControl.account_id)
    )
    try:
        async with sqlite_writer_section():
            result = await session.execute(stmt)
            written = result.scalar_one_or_none() is not None
            await session.commit()
            return written
    except BaseException:
        await session.rollback()
        raise

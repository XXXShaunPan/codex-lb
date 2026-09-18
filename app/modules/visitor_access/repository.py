from __future__ import annotations

import time
import uuid
from collections.abc import Iterable, Sequence

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_background_session, sqlite_writer_section
from app.modules.visitor_access.models import VisitorAccount, VisitorApiKey
from app.modules.visitor_access.schemas import Visitor


class VisitorStore:
    """Each operation owns its session; DDL is exclusively Alembic-owned."""

    async def _snapshot(self, session: AsyncSession, row: VisitorAccount) -> Visitor:
        ids = tuple(
            (
                await session.scalars(
                    select(VisitorApiKey.api_key_id)
                    .where(VisitorApiKey.visitor_id == row.id)
                    .order_by(VisitorApiKey.api_key_id)
                )
            ).all()
        )
        return Visitor(
            id=row.id,
            username=row.username,
            display_name=row.display_name,
            password_hash=row.password_hash,
            active=row.active,
            session_version=row.session_version,
            created_at=row.created_at,
            updated_at=row.updated_at,
            api_key_ids=ids,
        )

    async def list(self) -> Sequence[Visitor]:
        async with get_background_session() as session:
            rows = (await session.scalars(select(VisitorAccount).order_by(VisitorAccount.username))).all()
            return [await self._snapshot(session, row) for row in rows]

    async def get(self, visitor_id: str) -> Visitor | None:
        async with get_background_session() as session:
            row = await session.get(VisitorAccount, visitor_id)
            return await self._snapshot(session, row) if row is not None else None

    async def get_by_username(self, username: str) -> Visitor | None:
        async with get_background_session() as session:
            row = await session.scalar(
                select(VisitorAccount).where(VisitorAccount.username == username.strip().lower())
            )
            return await self._snapshot(session, row) if row is not None else None

    async def create(
        self, *, username: str, display_name: str, password: str, active: bool, api_key_ids: Iterable[str]
    ) -> Visitor:
        from app.modules.visitor_access.service import _hash_password, _normalize_username, _validate_password

        username = _normalize_username(username)
        now = int(time.time())
        row = VisitorAccount(
            id=uuid.uuid4().hex,
            username=username,
            display_name=display_name.strip() or username,
            password_hash=_hash_password(_validate_password(password)),
            active=active,
            session_version=1,
            created_at=now,
            updated_at=now,
        )
        async with sqlite_writer_section(), get_background_session() as session:
            session.add(row)
            await session.flush()
            session.add_all(VisitorApiKey(visitor_id=row.id, api_key_id=key) for key in sorted(set(api_key_ids)))
            await session.commit()
            return await self._snapshot(session, row)

    async def update(
        self,
        visitor_id: str,
        *,
        username: str | None,
        display_name: str | None,
        password: str | None,
        active: bool | None,
        api_key_ids: Iterable[str] | None,
    ) -> Visitor | None:
        from app.modules.visitor_access.service import _hash_password, _normalize_username, _validate_password

        async with sqlite_writer_section(), get_background_session() as session:
            row = await session.get(VisitorAccount, visitor_id, with_for_update=True)
            if row is None:
                return None
            if username is not None:
                row.username = _normalize_username(username)
            if display_name is not None:
                row.display_name = display_name.strip() or row.username
            if password:
                row.password_hash = _hash_password(_validate_password(password))
                row.session_version += 1
            if active is not None:
                if row.active and not active:
                    row.session_version += 1
                row.active = active
            row.updated_at = int(time.time())
            if api_key_ids is not None:
                await session.execute(delete(VisitorApiKey).where(VisitorApiKey.visitor_id == visitor_id))
                session.add_all(
                    VisitorApiKey(visitor_id=visitor_id, api_key_id=key) for key in sorted(set(api_key_ids))
                )
            await session.commit()
            return await self._snapshot(session, row)

    async def delete(self, visitor_id: str) -> bool:
        async with sqlite_writer_section(), get_background_session() as session:
            row = await session.get(VisitorAccount, visitor_id)
            if row is None:
                return False
            await session.delete(row)
            await session.commit()
            return True

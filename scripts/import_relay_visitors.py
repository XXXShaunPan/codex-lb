"""Import external visitor data idempotently without changing credentials.

Run after `codex-lb-db upgrade head`, with CODEX_LB_DATA_DIR pointing to the
target database. Existing visitor IDs must match exactly; conflicting IDs or
usernames abort instead of replacing current authorization.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sqlite3
from pathlib import Path

from sqlalchemy import select

from app.db.session import get_background_session, sqlite_writer_section
from app.modules.visitor_access.models import VisitorAccount, VisitorApiKey


async def import_visitors(path: Path, *, apply: bool) -> dict[str, int | bool]:
    with sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True) as source:
        source.row_factory = sqlite3.Row
        visitors = [dict(row) for row in source.execute("SELECT * FROM visitors")]
        assignments = [dict(row) for row in source.execute("SELECT * FROM visitor_api_keys")]
    async with sqlite_writer_section(), get_background_session() as session:
        existing = {row.id: row for row in (await session.scalars(select(VisitorAccount))).all()}
        imported = 0
        new_ids: set[str] = set()
        for row in visitors:
            current = existing.get(row["id"])
            if current is not None:
                if current.username != row["username"] or current.password_hash != row["password_hash"]:
                    raise ValueError("Existing visitor conflicts with the import; no rows changed")
                continue
            session.add(VisitorAccount(**{**row, "active": bool(row["active"])}))
            new_ids.add(row["id"])
            imported += 1
        await session.flush()
        assigned = 0
        for row in assignments:
            if row["visitor_id"] not in new_ids:
                continue
            if await session.get(VisitorApiKey, (row["visitor_id"], row["api_key_id"])) is None:
                session.add(VisitorApiKey(**row))
                assigned += 1
        if apply:
            await session.commit()
        else:
            await session.rollback()
    return {"apply": apply, "visitors": imported, "assignments": assigned}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    print(json.dumps(asyncio.run(import_visitors(args.source, apply=args.apply))))

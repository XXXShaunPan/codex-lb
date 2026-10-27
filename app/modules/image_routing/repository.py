from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import sqlite_writer_section
from app.modules.image_routing.models import ImageRoutingSettings


class ImageRoutingRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_host(self) -> str | None:
        row = await self.session.get(ImageRoutingSettings, 1)
        return row.host_model if row is not None else None

    async def set_host(self, host_model: str | None) -> None:
        async with sqlite_writer_section():
            row = await self.session.get(ImageRoutingSettings, 1)
            if row is None:
                self.session.add(ImageRoutingSettings(id=1, host_model=host_model))
            else:
                row.host_model = host_model
            await self.session.commit()

from __future__ import annotations

from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.models import Base


class ImageRoutingSettings(Base):
    __tablename__ = "relay_image_routing_settings"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    host_model: Mapped[str | None] = mapped_column(String, nullable=True)

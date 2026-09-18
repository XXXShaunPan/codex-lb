from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select

from app.core.auth.dependencies import require_dashboard_admin_access
from app.db.session import get_background_session
from app.modules.provider_billing.models import ProviderBillingEntry

router = APIRouter(
    prefix="/api/provider-billing",
    tags=["provider-billing"],
    dependencies=[Depends(require_dashboard_admin_access)],
)


@router.get("/{request_id}")
async def request_billing(request_id: str) -> dict:
    async with get_background_session() as session:
        entries = (
            await session.scalars(
                select(ProviderBillingEntry)
                .where(ProviderBillingEntry.request_id == request_id)
                .order_by(ProviderBillingEntry.created_at)
            )
        ).all()
        return {
            "entries": [
                {column.name: getattr(entry, column.name) for column in ProviderBillingEntry.__table__.columns}
                for entry in entries
            ]
        }

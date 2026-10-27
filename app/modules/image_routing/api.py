from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth.dependencies import require_dashboard_admin_access
from app.db.session import get_session
from app.modules.image_routing.repository import ImageRoutingRepository
from app.modules.image_routing.schemas import ImageRoutingResponse, ImageRoutingUpdate
from app.modules.image_routing.service import host_catalog, resolve_host

router = APIRouter(
    prefix="/api/image-routing", tags=["image-routing"], dependencies=[Depends(require_dashboard_admin_access)]
)


@router.get("/settings", response_model=ImageRoutingResponse)
async def read_settings(session: AsyncSession = Depends(get_session)) -> ImageRoutingResponse:
    return ImageRoutingResponse(
        host_model=await ImageRoutingRepository(session).get_host(),
        resolved_host_model=await resolve_host(),
        available_host_models=[model.slug for model in host_catalog()],
    )


@router.put("/settings", response_model=ImageRoutingResponse)
async def update_settings(
    payload: ImageRoutingUpdate, session: AsyncSession = Depends(get_session)
) -> ImageRoutingResponse:
    await ImageRoutingRepository(session).set_host(payload.host_model)
    return await read_settings(session)

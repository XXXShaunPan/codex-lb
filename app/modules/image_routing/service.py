from __future__ import annotations

from app.core.openai.model_registry import MODEL_SOURCE_KIND_SUBSCRIPTION, UpstreamModel, get_model_registry
from app.db.models import ModelSource
from app.db.session import get_background_session
from app.modules.api_keys.service import ApiKeyData
from app.modules.image_routing.repository import ImageRoutingRepository
from app.modules.virtual_accounts.routing import _choose_virtual_candidate, _eligible_sources


def host_catalog() -> list[UpstreamModel]:
    def explicit_image_tool(model: UpstreamModel) -> bool:
        tools = model.raw.get("experimental_supported_tools")
        return isinstance(tools, list) and "image_generation" in tools

    return sorted(
        (
            model
            for model in get_model_registry().get_models_with_fallback().values()
            if model.source_kind == MODEL_SOURCE_KIND_SUBSCRIPTION
            and not model.slug.startswith("gpt-image-")
            and "image" in model.input_modalities
            and model.supported_in_api
            and model.raw.get("visibility") != "hide"
        ),
        # Zero denotes an unspecified priority in the bundled catalog.
        key=lambda model: (not explicit_image_tool(model), model.priority if model.priority > 0 else 1_000_000),
    )


async def resolve_host(api_key: ApiKeyData | None = None) -> str | None:
    if api_key is not None and api_key.account_assignment_scope_enabled and not api_key.assigned_account_ids:
        return None
    async with get_background_session() as session:
        configured = await ImageRoutingRepository(session).get_host()
    if configured:
        return configured
    registry = get_model_registry()
    scoped = (
        set(api_key.assigned_account_ids) if api_key is not None and api_key.account_assignment_scope_enabled else None
    )
    for model in host_catalog():
        known = registry.account_ids_for_model(model.slug)
        if known is not None and (not known or (scoped is not None and not scoped.intersection(known))):
            continue
        return model.slug
    return None


async def choose_image_route(
    model: str, api_key: ApiKeyData | None, *, stream: bool
) -> tuple[ModelSource | None, str | None]:
    host = await resolve_host(api_key)
    sources = await _eligible_sources(route="images", model=model, api_key=api_key, require_streaming=stream)
    if sources:
        selected = await _choose_virtual_candidate(
            model=model,
            account_model=host,
            api_key=api_key,
            sources=sources,
            include_accounts=host is not None,
            lease_kind="stream" if stream else "response_create",
        )
        if selected is not None:
            return selected[0], host
    return None, host

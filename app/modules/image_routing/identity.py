"""Carry public image identity into detached logging without changing the wire model."""

from collections.abc import AsyncIterator
from contextvars import ContextVar
from dataclasses import dataclass

from app.core.openai.images import V1ImageUsage
from app.core.utils.json_guards import is_json_mapping
from app.core.utils.sse import parse_sse_data_json


@dataclass(slots=True)
class ImageRequestIdentity:
    public_model: str
    host_model: str
    response_id: str | None = None
    usage: V1ImageUsage | None = None
    cached_input_tokens: int | None = None

    def observe(self, chunk: str) -> None:
        # The subscription stream yields complete SSE blocks. Avoid reparsing
        # large partial images; only the final envelope carries tool usage.
        if '"response.completed"' not in chunk:
            return
        event = parse_sse_data_json(chunk)
        if event is None or event.get("type") != "response.completed":
            return
        response = event.get("response")
        if not is_json_mapping(response):
            return
        from app.modules.proxy.images_service import _extract_cached_input_tokens, _extract_image_usage

        response_id = response.get("id")
        self.response_id = response_id if isinstance(response_id, str) else None
        self.usage = _extract_image_usage(response)
        self.cached_input_tokens = _extract_cached_input_tokens(self.usage) if self.usage is not None else None


image_identity: ContextVar[ImageRequestIdentity | None] = ContextVar("image_request_identity", default=None)


async def image_identity_stream(upstream: AsyncIterator[str], public_model: str, host_model: str) -> AsyncIterator[str]:
    iterator = upstream.__aiter__()
    identity = ImageRequestIdentity(public_model, host_model)
    try:
        while True:
            token = image_identity.set(identity)
            try:
                chunk = await anext(iterator)
                identity.observe(chunk)
            except StopAsyncIteration:
                return
            finally:
                image_identity.reset(token)
            yield chunk
    finally:
        close = getattr(iterator, "aclose", None)
        if close is not None:
            token = image_identity.set(identity)
            try:
                await close()
            finally:
                image_identity.reset(token)

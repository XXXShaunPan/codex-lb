"""Native Images API forwarding with the shared source lifecycle owner."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import AsyncExitStack
from typing import TYPE_CHECKING

import aiohttp
from fastapi import Request
from starlette.responses import JSONResponse, Response

from app.core.clients.http import lease_model_source_session
from app.core.clients.stream_errors import StreamEventTooLargeError
from app.core.clock import REAL_SCHEDULER
from app.core.errors import openai_error
from app.core.openai.images import V1ImagesEditsForm, V1ImagesGenerationsRequest
from app.core.types import JsonValue
from app.core.utils.shared_future import _await_cleanup_deferring_cancellation
from app.core.utils.sse import format_sse_event, parse_sse_data_json
from app.db.models import ModelSource
from app.modules.api_keys.service import ApiKeyData
from app.modules.model_sources import forwarding as transport
from app.modules.model_sources.forwarding import (
    ModelSourceForwardingError,
    SourceResponsesStream,
    SourceStreamTransport,
    SourceUsageHolder,
)
from app.modules.proxy.source_admission import try_claim
from app.modules.proxy.source_dispatch import (
    ABANDON_CLIENT_DISCONNECTED_DURING_OPEN,
    ABANDON_DISPATCH_INTERRUPTED,
    ClientDisconnectedDuringOpen,
    SourceDispatch,
    SourceStreamingResponse,
    open_with_disconnect_watch,
)

if TYPE_CHECKING:
    from app.dependencies import ProxyContext

ImageInput = tuple[bytes, str | None]
_MAX_IMAGE_EVENT_BYTES = 128 * 1024 * 1024


async def _chunks(response: aiohttp.ClientResponse) -> AsyncIterator[bytes]:
    while True:
        try:
            chunk = await REAL_SCHEDULER.wait_for(response.content.readany(), transport.source_stream_idle_seconds())
        except TimeoutError as exc:
            raise transport._idle_timeout_error(transport.source_stream_idle_seconds()) from exc
        except aiohttp.ClientError as exc:
            raise transport._unreachable_error(exc) from exc
        if not chunk:
            return
        yield chunk


async def _open(
    owner: SourceDispatch,
    payload: V1ImagesGenerationsRequest | V1ImagesEditsForm,
    images: list[ImageInput] | None,
    mask: ImageInput | None,
) -> dict[str, JsonValue] | None:
    stack = AsyncExitStack()
    handed_off = False
    try:
        session = await stack.enter_async_context(lease_model_source_session())
        fields = payload.model_dump(mode="json", exclude_unset=True, exclude_none=True)
        fields["model"] = owner.model
        fields["stream"] = payload.stream
        headers = transport._source_headers(
            owner.source,
            encryptor=None,
            stream=payload.stream,
            content_type=None if images is not None else "application/json",
        )
        if images is None:
            response = await stack.enter_async_context(
                session.post(
                    transport._source_url(owner.source, "/images/generations"),
                    headers=headers,
                    json=fields,
                    timeout=transport._source_client_timeout(owner.source),
                )
            )
        else:
            form = aiohttp.FormData()
            for name, value in fields.items():
                form.add_field(name, str(value).lower() if isinstance(value, bool) else str(value))
            for index, (content, content_type) in enumerate(images):
                form.add_field(
                    "image" if len(images) == 1 else "image[]",
                    content,
                    filename=f"image-{index}.png",
                    content_type=content_type or "image/png",
                )
            if mask is not None:
                form.add_field("mask", mask[0], filename="mask.png", content_type=mask[1] or "image/png")
            response = await stack.enter_async_context(
                session.post(
                    transport._source_url(owner.source, "/images/edits"),
                    headers=headers,
                    data=form,
                    timeout=transport._source_client_timeout(owner.source),
                )
            )
        if response.status >= 400:
            data = await transport._read_error_body(response, scheduler=owner.scheduler)
            raise transport._upstream_status_error(
                response, owner.source, encryptor=None, error_payload=transport._error_payload(data)
            )
        if payload.stream:
            if "text/event-stream" not in response.headers.get("content-type", "").lower():
                raise transport._invalid_upstream_response_error(response.status)
            owner.stream = SourceResponsesStream(
                body=_chunks(response),
                usage_holder=SourceUsageHolder(),
                upstream_status_code=response.status,
                transport=SourceStreamTransport(stack, scheduler=owner.scheduler),
            )
            handed_off = True
            return None
        data = await transport._response_json(response)
        if data is None or not isinstance(data.get("data"), list) or not data["data"]:
            raise transport._invalid_upstream_response_error(response.status)
        return data
    except (aiohttp.ClientError, TimeoutError) as exc:
        raise transport._unreachable_error(exc) from exc
    finally:
        if not handed_off:
            await _await_cleanup_deferring_cancellation(stack.aclose(), scheduler=owner.scheduler)


def _usage_required(owner: SourceDispatch) -> bool:
    return owner.reservation is not None and owner.reservation.has_applicable_limits


async def _stream(owner: SourceDispatch) -> AsyncIterator[str]:
    from app.modules.proxy.api import _iter_source_sse_event_blocks

    assert owner.stream is not None
    owner.body_started = True
    try:
        async for block in _iter_source_sse_event_blocks(owner.stream.body, max_event_bytes=_MAX_IMAGE_EVENT_BYTES):
            event = parse_sse_data_json(block)
            if event is None:
                yield block
                continue
            kind = event.get("type")
            if not isinstance(kind, str):
                kind = next(
                    (line[6:].strip() for line in block.replace("\r", "\n").split("\n") if line.startswith("event:")),
                    "",
                )
            if kind in {"image_generation.completed", "image_edit.completed"}:
                usage = transport._usage_from_responses_payload(event)
                if not event.get("b64_json") or (usage is None and _usage_required(owner)):
                    await owner.finish(
                        status="error",
                        error_code="usage_unavailable",
                        error_message="Image source completed without image data or required usage",
                    )
                    yield format_sse_event(
                        {"type": "error", **openai_error("usage_unavailable", "Image usage unavailable")}
                    )
                    return
                # Settle before releasing the final image: disconnecting immediately
                # after the terminal cannot cause a second settlement or a free image.
                await owner.finish(status="success", usage=usage, trial_result="success")
                if owner.settlement_failed:
                    yield format_sse_event(
                        {"type": "error", **openai_error("usage_settlement_failed", "Image settlement failed")}
                    )
                else:
                    yield block
                return
            if kind == "error" or event.get("error") is not None:
                await owner.finish(
                    status="error",
                    error_code="model_source_response_failed",
                    error_message="Image source reported an error",
                )
                yield format_sse_event(
                    {"type": "error", **openai_error("model_source_response_failed", "Image source failed")}
                )
                return
            yield block
        await owner.finish(
            status="error",
            error_code="model_source_stream_truncated",
            error_message="Image source closed without a completed image",
        )
        yield format_sse_event(
            {"type": "error", **openai_error("model_source_stream_truncated", "Image stream truncated")}
        )
    except ModelSourceForwardingError as exc:
        await owner.finish_with_forwarding_error(exc)
        yield format_sse_event({"type": "error", **exc.payload})
    except StreamEventTooLargeError:
        await owner.finish(
            status="error", error_code="image_event_too_large", error_message="Image event exceeds size limit"
        )
        yield format_sse_event(
            {"type": "error", **openai_error("image_event_too_large", "Image event exceeds size limit")}
        )
    finally:
        if not owner.finished:
            # A partial-image preview has no final image usage; mirror the
            # subscription image route's release-until-completion policy.
            await _await_cleanup_deferring_cancellation(owner.abandon("client_disconnected"), scheduler=owner.scheduler)


async def proxy_source_image(
    request: Request,
    source: ModelSource,
    payload: V1ImagesGenerationsRequest | V1ImagesEditsForm,
    api_key: ApiKeyData | None,
    context: ProxyContext,
    rate_limit_headers: dict[str, str],
    *,
    images: list[ImageInput] | None = None,
    mask: ImageInput | None = None,
) -> Response:
    from app.modules.proxy import api as proxy_api

    assert payload.model is not None
    claims = try_claim(source)
    if claims is None:
        return JSONResponse(
            openai_error("model_source_busy", "Image source is at capacity"),
            status_code=503,
            headers={**rate_limit_headers, "Retry-After": "1"},
        )
    try:
        reservation = await proxy_api._enforce_request_limits(
            api_key, request_model=payload.model, request_service_tier=None
        )
        owner = SourceDispatch(
            request=request,
            source=source,
            model=payload.model,
            api_key=api_key,
            reservation=reservation,
            claims=claims,
            admission_budget=None,
            requested_service_tier=None,
            settle_reservation=proxy_api._settle_source_reservation,
            release_reservation=proxy_api._release_reservation,
            cleanup_scheduler=proxy_api._responses_cleanup_scheduler(context.service),
        )
        claims.transfer_to(owner)
    except BaseException:
        claims.release_if_unowned()
        raise
    try:
        result = await open_with_disconnect_watch(request, owner, _open(owner, payload, images, mask))
        if payload.stream:
            return SourceStreamingResponse(
                _stream(owner),
                owner=owner,
                media_type="text/event-stream",
                headers={"Cache-Control": "no-cache", **rate_limit_headers},
            )
        assert result is not None
        usage = transport._usage_from_responses_payload(result)
        if usage is None and _usage_required(owner):
            await owner.finish(
                status="error", error_code="usage_unavailable", error_message="Image source omitted usage"
            )
            return JSONResponse(
                openai_error("usage_unavailable", "Image source omitted required usage"),
                status_code=502,
                headers=rate_limit_headers,
            )
        await owner.finish(status="success", usage=usage, upstream_status_code=200, trial_result="success")
        if owner.settlement_failed:
            return JSONResponse(
                openai_error("usage_settlement_failed", "Image settlement failed"),
                status_code=502,
                headers=rate_limit_headers,
            )
        return JSONResponse(result, headers=rate_limit_headers)
    except ModelSourceForwardingError as exc:
        await owner.finish_with_forwarding_error(exc)
        return JSONResponse(
            exc.payload,
            status_code=exc.status_code,
            headers=proxy_api._source_error_response_headers(rate_limit_headers, exc),
        )
    except ClientDisconnectedDuringOpen:
        await owner.abandon(ABANDON_CLIENT_DISCONNECTED_DURING_OPEN)
        return Response()
    except BaseException:
        await _await_cleanup_deferring_cancellation(
            owner.abandon(ABANDON_DISPATCH_INTERRUPTED), scheduler=owner.scheduler
        )
        raise

import asyncio
import base64
import json

import pytest
from aiohttp import web
from sqlalchemy import select

from app.db.models import ApiKeyLimit, ApiKeyUsageReservation, RequestLog
from app.db.session import get_background_session
from app.modules.provider_billing.models import ProviderBillingEntry
from app.modules.proxy.source_admission import get_source_bulkhead
from tests.integration.model_source_helpers import (
    _AsgiStream,
    _create_model_source,
    _enable_api_key_auth,
    stub_source_upstreams,
)

pytestmark = pytest.mark.integration
USAGE = {
    "input_tokens": 100,
    "output_tokens": 20,
    "input_tokens_details": {"text_tokens": 100, "image_tokens": 0},
    "total_tokens": 120,
}
PNG = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO5+AvsAAAAASUVORK5CYII=")


@pytest.fixture
async def source_upstream():
    async with stub_source_upstreams() as start:
        yield start


async def create_source_key(client, url):
    await _enable_api_key_auth(client)
    source = await _create_model_source(client, name="image-source", model="gpt-image-2", base_url=url)
    response = await client.post(
        "/api/api-keys",
        json={
            "name": "image-key",
            "assignedAccountIds": ["model-source:" + source],
            "enforcedModel": "gpt-5.5",
            "limits": [{"limitType": "total_tokens", "limitWindow": "weekly", "maxValue": 100_000}],
        },
    )
    assert response.status_code == 200, response.text
    key = response.json()
    return source, key, {"Authorization": "Bearer " + key["key"]}


async def assert_settled(source, key, *, status="success", charged=True):
    async with get_background_session() as session:
        rows = list((await session.scalars(select(RequestLog).where(RequestLog.model_source_id == source))).all())
        assert len(rows) == 1
        row = rows[0]
        assert row.model == "gpt-image-2" and row.image_host_model is None and row.api_key_id == key["id"]
        assert row.status == status
        reservations = list(
            (
                await session.scalars(
                    select(ApiKeyUsageReservation).where(ApiKeyUsageReservation.api_key_id == key["id"])
                )
            ).all()
        )
        assert len(reservations) == 1 and reservations[0].status == ("finalized" if charged else "released")
        limit = await session.scalar(select(ApiKeyLimit).where(ApiKeyLimit.api_key_id == key["id"]))
        assert limit.current_value == (120 if charged else 0)
        if charged:
            assert row.cost_usd == pytest.approx(0.0011)
            entry = await session.scalar(
                select(ProviderBillingEntry).where(ProviderBillingEntry.request_log_id == row.id)
            )
            assert entry is not None and entry.cost_usd == pytest.approx(row.cost_usd)
    assert get_source_bulkhead().in_flight(source) == 0


@pytest.mark.asyncio
@pytest.mark.parametrize("route", ["/v1/images/generations", "/backend-api/codex/images/generations"])
async def test_source_only_generation_preserves_image_model_and_bills_once(async_client, source_upstream, route):
    calls = []

    async def handler(request):
        calls.append((request.path, await request.json()))
        return web.json_response({"created": 1, "data": [{"b64_json": "image"}], "usage": USAGE})

    source, key, headers = await create_source_key(async_client, await source_upstream(handler))
    result = await async_client.post(route, headers=headers, json={"model": "gpt-image-2", "prompt": "a red circle"})
    assert result.status_code == 200, result.text
    assert result.json()["data"] == [{"b64_json": "image"}]
    assert len(calls) == 1 and calls[0][0] == "/v1/images/generations"
    assert calls[0][1]["model"] == "gpt-image-2" and "tools" not in calls[0][1]
    await assert_settled(source, key)


@pytest.mark.asyncio
async def test_source_edit_preserves_images_mask_and_fields(async_client, source_upstream):
    parts = {}

    async def handler(request):
        assert request.path == "/v1/images/edits"
        reader = await request.multipart()
        async for part in reader:
            parts.setdefault(part.name, []).append(bytes(await part.read()))
        return web.json_response({"created": 1, "data": [{"b64_json": "edited"}], "usage": USAGE})

    source, key, headers = await create_source_key(async_client, await source_upstream(handler))
    result = await async_client.post(
        "/v1/images/edits",
        headers=headers,
        data={"model": "gpt-image-2", "prompt": "make it blue", "quality": "low"},
        files=[
            ("image[]", ("one.png", PNG, "image/png")),
            ("image[]", ("two.png", PNG, "image/png")),
            ("mask", ("mask.png", PNG, "image/png")),
        ],
    )
    assert result.status_code == 200, result.text
    assert parts["image[]"] == [PNG, PNG] and parts["mask"] == [PNG]
    assert parts["model"] == [b"gpt-image-2"] and parts["quality"] == [b"low"]
    await assert_settled(source, key)


@pytest.mark.asyncio
@pytest.mark.parametrize("outcome", ["complete", "truncated", "no_usage", "error"])
async def test_source_image_stream_terminal_cleanup_and_accounting(async_client, source_upstream, outcome):
    async def handler(request):
        response = web.StreamResponse(headers={"Content-Type": "text/event-stream"})
        await response.prepare(request)
        await response.write(b'data: {"type":"image_generation.partial_image","b64_json":"preview"}\n\n')
        if outcome != "truncated":
            event = {"type": "image_generation.completed", "b64_json": "final"}
            if outcome == "complete":
                event["usage"] = USAGE
            elif outcome == "error":
                event = {"type": "error", "error": {"message": "secret upstream diagnostic"}}
            await response.write(("data: " + json.dumps(event) + "\n\n").encode())
        await response.write_eof()
        return response

    source, key, headers = await create_source_key(async_client, await source_upstream(handler))
    response = await async_client.post(
        "/v1/images/generations", headers=headers, json={"model": "gpt-image-2", "prompt": "a circle", "stream": True}
    )
    assert response.status_code == 200, response.text
    assert "preview" in response.text
    assert "secret upstream diagnostic" not in response.text
    if outcome == "complete":
        assert '"b64_json": "final"' in response.text
    else:
        assert '"type":"error"' in response.text.replace(" ", "") and '"b64_json": "final"' not in response.text
    await assert_settled(
        source, key, status="success" if outcome == "complete" else "error", charged=outcome == "complete"
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("stall_start", [False, True])
async def test_source_image_disconnect_releases_reservation_and_transport(async_client, source_upstream, stall_start):
    disconnected = asyncio.Event()

    async def handler(request):
        try:
            response = web.StreamResponse(headers={"Content-Type": "text/event-stream"})
            await response.prepare(request)
            await response.write(b'data: {"type":"image_generation.partial_image","b64_json":"preview"}\n\n')
            await asyncio.Event().wait()
            return response
        finally:
            disconnected.set()

    source, key, headers = await create_source_key(
        async_client, await source_upstream(handler, handler_cancellation=True, shutdown_timeout=0.1)
    )
    exchange = _AsgiStream(
        async_client._transport.app,
        "/v1/images/generations",
        {**headers, "content-type": "application/json"},
        json.dumps({"model": "gpt-image-2", "prompt": "test", "stream": True}).encode(),
        stall_response_start=stall_start,
    )
    task = asyncio.create_task(exchange.run())
    try:
        if stall_start:
            await exchange.wait_for_response_start()
        else:
            await exchange.wait_for_text("preview")
        exchange.disconnect()
        await asyncio.wait_for(task, 10)
        await asyncio.wait_for(disconnected.wait(), 5)
        await assert_settled(source, key, status="cancelled", charged=False)
    finally:
        if not task.done():
            task.cancel()
        await asyncio.gather(task, return_exceptions=True)


@pytest.mark.asyncio
async def test_source_image_missing_usage_fails_closed_and_unassigned_source_is_not_used(async_client, source_upstream):
    calls = []

    async def handler(request):
        calls.append(request.path)
        return web.json_response({"data": [{"b64_json": "withheld"}]})

    source, key, headers = await create_source_key(async_client, await source_upstream(handler))
    result = await async_client.post(
        "/v1/images/generations", headers=headers, json={"model": "gpt-image-2", "prompt": "test"}
    )
    assert result.status_code == 502 and "withheld" not in result.text
    await assert_settled(source, key, status="error", charged=False)
    other_source = await _create_model_source(
        async_client, name="not-an-image-source", model="text-only", base_url="https://example.invalid/v1"
    )
    other = (
        await async_client.post(
            "/api/api-keys", json={"name": "other", "assignedAccountIds": ["model-source:" + other_source]}
        )
    ).json()
    result = await async_client.post(
        "/v1/images/generations",
        headers={"Authorization": "Bearer " + other["key"]},
        json={"model": "gpt-image-2", "prompt": "test"},
    )
    assert result.status_code == 503 and len(calls) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("items", [[None], [{}], [{"b64_json": ""}]])
async def test_malformed_source_image_is_not_charged(async_client, source_upstream, items):
    async def handler(request):
        return web.json_response({"data": items, "usage": USAGE})

    source, key, headers = await create_source_key(async_client, await source_upstream(handler))
    result = await async_client.post(
        "/v1/images/generations", headers=headers, json={"model": "gpt-image-2", "prompt": "test"}
    )
    assert result.status_code == 502
    await assert_settled(source, key, status="error", charged=False)

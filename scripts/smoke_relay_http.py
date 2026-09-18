"""Live Compass Responses test for Model Source account-pool pricing."""

from __future__ import annotations

import asyncio
import json
import os
import uuid
from datetime import timedelta
from math import isclose
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.core.usage.pricing import UsageTokens, calculate_cost_from_usage, get_pricing_for_model
from app.core.utils.time import utcnow
from app.db.models import ModelSource, RequestLog
from app.db.session import get_background_session
from app.modules.api_keys.repository import ApiKeysRepository
from app.modules.api_keys.service import ApiKeyCreateData, ApiKeysService
from app.modules.provider_billing.models import ProviderBillingEntry
from app.modules.usage.repository import UsageRepository

MODEL = "gpt-6-astra"
BASE_URL = os.environ.get("CODEX_LB_TEST_BASE_URL", "http://127.0.0.1:8080").rstrip("/")


async def _service() -> tuple[Any, ApiKeysService]:
    manager = get_background_session()
    session = await manager.__aenter__()
    return manager, ApiKeysService(ApiKeysRepository(session), usage_repository=UsageRepository(session))


async def _call(key: str) -> dict[str, Any]:
    request_id = str(uuid.uuid4())
    session_id = "pricing-selftest-" + uuid.uuid4().hex
    marker = "MODEL_SOURCE_PRICING_OK_" + uuid.uuid4().hex[:8]
    headers = {
        "Authorization": f"Bearer {key}",
        "Accept": "text/event-stream",
        "User-Agent": "codex-lb/model-source-pricing-selftest",
        "session_id": session_id,
        "x-codex-session-id": session_id,
        "x-request-id": request_id,
    }
    payload = {
        "model": MODEL,
        "instructions": "Reply with exactly the marker in the user message.",
        "input": [
            {
                "role": "user",
                "content": [{"type": "input_text", "text": marker}],
            }
        ],
        "store": False,
        "stream": True,
        "reasoning": {"effort": "low"},
    }
    async with httpx.AsyncClient(timeout=httpx.Timeout(180, connect=10)) as client:
        async with client.stream(
            "POST",
            f"{BASE_URL}/backend-api/codex/responses",
            headers=headers,
            json=payload,
        ) as response:
            if response.status_code != 200:
                detail = (await response.aread()).decode("utf-8", "replace")[:800]
                raise RuntimeError(f"HTTP {response.status_code} request_id={request_id} body={detail}")
            terminal = None
            usage = None
            failure = None
            output: list[str] = []
            async for line in response.aiter_lines():
                if not line.startswith("data:"):
                    continue
                raw = line[5:].strip()
                if not raw or raw == "[DONE]":
                    continue
                try:
                    event = json.loads(raw)
                except json.JSONDecodeError:
                    continue
                response_payload = event.get("response") or {}
                if event.get("type") == "response.output_text.delta":
                    output.append(str(event.get("delta") or ""))
                if event.get("type") in {"response.completed", "response.failed", "response.incomplete"}:
                    terminal = event.get("type")
                    usage = response_payload.get("usage")
                    failure = response_payload.get("error") or response_payload.get("incomplete_details")
                    break
    text = "".join(output).strip()
    if terminal != "response.completed" or not usage or marker not in text:
        raise AssertionError(
            f"bad pricing probe terminal={terminal} usage={bool(usage)} marker={marker in text} failure={failure!r}"
        )
    return {"requestId": request_id, "usagePresent": True, "markerObserved": True}


async def _call_alpha_search(key: str) -> int:
    async with httpx.AsyncClient(timeout=httpx.Timeout(30, connect=10)) as client:
        response = await client.post(
            f"{BASE_URL}/backend-api/codex/alpha/search?result_count=1",
            headers={
                "Authorization": f"Bearer {key}",
                "User-Agent": "codex-lb/request-log-hygiene-selftest",
                "content-type": "application/json",
            },
            json={"query": "OpenAI official website"},
        )
    return response.status_code


async def main() -> int:
    async with get_background_session() as session:
        sources = list(
            (
                await session.scalars(
                    select(ModelSource)
                    .options(selectinload(ModelSource.models))
                    .where(ModelSource.is_enabled.is_(True), ModelSource.supports_responses.is_(True))
                    .order_by(ModelSource.created_at)
                )
            ).unique()
        )
        source = next(
            (
                candidate
                for candidate in sources
                if "compass.llm.shopee.io" in candidate.base_url.lower()
                and any(model.model == MODEL and model.is_enabled for model in candidate.models)
            ),
            None,
        )
        if source is None:
            raise AssertionError(f"No enabled Compass Responses source provides {MODEL}")
        source_id = source.id

    created = None
    manager, service = await _service()
    try:
        created = await service.create_key(
            ApiKeyCreateData(
                name=f"__model_source_pricing_http_{uuid.uuid4().hex[:8]}__",
                allowed_models=[MODEL],
                assigned_account_ids=[],
                assigned_source_ids=[source_id],
                expires_at=utcnow() + timedelta(minutes=15),
            )
        )
    finally:
        await manager.__aexit__(None, None, None)

    try:
        result = await _call(created.key)
        row = None
        deadline = asyncio.get_running_loop().time() + 10
        while row is None and asyncio.get_running_loop().time() < deadline:
            async with get_background_session() as session:
                row = (
                    await session.scalars(
                        select(RequestLog)
                        .where(RequestLog.api_key_id == created.id)
                        .order_by(RequestLog.id.desc())
                        .limit(1)
                    )
                ).one_or_none()
                if row is not None:
                    snapshot = {
                        "requestLogId": row.id,
                        "status": row.status,
                        "sourceId": row.model_source_id,
                        "model": row.model,
                        "inputTokens": row.input_tokens,
                        "cachedInputTokens": row.cached_input_tokens,
                        "outputTokens": row.output_tokens,
                        "costUsd": row.cost_usd,
                    }
            if row is None:
                await asyncio.sleep(0.2)

        if row is None:
            raise AssertionError("Model Source pricing request log did not appear")
        async with get_background_session() as session:
            ledger = await session.scalar(
                select(ProviderBillingEntry).where(ProviderBillingEntry.request_log_id == snapshot["requestLogId"])
            )
            if (
                ledger is None
                or ledger.cost_usd != snapshot["costUsd"]
                or not ledger.pricing_version.startswith("sha256:")
            ):
                raise AssertionError("Durable billing evidence is missing or differs from the request log")
            snapshot["pricingVersion"] = ledger.pricing_version
        if (
            snapshot["status"] != "success"
            or snapshot["sourceId"] != source_id
            or snapshot["model"] != MODEL
            or snapshot["inputTokens"] is None
            or snapshot["outputTokens"] is None
            or snapshot["costUsd"] is None
            or snapshot["costUsd"] <= 0
        ):
            raise AssertionError(f"Model Source pricing log is incomplete: {snapshot}")

        resolved = get_pricing_for_model(MODEL)
        if resolved is None:
            raise AssertionError(f"Current account price catalog does not contain {MODEL}")
        _canonical_model, price = resolved
        expected = calculate_cost_from_usage(
            UsageTokens(
                input_tokens=snapshot["inputTokens"],
                output_tokens=snapshot["outputTokens"],
                cached_input_tokens=snapshot["cachedInputTokens"] or 0,
            ),
            price,
            service_tier=None,
        )
        if expected is None or not isclose(snapshot["costUsd"], expected, rel_tol=1e-12, abs_tol=1e-12):
            raise AssertionError(f"expected cost {expected}, got {snapshot['costUsd']}")

        control_http_status = await _call_alpha_search(created.key)
        control_snapshot = None
        deadline = asyncio.get_running_loop().time() + 10
        while control_snapshot is None and asyncio.get_running_loop().time() < deadline:
            async with get_background_session() as session:
                control_row = (
                    await session.scalars(
                        select(RequestLog)
                        .where(RequestLog.api_key_id == created.id, RequestLog.model == "")
                        .order_by(RequestLog.id.desc())
                        .limit(1)
                    )
                ).one_or_none()
                if control_row is not None:
                    control_snapshot = {
                        "status": control_row.status,
                        "source": control_row.source,
                        "requestKind": control_row.request_kind,
                        "inputTokens": control_row.input_tokens,
                        "outputTokens": control_row.output_tokens,
                        "costUsd": control_row.cost_usd,
                    }
            if control_snapshot is None:
                await asyncio.sleep(0.2)
        if (
            control_snapshot is None
            or control_snapshot["requestKind"] != "codex_control_alpha_search"
            or control_snapshot["inputTokens"] is not None
            or control_snapshot["outputTokens"] is not None
            or control_snapshot["costUsd"] is not None
        ):
            raise AssertionError(f"control request-log classification failed: {control_snapshot}")

        print(
            json.dumps(
                {
                    "transport": "http_sse",
                    "request": result,
                    "log": snapshot,
                    "controlHttpStatus": control_http_status,
                    "controlLog": control_snapshot,
                },
                indent=2,
                sort_keys=True,
            )
        )
        return 0
    finally:
        if created is not None:
            try:
                from app.modules.virtual_accounts.continuity import _reset_durable_http_bridge_scope

                await _reset_durable_http_bridge_scope(created.id)
            except Exception:
                pass
            manager, service = await _service()
            try:
                try:
                    await service.delete_key(created.id)
                except Exception:
                    pass
            finally:
                await manager.__aexit__(None, None, None)


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))

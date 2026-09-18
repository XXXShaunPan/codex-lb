import pytest
from sqlalchemy import select

from app.db.models import ModelSource, ModelSourceModel
from app.db.session import get_background_session
from app.modules.model_sources.forwarding import SourceUsage
from app.modules.provider_billing.models import ProviderBillingEntry
from app.modules.provider_billing.service import quote_usage
from app.modules.request_logs.repository import RequestLogsRepository
from app.modules.visitor_access.repository import VisitorStore


@pytest.mark.asyncio
async def test_source_account_list_and_unified_assignment(async_client):
    async with get_background_session() as session:
        session.add(
            ModelSource(
                id="src-native",
                name="Native Compass",
                kind="openai_compatible",
                base_url="https://example.invalid/v1",
                is_enabled=True,
            )
        )
        await session.commit()
    response = await async_client.get("/api/accounts")
    assert response.status_code == 200
    source = next(row for row in response.json()["accounts"] if row["accountId"] == "model-source:src-native")
    assert source["planType"] == "other"
    assert source["usage"]["secondaryRemainingPercent"] == 100
    overview = await async_client.get("/api/dashboard/overview")
    assert overview.status_code == 200
    assert any(row["accountId"] == source["accountId"] for row in overview.json()["accounts"])
    created = await async_client.post(
        "/api/api-keys", json={"name": "native-scope", "assignedAccountIds": [source["accountId"]]}
    )
    assert created.status_code == 200 or created.status_code == 201, created.text
    assert created.json()["assignedAccountIds"] == ["model-source:src-native"]
    assert created.json()["accountAssignmentScopeEnabled"] is True


@pytest.mark.asyncio
async def test_visitor_login_scope_mutation_denial_and_logout(async_client):
    first = (await async_client.post("/api/api-keys", json={"name": "allowed"})).json()
    second = (await async_client.post("/api/api-keys", json={"name": "private"})).json()
    store = VisitorStore()
    visitor = await store.create(
        username="native-visitor",
        display_name="Visitor",
        password="test-password-123",
        active=True,
        api_key_ids=[first["id"]],
    )
    login = await async_client.post(
        "/api/visitor/login", json={"username": visitor.username, "password": "test-password-123"}
    )
    assert login.status_code == 200, login.text
    assert login.json()["role"] == "guest"
    keys = await async_client.get("/api/api-keys")
    assert keys.status_code == 200
    assert [key["id"] for key in keys.json()] == [first["id"]]
    assert (await async_client.get(f"/api/api-keys/{second['id']}/usage-7d")).status_code == 403
    assert (await async_client.post("/api/api-keys", json={"name": "forbidden"})).status_code == 403
    assert (await async_client.get("/api/visitor/admin/visitors")).status_code == 403
    assert (await async_client.get("/api/accounts")).json() == {"accounts": []}
    assert (
        await async_client.post("/api/codex-config/regenerate", json={"apiKeyId": first["id"], "confirmReset": False})
    ).status_code == 409
    assert (
        await async_client.post("/api/codex-config/regenerate", json={"apiKeyId": second["id"], "confirmReset": True})
    ).status_code == 403
    rotated = await async_client.post(
        "/api/codex-config/regenerate", json={"apiKeyId": first["id"], "confirmReset": True}
    )
    assert rotated.status_code == 200, rotated.text
    assert rotated.json()["apiKey"]["key"] != first["key"]
    assert (
        await async_client.post("/api/codex-config/regenerate", json={"apiKeyId": first["id"], "confirmReset": True})
    ).status_code == 409
    options = await async_client.get("/api/reports/options")
    assert options.status_code == 200, options.text
    assert (await async_client.post("/api/dashboard-auth/logout")).status_code == 200
    assert (await async_client.get("/api/visitor/self")).status_code == 401


@pytest.mark.asyncio
async def test_billing_snapshot_persists_atomically_with_log(async_client):
    async with get_background_session() as session:
        source = ModelSource(
            id="src-billing",
            name="Billing",
            kind="openai_compatible",
            base_url="https://example.invalid/v1",
            is_enabled=True,
        )
        source.models = [ModelSourceModel(model="gpt-6-astra", is_enabled=True)]
        session.add(source)
        await session.commit()
        usage = SourceUsage(300_000, 10_000, 100_000)
        quote = quote_usage(source, "gpt-6-astra", usage)
        assert quote is not None
        log = await RequestLogsRepository(session).add_log(
            account_id=None,
            request_id="native-billing",
            model="gpt-6-astra",
            model_source_id=source.id,
            status="success",
            input_tokens=usage.input_tokens,
            output_tokens=usage.output_tokens,
            cached_input_tokens=usage.cached_input_tokens,
            cost_usd=quote.cost_usd,
            billing_quote=quote,
            latency_ms=100,
            error_code=None,
        )
        entry = await session.scalar(select(ProviderBillingEntry).where(ProviderBillingEntry.request_log_id == log.id))
        assert entry is not None
        assert entry.cost_usd == pytest.approx(4.95)
        assert entry.pricing_version == quote.pricing_version
        assert entry.rates_json == quote.rates_json
        assert entry.provider_cost_usd is None
    response = await async_client.get("/api/provider-billing/native-billing")
    assert response.status_code == 200
    assert response.json()["entries"][0]["cost_usd"] == pytest.approx(4.95)

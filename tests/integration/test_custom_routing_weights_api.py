import pytest
from sqlalchemy import select

from app.core.utils.time import utcnow
from app.db.models import Account, AccountStatus, ModelSource, ModelSourceModel
from app.db.session import get_background_session
from app.modules.proxy.account_cache import get_account_selection_cache
from app.modules.visitor_access.repository import VisitorStore


async def seed():
    async with get_background_session() as session:
        session.add(
            Account(
                id="routing-a",
                email="a@example.test",
                plan_type="plus",
                status=AccountStatus.ACTIVE,
                access_token_encrypted=b"test",
                refresh_token_encrypted=b"test",
                id_token_encrypted=b"test",
                last_refresh=utcnow(),
            )
        )
        session.add(
            ModelSource(
                id="routing-source",
                name="Compass test",
                kind="openai_compatible",
                base_url="https://example.invalid/v1",
            )
        )
        await session.commit()


@pytest.mark.asyncio
async def test_weights_default_persist_and_invalidate_selection_cache(async_client):
    await seed()
    response = await async_client.get("/api/relay-routing/weights")
    assert response.status_code == 200
    assert {row["accountId"]: row["weight"] for row in response.json()["accounts"]} == {
        "routing-a": 1,
        "model-source:routing-source": 1,
    }
    generation = get_account_selection_cache().generation
    for account_id, weight in [("routing-a", 2.5), ("model-source:routing-source", 0)]:
        response = await async_client.put(f"/api/relay-routing/weights/{account_id}", json={"weight": weight})
        assert response.status_code == 200, response.text
        assert response.json()["weight"] == weight
    assert get_account_selection_cache().generation > generation
    async with get_background_session() as session:
        assert await session.scalar(select(Account.routing_weight).where(Account.id == "routing-a")) == 2.5
        assert await session.scalar(select(ModelSource.routing_weight).where(ModelSource.id == "routing-source")) == 0
    response = await async_client.put("/api/settings", json={"routingStrategy": "custom_weighted_quota"})
    assert response.status_code == 200, response.text
    assert (await async_client.get("/api/settings")).json()["routingStrategy"] == "custom_weighted_quota"


@pytest.mark.asyncio
async def test_zero_weight_fixed_owner_is_retained_but_new_assignment_is_denied(async_client):
    from app.dependencies import get_proxy_service_for_app
    from app.main import app

    await seed()
    assert (await async_client.put("/api/relay-routing/weights/routing-a", json={"weight": 0})).status_code == 200
    balancer = get_proxy_service_for_app(app)._load_balancer
    fresh = await balancer.select_account(routing_strategy="custom_weighted_quota", account_ids={"routing-a"})
    assert fresh.account is None
    continued = await balancer.select_account(
        routing_strategy="custom_weighted_quota",
        account_ids={"routing-a"},
        required_account_id="routing-a",
        required_continuity_owner=True,
    )
    assert continued.account is not None and continued.account.id == "routing-a"


@pytest.mark.asyncio
async def test_embedding_source_selection_uses_weights_without_subscription_fallback(async_client):
    from app.modules.proxy.api import _select_embeddings_model_source

    await seed()
    async with get_background_session() as session:
        for source_id, weight in [("embed-zero", 0), ("embed-active", 3)]:
            source = ModelSource(
                id=source_id,
                name=source_id,
                base_url="https://example.invalid/v1",
                supports_embeddings=True,
                routing_weight=weight,
            )
            source.models = [ModelSourceModel(model="test-embedding", is_enabled=True)]
            session.add(source)
        await session.commit()
    assert (
        await async_client.put("/api/settings", json={"routingStrategy": "custom_weighted_quota"})
    ).status_code == 200
    selected = await _select_embeddings_model_source("test-embedding", None)
    assert selected is not None and selected.id == "embed-active"
    assert (
        await async_client.put("/api/relay-routing/weights/model-source:embed-active", json={"weight": 0})
    ).status_code == 200
    assert await _select_embeddings_model_source("test-embedding", None) is None
    assert (
        await async_client.post("/v1/embeddings", json={"model": "test-embedding", "input": "test"})
    ).status_code == 404


@pytest.mark.asyncio
@pytest.mark.parametrize("value", [-1, 1_000_001, True, False, "2", None, "NaN", "Infinity"])
async def test_invalid_weights_rejected(async_client, value):
    response = await async_client.put("/api/relay-routing/weights/routing-a", json={"weight": value})
    assert response.status_code == 422, response.text


@pytest.mark.asyncio
@pytest.mark.parametrize("literal", ["NaN", "Infinity", "-Infinity"])
async def test_nonfinite_json_number_is_rejected(async_client, literal):
    response = await async_client.put(
        "/api/relay-routing/weights/routing-a",
        content='{"weight":' + literal + "}",
        headers={"content-type": "application/json"},
    )
    assert response.status_code == 422, response.text


@pytest.mark.asyncio
async def test_missing_deleted_and_visitor_targets_are_denied(async_client):
    await seed()
    async with get_background_session() as session:
        row = await session.get(Account, "routing-a")
        row.delete_requested_at = utcnow()
        await session.commit()
    for account_id in ["routing-a", "missing", "model-source:missing"]:
        response = await async_client.put(f"/api/relay-routing/weights/{account_id}", json={"weight": 1})
        assert response.status_code == 404, response.text
    assert all(
        row["accountId"] != "routing-a"
        for row in (await async_client.get("/api/relay-routing/weights")).json()["accounts"]
    )
    visitor = await VisitorStore().create(
        username="weight-visitor", display_name="Visitor", password="test-password-123", active=True, api_key_ids=[]
    )
    assert (
        await async_client.post(
            "/api/visitor/login", json={"username": visitor.username, "password": "test-password-123"}
        )
    ).status_code == 200
    assert (await async_client.get("/api/relay-routing/weights")).status_code == 403
    assert (
        await async_client.put("/api/relay-routing/weights/model-source:routing-source", json={"weight": 1})
    ).status_code == 403

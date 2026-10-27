import hashlib
from datetime import timedelta

import pytest
from sqlalchemy import delete, select

from app.core.utils.time import utcnow
from app.db.models import ApiKey
from app.db.session import get_background_session
from app.modules.api_keys.repository import ApiKeysRepository
from app.modules.api_keys.service import ApiKeyInvalidError, ApiKeysService
from app.modules.codex_config.models import CodexApiToken
from app.modules.visitor_access.repository import VisitorStore

pytestmark = pytest.mark.integration


async def create_key(client, name="config-test"):
    response = await client.post("/api/api-keys", json={"name": name})
    assert response.status_code == 200, response.text
    return response.json()


@pytest.mark.asyncio
async def test_create_reuse_native_regeneration_and_delete(async_client):
    key = await create_key(async_client)
    status = await async_client.get("/api/codex-config/status", params={"apiKeyId": key["id"]})
    assert status.status_code == 200 and status.json()["tokenAvailable"]
    assert "no-store" in status.headers["cache-control"]
    assert key["key"] not in status.text
    assert key["key"] not in (await async_client.get("/api/api-keys")).text
    for _ in range(2):
        result = await async_client.post("/api/codex-config/generate", json={"apiKeyId": key["id"]})
        assert result.status_code == 200, result.text
        assert result.json()["apiKey"]["key"] == key["key"]
        assert result.json()["reset"] is False
        assert "no-store" in result.headers["cache-control"]
    denied = await async_client.post("/api/codex-config/generate", json={"apiKeyId": key["id"], "resetKey": True})
    assert denied.status_code == 409
    rotated = await async_client.post(f"/api/api-keys/{key['id']}/regenerate")
    assert rotated.status_code == 200, rotated.text
    token = rotated.json()["key"]
    assert token != key["key"]
    result = await async_client.post("/api/codex-config/generate", json={"apiKeyId": key["id"]})
    assert result.json()["apiKey"]["key"] == token
    async with get_background_session() as session:
        saved = await session.get(CodexApiToken, key["id"])
        assert saved.token == token
        service = ApiKeysService(ApiKeysRepository(session))
        assert (await service.validate_key(token)).id == key["id"]
        with pytest.raises(ApiKeyInvalidError):
            await service.validate_key(key["key"])
    assert (await async_client.delete(f"/api/api-keys/{key['id']}")).status_code in (200, 204)
    async with get_background_session() as session:
        assert await session.get(CodexApiToken, key["id"]) is None


@pytest.mark.asyncio
@pytest.mark.parametrize("stale", [False, True])
async def test_historical_or_mismatched_token_requires_explicit_confirmation(async_client, stale):
    key = await create_key(async_client)
    async with get_background_session() as session:
        if stale:
            (await session.get(CodexApiToken, key["id"])).token = "not-the-current-token"
        else:
            await session.execute(delete(CodexApiToken).where(CodexApiToken.api_key_id == key["id"]))
        await session.commit()
    status = await async_client.get("/api/codex-config/status", params={"apiKeyId": key["id"]})
    assert status.json()["resetRequired"]
    result = await async_client.post("/api/codex-config/generate", json={"apiKeyId": key["id"]})
    assert result.status_code == 409 and result.json()["error"]["code"] == "key_reset_required"
    async with get_background_session() as session:
        assert (await session.get(ApiKey, key["id"])).key_hash == hashlib.sha256(key["key"].encode()).hexdigest()
    result = await async_client.post("/api/codex-config/generate", json={"apiKeyId": key["id"], "confirmReset": True})
    assert result.status_code == 200 and result.json()["reset"]
    assert result.json()["apiKey"]["key"] != key["key"]


@pytest.mark.asyncio
async def test_visitor_scope_and_inactive_expired_keys(async_client):
    first = await create_key(async_client)
    second = await create_key(async_client, "private")
    visitor = await VisitorStore().create(
        username="config-visitor",
        display_name="Visitor",
        password="test-password-123",
        active=True,
        api_key_ids=[first["id"]],
    )
    assert (
        await async_client.post(
            "/api/visitor/login", json={"username": visitor.username, "password": "test-password-123"}
        )
    ).status_code == 200
    assert (await async_client.post("/api/codex-config/generate", json={"apiKeyId": first["id"]})).json()["apiKey"][
        "key"
    ] == first["key"]
    assert (await async_client.get("/api/codex-config/status", params={"apiKeyId": second["id"]})).status_code == 403
    assert (await async_client.post("/api/codex-config/generate", json={"apiKeyId": second["id"]})).status_code == 403
    for field, value in [("is_active", False), ("expires_at", utcnow() - timedelta(days=1))]:
        async with get_background_session() as session:
            row = await session.get(ApiKey, first["id"])
            row.is_active = True
            setattr(row, field, value)
            await session.commit()
        assert (
            await async_client.post("/api/codex-config/generate", json={"apiKeyId": first["id"]})
        ).status_code == 409
    assert (await async_client.put("/api/image-routing/settings", json={"hostModel": "gpt-5.4"})).status_code == 403
    assert (await async_client.get("/api/image-routing/settings")).status_code == 403


@pytest.mark.asyncio
async def test_token_write_failure_rolls_back_hash_and_creation(async_client, monkeypatch):
    key = await create_key(async_client)

    async def fail(*args):
        raise RuntimeError("simulated token persistence failure")

    monkeypatch.setattr(ApiKeysRepository, "save_token", fail)
    async with get_background_session() as session:
        with pytest.raises(RuntimeError, match="simulated"):
            await ApiKeysService(ApiKeysRepository(session)).regenerate_key(key["id"])
    async with get_background_session() as session:
        assert (await session.get(CodexApiToken, key["id"])).token == key["key"]
        assert (await session.get(ApiKey, key["id"])).key_hash == hashlib.sha256(key["key"].encode()).hexdigest()
        from app.modules.api_keys.service import ApiKeyCreateData

        with pytest.raises(RuntimeError, match="simulated"):
            await ApiKeysService(ApiKeysRepository(session)).create_key(
                ApiKeyCreateData(name="rollback", allowed_models=None)
            )
    async with get_background_session() as session:
        assert await session.scalar(select(ApiKey).where(ApiKey.name == "rollback")) is None

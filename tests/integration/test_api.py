"""Integration smoke tests — health, shipment CRUD, agent availability."""

import uuid

import pytest
from httpx import AsyncClient

from app.core.config import settings

API_KEY = settings.api_key or ""
HEADERS = {"X-API-Key": API_KEY}


@pytest.mark.asyncio
async def test_health_returns_ok(client: AsyncClient):
    resp = await client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] in ("ok", "degraded")
    assert "database" in data


@pytest.mark.asyncio
async def test_list_shipments_empty(client: AsyncClient):
    resp = await client.get("/api/v1/shipments", headers=HEADERS)
    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data
    assert "total" in data


@pytest.mark.asyncio
async def test_track_shipment_invalid_container(client: AsyncClient):
    """Invalid container format should return 422."""
    resp = await client.post(
        "/api/v1/shipments/track",
        headers=HEADERS,
        json={"container_number": "INVALID", "user_id": str(uuid.uuid4())},
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_get_shipment_not_found(client: AsyncClient):
    resp = await client.get(f"/api/v1/shipments/{uuid.uuid4()}", headers=HEADERS)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_agent_chat_missing_message(client: AsyncClient):
    """Empty message should return 400."""
    resp = await client.post(
        "/api/v1/agent/chat",
        headers=HEADERS,
        json={"user_id": str(uuid.uuid4()), "message": "   "},
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_unauthorized_without_api_key(client: AsyncClient):
    """Requests without X-API-Key must be rejected when API_KEY is set."""
    if not settings.api_key:
        pytest.skip("API_KEY not configured — auth enforcement skipped")
    resp = await client.get("/api/v1/shipments")
    assert resp.status_code == 401

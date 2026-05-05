"""Tests for API endpoints."""

import pytest


@pytest.mark.asyncio
async def test_health_check(client):
    response = await client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"


@pytest.mark.asyncio
async def test_list_beaches(client):
    response = await client.get("/api/v1/beaches")
    assert response.status_code == 200
    beaches = response.json()
    assert len(beaches) >= 7
    codes = {b["code"] for b in beaches}
    assert "diani" in codes
    assert "lamu" in codes
    assert "mombasa" in codes


@pytest.mark.asyncio
async def test_get_beach_detail(client):
    response = await client.get("/api/v1/beaches/diani")
    assert response.status_code == 200
    data = response.json()
    assert data["beach"]["code"] == "diani"
    assert "activities" in data


@pytest.mark.asyncio
async def test_get_beach_not_found(client):
    response = await client.get("/api/v1/beaches/nonexistent")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_get_activity_scores(client):
    response = await client.get("/api/v1/activities/diani")
    assert response.status_code == 200
    data = response.json()
    assert "surfing" in data
    assert "swimming" in data
    assert "kite_surfing" in data
    assert "kids_and_dogs" in data


@pytest.mark.asyncio
async def test_get_alerts(client):
    response = await client.get("/api/v1/alerts")
    assert response.status_code == 200
    assert isinstance(response.json(), list)

import pytest
import os
from httpx import AsyncClient, ASGITransport
from backend2.main import app
from backend2 import db

@pytest.fixture(autouse=True)
async def setup_test_db():
    os.environ["BACKEND2_DB_PATH"] = ":memory:"
    await db.close_connection()
    yield
    await db.close_connection()

@pytest.mark.live
@pytest.mark.asyncio
async def test_api_health_live():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

@pytest.mark.live
@pytest.mark.asyncio
async def test_api_account_live():
    # Tests the newly renamed /account endpoint
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get("/account")
    assert response.status_code == 200
    data = response.json()
    assert "cash" in data
    assert "account_value" in data
    assert "positions" in data

@pytest.mark.live
@pytest.mark.asyncio
async def test_api_workspace_overview_live():
    # Tests /overview which fetches benchmark and news
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get("/overview")
    assert response.status_code == 200
    data = response.json()
    assert "market_profile" in data
    assert "benchmark_quote" in data
    # benchmark_quote might be null if fetching fails, but keys should exist

@pytest.mark.live
@pytest.mark.asyncio
async def test_api_quote_live():
    # Tests /quote/AAPL
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get("/quote/AAPL")
    assert response.status_code == 200
    data = response.json()
    assert data["symbol"] == "AAPL"
    assert data["price"] > 0

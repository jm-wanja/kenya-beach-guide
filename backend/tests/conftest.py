"""Shared test fixtures."""

import asyncio

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from src.database import init_db


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="session")
async def setup_db():
    """Initialize the test database once per session."""
    await init_db()


@pytest_asyncio.fixture
async def client(setup_db):
    """Async test client for the FastAPI app."""
    from main import app

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

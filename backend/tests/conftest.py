import os
import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.db import get_db
from app.main import app
from app.models import Base, Project
from app.queue import get_arq_pool
from app.security import hash_api_key


class FakeArqPool:
    """Records enqueue_job calls instead of touching real Redis. Applied to
    every test by default (autouse) -- otherwise every test that hits
    /v1/ingest silently enqueues a real job into whatever Redis the dev
    environment points at, which is exactly what happened before this
    fixture existed: a real worker, started for the first time, found a
    backlog of jobs from every prior test run (harmless -- those call_ids
    only exist in the test database -- but not what a test suite should do)."""

    def __init__(self) -> None:
        self.enqueued: list[tuple[str, tuple[object, ...]]] = []

    async def enqueue_job(self, function: str, *args: object) -> None:
        self.enqueued.append((function, args))


TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL", "postgresql+asyncpg://debrief:debrief@localhost:5432/debrief_test"
)

test_engine = create_async_engine(TEST_DATABASE_URL)
TestSessionLocal = async_sessionmaker(test_engine, expire_on_commit=False)


@pytest.fixture(scope="session", autouse=True)
async def _schema():
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.fixture(autouse=True)
async def _clean_tables():
    yield
    async with test_engine.begin() as conn:
        for table in reversed(Base.metadata.sorted_tables):
            await conn.execute(table.delete())


@pytest.fixture
async def db_session():
    async with TestSessionLocal() as session:
        yield session


@pytest.fixture(autouse=True)
def fake_arq_pool():
    # .pop(..., None) rather than del: client()'s teardown may run first and
    # already clear this key, depending on fixture teardown order -- either
    # fixture cleaning up its own key should be a no-op if the other beat it there.
    pool = FakeArqPool()
    app.dependency_overrides[get_arq_pool] = lambda: pool
    yield pool
    app.dependency_overrides.pop(get_arq_pool, None)


@pytest.fixture
async def client():
    async def _get_db_override():
        async with TestSessionLocal() as session:
            yield session

    app.dependency_overrides[get_db] = _get_db_override
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.pop(get_db, None)


@pytest.fixture
def worker_ctx():
    """Minimal ctx for calling worker task functions directly, bypassing the
    real arq queue -- same session factory the API's test client uses, so
    a task's writes are visible to assertions in the same test."""
    return {"session_factory": TestSessionLocal, "anthropic_client": None}


@pytest.fixture
async def project(db_session):
    """Returns (Project row, raw API key) — the raw key only ever exists here."""
    raw_key = f"sk_test_{uuid.uuid4().hex}"
    p = Project(
        name="test-project", api_key_hash=hash_api_key(raw_key), api_key_prefix=raw_key[:12]
    )
    db_session.add(p)
    await db_session.commit()
    await db_session.refresh(p)
    return p, raw_key

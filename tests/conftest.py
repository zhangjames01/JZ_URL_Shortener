"""Shared fixtures for unit and integration tests."""

import os
from urllib.parse import urlsplit

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app

TEST_BASE_URL = "https://sho.rt"


@pytest.fixture
def settings():
    """Test settings: an in-memory database and a fixed public base URL."""
    return Settings(database_path=":memory:", base_url=TEST_BASE_URL)


@pytest.fixture
def client(settings):
    """A client for a freshly built app, so every test starts with an empty database."""
    return TestClient(create_app(settings))


# --- Postgres test support ---------------------------------------------------------


@pytest.fixture
def postgres_dsn():
    """Connection string of a *disposable* Postgres database, wiped before each test.

    Set TEST_DATABASE_URL to enable the Postgres tests. Without it they are skipped, so a
    plain `pytest` still works offline. In CI, REQUIRE_POSTGRES=1 turns "skipped" into
    "failed", so a broken database service cannot hide behind green skipped tests.
    """
    dsn = os.environ.get("TEST_DATABASE_URL")
    if not dsn:
        if os.environ.get("REQUIRE_POSTGRES") == "1":
            pytest.fail("REQUIRE_POSTGRES=1 but TEST_DATABASE_URL is not set")
        pytest.skip("TEST_DATABASE_URL not set; skipping Postgres tests")

    # These tests DROP tables, so refuse to run against anything that is not clearly a
    # throwaway test database.
    database_name = urlsplit(dsn).path.lstrip("/")
    if "test" not in database_name:
        pytest.fail(f"refusing to wipe database {database_name!r}: its name must contain 'test'")

    _wipe_postgres(dsn)
    return dsn


def _wipe_postgres(dsn):
    """Drop the app's table and id sequence so each test starts from a blank slate.

    The names below are part of the storage contract: PostgresUrlRepository must create
    exactly a `urls` table and a `url_id_seq` sequence.
    """
    import psycopg

    with psycopg.connect(dsn, autocommit=True) as conn:
        conn.execute("DROP TABLE IF EXISTS urls")
        conn.execute("DROP SEQUENCE IF EXISTS url_id_seq")


@pytest.fixture
def postgres_repo(postgres_dsn):
    """A PostgresUrlRepository on a freshly wiped database (closed after the test)."""
    from app.postgres_repository import PostgresUrlRepository

    repository = PostgresUrlRepository(postgres_dsn)
    yield repository
    repository.close()

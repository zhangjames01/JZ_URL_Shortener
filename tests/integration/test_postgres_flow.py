"""One end-to-end flow against a real Postgres database.

The repository contract tests already prove Postgres behaves like SQLite at the storage
level. This single flow only proves the whole app is wired to it correctly, so it does
not repeat the full integration suite.
"""

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from tests.conftest import TEST_BASE_URL

URL = "https://example.com/some/page"


@pytest.fixture
def postgres_client(postgres_dsn):
    settings = Settings(database_path=":memory:", base_url=TEST_BASE_URL, database_url=postgres_dsn)
    # Using the client as a context manager runs app startup and shutdown, which also
    # closes the connection pool.
    with TestClient(create_app(settings)) as client:
        yield client


def test_create_redirect_and_metadata_flow(postgres_client):
    client = postgres_client

    # A generated code comes from the Postgres sequence.
    generated = client.post("/api/v1/urls", json={"url": URL})
    assert generated.status_code == 201
    assert generated.json()["code"] == "1000000"

    # A custom alias works, and claiming it twice conflicts.
    assert client.post("/api/v1/urls", json={"url": URL, "alias": "promo"}).status_code == 201
    duplicate = client.post("/api/v1/urls", json={"url": URL, "alias": "promo"})
    assert duplicate.status_code == 409
    assert duplicate.json()["error"]["code"] == "ALIAS_TAKEN"

    # Redirecting counts a click, which the metadata endpoint reports.
    redirect = client.get("/promo", follow_redirects=False)
    assert redirect.status_code == 302
    assert redirect.headers["location"] == URL
    metadata = client.get("/api/v1/urls/promo").json()
    assert metadata["click_count"] == 1
    assert metadata["last_accessed_at"] is not None

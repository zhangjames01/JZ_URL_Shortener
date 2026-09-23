"""HTTP-level tests for GET /api/v1/urls/{code} (link metadata and click statistics)."""

from datetime import datetime

from tests.conftest import TEST_BASE_URL

URL = "https://example.com/some/page"


def create(client, **body):
    return client.post("/api/v1/urls", json={"url": URL, **body}).json()["code"]


def test_fresh_link_returns_all_fields_with_zero_clicks(client):
    code = create(client)

    response = client.get(f"/api/v1/urls/{code}")

    assert response.status_code == 200
    body = response.json()
    assert body["code"] == code
    assert body["short_url"] == f"{TEST_BASE_URL}/{code}"
    assert body["original_url"] == URL
    datetime.fromisoformat(body["created_at"])  # must be a valid ISO-8601 timestamp
    assert body["click_count"] == 0
    assert body["last_accessed_at"] is None


def test_visits_through_the_redirect_show_up_in_the_metadata(client):
    # End to end: the public redirect and the metadata endpoint agree on click counts.
    code = create(client)

    for _ in range(3):
        client.get(f"/{code}", follow_redirects=False)

    body = client.get(f"/api/v1/urls/{code}").json()
    assert body["click_count"] == 3
    datetime.fromisoformat(body["last_accessed_at"])


def test_reading_the_metadata_does_not_change_the_click_count(client):
    code = create(client)

    for _ in range(3):
        client.get(f"/api/v1/urls/{code}")

    assert client.get(f"/api/v1/urls/{code}").json()["click_count"] == 0


def test_metadata_works_for_a_custom_alias(client):
    create(client, alias="promo")

    response = client.get("/api/v1/urls/promo")

    assert response.status_code == 200
    assert response.json()["code"] == "promo"


def test_unknown_code_returns_404_in_the_error_envelope(client):
    response = client.get("/api/v1/urls/nope123")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"

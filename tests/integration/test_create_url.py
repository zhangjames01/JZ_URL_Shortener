"""HTTP-level tests for POST /api/v1/urls (status codes, body shape, error envelope)."""

from datetime import datetime

from tests.conftest import TEST_BASE_URL

URL = "https://example.com/some/very/long/page"


def test_create_returns_201_with_the_link_details(client):
    response = client.post("/api/v1/urls", json={"url": URL})

    assert response.status_code == 201
    body = response.json()
    assert body["code"] == "1000000"
    assert body["short_url"] == f"{TEST_BASE_URL}/1000000"
    assert body["original_url"] == URL
    datetime.fromisoformat(body["created_at"])  # must be a valid ISO-8601 timestamp


def test_each_create_gets_a_new_code(client):
    first = client.post("/api/v1/urls", json={"url": URL}).json()
    second = client.post("/api/v1/urls", json={"url": URL}).json()

    assert (first["code"], second["code"]) == ("1000000", "1000001")


def test_invalid_url_returns_422_in_the_error_envelope(client):
    response = client.post("/api/v1/urls", json={"url": "javascript:alert(1)"})

    assert response.status_code == 422
    error = response.json()["error"]
    assert error["code"] == "INVALID_URL"
    assert isinstance(error["message"], str)


def test_missing_field_uses_the_same_error_envelope(client):
    response = client.post("/api/v1/urls", json={})

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_wrong_field_type_uses_the_same_error_envelope(client):
    response = client.post("/api/v1/urls", json={"url": 123})

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_malformed_json_uses_the_same_error_envelope(client):
    response = client.post(
        "/api/v1/urls", content=b"{not json", headers={"Content-Type": "application/json"}
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"

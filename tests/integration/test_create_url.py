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


# --- custom aliases ---


def test_create_with_alias_returns_it_as_the_code(client):
    response = client.post("/api/v1/urls", json={"url": URL, "alias": "promo"})

    assert response.status_code == 201
    body = response.json()
    assert body["code"] == "promo"
    assert body["short_url"] == f"{TEST_BASE_URL}/promo"


def test_null_alias_means_auto_generate(client):
    response = client.post("/api/v1/urls", json={"url": URL, "alias": None})

    assert response.status_code == 201
    assert response.json()["code"] == "1000000"


def test_taken_alias_returns_409(client):
    client.post("/api/v1/urls", json={"url": URL, "alias": "promo"})

    response = client.post("/api/v1/urls", json={"url": URL, "alias": "promo"})

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "ALIAS_TAKEN"


def test_invalid_alias_returns_422(client):
    response = client.post("/api/v1/urls", json={"url": URL, "alias": "no spaces"})

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "INVALID_ALIAS"


def test_reserved_alias_returns_422(client):
    response = client.post("/api/v1/urls", json={"url": URL, "alias": "api"})

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "INVALID_ALIAS"


def test_empty_alias_is_invalid_not_absent(client):
    response = client.post("/api/v1/urls", json={"url": URL, "alias": ""})

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "INVALID_ALIAS"


def test_non_string_alias_is_a_validation_error(client):
    response = client.post("/api/v1/urls", json={"url": URL, "alias": 123})

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_alias_equal_to_the_next_generated_code_does_not_break_generation(client):
    client.post("/api/v1/urls", json={"url": URL, "alias": "1000000"})

    response = client.post("/api/v1/urls", json={"url": URL})

    assert response.status_code == 201
    assert response.json()["code"] == "1000001"

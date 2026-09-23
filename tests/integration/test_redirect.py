"""HTTP-level tests for GET /{code} and for the shared error envelope on unknown routes."""

URL = "https://example.com/some/page?x=1&y=two#section"


def create(client, **body):
    return client.post("/api/v1/urls", json={"url": URL, **body}).json()["code"]


def test_known_code_redirects_with_302_to_the_original_url(client):
    code = create(client)

    # follow_redirects=False so we inspect the redirect itself, not the destination.
    response = client.get(f"/{code}", follow_redirects=False)

    assert response.status_code == 302
    assert response.headers["location"] == URL


def test_location_is_the_stored_url_exactly_including_query_and_fragment(client):
    code = create(client)

    location = client.get(f"/{code}", follow_redirects=False).headers["location"]

    assert location == URL  # not re-encoded or normalised on the way out


def test_custom_alias_redirects(client):
    create(client, alias="promo")

    response = client.get("/promo", follow_redirects=False)

    assert response.status_code == 302
    assert response.headers["location"] == URL


def test_lookup_is_case_sensitive(client):
    create(client, alias="Promo")

    # The exact spelling works, so the 404 below can only come from the case difference.
    assert client.get("/Promo", follow_redirects=False).status_code == 302
    assert client.get("/promo", follow_redirects=False).status_code == 404


def test_unknown_code_returns_404_in_the_error_envelope(client):
    response = client.get("/nope123", follow_redirects=False)

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"


# --- the catch-all /{code} route must not swallow the service's own routes ---


def test_health_check_is_not_shadowed_by_the_redirect_route(client):
    assert client.get("/healthz").json() == {"status": "ok"}


def test_api_docs_are_not_shadowed_by_the_redirect_route(client):
    assert client.get("/docs").status_code == 200


# --- Starlette's own HTTP errors use the same envelope ---


def test_unknown_deeper_path_returns_404_in_the_error_envelope(client):
    response = client.get("/nope/deeper")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"


def test_wrong_method_returns_405_in_the_error_envelope(client):
    response = client.post("/healthz")

    assert response.status_code == 405
    assert response.json()["error"]["code"] == "METHOD_NOT_ALLOWED"

"""Guards the reserved-alias list against drifting out of sync with the app's routes."""

import pytest

from app.errors import InvalidAliasError
from app.validation import validate_alias


def _route_paths(app):
    """Every fixed path the app serves, gathered from public FastAPI interfaces only.

    - `app.openapi()["paths"]` lists all API routes with their full prefixes (routers
      added through include_router are wrapped in objects that have no `.path`).
    - Top-level routes with a `.path` add the framework's own /docs, /redoc and
      /openapi.json, which are not part of the OpenAPI schema.
    """
    paths = set(app.openapi()["paths"])
    paths.update(route.path for route in app.routes if hasattr(route, "path"))
    return paths


def _first_segments(paths):
    """First path segment of each path, e.g. "/api/v1/urls" -> "api".

    Paths whose first segment is a path parameter (like "/{code}") are skipped: that is
    the route aliases are served from, not a fixed word an alias could collide with.
    """
    segments = {path.strip("/").split("/")[0] for path in paths}
    return {segment for segment in segments if segment and not segment.startswith("{")}


def test_every_root_level_route_is_unavailable_as_an_alias(client):
    segments = _first_segments(_route_paths(client.app))

    # Sanity check that the discovery really found our routes, so the loop below
    # cannot pass vacuously.
    assert {"api", "healthz", "docs", "redoc", "openapi.json"} <= segments
    for segment in segments:
        with pytest.raises(InvalidAliasError):
            validate_alias(segment)

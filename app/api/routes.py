"""HTTP routes. Deliberately thin: translate HTTP to service calls and back."""

from fastapi import APIRouter
from fastapi.responses import RedirectResponse

from app.repository import UrlRecord
from app.schemas import CreateUrlRequest, UrlResponse
from app.service import ShortenerService


def _to_response(record: UrlRecord, base_url: str) -> UrlResponse:
    """Single place that shapes a stored record for API clients (create and metadata)."""
    return UrlResponse(
        code=record.code,
        short_url=f"{base_url}/{record.code}",
        original_url=record.original_url,
        created_at=record.created_at,
        click_count=record.click_count,
        last_accessed_at=record.last_accessed_at,
    )


def build_router(service: ShortenerService, base_url: str) -> APIRouter:
    """Create the router with its dependencies passed in (no module-level globals)."""
    router = APIRouter()

    # A plain `def` (not async) is intentional: the SQLite calls block, so FastAPI runs
    # this handler in its threadpool instead of stalling the event loop.
    @router.post("/api/v1/urls", status_code=201, response_model=UrlResponse)
    def create_url(body: CreateUrlRequest) -> UrlResponse:
        return _to_response(service.create(body.url, body.alias), base_url)

    @router.get("/api/v1/urls/{code}", response_model=UrlResponse)
    def get_url(code: str) -> UrlResponse:
        # Read-only: looking at the stats is not a visit, so no click is recorded.
        return _to_response(service.get_link(code), base_url)

    return router


def build_redirect_router(service: ShortenerService) -> APIRouter:
    """Router for the public short links: GET /{code} redirects to the original URL."""
    router = APIRouter()

    # 302 (temporary) rather than 301 on purpose: browsers cache a 301, so repeat
    # visits would never reach the server and clicks would be undercounted.
    @router.get("/{code}", status_code=302, response_class=RedirectResponse)
    def redirect(code: str) -> RedirectResponse:
        return RedirectResponse(service.visit(code), status_code=302)

    return router

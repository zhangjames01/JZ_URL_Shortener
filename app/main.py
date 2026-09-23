"""Application wiring: build the object graph (repository -> service -> routes)."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.error_handlers import register_error_handlers
from app.api.routes import build_redirect_router, build_router
from app.config import Settings
from app.postgres_repository import PostgresUrlRepository
from app.repository import SqliteUrlRepository, UrlRepository
from app.service import ShortenerService


def build_repository(settings: Settings) -> UrlRepository:
    """Use PostgreSQL when DATABASE_URL is set (production), otherwise a local SQLite file."""
    if settings.database_url:
        return PostgresUrlRepository(settings.database_url)
    return SqliteUrlRepository(settings.database_path)


def create_app(settings: Settings | None = None) -> FastAPI:
    """Build an app instance. Tests pass their own settings (e.g. an in-memory database).

    There is intentionally no module-level `app`: importing this module must not open a
    database. Run with `uvicorn app.main:create_app --factory`.
    """
    settings = settings or Settings.from_env()

    repository = build_repository(settings)
    service = ShortenerService(repository)

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        yield
        # Runs at shutdown: release database connections cleanly.
        repository.close()

    app = FastAPI(title="URL Shortener", lifespan=lifespan)
    app.include_router(build_router(service, settings.base_url))
    register_error_handlers(app)

    @app.get("/healthz")
    def healthz() -> dict[str, str]:
        return {"status": "ok"}

    # Must be registered last: "/{code}" matches any single path segment, so adding it
    # earlier would shadow /healthz and the framework's /docs and /redoc.
    app.include_router(build_redirect_router(service))

    return app

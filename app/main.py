"""Application wiring: build the object graph (repository -> service -> routes)."""

from fastapi import FastAPI

from app.api.error_handlers import register_error_handlers
from app.api.routes import build_router
from app.config import Settings
from app.repository import SqliteUrlRepository
from app.service import ShortenerService


def create_app(settings: Settings | None = None) -> FastAPI:
    """Build an app instance. Tests pass their own settings (e.g. an in-memory database).

    There is intentionally no module-level `app`: importing this module must not open a
    database. Run with `uvicorn app.main:create_app --factory`.
    """
    settings = settings or Settings.from_env()

    repository = SqliteUrlRepository(settings.database_path)
    service = ShortenerService(repository)

    app = FastAPI(title="URL Shortener")
    app.include_router(build_router(service, settings.base_url))
    register_error_handlers(app)

    @app.get("/healthz")
    def healthz() -> dict[str, str]:
        return {"status": "ok"}

    return app

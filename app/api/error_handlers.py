"""Translate errors into one consistent JSON shape:

    {"error": {"code": "<MACHINE_READABLE>", "message": "<human readable>"}}

This is the only place that maps domain errors to HTTP status codes, so the service and
storage layers stay free of web concerns.
"""

import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.errors import InvalidUrlError

logger = logging.getLogger(__name__)


def _error(status: int, code: str, message: str) -> JSONResponse:
    return JSONResponse(status_code=status, content={"error": {"code": code, "message": message}})


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(InvalidUrlError)
    async def invalid_url(_: Request, exc: InvalidUrlError) -> JSONResponse:
        return _error(422, "INVALID_URL", str(exc))

    # Overrides FastAPI's default 422 body (a list of objects) so clients only ever
    # have to handle a single error shape.
    @app.exception_handler(RequestValidationError)
    async def validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
        problems = "; ".join(
            f"{'.'.join(str(part) for part in err['loc'][1:]) or 'body'}: {err['msg']}"
            for err in exc.errors()
        )
        return _error(422, "VALIDATION_ERROR", problems)

    @app.exception_handler(Exception)
    async def unexpected(_: Request, exc: Exception) -> JSONResponse:
        # Log the details server-side but never leak internals to the client.
        logger.exception("Unhandled error", exc_info=exc)
        return _error(500, "INTERNAL_ERROR", "An unexpected error occurred")

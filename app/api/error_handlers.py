"""Translate errors into one consistent JSON shape:

    {"error": {"code": "<MACHINE_READABLE>", "message": "<human readable>"}}

This is the only place that maps domain errors to HTTP status codes, so the service and
storage layers stay free of web concerns.
"""

import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.errors import AliasTakenError, InvalidAliasError, InvalidUrlError, NotFoundError

logger = logging.getLogger(__name__)


_HTTP_ERRORS = {
    404: ("NOT_FOUND", "Resource not found"),
    405: ("METHOD_NOT_ALLOWED", "Method not allowed"),
}


def _error(status: int, code: str, message: str) -> JSONResponse:
    return JSONResponse(status_code=status, content={"error": {"code": code, "message": message}})


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(InvalidUrlError)
    async def invalid_url(_: Request, exc: InvalidUrlError) -> JSONResponse:
        return _error(422, "INVALID_URL", str(exc))

    @app.exception_handler(InvalidAliasError)
    async def invalid_alias(_: Request, exc: InvalidAliasError) -> JSONResponse:
        return _error(422, "INVALID_ALIAS", str(exc))

    @app.exception_handler(AliasTakenError)
    async def alias_taken(_: Request, exc: AliasTakenError) -> JSONResponse:
        return _error(409, "ALIAS_TAKEN", f"Alias '{exc}' is already in use")

    @app.exception_handler(NotFoundError)
    async def not_found(_: Request, exc: NotFoundError) -> JSONResponse:
        return _error(404, "NOT_FOUND", f"No short link exists for '{exc}'")

    # Framework-level HTTP errors (unknown path, wrong method) get the same envelope.
    # This also covers any HTTPException a future route might raise.
    @app.exception_handler(StarletteHTTPException)
    async def http_error(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        code, message = _HTTP_ERRORS.get(exc.status_code, ("HTTP_ERROR", str(exc.detail)))
        return _error(exc.status_code, code, message)

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

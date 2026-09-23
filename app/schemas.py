"""Request and response bodies for the HTTP API."""

from datetime import datetime

from pydantic import BaseModel


class CreateUrlRequest(BaseModel):
    # Only the shape is checked here; the business rules live in app.validation.
    url: str
    # Optional custom short code. None means "generate one for me".
    alias: str | None = None


class UrlResponse(BaseModel):
    code: str
    short_url: str
    original_url: str
    created_at: datetime
    click_count: int
    last_accessed_at: datetime | None

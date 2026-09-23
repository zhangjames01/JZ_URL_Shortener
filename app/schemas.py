"""Request and response bodies for the HTTP API."""

from datetime import datetime

from pydantic import BaseModel


class CreateUrlRequest(BaseModel):
    # Only the shape is checked here; the business rules live in app.validation.
    url: str


class UrlResponse(BaseModel):
    code: str
    short_url: str
    original_url: str
    created_at: datetime

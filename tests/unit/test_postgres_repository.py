"""Tests for behaviour that is specific to the Postgres backend.

Behaviour shared by all backends lives in test_repository_contract.py.
"""

from datetime import UTC, datetime, timedelta, timezone

from app.postgres_repository import PostgresUrlRepository
from app.repository import UrlRecord


def test_returned_datetimes_are_utc_even_when_the_database_session_is_not(postgres_dsn):
    # Postgres hands timestamps back in the *session* time zone. The API must always
    # report UTC, so the repository must not depend on how the session is configured.
    # We force a non-UTC session (UTC+5:30) so this test fails if normalisation is lost.
    kolkata_dsn = postgres_dsn + "?options=-c%20TimeZone%3DAsia%2FKolkata"
    repository = PostgresUrlRepository(kolkata_dsn)
    try:
        created = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
        repository.add(
            UrlRecord(code="abc123", original_url="https://example.com", created_at=created)
        )
        repository.record_click("abc123", at=created)

        stored = repository.get("abc123")
    finally:
        repository.close()

    assert stored.created_at.utcoffset() == timedelta(0)
    assert stored.last_accessed_at.utcoffset() == timedelta(0)
    assert stored.created_at == created


def test_offset_datetimes_keep_the_same_instant(postgres_repo):
    # A caller may pass any timezone-aware datetime; the instant must be preserved.
    plus_five = timezone(timedelta(hours=5))
    created = datetime(2026, 1, 1, 17, 0, tzinfo=plus_five)  # 12:00 UTC
    postgres_repo.add(
        UrlRecord(code="abc123", original_url="https://example.com", created_at=created)
    )

    assert postgres_repo.get("abc123").created_at == datetime(2026, 1, 1, 12, 0, tzinfo=UTC)


def test_creating_the_repository_twice_is_safe(postgres_dsn):
    # An app restart builds the repository again against an existing schema, so schema
    # creation must be idempotent and must not disturb existing data.
    first = PostgresUrlRepository(postgres_dsn)
    first.add(
        UrlRecord(
            code="keep",
            original_url="https://example.com",
            created_at=datetime(2026, 1, 1, tzinfo=UTC),
        )
    )
    first.close()

    second = PostgresUrlRepository(postgres_dsn)
    try:
        assert second.get("keep") is not None
    finally:
        second.close()

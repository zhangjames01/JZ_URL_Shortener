"""Tests for the shortener service (business rules), using a real in-memory repository."""

from datetime import UTC, datetime

import pytest
from app.service import MAX_CODE_ATTEMPTS, ShortenerService

from app.errors import CodeGenerationError, InvalidUrlError
from app.repository import SqliteUrlRepository, UrlRecord

NOW = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
URL = "https://example.com/page"


@pytest.fixture
def repo():
    return SqliteUrlRepository(":memory:")


@pytest.fixture
def service(repo):
    # The clock is injected so tests get a fixed created_at instead of the real time.
    return ShortenerService(repo, clock=lambda: NOW)


def occupy(repo, code):
    """Store a record under `code`, as if someone had already claimed it."""
    repo.add(UrlRecord(code=code, original_url="https://taken.example", created_at=NOW))


def test_create_returns_a_new_record_with_the_generated_code(service):
    record = service.create(URL)

    assert record == UrlRecord(code="1000000", original_url=URL, created_at=NOW)
    assert record.click_count == 0


def test_create_persists_the_record(service, repo):
    record = service.create(URL)

    assert repo.get(record.code) == record


def test_create_stores_the_trimmed_url(service):
    assert service.create("  " + URL + "  ").original_url == URL


def test_create_generates_a_different_code_each_time(service):
    assert service.create(URL).code != service.create(URL).code


def test_create_rejects_an_invalid_url_and_stores_nothing(service, repo):
    with pytest.raises(InvalidUrlError):
        service.create("ftp://example.com")

    assert repo.get("1000000") is None


def test_create_skips_a_code_that_is_already_taken(service, repo):
    # A code can be taken before the counter reaches it (e.g. a custom alias).
    occupy(repo, "1000000")

    assert service.create(URL).code == "1000001"


def test_create_gives_up_after_too_many_consecutive_collisions(service, repo):
    # Bounded retries: a bug or a hostile alias pattern must not cause an endless loop.
    for counter in range(1, MAX_CODE_ATTEMPTS + 1):
        occupy(repo, f"{1000000 + counter - 1}")

    with pytest.raises(CodeGenerationError):
        service.create(URL)

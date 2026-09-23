"""Tests for the shortener service (business rules), using a real in-memory repository."""

import logging
from datetime import UTC, datetime

import pytest

from app.errors import (
    AliasTakenError,
    CodeGenerationError,
    InvalidAliasError,
    InvalidUrlError,
    NotFoundError,
)
from app.repository import SqliteUrlRepository, UrlRecord
from app.service import MAX_CODE_ATTEMPTS, ShortenerService

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


# --- custom aliases ---


def test_create_with_alias_uses_the_alias_as_the_code(service, repo):
    record = service.create(URL, alias="promo")

    assert record == UrlRecord(code="promo", original_url=URL, created_at=NOW)
    assert repo.get("promo") == record


def test_create_without_alias_behaves_as_before(service):
    assert service.create(URL, alias=None).code == "1000000"


def test_alias_does_not_consume_a_counter_value(service):
    # Custom links must not leave gaps in the generated sequence.
    service.create(URL, alias="promo")

    assert service.create(URL).code == "1000000"


def test_taken_alias_is_rejected_and_the_original_is_kept(service, repo):
    service.create("https://first.example", alias="promo")

    with pytest.raises(AliasTakenError):
        service.create("https://second.example", alias="promo")

    assert repo.get("promo").original_url == "https://first.example"


def test_invalid_alias_is_rejected_and_nothing_is_stored(service, repo):
    with pytest.raises(InvalidAliasError):
        service.create(URL, alias="no spaces allowed")

    assert repo.get("no spaces allowed") is None


def test_invalid_url_with_a_valid_alias_leaves_the_alias_free(service, repo):
    # Everything is validated before anything is written.
    with pytest.raises(InvalidUrlError):
        service.create("ftp://example.com", alias="promo")

    assert repo.get("promo") is None
    assert service.create(URL, alias="promo").code == "promo"


def test_alias_matching_a_future_generated_code_is_skipped_by_the_counter(service):
    # Someone claims exactly the code the counter would produce next.
    service.create(URL, alias="1000000")

    assert service.create(URL).code == "1000001"


# --- visiting a link (redirect + click tracking) ---


def test_visit_returns_the_original_url_for_a_generated_code(service):
    record = service.create(URL)

    assert service.visit(record.code) == URL


def test_visit_returns_the_original_url_for_a_custom_alias(service):
    service.create(URL, alias="promo")

    assert service.visit("promo") == URL


def test_visit_unknown_code_raises_not_found(service):
    with pytest.raises(NotFoundError):
        service.visit("nope123")


def test_visit_records_a_click_with_the_current_time(service, repo):
    record = service.create(URL)

    service.visit(record.code)

    stored = repo.get(record.code)
    assert stored.click_count == 1
    assert stored.last_accessed_at == NOW


def test_each_visit_adds_one_click(service, repo):
    record = service.create(URL)

    service.visit(record.code)
    service.visit(record.code)

    assert repo.get(record.code).click_count == 2


def test_visiting_an_unknown_code_creates_no_record(service, repo):
    with pytest.raises(NotFoundError):
        service.visit("nope123")

    assert repo.get("nope123") is None


class _RepoWithBrokenClickTracking:
    """Delegates to a real repository, but click recording always fails."""

    def __init__(self, inner):
        self._inner = inner

    def __getattr__(self, name):
        return getattr(self._inner, name)

    def record_click(self, code, at):
        raise RuntimeError("analytics storage is down")


def test_a_click_tracking_failure_is_logged_but_never_blocks_the_redirect(repo, caplog):
    # Analytics are secondary: the visitor must still reach their destination.
    service = ShortenerService(_RepoWithBrokenClickTracking(repo), clock=lambda: NOW)
    record = service.create(URL)

    with caplog.at_level(logging.ERROR):
        result = service.visit(record.code)

    assert result == URL
    assert "analytics storage is down" in caplog.text


# --- reading link metadata ---


def test_get_link_returns_the_stored_record(service):
    created = service.create(URL)
    aliased = service.create(URL, alias="promo")

    assert service.get_link(created.code) == created
    assert service.get_link("promo") == aliased


def test_get_link_unknown_code_raises_not_found(service):
    with pytest.raises(NotFoundError):
        service.get_link("nope123")


def test_get_link_does_not_count_as_a_click(service):
    # Only a real visit (the redirect) is a click; looking at stats must not inflate them.
    record = service.create(URL)

    service.get_link(record.code)
    service.get_link(record.code)

    stored = service.get_link(record.code)
    assert stored.click_count == 0
    assert stored.last_accessed_at is None


def test_get_link_reflects_recorded_visits(service):
    record = service.create(URL)
    service.visit(record.code)
    service.visit(record.code)

    stored = service.get_link(record.code)

    assert stored.click_count == 2
    assert stored.last_accessed_at == NOW

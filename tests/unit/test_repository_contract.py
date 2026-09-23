"""Contract tests for the URL repository, run against every storage backend.

The repository is the storage layer: it saves, fetches and updates URL records and
knows nothing about HTTP or business rules. Every implementation must pass exactly the
same tests, which is what makes swapping backends safe. The `repo` fixture below runs
each test once per backend; the Postgres run is skipped when no test database is
configured (see `postgres_dsn` in conftest.py).
"""

from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime

import pytest

from app.errors import DuplicateCodeError
from app.repository import SqliteUrlRepository, UrlRecord

# Fixed timestamps keep the tests deterministic (no dependence on the real clock).
CREATED_AT = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
CLICKED_AT = datetime(2026, 1, 2, 9, 30, tzinfo=UTC)


@pytest.fixture(params=["sqlite", "postgres"])
def repo(request):
    """A new, empty repository for every test, once per backend.

    SQLite uses ":memory:", so the database lives in RAM and vanishes afterwards and
    tests cannot leak state into each other. Postgres uses a disposable test database
    that is wiped before each test.
    """
    if request.param == "sqlite":
        repository = SqliteUrlRepository(":memory:")
    else:
        repository = request.getfixturevalue("postgres_repo")
    yield repository
    repository.close()


def make_record(code="abc123", url="https://example.com/a"):
    """Build a record with defaults so each test only specifies what it cares about."""
    return UrlRecord(code=code, original_url=url, created_at=CREATED_AT)


def test_get_returns_none_for_unknown_code(repo):
    # A missing code is a normal outcome, not an error at this layer. Turning it into
    # a 404 is the service layer's responsibility.
    assert repo.get("nope") is None


def test_add_then_get_round_trips_the_record(repo):
    # Every field must survive storage, including timezone-aware datetimes.
    # A new record starts with zero clicks and no last-access time.
    repo.add(make_record())

    found = repo.get("abc123")

    assert found == UrlRecord(
        code="abc123",
        original_url="https://example.com/a",
        created_at=CREATED_AT,
        click_count=0,
        last_accessed_at=None,
    )


def test_add_rejects_a_duplicate_code(repo):
    # Codes are unique. The database enforces this (PRIMARY KEY), which keeps custom
    # aliases and generated codes safe even if two requests collide. The repository
    # raises our own DuplicateCodeError so callers never depend on sqlite3 types.
    repo.add(make_record())

    with pytest.raises(DuplicateCodeError):
        repo.add(make_record(url="https://example.com/other"))


def test_duplicate_add_does_not_overwrite_the_original(repo):
    # A rejected insert must leave the existing record untouched. This guards against
    # "upsert"-style implementations that would silently hijack an existing short link.
    repo.add(make_record())
    with pytest.raises(DuplicateCodeError):
        repo.add(make_record(url="https://example.com/other"))

    assert repo.get("abc123").original_url == "https://example.com/a"


def test_same_long_url_can_have_many_codes(repo):
    # No deduplication by design: each short code is its own link with its own
    # click statistics, even when two codes point at the same destination.
    repo.add(make_record(code="one"))
    repo.add(make_record(code="two"))

    assert repo.get("one") is not None
    assert repo.get("two") is not None


def test_record_click_increments_count_and_sets_last_accessed(repo):
    # Click tracking is one atomic SQL UPDATE ("click_count = click_count + 1"),
    # not read-then-write in Python, which would lose counts under concurrent requests.
    repo.add(make_record())

    repo.record_click("abc123", at=CLICKED_AT)
    repo.record_click("abc123", at=CLICKED_AT)

    found = repo.get("abc123")
    assert found.click_count == 2
    assert found.last_accessed_at == CLICKED_AT


def test_record_click_on_unknown_code_is_a_no_op(repo):
    # The repository does not decide whether an unknown code is an error; it simply
    # updates nothing. The service layer owns that decision.
    repo.record_click("nope", at=CLICKED_AT)  # must not raise

    assert repo.get("nope") is None


def test_add_rejects_naive_datetimes(repo):
    # A timestamp without a timezone is ambiguous once stored as text, so we refuse it
    # up front rather than persist something we can't interpret reliably later.
    naive = UrlRecord(
        code="abc123",
        original_url="https://example.com/a",
        created_at=datetime(2026, 1, 1, 12, 0),  # noqa: DTZ001 (deliberately naive)
    )

    with pytest.raises(ValueError):
        repo.add(naive)


def test_next_id_returns_an_increasing_sequence_starting_at_one(repo):
    assert [repo.next_id(), repo.next_id(), repo.next_id()] == [1, 2, 3]


def test_next_id_is_unique_across_concurrent_callers(repo):
    # The API serves requests on multiple threads, so no two callers may ever be
    # handed the same id, otherwise two links could receive the same short code.
    with ThreadPoolExecutor(max_workers=16) as pool:
        ids = list(pool.map(lambda _: repo.next_id(), range(50)))

    assert len(set(ids)) == 50


def test_concurrent_clicks_are_all_counted(repo):
    # The API serves requests on several threads at once. The increment must be atomic,
    # otherwise two overlapping clicks could both read N and both write N + 1.
    repo.add(make_record())

    with ThreadPoolExecutor(max_workers=16) as pool:
        list(pool.map(lambda _: repo.record_click("abc123", at=CLICKED_AT), range(50)))

    assert repo.get("abc123").click_count == 50

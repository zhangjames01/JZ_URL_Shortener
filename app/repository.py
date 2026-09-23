"""Storage layer for short URLs.

`UrlRepository` is the interface the rest of the app depends on. `SqliteUrlRepository`
is the concrete implementation. Because callers only rely on the interface, swapping in
another database later does not require changing the service or the API.
"""

import sqlite3
import threading
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from app.errors import DuplicateCodeError


@dataclass(frozen=True)
class UrlRecord:
    """A stored short link. Frozen so state only changes through the repository."""

    code: str
    original_url: str
    created_at: datetime
    click_count: int = 0
    last_accessed_at: datetime | None = None


class UrlRepository(Protocol):
    """What the service layer needs from any storage backend.

    A Protocol (structural typing) means implementations, including test fakes, only
    need matching methods and do not have to inherit from this class.
    """

    def add(self, record: UrlRecord) -> None:
        """Store a new record. Raises DuplicateCodeError if the code already exists."""

    def get(self, code: str) -> UrlRecord | None:
        """Return the record for `code`, or None if it does not exist."""

    def next_id(self) -> int:
        """Return the next unique integer (1, 2, 3, ...), safe under concurrent callers."""

    def record_click(self, code: str, at: datetime) -> None:
        """Atomically add one click and set last_accessed_at. No-op for unknown codes."""


_SCHEMA = """
CREATE TABLE IF NOT EXISTS urls (
    code             TEXT PRIMARY KEY,            -- uniqueness enforced by the database
    original_url     TEXT NOT NULL,
    created_at       TEXT NOT NULL,               -- ISO-8601, timezone-aware
    click_count      INTEGER NOT NULL DEFAULT 0,
    last_accessed_at TEXT
)
"""

# A table whose only job is to hand out unique, increasing integers. AUTOINCREMENT
# guarantees an id is never reused, even after a crash.
_COUNTER_SCHEMA = """
CREATE TABLE IF NOT EXISTS id_counter (
    id INTEGER PRIMARY KEY AUTOINCREMENT
)
"""


class SqliteUrlRepository:
    """SQLite-backed repository.

    Uses a single shared connection guarded by a lock. `check_same_thread=False` is
    required because FastAPI runs sync endpoints on a threadpool, and one connection is
    needed so that ":memory:" databases (used in tests) are not separate per call.
    The lock serialises access, which costs little since SQLite serialises writes anyway.
    """

    def __init__(self, database: str) -> None:
        self._conn = sqlite3.connect(database, check_same_thread=False)
        self._lock = threading.Lock()
        with self._lock, self._conn:
            self._conn.execute(_SCHEMA)
            self._conn.execute(_COUNTER_SCHEMA)

    def add(self, record: UrlRecord) -> None:
        # Naive datetimes are ambiguous once stored as text, so reject them early.
        _require_timezone(record.created_at)
        _require_timezone(record.last_accessed_at)
        try:
            # `with self._conn` wraps the statement in a transaction (commit or rollback).
            with self._lock, self._conn:
                self._conn.execute(
                    "INSERT INTO urls (code, original_url, created_at, click_count, "
                    "last_accessed_at) VALUES (?, ?, ?, ?, ?)",
                    (
                        record.code,
                        record.original_url,
                        record.created_at.isoformat(),
                        record.click_count,
                        _to_text(record.last_accessed_at),
                    ),
                )
        except sqlite3.IntegrityError as exc:
            # The only constraint a valid record can violate is the PRIMARY KEY on `code`.
            raise DuplicateCodeError(record.code) from exc

    def get(self, code: str) -> UrlRecord | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT code, original_url, created_at, click_count, last_accessed_at "
                "FROM urls WHERE code = ?",
                (code,),
            ).fetchone()
        if row is None:
            return None
        return UrlRecord(
            code=row[0],
            original_url=row[1],
            created_at=datetime.fromisoformat(row[2]),
            click_count=row[3],
            last_accessed_at=datetime.fromisoformat(row[4]) if row[4] else None,
        )

    def next_id(self) -> int:
        # Inserting a row makes SQLite assign the next id atomically; the lock and the
        # transaction ensure two threads can never receive the same number. If the
        # process crashes before the id is used, that number is skipped, which is
        # harmless because codes only need to be unique, not gap-free.
        with self._lock, self._conn:
            cursor = self._conn.execute("INSERT INTO id_counter DEFAULT VALUES")
            return cursor.lastrowid

    def record_click(self, code: str, at: datetime) -> None:
        _require_timezone(at)
        # Single UPDATE so the increment is atomic. Reading the count in Python and
        # writing it back would lose clicks when requests overlap.
        with self._lock, self._conn:
            self._conn.execute(
                "UPDATE urls SET click_count = click_count + 1, last_accessed_at = ? "
                "WHERE code = ?",
                (at.isoformat(), code),
            )


def _require_timezone(value: datetime | None) -> None:
    if value is not None and value.tzinfo is None:
        raise ValueError("datetime must be timezone-aware")


def _to_text(value: datetime | None) -> str | None:
    return value.isoformat() if value is not None else None

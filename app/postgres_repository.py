"""PostgreSQL implementation of the UrlRepository interface.

Same behaviour as the SQLite repository (the shared contract tests enforce that), but
suitable for production: data lives in a separate service, survives redeploys, and can
be shared by several app instances.
"""

from datetime import UTC, datetime

from psycopg import errors
from psycopg_pool import ConnectionPool

from app.errors import DuplicateCodeError
from app.repository import UrlRecord, require_timezone

# Arbitrary constant identifying the "create the schema" advisory lock.
_SCHEMA_LOCK_ID = 727001

_CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS urls (
    code             TEXT PRIMARY KEY,             -- uniqueness enforced by the database
    original_url     TEXT NOT NULL,
    created_at       TIMESTAMPTZ NOT NULL,
    click_count      INTEGER NOT NULL DEFAULT 0,
    last_accessed_at TIMESTAMPTZ
)
"""

# Native, concurrency-safe source of unique increasing integers for generated codes.
_CREATE_SEQUENCE = "CREATE SEQUENCE IF NOT EXISTS url_id_seq"


class PostgresUrlRepository:
    """Uses a connection pool so concurrent requests can hit the database in parallel."""

    def __init__(self, dsn: str) -> None:
        self._pool = ConnectionPool(dsn, open=False)
        # Wait for the first connections so a wrong or unreachable database fails at
        # startup with a clear error, not on the first request.
        self._pool.open(wait=True, timeout=10)
        self._create_schema()

    def _create_schema(self) -> None:
        with self._pool.connection() as conn:
            # "CREATE ... IF NOT EXISTS" can still fail when two instances start at the
            # same moment, so serialise schema creation with an advisory lock. The lock
            # is released automatically when this transaction ends.
            conn.execute("SELECT pg_advisory_xact_lock(%s)", (_SCHEMA_LOCK_ID,))
            conn.execute(_CREATE_TABLE)
            conn.execute(_CREATE_SEQUENCE)

    def add(self, record: UrlRecord) -> None:
        require_timezone(record.created_at)
        require_timezone(record.last_accessed_at)
        try:
            with self._pool.connection() as conn:
                conn.execute(
                    "INSERT INTO urls (code, original_url, created_at, click_count, "
                    "last_accessed_at) VALUES (%s, %s, %s, %s, %s)",
                    (
                        record.code,
                        record.original_url,
                        record.created_at,
                        record.click_count,
                        record.last_accessed_at,
                    ),
                )
        except errors.UniqueViolation as exc:
            # The only unique constraint is the PRIMARY KEY on `code`.
            raise DuplicateCodeError(record.code) from exc

    def get(self, code: str) -> UrlRecord | None:
        with self._pool.connection() as conn:
            row = conn.execute(
                "SELECT code, original_url, created_at, click_count, last_accessed_at "
                "FROM urls WHERE code = %s",
                (code,),
            ).fetchone()
        if row is None:
            return None
        # Postgres returns timestamps in the session time zone; normalise to UTC here so
        # the result does not depend on how the database or a connection pooler in front
        # of it is configured.
        return UrlRecord(
            code=row[0],
            original_url=row[1],
            created_at=row[2].astimezone(UTC),
            click_count=row[3],
            last_accessed_at=_to_utc(row[4]),
        )

    def next_id(self) -> int:
        with self._pool.connection() as conn:
            return conn.execute("SELECT nextval('url_id_seq')").fetchone()[0]

    def record_click(self, code: str, at: datetime) -> None:
        require_timezone(at)
        # One atomic UPDATE: concurrent clicks cannot overwrite each other's increment.
        with self._pool.connection() as conn:
            conn.execute(
                "UPDATE urls SET click_count = click_count + 1, last_accessed_at = %s "
                "WHERE code = %s",
                (at, code),
            )

    def close(self) -> None:
        self._pool.close()


def _to_utc(value: datetime | None) -> datetime | None:
    return value.astimezone(UTC) if value is not None else None

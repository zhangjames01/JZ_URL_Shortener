"""Runtime configuration, read from environment variables."""

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    # Path to the SQLite database file (":memory:" for a throwaway in-RAM database).
    database_path: str = "urls.db"
    # PostgreSQL connection string. When set it takes precedence over `database_path`.
    database_url: str | None = None
    # Public address used to build short links, without a trailing slash.
    base_url: str = "http://localhost:8000"

    @classmethod
    def from_env(cls) -> "Settings":
        defaults = cls()
        return cls(
            database_path=os.environ.get("DATABASE_PATH", defaults.database_path),
            base_url=os.environ.get("BASE_URL", defaults.base_url).rstrip("/"),
            # `or None` so a variable that exists but is empty counts as not set.
            database_url=os.environ.get("DATABASE_URL") or None,
        )

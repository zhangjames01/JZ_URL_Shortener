"""Tests for reading settings from environment variables, and for choosing a backend."""

import pytest

from app.config import Settings
from app.main import build_repository
from app.postgres_repository import PostgresUrlRepository
from app.repository import SqliteUrlRepository


@pytest.fixture(autouse=True)
def clean_environment(monkeypatch):
    """Start every test with none of our variables set, whatever the developer's shell has."""
    for name in ("DATABASE_URL", "DATABASE_PATH", "BASE_URL"):
        monkeypatch.delenv(name, raising=False)


def test_defaults_when_nothing_is_set():
    settings = Settings.from_env()

    assert settings.database_path == "urls.db"
    assert settings.base_url == "http://localhost:8000"
    assert settings.database_url is None


def test_reads_database_url(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://user:pw@host:5432/db")

    assert Settings.from_env().database_url == "postgresql://user:pw@host:5432/db"


def test_empty_database_url_means_not_set(monkeypatch):
    # Platforms sometimes define a variable with an empty value; treat it as absent.
    monkeypatch.setenv("DATABASE_URL", "")

    assert Settings.from_env().database_url is None


def test_base_url_trailing_slash_is_removed(monkeypatch):
    monkeypatch.setenv("BASE_URL", "https://sho.rt/")

    assert Settings.from_env().base_url == "https://sho.rt"


def test_without_a_database_url_the_sqlite_backend_is_used():
    repository = build_repository(Settings(database_path=":memory:"))

    assert isinstance(repository, SqliteUrlRepository)
    repository.close()


def test_with_a_database_url_the_postgres_backend_is_used(postgres_dsn):
    repository = build_repository(Settings(database_path=":memory:", database_url=postgres_dsn))

    assert isinstance(repository, PostgresUrlRepository)
    repository.close()

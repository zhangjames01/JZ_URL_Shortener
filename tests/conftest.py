"""Shared fixtures for unit and integration tests."""

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app

TEST_BASE_URL = "https://sho.rt"


@pytest.fixture
def settings():
    """Test settings: an in-memory database and a fixed public base URL."""
    return Settings(database_path=":memory:", base_url=TEST_BASE_URL)


@pytest.fixture
def client(settings):
    """A client for a freshly built app, so every test starts with an empty database."""
    return TestClient(create_app(settings))

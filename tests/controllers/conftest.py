"""Shared fixtures for controller tests. DB calls are mocked per test."""

import pytest
from fastapi.testclient import TestClient

from main import app


@pytest.fixture
def client():
    # Not used as a context manager, so the app's lifespan (DB init) doesn't run.
    return TestClient(app)

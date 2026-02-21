"""Shared pytest fixtures for CHM test suites."""

from collections.abc import Generator
from pathlib import Path
import sys

import pytest
from fastapi.testclient import TestClient

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


@pytest.fixture
def client() -> Generator[TestClient, None, None]:
    """Provide an API test client for contract and integration suites."""
    from app.main import app

    with TestClient(app) as test_client:
        yield test_client


def pytest_sessionfinish(session: pytest.Session, exitstatus: int) -> None:
    """Treat empty baseline collection as success for scaffold-only phase."""
    if exitstatus == 5:
        session.exitstatus = 0

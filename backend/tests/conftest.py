import pytest
from fastapi.testclient import TestClient

from tick.main import create_app


@pytest.fixture
def client() -> TestClient:
    return TestClient(create_app())

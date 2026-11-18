from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from tick.core.config import settings
from tick.main import create_app


@pytest.fixture(autouse=True)
def isolate_data_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "data_dir", tmp_path / "data")


@pytest.fixture
def client() -> TestClient:
    return TestClient(create_app())

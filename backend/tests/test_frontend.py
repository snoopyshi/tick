from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from tick.core.config import settings
from tick.main import create_app


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    static_dir = tmp_path / "static"
    assets = static_dir / "assets"
    assets.mkdir(parents=True)
    (static_dir / "index.html").write_text(
        "<!doctype html><title>tick</title>",
        encoding="utf-8",
    )
    (static_dir / "favicon.svg").write_text("<svg></svg>", encoding="utf-8")
    (assets / "app.js").write_text("console.log(1)", encoding="utf-8")
    (tmp_path / "secret.txt").write_text("secret", encoding="utf-8")
    monkeypatch.setattr(settings, "static_dir", str(static_dir))
    return TestClient(create_app())


def test_spa_and_static_files(client: TestClient) -> None:
    assert "tick" in client.get("/").text
    assert "tick" in client.get("/users").text
    assert client.get("/favicon.svg").text == "<svg></svg>"
    assert client.get("/assets/app.js").text == "console.log(1)"


def test_api_and_docs_stay_available(client: TestClient) -> None:
    health = client.get("/api/v1/health")
    assert health.status_code == 200
    assert health.headers["content-type"].startswith("application/json")

    assert client.get("/docs").status_code == 200
    assert "/api/v1/health" in client.get("/openapi.json").json()["paths"]


def test_static_path_cannot_escape_directory(client: TestClient) -> None:
    response = client.get("/../secret.txt")
    assert response.text != "secret"
    assert "tick" in response.text

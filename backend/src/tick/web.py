from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles


def mount_frontend(application: FastAPI, static_dir: Path) -> None:
    """Serve the built frontend when ``static_dir`` contains ``index.html``."""
    root = static_dir.resolve()
    index = root / "index.html"
    if not index.is_file():
        return

    assets = root / "assets"
    if assets.is_dir():
        application.mount(
            "/assets",
            StaticFiles(directory=assets),
            name="assets",
        )

    def resolve_file(full_path: str) -> Path:
        candidate = (root / full_path).resolve()
        if candidate.is_file() and root in candidate.parents:
            return candidate
        return index

    @application.get("/", include_in_schema=False)
    async def frontend_index() -> FileResponse:
        return FileResponse(index)

    @application.get("/{full_path:path}", include_in_schema=False)
    async def frontend_spa(full_path: str) -> FileResponse:
        return FileResponse(resolve_file(full_path))

from contextlib import asynccontextmanager
from pathlib import Path

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from tick import __version__
from tick.api.router import api_router
from tick.core.config import settings
from tick.core.logging import configure_tick_logging
from tick.web import mount_frontend


@asynccontextmanager
async def lifespan(_application: FastAPI):
    configure_tick_logging()
    settings.paths.ensure()
    yield


def create_app() -> FastAPI:
    application = FastAPI(
        title=settings.app_name,
        version=__version__,
        debug=settings.debug,
        docs_url="/docs" if settings.docs_enabled else None,
        redoc_url="/redoc" if settings.docs_enabled else None,
        openapi_url="/openapi.json" if settings.docs_enabled else None,
        lifespan=lifespan,
    )
    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    application.include_router(api_router, prefix=settings.api_prefix)
    if settings.static_dir:
        mount_frontend(application, Path(settings.static_dir))
    return application


app = create_app()


def main() -> None:
    uvicorn.run(
        "tick.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.reload,
    )

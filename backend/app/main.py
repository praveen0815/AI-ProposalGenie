"""FastAPI application entrypoint."""

import logging
from contextlib import asynccontextmanager

import app.models  # noqa: F401

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import api_router
from app.core.config import get_settings
from app.core.exceptions import register_exception_handlers
from app.core.logging import configure_logging
from app.core.middleware import RequestLoggingMiddleware
from app.schemas.health import LivenessResponse

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    configure_logging(settings.log_level)
    logger.info(
        "Starting %s %s (%s)",
        settings.app_name,
        settings.app_version,
        settings.environment,
    )
    logger.info(
        "PostgreSQL target %s:%s/%s",
        settings.postgres_host,
        settings.postgres_port,
        settings.postgres_db,
    )
    logger.info(
        "Redis target %s:%s/%s",
        settings.redis_host,
        settings.redis_port,
        settings.redis_db,
    )
    yield
    logger.info("Stopping %s", settings.app_name)
    del app


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings.log_level)

    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        lifespan=lifespan,
    )
    register_exception_handlers(app)
    app.add_middleware(RequestLoggingMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(api_router, prefix=settings.api_v1_prefix)

    @app.get("/health", response_model=LivenessResponse, tags=["health"])
    def liveness() -> LivenessResponse:
        """Process liveness. This does not check PostgreSQL or Redis."""

        return LivenessResponse(status="ok")

    return app


app = create_app()

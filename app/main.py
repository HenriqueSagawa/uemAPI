import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.v1 import campi, centros, cursos, departamentos, health
from app.core.config import Settings
from app.core.errors import register_error_handlers
from app.services.repository import DatasetError, load_snapshot

logger = logging.getLogger(__name__)


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings()
    logging.basicConfig(level=settings.log_level.upper())

    @asynccontextmanager
    async def lifespan(application: FastAPI):
        try:
            application.state.snapshot = load_snapshot(settings.data_dir)
        except DatasetError as exc:
            logger.warning("Snapshot aprovado indisponível: %s", exc)
            application.state.snapshot = None
        yield

    application = FastAPI(
        title="uemAPI",
        description="API comunitária, independente e não oficial para dados públicos da UEM.",
        version=settings.version,
        lifespan=lifespan,
    )
    application.state.settings = settings
    application.state.snapshot = None
    register_error_handlers(application)
    for router in (
        campi.router,
        centros.router,
        departamentos.router,
        cursos.router,
        health.router,
    ):
        application.include_router(router, prefix="/v1")
    return application


app = create_app()

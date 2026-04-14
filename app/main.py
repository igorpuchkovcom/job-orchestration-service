from fastapi import FastAPI

from app.api.routes.health import router as health_router
from app.api.routes.jobs import router as jobs_router
from app.core.config import get_settings


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        docs_url="/docs",
        openapi_url="/openapi.json",
        redoc_url=None,
    )
    app.include_router(health_router)
    app.include_router(jobs_router)
    return app


app = create_app()

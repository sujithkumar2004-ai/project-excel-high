from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.db.base import Base
from app.db.session import engine
from app.routers.record_router import router as record_router
from app.routes.ml_dataset import router as ml_dataset_router
from app.routes.ot_register import router as ot_register_router
from app.routes.records import router as records_router
from app.routes.upload import router as upload_router


def create_app() -> FastAPI:
    app = FastAPI(title=settings.app_name, version="1.0.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(ot_register_router)
    app.include_router(records_router)
    app.include_router(ml_dataset_router)
    app.include_router(upload_router)
    app.include_router(record_router)

    @app.on_event("startup")
    def create_tables_for_dev() -> None:
        if settings.auto_create_tables:
            Base.metadata.create_all(bind=engine)

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()

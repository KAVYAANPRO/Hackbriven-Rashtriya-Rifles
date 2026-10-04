from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.api.routes import auth_router, credits_router, meta_router, prompt_router, router, uploads_router
from backend.config import settings
from backend.utils.logger import setup_logging


def create_app() -> FastAPI:
    setup_logging()
    app = FastAPI(
        title="From Idea to Feed",
        description="AI-powered content production pipeline for the Qoneqt Global Feed",
        version="0.2.0",
    )

    # Lets a browser app on another origin (a deployed frontend) call this API.
    # Credentials are bearer tokens in a header, never cookies, so no
    # allow_credentials is needed. Range headers are exposed for video seeking.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["Content-Range", "Accept-Ranges", "Content-Disposition"],
    )

    app.include_router(router)
    app.include_router(credits_router)
    app.include_router(meta_router)
    app.include_router(auth_router)
    app.include_router(uploads_router)
    app.include_router(prompt_router)

    @app.get("/health")
    def health() -> dict:
        return {"status": "ok"}

    return app


app = create_app()

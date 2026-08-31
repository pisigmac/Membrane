"""FastAPI app for Membrane console API."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from membrane import __version__
from membrane.api.routes import router
from membrane.api.settings import get_api_settings
from membrane.paths import init_layout


def create_app() -> FastAPI:
    settings = get_api_settings()
    init_layout(settings.root_path())
    app = FastAPI(
        title="Membrane API",
        version=__version__,
        description="Membrane Memory OS HTTP API (Auth JWT / API keys).",
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_list(),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/api/version")
    def version() -> dict:
        return {"version": __version__, "service": "membrane"}

    app.include_router(router, prefix="/api")

    dist = Path(settings.web_dist) if settings.web_dist else Path(__file__).resolve().parents[3] / "web" / "dist"
    if dist.is_dir():
        app.mount("/", StaticFiles(directory=str(dist), html=True), name="web")

    return app


app = create_app()

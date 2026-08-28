from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from ..run_executor import LocalAsyncRunExecutor, configure_run_executor
from ..runner import run_pipeline
from ..settings import load_app_settings
from .routers import assets, events, exports, health, matching, review, runs, setup


def create_app() -> FastAPI:
    settings = load_app_settings()
    app = FastAPI(title='Extract Structured Info from Papers', version='0.1.0')
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_allowed_origins,
        allow_methods=settings.cors_allowed_methods,
        allow_headers=settings.cors_allowed_headers,
        allow_credentials=settings.cors_allow_credentials,
    )
    configure_run_executor(LocalAsyncRunExecutor(pipeline_runner=run_pipeline))
    app.state.app_settings = settings
    app.include_router(health.router)
    app.include_router(setup.router)
    # Register the static event-stream route before /api/runs/{run_id}.
    app.include_router(events.router)
    app.include_router(runs.router)
    app.include_router(matching.router)
    app.include_router(review.router)
    app.include_router(assets.router)
    app.include_router(exports.router)
    return app

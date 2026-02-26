"""
Dashboard FastAPI application factory.
"""

import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Dict

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.staticfiles import StaticFiles

from alithia.storage.base import StorageBackend

from .agent_dispatcher import AgentDispatcher
from .middleware import SecurityMiddleware
from .routers import agents, calendar, config_public, overview, papers, profile
from .scheduler import PaperScoutScheduler
from .task_manager import TaskManager
from .websocket_hub import WebSocketHub


class SPAStaticFiles(StaticFiles):
    """Serve static files with SPA fallback.

    When a path doesn't match any static file, serve ``index.html`` so the
    client-side router (React Router) can handle the route.  Without this,
    refreshing on ``/agents`` or ``/papers`` returns a 404.
    """

    async def get_response(self, path: str, scope):
        try:
            return await super().get_response(path, scope)
        except StarletteHTTPException as exc:
            if exc.status_code == 404:
                return await super().get_response("index.html", scope)
            raise


FRONTEND_DIR = (
    Path(os.environ.get("ALITHIA_FRONTEND_DIR", ""))
    if os.environ.get("ALITHIA_FRONTEND_DIR")
    else (Path(__file__).parent.parent.parent / "frontend" / "dist")
)


def create_app(config: Dict[str, Any] | None = None, storage: StorageBackend | None = None) -> FastAPI:
    """Create and configure the FastAPI application.

    For reload mode with uvicorn factory, config and storage will be None.
    In that case, load from environment or defaults.
    """
    # Load config and storage if not provided (for reload mode)
    if config is None:
        from alithia.config_loader import load_config

        config_path = os.environ.get("ALITHIA_CONFIG_PATH", "alithia_config.json")
        config = load_config(config_path)

    if storage is None:
        from alithia.storage.factory import get_storage_backend

        storage = get_storage_backend(config)
        storage.connect()

    user_id = config.get("storage", {}).get("user_id", "default")
    ws_hub = WebSocketHub()
    task_manager = TaskManager(storage, user_id)
    task_manager.set_update_callback(ws_hub.on_task_update)
    agent_dispatcher = AgentDispatcher(task_manager, storage, config, user_id)
    scheduler = PaperScoutScheduler(storage, config, user_id)
    scheduler.set_dispatcher(agent_dispatcher)

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        ws_hub.capture_loop()
        await scheduler.start()
        yield
        scheduler.stop()

    app = FastAPI(
        title="Alithia Dashboard",
        version="0.1.0",
        docs_url="/api/docs",
        openapi_url="/api/openapi.json",
        lifespan=lifespan,
    )

    cors_origins = config.get("dashboard", {}).get("cors_origins", ["*"])
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(SecurityMiddleware)

    # Attach to app state
    app.state.storage = storage
    app.state.config = config
    app.state.user_id = user_id
    app.state.task_manager = task_manager
    app.state.agent_dispatcher = agent_dispatcher
    app.state.ws_hub = ws_hub
    app.state.scheduler = scheduler

    # Register API routers
    app.include_router(overview.router)
    app.include_router(profile.router)
    app.include_router(papers.router)
    app.include_router(calendar.router)
    app.include_router(agents.router)
    app.include_router(config_public.router)

    # WebSocket endpoint
    @app.websocket("/ws")
    async def websocket_endpoint(ws: WebSocket):
        await ws_hub.connect(ws)
        try:
            while True:
                await ws.receive_text()
        except WebSocketDisconnect:
            await ws_hub.disconnect(ws)

    # Serve frontend static files with SPA fallback for client-side routing
    if FRONTEND_DIR.exists():
        app.mount("/", SPAStaticFiles(directory=str(FRONTEND_DIR), html=True), name="static")

    return app

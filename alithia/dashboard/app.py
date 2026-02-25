"""
Dashboard FastAPI application factory.
"""

from pathlib import Path
from typing import Any, Dict

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from alithia.storage.base import StorageBackend

from .agent_dispatcher import AgentDispatcher
from .routers import agents, calendar, overview, papers, profile
from .task_manager import TaskManager
from .websocket_hub import WebSocketHub

FRONTEND_DIR = Path(__file__).parent.parent.parent / "dashboard-frontend" / "dist"


def create_app(config: Dict[str, Any], storage: StorageBackend) -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title="Alithia Dashboard",
        version="0.1.0",
        docs_url="/api/docs",
        openapi_url="/api/openapi.json",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    user_id = config.get("storage", {}).get("user_id", "default")

    ws_hub = WebSocketHub()
    task_manager = TaskManager(storage, user_id)
    task_manager.set_update_callback(ws_hub.on_task_update)
    agent_dispatcher = AgentDispatcher(task_manager, storage, config, user_id)

    # Attach to app state
    app.state.storage = storage
    app.state.config = config
    app.state.user_id = user_id
    app.state.task_manager = task_manager
    app.state.agent_dispatcher = agent_dispatcher
    app.state.ws_hub = ws_hub

    # Register API routers
    app.include_router(overview.router)
    app.include_router(profile.router)
    app.include_router(papers.router)
    app.include_router(calendar.router)
    app.include_router(agents.router)

    # WebSocket endpoint
    @app.websocket("/ws")
    async def websocket_endpoint(ws: WebSocket):
        await ws_hub.connect(ws)
        try:
            while True:
                await ws.receive_text()
        except WebSocketDisconnect:
            await ws_hub.disconnect(ws)

    # Serve frontend static files if built
    if FRONTEND_DIR.exists():
        app.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="static")

    return app

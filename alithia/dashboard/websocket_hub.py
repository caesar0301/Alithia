"""
WebSocket hub for real-time updates.
"""

import asyncio
import json
from datetime import datetime
from typing import Any, Dict, Optional, Set

from fastapi import WebSocket
from noesium.core.utils import get_logger

logger = get_logger(__name__)


class WebSocketHub:
    """Manages WebSocket connections and broadcasts updates."""

    def __init__(self):
        self._connections: Set[WebSocket] = set()
        self._lock = asyncio.Lock()
        self._loop: Optional[asyncio.AbstractEventLoop] = None

    async def connect(self, ws: WebSocket) -> None:
        await ws.accept()
        if self._loop is None:
            self._loop = asyncio.get_running_loop()
        async with self._lock:
            self._connections.add(ws)
        logger.info(f"WebSocket connected. Total: {len(self._connections)}")

    async def disconnect(self, ws: WebSocket) -> None:
        async with self._lock:
            self._connections.discard(ws)
        logger.info(f"WebSocket disconnected. Total: {len(self._connections)}")

    async def broadcast(self, message_type: str, payload: Dict[str, Any]) -> None:
        """Broadcast a message to all connected clients."""
        if not self._connections:
            return

        data = json.dumps(
            {
                "type": message_type,
                "payload": payload,
                "timestamp": datetime.utcnow().isoformat(),
            }
        )

        stale: Set[WebSocket] = set()
        async with self._lock:
            for ws in self._connections:
                try:
                    await ws.send_text(data)
                except Exception:
                    stale.add(ws)

            self._connections -= stale

    def on_task_update(self, task_id: str, updates: Dict[str, Any]) -> None:
        """Callback for TaskManager — safe to call from any thread."""
        coro = self.broadcast("task_update", {"task_id": task_id, **updates})
        try:
            asyncio.get_running_loop().create_task(coro)
        except RuntimeError:
            if self._loop and self._loop.is_running():
                asyncio.run_coroutine_threadsafe(coro, self._loop)

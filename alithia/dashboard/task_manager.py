"""
Background task manager: queues and tracks async tasks.
"""

import asyncio
import uuid
from datetime import datetime
from typing import Any, Callable, Coroutine, Dict, List, Optional

from cogents_core.utils import get_logger

from alithia.storage.base import StorageBackend

from .models import BackgroundTask

logger = get_logger(__name__)


class TaskManager:
    """Manages background tasks backed by storage."""

    def __init__(self, storage: StorageBackend, user_id: str):
        self._storage = storage
        self._user_id = user_id
        self._running: Dict[str, asyncio.Task] = {}
        self._on_update: Optional[Callable] = None

    def set_update_callback(self, callback: Callable) -> None:
        """Register a callback for task status changes (used by WebSocketHub)."""
        self._on_update = callback

    async def submit(
        self,
        task_type: str,
        coro: Coroutine,
        parameters: Optional[Dict[str, Any]] = None,
    ) -> BackgroundTask:
        """Submit an async coroutine as a background task."""
        task_id = str(uuid.uuid4())
        now = datetime.utcnow().isoformat()

        task = BackgroundTask(
            id=task_id,
            user_id=self._user_id,
            task_type=task_type,
            status="queued",
            parameters=parameters or {},
            created_at=now,
        )

        self._storage.save_task(task.model_dump())

        async_task = asyncio.create_task(self._run_task(task_id, coro))
        self._running[task_id] = async_task

        return task

    async def _run_task(self, task_id: str, coro: Coroutine) -> None:
        now = datetime.utcnow().isoformat()
        self._update_task(task_id, status="running", started_at=now)

        try:
            result = await coro
            completed_at = datetime.utcnow().isoformat()
            self._update_task(
                task_id,
                status="completed",
                progress=1.0,
                result=result if isinstance(result, dict) else {"result": str(result)},
                completed_at=completed_at,
            )
        except Exception as e:
            completed_at = datetime.utcnow().isoformat()
            self._update_task(
                task_id,
                status="failed",
                error_message=str(e),
                completed_at=completed_at,
            )
            logger.error(f"Task {task_id} failed: {e}")
        finally:
            self._running.pop(task_id, None)

    def _update_task(self, task_id: str, **updates) -> None:
        existing = self._storage.get_task(task_id)
        if existing:
            existing.update(updates)
            self._storage.save_task(existing)

            if self._on_update:
                try:
                    self._on_update(task_id, updates)
                except Exception:
                    pass

    def update_progress(self, task_id: str, progress: float, current_step: str = "") -> None:
        """Update task progress (called by agents via ProgressReporter)."""
        self._update_task(task_id, progress=progress, current_step=current_step)

    def get_task(self, task_id: str) -> Optional[BackgroundTask]:
        data = self._storage.get_task(task_id)
        if data:
            return BackgroundTask(**data)
        return None

    def get_tasks(self, status: Optional[str] = None, limit: int = 50) -> List[BackgroundTask]:
        data = self._storage.get_tasks(self._user_id, status=status, limit=limit)
        return [BackgroundTask(**d) for d in data]

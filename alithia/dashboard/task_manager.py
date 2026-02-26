"""
Background task manager: queues and tracks async tasks.
"""

import asyncio
import uuid
from datetime import datetime
from typing import Any, Callable, Coroutine, Dict, List, Optional

from noesium.core.utils import get_logger

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

    def recover_stale_tasks(self) -> int:
        """Mark orphaned running/queued tasks as failed.

        Should be called once at startup to clean up tasks left behind by
        a previous crash or forced shutdown (e.g. Ctrl+C / SIGKILL).
        Returns the number of recovered tasks.
        """
        recovered = 0
        now = datetime.utcnow().isoformat()
        for status in ("running", "queued"):
            stale = self._storage.get_tasks(self._user_id, status=status, limit=200)
            for task_data in stale:
                task_id = task_data["id"]
                task_data.update(
                    status="failed",
                    error_message="Process interrupted — task did not complete",
                    completed_at=now,
                )
                self._storage.save_task(task_data)
                recovered += 1
                logger.warning("Recovered stale task %s (was %s)", task_id, status)
        return recovered

    async def submit(
        self,
        task_type: str,
        coro: Coroutine,
        parameters: Optional[Dict[str, Any]] = None,
        task_id: Optional[str] = None,
    ) -> BackgroundTask:
        """Submit an async coroutine as a background task."""
        task_id = task_id or str(uuid.uuid4())
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

    def add_milestone(self, task_id: str, message: str) -> None:
        """Append a major milestone to task logs and broadcast."""
        existing = self._storage.get_task(task_id)
        if existing:
            logs = existing.get("logs", [])
            logs.append(message)
            self._update_task(task_id, logs=logs)

    def get_task(self, task_id: str) -> Optional[BackgroundTask]:
        data = self._storage.get_task(task_id)
        if data:
            return BackgroundTask(**data)
        return None

    def get_tasks(self, status: Optional[str] = None, limit: int = 50) -> List[BackgroundTask]:
        data = self._storage.get_tasks(self._user_id, status=status, limit=limit)
        return [BackgroundTask(**d) for d in data]

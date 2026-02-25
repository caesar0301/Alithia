"""
Progress reporter: wraps TaskManager.update_progress for agent callbacks.
"""

from .task_manager import TaskManager


class ProgressReporter:
    """Lightweight wrapper for reporting task progress from agents."""

    def __init__(self, task_manager: TaskManager, task_id: str):
        self._tm = task_manager
        self._task_id = task_id

    def report(self, progress: float, step: str = "") -> None:
        """Update progress (0.0-1.0) and optional step name."""
        self._tm.update_progress(self._task_id, min(max(progress, 0.0), 1.0), step)

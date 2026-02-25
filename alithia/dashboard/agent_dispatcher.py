"""
Agent dispatcher: translates API requests into agent runs.
"""

import asyncio
import uuid
from typing import Any, Dict

from noesium.core.utils import get_logger

from alithia.storage.base import StorageBackend

from .models import RunAgentRequest
from .task_manager import TaskManager

logger = get_logger(__name__)


class AgentDispatcher:
    """Dispatches agent runs as background tasks."""

    def __init__(
        self,
        task_manager: TaskManager,
        storage: StorageBackend,
        config: Dict[str, Any],
        user_id: str,
    ):
        self._task_manager = task_manager
        self._storage = storage
        self._config = config
        self._user_id = user_id

    async def dispatch(self, request: RunAgentRequest):
        """Dispatch an agent run request and return the background task."""
        if request.agent_type == "paperscout":
            return await self._dispatch_paperscout(request.parameters)
        elif request.agent_type == "sync":
            return await self._dispatch_sync(request.parameters)
        else:
            raise ValueError(f"Unknown agent type: {request.agent_type}")

    async def _dispatch_paperscout(self, params: Dict[str, Any]):
        task_id = str(uuid.uuid4())
        tm = self._task_manager

        def on_step(progress: float, label: str) -> None:
            tm.update_progress(task_id, progress, label)
            tm.add_milestone(task_id, label)

        async def _run():
            from alithia.constants import (
                ALITHIA_MAX_PAPERS,
                ALITHIA_MAX_PAPERS_QUERIED,
                DEFAULT_ARXIV_QUERY,
                DEFAULT_SEND_EMPTY,
            )
            from alithia.paperscout.agent import PaperScoutAgent
            from alithia.paperscout.state import PaperScoutConfig
            from alithia.researcher.profile import ResearcherProfile

            ps_settings = self._config.get("paperscout_agent", self._config.get("arxrec", {}))
            config = PaperScoutConfig(
                user_profile=ResearcherProfile.from_config(self._config),
                query=params.get("query", ps_settings.get("query", DEFAULT_ARXIV_QUERY)),
                max_papers=params.get("max_papers", ps_settings.get("max_papers", ALITHIA_MAX_PAPERS)),
                max_papers_queried=ps_settings.get("max_papers_queried", ALITHIA_MAX_PAPERS_QUERIED),
                send_empty=ps_settings.get("send_empty", DEFAULT_SEND_EMPTY),
                ignore_patterns=ps_settings.get("ignore_patterns", []),
                from_date=params.get("from_date"),
                to_date=params.get("to_date"),
                debug=params.get("debug", self._config.get("debug", False)),
            )

            agent = PaperScoutAgent(
                storage=self._storage, user_id=self._user_id, on_step=on_step,
            )
            return await asyncio.to_thread(agent.run, config)

        return await self._task_manager.submit(
            "paperscout", _run(), parameters=params, task_id=task_id,
        )

    async def _dispatch_sync(self, params: Dict[str, Any]):
        task_id = str(uuid.uuid4())
        tm = self._task_manager

        async def _run():
            from alithia.researcher.profile import ResearcherProfile
            from alithia.sync.orchestrator import SyncOrchestrator

            profile = ResearcherProfile.from_config(self._config)
            orchestrator = SyncOrchestrator(self._storage, self._user_id, profile)

            connector = params.get("connector")
            force_full = params.get("force_full", False)

            if connector:
                tm.update_progress(task_id, 0.2, f"Syncing {connector}")
                tm.add_milestone(task_id, f"Syncing {connector}")
                result = await orchestrator.sync_one(connector, force_full=force_full)
                return {"connector": connector, "status": result.status.value, "items": result.items_synced}
            else:
                tm.update_progress(task_id, 0.1, "Starting full sync")
                tm.add_milestone(task_id, "Starting full sync")
                results = await orchestrator.sync_all(force_full=force_full)
                return [
                    {"connector": r.connector_name, "status": r.status.value, "items": r.items_synced}
                    for r in results
                ]

        return await self._task_manager.submit(
            "sync", _run(), parameters=params, task_id=task_id,
        )

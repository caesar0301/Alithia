"""
Sync orchestrator: runs all configured connectors concurrently.
"""

import asyncio
from typing import List, Optional

from cogents_core.utils import get_logger

from alithia.researcher.profile import ResearcherProfile
from alithia.storage.base import StorageBackend

from .base import SyncConnector, SyncResult, SyncStatus

logger = get_logger(__name__)


class SyncOrchestrator:
    """Runs all configured sync connectors."""

    def __init__(self, storage: StorageBackend, user_id: str, profile: ResearcherProfile):
        self._storage = storage
        self._user_id = user_id
        self._connectors: List[SyncConnector] = self._build_connectors(profile)

    @property
    def connectors(self) -> List[SyncConnector]:
        return self._connectors

    def _build_connectors(self, profile: ResearcherProfile) -> List[SyncConnector]:
        connectors: List[SyncConnector] = []

        if profile.zotero:
            from .connectors.zotero import ZoteroConnector

            connectors.append(ZoteroConnector(profile.zotero))

        if profile.google_scholar:
            from .connectors.scholar import ScholarConnector

            connectors.append(ScholarConnector(profile.google_scholar))

        return connectors

    async def sync_all(self, force_full: bool = False) -> List[SyncResult]:
        """Run all connectors concurrently with failure isolation."""
        tasks = [
            connector.sync(self._storage, self._user_id, force_full)
            for connector in self._connectors
            if connector.is_configured()
        ]

        if not tasks:
            logger.warning("No configured connectors to sync")
            return []

        results_raw = await asyncio.gather(*tasks, return_exceptions=True)

        results: List[SyncResult] = []
        for i, r in enumerate(results_raw):
            if isinstance(r, SyncResult):
                results.append(r)
            else:
                name = self._connectors[i].name if i < len(self._connectors) else "unknown"
                results.append(
                    SyncResult(connector_name=name, status=SyncStatus.FAILED, error_message=str(r))
                )

        return results

    async def sync_one(self, connector_name: str, force_full: bool = False) -> SyncResult:
        """Run a specific connector by name."""
        for connector in self._connectors:
            if connector.name == connector_name:
                if not connector.is_configured():
                    return SyncResult(
                        connector_name=connector_name,
                        status=SyncStatus.SKIPPED,
                        error_message="Connector not configured",
                    )
                return await connector.sync(self._storage, self._user_id, force_full)

        return SyncResult(
            connector_name=connector_name,
            status=SyncStatus.FAILED,
            error_message=f"No connector found with name '{connector_name}'",
        )

    def get_status(self) -> List[dict]:
        """Return last sync status for each connector."""
        statuses = []
        for connector in self._connectors:
            last = connector.last_synced_at(self._storage, self._user_id)
            statuses.append({
                "connector": connector.name,
                "configured": connector.is_configured(),
                "last_synced": last.isoformat() if last else None,
            })
        return statuses

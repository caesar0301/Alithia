"""
Zotero sync connector.

Wraps existing get_zotero_corpus() to normalize data into ZoteroPaper models
and persist to storage.
"""

from datetime import datetime
from typing import Optional

from noesium.core.utils import get_logger

from alithia.models.zotero_paper import ZoteroPaper
from alithia.researcher.connection import ZoteroConnection
from alithia.storage.base import StorageBackend
from alithia.sync.base import SyncConnector, SyncResult, SyncStatus

logger = get_logger(__name__)


class ZoteroConnector(SyncConnector):
    """Syncs user's Zotero library to storage."""

    def __init__(self, connection: ZoteroConnection):
        self._connection = connection

    @property
    def name(self) -> str:
        return "zotero"

    def is_configured(self) -> bool:
        return bool(self._connection.zotero_id and self._connection.zotero_key)

    async def sync(self, storage: StorageBackend, user_id: str, force_full: bool = False) -> SyncResult:
        started_at = datetime.utcnow()

        try:
            from alithia.utils.zotero_client import get_zotero_corpus

            if not force_full:
                cached = storage.get_zotero_papers(user_id, max_age_hours=24)
                if cached:
                    return SyncResult(
                        connector_name=self.name,
                        status=SyncStatus.SKIPPED,
                        items_synced=len(cached),
                        items_total=len(cached),
                        started_at=started_at,
                        completed_at=datetime.utcnow(),
                        details={"reason": "cache_fresh"},
                    )

            raw_items = get_zotero_corpus(self._connection.zotero_id, self._connection.zotero_key)

            papers = []
            for item in raw_items:
                paths = item.get("paths", [])
                zp = ZoteroPaper.from_zotero_api(item, paths)
                if zp:
                    papers.append(zp)

            storage.cache_zotero_papers(user_id, [p.to_storage_dict() for p in papers])

            completed_at = datetime.utcnow()

            storage.save_sync_log(
                {
                    "user_id": user_id,
                    "connector_name": self.name,
                    "status": SyncStatus.SUCCESS.value,
                    "items_synced": len(papers),
                    "items_total": len(raw_items),
                    "started_at": started_at.isoformat(),
                    "completed_at": completed_at.isoformat(),
                }
            )

            logger.info(f"Zotero sync complete: {len(papers)}/{len(raw_items)} papers")

            return SyncResult(
                connector_name=self.name,
                status=SyncStatus.SUCCESS,
                items_synced=len(papers),
                items_total=len(raw_items),
                started_at=started_at,
                completed_at=completed_at,
            )

        except Exception as e:
            completed_at = datetime.utcnow()
            error_msg = str(e)
            logger.error(f"Zotero sync failed: {error_msg}")

            try:
                storage.save_sync_log(
                    {
                        "user_id": user_id,
                        "connector_name": self.name,
                        "status": SyncStatus.FAILED.value,
                        "error_message": error_msg,
                        "started_at": started_at.isoformat(),
                        "completed_at": completed_at.isoformat(),
                    }
                )
            except Exception:
                pass

            return SyncResult(
                connector_name=self.name,
                status=SyncStatus.FAILED,
                started_at=started_at,
                completed_at=completed_at,
                error_message=error_msg,
            )

    def last_synced_at(self, storage: StorageBackend, user_id: str) -> Optional[datetime]:
        entry = storage.get_last_sync(user_id, self.name)
        if entry and entry.get("completed_at"):
            try:
                return datetime.fromisoformat(entry["completed_at"])
            except (ValueError, TypeError):
                pass
        return None

"""
Google Scholar sync connector.

Fetches profile and publications via SerpAPI (preferred) or scholarly (fallback).
"""

from datetime import datetime
from typing import Optional

from noesium.core.utils import get_logger

from alithia.models.scholar_profile import ScholarProfile, ScholarPublication
from alithia.researcher.connection import GoogleScholarConnection
from alithia.storage.base import StorageBackend
from alithia.sync.base import SyncConnector, SyncResult, SyncStatus

logger = get_logger(__name__)


class ScholarConnector(SyncConnector):
    """Syncs Google Scholar profile and publications to storage."""

    def __init__(self, connection: GoogleScholarConnection):
        self._connection = connection

    @property
    def name(self) -> str:
        return "google_scholar"

    def is_configured(self) -> bool:
        return bool(self._connection.scholar_id)

    async def sync(
        self, storage: StorageBackend, user_id: str, force_full: bool = False
    ) -> SyncResult:
        started_at = datetime.utcnow()

        try:
            if not force_full:
                last = storage.get_last_sync(user_id, self.name)
                if last and last.get("completed_at"):
                    try:
                        last_dt = datetime.fromisoformat(last["completed_at"])
                        if (datetime.utcnow() - last_dt).total_seconds() < 24 * 3600:
                            return SyncResult(
                                connector_name=self.name,
                                status=SyncStatus.SKIPPED,
                                started_at=started_at,
                                completed_at=datetime.utcnow(),
                                details={"reason": "within_ttl"},
                            )
                    except (ValueError, TypeError):
                        pass

            from alithia.utils.scholar_client import get_scholar_data

            profile_data, publications_data = get_scholar_data(
                self._connection.scholar_id, self._connection.serpapi_key
            )

            profile = ScholarProfile(
                scholar_user_id=self._connection.scholar_id,
                name=profile_data.get("name", ""),
                affiliation=profile_data.get("affiliation"),
                interests=profile_data.get("interests", []),
                h_index=profile_data.get("h_index"),
                i10_index=profile_data.get("i10_index"),
                total_citations=profile_data.get("total_citations", 0),
                fetched_at=datetime.utcnow(),
            )
            storage.save_scholar_profile(user_id, profile.to_storage_dict())

            pubs = []
            for p in publications_data:
                pub = ScholarPublication(
                    title=p.get("title", ""),
                    authors=p.get("authors", []),
                    year=p.get("year"),
                    citation_count=p.get("citation_count", 0),
                    venue=p.get("venue"),
                    url=p.get("url"),
                    scholar_id=p.get("scholar_id"),
                )
                pubs.append(pub)

            storage.save_scholar_publications(
                user_id, [p.to_storage_dict() for p in pubs]
            )

            completed_at = datetime.utcnow()

            storage.save_sync_log({
                "user_id": user_id,
                "connector_name": self.name,
                "status": SyncStatus.SUCCESS.value,
                "items_synced": len(pubs),
                "items_total": len(publications_data),
                "started_at": started_at.isoformat(),
                "completed_at": completed_at.isoformat(),
            })

            logger.info(f"Scholar sync complete: profile + {len(pubs)} publications")

            return SyncResult(
                connector_name=self.name,
                status=SyncStatus.SUCCESS,
                items_synced=len(pubs),
                items_total=len(publications_data),
                started_at=started_at,
                completed_at=completed_at,
            )

        except Exception as e:
            completed_at = datetime.utcnow()
            error_msg = str(e)
            logger.error(f"Scholar sync failed: {error_msg}")

            try:
                storage.save_sync_log({
                    "user_id": user_id,
                    "connector_name": self.name,
                    "status": SyncStatus.FAILED.value,
                    "error_message": error_msg,
                    "started_at": started_at.isoformat(),
                    "completed_at": completed_at.isoformat(),
                })
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

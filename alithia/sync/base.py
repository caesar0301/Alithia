"""
Sync connector interface and result types.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING, Any, Dict, Optional

if TYPE_CHECKING:
    from alithia.storage.base import StorageBackend


class SyncStatus(str, Enum):
    SUCCESS = "success"
    PARTIAL = "partial"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class SyncResult:
    """Result of a single connector sync run."""

    connector_name: str
    status: SyncStatus
    items_synced: int = 0
    items_total: int = 0
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None
    details: Dict[str, Any] = field(default_factory=dict)


class SyncConnector(ABC):
    """Interface for Connected Service sync connectors."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique connector identifier (e.g., 'zotero', 'google_scholar')."""

    @abstractmethod
    def is_configured(self) -> bool:
        """Return True if credentials and config are present."""

    @abstractmethod
    async def sync(self, storage: "StorageBackend", user_id: str, force_full: bool = False) -> SyncResult:
        """
        Run sync. Writes data to storage.

        Args:
            storage: Storage backend to write to
            user_id: User identifier
            force_full: If True, ignore incremental state and do full sync
        """

    @abstractmethod
    def last_synced_at(self, storage: "StorageBackend", user_id: str) -> Optional[datetime]:
        """Return timestamp of last successful sync, or None."""

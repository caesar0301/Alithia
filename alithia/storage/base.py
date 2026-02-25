"""
Abstract base class for storage backends.

Defines the interface that all storage backends must implement.
"""

from abc import ABC, abstractmethod
from datetime import date
from typing import Any, Dict, List, Optional

from alithia.constants import DEFAULT_QUERY_HISTORY_LIMIT


class StorageBackend(ABC):
    """Abstract base class for stateful storage backends."""

    @abstractmethod
    def connect(self) -> None:
        """Establish connection to the storage backend."""

    @abstractmethod
    def disconnect(self) -> None:
        """Close connection to the storage backend."""

    @abstractmethod
    def test_connection(self) -> bool:
        """
        Test if connection is working.

        Returns:
            True if connection is successful, False otherwise
        """

    # Zotero paper caching methods
    @abstractmethod
    def cache_zotero_papers(self, user_id: str, papers: List[Dict[str, Any]]) -> None:
        """
        Cache Zotero papers for a user.

        Args:
            user_id: User identifier
            papers: List of paper dictionaries with fields:
                - title, authors, abstract, url, zotero_item_key, tags
        """

    @abstractmethod
    def get_zotero_papers(self, user_id: str, max_age_hours: int = 24) -> Optional[List[Dict[str, Any]]]:
        """
        Get cached Zotero papers if they're fresh enough.

        Args:
            user_id: User identifier
            max_age_hours: Maximum age of cache in hours

        Returns:
            List of cached papers or None if cache is stale/missing
        """

    # ArXiv processed ranges tracking
    @abstractmethod
    def mark_date_range_processed(
        self,
        user_id: str,
        from_date: str,
        to_date: str,
        query_categories: str,
        papers_found: int,
    ) -> None:
        """
        Mark a date range as processed.

        Args:
            user_id: User identifier
            from_date: Start date (YYYYMMDD format)
            to_date: End date (YYYYMMDD format)
            query_categories: ArXiv query categories
            papers_found: Number of papers found in this range
        """

    @abstractmethod
    def get_processed_ranges(self, user_id: str, query_categories: str, days_back: int = 30) -> List[Dict[str, Any]]:
        """
        Get processed date ranges for a user.

        Args:
            user_id: User identifier
            query_categories: ArXiv query categories
            days_back: Number of days to look back

        Returns:
            List of processed ranges with from_date, to_date, papers_found
        """

    # ArXiv papers emailed tracking
    @abstractmethod
    def save_emailed_papers(self, user_id: str, papers: List[Dict[str, Any]]) -> None:
        """
        Save papers that were emailed to user.

        Args:
            user_id: User identifier
            papers: List of paper dictionaries with fields:
                - arxiv_id, title, authors, summary, pdf_url, code_url,
                  tldr, relevance_score, published_date
        """

    @abstractmethod
    def get_emailed_papers(
        self, user_id: str, arxiv_ids: Optional[List[str]] = None, days_back: int = 30
    ) -> List[Dict[str, Any]]:
        """
        Get papers that were already emailed.

        Args:
            user_id: User identifier
            arxiv_ids: Optional list of specific arxiv_ids to check
            days_back: Number of days to look back

        Returns:
            List of emailed papers
        """

    @abstractmethod
    def is_paper_emailed(self, user_id: str, arxiv_id: str) -> bool:
        """
        Check if a paper was already emailed.

        Args:
            user_id: User identifier
            arxiv_id: ArXiv paper ID

        Returns:
            True if paper was already emailed
        """

    # PaperLens parsed papers caching
    @abstractmethod
    def cache_parsed_paper(self, user_id: str, paper_data: Dict[str, Any]) -> str:
        """
        Cache a parsed paper.

        Args:
            user_id: User identifier
            paper_data: Dictionary with fields:
                - file_path, file_name, file_hash, title, authors, abstract,
                  full_text, sections, figures, tables

        Returns:
            Paper ID (UUID)
        """

    @abstractmethod
    def get_parsed_paper(self, user_id: str, file_hash: str) -> Optional[Dict[str, Any]]:
        """
        Get a cached parsed paper by file hash.

        Args:
            user_id: User identifier
            file_hash: MD5 hash of the PDF file

        Returns:
            Cached paper data or None if not found
        """

    @abstractmethod
    def update_paper_access_time(self, paper_id: str) -> None:
        """
        Update the last_accessed timestamp for a paper.

        Args:
            paper_id: Paper ID (UUID)
        """

    # PaperLens query history
    @abstractmethod
    def save_query(
        self,
        user_id: str,
        paper_id: str,
        query_text: str,
        query_results: List[Dict[str, Any]],
        similarity_scores: Dict[str, float],
    ) -> None:
        """
        Save a query to history.

        Args:
            user_id: User identifier
            paper_id: Paper ID (UUID)
            query_text: The user's query
            query_results: List of search results
            similarity_scores: Dictionary of section/chunk IDs to similarity scores
        """

    @abstractmethod
    def get_query_history(
        self, user_id: str, paper_id: Optional[str] = None, limit: int = DEFAULT_QUERY_HISTORY_LIMIT
    ) -> List[Dict[str, Any]]:
        """
        Get query history.

        Args:
            user_id: User identifier
            paper_id: Optional paper ID to filter by
            limit: Maximum number of queries to return

        Returns:
            List of queries with results
        """

    # ===========================
    # Assessed papers (PaperScout v2)
    # ===========================

    @abstractmethod
    def save_assessed_papers(
        self, user_id: str, query_categories: str, papers: List[Dict[str, Any]], assessment_date: date
    ) -> None:
        """Persist all assessed papers with scores."""

    @abstractmethod
    def get_assessed_papers(
        self, user_id: str, query_categories: str, from_date: date, to_date: date
    ) -> List[Dict[str, Any]]:
        """Retrieve assessed papers for a date range."""

    # ===========================
    # Notification records (exactly-once email)
    # ===========================

    @abstractmethod
    def save_notification_record(self, record: Dict[str, Any]) -> None:
        """Save a notification record. Enforces unique (user_id, query_categories, notification_date)."""

    @abstractmethod
    def get_notification_record(
        self, user_id: str, query_categories: str, notification_date: date
    ) -> Optional[Dict[str, Any]]:
        """Check if a notification was already sent for this (user, query, date)."""

    @abstractmethod
    def get_missing_notification_dates(self, user_id: str, query_categories: str, window_days: int = 7) -> List[date]:
        """Return dates within window that have no successful notification."""

    @abstractmethod
    def get_notification_records_range(
        self, user_id: str, query_categories: str, from_date: date, to_date: date
    ) -> List[Dict[str, Any]]:
        """Get notification records for a date range (calendar view)."""

    # ===========================
    # Google Scholar data
    # ===========================

    @abstractmethod
    def save_scholar_profile(self, user_id: str, profile: Dict[str, Any]) -> None:
        """Upsert Google Scholar profile for a user."""

    @abstractmethod
    def get_scholar_profile(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Get cached Scholar profile. Returns None if not synced."""

    @abstractmethod
    def save_scholar_publications(self, user_id: str, publications: List[Dict[str, Any]]) -> None:
        """Upsert Scholar publications for a user."""

    @abstractmethod
    def get_scholar_publications(self, user_id: str, limit: int = 100) -> List[Dict[str, Any]]:
        """Get cached Scholar publications."""

    # ===========================
    # Sync log
    # ===========================

    @abstractmethod
    def save_sync_log(self, entry: Dict[str, Any]) -> None:
        """Record a sync attempt."""

    @abstractmethod
    def get_last_sync(self, user_id: str, connector_name: str) -> Optional[Dict[str, Any]]:
        """Get the most recent successful sync log entry for a connector."""

    # ===========================
    # Background tasks (Dashboard)
    # ===========================

    @abstractmethod
    def save_task(self, task: Dict[str, Any]) -> None:
        """Upsert a background task record."""

    @abstractmethod
    def get_task(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Get task by ID."""

    @abstractmethod
    def get_tasks(self, user_id: str, status: Optional[str] = None, limit: int = 50) -> List[Dict[str, Any]]:
        """List tasks for a user, optionally filtered by status."""

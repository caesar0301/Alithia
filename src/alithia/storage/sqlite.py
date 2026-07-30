"""SQLite storage implementation.

AsyncPersistStore protocol implementation for local-first persistence.
Thread-safe with per-thread connections and write serialization.
"""

from __future__ import annotations

import json
import logging
import sqlite3
import threading
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class SQLiteStorage:
    """SQLite-based key-value storage.

    Implements AsyncPersistStore protocol for soothe integration.
    Thread-safe with per-thread connections.

    Note: connections are stored in ``threading.local`` so that when a worker
    thread exits, its connection is torn down automatically. The previous
    class-level ``_connections`` dict (keyed by ``threading.get_ident()``)
    leaked stale connections after a thread died, and because Python reuses
    thread IDs a *new* thread could retrieve a dead thread's now-invalid
    connection and segfault inside ``_pysqlite_query_execute`` (see the
    py3.11/py3.12 SIGSEGV crash reports of Jun 29 / Jul 01 2026).
    """

    _lock = threading.Lock()  # serializes schema-init only

    def __init__(self, db_path: Path | str):
        """Initialize storage with database path.

        Args:
            db_path: Path to SQLite database file.
        """
        self.db_path = Path(db_path)
        self._local = threading.local()  # per-thread connection, auto-cleaned on thread exit
        self._ensure_db_exists()

    def _ensure_db_exists(self) -> None:
        """Ensure database file and kv_store table exist."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        conn = self._get_connection()
        cursor = conn.cursor()

        # Create kv_store table if not exists
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS kv_store (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                updated_at TEXT NOT NULL DEFAULT (datetime('now'))
            )
        """)

        # Create index for prefix queries
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_kv_store_prefix ON kv_store(key)
        """)

        conn.commit()
        logger.debug(f"SQLite storage initialized at {self.db_path}")

    def _get_connection(self) -> sqlite3.Connection:
        """Get thread-local connection.

        Each thread gets its own connection stored in ``threading.local``,
        which is torn down automatically when the thread exits — so a new
        thread can never retrieve a dead thread's (now invalid) connection.
        """
        conn = getattr(self._local, "conn", None)
        if conn is None:
            conn = sqlite3.connect(str(self.db_path))
            conn.row_factory = sqlite3.Row
            self._local.conn = conn  # dies with the thread automatically
            logger.debug(f"Created new connection for thread {threading.get_ident()}")
        return conn

    async def load(self, key: str) -> Any | None:
        """Load value by key.

        Args:
            key: Storage key (e.g., "paperscout:emailed:user123")

        Returns:
            Deserialized value or None if not found.
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute("SELECT value FROM kv_store WHERE key = ?", (key,))
            row = cursor.fetchone()

            if row:
                return json.loads(row["value"])
            return None

        except Exception as e:
            logger.error(f"Failed to load key {key}: {e}")
            return None

    async def save(self, key: str, value: Any) -> None:
        """Save value with key.

        Args:
            key: Storage key
            value: Value to store (will be JSON-serialized)
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        try:
            serialized = json.dumps(value)

            cursor.execute("BEGIN IMMEDIATE")  # Acquire write lock

            # Upsert: insert or replace
            cursor.execute(
                """
                INSERT OR REPLACE INTO kv_store (key, value, updated_at)
                VALUES (?, ?, datetime('now'))
            """,
                (key, serialized),
            )

            cursor.execute("COMMIT")
            logger.debug(f"Saved key {key}")

        except Exception as e:
            cursor.execute("ROLLBACK")
            logger.error(f"Failed to save key {key}: {e}")
            raise

    async def delete(self, key: str) -> None:
        """Delete value by key.

        Args:
            key: Storage key to delete
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute("BEGIN IMMEDIATE")
            cursor.execute("DELETE FROM kv_store WHERE key = ?", (key,))
            cursor.execute("COMMIT")
            logger.debug(f"Deleted key {key}")

        except Exception as e:
            cursor.execute("ROLLBACK")
            logger.error(f"Failed to delete key {key}: {e}")

    async def list_keys(self, prefix: str) -> list[str]:
        """List all keys matching prefix.

        Args:
            prefix: Key prefix to match (e.g., "paperscout:")

        Returns:
            List of matching keys.
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute(
                "SELECT key FROM kv_store WHERE key LIKE ? ORDER BY key", (prefix + "%",)
            )
            rows = cursor.fetchall()
            return [row["key"] for row in rows]

        except Exception as e:
            logger.error(f"Failed to list keys with prefix {prefix}: {e}")
            return []

    # ===========================
    # Notification records (exactly-once semantics)
    # ===========================

    def _ensure_notification_table(self) -> None:
        """Ensure notification_records table exists."""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS notification_records (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                query_categories TEXT NOT NULL,
                notification_date TEXT NOT NULL,
                paper_count INTEGER DEFAULT 0,
                status TEXT NOT NULL DEFAULT 'pending',
                retry_count INTEGER DEFAULT 0,
                sent_at TEXT,
                error_message TEXT,
                created_at TEXT,
                UNIQUE(user_id, query_categories, notification_date)
            )
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_notification_lookup
            ON notification_records(user_id, query_categories, notification_date)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_notification_status
            ON notification_records(user_id, status, notification_date)
        """)
        conn.commit()

    def save_notification_record(self, record: dict[str, Any]) -> None:
        """Save a notification record.

        Enforces unique (user_id, query_categories, notification_date) constraint
        for exactly-once semantics (RFC-0002 PS-001).

        Args:
            record: Dict with fields:
                - id: UUID (optional, auto-generated if missing)
                - user_id: User identifier
                - query_categories: ArXiv query string
                - notification_date: Date string (YYYY-MM-DD)
                - paper_count: Number of papers in notification
                - status: "pending" | "empty" | "sent" | "failed"
                - retry_count: Number of retry attempts
                - sent_at: Timestamp when sent
                - error_message: Error if failed
                - created_at: Creation timestamp
        """
        self._ensure_notification_table()
        conn = self._get_connection()
        cursor = conn.cursor()

        import uuid
        from datetime import datetime

        now = datetime.utcnow().isoformat()

        try:
            cursor.execute("BEGIN IMMEDIATE")
            cursor.execute(
                """
                INSERT OR REPLACE INTO notification_records
                (id, user_id, query_categories, notification_date, paper_count,
                 status, retry_count, sent_at, error_message, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    record.get("id", str(uuid.uuid4())),
                    record["user_id"],
                    record["query_categories"],
                    record["notification_date"],
                    record.get("paper_count", 0),
                    record.get("status", "pending"),
                    record.get("retry_count", 0),
                    record.get("sent_at"),
                    record.get("error_message"),
                    record.get("created_at", now),
                ),
            )
            cursor.execute("COMMIT")
            logger.debug(f"Saved notification record for {record['notification_date']}")

        except Exception as e:
            cursor.execute("ROLLBACK")
            logger.error(f"Failed to save notification record: {e}")
            raise

    def get_notification_record(
        self,
        user_id: str,
        query_categories: str,
        notification_date: str,
    ) -> dict[str, Any] | None:
        """Get notification record for a specific date.

        Args:
            user_id: User identifier
            query_categories: ArXiv query string
            notification_date: Date string (YYYY-MM-DD)

        Returns:
            Notification record dict or None if not found.
        """
        self._ensure_notification_table()
        conn = self._get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute(
                """
                SELECT * FROM notification_records
                WHERE user_id = ? AND query_categories = ? AND notification_date = ?
                LIMIT 1
            """,
                (user_id, query_categories, notification_date),
            )
            row = cursor.fetchone()
            return dict(row) if row else None

        except Exception as e:
            logger.error(f"Failed to get notification record: {e}")
            return None

    def get_missing_notification_dates(
        self,
        user_id: str,
        query_categories: str,
        window_days: int = 7,
    ) -> list[str]:
        """Backward-compatible alias for unretrieved date lookup.

        A day is considered unretrieved when it does not have terminal
        `sent` status in notification records.
        """
        return self.get_unretrieved_notification_dates(
            user_id=user_id,
            query_categories=query_categories,
            window_days=window_days,
        )

    def get_unretrieved_notification_dates(
        self,
        user_id: str,
        query_categories: str,
        window_days: int = 7,
    ) -> list[str]:
        """Get dates within window that are still unretrieved.

        Args:
            user_id: User identifier
            query_categories: ArXiv query string
            window_days: Number of days to look back

        Returns:
            List of date strings (YYYY-MM-DD) without terminal `sent` status.
        """
        self._ensure_notification_table()
        conn = self._get_connection()
        cursor = conn.cursor()

        from datetime import date, timedelta

        today = date.today()
        expected = [today - timedelta(days=i) for i in range(1, window_days + 1)]
        expected_strs = [d.isoformat() for d in expected]

        try:
            placeholders = ",".join("?" * len(expected_strs))
            cursor.execute(
                f"""
                SELECT notification_date FROM notification_records
                WHERE user_id = ? AND query_categories = ?
                  AND notification_date IN ({placeholders})
                  AND status = 'sent'
            """,
                [user_id, query_categories] + expected_strs,
            )
            sent_dates = {row["notification_date"] for row in cursor.fetchall()}
            missing = [d for d in expected_strs if d not in sent_dates]
            return sorted(missing)

        except Exception as e:
            logger.error(f"Failed to get missing notification dates: {e}")
            return []

    def get_notification_records_range(
        self,
        user_id: str,
        query_categories: str,
        from_date: str,
        to_date: str,
    ) -> list[dict[str, Any]]:
        """Get notification records for a date range (calendar view).

        Args:
            user_id: User identifier
            query_categories: ArXiv query string
            from_date: Start date (YYYY-MM-DD)
            to_date: End date (YYYY-MM-DD)

        Returns:
            List of notification records within range.
        """
        self._ensure_notification_table()
        conn = self._get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute(
                """
                SELECT * FROM notification_records
                WHERE user_id = ? AND query_categories = ?
                  AND notification_date >= ? AND notification_date <= ?
                ORDER BY notification_date
            """,
                (user_id, query_categories, from_date, to_date),
            )
            return [dict(row) for row in cursor.fetchall()]

        except Exception as e:
            logger.error(f"Failed to get notification records range: {e}")
            return []

    def close(self) -> None:
        """Close the current thread's connection.

        Other threads' connections are cleaned up automatically by
        ``threading.local`` when those threads exit. This method only
        closes the calling thread's connection (the one that would be
        returned by ``_get_connection``).
        """
        conn = getattr(self._local, "conn", None)
        if conn is not None:
            conn.close()
            self._local.conn = None
            logger.info("SQLite storage connection closed for current thread")


class AlithiaStore:
    """Alithia storage wrapper with user_id namespace.

    Wraps SQLiteStorage to provide user-isolated keys for soothe integration.
    Implements AsyncPersistStore protocol with user_id prefix for all keys.
    """

    def __init__(self, user_id: str = "default", db_path: Path | None = None):
        """Initialize AlithiaStore.

        Args:
            user_id: User identifier for key namespace.
            db_path: Optional database path (defaults to ~/.alithia/data/alithia.db).
        """
        from alithia import ALITHIA_HOME

        self._user_id = user_id
        if db_path is None:
            db_path = ALITHIA_HOME / "data" / "alithia.db"
        self._storage = SQLiteStorage(db_path)

    def _user_prefix(self) -> str:
        """Get user-specific key prefix."""
        return f"alithia:{self._user_id}:"

    def _full_key(self, key: str) -> str:
        """Add user prefix to key."""
        return f"{self._user_prefix()}{key}"

    async def load(self, key: str) -> Any | None:
        """Load value by key with user namespace.

        Args:
            key: Storage key (without user prefix).

        Returns:
            Deserialized value or None if not found.
        """
        return await self._storage.load(self._full_key(key))

    async def save(self, key: str, value: Any) -> None:
        """Save value with key in user namespace.

        Args:
            key: Storage key (without user prefix).
            value: Value to store (will be JSON-serialized).
        """
        await self._storage.save(self._full_key(key), value)

    async def delete(self, key: str) -> None:
        """Delete value by key in user namespace.

        Args:
            key: Storage key (without user prefix).
        """
        await self._storage.delete(self._full_key(key))

    async def list_keys(self, prefix: str) -> list[str]:
        """List all keys matching prefix in user namespace.

        Args:
            prefix: Key prefix (without user prefix).

        Returns:
            List of matching keys (without user prefix).
        """
        full_prefix = self._full_key(prefix)
        full_keys = await self._storage.list_keys(full_prefix)
        # Strip user prefix from returned keys
        user_prefix = self._user_prefix()
        return [k[len(user_prefix) :] for k in full_keys]

    def close(self) -> None:
        """Close underlying storage connections."""
        self._storage.close()

    # ===========================
    # Notification record methods (wrapper)
    # ===========================

    def save_notification_record(self, record: dict[str, Any]) -> None:
        """Save notification record with user_id from store."""
        record["user_id"] = self._user_id
        self._storage.save_notification_record(record)

    def get_notification_record(
        self,
        query_categories: str,
        notification_date: str,
    ) -> dict[str, Any] | None:
        """Get notification record for user."""
        return self._storage.get_notification_record(
            self._user_id, query_categories, notification_date
        )

    def get_missing_notification_dates(
        self,
        query_categories: str,
        window_days: int = 7,
    ) -> list[str]:
        """Backward-compatible alias for unretrieved dates for user."""
        return self.get_unretrieved_notification_dates(
            query_categories=query_categories,
            window_days=window_days,
        )

    def get_unretrieved_notification_dates(
        self,
        query_categories: str,
        window_days: int = 7,
    ) -> list[str]:
        """Get unretrieved notification dates for user."""
        return self._storage.get_unretrieved_notification_dates(
            self._user_id, query_categories, window_days
        )

    def get_notification_records_range(
        self,
        query_categories: str,
        from_date: str,
        to_date: str,
    ) -> list[dict[str, Any]]:
        """Get notification records range for user."""
        return self._storage.get_notification_records_range(
            self._user_id, query_categories, from_date, to_date
        )


__all__ = ["SQLiteStorage", "AlithiaStore"]

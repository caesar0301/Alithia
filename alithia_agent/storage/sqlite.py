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
    Thread-safe with per-thread connection pooling.
    """

    _connections: dict[int, sqlite3.Connection] = {}  # thread_id → connection
    _lock = threading.Lock()

    def __init__(self, db_path: Path | str):
        """Initialize storage with database path.

        Args:
            db_path: Path to SQLite database file.
        """
        self.db_path = Path(db_path)
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
        logger.info(f"SQLite storage initialized at {self.db_path}")

    def _get_connection(self) -> sqlite3.Connection:
        """Get thread-local connection.

        Each thread gets its own connection to avoid locking issues.
        """
        thread_id = threading.get_ident()

        with self._lock:
            if thread_id not in self._connections:
                conn = sqlite3.connect(str(self.db_path))
                conn.row_factory = sqlite3.Row
                self._connections[thread_id] = conn
                logger.debug(f"Created new connection for thread {thread_id}")

            return self._connections[thread_id]

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
            cursor.execute("""
                INSERT OR REPLACE INTO kv_store (key, value, updated_at)
                VALUES (?, ?, datetime('now'))
            """, (key, serialized))

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
                "SELECT key FROM kv_store WHERE key LIKE ? ORDER BY key",
                (prefix + "%",)
            )
            rows = cursor.fetchall()
            return [row["key"] for row in rows]

        except Exception as e:
            logger.error(f"Failed to list keys with prefix {prefix}: {e}")
            return []

    def close(self) -> None:
        """Close all connections."""
        with self._lock:
            for conn in self._connections.values():
                conn.close()
            self._connections.clear()
            logger.info("SQLite storage connections closed")


__all__ = ["SQLiteStorage"]
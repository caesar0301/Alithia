"""Schema migrations for SQLite storage.

Versioned SQL migrations for schema evolution.
Applied sequentially, tracked in schema_version table.
"""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path
from typing import Any

import sqlite3

logger = logging.getLogger(__name__)


# Migration SQL statements
MIGRATIONS = {
    1: """
        -- Initial schema for PaperScout and PaperLens
        CREATE TABLE IF NOT EXISTS schema_version (
            version INTEGER PRIMARY KEY,
            applied_at TEXT NOT NULL,
            description TEXT
        );

        CREATE TABLE IF NOT EXISTS kv_store (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        );

        CREATE INDEX IF NOT EXISTS idx_kv_store_prefix ON kv_store(key);

        CREATE TABLE IF NOT EXISTS paperscout_notifications (
            user_id TEXT NOT NULL,
            date TEXT NOT NULL,
            papers_count INTEGER NOT NULL,
            recipient TEXT NOT NULL,
            arxiv_ids TEXT NOT NULL,
            sent_at TEXT NOT NULL,
            success INTEGER NOT NULL DEFAULT 1,
            error_message TEXT,
            PRIMARY KEY (user_id, date)
        );

        CREATE TABLE IF NOT EXISTS paperscout_emailed (
            user_id TEXT NOT NULL,
            arxiv_id TEXT NOT NULL,
            emailed_at TEXT NOT NULL,
            PRIMARY KEY (user_id, arxiv_id)
        );

        CREATE INDEX IF NOT EXISTS idx_emailed_user ON paperscout_emailed(user_id);

        CREATE TABLE IF NOT EXISTS paperscout_zotero_cache (
            user_id TEXT PRIMARY KEY,
            papers TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            expires_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS paperlens_parsed_papers (
            user_id TEXT NOT NULL,
            file_hash TEXT NOT NULL,
            file_path TEXT NOT NULL,
            file_name TEXT NOT NULL,
            title TEXT,
            authors TEXT,
            abstract TEXT,
            full_text TEXT,
            sections TEXT,
            parsed_at TEXT NOT NULL,
            PRIMARY KEY (user_id, file_hash)
        );

        CREATE INDEX IF NOT EXISTS idx_parsed_user ON paperlens_parsed_papers(user_id);

        CREATE TABLE IF NOT EXISTS paperlens_query_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            query TEXT NOT NULL,
            pdf_path TEXT NOT NULL,
            papers_count INTEGER,
            top_score REAL,
            queried_at TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_query_user ON paperlens_query_history(user_id);
    """,
}


class MigrationRunner:
    """Run schema migrations for SQLite database.

    Migrations are applied sequentially and tracked in schema_version table.
    """

    def __init__(self, db_path: Path):
        """Initialize migration runner.

        Args:
            db_path: Path to SQLite database file.
        """
        self.db_path = Path(db_path)

    def get_current_version(self) -> int:
        """Get current schema version from database.

        Returns:
            Current version number (0 if no migrations applied).
        """
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()

        try:
            # Check if schema_version table exists
            cursor.execute("""
                SELECT name FROM sqlite_master
                WHERE type='table' AND name='schema_version'
            """)

            if not cursor.fetchone():
                return 0

            cursor.execute("SELECT MAX(version) FROM schema_version")
            row = cursor.fetchone()
            return row[0] if row and row[0] else 0

        finally:
            conn.close()

    def get_pending_migrations(self) -> list[int]:
        """Get list of pending migration versions.

        Returns:
            List of migration version numbers not yet applied.
        """
        current = self.get_current_version()
        return [v for v in MIGRATIONS.keys() if v > current]

    def run_migrations(self) -> None:
        """Run all pending migrations.

        Migrations are executed in order, each recorded in schema_version.
        """
        pending = self.get_pending_migrations()

        if not pending:
            logger.info(f"No pending migrations (current version: {self.get_current_version()})")
            return

        logger.info(f"Running {len(pending)} pending migrations")

        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()

        try:
            for version in sorted(pending):
                sql = MIGRATIONS[version]
                description = f"Migration {version}"

                logger.info(f"Applying migration {version}...")

                # Execute migration SQL
                cursor.executescript(sql)

                # Record in schema_version
                cursor.execute("""
                    INSERT INTO schema_version (version, applied_at, description)
                    VALUES (?, ?, ?)
                """, (version, datetime.now().isoformat(), description))

                conn.commit()
                logger.info(f"Migration {version} applied successfully")

        except Exception as e:
            conn.rollback()
            logger.error(f"Migration failed: {e}")
            raise

        finally:
            conn.close()

    def initialize(self) -> None:
        """Initialize database with all migrations.

        Creates database file if needed and runs all migrations.
        """
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.run_migrations()


def initialize_storage(user_id: str = "default") -> SQLiteStorage:
    """Initialize storage for alithia-agent.

    Creates ~/.alithia/ directory, runs migrations, and returns storage instance.

    Args:
        user_id: User identifier for storage keys.

    Returns:
        Initialized SQLiteStorage instance.
    """
    from alithia_agent.storage.sqlite import SQLiteStorage

    alithia_dir = Path.home() / ".alithia"
    alithia_dir.mkdir(exist_ok=True)

    db_path = alithia_dir / "alithia.db"

    # Run migrations
    runner = MigrationRunner(db_path)
    runner.initialize()

    # Create storage instance
    storage = SQLiteStorage(db_path)
    logger.info(f"Storage initialized for user {user_id}")

    return storage


__all__ = ["MigrationRunner", "initialize_storage"]
"""
SQLite storage backend implementation (fallback).
"""

import json
import sqlite3
import uuid
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

from cogents_core.utils import get_logger

from alithia.constants import DEFAULT_QUERY_HISTORY_LIMIT, DEFAULT_SQLITE_PATH

from .base import StorageBackend

logger = get_logger(__name__)


class SQLiteStorage(StorageBackend):
    """SQLite implementation of storage backend (fallback)."""

    def __init__(self, db_path: str = DEFAULT_SQLITE_PATH):
        """
        Initialize SQLite storage.

        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn: Optional[sqlite3.Connection] = None

    def connect(self) -> None:
        """Establish connection to SQLite."""
        try:
            self.conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
            self.conn.row_factory = sqlite3.Row
            self._create_tables()
            logger.info(f"Connected to SQLite database at {self.db_path}")
        except Exception as e:
            logger.error(f"Failed to connect to SQLite: {e}")
            raise

    def disconnect(self) -> None:
        """Close connection to SQLite."""
        if self.conn:
            self.conn.close()
            self.conn = None
            logger.info("Disconnected from SQLite")

    def test_connection(self) -> bool:
        """Test if connection is working."""
        try:
            if self.conn is None:
                return False
            cursor = self.conn.cursor()
            cursor.execute("SELECT 1")
            return True
        except Exception as e:
            logger.warning(f"SQLite connection test failed: {e}")
            return False

    def _create_tables(self) -> None:
        """Create tables if they don't exist."""
        cursor = self.conn.cursor()

        # Zotero papers cache
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS zotero_papers (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                paper_title TEXT,
                paper_authors TEXT,
                paper_abstract TEXT,
                paper_url TEXT,
                zotero_item_key TEXT UNIQUE,
                tags TEXT,
                date_added TEXT,
                last_synced TEXT
            )
        """
        )

        # ArXiv processed ranges
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS arxiv_processed_ranges (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                from_date TEXT NOT NULL,
                to_date TEXT NOT NULL,
                query_categories TEXT NOT NULL,
                papers_found INTEGER,
                processed_at TEXT,
                UNIQUE(user_id, from_date, to_date, query_categories)
            )
        """
        )

        # ArXiv papers emailed
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS arxiv_papers_emailed (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                arxiv_id TEXT NOT NULL,
                paper_title TEXT,
                paper_authors TEXT,
                paper_summary TEXT,
                pdf_url TEXT,
                code_url TEXT,
                tldr TEXT,
                relevance_score REAL,
                published_date TEXT,
                emailed_at TEXT,
                UNIQUE(user_id, arxiv_id)
            )
        """
        )

        # Parsed papers cache
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS parsed_papers (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                file_path TEXT,
                file_name TEXT,
                file_hash TEXT UNIQUE,
                paper_title TEXT,
                paper_authors TEXT,
                paper_abstract TEXT,
                full_text TEXT,
                sections TEXT,
                figures TEXT,
                tables TEXT,
                parsed_at TEXT,
                last_accessed TEXT
            )
        """
        )

        # Query history
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS query_history (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                paper_id TEXT,
                query_text TEXT,
                query_results TEXT,
                similarity_scores TEXT,
                queried_at TEXT,
                FOREIGN KEY (paper_id) REFERENCES parsed_papers(id)
            )
        """
        )

        # Assessed papers (PaperScout v2)
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS assessed_papers (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                arxiv_id TEXT NOT NULL,
                query_categories TEXT NOT NULL,
                assessment_date TEXT NOT NULL,
                paper_title TEXT,
                paper_authors TEXT,
                paper_summary TEXT,
                pdf_url TEXT,
                relevance_score REAL,
                relevance_factors TEXT,
                code_url TEXT,
                tldr TEXT,
                affiliations TEXT,
                emailed INTEGER DEFAULT 0,
                assessed_at TEXT,
                UNIQUE(user_id, arxiv_id, query_categories)
            )
        """
        )

        # Notification records (exactly-once email)
        cursor.execute(
            """
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
        """
        )

        # Scholar profiles
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS scholar_profiles (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL UNIQUE,
                scholar_user_id TEXT NOT NULL,
                name TEXT,
                affiliation TEXT,
                interests TEXT,
                h_index INTEGER,
                i10_index INTEGER,
                total_citations INTEGER DEFAULT 0,
                last_synced TEXT
            )
        """
        )

        # Scholar publications
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS scholar_publications (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                scholar_article_id TEXT,
                title TEXT NOT NULL,
                authors TEXT,
                year INTEGER,
                citation_count INTEGER DEFAULT 0,
                venue TEXT,
                url TEXT,
                last_synced TEXT,
                UNIQUE(user_id, title, year)
            )
        """
        )

        # Sync log
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS sync_log (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                connector_name TEXT NOT NULL,
                status TEXT NOT NULL,
                items_synced INTEGER DEFAULT 0,
                items_total INTEGER DEFAULT 0,
                sync_version TEXT,
                error_message TEXT,
                started_at TEXT NOT NULL,
                completed_at TEXT
            )
        """
        )

        # Background tasks (Dashboard)
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS background_tasks (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                task_type TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'queued',
                progress REAL DEFAULT 0.0,
                current_step TEXT DEFAULT '',
                parameters TEXT,
                result TEXT,
                logs TEXT,
                created_at TEXT,
                started_at TEXT,
                completed_at TEXT,
                error_message TEXT
            )
        """
        )

        # Create indexes for common queries
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_zotero_user ON zotero_papers(user_id, last_synced)")
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_arxiv_ranges_user ON arxiv_processed_ranges(user_id, query_categories)"
        )
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_arxiv_emailed_user ON arxiv_papers_emailed(user_id, arxiv_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_parsed_papers_hash ON parsed_papers(file_hash)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_query_history_paper ON query_history(paper_id, queried_at)")
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_assessed_papers_lookup "
            "ON assessed_papers(user_id, query_categories, assessment_date)"
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_notification_records_lookup "
            "ON notification_records(user_id, query_categories, notification_date)"
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_sync_log_lookup "
            "ON sync_log(user_id, connector_name, started_at)"
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_background_tasks_user "
            "ON background_tasks(user_id, status, created_at)"
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_scholar_pub_user "
            "ON scholar_publications(user_id, citation_count)"
        )

        self.conn.commit()

    def _dict_to_row(self, data: Dict[str, Any]) -> sqlite3.Row:
        """Convert dictionary to Row-like object for consistency."""
        return data

    # Zotero paper caching methods
    def cache_zotero_papers(self, user_id: str, papers: List[Dict[str, Any]]) -> None:
        """Cache Zotero papers for a user."""
        try:
            cursor = self.conn.cursor()
            now = datetime.utcnow().isoformat()

            for paper in papers:
                cursor.execute(
                    """
                    INSERT OR REPLACE INTO zotero_papers
                    (id, user_id, paper_title, paper_authors, paper_abstract,
                     paper_url, zotero_item_key, tags, date_added, last_synced)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                    (
                        str(uuid.uuid4()),
                        user_id,
                        paper.get("title", ""),
                        json.dumps(paper.get("authors", [])),
                        paper.get("abstract", ""),
                        paper.get("url", ""),
                        paper.get("zotero_item_key", ""),
                        json.dumps(paper.get("tags", [])),
                        paper.get("date_added", now),
                        now,
                    ),
                )

            self.conn.commit()
            logger.info(f"Cached {len(papers)} Zotero papers for user {user_id}")

        except Exception as e:
            logger.error(f"Failed to cache Zotero papers: {e}")
            self.conn.rollback()
            raise

    def get_zotero_papers(self, user_id: str, max_age_hours: int = 24) -> Optional[List[Dict[str, Any]]]:
        """Get cached Zotero papers if they're fresh enough."""
        try:
            cursor = self.conn.cursor()
            cutoff_time = (datetime.utcnow() - timedelta(hours=max_age_hours)).isoformat()

            cursor.execute(
                """
                SELECT * FROM zotero_papers
                WHERE user_id = ? AND last_synced >= ?
                ORDER BY last_synced DESC
            """,
                (user_id, cutoff_time),
            )

            rows = cursor.fetchall()

            if not rows:
                logger.info(f"No fresh Zotero cache found for user {user_id}")
                return None

            logger.info(f"Retrieved {len(rows)} cached Zotero papers for user {user_id}")

            papers = []
            for row in rows:
                papers.append(
                    {
                        "title": row["paper_title"],
                        "authors": json.loads(row["paper_authors"]) if row["paper_authors"] else [],
                        "abstract": row["paper_abstract"],
                        "url": row["paper_url"],
                        "zotero_item_key": row["zotero_item_key"],
                        "tags": json.loads(row["tags"]) if row["tags"] else [],
                        "date_added": row["date_added"],
                    }
                )

            return papers

        except Exception as e:
            logger.error(f"Failed to get cached Zotero papers: {e}")
            return None

    # ArXiv processed ranges tracking
    def mark_date_range_processed(
        self,
        user_id: str,
        from_date: str,
        to_date: str,
        query_categories: str,
        papers_found: int,
    ) -> None:
        """Mark a date range as processed."""
        try:
            cursor = self.conn.cursor()
            cursor.execute(
                """
                INSERT OR REPLACE INTO arxiv_processed_ranges
                (id, user_id, from_date, to_date, query_categories, papers_found, processed_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    str(uuid.uuid4()),
                    user_id,
                    from_date,
                    to_date,
                    query_categories,
                    papers_found,
                    datetime.utcnow().isoformat(),
                ),
            )

            self.conn.commit()
            logger.info(
                f"Marked date range {from_date}-{to_date} as processed " f"for user {user_id} ({papers_found} papers)"
            )

        except Exception as e:
            logger.error(f"Failed to mark date range as processed: {e}")
            self.conn.rollback()
            raise

    def get_processed_ranges(self, user_id: str, query_categories: str, days_back: int = 30) -> List[Dict[str, Any]]:
        """Get processed date ranges for a user."""
        try:
            cursor = self.conn.cursor()
            cutoff_date = (datetime.utcnow() - timedelta(days=days_back)).strftime("%Y%m%d")

            cursor.execute(
                """
                SELECT from_date, to_date, papers_found, processed_at
                FROM arxiv_processed_ranges
                WHERE user_id = ? AND query_categories = ? AND from_date >= ?
                ORDER BY from_date DESC
            """,
                (user_id, query_categories, cutoff_date),
            )

            rows = cursor.fetchall()
            logger.info(f"Retrieved {len(rows)} processed ranges for user {user_id} (last {days_back} days)")

            return [
                {
                    "from_date": row["from_date"],
                    "to_date": row["to_date"],
                    "papers_found": row["papers_found"],
                    "processed_at": row["processed_at"],
                }
                for row in rows
            ]

        except Exception as e:
            logger.error(f"Failed to get processed ranges: {e}")
            return []

    # ArXiv papers emailed tracking
    def save_emailed_papers(self, user_id: str, papers: List[Dict[str, Any]]) -> None:
        """Save papers that were emailed to user."""
        try:
            cursor = self.conn.cursor()
            now = datetime.utcnow().isoformat()

            for paper in papers:
                cursor.execute(
                    """
                    INSERT OR REPLACE INTO arxiv_papers_emailed
                    (id, user_id, arxiv_id, paper_title, paper_authors, paper_summary,
                     pdf_url, code_url, tldr, relevance_score, published_date, emailed_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                    (
                        str(uuid.uuid4()),
                        user_id,
                        paper.get("arxiv_id", ""),
                        paper.get("title", ""),
                        json.dumps(paper.get("authors", [])),
                        paper.get("summary", ""),
                        paper.get("pdf_url", ""),
                        paper.get("code_url"),
                        paper.get("tldr"),
                        paper.get("relevance_score", 0.0),
                        paper.get("published_date"),
                        now,
                    ),
                )

            self.conn.commit()
            logger.info(f"Saved {len(papers)} emailed papers for user {user_id}")

        except Exception as e:
            logger.error(f"Failed to save emailed papers: {e}")
            self.conn.rollback()
            raise

    def get_emailed_papers(
        self, user_id: str, arxiv_ids: Optional[List[str]] = None, days_back: int = 30
    ) -> List[Dict[str, Any]]:
        """Get papers that were already emailed."""
        try:
            cursor = self.conn.cursor()
            cutoff_date = (datetime.utcnow() - timedelta(days=days_back)).isoformat()

            if arxiv_ids:
                placeholders = ",".join("?" * len(arxiv_ids))
                cursor.execute(
                    f"""
                    SELECT * FROM arxiv_papers_emailed
                    WHERE user_id = ? AND arxiv_id IN ({placeholders}) AND emailed_at >= ?
                """,
                    [user_id] + arxiv_ids + [cutoff_date],
                )
            else:
                cursor.execute(
                    """
                    SELECT * FROM arxiv_papers_emailed
                    WHERE user_id = ? AND emailed_at >= ?
                    ORDER BY emailed_at DESC
                """,
                    (user_id, cutoff_date),
                )

            rows = cursor.fetchall()
            logger.info(f"Retrieved {len(rows)} emailed papers for user {user_id}")

            return [dict(row) for row in rows]

        except Exception as e:
            logger.error(f"Failed to get emailed papers: {e}")
            return []

    def is_paper_emailed(self, user_id: str, arxiv_id: str) -> bool:
        """Check if a paper was already emailed."""
        try:
            cursor = self.conn.cursor()
            cursor.execute(
                """
                SELECT 1 FROM arxiv_papers_emailed
                WHERE user_id = ? AND arxiv_id = ?
                LIMIT 1
            """,
                (user_id, arxiv_id),
            )

            return cursor.fetchone() is not None

        except Exception as e:
            logger.error(f"Failed to check if paper was emailed: {e}")
            return False

    # PaperLens parsed papers caching
    def cache_parsed_paper(self, user_id: str, paper_data: Dict[str, Any]) -> str:
        """Cache a parsed paper."""
        try:
            cursor = self.conn.cursor()
            paper_id = str(uuid.uuid4())
            now = datetime.utcnow().isoformat()

            cursor.execute(
                """
                INSERT OR REPLACE INTO parsed_papers
                (id, user_id, file_path, file_name, file_hash, paper_title,
                 paper_authors, paper_abstract, full_text, sections, figures,
                 tables, parsed_at, last_accessed)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    paper_id,
                    user_id,
                    paper_data.get("file_path", ""),
                    paper_data.get("file_name", ""),
                    paper_data.get("file_hash", ""),
                    paper_data.get("title"),
                    json.dumps(paper_data.get("authors", [])),
                    paper_data.get("abstract"),
                    paper_data.get("full_text", ""),
                    json.dumps(paper_data.get("sections", {})),
                    json.dumps(paper_data.get("figures", [])),
                    json.dumps(paper_data.get("tables", [])),
                    now,
                    now,
                ),
            )

            self.conn.commit()
            logger.info(f"Cached parsed paper {paper_id} for user {user_id}")
            return paper_id

        except Exception as e:
            logger.error(f"Failed to cache parsed paper: {e}")
            self.conn.rollback()
            raise

    def get_parsed_paper(self, user_id: str, file_hash: str) -> Optional[Dict[str, Any]]:
        """Get a cached parsed paper by file hash."""
        try:
            cursor = self.conn.cursor()
            cursor.execute(
                """
                SELECT * FROM parsed_papers
                WHERE user_id = ? AND file_hash = ?
                LIMIT 1
            """,
                (user_id, file_hash),
            )

            row = cursor.fetchone()

            if not row:
                logger.info(f"No cached paper found for hash {file_hash}")
                return None

            # Update last_accessed time
            self.update_paper_access_time(row["id"])

            logger.info(f"Retrieved cached paper {row['id']} for user {user_id}")

            return {
                "id": row["id"],
                "file_path": row["file_path"],
                "file_name": row["file_name"],
                "file_hash": row["file_hash"],
                "title": row["paper_title"],
                "authors": json.loads(row["paper_authors"]) if row["paper_authors"] else [],
                "abstract": row["paper_abstract"],
                "full_text": row["full_text"],
                "sections": json.loads(row["sections"]) if row["sections"] else {},
                "figures": json.loads(row["figures"]) if row["figures"] else [],
                "tables": json.loads(row["tables"]) if row["tables"] else [],
                "parsed_at": row["parsed_at"],
            }

        except Exception as e:
            logger.error(f"Failed to get cached paper: {e}")
            return None

    def update_paper_access_time(self, paper_id: str) -> None:
        """Update the last_accessed timestamp for a paper."""
        try:
            cursor = self.conn.cursor()
            cursor.execute(
                """
                UPDATE parsed_papers
                SET last_accessed = ?
                WHERE id = ?
            """,
                (datetime.utcnow().isoformat(), paper_id),
            )
            self.conn.commit()
        except Exception as e:
            logger.warning(f"Failed to update paper access time: {e}")

    # PaperLens query history
    def save_query(
        self,
        user_id: str,
        paper_id: str,
        query_text: str,
        query_results: List[Dict[str, Any]],
        similarity_scores: Dict[str, float],
    ) -> None:
        """Save a query to history."""
        try:
            cursor = self.conn.cursor()
            cursor.execute(
                """
                INSERT INTO query_history
                (id, user_id, paper_id, query_text, query_results, similarity_scores, queried_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    str(uuid.uuid4()),
                    user_id,
                    paper_id,
                    query_text,
                    json.dumps(query_results),
                    json.dumps(similarity_scores),
                    datetime.utcnow().isoformat(),
                ),
            )

            self.conn.commit()
            logger.info(f"Saved query for paper {paper_id}")

        except Exception as e:
            logger.error(f"Failed to save query: {e}")
            self.conn.rollback()
            raise

    def get_query_history(
        self, user_id: str, paper_id: Optional[str] = None, limit: int = DEFAULT_QUERY_HISTORY_LIMIT
    ) -> List[Dict[str, Any]]:
        """Get query history."""
        try:
            cursor = self.conn.cursor()

            if paper_id:
                cursor.execute(
                    """
                    SELECT * FROM query_history
                    WHERE user_id = ? AND paper_id = ?
                    ORDER BY queried_at DESC
                    LIMIT ?
                """,
                    (user_id, paper_id, limit),
                )
            else:
                cursor.execute(
                    """
                    SELECT * FROM query_history
                    WHERE user_id = ?
                    ORDER BY queried_at DESC
                    LIMIT ?
                """,
                    (user_id, limit),
                )

            rows = cursor.fetchall()
            logger.info(f"Retrieved {len(rows)} queries from history")

            return [dict(row) for row in rows]

        except Exception as e:
            logger.error(f"Failed to get query history: {e}")
            return []

    # ===========================
    # Assessed papers
    # ===========================

    def save_assessed_papers(
        self, user_id: str, query_categories: str, papers: List[Dict[str, Any]], assessment_date: date
    ) -> None:
        try:
            cursor = self.conn.cursor()
            now = datetime.utcnow().isoformat()
            for paper in papers:
                cursor.execute(
                    """
                    INSERT OR REPLACE INTO assessed_papers
                    (id, user_id, arxiv_id, query_categories, assessment_date,
                     paper_title, paper_authors, paper_summary, pdf_url,
                     relevance_score, relevance_factors, code_url, tldr,
                     affiliations, emailed, assessed_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                    (
                        str(uuid.uuid4()),
                        user_id,
                        paper.get("arxiv_id", ""),
                        query_categories,
                        assessment_date.isoformat(),
                        paper.get("title", ""),
                        json.dumps(paper.get("authors", [])),
                        paper.get("summary", ""),
                        paper.get("pdf_url", ""),
                        paper.get("relevance_score", 0.0),
                        json.dumps(paper.get("relevance_factors", {})),
                        paper.get("code_url"),
                        paper.get("tldr"),
                        json.dumps(paper.get("affiliations", [])),
                        1 if paper.get("emailed") else 0,
                        now,
                    ),
                )
            self.conn.commit()
            logger.info(f"Saved {len(papers)} assessed papers for user {user_id}")
        except Exception as e:
            logger.error(f"Failed to save assessed papers: {e}")
            self.conn.rollback()
            raise

    def get_assessed_papers(
        self, user_id: str, query_categories: str, from_date: date, to_date: date
    ) -> List[Dict[str, Any]]:
        try:
            cursor = self.conn.cursor()
            cursor.execute(
                """
                SELECT * FROM assessed_papers
                WHERE user_id = ? AND query_categories = ?
                  AND assessment_date >= ? AND assessment_date <= ?
                ORDER BY assessment_date DESC, relevance_score DESC
            """,
                (user_id, query_categories, from_date.isoformat(), to_date.isoformat()),
            )
            rows = cursor.fetchall()
            result = []
            for row in rows:
                d = dict(row)
                d["paper_authors"] = json.loads(d["paper_authors"]) if d.get("paper_authors") else []
                d["relevance_factors"] = json.loads(d["relevance_factors"]) if d.get("relevance_factors") else {}
                d["affiliations"] = json.loads(d["affiliations"]) if d.get("affiliations") else []
                d["emailed"] = bool(d.get("emailed"))
                result.append(d)
            return result
        except Exception as e:
            logger.error(f"Failed to get assessed papers: {e}")
            return []

    # ===========================
    # Notification records
    # ===========================

    def save_notification_record(self, record: Dict[str, Any]) -> None:
        try:
            cursor = self.conn.cursor()
            now = datetime.utcnow().isoformat()
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
            self.conn.commit()
        except Exception as e:
            logger.error(f"Failed to save notification record: {e}")
            self.conn.rollback()
            raise

    def get_notification_record(
        self, user_id: str, query_categories: str, notification_date: date
    ) -> Optional[Dict[str, Any]]:
        try:
            cursor = self.conn.cursor()
            cursor.execute(
                """
                SELECT * FROM notification_records
                WHERE user_id = ? AND query_categories = ? AND notification_date = ?
                LIMIT 1
            """,
                (user_id, query_categories, notification_date.isoformat()),
            )
            row = cursor.fetchone()
            return dict(row) if row else None
        except Exception as e:
            logger.error(f"Failed to get notification record: {e}")
            return None

    def get_missing_notification_dates(
        self, user_id: str, query_categories: str, window_days: int = 7
    ) -> List[date]:
        try:
            today = date.today()
            expected = [today - timedelta(days=i) for i in range(1, window_days + 1)]
            cursor = self.conn.cursor()
            placeholders = ",".join("?" * len(expected))
            cursor.execute(
                f"""
                SELECT notification_date FROM notification_records
                WHERE user_id = ? AND query_categories = ?
                  AND notification_date IN ({placeholders})
                  AND status = 'sent'
            """,
                [user_id, query_categories] + [d.isoformat() for d in expected],
            )
            sent_dates = {row["notification_date"] for row in cursor.fetchall()}
            return sorted([d for d in expected if d.isoformat() not in sent_dates])
        except Exception as e:
            logger.error(f"Failed to get missing notification dates: {e}")
            return []

    def get_notification_records_range(
        self, user_id: str, query_categories: str, from_date: date, to_date: date
    ) -> List[Dict[str, Any]]:
        try:
            cursor = self.conn.cursor()
            cursor.execute(
                """
                SELECT * FROM notification_records
                WHERE user_id = ? AND query_categories = ?
                  AND notification_date >= ? AND notification_date <= ?
                ORDER BY notification_date
            """,
                (user_id, query_categories, from_date.isoformat(), to_date.isoformat()),
            )
            return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"Failed to get notification records range: {e}")
            return []

    # ===========================
    # Google Scholar data
    # ===========================

    def save_scholar_profile(self, user_id: str, profile: Dict[str, Any]) -> None:
        try:
            cursor = self.conn.cursor()
            now = datetime.utcnow().isoformat()
            cursor.execute(
                """
                INSERT OR REPLACE INTO scholar_profiles
                (id, user_id, scholar_user_id, name, affiliation, interests,
                 h_index, i10_index, total_citations, last_synced)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    str(uuid.uuid4()),
                    user_id,
                    profile.get("scholar_user_id", ""),
                    profile.get("name", ""),
                    profile.get("affiliation"),
                    json.dumps(profile.get("interests", [])),
                    profile.get("h_index"),
                    profile.get("i10_index"),
                    profile.get("total_citations", 0),
                    profile.get("last_synced", now),
                ),
            )
            self.conn.commit()
        except Exception as e:
            logger.error(f"Failed to save scholar profile: {e}")
            self.conn.rollback()
            raise

    def get_scholar_profile(self, user_id: str) -> Optional[Dict[str, Any]]:
        try:
            cursor = self.conn.cursor()
            cursor.execute("SELECT * FROM scholar_profiles WHERE user_id = ? LIMIT 1", (user_id,))
            row = cursor.fetchone()
            if not row:
                return None
            d = dict(row)
            d["interests"] = json.loads(d["interests"]) if d.get("interests") else []
            return d
        except Exception as e:
            logger.error(f"Failed to get scholar profile: {e}")
            return None

    def save_scholar_publications(self, user_id: str, publications: List[Dict[str, Any]]) -> None:
        try:
            cursor = self.conn.cursor()
            now = datetime.utcnow().isoformat()
            for pub in publications:
                cursor.execute(
                    """
                    INSERT OR REPLACE INTO scholar_publications
                    (id, user_id, scholar_article_id, title, authors, year,
                     citation_count, venue, url, last_synced)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                    (
                        str(uuid.uuid4()),
                        user_id,
                        pub.get("scholar_article_id"),
                        pub.get("title", ""),
                        json.dumps(pub.get("authors", [])),
                        pub.get("year"),
                        pub.get("citation_count", 0),
                        pub.get("venue"),
                        pub.get("url"),
                        now,
                    ),
                )
            self.conn.commit()
            logger.info(f"Saved {len(publications)} scholar publications for user {user_id}")
        except Exception as e:
            logger.error(f"Failed to save scholar publications: {e}")
            self.conn.rollback()
            raise

    def get_scholar_publications(self, user_id: str, limit: int = 100) -> List[Dict[str, Any]]:
        try:
            cursor = self.conn.cursor()
            cursor.execute(
                """
                SELECT * FROM scholar_publications
                WHERE user_id = ?
                ORDER BY citation_count DESC
                LIMIT ?
            """,
                (user_id, limit),
            )
            rows = cursor.fetchall()
            result = []
            for row in rows:
                d = dict(row)
                d["authors"] = json.loads(d["authors"]) if d.get("authors") else []
                result.append(d)
            return result
        except Exception as e:
            logger.error(f"Failed to get scholar publications: {e}")
            return []

    # ===========================
    # Sync log
    # ===========================

    def save_sync_log(self, entry: Dict[str, Any]) -> None:
        try:
            cursor = self.conn.cursor()
            cursor.execute(
                """
                INSERT INTO sync_log
                (id, user_id, connector_name, status, items_synced, items_total,
                 sync_version, error_message, started_at, completed_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    entry.get("id", str(uuid.uuid4())),
                    entry["user_id"],
                    entry["connector_name"],
                    entry["status"],
                    entry.get("items_synced", 0),
                    entry.get("items_total", 0),
                    entry.get("sync_version"),
                    entry.get("error_message"),
                    entry["started_at"],
                    entry.get("completed_at"),
                ),
            )
            self.conn.commit()
        except Exception as e:
            logger.error(f"Failed to save sync log: {e}")
            self.conn.rollback()
            raise

    def get_last_sync(self, user_id: str, connector_name: str) -> Optional[Dict[str, Any]]:
        try:
            cursor = self.conn.cursor()
            cursor.execute(
                """
                SELECT * FROM sync_log
                WHERE user_id = ? AND connector_name = ? AND status = 'success'
                ORDER BY started_at DESC
                LIMIT 1
            """,
                (user_id, connector_name),
            )
            row = cursor.fetchone()
            return dict(row) if row else None
        except Exception as e:
            logger.error(f"Failed to get last sync: {e}")
            return None

    # ===========================
    # Background tasks (Dashboard)
    # ===========================

    def save_task(self, task: Dict[str, Any]) -> None:
        try:
            cursor = self.conn.cursor()
            cursor.execute(
                """
                INSERT OR REPLACE INTO background_tasks
                (id, user_id, task_type, status, progress, current_step,
                 parameters, result, logs, created_at, started_at,
                 completed_at, error_message)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    task["id"],
                    task["user_id"],
                    task["task_type"],
                    task.get("status", "queued"),
                    task.get("progress", 0.0),
                    task.get("current_step", ""),
                    json.dumps(task.get("parameters", {})),
                    json.dumps(task.get("result")) if task.get("result") else None,
                    json.dumps(task.get("logs", [])),
                    task.get("created_at", datetime.utcnow().isoformat()),
                    task.get("started_at"),
                    task.get("completed_at"),
                    task.get("error_message"),
                ),
            )
            self.conn.commit()
        except Exception as e:
            logger.error(f"Failed to save task: {e}")
            self.conn.rollback()
            raise

    def get_task(self, task_id: str) -> Optional[Dict[str, Any]]:
        try:
            cursor = self.conn.cursor()
            cursor.execute("SELECT * FROM background_tasks WHERE id = ?", (task_id,))
            row = cursor.fetchone()
            if not row:
                return None
            d = dict(row)
            d["parameters"] = json.loads(d["parameters"]) if d.get("parameters") else {}
            d["result"] = json.loads(d["result"]) if d.get("result") else None
            d["logs"] = json.loads(d["logs"]) if d.get("logs") else []
            return d
        except Exception as e:
            logger.error(f"Failed to get task: {e}")
            return None

    def get_tasks(self, user_id: str, status: Optional[str] = None, limit: int = 50) -> List[Dict[str, Any]]:
        try:
            cursor = self.conn.cursor()
            if status:
                cursor.execute(
                    """
                    SELECT * FROM background_tasks
                    WHERE user_id = ? AND status = ?
                    ORDER BY created_at DESC LIMIT ?
                """,
                    (user_id, status, limit),
                )
            else:
                cursor.execute(
                    """
                    SELECT * FROM background_tasks
                    WHERE user_id = ?
                    ORDER BY created_at DESC LIMIT ?
                """,
                    (user_id, limit),
                )
            rows = cursor.fetchall()
            result = []
            for row in rows:
                d = dict(row)
                d["parameters"] = json.loads(d["parameters"]) if d.get("parameters") else {}
                d["result"] = json.loads(d["result"]) if d.get("result") else None
                d["logs"] = json.loads(d["logs"]) if d.get("logs") else []
                result.append(d)
            return result
        except Exception as e:
            logger.error(f"Failed to get tasks: {e}")
            return []

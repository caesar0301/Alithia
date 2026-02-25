"""
PostgreSQL storage backend implementation.
"""

import json
import uuid
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional

from noesium.core.utils import get_logger

from alithia.constants import DEFAULT_QUERY_HISTORY_LIMIT

from .base import StorageBackend

logger = get_logger(__name__)


class PostgresStorage(StorageBackend):
    """PostgreSQL implementation of storage backend."""

    def __init__(self, dsn: str):
        """
        Args:
            dsn: PostgreSQL connection string, e.g.
                 ``postgresql://user:pass@host:5432/dbname``
        """
        self.dsn = dsn
        self.conn = None

    def _import_psycopg(self):
        try:
            import psycopg

            return psycopg
        except ImportError:
            raise ImportError("psycopg is required for PostgreSQL storage. Install with: pip install psycopg[binary]")

    def connect(self) -> None:
        psycopg = self._import_psycopg()
        try:
            self.conn = psycopg.connect(self.dsn, autocommit=False)
            self._create_tables()
            logger.info("Connected to PostgreSQL")
        except Exception as e:
            logger.error(f"Failed to connect to PostgreSQL: {e}")
            raise

    def disconnect(self) -> None:
        if self.conn:
            self.conn.close()
            self.conn = None
            logger.info("Disconnected from PostgreSQL")

    def test_connection(self) -> bool:
        try:
            if self.conn is None:
                return False
            with self.conn.cursor() as cur:
                cur.execute("SELECT 1")
            return True
        except Exception as e:
            logger.warning(f"PostgreSQL connection test failed: {e}")
            return False

    def _create_tables(self) -> None:
        with self.conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS zotero_papers (
                    id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    paper_title TEXT,
                    paper_authors JSONB DEFAULT '[]',
                    paper_abstract TEXT,
                    paper_url TEXT,
                    zotero_item_key TEXT UNIQUE,
                    tags JSONB DEFAULT '[]',
                    date_added TEXT,
                    last_synced TEXT
                )
            """)
            cur.execute("""
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
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS arxiv_papers_emailed (
                    id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    arxiv_id TEXT NOT NULL,
                    paper_title TEXT,
                    paper_authors JSONB DEFAULT '[]',
                    paper_summary TEXT,
                    pdf_url TEXT,
                    code_url TEXT,
                    tldr TEXT,
                    relevance_score DOUBLE PRECISION,
                    published_date TEXT,
                    emailed_at TEXT,
                    UNIQUE(user_id, arxiv_id)
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS parsed_papers (
                    id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    file_path TEXT,
                    file_name TEXT,
                    file_hash TEXT UNIQUE,
                    paper_title TEXT,
                    paper_authors JSONB DEFAULT '[]',
                    paper_abstract TEXT,
                    full_text TEXT,
                    sections JSONB DEFAULT '{}',
                    figures JSONB DEFAULT '[]',
                    tables JSONB DEFAULT '[]',
                    parsed_at TEXT,
                    last_accessed TEXT
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS query_history (
                    id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    paper_id TEXT REFERENCES parsed_papers(id),
                    query_text TEXT,
                    query_results JSONB DEFAULT '[]',
                    similarity_scores JSONB DEFAULT '{}',
                    queried_at TEXT
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS assessed_papers (
                    id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    arxiv_id TEXT NOT NULL,
                    query_categories TEXT NOT NULL,
                    assessment_date TEXT NOT NULL,
                    paper_title TEXT,
                    paper_authors JSONB DEFAULT '[]',
                    paper_summary TEXT,
                    pdf_url TEXT,
                    relevance_score DOUBLE PRECISION,
                    relevance_factors JSONB DEFAULT '{}',
                    code_url TEXT,
                    tldr TEXT,
                    affiliations JSONB DEFAULT '[]',
                    emailed BOOLEAN DEFAULT FALSE,
                    assessed_at TEXT,
                    UNIQUE(user_id, arxiv_id, query_categories)
                )
            """)
            cur.execute("""
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
            cur.execute("""
                CREATE TABLE IF NOT EXISTS scholar_profiles (
                    id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL UNIQUE,
                    scholar_user_id TEXT NOT NULL,
                    name TEXT,
                    affiliation TEXT,
                    interests JSONB DEFAULT '[]',
                    h_index INTEGER,
                    i10_index INTEGER,
                    total_citations INTEGER DEFAULT 0,
                    last_synced TEXT
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS scholar_publications (
                    id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    scholar_article_id TEXT,
                    title TEXT NOT NULL,
                    authors JSONB DEFAULT '[]',
                    year INTEGER,
                    citation_count INTEGER DEFAULT 0,
                    venue TEXT,
                    url TEXT,
                    last_synced TEXT,
                    UNIQUE(user_id, title, year)
                )
            """)
            cur.execute("""
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
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS background_tasks (
                    id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    task_type TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'queued',
                    progress DOUBLE PRECISION DEFAULT 0.0,
                    current_step TEXT DEFAULT '',
                    parameters JSONB DEFAULT '{}',
                    result JSONB,
                    logs JSONB DEFAULT '[]',
                    created_at TEXT,
                    started_at TEXT,
                    completed_at TEXT,
                    error_message TEXT
                )
            """)

            cur.execute("CREATE INDEX IF NOT EXISTS idx_zotero_user ON zotero_papers(user_id, last_synced)")
            cur.execute(
                "CREATE INDEX IF NOT EXISTS idx_arxiv_ranges_user ON arxiv_processed_ranges(user_id, query_categories)"
            )
            cur.execute("CREATE INDEX IF NOT EXISTS idx_arxiv_emailed_user ON arxiv_papers_emailed(user_id, arxiv_id)")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_parsed_papers_hash ON parsed_papers(file_hash)")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_query_history_paper ON query_history(paper_id, queried_at)")
            cur.execute(
                "CREATE INDEX IF NOT EXISTS idx_assessed_papers_lookup "
                "ON assessed_papers(user_id, query_categories, assessment_date)"
            )
            cur.execute(
                "CREATE INDEX IF NOT EXISTS idx_notification_records_lookup "
                "ON notification_records(user_id, query_categories, notification_date)"
            )
            cur.execute(
                "CREATE INDEX IF NOT EXISTS idx_sync_log_lookup ON sync_log(user_id, connector_name, started_at)"
            )
            cur.execute(
                "CREATE INDEX IF NOT EXISTS idx_background_tasks_user ON background_tasks(user_id, status, created_at)"
            )
            cur.execute(
                "CREATE INDEX IF NOT EXISTS idx_scholar_pub_user ON scholar_publications(user_id, citation_count)"
            )

        self.conn.commit()

    def _upsert(self, table: str, record: Dict[str, Any], conflict_columns: List[str]) -> None:
        """Generic upsert helper using ON CONFLICT DO UPDATE."""
        cols = list(record.keys())
        placeholders = [f"%({c})s" for c in cols]
        updates = [f"{c} = EXCLUDED.{c}" for c in cols if c not in conflict_columns]

        sql = (
            f"INSERT INTO {table} ({', '.join(cols)}) VALUES ({', '.join(placeholders)}) "
            f"ON CONFLICT ({', '.join(conflict_columns)}) DO UPDATE SET {', '.join(updates)}"
        )
        with self.conn.cursor() as cur:
            cur.execute(sql, record)

    def _fetchall(self, sql: str, params: Any = None) -> List[Dict[str, Any]]:
        with self.conn.cursor() as cur:
            cur.execute(sql, params)
            columns = [desc[0] for desc in cur.description]
            return [dict(zip(columns, row)) for row in cur.fetchall()]

    def _fetchone(self, sql: str, params: Any = None) -> Optional[Dict[str, Any]]:
        rows = self._fetchall(sql, params)
        return rows[0] if rows else None

    # ===========================
    # Zotero
    # ===========================

    def cache_zotero_papers(self, user_id: str, papers: List[Dict[str, Any]]) -> None:
        try:
            now = datetime.utcnow().isoformat()
            for paper in papers:
                record = {
                    "id": str(uuid.uuid4()),
                    "user_id": user_id,
                    "paper_title": paper.get("title", ""),
                    "paper_authors": json.dumps(paper.get("authors", [])),
                    "paper_abstract": paper.get("abstract", ""),
                    "paper_url": paper.get("url", ""),
                    "zotero_item_key": paper.get("zotero_item_key", ""),
                    "tags": json.dumps(paper.get("tags", [])),
                    "date_added": paper.get("date_added", now),
                    "last_synced": now,
                }
                self._upsert("zotero_papers", record, ["zotero_item_key"])
            self.conn.commit()
            logger.info(f"Cached {len(papers)} Zotero papers for user {user_id}")
        except Exception as e:
            logger.error(f"Failed to cache Zotero papers: {e}")
            self.conn.rollback()
            raise

    def get_zotero_papers(self, user_id: str, max_age_hours: int = 24) -> Optional[List[Dict[str, Any]]]:
        try:
            cutoff = (datetime.utcnow() - timedelta(hours=max_age_hours)).isoformat()
            rows = self._fetchall(
                "SELECT * FROM zotero_papers WHERE user_id = %s AND last_synced >= %s ORDER BY last_synced DESC",
                (user_id, cutoff),
            )
            if not rows:
                return None
            return [
                {
                    "title": r["paper_title"],
                    "authors": (
                        r["paper_authors"] if isinstance(r["paper_authors"], list) else json.loads(r["paper_authors"])
                    ),
                    "abstract": r["paper_abstract"],
                    "url": r["paper_url"],
                    "zotero_item_key": r["zotero_item_key"],
                    "tags": r["tags"] if isinstance(r["tags"], list) else json.loads(r["tags"]),
                    "date_added": r["date_added"],
                }
                for r in rows
            ]
        except Exception as e:
            logger.error(f"Failed to get cached Zotero papers: {e}")
            return None

    # ===========================
    # ArXiv processed ranges
    # ===========================

    def mark_date_range_processed(
        self, user_id: str, from_date: str, to_date: str, query_categories: str, papers_found: int
    ) -> None:
        try:
            record = {
                "id": str(uuid.uuid4()),
                "user_id": user_id,
                "from_date": from_date,
                "to_date": to_date,
                "query_categories": query_categories,
                "papers_found": papers_found,
                "processed_at": datetime.utcnow().isoformat(),
            }
            self._upsert("arxiv_processed_ranges", record, ["user_id", "from_date", "to_date", "query_categories"])
            self.conn.commit()
            logger.info(f"Marked range {from_date}-{to_date} processed for user {user_id} ({papers_found} papers)")
        except Exception as e:
            logger.error(f"Failed to mark date range as processed: {e}")
            self.conn.rollback()
            raise

    def get_processed_ranges(self, user_id: str, query_categories: str, days_back: int = 30) -> List[Dict[str, Any]]:
        try:
            cutoff = (datetime.utcnow() - timedelta(days=days_back)).strftime("%Y%m%d")
            rows = self._fetchall(
                "SELECT from_date, to_date, papers_found, processed_at FROM arxiv_processed_ranges "
                "WHERE user_id = %s AND query_categories = %s AND from_date >= %s ORDER BY from_date DESC",
                (user_id, query_categories, cutoff),
            )
            return rows
        except Exception as e:
            logger.error(f"Failed to get processed ranges: {e}")
            return []

    # ===========================
    # Emailed papers
    # ===========================

    def save_emailed_papers(self, user_id: str, papers: List[Dict[str, Any]]) -> None:
        try:
            now = datetime.utcnow().isoformat()
            for paper in papers:
                record = {
                    "id": str(uuid.uuid4()),
                    "user_id": user_id,
                    "arxiv_id": paper.get("arxiv_id", ""),
                    "paper_title": paper.get("title", ""),
                    "paper_authors": json.dumps(paper.get("authors", [])),
                    "paper_summary": paper.get("summary", ""),
                    "pdf_url": paper.get("pdf_url", ""),
                    "code_url": paper.get("code_url"),
                    "tldr": paper.get("tldr"),
                    "relevance_score": paper.get("relevance_score", 0.0),
                    "published_date": paper.get("published_date"),
                    "emailed_at": now,
                }
                self._upsert("arxiv_papers_emailed", record, ["user_id", "arxiv_id"])
            self.conn.commit()
            logger.info(f"Saved {len(papers)} emailed papers for user {user_id}")
        except Exception as e:
            logger.error(f"Failed to save emailed papers: {e}")
            self.conn.rollback()
            raise

    def get_emailed_papers(
        self, user_id: str, arxiv_ids: Optional[List[str]] = None, days_back: int = 30
    ) -> List[Dict[str, Any]]:
        try:
            cutoff = (datetime.utcnow() - timedelta(days=days_back)).isoformat()
            if arxiv_ids:
                rows = self._fetchall(
                    "SELECT * FROM arxiv_papers_emailed "
                    "WHERE user_id = %s AND arxiv_id = ANY(%s) AND emailed_at >= %s",
                    (user_id, arxiv_ids, cutoff),
                )
            else:
                rows = self._fetchall(
                    "SELECT * FROM arxiv_papers_emailed "
                    "WHERE user_id = %s AND emailed_at >= %s ORDER BY emailed_at DESC",
                    (user_id, cutoff),
                )
            return rows
        except Exception as e:
            logger.error(f"Failed to get emailed papers: {e}")
            return []

    def is_paper_emailed(self, user_id: str, arxiv_id: str) -> bool:
        try:
            row = self._fetchone(
                "SELECT 1 FROM arxiv_papers_emailed WHERE user_id = %s AND arxiv_id = %s LIMIT 1",
                (user_id, arxiv_id),
            )
            return row is not None
        except Exception as e:
            logger.error(f"Failed to check if paper was emailed: {e}")
            return False

    # ===========================
    # Parsed papers
    # ===========================

    def cache_parsed_paper(self, user_id: str, paper_data: Dict[str, Any]) -> str:
        try:
            paper_id = str(uuid.uuid4())
            now = datetime.utcnow().isoformat()
            record = {
                "id": paper_id,
                "user_id": user_id,
                "file_path": paper_data.get("file_path", ""),
                "file_name": paper_data.get("file_name", ""),
                "file_hash": paper_data.get("file_hash", ""),
                "paper_title": paper_data.get("title"),
                "paper_authors": json.dumps(paper_data.get("authors", [])),
                "paper_abstract": paper_data.get("abstract"),
                "full_text": paper_data.get("full_text", ""),
                "sections": json.dumps(paper_data.get("sections", {})),
                "figures": json.dumps(paper_data.get("figures", [])),
                "tables": json.dumps(paper_data.get("tables", [])),
                "parsed_at": now,
                "last_accessed": now,
            }
            self._upsert("parsed_papers", record, ["file_hash"])
            self.conn.commit()
            logger.info(f"Cached parsed paper {paper_id} for user {user_id}")
            return paper_id
        except Exception as e:
            logger.error(f"Failed to cache parsed paper: {e}")
            self.conn.rollback()
            raise

    def get_parsed_paper(self, user_id: str, file_hash: str) -> Optional[Dict[str, Any]]:
        try:
            row = self._fetchone(
                "SELECT * FROM parsed_papers WHERE user_id = %s AND file_hash = %s LIMIT 1",
                (user_id, file_hash),
            )
            if not row:
                return None
            self.update_paper_access_time(row["id"])
            authors = row["paper_authors"]
            sections = row["sections"]
            figures = row["figures"]
            tables = row["tables"]
            return {
                "id": row["id"],
                "file_path": row["file_path"],
                "file_name": row["file_name"],
                "file_hash": row["file_hash"],
                "title": row["paper_title"],
                "authors": authors if isinstance(authors, list) else json.loads(authors),
                "abstract": row["paper_abstract"],
                "full_text": row["full_text"],
                "sections": sections if isinstance(sections, dict) else json.loads(sections),
                "figures": figures if isinstance(figures, list) else json.loads(figures),
                "tables": tables if isinstance(tables, list) else json.loads(tables),
                "parsed_at": row["parsed_at"],
            }
        except Exception as e:
            logger.error(f"Failed to get cached paper: {e}")
            return None

    def update_paper_access_time(self, paper_id: str) -> None:
        try:
            with self.conn.cursor() as cur:
                cur.execute(
                    "UPDATE parsed_papers SET last_accessed = %s WHERE id = %s",
                    (datetime.utcnow().isoformat(), paper_id),
                )
            self.conn.commit()
        except Exception as e:
            logger.warning(f"Failed to update paper access time: {e}")

    # ===========================
    # Query history
    # ===========================

    def save_query(
        self,
        user_id: str,
        paper_id: str,
        query_text: str,
        query_results: List[Dict[str, Any]],
        similarity_scores: Dict[str, float],
    ) -> None:
        try:
            with self.conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO query_history (id, user_id, paper_id, query_text, query_results, similarity_scores, queried_at) "
                    "VALUES (%s, %s, %s, %s, %s, %s, %s)",
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
        except Exception as e:
            logger.error(f"Failed to save query: {e}")
            self.conn.rollback()
            raise

    def get_query_history(
        self, user_id: str, paper_id: Optional[str] = None, limit: int = DEFAULT_QUERY_HISTORY_LIMIT
    ) -> List[Dict[str, Any]]:
        try:
            if paper_id:
                rows = self._fetchall(
                    "SELECT * FROM query_history WHERE user_id = %s AND paper_id = %s ORDER BY queried_at DESC LIMIT %s",
                    (user_id, paper_id, limit),
                )
            else:
                rows = self._fetchall(
                    "SELECT * FROM query_history WHERE user_id = %s ORDER BY queried_at DESC LIMIT %s",
                    (user_id, limit),
                )
            return rows
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
            now = datetime.utcnow().isoformat()
            for paper in papers:
                record = {
                    "id": str(uuid.uuid4()),
                    "user_id": user_id,
                    "arxiv_id": paper.get("arxiv_id", ""),
                    "query_categories": query_categories,
                    "assessment_date": assessment_date.isoformat(),
                    "paper_title": paper.get("title", ""),
                    "paper_authors": json.dumps(paper.get("authors", [])),
                    "paper_summary": paper.get("summary", ""),
                    "pdf_url": paper.get("pdf_url", ""),
                    "relevance_score": paper.get("relevance_score", 0.0),
                    "relevance_factors": json.dumps(paper.get("relevance_factors", {})),
                    "code_url": paper.get("code_url"),
                    "tldr": paper.get("tldr"),
                    "affiliations": json.dumps(paper.get("affiliations", [])),
                    "emailed": paper.get("emailed", False),
                    "assessed_at": now,
                }
                self._upsert("assessed_papers", record, ["user_id", "arxiv_id", "query_categories"])
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
            rows = self._fetchall(
                "SELECT * FROM assessed_papers WHERE user_id = %s AND query_categories = %s "
                "AND assessment_date >= %s AND assessment_date <= %s "
                "ORDER BY assessment_date DESC, relevance_score DESC",
                (user_id, query_categories, from_date.isoformat(), to_date.isoformat()),
            )
            for r in rows:
                for col in ("paper_authors", "relevance_factors", "affiliations"):
                    if isinstance(r.get(col), str):
                        r[col] = json.loads(r[col])
            return rows
        except Exception as e:
            logger.error(f"Failed to get assessed papers: {e}")
            return []

    # ===========================
    # Notification records
    # ===========================

    def save_notification_record(self, record: Dict[str, Any]) -> None:
        try:
            record.setdefault("id", str(uuid.uuid4()))
            record.setdefault("created_at", datetime.utcnow().isoformat())
            self._upsert(
                "notification_records",
                record,
                ["user_id", "query_categories", "notification_date"],
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
            return self._fetchone(
                "SELECT * FROM notification_records WHERE user_id = %s AND query_categories = %s AND notification_date = %s LIMIT 1",
                (user_id, query_categories, notification_date.isoformat()),
            )
        except Exception as e:
            logger.error(f"Failed to get notification record: {e}")
            return None

    def get_missing_notification_dates(self, user_id: str, query_categories: str, window_days: int = 7) -> List[date]:
        try:
            today = date.today()
            expected = [today - timedelta(days=i) for i in range(1, window_days + 1)]
            iso_dates = [d.isoformat() for d in expected]
            rows = self._fetchall(
                "SELECT notification_date FROM notification_records "
                "WHERE user_id = %s AND query_categories = %s AND notification_date = ANY(%s) AND status = 'sent'",
                (user_id, query_categories, iso_dates),
            )
            sent_dates = {r["notification_date"] for r in rows}
            return sorted([d for d in expected if d.isoformat() not in sent_dates])
        except Exception as e:
            logger.error(f"Failed to get missing notification dates: {e}")
            return []

    def get_notification_records_range(
        self, user_id: str, query_categories: str, from_date: date, to_date: date
    ) -> List[Dict[str, Any]]:
        try:
            return self._fetchall(
                "SELECT * FROM notification_records WHERE user_id = %s AND query_categories = %s "
                "AND notification_date >= %s AND notification_date <= %s ORDER BY notification_date",
                (user_id, query_categories, from_date.isoformat(), to_date.isoformat()),
            )
        except Exception as e:
            logger.error(f"Failed to get notification records range: {e}")
            return []

    # ===========================
    # Google Scholar data
    # ===========================

    def save_scholar_profile(self, user_id: str, profile: Dict[str, Any]) -> None:
        try:
            record = {
                "id": profile.get("id", str(uuid.uuid4())),
                "user_id": user_id,
                "scholar_user_id": profile.get("scholar_user_id", ""),
                "name": profile.get("name", ""),
                "affiliation": profile.get("affiliation"),
                "interests": json.dumps(profile.get("interests", [])),
                "h_index": profile.get("h_index"),
                "i10_index": profile.get("i10_index"),
                "total_citations": profile.get("total_citations", 0),
                "last_synced": profile.get("last_synced", datetime.utcnow().isoformat()),
            }
            self._upsert("scholar_profiles", record, ["user_id"])
            self.conn.commit()
        except Exception as e:
            logger.error(f"Failed to save scholar profile: {e}")
            self.conn.rollback()
            raise

    def get_scholar_profile(self, user_id: str) -> Optional[Dict[str, Any]]:
        try:
            row = self._fetchone("SELECT * FROM scholar_profiles WHERE user_id = %s LIMIT 1", (user_id,))
            if row and isinstance(row.get("interests"), str):
                row["interests"] = json.loads(row["interests"])
            return row
        except Exception as e:
            logger.error(f"Failed to get scholar profile: {e}")
            return None

    def save_scholar_publications(self, user_id: str, publications: List[Dict[str, Any]]) -> None:
        try:
            now = datetime.utcnow().isoformat()
            for pub in publications:
                record = {
                    "id": pub.get("id", str(uuid.uuid4())),
                    "user_id": user_id,
                    "scholar_article_id": pub.get("scholar_article_id"),
                    "title": pub.get("title", ""),
                    "authors": json.dumps(pub.get("authors", [])),
                    "year": pub.get("year"),
                    "citation_count": pub.get("citation_count", 0),
                    "venue": pub.get("venue"),
                    "url": pub.get("url"),
                    "last_synced": now,
                }
                self._upsert("scholar_publications", record, ["user_id", "title", "year"])
            self.conn.commit()
            logger.info(f"Saved {len(publications)} scholar publications for user {user_id}")
        except Exception as e:
            logger.error(f"Failed to save scholar publications: {e}")
            self.conn.rollback()
            raise

    def get_scholar_publications(self, user_id: str, limit: int = 100) -> List[Dict[str, Any]]:
        try:
            rows = self._fetchall(
                "SELECT * FROM scholar_publications WHERE user_id = %s ORDER BY citation_count DESC LIMIT %s",
                (user_id, limit),
            )
            for r in rows:
                if isinstance(r.get("authors"), str):
                    r["authors"] = json.loads(r["authors"])
            return rows
        except Exception as e:
            logger.error(f"Failed to get scholar publications: {e}")
            return []

    # ===========================
    # Sync log
    # ===========================

    def save_sync_log(self, entry: Dict[str, Any]) -> None:
        try:
            entry.setdefault("id", str(uuid.uuid4()))
            with self.conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO sync_log (id, user_id, connector_name, status, items_synced, items_total, "
                    "sync_version, error_message, started_at, completed_at) "
                    "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
                    (
                        entry["id"],
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
            return self._fetchone(
                "SELECT * FROM sync_log WHERE user_id = %s AND connector_name = %s AND status = 'success' "
                "ORDER BY started_at DESC LIMIT 1",
                (user_id, connector_name),
            )
        except Exception as e:
            logger.error(f"Failed to get last sync: {e}")
            return None

    # ===========================
    # Background tasks
    # ===========================

    def save_task(self, task: Dict[str, Any]) -> None:
        try:
            record = {
                "id": task["id"],
                "user_id": task["user_id"],
                "task_type": task["task_type"],
                "status": task.get("status", "queued"),
                "progress": task.get("progress", 0.0),
                "current_step": task.get("current_step", ""),
                "parameters": json.dumps(task.get("parameters", {})),
                "result": json.dumps(task.get("result")) if task.get("result") else None,
                "logs": json.dumps(task.get("logs", [])),
                "created_at": task.get("created_at", datetime.utcnow().isoformat()),
                "started_at": task.get("started_at"),
                "completed_at": task.get("completed_at"),
                "error_message": task.get("error_message"),
            }
            self._upsert("background_tasks", record, ["id"])
            self.conn.commit()
        except Exception as e:
            logger.error(f"Failed to save task: {e}")
            self.conn.rollback()
            raise

    def get_task(self, task_id: str) -> Optional[Dict[str, Any]]:
        try:
            row = self._fetchone("SELECT * FROM background_tasks WHERE id = %s", (task_id,))
            if row:
                for col in ("parameters", "result", "logs"):
                    val = row.get(col)
                    if isinstance(val, str):
                        row[col] = json.loads(val)
                    elif val is None and col == "logs":
                        row[col] = []
                    elif val is None and col == "parameters":
                        row[col] = {}
            return row
        except Exception as e:
            logger.error(f"Failed to get task: {e}")
            return None

    def get_tasks(self, user_id: str, status: Optional[str] = None, limit: int = 50) -> List[Dict[str, Any]]:
        try:
            if status:
                rows = self._fetchall(
                    "SELECT * FROM background_tasks WHERE user_id = %s AND status = %s ORDER BY created_at DESC LIMIT %s",
                    (user_id, status, limit),
                )
            else:
                rows = self._fetchall(
                    "SELECT * FROM background_tasks WHERE user_id = %s ORDER BY created_at DESC LIMIT %s",
                    (user_id, limit),
                )
            for row in rows:
                for col in ("parameters", "result", "logs"):
                    val = row.get(col)
                    if isinstance(val, str):
                        row[col] = json.loads(val)
                    elif val is None and col == "logs":
                        row[col] = []
                    elif val is None and col == "parameters":
                        row[col] = {}
            return rows
        except Exception as e:
            logger.error(f"Failed to get tasks: {e}")
            return []

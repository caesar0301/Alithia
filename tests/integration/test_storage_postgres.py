"""
Integration tests for PostgresStorage.

Requires a running PostgreSQL instance. The default DSN matches
the docker-compose.yml service (``docker compose up -d postgres``).

Override with ``ALITHIA_POSTGRES_DSN`` env var if needed.
"""

import os
import uuid
from datetime import date, datetime, timedelta

import pytest

POSTGRES_DSN = os.environ.get(
    "ALITHIA_POSTGRES_DSN",
    "postgresql://test_user:test_password@localhost:5432/test_db",
)


def _storage():
    """Create a fresh PostgresStorage connected to the test database."""
    from alithia.storage.postgres import PostgresStorage

    s = PostgresStorage(POSTGRES_DSN)
    s.connect()
    return s


def _clean(storage):
    """Truncate all tables so each test starts clean."""
    tables = [
        "query_history",
        "parsed_papers",
        "arxiv_papers_emailed",
        "arxiv_processed_ranges",
        "zotero_papers",
        "assessed_papers",
        "notification_records",
        "scholar_publications",
        "scholar_profiles",
        "sync_log",
        "background_tasks",
    ]
    with storage.conn.cursor() as cur:
        for t in tables:
            cur.execute(f"TRUNCATE {t} CASCADE")
    storage.conn.commit()


@pytest.fixture
def storage():
    s = _storage()
    _clean(s)
    yield s
    _clean(s)
    s.disconnect()


USER_ID = "test-user"


@pytest.mark.integration
class TestPostgresConnection:
    def test_connect_and_test(self, storage):
        assert storage.test_connection() is True

    def test_disconnect_reconnect(self, storage):
        storage.disconnect()
        assert storage.test_connection() is False
        storage.connect()
        assert storage.test_connection() is True


@pytest.mark.integration
class TestZoteroPapers:
    def test_cache_and_get(self, storage):
        papers = [
            {
                "title": "Paper A",
                "authors": ["Alice"],
                "abstract": "abs",
                "url": "http://a",
                "zotero_item_key": "ZK1",
                "tags": ["ml"],
            },
            {
                "title": "Paper B",
                "authors": ["Bob"],
                "abstract": "abs2",
                "url": "http://b",
                "zotero_item_key": "ZK2",
                "tags": [],
            },
        ]
        storage.cache_zotero_papers(USER_ID, papers)
        result = storage.get_zotero_papers(USER_ID, max_age_hours=1)
        assert result is not None
        assert len(result) == 2
        titles = {p["title"] for p in result}
        assert titles == {"Paper A", "Paper B"}

    def test_stale_cache_returns_none(self, storage):
        papers = [{"title": "Old", "authors": [], "abstract": "", "url": "", "zotero_item_key": "ZK3", "tags": []}]
        storage.cache_zotero_papers(USER_ID, papers)
        assert storage.get_zotero_papers(USER_ID, max_age_hours=0) is None


@pytest.mark.integration
class TestProcessedRanges:
    def test_mark_and_get(self, storage):
        storage.mark_date_range_processed(USER_ID, "20240101", "20240101", "cs.AI", 42)
        ranges = storage.get_processed_ranges(USER_ID, "cs.AI", days_back=365)
        assert len(ranges) == 1
        assert ranges[0]["papers_found"] == 42


@pytest.mark.integration
class TestEmailedPapers:
    def test_save_and_get(self, storage):
        papers = [{"arxiv_id": "2401.00001", "title": "Test", "authors": ["X"], "summary": "s", "pdf_url": "http://p"}]
        storage.save_emailed_papers(USER_ID, papers)
        result = storage.get_emailed_papers(USER_ID)
        assert len(result) == 1
        assert result[0]["arxiv_id"] == "2401.00001"

    def test_is_paper_emailed(self, storage):
        papers = [{"arxiv_id": "2401.00002", "title": "Test2"}]
        storage.save_emailed_papers(USER_ID, papers)
        assert storage.is_paper_emailed(USER_ID, "2401.00002") is True
        assert storage.is_paper_emailed(USER_ID, "2401.99999") is False


@pytest.mark.integration
class TestParsedPapers:
    def test_cache_and_get(self, storage):
        data = {
            "file_path": "/a/b.pdf",
            "file_name": "b.pdf",
            "file_hash": "abc123",
            "title": "Parsed",
            "authors": ["Y"],
        }
        pid = storage.cache_parsed_paper(USER_ID, data)
        assert pid
        result = storage.get_parsed_paper(USER_ID, "abc123")
        assert result is not None
        assert result["title"] == "Parsed"

    def test_get_missing_returns_none(self, storage):
        assert storage.get_parsed_paper(USER_ID, "no-such-hash") is None


@pytest.mark.integration
class TestQueryHistory:
    def test_save_and_get(self, storage):
        data = {"file_path": "/a.pdf", "file_name": "a.pdf", "file_hash": "qh1", "title": "Q"}
        pid = storage.cache_parsed_paper(USER_ID, data)
        storage.save_query(USER_ID, pid, "how?", [{"chunk": "c1"}], {"c1": 0.9})
        history = storage.get_query_history(USER_ID, paper_id=pid, limit=10)
        assert len(history) == 1
        assert history[0]["query_text"] == "how?"


@pytest.mark.integration
class TestAssessedPapers:
    def test_save_and_get(self, storage):
        today = date.today()
        papers = [{"arxiv_id": "2401.11111", "title": "Assessed", "authors": ["Z"], "relevance_score": 0.85}]
        storage.save_assessed_papers(USER_ID, "cs.AI", papers, today)
        result = storage.get_assessed_papers(USER_ID, "cs.AI", today, today)
        assert len(result) == 1
        assert result[0]["paper_title"] == "Assessed"


@pytest.mark.integration
class TestNotificationRecords:
    def test_save_and_get(self, storage):
        today = date.today()
        record = {
            "user_id": USER_ID,
            "query_categories": "cs.AI",
            "notification_date": today.isoformat(),
            "paper_count": 5,
            "status": "sent",
            "sent_at": datetime.utcnow().isoformat(),
        }
        storage.save_notification_record(record)
        result = storage.get_notification_record(USER_ID, "cs.AI", today)
        assert result is not None
        assert result["status"] == "sent"

    def test_missing_dates(self, storage):
        yesterday = date.today() - timedelta(days=1)
        record = {
            "user_id": USER_ID,
            "query_categories": "cs.AI",
            "notification_date": yesterday.isoformat(),
            "paper_count": 3,
            "status": "sent",
        }
        storage.save_notification_record(record)
        missing = storage.get_missing_notification_dates(USER_ID, "cs.AI", window_days=3)
        assert yesterday not in missing
        assert len(missing) >= 1

    def test_records_range(self, storage):
        today = date.today()
        for i in range(3):
            d = today - timedelta(days=i)
            record = {
                "user_id": USER_ID,
                "query_categories": "cs.AI",
                "notification_date": d.isoformat(),
                "status": "sent",
            }
            storage.save_notification_record(record)
        records = storage.get_notification_records_range(USER_ID, "cs.AI", today - timedelta(days=5), today)
        assert len(records) == 3


@pytest.mark.integration
class TestScholarData:
    def test_profile(self, storage):
        profile = {
            "scholar_user_id": "ABC",
            "name": "Alice",
            "h_index": 10,
            "total_citations": 500,
            "interests": ["ML"],
        }
        storage.save_scholar_profile(USER_ID, profile)
        result = storage.get_scholar_profile(USER_ID)
        assert result is not None
        assert result["h_index"] == 10
        assert "ML" in result["interests"]

    def test_publications(self, storage):
        pubs = [
            {"title": "Paper X", "year": 2024, "citation_count": 100, "authors": ["A"]},
            {"title": "Paper Y", "year": 2023, "citation_count": 50, "authors": ["B"]},
        ]
        storage.save_scholar_publications(USER_ID, pubs)
        result = storage.get_scholar_publications(USER_ID)
        assert len(result) == 2
        assert result[0]["citation_count"] >= result[1]["citation_count"]


@pytest.mark.integration
class TestSyncLog:
    def test_save_and_get(self, storage):
        entry = {
            "user_id": USER_ID,
            "connector_name": "zotero",
            "status": "success",
            "items_synced": 10,
            "items_total": 10,
            "started_at": datetime.utcnow().isoformat(),
            "completed_at": datetime.utcnow().isoformat(),
        }
        storage.save_sync_log(entry)
        result = storage.get_last_sync(USER_ID, "zotero")
        assert result is not None
        assert result["items_synced"] == 10


@pytest.mark.integration
class TestBackgroundTasks:
    def test_save_and_get(self, storage):
        task_id = str(uuid.uuid4())
        task = {
            "id": task_id,
            "user_id": USER_ID,
            "task_type": "paperscout",
            "status": "running",
            "progress": 0.5,
            "parameters": {"from_date": "2024-01-01"},
            "logs": ["step 1"],
        }
        storage.save_task(task)
        result = storage.get_task(task_id)
        assert result is not None
        assert result["status"] == "running"
        assert result["parameters"]["from_date"] == "2024-01-01"

    def test_list_tasks(self, storage):
        for i in range(3):
            storage.save_task(
                {
                    "id": str(uuid.uuid4()),
                    "user_id": USER_ID,
                    "task_type": "paperscout",
                    "status": "completed" if i < 2 else "running",
                }
            )
        all_tasks = storage.get_tasks(USER_ID)
        assert len(all_tasks) == 3
        running = storage.get_tasks(USER_ID, status="running")
        assert len(running) == 1

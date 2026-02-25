"""
Integration tests for the extended SQLite storage backend.

Tests all new Phase-2 methods: assessed papers, notification records,
scholar data, sync log, and background tasks.
"""

import os
import tempfile
import uuid
from datetime import date, datetime, timedelta

import pytest

from alithia.storage.sqlite import SQLiteStorage


@pytest.fixture
def storage():
    """Create a temporary SQLite storage instance."""
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    s = SQLiteStorage(path)
    s.connect()
    yield s
    s.disconnect()
    os.unlink(path)


@pytest.fixture
def user_id():
    return f"test_{uuid.uuid4().hex[:8]}"


class TestAssessedPapers:
    def test_save_and_retrieve(self, storage, user_id):
        today = date.today()
        papers = [
            {
                "arxiv_id": "2401.00001",
                "title": "Test Paper A",
                "authors": ["Alice", "Bob"],
                "summary": "Summary A",
                "pdf_url": "https://arxiv.org/pdf/2401.00001",
                "relevance_score": 8.5,
                "relevance_factors": {"embedding": 8.5},
                "code_url": "https://github.com/example/a",
                "tldr": "TLDR A",
                "affiliations": ["MIT"],
            },
            {
                "arxiv_id": "2401.00002",
                "title": "Test Paper B",
                "authors": ["Carol"],
                "summary": "Summary B",
                "pdf_url": "https://arxiv.org/pdf/2401.00002",
                "relevance_score": 6.2,
                "relevance_factors": {},
                "code_url": None,
                "tldr": None,
                "affiliations": [],
            },
        ]
        query = "cs.AI+cs.LG"

        storage.save_assessed_papers(user_id, query, papers, today)
        result = storage.get_assessed_papers(user_id, query, today, today)

        assert len(result) == 2
        assert result[0]["relevance_score"] >= result[1]["relevance_score"]
        assert result[0]["paper_title"] == "Test Paper A"
        assert result[0]["paper_authors"] == ["Alice", "Bob"]

    def test_date_range_filter(self, storage, user_id):
        query = "cs.AI"
        today = date.today()
        yesterday = today - timedelta(days=1)

        storage.save_assessed_papers(user_id, query, [{"arxiv_id": "a", "title": "Old"}], yesterday)
        storage.save_assessed_papers(user_id, query, [{"arxiv_id": "b", "title": "New"}], today)

        only_today = storage.get_assessed_papers(user_id, query, today, today)
        assert len(only_today) == 1
        assert only_today[0]["arxiv_id"] == "b"

        both = storage.get_assessed_papers(user_id, query, yesterday, today)
        assert len(both) == 2


class TestNotificationRecords:
    def test_save_and_get(self, storage, user_id):
        today = date.today()
        query = "cs.AI"

        storage.save_notification_record(
            {
                "user_id": user_id,
                "query_categories": query,
                "notification_date": today.isoformat(),
                "paper_count": 10,
                "status": "sent",
                "sent_at": datetime.utcnow().isoformat(),
            }
        )

        rec = storage.get_notification_record(user_id, query, today)
        assert rec is not None
        assert rec["status"] == "sent"
        assert rec["paper_count"] == 10

    def test_missing_dates(self, storage, user_id):
        query = "cs.AI"
        today = date.today()

        storage.save_notification_record(
            {
                "user_id": user_id,
                "query_categories": query,
                "notification_date": (today - timedelta(days=1)).isoformat(),
                "paper_count": 5,
                "status": "sent",
            }
        )

        missing = storage.get_missing_notification_dates(user_id, query, window_days=3)
        # day-1 is sent, so day-2 and day-3 should be missing
        assert (today - timedelta(days=1)) not in missing
        assert (today - timedelta(days=2)) in missing

    def test_records_range(self, storage, user_id):
        query = "cs.AI"
        today = date.today()
        for i in range(3):
            d = today - timedelta(days=i)
            storage.save_notification_record(
                {
                    "user_id": user_id,
                    "query_categories": query,
                    "notification_date": d.isoformat(),
                    "status": "sent",
                }
            )

        recs = storage.get_notification_records_range(user_id, query, today - timedelta(days=2), today)
        assert len(recs) == 3

    def test_exactly_once(self, storage, user_id):
        """Saving same (user, query, date) twice should upsert, not duplicate."""
        today = date.today()
        query = "cs.AI"

        storage.save_notification_record(
            {
                "user_id": user_id,
                "query_categories": query,
                "notification_date": today.isoformat(),
                "status": "pending",
            }
        )
        storage.save_notification_record(
            {
                "user_id": user_id,
                "query_categories": query,
                "notification_date": today.isoformat(),
                "status": "sent",
                "sent_at": datetime.utcnow().isoformat(),
            }
        )

        rec = storage.get_notification_record(user_id, query, today)
        assert rec["status"] == "sent"


class TestScholarData:
    def test_profile_upsert(self, storage, user_id):
        profile = {
            "scholar_user_id": "abcdef123",
            "name": "Test Researcher",
            "affiliation": "Test University",
            "interests": ["AI", "ML"],
            "h_index": 15,
            "i10_index": 20,
            "total_citations": 500,
        }

        storage.save_scholar_profile(user_id, profile)
        result = storage.get_scholar_profile(user_id)

        assert result is not None
        assert result["name"] == "Test Researcher"
        assert result["interests"] == ["AI", "ML"]
        assert result["h_index"] == 15

        # Upsert
        profile["h_index"] = 16
        storage.save_scholar_profile(user_id, profile)
        result2 = storage.get_scholar_profile(user_id)
        assert result2["h_index"] == 16

    def test_publications(self, storage, user_id):
        pubs = [
            {"title": "Paper X", "authors": ["A"], "year": 2024, "citation_count": 50, "venue": "NeurIPS"},
            {"title": "Paper Y", "authors": ["B"], "year": 2023, "citation_count": 120, "venue": "ICML"},
        ]

        storage.save_scholar_publications(user_id, pubs)
        result = storage.get_scholar_publications(user_id)

        assert len(result) == 2
        # Ordered by citation_count DESC
        assert result[0]["citation_count"] == 120
        assert result[0]["title"] == "Paper Y"


class TestSyncLog:
    def test_save_and_get_last(self, storage, user_id):
        now = datetime.utcnow()

        storage.save_sync_log(
            {
                "user_id": user_id,
                "connector_name": "zotero",
                "status": "success",
                "items_synced": 42,
                "items_total": 42,
                "started_at": (now - timedelta(seconds=10)).isoformat(),
                "completed_at": now.isoformat(),
            }
        )

        last = storage.get_last_sync(user_id, "zotero")
        assert last is not None
        assert last["status"] == "success"
        assert last["items_synced"] == 42

    def test_failed_not_returned(self, storage, user_id):
        now = datetime.utcnow()

        storage.save_sync_log(
            {
                "user_id": user_id,
                "connector_name": "google_scholar",
                "status": "failed",
                "error_message": "rate limited",
                "started_at": now.isoformat(),
                "completed_at": now.isoformat(),
            }
        )

        last = storage.get_last_sync(user_id, "google_scholar")
        assert last is None  # get_last_sync only returns status='success'


class TestBackgroundTasks:
    def test_save_and_get(self, storage, user_id):
        task_id = str(uuid.uuid4())
        storage.save_task(
            {
                "id": task_id,
                "user_id": user_id,
                "task_type": "paperscout",
                "status": "queued",
                "parameters": {"query": "cs.AI"},
                "created_at": datetime.utcnow().isoformat(),
            }
        )

        task = storage.get_task(task_id)
        assert task is not None
        assert task["task_type"] == "paperscout"
        assert task["parameters"] == {"query": "cs.AI"}

    def test_update_progress(self, storage, user_id):
        task_id = str(uuid.uuid4())
        storage.save_task(
            {
                "id": task_id,
                "user_id": user_id,
                "task_type": "sync",
                "status": "running",
                "progress": 0.5,
                "current_step": "fetching",
            }
        )

        task = storage.get_task(task_id)
        assert task["progress"] == 0.5
        assert task["current_step"] == "fetching"

    def test_list_tasks(self, storage, user_id):
        for i in range(3):
            storage.save_task(
                {
                    "id": str(uuid.uuid4()),
                    "user_id": user_id,
                    "task_type": "test",
                    "status": "completed" if i < 2 else "failed",
                }
            )

        all_tasks = storage.get_tasks(user_id)
        assert len(all_tasks) == 3

        completed = storage.get_tasks(user_id, status="completed")
        assert len(completed) == 2

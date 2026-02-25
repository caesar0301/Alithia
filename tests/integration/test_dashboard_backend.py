"""
Integration tests for the Dashboard FastAPI backend.

Uses a temporary SQLite storage and the TestClient (no live server needed).
Loads real config from .env for profile data.
"""

import os
import tempfile
import uuid
from datetime import date, datetime, timedelta

import pytest

from alithia.config_loader import load_config
from alithia.storage.sqlite import SQLiteStorage


@pytest.fixture
def config():
    return load_config()


@pytest.fixture
def storage():
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


@pytest.fixture
def app(config, storage, user_id):
    """Create FastAPI test app with injected storage."""
    config.setdefault("storage", {})["user_id"] = user_id
    from alithia.dashboard.app import create_app

    return create_app(config, storage)


@pytest.fixture
def client(app):
    from fastapi.testclient import TestClient

    return TestClient(app)


def _seed_data(storage, user_id, query="cs.AI+cs.CV+cs.LG+cs.CL"):
    """Seed storage with sample data for testing endpoints."""
    today = date.today()
    yesterday = today - timedelta(days=1)

    storage.save_assessed_papers(
        user_id,
        query,
        [
            {"arxiv_id": "2401.00001", "title": "Paper A", "authors": ["Alice"], "relevance_score": 8.0},
            {"arxiv_id": "2401.00002", "title": "Paper B", "authors": ["Bob"], "relevance_score": 6.5},
        ],
        today,
    )

    for d in [yesterday, today]:
        storage.save_notification_record(
            {
                "user_id": user_id,
                "query_categories": query,
                "notification_date": d.isoformat(),
                "paper_count": 2,
                "status": "sent",
                "sent_at": datetime.utcnow().isoformat(),
            }
        )

    storage.save_task(
        {
            "id": str(uuid.uuid4()),
            "user_id": user_id,
            "task_type": "paperscout",
            "status": "completed",
            "progress": 1.0,
            "created_at": datetime.utcnow().isoformat(),
        }
    )


# =============================================================================
# GET /api/overview
# =============================================================================


@pytest.mark.integration
class TestOverviewEndpoint:
    def test_overview_empty(self, client):
        resp = client.get("/api/overview")
        assert resp.status_code == 200
        data = resp.json()
        assert "total_papers_assessed" in data
        assert "services" in data

    def test_overview_with_data(self, client, storage, user_id):
        _seed_data(storage, user_id)
        resp = client.get("/api/overview")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_papers_assessed"] >= 2
        assert data["total_notifications_sent"] >= 2


# =============================================================================
# GET /api/profile
# =============================================================================


@pytest.mark.integration
class TestProfileEndpoint:
    def test_profile_returns_config_data(self, client, config):
        resp = client.get("/api/profile")
        assert resp.status_code == 200
        data = resp.json()
        expected_email = config.get("researcher_profile", {}).get("email", "")
        assert data["email"] == expected_email


# =============================================================================
# GET /api/papers
# =============================================================================


@pytest.mark.integration
class TestPapersEndpoint:
    def test_papers_empty(self, client):
        resp = client.get("/api/papers")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_papers_with_data(self, client, storage, user_id):
        _seed_data(storage, user_id)
        resp = client.get("/api/papers")
        assert resp.status_code == 200
        papers = resp.json()
        assert len(papers) >= 2
        assert papers[0]["relevance_score"] >= papers[1]["relevance_score"]

    def test_papers_date_filter(self, client, storage, user_id):
        _seed_data(storage, user_id)
        today = date.today().isoformat()
        resp = client.get(f"/api/papers?from_date={today}&to_date={today}")
        assert resp.status_code == 200


# =============================================================================
# GET /api/calendar
# =============================================================================


@pytest.mark.integration
class TestCalendarEndpoint:
    def test_calendar_empty(self, client):
        resp = client.get("/api/calendar?months=1")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) >= 1
        assert "days" in data[0]

    def test_calendar_with_data(self, client, storage, user_id):
        _seed_data(storage, user_id)
        resp = client.get("/api/calendar?months=1")
        assert resp.status_code == 200
        data = resp.json()
        all_days = [d for m in data for d in m["days"]]
        sent_days = [d for d in all_days if d["status"] == "sent"]
        assert len(sent_days) >= 1

    def test_calendar_big_bang_clamps_start(self, config, storage, user_id):
        """Calendar should not show dates before big_bang."""
        today = date.today()
        big_bang = (today - timedelta(days=3)).isoformat()
        config.setdefault("paperscout_agent", {})["big_bang"] = big_bang
        config.setdefault("storage", {})["user_id"] = user_id

        from fastapi.testclient import TestClient

        from alithia.dashboard.app import create_app

        app = create_app(config, storage)
        client = TestClient(app)

        resp = client.get("/api/calendar?months=1")
        assert resp.status_code == 200
        data = resp.json()
        all_days = [d for m in data for d in m["days"]]
        all_dates = [d["date"] for d in all_days]
        for d in all_dates:
            assert d >= big_bang

    def test_calendar_no_big_bang_shows_full_range(self, config, storage, user_id):
        """Without big_bang, calendar shows the full month range."""
        config.get("paperscout_agent", {}).pop("big_bang", None)
        config.setdefault("storage", {})["user_id"] = user_id

        from fastapi.testclient import TestClient

        from alithia.dashboard.app import create_app

        app = create_app(config, storage)
        client = TestClient(app)

        resp = client.get("/api/calendar?months=2")
        assert resp.status_code == 200
        data = resp.json()
        all_days = [d for m in data for d in m["days"]]
        # 2 months of days should be > 30
        assert len(all_days) > 30


# =============================================================================
# GET /api/agents/tasks
# =============================================================================


@pytest.mark.integration
class TestAgentEndpoints:
    def test_list_tasks_empty(self, client):
        resp = client.get("/api/agents/tasks")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_list_tasks_with_data(self, client, storage, user_id):
        _seed_data(storage, user_id)
        resp = client.get("/api/agents/tasks")
        assert resp.status_code == 200
        tasks = resp.json()
        assert len(tasks) >= 1
        assert tasks[0]["task_type"] == "paperscout"

    def test_get_task_not_found(self, client):
        resp = client.get(f"/api/agents/tasks/{uuid.uuid4()}")
        assert resp.status_code == 404

    def test_task_parameters_persisted(self, client, storage, user_id):
        """Task parameters (from_date, to_date) should be persisted and returned."""
        task_id = str(uuid.uuid4())
        params = {"from_date": "2025-02-24", "to_date": "2025-02-24", "source": "test"}
        storage.save_task(
            {
                "id": task_id,
                "user_id": user_id,
                "task_type": "paperscout",
                "status": "completed",
                "parameters": params,
                "created_at": datetime.utcnow().isoformat(),
            }
        )

        resp = client.get(f"/api/agents/tasks/{task_id}")
        assert resp.status_code == 200
        task = resp.json()
        assert task["parameters"]["from_date"] == "2025-02-24"
        assert task["parameters"]["source"] == "test"


# =============================================================================
# WebSocket /ws
# =============================================================================


@pytest.mark.integration
class TestWebSocket:
    def test_websocket_connects(self, client):
        with client.websocket_connect("/ws") as ws:
            assert ws is not None

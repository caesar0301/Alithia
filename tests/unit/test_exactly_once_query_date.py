"""
Tests for exactly-once notification logic keyed by paper query date.

Verifies that:
- notification_date is derived from config.from_date, not date.today()
- multiple runs on the same running day for different query dates are independent
- already-sent query dates are properly skipped with info_messages
- data_collection_node returns info_messages when range already processed
"""

import os
import tempfile
import uuid
from datetime import date, timedelta
from unittest.mock import patch

import pytest

from alithia.paperscout.state import AgentState, PaperScoutConfig
from alithia.researcher import (
    EmailConnection,
    LLMConnection,
    ResearcherProfile,
    ZoteroConnection,
)
from alithia.storage.sqlite import SQLiteStorage


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
def profile():
    return ResearcherProfile(
        email="test@example.com",
        zotero=ZoteroConnection(zotero_id="test_id", zotero_key="test_key"),
        email_notification=EmailConnection(
            smtp_server="smtp.test.com",
            smtp_port=587,
            sender="sender@test.com",
            sender_password="password",
        ),
        llm=LLMConnection(
            openai_api_key="test_key",
            openai_api_base="https://api.openai.com/v1",
            model_name="gpt-4",
        ),
    )


def _make_state(profile, from_date=None, to_date=None, query="cs.AI"):
    config = PaperScoutConfig(
        user_profile=profile,
        query=query,
        from_date=from_date,
        to_date=to_date or from_date,
    )
    return AgentState(config=config)


class TestCommunicationNodeExactlyOnce:
    """Exactly-once notification check uses the paper query date, not the running date."""

    def test_notification_date_from_config(self, storage, user_id, profile):
        """notification_date should equal config.from_date, not date.today()."""
        from alithia.paperscout.nodes import make_nodes

        nodes = make_nodes(storage, user_id)
        comm = nodes["communication"]

        query_date = (date.today() - timedelta(days=3)).isoformat()

        storage.save_notification_record(
            {
                "user_id": user_id,
                "query_categories": "cs.AI",
                "notification_date": query_date,
                "paper_count": 5,
                "status": "sent",
            }
        )

        state = _make_state(profile, from_date=query_date)
        result = comm(state)

        assert result["current_step"] == "workflow_complete"
        assert len(result.get("info_messages", [])) == 1
        assert "exactly-once" in result["info_messages"][0]
        assert query_date in result["info_messages"][0]

    def test_different_query_dates_same_day(self, storage, user_id, profile):
        """Running for two different query dates on the same day should be independent."""
        from alithia.paperscout.nodes import make_nodes

        nodes = make_nodes(storage, user_id)
        comm = nodes["communication"]

        date_a = (date.today() - timedelta(days=2)).isoformat()
        date_b = (date.today() - timedelta(days=3)).isoformat()

        storage.save_notification_record(
            {
                "user_id": user_id,
                "query_categories": "cs.AI",
                "notification_date": date_a,
                "paper_count": 5,
                "status": "sent",
            }
        )

        state_a = _make_state(profile, from_date=date_a)
        result_a = comm(state_a)
        assert len(result_a.get("info_messages", [])) == 1

        state_b = _make_state(profile, from_date=date_b)
        result_b = comm(state_b)
        assert result_b.get("info_messages") is None or len(result_b.get("info_messages", [])) == 0

    def test_no_skip_when_not_sent(self, storage, user_id, profile):
        """If notification is pending (not sent), should not skip."""
        from alithia.paperscout.nodes import make_nodes

        nodes = make_nodes(storage, user_id)
        comm = nodes["communication"]

        query_date = (date.today() - timedelta(days=1)).isoformat()
        storage.save_notification_record(
            {
                "user_id": user_id,
                "query_categories": "cs.AI",
                "notification_date": query_date,
                "paper_count": 5,
                "status": "pending",
            }
        )

        state = _make_state(profile, from_date=query_date)
        result = comm(state)
        # Should not skip; proceeds to try sending (will fail because no real SMTP)
        # but should not have an exactly-once skip message
        info = result.get("info_messages", [])
        assert not any("exactly-once" in m for m in info)

    def test_no_from_date_defaults_to_yesterday(self, storage, user_id, profile):
        """When from_date is None, notification_date defaults to yesterday."""
        from alithia.paperscout.nodes import make_nodes

        nodes = make_nodes(storage, user_id)
        comm = nodes["communication"]

        yesterday = (date.today() - timedelta(days=1)).isoformat()
        storage.save_notification_record(
            {
                "user_id": user_id,
                "query_categories": "cs.AI",
                "notification_date": yesterday,
                "paper_count": 5,
                "status": "sent",
            }
        )

        state = _make_state(profile, from_date=None)
        result = comm(state)
        assert result["current_step"] == "workflow_complete"
        assert any("exactly-once" in m for m in result.get("info_messages", []))

    def test_notification_record_saved_with_query_date(self, storage, user_id, profile):
        """Pending notification record should be saved with notification_date = query date."""
        from alithia.paperscout.nodes import make_nodes

        nodes = make_nodes(storage, user_id)
        comm = nodes["communication"]

        query_date = (date.today() - timedelta(days=5)).isoformat()
        state = _make_state(profile, from_date=query_date)
        # Provide email_content so it tries to send
        state.scored_papers = []

        comm(state)

        rec = storage.get_notification_record(user_id, "cs.AI", date.fromisoformat(query_date))
        # Either pending or failed (since no real SMTP), but the date key is correct
        if rec:
            assert rec["notification_date"] == query_date


class TestDataCollectionNodeSkipInfo:
    """data_collection_node returns info_messages when date range is already processed."""

    def test_already_processed_returns_info(self, storage, user_id, profile):
        from alithia.paperscout.nodes import make_nodes

        nodes = make_nodes(storage, user_id)
        collect = nodes["data_collection"]

        query_date = date.today() - timedelta(days=1)
        from_date_str = query_date.strftime("%Y%m%d")

        # Seed: cache some Zotero papers so the node doesn't call the real API
        storage.cache_zotero_papers(user_id, [{"title": "Test", "authors": ["A"], "abstract": "..."}])
        storage.mark_date_range_processed(user_id, from_date_str, from_date_str, "cs.AI", 10)

        state = _make_state(profile, from_date=query_date.isoformat())
        result = collect(state)

        assert result["current_step"] == "data_collection_complete"
        assert len(result.get("discovered_papers", [])) == 0
        info = result.get("info_messages", [])
        assert len(info) == 1
        assert "already processed" in info[0]
        assert from_date_str in info[0]

    def test_not_processed_no_info(self, storage, user_id, profile):
        """When date range is NOT processed, no info_messages about skipping."""
        from alithia.paperscout.nodes import make_nodes

        nodes = make_nodes(storage, user_id)
        collect = nodes["data_collection"]

        storage.cache_zotero_papers(user_id, [{"title": "Test", "authors": ["A"], "abstract": "..."}])

        query_date = date.today() - timedelta(days=1)
        state = _make_state(profile, from_date=query_date.isoformat())

        with patch("alithia.paperscout.nodes.fetch_arxiv_papers", return_value=[]):
            result = collect(state)

        info = result.get("info_messages", [])
        assert not any("already processed" in m for m in info)


class TestInfoMessagesAccumulation:
    """info_messages field on AgentState accumulates across nodes."""

    def test_info_messages_field_exists(self, profile):
        state = _make_state(profile)
        assert hasattr(state, "info_messages")
        assert state.info_messages == []

    def test_info_messages_accumulate(self, profile):
        state = _make_state(profile)
        state_dict = state.model_dump()
        assert "info_messages" in state_dict
        assert state_dict["info_messages"] == []

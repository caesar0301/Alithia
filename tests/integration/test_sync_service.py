"""
Integration tests for the sync service.

Tests the SyncOrchestrator, ZoteroConnector (live against API using .env creds),
and the scholar client module.
"""

import asyncio
import os
import tempfile
import uuid
from datetime import datetime

import pytest

from alithia.config_loader import load_config
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
def config():
    return load_config()


@pytest.fixture
def user_id():
    return f"test_{uuid.uuid4().hex[:8]}"


def _has_zotero_creds():
    return bool(os.getenv("ALITHIA_ZOTERO_ID") and os.getenv("ALITHIA_ZOTERO_KEY"))


def _has_scholar_creds():
    return bool(os.getenv("ALITHIA_SCHOLAR_ID"))


# =============================================================================
# SyncOrchestrator tests
# =============================================================================


@pytest.mark.integration
class TestSyncOrchestrator:
    def test_build_connectors_from_profile(self, storage, config, user_id):
        """Orchestrator should detect configured connectors from profile."""
        from alithia.researcher.profile import ResearcherProfile
        from alithia.sync.orchestrator import SyncOrchestrator

        profile = ResearcherProfile.from_config(config)
        orch = SyncOrchestrator(storage, user_id, profile)

        names = [c.name for c in orch.connectors]
        # Zotero should always be present since .env has creds
        if _has_zotero_creds():
            assert "zotero" in names

    def test_get_status(self, storage, config, user_id):
        from alithia.researcher.profile import ResearcherProfile
        from alithia.sync.orchestrator import SyncOrchestrator

        profile = ResearcherProfile.from_config(config)
        orch = SyncOrchestrator(storage, user_id, profile)

        statuses = orch.get_status()
        assert isinstance(statuses, list)
        for s in statuses:
            assert "connector" in s
            assert "configured" in s


# =============================================================================
# ZoteroConnector live test
# =============================================================================


@pytest.mark.integration
class TestZoteroConnectorLive:
    @pytest.mark.skipif(not _has_zotero_creds(), reason="Zotero creds not in .env")
    def test_sync_zotero(self, storage, config, user_id):
        """Live sync against the Zotero API. Validates data lands in storage."""
        from alithia.researcher.profile import ResearcherProfile
        from alithia.sync.connectors.zotero import ZoteroConnector

        profile = ResearcherProfile.from_config(config)
        connector = ZoteroConnector(profile.zotero)

        assert connector.is_configured()

        result = asyncio.get_event_loop().run_until_complete(connector.sync(storage, user_id, force_full=True))

        assert result.status.value in ("success", "partial")
        assert result.items_synced > 0

        # Check data arrived in storage
        cached = storage.get_zotero_papers(user_id, max_age_hours=1)
        assert cached is not None
        assert len(cached) > 0

        # Check sync log was written
        last = storage.get_last_sync(user_id, "zotero")
        assert last is not None
        assert last["status"] == "success"


# =============================================================================
# Scholar client unit test (no live API call)
# =============================================================================


@pytest.mark.integration
class TestScholarClientFallback:
    def test_scholarly_import_error_message(self):
        """If scholarly is not installed, a clear error should be raised."""
        from alithia.utils.scholar_client import _fetch_via_scholarly

        try:
            import scholarly  # noqa: F401

            pytest.skip("scholarly is installed; can't test import error path")
        except ImportError:
            with pytest.raises(ImportError, match="scholarly is not installed"):
                _fetch_via_scholarly("fake_id")

    def test_serpapi_import_error_message(self):
        """If google-search-results is not installed, a clear error should be raised."""
        from alithia.utils.scholar_client import _fetch_via_serpapi

        try:
            import serpapi  # noqa: F401

            pytest.skip("serpapi is installed; can't test import error path")
        except ImportError:
            with pytest.raises(ImportError, match="google-search-results is not installed"):
                _fetch_via_serpapi("fake_id", "fake_key")


# =============================================================================
# SyncLog integration (no network)
# =============================================================================


@pytest.mark.integration
class TestSyncLogIntegration:
    def test_multiple_connectors_logged(self, storage, user_id):
        """Multiple connector sync logs should be independent."""
        now = datetime.utcnow()

        storage.save_sync_log(
            {
                "user_id": user_id,
                "connector_name": "zotero",
                "status": "success",
                "items_synced": 10,
                "started_at": now.isoformat(),
                "completed_at": now.isoformat(),
            }
        )
        storage.save_sync_log(
            {
                "user_id": user_id,
                "connector_name": "google_scholar",
                "status": "success",
                "items_synced": 5,
                "started_at": now.isoformat(),
                "completed_at": now.isoformat(),
            }
        )

        z = storage.get_last_sync(user_id, "zotero")
        g = storage.get_last_sync(user_id, "google_scholar")
        assert z is not None and z["items_synced"] == 10
        assert g is not None and g["items_synced"] == 5

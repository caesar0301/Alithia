"""Tests for the Zotero → Markdown sync (RFC-010 §8).

All tests mock ``pyzotero`` so no network is required. The sync function is
imported lazily, so we inject a fake ``pyzotero.zotero`` module into
``sys.modules`` before each test.
"""

from __future__ import annotations

import sys
import types
from unittest.mock import MagicMock

import pytest

from alithia_agent.research_interests import sync_zotero_to_markdown
from alithia_agent.research_interests.zotero_sync import SyncResult


def _install_fake_pyzotero(items: list[dict]) -> MagicMock:
    """Install a fake ``pyzotero.zotero.Zotero`` returning ``items`` from top()."""
    fake_mod = types.ModuleType("pyzotero")
    fake_zotero_mod = types.ModuleType("pyzotero.zotero")

    class _FakeZotero:
        def __init__(self, library_id, library_type, api_key):
            self.library_id = library_id
            self.library_type = library_type
            self.api_key = api_key

        def top(self):
            return list(items)

        def everything(self, query):
            return list(query)

    fake_zotero_mod.Zotero = _FakeZotero
    fake_mod.zotero = fake_zotero_mod
    sys.modules["pyzotero"] = fake_mod
    sys.modules["pyzotero.zotero"] = fake_zotero_mod
    return fake_mod


def _teardown_pyzotero():
    for key in ("pyzotero", "pyzotero.zotero"):
        sys.modules.pop(key, None)


def _config(api_key="k", library_id="L1", library_type="user"):
    cfg = MagicMock()
    cfg.api_key = api_key
    cfg.library_id = library_id
    cfg.library_type = library_type
    return cfg


def _item(key: str, title: str, abstract: str, date_added="2024-05-24T10:30:00Z", tags=None):
    return {
        "key": key,
        "data": {
            "title": title,
            "abstractNote": abstract,
            "dateAdded": date_added,
            "tags": [{"tag": t} for t in (tags or [])],
        },
    }


@pytest.fixture(autouse=True)
def _cleanup():
    yield
    _teardown_pyzotero()


def test_noop_when_zotero_config_none(tmp_path):
    res = sync_zotero_to_markdown(None, tmp_path)
    assert res == SyncResult(synced=0, pruned=0, skipped=True)
    assert not (tmp_path / "zotero").exists()


def test_no_config_keeps_cached_zotero_files(tmp_path):
    """When zotero is not configured, cached zotero/*.md MUST be preserved —
    they keep contributing to the interests corpus. No pruning, no deletion."""
    zdir = tmp_path / "zotero"
    zdir.mkdir()
    cached_file = zdir / "CACHEDKEY.md"
    cached_file.write_text(
        "---\nsource: zotero\nzotero_item_key: CACHEDKEY\ntitle: Cached\n---\n\nold abstract"
    )
    # Also a hand-written file, which must also be untouched.
    hand = tmp_path / "manual.md"
    hand.write_text("---\ntitle: Manual\n---\n\nbody")

    res = sync_zotero_to_markdown(None, tmp_path)

    assert res == SyncResult(synced=0, pruned=0, skipped=True)
    assert cached_file.exists(), "cached zotero file must NOT be deleted when zotero unconfigured"
    assert (
        cached_file.read_text()
        == "---\nsource: zotero\nzotero_item_key: CACHEDKEY\ntitle: Cached\n---\n\nold abstract"
    )
    assert hand.exists()


def test_writes_one_file_per_item(tmp_path):
    items = [
        _item("ABC123", "Paper A", "Abstract A " * 10),
        _item("DEF456", "Paper B", "Abstract B " * 10, tags=["ml", "cv"]),
    ]
    _install_fake_pyzotero(items)
    res = sync_zotero_to_markdown(_config(), tmp_path)
    assert res.synced == 2
    assert res.pruned == 0
    assert res.skipped is False

    a = (tmp_path / "zotero" / "ABC123.md").read_text()
    assert "source: zotero" in a
    assert "zotero_item_key: ABC123" in a
    assert "Paper A" in a
    assert "Abstract A" in a  # body = abstract

    b = (tmp_path / "zotero" / "DEF456.md").read_text()
    assert "ml" in b and "cv" in b  # tags


def test_date_added_trimmed_to_date(tmp_path):
    items = [_item("K1", "T", "abs " * 20, date_added="2024-05-24T10:30:00Z")]
    _install_fake_pyzotero(items)
    sync_zotero_to_markdown(_config(), tmp_path)
    content = (tmp_path / "zotero" / "K1.md").read_text()
    assert "date_added: '2024-05-24'" in content or "date_added: 2024-05-24" in content
    assert "10:30:00" not in content  # full timestamp NOT written


def test_prunes_stale_files_not_in_fetched_set(tmp_path):
    # Pre-existing stale file for an item no longer in the library.
    (tmp_path / "zotero").mkdir()
    (tmp_path / "zotero" / "OLDKEY.md").write_text(
        "---\nsource: zotero\nzotero_item_key: OLDKEY\ntitle: Old\n---\n\nold abstract"
    )
    items = [_item("NEWKEY", "New", "abs " * 20)]
    _install_fake_pyzotero(items)
    res = sync_zotero_to_markdown(_config(), tmp_path)
    assert res.synced == 1
    assert res.pruned == 1
    assert not (tmp_path / "zotero" / "OLDKEY.md").exists()
    assert (tmp_path / "zotero" / "NEWKEY.md").exists()


def test_hand_written_files_outside_zotero_dir_not_deleted(tmp_path):
    hand = tmp_path / "multimodal.md"
    hand.write_text("---\ntitle: Multimodal\n---\n\nbody")
    items = [_item("K1", "T", "abs " * 20)]
    _install_fake_pyzotero(items)
    sync_zotero_to_markdown(_config(), tmp_path)
    assert hand.exists()  # untouched
    assert hand.read_text().startswith("---\ntitle: Multimodal")


def test_pyzotero_missing_is_skipped_not_raised(tmp_path):
    # Ensure pyzotero is NOT importable.
    _teardown_pyzotero()
    # Block import by injecting a module that raises on import.
    sys.modules["pyzotero"] = None  # type: ignore[assignment]
    res = sync_zotero_to_markdown(_config(), tmp_path)
    assert res.skipped is True
    assert res.error == "pyzotero not installed"
    _teardown_pyzotero()


def test_rollback_warning_suppressed(tmp_path):
    class _RollbackZotero:
        def __init__(self, *a, **k):
            pass

        def top(self):
            raise RuntimeError("transaction rollback")

        def everything(self, q):
            return []

    fake_mod = types.ModuleType("pyzotero")
    fake_zotero_mod = types.ModuleType("pyzotero.zotero")
    fake_zotero_mod.Zotero = _RollbackZotero
    fake_mod.zotero = fake_zotero_mod
    sys.modules["pyzotero"] = fake_mod
    sys.modules["pyzotero.zotero"] = fake_zotero_mod

    res = sync_zotero_to_markdown(_config(), tmp_path)
    assert res.skipped is True
    assert res.error == "rollback warning suppressed"


def test_credentials_incomplete_is_skipped(tmp_path):
    _install_fake_pyzotero([])
    res = sync_zotero_to_markdown(_config(api_key=None, library_id="L1"), tmp_path)
    assert res.skipped is True
    assert res.error == "zotero credentials incomplete"


def test_cache_fresh_uses_cached_items_no_api_call(tmp_path):
    fetched = [_item("LIVE", "Live", "abs " * 20)]
    fake = _install_fake_pyzotero(fetched)
    # Track whether top() is called (it would be on a cache miss).
    call_count = {"top": 0}
    original_top = fake.zotero.Zotero.top

    def counting_top(self):
        call_count["top"] += 1
        return original_top(self)

    fake.zotero.Zotero.top = counting_top

    cached = {
        "papers": [_item("CACHED1", "Cached", "cached abstract " * 5)],
        "timestamp": "2099-01-01T00:00:00",  # future = fresh
    }
    res = sync_zotero_to_markdown(_config(), tmp_path, cache_loader=lambda: cached)
    assert call_count["top"] == 0  # no API call
    assert res.synced == 1
    assert (tmp_path / "zotero" / "CACHED1.md").exists()
    assert not (tmp_path / "zotero" / "LIVE.md").exists()


def test_cache_saver_called_on_fresh_fetch(tmp_path):
    items = [_item("K1", "T", "abs " * 20)]
    _install_fake_pyzotero(items)
    saved: list[dict] = []
    sync_zotero_to_markdown(
        _config(), tmp_path, cache_loader=lambda: None, cache_saver=saved.append
    )
    assert len(saved) == 1
    assert "papers" in saved[0]
    assert "timestamp" in saved[0]

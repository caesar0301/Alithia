"""Sync a Zotero library into research_interests/zotero/*.md.

See RFC-010 §8. This normalizes the user's Zotero library into the same
Markdown format as hand-written research interests, so the matcher can treat
both uniformly. The sync is:

* **Optional**: a no-op when ``zotero_config`` is None or pyzotero is missing.
* **Non-fatal**: sync errors are logged and the run continues with whatever
  interest files already exist on disk (cache, or previously synced files).
* **Lazy**: ``pyzotero`` is imported inside the function, so importing this
  module (and ``paperscout.nodes``) does not require pyzotero installed.
* **Polite**: it only ever manages ``zotero/*.md``; hand-written interest
  files outside that subdirectory are never overwritten or deleted.
"""

from __future__ import annotations

import logging
import re
import warnings
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)

_ZOTERO_SUBDIR = "zotero"
_FRONTMATTER_RE = re.compile(r"\A---\s*\n(.*?)\n---\s*\n?(.*)\Z", re.DOTALL)


@dataclass(frozen=True)
class SyncResult:
    """Outcome of a Zotero sync run (RFC-010 §8.4)."""

    synced: int  # files written
    pruned: int  # stale zotero files removed
    skipped: bool  # True when zotero unconfigured or pyzotero missing
    error: str | None = None  # non-fatal error message, if any


def _zotero_dir(base: Path) -> Path:
    return base / _ZOTERO_SUBDIR


def _coerce_date(value: str | None) -> str | None:
    """Reduce a Zotero dateAdded timestamp to a YYYY-MM-DD string.

    The ``ResearchInterest.date_added`` field is a ``date``; Pydantic v2 will
    not coerce a full ISO datetime string into a date, so we trim to the date
    portion ourselves. Returns None when the input is empty/invalid.
    """
    if not value:
        return None
    s = str(value).strip()
    # Zotero uses e.g. "2024-05-24T10:30:00Z"; the first 10 chars are the date.
    if len(s) >= 10 and s[4] == "-" and s[7] == "-":
        return s[:10]
    return None


def _read_existing_keys(zotero_dir: Path) -> set[str]:
    """Return zotero_item_key values for every zotero/*.md currently on disk."""
    keys: set[str] = set()
    if not zotero_dir.exists():
        return keys
    for path in zotero_dir.glob("*.md"):
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            continue
        m = _FRONTMATTER_RE.match(text)
        if not m:
            continue
        try:
            meta = yaml.safe_load(m.group(1)) or {}
        except yaml.YAMLError:
            continue
        if isinstance(meta, dict) and meta.get("zotero_item_key"):
            keys.add(str(meta["zotero_item_key"]))
    return keys


def _write_item(zotero_dir: Path, item: dict[str, Any]) -> str | None:
    """Write one Zotero item as zotero/<key>.md. Returns the key, or None."""
    data = item.get("data", {}) or {}
    key = item.get("key") or data.get("key") or ""
    if not key:
        return None

    title = data.get("title", "") or "Untitled"
    abstract = data.get("abstractNote", "") or ""
    tags = [t.get("tag", "") for t in data.get("tags", []) if t.get("tag")]
    date_added = _coerce_date(data.get("dateAdded"))

    meta: dict[str, Any] = {
        "title": title,
        "source": "zotero",
        "zotero_item_key": key,
        "tags": tags,
    }
    if date_added:
        meta["date_added"] = date_added

    front = yaml.safe_dump(meta, sort_keys=False, allow_unicode=True).strip()
    body = abstract.strip()
    content = f"---\n{front}\n---\n\n{body}\n"
    zotero_dir.mkdir(parents=True, exist_ok=True)
    (zotero_dir / f"{key}.md").write_text(content, encoding="utf-8")
    return key


def _prune(zotero_dir: Path, keep_keys: set[str]) -> int:
    """Delete zotero/*.md whose key is not in keep_keys (RFC-010 §8.2)."""
    if not zotero_dir.exists():
        return 0
    removed = 0
    for path in zotero_dir.glob("*.md"):
        if path.stem not in keep_keys:
            try:
                path.unlink()
                removed += 1
            except OSError as e:
                logger.warning("zotero_sync: could not prune %s: %s", path, e)
    return removed


def _cache_fresh(cached: dict[str, Any]) -> bool:
    ts = cached.get("timestamp")
    if not ts:
        return False
    try:
        ts_dt = datetime.fromisoformat(str(ts))
    except ValueError:
        return False
    return (datetime.now() - ts_dt).total_seconds() < 86400


def sync_zotero_to_markdown(
    zotero_config: Any | None,
    directory: Path | str,
    *,
    user_id: str = "default",
    cache_loader: Callable[[], dict[str, Any] | None] | None = None,
    cache_saver: Callable[[dict[str, Any]], None] | None = None,
) -> SyncResult:
    """Fetch the Zotero library and write one .md per item (RFC-010 §8.2).

    Args:
        zotero_config: A runtime zotero config (``library_id``, ``api_key``,
            ``library_type``) or None. None → no-op.
        directory: The research_interests directory; items go under ``zotero/``.
        user_id: Used only for logging.
        cache_loader: Optional sync callable returning a cached ``{papers,
            timestamp}`` dict (or None). Lets the node wire its AsyncPersistStore
            without leaking async into this function.
        cache_saver: Optional sync callable to persist a freshly fetched cache.

    Returns:
        SyncResult. Never raises — sync errors are non-fatal.
    """
    base = Path(directory)
    zotero_dir = _zotero_dir(base)

    if zotero_config is None:
        # Zotero not configured: keep all existing cached zotero/*.md files
        # (they still contribute to the interests corpus). Never prune here.
        return SyncResult(synced=0, pruned=0, skipped=True)

    try:
        from pyzotero import zotero  # lazy import (RFC-010 §8.3)
    except ImportError:
        logger.warning(
            "zotero_sync: pyzotero not installed; skipping Zotero sync. "
            "Hand-written research_interests will still be used."
        )
        return SyncResult(synced=0, pruned=0, skipped=True, error="pyzotero not installed")

    try:
        library_id = getattr(zotero_config, "library_id", None)
        api_key = getattr(zotero_config, "api_key", None)
        library_type = getattr(zotero_config, "library_type", "user") or "user"
        if not (library_id and api_key):
            return SyncResult(
                synced=0, pruned=0, skipped=True, error="zotero credentials incomplete"
            )

        items: list[dict[str, Any]] = []
        cached = cache_loader() if cache_loader is not None else None

        if cached and _cache_fresh(cached):
            items = cached.get("papers", []) or []
            logger.info("zotero_sync: using cached Zotero library (%d items)", len(items))
        else:
            zot = zotero.Zotero(library_id, library_type, api_key)
            # Suppress pyzotero's harmless transaction-rollback warnings.
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                items = list(zot.everything(zot.top()))
            if cache_saver is not None:
                try:
                    cache_saver({"papers": items, "timestamp": datetime.now().isoformat()})
                except Exception as e:  # cache write is best-effort
                    logger.debug("zotero_sync: cache save failed: %s", e)

        keep_keys: set[str] = set()
        for item in items:
            key = _write_item(zotero_dir, item)
            if key:
                keep_keys.add(key)

        pruned = _prune(zotero_dir, keep_keys)
        logger.info("zotero_sync: synced %d Zotero items, pruned %d stale", len(keep_keys), pruned)
        return SyncResult(synced=len(keep_keys), pruned=pruned, skipped=False)

    except Exception as e:
        if "rollback" in str(e).lower():
            logger.debug("zotero_sync: suppressed pyzotero rollback warning: %s", e)
            return SyncResult(synced=0, pruned=0, skipped=True, error="rollback warning suppressed")
        logger.warning("zotero_sync: non-fatal error, continuing with existing files: %s", e)
        return SyncResult(synced=0, pruned=0, skipped=True, error=str(e))


__all__ = ["sync_zotero_to_markdown", "SyncResult"]

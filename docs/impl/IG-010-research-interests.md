# IG-010: Research Interests Knowledge Base — Implementation Guide

**Implements**: [RFC-010-research-interests-knowledge](../specs/RFC-010-research-interests-knowledge.md)
**RFC also touches**: RFC-003, RFC-006, RFC-008 (updates handled separately)
**Target modules**: `alithia_agent/research_interests/` (new), `alithia_agent/paperscout/` (reranker, state, nodes, __init__)
**Created**: 2026-06-29
**Status**: Draft

---

## 1. Overview

This guide translates RFC-010 into concrete code: a new `research_interests` package, a unified-corpus extension to `PaperReranker`, and the wiring that drops the hard Zotero gate and loads+syncs interests inside the PaperScout data-collection node. It is ordered so each step is independently testable.

---

## 2. File Plan

| File | Action | Purpose |
|------|--------|---------|
| `alithia_agent/research_interests/__init__.py` | create | public API re-exports |
| `alithia_agent/research_interests/model.py` | create | `ResearchInterest` pydantic model |
| `alithia_agent/research_interests/loader.py` | create | `load_research_interests(dir)` scanner |
| `alithia_agent/research_interests/zotero_sync.py` | create | `sync_zotero_to_markdown()` + `SyncResult` |
| `alithia_agent/paperscout/reranker.py` | edit | unified corpus + weights + observability |
| `alithia_agent/paperscout/state.py` | edit | `research_interests_dir` + `build_runtime_config` + `AgentState` field |
| `alithia_agent/paperscout/nodes.py` | edit | drop zotero gate; sync+load interests; pass to reranker; lazy pyzotero import |
| `alithia_agent/paperscout/__init__.py` | edit | note `pyzotero` optional in plugin deps |
| `alithia_agent/__init__.py` | edit | re-export `ResearchInterest` (optional, for convenience) |

Tests:

| File | Action |
|------|--------|
| `tests/test_research_interests/__init__.py` | create |
| `tests/test_research_interests/test_model.py` | create |
| `tests/test_research_interests/test_loader.py` | create |
| `tests/test_research_interests/test_zotero_sync.py` | create |
| `tests/test_paperscout/test_reranker.py` | edit (add unified-corpus cases) |
| `tests/test_paperscout/test_nodes.py` | edit (add optional-zotero profile_analysis cases) |

---

## 3. `research_interests/model.py`

```python
"""ResearchInterest data model — one knowledge unit from a Markdown file."""

from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class ResearchInterest(BaseModel):
    """One knowledge unit parsed from a research_interests/*.md file.

    See RFC-010 §6.1. The body is set by the loader after stripping frontmatter.
    """

    model_config = ConfigDict(extra="allow")

    title: str
    source: Literal["manual", "zotero"] = "manual"
    weight: float = Field(default=1.0, ge=0.0)
    arxiv_categories: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    notes: str = ""
    date_added: date | None = None
    zotero_item_key: str | None = None

    body: str = ""

    @property
    def display_title(self) -> str:
        return self.title

    def get_searchable_text(self) -> str:
        """Text fed to the embedder: notes + body + tags (RFC-010 §5.4)."""
        parts: list[str] = []
        if self.notes:
            parts.append(self.notes)
        if self.body:
            parts.append(self.body)
        if self.tags:
            parts.append(" ".join(self.tags))
        return " ".join(parts)


__all__ = ["ResearchInterest"]
```

**Notes**: `extra="allow"` matches RFC-008 §11.1 house style for data models. `weight` clamped `ge=0.0` so a user can "park" a unit at `0.0`.

---

## 4. `research_interests/loader.py`

```python
"""Scan a directory of research-interests Markdown files into ResearchInterest units."""

from __future__ import annotations

import logging
import re
from pathlib import Path

import yaml

from alithia_agent.research_interests.model import ResearchInterest

logger = logging.getLogger(__name__)

# Matches a leading ---\n...\n--- frontmatter block.
_FRONTMATTER_RE = re.compile(r"\A---\s*\n(.*?)\n---\s*\n?(.*)\Z", re.DOTALL)


def _parse_file(path: Path) -> ResearchInterest | None:
    """Parse one .md file. Return None (with a warning) if invalid."""
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as e:
        logger.warning("research_interests: cannot read %s: %s", path, e)
        return None

    match = _FRONTMATTER_RE.match(text)
    if not match:
        logger.warning("research_interests: %s has no frontmatter, skipping", path)
        return None

    raw_meta, body = match.group(1), match.group(2)
    try:
        meta = yaml.safe_load(raw_meta) or {}
    except yaml.YAMLError as e:
        logger.warning("research_interests: invalid YAML in %s: %s", path, e)
        return None

    if not isinstance(meta, dict):
        logger.warning("research_interests: frontmatter in %s is not a mapping", path)
        return None

    if not meta.get("title"):
        logger.warning("research_interests: %s missing required 'title', skipping", path)
        return None

    try:
        return ResearchInterest(body=body.strip(), **meta)
    except Exception as e:  # pydantic validation
        logger.warning("research_interests: %s failed validation: %s", path, e)
        return None


def load_research_interests(directory: Path | str) -> list[ResearchInterest]:
    """Load all *.md knowledge units under `directory` (RFC-010 §7.1).

    Pure: no network, no writes. Returns [] for a missing/empty directory.
    Units are returned in stable path-sorted order.
    """
    root = Path(directory)
    if not root.exists() or not root.is_dir():
        return []

    units: list[ResearchInterest] = []
    for path in sorted(root.rglob("*.md")):
        unit = _parse_file(path)
        if unit is not None:
            units.append(unit)
    return units


__all__ = ["load_research_interests"]
```

**Invariants**: never writes/deletes files; never touches the network; tolerates missing dir (`[]`); stable sort by path for deterministic reranking.

---

## 5. `research_interests/zotero_sync.py`

```python
"""Sync a Zotero library into research_interests/zotero/*.md (RFC-010 §8)."""

from __future__ import annotations

import logging
import re
import warnings
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml

from alithia_agent.research_interests.model import ResearchInterest

logger = logging.getLogger(__name__)

_ZOTERO_SUBDIR = "zotero"
_FRONTMATTER_RE = re.compile(r"\A---\s*\n(.*?)\n---\s*\n?(.*)\Z", re.DOTALL)


@dataclass(frozen=True)
class SyncResult:
    synced: int
    pruned: int
    skipped: bool
    error: str | None = None


def _zotero_dir(base: Path) -> Path:
    return base / _ZOTERO_SUBDIR


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


def _write_item(zotero_dir: Path, item: dict[str, Any]) -> None:
    data = item.get("data", {})
    key = item.get("key") or data.get("key") or ""
    if not key:
        return
    title = data.get("title", "") or "Untitled"
    abstract = data.get("abstractNote", "") or ""
    tags = [t.get("tag", "") for t in data.get("tags", []) if t.get("tag")]
    date_added = data.get("dateAdded", "")

    meta = {
        "title": title,
        "source": "zotero",
        "zotero_item_key": key,
        "tags": tags,
    }
    if date_added:
        meta["date_added"] = date_added  # ISO-ish; model coerces to date

    front = yaml.safe_dump(meta, sort_keys=False, allow_unicode=True).strip()
    body = abstract.strip()
    content = f"---\n{front}\n---\n\n{body}\n"
    (zotero_dir).mkdir(parents=True, exist_ok=True)
    (zotero_dir / f"{key}.md").write_text(content, encoding="utf-8")


def _prune(zotero_dir: Path, keep_keys: set[str]) -> int:
    """Delete zotero/*.md whose key is not in keep_keys."""
    if not zotero_dir.exists():
        return 0
    removed = 0
    for path in zotero_dir.glob("*.md"):
        key = path.stem
        if key not in keep_keys:
            try:
                path.unlink()
                removed += 1
            except OSError as e:
                logger.warning("zotero_sync: could not prune %s: %s", path, e)
    return removed


def sync_zotero_to_markdown(
    zotero_config: Any | None,
    directory: Path | str,
    *,
    user_id: str = "default",
    cache_loader: Any | None = None,
) -> SyncResult:
    """Fetch the Zotero library and write one .md per item (RFC-010 §8.2).

    No-op (skipped=True) when zotero_config is None or pyzotero is missing.
    Never raises — sync errors are non-fatal.
    """
    base = Path(directory)
    zotero_dir = _zotero_dir(base)

    if zotero_config is None:
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
            return SyncResult(synced=0, pruned=0, skipped=True, error="zotero credentials incomplete")

        # Optional cache (injected by the node using the AsyncPersistStore).
        items: list[dict[str, Any]] = []
        cached = None
        if cache_loader is not None:
            try:
                cached = cache_loader()
            except Exception:
                cached = None

        if cached and _cache_fresh(cached):
            items = cached.get("papers", []) or []
            _emit_step_local("Using cached Zotero library")
        else:
            zot = zotero.Zotero(library_id, library_type, api_key)
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                items = list(zot.everything(zot.top()))

        keep_keys: set[str] = set()
        for item in items:
            key = item.get("key") or (item.get("data") or {}).get("key")
            if key:
                keep_keys.add(str(key))
                _write_item(zotero_dir, item)

        pruned = _prune(zotero_dir, keep_keys)
        _emit_step_local(f"Synced {len(keep_keys)} Zotero items, pruned {pruned}")
        return SyncResult(synced=len(keep_keys), pruned=pruned, skipped=False)

    except Exception as e:
        if "rollback" in str(e).lower():
            logger.debug("zotero_sync: suppressed pyzotero rollback warning: %s", e)
            return SyncResult(synced=0, pruned=0, skipped=True, error="rollback warning suppressed")
        logger.warning("zotero_sync: non-fatal error, continuing with existing files: %s", e)
        return SyncResult(synced=0, pruned=0, skipped=True, error=str(e))


def _cache_fresh(cached: dict[str, Any]) -> bool:
    ts = cached.get("timestamp")
    if not ts:
        return False
    try:
        ts_dt = datetime.fromisoformat(str(ts))
    except ValueError:
        return False
    return (datetime.now() - ts_dt).total_seconds() < 86400


def _emit_step_local(msg: str) -> None:
    logger.info("zotero_sync: %s", msg)


__all__ = ["sync_zotero_to_markdown", "SyncResult"]
```

**Design notes**:
- `pyzotero` imported lazily — module imports fine without it.
- Cache is *injected* (`cache_loader` callable) so the sync function stays unit-testable without an async store; the node wires `store.load(cache_key)`.
- Pruning uses `path.stem` (the `<key>.md` filename) as the canonical key — robust against malformed frontmatter.
- "rollback" warnings suppressed, matching existing `data_collection_node` behavior.

---

## 6. `research_interests/__init__.py`

```python
"""Research interests knowledge base (RFC-010).

Public API:
- ResearchInterest: one knowledge unit.
- load_research_interests(dir): scan a directory of *.md into units.
- sync_zotero_to_markdown(config, dir): normalize a Zotero library into *.md.
"""

from alithia_agent.research_interests.loader import load_research_interests
from alithia_agent.research_interests.model import ResearchInterest
from alithia_agent.research_interests.zotero_sync import SyncResult, sync_zotero_to_markdown

__all__ = ["ResearchInterest", "load_research_interests", "sync_zotero_to_markdown", "SyncResult"]
```

---

## 7. `paperscout/reranker.py` edits

### 7.1 Constructor

> **CUT AMENDMENT (2026-06-29)**: The `corpus: list[ZoteroPaper]` parameter was
> **removed**. `PaperReranker` now takes only `papers` and `interests`. Zotero
> items arrive exclusively as `ResearchInterest(source="zotero")` units (written
> by the sync step), so there is one matching logic and no double-counting. The
> pseudocode below is superseded by the implemented
> `alithia_agent/paperscout/reranker.py` and RFC-010 §9 (interests-only). Read
> the code blocks below as the pre-cut design; the implemented version drops
> every `corpus`/`zp`/`zotero_papers` reference.

Add an optional `interests` kwarg and a helper to normalize both corpus types into uniform units:

```python
from alithia_agent.research_interests import ResearchInterest

@dataclass
class _CorpusUnit:
    text: str
    weight: float
    date_added: datetime | None
    label: str  # for logging/factors

class PaperReranker:
    def __init__(
        self,
        papers: list[ArxivPaper],
        corpus: list[ZoteroPaper],
        *,
        interests: list[ResearchInterest] | None = None,
        cache_dir: str | None = None,
    ):
        self.papers = papers
        self.corpus = corpus
        self.interests = interests or []
        self.cache_dir = cache_dir or str(get_model_cache_dir())
        ...
```

### 7.2 Unified corpus in `rerank()`

Replace the corpus-text extraction block with one that merges interest units + zotero papers:

```python
units: list[_CorpusUnit] = []
for it in self.interests:
    txt = it.get_searchable_text()
    if txt and len(txt.strip()) > 50:
        units.append(_CorpusUnit(text=txt, weight=it.weight, date_added=_as_datetime(it.date_added), label="interest"))
for zp in sorted_corpus:  # existing zotero sort
    if zp.abstract and len(zp.abstract.strip()) > 50:
        units.append(_CorpusUnit(text=zp.abstract, weight=1.0, date_added=zp.date_added, label="zotero"))

if not units:
    # existing 5.0 fallback, factors note interests_count
```

Then `scores = (similarities * (time_decay_weight * unit_weights)).sum(axis=1) * 10` where `unit_weights` is the per-column weight vector. Keep time-decay normalization exactly as today.

### 7.3 Factors

```python
relevance_factors={
    "corpus_similarity": float(score),
    "corpus_size": len(units),
    "interests_count": len(self.interests),
    "interest_weight": float(max((u.weight for u in units if u.label == "interest"), default=0.0)),
    "max_similarity": float(sim_row.max()),
    "mean_similarity": float(sim_row.mean()),
}
```

### 7.4 Fallback `_fallback_rank()`

Draw keywords from **both** interest titles/tags and zotero titles:

```python
corpus_keywords: set[str] = set()
for it in self.interests:
    for src in (it.title, " ".join(it.tags)):
        for w in src.lower().split():
            if len(w) > 4 and w not in _STOPWORDS:
                corpus_keywords.add(w)
for zp in self.corpus:
    ...  # existing
```

### 7.5 Empty-corpus gate

After the cut, the early-return is simply `if not self.interests:` → default `5.0` scores. (Pre-cut this was `if not self.corpus and not self.interests:`.)

---

## 8. `paperscout/state.py` edits

### 8.1 Runtime config field

Add to `PaperScoutRuntimeConfig`:

```python
research_interests_dir: str | None = None
```

### 8.2 `build_runtime_config`

Set it in the `return cls(...)`:

```python
from alithia_agent import ALITHIA_HOME
...
research_interests_dir=str(ALITHIA_HOME / "research_interests"),
```

(Import `ALITHIA_HOME` at top of file — already available via `alithia_agent`.)

### 8.3 `AgentState`

Add field:

```python
research_interests: list[ResearchInterest]  # loaded from research_interests_dir
```

and set `"research_interests": []` in `runner._initial_state`.

---

## 9. `paperscout/nodes.py` edits

### 9.1 Remove top-level `from pyzotero import zotero` (line 14)

Move it into the zotero branch of `data_collection_node` (and rely on `zotero_sync`'s lazy import).

### 9.2 `profile_analysis_node`

Replace the Zotero hard-gate block (lines 98-105) with:

```python
# RFC-010 §10: zotero is optional. Fail fast only if there is NO knowledge source.
has_zotero = bool(config.zotero and config.zotero.api_key and config.zotero.library_id)
interests_dir = Path(config.research_interests_dir) if config.research_interests_dir else None
has_interests = bool(interests_dir and interests_dir.exists() and any(interests_dir.rglob("*.md")))

if not has_zotero and not has_interests:
    errors.append(
        "No knowledge source: add research_interests markdown files under "
        f"{interests_dir or '~/.alithia/research_interests'} or configure zotero"
    )

if config.send_email and not config.smtp:
    errors.append("SMTP configuration required when send_email=True")
```

### 9.3 `data_collection_node`

After the affiliation-extraction block, replace the existing Zotero-fetch block with:

```python
# RFC-010 §8: sync Zotero into markdown, then load the unified knowledge base.
from alithia_agent.research_interests import load_research_interests, sync_zotero_to_markdown

interests_dir = Path(config.research_interests_dir) if config.research_interests_dir else None
interests: list[ResearchInterest] = []

if interests_dir:
    _emit_step("data_collection", "Syncing Zotero library to research_interests")
    cache_key = f"paperscout:zotero:{user_id}"

    def _cache_loader():
        # runs inside sync; returns cached dict or None
        return await store.load(cache_key)  # see note below on async

    sync_res = sync_zotero_to_markdown(
        config.zotero, interests_dir, user_id=user_id, cache_loader=_cache_loader
    )
    metrics["zotero_sync"] = {"synced": sync_res.synced, "pruned": sync_res.pruned, "skipped": sync_res.skipped}

    _emit_step("data_collection", "Scanning research_interests markdown")
    interests = load_research_interests(interests_dir)
    metrics["interests_count"] = len(interests)
    _emit_step("data_collection", f"Loaded {len(interests)} interest units")

# Keep populating zotero_papers for the legacy corpus branch + cache (RFC-010 §10.2).
zotero_papers: list[ZoteroPaper] = []
if config.zotero:
    # existing fetch/cache logic, moved into a helper or inline, lazy pyzotero import
    ...
```

> **Async cache note**: `sync_zotero_to_markdown` is sync; to keep the existing `await store.load` cache, the node can pre-load the cache into a plain dict and pass a sync `cache_loader` closure. Implementation choice: read cache **before** calling sync, pass the dict via closure. This keeps sync unit-testable (no async leakage).

Then return `research_interests: interests` in the node's return dict.

### 9.4 `relevance_assessment_node`

```python
interests = state.get("research_interests", [])
reranker = PaperReranker(papers=papers, interests=interests)  # no corpus= (cut)
```

### 9.5 Imports

Add `from alithia_agent.research_interests import ResearchInterest` for typing; `from pathlib import Path` if not present.

---

## 10. `paperscout/__init__.py` edits

In the `@plugin(dependencies=[...])` list, add a comment marking `pyzotero` optional:

```python
dependencies=[
    "langgraph>=0.2.0",
    "arxiv>=2.0.0",
    "fastembed>=0.6.0",   # optional at runtime; fallback scoring if absent
    "pyzotero>=1.5.0",    # optional: only needed for Zotero sync (RFC-010 §8.3)
    "scikit-learn>=1.0.0",
],
```

---

## 11. `alithia_agent/__init__.py` (optional re-export)

Add `ResearchInterest` to the model imports and `__all__` for convenience. Not strictly required.

---

## 12. Test Plan

All tests are unit tests with no network.

### 12.1 `tests/test_research_interests/test_model.py`
- Defaults: `source="manual"`, `weight=1.0`, empty lists.
- `weight` clamps `ge=0.0` (negative rejected).
- `get_searchable_text()` = notes + body + tags; handles missing fields.
- `date_added` coerces from ISO string.

### 12.2 `tests/test_research_interests/test_loader.py`
- Valid file → parsed with body stripped of frontmatter.
- File with no frontmatter → skipped (no raise).
- Malformed YAML → skipped.
- Missing `title` → skipped.
- `zotero/` subdir files included (recursive).
- Missing directory → `[]`.
- Stable path-sorted order.
- Tags list parsed correctly.

### 12.3 `tests/test_research_interests/test_zotero_sync.py`
- `zotero_config=None` → `SyncResult(skipped=True)`, no files written.
- Mocked `pyzotero.Zotero` returning 2 items → 2 files written under `zotero/`, correct frontmatter (`source: zotero`, `zotero_item_key`), body = abstract.
- A pre-existing stale `zotero/OLDKEY.md` (not in fetched set) → pruned.
- A hand-written file in the parent dir → **not** deleted.
- `pyzotero` import failing (monkeypatch `sys.modules`) → `skipped=True`, no raise.
- Cache fresh → uses cached items, no API call.
- "rollback" exception → suppressed, `skipped=True`.

### 12.4 `tests/test_paperscout/test_reranker.py` (extend)
- Interests-only corpus (no zotero) → ranks by interest similarity (not all-5.0).
- Mixed manual + zotero-source interest units → unified corpus; `interests_count` factor present.
- `weight` on an interest amplifies its contribution vs a weight-1.0 twin (assert ordering).
- Empty interests → 5.0 fallback (the degenerate path; no separate corpus slot).
- `_fallback_rank` draws keywords from interest tags.

### 12.5 `tests/test_paperscout/test_nodes.py` (extend)
- `profile_analysis`: no zotero + interests dir with ≥1 `.md` → passes (empty errors).
- `profile_analysis`: no zotero + empty/missing interests dir → fails with the new error.
- `profile_analysis`: zotero configured + no interests → passes (existing path).
- `data_collection`: interests loaded into state; sync called (mocked); `interests_count` metric set.
- `relevance_assessment`: reranker receives `interests`.

### 12.6 Regression
- Full `tests/test_paperscout/` suite green (zotero fixtures still valid; `interests` defaults to `[]`).
- `tests/test_daemon/` green (runner uses default runtime config).

---

## 13. Migration Script (`scripts/migrate_research_interests.py`)

Idempotent one-off that:
1. Ensures `~/.alithia/research_interests/` exists.
2. Seeds `01-ai.md`, `02-machine-learning.md`, `03-computer-vision.md` from the legacy config list (only if not already present — never overwrite hand-written files).
3. Leaves `~/.alithia/config.yml` untouched except: the `research_interests` list stays (deprecated, ignored). The user's `zotero` block stays (now optional).

Run with `python scripts/migrate_research_interests.py` (or inline during the migration task).

---

## 14. Acceptance Criteria

- [ ] `import alithia_agent.paperscout.nodes` succeeds with `pyzotero` uninstalled.
- [ ] A PaperScout run with **no zotero** but ≥1 interest `.md` completes and ranks by interest similarity.
- [ ] A PaperScout run with **no zotero and no interests** fails fast with the documented error.
- [ ] A run with zotero configured writes `research_interests/zotero/<key>.md` and prunes stale keys.
- [ ] `pytest tests/` is green; `ruff check` and `mypy` clean on touched files.
- [ ] RFC-003/006/008, rfc-index, rfc-history updated to match.

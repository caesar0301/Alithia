# Syncing Service & Connected Services Persistence Implementation Architecture

> Implementation guide for asynchronous profile syncing and connected service persistence in Alithia.
>
> **Module**: `alithia.sync`
> **Source**: Derived from RFC-0001 (§4.3 Asynchronous by Default, §5.1 Connected Services), RFC-0002 (§5.3 Profile Syncer)
> **Related RFCs**: RFC-0001, RFC-0002, RFC-0004 (Dashboard Architecture)
> **Related Impl Guides**: [paperscout-impl.md](paperscout-impl.md), [dashboard-impl.md](dashboard-impl.md)

---

## 1. Overview

This guide specifies the implementation of a **syncing service layer** that asynchronously synchronizes data from Connected Services (Zotero, Google Scholar, and future integrations) into the Alithia Storage Backend. The sync layer is internal infrastructure — it runs in the background, is triggered on schedule or on-demand, and writes normalized data to persistent storage that other agents (PaperScout, PaperLens) consume.

### Design Goals

1. **Decoupled from agents**: Agents read from storage; they never call external APIs for profile data directly (except as a cache-miss fallback).
2. **Incremental sync**: Only fetch what changed since last sync where APIs support it.
3. **Pluggable connectors**: Each Connected Service implements a common `SyncConnector` interface. Adding a new service means adding one connector module.
4. **Idempotent writes**: Re-running sync for the same data window produces the same storage state.
5. **Failure isolation**: One connector failing does not block others.

---

## 2. Architectural Position

```
                    ┌──────────────────────────────┐
                    │       ResearcherProfile       │
                    │  (connected service configs)  │
                    └───────────────┬───────────────┘
                                    │ reads configs
                                    ▼
    ┌───────────────────────────────────────────────────────────┐
    │                      SyncOrchestrator                     │
    │                                                           │
    │  ┌─────────────────┐  ┌─────────────────┐  ┌──────────┐  │
    │  │ ZoteroConnector │  │ ScholarConnector │  │ Future.. │  │
    │  └────────┬────────┘  └────────┬────────┘  └────┬─────┘  │
    │           │                    │                 │         │
    │           ▼                    ▼                 ▼         │
    │     Zotero API          SerpAPI /          (other APIs)   │
    │                         Scholarly                          │
    └───────────────────────────┬───────────────────────────────┘
                                │ writes normalized data
                                ▼
    ┌───────────────────────────────────────────────────────────┐
    │            StorageBackend (Supabase / SQLite)             │
    │                                                           │
    │  zotero_papers │ scholar_profile │ scholar_papers │ ...   │
    └───────────────────────────────────────────────────────────┘
                                │
              ┌─────────────────┼─────────────────┐
              ▼                 ▼                  ▼
        PaperScout          PaperLens         (other agents)
        reads corpus        reads profile     reads data
```

### Dependency Graph

```
alithia.sync.orchestrator    → sync.base, sync.connectors.*, storage, researcher
alithia.sync.base            → (no internal deps)
alithia.sync.connectors.zotero    → sync.base, utils.zotero_client, models.zotero_paper
alithia.sync.connectors.scholar   → sync.base, models.scholar_profile [NEW]
alithia.storage.base         → (extended with scholar methods)
```

---

## 3. Module Structure

```
alithia/
├── sync/                              # [NEW] Syncing service layer
│   ├── __init__.py
│   ├── base.py                        # SyncConnector ABC, SyncResult model
│   ├── orchestrator.py                # SyncOrchestrator: runs all connectors
│   └── connectors/
│       ├── __init__.py
│       ├── zotero.py                  # ZoteroConnector: sync Zotero favorites
│       └── scholar.py                 # ScholarConnector: sync Google Scholar profile
├── models/
│   ├── zotero_paper.py                # ZoteroPaper (shared with paperscout)
│   └── scholar_profile.py            # [NEW] ScholarProfile, ScholarPublication
├── storage/
│   ├── base.py                        # StorageBackend (extended)
│   ├── sqlite.py                      # SQLiteStorage (extended)
│   ├── supabase.py                    # SupabaseStorage (extended)
│   └── migrations/
│       └── 003_sync_service.sql       # [NEW] Scholar tables, sync_log
├── researcher/
│   └── connection.py                  # GoogleScholarConnection (existing, enhanced)
├── utils/
│   ├── zotero_client.py               # Existing Zotero API wrapper
│   └── scholar_client.py             # [NEW] Google Scholar API wrapper
└── run/
    └── __main__.py                    # CLI: `sync` subcommand
```

---

## 4. Core Types

### 4.1 SyncConnector ABC (`alithia/sync/base.py`)

```python
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

class SyncStatus(str, Enum):
    SUCCESS = "success"
    PARTIAL = "partial"
    FAILED = "failed"
    SKIPPED = "skipped"

@dataclass
class SyncResult:
    """Result of a single connector sync run."""
    connector_name: str
    status: SyncStatus
    items_synced: int = 0
    items_total: int = 0
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None
    details: Dict[str, Any] = field(default_factory=dict)

class SyncConnector(ABC):
    """Interface for Connected Service sync connectors."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique connector identifier (e.g., 'zotero', 'google_scholar')."""

    @abstractmethod
    def is_configured(self) -> bool:
        """Return True if credentials and config are present."""

    @abstractmethod
    async def sync(
        self, storage: "StorageBackend", user_id: str,
        force_full: bool = False
    ) -> SyncResult:
        """
        Run sync. Writes data to storage.

        Args:
            storage: Storage backend to write to
            user_id: User identifier
            force_full: If True, ignore incremental state and do full sync

        Returns:
            SyncResult with status and metrics
        """

    @abstractmethod
    def last_synced_at(self, storage: "StorageBackend", user_id: str) -> Optional[datetime]:
        """Return timestamp of last successful sync, or None."""
```

### 4.2 SyncOrchestrator (`alithia/sync/orchestrator.py`)

```python
class SyncOrchestrator:
    """Runs all configured sync connectors."""

    def __init__(
        self, storage: StorageBackend, user_id: str,
        profile: ResearcherProfile
    ):
        self._storage = storage
        self._user_id = user_id
        self._connectors: List[SyncConnector] = self._build_connectors(profile)

    def _build_connectors(self, profile: ResearcherProfile) -> List[SyncConnector]:
        """Instantiate connectors based on which services are configured."""
        connectors = []
        if profile.zotero:
            connectors.append(ZoteroConnector(profile.zotero))
        if profile.google_scholar:
            connectors.append(ScholarConnector(profile.google_scholar))
        return connectors

    async def sync_all(self, force_full: bool = False) -> List[SyncResult]:
        """
        Run all connectors concurrently. Each connector is independent (failure isolation).
        Returns list of SyncResults.
        """

    async def sync_one(self, connector_name: str, force_full: bool = False) -> SyncResult:
        """Run a specific connector by name."""
```

### 4.3 ZoteroPaper (`alithia/models/zotero_paper.py`)

Already defined in `paperscout-impl.md` §4.1. Shared between sync service and PaperScout.

### 4.4 ScholarProfile (NEW — `alithia/models/scholar_profile.py`)

```python
class ScholarPublication(BaseModel):
    """A single publication from Google Scholar."""
    title: str
    authors: List[str]
    year: Optional[int] = None
    citation_count: int = 0
    venue: Optional[str] = None
    url: Optional[str] = None
    scholar_id: Optional[str] = None    # Google Scholar article ID

class ScholarProfile(BaseModel):
    """Normalized Google Scholar researcher profile."""
    scholar_user_id: str                 # Google Scholar user ID
    name: str
    affiliation: Optional[str] = None
    interests: List[str] = Field(default_factory=list)
    h_index: Optional[int] = None
    i10_index: Optional[int] = None
    total_citations: int = 0
    publications: List[ScholarPublication] = Field(default_factory=list)
    fetched_at: Optional[datetime] = None

    def to_storage_dict(self) -> Dict[str, Any]:
        """Serialize for storage."""

    @classmethod
    def from_storage_dict(cls, row: Dict[str, Any]) -> "ScholarProfile":
        """Deserialize from storage row."""
```

### 4.5 GoogleScholarConnection (enhanced — `alithia/researcher/connection.py`)

The existing model has placeholder fields. Update to reflect actual usage:

```python
class GoogleScholarConnection(BaseModel):
    """Google Scholar connection configuration."""
    scholar_id: str            # Google Scholar user/profile ID (from URL)
    serpapi_key: Optional[str] = None  # SerpAPI key for reliable fetching
```

**Note**: `google_scholar_token` is renamed to `serpapi_key` for clarity. The `scholar_id` is the Google Scholar profile ID visible in the profile URL, not a token.

---

## 5. Connector Implementations

### 5.1 ZoteroConnector (`alithia/sync/connectors/zotero.py`)

```python
class ZoteroConnector(SyncConnector):
    """Syncs user's Zotero library to storage."""

    def __init__(self, connection: ZoteroConnection):
        self._connection = connection

    @property
    def name(self) -> str:
        return "zotero"

    def is_configured(self) -> bool:
        return bool(self._connection.zotero_id and self._connection.zotero_key)

    async def sync(self, storage, user_id, force_full=False) -> SyncResult:
        """
        Sync flow:
        1. Call get_zotero_corpus(zotero_id, zotero_key)
        2. Convert raw items → List[ZoteroPaper] via ZoteroPaper.from_zotero_api()
        3. Filter out items without abstracts
        4. Write to storage via storage.cache_zotero_papers()
        5. Return SyncResult with counts
        """

    def last_synced_at(self, storage, user_id) -> Optional[datetime]:
        """Check max(last_synced) from zotero_papers table."""
```

**Incremental sync**: Zotero API supports `since` parameter (library version number). Store the library version in a `sync_metadata` table and pass it on subsequent syncs. If `force_full=True`, ignore the version and re-fetch everything.

### 5.2 ScholarConnector (`alithia/sync/connectors/scholar.py`)

```python
class ScholarConnector(SyncConnector):
    """Syncs Google Scholar profile and publications to storage."""

    def __init__(self, connection: GoogleScholarConnection):
        self._connection = connection

    @property
    def name(self) -> str:
        return "google_scholar"

    def is_configured(self) -> bool:
        return bool(self._connection.scholar_id)

    async def sync(self, storage, user_id, force_full=False) -> SyncResult:
        """
        Sync flow:
        1. Fetch profile via scholar_client.get_profile(scholar_id, serpapi_key)
        2. Fetch publications list
        3. Convert to ScholarProfile model
        4. Write to storage via storage.save_scholar_profile()
        5. Write publications via storage.save_scholar_publications()
        6. Return SyncResult
        """
```

**API Strategy**: Google Scholar has no official API. Options (in priority order):
1. **SerpAPI** (`serpapi_key` configured): Reliable, paid, structured JSON responses.
2. **scholarly** library (fallback): Open-source scraper, may hit rate limits.
3. If neither works, return `SyncStatus.FAILED` with descriptive error.

---

## 6. Implementation Details

### 6.1 Concurrency Model

The `SyncOrchestrator.sync_all()` method runs connectors concurrently using `asyncio.gather` with `return_exceptions=True`. Each connector is independent — one failing does not affect others (RFC-0001 §4.4 Graceful Degradation).

```python
async def sync_all(self, force_full=False) -> List[SyncResult]:
    tasks = [
        connector.sync(self._storage, self._user_id, force_full)
        for connector in self._connectors
        if connector.is_configured()
    ]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    return [
        r if isinstance(r, SyncResult) else SyncResult(
            connector_name="unknown", status=SyncStatus.FAILED,
            error_message=str(r)
        )
        for r in results
    ]
```

### 6.2 Sync Trigger Modes

| Mode | Trigger | Implementation |
|------|---------|----------------|
| **CLI manual** | `python -m alithia.run sync --all` | Calls `SyncOrchestrator.sync_all()` |
| **CLI single** | `python -m alithia.run sync --connector zotero` | Calls `sync_one("zotero")` |
| **Agent inline** | PaperScout data_collection_node cache miss | Calls `ZoteroConnector.sync()` directly |
| **Scheduled** | GitHub Actions cron / system crontab | Runs CLI command on schedule |

### 6.3 Zotero Sync Detail

**Current flow** (in `data_collection_node`):
1. `get_zotero_corpus()` → raw dicts
2. Pass raw dicts to `cache_zotero_papers()` → format mismatch
3. Read back from cache → flat format doesn't match reranker expectations

**New flow**:
1. `ZoteroConnector.sync()`:
   - Calls `get_zotero_corpus(zotero_id, zotero_key)` → raw dicts
   - Converts each to `ZoteroPaper.from_zotero_api(raw_item, paths)`
   - Calls `storage.cache_zotero_papers(user_id, [p.to_storage_dict() for p in papers])`
2. PaperScout reads from storage:
   - `cached = storage.get_zotero_papers(user_id)`
   - `corpus = [ZoteroPaper.from_storage_dict(row) for row in cached]`
3. Reranker uses `paper.abstract` directly — no format mismatch.

### 6.4 Google Scholar Sync Detail

**Profile data persisted**:
- Researcher name, affiliation, interests (tags) → can enrich `ResearcherProfile.research_interests`
- h-index, i10-index, total citations → metadata for display/filtering
- Publication list → can be used as additional corpus for relevance scoring (alongside Zotero)

**Sync strategy**:
- Full sync only (Google Scholar has no incremental API).
- Cache TTL: 24 hours (configurable). Skip sync if last sync within TTL and `force_full=False`.
- Rate limit: At most 1 request per 10 seconds for `scholarly`; SerpAPI handles its own limits.

### 6.5 Sync Metadata Tracking

A `sync_log` table records every sync attempt for observability and incremental sync support:

```sql
CREATE TABLE IF NOT EXISTS sync_log (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id TEXT NOT NULL,
    connector_name TEXT NOT NULL,          -- 'zotero', 'google_scholar', etc.
    status TEXT NOT NULL,                  -- success | partial | failed | skipped
    items_synced INTEGER DEFAULT 0,
    items_total INTEGER DEFAULT 0,
    sync_version TEXT,                     -- Connector-specific version (e.g., Zotero library version)
    error_message TEXT,
    started_at TIMESTAMPTZ NOT NULL,
    completed_at TIMESTAMPTZ,

    CONSTRAINT sync_log_recent UNIQUE (user_id, connector_name, started_at)
);

CREATE INDEX IF NOT EXISTS idx_sync_log_lookup
    ON sync_log(user_id, connector_name, started_at DESC);
```

---

## 7. Storage Extensions

### 7.1 New StorageBackend Methods

```python
class StorageBackend(ABC):
    # ... existing methods ...

    # --- NEW: Google Scholar ---
    @abstractmethod
    def save_scholar_profile(self, user_id: str, profile: Dict[str, Any]) -> None:
        """Upsert Google Scholar profile for a user."""

    @abstractmethod
    def get_scholar_profile(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Get cached Scholar profile. Returns None if not synced."""

    @abstractmethod
    def save_scholar_publications(
        self, user_id: str, publications: List[Dict[str, Any]]
    ) -> None:
        """Upsert Scholar publications for a user."""

    @abstractmethod
    def get_scholar_publications(
        self, user_id: str, limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Get cached Scholar publications."""

    # --- NEW: Sync log ---
    @abstractmethod
    def save_sync_log(self, entry: Dict[str, Any]) -> None:
        """Record a sync attempt."""

    @abstractmethod
    def get_last_sync(
        self, user_id: str, connector_name: str
    ) -> Optional[Dict[str, Any]]:
        """Get the most recent successful sync log entry for a connector."""
```

### 7.2 New Tables

#### `scholar_profiles`

```sql
CREATE TABLE IF NOT EXISTS scholar_profiles (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id TEXT NOT NULL UNIQUE,
    scholar_user_id TEXT NOT NULL,
    name TEXT,
    affiliation TEXT,
    interests JSONB DEFAULT '[]'::jsonb,
    h_index INTEGER,
    i10_index INTEGER,
    total_citations INTEGER DEFAULT 0,
    last_synced TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT scholar_profiles_user_unique UNIQUE (user_id)
);
```

#### `scholar_publications`

```sql
CREATE TABLE IF NOT EXISTS scholar_publications (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id TEXT NOT NULL,
    scholar_article_id TEXT,
    title TEXT NOT NULL,
    authors JSONB DEFAULT '[]'::jsonb,
    year INTEGER,
    citation_count INTEGER DEFAULT 0,
    venue TEXT,
    url TEXT,
    last_synced TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT scholar_publications_unique UNIQUE (user_id, title, year)
);

CREATE INDEX IF NOT EXISTS idx_scholar_pub_user
    ON scholar_publications(user_id, citation_count DESC);
```

#### `sync_log`

See §6.5 above.

---

## 8. Error Handling

### 8.1 Per-Connector Isolation

Each connector runs in its own `try/except` block within `sync_all()`. Failures produce a `SyncResult` with `status=FAILED` and `error_message` — they do not propagate to other connectors.

### 8.2 Retry Strategy

| Connector | Retryable Errors | Strategy |
|-----------|-----------------|----------|
| Zotero | HTTP 429, 5xx, timeout | Exponential backoff, max 3 retries |
| Google Scholar (SerpAPI) | HTTP 429, 5xx | Exponential backoff, max 3 retries |
| Google Scholar (scholarly) | Rate limit, captcha | Wait 30s, retry once, then fail |

### 8.3 Partial Sync

If a connector fetches N items but fails partway through writing:
- `SyncStatus.PARTIAL` is recorded with `items_synced < items_total`.
- Already-written items remain in storage (idempotent upsert).
- Next sync run picks up where it left off if incremental sync is supported.

---

## 9. Configuration

### 9.1 Config Schema Additions

```json
{
  "researcher_profile": {
    "google_scholar": {
      "scholar_id": "aBcDeFg1234",
      "serpapi_key": "optional_serpapi_key"
    }
  },
  "sync": {
    "zotero_sync_interval_hours": 24,
    "scholar_sync_interval_hours": 24,
    "max_retries": 3
  }
}
```

### 9.2 Environment Variable Mapping

| Config Path | Env Var |
|-------------|---------|
| `researcher_profile.google_scholar.scholar_id` | `ALITHIA_GOOGLE_SCHOLAR_ID` |
| `researcher_profile.google_scholar.serpapi_key` | `ALITHIA_SERPAPI_KEY` |
| `sync.zotero_sync_interval_hours` | `ALITHIA_ZOTERO_SYNC_INTERVAL` |
| `sync.scholar_sync_interval_hours` | `ALITHIA_SCHOLAR_SYNC_INTERVAL` |

---

## 10. CLI Interface

Add a `sync` subcommand to the existing CLI:

```bash
# Sync all configured services
uv run python -m alithia.run sync --config config.json

# Sync specific connector
uv run python -m alithia.run sync --config config.json --connector zotero
uv run python -m alithia.run sync --config config.json --connector google_scholar

# Force full sync (ignore incremental state)
uv run python -m alithia.run sync --config config.json --full

# Show sync status
uv run python -m alithia.run sync --config config.json --status
```

**Implementation in `run/__main__.py`**:

```python
def add_sync_subparser(subparsers):
    parser = subparsers.add_parser("sync", help="Sync connected services")
    parser.add_argument("-c", "--config", help="Config file path")
    parser.add_argument("--connector", choices=["zotero", "google_scholar"],
                        help="Sync specific connector only")
    parser.add_argument("--full", action="store_true",
                        help="Force full sync (ignore incremental state)")
    parser.add_argument("--status", action="store_true",
                        help="Show last sync status for all connectors")

async def run_sync(args):
    config = load_config(args.config)
    storage = get_storage_backend(config)
    user_id = config.get("storage", {}).get("user_id", "default")
    profile = ResearcherProfile.from_config(config)

    orchestrator = SyncOrchestrator(storage, user_id, profile)

    if args.status:
        for connector in orchestrator.connectors:
            last = connector.last_synced_at(storage, user_id)
            print(f"{connector.name}: last synced {last or 'never'}")
        return

    if args.connector:
        result = await orchestrator.sync_one(args.connector, force_full=args.full)
        results = [result]
    else:
        results = await orchestrator.sync_all(force_full=args.full)

    for r in results:
        print(f"{r.connector_name}: {r.status.value} "
              f"({r.items_synced}/{r.items_total} items)")
```

---

## 11. Testing Strategy

### 11.1 Unit Tests

| Test File | Scope |
|-----------|-------|
| `tests/unit/test_sync_connector_base.py` | `SyncConnector` interface contract |
| `tests/unit/test_zotero_connector.py` | Zotero normalization, mock API |
| `tests/unit/test_scholar_connector.py` | Scholar profile parsing, mock API |
| `tests/unit/test_scholar_profile_model.py` | `ScholarProfile` serialization round-trip |
| `tests/unit/test_sync_orchestrator.py` | Concurrent execution, failure isolation |

### 11.2 Integration Tests

| Test File | Scope |
|-----------|-------|
| `tests/integration/test_zotero_sync_e2e.py` | Real Zotero API (with test library) → SQLite |
| `tests/integration/test_scholar_sync_e2e.py` | Real SerpAPI → SQLite |
| `tests/integration/test_sync_storage.py` | Both backends implement scholar methods |

### 11.3 Key Test Scenarios

1. **Connector isolation**: One connector raises exception → others still complete.
2. **Idempotent upsert**: Run Zotero sync twice → same row count, no duplicates.
3. **Incremental sync**: Add a paper to Zotero → only new paper is synced on next run.
4. **Cache TTL**: Sync with TTL=24h → second call within 24h returns `SKIPPED`.
5. **Missing config**: No `google_scholar` in config → ScholarConnector not instantiated, no error.
6. **PaperScout integration**: Sync Zotero → run PaperScout → corpus loaded from storage matches synced data.

---

## 12. Dashboard Integration

The Sync Service is a primary data source for the Dashboard's Profile & Configuration page (see [dashboard-impl.md](dashboard-impl.md)):

- **`sync_log`** table feeds the service status cards and sync history views.
- **`zotero_papers`** count drives the Zotero service summary ("342 papers synced").
- **`scholar_profiles`** data drives the Google Scholar service details (h-index, interests).
- **Manual sync** is triggerable from the Dashboard via `AgentDispatcher.dispatch_sync()`, which wraps `SyncOrchestrator.sync_all()` or `sync_one()` in a `BackgroundTask`.

### Service Status Assembly

The Dashboard Profile page calls `storage.get_last_sync(user_id, connector_name)` to build `ServiceStatus` objects for each configured service. See `dashboard-impl.md` §6.4 for the full assembly logic.

---

## 13. Migration / Compatibility

### 12.1 Backward Compatibility

- `get_zotero_corpus()` in `alithia/utils/zotero_client.py` remains unchanged. The `ZoteroConnector` wraps it internally.
- Existing `zotero_papers` schema is unchanged. The connector normalizes data before writing.
- PaperScout data_collection_node retains its cache-miss fallback: if sync hasn't run yet, it syncs inline.

### 12.2 New Dependencies

| Package | Purpose | Required? |
|---------|---------|-----------|
| `scholarly` | Google Scholar scraping (free fallback) | Optional |
| `google-search-results` | SerpAPI client | Optional (only if `serpapi_key` configured) |

Add to `pyproject.toml` under optional dependencies:

```toml
[project.optional-dependencies]
scholar = ["scholarly>=1.7", "google-search-results>=2.4"]
```

### 12.3 Schema Migration

Migration `003_sync_service.sql` adds:
- `scholar_profiles` table
- `scholar_publications` table
- `sync_log` table

No existing tables are modified. Run migration via:
```bash
# Supabase
supabase db push

# SQLite (auto-created on first connect)
# SQLiteStorage._create_tables() handles new tables
```

---

## 14. Future Extensions

### 13.1 Additional Connectors

The `SyncConnector` interface supports adding new services without modifying existing code:

| Service | Connector | Data Persisted |
|---------|-----------|----------------|
| GitHub | `GithubConnector` | Repos, stars, README content |
| X / Twitter | `XConnector` | Followed researchers, bookmarked papers |
| Semantic Scholar | `SemanticScholarConnector` | Citation graph, recommended papers |
| ORCID | `OrcidConnector` | Publication list, reviewer activity |

Each requires: a connection model in `connection.py`, a connector in `sync/connectors/`, storage tables, and storage backend methods.

### 13.2 Interest Model Derivation

Synced data (Zotero corpus + Scholar publications + Scholar interests) can feed an **Interest Model** that derives research interests automatically, replacing the manual `research_interests` list in config. This is deferred to a separate impl guide.

### 13.3 Bidirectional Sync

Current design is read-only (pull from external → write to storage). Future: push Gems or annotations back to Zotero. The `SyncConnector` interface can be extended with a `push()` method.

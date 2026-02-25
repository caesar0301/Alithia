# PaperScout Agent Implementation Architecture

> Implementation guide for the PaperScout agent in Alithia.
>
> **Module**: `alithia.paperscout`
> **Source**: Derived from RFC-0002 (PaperScout Agent Architecture)
> **Related RFCs**: RFC-0001 (Global Design Philosophy), RFC-0004 (Dashboard Architecture)
> **Related Impl Guides**: [sync-persistence-impl.md](sync-persistence-impl.md), [dashboard-impl.md](dashboard-impl.md)

---

## 1. Overview

PaperScout is Alithia's paper discovery agent. It automates the daily workflow of fetching ArXiv papers, scoring them against the user's research profile, persisting results to a Storage Backend, and delivering exactly-once email notifications. This guide describes the concrete module layout, types, interfaces, data flows, and background services needed to implement RFC-0002 in Python, targeting the existing `alithia` package with Supabase-first (SQLite fallback) persistence, LangGraph orchestration, and sentence-transformer-based relevance scoring.

### Key Design Changes from Current Implementation

| Area | Current State | Target State |
|------|--------------|--------------|
| Zotero corpus caching | Raw Zotero dicts → format mismatch with storage and reranker | Normalized `ZoteroPaper` model flows through all layers |
| Profile sync | Synchronous, inline in data_collection node | Async background service, decoupled from agent run |
| ArXiv paper persistence | Only emailed papers stored | All assessed papers saved with scores; emailed flag is a column |
| Email deduplication | Per-paper dedup only | Per-query-date notification record (exactly-once per Daily Query) |
| Gap Scanner | Not implemented | Background service scans `arxiv_processed_ranges` for missing slots |
| Storage init | Nodes call `load_config()` without path | Storage injected at agent construction via factory |

---

## 2. Architectural Position

### 2.1 System Context

```
                    ┌─────────────────────────┐
                    │    ResearcherProfile     │
                    │    (from config/DB)      │
                    └───────────┬─────────────┘
                                │
           ┌────────────────────┼────────────────────┐
           │                    │                    │
           ▼                    ▼                    ▼
    ┌──────────────┐  ┌──────────────────┐  ┌──────────────┐
    │  SyncService │  │   PaperScout     │  │  GapScanner  │
    │  (async bg)  │  │   Agent (main)   │  │  (cron/bg)   │
    └──────┬───────┘  └───────┬──────────┘  └──────┬───────┘
           │                  │                    │
           ▼                  ▼                    ▼
    ┌──────────────────────────────────────────────────────┐
    │               StorageBackend (Supabase / SQLite)     │
    └──────────────────────────────────────────────────────┘
           │                  │                    │
           ▼                  ▼                    ▼
      Zotero API         ArXiv API            SMTP Server
```

### 2.2 Dependency Graph

```
alithia.paperscout.agent        → state, nodes
alithia.paperscout.nodes        → state, models, reranker, email
                                  alithia.storage (via injection)
                                  alithia.utils.arxiv_paper_fetcher
                                  alithia.utils.arxiv_paper_utils
                                  alithia.utils.email_utils
alithia.paperscout.reranker     → models (ArxivPaper)
alithia.paperscout.email        → models (ScoredPaper, EmailContent)
alithia.paperscout.state        → models, alithia.researcher, alithia.constants
alithia.paperscout.models       → alithia.models.arxiv_paper
alithia.paperscout.gap_scanner  → alithia.storage, alithia.paperscout.agent
```

---

## 3. Module Structure

```
alithia/
├── paperscout/
│   ├── __init__.py
│   ├── agent.py              # PaperScoutAgent: LangGraph workflow definition
│   ├── state.py              # PaperScoutConfig, AgentState
│   ├── models.py             # ScoredPaper, EmailContent, NotificationRecord
│   ├── nodes.py              # LangGraph node functions (5 nodes)
│   ├── reranker.py           # PaperReranker (sentence-transformer + FlashRank)
│   ├── email.py              # Email HTML construction
│   └── gap_scanner.py        # GapScanner background service [NEW]
├── models/
│   ├── __init__.py
│   ├── arxiv_paper.py        # ArxivPaper Pydantic model
│   └── zotero_paper.py       # ZoteroPaper normalized model [NEW]
├── storage/
│   ├── base.py               # StorageBackend ABC (extended)
│   ├── factory.py            # get_storage_backend()
│   ├── sqlite.py             # SQLiteStorage
│   ├── supabase.py           # SupabaseStorage
│   └── migrations/
│       ├── 001_initial_schema.sql
│       └── 002_paperscout_v2.sql   # [NEW] query configs, notification records, assessed papers
├── researcher/
│   ├── profile.py            # ResearcherProfile
│   └── connection.py         # Connection models
├── sync/                     # [NEW] see sync-persistence-impl.md
│   └── ...
├── utils/
│   ├── arxiv_paper_fetcher.py
│   ├── arxiv_paper_utils.py
│   ├── zotero_client.py
│   ├── email_utils.py
│   └── llm_utils.py
├── config_loader.py
├── constants.py
└── run/
    └── __main__.py           # CLI entrypoint
```

---

## 4. Core Types

### 4.1 ZoteroPaper (NEW — `alithia/models/zotero_paper.py`)

Normalized model that bridges raw Zotero API response, storage schema, and reranker expectations.

```python
class ZoteroPaper(BaseModel):
    """Normalized representation of a Zotero library paper."""
    zotero_item_key: str
    title: str
    authors: List[str]
    abstract: str
    url: Optional[str] = None
    tags: List[str] = Field(default_factory=list)
    date_added: Optional[datetime] = None
    collection_paths: List[str] = Field(default_factory=list)

    @classmethod
    def from_zotero_api(cls, raw_item: Dict[str, Any], paths: List[str]) -> Optional["ZoteroPaper"]:
        """Convert raw Zotero API item to ZoteroPaper. Returns None if abstract is empty."""

    def to_storage_dict(self) -> Dict[str, Any]:
        """Serialize to flat dict matching storage schema columns."""

    @classmethod
    def from_storage_dict(cls, row: Dict[str, Any]) -> "ZoteroPaper":
        """Deserialize from storage row."""
```

**Rationale**: Eliminates the current format mismatch between raw Zotero `{"data": {"abstractNote": ...}}` dicts, storage rows `{"title", "abstract", ...}`, and the reranker which expects `paper.get("data", {}).get("abstractNote")`. All layers now work with a single canonical type.

### 4.2 ArxivPaper (existing — `alithia/models/arxiv_paper.py`)

No changes needed. Already a well-defined Pydantic model.

### 4.3 ScoredPaper (existing — `alithia/paperscout/models.py`)

```python
class ScoredPaper(BaseModel):
    paper: ArxivPaper
    score: float
    relevance_factors: Dict[str, float] = Field(default_factory=dict)
```

### 4.4 NotificationRecord (NEW — `alithia/paperscout/models.py`)

Tracks sent notifications per (user, query, date) triple for exactly-once semantics.

```python
class NotificationRecord(BaseModel):
    """Tracks a notification event for deduplication (PS-001)."""
    notification_id: Optional[str] = None   # UUID, assigned by storage
    user_id: str
    query_categories: str                   # ArXiv categories string
    notification_date: date                 # The day this notification covers
    paper_count: int
    status: Literal["pending", "sent", "failed"] = "pending"
    sent_at: Optional[datetime] = None
    error_message: Optional[str] = None
```

### 4.5 PaperScoutConfig (existing — `alithia/paperscout/state.py`)

Extend with optional storage injection and gap scanner window:

```python
class PaperScoutConfig(BaseModel):
    user_profile: ResearcherProfile
    query: str = DEFAULT_ARXIV_QUERY
    max_papers: int = ALITHIA_MAX_PAPERS
    max_papers_queried: int = ALITHIA_MAX_PAPERS_QUERIED
    send_empty: bool = DEFAULT_SEND_EMPTY
    ignore_patterns: List[str] = Field(default_factory=list)
    from_date: Optional[str] = None
    to_date: Optional[str] = None
    gap_scan_window_days: int = 7          # NEW: max days back for Gap Scanner
    debug: bool = False
```

### 4.6 AgentState (existing — `alithia/paperscout/state.py`)

Add `zotero_corpus` type annotation change:

```python
class AgentState(BaseModel):
    config: PaperScoutConfig
    discovered_papers: List[ArxivPaper] = Field(default_factory=list)
    zotero_corpus: List[ZoteroPaper] = Field(default_factory=list)  # CHANGED: was List[Dict]
    scored_papers: List[ScoredPaper] = Field(default_factory=list)
    email_content: Optional[EmailContent] = None
    current_step: str = "initializing"
    error_log: Annotated[List[str], add] = Field(default_factory=list)
    performance_metrics: Annotated[Dict[str, float], merge_dicts] = Field(default_factory=dict)
    debug_mode: bool = False
```

---

## 5. Key Interfaces

### 5.1 PaperScoutAgent (`alithia/paperscout/agent.py`)

```python
class PaperScoutAgent:
    """LangGraph-based PaperScout workflow."""

    def __init__(self, storage: StorageBackend, user_id: str):
        """Accept injected storage instead of calling load_config() internally."""

    def build_graph(self) -> StateGraph:
        """Build the 5-node LangGraph workflow."""

    async def run(self, config: PaperScoutConfig) -> AgentState:
        """Execute the full pipeline. Returns final state."""
```

### 5.2 StorageBackend Extensions (`alithia/storage/base.py`)

New abstract methods for PaperScout v2:

```python
class StorageBackend(ABC):
    # ... existing methods ...

    # --- NEW: Assessed papers ---
    @abstractmethod
    def save_assessed_papers(
        self, user_id: str, query_categories: str,
        papers: List[Dict[str, Any]], assessment_date: date
    ) -> None:
        """Persist all assessed papers with scores (not just emailed ones)."""

    @abstractmethod
    def get_assessed_papers(
        self, user_id: str, query_categories: str,
        from_date: date, to_date: date
    ) -> List[Dict[str, Any]]:
        """Retrieve assessed papers for a date range."""

    # --- NEW: Notification records ---
    @abstractmethod
    def save_notification_record(self, record: Dict[str, Any]) -> None:
        """Save a notification record. Enforces unique (user_id, query_categories, notification_date)."""

    @abstractmethod
    def get_notification_record(
        self, user_id: str, query_categories: str, notification_date: date
    ) -> Optional[Dict[str, Any]]:
        """Check if a notification was already sent for this (user, query, date)."""

    @abstractmethod
    def get_missing_notification_dates(
        self, user_id: str, query_categories: str, window_days: int = 7
    ) -> List[date]:
        """Return dates within window that have no successful notification."""
```

### 5.3 GapScanner (`alithia/paperscout/gap_scanner.py`)

```python
class GapScanner:
    """Detects and fills missing recommendation slots (RFC-0002 §5.9)."""

    def __init__(self, storage: StorageBackend, user_id: str):
        ...

    def scan(self, query_categories: str, window_days: int = 7) -> List[date]:
        """Return dates with missing notifications within the window."""

    async def fill_gaps(
        self, config: PaperScoutConfig, agent: PaperScoutAgent
    ) -> Dict[date, str]:
        """
        For each missing date, run the PaperScout agent with that date range.
        Returns {date: status} mapping.
        Respects PS-002 (bounded gap window).
        """
```

### 5.4 PaperReranker (`alithia/paperscout/reranker.py`)

Update to accept `List[ZoteroPaper]` instead of raw dicts:

```python
class PaperReranker:
    def __init__(self, papers: List[ArxivPaper], corpus: List[ZoteroPaper]):
        """Corpus is now typed as ZoteroPaper for uniform abstract access."""

    def rerank_sentence_transformer(
        self, model_name: str = "avsolatorio/GIST-small-Embedding-v0"
    ) -> List[ScoredPaper]:
        """
        Score papers against corpus using sentence embeddings.
        Access corpus abstracts via `paper.abstract` (not paper["data"]["abstractNote"]).
        """
```

---

## 6. Implementation Details

### 6.1 LangGraph Workflow (5 nodes)

The pipeline remains a linear 5-node graph, but with revised responsibilities:

```
profile_analysis → data_collection → relevance_assessment → content_generation → communication
```

#### Node 1: `profile_analysis_node`

- Validates `ResearcherProfile` connections (LLM, optionally Zotero, optionally Email).
- If Zotero is configured, triggers async profile sync check (does not block).
- If Email is not configured, sets `state.skip_email = True`.

#### Node 2: `data_collection_node`

1. **Load Zotero corpus from storage** (not from Zotero API directly — sync service handles that):
   ```python
   cached = storage.get_zotero_papers(user_id, max_age_hours=24)
   if cached:
       corpus = [ZoteroPaper.from_storage_dict(p) for p in cached]
   else:
       # Fallback: sync inline if no cache exists
       raw = get_zotero_corpus(zotero_id, zotero_key)
       corpus = [ZoteroPaper.from_zotero_api(item, item.get("paths", [])) for item in raw if ...]
       storage.cache_zotero_papers(user_id, [p.to_storage_dict() for p in corpus])
   ```
2. **Apply ignore patterns** using `filter_corpus()` on `ZoteroPaper.collection_paths`.
3. **Check processed ranges**: Skip if `(user_id, from_date, to_date, query_categories)` already processed.
4. **Fetch ArXiv papers**: `fetch_arxiv_papers(query, from_time, to_time, max_results)`.
5. **Filter already-emailed**: `storage.get_emailed_papers(user_id, arxiv_ids)`.
6. **Mark range processed**: `storage.mark_date_range_processed(...)`.

#### Node 3: `relevance_assessment_node`

1. Create `PaperReranker(discovered_papers, zotero_corpus)`.
2. Call `reranker.rerank_sentence_transformer()`.
3. Slice by `config.max_papers`.
4. Persist all assessed papers: `storage.save_assessed_papers(user_id, query, scored_papers, date)`.

#### Node 4: `content_generation_node`

1. For each `ScoredPaper`, run LLM enrichment:
   - `generate_tldr(paper, llm_client)` — TL;DR summary
   - `extract_affiliations(paper, llm_client)` — Author affiliations
   - `get_code_url(paper.arxiv_id)` — Papers with Code lookup
2. Build `EmailContent` via `construct_email_content(scored_papers)`.

#### Node 5: `communication_node`

1. **Check notification record**: `storage.get_notification_record(user_id, query, today)`.
2. If record exists with `status="sent"` → skip (exactly-once, PS-001).
3. If email not configured → skip, log warning.
4. Save `NotificationRecord(status="pending")`.
5. Call `send_email(...)`.
6. On success: update record to `status="sent"`, call `storage.save_emailed_papers(...)`.
7. On failure: update record to `status="failed"` with error message.

### 6.2 Zotero Corpus Format Normalization

**Problem**: Raw Zotero API returns `{"data": {"abstractNote": ..., "dateAdded": ...}}`. Storage expects `{"title", "abstract", ...}`. Reranker expects `paper.get("data", {}).get("abstractNote")`.

**Solution**: `ZoteroPaper` model (§4.1) is the single canonical type:
- `ZoteroPaper.from_zotero_api(raw_item)` → normalizes on ingest
- `ZoteroPaper.to_storage_dict()` → flat dict for storage write
- `ZoteroPaper.from_storage_dict(row)` → reconstruct from storage read
- Reranker uses `paper.abstract` attribute directly

### 6.3 Exactly-Once Email Semantics (PS-001)

The current implementation deduplicates at the paper level (`arxiv_papers_emailed`). The new design adds a higher-level guard:

1. **Notification Record** table keyed on `(user_id, query_categories, notification_date)`.
2. Before sending, check if a record with `status="sent"` exists for today's date.
3. Create a `pending` record before attempting send.
4. Update to `sent` on success, `failed` on error.
5. The Gap Scanner only re-runs dates where the record is missing or `status="failed"`.

This preserves the existing per-paper dedup while adding per-query-date idempotency.

### 6.4 Gap Scanner Algorithm

```
1. Compute expected_dates = [today - window_days .. yesterday]
2. For each date in expected_dates:
     record = storage.get_notification_record(user_id, query, date)
     if record is None or record.status == "failed":
         missing_dates.append(date)
3. For each missing_date (sorted ascending):
     config_copy = config.copy(from_date=missing_date, to_date=missing_date)
     await agent.run(config_copy)
4. Return {date: final_status} for each attempted fill
```

**Constraint (PS-002)**: `window_days` is configurable (default 7) and MUST be bounded to prevent unbounded backfill.

### 6.5 Storage Injection Pattern

The current implementation calls `get_or_create_storage()` inside nodes with `load_config()` (no config path). The new design injects storage at construction:

```python
# In CLI entrypoint (run/__main__.py)
config = load_config(args.config)
storage = get_storage_backend(config)
user_id = config.get("storage", {}).get("user_id", "default")

agent = PaperScoutAgent(storage=storage, user_id=user_id)
await agent.run(paperscout_config)
```

Nodes access storage via closure or state:

```python
def make_nodes(storage: StorageBackend, user_id: str):
    def data_collection_node(state: AgentState) -> Dict:
        # Use `storage` and `user_id` from closure
        ...
    return {
        "data_collection": data_collection_node,
        ...
    }
```

---

## 7. Error Handling

### 7.1 Error Categories

| Category | Examples | Strategy |
|----------|----------|----------|
| **External API** | ArXiv timeout, Zotero 429, SMTP failure | Retry with exponential backoff (max 3), then graceful skip |
| **Storage** | Supabase unreachable | Auto-fallback to SQLite (I-005) |
| **LLM** | Token limit, rate limit | Retry (max 2), skip enrichment on failure |
| **Data** | Empty abstract, malformed PDF URL | Log warning, exclude paper from scoring |
| **Config** | Missing credentials | Fail fast with descriptive error at `profile_analysis_node` |

### 7.2 Error Propagation

Errors are appended to `AgentState.error_log` (accumulated across nodes via `Annotated[List[str], add]`). Critical errors (storage failure, no papers found) short-circuit the pipeline by setting `current_step = "error"`.

### 7.3 Notification Failure Recovery

If `communication_node` fails to send email:
1. `NotificationRecord.status` is set to `"failed"` with `error_message`.
2. Gap Scanner picks up the failed date on next run.
3. Retry limit: Gap Scanner attempts each date at most 3 times (tracked via a retry counter in the notification record).

---

## 8. Configuration

### 8.1 Config Schema (relevant sections)

```json
{
  "researcher_profile": {
    "email": "user@example.com",
    "research_interests": ["NLP", "computer vision"],
    "llm": { "openai_api_key": "...", "openai_api_base": "...", "model_name": "gpt-4o-mini" },
    "zotero": { "zotero_id": "...", "zotero_key": "..." },
    "email_notification": { "smtp_server": "smtp.gmail.com", "smtp_port": 587, "sender": "...", "sender_password": "..." }
  },
  "paperscout_agent": {
    "query": "cs.AI+cs.CV+cs.LG+cs.CL",
    "max_papers": 25,
    "max_papers_queried": 500,
    "send_empty": false,
    "ignore_patterns": ["*/Archive/*"],
    "gap_scan_window_days": 7
  },
  "storage": {
    "backend": "supabase",
    "fallback_to_sqlite": true,
    "sqlite_path": "data/alithia.db",
    "user_id": "default_user"
  },
  "supabase": {
    "url": "https://xxx.supabase.co",
    "anon_key": "...",
    "service_role_key": "..."
  }
}
```

### 8.2 Environment Variable Mapping

| Config Path | Env Var |
|-------------|---------|
| `paperscout_agent.query` | `ALITHIA_ARXIV_QUERY` |
| `paperscout_agent.max_papers` | `ALITHIA_MAX_PAPERS` |
| `paperscout_agent.gap_scan_window_days` | `ALITHIA_GAP_SCAN_WINDOW_DAYS` |
| `storage.backend` | `ALITHIA_STORAGE_BACKEND` |
| `storage.user_id` | `ALITHIA_STORAGE_USER_ID` |
| `supabase.url` | `ALITHIA_SUPABASE_URL` |
| `supabase.service_role_key` | `ALITHIA_SUPABASE_SERVICE_ROLE_KEY` |

---

## 9. Database Schema Changes

### 9.1 New Table: `assessed_papers`

Stores every paper that was scored, not just those that were emailed.

```sql
CREATE TABLE IF NOT EXISTS assessed_papers (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id TEXT NOT NULL,
    arxiv_id TEXT NOT NULL,
    query_categories TEXT NOT NULL,
    assessment_date DATE NOT NULL,
    paper_title TEXT,
    paper_authors JSONB DEFAULT '[]'::jsonb,
    paper_summary TEXT,
    pdf_url TEXT,
    relevance_score REAL,
    relevance_factors JSONB DEFAULT '{}'::jsonb,
    code_url TEXT,
    tldr TEXT,
    affiliations JSONB DEFAULT '[]'::jsonb,
    emailed BOOLEAN DEFAULT FALSE,
    assessed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT assessed_papers_unique UNIQUE (user_id, arxiv_id, query_categories)
);

CREATE INDEX IF NOT EXISTS idx_assessed_papers_lookup
    ON assessed_papers(user_id, query_categories, assessment_date DESC);
```

### 9.2 New Table: `notification_records`

Tracks per-(user, query, date) notification events for exactly-once semantics.

```sql
CREATE TABLE IF NOT EXISTS notification_records (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id TEXT NOT NULL,
    query_categories TEXT NOT NULL,
    notification_date DATE NOT NULL,
    paper_count INTEGER DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'pending',  -- pending | sent | failed
    retry_count INTEGER DEFAULT 0,
    sent_at TIMESTAMPTZ,
    error_message TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT notification_records_unique
        UNIQUE (user_id, query_categories, notification_date)
);

CREATE INDEX IF NOT EXISTS idx_notification_records_lookup
    ON notification_records(user_id, query_categories, notification_date);
```

### 9.3 Existing Tables (unchanged)

- `zotero_papers` — used by sync service, schema unchanged
- `arxiv_processed_ranges` — used for gap detection, schema unchanged
- `arxiv_papers_emailed` — kept for backward compatibility; new code writes to `assessed_papers` with `emailed=True`

---

## 10. Testing Strategy

### 10.1 Unit Tests

| Test File | Scope |
|-----------|-------|
| `tests/unit/test_zotero_paper_model.py` | `ZoteroPaper` round-trip: API → model → storage → model |
| `tests/unit/test_notification_record.py` | `NotificationRecord` creation and validation |
| `tests/unit/test_reranker_typed.py` | `PaperReranker` with typed `ZoteroPaper` corpus |
| `tests/unit/test_gap_scanner.py` | Gap detection logic with mocked storage |
| `tests/unit/test_email_dedup.py` | Exactly-once semantics at notification record level |

### 10.2 Integration Tests

| Test File | Scope |
|-----------|-------|
| `tests/integration/test_paperscout_pipeline.py` | Full LangGraph pipeline with mocked APIs, real SQLite |
| `tests/integration/test_gap_scanner_fill.py` | Gap Scanner detects and fills missing dates end-to-end |
| `tests/integration/test_storage_backends.py` | Both Supabase and SQLite backends implement same interface |

### 10.3 Key Test Scenarios

1. **Exactly-once email**: Run agent twice for the same date → only one email sent.
2. **Zotero cache hit**: Pre-populate `zotero_papers` → agent skips Zotero API.
3. **Zotero cache miss**: Empty cache → agent syncs inline, caches result.
4. **Gap fill**: Delete notification record for yesterday → Gap Scanner re-runs and sends email.
5. **Storage fallback**: Supabase unreachable → SQLite fallback activates transparently.
6. **No email config**: Run without `email_notification` → pipeline completes, papers assessed and stored, no email sent.

---

## 11. Dashboard Integration

PaperScout is a primary data source for the Dashboard's Paper Trend page (see [dashboard-impl.md](dashboard-impl.md)):

- **`assessed_papers`** table feeds the calendar heatmap and paper detail views.
- **`notification_records`** table drives calendar day notification status indicators.
- **Gap fill** is triggerable from the Dashboard via `AgentDispatcher.dispatch_gap_fill()`, which wraps `GapScanner.fill_gaps()` in a `BackgroundTask`.
- **Paper discovery** is triggerable from the Dashboard via `AgentDispatcher.dispatch_paper_discovery()`, which wraps `PaperScoutAgent.run()` in a `BackgroundTask`.

### ProgressReporter Integration

PaperScout nodes accept an optional `ProgressReporter` to emit progress updates when run from the Dashboard:

```python
def data_collection_node(state: AgentState, reporter: Optional[ProgressReporter] = None) -> Dict:
    if reporter:
        reporter.report(0.1, "Loading Zotero corpus")
    # ...
    if reporter:
        reporter.report(0.3, f"Fetching ArXiv papers for {from_date}")
    # ...
```

When run from CLI, no reporter is passed and progress calls are no-ops.

---

## 12. Migration / Compatibility

### 11.1 Data Migration

- **`arxiv_papers_emailed`**: Existing rows are preserved. New pipeline writes to both `assessed_papers` (with `emailed=True`) and `arxiv_papers_emailed` (for backward compat) during a transition period.
- **`zotero_papers`**: Schema is unchanged. The sync service (see `sync-persistence-impl.md`) handles writing normalized data.

### 11.2 CLI Compatibility

The existing CLI remains backward-compatible:

```bash
# Existing usage (unchanged)
uv run python -m alithia.run paperscout_agent --config config.json

# New: explicit date range
uv run python -m alithia.run paperscout_agent --config config.json --from-date 2026-02-20 --to-date 2026-02-24

# New: run gap scanner
uv run python -m alithia.run paperscout_agent --config config.json --fill-gaps
```

### 11.3 Breaking Changes

- `AgentState.zotero_corpus` type changes from `List[Dict[str, Any]]` to `List[ZoteroPaper]`. Any code accessing `corpus[i]["data"]["abstractNote"]` must be updated to `corpus[i].abstract`.
- `PaperReranker.__init__` signature changes: `corpus` parameter type becomes `List[ZoteroPaper]`.
- Storage backend ABC gains new abstract methods; both `SQLiteStorage` and `SupabaseStorage` must implement them.

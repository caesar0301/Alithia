# RFC-004-storage-layer: SQLite Storage Architecture

**Status**: Draft
**Authors**: Claude
**Created**: 2026-06-06
**Last Updated**: 2026-06-06
**Depends on**: RFC-002-world-view
**Supersedes**: ---
**Stage**: Core
**Kind**: Architecture Design

---

## 1. Abstract

Alithia-agent uses SQLite for local-first persistence at `~/.alithia/`. This RFC defines the storage architecture, database schema, AsyncPersistStore implementation, and data access patterns for caching API results, tracking notifications, and enabling deduplication across subagent workflows.

---

## 2. Scope and Non-Goals

### 2.1 Scope

This RFC defines:

* Storage location and initialization
* SQLite database schema for PaperScout and PaperLens
* AsyncPersistStore protocol implementation
* Key-value storage patterns for subagent state
* Migration strategy for schema evolution
* Thread-safety and concurrency handling

### 2.2 Non-Goals

This RFC does **not** define:

* Multi-user storage or access control
* Cloud storage backends (Supabase, PostgreSQL)
* Encryption or security mechanisms
* Backup/restore procedures
* Complex query patterns beyond key-value access

---

## 3. Background & Motivation

Alithia-agent is local-first, requiring no cloud infrastructure. SQLite provides:

1. **Zero configuration**: No server setup, just a file
2. **Portability**: Works on any platform with Python
3. **Reliability**: ACID transactions, crash recovery
4. **Performance**: Fast for single-user read/write patterns
5. **Simplicity**: Standard library support via sqlite3

The storage layer serves two purposes:
- **Subagent state**: Key-value store via AsyncPersistStore protocol
- **Structured data**: Notification records, processed ranges, cached papers

---

## 4. Design Principles

1. **Local-first**: All data stored at `~/.alithia/`; no external dependencies
2. **Async interface**: AsyncPersistStore protocol for LangGraph compatibility
3. **User isolation**: All keys scoped by user_id
4. **Schema migrations**: Versioned SQL migrations for safe evolution
5. **Thread-safe**: Connection pooling or per-thread connections
6. **Graceful degradation**: Storage failures logged but don't crash workflows

---

## 5. Storage Architecture

### 5.1 Directory Structure

```
~/.alithia/
├── alithia.db           # SQLite database file
├── config.json          # User configuration (optional)
├── migrations/
│   ├── 001_initial_schema.sql
│   ├── 002_paperscout_v2.sql
│   └── 003_paperlens_schema.sql
└── logs/
    └── alithia.log      # Application logs
```

### 5.2 Component Structure

```
storage/
├── __init__.py          # Storage module entry point
├── base.py              # StorageBackend abstract base class
├── sqlite.py            # SQLiteStorage implementation
├── migrations.py        # Migration runner
└── schema.py            # Schema version tracking
```

### 5.3 AsyncPersistStore Protocol

```python
class AsyncPersistStore(Protocol):
    """Async key-value storage protocol for soothe subagents."""

    async def load(self, key: str) -> Any | None:
        """Load value by key. Returns None if not found."""

    async def save(self, key: str, value: Any) -> None:
        """Save value with key. Overwrites existing."""

    async def delete(self, key: str) -> None:
        """Delete value by key. No error if not found."""

    async def list_keys(self, prefix: str) -> list[str]:
        """List all keys matching prefix."""
```

---

## 6. Database Schema

### 6.1 Schema Overview

| Table | Purpose | Primary Key |
|-------|---------|-------------|
| `schema_version` | Migration tracking | `version` |
| `kv_store` | Generic key-value storage | `key` |
| `paperscout_notifications` | Notification records | `user_id, date` |
| `paperscout_emailed` | Deduplication list | `user_id, arxiv_id` |
| `paperscout_zotero_cache` | Zotero corpus cache | `user_id` |
| `paperlens_parsed_papers` | PDF parse cache | `user_id, file_hash` |
| `paperlens_query_history` | Query history | `id` |

### 6.2 Schema Definition

#### schema_version

```sql
CREATE TABLE schema_version (
    version INTEGER PRIMARY KEY,
    applied_at TEXT NOT NULL,
    description TEXT
);
```

#### kv_store (Generic Key-Value)

```sql
CREATE TABLE kv_store (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,  -- JSON-encoded value
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX idx_kv_store_prefix ON kv_store(key);
```

#### paperscout_notifications

```sql
CREATE TABLE paperscout_notifications (
    user_id TEXT NOT NULL,
    date TEXT NOT NULL,
    papers_count INTEGER NOT NULL,
    recipient TEXT NOT NULL,
    arxiv_ids TEXT NOT NULL,  -- JSON array
    sent_at TEXT NOT NULL,
    success INTEGER NOT NULL DEFAULT 1,
    error_message TEXT,
    PRIMARY KEY (user_id, date)
);
```

#### paperscout_emailed

```sql
CREATE TABLE paperscout_emailed (
    user_id TEXT NOT NULL,
    arxiv_id TEXT NOT NULL,
    emailed_at TEXT NOT NULL,
    PRIMARY KEY (user_id, arxiv_id)
);

CREATE INDEX idx_emailed_user ON paperscout_emailed(user_id);
```

#### paperscout_zotero_cache

```sql
CREATE TABLE paperscout_zotero_cache (
    user_id TEXT PRIMARY KEY,
    papers TEXT NOT NULL,  -- JSON array of ZoteroPaper
    timestamp TEXT NOT NULL,
    expires_at TEXT NOT NULL
);
```

#### paperlens_parsed_papers

```sql
CREATE TABLE paperlens_parsed_papers (
    user_id TEXT NOT NULL,
    file_hash TEXT NOT NULL,
    file_path TEXT NOT NULL,
    file_name TEXT NOT NULL,
    title TEXT,
    authors TEXT,  -- JSON array
    abstract TEXT,
    full_text TEXT,
    sections TEXT,  -- JSON object
    parsed_at TEXT NOT NULL,
    PRIMARY KEY (user_id, file_hash)
);

CREATE INDEX idx_parsed_user ON paperlens_parsed_papers(user_id);
```

#### paperlens_query_history

```sql
CREATE TABLE paperlens_query_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL,
    query TEXT NOT NULL,
    pdf_path TEXT NOT NULL,
    papers_count INTEGER,
    top_score REAL,
    queried_at TEXT NOT NULL
);

CREATE INDEX idx_query_user ON paperlens_query_history(user_id);
```

---

## 7. Key-Value Storage Patterns

### 7.1 Key Naming Convention

Keys MUST follow the pattern: `{subagent}:{category}:{user_id}:{suffix}`

| Pattern | Example | Purpose |
|---------|---------|---------|
| `paperscout:emailed:{user_id}` | `paperscout:emailed:chenxm` | List of emailed arxiv_ids |
| `paperscout:zotero:{user_id}` | `paperscout:zotero:chenxm` | Cached Zotero corpus |
| `paperscout:notifications:{user_id}:{date}` | `paperscout:notifications:chenxm:2026-06-06` | Daily notification record |
| `paperlens:parsed:{user_id}:{hash}` | `paperlens:parsed:chenxm:abc123` | Parsed paper cache |
| `paperlens:session:{user_id}:{session_id}` | `paperlens:session:chenxm:s1` | Session state |

### 7.2 Value Encoding

All values stored as JSON strings:

```python
# Save
await store.save("paperscout:emailed:chenxm", ["2401.12345", "2401.12346"])

# Load
emailed = await store.load("paperscout:emailed:chenxm")
# Returns: ["2401.12345", "2401.12346"] or None
```

### 7.3 TTL Handling

Some keys have TTL (time-to-live):

| Key Category | TTL | Handling |
|--------------|-----|----------|
| `zotero` cache | 24 hours | Check `expires_at` before use |
| `emailed` list | `emailed_papers_retention_days` (config) | Prune on access |
| `notifications` | Permanent | No TTL |
| `parsed` papers | Permanent | No TTL |

---

## 8. Migration Strategy

### 8.1 Migration Files

Migrations are numbered SQL files in `~/.alithia/migrations/`:

```
001_initial_schema.sql
002_paperscout_v2.sql
003_paperlens_schema.sql
```

### 8.2 Migration Runner

```python
class MigrationRunner:
    def __init__(self, db_path: Path, migrations_dir: Path)

    def get_current_version(self) -> int
        # Read from schema_version table

    def get_pending_migrations(self) -> list[Path]
        # Find migrations > current_version

    async def run_migrations(self) -> None
        # Execute pending migrations in order
        # Update schema_version after each
```

### 8.3 Migration Execution Rules

| Rule | Description |
|------|-------------|
| Sequential | Migrations MUST run in order (001, 002, 003...) |
| No rollback | Once applied, migration cannot be undone |
| Version tracking | Each migration records version + timestamp |
| Idempotent init | If db doesn't exist, create with all migrations |

---

## 9. Thread Safety

### 9.1 Connection Strategy

SQLite has limitations with concurrent writes. Use per-thread connections:

```python
class SQLiteStorage:
    _connections: dict[int, sqlite3.Connection] = {}  # thread_id → connection

    def _get_connection(self) -> sqlite3.Connection:
        thread_id = threading.get_ident()
        if thread_id not in self._connections:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            self._connections[thread_id] = conn
        return self._connections[thread_id]
```

### 9.2 Write Serialization

All writes use explicit transaction:

```python
async def save(self, key: str, value: Any) -> None:
    conn = self._get_connection()
    cursor = conn.cursor()
    cursor.execute("BEGIN IMMEDIATE")  # Acquire write lock
    try:
        # ... insert/update
        cursor.execute("COMMIT")
    except:
        cursor.execute("ROLLBACK")
        raise
```

### 9.3 Read Consistency

Reads use separate connections; no blocking on writes:

```python
async def load(self, key: str) -> Any | None:
    conn = self._get_connection()
    cursor = conn.cursor()
    # SQLite reads don't block other reads
    cursor.execute("SELECT value FROM kv_store WHERE key = ?", (key,))
    row = cursor.fetchone()
    return json.loads(row["value"]) if row else None
```

---

## 10. Error Handling

### 10.1 Error Categories

| Category | Example | Handling |
|----------|---------|----------|
| **Database locked** | Concurrent write attempt | Retry with backoff (3 retries, 100ms delay) |
| **Disk full** | No space to write | Log error, return without saving |
| **Corrupt database** | Malformed SQLite file | Log error, recreate database |
| **Migration failure** | SQL syntax error | Log error, halt startup |

### 10.2 Graceful Degradation

| Scenario | Behavior |
|----------|----------|
| Storage unavailable | Subagents MUST continue without persistence |
| Cache miss | Fetch from API (no cached data available) |
| Write failure | Log error, continue workflow |

---

## 11. Integration with Subagents

### 11.1 PaperScout Storage Usage

| Operation | Key | Value Type |
|-----------|-----|------------|
| Deduplication check | `paperscout:emailed:{user_id}` | `list[str]` (arxiv_ids) |
| Mark papers emailed | `paperscout:emailed:{user_id}` | Append arxiv_id |
| Zotero cache read | `paperscout:zotero:{user_id}` | `{papers, timestamp}` |
| Zotero cache write | `paperscout:zotero:{user_id}` | `{papers, timestamp}` |
| Notification record | `paperscout:notifications:{user_id}:{date}` | `{date, papers_count, ...}` |

### 11.2 PaperLens Storage Usage

| Operation | Key | Value Type |
|-----------|-----|------------|
| Parse cache check | `paperlens:parsed:{user_id}:{hash}` | `{title, authors, ...}` |
| Parse cache write | `paperlens:parsed:{user_id}:{hash}` | `{title, authors, full_text, ...}` |
| Query history log | `paperlens:query_history` (table) | `{user_id, query, ...}` |

### 11.3 Storage Injection

Subagents receive storage via kwargs or config:

```python
@subagent(name="paperscout", ...)
async def create_paperscout(model, config, context, **kwargs):
    store = kwargs.get("store")
    if not store:
        store = config.services.get("persistence")
    if not store:
        raise ValueError("PaperScout requires AsyncPersistStore")
```

---

## 12. Initialization

### 12.1 First Run Setup

```python
def initialize_storage() -> SQLiteStorage:
    alithia_dir = Path.home() / ".alithia"
    alithia_dir.mkdir(exist_ok=True)

    db_path = alithia_dir / "alithia.db"
    migrations_dir = alithia_dir / "migrations"

    storage = SQLiteStorage(db_path)

    # Run migrations if needed
    runner = MigrationRunner(db_path, migrations_dir)
    await runner.run_migrations()

    return storage
```

### 12.2 Configuration Integration

Storage config in `~/.alithia/config.json`:

```json
{
  "storage": {
    "backend": "sqlite",
    "path": "~/.alithia/alithia.db",
    "user_id": "user@example.com"
  }
}
```

---

## 13. Dependencies

### 13.1 Required Dependencies

| Package | Purpose | Source |
|---------|---------|--------|
| `sqlite3` | Database driver | Python stdlib |
| `json` | Value serialization | Python stdlib |
| `threading` | Connection pooling | Python stdlib |
| `aiosqlite` | Async wrapper (optional) | pip |

### 13.2 Framework Integration

| Integration | Mechanism |
|-------------|-----------|
| AsyncPersistStore | Protocol from soothe_sdk.protocols |
| Subagent injection | Passed via kwargs or config.services |

---

## 14. Relationship to Other RFCs

| RFC | Relationship |
|-----|--------------|
| RFC-002-world-view | Implements Storage abstraction and invariants |
| RFC-003-paperscout-workflow | Defines PaperScout storage usage patterns |
| RFC-001-paperlens-workflow | Defines PaperLens storage usage patterns |

---

## 15. Open Questions

None. SQLite is the chosen backend for local-first operation.

---

## 16. Conclusion

Alithia-agent uses SQLite for local-first persistence at `~/.alithia/`. The storage layer:

1. **Generic key-value**: `kv_store` table for AsyncPersistStore protocol
2. **Structured tables**: Notification records, deduplication, parse cache
3. **User isolation**: All keys scoped by user_id
4. **Schema migrations**: Versioned SQL files for safe evolution
5. **Thread-safe**: Per-thread connections with write serialization

> **SQLite provides zero-config, local-first persistence with async interface compatibility for LangGraph workflows — all data stays on the user's machine.**
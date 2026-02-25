# Alithia Dashboard Implementation Architecture

> Implementation guide for the Alithia Dashboard web interface.
>
> **Module**: `alithia.dashboard`
> **Source**: Derived from RFC-0004 (Alithia Dashboard Architecture)
> **Related RFCs**: RFC-0001 (Global Design), RFC-0002 (PaperScout), RFC-0003 (PaperLens)
> **Related Impl Guides**: [paperscout-impl.md](paperscout-impl.md), [sync-persistence-impl.md](sync-persistence-impl.md)

---

## 1. Overview

The Alithia Dashboard is a full-stack web application that provides a visual interface to all Alithia capabilities. It is implemented as a Python backend (FastAPI) serving a modern frontend (React/Next.js or similar), reading from and writing to the shared Storage Backend, and dispatching operations to PaperScout, PaperLens, and the Sync Service.

This guide covers the backend API, frontend page structure, Background Task system, real-time communication, and integration points with existing agents.

### Key Capabilities

| Feature | Description | Source Agent |
|---------|-------------|-------------|
| **Overview / Tasks** | Background task monitoring, progress, logs | Task Manager (new) |
| **Profile & Config** | Connected services status, sync summaries, config editing | Sync Service, Storage |
| **Paper Trend** | Calendar heatmap of daily paper recommendations | PaperScout (assessed_papers, notification_records) |
| **AI Agent** | Contextual chat and deep research from any page | PaperLens, PaperScout |

---

## 2. Architectural Position

### 2.1 System Context

```
Browser (React SPA)
        │
        │  HTTP / WebSocket
        ▼
┌───────────────────────────────────────────────────────┐
│              Dashboard Backend (FastAPI)               │
│                                                       │
│  ┌─────────┐  ┌─────────┐  ┌───────────┐  ┌───────┐ │
│  │  Task   │  │  Data   │  │  Agent    │  │  WS   │ │
│  │  API    │  │  API    │  │ Dispatch  │  │ Hub   │ │
│  │         │  │         │  │  API      │  │       │ │
│  └────┬────┘  └────┬────┘  └─────┬─────┘  └───┬───┘ │
│       │            │             │             │     │
│       └────────────┼─────────────┼─────────────┘     │
│                    │             │                    │
│                    ▼             ▼                    │
│         ┌──────────────┐  ┌──────────────┐           │
│         │   Storage    │  │   Agent      │           │
│         │   Backend    │  │  Instances   │           │
│         └──────────────┘  └──────────────┘           │
└───────────────────────────────────────────────────────┘
```

### 2.2 Dependency Graph

```
alithia.dashboard.app           → FastAPI, routers
alithia.dashboard.routers.tasks → task_manager, storage
alithia.dashboard.routers.data  → storage (read: assessed_papers, notifications, sync_log, profiles)
alithia.dashboard.routers.agent → agent_dispatcher, task_manager
alithia.dashboard.routers.ws    → websocket hub, task_manager events
alithia.dashboard.task_manager  → storage, asyncio, agent instances
alithia.dashboard.agent_dispatch→ paperscout.agent, paperlens.engine, sync.orchestrator
```

---

## 3. Module Structure

```
alithia/
├── dashboard/                        # [NEW] Dashboard package
│   ├── __init__.py
│   ├── app.py                        # FastAPI application factory
│   ├── config.py                     # Dashboard-specific config (port, CORS, etc.)
│   ├── task_manager.py               # Background Task abstraction
│   ├── agent_dispatcher.py           # Routes UI actions → agent invocations
│   ├── ws_hub.py                     # WebSocket connection manager
│   ├── routers/
│   │   ├── __init__.py
│   │   ├── tasks.py                  # POST /tasks, GET /tasks, GET /tasks/{id}
│   │   ├── data.py                   # GET /papers/calendar, GET /papers/{date}, GET /profile, etc.
│   │   ├── agent.py                  # POST /agent/chat, POST /agent/dispatch
│   │   ├── config.py                 # GET/PUT /config/profile, GET/PUT /config/services
│   │   └── ws.py                     # WebSocket endpoint /ws
│   ├── models/
│   │   ├── __init__.py
│   │   ├── task.py                   # BackgroundTask, LogEntry, TaskStatus
│   │   ├── calendar.py               # CalendarDay, CalendarMonth
│   │   ├── service_status.py         # ServiceStatus
│   │   └── agent_context.py          # AIAgentContext, ChatMessage
│   └── static/                       # Built frontend assets (or separate repo)
│       └── ...
├── storage/
│   ├── base.py                       # StorageBackend (extended with task methods)
│   └── migrations/
│       └── 004_dashboard.sql         # [NEW] background_tasks table
├── paperscout/                       # Existing — invoked by agent_dispatcher
├── paperlens/                        # Existing — invoked by agent_dispatcher
├── sync/                             # Existing — invoked by agent_dispatcher
└── run/
    └── __main__.py                   # Add `dashboard` subcommand
```

### 3.1 Frontend Structure (if co-located)

```
frontend/                             # Separate package or subdirectory
├── package.json
├── src/
│   ├── App.tsx
│   ├── pages/
│   │   ├── Overview.tsx              # Task list, system health
│   │   ├── Profile.tsx               # Profile & connected services
│   │   ├── PaperTrend.tsx            # Calendar view
│   │   └── Layout.tsx                # Nav, AI Agent Button
│   ├── components/
│   │   ├── TaskCard.tsx              # Single task display
│   │   ├── TaskLog.tsx               # Expandable log viewer
│   │   ├── CalendarHeatmap.tsx       # Month calendar with paper counts
│   │   ├── PaperList.tsx             # Paper list for selected day
│   │   ├── PaperCard.tsx             # Single paper display (title, score, TLDR)
│   │   ├── ServiceCard.tsx           # Connected service status card
│   │   ├── AIAgentPanel.tsx          # Chat panel (slide-out or modal)
│   │   └── AIAgentButton.tsx         # Floating action button
│   ├── hooks/
│   │   ├── useWebSocket.ts           # WebSocket connection with reconnect
│   │   ├── useTasks.ts               # Task polling/subscription
│   │   └── useCalendar.ts            # Calendar data fetching
│   └── api/
│       └── client.ts                 # API client (fetch wrapper)
└── public/
    └── index.html
```

---

## 4. Core Types

### 4.1 BackgroundTask (`alithia/dashboard/models/task.py`)

```python
class TaskStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

class TaskType(str, Enum):
    PAPER_DISCOVERY = "paper_discovery"
    GAP_FILL = "gap_fill"
    SYNC_ZOTERO = "sync_zotero"
    SYNC_SCHOLAR = "sync_scholar"
    PAPER_ANALYSIS = "paper_analysis"
    DEEP_RESEARCH = "deep_research"

@dataclass
class LogEntry:
    timestamp: datetime
    level: str          # debug | info | warning | error
    message: str
    metadata: Dict[str, Any] = field(default_factory=dict)

class BackgroundTask(BaseModel):
    task_id: str = Field(default_factory=lambda: str(uuid4()))
    user_id: str
    task_type: TaskType
    status: TaskStatus = TaskStatus.QUEUED
    progress: float = 0.0                     # 0.0 - 1.0
    current_step: str = ""
    parameters: Dict[str, Any] = Field(default_factory=dict)
    result: Optional[Dict[str, Any]] = None
    logs: List[LogEntry] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None
```

### 4.2 CalendarDay (`alithia/dashboard/models/calendar.py`)

```python
class CalendarDay(BaseModel):
    date: date
    total_papers: int = 0
    relevant_papers: int = 0            # score >= threshold
    top_score: float = 0.0
    avg_score: float = 0.0
    notification_status: str = "missing" # sent | failed | missing | not_configured
    categories: List[str] = Field(default_factory=list)

class CalendarMonth(BaseModel):
    year: int
    month: int
    days: List[CalendarDay]
    total_papers: int
    total_notifications_sent: int
```

### 4.3 ServiceStatus (`alithia/dashboard/models/service_status.py`)

```python
class ServiceStatus(BaseModel):
    service_name: str                    # zotero | google_scholar | email | llm
    status: str                          # connected | disconnected | error | not_configured
    last_sync_at: Optional[datetime] = None
    sync_summary: Optional[str] = None   # "342 papers synced"
    details: Dict[str, Any] = Field(default_factory=dict)
    error_message: Optional[str] = None
```

### 4.4 AIAgentContext (`alithia/dashboard/models/agent_context.py`)

```python
class ChatMessage(BaseModel):
    role: str                            # user | assistant | system
    content: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)

class AIAgentContext(BaseModel):
    source_page: str                     # overview | profile | paper_trend
    selected_papers: List[str] = Field(default_factory=list)  # arxiv_ids
    selected_date_range: Optional[Tuple[date, date]] = None
    selected_service: Optional[str] = None
    user_query: str
    conversation_history: List[ChatMessage] = Field(default_factory=list)
```

---

## 5. Key Interfaces

### 5.1 REST API Endpoints

#### Tasks API (`/api/tasks`)

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/tasks` | Create and enqueue a new background task |
| `GET` | `/api/tasks` | List tasks (filterable by status, type) |
| `GET` | `/api/tasks/{task_id}` | Get task details with logs |
| `DELETE` | `/api/tasks/{task_id}` | Cancel a running/queued task |

#### Data API (`/api/data`)

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/data/calendar/{year}/{month}` | Get CalendarMonth with day summaries |
| `GET` | `/api/data/papers/{date}` | Get full list of assessed papers for a date |
| `GET` | `/api/data/papers/{date}/{arxiv_id}` | Get single paper details |
| `GET` | `/api/data/profile` | Get current ResearcherProfile |
| `GET` | `/api/data/services` | Get all ServiceStatus entries |
| `GET` | `/api/data/services/{name}/sync-history` | Get sync_log entries for a service |

#### Config API (`/api/config`)

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/config/profile` | Get profile config (editable fields) |
| `PUT` | `/api/config/profile` | Update profile fields |
| `GET` | `/api/config/services/{name}` | Get service credentials (masked) |
| `PUT` | `/api/config/services/{name}` | Update service credentials |

#### Agent API (`/api/agent`)

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/agent/chat` | Send message to AI Agent, receive response |
| `POST` | `/api/agent/dispatch` | Dispatch an agent action (returns task_id) |

#### WebSocket (`/ws`)

| Event Direction | Event | Payload |
|-----------------|-------|---------|
| Server → Client | `task.progress` | `{task_id, progress, current_step}` |
| Server → Client | `task.completed` | `{task_id, result}` |
| Server → Client | `task.failed` | `{task_id, error_message}` |
| Server → Client | `task.log` | `{task_id, log_entry}` |
| Server → Client | `agent.token` | `{session_id, token}` (streaming AI response) |
| Client → Server | `subscribe` | `{task_ids: [...]}` |

### 5.2 TaskManager (`alithia/dashboard/task_manager.py`)

```python
class TaskManager:
    """Manages background task lifecycle and execution."""

    MAX_CONCURRENT_TASKS = 3

    def __init__(self, storage: StorageBackend, ws_hub: WebSocketHub):
        self._storage = storage
        self._ws_hub = ws_hub
        self._running: Dict[str, asyncio.Task] = {}

    async def create_task(self, task: BackgroundTask) -> BackgroundTask:
        """Persist task and enqueue for execution."""

    async def execute_task(self, task: BackgroundTask, coroutine: Coroutine) -> None:
        """Run coroutine, update progress, emit events."""

    def update_progress(self, task_id: str, progress: float, step: str) -> None:
        """Update task progress and notify subscribers."""

    def add_log(self, task_id: str, level: str, message: str) -> None:
        """Append log entry and emit via WebSocket."""

    async def cancel_task(self, task_id: str) -> None:
        """Cancel a running or queued task."""

    async def get_tasks(self, user_id: str, status: Optional[str] = None) -> List[BackgroundTask]:
        """Retrieve tasks from storage."""
```

### 5.3 AgentDispatcher (`alithia/dashboard/agent_dispatcher.py`)

```python
class AgentDispatcher:
    """Routes Dashboard actions to agent invocations wrapped in BackgroundTasks."""

    def __init__(
        self, storage: StorageBackend, user_id: str,
        task_manager: TaskManager, profile: ResearcherProfile
    ):
        self._storage = storage
        self._user_id = user_id
        self._task_manager = task_manager
        self._profile = profile

    async def dispatch_paper_discovery(
        self, query: str, from_date: date, to_date: date
    ) -> BackgroundTask:
        """Create task → run PaperScoutAgent.run()."""

    async def dispatch_gap_fill(self, query: str, window_days: int = 7) -> BackgroundTask:
        """Create task → run GapScanner.fill_gaps()."""

    async def dispatch_sync(self, connector_name: Optional[str] = None) -> BackgroundTask:
        """Create task → run SyncOrchestrator.sync_all() or sync_one()."""

    async def dispatch_paper_analysis(self, arxiv_id: str, query: str) -> BackgroundTask:
        """Create task → run PaperLens on a specific paper with a query."""

    async def dispatch_deep_research(self, topic: str, paper_ids: List[str]) -> BackgroundTask:
        """Create task → run PaperLens Topic Explorer."""

    async def chat(self, context: AIAgentContext) -> str:
        """Direct chat: route to LLM with paper/profile context. Returns response text."""
```

### 5.4 WebSocketHub (`alithia/dashboard/ws_hub.py`)

```python
class WebSocketHub:
    """Manages WebSocket connections and event broadcasting."""

    def __init__(self):
        self._connections: Dict[str, WebSocket] = {}
        self._subscriptions: Dict[str, Set[str]] = {}  # task_id → {conn_ids}

    async def connect(self, websocket: WebSocket, conn_id: str) -> None:
        """Accept and register connection."""

    async def disconnect(self, conn_id: str) -> None:
        """Clean up connection and subscriptions."""

    async def subscribe(self, conn_id: str, task_ids: List[str]) -> None:
        """Subscribe connection to task events."""

    async def broadcast(self, event: str, payload: Dict[str, Any], task_id: Optional[str] = None) -> None:
        """Send event to all subscribers (or all connections if no task_id)."""
```

---

## 6. Implementation Details

### 6.1 Background Task Execution Model

Tasks run as `asyncio.Task` instances managed by `TaskManager`. The pattern:

```python
async def _run_paper_discovery(task: BackgroundTask, agent: PaperScoutAgent, config: PaperScoutConfig):
    task_manager.update_progress(task.task_id, 0.1, "Loading profile")
    # ... agent.run() with progress callbacks ...
    task_manager.update_progress(task.task_id, 0.5, "Assessing relevance")
    # ...
    task_manager.update_progress(task.task_id, 1.0, "Complete")
```

Progress callbacks are injected into agent execution via a `ProgressReporter` protocol:

```python
class ProgressReporter(Protocol):
    def report(self, progress: float, step: str) -> None: ...
    def log(self, level: str, message: str) -> None: ...
```

Agents accept an optional `reporter` parameter. When running from CLI, the reporter is a no-op. When running from Dashboard, it bridges to `TaskManager.update_progress()`.

### 6.2 Paper Trend Calendar Data Assembly

The `/api/data/calendar/{year}/{month}` endpoint queries storage:

```python
async def get_calendar_month(year: int, month: int, user_id: str) -> CalendarMonth:
    first_day = date(year, month, 1)
    last_day = ...  # last day of month

    assessed = storage.get_assessed_papers(user_id, query, first_day, last_day)
    notifications = storage.get_notification_records_range(user_id, query, first_day, last_day)

    days = []
    for d in date_range(first_day, last_day):
        day_papers = [p for p in assessed if p["assessment_date"] == d]
        notif = next((n for n in notifications if n["notification_date"] == d), None)
        days.append(CalendarDay(
            date=d,
            total_papers=len(day_papers),
            relevant_papers=len([p for p in day_papers if p["relevance_score"] >= 6.0]),
            top_score=max((p["relevance_score"] for p in day_papers), default=0.0),
            avg_score=mean([p["relevance_score"] for p in day_papers]) if day_papers else 0.0,
            notification_status=notif["status"] if notif else "missing",
            categories=list(set(p.get("query_categories", "") for p in day_papers)),
        ))
    return CalendarMonth(year=year, month=month, days=days, ...)
```

### 6.3 Paper Day Detail View

When a user clicks a calendar day, `/api/data/papers/{date}` returns the full paper list:

```python
async def get_papers_for_date(date_str: str, user_id: str) -> List[Dict]:
    papers = storage.get_assessed_papers(user_id, query, date_val, date_val)
    return sorted(papers, key=lambda p: p["relevance_score"], reverse=True)
```

Each paper includes: `arxiv_id`, `title`, `authors`, `summary`, `relevance_score`, `tldr`, `pdf_url`, `code_url`, `affiliations` — the same content as the email notification.

### 6.4 Connected Service Status Assembly

The Profile page assembles `ServiceStatus` from multiple sources:

```python
async def get_service_statuses(user_id: str, profile: ResearcherProfile) -> List[ServiceStatus]:
    statuses = []

    # Zotero
    if profile.zotero:
        last_sync = storage.get_last_sync(user_id, "zotero")
        cached = storage.get_zotero_papers(user_id)
        statuses.append(ServiceStatus(
            service_name="zotero",
            status="connected" if last_sync else "disconnected",
            last_sync_at=last_sync["completed_at"] if last_sync else None,
            sync_summary=f"{len(cached)} papers synced" if cached else None,
            details={"collection_count": ..., "paper_count": len(cached) if cached else 0},
        ))

    # Google Scholar
    if profile.google_scholar:
        scholar = storage.get_scholar_profile(user_id)
        last_sync = storage.get_last_sync(user_id, "google_scholar")
        statuses.append(ServiceStatus(
            service_name="google_scholar",
            status="connected" if scholar else "disconnected",
            last_sync_at=last_sync["completed_at"] if last_sync else None,
            sync_summary=f"h-index: {scholar['h_index']}" if scholar else None,
            details=scholar or {},
        ))

    # ... email, llm status checks ...
    return statuses
```

### 6.5 AI Agent Chat Integration

The AI Agent Panel sends requests to `/api/agent/chat` with `AIAgentContext`:

```python
async def agent_chat(context: AIAgentContext) -> str:
    llm_client = get_llm_client(profile.llm)

    system_prompt = build_system_prompt(context)

    if context.selected_papers:
        paper_context = []
        for arxiv_id in context.selected_papers:
            paper = storage.get_assessed_paper(user_id, arxiv_id)
            if paper:
                paper_context.append(format_paper_for_context(paper))
        system_prompt += "\n\nSelected papers:\n" + "\n".join(paper_context)

    messages = [{"role": "system", "content": system_prompt}]
    messages += [{"role": m.role, "content": m.content} for m in context.conversation_history]
    messages.append({"role": "user", "content": context.user_query})

    response = await llm_client.chat(messages)
    return response.content
```

For deep research or paper analysis, the chat endpoint detects intent and dispatches to `AgentDispatcher`, returning a `task_id` that the frontend can track.

### 6.6 Real-Time Updates

WebSocket flow:

1. Frontend connects to `/ws` on page load.
2. Frontend sends `subscribe` with task IDs of interest.
3. `TaskManager` calls `ws_hub.broadcast()` on every progress update.
4. Frontend updates UI reactively on received events.

Fallback: If WebSocket fails, frontend polls `GET /api/tasks` every 5 seconds.

---

## 7. Error Handling

### 7.1 API Error Responses

All API errors use a consistent format:

```python
class APIError(BaseModel):
    error: str
    detail: Optional[str] = None
    status_code: int
```

HTTP status codes:
- `400` — Invalid parameters
- `404` — Resource not found
- `409` — Task conflict (e.g., duplicate task)
- `500` — Internal server error
- `503` — Storage backend unavailable

### 7.2 Task Failure Handling

When a task fails:
1. `TaskManager` catches the exception.
2. Sets `task.status = FAILED`, `task.error_message = str(e)`.
3. Persists final state to storage.
4. Emits `task.failed` event via WebSocket.
5. Frontend shows error in task card with expandable stack trace.

### 7.3 WebSocket Resilience

- Server sends `ping` every 30 seconds; expects `pong` within 10 seconds.
- Client auto-reconnects with exponential backoff (1s, 2s, 4s, max 30s).
- On reconnect, client re-subscribes to active task IDs.
- Missed events during disconnect are recovered via `GET /api/tasks`.

---

## 8. Configuration

### 8.1 Dashboard Config

```json
{
  "dashboard": {
    "host": "0.0.0.0",
    "port": 8080,
    "cors_origins": ["http://localhost:3000"],
    "max_concurrent_tasks": 3,
    "task_timeout_seconds": 600,
    "ws_ping_interval": 30,
    "static_dir": "frontend/dist"
  }
}
```

### 8.2 Environment Variable Mapping

| Config Path | Env Var |
|-------------|---------|
| `dashboard.host` | `ALITHIA_DASHBOARD_HOST` |
| `dashboard.port` | `ALITHIA_DASHBOARD_PORT` |
| `dashboard.cors_origins` | `ALITHIA_DASHBOARD_CORS` |
| `dashboard.max_concurrent_tasks` | `ALITHIA_DASHBOARD_MAX_TASKS` |

---

## 9. Database Schema Changes

### 9.1 New Table: `background_tasks`

```sql
CREATE TABLE IF NOT EXISTS background_tasks (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id TEXT NOT NULL,
    task_type TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'queued',
    progress REAL DEFAULT 0.0,
    current_step TEXT DEFAULT '',
    parameters JSONB DEFAULT '{}'::jsonb,
    result JSONB,
    logs JSONB DEFAULT '[]'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    error_message TEXT,

    CONSTRAINT background_tasks_status_check
        CHECK (status IN ('queued', 'running', 'completed', 'failed', 'cancelled'))
);

CREATE INDEX IF NOT EXISTS idx_background_tasks_user_status
    ON background_tasks(user_id, status, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_background_tasks_active
    ON background_tasks(status) WHERE status IN ('queued', 'running');
```

### 9.2 StorageBackend Extensions

```python
class StorageBackend(ABC):
    # ... existing methods ...

    # --- NEW: Background tasks ---
    @abstractmethod
    def save_task(self, task: Dict[str, Any]) -> None:
        """Upsert a background task record."""

    @abstractmethod
    def get_task(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Get task by ID."""

    @abstractmethod
    def get_tasks(
        self, user_id: str, status: Optional[str] = None,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """List tasks for a user, optionally filtered by status."""

    @abstractmethod
    def get_notification_records_range(
        self, user_id: str, query_categories: str,
        from_date: date, to_date: date
    ) -> List[Dict[str, Any]]:
        """Get notification records for a date range (calendar view)."""
```

---

## 10. Testing Strategy

### 10.1 Backend Unit Tests

| Test File | Scope |
|-----------|-------|
| `tests/unit/test_task_manager.py` | Task lifecycle, concurrency limits, cancellation |
| `tests/unit/test_agent_dispatcher.py` | Dispatch routing, parameter mapping |
| `tests/unit/test_calendar_assembly.py` | CalendarMonth aggregation from storage data |
| `tests/unit/test_service_status.py` | Service status assembly from sync_log + profile |
| `tests/unit/test_ws_hub.py` | WebSocket subscribe, broadcast, disconnect |

### 10.2 Backend Integration Tests

| Test File | Scope |
|-----------|-------|
| `tests/integration/test_dashboard_api.py` | Full API round-trips (FastAPI TestClient) |
| `tests/integration/test_task_execution.py` | Task creation → agent execution → completion |
| `tests/integration/test_calendar_e2e.py` | Seed assessed_papers → verify calendar endpoint |

### 10.3 Frontend Tests

| Test File | Scope |
|-----------|-------|
| `CalendarHeatmap.test.tsx` | Renders correct day counts and colors |
| `PaperList.test.tsx` | Renders paper cards with all fields |
| `TaskCard.test.tsx` | Shows progress bar, status badge |
| `AIAgentPanel.test.tsx` | Sends context, renders responses |
| `useWebSocket.test.ts` | Reconnection logic, event handling |

### 10.4 Key Test Scenarios

1. **Task idempotency (DB-003)**: Dispatch same paper discovery twice → second returns existing task, no duplicate execution.
2. **Calendar empty month**: Month with no assessed papers → all days show 0, no errors.
3. **Calendar gap fill**: Click missing day → dispatches gap_fill task → task completes → calendar updates.
4. **Service disconnected**: Zotero not configured → ServiceStatus shows `not_configured`.
5. **AI Agent with paper context**: Select papers → open AI panel → response references selected papers.
6. **WebSocket disconnect**: Kill WS → frontend polls → reconnects → resumes live updates.
7. **Task cancellation**: Start long-running sync → cancel → task status becomes `cancelled`.

---

## 11. CLI Integration

Add `dashboard` subcommand to `alithia/run/__main__.py`:

```bash
# Start dashboard server
uv run python -m alithia.run dashboard --config config.json

# Start with custom port
uv run python -m alithia.run dashboard --config config.json --port 8080

# Start in development mode (auto-reload)
uv run python -m alithia.run dashboard --config config.json --dev
```

Implementation:

```python
def add_dashboard_subparser(subparsers):
    parser = subparsers.add_parser("dashboard", help="Start Alithia Dashboard")
    parser.add_argument("-c", "--config", help="Config file path")
    parser.add_argument("--port", type=int, default=8080, help="Server port")
    parser.add_argument("--host", default="0.0.0.0", help="Server host")
    parser.add_argument("--dev", action="store_true", help="Enable auto-reload")

async def run_dashboard(args):
    config = load_config(args.config)
    storage = get_storage_backend(config)

    from alithia.dashboard.app import create_app
    app = create_app(config, storage)

    import uvicorn
    uvicorn.run(app, host=args.host, port=args.port, reload=args.dev)
```

---

## 12. Dependencies

### 12.1 Backend

| Package | Purpose |
|---------|---------|
| `fastapi` | Web framework |
| `uvicorn` | ASGI server |
| `websockets` | WebSocket support (via FastAPI) |
| `pydantic` | Already used; request/response models |

### 12.2 Frontend

| Package | Purpose |
|---------|---------|
| `react` | UI framework |
| `next` or `vite` | Build tooling |
| `tailwindcss` | Styling |
| `recharts` or `d3` | Calendar heatmap visualization |
| `lucide-react` | Icons |

Add to `pyproject.toml`:

```toml
[project.optional-dependencies]
dashboard = ["fastapi>=0.100", "uvicorn>=0.20", "websockets>=11.0"]
```

---

## 13. Migration / Compatibility

### 13.1 Backward Compatibility

- All existing CLI commands remain unchanged.
- The Dashboard is an additive feature — no existing behavior is modified.
- Agents do not require the Dashboard to function.

### 13.2 Data Dependencies

The Dashboard reads from tables populated by PaperScout and Sync Service:
- `assessed_papers` (from paperscout-impl.md §9.1) — required for Paper Trend
- `notification_records` (from paperscout-impl.md §9.2) — required for calendar status
- `sync_log` (from sync-persistence-impl.md §6.5) — required for service status
- `scholar_profiles` (from sync-persistence-impl.md §7.2) — optional, for Scholar details
- `zotero_papers` (existing) — for Zotero summary

The Dashboard adds one new table: `background_tasks`.

### 13.3 Deployment

The Dashboard can be deployed as:
1. **Local development**: `uv run python -m alithia.run dashboard --dev`
2. **Docker**: Single container with backend + built frontend
3. **Separate services**: Backend API + CDN-served frontend SPA

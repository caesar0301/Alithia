# RFC-003-paperscout-workflow: PaperScout Subagent Architecture

**Status**: Draft
**Authors**: Claude (recovered from existing implementation)
**Created**: 2026-06-06
**Last Updated**: 2026-06-06
**Depends on**: RFC-002-world-view
**Supersedes**: ---
**Stage**: DataCollection, Relevance, Notification
**Kind**: Architecture Design

---

## 1. Abstract

PaperScout is a soothe framework subagent for proactive ArXiv paper discovery and email notification. This RFC defines the LangGraph workflow architecture, component structure, data flow, and key interface contracts for the PaperScout subagent. It fetches papers from ArXiv API, builds a relevance profile from the user's Zotero library, ranks papers using sentence embeddings, generates TLDR summaries, and sends email digest notifications.

---

## 2. Scope and Non-Goals

### 2.1 Scope

This RFC defines:

* The 5-node LangGraph workflow pipeline and node responsibilities
* Component module structure and layer classification
* AgentState schema and data flow between nodes
* Integration with external APIs (ArXiv, Zotero, SMTP)
* Error handling strategy and graceful degradation rules
* Event types for observability
* Configuration schema (PaperScoutConfig, SmtpConfig, ZoteroConfig)
* Storage integration via AsyncPersistStore
* Gap Scanner for detecting missed notifications

### 2.2 Non-Goals

This RFC does **not** define:

* PaperLens integration or shared paper processing
* Web dashboard or real-time updates
* Alternative notification channels (Slack, webhooks)
* Multi-user or collaborative features
* Detailed reranking algorithm implementation
* Testing implementation details

---

## 3. Background & Motivation

PaperScout is the primary discovery mechanism in alithia-agent. Researchers need proactive monitoring of new publications in their fields of interest. PaperScout:

1. **Monitors ArXiv**: Fetches newly published papers from configured categories
2. **Profiles interests**: Analyzes user's Zotero library to understand research focus
3. **Ranks relevance**: Uses sentence embeddings to score papers against corpus
4. **Notifies efficiently**: Sends concise email digests with top papers

The workflow runs on-demand via CLI or can be scheduled (e.g., daily via cron/GitHub Actions).

---

## 4. Design Principles

1. **Proactive discovery**: User doesn't need to search; papers arrive automatically
2. **Personalized ranking**: Relevance determined by user's existing library
3. **Time-decay weighting**: Recent papers in Zotero weighted higher for profile
4. **Exactly-once notification**: Deduplication prevents duplicate emails
5. **Gap detection**: Missed notification dates can be filled retroactively
6. **Graceful degradation**: External API failures logged but don't crash workflow

---

## 5. Workflow Architecture

### 5.1 Pipeline Structure

```
START → profile_analysis → data_collection → relevance_assessment → content_generation → communication → END
```

### 5.2 Node Responsibilities

| Node | Responsibility | Input | Output to State |
|------|----------------|-------|-----------------|
| `profile_analysis` | Validate Zotero/SMTP config | `config.zotero`, `config.smtp` | `info`/`errors` |
| `data_collection` | Fetch ArXiv papers + Zotero corpus | `config.arxiv_categories`, `config.lookback_days` | `discovered_papers`, `zotero_papers` |
| `relevance_assessment` | Score papers against corpus | `discovered_papers`, `zotero_papers` | `scored_papers` |
| `content_generation` | Generate TLDR + email HTML | `scored_papers`, `config.max_papers` | `email_content` |
| `communication` | Send email + record notification | `email_content`, `config.smtp` | Notification record in storage |

### 5.3 Node Execution Constraints

| Constraint | Rule |
|------------|------|
| Linear flow | Nodes MUST execute in sequential order |
| Early exit | If `profile_analysis` fails validation, workflow MUST return early |
| Partial success | If `data_collection` fails partially (Zotero error), continue with ArXiv only |
| Empty handling | If no new papers, skip email unless `config.send_empty=True` |
| Notification recording | MUST save notification record and mark papers as emailed |

---

## 6. Component Structure

### 6.1 Module Organization

```
paperscout/
├── __init__.py          # Plugin entry point (@plugin/@subagent)
├── models.py            # ArxivPaper, ZoteroPaper, ScoredPaper, EmailContent, NotificationRecord
├── state.py             # AgentState, PaperScoutConfig, SmtpConfig, ZoteroConfig
├── implementation.py    # create_paperscout_graph, create_paperscout_subagent
├── nodes.py             # 5 workflow node functions
├── reranker.py          # PaperReranker (sentence transformer scoring)
├── gap_scanner.py       # GapScanner (detect/fill missed notifications)
├── email.py             # construct_email_content, send_email, HTML templates
├── events.py            # PaperScoutStepEvent, PaperScoutPaperFoundEvent, etc.
```

### 6.2 Layer Classification

| Module | Layer | Dependencies | Purpose |
|--------|-------|--------------|---------|
| `models.py` | Foundation | pydantic | Data model definitions |
| `state.py` | Foundation | models, langgraph | State and config schemas |
| `reranker.py` | Foundation | sentence-transformers, sklearn | Similarity computation |
| `gap_scanner.py` | Foundation | storage protocol | Gap detection logic |
| `email.py` | Foundation | smtplib | Email construction/sending |
| `events.py` | Foundation | soothe_sdk events | Event type definitions |
| `nodes.py` | Middle | arxiv, pyzotero, reranker, email, events | Workflow node functions |
| `implementation.py` | Middle | nodes, state, langgraph | Graph construction |
| `__init__.py` | Leaf | implementation, soothe_sdk | Plugin entry point |

### 6.3 External Dependencies

| Service | Library | Purpose |
|---------|---------|---------|
| ArXiv API | `arxiv>=2.0.0` | Paper discovery |
| Zotero API | `pyzotero>=1.5.0` | User library access |
| Sentence Transformers | `sentence-transformers>=2.2.0` | Embedding/ranking |
| SMTP | `smtplib` (stdlib) | Email delivery |

---

## 7. Data Flow

### 7.1 State Schema

```python
class AgentState(TypedDict):
    """LangGraph agent state for PaperScout workflow."""

    # LangGraph message history
    messages: Annotated[list[Any], add_messages]

    # Configuration
    config: PaperScoutConfig
    user_id: str

    # Discovered papers (from ArXiv)
    discovered_papers: list[ArxivPaper]

    # User corpus (from Zotero)
    zotero_papers: list[ZoteroPaper]

    # Ranked papers
    scored_papers: list[ScoredPaper]

    # Email content
    email_content: EmailContent | None

    # Tracking
    errors: Annotated[list[str], "add"]
    info: Annotated[list[str], "add"]
    metrics: dict[str, Any]
```

### 7.2 Data Transformation Flow

| Stage | Input | Transform | Output |
|-------|-------|-----------|--------|
| `data_collection` | ArXiv categories + date range | ArXiv API query → filter by date → dedupe vs emailed | `list[ArxivPaper]` |
| `data_collection` | Zotero config | Zotero API fetch → cache check → parse items | `list[ZoteroPaper]` |
| `relevance_assessment` | Papers + corpus | Encode corpus + papers → cosine similarity → time-decay weighting | `list[ScoredPaper]` |
| `content_generation` | Scored papers + max_papers | Slice top N → generate TLDR → build HTML | `EmailContent` |
| `communication` | Email + SMTP config | Connect SMTP → send → record notification | Storage record |

### 7.3 Storage Keys

| Key Pattern | Content | Purpose |
|-------------|---------|---------|
| `paperscout:emailed:{user_id}` | `list[arxiv_id]` | Deduplication (papers already notified) |
| `paperscout:zotero:{user_id}` | `{papers, timestamp}` | Zotero corpus cache (24h TTL) |
| `paperscout:notifications:{user_id}:{date}` | `{date, papers_count, arxiv_ids, sent_at}` | Notification history |

---

## 8. Configuration Schema

### 8.1 PaperScoutConfig

| Field | Type | Default | Constraints | Description |
|-------|------|---------|-------------|-------------|
| `arxiv_categories` | `list[str]` | `["cs.AI", "cs.CV", "cs.LG", "cs.CL"]` | — | ArXiv categories to query |
| `max_papers` | `int` | `25` | 1-100 | Papers in email digest |
| `max_papers_queried` | `int` | `500` | 10-1000 | Papers to query from ArXiv |
| `send_email` | `bool` | `True` | — | Enable email notifications |
| `send_empty` | `bool` | `False` | — | Send email if no papers |
| `recipient_email` | `str` | None | — | Override recipient (defaults to SMTP user) |
| `lookback_days` | `int` | `7` | 1-30 | Days to look back for papers |
| `big_bang_date` | `date` | None | — | Earliest valid notification date |
| `gap_window_days` | `int` | `7` | 1-30 | Window for gap detection |
| `emailed_papers_retention_days` | `int` | `30` | 7-90 | Dedupe list TTL |
| `smtp` | `SmtpConfig` | None | — | SMTP server config |
| `zotero` | `ZoteroConfig` | None | — | Zotero API config |
| `tldr_max_tokens` | `int` | `150` | 50-300 | TLDR generation limit |
| `tldr_language` | `str` | `"English"` | — | TLDR language |

### 8.2 SmtpConfig

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `host` | `str` | Yes | SMTP server hostname |
| `port` | `int` | No (default 587) | SMTP port |
| `user` | `str` | Yes | SMTP username |
| `password` | `str` | Yes | SMTP password |
| `use_tls` | `bool` | No (default True) | Enable TLS |

### 8.3 ZoteroConfig

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `api_key` | `str` | Yes | Zotero API key |
| `library_id` | `str` | Yes | Zotero library ID |
| `library_type` | `str` | No (default "user") | "user" or "group" |

---

## 9. Key Data Model Contracts

### 9.1 ArxivPaper

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `title` | `str` | Yes | Paper title |
| `summary` | `str` | Yes | Abstract/summary |
| `authors` | `list[str]` | Yes | Author names |
| `arxiv_id` | `str` | Yes | ArXiv identifier (e.g., "2401.12345") |
| `pdf_url` | `str` | Yes | PDF download URL |
| `published_date` | `datetime` | Yes | Publication timestamp |
| `score` | `float` | No (default 0.0) | Relevance score |
| `code_url` | `str` | None | PapersWithCode link |
| `tldr` | `str` | None | Generated TLDR summary |

### 9.2 ZoteroPaper

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `zotero_item_key` | `str` | Yes | Zotero item identifier |
| `title` | `str` | Yes | Paper title |
| `authors` | `list[str]` | Yes | Author names |
| `abstract` | `str` | None | Paper abstract |
| `url` | `str` | None | Source URL |
| `tags` | `list[str]` | No | User-assigned tags |
| `date_added` | `datetime` | None | When added to library |
| `collection_paths` | `list[str]` | No | Collection hierarchy |

### 9.3 EmailContent

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `subject` | `str` | Yes | Email subject line |
| `html_body` | `str` | Yes | HTML email body |
| `text_body` | `str` | None | Plain text fallback |
| `papers` | `list[ArxivPaper]` | Yes | Papers included in digest |

### 9.4 NotificationRecord

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `date` | `date` | Yes | Notification date |
| `papers_count` | `int` | Yes | Number of papers |
| `recipient` | `str` | Yes | Email recipient |
| `arxiv_ids` | `list[str]` | Yes | Papers included |
| `sent_at` | `datetime` | Yes | Timestamp |
| `success` | `bool` | No (default True) | Delivery status |
| `error_message` | `str` | None | Failure reason |

---

## 10. Gap Scanner Architecture

### 10.1 Purpose

GapScanner detects dates within a window where notifications were not sent and triggers PaperScout to fill those gaps. Useful for:
- Recovering from missed scheduled runs
- Backfilling after first-time setup
- Handling service interruptions

### 10.2 GapScanner Interface

```python
class GapScanner:
    def __init__(self, store: AsyncPersistStore, user_id: str, big_bang: date | None)

    async def scan(window_days: int) -> list[date]
        # Find dates with missing notifications

    async def fill_gaps(config: PaperScoutConfig, agent) -> dict[date, str]
        # Run PaperScout for each missing date
```

### 10.3 Gap Detection Logic

| Step | Logic |
|------|-------|
| 1 | Calculate date range: `today - window_days` to `today` |
| 2 | Check each date for notification record in storage |
| 3 | Filter by `big_bang_date` if configured |
| 4 | Return list of missing dates |

---

## 11. Error Handling

### 11.1 Error Categories

| Category | Example | Handling |
|----------|---------|----------|
| **Config validation** | Missing Zotero API key | Emit error, return early from `profile_analysis` |
| **ArXiv API failure** | Rate limit, network error | Log error, return empty `discovered_papers` |
| **Zotero API failure** | Invalid credentials, timeout | Log error, continue with ArXiv only |
| **Reranking failure** | Model load error, OOM | Use fallback scores (5.0 default) |
| **SMTP failure** | Auth error, connection refused | Log error, mark notification as failed |
| **Storage failure** | SQLite locked, disk full | Log error, continue without cache |

### 11.2 Graceful Degradation Invariants

| Invariant | Rule |
|-----------|------|
| Zotero unavailable | MUST continue with ArXiv-only (no corpus ranking) |
| Reranker unavailable | MUST use default score 5.0 for all papers |
| SMTP unavailable | MUST record failure in notification record |
| Storage unavailable | MUST continue without caching |

---

## 12. Events

### 12.1 Event Types

| Event Type | When Emitted | Verbosity |
|------------|--------------|-----------|
| `soothe.community.paperscout.step` | Each workflow step start/end | NORMAL |
| `soothe.community.paperscout.paper.found` | Paper scored and selected | NORMAL |
| `soothe.community.paperscout.email.sent` | Email successfully sent | NORMAL |
| `soothe.community.paperscout.error` | Error occurred | DEBUG |

### 12.2 Event Schemas

**PaperScoutStepEvent**:
| Field | Type | Description |
|-------|------|-------------|
| `step` | `str` | Node name |
| `status` | `str` | Status message |

**PaperScoutPaperFoundEvent**:
| Field | Type | Description |
|-------|------|-------------|
| `paper_title` | `str` | Paper title |
| `arxiv_id` | `str` | ArXiv identifier |
| `score` | `float` | Relevance score |

**PaperScoutEmailSentEvent**:
| Field | Type | Description |
|-------|------|-------------|
| `recipient` | `str` | Email recipient |
| `papers_count` | `int` | Papers in digest |

**PaperScoutErrorEvent**:
| Field | Type | Description |
|-------|------|-------------|
| `error_message` | `str` | Error description |
| `step` | `str` | Node where error occurred |

---

## 13. Dependencies

### 13.1 Required Dependencies

| Package | Purpose | Minimum Version |
|---------|---------|-----------------|
| `langgraph` | Workflow orchestration | 0.2.0 |
| `pydantic` | Data models | 2.0 |
| `arxiv` | ArXiv API client | 2.0.0 |
| `pyzotero` | Zotero API client | 1.5.0 |
| `sentence-transformers` | Similarity embeddings | 2.2.0 |
| `scikit-learn` | Cosine similarity | 1.0.0 |
| `numpy` | Array operations | 1.20.0 |

### 13.2 Framework Integration

| Integration | Mechanism |
|-------------|-----------|
| Plugin registration | `@plugin(name="paperscout", ...)` |
| Subagent creation | `@subagent(name="paperscout", ...)` |
| Storage | `AsyncPersistStore` via kwargs or config.services |
| Events | SubagentEvent base class |

---

## 14. Relationship to PaperLens

### 14.1 Shared Patterns

| Pattern | Implementation |
|---------|----------------|
| 5-node linear workflow | Same pipeline structure |
| AgentState TypedDict | Same state pattern |
| Event emission | Same naming convention |
| Pydantic config | Same validation approach |

### 14.2 Key Differences

| Aspect | PaperScout | PaperLens |
|--------|------------|-----------|
| Trigger | Scheduled/CLI | User-initiated query |
| Data source | ArXiv API + Zotero | User-provided PDFs |
| Ranking corpus | Zotero library | Query string |
| Output | Email notification | In-state response |
| Persistence | Extensive (notifications, dedupe) | None |
| Time awareness | Yes (lookback_days, gap detection) | No |

---

## 15. Open Questions

None. All design decisions are implemented in existing code.

---

## 16. Conclusion

PaperScout is a soothe subagent implementing a 5-node LangGraph workflow for proactive ArXiv paper discovery. The architecture defines:

1. **Linear pipeline**: profile_analysis → data_collection → relevance_assessment → content_generation → communication
2. **External integrations**: ArXiv API, Zotero API, SMTP
3. **Reranking**: Sentence transformer embeddings with time-decay weighting
4. **Storage**: Notification records, deduplication, corpus caching
5. **Gap detection**: GapScanner for missed notification recovery
6. **Graceful degradation**: Continue on partial failures, log errors

> **PaperScout delivers personalized ArXiv recommendations by analyzing the user's Zotero library, ranking new papers by semantic similarity, and sending concise email digests — ensuring exactly-once notification delivery.**
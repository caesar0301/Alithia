# RFC-001-paperlens-workflow: PaperLens Subagent Architecture

**Status**: Draft
**Authors**: Claude (from brainstorming session)
**Created**: 2026-06-06
**Last Updated**: 2026-06-06
**Depends on**: RFC-002-world-view
**Supersedes**: ---
**Stage**: Core
**Kind**: Architecture Design

---

## 1. Abstract

PaperLens is a soothe framework subagent for discovering relevant academic papers from user-provided PDF collections. This RFC defines the LangGraph workflow architecture, component structure, data flow, and key interface contracts for the PaperLens subagent. It parses PDFs using Docling with IBM Granite VLM, enhances metadata using LLM when needed, calculates semantic similarity using sentence embeddings, and returns ranked results with relevance scores.

---

## 2. Scope and Non-Goals

### 2.1 Scope

This RFC defines:

* The 5-node LangGraph workflow pipeline and node responsibilities
* Component module structure and layer classification
* AgentState schema and data flow between nodes
* Error handling strategy and graceful degradation rules
* Event types for observability
* Configuration schema (PaperLensConfig)
* Key data model contracts (AcademicPaper, ScoredPaper)

### 2.2 Non-Goals

This RFC does **not** define:

* Interactive Q&A mode for individual papers
* Integration with PaperScout's cached papers
* Email notifications (PaperLens returns results in state)
* PDF storage or caching strategy
* Frontend/dashboard integration
* Detailed implementation algorithms for PDF parsing
* Testing implementation details

---

## 3. Background & Motivation

Alithia-agent is a pure CLI version of alithia-app, built on the soothe framework. The existing PaperScout subagent handles ArXiv paper discovery and email notifications. PaperLens is the second subagent needed to complete core functionality — it enables researchers to analyze local PDF collections and find papers relevant to specific research questions.

The soothe framework uses LangGraph workflows with:
- State management via TypedDict
- Multiple nodes forming a processing pipeline
- Event emission for observability
- AsyncPersistStore integration for persistence

PaperLens MUST follow this pattern to be consistent with PaperScout and fully integrate with the soothe ecosystem.

---

## 4. Design Principles

1. **Consistency**: PaperLens follows the same LangGraph workflow pattern as PaperScout
2. **Parallelism**: Batch processing with asyncio for efficient PDF parsing
3. **Graceful degradation**: Single PDF failures MUST NOT abort the entire workflow
4. **Soothe integration**: Full event emission and state management
5. **LLM enhancement**: Improve metadata quality when Docling output is incomplete

---

## 5. Workflow Architecture

### 5.1 Pipeline Structure

```
START → validate_input → parse_pdfs → calculate_similarity → rank_results → generate_summary → END
```

### 5.2 Node Responsibilities

| Node | Responsibility | Input | Output to State |
|------|----------------|-------|-----------------|
| `validate_input` | Check PDF path exists, query non-empty | `query`, `pdf_path` | `info`/`errors` |
| `parse_pdfs` | Batch parse PDFs with Docling + LLM enhancement | `pdf_path` | `parsed_papers` |
| `calculate_similarity` | Encode query + papers, compute cosine similarity | `query`, `parsed_papers` | `papers_with_scores` |
| `rank_results` | Sort by score descending, take top N | `papers_with_scores`, `config.max_papers` | `ranked_papers` |
| `generate_summary` | Format results for response | `ranked_papers`, `config.output_format` | `response_content` |

### 5.3 Node Execution Constraints

| Constraint | Rule |
|------------|------|
| Linear flow | Nodes MUST execute in sequential order |
| Early exit | If `validate_input` fails, workflow MUST return early with errors |
| Partial results | If `parse_pdfs` has failures, workflow MUST continue with successful parses |
| Empty handling | If no papers parsed, workflow MUST return empty results (not error) |

---

## 6. Component Structure

### 6.1 Module Organization

```
paperlens/
├── __init__.py          # Plugin entry point (soothe_sdk @plugin/@subagent)
├── state.py             # AgentState + PaperLensConfig
├── models.py            # AcademicPaper, PaperMetadata, PaperContent, ScoredPaper
├── implementation.py    # LangGraph graph construction
├── nodes.py             # 5 workflow node functions
├── pdf_parser.py        # Docling + LLM enhancement wrapper
├── similarity.py        # Sentence transformer similarity engine
├── events.py            # PaperLens event types
```

### 6.2 Layer Classification

| Module | Layer | Dependencies | Purpose |
|--------|-------|--------------|---------|
| `models.py` | Foundation | pydantic | Data model definitions |
| `state.py` | Foundation | models, langgraph | State and config schemas |
| `pdf_parser.py` | Foundation | docling, soothe LLM | PDF parsing implementation |
| `similarity.py` | Foundation | sentence-transformers | Similarity computation |
| `events.py` | Foundation | soothe_sdk events | Event type definitions |
| `nodes.py` | Middle | parser, similarity, events | Workflow node functions |
| `implementation.py` | Middle | nodes, state, langgraph | Graph construction |
| `__init__.py` | Leaf | implementation, soothe_sdk | Plugin entry point |

### 6.3 Dependency Constraints

| Constraint | Rule |
|------------|------|
| Foundation isolation | Foundation modules MUST NOT import Middle or Leaf modules |
| Middle dependencies | Middle modules MAY import Foundation modules |
| Leaf dependencies | Leaf modules MAY import Middle and Foundation modules |
| No circular deps | All imports MUST form a directed acyclic graph |

---

## 7. Data Flow

### 7.1 State Schema

```python
class AgentState(TypedDict):
    """LangGraph agent state for PaperLens workflow."""

    # LangGraph message history (required by framework)
    messages: Annotated[list[Any], add_messages]

    # Configuration
    config: PaperLensConfig
    user_id: str

    # Input (provided at invocation)
    query: str                    # Research topic/question
    pdf_path: str                 # Directory or file path

    # Intermediate results (populated by nodes)
    parsed_papers: list[AcademicPaper]      # After parse_pdfs
    papers_with_scores: list[ScoredPaper]   # After calculate_similarity
    ranked_papers: list[ScoredPaper]        # After rank_results

    # Output
    response_content: str         # Formatted summary

    # Tracking
    errors: Annotated[list[str], "add"]
    info: Annotated[list[str], "add"]
    metrics: dict[str, Any]
```

### 7.2 Data Transformation Flow

| Stage | Input | Transform | Output |
|-------|-------|-----------|--------|
| `parse_pdfs` | PDF bytes | Docling parse → metadata extraction → LLM enhancement | `list[AcademicPaper]` |
| `calculate_similarity` | query + paper texts | Sentence transformer encode → cosine similarity | `list[ScoredPaper]` |
| `rank_results` | ScoredPapers | Sort descending → slice to max_papers | `list[ScoredPaper]` |
| `generate_summary` | Ranked papers + format config | Markdown/JSON formatting | `str` |

### 7.3 Metrics Schema

```python
metrics: {
    "pdfs_found": int,              # Total PDFs discovered
    "pdfs_parsed": int,             # Successfully parsed
    "pdfs_failed": int,             # Parse failures
    "avg_parse_time_ms": float,     # Average parse duration
    "avg_similarity_score": float,  # Mean score across papers
    "top_score": float,             # Highest similarity score
    "total_processing_time_ms": float,
}
```

---

## 8. Configuration Schema

### 8.1 PaperLensConfig

| Field | Type | Default | Constraints | Description |
|-------|------|---------|-------------|-------------|
| `pdf_extensions` | `list[str]` | `["pdf"]` | — | File extensions to process |
| `recursive_scan` | `bool` | `True` | — | Search subdirectories for PDFs |
| `max_papers` | `int` | `50` | 1-200 | Maximum papers in results |
| `batch_size` | `int` | `8` | 1-32 | Parallel parse batch size |
| `sbert_model` | `str` | `"all-MiniLM-L6-v2"` | — | Sentence transformer model |
| `use_gpu` | `bool` | `False` | — | GPU for embedding computation |
| `llm_enhance_metadata` | `bool` | `True` | — | LLM enhancement for incomplete metadata |
| `llm_max_tokens` | `int` | `500` | 100-1000 | Max tokens for LLM extraction |
| `output_format` | `str` | `"markdown"` | `"markdown"` or `"json"` | Output format |
| `include_full_text` | `bool` | `False` | — | Include full text in results |

### 8.2 Subagent Invocation Interface

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `query` | `str` | Yes | Research topic/question |
| `pdf_path` | `str` | Yes | Path to PDF file or directory |

---

## 9. Key Data Model Contracts

### 9.1 AcademicPaper

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `file_metadata` | `FileMetadata` | Yes | File system metadata |
| `paper_metadata` | `PaperMetadata` | Yes | Extracted paper metadata |
| `content` | `PaperContent` | Yes | Structured paper content |
| `similarity_score` | `float` | No (default 0.0) | Similarity to query |
| `parse_timestamp` | `datetime` | No | When paper was parsed |
| `parsing_errors` | `list[str]` | No | Parse error messages |

**MUST implement**: `get_searchable_text() -> str` — Returns weighted combination of title, abstract, keywords, and full text for similarity matching.

### 9.2 ScoredPaper

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `paper` | `AcademicPaper` | Yes | The paper object |
| `score` | `float` | Yes | Similarity score |
| `relevance_factors` | `dict[str, float]` | No | Breakdown of score factors |

### 9.3 FileMetadata

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `file_path` | `Path` | Yes | Absolute file path |
| `file_name` | `str` | Yes | File name with extension |
| `file_size` | `int` | Yes | Size in bytes |
| `last_modified` | `datetime` | Yes | Last modification time |
| `md5_hash` | `str` | No | MD5 hash of file |

### 9.4 PaperMetadata

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `title` | `str` | No | Paper title |
| `authors` | `list[str]` | No | Author names |
| `year` | `int` | No | Publication year |
| `abstract` | `str` | No | Paper abstract |
| `keywords` | `list[str]` | No | Keywords/topics |
| `doi` | `str` | No | Digital Object Identifier |
| `venue` | `str` | No | Journal/conference name |

### 9.5 PaperContent

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `full_text` | `str` | Yes | Complete text content |
| `sections` | `dict[str, str]` | No | Section name → content |
| `references` | `list[str]` | No | Reference entries |
| `figures` | `list[str]` | No | Figure descriptions |
| `tables` | `list[str]` | No | Table descriptions |

---

## 10. Error Handling

### 10.1 Error Categories

| Category | Example | Handling |
|----------|---------|----------|
| **Input validation** | Invalid path, empty query | Emit error event, return early with error in state |
| **PDF parse failure** | Corrupted PDF, unsupported format | Skip paper, log warning, continue with others |
| **Metadata incomplete** | Docling can't extract title | Attempt LLM enhancement; if fails, use filename as fallback |
| **Similarity computation** | Embedding model error | Return papers with default score 0.0, emit error event |
| **Resource exhaustion** | Memory/CPU limits | Stop batch processing, return partial results |

### 10.2 Graceful Degradation Invariants

| Invariant | Rule |
|-----------|------|
| Single PDF failure | MUST skip, not abort workflow |
| LLM unavailable | MUST use Docling-only (incomplete metadata acceptable) |
| GPU unavailable | MUST fall back to CPU |
| No valid papers | MUST return empty results (not error) |

---

## 11. Events

### 11.1 Event Types

| Event Type | When Emitted | Verbosity |
|------------|--------------|-----------|
| `soothe.community.paperlens.step` | Each workflow step start/end | NORMAL |
| `soothe.community.paperlens.paper.parsed` | PDF successfully parsed | NORMAL |
| `soothe.community.paperlens.paper.rank` | Paper assigned rank | NORMAL |
| `soothe.community.paperlens.error` | Error occurred | DEBUG |
| `soothe.community.paperlens.complete` | Workflow finished | NORMAL |

### 11.2 Event Schemas

**PaperLensStepEvent**:
| Field | Type | Description |
|-------|------|-------------|
| `step` | `str` | Node name |
| `status` | `str` | Status message |

**PaperLensPaperParsedEvent**:
| Field | Type | Description |
|-------|------|-------------|
| `paper_title` | `str` | Extracted title or filename |
| `file_name` | `str` | PDF filename |

**PaperLensRankEvent**:
| Field | Type | Description |
|-------|------|-------------|
| `rank` | `int` | Position in results |
| `paper_title` | `str` | Paper title |
| `score` | `float` | Similarity score |

**PaperLensErrorEvent**:
| Field | Type | Description |
|-------|------|-------------|
| `error_message` | `str` | Error description |
| `step` | `str` | Node where error occurred |
| `paper_id` | `str` | PDF identifier (if paper-specific) |

**PaperLensCompleteEvent**:
| Field | Type | Description |
|-------|------|-------------|
| `papers_count` | `int` | Total papers analyzed |

---

## 12. Dependencies

### 12.1 Required Dependencies

| Package | Purpose | Minimum Version |
|---------|---------|-----------------|
| `langgraph` | Workflow orchestration | 0.2.0 |
| `pydantic` | Data models | 2.0 |
| `docling` | PDF parsing (IBM Granite VLM) | 2.0.0 |
| `sentence-transformers` | Similarity embeddings | 2.2.0 |

### 12.2 Framework Integration

| Integration | Mechanism |
|-------------|-----------|
| Plugin registration | `@plugin` decorator from soothe_sdk |
| Subagent creation | `@subagent` decorator from soothe_sdk |
| Event emission | SubagentEvent base class from soothe_sdk |
| LLM access | Model parameter passed to create_paperlens |

---

## 13. Relationship to PaperScout

### 13.1 Shared Patterns

| Pattern | Implementation |
|---------|----------------|
| 5-node linear workflow | Same pipeline structure |
| AgentState TypedDict | Same state pattern with messages, errors, info, metrics |
| Event emission | Same event naming pattern (`soothe.community.<agent>.<event>`) |
| Config BaseModel | Same Pydantic config pattern |
| @plugin/@subagent decorators | Same soothe_sdk integration |

### 13.2 Key Differences

| Aspect | PaperScout | PaperLens |
|--------|------------|-----------|
| Data source | ArXiv API | User-provided PDFs |
| Output mechanism | Email notification | In-state response |
| Persistence | AsyncPersistStore | No persistent storage |
| Invocation timing | Scheduled (daily) | User-initiated (ad-hoc) |
| Ranking corpus | Zotero library | Query string only |

---

## 14. Open Questions

None. All design decisions have been resolved through brainstorming.

---

## 15. Conclusion

PaperLens is a soothe subagent implementing a 5-node LangGraph workflow for PDF discovery and ranking. The architecture defines:

1. **Linear pipeline**: validate_input → parse_pdfs → calculate_similarity → rank_results → generate_summary
2. **Foundation/Middle/Leaf layers**: Clean dependency hierarchy
3. **AgentState schema**: TypedDict with input, intermediate, output, and tracking fields
4. **Graceful degradation**: Skip failures, not abort; LLM fallback; CPU fallback
5. **Event types**: Step, paper parsed, rank, error, complete
6. **Configuration**: PaperLensConfig with PDF, similarity, LLM, and output settings

> **PaperLens enables researchers to find relevant papers in their local collections through semantic similarity matching, complementing PaperScout's ArXiv discovery workflow.**
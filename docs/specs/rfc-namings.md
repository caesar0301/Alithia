# alithia-agent Terminology Reference

Authoritative terminology reference for alithia-agent RFC specifications.

---

## Rules

1. All RFCs **MUST** use the terms defined here when referring to project concepts
2. New terms introduced in an RFC **MUST** be registered in this document
3. Deprecated terms **MUST** be removed when the defining RFC is deprecated
4. This document reflects the **current** state of terminology (not historical)

---

## System-Level Terms

| Term | Source RFC | Brief Description |
|------|-----------|-------------------|
| Alithia-agent | RFC-002-world-view | CLI-based research assistant built on soothe framework |
| Subagent | RFC-002, RFC-007 | Soothe framework agent implementing LangGraph workflow |
| Workflow | RFC-002-world-view | Directed graph of processing nodes transforming input to output |
| Node | RFC-002-world-view | Single processing step in a workflow |
| AgentState | RFC-002-world-view | TypedDict holding all workflow data |
| Event | RFC-002, RFC-007 | Structured record emitted for observability |
| Config | RFC-002, RFC-006 | Pydantic BaseModel for user-controllable parameters |
| Storage | RFC-002, RFC-004 | Persistence layer for caching and deduplication |
| Plugin | RFC-007 | soothe_sdk module via @plugin decorator |

---

## Subagent Terms

| Term | Source RFC | Brief Description |
|------|-----------|-------------------|
| PaperLens | RFC-001, RFC-002 | Subagent for PDF discovery and ranking |
| PaperScout | RFC-003, RFC-002 | Subagent for ArXiv discovery and email notifications |
| Gap Scanner | RFC-003-paperscout | Component detecting/filling missed notifications |
| OmniResearch | RFC-010 | Subagent for structured research workflows with pattern routing |

---

## Paper Data Terms

| Term | Source RFC | Brief Description |
|------|-----------|-------------------|
| Paper | RFC-002, RFC-008 | Unit of academic content with metadata |
| Score | RFC-002, RFC-008 | Relevance metric comparing paper to interests |
| AcademicPaper | RFC-001, RFC-008 | Generic paper with title, authors, abstract, content |
| ArxivPaper | RFC-003, RFC-008 | Paper from ArXiv API with arxiv_id, pdf_url |
| ZoteroPaper | RFC-003, RFC-008 | Paper from Zotero library with zotero_item_key |
| ScoredPaper | RFC-001, RFC-003, RFC-008 | Paper with attached relevance score |
| FileMetadata | RFC-001, RFC-008 | PDF file system metadata (path, size, hash) |
| PaperMetadata | RFC-001, RFC-008 | Extracted paper metadata (title, authors, abstract) |
| PaperContent | RFC-001, RFC-008 | Structured paper content (text, sections, figures) |

---

## Processing Terms

| Term | Source RFC | Brief Description |
|------|-----------|-------------------|
| Discovery | RFC-002-world-view | Finding new papers from external sources |
| Analysis | RFC-002-world-view | Extracting content/metadata from papers |
| Ranking | RFC-002-world-view | Ordering papers by relevance score |
| Notification | RFC-002-world-view | Delivering results to user |
| Caching | RFC-002, RFC-004 | Storing API results to avoid redundant fetches |
| Deduplication | RFC-002, RFC-004 | Preventing duplicate processing/notification |
| Reranking | RFC-003-paperscout | Paper scoring using sentence embeddings |
| Time-decay weighting | RFC-003-paperscout | Recent papers weighted higher in corpus |

---

## OmniResearch Terms

| Term | Source RFC | Brief Description |
|------|-----------|-------------------|
| Pattern routing | RFC-010 | Auto-detecting research intent and selecting workflow pattern |
| Skill tree | RFC-010 | State tracking for skill progression (unlocked/ready/locked/completed) |
| Gate enforcement | RFC-010 | Quality criteria checks at skill boundaries (Gates A, B, C, D) |
| Evidence-First | RFC-010 | Research pattern: literature surveys starting from papers |
| Idea-First | RFC-010 | Research pattern: exploratory research starting from insights |
| Decision-First | RFC-010 | Research pattern: engineering decisions validation |
| Experiment-First | RFC-010 | Research pattern: hypothesis testing with rapid iteration |
| Rapid-Prototype | RFC-010 | Research pattern: fast exploration without gate constraints |
| Bootstrap node | RFC-010 | Workspace creation node (directories, CLAUDE.md, skill tree) |
| Collection node | RFC-010 | Material collection node with 4 handlers |
| Evidence node | RFC-010 | Evidence extraction and brief generation node |
| OmrAgentConfig | RFC-006, RFC-010 | Configuration schema for OmniResearch subagent |
| OmrRuntimeConfig | RFC-010 | Runtime config derived from global config + soothe workspace |

---

## Framework Integration Terms

| Term | Source RFC | Brief Description |
|------|-----------|-------------------|
| @plugin | RFC-007 | Decorator for plugin module registration |
| @subagent | RFC-007 | Decorator for subagent factory registration |
| AsyncPersistStore | RFC-004, RFC-007 | Protocol for async key-value persistence |
| SubagentEvent | RFC-007 | Base class for agent-emitted events |
| PluginContext | RFC-007 | Context with logger, config, services |
| VerbosityTier | RFC-007 | Event visibility level (NORMAL, DEBUG, VERBOSE) |

---

## Storage Terms

| Term | Source RFC | Brief Description |
|------|-----------|-------------------|
| SQLite Storage | RFC-004-storage | Local-first persistence at ~/.alithia/ |
| kv_store | RFC-004-storage | Generic key-value table |
| Schema migration | RFC-004-storage | Versioned SQL files for schema evolution |
| Key naming | RFC-004-storage | Pattern: {subagent}:{category}:{user_id}:{suffix} |
| TTL | RFC-004-storage | Time-to-live for cached data |
| Notification record | RFC-003, RFC-008 | Record of sent email notification |

---

## Configuration Terms

| Term | Source RFC | Brief Description |
|------|-----------|-------------------|
| PaperLensConfig | RFC-001, RFC-006 | Configuration schema for PaperLens |
| PaperScoutConfig | RFC-003, RFC-006 | Configuration schema for PaperScout |
| SmtpConfig | RFC-003, RFC-006 | SMTP server configuration |
| ZoteroConfig | RFC-003, RFC-006 | Zotero API configuration |
| LlmConfig | RFC-006 | LLM provider configuration |
| Environment substitution | RFC-006 | ${VAR_NAME} syntax for secrets |
| Config merge precedence | RFC-006 | CLI > file > defaults |

---

## CLI Terms

| Term | Source RFC | Brief Description |
|------|-----------|-------------------|
| Entry point | RFC-005-cli | python -m alithia_agent invocation |
| Subagent flag | RFC-005-cli | --subagent paperscout/paperlens |
| Config flag | RFC-005-cli | --config PATH override |
| Output format | RFC-005-cli | stdout, json, none |
| Verbosity level | RFC-005-cli | --verbose, --quiet |
| Exit code | RFC-005-cli | 0=success, 1=arg error, 2=exec error, 3=config error |

---

## External Integration Terms

| Term | Source RFC | Brief Description |
|------|-----------|-------------------|
| Docling | RFC-001, RFC-008 | PDF parsing library with IBM Granite VLM |
| Sentence Transformer | RFC-001, RFC-003 | Embedding model for semantic similarity |
| LLM Enhancement | RFC-001, RFC-008 | LLM-based metadata extraction fallback |
| ArXiv API | RFC-003-paperscout | Paper discovery source |
| Zotero API | RFC-003-paperscout | User library access |
| SMTP | RFC-003, RFC-006 | Email delivery |

---

## Email/Notification Terms

| Term | Source RFC | Brief Description |
|------|-----------|-------------------|
| EmailContent | RFC-003, RFC-008 | Email digest with subject, HTML body, papers |
| NotificationRecord | RFC-003, RFC-008 | Record of sent notification with arxiv_ids |
| Email digest | RFC-003 | Daily email with paper recommendations |
| TLDR | RFC-001, RFC-003 | Generated paper summary |

---

## Naming Conventions (RFC-008)

| Convention | Example |
|------------|---------|
| snake_case fields | `arxiv_id`, `published_date` |
| `_at` timestamp suffix | `sent_at`, `parsed_at` |
| `_date` date suffix | `published_date` |
| `_count` count suffix | `papers_count` |
| Boolean `is_`, `has_`, `send_` | `is_complete`, `send_email` |
| `get_*()` computed methods | `get_searchable_text()` |
| `to_*()` conversion methods | `to_dict()` |
| `display_*` human-readable | `display_title`, `display_authors` |

---

## Usage Guidelines

- **Capitalization**: Use the capitalization shown in the Term column
- **First use**: On first use in an RFC, link to this document or the defining RFC
- **Synonyms**: Avoid synonyms; use the canonical term from this table

---

## Related Documents

- [rfc-standard.md](rfc-standard.md) - RFC process and conventions
- [rfc-index.md](rfc-index.md) - RFC index
- [rfc-history.md](rfc-history.md) - Change history
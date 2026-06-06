# RFC-002-world-view: Alithia Agent System Vision

**Status**: Draft
**Authors**: Claude
**Created**: 2026-06-06
**Last Updated**: 2026-06-06
**Depends on**: ---
**Supersedes**: ---
**Stage**: Core
**Kind**: Conceptual Design

---

## 1. Abstract

Alithia-agent is a CLI-based research assistant built on the soothe agent framework. It provides personalized academic paper discovery through specialized subagents — PaperScout for ArXiv recommendations and PaperLens for local PDF analysis. This RFC defines the system's vision, design philosophy, core abstractions, taxonomy, and system-wide invariants that govern all subagent implementations.

---

## 2. Scope and Non-Goals

### 2.1 Scope

This RFC defines:

* System purpose and target users
* Design philosophy and guiding principles
* Core conceptual model (subagent orchestration)
* System-wide taxonomy and terminology
* Cross-cutting invariants all components MUST respect
* High-level architecture constraints

### 2.2 Non-Goals

This RFC does **not** define:

* Concrete module or component structure (see Architecture Design RFCs)
* API contracts or interface signatures (see Implementation Interface Design RFCs)
* Implementation details, storage formats, or algorithms
* Specific subagent workflows (see RFC-001-paperlens-workflow, RFC-003-paperscout-workflow)

---

## 3. Background & Motivation

Alithia-app is a multi-agent research companion with a web dashboard, multiple agents, and complex deployment. Alithia-agent is a **pure CLI version** designed for:

- **Simplicity**: Single-user, local-first operation
- **Portability**: Runs anywhere Python runs
- **Integration**: Built on soothe framework for standardized agent patterns

Researchers need tools that:
1. Monitor new publications relevant to their interests
2. Analyze their local paper collections
3. Operate without complex setup or cloud dependencies

Alithia-agent addresses these needs through two complementary subagents:
- **PaperScout**: Proactive discovery (ArXiv monitoring + email alerts)
- **PaperLens**: Reactive analysis (user-initiated PDF ranking)

---

## 4. Design Philosophy

### 4.1 Core Principles

1. **Local-first**: All data stored locally at `~/.alithia/`; no cloud required
2. **Subagent autonomy**: Each subagent is a self-contained soothe subagent with its own workflow
3. **Composable workflows**: Subagents can be invoked independently or chained
4. **Graceful degradation**: Failures in external services (APIs, email) MUST NOT crash the agent
5. **Event-driven observability**: All significant operations emit events for logging/monitoring
6. **Configuration over code**: User behavior controlled via config, not code changes

### 4.2 Design Philosophy Statement

> Alithia-agent treats research workflows as independent, event-emitting pipelines that can run standalone or together. Each subagent owns its data sources, processing logic, and output mechanism. The system prefers local storage, handles external failures gracefully, and provides clear observability through structured events.

---

## 5. Conceptual Model

### 5.1 System Context

```
┌─────────────────────────────────────────────────────────┐
│                      User                                │
│  (Researcher with papers, interests, questions)         │
└─────────────────────────────────────────────────────────┘
                          │
                          │ CLI Invocation
                          ▼
┌─────────────────────────────────────────────────────────┐
│                   alithia-agent                          │
│                                                          │
│  ┌──────────────┐    ┌──────────────┐                   │
│  │  PaperScout  │    │  PaperLens   │                   │
│  │  Subagent    │    │  Subagent    │                   │
│  └──────────────┘    └──────────────┘                   │
│         │                   │                           │
│         │                   │                           │
│  ┌──────────────────────────────────────┐              │
│  │         Storage Layer                │              │
│  │      (SQLite at ~/.alithia/)         │              │
│  └──────────────────────────────────────┘              │
└─────────────────────────────────────────────────────────┘
                          │
          ┌───────────────┼───────────────┐
          │               │               │
          ▼               ▼               ▼
    ┌──────────┐   ┌──────────┐   ┌──────────┐
    │  ArXiv   │   │  Zotero  │   │   SMTP   │
    │   API    │   │   API    │   │  Server  │
    └──────────┘   └──────────┘   └──────────┘
```

### 5.2 Core Abstractions

| Abstraction | Definition |
|-------------|------------|
| **Subagent** | A soothe framework agent implementing a LangGraph workflow with defined state, nodes, events, and configuration |
| **Workflow** | A directed graph of processing nodes that transform input to output via state mutations |
| **Node** | A single processing step in a workflow; receives state, performs work, returns state updates |
| **AgentState** | A TypedDict holding all data flowing through a workflow (input, intermediate, output, tracking) |
| **Event** | A structured record emitted during execution for observability (step progress, errors, completions) |
| **Config** | A Pydantic BaseModel defining user-controllable parameters for subagent behavior |
| **Paper** | A unit of academic content with metadata (title, authors, abstract) and optional full text |
| **Score** | A relevance metric comparing paper content to user interests or query |
| **Storage** | A persistence layer for caching API results, tracking notifications, and deduplicating |

### 5.3 Subagent Lifecycle

```
┌─────────┐     ┌─────────┐     ┌─────────┐     ┌─────────┐
│ Config  │────▶│ Invoke  │────▶│ Execute │────▶│ Output  │
│ Loaded  │     │ via CLI │     │Workflow │     │ Result  │
└─────────┘     └─────────┘     └─────────┘     └─────────┘
                                    │
                                    │ Events
                                    ▼
                              ┌─────────┐
                              │  Log/   │
                              │ Monitor │
                              └─────────┘
```

---

## 6. Taxonomy

### 6.1 Agent Types

| Term | Definition |
|------|------------|
| **PaperScout** | Subagent for proactive ArXiv paper discovery with email notifications |
| **PaperLens** | Subagent for reactive local PDF analysis with similarity ranking |

### 6.2 Paper Types

| Term | Definition |
|------|------------|
| **ArxivPaper** | Paper fetched from ArXiv API with arxiv_id, pdf_url, published_date |
| **ZoteroPaper** | Paper from user's Zotero library with zotero_item_key, collection_paths |
| **AcademicPaper** | Generic paper representation with file_metadata, paper_metadata, content |
| **ScoredPaper** | Any paper type with attached relevance score |

### 6.3 Processing Terms

| Term | Definition |
|------|------------|
| **Discovery** | Finding new papers from external sources (ArXiv) |
| **Analysis** | Extracting content/metadata from papers (PDF parsing) |
| **Ranking** | Ordering papers by relevance score |
| **Notification** | Delivering results to user (email, CLI output) |
| **Caching** | Storing API results to avoid redundant fetches |
| **Deduplication** | Preventing duplicate processing/notification of same paper |

### 6.4 Framework Integration Terms

| Term | Definition |
|------|------------|
| **Plugin** | soothe_sdk module registered via `@plugin` decorator |
| **Subagent** | Agent factory registered via `@subagent` decorator |
| **AsyncPersistStore** | soothe protocol for async key-value persistence |
| **SubagentEvent** | Base class for all agent-emitted events |
| **VerbosityTier** | Event visibility level (NORMAL, DEBUG, VERBOSE) |

---

## 7. System-Wide Invariants

All subagents and components MUST respect these invariants:

### 7.1 Execution Invariants

| ID | Invariant | Consequence of Violation |
|----|-----------|-------------------------|
| INV-001 | A workflow MUST NOT crash on external API failure | User loses all progress; no graceful recovery |
| INV-002 | A workflow MUST emit events for each node execution | Observability gaps; debugging impossible |
| INV-003 | A workflow MUST accumulate errors in state.errors, not raise exceptions | Workflow terminates unexpectedly |
| INV-004 | A single item failure MUST NOT abort batch processing | All work lost for one bad input |

### 7.2 Data Invariants

| ID | Invariant | Consequence of Violation |
|----|-----------|-------------------------|
| INV-005 | Storage MUST use user_id for key isolation | Data leakage between users |
| INV-006 | Cached data MUST include timestamp for freshness checks | Stale data used indefinitely |
| INV-007 | Notification records MUST prevent duplicate delivery | User receives spam |
| INV-008 | Paper deduplication MUST use stable identifiers (arxiv_id, md5_hash) | Same paper processed multiple times |

### 7.3 Configuration Invariants

| ID | Invariant | Consequence of Violation |
|----|-----------|-------------------------|
| INV-009 | All config MUST be Pydantic BaseModel with validation | Invalid configs accepted silently |
| INV-010 | Missing optional config MUST use documented defaults | Unpredictable behavior |
| INV-011 | Sensitive config (API keys) MUST come from environment/secrets | Credentials leaked in files |

### 7.4 Output Invariants

| ID | Invariant | Consequence of Violation |
|----|-----------|-------------------------|
| INV-012 | PaperScout MUST send exactly one email per successful run | Missing or duplicate notifications |
| INV-013 | PaperLens MUST return results in state.response_content | Results lost; no user visibility |
| INV-014 | Empty results MUST be handled per config (send_empty, output_format) | Confusing user experience |

---

## 8. Architectural Constraints

### 8.1 Dependency Direction

```
User Config → Plugin Entry → Subagent Factory → Workflow Graph → Nodes → Foundation Modules
```

- Leaf modules MAY depend on Middle and Foundation
- Middle modules MAY depend on Foundation
- Foundation modules MUST NOT depend on Middle or Leaf
- No circular dependencies allowed

### 8.2 Framework Integration Requirements

| Requirement | Rule |
|-------------|------|
| Plugin registration | MUST use `@plugin` decorator with name, version, dependencies |
| Subagent factory | MUST use `@subagent` decorator with name, description, model |
| State type | MUST be TypedDict compatible with LangGraph |
| Event types | MUST inherit from soothe_sdk SubagentEvent |
| Storage interface | MUST use AsyncPersistStore protocol (load/save) |

### 8.3 CLI Interface Constraints

| Constraint | Rule |
|------------|------|
| Entry point | MUST be invokable via `python -m alithia_agent` |
| Subagent selection | MUST support `--subagent <name>` flag |
| Config path | MUST support `--config <path>` flag |
| Output | MUST write to stdout/stderr, not implicit files |

---

## 9. Relationship to Other RFCs

This RFC is the foundational conceptual spec. All other RFCs depend on it:

| RFC | Relationship |
|-----|--------------|
| RFC-001-paperlens-workflow | Implements PaperLens subagent per conceptual model |
| RFC-003-paperscout-workflow | Implements PaperScout subagent per conceptual model |
| RFC-004-storage-layer | Implements Storage abstraction per invariants |

---

## 10. Open Questions

None. Core conceptual decisions are settled.

---

## 11. Conclusion

Alithia-agent is a CLI research assistant with two complementary subagents: PaperScout for proactive discovery and PaperLens for reactive analysis. The system is built on soothe framework patterns, uses local SQLite storage, and enforces strict invariants for reliability and observability.

> **Alithia-agent treats research workflows as independent, event-emitting pipelines — each subagent owns its data sources, processing logic, and output mechanism while sharing a common storage layer and configuration pattern.**
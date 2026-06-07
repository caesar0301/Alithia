# RFC-009-soothe-integration: Soothe Framework Integration Architecture

**Status**: Draft
**Authors**: Claude, Xiaming Chen
**Created**: 2026-06-07
**Last Updated**: 2026-06-07
**Depends on**: RFC-002-world-view, RFC-007-plugin-integration
**Supersedes**: ---
**Stage**: Core
**Kind**: Architecture Design

---

## 1. Abstract

Alithia-agent transforms from a standalone CLI with direct subagent invocation into a branded wrapper around soothe's full agent framework. Paperscout and paperlens become soothe plugins registered via `@plugin/@subagent` decorators, enabling intent-based routing through soothe's goal engine. This architecture maintains alithia's domain-specific configuration and CLI branding while leveraging soothe's complete agentic capabilities including goal-driven orchestration, tool integration, and subagent delegation.

---

## 2. Scope and Non-Goals

### 2.1 Scope

This RFC defines:

* Directory layout with soothe runtime under `~/.alithia/soothe/`
* AlithiaAgent wrapper class that sets `SOOTHE_HOME` and registers plugins
* Plugin registration pattern using soothe's global registry
* Dual configuration: alithia domain config + standard soothe config
* CLI integration with prompt-based interface and intent routing
* Storage integration implementing soothe's `AsyncPersistStore` protocol

### 2.2 Non-Goals

This RFC does **not** define:

* Soothe framework internals (plugin lifecycle, goal engine) - these are soothe's responsibility
* Changes to paperscout/paperlens workflow logic - only registration pattern changes
* Multi-user or deployment scenarios - single-user CLI remains the scope
* Custom soothe middlewares or policy extensions

---

## 3. Background & Motivation

### 3.1 Current Implementation Gap

RFC-007 defined alithia's integration with soothe as plugins using `@plugin/@subagent` decorators. However, the current implementation:

- Has standalone CLI that directly invokes subagent workflows via `--subagent <name>`
- Paperscout/paperlens implemented as independent LangGraph workflows
- Bypasses soothe's plugin system and agent orchestration entirely
- Does not leverage soothe's goal engine, tool dispatch, or subagent routing
- Limited to direct invocation, no intent-based routing

### 3.2 Desired Architecture

Alithia-agent should:

- Use soothe's full agent loop for goal-driven orchestration
- Register paperscout/paperlens as discoverable soothe plugins
- Enable intent-based routing (user says "find new papers" → paperscout)
- Keep alithia's branded CLI entry point and domain configuration
- Maintain separation between alithia domain config and soothe framework config

---

## 4. Architecture Overview

### 4.1 System Context

```
┌─────────────────────────────────────────────────────────────┐
│                         User                                  │
│  (Researcher with natural language requests)                 │
└─────────────────────────────────────────────────────────────┘
                          │
                          │ "Find new papers about transformers"
                          ▼
┌─────────────────────────────────────────────────────────────┐
│                    alithia-agent CLI                          │
│                                                               │
│  ┌─────────────────────────────────────────────────────┐    │
│  │              AlithiaAgent Wrapper                    │    │
│  │  - Sets SOOTHE_HOME=~/.alithia/soothe/               │    │
│  │  - Loads alithia config.yml                          │    │
│  │  - Registers plugins in soothe global registry       │    │
│  └─────────────────────────────────────────────────────┘    │
│                          │                                    │
│                          ▼                                    │
│  ┌─────────────────────────────────────────────────────┐    │
│  │              soothe CoreAgent                        │    │
│  │  - Goal engine analyzes intent                       │    │
│  │  - Routes to subagent via trigger matching           │    │
│  │  - Delegates: task(paperscout, "...")                │    │
│  └─────────────────────────────────────────────────────┘    │
│                          │                                    │
│          ┌───────────────┴───────────────┐                   │
│          ▼                               ▼                   │
│  ┌──────────────┐                ┌──────────────┐            │
│  │  paperscout  │                │  paperlens   │            │
│  │   plugin     │                │   plugin     │            │
│  └──────────────┘                └──────────────┘            │
│          │                               │                   │
│          └───────────────┬───────────────┘                   │
│                          ▼                                    │
│  ┌─────────────────────────────────────────────────────┐    │
│  │         AlithiaStore (AsyncPersistStore)            │    │
│  │         SQLite at ~/.alithia/data/alithia.db        │    │
│  └─────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────┘
                          │
          ┌───────────────┼───────────────┐
          ▼               ▼               ▼
    ┌──────────┐   ┌──────────┐   ┌──────────┐
    │  ArXiv   │   │  Zotero  │   │   SMTP   │
    │   API    │   │   API    │   │  Server  │
    └──────────┘   └──────────┘   └──────────┘
```

### 4.2 Component Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                     ~/.alithia/                               │
│                                                               │
│  config.yml ──────────────────────────────────────────┐      │
│  (alithia domain config)                               │      │
│                                                        │      │
│  data/                                                 │      │
│  └── alithia.db ───────────────────────────────────┐  │      │
│      (SQLite storage)                               │  │      │
│                                                     │  │      │
│  soothe/ (SOOTHE_HOME)                              │  │      │
│  ├── config/                                        │  │      │
│  │   └── config.yml ─────────────────────────────┐ │  │      │
│  │       (soothe framework config)               │ │  │      │
│  │                                               │ │  │      │
│  ├── logs/                                       │ │  │      │
│  │   └── soothe.log                              │ │  │      │
│  │                                               │ │  │      │
│  └── workspace/                                  │ │  │      │
│                                                  │ │  │      │
└──────────────────────────────────────────────────┴─┴─┴──────┘
                                                   │ │ │
                                                   │ │ │
┌──────────────────────────────────────────────────┴─┴─┴──────┐
│                   alithia_agent/                              │
│                                                               │
│  __main__.py (CLI entry)                                      │
│       │                                                       │
│       ▼                                                       │
│  agent.py (AlithiaAgent)                                      │
│       │                                                       │
│       ├─── config/loader.py                                   │
│       │                                                       │
│       ├─── plugins/__init__.py                                │
│       │    ├─── paperscout/                                   │
│       │    │    ├── @plugin, @subagent decorators            │
│       │    │    ├── implementation.py (LangGraph workflow)   │
│       │    │    └── events.py (SubagentEvent classes)        │
│       │    └─── paperlens/                                    │
│       │         ├── @plugin, @subagent decorators            │
│       │         ├── implementation.py (LangGraph workflow)   │
│       │         └── events.py (SubagentEvent classes)        │
│       │                                                       │
│       └─── storage/__init__.py                                │
│            └── AlithiaStore (AsyncPersistStore impl)         │
│                                                               │
└───────────────────────────────────────────────────────────────┘
```

---

## 5. Components

### 5.1 AlithiaAgent Wrapper

**Responsibility**: Initialize soothe environment, load configs, register plugins, and provide execution interface.

The `AlithiaAgent` class wraps soothe's `CoreAgent` with alithia-specific initialization:

```python
class AlithiaAgent:
    """Alithia research assistant powered by soothe framework."""

    def __init__(self, config_path: str | None = None) -> None:
        # 1. Set SOOTHE_HOME before any soothe imports
        self._setup_soothe_environment()

        # 2. Load alithia domain config
        self._alithia_config = load_alithia_config(config_path)

        # 3. Register plugins in soothe's global registry
        register_alithia_plugins()

        # 4. Load soothe config from SOOTHE_HOME
        self._soothe_config = SootheConfig.from_file(...)

        # 5. Create CoreAgent (plugins loaded from global registry)
        self._core_agent = create_soothe_agent(self._soothe_config, ...)

    async def run(self, user_input: str, ...) -> AsyncIterator[Any]:
        return self._core_agent.astream(user_input, ...)
```

### 5.2 Plugin Registration

**Responsibility**: Register paperscout/paperlens in soothe's global registry for goal engine discovery.

Alithia uses explicit in-app registration via soothe's global registry:

```python
def register_alithia_plugins() -> None:
    """Register alithia plugins in soothe's global registry."""
    registry = get_global_registry()

    registry.register(PaperScoutPlugin._plugin_manifest, source="config", priority=30)
    registry.register(PaperLensPlugin._plugin_manifest, source="config", priority=30)
```

The global registry is used by soothe's `AgentBuilder._load_plugins()`, so plugins registered here are automatically discovered when `create_soothe_agent()` is called.

### 5.3 Plugin Classes (paperscout/paperlens)

**Responsibility**: Provide subagent factories with trigger definitions for intent routing.

Each plugin uses `@plugin/@subagent` decorators from `soothe_sdk`:

```python
@plugin(name="paperscout", version="1.0.0", ...)
class PaperScoutPlugin:
    @subagent(
        name="paperscout",
        description="ArXiv paper recommendation agent...",
        triggers=["new papers", "arxiv", "paper digest", "daily papers"],
    )
    async def create_subagent(self, model, config, context, **kwargs):
        return create_paperscout_subagent(...)
```

Trigger definitions enable intent-based routing:
- paperscout triggers: "new papers", "arxiv", "paper digest", "daily papers"
- paperlens triggers: "rank papers", "analyze pdf", "similar papers", "local papers"

### 5.4 AlithiaStore

**Responsibility**: Provide async key-value storage implementing soothe's `AsyncPersistStore` protocol.

```python
class AlithiaStore:
    """SQLite storage implementing AsyncPersistStore."""

    async def load(self, key: str) -> Any | None: ...
    async def save(self, key: str, value: Any) -> None: ...
    async def delete(self, key: str) -> None: ...
    async def list_keys(self, prefix: str) -> list[str]: ...
```

Key namespace: `alithia:{user_id}:{subagent}:{key_type}:{identifier}`

---

## 6. Data Flow

### 6.1 Primary Flow

```
User Prompt → CLI → AlithiaAgent.run() → CoreAgent.astream()
                                              │
                                      Goal Engine analyzes intent
                                              │
                              Matches trigger → routes to subagent
                                              │
                         paperscout/paperlens workflow executes
                                              │
                                  Results stream back to user
```

### 6.2 Flow Description

1. **CLI Entry**: User provides natural language prompt via CLI
2. **AlithiaAgent Initialization**: Sets `SOOTHE_HOME`, loads configs, registers plugins
3. **CoreAgent Creation**: `create_soothe_agent()` loads plugins from global registry
4. **Intent Analysis**: Goal engine classifies user intent, matches trigger keywords
5. **Subagent Delegation**: `task(paperscout, "Find new papers...")` invoked
6. **Workflow Execution**: Subagent's LangGraph workflow runs with alithia config
7. **Result Stream**: Output events stream back through soothe to CLI

---

## 7. Invariants and Constraints

### 7.1 Architectural Invariants

| Invariant | Meaning | Consequence of Violation |
|-----------|---------|------------------------|
| ENV-001 | `SOOTHE_HOME` must be set before any soothe imports | Soothe uses default `~/.soothe/` instead of `~/.alithia/soothe/` |
| REG-001 | Plugins must be registered before `create_soothe_agent()` | Subagents not available for goal engine routing |
| CFG-001 | Alithia config values passed via kwargs to subagent factories | Subagents use incorrect/missing configuration |
| STR-001 | Storage keys must include `user_id` prefix | Data leakage between users |

### 7.2 Dependency Constraints

| Constraint | Rule |
|------------|------|
| soothe import order | `SOOTHE_HOME` set before importing any soothe modules |
| Plugin priority | alithia plugins use `priority=30` (PRIORITY_CONFIG level) |
| Config separation | Alithia domain config separate from soothe framework config |
| Storage protocol | AlithiaStore must implement all `AsyncPersistStore` methods |

---

## 8. Abstract Schemas

### 8.1 Alithia Domain Config Schema

```yaml
paperscout:
  arxiv_categories: list[str]    # e.g., ["cs.AI", "cs.LG"]
  max_papers_per_digest: int     # default: 10
  lookback_days: int             # default: 7
  email:
    enabled: bool
    recipient: str
  zotero:
    library_id: str
    api_key: str                 # from environment

paperlens:
  default_pdf_path: str
  max_results: int               # default: 50
  recursive_scan: bool           # default: true

storage:
  user_id: str                   # default: "default"
```

### 8.2 Soothe Framework Config Schema

```yaml
providers:
  openai:
    api_key: str                 # from ${OPENAI_API_KEY}
  anthropic:
    api_key: str                 # from ${ANTHROPIC_API_KEY}

models:
  default: str                   # e.g., "openai:gpt-4o-mini"

subagents:
  paperscout:
    enabled: bool
    triggers: list[str]
  paperlens:
    enabled: bool
    triggers: list[str]

tools: list[str]                 # e.g., ["execution", "file_ops", "websearch"]

memory:
  enabled: bool                  # default: false

planner:
  enabled: bool                  # default: true
```

---

## 9. Relationship to Other RFCs

| RFC | Relationship |
|-----|--------------|
| RFC-002-world-view | Extends conceptual model with soothe integration |
| RFC-007-plugin-integration | Implements plugin registration using soothe_sdk decorators |
| RFC-001-paperlens-workflow | PaperLens workflow unchanged, only registration pattern changes |
| RFC-003-paperscout-workflow | PaperScout workflow unchanged, only registration pattern changes |
| RFC-004-storage-layer | Storage adapted to implement `AsyncPersistStore` protocol |
| RFC-005-cli-interface | CLI changes from direct invocation to prompt-based interface |
| RFC-006-configuration | Config extends with dual config files |

---

## 10. Open Questions

None. All design decisions are resolved based on user feedback:

1. Integration mode: Branded CLI wrapper ✓
2. Plugin discovery: Explicit in-app registration via global registry ✓
3. Execution mode: Full soothe agent loop ✓
4. Routing mode: Intent-based with trigger definitions ✓
5. Directory layout: Soothe under `~/.alithia/soothe/` ✓
6. Config format: YAML for both alithia and soothe configs ✓

---

## 11. Conclusion

Alithia-agent becomes a branded wrapper around soothe's full agent framework:

1. **Directory structure**: Soothe runtime under `~/.alithia/soothe/`, alithia domain config in `~/.alithia/config.yml`
2. **Plugin system**: Paperscout/paperlens registered explicitly in soothe's global registry via `@plugin/@subagent` decorators
3. **Execution**: User prompts flow through soothe's goal engine with intent-based routing
4. **Storage**: SQLite implements `AsyncPersistStore` for soothe compatibility
5. **CLI**: Prompt-based interface with optional `--subagent` override

> **Alithia-agent wraps soothe's CoreAgent, registers paperscout/paperlens in the global registry, and enables intent-based routing through soothe's goal engine — maintaining alithia's branding and domain configuration while leveraging full agentic capabilities.**
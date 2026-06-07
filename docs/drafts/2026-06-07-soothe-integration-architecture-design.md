# Soothe Integration Architecture Design

**Status**: Draft
**Created**: 2026-06-07
**Topic**: Refining alithia-agent architecture as a branded wrapper of soothe framework with paperscout/paperlens as plugin subagents

---

## 1. Abstract

Alithia-agent transforms from a standalone CLI with direct subagent invocation into a branded wrapper around soothe's full agent framework. Paperscout and paperlens become soothe plugins that the goal engine can route to automatically based on user intent. This design maintains alithia's domain-specific configuration and branding while leveraging soothe's complete agentic capabilities including goal-driven orchestration, tool integration, and subagent delegation.

---

## 2. Problem Statement

### 2.1 Current Implementation Gap

The current alithia-agent implementation:
- Has standalone CLI that directly invokes subagent workflows
- Paperscout/paperlens implemented as independent LangGraph workflows
- Bypasses soothe's plugin system and agent orchestration entirely
- Does not leverage soothe's goal engine, tool dispatch, or subagent routing
- Limited to direct invocation (`--subagent paperscout`), no intent-based routing

### 2.2 Desired Architecture

Alithia-agent should:
- Use soothe's full agent loop for goal-driven orchestration
- Register paperscout/paperlens as discoverable soothe plugins
- Enable intent-based routing (user says "find new papers" → paperscout)
- Keep alithia's branded CLI entry point and domain configuration
- Maintain separation between alithia domain config and soothe framework config

---

## 3. Design Decisions

### 3.1 Integration Mode: Branded CLI Wrapper

**Decision**: alithia-agent keeps its own CLI entry point (`alithia-agent`) but internally uses soothe's `CoreAgent` and goal engine for orchestration.

**Rationale**: Provides clean separation where alithia owns configuration and branding while leveraging soothe's full capabilities. Avoids tight coupling to soothe internals while enabling intent-based routing.

### 3.2 Plugin Discovery: Explicit In-App Registration

**Decision**: Paperscout and paperlens are registered explicitly at startup via `PluginRegistry.register()`, not discovered through entry points or filesystem.

**Rationale**: Simpler development workflow, no pip install required for testing, predictable plugin loading. Works with soothe's existing registry infrastructure.

### 3.3 Execution Mode: Full Soothe Agent Loop

**Decision**: User input flows through soothe's full goal engine, which analyzes intent and delegates to appropriate subagents.

**Rationale**: Enables intent-based routing without explicit subagent selection. Users can say "find new papers" and soothe routes to paperscout automatically.

### 3.4 Routing Mode: Intent-Based with Trigger Definitions

**Decision**: Subagent triggers are defined via `@subagent` decorator's `triggers` parameter. Soothe's goal engine matches user intent to subagent triggers.

**Rationale**: Automatic routing based on natural language intent. Users don't need to know subagent names. Triggers like "new papers", "arxiv" route to paperscout; "rank papers", "analyze pdf" route to paperlens.

---

## 4. Directory Layout

### 4.1 Home Directory Structure

```
~/.alithia/
├── config.yml              # Alithia domain config (categories, email, zotero)
├── data/
│   └── alithia.db          # SQLite for papers, notifications, scores
├── soothe/                  # Soothe runtime environment (SOOTHE_HOME)
│   ├── config/
│   │   └── config.yml      # Standard soothe config (models, tools, subagents)
│   ├── logs/
│   │   └── soothe.log      # Soothe framework logs
│   └── workspace/          # Soothe workspace directory (optional)
```

### 4.2 Rationale for Separation

- **Soothe runtime isolation**: Soothe uses its standard config format under its own `SOOTHE_HOME`, ensuring compatibility with soothe's conventions
- **Alithia domain ownership**: Alithia-specific settings (categories, email, zotero) stay in alithia's config, avoiding config format conflicts
- **Storage independence**: Alithia's SQLite storage (`alithia.db`) implements soothe's `AsyncPersistStore` protocol but maintains its own schema

---

## 5. Module Structure

### 5.1 Package Layout

```
alithia_agent/
├── __init__.py              # ALITHIA_HOME, SOOTHE_HOME constants
├── __main__.py              # CLI entry (branded soothe interface)
├── agent.py                 # AlithiaAgent wrapper class
├── config/
│   ├── __init__.py
│   ├── loader.py            # Config loading with SOOTHE_HOME setup
│   └ schema.py              # Alithia domain config schema (Pydantic)
├── plugins/
│   ├── __init__.py          # register_alithia_plugins() function
│   ├── paperscout/
│   │   ├── __init__.py      # @plugin/@subagent decorators, exports
│   │   ├── implementation.py # LangGraph workflow (adapted from existing)
│   │   ├── events.py        # SubagentEvent classes for soothe
│   │   ├── state.py         # Config/State TypedDicts
│   │   └ nodes.py           # Workflow nodes
│   │   ├── schemas.py       # Input/output schemas
│   ├── paperlens/
│   │   ├── __init__.py      # @plugin/@subagent decorators, exports
│   │   ├── implementation.py # LangGraph workflow (adapted from existing)
│   │   ├── events.py        # SubagentEvent classes for soothe
│   │   ├── state.py         # Config/State TypedDicts
│   │   └ nodes.py           # Workflow nodes
│   │   ├── schemas.py       # Input/output schemas
├── storage/
│   ├── __init__.py          # Storage initialization, AsyncPersistStore impl
│   ├── sqlite.py            # SQLite backend (adapted for soothe protocol)
├── models/
│   ├── __init__.py
│   ├── papers.py            # Paper data models (existing)
│   ├── metadata.py          # Metadata models (existing)
```

### 5.2 Key Changes from Current Structure

- **`agent.py`**: New file, the `AlithiaAgent` wrapper class
- **`plugins/`**: New directory, replaces `paperscout/` and `paperlens/` as direct children
- **`__main__.py`**: Refactored from direct invocation to prompt-based interface
- **`config/loader.py`**: Enhanced to set `SOOTHE_HOME` before soothe imports
- **`storage/`**: Adapted to implement soothe's `AsyncPersistStore` protocol

---

## 6. Configuration

### 6.1 Alithia Domain Config (`~/.alithia/config.yml`)

```yaml
# Alithia domain-specific settings
paperscout:
  arxiv_categories:
    - cs.AI
    - cs.LG
  max_papers_per_digest: 10
  lookback_days: 7
  email:
    enabled: true
    recipient: user@example.com
  zotero:
    library_id: "12345"
    api_key: ${ZOTERO_API_KEY}

paperlens:
  default_pdf_path: ~/papers
  max_results: 50
  recursive_scan: true

storage:
  user_id: default
```

### 6.2 Soothe Framework Config (`~/.alithia/soothe/config/config.yml`)

```yaml
# Standard soothe configuration
providers:
  openai:
    api_key: ${OPENAI_API_KEY}
  anthropic:
    api_key: ${ANTHROPIC_API_KEY}

models:
  default: openai:gpt-4o-mini

subagents:
  paperscout:
    enabled: true
    triggers:
      - "new papers"
      - "arxiv"
      - "paper digest"
      - "daily papers"
      - "research papers"
  paperlens:
    enabled: true
    triggers:
      - "rank papers"
      - "analyze pdf"
      - "similar papers"
      - "local papers"
      - "find relevant"

tools:
  - execution
  - file_ops
  - websearch

memory:
  enabled: false

planner:
  enabled: true
```

### 6.3 Config Loading Sequence

1. `AlithiaAgent.__init__()` sets `SOOTHE_HOME=~/.alithia/soothe/`
2. Load alithia domain config from `~/.alithia/config.yml`
3. Soothe loads its config from `$SOOTHE_HOME/config/config.yml`
4. Alithia domain config values are passed to subagent factories via kwargs

---

## 7. Plugin Implementation

### 7.1 Plugin Registration Pattern

Alithia uses explicit in-app registration rather than soothe's automatic discovery. The registration connects to soothe's plugin system via the global registry:

```python
# alithia_agent/plugins/__init__.py
from soothe.plugin import PluginRegistry
from soothe.plugin.global_registry import get_global_registry

def register_alithia_plugins() -> None:
    """Explicitly register alithia plugins in soothe's global registry."""
    from alithia_agent.plugins.paperscout import PaperScoutPlugin
    from alithia_agent.plugins.paperlens import PaperLensPlugin

    # Get soothe's global registry (used by AgentBuilder._load_plugins)
    registry = get_global_registry()

    # Register plugin manifests directly
    registry.register(
        PaperScoutPlugin._plugin_manifest,
        source="config",
        priority=30,  # PRIORITY_CONFIG level
    )
    registry.register(
        PaperLensPlugin._plugin_manifest,
        source="config",
        priority=30,
    )
```

This pattern leverages soothe's `global_registry` which `AgentBuilder._load_plugins()` uses for plugin loading. By registering directly in the global registry, alithia's plugins are automatically picked up when `create_soothe_agent()` calls `_load_plugins()`.

**Connection to soothe's Plugin Lifecycle:**

1. `AlithiaAgent.__init__()` calls `register_alithia_plugins()` first
2. Plugins registered in soothe's global registry
3. `create_soothe_agent()` → `AgentBuilder._load_plugins()` → `load_plugins(config)`
4. `load_plugins()` uses global registry to discover already-registered plugins
5. PluginLifecycleManager instantiates plugin classes, calls `on_load()`, extracts subagents

### 7.2 Paperscout Plugin

```python
# alithia_agent/plugins/paperscout/__init__.py
from soothe_sdk.plugin import plugin, subagent
from typing import Any

from .implementation import create_paperscout_subagent
from .state import PaperScoutConfig
from . import events as _events  # noqa: F401 — register event types

__all__ = ["PaperScoutPlugin", "create_paperscout_subagent"]


@plugin(
    name="paperscout",
    version="1.0.0",
    description="ArXiv paper recommendation agent using Zotero library analysis",
    dependencies=[
        "langgraph>=0.2.0",
        "arxiv>=2.0.0",
        "sentence-transformers>=2.2.0",
        "pyzotero>=1.5.0",
    ],
    trust_level="standard",
)
class PaperScoutPlugin:
    """PaperScout plugin for ArXiv paper recommendations."""

    async def on_load(self, context: Any) -> None:
        """Validate dependencies."""
        context.logger.info("Loading PaperScout plugin v1.0.0")

    @subagent(
        name="paperscout",
        description=(
            "ArXiv paper recommendation agent that delivers personalized daily "
            "paper recommendations by analyzing your Zotero library and ranking "
            "newly published papers by relevance."
        ),
        triggers=["new papers", "arxiv", "paper digest", "daily papers", "research papers"],
    )
    async def create_subagent(
        self,
        model: Any,
        config: Any,
        context: Any,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Create PaperScout subagent."""
        # Extract alithia-specific config from kwargs
        alithia_config = kwargs.get("alithia_config")
        if alithia_config and "paperscout" in alithia_config:
            paperscout_config = PaperScoutConfig(**alithia_config["paperscout"])
        else:
            paperscout_config = PaperScoutConfig()

        store = kwargs.get("store")
        user_id = kwargs.get("user_id", "default")

        return create_paperscout_subagent(
            config=paperscout_config,
            store=store,
            user_id=user_id,
        )
```

### 7.3 PaperLens Plugin

```python
# alithia_agent/plugins/paperlens/__init__.py
from soothe_sdk.plugin import plugin, subagent
from typing import Any

from .implementation import create_paperlens_subagent
from .state import PaperLensConfig
from . import events as _events  # noqa: F401

__all__ = ["PaperLensPlugin", "create_paperlens_subagent"]


@plugin(
    name="paperlens",
    version="1.0.0",
    description="PDF discovery and ranking subagent for local paper analysis",
    dependencies=[
        "langgraph>=0.2.0",
        "docling>=2.0.0",
        "sentence-transformers>=2.2.0",
    ],
    trust_level="standard",
)
class PaperLensPlugin:
    """PaperLens plugin for local PDF analysis."""

    async def on_load(self, context: Any) -> None:
        """Validate dependencies."""
        context.logger.info("Loading PaperLens plugin v1.0.0")

    @subagent(
        name="paperlens",
        description=(
            "Discover relevant academic papers from PDF collections by "
            "semantic similarity matching. Use for local paper analysis."
        ),
        triggers=["rank papers", "analyze pdf", "similar papers", "local papers", "find relevant"],
    )
    async def create_subagent(
        self,
        model: Any,
        config: Any,
        context: Any,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Create PaperLens subagent."""
        alithia_config = kwargs.get("alithia_config")
        if alithia_config and "paperlens" in alithia_config:
            paperlens_config = PaperLensConfig(**alithia_config["paperlens"])
        else:
            paperlens_config = PaperLensConfig()

        user_id = kwargs.get("user_id", "default")

        return create_paperlens_subagent(
            config=paperlens_config,
            llm=model,
            user_id=user_id,
        )
```

### 7.4 Trigger Definitions for Intent Routing

| Subagent | Triggers | Intent Pattern |
|----------|----------|----------------|
| paperscout | new papers, arxiv, paper digest, daily papers, research papers | Proactive discovery, monitoring new publications |
| paperlens | rank papers, analyze pdf, similar papers, local papers, find relevant | Reactive analysis, local PDF processing |

---

## 8. AlithiaAgent Wrapper Class

### 8.1 Class Design

```python
# alithia_agent/agent.py
from pathlib import Path
from typing import Any, AsyncIterator
import os

from soothe.core import CoreAgent, create_soothe_agent
from soothe.config.settings import SootheConfig

from alithia_agent.config import load_alithia_config, AlithiaConfig
from alithia_agent.plugins import register_alithia_plugins


class AlithiaAgent:
    """Alithia research assistant powered by soothe framework.

    Wraps soothe's CoreAgent with alithia-specific initialization:
    - Sets SOOTHE_HOME to ~/.alithia/soothe/
    - Loads alithia domain config from ~/.alithia/config.yml
    - Registers paperscout/paperlens plugins in soothe's global registry
    - Provides branded CLI entry with alithia defaults
    """

    def __init__(self, config_path: str | None = None) -> None:
        """Initialize AlithiaAgent.

        Args:
            config_path: Optional override for alithia config path.
        """
        # Set up soothe environment BEFORE any soothe imports
        self._setup_soothe_environment()

        # Load alithia domain config
        self._alithia_config = load_alithia_config(config_path)

        # Register alithia plugins in soothe's global registry
        # This happens BEFORE create_soothe_agent() calls _load_plugins()
        register_alithia_plugins()

        # Load soothe config (from SOOTHE_HOME/config/config.yml)
        self._soothe_config = SootheConfig.from_file(
            Path(os.environ["SOOTHE_HOME"]) / "config" / "config.yml"
        )

        # Create soothe CoreAgent (plugins loaded from global registry)
        self._core_agent = self._create_core_agent()

    def _setup_soothe_environment(self) -> None:
        """Set SOOTHE_HOME to ~/.alithia/soothe/"""
        alithia_home = Path.home() / ".alithia"
        soothe_home = alithia_home / "soothe"

        # Create directories
        soothe_home.mkdir(parents=True, exist_ok=True)
        (soothe_home / "config").mkdir(exist_ok=True)
        (soothe_home / "logs").mkdir(exist_ok=True)

        # Set environment variable BEFORE soothe imports
        os.environ["SOOTHE_HOME"] = str(soothe_home)

    def _create_core_agent(self) -> CoreAgent:
        """Create soothe CoreAgent with alithia plugins registered."""
        # Pass registry to agent builder so plugins are available
        return create_soothe_agent(
            self._soothe_config,
            # Additional kwargs passed to subagent factories
            alithia_config=self._alithia_config.model_dump(),
            store=self._create_store(),
            user_id=self._alithia_config.storage.user_id,
        )

    def _create_store(self) -> Any:
        """Create storage implementing AsyncPersistStore."""
        from alithia_agent.storage import AlithiaStore
        return AlithiaStore(self._alithia_config.storage.user_id)

    async def run(
        self,
        user_input: str,
        *,
        thread_id: str | None = None,
        stream_mode: list[str] | None = None,
    ) -> AsyncIterator[Any]:
        """Run user input through soothe's agent loop.

        Args:
            user_input: Natural language input from user.
            thread_id: Optional thread identifier for persistence.
            stream_mode: Optional stream mode configuration.

        Returns:
            AsyncIterator of stream events from soothe execution.
        """
        config = {}
        if thread_id:
            config["configurable"] = {"thread_id": thread_id}

        return self._core_agent.astream(
            user_input,
            config,
            stream_mode=stream_mode,
        )

    @classmethod
    def create(cls, config_path: str | None = None) -> AlithiaAgent:
        """Factory method for AlithiaAgent."""
        return cls(config_path)
```

### 8.2 Initialization Sequence

1. Set `SOOTHE_HOME=~/.alithia/soothe/` (before any soothe imports)
2. Create soothe directory structure if missing
3. Load alithia domain config from `~/.alithia/config.yml`
4. Register paperscout/paperlens in soothe's global registry
5. Load soothe config from `$SOOTHE_HOME/config/config.yml`
6. Call `create_soothe_agent()` which:
   - Calls `AgentBuilder._load_plugins()` → `load_plugins(config)`
   - `load_plugins()` discovers plugins from global registry
   - PluginLifecycleManager instantiates registered plugins
   - Subagent factories extracted and added to CoreAgent
7. Ready for execution via `run(user_input)`

---

## 9. CLI Integration

### 9.1 New CLI Interface

```python
# alithia_agent/__main__.py
import argparse
import asyncio
import sys
from typing import Any

from alithia_agent.agent import AlithiaAgent


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        prog="alithia-agent",
        description="CLI research assistant powered by soothe framework",
    )

    parser.add_argument(
        "prompt",
        type=str,
        nargs="?",
        help="Natural language prompt for the research assistant",
    )
    parser.add_argument(
        "--config",
        type=str,
        default=None,
        help="Alithia config file path (default: ~/.alithia/config.yml)",
    )
    parser.add_argument(
        "--subagent",
        choices=["paperscout", "paperlens"],
        default=None,
        help="Explicitly invoke a specific subagent",
    )
    parser.add_argument(
        "--thread-id",
        type=str,
        default=None,
        help="Thread identifier for persistence",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Show detailed progress",
    )
    parser.add_argument(
        "--output",
        choices=["stdout", "json", "none"],
        default="stdout",
        help="Output format",
    )

    return parser.parse_args()


async def main_async() -> int:
    """Async main entry point."""
    args = parse_args()

    if not args.prompt:
        print("ERROR: Please provide a prompt")
        print("Example: alithia-agent 'Find new papers about transformers'")
        return 1

    # Create alithia agent
    agent = AlithiaAgent.create(args.config)

    # Run prompt through soothe's agent loop
    result_stream = agent.run(
        user_input=args.prompt,
        thread_id=args.thread_id,
        stream_mode=["messages", "updates"],
    )

    # Process stream
    output_parts = []
    async for chunk in result_stream:
        if args.output == "json":
            output_parts.append(chunk)
        else:
            # Format for stdout
            if isinstance(chunk, dict) and "content" in chunk:
                print(chunk["content"], end="", flush=True)

    if args.output == "json":
        import json
        print(json.dumps(output_parts, indent=2, default=str))

    return 0


def main() -> None:
    """Main entry point."""
    exit_code = asyncio.run(main_async())
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
```

### 9.2 CLI Usage Examples

**Intent-based routing (automatic):**
```bash
# Routes to paperscout (triggers match "new papers", "arxiv")
alithia-agent "Find new papers about reinforcement learning"

# Routes to paperlens (triggers match "rank papers", "analyze pdf")
alithia-agent "Rank my PDFs in ~/research by relevance to quantum computing"

# Routes based on goal engine analysis
alithia-agent "What papers should I read today?"
```

**Explicit subagent invocation:**
```bash
# Force paperscout regardless of intent analysis
alithia-agent --subagent paperscout "Check for new papers"

# Force paperlens
alithia-agent --subagent paperlens "Analyze ~/papers directory"
```

**With options:**
```bash
alithia-agent --config /path/to/config.yml "Find papers"
alithia-agent --thread-id research-session-1 "Analyze papers"
alithia-agent --verbose --output json "Find new papers"
```

---

## 10. Storage Integration

### 10.1 AsyncPersistStore Implementation

```python
# alithia_agent/storage/__init__.py
from typing import Any
from pathlib import Path

from alithia_agent.config import AlithiaConfig


class AlithiaStore:
    """Alithia storage implementing soothe's AsyncPersistStore protocol.

    Wraps SQLite storage with async interface for soothe compatibility.
    """

    def __init__(self, user_id: str) -> None:
        self._db_path = Path.home() / ".alithia" / "data" / "alithia.db"
        self._user_id = user_id
        self._db_path.parent.mkdir(parents=True, exist_ok=True)

    async def load(self, key: str) -> Any | None:
        """Load value by key. Returns None if not found."""
        import json
        full_key = f"{self._user_prefix()}{key}"
        # SQLite query: SELECT value FROM storage WHERE key = ?
        # Deserialize JSON value
        ...

    async def save(self, key: str, value: Any) -> None:
        """Save value with key. Overwrites existing."""
        import json
        full_key = f"{self._user_prefix()}{key}"
        serialized = json.dumps(value)
        # SQLite query: INSERT OR REPLACE INTO storage (key, value) VALUES (?, ?)
        ...

    async def delete(self, key: str) -> None:
        """Delete value by key. No error if not found."""
        full_key = f"{self._user_prefix()}{key}"
        # SQLite query: DELETE FROM storage WHERE key = ?
        ...

    async def list_keys(self, prefix: str) -> list[str]:
        """List all keys matching prefix."""
        full_prefix = f"{self._user_prefix()}{prefix}"
        # SQLite query: SELECT key FROM storage WHERE key LIKE ?
        # Strip user prefix from returned keys
        ...

    def _user_prefix(self) -> str:
        """Get user-specific key prefix."""
        return f"alithia:{self._user_id}:"
```

### 10.2 Key Namespace Convention

All storage keys use user_id prefix for isolation:
- `alithia:{user_id}:paperscout:notifications:{date}`
- `alithia:{user_id}:paperscout:emailed:{arxiv_ids}`
- `alithia:{user_id}:paperlens:parsed:{pdf_hash}`

---

## 11. Data Flow

### 11.1 Execution Flow

```
User Prompt → CLI → AlithiaAgent.run() → CoreAgent.astream()
                                              ↓
                                      Goal Engine analyzes intent
                                              ↓
                              Matches trigger → routes to subagent
                                              ↓
                         paperscout/paperlens workflow executes
                                              ↓
                                  Results stream back to user
```

### 11.2 Intent Routing Decision

```
Goal Engine receives: "Find new papers about transformers"
    ↓
Intent classification: "proactive discovery", "monitoring"
    ↓
Trigger match: paperscout triggers = ["new papers", "arxiv", ...]
    ↓
Delegation: task(paperscout, "Find new papers about transformers")
    ↓
paperscout workflow runs with alithia_config and store
```

---

## 12. Error Handling

### 12.1 Graceful Degradation

Following alithia's existing invariants (RFC-002):

- External API failures (ArXiv, Zotero, SMTP) do NOT crash agent
- Errors accumulated in workflow state, not raised as exceptions
- Partial results returned with error messages
- Soothe's policy enforcement applies to all operations

### 12.2 Plugin Loading Failures

If plugin fails to load:
- soothe emits `PluginFailedEvent`
- agent continues with available tools/subagents
- User sees warning in logs, agent remains functional

---

## 13. Testing Strategy

### 13.1 Unit Tests

- `AlithiaAgent` initialization with mock configs
- Plugin registration verification
- Store implementation with async interface
- Config loading and SOOTHE_HOME setup

### 13.2 Integration Tests

- Full execution flow with soothe goal engine
- Intent routing to correct subagent
- Subagent workflow execution with soothe dispatch
- Storage persistence through soothe protocol

### 13.3 End-to-End Tests

- CLI invocation with various prompts
- Intent-based routing scenarios
- Explicit subagent override scenarios
- Multi-turn conversation threads

---

## 14. Migration Path

### 14.1 From Current Implementation

| Component | Current | New | Migration Action |
|-----------|---------|-----|------------------|
| CLI | `--subagent <name>` direct invoke | Prompt-based with intent routing | Refactor `__main__.py` |
| Config | Single `config.json` | Dual `config.yml` + `soothe/config.yml` | Create soothe config template |
| Plugin system | None | `@plugin/@subagent` decorators | Add decorators to existing modules |
| Agent orchestration | Direct LangGraph invoke | CoreAgent + goal engine | Add `agent.py` wrapper |
| Storage | SQLite direct | AsyncPersistStore protocol | Add async wrapper |

### 14.2 Backward Compatibility

- `--subagent` flag still works for explicit invocation
- Existing config values map to new schema
- Workflow logic unchanged, only registration changes

---

## 15. Dependencies

### 15.1 Required Packages

| Package | Purpose | Version |
|---------|---------|---------|
| `soothe` | Framework orchestration | >=1.0.0 |
| `soothe_sdk` | Plugin decorators | >=1.0.0 |
| `langgraph` | Workflow graphs | >=0.2.0 |
| `pydantic` | Config schemas | >=2.0.0 |

### 15.2 Optional Packages (Subagent-specific)

- `arxiv` - PaperScout ArXiv API
- `pyzotero` - PaperScout Zotero integration
- `sentence-transformers` - Both subagents
- `docling` - PaperLens PDF parsing

---

## 16. Open Questions

None. All design decisions are resolved based on user feedback.

---

## 17. Conclusion

Alithia-agent becomes a branded wrapper around soothe's full agent framework:

1. **Directory structure**: Soothe runtime under `~/.alithia/soothe/`, alithia domain config in `~/.alithia/config.yml`
2. **Plugin system**: Paperscout/paperlens registered explicitly via `@plugin/@subagent` decorators
3. **Execution**: User prompts flow through soothe's goal engine with intent-based routing
4. **Storage**: SQLite implements `AsyncPersistStore` for soothe compatibility
5. **CLI**: Prompt-based interface with optional `--subagent` override

> **Alithia-agent wraps soothe's CoreAgent, registers paperscout/paperlens as plugins, and enables intent-based routing through soothe's goal engine — maintaining alithia's branding and domain configuration while leveraging full agentic capabilities.**
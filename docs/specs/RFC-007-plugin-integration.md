# RFC-007-plugin-integration: Soothe Framework Integration

**Status**: Draft
**Authors**: Claude
**Created**: 2026-06-06
**Last Updated**: 2026-06-06
**Depends on**: RFC-002-world-view
**Supersedes**: ---
**Stage**: Core
**Kind**: Implementation Interface Design

---

## 1. Abstract

Alithia-agent subagents are implemented as soothe framework plugins using the `soothe_sdk` package. This RFC defines the integration contracts: plugin registration via decorators, subagent factory signatures, AsyncPersistStore protocol usage, event emission patterns, and configuration injection mechanisms.

---

## 2. Scope and Non-Goals

### 2.1 Scope

This RFC defines:

* Plugin registration contract (`@plugin` decorator)
* Subagent factory contract (`@subagent` decorator)
* AsyncPersistStore protocol usage
* Event emission patterns and registration
* Configuration and context injection
* Subagent return value contract

### 2.2 Non-Goals

This RFC does **not** define:

* soothe framework internals (outside alithia-agent scope)
* Custom middleware or hooks
* Multi-plugin coordination
* Plugin hot-loading
* soothe CLI integration (soothe handles this)

---

## 3. Background & Motivation

Alithia-agent subagents must integrate with the soothe framework to:
- Be discoverable by soothe's plugin system
- Receive configuration and services from soothe
- Emit events for observability
- Use persistent storage via the framework's protocol

The soohe_sdk package provides:
- `@plugin` decorator for module registration
- `@subagent` decorator for agent factory registration
- `AsyncPersistStore` protocol for storage
- `SubagentEvent` base class for events
- Context objects with services and utilities

---

## 4. Plugin Registration

### 4.1 Plugin Decorator Contract

```python
@plugin(
    name: str,                    # Plugin identifier (unique)
    version: str,                 # Plugin version (semver)
    description: str,             # Human-readable description
    dependencies: list[str],      # Required pip packages
    trust_level: str,             # "standard" or "trusted"
)
class PluginClass:
    """Plugin class with lifecycle hooks."""
    
    async def on_load(self, context: PluginContext) -> None:
        """Called when plugin is loaded. Validate dependencies."""
    
    def get_subagents(self) -> list[Callable]:
        """Return list of subagent factory methods."""
```

### 4.2 PaperScout Plugin Registration

```python
from soothe_sdk.plugin import plugin, subagent

@plugin(
    name="paperscout",
    version="1.0.0",
    description="ArXiv paper recommendation agent using Zotero library analysis",
    dependencies=[
        "langgraph>=0.2.0",
        "arxiv>=2.0.0",
        "sentence-transformers>=2.2.0",
        "pyzotero>=1.5.0",
        "scikit-learn>=1.0.0",
        "numpy>=1.20.0",
    ],
    trust_level="standard",
)
class PaperScoutPlugin:
    """PaperScout community plugin for ArXiv paper recommendations."""

    async def on_load(self, context: PluginContext) -> None:
        """Validate dependencies are installed."""
        context.logger.info("Loading PaperScout plugin...")
        
        missing_deps = []
        for dep in ["arxiv", "sentence_transformers", "pyzotero", "sklearn"]:
            try:
                __import__(dep)
            except ImportError:
                missing_deps.append(dep)
        
        if missing_deps:
            from soothe_sdk.core.exceptions import PluginError
            raise PluginError(f"Missing dependencies: {missing_deps}")
        
        context.logger.info("PaperScout plugin loaded successfully")

    def get_subagents(self) -> list[Callable]:
        return [self.create_paperscout]
```

### 4.3 PaperLens Plugin Registration

```python
@plugin(
    name="paperlens",
    version="1.0.0",
    description="PDF discovery and ranking subagent for soothe",
    dependencies=[
        "langgraph>=0.2.0",
        "docling>=2.0.0",
        "sentence-transformers>=2.2.0",
        "torch>=2.0.0",
    ],
    trust_level="standard",
)
class PaperLensPlugin:
    """PaperLens plugin for local PDF analysis."""

    async def on_load(self, context: PluginContext) -> None:
        """Validate Docling and sentence-transformers available."""
        context.logger.info("Loading PaperLens plugin...")
        
        try:
            import docling
            import sentence_transformers
        except ImportError as e:
            from soothe_sdk.core.exceptions import PluginError
            raise PluginError(f"Missing dependency: {e}")
        
        context.logger.info("PaperLens plugin loaded successfully")

    def get_subagents(self) -> list[Callable]:
        return [self.create_paperlens]
```

---

## 5. Subagent Factory Contract

### 5.1 Subagent Decorator Contract

```python
@subagent(
    name: str,                    # Subagent identifier (unique within plugin)
    description: str,             # Human-readable description
    model: str,                   # Default LLM model for subagent
)
async def create_subagent(
    self,                         # Plugin instance (if method)
    model: Any,                   # Resolved model (BaseChatModel or str)
    config: Any,                  # Soothe configuration object
    context: Any,                 # Plugin context with services
    **kwargs: Any,                # Additional args (user_id, store, etc.)
) -> dict[str, Any]:
    """Create subagent runnable.
    
    Returns:
        {
            "name": str,
            "description": str,
            "runnable": CompiledStateGraph,
            "config": SubagentConfig,  # Optional
        }
    """
```

### 5.2 PaperScout Factory

```python
@subagent(
    name="paperscout",
    description=(
        "ArXiv paper recommendation agent that delivers personalized daily "
        "paper recommendations by analyzing your Zotero library and ranking "
        "newly published papers by relevance."
    ),
    model="openai:gpt-4o-mini",
)
async def create_paperscout(
    self,
    model: Any,
    config: Any,
    context: Any,
    **kwargs: Any,
) -> dict[str, Any]:
    """Create PaperScout subagent."""
    
    # Extract PaperScout config from soothe config
    paperscout_config = None
    if hasattr(config, "subagents") and "paperscout" in config.subagents:
        subagent_config = config.subagents["paperscout"]
        if subagent_config.enabled and subagent_config.config:
            paperscout_config = PaperScoutConfig(**subagent_config.config)
    
    if not paperscout_config:
        paperscout_config = PaperScoutConfig()  # Use defaults
    
    # Get storage from context or kwargs
    store = kwargs.get("store")
    if not store and hasattr(config, "services"):
        store = config.services.get("persistence")
    if not store:
        raise ValueError("PaperScout requires AsyncPersistStore")
    
    # Get user ID
    user_id = kwargs.get("user_id", "default")
    
    # Create subagent
    return create_paperscout_subagent(
        config=paperscout_config,
        store=store,
        user_id=user_id,
    )
```

### 5.3 PaperLens Factory

```python
@subagent(
    name="paperlens",
    description=(
        "Discover relevant academic papers from PDF collections by "
        "semantic similarity matching. Use for local paper analysis."
    ),
    model="openai:gpt-4o-mini",
)
async def create_paperlens(
    self,
    model: Any,
    config: Any,
    context: Any,
    **kwargs: Any,
) -> dict[str, Any]:
    """Create PaperLens subagent."""
    
    # Extract config
    paperlens_config = None
    if hasattr(config, "subagents") and "paperlens" in config.subagents:
        subagent_config = config.subagents["paperlens"]
        if subagent_config.enabled and subagent_config.config:
            paperlens_config = PaperLensConfig(**subagent_config.config)
    
    if not paperlens_config:
        paperlens_config = PaperLensConfig()
    
    # Get user ID
    user_id = kwargs.get("user_id", "default")
    
    # Create subagent with LLM for metadata enhancement
    return create_paperlens_subagent(
        config=paperlens_config,
        llm=model,
        user_id=user_id,
    )
```

---

## 6. AsyncPersistStore Protocol

### 6.1 Protocol Definition

```python
from typing import Protocol, Any

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

### 6.2 Usage in Subagents

```python
# In workflow nodes
async def communication_node(state: AgentState) -> dict[str, Any]:
    store = state.get("_store")  # Injected via initial state
    user_id = state["user_id"]
    
    # Save notification record
    notification_key = f"paperscout:notifications:{user_id}:{date.today().isoformat()}"
    await store.save(notification_key, {
        "date": date.today().isoformat(),
        "papers_count": len(email_content.papers),
        "sent_at": datetime.now().isoformat(),
    })
    
    # Load dedupe list
    emailed_key = f"paperscout:emailed:{user_id}"
    emailed = await store.load(emailed_key) or []
    
    # Update dedupe list
    for paper in email_content.papers:
        emailed.append(paper.arxiv_id)
    await store.save(emailed_key, emailed)
```

### 6.3 Storage Injection Pattern

```python
def create_paperscout_subagent(
    config: PaperScoutConfig,
    store: AsyncPersistStore,
    user_id: str,
) -> dict[str, Any]:
    # Create nodes with store closure
    nodes = make_nodes(store, user_id)
    
    # Build initial state template
    initial_state = {
        "config": config,
        "user_id": user_id,
        "_store": store,  # Private, not in AgentState TypedDict
    }
    
    # Create and compile graph
    graph = StateGraph(AgentState)
    for name, node in nodes.items():
        graph.add_node(name, node)
    ...
    
    return {
        "name": "paperscout",
        "runnable": graph.compile(),
        "config": config,
    }
```

---

## 7. Event Emission

### 7.1 Event Base Class

```python
from soothe_sdk.core.events import SubagentEvent
from typing import Literal

class PaperScoutStepEvent(SubagentEvent):
    """Workflow step progress event."""
    
    type: Literal["soothe.community.paperscout.step"] = "soothe.community.paperscout.step"
    step: str = ""
    status: str = ""
```

### 7.2 Event Registration

```python
from soothe_sdk.plugin.registry import register_event
from soothe_sdk.core.verbosity import VerbosityTier

# Register event with summary template and verbosity
register_event(
    PaperScoutStepEvent,
    verbosity=VerbosityTier.NORMAL,
    summary_template="{step}: {status}",
)

register_event(
    PaperScoutPaperFoundEvent,
    verbosity=VerbosityTier.NORMAL,
    summary_template="Found paper: {paper_title} (score: {score:.2f})",
)

register_event(
    PaperScoutErrorEvent,
    verbosity=VerbosityTier.DEBUG,
    summary_template="Error in {step}: {error_message}",
)
```

### 7.3 Event Emission Pattern

```python
def _emit_step_event(step: str, status: str) -> None:
    """Emit workflow step event."""
    event = PaperScoutStepEvent(step=step, status=status)
    # Event automatically registered with soothe's event system
    # via class-level registration in events.py module
    logger.info(f"[{step}] {status}")

# In node implementation
def profile_analysis_node(state: AgentState) -> dict[str, Any]:
    _emit_step_event("profile_analysis", "Validating configuration")
    
    # ... validation logic
    
    _emit_step_event("profile_analysis", "Configuration validated")
    return {"info": state["info"]}
```

---

## 8. Context Object

### 8.1 PluginContext Interface

```python
class PluginContext:
    """Context provided to plugin lifecycle hooks."""
    
    logger: Logger          # Plugin-specific logger
    config: SootheConfig    # Global soothe configuration
    services: dict          # Service registry (persistence, etc.)
    utilities: dict         # Utility functions
```

### 8.2 Context Usage

```python
async def on_load(self, context: PluginContext) -> None:
    # Access logger
    context.logger.info("Loading plugin...")
    
    # Access config
    if context.config.subagents.get("paperscout"):
        context.logger.info("PaperScout configured")
    
    # Access services
    persistence = context.services.get("persistence")
    if persistence:
        context.logger.info("Persistence available")
```

---

## 9. Subagent Return Contract

### 9.1 Required Fields

| Field | Type | Description |
|-------|------|-------------|
| `name` | `str` | Subagent identifier (matches @subagent name) |
| `description` | `str` | Human-readable description |
| `runnable` | `CompiledStateGraph` | LangGraph compiled workflow |

### 9.2 Optional Fields

| Field | Type | Description |
|-------|------|-------------|
| `config` | `BaseModel` | Subagent-specific configuration |
| `initial_state` | `dict` | Pre-populated state values |

### 9.3 Return Value Example

```python
return {
    "name": "paperscout",
    "description": "ArXiv paper recommendation agent...",
    "runnable": graph.compile(),
    "config": paperscout_config,
}
```

---

## 10. Dependency Validation

### 10.1 Validation Pattern

```python
async def on_load(self, context: PluginContext) -> None:
    """Validate all required dependencies are installed."""
    
    REQUIRED_IMPORTS = {
        "arxiv": "arxiv>=2.0.0",
        "sentence_transformers": "sentence-transformers>=2.2.0",
        "pyzotero": "pyzotero>=1.5.0",
        "sklearn": "scikit-learn>=1.0.0",
    }
    
    missing = []
    for module_name, pip_spec in REQUIRED_IMPORTS.items():
        try:
            __import__(module_name)
        except ImportError:
            missing.append(pip_spec)
    
    if missing:
        from soothe_sdk.core.exceptions import PluginError
        raise PluginError(
            f"Missing required dependencies: {', '.join(missing)}. "
            f"Install with: pip install soothe[paperscout]"
        )
```

---

## 11. Module Structure

### 11.1 Plugin Module Layout

```python
# paperscout/__init__.py
"""PaperScout subagent plugin."""

from soothe_sdk.plugin import plugin, subagent
from soothe_sdk.protocols import AsyncPersistStore

from .implementation import create_paperscout_subagent
from .state import PaperScoutConfig
from .events import *  # Register all events

__all__ = [
    "PaperScoutPlugin",
    "create_paperscout_subagent",
]

@plugin(...)
class PaperScoutPlugin:
    ...

@subagent(...)
async def create_paperscout(...):
    ...

# Events are registered at module import time
# via register_event calls in events.py
```

---

## 12. Integration Checklist

### 12.1 Plugin Implementation Checklist

| Step | Task |
|------|------|
| 1 | Define `@plugin` decorator with name, version, dependencies |
| 2 | Implement `on_load` for dependency validation |
| 3 | Implement `get_subagents` returning factory methods |
| 4 | Define `@subagent` decorator on factory method |
| 5 | Define event classes inheriting `SubagentEvent` |
| 6 | Register events with `register_event` |
| 7 | Import events in `__init__.py` (triggers registration) |
| 8 | Return `{name, description, runnable}` from factory |

---

## 13. Dependencies

### 13.1 Required Dependencies

| Package | Purpose | Source |
|---------|---------|--------|
| `soothe_sdk` | Framework integration | soothe package |
| `langgraph` | Workflow compilation | pip |
| `pydantic` | Config models | pip |

---

## 14. Relationship to Other RFCs

| RFC | Relationship |
|-----|--------------|
| RFC-002-world-view | Implements Plugin/Subagent abstractions |
| RFC-001-paperlens-workflow | PaperLens plugin implementation |
| RFC-003-paperscout-workflow | PaperScout plugin implementation |
| RFC-006-configuration | Config injection from soothe |

---

## 15. Open Questions

None. soothe_sdk contracts are defined by the framework.

---

## 16. Conclusion

Alithia-agent subagents integrate with soothe framework via:

1. **@plugin decorator**: Module registration with name, version, dependencies
2. **@subagent decorator**: Factory method for agent creation
3. **AsyncPersistStore**: Protocol for key-value persistence
4. **SubagentEvent**: Base class with type discriminator
5. **PluginContext**: Logger, config, services injection
6. **Return contract**: `{name, description, runnable}` dict

> **Plugins register via decorators, validate dependencies on load, emit typed events, and return compiled LangGraph runnables — all following soothe_sdk contracts.**
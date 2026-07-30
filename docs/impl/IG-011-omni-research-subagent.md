# IG-011-omni-research-subagent: OmniResearch Subagent Implementation

**RFC Source**: [RFC-011-omni-research-subagent](../specs/RFC-011-omni-research-subagent.md)
**Target Module**: `alithia/omr`
**Language**: Python 3.10+
**Framework**: LangGraph + soothe_sdk
**Created**: 2026-06-17

---

## 1. Overview

This guide implements the OmniResearch (omr) soothe subagent as defined in RFC-011. The implementation follows the existing patterns from paperscout/paperlens subagents and adds pattern-based research workflow orchestration.

### 1.1 Architectural Position

```
alithia/
├── agent.py              # AlithiaAgent (updated to include omr subagent)
├── plugin_registration.py # Updated to register omr plugin
├── config/
│   └── schema.py         # Updated: add OmrAgentConfig
│
├── omr/                  # NEW: OmniResearch subagent
│   ├── __init__.py       # @plugin/@subagent entry point
│   ├── state.py          # AgentState, OmrRuntimeConfig
│   ├── implementation.py # create_omr_graph, create_omr_subagent
│   ├── nodes.py          # Workflow node functions
│   ├── pattern_router.py # Pattern detection logic
│   ├── skill_tree.py     # SkillTree state management
│   ├── events.py         # Event type definitions
│   │
│   ├── bootstrap/
│   │   └── node.py       # Workspace creation
│   │
│   ├── collection/
│   │   ├── node.py       # Collection orchestration
│   │   ├── input_router.py
│   │   └── handlers/
│   │       ├── base_handler.py
│   │       ├── paper_handler.py
│   │       ├── github_handler.py
│   │       ├── huggingface_handler.py
│   │       └── web_handler.py
│   │
│   ├── evidence/
│   │   └── node.py       # Evidence extraction
│   │
│   └── contracts/        # Skill contracts (copied from omni-research)
│       ├── omr-bootstrap.json
│       ├── omr-collection.json
│       ├── omr-evidence.json
│       └── patterns/
│           └── *.json
│
├── paperscout/           # Existing: PaperScout pattern
└── paperlens/            # Existing: PaperLens pattern
```

---

## 2. Module Structure

### 2.1 File Responsibilities

| File | Responsibility | RFC Reference |
|------|----------------|---------------|
| `__init__.py` | Plugin registration with @plugin/@subagent decorators | Section 15 |
| `state.py` | AgentState TypedDict, OmrRuntimeConfig | Section 7 |
| `implementation.py` | LangGraph construction, subagent factory | Section 5 |
| `nodes.py` | Node function aggregation | Section 5.2 |
| `pattern_router.py` | Pattern detection heuristics | Section 9 |
| `skill_tree.py` | SkillTree class for state management | Section 11 |
| `events.py` | Soothe event definitions | Section 14 |
| `bootstrap/node.py` | Workspace creation, CLAUDE.md generation | Section 5.2 |
| `collection/node.py` | Handler orchestration, retry/fallback | Section 10 |
| `collection/handlers/*.py` | Source-specific collection | Section 10.2 |
| `evidence/node.py` | Evidence extraction, brief generation | Section 5.2 |

---

## 3. Type Definitions

### 3.1 OmrAgentConfig (config/schema.py)

```python
class OmrAgentConfig(BaseModel):
    """OmniResearch agent configuration.

    RFC Reference: RFC-011 Section 8.1
    """

    model_config = ConfigDict(extra="forbid")

    # Workspace settings
    workspace_base: str = Field(
        default="omr-output",
        description="Base directory for research workspaces (relative to soothe workspace)"
    )

    # Pattern settings
    default_pattern: Literal[
        "auto", "evidence-first", "idea-first",
        "decision-first", "experiment-first", "rapid-prototype"
    ] = Field(default="auto", description="Default research pattern")

    # Collection settings
    collection_depth: Literal["default", "full-repo", "download-dataset"] = "default"
    max_papers_per_query: int = Field(default=10, ge=1, le=50)
    max_repos_per_query: int = Field(default=5, ge=1, le=20)

    # Evidence settings
    evidence_confidence_threshold: float = Field(default=0.7, ge=0.0, le=1.0)
    min_sources_for_evidence: int = Field(default=3, ge=1, le=10)

    # Synthesis settings (for future phases)
    synthesis_mode: Literal["survey", "report", "manuscript", "brief"] = "survey"
```

### 3.2 OmrRuntimeConfig (omr/state.py)

```python
class OmrRuntimeConfig(BaseModel):
    """OmniResearch runtime configuration (derived from global config).

    RFC Reference: RFC-011 Section 8.2
    """

    model_config = ConfigDict(extra="forbid")

    # Workspace
    workspace_base: Path
    research_topic: str

    # Pattern
    pattern: Literal["evidence-first", "idea-first", "decision-first",
                      "experiment-first", "rapid-prototype"]

    # Collection
    collection_depth: Literal["default", "full-repo", "download-dataset"]
    input_sources: list[str] = []

    # LLM integration
    llm_api_key: str | None = None
    llm_api_base: str | None = None
    llm_model: str = "qwen-turbo-latest"

    @classmethod
    def build_runtime_config(
        cls,
        global_config: Config,
        research_topic: str,
        soothe_workspace: Path,
    ) -> OmrRuntimeConfig:
        """Build runtime config from global config.

        RFC Reference: RFC-011 Section 2.3
        """
        omr_cfg = global_config.omr_agent
        profile = global_config.researcher_profile

        pattern = omr_cfg.default_pattern
        if pattern == "auto":
            pattern = "evidence-first"

        workspace_base = soothe_workspace / omr_cfg.workspace_base

        return cls(
            workspace_base=workspace_base,
            research_topic=research_topic,
            pattern=pattern,
            collection_depth=omr_cfg.collection_depth,
            llm_api_key=profile.llm.openai_api_key if profile.llm else None,
            llm_api_base=profile.llm.openai_api_base if profile.llm else None,
            llm_model=profile.llm.model_name if profile.llm else "qwen-turbo-latest",
        )
```

### 3.3 AgentState (omr/state.py)

```python
class AgentState(TypedDict):
    """LangGraph agent state for OmniResearch workflow.

    RFC Reference: RFC-011 Section 7.1
    """

    # LangGraph message history
    messages: Annotated[list[Any], add_messages]

    # Configuration
    config: OmrRuntimeConfig
    user_id: str

    # Workspace context
    workspace_path: str
    project_id: str
    research_topic: str
    pattern: Literal["evidence-first", "idea-first", "decision-first",
                      "experiment-first", "rapid-prototype"]

    # Skill tree state
    skill_tree: dict
    current_skill: str
    completed_skills: list[str]
    pending_gates: dict

    # Artifact state
    raw_materials: dict
    materials_index: dict | None
    evidence_map: dict | None
    research_brief: dict | None

    # Collection state
    input_sources: list[str]
    collection_results: dict
    failed_sources: list[dict]

    # Tracking
    errors: Annotated[list[str], "add"]
    info: Annotated[list[str], "add"]
    metrics: dict[str, Any]
```

### 3.4 SkillTreeState (omr/skill_tree.py)

```python
DEFAULT_TREE_STATE: dict = {
    "unlocked": ["omr-collection", "omr-idea-note"],
    "ready": [],
    "locked": ["omr-evidence", "omr-research-plan", "omr-decision",
               "omr-evaluation", "omr-synthesis", "omr-wiki"],
    "completed": ["omr-bootstrap"],
    "pattern": "evidence-first",
    "last_updated": "",  # ISO-8601
}

class SkillTree:
    """Skill tree state management.

    RFC Reference: RFC-011 Section 11
    """

    def __init__(self, tree_path: Path):
        self.tree_path = tree_path
        self.state = self._load_state()

    def mark_completed(self, skill_name: str) -> None:
        """Mark skill as completed and unlock downstream."""
        ...

    def check_prerequisites(self, skill_name: str) -> bool:
        """Check if skill prerequisites are satisfied."""
        ...

    def get_visualization(self) -> str:
        """Generate ASCII tree visualization."""
        ...
```

---

## 4. Interface Definitions

### 4.1 BaseHandler (collection/handlers/base_handler.py)

```python
class BaseHandler(ABC):
    """Abstract base class for collection handlers.

    RFC Reference: RFC-011 Section 10.1
    """

    max_retries: int = 2
    retry_delay: float = 2.0

    @abstractmethod
    async def collect(self, source: str, workspace: Path) -> Artifact:
        """Collect material from source and store in workspace.

        Args:
            source: Input URL/DOI/ID
            workspace: Project workspace path

        Returns:
            Artifact with metadata and file path
        """
        pass

    async def with_retry(self, fn: Callable[..., T]) -> T:
        """Execute function with retry logic."""
        for attempt in range(self.max_retries + 1):
            try:
                return await fn()
            except Exception as e:
                if attempt == self.max_retries:
                    raise
                await asyncio.sleep(self.retry_delay)
```

### 4.2 InputRouter (collection/input_router.py)

```python
class InputRouter:
    """Route inputs to appropriate handlers.

    RFC Reference: RFC-011 Section 10.3
    """

    def route_inputs(self, sources: list[str]) -> dict[str, list[str]]:
        """Categorize sources by type.

        Returns:
            Dict with keys: paper, github, huggingface, web
        """
        ...

    def is_arxiv_id(self, source: str) -> bool:
        """Check if source is arxiv ID pattern."""
        ...

    def is_doi(self, source: str) -> bool:
        """Check if source is DOI pattern."""
        ...

    def is_github_url(self, source: str) -> bool:
        """Check if source is GitHub URL."""
        ...

    def is_huggingface_url(self, source: str) -> bool:
        """Check if source is HuggingFace URL."""
        ...
```

---

## 5. Node Implementations

### 5.1 Bootstrap Node

**File**: `bootstrap/node.py`

**RFC Reference**: Section 5.2, Section 13

**Algorithm**:
1. Generate project_id from research_topic (lowercase-hyphenated)
2. Create workspace directory structure
3. Generate CLAUDE.md with metadata
4. Initialize skill-tree.json
5. Initialize empty indexes
6. Update state with workspace_path, project_id, skill_tree

**Directory Structure**:
```
{project-id}/
├── CLAUDE.md
├── skill-tree.json
├── raw/{paper,web,github,dataset}/
├── docs/{survey,report,manuscript,brief,plans,ideas,index}/
├── src/{prototype,evaluation}/
└── wiki/
```

### 5.2 Pattern Router Node

**File**: `pattern_router.py`

**RFC Reference**: Section 9.2

**Auto-Detection Heuristics**:
```python
def detect_pattern(state: AgentState) -> str:
    """Detect pattern from input sources and messages."""
    sources = state.get("input_sources", [])
    user_msg = str(state.get("messages", []))

    # Paper URLs/DOIs → evidence-first
    if any(is_paper_url(s) or is_doi(s) for s in sources):
        return "evidence-first"

    # Hypothesis keywords → experiment-first
    hypothesis_kws = ["hypothesis", "test", "validate", "experiment"]
    if any(kw in user_msg.lower() for kw in hypothesis_kws):
        return "experiment-first"

    # Idea keywords → idea-first
    idea_kws = ["i think", "my idea", "hypothesize", "insight"]
    if any(kw in user_msg.lower() for kw in idea_kws):
        return "idea-first"

    # Decision keywords → decision-first
    decision_kws = ["architecture", "design decision", "approach"]
    if any(kw in user_msg.lower() for kw in decision_kws):
        return "decision-first"

    # Default
    return "evidence-first"
```

### 5.3 Collection Node

**File**: `collection/node.py`

**RFC Reference**: Section 10

**Algorithm**:
1. Route inputs via InputRouter
2. For each category, get appropriate handler
3. Execute handlers with retry/fallback
4. Store artifacts in raw/{category}/
5. Update artifacts-index.json
6. Update skill tree (unlock evidence)
7. Handle failures gracefully (create error artifacts)

**Fallback Chain**:
- Primary handler → retry 2x → Generic Web handler → error artifact

### 5.4 Evidence Node

**File**: `evidence/node.py`

**RFC Reference**: Section 5.2, Section 7.1

**Algorithm**:
1. Read materials from raw/{paper,web}/
2. Extract claims, citations, confidence levels
3. Generate research-brief.md
4. Generate evidence-map.md
5. Update skill tree (unlock research_plan)

**Minimal Parsing Boundary** (Section 4.5):
- Extract: claims, citations, confidence (proven/suggested/inferred)
- DO NOT: abstract extraction, keyword classification, semantic analysis

---

## 6. Plugin Integration

### 6.1 Plugin Registration (__init__.py)

```python
from soothe_sdk.plugin import plugin, subagent

@plugin(
    name="omr",
    version="1.0.0",
    description="OmniResearch structured workflow with pattern routing",
    dependencies=["langgraph>=0.2.0", "arxiv>=2.0.0", "pdfplumber>=0.10.0"],
    trust_level="standard",
)
class OmniResearchPlugin:
    """OmniResearch plugin for structured research workflows."""

    async def on_load(self, context: Any) -> None:
        context.logger.info("Loading OmniResearch plugin v1.0.0")

    @subagent(
        name="omni-research",
        description=(
            "Structured research workflow with pattern-based routing. "
            "Supports Evidence-First, Idea-First, Decision-First, "
            "Experiment-First, and Rapid-Prototype patterns."
        ),
        triggers=["research", "omni", "start research", "literature review"],
    )
    async def create_subagent(
        self,
        model: Any,
        config: Any,
        context: Any,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Create OmniResearch subagent."""
        ...
```

### 6.2 Registration Updates

**plugin_registration.py**:
```python
# Add to register_alithia_plugins():
from alithia.omr import OmniResearchPlugin
registry.register(getattr(OmniResearchPlugin, "_plugin_manifest"), ...)
```

**agent.py**:
```python
# Update alithia_subagents list:
alithia_subagents = ["paperscout", "paperlens", "omni-research"]
```

---

## 7. Error Handling Strategy

### 7.1 Error Categories

| Category | Example | Handling |
|----------|---------|----------|
| Config validation | Missing research_topic | Emit error, return early |
| Handler failure | ArXiv rate limit | Retry 2x → fallback → error artifact |
| Storage failure | Workspace write error | Log error, continue |
| Pattern mismatch | Invalid pattern | Default to evidence-first |

### 7.2 Graceful Degradation

**RFC Reference**: Section 11.2

| Invariant | Rule |
|-----------|------|
| Handler unavailable | MUST fallback to Generic Web handler |
| All handlers fail | MUST create error artifact in raw/failed/ |
| Pattern auto-detect fails | MUST default to evidence-first |
| Workspace creation fails | MUST return early with error |

---

## 8. Testing Strategy

### 8.1 Unit Tests

| Module | Test Focus |
|--------|------------|
| `state.py` | Config validation, default values |
| `pattern_router.py` | Pattern detection for each heuristic |
| `skill_tree.py` | State transitions, prerequisite checking |
| `input_router.py` | URL/DOI/arxiv detection |
| `handlers/*.py` | Mock API responses, retry behavior |

### 8.2 Integration Tests

| Scenario | Test |
|----------|------|
| Bootstrap → Collection | Full workspace creation + material collection |
| Pattern routing | Each pattern branch |
| Handler fallback | Primary failure → Generic Web |
| Skill tree unlocking | Evidence unlocks after collection |

### 8.3 Test Fixtures

- Mock arxiv papers (cached responses)
- Mock GitHub API responses
- Mock workspace paths (temp directories)

---

## 9. Implementation Sequence

### Phase 1: Foundation (Est. 2-3 days)

1. Add `OmrAgentConfig` to `config/schema.py`
2. Update `Config` class to include `omr_agent`
3. Create `alithia/omr/` package structure
4. Implement `state.py` (AgentState, OmrRuntimeConfig)
5. Implement `skill_tree.py`
6. Create `events.py`

### Phase 2: Core Nodes (Est. 3-4 days)

7. Implement `pattern_router.py`
8. Implement `bootstrap/node.py`
9. Implement `collection/input_router.py`
10. Implement `collection/handlers/base_handler.py`
11. Implement `collection/handlers/paper_handler.py`
12. Implement `collection/handlers/github_handler.py`
13. Implement `collection/handlers/web_handler.py`
14. Implement `collection/node.py`
15. Implement `evidence/node.py`

### Phase 3: Integration (Est. 1-2 days)

16. Implement `implementation.py` (graph construction)
17. Implement `__init__.py` (plugin registration)
18. Update `plugin_registration.py`
19. Update `agent.py`
20. Add tests

---

## 10. Dependencies

### 10.1 Required Packages

| Package | Purpose | Version |
|---------|---------|---------|
| `langgraph` | Workflow orchestration | >=0.2.0 |
| `arxiv` | ArXiv API | >=2.0.0 |
| `pdfplumber` | PDF parsing | >=0.10.0 |
| `httpx` | HTTP requests | >=0.25.0 |
| `html2text` | HTML to Markdown | >=2020.1.16 |

### 10.2 Optional Packages

| Package | Purpose | When Used |
|---------|---------|-----------|
| `huggingface_hub` | HF API | HuggingFace URLs |
| `langchain` | LLM evidence | Advanced extraction |

---

## 11. Open Questions

1. Should evidence extraction use LLM by default? (Currently: rule-based)
2. Pattern switching mid-workflow? (Currently: pattern set at bootstrap)
3. Skill tree persistence across sessions? (Currently: per-project)

---

## 12. Conclusion

This implementation guide provides the concrete design for the OmniResearch subagent following RFC-011 specifications. Key implementation points:

1. **Pattern routing** auto-detects user intent from keywords
2. **Skill tree** tracks progress with prerequisite-based unlocking
3. **Handlers** process sources with retry/fallback chains
4. **Plugin integration** follows existing paperscout/paperlens patterns
5. **Workspace** created relative to soothe current workspace

> **Implementation follows soothe subagent patterns with LangGraph workflow orchestration, maintaining consistency with existing paperscout/paperlens architecture.**
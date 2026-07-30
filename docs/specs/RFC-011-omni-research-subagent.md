# RFC-011-omni-research-subagent: OmniResearch Soothe Subagent Architecture

**Status**: Draft
**Authors**: Claude (from design draft 2026-06-17)
**Created**: 2026-06-17
**Last Updated**: 2026-06-17
**Depends on**: RFC-002-world-view, RFC-007-plugin-integration, RFC-009-soothe-integration
**Supersedes**: ---
**Stage**: Core
**Kind**: Architecture Design

---

## 1. Abstract

OmniResearch (omr) is a soothe framework subagent that orchestrates structured research workflows with pattern-based routing. This RFC defines the LangGraph workflow architecture, component structure, pattern routing system, skill tree state management, and key interface contracts for the omr subagent. It bootstraps research workspaces, collects materials from multiple sources (ArXiv, GitHub, HuggingFace, Web), extracts evidence, and maintains progress tracking through a skill tree state system with gate enforcement.

---

## 2. Scope and Non-Goals

### 2.1 Scope

This RFC defines:

* The LangGraph workflow with pattern-based routing (5 research patterns)
* Component module structure and layer classification
* AgentState schema and skill tree state management
* Bootstrap node for workspace creation under `{soothe_workspace}/omr-output/`
* Collection node with 4 handlers (Paper, GitHub, HuggingFace, Web)
* Evidence node for minimal evidence extraction
* Pattern routing logic with auto-detection heuristics
* Gate enforcement at skill boundaries (Gates A, B, C, D)
* Configuration schema (OmrAgentConfig, OmrRuntimeConfig)
* Integration with existing omni-research skill contracts

### 2.2 Non-Goals

This RFC does **not** define:

* Full 11-skill implementation (only core pipeline: bootstrap, collection, evidence)
* Downstream skills (research-plan, decision, evaluation, synthesis, wiki)
* Advanced pattern detection algorithms
* Semantic analysis in collection (belongs in evidence)
* Web dashboard or UI components
* Multi-user collaboration features
* Testing implementation details

---

## 3. Background & Motivation

OmniResearch provides structured, evidence-bound research workflows that integrate with the alithia soothe infrastructure. Researchers need systematic approaches that differ by intent:

1. **Evidence-First**: Literature surveys starting from papers
2. **Idea-First**: Exploratory research starting from insights
3. **Decision-First**: Engineering research validating architectural decisions
4. **Experiment-First**: Hypothesis-driven research requiring rapid iteration
5. **Rapid-Prototype**: Fast exploration without gate constraints

The omr subagent routes user requests to appropriate patterns, enforces quality gates, and maintains progress state for resumption.

---

## 4. Design Principles

1. **Pattern flexibility**: Same infrastructure supports 5 distinct research workflows
2. **Gate enforcement**: Quality criteria must be met before skill progression
3. **Skill tree state**: Progress tracked for resumption and visualization
4. **Workspace isolation**: Each project gets dedicated workspace under soothe workspace
5. **Minimal parsing boundary**: Collection extracts format/metadata only; evidence extracts semantics
6. **Graceful degradation**: Handler failures logged but don't block workflow
7. **Contract-based dependencies**: Skills unlock based on artifact production

---

## 5. Workflow Architecture

### 5.1 Pattern Routing Structure

**Design Decision**: Pattern routing happens during config resolution, not as a graph node.
This allows pattern detection to occur before graph execution, enabling more efficient workflow initialization.

```
Config Resolution: pattern_router.detect_pattern() → OmrRuntimeConfig.pattern

Graph Structure:
START → bootstrap → collection → evidence → END
```

Pattern detection happens in `OmrRuntimeConfig.build_runtime_config()`:
1. If `default_pattern != "auto"`, use explicit pattern
2. If `"auto"`, call `detect_pattern(input_sources, user_message)`
3. Pattern stored in config, available to all nodes

**Rationale**: Pattern selection doesn't require graph state transitions because:
- Detection depends only on input sources and user message (available at init)
- All patterns route to same core pipeline (collection → evidence)
- Future pattern-specific nodes will branch from evidence output, not collection input

Note: Core pipeline implements collection + evidence for all patterns. Future phases will add pattern-specific downstream nodes (idea_note, decision, evaluation, synthesis).

### 5.2 Node Responsibilities

| Node | Responsibility | Input | Output to State |
|------|----------------|-------|-----------------|
| `bootstrap` | Create workspace structure + CLAUDE.md + skill tree | `config.research_topic`, `config.workspace_base`, `config.pattern` | `workspace_path`, `project_id`, `skill_tree` |
| `collection` | Collect materials from sources | `input_sources`, handlers | `raw_materials`, `materials_index` |
| `evidence` | Extract evidence + generate brief | `raw_materials` | `evidence_map`, `research_brief` |

**Note**: `pattern_router` is a module (`pattern_router.py`) used during config resolution, not a graph node. Pattern is detected before workflow execution and passed via `OmrRuntimeConfig.pattern`.

### 5.3 Node Execution Constraints

| Constraint | Rule |
|------------|------|
| Bootstrap first | Bootstrap MUST execute before any other node |
| Pattern routing | Pattern MUST be set (auto → detected or default) before collection |
| Handler isolation | Each handler MUST process sources independently; failures MUST NOT block other handlers |
| Skill tree updates | Skill tree MUST be updated after each node completion |
| Evidence boundary | Evidence MUST NOT extract semantics beyond claims/citations/confidence |

---

## 6. Component Structure

### 6.1 Module Organization

```
alithia/omr/
├── __init__.py           # Plugin entry point (@plugin/@subagent)
├── state.py              # AgentState, OmrRuntimeConfig, OmrAgentConfig
├── implementation.py     # create_omr_graph, create_omr_subagent
├── nodes.py              # 4 workflow node functions
├── pattern_router.py     # Pattern detection and routing logic
├── skill_tree.py         # SkillTree class for state management
├── events.py             # OmrStepEvent, OmrMaterialCollectedEvent, etc.
│
├── bootstrap/
│   ├── __init__.py
│   └── node.py           # Workspace creation, CLAUDE.md generation
│
├── collection/
│   ├── __init__.py
│   ├── node.py           # Collection orchestration
│   ├── input_router.py   # URL/DOI/Search detection
│   └── handlers/
│       ├── __init__.py
│       ├── base_handler.py
│       ├── paper_handler.py
│       ├── github_handler.py
│       ├── huggingface_handler.py
│       └── web_handler.py
│
├── evidence/
│   ├── __init__.py
│   └── node.py           # Evidence extraction, brief generation
│
└── contracts/
    ├── omr-bootstrap.json
    ├── omr-collection.json
    ├── omr-evidence.json
    └── patterns/
        ├── evidence-first.json
        ├── idea-first.json
        ├── decision-first.json
        ├── experiment-first.json
        └── rapid-prototype.json
```

### 6.2 Layer Classification

| Module | Layer | Dependencies | Purpose |
|--------|-------|--------------|---------|
| `state.py` | Foundation | pydantic, langgraph | State and config schemas |
| `skill_tree.py` | Foundation | json, pathlib | Skill tree state management |
| `events.py` | Foundation | soothe_sdk events | Event type definitions |
| `contracts/*.json` | Foundation | — | Skill contract definitions |
| `pattern_router.py` | Foundation | re, typing | Pattern detection logic |
| `bootstrap/node.py` | Middle | pathlib, datetime | Workspace creation |
| `collection/handlers/*` | Middle | arxiv, httpx, pdfplumber | Source-specific collection |
| `collection/node.py` | Middle | handlers, input_router | Collection orchestration |
| `evidence/node.py` | Middle | langchain (optional) | Evidence extraction |
| `nodes.py` | Middle | bootstrap, collection, evidence | Node aggregation |
| `implementation.py` | Middle | nodes, state, langgraph | Graph construction |
| `__init__.py` | Leaf | implementation, soothe_sdk | Plugin entry point |

### 6.3 External Dependencies

| Service | Library | Purpose |
|---------|---------|---------|
| ArXiv API | `arxiv>=2.0.0` | Paper discovery/download |
| PDF parsing | `pdfplumber>=0.10.0` | Text extraction |
| Web fetch | `httpx>=0.25.0` | HTTP requests |
| Markdown | `html2text>=2020.1.16` | HTML → Markdown |

---

## 7. Data Flow

### 7.1 State Schema

```python
class AgentState(TypedDict):
    """LangGraph agent state for OmniResearch workflow."""

    # LangGraph message history
    messages: Annotated[list[Any], add_messages]

    # Configuration
    config: OmrRuntimeConfig
    user_id: str

    # Workspace context
    workspace_path: str  # soothe_workspace / omr-output / project-id
    project_id: str      # Lowercase-hyphenated topic
    research_topic: str
    pattern: Literal["evidence-first", "idea-first", "decision-first",
                      "experiment-first", "rapid-prototype"]

    # Skill tree state
    skill_tree: dict     # {unlocked, ready, locked, completed}
    current_skill: str
    completed_skills: list[str]
    pending_gates: dict  # {gate_id: criteria_status}

    # Artifact state
    raw_materials: dict  # {paper: [], web: [], github: [], dataset: []}
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

### 7.2 Skill Tree State Schema

```python
DEFAULT_TREE_STATE = {
    "unlocked": ["omr-collection", "omr-idea-note"],
    "ready": [],
    "locked": ["omr-evidence", "omr-research-plan", "omr-decision",
               "omr-evaluation", "omr-synthesis", "omr-wiki"],
    "completed": ["omr-bootstrap"],
    "pattern": "evidence-first",
    "last_updated": "ISO-8601"
}
```

### 7.3 Data Transformation Flow

| Stage | Input | Transform | Output |
|-------|-------|-----------|--------|
| `bootstrap` | Research topic | Create directories → generate CLAUDE.md → init skill tree | `workspace_path`, `skill_tree.json` |
| `pattern_router` | Input sources + messages | Keyword detection → pattern selection | `pattern` |
| `collection` | URLs/DOIs/Search | Route to handlers → fetch → store artifacts | `raw_materials`, `artifacts-index.json` |
| `evidence` | Raw materials | Parse artifacts → extract claims → generate brief | `evidence-map.md`, `research-brief.md` |

---

## 8. Configuration Schema

### 8.1 OmrAgentConfig (in config.yml)

| Field | Type | Default | Constraints | Description |
|-------|------|---------|-------------|-------------|
| `workspace_base` | `str` | `"omr-output"` | — | Base directory relative to soothe workspace |
| `default_pattern` | `str` | `"auto"` | auto/evidence-first/idea-first/decision-first/experiment-first/rapid-prototype | Default research pattern |
| `collection_depth` | `str` | `"default"` | default/full-repo/download-dataset | Material download depth |
| `max_papers_per_query` | `int` | `10` | 1-50 | Papers per search query |
| `max_repos_per_query` | `int` | `5` | 1-20 | Repos per search query |
| `evidence_confidence_threshold` | `float` | `0.7` | 0.0-1.0 | Minimum confidence for evidence |
| `min_sources_for_evidence` | `int` | `3` | 1-10 | Minimum sources for evidence extraction |
| `synthesis_mode` | `str` | `"survey"` | survey/report/manuscript/brief | Default synthesis output format |

### 8.2 OmrRuntimeConfig

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `workspace_base` | `Path` | Yes | Resolved: `soothe_workspace / workspace_base` |
| `research_topic` | `str` | Yes | User-provided research topic |
| `pattern` | `str` | Yes | Resolved pattern (from auto-detect or explicit) |
| `collection_depth` | `str` | No | Override for collection depth |
| `input_sources` | `list[str]` | No | URLs, DOIs, search queries |
| `llm_api_key` | `str` | No | LLM API key (from researcher_profile) |
| `llm_api_base` | `str` | No | LLM API base URL |
| `llm_model` | `str` | No | LLM model name |

---

## 9. Pattern Routing

### 9.1 Pattern Definitions

| Pattern | Entry Point | Description | Estimated Time |
|---------|-------------|-------------|----------------|
| `evidence-first` | collection | Literature surveys, systematic reviews | 3-5 days |
| `idea-first` | collection | Exploratory research from insights | 1-2 days |
| `decision-first` | collection | Engineering decisions validation | 2-3 days |
| `experiment-first` | collection | Hypothesis testing with rapid iteration | 1-3 days |
| `rapid-prototype` | collection | Fast exploration, minimal gates | <1 day |

### 9.2 Auto-Detection Heuristics

| Detected Input | Keyword Patterns | Pattern Selection |
|----------------|------------------|-------------------|
| Paper URLs/DOIs | — | `evidence-first` |
| Hypothesis keywords | "hypothesis", "test", "validate", "experiment" | `experiment-first` |
| Idea keywords | "i think", "my idea", "hypothesize", "insight" | `idea-first` |
| Decision keywords | "architecture", "design decision", "approach" | `decision-first` |
| Default | — | `evidence-first` |

### 9.3 Pattern Routing Logic

```python
def route_by_pattern(state: AgentState) -> str:
    """Route to appropriate pattern branch."""
    pattern = state["pattern"]
    
    # Core pipeline routes all patterns to collection first
    routes = {
        "evidence-first": "collection",
        "idea-first": "collection",
        "decision-first": "collection",
        "experiment-first": "collection",
        "rapid-prototype": "collection",
    }
    
    return routes.get(pattern, "collection")
```

---

## 10. Handler Architecture

### 10.1 Base Handler Contract

```python
class BaseHandler(ABC):
    """Abstract base class for collection handlers."""

    max_retries: int = 2
    retry_delay: float = 2.0

    @abstractmethod
    async def collect(self, source: str, workspace: Path) -> Artifact:
        """Collect material from source and store in workspace."""
        pass

    async def with_retry(self, fn: Callable) -> Any:
        """Execute with retry logic."""
        pass
```

### 10.2 Handler Types

| Handler | Source Types | Retrieval Strategy | Output Format |
|---------|--------------|-------------------|---------------|
| **PaperHandler** | arxiv IDs, DOIs, PDF URLs | arxiv SDK / HTTP download | `raw/paper/arxiv-{id}.md` |
| **GitHubHandler** | GitHub URLs | README + metadata via API | `raw/github/github-{repo}.md` |
| **HuggingFaceHandler** | HF URLs | README + card via API | `raw/dataset/hf-{name}.md` |
| **WebHandler** | HTTP URLs | HTTP fetch → markdown | `raw/web/url-{hash}.md` |

### 10.3 Input Router

```python
class InputRouter:
    """Route inputs to appropriate handlers."""

    def route_inputs(self, sources: list[str]) -> dict[str, list[str]]:
        """Categorize sources by type."""
        return {
            "paper": [s for s in sources if is_paper_source(s)],
            "github": [s for s in sources if is_github_url(s)],
            "huggingface": [s for s in sources if is_huggingface_url(s)],
            "web": [s for s in sources if is_web_url(s)],
        }
```

---

## 11. Skill Tree Management

### 11.1 Skill Tree States

| State | Symbol | Meaning |
|-------|--------|---------|
| `unlocked` | ○ | Can run anytime |
| `ready` | ● | Prerequisites satisfied, awaiting execution |
| `locked` | 🔒 | Missing prerequisites |
| `completed` | ✓ | Successfully executed |

### 11.2 Skill Unlocking Logic

```python
def update_skill_tree(state: AgentState) -> AgentState:
    """Update skill tree after node completion."""
    tree = state["skill_tree"]
    completed = state["current_skill"]
    
    # Move to completed
    if completed in tree["ready"]:
        tree["ready"].remove(completed)
    elif completed in tree["unlocked"]:
        tree["unlocked"].remove(completed)
    tree["completed"].append(completed)
    
    # Check downstream skills
    contracts = load_contracts()
    for skill in tree["locked"]:
        if check_prerequisites(contracts[skill], tree):
            tree["locked"].remove(skill)
            tree["ready"].append(skill)
    
    # Persist
    tree["last_updated"] = datetime.now().isoformat()
    return state
```

---

## 12. Gate Enforcement

### 12.1 Gate Definitions

| Gate | Location | Criteria |
|------|----------|----------|
| **Gate A** | Before `omr-research-plan` | evidence-map.md exists, ≥5 sources |
| **Gate B** | Before `omr-decision` | research-brief.md exists, judgment quality |
| **Gate C** | Before `omr-evaluation` | decision.md exists, actionable experiment plan |
| **Gate D** | Before `omr-synthesis` | evaluation-report.md exists, results documented |

### 12.2 Gate Check Logic

```python
def gate_check(state: AgentState, gate_id: str) -> dict:
    """Check gate criteria."""
    workspace = Path(state["workspace_path"])
    
    criteria = {
        "gate_a": [
            (workspace / "docs/evidence-map.md").exists(),
            sum(len(v) for v in state["raw_materials"].values()) >= 5,
        ],
        "gate_b": [
            (workspace / "docs/research-brief.md").exists(),
            check_judgment_quality(state),
        ],
        # Additional gates for future phases
    }
    
    met = all(criteria.get(gate_id, []))
    return {"gate": gate_id, "status": "passed" if met else "blocked"}
```

---

## 13. Workspace Output Structure

After bootstrap, workspace at `{soothe_workspace}/omr-output/{project-id}/`:

```
{project-id}/
├── CLAUDE.md              # Project context for AI agents
├── skill-tree.json        # Skill tree state
│
├── raw/                   # Collected materials (markdown artifacts)
│   ├── paper/
│   ├── web/
│   ├── github/
│   └── dataset/
│
├── docs/                  # Distilled knowledge
│   ├── evidence-map.md    # (from evidence node)
│   ├── research-brief.md  # (from evidence node)
│   ├── survey/
│   ├── report/
│   ├── plans/
│   ├── ideas/
│   └── index/
│       └── artifacts-index.json
│
├── src/                   # Generated code (future)
│
└── wiki/                  # Living knowledge base (future)
```

---

## 14. Events

### 14.1 Event Types

| Event Type | When Emitted | Verbosity |
|------------|--------------|-----------|
| `soothe.community.omr.step` | Each workflow step | NORMAL |
| `soothe.community.omr.material.collected` | Material collected | NORMAL |
| `soothe.community.omr.evidence.extracted` | Evidence extracted | NORMAL |
| `soothe.community.omr.error` | Error occurred | DEBUG |

### 14.2 Event Schemas

**OmrStepEvent**:
| Field | Type | Description |
|-------|------|-------------|
| `step` | `str` | Node name |
| `skill` | `str` | Current skill |
| `status` | `str` | Status message |

**OmrMaterialCollectedEvent**:
| Field | Type | Description |
|-------|------|-------------|
| `source_type` | `str` | paper/web/github/dataset |
| `source` | `str` | Original input |
| `artifact_path` | `str` | Stored artifact path |

---

## 15. Plugin Integration

### 15.1 Soothe Plugin Registration

```python
@plugin(
    name="omr",
    version="1.0.0",
    description="OmniResearch structured workflow with pattern routing",
    dependencies=["langgraph>=0.2.0", "arxiv>=2.0.0", "pdfplumber>=0.10.0"],
    trust_level="standard",
)
class OmniResearchPlugin:
    @subagent(
        name="omni-research",
        description="Structured research workflow...",
        triggers=["research", "omni", "start research", "literature review"],
    )
    async def create_subagent(self, model, config, context, **kwargs):
        # Build runtime config from soothe workspace
        soothe_workspace = Path(context.get("workspace", SOOTHE_HOME))
        runtime_config = OmrRuntimeConfig.build_runtime_config(
            global_config, research_topic, soothe_workspace
        )
        return create_omr_subagent(config=runtime_config, user_id=user_id)
```

### 15.2 Alithia Agent Integration

Update `alithia/agent.py` to include "omni-research" in subagents list:

```python
alithia_subagents = ["paperscout", "paperlens", "omni-research"]
```

---

## 16. Dependencies

### 16.1 Required Dependencies

| Package | Purpose | Minimum Version |
|---------|---------|-----------------|
| `langgraph` | Workflow orchestration | 0.2.0 |
| `pydantic` | Data models | 2.0 |
| `arxiv` | ArXiv API client | 2.0.0 |
| `pdfplumber` | PDF parsing | 0.10.0 |
| `httpx` | HTTP requests | 0.25.0 |
| `html2text` | HTML to Markdown | 2020.1.16 |

### 16.2 Optional Dependencies

| Package | Purpose | When Needed |
|---------|---------|-------------|
| `huggingface_hub` | HF API access | HuggingFace URLs |
| `langchain` | LLM evidence extraction | Advanced evidence |

---

## 17. Relationship to Other RFCs

* **RFC-002-world-view**: Shared vision and conceptual foundation
* **RFC-007-plugin-integration**: Soothe plugin pattern (same as paperscout/paperlens)
* **RFC-009-soothe-integration**: SootheRunner integration, workspace context
* **RFC-003-paperscout-workflow**: Similar LangGraph pattern, 5-node structure
* **RFC-006-configuration**: Config schema extension (OmrAgentConfig)

---

## 18. Open Questions

1. Should evidence extraction use LLM by default or rule-based parsing?
2. How to handle pattern switching mid-workflow?
3. Should skill tree state be shared across multiple omr sessions?

---

## 19. Conclusion

OmniResearch is a soothe subagent implementing pattern-based research workflows with LangGraph orchestration. The architecture defines:

1. **Pattern routing**: 5 research patterns with auto-detection
2. **Core pipeline**: Bootstrap → Collection → Evidence
3. **Skill tree state**: Progress tracking for resumption
4. **Gate enforcement**: Quality criteria at skill boundaries
5. **Workspace isolation**: `{soothe_workspace}/omr-output/{project-id}/`
6. **Handler architecture**: 4 handlers with retry/fallback logic

> **OmniResearch delivers structured, traceable research workflows by routing user requests to appropriate patterns, enforcing quality gates, and maintaining progress state — all integrated with the soothe framework infrastructure.**
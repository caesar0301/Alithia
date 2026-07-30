# OmniResearch Soothe Subagent Design

**Date**: 2026-06-17
**Status**: Draft for Review
**Scope**: Core Pipeline (bootstrap, collection, evidence)

---

## Executive Summary

Create a `omr` soothe subagent that orchestrates the omni-research workflow as a pure LangGraph implementation. The subagent will:

1. Bootstrap research workspaces under `{soothe_workspace}/omr-output/`
2. Route to appropriate research patterns (Evidence-First, Idea-First, etc.)
3. Execute skill nodes following pattern-defined graphs with gate enforcement
4. Maintain skill tree state for progress tracking and resumption

**Why**: Leverage existing alithia infrastructure (soothe framework, config system) while providing structured, traceable research workflows with pattern-based flexibility.

---

## 1. Package Structure

```
alithia/omr/
├── __init__.py           # Plugin registration (@plugin, @subagent)
├── state.py              # OmrRuntimeConfig + AgentState TypedDict
├── implementation.py     # create_omr_graph() + create_omr_subagent()
├── nodes.py              # LangGraph node implementations
├── pattern_router.py     # Pattern detection and routing logic
├── skill_tree.py         # Skill tree state integration
├── events.py             # Soothe event definitions
│
├── bootstrap/            # omr-bootstrap node implementation
│   ├── __init__.py
│   └── node.py           # Workspace creation, CLAUDE.md generation
│
├── collection/           # omr-collection node implementation
│   ├── __init__.py
│   ├── node.py           # Material collection orchestration
│   ├── input_router.py   # URL/DOI/Search detection
│   └── handlers/         # Source-specific handlers
│       ├── __init__.py
│       ├── base_handler.py
│       ├── paper_handler.py
│       ├── github_handler.py
│       ├── huggingface_handler.py
│       └── web_handler.py
│
├── evidence/             # omr-evidence node implementation
│   ├── __init__.py
│   └── node.py           # Evidence extraction, brief generation
│
└── contracts/            # Skill contracts for dependency resolution
    ├── omr-bootstrap.json
    ├── omr-collection.json
    ├── omr-evidence.json
    └── patterns/         # Pattern definitions
        ├── evidence-first.json
        ├── idea-first.json
        ├── decision-first.json
        ├── experiment-first.json
        └── rapid-prototype.json
```

---

## 2. Configuration Integration

### 2.1 Config Schema Extension

Add `OmrAgentConfig` to `alithia/config/schema.py`:

```python
class OmrAgentConfig(BaseModel):
    """OmniResearch agent configuration."""

    model_config = ConfigDict(extra="forbid")

    # Workspace settings
    workspace_base: str = Field(
        default="omr-output",
        description="Base directory for research workspaces (relative to soothe current workspace)"
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

    # Synthesis settings
    synthesis_mode: Literal["survey", "report", "manuscript", "brief"] = "survey"

    # Gate settings
    gate_a_criteria: list[str] = Field(
        default=["evidence_map_exists", "min_5_sources"],
        description="Gate A criteria before research planning"
    )
    gate_b_criteria: list[str] = Field(
        default=["research_brief_exists", "judgment_quality"],
        description="Gate B criteria before decision"
    )
```

### 2.2 Config File Location

Configuration stored in `~/.alithia/config.yml`:

```yaml
# Existing sections...
researcher_profile:
  research_interests: ["AI", "Machine Learning"]
  # ...

paperscout_agent:
  query: "cs.AI+cs.CV+cs.LG+cs.CL"
  # ...

paperlens_agent:
  sbert_model: "all-MiniLM-L6-v2"
  # ...

# NEW: OmniResearch section
omr_agent:
  workspace_base: "omr-output"  # Relative to soothe current workspace
  default_pattern: "auto"
  collection_depth: "default"
  max_papers_per_query: 10
  synthesis_mode: "survey"
```

### 2.3 Runtime Config

`OmrRuntimeConfig` derives from `Config.omr_agent`:

```python
class OmrRuntimeConfig(BaseModel):
    """OmniResearch runtime configuration (derived from global config)."""

    model_config = ConfigDict(extra="forbid")

    # Workspace
    workspace_base: Path  # Resolved: soothe_workspace / workspace_base
    research_topic: str

    # Pattern (resolved from auto or explicit)
    pattern: Literal["evidence-first", "idea-first", "decision-first",
                      "experiment-first", "rapid-prototype"]

    # Collection
    collection_depth: Literal["default", "full-repo", "download-dataset"]
    input_sources: list[str] = []  # URLs, DOIs, search queries

    # Integration
    llm_api_key: str | None = None
    llm_api_base: str | None = None
    llm_model: str = "qwen-turbo-latest"

    @classmethod
    def build_runtime_config(
        cls,
        global_config: Config,
        research_topic: str,
        soothe_workspace: Path,  # Current soothe workspace path
    ) -> OmrRuntimeConfig:
        """Build runtime config from global alithia config.

        Args:
            global_config: The loaded alithia Config object.
            research_topic: User-provided research topic.
            soothe_workspace: Current soothe workspace path (from context).
        """
        omr_cfg = global_config.omr_agent
        profile = global_config.researcher_profile

        # Resolve pattern (auto → detect or default to evidence-first)
        pattern = omr_cfg.default_pattern
        if pattern == "auto":
            pattern = "evidence-first"  # Default fallback

        # Resolve workspace base path relative to soothe current workspace
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

---

## 3. AgentState Design

```python
class AgentState(TypedDict):
    """LangGraph agent state for OmniResearch workflow."""

    # LangGraph message history
    messages: Annotated[list[Any], add_messages]

    # Configuration
    config: OmrRuntimeConfig
    user_id: str

    # Workspace context
    workspace_path: str  # workspace_base / {project-id}
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

---

## 4. Pattern Routing Graph

### 4.1 Graph Structure

The orchestrator uses pattern-based routing:

```python
def create_omr_graph(config: OmrRuntimeConfig, user_id: str) -> StateGraph:
    graph = StateGraph(AgentState)

    # Common nodes
    graph.add_node("bootstrap", bootstrap_node)
    graph.add_node("pattern_router", pattern_router_node)

    # Pattern-specific branches
    graph.add_node("collection", collection_node)
    graph.add_node("evidence", evidence_node)

    # Conditional edges
    graph.add_edge(START, "bootstrap")
    graph.add_edge("bootstrap", "pattern_router")
    graph.add_conditional_edges("pattern_router", route_by_pattern)

    # Evidence-First pattern edges
    graph.add_edge("collection", "evidence")
    # ... additional edges for full patterns

    graph.add_edge("evidence", END)  # Core pipeline ends here

    return graph
```

### 4.2 Pattern Routing Logic

```python
def route_by_pattern(state: AgentState) -> str:
    """Route to appropriate pattern branch based on state.pattern."""
    pattern = state["pattern"]

    # Core pipeline only implements collection + evidence
    # Idea-First and Decision-First patterns will route to collection first
    # in core implementation, then extend to their specific nodes in future phases
    routes = {
        "evidence-first": "collection",
        "idea-first": "collection",       # TODO: route to idea_note in future phase
        "decision-first": "collection",   # TODO: route to decision in future phase
        "experiment-first": "collection",
        "rapid-prototype": "collection",
    }

    return routes.get(pattern, "collection")


def pattern_router_node(state: AgentState) -> AgentState:
    """Detect pattern from user intent or use configured pattern."""
    config = state["config"]

    if config.pattern != "auto":
        state["pattern"] = config.pattern
    else:
        # Auto-detect heuristics:
        # - Paper URLs/DOIs → evidence-first
        # - Keywords like "hypothesis", "test", "validate" → experiment-first
        # - Keywords like "I think", "my idea", "hypothesize" → idea-first
        # - Keywords like "architecture", "design decision" → decision-first
        # - Default → evidence-first
        sources = state.get("input_sources", [])
        user_msg = str(state.get("messages", []))

        if any(is_paper_url(s) or is_doi(s) for s in sources):
            state["pattern"] = "evidence-first"
        elif any(kw in user_msg.lower() for kw in ["hypothesis", "test", "validate", "experiment"]):
            state["pattern"] = "experiment-first"
        elif any(kw in user_msg.lower() for kw in ["i think", "my idea", "hypothesize", "insight"]):
            state["pattern"] = "idea-first"
        elif any(kw in user_msg.lower() for kw in ["architecture", "design decision", "approach"]):
            state["pattern"] = "decision-first"
        else:
            state["pattern"] = "evidence-first"  # Default

    return state
```

---

## 5. Core Node Implementations

### 5.1 Bootstrap Node

```python
async def bootstrap_node(state: AgentState) -> AgentState:
    """Create research workspace with directory structure and CLAUDE.md."""
    config = state["config"]
    topic = config.research_topic

    # Generate project ID (lowercase-hyphenated)
    project_id = topic.lower().replace(" ", "-").replace("_", "-")
    workspace_path = config.workspace_base / project_id

    # Create directory structure
    dirs = ["raw/paper", "raw/web", "raw/github", "raw/dataset",
            "docs/survey", "docs/report", "docs/manuscript", "docs/brief",
            "docs/plans", "docs/ideas", "docs/index",
            "src/prototype", "src/evaluation", "wiki"]

    for dir_path in dirs:
        (workspace_path / dir_path).mkdir(parents=True, exist_ok=True)

    # Generate CLAUDE.md
    claude_md = generate_claude_md(topic, project_id, config.pattern)
    (workspace_path / "CLAUDE.md").write_text(claude_md)

    # Initialize skill tree state
    skill_tree = {
        "unlocked": ["omr-collection", "omr-idea-note"],
        "ready": [],
        "locked": ["omr-evidence", "omr-research-plan", "omr-decision",
                   "omr-evaluation", "omr-synthesis", "omr-wiki"],
        "completed": ["omr-bootstrap"]
    }

    # Initialize empty indexes
    (workspace_path / "docs/index/artifacts-index.json").write_text('{"artifacts": []}')

    # Update state
    state["workspace_path"] = str(workspace_path)
    state["project_id"] = project_id
    state["skill_tree"] = skill_tree
    state["completed_skills"] = ["omr-bootstrap"]
    state["info"].append(f"Workspace created at {workspace_path}")
    state["metrics"]["bootstrap_time"] = datetime.now().isoformat()

    return state
```

### 5.2 Collection Node

```python
async def collection_node(state: AgentState) -> AgentState:
    """Collect materials from papers, repos, datasets, and web sources."""
    config = state["config"]
    workspace_path = Path(state["workspace_path"])
    sources = state.get("input_sources", [])

    # Route inputs
    router = InputRouter()
    routed = router.route_inputs(sources)

    results = {"paper": [], "web": [], "github": [], "dataset": []}
    failed = []

    # Process each category
    for category, items in routed.items():
        handler = get_handler(category, config)
        for item in items:
            try:
                artifact = await handler.collect(item, workspace_path)
                results[category].append(artifact)
            except Exception as e:
                failed.append({"source": item, "error": str(e), "category": category})

    # Update indexes
    update_artifacts_index(workspace_path, results)

    # Update skill tree
    skill_tree = state["skill_tree"]
    skill_tree["locked"].remove("omr-evidence")
    skill_tree["ready"].append("omr-evidence")
    skill_tree["completed"].append("omr-collection")

    # Update state
    state["raw_materials"] = results
    state["failed_sources"] = failed
    state["skill_tree"] = skill_tree
    state["completed_skills"].append("omr-collection")
    state["info"].append(f"Collected {sum(len(v) for v in results.values())} materials")

    return state
```

### 5.3 Evidence Node

```python
async def evidence_node(state: AgentState) -> AgentState:
    """Extract evidence from collected materials and generate research brief."""
    workspace_path = Path(state["workspace_path"])
    materials = state["raw_materials"]

    # Read collected materials
    papers = [read_artifact(p) for p in materials.get("paper", [])]
    webs = [read_artifact(w) for w in materials.get("web", [])]

    # Extract evidence (minimal parsing - claims, citations, confidence)
    evidence_extractor = EvidenceExtractor(config=state["config"])
    evidence_map = await evidence_extractor.extract(papers + webs)

    # Generate research brief
    research_brief = await evidence_extractor.generate_brief(
        topic=state["research_topic"],
        evidence_map=evidence_map
    )

    # Write artifacts
    (workspace_path / "docs/evidence-map.md").write_text(
        format_evidence_map(evidence_map)
    )
    (workspace_path / "docs/research-brief.md").write_text(
        format_research_brief(research_brief)
    )

    # Update skill tree
    skill_tree = state["skill_tree"]
    skill_tree["ready"].remove("omr-evidence")
    skill_tree["locked"].remove("omr-research-plan")
    skill_tree["ready"].append("omr-research-plan")
    skill_tree["completed"].append("omr-evidence")

    # Update state
    state["evidence_map"] = evidence_map
    state["research_brief"] = research_brief
    state["skill_tree"] = skill_tree
    state["completed_skills"].append("omr-evidence")

    return state
```

---

## 6. Handler Architecture

### 6.1 Base Handler

```python
class BaseHandler(ABC):
    """Abstract base class for collection handlers."""

    def __init__(self, config: OmrRuntimeConfig):
        self.config = config
        self.max_retries = 2
        self.retry_delay = 2.0

    @abstractmethod
    async def collect(self, source: str, workspace: Path) -> Artifact:
        """Collect material from source and store in workspace."""
        pass

    async def with_retry(self, fn: Callable, *args) -> Any:
        """Execute with retry logic."""
        for attempt in range(self.max_retries + 1):
            try:
                return await fn(*args)
            except Exception as e:
                if attempt == self.max_retries:
                    raise
                await asyncio.sleep(self.retry_delay)
```

### 6.2 Paper Handler

```python
class PaperHandler(BaseHandler):
    """Handle arxiv papers, DOIs, and PDF URLs."""

    async def collect(self, source: str, workspace: Path) -> Artifact:
        # Detect source type
        if is_arxiv_id(source):
            return await self._collect_arxiv(source, workspace)
        elif is_doi(source):
            return await self._collect_doi(source, workspace)
        elif is_pdf_url(source):
            return await self._collect_pdf_url(source, workspace)

    async def _collect_arxiv(self, arxiv_id: str, workspace: Path) -> Artifact:
        """Use arxiv SDK for reliable downloads with rich metadata."""
        import arxiv

        paper = next(arxiv.Search(id_list=[arxiv_id]).results())
        filename = f"arxiv-{arxiv_id}.md"

        # Download PDF
        pdf_path = workspace / "raw/paper" / f"{arxiv_id}.pdf"
        paper.download_pdf(dirpath=str(pdf_path.parent), filename=pdf_path.name)

        # Extract text and metadata
        content = await self._extract_pdf_content(pdf_path)
        metadata = {
            "id": arxiv_id,
            "title": paper.title,
            "authors": [a.name for a in paper.authors],
            "doi": paper.doi,
            "categories": paper.categories,
            "collected_at": datetime.now().isoformat(),
        }

        # Write markdown artifact
        artifact_path = workspace / "raw/paper" / filename
        artifact_path.write_text(format_artifact(content, metadata))

        return Artifact(path=str(artifact_path), metadata=metadata, type="paper")
```

### 6.3 GitHub Handler

```python
class GitHubHandler(BaseHandler):
    """Handle GitHub repository URLs."""

    async def collect(self, source: str, workspace: Path) -> Artifact:
        repo_name = parse_github_repo(source)

        # Fetch README and metadata via GitHub API
        readme = await self._fetch_readme(repo_name)
        metadata = await self._fetch_metadata(repo_name)

        filename = f"github-{repo_name.replace('/', '-')}.md"
        artifact_path = workspace / "raw/github" / filename

        artifact_path.write_text(format_artifact(readme, metadata))

        # Optional: full clone if --full-repo
        if self.config.collection_depth == "full-repo":
            await self._clone_repo(repo_name, workspace)

        return Artifact(path=str(artifact_path), metadata=metadata, type="github")
```

---

## 7. Soothe Plugin Integration

### 7.1 Plugin Registration

```python
# alithia/omr/__init__.py

from soothe_sdk.plugin import plugin, subagent
from alithia.omr.implementation import create_omr_subagent
from alithia.omr.state import OmrRuntimeConfig, AgentState

@plugin(
    name="omr",
    version="1.0.0",
    description="OmniResearch structured workflow with pattern-based routing",
    dependencies=[
        "langgraph>=0.2.0",
        "arxiv>=2.0.0",
        "pdfplumber>=0.10.0",
    ],
    trust_level="standard",
)
class OmniResearchPlugin:
    """OmniResearch plugin for structured research workflows."""

    async def on_load(self, context: Any) -> None:
        context.logger.info("Loading OmniResearch plugin v1.0.0")

    @subagent(
        name="omni-research",
        description=(
            "Structured research workflow that guides evidence-bound, traceable research "
            "with pattern-based flexibility. Supports Evidence-First, Idea-First, "
            "Decision-First, Experiment-First, and Rapid-Prototype patterns. "
            "Use for systematic literature reviews, hypothesis validation, and research projects."
        ),
        triggers=[
            "research",
            "omni",
            "start research",
            "literature review",
            "systematic review",
            "workflow",
        ],
    )
    async def create_subagent(
        self,
        model: Any,
        config: Any,
        context: Any,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Create OmniResearch subagent."""
        alithia_config = kwargs.get("alithia_config")
        user_id = kwargs.get("user_id", "default")
        research_topic = kwargs.get("research_topic", kwargs.get("query", ""))

        # Build runtime config
        if alithia_config:
            from alithia.config import Config
            full_config = Config(**alithia_config)
            # Get soothe workspace from context
            soothe_workspace = Path(context.get("workspace", SOOTHE_HOME))
            runtime_config = OmrRuntimeConfig.build_runtime_config(
                full_config, research_topic, soothe_workspace
            )
        else:
            # Fallback: use soothe default workspace
            soothe_workspace = Path(context.get("workspace", SOOTHE_HOME))
            runtime_config = OmrRuntimeConfig(
                workspace_base=soothe_workspace / "omr-output",
                research_topic=research_topic,
                pattern="evidence-first",
            )

        return create_omr_subagent(config=runtime_config, user_id=user_id)
```

### 7.2 Plugin Registration Update

Add to `alithia/plugin_registration.py`:

```python
def register_alithia_plugins() -> None:
    # ... existing registration ...

    # Import and register omr plugin
    from alithia.omr import OmniResearchPlugin

    registry.register(
        getattr(OmniResearchPlugin, "_plugin_manifest"),
        source="config",
        priority=30,
    )
    logger.info("Manually registered omr plugin")
```

### 7.3 Agent Integration

Update `alithia/agent.py`:

```python
def _ensure_alithia_subagents_enabled(self) -> None:
    alithia_subagents = ["paperscout", "paperlens", "omni-research"]

    for name in alithia_subagents:
        if name not in self._soothe_config.subagents:
            self._soothe_config.subagents[name] = SubagentConfig(enabled=True)
```

---

## 8. Skill Tree State Management

### 8.1 Tree State File

Stored in workspace: `{workspace_path}/skill-tree.json`

```json
{
  "unlocked": ["omr-collection", "omr-idea-note"],
  "ready": ["omr-evidence"],
  "locked": ["omr-research-plan", "omr-decision", "omr-evaluation"],
  "completed": ["omr-bootstrap", "omr-collection"],
  "pattern": "evidence-first",
  "last_updated": "2026-06-17T10:30:00Z"
}
```

### 8.2 Skill Tree Node

```python
DEFAULT_TREE_STATE = {
    "unlocked": ["omr-collection", "omr-idea-note"],
    "ready": [],
    "locked": ["omr-evidence", "omr-research-plan", "omr-decision",
               "omr-evaluation", "omr-synthesis", "omr-wiki"],
    "completed": ["omr-bootstrap"]
}

def skill_tree_node(state: AgentState) -> AgentState:
    """Update skill tree after each skill completion."""
    workspace_path = Path(state["workspace_path"])
    tree_path = workspace_path / "skill-tree.json"

    # Read current state
    if tree_path.exists():
        tree_state = json.loads(tree_path.read_text())
    else:
        tree_state = DEFAULT_TREE_STATE

    # Update based on produced artifacts
    completed_skill = state["current_skill"]

    # Move skill to completed
    if completed_skill in tree_state["ready"]:
        tree_state["ready"].remove(completed_skill)
    elif completed_skill in tree_state["unlocked"]:
        tree_state["unlocked"].remove(completed_skill)

    tree_state["completed"].append(completed_skill)

    # Check downstream skills
    contracts = load_contracts()
    for skill_name in tree_state["locked"]:
        contract = contracts[skill_name]
        if check_prerequisites(contract, tree_state):
            tree_state["locked"].remove(skill_name)
            tree_state["ready"].append(skill_name)

    # Persist
    tree_state["last_updated"] = datetime.now().isoformat()
    tree_path.write_text(json.dumps(tree_state, indent=2))

    state["skill_tree"] = tree_state
    return state
```

---

## 9. Gate Enforcement

### 9.1 Gate Definitions

| Gate | Location | Criteria |
|------|----------|----------|
| **Gate A** | Before `omr-research-plan` | evidence-map.md exists, min 5 sources |
| **Gate B** | Before `omr-decision` | research-brief.md exists, judgment quality |
| **Gate C** | Before `omr-evaluation` | decision.md exists, actionable experiment plan |
| **Gate D** | Before `omr-synthesis` | evaluation-report.md exists, results documented |

### 9.2 Gate Check Node

```python
async def gate_check_node(state: AgentState, gate_id: str) -> AgentState:
    """Check gate criteria before skill progression."""
    workspace_path = Path(state["workspace_path"])
    config = state["config"]

    def check_judgment_quality(state: AgentState) -> bool:
        """Check if research brief has sufficient judgment quality."""
        brief = state.get("research_brief")
        if not brief:
            return False
        # Criteria: has research question, has scope definition, has at least 3 evidence references
        return (
            brief.get("research_question") is not None
            and brief.get("scope") is not None
            and len(brief.get("evidence_references", [])) >= 3
        )

    gate_criteria = {
        "gate_a": [
            (workspace_path / "docs/evidence-map.md").exists(),
            sum(len(v) for v in state["raw_materials"].values()) >= 5,
        ],
        "gate_b": [
            (workspace_path / "docs/research-brief.md").exists(),
            check_judgment_quality(state),
        ],
        # ... additional gates for Phase 6+
    }

    criteria_met = all(gate_criteria.get(gate_id, []))

    if not criteria_met:
        missing = [i for i, met in enumerate(gate_criteria.get(gate_id, [])) if not met]
        state["pending_gates"][gate_id] = {"status": "blocked", "missing": missing}
        # Block progression and request user action
    else:
        state["pending_gates"][gate_id] = {"status": "passed"}

    return state
```

---

## 10. Output Directory Structure

After bootstrap, workspace structure under `{soothe_workspace}/omr-output/{project-id}/`:

```
{project-id}/
├── CLAUDE.md              # Project context for AI agents
├── skill-tree.json        # Skill tree state
│
├── raw/                   # Collected materials (markdown artifacts)
│   ├── paper/
│   │   ├── arxiv-2402-12345.md
│   │   └── doi-10-1234-abc.md
│   ├── web/
│   │   └── url-hashabc123.md
│   ├── github/
│   │   └── github-user-project.md
│   └── dataset/
│       └── hf-dataset-name.md
│
├── docs/                  # Distilled knowledge
│   ├── evidence-map.md    # Primary evidence mapping
│   ├── research-brief.md  # Research question definition
│   ├── survey/            # Survey chapters (future)
│   ├── report/            # Structured findings (future)
│   ├── plans/             # Formal artifacts (future)
│   ├── ideas/             # Subjective insights (future)
│   └── index/
│       └── artifacts-index.json
│
├── src/                   # Generated code (future)
│   ├── prototype/
│   └── evaluation/
│
└── wiki/                  # Living knowledge base (future)
    └── README.md
```

---

## 11. Success Criteria

- [ ] `omr` plugin registered in soothe global registry
- [ ] `omni-research` subagent available in soothe config
- [ ] Bootstrap node creates correct workspace structure
- [ ] Pattern routing node detects or uses configured pattern
- [ ] Collection node processes papers, repos, web sources
- [ ] Evidence node generates evidence-map and research-brief
- [ ] Skill tree state persisted and updated correctly
- [ ] Configuration loaded from `~/.alithia/config.yml`
- [ ] Workspace output in `{soothe_workspace}/omr-output/`
- [ ] Gate enforcement blocks progression when criteria not met
- [ ] Failed sources handled gracefully with error artifacts
- [ ] Subagent accessible via soothe StrangeLoop routing

---

## 12. Testing Strategy

### 12.1 Unit Tests

- `test_bootstrap_node.py`: Workspace creation, CLAUDE.md generation
- `test_pattern_router.py`: Pattern detection logic
- `test_collection_handlers.py`: Each handler with mock sources
- `test_evidence_node.py`: Evidence extraction and brief generation
- `test_skill_tree.py`: State management and unlocking logic

### 12.2 Integration Tests

- `test_omr_subagent.py`: Full workflow from bootstrap to evidence
- `test_gate_enforcement.py`: Gate blocking and passing scenarios
- `test_pattern_workflow.py`: Evidence-First pattern complete

### 12.3 Test Fixtures

- Mock arxiv papers (cached PDFs)
- Mock GitHub API responses
- Mock web snapshots
- Sample workspace state files

---

## 13. Dependencies

Add to `pyproject.toml`:

```toml
dependencies = [
    # Existing...
    "langgraph>=0.2.0",
    "arxiv>=2.0.0",
    "pdfplumber>=0.10.0",
    "html2text>=2020.1.16",
]
```

---

## 14. Implementation Phases

### Phase 1: Foundation (Est. 2-3 days)

1. Create package structure (`alithia/omr/`)
2. Add `OmrAgentConfig` to schema
3. Implement `OmrRuntimeConfig` and `AgentState`
4. Create plugin registration (`__init__.py`)
5. Update `plugin_registration.py` and `agent.py`

### Phase 2: Bootstrap Node (Est. 1-2 days)

1. Implement workspace creation
2. Generate CLAUDE.md template
3. Initialize skill tree state
4. Pattern router node (auto-detect + explicit)

### Phase 3: Collection Node (Est. 3-4 days)

1. Input router (URL/DOI/Search detection)
2. Paper handler (arxiv SDK integration)
3. GitHub handler (API + README fetch)
4. Web handler (HTTP fetch + markdown)
5. HuggingFace handler (README + metadata)
6. Error handling and retry logic
7. Artifact index updates

### Phase 4: Evidence Node (Est. 2-3 days)

1. Evidence extraction from materials
2. Research brief generation
3. Confidence level assignment
4. Skill tree unlocking

### Phase 5: Integration (Est. 1-2 days)

1. Connect to soothe StrangeLoop
2. Test routing triggers
3. Integration with existing alithia config
4. End-to-end workflow test

**Total Estimated: 9-14 days**

---

## 15. Future Extensions (Post-Core Pipeline)

After core pipeline is complete, future phases can add:

1. **Phase 6**: research_plan node (Gate A)
2. **Phase 7**: decision node (Gate B)
3. **Phase 8**: evaluation node (Gate C)
4. **Phase 9**: synthesis node (Gate D)
5. **Phase 10**: wiki node

Each phase adds nodes following the same LangGraph pattern.

---

_Draft completed 2026-06-17. Ready for review before Platonic Coding Phase 1 RFC formalization._
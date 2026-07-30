"""OmniResearch state and configuration models.

AgentState TypedDict for LangGraph workflow.
OmrRuntimeConfig for runtime parameters derived from global config.

RFC Reference: RFC-011 Section 7, Section 8.2
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Annotated, Any, Literal, TypedDict

from langgraph.graph.message import add_messages
from pydantic import BaseModel, ConfigDict

from alithia import SOOTHE_HOME

if TYPE_CHECKING:
    from alithia.config.schema import Config


class OmrRuntimeConfig(BaseModel):
    """OmniResearch runtime configuration (derived from global config).

    RFC Reference: RFC-011 Section 8.2
    """

    model_config = ConfigDict(extra="forbid")

    # Workspace
    workspace_base: Path  # Resolved: soothe_workspace / workspace_base
    research_topic: str

    # Pattern (resolved from auto or explicit)
    pattern: Literal[
        "evidence-first", "idea-first", "decision-first", "experiment-first", "rapid-prototype"
    ]

    # Collection
    collection_depth: Literal["default", "full-repo", "download-dataset"] = "default"
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
        soothe_workspace: Path | None = None,
    ) -> OmrRuntimeConfig:
        """Build runtime config from global alithia config.

        Args:
            global_config: The loaded alithia Config object.
            research_topic: User-provided research topic.
            soothe_workspace: Current soothe workspace path (from context).

        Returns:
            OmrRuntimeConfig ready for agent execution.
        """
        omr_cfg = global_config.omr_agent
        profile = global_config.researcher_profile

        # Resolve pattern (auto → detect or default to evidence-first)
        pattern = omr_cfg.default_pattern
        if pattern == "auto":
            pattern = "evidence-first"  # Default fallback

        # Resolve workspace base path relative to soothe current workspace
        if soothe_workspace is None:
            soothe_workspace = SOOTHE_HOME
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


DEFAULT_TREE_STATE = {
    "unlocked": ["omr-collection", "omr-idea-note"],
    "ready": [],
    "locked": [
        "omr-evidence",
        "omr-research-plan",
        "omr-decision",
        "omr-evaluation",
        "omr-synthesis",
        "omr-wiki",
    ],
    "completed": ["omr-bootstrap"],
    "pattern": "evidence-first",
    "last_updated": "",
}


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
    workspace_path: str  # workspace_base / {project-id}
    project_id: str  # Lowercase-hyphenated topic
    research_topic: str
    pattern: Literal[
        "evidence-first", "idea-first", "decision-first", "experiment-first", "rapid-prototype"
    ]

    # Skill tree state
    skill_tree: dict  # {unlocked, ready, locked, completed}
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


def default_agent_state(
    runtime_config: OmrRuntimeConfig,
    user_id: str,
) -> AgentState:
    """Build a complete initial AgentState for graph invocation."""
    return {
        "messages": [],
        "config": runtime_config,
        "user_id": user_id,
        "workspace_path": "",
        "project_id": "",
        "research_topic": runtime_config.research_topic,
        "pattern": runtime_config.pattern,
        "skill_tree": DEFAULT_TREE_STATE.copy(),
        "current_skill": "",
        "completed_skills": [],
        "pending_gates": {},
        "raw_materials": {"paper": [], "web": [], "github": [], "dataset": []},
        "materials_index": None,
        "evidence_map": None,
        "research_brief": None,
        "input_sources": runtime_config.input_sources,
        "collection_results": {},
        "failed_sources": [],
        "errors": [],
        "info": [],
        "metrics": {},
    }


__all__ = [
    "OmrRuntimeConfig",
    "AgentState",
    "DEFAULT_TREE_STATE",
    "default_agent_state",
]

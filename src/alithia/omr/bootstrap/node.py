"""Bootstrap node implementation for OmniResearch workflow.

Creates workspace directory structure, CLAUDE.md, and initializes skill tree.

RFC Reference: RFC-011 Section 5.2, Section 13
"""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime
from pathlib import Path

from alithia.omr.skill_tree import DEFAULT_TREE_STATE

logger = logging.getLogger(__name__)


def generate_project_id(research_topic: str) -> str:
    """Generate project ID from research topic (lowercase-hyphenated).

    Args:
        research_topic: User-provided research topic.

    Returns:
        Lowercase-hyphenated project ID.
    """
    # Remove special characters, convert to lowercase, replace spaces with hyphens
    cleaned = re.sub(r"[^\w\s-]", "", research_topic.lower())
    cleaned = re.sub(r"[\s_]+", "-", cleaned)
    cleaned = re.sub(r"-+", "-", cleaned)
    return cleaned.strip("-")


def generate_claude_md(
    research_topic: str,
    project_id: str,
    pattern: str,
) -> str:
    """Generate CLAUDE.md content for workspace.

    Args:
        research_topic: User-provided research topic.
        project_id: Generated project ID.
        pattern: Selected research pattern.

    Returns:
        CLAUDE.md markdown content.
    """
    timestamp = datetime.now().isoformat()

    return f"""---
id: PROJ-{timestamp[:10]}
type: project
topic: "{research_topic}"
created_at: {timestamp}
pattern_detected: {pattern}
workspace: ./{project_id}/
status: initialized
---

# {research_topic} Research Project

## Project Overview

This workspace is initialized for researching **{research_topic}**.

## Omni-Research Integration

This project uses omni-research skills for evidence-bound, traceable research.

### Available Skills
- omr-collection: Collect and classify materials
- omr-evidence: Map evidence landscape
- omr-research-plan: Judge evidence and plan research
- omr-decision: Make architectural decisions
- omr-evaluation: Run experiments
- omr-synthesis: Write findings (survey/report/manuscript/brief)
- omr-wiki: Generate wiki
- omr-reconcile: Update state on evidence changes
- omr-idea-note: Capture insights
- omr-research-archive: Snapshot progress

### Evidence Philosophy
- All claims must be traceable to sources
- Evidence boundaries: "proven", "suggested", "inferred"
- Never claim "paper proves X" when it only suggests

## Workspace Structure

- `raw/`: Collected materials (papers, web, github, datasets)
- `docs/`: Distilled knowledge (evidence-map, research-brief, synthesis)
- `src/`: Generated code (prototype, evaluation)
- `wiki/`: Living knowledge base

## Research Pattern: {pattern}

{get_pattern_description(pattern)}

## Next Steps

Run `omr-collection` to begin material collection.
"""


def get_pattern_description(pattern: str) -> str:
    """Get description for research pattern."""
    descriptions = {
        "evidence-first": (
            "Rigorous research starting from literature collection. "
            "Systematic review with strong evidence foundation before decisions."
        ),
        "idea-first": (
            "Exploratory research starting from creative insights. "
            "Less structured, allows for speculation before evidence."
        ),
        "decision-first": (
            "Engineering-focused research validating architectural decisions. "
            "Hypothesis-driven with targeted evidence."
        ),
        "experiment-first": (
            "Empirical research with rapid iteration. Testing before full evidence collection."
        ),
        "rapid-prototype": (
            "Fastest research mode with minimal gates. "
            "Quick exploration without formal constraints."
        ),
    }
    return descriptions.get(pattern, "Standard research workflow.")


def create_workspace_structure(workspace_path: Path) -> None:
    """Create complete workspace directory structure.

    Args:
        workspace_path: Root workspace path.
    """
    directories = [
        # Raw materials
        "raw/paper",
        "raw/web",
        "raw/github",
        "raw/dataset",
        "raw/failed",
        # Distilled knowledge
        "docs/survey",
        "docs/report",
        "docs/manuscript",
        "docs/brief",
        "docs/plans",
        "docs/ideas",
        "docs/archive",
        "docs/index/versions",
        # Generated code
        "src/prototype",
        "src/evaluation",
        "src/tools",
        # Wiki
        "wiki",
    ]

    for dir_path in directories:
        (workspace_path / dir_path).mkdir(parents=True, exist_ok=True)

    logger.info(f"Created {len(directories)} directories in {workspace_path}")


def initialize_indexes(workspace_path: Path) -> None:
    """Initialize empty artifact index files.

    Args:
        workspace_path: Root workspace path.
    """
    index_dir = workspace_path / "docs" / "index"

    # Create empty artifacts index
    artifacts_index = index_dir / "artifacts-index.json"
    artifacts_index.write_text(json.dumps({"artifacts": []}, indent=2))

    # Create empty papers index
    papers_index = index_dir / "papers-index.json"
    papers_index.write_text(json.dumps({"papers": []}, indent=2))

    # Create .gitkeep for empty directories
    (workspace_path / "docs" / "index" / "versions" / ".gitkeep").touch()

    logger.debug("Initialized empty index files")


def initialize_skill_tree(workspace_path: Path, pattern: str) -> dict:
    """Initialize skill tree state for workspace.

    Args:
        workspace_path: Root workspace path.
        pattern: Selected research pattern.

    Returns:
        Initial skill tree state dict.
    """
    tree_state = DEFAULT_TREE_STATE.copy()
    tree_state["pattern"] = pattern
    tree_state["last_updated"] = datetime.now().isoformat()

    tree_path = workspace_path / "skill-tree.json"
    tree_path.write_text(json.dumps(tree_state, indent=2))

    logger.debug(f"Initialized skill tree with pattern: {pattern}")
    return tree_state


async def bootstrap_node(state: dict) -> dict:
    """Bootstrap node implementation.

    Creates workspace structure, CLAUDE.md, and initializes skill tree.

    Args:
        state: Current agent state.

    Returns:
        Updated agent state with workspace_path, project_id, skill_tree.
    """
    config = state["config"]
    research_topic = config.research_topic
    pattern = state.get("pattern", config.pattern)

    # Generate project ID
    project_id = generate_project_id(research_topic)

    # Create workspace path
    workspace_base = config.workspace_base
    workspace_path = workspace_base / project_id

    # Check for duplicate workspace
    if workspace_path.exists():
        # Add timestamp suffix for uniqueness
        timestamp_suffix = datetime.now().strftime("%Y%m%dT%H%M%S")
        project_id = f"{project_id}-{timestamp_suffix}"
        workspace_path = workspace_base / project_id
        state["info"].append(f"Workspace existed, created new: {project_id}")

    # Create directory structure
    create_workspace_structure(workspace_path)

    # Generate CLAUDE.md
    claude_md_content = generate_claude_md(research_topic, project_id, pattern)
    (workspace_path / "CLAUDE.md").write_text(claude_md_content)

    # Initialize indexes
    initialize_indexes(workspace_path)

    # Initialize skill tree
    skill_tree = initialize_skill_tree(workspace_path, pattern)

    # Update state
    state["workspace_path"] = str(workspace_path)
    state["project_id"] = project_id
    state["skill_tree"] = skill_tree
    state["current_skill"] = "omr-bootstrap"
    state["completed_skills"] = ["omr-bootstrap"]
    state["info"].append(f"Workspace created at {workspace_path}")
    state["metrics"]["bootstrap_time"] = datetime.now().isoformat()

    logger.info(f"Bootstrap complete: workspace={workspace_path}, pattern={pattern}")

    return state


__all__ = [
    "generate_project_id",
    "generate_claude_md",
    "create_workspace_structure",
    "initialize_indexes",
    "initialize_skill_tree",
    "bootstrap_node",
]

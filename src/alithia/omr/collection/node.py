"""Collection node implementation for OmniResearch workflow.

Orchestrates handlers for multiple source types with retry/fallback.

RFC Reference: RFC-011 Section 10
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

from alithia.omr.collection.handlers.base_handler import Artifact, BaseHandler
from alithia.omr.collection.handlers.github_handler import GitHubHandler
from alithia.omr.collection.handlers.huggingface_handler import HuggingFaceHandler
from alithia.omr.collection.handlers.paper_handler import PaperHandler
from alithia.omr.collection.handlers.web_handler import WebHandler
from alithia.omr.pattern_router import InputRouter
from alithia.omr.skill_tree import SkillTree

logger = logging.getLogger(__name__)


def get_handler(category: str) -> BaseHandler:
    """Get appropriate handler for source category.

    Args:
        category: Source category (paper/github/huggingface/web).

    Returns:
        Handler instance.
    """
    handlers = {
        "paper": PaperHandler,
        "github": GitHubHandler,
        "huggingface": HuggingFaceHandler,
        "web": WebHandler,
    }

    handler_cls = handlers.get(category, WebHandler)  # Default to web
    return handler_cls()


def update_artifacts_index(workspace: Path, results: dict[str, list[Artifact]]) -> None:
    """Update artifacts-index.json with collected artifacts.

    Args:
        workspace: Workspace root path.
        results: Dict of collected artifacts by category.
    """
    index_path = workspace / "docs" / "index" / "artifacts-index.json"

    # Read existing index
    if index_path.exists():
        try:
            index_data = json.loads(index_path.read_text())
        except json.JSONDecodeError:
            index_data = {"artifacts": []}
    else:
        index_data = {"artifacts": []}

    # Add new artifacts
    for category, artifacts in results.items():
        for artifact in artifacts:
            index_data["artifacts"].append(artifact.to_dict())

    # Write updated index
    index_path.write_text(json.dumps(index_data, indent=2))
    logger.info(f"Updated artifacts index with {len(index_data['artifacts'])} items")


async def collection_node(state: dict) -> dict:
    """Collection node implementation.

    Collects materials from multiple sources with retry/fallback.

    Args:
        state: Current agent state.

    Returns:
        Updated agent state with raw_materials, failed_sources.
    """
    config = state["config"]
    workspace_path = Path(state["workspace_path"])
    input_sources = state.get("input_sources", config.input_sources)

    # Route inputs by type
    router = InputRouter()
    routed = router.route_inputs(input_sources)

    results: dict[str, list[Artifact]] = {
        "paper": [],
        "web": [],
        "github": [],
        "dataset": [],
    }
    failed: list[dict[str, Any]] = []

    # Process each category
    for category, sources in routed.items():
        if not sources:
            continue

        handler = get_handler(category)

        for source in sources:
            try:
                artifact = await handler.collect(source, workspace_path)
                results[category].append(artifact)

                # Emit event
                state["info"].append(f"Collected {category}: {source}")

            except Exception as e:
                logger.error(f"Failed to collect {source}: {e}")

                # Try fallback to web handler
                try:
                    web_handler = WebHandler()
                    artifact = await web_handler.collect(source, workspace_path)
                    results["web"].append(artifact)
                    state["info"].append(f"Collected via fallback (web): {source}")
                except Exception as fallback_error:
                    # Create error artifact
                    handler.create_error_artifact(
                        workspace_path, source, str(e), category, handler.max_retries
                    )
                    failed.append(
                        {
                            "source": source,
                            "category": category,
                            "error": str(e),
                            "fallback_error": str(fallback_error),
                        }
                    )
                    state["errors"].append(f"Failed to collect {source}: {e}")

    # Update indexes
    update_artifacts_index(workspace_path, results)

    # Update skill tree
    skill_tree_path = workspace_path / "skill-tree.json"
    skill_tree = SkillTree(skill_tree_path)
    skill_tree.mark_completed("omr-collection")

    # Convert artifacts to state-compatible format
    raw_materials = {
        "paper": [{"path": a.path, "metadata": a.metadata} for a in results["paper"]],
        "web": [{"path": a.path, "metadata": a.metadata} for a in results["web"]],
        "github": [{"path": a.path, "metadata": a.metadata} for a in results["github"]],
        "dataset": [{"path": a.path, "metadata": a.metadata} for a in results["dataset"]],
    }

    # Update state
    state["raw_materials"] = raw_materials
    state["failed_sources"] = failed
    state["skill_tree"] = skill_tree.state
    state["current_skill"] = "omr-collection"
    state["completed_skills"].append("omr-collection")
    state["collection_results"] = {
        "total_collected": sum(len(v) for v in results.values()),
        "total_failed": len(failed),
        "by_category": {k: len(v) for k, v in results.items()},
    }
    state["metrics"]["collection_time"] = datetime.now().isoformat()

    # Summary info
    total = sum(len(v) for v in results.values())
    state["info"].append(f"Collected {total} materials ({len(failed)} failed)")

    logger.info(f"Collection complete: {total} collected, {len(failed)} failed")

    return state


__all__ = [
    "collection_node",
    "get_handler",
    "update_artifacts_index",
]

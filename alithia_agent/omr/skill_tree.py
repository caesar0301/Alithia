"""Skill tree state management for OmniResearch workflow.

Tracks skill progress (unlocked/ready/locked/completed) and provides
prerequisite-based unlocking logic.

RFC Reference: RFC-010 Section 11
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

DEFAULT_TREE_STATE: dict[str, Any] = {
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


class SkillTree:
    """Skill tree state management.

    RFC Reference: RFC-010 Section 11.2
    """

    def __init__(self, tree_path: Path) -> None:
        """Initialize skill tree from file or defaults.

        Args:
            tree_path: Path to skill-tree.json in workspace.
        """
        self.tree_path = tree_path
        self.state = self._load_state()

    def _load_state(self) -> dict[str, Any]:
        """Load state from file or return defaults."""
        if self.tree_path.exists():
            try:
                return json.loads(self.tree_path.read_text())
            except json.JSONDecodeError:
                logger.warning(f"Invalid skill-tree.json at {self.tree_path}, using defaults")
        return DEFAULT_TREE_STATE.copy()

    def save_state(self) -> None:
        """Persist state to skill-tree.json."""
        self.state["last_updated"] = datetime.now().isoformat()
        self.tree_path.write_text(json.dumps(self.state, indent=2))

    def mark_completed(self, skill_name: str) -> None:
        """Mark skill as completed and unlock downstream skills.

        Args:
            skill_name: Name of completed skill.
        """
        # Remove from current state
        if skill_name in self.state["unlocked"]:
            self.state["unlocked"].remove(skill_name)
        elif skill_name in self.state["ready"]:
            self.state["ready"].remove(skill_name)

        # Add to completed
        if skill_name not in self.state["completed"]:
            self.state["completed"].append(skill_name)

        # Check downstream skills for unlocking
        self._check_downstream_unlocking(skill_name)

        self.save_state()
        logger.info(f"Skill '{skill_name}' marked as completed")

    def _check_downstream_unlocking(self, completed_skill: str) -> None:
        """Check if completed skill unlocks downstream skills."""
        # Define skill dependencies (simplified for core pipeline)
        dependencies = {
            "omr-bootstrap": ["omr-collection"],
            "omr-collection": ["omr-evidence"],
            "omr-evidence": ["omr-research-plan"],
            "omr-research-plan": ["omr-decision"],
            "omr-decision": ["omr-evaluation"],
            "omr-evaluation": ["omr-synthesis"],
            "omr-synthesis": ["omr-wiki"],
        }

        downstream_skills = dependencies.get(completed_skill, [])
        for skill in downstream_skills:
            if skill in self.state["locked"]:
                self.state["locked"].remove(skill)
                self.state["ready"].append(skill)
                logger.info(f"Skill '{skill}' unlocked and ready")

    def check_prerequisites(self, skill_name: str) -> bool:
        """Check if skill prerequisites are satisfied.

        Args:
            skill_name: Skill to check.

        Returns:
            True if skill can be invoked.
        """
        if skill_name in self.state["unlocked"]:
            return True
        if skill_name in self.state["ready"]:
            return True
        return False

    def get_visualization(self) -> str:
        """Generate ASCII tree visualization.

        Returns:
            ASCII art skill tree.
        """
        lines = ["📊 Skill Tree Progress"]
        lines.append("=" * 40)
        lines.append("")

        # Completed
        if self.state["completed"]:
            lines.append("✓ Completed:")
            for skill in self.state["completed"]:
                lines.append(f"  [{skill}]")
            lines.append("")

        # Unlocked
        if self.state["unlocked"]:
            lines.append("○ Unlocked (available):")
            for skill in self.state["unlocked"]:
                lines.append(f"  [{skill}]")
            lines.append("")

        # Ready
        if self.state["ready"]:
            lines.append("● Ready (prerequisites satisfied):")
            for skill in self.state["ready"]:
                lines.append(f"  [{skill}]")
            lines.append("")

        # Locked
        if self.state["locked"]:
            lines.append("🔒 Locked (missing prerequisites):")
            for skill in self.state["locked"]:
                lines.append(f"  [{skill}]")
            lines.append("")

        return "\n".join(lines)

    def get_progress_stats(self) -> dict[str, int]:
        """Get statistics about skill tree progress."""
        total = (
            len(self.state["unlocked"])
            + len(self.state["ready"])
            + len(self.state["locked"])
            + len(self.state["completed"])
        )
        return {
            "total": total,
            "completed": len(self.state["completed"]),
            "unlocked": len(self.state["unlocked"]),
            "ready": len(self.state["ready"]),
            "locked": len(self.state["locked"]),
        }


__all__ = ["SkillTree", "DEFAULT_TREE_STATE"]

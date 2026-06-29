"""Scan a directory of research-interests Markdown files into units.

See RFC-010 §7. The loader is a pure function: no network, no writes, no
cache. It tolerates a missing/empty directory (returns ``[]``) and skips
individual malformed files with a warning rather than raising.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path

import yaml

from alithia_agent.research_interests.model import ResearchInterest

logger = logging.getLogger(__name__)

# Matches a leading ---\n...\n--- frontmatter block.
_FRONTMATTER_RE = re.compile(r"\A---\s*\n(.*?)\n---\s*\n?(.*)\Z", re.DOTALL)


def _parse_file(path: Path) -> ResearchInterest | None:
    """Parse one .md file. Return None (with a warning) if invalid."""
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as e:
        logger.warning("research_interests: cannot read %s: %s", path, e)
        return None

    match = _FRONTMATTER_RE.match(text)
    if not match:
        logger.warning("research_interests: %s has no frontmatter, skipping", path)
        return None

    raw_meta, body = match.group(1), match.group(2)
    try:
        meta = yaml.safe_load(raw_meta) or {}
    except yaml.YAMLError as e:
        logger.warning("research_interests: invalid YAML in %s: %s", path, e)
        return None

    if not isinstance(meta, dict):
        logger.warning("research_interests: frontmatter in %s is not a mapping", path)
        return None

    if not meta.get("title"):
        logger.warning("research_interests: %s missing required 'title', skipping", path)
        return None

    try:
        return ResearchInterest(body=body.strip(), **meta)
    except Exception as e:  # pydantic validation errors
        logger.warning("research_interests: %s failed validation: %s", path, e)
        return None


def load_research_interests(directory: Path | str) -> list[ResearchInterest]:
    """Load all *.md knowledge units under ``directory`` (RFC-010 §7.1).

    Args:
        directory: Path to the research_interests directory.

    Returns:
        Units in stable path-sorted order. Empty list for a missing/empty
        directory or when every file is malformed.
    """
    root = Path(directory)
    if not root.exists() or not root.is_dir():
        return []

    units: list[ResearchInterest] = []
    for path in sorted(root.rglob("*.md")):
        unit = _parse_file(path)
        if unit is not None:
            units.append(unit)
    return units


__all__ = ["load_research_interests"]

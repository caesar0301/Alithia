"""Pattern detection and routing for OmniResearch workflow.

Auto-detects research pattern from input sources and user messages,
or uses explicitly configured pattern.

RFC Reference: RFC-011 Section 9
"""

from __future__ import annotations

import logging
import re
from typing import Literal

logger = logging.getLogger(__name__)

PatternType = Literal[
    "evidence-first", "idea-first", "decision-first", "experiment-first", "rapid-prototype"
]


def is_paper_url(source: str) -> bool:
    """Check if source is a paper URL pattern."""
    patterns = [
        r"https?://arxiv\.org/abs/",
        r"https?://arxiv\.org/pdf/",
        r"https?://.*\.pdf$",
        r"arxiv:\d{4}\.\d{4,5}",  # arxiv:2402.12345
        r"\d{4}\.\d{4,5}",  # 2402.12345 (bare arxiv ID)
    ]
    return any(re.match(p, source.lower()) for p in patterns)


def is_doi(source: str) -> bool:
    """Check if source is a DOI pattern."""
    patterns = [
        r"10\.\d{4,}/[^\s]+",  # Standard DOI
        r"doi:10\.\d{4,}/[^\s]+",  # doi: prefix
        r"https?://doi\.org/10\.\d{4,}/",
    ]
    return any(re.match(p, source.lower()) for p in patterns)


def is_github_url(source: str) -> bool:
    """Check if source is a GitHub URL."""
    patterns = [
        r"https?://github\.com/[^/]+/[^/]+",
        r"https?://gist\.github\.com/",
    ]
    return any(re.match(p, source.lower()) for p in patterns)


def is_huggingface_url(source: str) -> bool:
    """Check if source is a HuggingFace URL."""
    patterns = [
        r"https?://huggingface\.co/",
        r"https?://hf\.co/",
    ]
    return any(re.match(p, source.lower()) for p in patterns)


def is_web_url(source: str) -> bool:
    """Check if source is a generic web URL."""
    return source.startswith("http://") or source.startswith("https://")


def detect_pattern(
    input_sources: list[str],
    user_message: str,
) -> PatternType:
    """Detect pattern from input sources and user message.

    RFC Reference: RFC-011 Section 9.2

    Args:
        input_sources: List of provided sources (URLs, DOIs, etc.)
        user_message: User's natural language input.

    Returns:
        Detected pattern type.
    """
    # Check for paper URLs/DOIs → evidence-first
    if any(is_paper_url(s) or is_doi(s) for s in input_sources):
        logger.debug("Detected evidence-first pattern from paper sources")
        return "evidence-first"

    msg_lower = user_message.lower()

    # Hypothesis keywords → experiment-first
    hypothesis_kws = ["hypothesis", "test", "validate", "experiment", "verify"]
    if any(kw in msg_lower for kw in hypothesis_kws):
        logger.debug("Detected experiment-first pattern from hypothesis keywords")
        return "experiment-first"

    # Idea keywords → idea-first
    idea_kws = ["i think", "my idea", "hypothesize", "insight", "my theory"]
    if any(kw in msg_lower for kw in idea_kws):
        logger.debug("Detected idea-first pattern from idea keywords")
        return "idea-first"

    # Decision keywords → decision-first
    decision_kws = [
        "architecture",
        "design decision",
        "approach",
        "choose between",
        "which approach",
    ]
    if any(kw in msg_lower for kw in decision_kws):
        logger.debug("Detected decision-first pattern from decision keywords")
        return "decision-first"

    # Rapid prototype keywords
    rapid_kws = ["quick", "fast", "prototype", "sketch", "minimal"]
    if any(kw in msg_lower for kw in rapid_kws):
        logger.debug("Detected rapid-prototype pattern from rapid keywords")
        return "rapid-prototype"

    # Default to evidence-first
    logger.debug("Defaulting to evidence-first pattern")
    return "evidence-first"


def route_by_pattern(pattern: PatternType) -> str:
    """Route to appropriate next node based on pattern.

    RFC Reference: RFC-011 Section 9.3

    Args:
        pattern: Current research pattern.

    Returns:
        Next node name for routing.
    """
    # Core pipeline routes all patterns to collection first
    routes = {
        "evidence-first": "collection",
        "idea-first": "collection",  # Future: route to idea_note
        "decision-first": "collection",  # Future: route to decision
        "experiment-first": "collection",
        "rapid-prototype": "collection",
    }

    return routes.get(pattern, "collection")


class InputRouter:
    """Route inputs to appropriate handlers.

    RFC Reference: RFC-011 Section 10.3
    """

    def route_inputs(self, sources: list[str]) -> dict[str, list[str]]:
        """Categorize sources by type.

        Returns:
            Dict with keys: paper, github, huggingface, web
        """
        routed = {
            "paper": [],
            "github": [],
            "huggingface": [],
            "web": [],
        }

        for source in sources:
            if is_paper_url(source) or is_doi(source):
                routed["paper"].append(source)
            elif is_github_url(source):
                routed["github"].append(source)
            elif is_huggingface_url(source):
                routed["huggingface"].append(source)
            elif is_web_url(source):
                routed["web"].append(source)
            else:
                # Treat unknown URLs as web
                if source.startswith("http"):
                    routed["web"].append(source)
                else:
                    # Could be a search query - treat as paper search
                    routed["paper"].append(source)

        return routed


__all__ = [
    "PatternType",
    "is_paper_url",
    "is_doi",
    "is_github_url",
    "is_huggingface_url",
    "is_web_url",
    "detect_pattern",
    "route_by_pattern",
    "InputRouter",
]

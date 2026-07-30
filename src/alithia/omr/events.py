"""OmniResearch event definitions for soothe framework.

Defines event types emitted during workflow execution.

RFC Reference: RFC-011 Section 14
"""

from __future__ import annotations

from dataclasses import dataclass

# Import soothe_sdk event base if available
try:
    from soothe_sdk.events import SubagentEvent

    HAS_SOOTHE_SDK = True
except ImportError:
    HAS_SOOTHE_SDK = False

    # Fallback: define minimal base class
    @dataclass
    class SubagentEvent:
        """Fallback event base class."""

        pass


@dataclass
class OmrStepEvent(SubagentEvent):
    """Event emitted at each workflow step.

    RFC Reference: RFC-011 Section 14.2
    """

    step: str
    skill: str
    status: str


@dataclass
class OmrMaterialCollectedEvent(SubagentEvent):
    """Event emitted when material is collected.

    RFC Reference: RFC-011 Section 14.2
    """

    source_type: str  # paper/web/github/dataset
    source: str  # Original input
    artifact_path: str  # Stored artifact path


@dataclass
class OmrEvidenceExtractedEvent(SubagentEvent):
    """Event emitted when evidence is extracted."""

    materials_count: int
    claims_count: int


@dataclass
class OmrErrorEvent(SubagentEvent):
    """Event emitted when error occurs."""

    error_message: str
    step: str
    source: str | None = None


__all__ = [
    "OmrStepEvent",
    "OmrMaterialCollectedEvent",
    "OmrEvidenceExtractedEvent",
    "OmrErrorEvent",
]

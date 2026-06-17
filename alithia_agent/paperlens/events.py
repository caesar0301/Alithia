"""PaperLens event types for soothe framework integration.

Events emitted during workflow execution for observability.
Uses soothe's SubagentEvent base class for proper event routing.
"""

from __future__ import annotations

from typing import Literal

from pydantic import ConfigDict
from soothe_sdk.core.events import SubagentEvent
from soothe_sdk.core.verbosity import VerbosityTier

# Try to import register_event from soothe, make optional if not available
try:
    from soothe.core.events import register_event

    HAS_REGISTER_EVENT = True
except ImportError:
    HAS_REGISTER_EVENT = False
    register_event = None  # type: ignore

# Wire type constants (soothe.subagent.alithia.paperlens.*)
PAPERLENS_STARTED = "soothe.subagent.alithia.paperlens.started"
PAPERLENS_STEP = "soothe.subagent.alithia.paperlens.step"
PAPERLENS_PAPER_PARSED = "soothe.subagent.alithia.paperlens.paper.parsed"
PAPERLENS_PAPER_RANK = "soothe.subagent.alithia.paperlens.paper.rank"
PAPERLENS_COMPLETED = "soothe.subagent.alithia.paperlens.completed"
PAPERLENS_ERROR = "soothe.subagent.alithia.paperlens.error"


class PaperLensStartedEvent(SubagentEvent):
    """PaperLens workflow started."""

    type: Literal["soothe.subagent.alithia.paperlens.started"] = PAPERLENS_STARTED  # type: ignore[assignment]
    user_id: str = ""
    query: str = ""
    pdf_path: str = ""

    model_config = ConfigDict(extra="allow")


class PaperLensStepEvent(SubagentEvent):
    """Workflow step progress event."""

    type: Literal["soothe.subagent.alithia.paperlens.step"] = PAPERLENS_STEP  # type: ignore[assignment]
    step: str = ""
    status: str = ""

    model_config = ConfigDict(extra="allow")


class PaperLensPaperParsedEvent(SubagentEvent):
    """PDF successfully parsed event."""

    type: Literal["soothe.subagent.alithia.paperlens.paper.parsed"] = PAPERLENS_PAPER_PARSED  # type: ignore[assignment]
    paper_title: str = ""
    file_name: str = ""

    model_config = ConfigDict(extra="allow")


class PaperLensRankEvent(SubagentEvent):
    """Paper ranked event."""

    type: Literal["soothe.subagent.alithia.paperlens.paper.rank"] = PAPERLENS_PAPER_RANK  # type: ignore[assignment]
    rank: int = 0
    paper_title: str = ""
    score: float = 0.0

    model_config = ConfigDict(extra="allow")


class PaperLensCompletedEvent(SubagentEvent):
    """Workflow finished event."""

    type: Literal["soothe.subagent.alithia.paperlens.completed"] = PAPERLENS_COMPLETED  # type: ignore[assignment]
    papers_count: int = 0
    top_score: float = 0.0

    model_config = ConfigDict(extra="allow")


class PaperLensErrorEvent(SubagentEvent):
    """Error event."""

    type: Literal["soothe.subagent.alithia.paperlens.error"] = PAPERLENS_ERROR  # type: ignore[assignment]
    error_message: str = ""
    step: str = ""
    paper_id: str | None = None

    model_config = ConfigDict(extra="allow")


# Register events with soothe's event system (if available)
if HAS_REGISTER_EVENT and register_event:
    register_event(
        PaperLensStartedEvent,
        verbosity=VerbosityTier.NORMAL,
        summary_template="PaperLens: analyzing {pdf_path}",
    )

    register_event(
        PaperLensStepEvent,
        verbosity=VerbosityTier.NORMAL,
        summary_template="{step}: {status}",
    )

    register_event(
        PaperLensPaperParsedEvent,
        verbosity=VerbosityTier.NORMAL,
        summary_template="Parsed: {paper_title}",
    )

    register_event(
        PaperLensRankEvent,
        verbosity=VerbosityTier.NORMAL,
        summary_template="#{rank}: {paper_title} (score: {score:.2f})",
    )

    register_event(
        PaperLensCompletedEvent,
        verbosity=VerbosityTier.NORMAL,
        summary_template="PaperLens done ({papers_count} papers ranked)",
    )

    register_event(
        PaperLensErrorEvent,
        verbosity=VerbosityTier.INTERNAL,
        summary_template="Error in {step}: {error_message}",
    )


# Legacy aliases for backward compatibility
PaperLensCompleteEvent = PaperLensCompletedEvent
PAPERLENS_COMPLETE = PAPERLENS_COMPLETED


__all__ = [
    # Wire type constants
    "PAPERLENS_STARTED",
    "PAPERLENS_STEP",
    "PAPERLENS_PAPER_PARSED",
    "PAPERLENS_PAPER_RANK",
    "PAPERLENS_COMPLETED",
    "PAPERLENS_COMPLETE",  # Legacy alias
    "PAPERLENS_ERROR",
    # Event classes
    "PaperLensStartedEvent",
    "PaperLensStepEvent",
    "PaperLensPaperParsedEvent",
    "PaperLensRankEvent",
    "PaperLensCompletedEvent",
    "PaperLensCompleteEvent",  # Legacy alias
    "PaperLensErrorEvent",
]

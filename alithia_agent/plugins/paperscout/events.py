"""PaperScout plugin events (soothe-compatible wire types).

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

# Wire type constants (soothe.subagent.alithia.paperscout.*)
PAPERSCOUT_STARTED = "soothe.subagent.alithia.paperscout.started"
PAPERSCOUT_STEP = "soothe.subagent.alithia.paperscout.step"
PAPERSCOUT_PAPER_FOUND = "soothe.subagent.alithia.paperscout.paper.found"
PAPERSCOUT_EMAIL_SENT = "soothe.subagent.alithia.paperscout.email.sent"
PAPERSCOUT_COMPLETED = "soothe.subagent.alithia.paperscout.completed"
PAPERSCOUT_ERROR = "soothe.subagent.alithia.paperscout.error"


class PaperScoutStartedEvent(SubagentEvent):
    """PaperScout workflow started."""

    type: Literal["soothe.subagent.alithia.paperscout.started"] = PAPERSCOUT_STARTED  # type: ignore[assignment]
    user_id: str = ""
    categories: str = ""

    model_config = ConfigDict(extra="allow")


class PaperScoutStepEvent(SubagentEvent):
    """Workflow step progress event."""

    type: Literal["soothe.subagent.alithia.paperscout.step"] = PAPERSCOUT_STEP  # type: ignore[assignment]
    step: str = ""
    status: str = ""

    model_config = ConfigDict(extra="allow")


class PaperScoutPaperFoundEvent(SubagentEvent):
    """New relevant paper discovered event."""

    type: Literal["soothe.subagent.alithia.paperscout.paper.found"] = PAPERSCOUT_PAPER_FOUND  # type: ignore[assignment]
    paper_title: str = ""
    arxiv_id: str = ""
    score: float = 0.0

    model_config = ConfigDict(extra="allow")


class PaperScoutEmailSentEvent(SubagentEvent):
    """Email notification sent event."""

    type: Literal["soothe.subagent.alithia.paperscout.email.sent"] = PAPERSCOUT_EMAIL_SENT  # type: ignore[assignment]
    recipient: str = ""
    papers_count: int = 0

    model_config = ConfigDict(extra="allow")


class PaperScoutCompletedEvent(SubagentEvent):
    """Workflow finished event."""

    type: Literal["soothe.subagent.alithia.paperscout.completed"] = PAPERSCOUT_COMPLETED  # type: ignore[assignment]
    papers_count: int = 0
    email_sent: bool = False
    errors_count: int = 0

    model_config = ConfigDict(extra="allow")


class PaperScoutErrorEvent(SubagentEvent):
    """Error event."""

    type: Literal["soothe.subagent.alithia.paperscout.error"] = PAPERSCOUT_ERROR  # type: ignore[assignment]
    error_message: str = ""
    step: str = ""

    model_config = ConfigDict(extra="allow")


# Register events with soothe's event system (if available)
if HAS_REGISTER_EVENT and register_event:
    register_event(
        PaperScoutStartedEvent,
        verbosity=VerbosityTier.NORMAL,
        summary_template="PaperScout: started for {user_id}",
    )

    register_event(
        PaperScoutStepEvent,
        verbosity=VerbosityTier.NORMAL,
        summary_template="{step}: {status}",
    )

    register_event(
        PaperScoutPaperFoundEvent,
        verbosity=VerbosityTier.NORMAL,
        summary_template="Found paper: {paper_title} (score: {score:.2f})",
    )

    register_event(
        PaperScoutEmailSentEvent,
        verbosity=VerbosityTier.NORMAL,
        summary_template="Email sent to {recipient} ({papers_count} papers)",
    )

    register_event(
        PaperScoutCompletedEvent,
        verbosity=VerbosityTier.NORMAL,
        summary_template="PaperScout done ({papers_count} papers)",
    )

    register_event(
        PaperScoutErrorEvent,
        verbosity=VerbosityTier.INTERNAL,
        summary_template="Error in {step}: {error_message}",
    )


__all__ = [
    # Wire type constants
    "PAPERSCOUT_STARTED",
    "PAPERSCOUT_STEP",
    "PAPERSCOUT_PAPER_FOUND",
    "PAPERSCOUT_EMAIL_SENT",
    "PAPERSCOUT_COMPLETED",
    "PAPERSCOUT_ERROR",
    # Event classes
    "PaperScoutStartedEvent",
    "PaperScoutStepEvent",
    "PaperScoutPaperFoundEvent",
    "PaperScoutEmailSentEvent",
    "PaperScoutCompletedEvent",
    "PaperScoutErrorEvent",
]

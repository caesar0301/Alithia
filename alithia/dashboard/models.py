"""
Dashboard API models (request/response schemas).
"""

from datetime import date, datetime
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field


class ServiceStatus(BaseModel):
    """Status of a connected service."""

    name: str
    configured: bool = False
    last_synced: Optional[str] = None
    status: Literal["ok", "error", "pending", "not_configured"] = "not_configured"


class BackgroundTask(BaseModel):
    """Background task representation."""

    id: str
    user_id: str
    task_type: str
    status: Literal["queued", "running", "completed", "failed", "cancelled"] = "queued"
    progress: float = 0.0
    current_step: str = ""
    parameters: Dict[str, Any] = Field(default_factory=dict)
    result: Optional[Dict[str, Any]] = None
    logs: List[str] = Field(default_factory=list)
    created_at: Optional[str] = None
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    error_message: Optional[str] = None


class CalendarDay(BaseModel):
    """Single day in the notification calendar."""

    date: str
    paper_count: int = 0
    status: Literal["sent", "pending", "failed", "missing"] = "missing"


class CalendarMonth(BaseModel):
    """Month data for the calendar heatmap."""

    year: int
    month: int
    days: List[CalendarDay]


class PaperResponse(BaseModel):
    """Paper in API responses."""

    arxiv_id: str = ""
    title: str = ""
    authors: List[str] = Field(default_factory=list)
    summary: str = ""
    pdf_url: str = ""
    code_url: Optional[str] = None
    tldr: Optional[str] = None
    relevance_score: float = 0.0
    affiliations: List[str] = Field(default_factory=list)
    assessment_date: Optional[str] = None
    emailed: bool = False


class AIAgentContext(BaseModel):
    """Context for an AI agent request."""

    agent_type: Literal["paperscout", "paperlens", "sync"]
    parameters: Dict[str, Any] = Field(default_factory=dict)


class ChatMessage(BaseModel):
    """WebSocket chat message."""

    type: Literal["task_update", "sync_update", "chat", "error"]
    payload: Dict[str, Any] = Field(default_factory=dict)
    timestamp: Optional[str] = None


class SyncRequest(BaseModel):
    """Request to trigger sync."""

    connector: Optional[str] = None
    force_full: bool = False


class RunAgentRequest(BaseModel):
    """Request to run an agent."""

    agent_type: str
    parameters: Dict[str, Any] = Field(default_factory=dict)


class OverviewResponse(BaseModel):
    """Dashboard overview data."""

    total_papers_assessed: int = 0
    total_papers_emailed: int = 0
    total_notifications_sent: int = 0
    zotero_papers_cached: int = 0
    scholar_publications: int = 0
    services: List[ServiceStatus] = Field(default_factory=list)
    recent_tasks: List[BackgroundTask] = Field(default_factory=list)


class ProfileResponse(BaseModel):
    """Researcher profile data."""

    email: str = ""
    research_interests: List[str] = Field(default_factory=list)
    expertise_level: str = "intermediate"
    zotero_connected: bool = False
    scholar_connected: bool = False
    scholar_h_index: Optional[int] = None
    scholar_total_citations: int = 0
    top_publications: List[Dict[str, Any]] = Field(default_factory=list)

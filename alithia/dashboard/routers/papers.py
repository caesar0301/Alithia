"""
GET /api/papers — Paper trend data and assessed papers.
"""

from datetime import date, timedelta
from typing import Optional

from fastapi import APIRouter, Query, Request

from alithia.dashboard.models import PaperResponse

router = APIRouter(prefix="/api", tags=["papers"])


@router.get("/papers", response_model=list[PaperResponse])
async def get_papers(
    request: Request,
    from_date: Optional[str] = Query(None, description="YYYY-MM-DD"),
    to_date: Optional[str] = Query(None, description="YYYY-MM-DD"),
    limit: int = Query(100, ge=1, le=500),
):
    storage = request.app.state.storage
    user_id = request.app.state.user_id
    config = request.app.state.config

    ps_settings = config.get("paperscout_agent", config.get("arxrec", {}))
    query = ps_settings.get("query", "")

    today = date.today()
    fd = date.fromisoformat(from_date) if from_date else today - timedelta(days=30)
    td = date.fromisoformat(to_date) if to_date else today

    rows = storage.get_assessed_papers(user_id, query, fd, td)

    results = []
    for row in rows[:limit]:
        results.append(
            PaperResponse(
                arxiv_id=row.get("arxiv_id", ""),
                title=row.get("paper_title", ""),
                authors=row.get("paper_authors", []),
                summary=row.get("paper_summary", ""),
                pdf_url=row.get("pdf_url", ""),
                code_url=row.get("code_url"),
                tldr=row.get("tldr"),
                relevance_score=row.get("relevance_score", 0.0),
                affiliations=row.get("affiliations", []),
                assessment_date=row.get("assessment_date"),
                emailed=row.get("emailed", False),
            )
        )

    return results

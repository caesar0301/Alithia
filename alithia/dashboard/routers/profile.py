"""
GET /api/profile — Researcher profile and Scholar data.
"""

from fastapi import APIRouter, Request

from alithia.dashboard.models import ProfileResponse

router = APIRouter(prefix="/api", tags=["profile"])


@router.get("/profile", response_model=ProfileResponse)
async def get_profile(request: Request):
    storage = request.app.state.storage
    user_id = request.app.state.user_id
    config = request.app.state.config

    rp = config.get("researcher_profile", {})

    scholar_profile = storage.get_scholar_profile(user_id)
    scholar_pubs = storage.get_scholar_publications(user_id, limit=10)

    return ProfileResponse(
        email=rp.get("email", ""),
        research_interests=rp.get("research_interests", []),
        expertise_level=rp.get("expertise_level", "intermediate"),
        zotero_connected=bool(rp.get("zotero")),
        scholar_connected=scholar_profile is not None,
        scholar_h_index=scholar_profile.get("h_index") if scholar_profile else None,
        scholar_total_citations=scholar_profile.get("total_citations", 0) if scholar_profile else 0,
        top_publications=scholar_pubs,
    )

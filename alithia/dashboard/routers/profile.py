"""
GET /api/profile — Researcher profile and Scholar data.
"""

from typing import List

from fastapi import APIRouter, Request

from alithia.dashboard.models import ProfileResponse, ServiceConnectionInfo

router = APIRouter(prefix="/api", tags=["profile"])


def _check_zotero(rp: dict, storage, user_id: str) -> ServiceConnectionInfo:
    cfg = rp.get("zotero")
    base = dict(name="zotero", label="Zotero")
    if not cfg:
        return ServiceConnectionInfo(**base, connected=False, error="Not configured")
    if not (cfg.get("zotero_key") or cfg.get("api_key")):
        return ServiceConnectionInfo(**base, connected=False, error="API key is missing")
    if not (cfg.get("zotero_id") or cfg.get("user_id")):
        return ServiceConnectionInfo(**base, connected=False, error="User ID is missing")

    papers = storage.get_zotero_papers(user_id, max_age_hours=9999)
    count = len(papers) if papers else 0
    last = storage.get_last_sync(user_id, "zotero")
    last_synced = last.get("completed_at") if last else None
    summary = f"{count} papers cached"
    if last_synced:
        summary += f" · synced {last_synced[:10]}"
    return ServiceConnectionInfo(**base, connected=True, summary=summary, last_synced=last_synced, item_count=count)


def _check_scholar(rp: dict, storage, user_id: str) -> ServiceConnectionInfo:
    cfg = rp.get("google_scholar") or rp.get("googlescholarconnection")
    base = dict(name="google_scholar", label="Google Scholar")
    if not cfg:
        return ServiceConnectionInfo(**base, connected=False, error="Not configured")
    if not (cfg.get("google_scholar_id") or cfg.get("scholar_id")):
        return ServiceConnectionInfo(**base, connected=False, error="Scholar ID is missing")

    profile = storage.get_scholar_profile(user_id)
    if profile is None:
        return ServiceConnectionInfo(**base, connected=False, error="Profile not synced yet — run Sync")

    pubs = storage.get_scholar_publications(user_id, limit=9999)
    count = len(pubs)
    h_index = profile.get("h_index")
    citations = profile.get("total_citations", 0)
    last = storage.get_last_sync(user_id, "google_scholar")
    last_synced = last.get("completed_at") if last else None
    parts = []
    if h_index is not None:
        parts.append(f"h-index {h_index}")
    parts.append(f"{citations:,} citations")
    parts.append(f"{count} pubs")
    return ServiceConnectionInfo(
        **base,
        connected=True,
        summary=" · ".join(parts),
        last_synced=last_synced,
        item_count=count,
    )


def _check_github(rp: dict) -> ServiceConnectionInfo:
    cfg = rp.get("github")
    base = dict(name="github", label="GitHub")
    if not cfg:
        return ServiceConnectionInfo(**base, connected=False, error="Not configured")
    username = cfg.get("github_username", "")
    token = cfg.get("github_token", "")
    if not username or not token:
        return ServiceConnectionInfo(**base, connected=False, error="Username or token missing")
    return ServiceConnectionInfo(**base, connected=True, summary=f"@{username}")


def _check_x(rp: dict) -> ServiceConnectionInfo:
    cfg = rp.get("x")
    base = dict(name="x", label="X / Twitter")
    if not cfg:
        return ServiceConnectionInfo(**base, connected=False, error="Not configured")
    username = cfg.get("x_username", "")
    token = cfg.get("x_token", "")
    if not username or not token:
        return ServiceConnectionInfo(**base, connected=False, error="Username or token missing")
    return ServiceConnectionInfo(**base, connected=True, summary=f"@{username}")


def _check_email(rp: dict) -> ServiceConnectionInfo:
    cfg = rp.get("email_notification")
    base = dict(name="email", label="Email (SMTP)")
    if not cfg:
        return ServiceConnectionInfo(**base, connected=False, error="Not configured")
    server = cfg.get("smtp_server", "")
    sender = cfg.get("sender", "")
    if not server or not sender:
        return ServiceConnectionInfo(**base, connected=False, error="SMTP server or sender missing")
    return ServiceConnectionInfo(**base, connected=True, summary=f"{sender} via {server}")


def _check_llm(rp: dict) -> ServiceConnectionInfo:
    cfg = rp.get("llm")
    base = dict(name="llm", label="LLM Provider")
    if not cfg:
        return ServiceConnectionInfo(**base, connected=False, error="Not configured")
    key = cfg.get("openai_api_key", "")
    model = cfg.get("model_name", "")
    if not key:
        return ServiceConnectionInfo(**base, connected=False, error="API key missing")
    api_base = cfg.get("openai_api_base", "")
    host = api_base.split("//")[-1].split("/")[0] if api_base else "openai"
    return ServiceConnectionInfo(**base, connected=True, summary=f"{model or 'default'} @ {host}")


def _build_services(config: dict, storage, user_id: str) -> List[ServiceConnectionInfo]:
    rp = config.get("researcher_profile", {})
    return [
        _check_zotero(rp, storage, user_id),
        _check_scholar(rp, storage, user_id),
        _check_github(rp),
        _check_x(rp),
        _check_email(rp),
        _check_llm(rp),
    ]


def _storage_backend_name(storage) -> str:
    cls = type(storage).__name__
    mapping = {
        "PostgresStorage": "postgres",
        "SQLiteStorage": "sqlite",
        "SupabaseStorage": "supabase",
    }
    return mapping.get(cls, cls)


@router.get("/profile", response_model=ProfileResponse)
async def get_profile(request: Request):
    storage = request.app.state.storage
    user_id = request.app.state.user_id
    config = request.app.state.config

    rp = config.get("researcher_profile", {})
    services = _build_services(config, storage, user_id)
    svc_map = {s.name: s for s in services}

    scholar_profile = storage.get_scholar_profile(user_id)
    scholar_pubs = storage.get_scholar_publications(user_id, limit=10)

    ps_settings = config.get("paperscout_agent", config.get("arxrec", {}))

    return ProfileResponse(
        email=rp.get("email", ""),
        name=rp.get("name", ""),
        affiliation=rp.get("affiliation", ""),
        language=rp.get("language", "en"),
        research_interests=rp.get("research_interests", []),
        expertise_level=rp.get("expertise_level", "intermediate"),
        arxiv_categories=ps_settings.get("query", ""),
        storage_backend=_storage_backend_name(storage),
        services=services,
        zotero_connected=svc_map.get("zotero", ServiceConnectionInfo()).connected,
        scholar_connected=svc_map.get("google_scholar", ServiceConnectionInfo()).connected,
        scholar_name=scholar_profile.get("name", "") if scholar_profile else "",
        scholar_affiliation=scholar_profile.get("affiliation", "") if scholar_profile else "",
        scholar_h_index=scholar_profile.get("h_index") if scholar_profile else None,
        scholar_i10_index=scholar_profile.get("i10_index") if scholar_profile else None,
        scholar_total_citations=scholar_profile.get("total_citations", 0) if scholar_profile else 0,
        scholar_interests=scholar_profile.get("interests", []) if scholar_profile else [],
        top_publications=scholar_pubs,
    )

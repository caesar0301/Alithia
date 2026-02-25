"""
Agent nodes for the research agent workflow.

Uses a closure-based pattern: `make_nodes(storage, user_id)` returns
node functions that capture the injected storage backend.
"""

from datetime import date, datetime, timedelta
from typing import Callable, Dict, List, Optional

from noesium.core.utils import get_logger

from alithia.config_loader import load_config
from alithia.models.zotero_paper import ZoteroPaper
from alithia.researcher import ResearcherProfile
from alithia.storage.base import StorageBackend
from alithia.storage.factory import get_storage_backend
from alithia.utils.arxiv_paper_fetcher import fetch_arxiv_papers
from alithia.utils.arxiv_paper_utils import extract_affiliations, generate_tldr, get_code_url
from alithia.utils.email_utils import send_email
from alithia.utils.llm_utils import get_llm_client
from alithia.utils.zotero_client import filter_corpus, get_zotero_corpus

from .email import construct_email_content
from .models import ScoredPaper
from .reranker import PaperReranker
from .state import AgentState

logger = get_logger(__name__)


def _get_or_create_storage(existing: Optional[StorageBackend]) -> Optional[StorageBackend]:
    """Return existing storage or try to create one from config."""
    if existing is not None:
        return existing
    try:
        config = load_config(None)
        storage = get_storage_backend(config)
        return storage
    except Exception as e:
        logger.warning(f"Failed to initialize storage backend: {e}")
        return None


def _validate_user_profile(user_profile: ResearcherProfile) -> List[str]:
    errors = []
    if not user_profile.zotero.zotero_id:
        errors.append("Zotero ID is required")
    if not user_profile.zotero.zotero_key:
        errors.append("Zotero API key is required")
    if not user_profile.email_notification.smtp_server:
        errors.append("SMTP server is required")
    if not user_profile.email_notification.sender:
        errors.append("Sender email is required")
    if not user_profile.email:
        errors.append("Researcher email is required for notifications")
    if not user_profile.llm.openai_api_key:
        errors.append("OpenAI API key is required when using LLM API")
    return errors


def make_nodes(storage: Optional[StorageBackend], user_id: str) -> Dict[str, Callable]:
    """
    Create node functions with injected storage and user_id.

    When storage is None (backward-compatible CLI usage), nodes try to
    create storage from the default config.
    """
    _storage = _get_or_create_storage(storage)

    def profile_analysis_node(state: AgentState) -> dict:
        logger.info("Analyzing user profile...")

        if not state.config.user_profile:
            state.add_error("No profile provided")
            return {"current_step": "profile_analysis_error", "error_log": state.error_log}

        errors = _validate_user_profile(state.config.user_profile)
        if errors:
            for error in errors:
                state.add_error(error)
            return {"current_step": "profile_validation_error", "error_log": state.error_log}

        logger.info(f"Profile validated for user: {state.config.user_profile.email}")
        return {"current_step": "profile_analysis_complete"}

    def data_collection_node(state: AgentState) -> dict:
        logger.info("Collecting data from ArXiv and Zotero...")

        if not state.config.user_profile:
            state.add_error("No profile available for data collection")
            return {"current_step": "data_collection_error", "error_log": state.error_log}

        uid = user_id or state.config.user_profile.email or "default_user"

        try:
            # Load Zotero corpus from storage or API
            corpus: List[ZoteroPaper] = []
            if _storage:
                cached = _storage.get_zotero_papers(uid, max_age_hours=24)
                if cached:
                    corpus = [ZoteroPaper.from_storage_dict(p) for p in cached]
                    logger.info(f"Using cached Zotero corpus ({len(corpus)} papers)")

            if not corpus:
                logger.info("Retrieving Zotero corpus from API...")
                raw_items = get_zotero_corpus(
                    state.config.user_profile.zotero.zotero_id,
                    state.config.user_profile.zotero.zotero_key,
                )
                for item in raw_items:
                    paths = item.get("paths", [])
                    zp = ZoteroPaper.from_zotero_api(item, paths)
                    if zp:
                        corpus.append(zp)
                logger.info(f"Retrieved {len(corpus)} papers from Zotero")

                if _storage:
                    try:
                        _storage.cache_zotero_papers(uid, [p.to_storage_dict() for p in corpus])
                    except Exception as e:
                        logger.warning(f"Failed to cache Zotero corpus: {e}")

            # Apply ignore patterns (filter on collection_paths)
            if state.config.ignore_patterns and corpus:
                ignore_str = "\n".join(state.config.ignore_patterns)
                raw_for_filter = [{"data": {"collections": p.collection_paths}} for p in corpus]
                filtered = filter_corpus(raw_for_filter, ignore_str)
                filtered_keys = set(range(len(filtered)))
                corpus = [c for i, c in enumerate(corpus) if i in filtered_keys]
                logger.info(f"Filtered corpus: {len(corpus)} papers remaining")

            # Compute date range
            if state.config.from_date:
                try:
                    from_dt = datetime.strptime(state.config.from_date, "%Y-%m-%d")
                    to_dt = datetime.strptime(state.config.to_date, "%Y-%m-%d") if state.config.to_date else from_dt
                except ValueError:
                    from_dt = datetime.now() - timedelta(days=1)
                    to_dt = from_dt
            else:
                from_dt = datetime.now() - timedelta(days=1)
                to_dt = from_dt

            from_date = from_dt.strftime("%Y%m%d")
            to_date = to_dt.strftime("%Y%m%d")
            from_time = from_date + "0000"
            to_time = to_date + "2359"

            logger.info(f"Date range: {from_date} to {to_date}, query: {state.config.query}")

            # Check processed ranges
            if _storage:
                processed = _storage.get_processed_ranges(uid, state.config.query, days_back=7)
                if any(r.get("from_date") == from_date and r.get("to_date") == to_date for r in processed):
                    logger.info(f"Date range {from_date}-{to_date} already processed, skipping")
                    return {
                        "discovered_papers": [],
                        "zotero_corpus": corpus,
                        "current_step": "data_collection_complete",
                    }

            # Fetch ArXiv papers
            papers = fetch_arxiv_papers(
                arxiv_query=state.config.query,
                from_time=from_time,
                to_time=to_time,
                max_results=state.config.max_papers_queried,
                debug=state.debug_mode,
                max_retries=3,
                enable_web_fallback=True,
            )
            logger.info(f"Retrieved {len(papers)} valid papers from ArXiv")

            if _storage:
                try:
                    _storage.mark_date_range_processed(uid, from_date, to_date, state.config.query, len(papers))
                except Exception as e:
                    logger.warning(f"Failed to mark date range: {e}")

            # Filter already emailed
            if _storage and papers:
                arxiv_ids = [p.arxiv_id for p in papers]
                emailed = _storage.get_emailed_papers(uid, arxiv_ids, days_back=30)
                emailed_ids = {p.get("arxiv_id") for p in emailed}
                if emailed_ids:
                    before = len(papers)
                    papers = [p for p in papers if p.arxiv_id not in emailed_ids]
                    logger.info(f"Filtered out {before - len(papers)} already-emailed papers")

            logger.info(f"Collected {len(papers)} papers for processing")
            return {
                "discovered_papers": papers,
                "zotero_corpus": corpus,
                "current_step": "data_collection_complete",
            }

        except Exception as e:
            state.add_error(f"Data collection failed: {str(e)}")
            return {"current_step": "data_collection_error", "error_log": state.error_log}

    def relevance_assessment_node(state: AgentState) -> dict:
        logger.info("Assessing paper relevance...")

        if not state.discovered_papers:
            logger.info("No papers discovered")
            return {"current_step": "relevance_assessment_complete"}

        if not state.zotero_corpus:
            scored_papers = [
                ScoredPaper(paper=p, score=5.0, relevance_factors={"basic": 5.0}) for p in state.discovered_papers
            ]
        else:
            try:
                reranker = PaperReranker(state.discovered_papers, state.zotero_corpus)
                scored_papers = reranker.rerank_sentence_transformer()
            except Exception as e:
                state.add_error(f"Relevance assessment failed: {str(e)}")
                scored_papers = [
                    ScoredPaper(paper=p, score=5.0, relevance_factors={"fallback": 5.0})
                    for p in state.discovered_papers
                ]

        if state.config and state.config.max_papers > 0:
            scored_papers = scored_papers[: state.config.max_papers]

        # Persist all assessed papers
        uid = user_id or (state.config.user_profile.email if state.config.user_profile else "default_user")
        if _storage and scored_papers:
            try:
                today = date.today()
                paper_dicts = []
                for sp in scored_papers:
                    paper_dicts.append(
                        {
                            "arxiv_id": sp.paper.arxiv_id,
                            "title": sp.paper.title,
                            "authors": sp.paper.authors,
                            "summary": sp.paper.summary,
                            "pdf_url": sp.paper.pdf_url,
                            "relevance_score": sp.score,
                            "relevance_factors": sp.relevance_factors,
                            "code_url": sp.paper.code_url,
                            "tldr": sp.paper.tldr,
                            "affiliations": sp.paper.affiliations or [],
                        }
                    )
                _storage.save_assessed_papers(uid, state.config.query, paper_dicts, today)
                logger.info(f"Persisted {len(paper_dicts)} assessed papers")
            except Exception as e:
                logger.warning(f"Failed to persist assessed papers: {e}")

        return {"scored_papers": scored_papers, "current_step": "relevance_assessment_complete"}

    def content_generation_node(state: AgentState) -> dict:
        logger.info("Generating content...")

        if not state.scored_papers:
            logger.info("No papers to process")
            return {"current_step": "content_generation_complete"}

        if not state.config.user_profile:
            state.add_error("No profile available for content generation")
            return {"current_step": "content_generation_error", "error_log": state.error_log}

        try:
            llm = get_llm_client(state.config.user_profile.llm)

            for i, scored_paper in enumerate(state.scored_papers):
                paper = scored_paper.paper
                logger.info(f"Processing paper {i+1}/{len(state.scored_papers)}: {paper.title[:50]}...")

                if not paper.tldr:
                    paper.tldr = generate_tldr(paper, llm)
                if not paper.affiliations:
                    paper.affiliations = extract_affiliations(paper, llm)
                if not paper.code_url:
                    paper.code_url = get_code_url(paper)

            email_content = construct_email_content(state.scored_papers)
            return {"email_content": email_content, "current_step": "content_generation_complete"}

        except Exception as e:
            state.add_error(f"Content generation failed: {str(e)}")
            return {"current_step": "content_generation_error", "error_log": state.error_log}

    def communication_node(state: AgentState) -> dict:
        if state.debug_mode:
            logger.info("Debug mode: skipping email delivery")
            return {"current_step": "workflow_complete"}

        logger.info("Preparing email delivery...")

        if not state.config.user_profile:
            state.add_error("No profile available for email delivery")
            return {"current_step": "communication_error", "error_log": state.error_log}

        uid = user_id or state.config.user_profile.email or "default_user"
        today = date.today()
        query = state.config.query

        # Exactly-once check (PS-001)
        if _storage:
            existing = _storage.get_notification_record(uid, query, today)
            if existing and existing.get("status") == "sent":
                logger.info("Notification already sent for today, skipping (exactly-once)")
                return {"current_step": "workflow_complete"}

        if not state.email_content or (hasattr(state.email_content, "is_empty") and state.email_content.is_empty()):
            if not state.config.send_empty:
                logger.info("No papers found and send_empty=False, skipping")
                return {"current_step": "workflow_complete"}

        # Create pending notification record
        if _storage:
            try:
                _storage.save_notification_record(
                    {
                        "user_id": uid,
                        "query_categories": query,
                        "notification_date": today.isoformat(),
                        "paper_count": len(state.scored_papers),
                        "status": "pending",
                    }
                )
            except Exception as e:
                logger.warning(f"Failed to save pending notification: {e}")

        try:
            success = send_email(
                sender=state.config.user_profile.email_notification.sender,
                receiver=state.config.user_profile.email,
                password=state.config.user_profile.email_notification.sender_password,
                smtp_server=state.config.user_profile.email_notification.smtp_server,
                smtp_port=state.config.user_profile.email_notification.smtp_port,
                html_content=(
                    state.email_content
                    if isinstance(state.email_content, str)
                    else state.email_content.html_content if state.email_content else ""
                ),
                subject=(
                    state.email_content.subject
                    if hasattr(state.email_content, "subject") and state.email_content.subject
                    else None
                ),
            )

            if success:
                logger.info("Email sent successfully")

                # Update notification record to sent
                if _storage:
                    try:
                        _storage.save_notification_record(
                            {
                                "user_id": uid,
                                "query_categories": query,
                                "notification_date": today.isoformat(),
                                "paper_count": len(state.scored_papers),
                                "status": "sent",
                                "sent_at": datetime.utcnow().isoformat(),
                            }
                        )
                    except Exception as e:
                        logger.warning(f"Failed to update notification to sent: {e}")

                # Track emailed papers (backward compat + new assessed_papers update)
                if state.scored_papers and _storage:
                    try:
                        papers_data = []
                        for sp in state.scored_papers:
                            papers_data.append(
                                {
                                    "arxiv_id": sp.paper.arxiv_id,
                                    "title": sp.paper.title,
                                    "authors": sp.paper.authors,
                                    "summary": sp.paper.summary,
                                    "pdf_url": sp.paper.pdf_url,
                                    "code_url": sp.paper.code_url,
                                    "tldr": sp.paper.tldr,
                                    "relevance_score": sp.score,
                                    "published_date": (
                                        sp.paper.published_date.isoformat() if sp.paper.published_date else None
                                    ),
                                }
                            )
                        _storage.save_emailed_papers(uid, papers_data)
                    except Exception as e:
                        logger.warning(f"Failed to track emailed papers: {e}")

                return {"current_step": "workflow_complete"}
            else:
                # Mark notification as failed
                if _storage:
                    try:
                        _storage.save_notification_record(
                            {
                                "user_id": uid,
                                "query_categories": query,
                                "notification_date": today.isoformat(),
                                "paper_count": len(state.scored_papers),
                                "status": "failed",
                                "error_message": "send_email returned False",
                            }
                        )
                    except Exception:
                        pass

                state.add_error("Email delivery failed")
                return {"current_step": "communication_error", "error_log": state.error_log}

        except Exception as e:
            if _storage:
                try:
                    _storage.save_notification_record(
                        {
                            "user_id": uid,
                            "query_categories": query,
                            "notification_date": today.isoformat(),
                            "status": "failed",
                            "error_message": str(e),
                        }
                    )
                except Exception:
                    pass

            state.add_error(f"Email delivery failed: {str(e)}")
            return {"current_step": "communication_error", "error_log": state.error_log}

    return {
        "profile_analysis": profile_analysis_node,
        "data_collection": data_collection_node,
        "relevance_assessment": relevance_assessment_node,
        "content_generation": content_generation_node,
        "communication": communication_node,
    }


# Backward-compatible standalone node functions (used if importing directly)
profile_analysis_node = make_nodes(None, "default")["profile_analysis"]
data_collection_node = make_nodes(None, "default")["data_collection"]
relevance_assessment_node = make_nodes(None, "default")["relevance_assessment"]
content_generation_node = make_nodes(None, "default")["content_generation"]
communication_node = make_nodes(None, "default")["communication"]

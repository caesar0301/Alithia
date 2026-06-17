"""PaperScout workflow nodes.

5-node linear pipeline:
profile_analysis → data_collection → relevance_assessment → content_generation → communication
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta
from typing import Any

import arxiv
from pyzotero import zotero

from alithia_agent.models import ArxivPaper, ScoredPaper, ZoteroPaper
from alithia_agent.paperscout.email import construct_email_content, send_email
from alithia_agent.paperscout.events import (
    PaperScoutEmailSentEvent,
    PaperScoutErrorEvent,
    PaperScoutPaperFoundEvent,
    PaperScoutStepEvent,
)
from alithia_agent.paperscout.reranker import PaperReranker
from alithia_agent.paperscout.state import AgentState, PaperScoutRuntimeConfig

logger = logging.getLogger(__name__)


def _emit_step(step: str, status: str) -> None:
    """Emit workflow step event."""
    PaperScoutStepEvent(step=step, status=status)  # Registers with soothe
    logger.info(f"[{step}] {status}")


def _emit_paper_found(paper_title: str, arxiv_id: str, score: float) -> None:
    """Emit paper found event."""
    PaperScoutPaperFoundEvent(
        paper_title=paper_title,
        arxiv_id=arxiv_id,
        score=score,
    )  # Registers with soothe
    logger.info(f"Found paper: {paper_title} (score: {score:.2f})")


def _emit_email_sent(recipient: str, papers_count: int) -> None:
    """Emit email sent event."""
    PaperScoutEmailSentEvent(recipient=recipient, papers_count=papers_count)  # Registers
    logger.info(f"Email sent to {recipient} ({papers_count} papers)")


def _emit_error(error_message: str, step: str) -> None:
    """Emit error event."""
    PaperScoutErrorEvent(error_message=error_message, step=step)  # Registers
    logger.error(f"Error in {step}: {error_message}")


def _arxiv_ids_from_store(raw: Any) -> set[str]:
    """Normalize stored emailed-paper IDs."""
    if raw is None:
        return set()
    if isinstance(raw, set):
        return {str(x) for x in raw}
    if isinstance(raw, list):
        return {str(x) for x in raw}
    return set()


def make_nodes(
    store: Any,
    user_id: str,
    config: PaperScoutRuntimeConfig,
) -> dict[str, Any]:
    """Create workflow node functions.

    Args:
        store: AsyncPersistStore for caching.
        user_id: User identifier.
        config: PaperScout runtime configuration (injected at graph build time).

    Returns:
        Dict mapping node names to functions.
    """

    def profile_analysis_node(state: AgentState) -> dict[str, Any]:
        """Validate configuration."""
        _emit_step("profile_analysis", "Validating configuration")
        errors: list[str] = []

        # Validate Zotero
        if not config.zotero:
            errors.append("Zotero configuration required")
        else:
            if not config.zotero.api_key:
                errors.append("Zotero API key required")
            if not config.zotero.library_id:
                errors.append("Zotero library ID required")

        # Validate SMTP if sending email
        if config.send_email and not config.smtp:
            errors.append("SMTP configuration required when send_email=True")

        if errors:
            for err in errors:
                _emit_error(err, "profile_analysis")
            return {"errors": errors}

        _emit_step("profile_analysis", "Configuration validated")
        return {"info": ["Profile validated"]}

    async def data_collection_node(state: AgentState) -> dict[str, Any]:
        """Fetch papers from ArXiv and Zotero."""
        _emit_step("data_collection", "Fetching papers")

        errors: list[str] = []
        metrics = state.get("metrics", {})

        try:
            # Calculate date range - use from_date/to_date if provided (scheduler/daemon)
            # Otherwise use lookback_days for manual runs
            if config.from_date:
                # Scheduler/daemon mode: explicit date range
                start_date = date.fromisoformat(config.from_date)
                end_date = date.fromisoformat(config.to_date) if config.to_date else start_date
                metrics["source"] = config.source
                metrics["notification_date"] = config.from_date
            else:
                # Manual mode: use lookback_days
                end_date = date.today()
                start_date = end_date - timedelta(days=config.lookback_days)
                metrics["source"] = "manual"
                metrics["notification_date"] = (date.today() - timedelta(days=1)).isoformat()

            # Fetch ArXiv papers
            _emit_step("data_collection", f"Querying ArXiv ({start_date} to {end_date})")

            arxiv_papers: list[ArxivPaper] = []
            papers_per_category = config.max_papers_queried // len(config.arxiv_categories)

            arxiv_client = arxiv.Client()

            for category in config.arxiv_categories:
                search = arxiv.Search(
                    query=f"cat:{category}",
                    max_results=papers_per_category,
                    sort_by=arxiv.SortCriterion.SubmittedDate,
                )

                for result in arxiv_client.results(search):
                    if result.published.date() < start_date:
                        continue

                    paper = ArxivPaper(
                        title=result.title,
                        summary=result.summary,
                        authors=[a.name for a in result.authors],
                        arxiv_id=result.entry_id.split("/")[-1],
                        pdf_url=str(result.pdf_url),
                        published_date=result.published,
                        categories=[category],
                    )
                    arxiv_papers.append(paper)

            _emit_step("data_collection", f"Found {len(arxiv_papers)} papers from ArXiv")

            # Check already emailed
            emailed_key = f"paperscout:emailed:{user_id}"
            emailed_papers = _arxiv_ids_from_store(await store.load(emailed_key))
            new_papers = [p for p in arxiv_papers if p.arxiv_id not in emailed_papers]

            _emit_step(
                "data_collection",
                f"{len(new_papers)} new papers "
                f"(filtered {len(arxiv_papers) - len(new_papers)} already sent)",
            )

            # Fetch Zotero corpus
            _emit_step("data_collection", "Fetching Zotero library")
            zotero_papers: list[ZoteroPaper] = []

            if config.zotero:
                try:
                    # Check cache
                    cache_key = f"paperscout:zotero:{user_id}"
                    cached = await store.load(cache_key)

                    if (
                        cached
                        and (datetime.now() - cached.get("timestamp", datetime.min)).total_seconds()
                        < 86400
                    ):
                        _emit_step("data_collection", "Using cached Zotero library")
                        zotero_papers = [ZoteroPaper(**p) for p in cached.get("papers", [])]
                    else:
                        # Fetch from API
                        zot = zotero.Zotero(
                            config.zotero.library_id,
                            config.zotero.library_type,
                            config.zotero.api_key,
                        )

                        # Suppress pyzotero's harmless transaction rollback warnings
                        import warnings

                        with warnings.catch_warnings():
                            warnings.simplefilter("ignore")
                            items = list(zot.everything(zot.top()))

                        for item in items:
                            data = item.get("data", {})
                            zp = ZoteroPaper(
                                zotero_item_key=item.get("key", ""),
                                title=data.get("title", ""),
                                authors=[c.get("name", "") for c in data.get("creators", [])],
                                abstract=data.get("abstractNote", ""),
                                url=data.get("url"),
                                tags=[t.get("tag", "") for t in data.get("tags", [])],
                                date_added=datetime.strptime(
                                    data.get("dateAdded", ""), "%Y-%m-%dT%H:%M:%SZ"
                                )
                                if data.get("dateAdded")
                                else None,
                            )
                            zotero_papers.append(zp)

                        # Cache
                        await store.save(
                            cache_key,
                            {
                                "papers": [zp.model_dump() for zp in zotero_papers],
                                "timestamp": datetime.now().isoformat(),
                            },
                        )

                    _emit_step("data_collection", f"Loaded {len(zotero_papers)} papers from Zotero")

                except Exception as e:
                    # Ignore harmless transaction rollback errors from pyzotero
                    if "rollback" not in str(e).lower():
                        _emit_error(f"Zotero error: {e}", "data_collection")
                        errors.append(f"Zotero error: {e}")
                    else:
                        logger.debug(f"Suppressed pyzotero transaction warning: {e}")

            metrics["arxiv_found"] = len(arxiv_papers)
            metrics["arxiv_new"] = len(new_papers)
            metrics["zotero_corpus"] = len(zotero_papers)

            return {
                "discovered_papers": new_papers,
                "zotero_papers": zotero_papers,
                "errors": errors,
                "metrics": metrics,
                "info": [f"Collected {len(new_papers)} new papers"],
            }

        except Exception as e:
            _emit_error(str(e), "data_collection")
            return {"errors": [str(e)]}

    def relevance_assessment_node(state: AgentState) -> dict[str, Any]:
        """Rank papers by relevance."""
        _emit_step("relevance_assessment", "Ranking papers")

        papers = state["discovered_papers"]
        corpus = state["zotero_papers"]
        metrics = state.get("metrics", {})

        if not papers:
            _emit_step("relevance_assessment", "No papers to rank")
            return {
                "scored_papers": [],
                "info": ["No papers to rank"],
            }

        try:
            reranker = PaperReranker(papers=papers, corpus=corpus)
            scored = reranker.rerank()

            # Take top N
            top = scored[: config.max_papers]

            # Emit events
            for sp in top:
                arxiv_id = sp.paper.arxiv_id or "unknown"
                _emit_paper_found(sp.paper_title, arxiv_id, sp.score)

            metrics["papers_scored"] = len(scored)
            metrics["papers_selected"] = len(top)
            metrics["avg_score"] = sum(p.score for p in top) / len(top) if top else 0

            _emit_step(
                "relevance_assessment",
                f"Ranked {len(scored)} papers, selected top {len(top)}",
            )

            return {
                "scored_papers": top,
                "metrics": metrics,
                "info": [f"Ranked {len(scored)} papers, selected top {len(top)}"],
            }

        except Exception as e:
            _emit_error(str(e), "relevance_assessment")
            return {
                "scored_papers": [
                    ScoredPaper(paper=p, score=5.0) for p in papers[: config.max_papers]
                ],
                "errors": [str(e)],
            }

    def content_generation_node(state: AgentState) -> dict[str, Any]:
        """Generate email content."""
        _emit_step("content_generation", "Generating content")

        scored = state["scored_papers"]

        if not scored:
            if config.send_empty:
                email = construct_email_content([])
                return {"email_content": email, "info": ["Generated empty digest"]}
            return {"info": ["No papers, skipping email"]}

        try:
            # Generate TLDRs (placeholder - would use LLM in production)
            for sp in scored:
                # Only ArxivPaper has tldr and summary fields
                if isinstance(sp.paper, ArxivPaper):
                    if not sp.paper.tldr:
                        sp.paper.tldr = sp.paper.summary[:200] + "..."

            email = construct_email_content(scored)

            _emit_step("content_generation", f"Generated digest ({len(scored)} papers)")

            return {
                "email_content": email,
                "info": [f"Generated email content ({len(scored)} papers)"],
            }

        except Exception as e:
            _emit_error(str(e), "content_generation")
            return {"errors": [str(e)]}

    async def communication_node(state: AgentState) -> dict[str, Any]:
        """Send email notification."""
        _emit_step("communication", "Sending notification")

        email_content = state.get("email_content")
        metrics = state.get("metrics", {})

        if not email_content:
            _emit_step("communication", "No email content, skipping")
            return {"info": ["No email to send"]}

        if not config.send_email:
            _emit_step("communication", "Email disabled")
            return {"info": ["Email notifications disabled"]}

        if not config.smtp:
            _emit_error("SMTP missing", "communication")
            return {"errors": ["SMTP configuration missing"]}

        # Determine notification date for exactly-once semantics
        notification_date = metrics.get(
            "notification_date", (date.today() - timedelta(days=1)).isoformat()
        )
        query_categories = config.query

        # Check if notification already sent (exactly-once semantics)
        if hasattr(store, "get_notification_record"):
            existing = store.get_notification_record(user_id, query_categories, notification_date)
            if existing and existing.get("status") == "sent":
                _emit_step(
                    "communication", f"Notification already sent for {notification_date}, skipping"
                )
                logger.info(
                    f"Exactly-once: skipping duplicate notification for {notification_date}"
                )
                return {"info": [f"Notification already sent for {notification_date}"]}

        try:
            recipient = config.recipient_email or config.smtp.user
            success = send_email(email_content, config.smtp, recipient)

            if success:
                _emit_email_sent(recipient, len(email_content.papers))

                # Record notification in kv_store (legacy)
                notification_key = f"paperscout:notifications:{user_id}:{notification_date}"
                await store.save(
                    notification_key,
                    {
                        "date": notification_date,
                        "papers_count": len(email_content.papers),
                        "recipient": recipient,
                        "arxiv_ids": [p.arxiv_id for p in email_content.papers],
                        "sent_at": datetime.now().isoformat(),
                        "success": True,
                    },
                )

                # Save notification record (exactly-once semantics)
                if hasattr(store, "save_notification_record"):
                    store.save_notification_record(
                        {
                            "user_id": user_id,
                            "query_categories": query_categories,
                            "notification_date": notification_date,
                            "paper_count": len(email_content.papers),
                            "status": "sent",
                            "sent_at": datetime.now().isoformat(),
                        }
                    )

                # Mark papers as emailed
                emailed_key = f"paperscout:emailed:{user_id}"
                emailed = _arxiv_ids_from_store(await store.load(emailed_key))
                for paper in email_content.papers:
                    if paper.arxiv_id:  # Only add if arxiv_id exists
                        emailed.add(paper.arxiv_id)
                await store.save(emailed_key, list(emailed))

                metrics["email_sent"] = True
                metrics["paper_count"] = len(email_content.papers)

                return {
                    "metrics": metrics,
                    "info": [f"Email sent to {recipient}"],
                }

            _emit_error("Failed to send email", "communication")
            # Record failed notification
            if hasattr(store, "save_notification_record"):
                store.save_notification_record(
                    {
                        "user_id": user_id,
                        "query_categories": query_categories,
                        "notification_date": notification_date,
                        "paper_count": 0,
                        "status": "failed",
                        "error_message": "Failed to send email",
                    }
                )
            return {"errors": ["Failed to send email"]}

        except Exception as e:
            _emit_error(str(e), "communication")
            # Record failed notification
            if hasattr(store, "save_notification_record"):
                store.save_notification_record(
                    {
                        "user_id": user_id,
                        "query_categories": query_categories,
                        "notification_date": notification_date,
                        "paper_count": 0,
                        "status": "failed",
                        "error_message": str(e),
                    }
                )
            return {"errors": [str(e)]}

    return {
        "profile_analysis": profile_analysis_node,
        "data_collection": data_collection_node,
        "relevance_assessment": relevance_assessment_node,
        "content_generation": content_generation_node,
        "communication": communication_node,
    }


__all__ = ["make_nodes"]

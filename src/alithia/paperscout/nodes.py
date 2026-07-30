"""PaperScout workflow nodes.

6-node linear pipeline:
profile_analysis → data_collection → relevance_assessment → content_generation
→ persist_digest → communication
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

import arxiv

from alithia.models import ArxivPaper, ScoredPaper
from alithia.paperscout.affiliation_extractor import AffiliationExtractor
from alithia.paperscout.digest_store import build_daily_digest_record, save_daily_digest
from alithia.paperscout.email import construct_email_content, send_email
from alithia.paperscout.events import (
    PaperScoutEmailSentEvent,
    PaperScoutErrorEvent,
    PaperScoutPaperFoundEvent,
    PaperScoutStepEvent,
)
from alithia.paperscout.reranker import PaperReranker
from alithia.paperscout.state import AgentState, PaperScoutRuntimeConfig
from alithia.paperscout.tldr import generate_tldrs
from alithia.research_interests import (
    ResearchInterest,
    load_research_interests,
    sync_zotero_to_markdown,
)

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


def _build_arxiv_category_query(category: str, start_date: date, end_date: date) -> str:
    """Build ArXiv API query scoped to category and submission date range."""
    start_ts = start_date.strftime("%Y%m%d") + "0000"
    end_ts = end_date.strftime("%Y%m%d") + "2359"
    return f"cat:{category} AND submittedDate:[{start_ts} TO {end_ts}]"


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

        # RFC-010 §10: Zotero is optional. Fail fast only when there is NO
        # knowledge source at all (neither interests markdown nor zotero).
        has_zotero = bool(config.zotero and config.zotero.api_key and config.zotero.library_id)
        interests_dir = (
            Path(config.research_interests_dir) if config.research_interests_dir else None
        )
        has_interests = bool(
            interests_dir and interests_dir.exists() and any(interests_dir.rglob("*.md"))
        )

        if not has_zotero and not has_interests:
            errors.append(
                "No knowledge source: add research_interests markdown files under "
                f"{interests_dir or '~/.alithia/research_interests'} or configure zotero"
            )

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
                    query=_build_arxiv_category_query(category, start_date, end_date),
                    max_results=papers_per_category,
                    sort_by=arxiv.SortCriterion.SubmittedDate,
                )

                for result in arxiv_client.results(search):
                    published = result.published.date()
                    if published < start_date or published > end_date:
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

            # Extract affiliations from ArXiv LaTeX source (for new papers).
            # When an LLM API key is configured, the extractor batches the
            # fetched sources into LLM requests; without a key, sources are
            # fetched but affiliations stay unset (→ "Unknown Affiliation").
            if new_papers:
                _emit_step("data_collection", "Extracting affiliations from LaTeX source")
                try:
                    llm_cfg = (
                        {
                            "api_key": config.llm_api_key,
                            "api_base": config.llm_api_base,
                            "model": config.llm_model,
                        }
                        if config.llm_api_key
                        else None
                    )
                    extractor = AffiliationExtractor(llm_config=llm_cfg)
                    new_papers = await extractor.enrich_papers(new_papers)
                    enriched_count = sum(1 for p in new_papers if p.affiliations)
                    _emit_step(
                        "data_collection",
                        f"Extracted affiliations for {enriched_count}/{len(new_papers)} papers",
                    )
                    metrics["affiliations_extracted"] = enriched_count
                    await extractor.close()
                except Exception as e:
                    _emit_error(f"Affiliation extraction error: {e}", "data_collection")
                    # Continue without affiliations - extraction is optional
                    logger.warning(f"Affiliation extraction failed, continuing without: {e}")

            # RFC-010 §8: normalize the Zotero library into research_interests
            # markdown, then scan all interest files (hand-written + synced)
            # into a unified knowledge base the reranker scores against.
            # Zotero items flow ONLY through the markdown sync → ResearchInterest
            # units → the unified interests corpus. There is no separate
            # zotero_papers corpus path in the matcher (the legacy slot was
            # removed to avoid double-counting and to keep one matching logic).
            _emit_step("data_collection", "Syncing Zotero library to research_interests")
            interests: list[ResearchInterest] = []

            interests_dir = (
                Path(config.research_interests_dir) if config.research_interests_dir else None
            )

            if interests_dir:
                cache_key = f"paperscout:zotero:{user_id}"

                # Pre-load the cache so the (sync) sync function can use it
                # without leaking async into its signature.
                try:
                    cached = await store.load(cache_key)
                except Exception:
                    cached = None

                def _cache_loader() -> dict[str, Any] | None:
                    # noqa: B023  (closure over the pre-loaded value)
                    if isinstance(cached, dict):
                        return cached
                    return None

                def _cache_saver(payload: dict[str, Any]) -> None:
                    # Best-effort fire-and-forget: the store is async, so
                    # schedule the write on the running loop without blocking
                    # the node. Failures are non-fatal (cache is advisory).
                    import asyncio

                    asyncio.get_event_loop().create_task(store.save(cache_key, payload))  # type: ignore[attr-defined]

                sync_res = sync_zotero_to_markdown(
                    config.zotero,
                    interests_dir,
                    user_id=user_id,
                    cache_loader=_cache_loader,
                    cache_saver=_cache_saver,
                )
                metrics["zotero_sync"] = {
                    "synced": sync_res.synced,
                    "pruned": sync_res.pruned,
                    "skipped": sync_res.skipped,
                }
                if sync_res.error and not sync_res.skipped:
                    errors.append(f"Zotero sync error: {sync_res.error}")

                _emit_step(
                    "data_collection",
                    f"Zotero sync: {sync_res.synced} synced, {sync_res.pruned} pruned"
                    + (" (skipped)" if sync_res.skipped else ""),
                )

                # Scan the unified knowledge base (hand-written + synced zotero).
                # Zotero items arrive here as source=zotero ResearchInterest units.
                _emit_step("data_collection", "Scanning research_interests markdown")
                interests = load_research_interests(interests_dir)
                metrics["interests_count"] = len(interests)
                _emit_step("data_collection", f"Loaded {len(interests)} interest units")

            metrics["arxiv_found"] = len(arxiv_papers)
            metrics["arxiv_new"] = len(new_papers)

            return {
                "discovered_papers": new_papers,
                "research_interests": interests,
                "errors": errors,
                "metrics": metrics,
                "info": [
                    f"Collected {len(new_papers)} new papers, {len(interests)} interest units"
                ],
            }

        except Exception as e:
            _emit_error(str(e), "data_collection")
            return {"errors": [str(e)]}

    def relevance_assessment_node(state: AgentState) -> dict[str, Any]:
        """Rank papers by relevance."""
        _emit_step("relevance_assessment", "Ranking papers")

        papers = state["discovered_papers"]
        interests = state.get("research_interests", [])
        metrics = state.get("metrics", {})

        if not papers:
            _emit_step("relevance_assessment", "No papers to rank")
            return {
                "scored_papers": [],
                "info": ["No papers to rank"],
            }

        try:
            reranker = PaperReranker(papers=papers, interests=interests)
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
                email = construct_email_content([], max_chars=config.tldr_max_tokens)
                return {"email_content": email, "info": ["Generated empty digest"]}
            return {"info": ["No papers, skipping email"]}

        try:
            # Generate LLM TLDRs for ArXiv papers (graceful: if no api key is
            # configured or any call fails, paper.tldr stays None and the
            # renderer falls back to a truncated summary). Only ArxivPaper
            # carries the summary/tldr fields.
            arxiv_papers_for_tldr = [sp.paper for sp in scored if isinstance(sp.paper, ArxivPaper)]
            tldrs_generated = 0
            if arxiv_papers_for_tldr and config.llm_api_key:
                try:
                    tldrs_generated = generate_tldrs(arxiv_papers_for_tldr, config)
                    _emit_step(
                        "content_generation",
                        f"Generated {tldrs_generated} LLM TLDRs",
                    )
                except Exception as e:
                    _emit_error(f"TLDR generation error: {e}", "content_generation")
                    logger.warning(f"TLDR generation failed, using summary fallback: {e}")

            # TLDR is rendered from each paper's tldr/summary at display time,
            # truncated to config.tldr_max_tokens chars inside
            # construct_email_content.
            email = construct_email_content(scored, max_chars=config.tldr_max_tokens)

            _emit_step("content_generation", f"Generated digest ({len(scored)} papers)")

            metrics = dict(state.get("metrics", {}))
            metrics["tldrs_generated"] = tldrs_generated

            return {
                "email_content": email,
                "info": [f"Generated email content ({len(scored)} papers)"],
                "metrics": metrics,
            }

        except Exception as e:
            _emit_error(str(e), "content_generation")
            return {"errors": [str(e)]}

    async def persist_digest_node(state: AgentState) -> dict[str, Any]:
        """Persist scored paper metadata for future analysis (no email HTML)."""
        _emit_step("persist_digest", "Saving daily digest metadata")

        metrics = dict(state.get("metrics", {}))
        notification_date = metrics.get(
            "notification_date", (date.today() - timedelta(days=1)).isoformat()
        )
        scored = state.get("scored_papers") or []

        try:
            record = build_daily_digest_record(
                scored,
                digest_date=notification_date,
                config=config,
                metrics=metrics,
            )
            key = await save_daily_digest(store, user_id, record)
            _emit_step(
                "persist_digest",
                f"Saved digest for {notification_date} ({len(scored)} papers)",
            )
            metrics["digest_saved"] = True
            metrics["digest_storage_key"] = key
            return {
                "metrics": metrics,
                "info": [f"Persisted digest metadata for {notification_date}"],
            }
        except Exception as e:
            _emit_error(str(e), "persist_digest")
            logger.warning(f"Failed to persist digest for {notification_date}: {e}")
            return {"errors": [f"Digest persistence failed: {e}"]}

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
        "persist_digest": persist_digest_node,
        "communication": communication_node,
    }


__all__ = ["make_nodes"]

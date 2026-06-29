#!/usr/bin/env python3
"""Real PaperScout example run — interests-only, no zotero, no email.

Verifies the RFC-010 interests-only path end-to-end:
  profile_analysis (no zotero, has interests) → data_collection (ArXiv fetch +
  no-op zotero sync + load interests) → relevance_assessment (fastembed
  embeddings vs. interests) → content_generation (email built but not sent).

Run:  python scripts/run_paperscout_example.py
"""

from __future__ import annotations

import asyncio
import logging
from datetime import date, timedelta
from pathlib import Path

from alithia_agent.config import load_config
from alithia_agent.paperscout.runner import build_scheduler_config
from alithia_agent.paperscout.state import PaperScoutRuntimeConfig
from alithia_agent.paperscout.implementation import create_paperscout_graph
from alithia_agent.storage.sqlite import SQLiteStorage

logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s %(name)s: %(message)s",
    force=True,
)
# Unbuffered so progress is visible during a long ArXiv/fastembed run.
import sys  # noqa: E402

sys.stdout.reconfigure(line_buffering=True)  # type: ignore[attr-defined]
sys.stderr.reconfigure(line_buffering=True)  # type: ignore[attr-defined]
logger = logging.getLogger("paperscout_example")


async def main() -> int:
    cfg = load_config()

    # Build runtime config for a 3-day window, email OFF, tight ArXiv scope.
    end = date.today()
    start = end - timedelta(days=3)
    rt: PaperScoutRuntimeConfig = build_scheduler_config(
        cfg, from_date=start.isoformat(), to_date=end.isoformat(), source="manual"
    )
    rt = rt.model_copy(
        update={
            "send_email": False,  # no email sending
            "smtp": None,
            "arxiv_categories": ["cs.AI"],  # single category for a fast verification
            "query": "cs.AI",
            "max_papers_queried": 10,  # cap per-run ArXiv load
            "max_papers": 3,  # top-3 digest
        }
    )

    print(f"\n=== PaperScout run: {start} → {end} (email OFF, no zotero) ===")
    print(f"arxiv_categories: {rt.arxiv_categories}")
    print(f"research_interests_dir: {rt.research_interests_dir}")
    print(f"zotero configured: {rt.zotero is not None}\n")

    store = SQLiteStorage(Path.home() / ".alithia" / "alithia.db")
    graph = create_paperscout_graph(store, cfg.storage.user_id, rt)
    compiled = graph.compile()
    initial = {
        "messages": [],
        "config": rt,
        "user_id": cfg.storage.user_id,
        "discovered_papers": [],
        "research_interests": [],
        "scored_papers": [],
        "email_content": None,
        "errors": [],
        "info": [],
        "metrics": {},
    }

    result = await compiled.ainvoke(initial)

    # ---- report ----
    errors = result.get("errors") or []
    metrics = result.get("metrics") or {}
    interests = result.get("research_interests") or []
    scored = result.get("scored_papers") or []

    print("\n=== RESULT ===")
    print(f"errors: {errors}")
    print(f"metrics: { {k: v for k, v in metrics.items()} }")
    print(
        f"interests loaded: {len(interests)} (sources: "
        f"{ {s: sum(1 for i in interests if i.source == s) for s in {i.source for i in interests}} })"
    )
    print(f"scored papers: {len(scored)}")

    if scored:
        print("\n--- top papers (rank, score, title) ---")
        for idx, sp in enumerate(scored, 1):
            f = sp.relevance_factors
            print(
                f"{idx:2d}. [{sp.score:5.2f}] {sp.paper.title[:80]}\n"
                f"     arxiv={sp.paper.arxiv_id} | "
                f"max_sim={f.get('max_similarity', 0):.3f} "
                f"interests_count={f.get('interests_count')} "
                f"corpus_size={f.get('corpus_size')}"
            )

    email = result.get("email_content")
    print(
        f"\nemail_content built: {email is not None}"
        + (
            f" (papers={email.papers_count}, subject='{email.subject}')"
            if email
            else " (skipped — no papers / send_empty=False)"
        )
    )

    store.close()
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))

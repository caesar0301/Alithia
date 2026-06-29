#!/usr/bin/env python3
"""Sync a Zotero library into the research-interests Markdown knowledge base.

Writes one ``research_interests/zotero/<key>.md`` per Zotero item (RFC-010 §8)
and prunes stale ``zotero/*.md`` whose keys are no longer in the library.
Hand-written interest files outside ``zotero/`` are never touched.

Credentials come from ``ZOTERO_ID`` and ``ZOTERO_KEY`` (or ``--library-id`` /
``--api-key``). The script never sends email and never touches the rest of the
PaperScout pipeline.

Usage:
    ZOTERO_ID=<ID> ZOTERO_KEY=<KEY> python scripts/sync_zotero_interests.py
    python scripts/sync_zotero_interests.py --library-id <ID> --api-key <KEY>

Note: if Zotero is not configured (no id/key), the script is a no-op and the
existing cached zotero/*.md files are left untouched (they keep contributing
to the interests corpus). This matches the in-pipeline guarantee.
"""

from __future__ import annotations

import argparse
import logging
import os
from pathlib import Path

from alithia_agent import ALITHIA_HOME
from alithia_agent.paperscout.state import ZoteroRuntimeConfig
from alithia_agent.research_interests import sync_zotero_to_markdown

ZOTERO_ID_ENV = "ZOTERO_ID"
ZOTERO_KEY_ENV = "ZOTERO_KEY"

logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s %(name)s: %(message)s",
    force=True,
)
logger = logging.getLogger("sync_zotero")


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Sync a Zotero library into research_interests/zotero/*.md."
    )
    ap.add_argument(
        "--library-id",
        metavar="ID",
        help=f"Zotero library ID (or set {ZOTERO_ID_ENV}).",
    )
    ap.add_argument(
        "--api-key",
        metavar="KEY",
        help=f"Zotero API key (or set {ZOTERO_KEY_ENV}).",
    )
    ap.add_argument(
        "--library-type",
        choices=["user", "group"],
        default="user",
        help="Zotero library type (default: %(default)s).",
    )
    ap.add_argument(
        "--dir",
        default=str(ALITHIA_HOME / "research_interests"),
        help="research_interests directory (default: %(default)s).",
    )
    args = ap.parse_args()

    library_id = args.library_id or os.environ.get(ZOTERO_ID_ENV)
    api_key = args.api_key or os.environ.get(ZOTERO_KEY_ENV)

    # No-cred guard: keep cached knowledge, do not prune.
    if not (library_id and api_key):
        logger.warning(
            "No Zotero credentials provided (set --library-id/--api-key or "
            f"{ZOTERO_ID_ENV}/{ZOTERO_KEY_ENV}). Leaving existing zotero/*.md untouched."
        )
        return 0

    zotero_cfg = ZoteroRuntimeConfig(
        api_key=api_key,
        library_id=library_id,
        library_type=args.library_type,  # type: ignore[arg-type]
    )
    interests_dir = Path(args.dir)
    interests_dir.mkdir(parents=True, exist_ok=True)

    print(f"Syncing Zotero library {library_id} ({args.library_type})")
    print(f"  → {interests_dir / 'zotero'}\n")

    # The standalone script has no AsyncPersistStore, so no cache is used — it
    # always does a live fetch. (The in-pipeline path uses the 24h cache.)
    result = sync_zotero_to_markdown(zotero_cfg, interests_dir, user_id="default")

    print("=== RESULT ===")
    print(f"  synced:  {result.synced}  (items written to zotero/*.md)")
    print(f"  pruned:  {result.pruned}  (stale zotero/*.md removed)")
    print(f"  skipped: {result.skipped}")
    if result.error:
        print(f"  error:   {result.error}")
    return 0 if not result.error or result.skipped else 1


if __name__ == "__main__":
    raise SystemExit(main())

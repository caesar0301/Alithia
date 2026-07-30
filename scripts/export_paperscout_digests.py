#!/usr/bin/env python3
"""Export persisted PaperScout daily digest metadata from local SQLite storage.

Reads ``paperscout:digest:{user_id}:{YYYY-MM-DD}`` records (scores, TLDRs, URLs,
etc.) and writes JSON and/or CSV for offline analysis. Does not export email HTML.

Usage:
    uv run python scripts/export_paperscout_digests.py --list
    uv run python scripts/export_paperscout_digests.py --format json -o digests.json
    uv run python scripts/export_paperscout_digests.py --format csv -o papers.csv
    uv run python scripts/export_paperscout_digests.py --from 2026-06-01 --to 2026-06-30
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import json
import sys
from datetime import date
from pathlib import Path
from typing import Any

from alithia import ALITHIA_HOME
from alithia.config.loader import load_config
from alithia.paperscout.digest_store import (
    digest_key_prefix,
    list_daily_digest_dates,
    load_daily_digest,
)
from alithia.storage.sqlite import SQLiteStorage

CSV_COLUMNS = [
    "digest_date",
    "rank",
    "score",
    "arxiv_id",
    "title",
    "authors",
    "tldr",
    "summary",
    "pdf_url",
    "published_date",
    "categories",
    "affiliations",
    "code_url",
    "digest_source",
    "query",
    "paper_count",
    "avg_score",
    "saved_at",
]


def _join_list(value: Any) -> str:
    if not value:
        return ""
    if isinstance(value, list):
        return "; ".join(str(v) for v in value)
    return str(value)


def _filter_dates(dates: list[str], from_date: str | None, to_date: str | None) -> list[str]:
    filtered = dates
    if from_date:
        filtered = [d for d in filtered if d >= from_date]
    if to_date:
        filtered = [d for d in filtered if d <= to_date]
    return filtered


def digest_to_csv_rows(digest: dict[str, Any]) -> list[dict[str, str]]:
    """Flatten one daily digest into CSV rows (one row per paper)."""
    metrics = digest.get("metrics") or {}
    avg_score = metrics.get("avg_score", "")
    base = {
        "digest_date": digest.get("digest_date", ""),
        "digest_source": digest.get("source", ""),
        "query": digest.get("query", ""),
        "paper_count": str(digest.get("paper_count", 0)),
        "avg_score": "" if avg_score == "" else str(avg_score),
        "saved_at": digest.get("saved_at", ""),
    }

    papers = digest.get("papers") or []
    if not papers:
        return [{**base, **{col: "" for col in CSV_COLUMNS if col not in base}}]

    rows: list[dict[str, str]] = []
    for paper in papers:
        rows.append(
            {
                **base,
                "rank": str(paper.get("rank", "")),
                "score": str(paper.get("score", "")),
                "arxiv_id": paper.get("arxiv_id") or "",
                "title": paper.get("title") or "",
                "authors": _join_list(paper.get("authors")),
                "tldr": paper.get("tldr") or "",
                "summary": paper.get("summary") or "",
                "pdf_url": paper.get("pdf_url") or "",
                "published_date": paper.get("published_date") or "",
                "categories": _join_list(paper.get("categories")),
                "affiliations": _join_list(paper.get("affiliations")),
                "code_url": paper.get("code_url") or "",
            }
        )
    return rows


def write_json(digests: list[dict[str, Any]], output: Path | None) -> None:
    payload = {
        "exported_at": date.today().isoformat(),
        "digest_count": len(digests),
        "digests": digests,
    }
    text = json.dumps(payload, indent=2, ensure_ascii=False) + "\n"
    if output:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(text, encoding="utf-8")
    else:
        sys.stdout.write(text)


def write_csv(rows: list[dict[str, str]], output: Path | None) -> None:
    if output:
        output.parent.mkdir(parents=True, exist_ok=True)
        with output.open("w", encoding="utf-8", newline="") as fh:
            writer = csv.DictWriter(fh, fieldnames=CSV_COLUMNS, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(rows)
    else:
        writer = csv.DictWriter(sys.stdout, fieldnames=CSV_COLUMNS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


async def load_digests(
    store: SQLiteStorage,
    user_id: str,
    from_date: str | None,
    to_date: str | None,
) -> list[dict[str, Any]]:
    dates = await list_daily_digest_dates(store, user_id)
    dates = _filter_dates(dates, from_date, to_date)

    digests: list[dict[str, Any]] = []
    for digest_date in dates:
        record = await load_daily_digest(store, user_id, digest_date)
        if record:
            digests.append(record)
    return digests


async def run(args: argparse.Namespace) -> int:
    db_path = Path(args.db).expanduser()
    if not db_path.exists():
        print(f"No database at {db_path}", file=sys.stderr)
        return 1

    user_id = args.user_id
    if user_id is None:
        try:
            user_id = load_config(args.config).storage.user_id
        except Exception:
            user_id = "default_user"

    store = SQLiteStorage(db_path)

    if args.list:
        dates = await list_daily_digest_dates(store, user_id)
        dates = _filter_dates(dates, args.from_date, args.to_date)
        if not dates:
            prefix = digest_key_prefix(user_id)
            print(f"No digest records for user {user_id!r} (prefix {prefix})")
            return 0
        for d in dates:
            record = await load_daily_digest(store, user_id, d)
            count = record.get("paper_count", 0) if record else 0
            print(f"{d}\t{count} papers")
        print(f"\n{len(dates)} day(s)")
        return 0

    digests = await load_digests(store, user_id, args.from_date, args.to_date)
    if not digests:
        print(
            f"No digest records to export for user {user_id!r}"
            + (
                f" between {args.from_date} and {args.to_date}"
                if args.from_date or args.to_date
                else ""
            ),
            file=sys.stderr,
        )
        return 1

    output = Path(args.output).expanduser() if args.output else None
    fmt = args.format

    if fmt in ("json", "both"):
        json_path = output
        if fmt == "both":
            if output is None:
                json_path = Path("paperscout_digests.json")
            else:
                json_path = output.with_suffix(".json") if output.suffix == ".csv" else output
        write_json(digests, json_path)
        if json_path:
            print(f"Wrote JSON: {json_path} ({len(digests)} digests)", file=sys.stderr)

    if fmt in ("csv", "both"):
        csv_path = output
        if fmt == "both":
            if output is None:
                csv_path = Path("paperscout_digests.csv")
            else:
                csv_path = output.with_suffix(".csv") if output.suffix == ".json" else output
        rows: list[dict[str, str]] = []
        for digest in digests:
            rows.extend(digest_to_csv_rows(digest))
        write_csv(rows, csv_path)
        if csv_path:
            print(f"Wrote CSV: {csv_path} ({len(rows)} rows)", file=sys.stderr)

    return 0


def main() -> int:
    default_db = ALITHIA_HOME / "data" / "alithia.db"

    parser = argparse.ArgumentParser(
        description="Export PaperScout daily digest metadata from local SQLite storage.",
    )
    parser.add_argument(
        "--db",
        default=str(default_db),
        help=f"SQLite database path (default: {default_db})",
    )
    parser.add_argument(
        "--config",
        help="Alithia config path (used to resolve --user-id when omitted).",
    )
    parser.add_argument(
        "--user-id",
        help="User id in digest keys (default: from config, else default_user).",
    )
    parser.add_argument(
        "--from", dest="from_date", metavar="YYYY-MM-DD", help="Start date (inclusive)."
    )
    parser.add_argument("--to", dest="to_date", metavar="YYYY-MM-DD", help="End date (inclusive).")
    parser.add_argument(
        "--format",
        choices=["json", "csv", "both"],
        default="json",
        help="Export format (default: json).",
    )
    parser.add_argument(
        "-o",
        "--output",
        help="Output file (default: stdout for single format).",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="List available digest dates and exit.",
    )
    args = parser.parse_args()

    return asyncio.run(run(args))


if __name__ == "__main__":
    raise SystemExit(main())

"""Tests for export_paperscout_digests script helpers."""

import json
from io import StringIO

from scripts.export_paperscout_digests import (
    CSV_COLUMNS,
    _filter_dates,
    digest_to_csv_rows,
    write_csv,
    write_json,
)


def test_filter_dates():
    dates = ["2026-06-01", "2026-06-10", "2026-06-20"]
    assert _filter_dates(dates, "2026-06-05", "2026-06-15") == ["2026-06-10"]


def test_digest_to_csv_rows_one_paper():
    digest = {
        "digest_date": "2026-06-10",
        "source": "scheduler",
        "query": "cat:cs.AI",
        "paper_count": 1,
        "saved_at": "2026-06-11T00:00:00",
        "metrics": {"avg_score": 8.1},
        "papers": [
            {
                "rank": 1,
                "score": 8.1,
                "arxiv_id": "2401.00001",
                "title": "Test",
                "authors": ["Alice"],
                "tldr": "TLDR",
                "summary": "Abstract",
                "pdf_url": "https://arxiv.org/pdf/2401.00001.pdf",
                "published_date": "2024-01-15",
                "categories": ["cs.AI"],
                "affiliations": ["MIT"],
            }
        ],
    }
    rows = digest_to_csv_rows(digest)
    assert len(rows) == 1
    assert rows[0]["digest_date"] == "2026-06-10"
    assert rows[0]["arxiv_id"] == "2401.00001"
    assert rows[0]["authors"] == "Alice"
    assert rows[0]["avg_score"] == "8.1"


def test_digest_to_csv_rows_empty_day():
    rows = digest_to_csv_rows({"digest_date": "2026-06-29", "papers": [], "paper_count": 0})
    assert len(rows) == 1
    assert rows[0]["digest_date"] == "2026-06-29"
    assert rows[0]["arxiv_id"] == ""


def test_write_json_stdout(capsys):
    write_json([{"digest_date": "2026-06-10", "papers": []}], None)
    out = json.loads(capsys.readouterr().out)
    assert out["digest_count"] == 1


def test_write_csv_stdout():
    buf = StringIO()
    import sys

    old = sys.stdout
    sys.stdout = buf
    try:
        write_csv([{col: "x" if col == "digest_date" else "" for col in CSV_COLUMNS}], None)
    finally:
        sys.stdout = old
    assert "digest_date" in buf.getvalue()

"""Tests for PaperScout workflow nodes."""

from datetime import date

from alithia_agent.paperscout.nodes import _build_arxiv_category_query


def test_build_arxiv_category_query_single_day():
    query = _build_arxiv_category_query("cs.AI", date(2026, 6, 14), date(2026, 6, 14))
    assert query == "cat:cs.AI AND submittedDate:[202606140000 TO 202606142359]"


def test_build_arxiv_category_query_date_range():
    query = _build_arxiv_category_query("cs.CV", date(2026, 6, 12), date(2026, 6, 14))
    assert query == "cat:cs.CV AND submittedDate:[202606120000 TO 202606142359]"

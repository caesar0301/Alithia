"""Tests for the ResearchInterest data model (RFC-010 §6.1)."""

from datetime import date

import pytest
from pydantic import ValidationError

from alithia.research_interests import ResearchInterest


def test_defaults():
    interest = ResearchInterest(title="Multimodal")
    assert interest.source == "manual"
    assert interest.weight == 1.0
    assert interest.arxiv_categories == []
    assert interest.tags == []
    assert interest.notes == ""
    assert interest.date_added is None
    assert interest.zotero_item_key is None
    assert interest.body == ""


def test_weight_must_be_non_negative():
    with pytest.raises(ValidationError):
        ResearchInterest(title="x", weight=-0.5)


def test_weight_zero_is_allowed_parking():
    interest = ResearchInterest(title="x", weight=0.0)
    assert interest.weight == 0.0


def test_source_literal():
    ResearchInterest(title="x", source="manual")
    ResearchInterest(title="x", source="zotero")
    with pytest.raises(ValidationError):
        ResearchInterest(title="x", source="google_scholar")  # type: ignore[arg-type]


def test_date_added_coerces_short_iso():
    interest = ResearchInterest(title="x", date_added="2024-05-24")
    assert interest.date_added == date(2024, 5, 24)


def test_date_added_rejects_full_iso_datetime():
    """Zotero sends full timestamps; the model must reject them so the sync
    step is forced to trim to YYYY-MM-DD (RFC-010 §8.2)."""
    with pytest.raises(ValidationError):
        ResearchInterest(title="x", date_added="2024-05-24T10:30:00Z")


def test_searchable_text_combines_notes_body_tags():
    interest = ResearchInterest(
        title="Multimodal",
        notes="prioritize benchmarks",
        body="cross-modal alignment is the bottleneck",
        tags=["clip", "siglip"],
    )
    text = interest.get_searchable_text()
    assert "prioritize benchmarks" in text
    assert "cross-modal alignment is the bottleneck" in text
    assert "clip" in text and "siglip" in text


def test_searchable_text_handles_missing_fields():
    interest = ResearchInterest(title="Only title")
    assert interest.get_searchable_text() == ""


def test_display_title():
    assert ResearchInterest(title="LLM Agents").display_title == "LLM Agents"

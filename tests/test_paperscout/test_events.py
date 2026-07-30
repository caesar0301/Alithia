"""Tests for PaperScout event system."""

from alithia.paperscout.events import (
    PAPERSCOUT_EMAIL_SENT,
    PAPERSCOUT_ERROR,
    PAPERSCOUT_PAPER_FOUND,
    PAPERSCOUT_STEP,
    PaperScoutEmailSentEvent,
    PaperScoutErrorEvent,
    PaperScoutPaperFoundEvent,
    PaperScoutStepEvent,
)


def test_events_constants():
    """Test that all PaperScout event constants have correct wire types."""
    # Check that all event types have the correct wire type prefix
    assert PAPERSCOUT_STEP.startswith("soothe.subagent.alithia.paperscout")
    assert PAPERSCOUT_PAPER_FOUND.startswith("soothe.subagent.alithia.paperscout")
    assert PAPERSCOUT_EMAIL_SENT.startswith("soothe.subagent.alithia.paperscout")
    assert PAPERSCOUT_ERROR.startswith("soothe.subagent.alithia.paperscout")


def test_step_event():
    """Test PaperScoutStepEvent creation."""
    event = PaperScoutStepEvent(step="data_collection", status="Fetching papers")

    assert event.type == PAPERSCOUT_STEP
    assert event.step == "data_collection"
    assert event.status == "Fetching papers"


def test_paper_found_event():
    """Test PaperScoutPaperFoundEvent creation."""
    event = PaperScoutPaperFoundEvent(
        paper_title="Attention Is All You Need",
        arxiv_id="1706.03762",
        score=7.5,
    )

    assert event.type == PAPERSCOUT_PAPER_FOUND
    assert event.paper_title == "Attention Is All You Need"
    assert event.arxiv_id == "1706.03762"
    assert event.score == 7.5


def test_email_sent_event():
    """Test PaperScoutEmailSentEvent creation."""
    event = PaperScoutEmailSentEvent(
        recipient="user@example.com",
        papers_count=10,
    )

    assert event.type == PAPERSCOUT_EMAIL_SENT
    assert event.recipient == "user@example.com"
    assert event.papers_count == 10


def test_error_event():
    """Test PaperScoutErrorEvent creation."""
    event = PaperScoutErrorEvent(
        error_message="SMTP connection failed",
        step="communication",
    )

    assert event.type == PAPERSCOUT_ERROR
    assert event.error_message == "SMTP connection failed"
    assert event.step == "communication"


def test_event_extra_fields():
    """Test that events allow extra fields."""
    event = PaperScoutStepEvent(
        step="test",
        status="testing",
        extra_field="extra_value",  # Should be allowed
    )

    assert event.extra_field == "extra_value"

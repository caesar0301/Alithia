"""Tests for PaperScout email formatting."""

from datetime import datetime

from alithia_agent.models import ArxivPaper, ScoredPaper
from alithia_agent.paperscout.email import (
    construct_email_content,
    create_empty_email_html,
    create_paper_html,
    get_stars_html,
)


def test_get_stars_html_low_score():
    """Test star rating for low score."""
    stars = get_stars_html(5.0)
    assert stars == ""


def test_get_stars_html_high_score():
    """Test star rating for high score."""
    stars = get_stars_html(8.5)
    assert "⭐" in stars


def test_get_stars_html_max_score():
    """Test star rating for max score."""
    stars = get_stars_html(10.0)
    assert stars.count("⭐") == 5


def test_create_paper_html(sample_arxiv_paper):
    """Test creating HTML for a paper."""
    scored_paper = ScoredPaper(
        paper=sample_arxiv_paper,
        score=7.5,
        relevance_factors={"test": 7.5},
    )

    html = create_paper_html(scored_paper)

    assert "Attention Is All You Need" in html
    assert "1706.03762" in html
    assert "Ashish Vaswani" in html


def test_create_empty_email_html():
    """Test creating empty email HTML."""
    html = create_empty_email_html()

    assert "No Papers Today" in html
    assert "Take a Rest" in html


def test_construct_email_content_empty():
    """Test constructing email with no papers."""
    email_content = construct_email_content([])

    assert "No Papers" in email_content.subject
    assert email_content.html_body is not None
    assert len(email_content.papers) == 0


def test_construct_email_content_with_papers(sample_arxiv_paper):
    """Test constructing email with papers."""
    scored_paper = ScoredPaper(
        paper=sample_arxiv_paper,
        score=7.5,
        relevance_factors={"test": 7.5},
    )

    email_content = construct_email_content([scored_paper])

    assert "PaperScout Digest" in email_content.subject
    assert "Attention Is All You Need" in email_content.html_body
    assert len(email_content.papers) == 1


# Affiliation Display Tests


def test_affiliation_display_with_affiliations():
    """Test that affiliations are displayed correctly in email HTML."""
    paper = ArxivPaper(
        title="Test Paper with Affiliations",
        summary="Test abstract for affiliation testing",
        authors=["Alice Smith", "Bob Jones"],
        arxiv_id="2401.12345",
        pdf_url="https://arxiv.org/pdf/2401.12345.pdf",
        published_date=datetime(2024, 1, 15),
        affiliations=["MIT", "Stanford University"],
    )
    scored_paper = ScoredPaper(paper=paper, score=8.0, relevance_factors={"test": 8.0})

    html = create_paper_html(scored_paper)

    # Verify affiliations are displayed
    assert "MIT" in html
    assert "Stanford University" in html
    assert "<i>MIT, Stanford University</i>" in html


def test_affiliation_display_with_many_affiliations():
    """Test that affiliations are truncated when more than 5."""
    paper = ArxivPaper(
        title="Multi-Institution Paper",
        summary="Paper with many affiliations",
        authors=["Alice Smith", "Bob Jones", "Carol White"],
        arxiv_id="2401.12346",
        pdf_url="https://arxiv.org/pdf/2401.12346.pdf",
        published_date=datetime(2024, 1, 15),
        affiliations=[
            "MIT",
            "Stanford",
            "Berkeley",
            "CMU",
            "Google",
            "OpenAI",
            "DeepMind",
        ],
    )
    scored_paper = ScoredPaper(paper=paper, score=7.5, relevance_factors={"test": 7.5})

    html = create_paper_html(scored_paper)

    # Should show first 5 affiliations with ellipsis
    assert "MIT" in html
    assert "Stanford" in html
    assert "Berkeley" in html
    assert "CMU" in html
    assert "Google" in html
    # Should NOT show the 6th and 7th affiliations
    assert "OpenAI" not in html
    assert "DeepMind" not in html
    # Should have ellipsis indicator
    assert "..." in html


def test_affiliation_display_graceful_fallback_none():
    """Test graceful fallback when affiliations is None."""
    paper = ArxivPaper(
        title="Paper Without Affiliations",
        summary="Test abstract",
        authors=["Alice Smith"],
        arxiv_id="2401.12347",
        pdf_url="https://arxiv.org/pdf/2401.12347.pdf",
        published_date=datetime(2024, 1, 15),
        affiliations=None,
    )
    scored_paper = ScoredPaper(paper=paper, score=7.0, relevance_factors={"test": 7.0})

    html = create_paper_html(scored_paper)

    # Should show fallback text
    assert "Unknown Affiliation" in html


def test_affiliation_display_graceful_fallback_empty():
    """Test graceful fallback when affiliations is empty list."""
    paper = ArxivPaper(
        title="Paper With Empty Affiliations",
        summary="Test abstract",
        authors=["Alice Smith"],
        arxiv_id="2401.12348",
        pdf_url="https://arxiv.org/pdf/2401.12348.pdf",
        published_date=datetime(2024, 1, 15),
        affiliations=[],
    )
    scored_paper = ScoredPaper(paper=paper, score=7.0, relevance_factors={"test": 7.0})

    html = create_paper_html(scored_paper)

    # Should show fallback text
    assert "Unknown Affiliation" in html


def test_affiliation_display_single_affiliation():
    """Test display with exactly one affiliation."""
    paper = ArxivPaper(
        title="Single Institution Paper",
        summary="Test abstract",
        authors=["Alice Smith"],
        arxiv_id="2401.12349",
        pdf_url="https://arxiv.org/pdf/2401.12349.pdf",
        published_date=datetime(2024, 1, 15),
        affiliations=["MIT"],
    )
    scored_paper = ScoredPaper(paper=paper, score=7.5, relevance_factors={"test": 7.5})

    html = create_paper_html(scored_paper)

    # Should show the single affiliation without comma
    assert "<i>MIT</i>" in html


def test_affiliation_display_exactly_five():
    """Test display with exactly 5 affiliations (boundary case)."""
    paper = ArxivPaper(
        title="Five Institutions Paper",
        summary="Test abstract",
        authors=["Alice Smith"],
        arxiv_id="2401.12350",
        pdf_url="https://arxiv.org/pdf/2401.12350.pdf",
        published_date=datetime(2024, 1, 15),
        affiliations=["MIT", "Stanford", "Berkeley", "CMU", "Google"],
    )
    scored_paper = ScoredPaper(paper=paper, score=7.5, relevance_factors={"test": 7.5})

    html = create_paper_html(scored_paper)

    # Should show all 5 without ellipsis
    assert "MIT" in html
    assert "Stanford" in html
    assert "Berkeley" in html
    assert "CMU" in html
    assert "Google" in html
    # Should NOT have ellipsis since exactly 5
    assert ", ..." not in html


def test_affiliation_formatting_in_email_context():
    """Test that affiliations appear correctly formatted in full email."""
    paper = ArxivPaper(
        title="Context Test Paper",
        summary="Test abstract for email context",
        authors=["Alice Smith", "Bob Jones"],
        arxiv_id="2401.12351",
        pdf_url="https://arxiv.org/pdf/2401.12351.pdf",
        published_date=datetime(2024, 1, 15),
        affiliations=["MIT", "Stanford University"],
    )
    scored_paper = ScoredPaper(paper=paper, score=8.0, relevance_factors={"test": 8.0})

    email_content = construct_email_content([scored_paper])

    # Verify affiliations appear in full email body
    assert "MIT" in email_content.html_body
    assert "Stanford University" in email_content.html_body
    # Verify proper HTML formatting with italics
    assert "<i>MIT, Stanford University</i>" in email_content.html_body
    # Verify the paper is tracked
    assert len(email_content.papers) == 1
    assert email_content.papers[0].arxiv_id == scored_paper.paper.arxiv_id


# TLDR / abstract length tests


def _make_paper(summary: str) -> ArxivPaper:
    return ArxivPaper(
        title="TLDR Test Paper",
        summary=summary,
        authors=["Alice Smith"],
        arxiv_id="2401.13999",
        pdf_url="https://arxiv.org/pdf/2401.13999.pdf",
        published_date=datetime(2024, 1, 15),
    )


def test_tldr_short_summary_no_ellipsis():
    """A summary shorter than max_chars is shown in full, with no trailing '...'."""
    paper = _make_paper("Short abstract.")
    scored = ScoredPaper(paper=paper, score=7.0, relevance_factors={"t": 7.0})

    html = create_paper_html(scored, max_chars=600)

    assert "Short abstract." in html
    assert "Short abstract...." not in html  # no double dots from old bug


def test_tldr_long_summary_truncated_to_max_chars():
    """A long summary is truncated to max_chars with a trailing '...'."""
    long_summary = "x" * 1000
    paper = _make_paper(long_summary)
    scored = ScoredPaper(paper=paper, score=7.0, relevance_factors={"t": 7.0})

    html = create_paper_html(scored, max_chars=120)

    # Exactly 120 'x' chars then "..."
    assert "x" * 120 + "..." in html
    assert "x" * 121 not in html


def test_tldr_max_chars_param_respected():
    """Different max_chars values produce different truncation."""
    long_summary = "y" * 500
    paper = _make_paper(long_summary)
    scored = ScoredPaper(paper=paper, score=7.0, relevance_factors={"t": 7.0})

    html_50 = create_paper_html(scored, max_chars=50)
    html_200 = create_paper_html(scored, max_chars=200)

    assert "y" * 50 + "..." in html_50
    assert "y" * 200 + "..." in html_200


def test_tldr_default_max_chars_is_600():
    """Default truncation budget is 600 chars (the raised config default)."""
    long_summary = "z" * 800
    paper = _make_paper(long_summary)
    scored = ScoredPaper(paper=paper, score=7.0, relevance_factors={"t": 7.0})

    html = create_paper_html(scored)  # no max_chars -> default 600

    assert "z" * 600 + "..." in html
    assert "z" * 601 not in html


def test_construct_email_content_threads_max_chars():
    """construct_email_content forwards max_chars to each paper block."""
    long_summary = "w" * 1000
    paper = _make_paper(long_summary)
    scored = ScoredPaper(paper=paper, score=7.0, relevance_factors={"t": 7.0})

    email_content = construct_email_content([scored], max_chars=80)

    assert "w" * 80 + "..." in email_content.html_body
    assert "w" * 81 not in email_content.html_body


def test_tldr_prefers_explicit_tldr_over_summary():
    """If ArxivPaper.tldr is set, it is used instead of summary."""
    paper = _make_paper("summary text")
    paper.tldr = "Explicit TLDR."
    scored = ScoredPaper(paper=paper, score=7.0, relevance_factors={"t": 7.0})

    html = create_paper_html(scored, max_chars=600)

    assert "Explicit TLDR." in html
    assert "summary text" not in html

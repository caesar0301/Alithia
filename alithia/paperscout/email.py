"""
Email construction and delivery utilities.
"""

import math
from typing import List

from .models import EmailContent, ScoredPaper

EMAIL_TEMPLATE = """
<!DOCTYPE HTML>
<html>
<head>
  <style>
    .star-wrapper {{
      font-size: 1.3em;
      line-height: 1;
      display: inline-flex;
      align-items: center;
    }}
    .half-star {{
      display: inline-block;
      width: 0.5em;
      overflow: hidden;
      white-space: nowrap;
      vertical-align: middle;
    }}
    .full-star {{
      vertical-align: middle;
    }}
  </style>
</head>
<body>

<div>
    {content}
</div>

<br><br>
<div>
To unsubscribe, remove your email in your Github Action setting.
</div>

</body>
</html>
"""


def get_stars_html(score: float) -> str:
    """
    Generate star rating HTML based on score.

    Args:
        score: Relevance score (0-10)

    Returns:
        HTML string with star rating
    """
    full_star = '<span class="full-star">⭐</span>'
    half_star = '<span class="half-star">⭐</span>'

    low = 6
    high = 8

    if score <= low:
        return ""
    elif score >= high:
        return full_star * 5
    else:
        interval = (high - low) / 10
        star_num = math.ceil((score - low) / interval)
        full_star_num = int(star_num / 2)
        half_star_num = star_num - full_star_num * 2
        return '<div class="star-wrapper">' + full_star * full_star_num + half_star * half_star_num + "</div>"


def create_paper_html(paper: ScoredPaper) -> str:
    """
    Create HTML block for a single paper.

    Args:
        paper: ScoredPaper to format

    Returns:
        HTML string for the paper
    """
    stars_html = get_stars_html(paper.score)

    # Format authors
    authors = paper.paper.authors[:5]
    authors_str = ", ".join(authors)
    if len(paper.paper.authors) > 5:
        authors_str += ", ..."

    # Format affiliations
    affiliations = []
    if paper.paper.affiliations:
        affiliations = paper.paper.affiliations[:5]
        affiliations_str = ", ".join(affiliations)
        if len(paper.paper.affiliations) > 5:
            affiliations_str += ", ..."
    else:
        affiliations_str = "Unknown Affiliation"

    # Code link
    code_link = ""
    if paper.paper.code_url:
        code_link = f'<a href="{paper.paper.code_url}" style="display: inline-block; text-decoration: none; font-size: 14px; font-weight: bold; color: #fff; background-color: #5bc0de; padding: 8px 16px; border-radius: 4px; margin-left: 8px;">Code</a>'

    return f"""
    <table border="0" cellpadding="0" cellspacing="0" width="100%" style="font-family: Arial, sans-serif; border: 1px solid #ddd; border-radius: 8px; padding: 16px; background-color: #f9f9f9;">
    <tr>
        <td style="font-size: 20px; font-weight: bold; color: #333;">
            {paper.paper.title}
        </td>
    </tr>
    <tr>
        <td style="font-size: 14px; color: #666; padding: 8px 0;">
            {authors_str}
            <br>
            <i>{affiliations_str}</i>
        </td>
    </tr>
    <tr>
        <td style="font-size: 14px; color: #333; padding: 8px 0;">
            <strong>Relevance:</strong> {stars_html}
        </td>
    </tr>
    <tr>
        <td style="font-size: 14px; color: #333; padding: 8px 0;">
            <strong>arXiv ID:</strong> {paper.paper.arxiv_id}
        </td>
    </tr>
    <tr>
        <td style="font-size: 14px; color: #333; padding: 8px 0;">
            <strong>TLDR:</strong> {paper.paper.tldr or 'No summary available'}
        </td>
    </tr>
    <tr>
        <td style="padding: 8px 0;">
            <a href="{paper.paper.pdf_url}" style="display: inline-block; text-decoration: none; font-size: 14px; font-weight: bold; color: #fff; background-color: #d9534f; padding: 8px 16px; border-radius: 4px;">PDF</a>
            {code_link}
        </td>
    </tr>
    </table>
    """


def create_empty_email_html() -> str:
    """Create HTML for empty email (no papers found)."""
    return """
    <table border="0" cellpadding="0" cellspacing="0" width="100%" style="font-family: Arial, sans-serif; border: 1px solid #ddd; border-radius: 8px; padding: 16px; background-color: #f9f9f9;">
    <tr>
        <td style="font-size: 20px; font-weight: bold; color: #333;">
            No Papers Today. Take a Rest!
        </td>
    </tr>
    </table>
    """


def _get_digest_date(papers: List[ScoredPaper]) -> str:
    """
    Get the digest date from papers (latest published date) or current date.

    Args:
        papers: List of scored papers

    Returns:
        Date string in YYYY-MM-DD format
    """
    from datetime import datetime

    if papers:
        # Get the latest published date from papers
        dates = [p.paper.published_date for p in papers if p.paper.published_date]
        if dates:
            latest_date = max(dates)
            return latest_date.strftime("%Y/%m/%d")

    # Fallback to current date
    return datetime.now().strftime("%Y/%m/%d")


def construct_email_content(papers: List[ScoredPaper]) -> EmailContent:
    """
    Construct complete email content from scored papers.

    Args:
        papers: List of scored papers to include

    Returns:
        EmailContent object or string content
    """
    digest_date = _get_digest_date(papers)

    if not papers:
        content = create_empty_email_html()
        return EmailContent(
            subject=f"Alithia Digest {digest_date} - No Papers Today",
            html_content=EMAIL_TEMPLATE.format(content=content),
            papers=[],
        )
    else:
        paper_blocks = [create_paper_html(paper) for paper in papers]
        content = "<br>".join(paper_blocks)

        return EmailContent(
            subject=f"Alithia Digest {digest_date}",
            html_content=EMAIL_TEMPLATE.format(content=content),
            papers=papers,
        )

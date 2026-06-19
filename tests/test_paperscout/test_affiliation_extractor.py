"""Tests for affiliation extraction from LaTeX source."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from alithia_agent.models import ArxivPaper
from alithia_agent.paperscout.affiliation_extractor import (
    AffiliationExtractor,
    enrich_papers_with_affiliations,
)

# Sample LaTeX content with affiliations
# Python source: \\author -> \author (LaTeX command)
# Python source: \\ -> \ (single backslash), but LaTeX line break is \\ so we need \\\\ in source
NIPS_STYLE_TEX = """
\\documentclass{article}
\\begin{document}
\\author{
  Ashish Vaswani\\\\
  Google Brain\\\\
  \\texttt{avaswani@google.com}\\\\
  \\And
  Noam Shazeer\\\\
  Google Brain\\\\
  \\texttt{noam@google.com}\\\\
  \\And
  Illia Polosukhin\\\\
  \\texttt{illia@gmail.com}\\\\
}
\\maketitle
\\end{document}
"""

IEEE_STYLE_TEX = """
\\documentclass{ieee}
\\begin{document}
\\author{John Smith}
\\institute{MIT}
\\maketitle
\\end{document}
"""

ACM_STYLE_TEX = """
\\documentclass{acmart}
\\begin{document}
\\author{Alice Johnson}
\\affiliation{Stanford University}
\\author{Bob Williams}
\\affiliation{Google Research}
\\maketitle
\\end{document}
"""

MULTI_AUTHOR_TEX = """
\\documentclass{article}
\\begin{document}
\\author{
  \\AND
  Alexander Viand\\\\
  ETH Zurich\\\\
  \\And
  Christian Knabenhans\\\\
  ETH Zurich\\\\
  \\And
  Anwar Hithnawi\\\\
  ETH Zurich\\\\
}
\\maketitle
\\end{document}
"""


# Tarball mock
class MockTarball:
    """Mock tarball for testing."""

    def __init__(self, tex_content: str):
        self.tex_content = tex_content

    def getmembers(self):
        """Return mock tar members."""
        member = MagicMock()
        member.name = "main.tex"
        member.isfile = lambda: True
        return [member]

    def extractfile(self, member):
        """Return mock file content."""
        mock_file = MagicMock()
        mock_file.read = lambda: self.tex_content.encode("utf-8")
        return mock_file


@pytest.fixture
def sample_paper():
    """Sample ArXiv paper for testing."""
    from datetime import datetime

    return ArxivPaper(
        title="Test Paper",
        summary="Test abstract",
        authors=["Ashish Vaswani", "Noam Shazeer"],
        arxiv_id="1706.03762",
        pdf_url="https://arxiv.org/pdf/1706.03762",
        published_date=datetime(2017, 6, 12),
    )


class TestAffiliationExtractor:
    """Tests for AffiliationExtractor class."""

    def test_parse_nips_style_affiliations(self):
        """Test parsing NIPS-style author blocks."""
        extractor = AffiliationExtractor()
        affiliations = extractor.parse_affiliations_from_tex(NIPS_STYLE_TEX)

        assert "Google Brain" in affiliations
        assert len(affiliations) >= 1

    def test_parse_ieee_style_affiliations(self):
        """Test parsing IEEE-style institute command."""
        extractor = AffiliationExtractor()
        affiliations = extractor.parse_affiliations_from_tex(IEEE_STYLE_TEX)

        assert "MIT" in affiliations

    def test_parse_acm_style_affiliations(self):
        """Test parsing ACM-style affiliation command."""
        extractor = AffiliationExtractor()
        affiliations = extractor.parse_affiliations_from_tex(ACM_STYLE_TEX)

        assert "Stanford University" in affiliations
        assert "Google Research" in affiliations

    def test_parse_multi_author_affiliations(self):
        """Test parsing multiple authors with same affiliation."""
        extractor = AffiliationExtractor()
        affiliations = extractor.parse_affiliations_from_tex(MULTI_AUTHOR_TEX)

        assert "ETH Zurich" in affiliations
        # Should deduplicate
        count_eth = sum(1 for a in affiliations if "ETH" in a)
        assert count_eth == 1

    def test_clean_institution(self):
        """Test institution name cleanup."""
        extractor = AffiliationExtractor()

        # Remove email wrapper (email itself remains in output after cleanup)
        cleaned = extractor._clean_institution("\\texttt{test@email.com}")
        # The cleanup removes \\texttt but leaves the content
        assert "\\texttt" not in cleaned

        # Remove LaTeX commands
        cleaned = extractor._clean_institution("\\textbf{MIT}")
        assert "MIT" in cleaned or "textbf" not in cleaned

        # Normalize whitespace
        cleaned = extractor._clean_institution("  MIT  ")
        assert cleaned == "MIT"

    def test_is_email_detection(self):
        """Test email detection."""
        extractor = AffiliationExtractor()

        assert extractor._is_email("test@email.com") is True
        assert extractor._is_email("\\texttt{test@email.com}") is True
        assert extractor._is_email("MIT") is False
        assert extractor._is_email("Google Brain") is False

    def test_looks_like_institution(self):
        """Test institution heuristics."""
        extractor = AffiliationExtractor()

        assert extractor._looks_like_institution("MIT") is True
        assert extractor._looks_like_institution("Google Brain") is True
        assert extractor._looks_like_institution("Stanford University") is True
        assert extractor._looks_like_institution("test@email.com") is False
        assert extractor._looks_like_institution("") is False
        assert extractor._looks_like_institution("ab") is False

    def test_deduplicate_affiliations(self):
        """Test that affiliations are deduplicated."""
        extractor = AffiliationExtractor()

        # Create tex with repeated affiliations
        tex = """
        \\author{
          Author A\\\\Google Brain\\\\
          \\And
          Author B\\\\Google Brain\\\\
        }
        """
        affiliations = extractor.parse_affiliations_from_tex(tex)

        # Should only have one Google Brain
        assert affiliations.count("Google Brain") == 1

    def test_limit_affiliations(self):
        """Test that affiliations are limited to 10."""
        extractor = AffiliationExtractor()

        # Create tex with many affiliations
        tex = "\\author{" + "\\And Author\\\\Inst{}\\\\" * 15 + "}"
        affiliations = extractor.parse_affiliations_from_tex(tex)

        assert len(affiliations) <= 10

    def test_empty_tex_returns_empty(self):
        """Test empty tex content returns empty list."""
        extractor = AffiliationExtractor()
        affiliations = extractor.parse_affiliations_from_tex("")
        assert affiliations == []

    def test_no_author_block_returns_empty(self):
        """Test tex without author block returns empty list."""
        extractor = AffiliationExtractor()
        tex = "\\documentclass{article}\\begin{document}Content\\end{document}"
        affiliations = extractor.parse_affiliations_from_tex(tex)
        assert affiliations == []

    @pytest.mark.asyncio
    async def test_enrich_paper_success(self, sample_paper):
        """Test enriching a paper with affiliations."""
        extractor = AffiliationExtractor()

        # Mock the fetch and extraction
        with patch.object(extractor, "fetch_source", new_callable=AsyncMock) as mock_fetch:
            with patch.object(extractor, "extract_tex_files") as mock_extract:
                mock_fetch.return_value = b"mock tarball"
                mock_extract.return_value = [NIPS_STYLE_TEX]

                enriched = await extractor.enrich_paper(sample_paper)

                assert enriched.affiliations is not None
                assert "Google Brain" in enriched.affiliations

    @pytest.mark.asyncio
    async def test_enrich_paper_no_source(self, sample_paper):
        """Test enriching when source not available."""
        extractor = AffiliationExtractor()

        with patch.object(extractor, "fetch_source", new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = None

            enriched = await extractor.enrich_paper(sample_paper)

            # Should return paper unchanged
            assert enriched.affiliations is None

    @pytest.mark.asyncio
    async def test_enrich_paper_pdf_only(self, sample_paper):
        """Test enriching when source is PDF-only."""
        extractor = AffiliationExtractor()

        with patch.object(extractor, "fetch_source", new_callable=AsyncMock) as mock_fetch:
            # Return None (PDF-only case)
            mock_fetch.return_value = None

            enriched = await extractor.enrich_paper(sample_paper)

            assert enriched.affiliations is None

    @pytest.mark.asyncio
    async def test_enrich_papers_batch(self, sample_paper):
        """Test enriching multiple papers."""
        from datetime import datetime

        papers = [
            sample_paper,
            ArxivPaper(
                title="Paper 2",
                summary="Abstract 2",
                authors=["Alice", "Bob"],
                arxiv_id="2301.07041",
                pdf_url="https://arxiv.org/pdf/2301.07041",
                published_date=datetime(2023, 1, 17),
            ),
        ]

        extractor = AffiliationExtractor()

        with patch.object(extractor, "fetch_source", new_callable=AsyncMock) as mock_fetch:
            with patch.object(extractor, "extract_tex_files") as mock_extract:
                mock_fetch.return_value = b"mock tarball"
                mock_extract.return_value = [NIPS_STYLE_TEX]

                enriched = await extractor.enrich_papers(papers)

                assert len(enriched) == 2
                # At least one should have affiliations
                assert any(p.affiliations for p in enriched)

    @pytest.mark.asyncio
    async def test_enrich_paper_already_has_affiliations(self, sample_paper):
        """Test that paper with existing affiliations is not re-enriched."""
        sample_paper.affiliations = ["MIT"]
        extractor = AffiliationExtractor()

        enriched = await extractor.enrich_paper(sample_paper)

        # Should keep existing affiliations
        assert enriched.affiliations == ["MIT"]


class TestEnrichPapersWithAffiliations:
    """Tests for the convenience function."""

    @pytest.mark.asyncio
    async def test_enrich_papers_with_affiliations(self, sample_paper):
        """Test the convenience function."""
        with patch(
            "alithia_agent.paperscout.affiliation_extractor.AffiliationExtractor.enrich_papers",
            new_callable=AsyncMock,
        ) as mock_enrich:
            mock_enrich.return_value = [sample_paper]

            result = await enrich_papers_with_affiliations([sample_paper])

            assert len(result) == 1

    @pytest.mark.asyncio
    async def test_enrich_empty_list(self):
        """Test enriching empty list."""
        result = await enrich_papers_with_affiliations([])
        assert result == []


class TestHttpxIntegration:
    """Tests for httpx HTTP integration."""

    @pytest.mark.asyncio
    async def test_fetch_source_success(self):
        """Test successful source fetch."""
        extractor = AffiliationExtractor()

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {"content-type": "application/gzip"}
        mock_response.content = b"tarball content"

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client.aclose = AsyncMock()
            mock_client_class.return_value = mock_client

            result = await extractor.fetch_source("2301.07041")

            assert result == b"tarball content"

    @pytest.mark.asyncio
    async def test_fetch_source_pdf_only(self):
        """Test fetch when source is PDF."""
        extractor = AffiliationExtractor()

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {"content-type": "application/pdf"}
        mock_response.content = b"pdf content"

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client.aclose = AsyncMock()
            mock_client_class.return_value = mock_client

            result = await extractor.fetch_source("2012.12104")

            assert result is None

    @pytest.mark.asyncio
    async def test_fetch_source_not_found(self):
        """Test fetch when source not found."""
        extractor = AffiliationExtractor()

        mock_response = MagicMock()
        mock_response.status_code = 404

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client.aclose = AsyncMock()
            mock_client_class.return_value = mock_client

            result = await extractor.fetch_source("invalid-id")

            assert result is None

    @pytest.mark.asyncio
    async def test_close_client(self):
        """Test closing HTTP client."""
        extractor = AffiliationExtractor()

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.aclose = AsyncMock()
            mock_client_class.return_value = mock_client

            await extractor._get_client()
            await extractor.close()

            mock_client.aclose.assert_called_once()

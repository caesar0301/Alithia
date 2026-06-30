"""Tests for affiliation extraction from ArXiv LaTeX source.

The parser layer is now an LLM call (see ``affiliation_llm.py``); these
tests cover the fetch + orchestration layer in ``affiliation_extractor.py``:
source download, tarball/gzip extraction, and wiring of the batched LLM
extraction onto ``paper.affiliations``. The LLM client itself is mocked.
"""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from alithia_agent.models import ArxivPaper
from alithia_agent.paperscout.affiliation_extractor import (
    AffiliationExtractor,
    enrich_papers_with_affiliations,
)


def _fake_llm_response(text: str) -> MagicMock:
    """Build a fake openai chat.completions.create return value."""
    msg = MagicMock()
    msg.content = text
    choice = MagicMock()
    choice.message = msg
    resp = MagicMock()
    resp.choices = [choice]
    return resp


def _llm_config() -> dict:
    return {
        "api_key": "fake-key",
        "api_base": "https://dashscope.example.com/v1",
        "model": "qwen-turbo-latest",
    }


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
}
\\maketitle
\\end{document}
"""


@pytest.fixture
def sample_paper():
    """Sample ArXiv paper for testing."""
    return ArxivPaper(
        title="Test Paper",
        summary="Test abstract",
        authors=["Ashish Vaswani", "Noam Shazeer"],
        arxiv_id="1706.03762",
        pdf_url="https://arxiv.org/pdf/1706.03762",
        published_date=datetime(2017, 6, 12),
    )


class TestEnrichPaper:
    """Single-paper enrichment via the LLM path."""

    @pytest.mark.asyncio
    async def test_enrich_paper_populates_affiliations(self, sample_paper):
        """A fetched source + LLM JSON response populates affiliations."""
        extractor = AffiliationExtractor(llm_config=_llm_config())
        with (
            patch.object(extractor, "fetch_source", new_callable=AsyncMock) as mock_fetch,
            patch.object(extractor, "extract_tex_files") as mock_extract,
            patch("openai.OpenAI") as mock_openai,
        ):
            mock_fetch.return_value = b"mock tarball"
            mock_extract.return_value = [NIPS_STYLE_TEX]
            mock_client = MagicMock()
            mock_client.chat.completions.create.return_value = _fake_llm_response(
                '[{"arxiv_id": "1706.03762", "affiliations": ["Google Brain"]}]'
            )
            mock_openai.return_value = mock_client

            enriched = await extractor.enrich_paper(sample_paper)

        assert enriched.affiliations == ["Google Brain"]

    @pytest.mark.asyncio
    async def test_enrich_paper_no_source(self, sample_paper):
        """No LaTeX source (PDF-only / 404) leaves affiliations unset."""
        extractor = AffiliationExtractor(llm_config=_llm_config())
        with patch.object(extractor, "fetch_source", new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = None
            enriched = await extractor.enrich_paper(sample_paper)
        assert enriched.affiliations is None

    @pytest.mark.asyncio
    async def test_enrich_paper_already_has_affiliations(self, sample_paper):
        """A paper with existing affiliations is not re-enriched."""
        sample_paper.affiliations = ["MIT"]
        extractor = AffiliationExtractor(llm_config=_llm_config())
        with patch.object(extractor, "fetch_source", new_callable=AsyncMock) as mock_fetch:
            enriched = await extractor.enrich_paper(sample_paper)
            # Source was never fetched.
            mock_fetch.assert_not_called()
        assert enriched.affiliations == ["MIT"]

    @pytest.mark.asyncio
    async def test_enrich_paper_llm_returns_empty(self, sample_paper):
        """A non-JSON / empty LLM response leaves affiliations unset."""
        extractor = AffiliationExtractor(llm_config=_llm_config())
        with (
            patch.object(extractor, "fetch_source", new_callable=AsyncMock) as mock_fetch,
            patch.object(extractor, "extract_tex_files") as mock_extract,
            patch("openai.OpenAI") as mock_openai,
        ):
            mock_fetch.return_value = b"mock tarball"
            mock_extract.return_value = [NIPS_STYLE_TEX]
            mock_client = MagicMock()
            mock_client.chat.completions.create.return_value = _fake_llm_response("not json")
            mock_openai.return_value = mock_client

            enriched = await extractor.enrich_paper(sample_paper)
        assert enriched.affiliations is None

    @pytest.mark.asyncio
    async def test_enrich_paper_no_llm_config_is_noop(self, sample_paper):
        """Without an LLM config enrichment is skipped (no ArXiv fetch)."""
        extractor = AffiliationExtractor()  # no llm_config
        with patch.object(extractor, "fetch_source", new_callable=AsyncMock) as mock_fetch:
            enriched = await extractor.enrich_paper(sample_paper)
            mock_fetch.assert_not_called()
        assert enriched.affiliations is None


class TestEnrichPapers:
    """Batch enrichment: sources fetched concurrently, one batched LLM call."""

    @pytest.mark.asyncio
    async def test_enrich_papers_batch(self, sample_paper):
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
        extractor = AffiliationExtractor(llm_config=_llm_config())
        with (
            patch.object(extractor, "fetch_source", new_callable=AsyncMock) as mock_fetch,
            patch.object(extractor, "extract_tex_files") as mock_extract,
            patch("openai.OpenAI") as mock_openai,
        ):
            mock_fetch.return_value = b"mock tarball"
            mock_extract.return_value = [NIPS_STYLE_TEX]
            mock_client = MagicMock()

            def fake_create(*args, **kwargs):
                # Return affiliations for both ids present in the prompt.
                import json as _json
                import re

                user_msg = kwargs["messages"][1]["content"]
                ids = [m.group(1) for m in re.finditer(r"### arxiv_id: (\S+)", user_msg)]
                arr = [{"arxiv_id": i, "affiliations": [f"Lab-{i}"]} for i in ids]
                return _fake_llm_response(_json.dumps(arr))

            mock_client.chat.completions.create.side_effect = fake_create
            mock_openai.return_value = mock_client

            enriched = await extractor.enrich_papers(papers)

        assert len(enriched) == 2
        assert enriched[0].affiliations == ["Lab-1706.03762"]
        assert enriched[1].affiliations == ["Lab-2301.07041"]

    @pytest.mark.asyncio
    async def test_enrich_papers_skips_existing(self, sample_paper):
        """Papers that already have affiliations are skipped (no fetch)."""
        sample_paper.affiliations = ["MIT"]
        papers = [
            sample_paper,
            ArxivPaper(
                title="Paper 2",
                summary="Abstract 2",
                authors=["Alice"],
                arxiv_id="2301.07041",
                pdf_url="https://arxiv.org/pdf/2301.07041",
                published_date=datetime(2023, 1, 17),
            ),
        ]
        extractor = AffiliationExtractor(llm_config=_llm_config())
        with (
            patch.object(extractor, "fetch_source", new_callable=AsyncMock) as mock_fetch,
            patch.object(extractor, "extract_tex_files") as mock_extract,
            patch("openai.OpenAI") as mock_openai,
        ):
            mock_fetch.return_value = b"mock tarball"
            mock_extract.return_value = [NIPS_STYLE_TEX]
            mock_client = MagicMock()
            mock_client.chat.completions.create.return_value = _fake_llm_response(
                '[{"arxiv_id": "2301.07041", "affiliations": ["Stanford"]}]'
            )
            mock_openai.return_value = mock_client

            await extractor.enrich_papers(papers)

        # Only the second paper was fetched (its arxiv_id appears once).
        assert sample_paper.affiliations == ["MIT"]
        assert papers[1].affiliations == ["Stanford"]

    @pytest.mark.asyncio
    async def test_enrich_papers_empty_list(self):
        extractor = AffiliationExtractor(llm_config=_llm_config())
        assert await extractor.enrich_papers([]) == []


class TestEnrichPapersWithAffiliations:
    """The module-level convenience wrapper."""

    @pytest.mark.asyncio
    async def test_enrich_papers_with_affiliations(self, sample_paper):
        with patch(
            "alithia_agent.paperscout.affiliation_extractor.AffiliationExtractor.enrich_papers",
            new_callable=AsyncMock,
        ) as mock_enrich:
            mock_enrich.return_value = [sample_paper]
            result = await enrich_papers_with_affiliations([sample_paper])
        assert len(result) == 1

    @pytest.mark.asyncio
    async def test_enrich_empty_list(self):
        result = await enrich_papers_with_affiliations([])
        assert result == []


class TestHttpxIntegration:
    """Tests for httpx HTTP integration (source fetch, independent of LLM)."""

    @pytest.mark.asyncio
    async def test_fetch_source_success(self):
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
        extractor = AffiliationExtractor()
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.aclose = AsyncMock()
            mock_client_class.return_value = mock_client

            await extractor._get_client()
            await extractor.close()
            mock_client.aclose.assert_called_once()


class TestExtractTexFiles:
    """Tarball / single-gzip extraction (no LLM involved)."""

    def test_single_file_gzip_fallback(self):
        """A gzipped single .tex (not a tar.gz) decompresses to its content."""
        import gzip

        tex = r"\affiliation{Stanford University}"
        gz_bytes = gzip.compress(tex.encode("utf-8"))
        ext = AffiliationExtractor()
        results = ext.extract_tex_files(gz_bytes)
        assert len(results) == 1
        assert "Stanford University" in results[0]

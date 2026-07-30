"""Tests for LLM-based TLDR generation."""

from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock, patch

from alithia.models import ArxivPaper
from alithia.paperscout.tldr import TldrGenerator, generate_tldrs


def _make_paper(
    summary: str = "A paper about transformers.",
    arxiv_id: str = "2401.00001",
) -> ArxivPaper:
    return ArxivPaper(
        title="Test Paper",
        summary=summary,
        authors=["Alice"],
        arxiv_id=arxiv_id,
        pdf_url="https://arxiv.org/pdf/2401.00001",
        published_date=datetime(2024, 1, 1),
    )


def _fake_openai_response(text: str) -> MagicMock:
    """Build a fake openai chat.completions.create return value."""
    msg = MagicMock()
    msg.content = text
    choice = MagicMock()
    choice.message = msg
    resp = MagicMock()
    resp.choices = [choice]
    return resp


class TestTldrGenerator:
    """Tests for the TldrGenerator class."""

    def test_no_api_key_is_noop(self):
        """Without an api key, generate returns None and builds no client."""
        gen = TldrGenerator(api_key=None, api_base=None, model="qwen-turbo-latest")
        paper = _make_paper()
        assert gen.generate(paper) is None
        assert paper.tldr is None
        assert gen._client is None
        assert gen._disabled is True

    def test_no_abstract_skipped(self):
        """A paper with no summary is skipped (no client call)."""
        gen = TldrGenerator(api_key="fake", api_base=None, model="x")
        paper = _make_paper(summary="   ")
        with patch.object(gen, "_get_client") as mock_client:
            assert gen.generate(paper) is None
            # Client never consulted because there's nothing to summarize.
            mock_client.assert_not_called()
        assert paper.tldr is None

    def test_generate_populates_tldr(self):
        """A successful completion populates paper.tldr with the text."""
        gen = TldrGenerator(
            api_key="fake",
            api_base=None,
            model="qwen-turbo-latest",
            language="English",
            max_tokens=600,
        )
        paper = _make_paper()
        with patch("openai.OpenAI") as mock_openai:
            mock_client = MagicMock()
            mock_client.chat.completions.create = MagicMock(
                return_value=_fake_openai_response("A concise summary.")
            )
            mock_openai.return_value = mock_client
            result = gen.generate(paper)
        assert result == "A concise summary."
        assert paper.tldr == "A concise summary."
        # The request used the configured model.
        call_kwargs = mock_client.chat.completions.create.call_args.kwargs
        assert call_kwargs["model"] == "qwen-turbo-latest"
        # And a bounded max_tokens derived from the char budget.
        assert call_kwargs["max_tokens"] == 150  # 600 // 4

    def test_generate_strips_whitespace_from_response(self):
        """Leading/trailing whitespace in the completion is stripped."""
        gen = TldrGenerator(api_key="fake", api_base=None, model="x")
        paper = _make_paper()
        with patch("openai.OpenAI"):
            with patch.object(gen, "_get_client") as mock_get:
                mock_client = MagicMock()
                mock_client.chat.completions.create = MagicMock(
                    return_value=_fake_openai_response("  trimmed summary  \n")
                )
                mock_get.return_value = mock_client
                result = gen.generate(paper)
        assert result == "trimmed summary"
        assert paper.tldr == "trimmed summary"

    def test_generate_empty_response_returns_none(self):
        """An empty completion leaves tldr unset."""
        gen = TldrGenerator(api_key="fake", api_base=None, model="x")
        paper = _make_paper()
        with patch("openai.OpenAI"):
            with patch.object(gen, "_get_client") as mock_get:
                mock_client = MagicMock()
                mock_client.chat.completions.create = MagicMock(
                    return_value=_fake_openai_response("")
                )
                mock_get.return_value = mock_client
                assert gen.generate(paper) is None
        assert paper.tldr is None

    def test_generate_api_error_returns_none(self):
        """An API exception is caught; tldr stays None (graceful fallback)."""
        gen = TldrGenerator(api_key="fake", api_base=None, model="x")
        paper = _make_paper()
        with patch("openai.OpenAI"):
            with patch.object(gen, "_get_client") as mock_get:
                mock_client = MagicMock()
                mock_client.chat.completions.create = MagicMock(
                    side_effect=RuntimeError("rate limited")
                )
                mock_get.return_value = mock_client
                assert gen.generate(paper) is None
        assert paper.tldr is None

    def test_generate_skips_paper_with_existing_tldr(self):
        """A paper that already has a tldr is not re-summarized."""
        gen = TldrGenerator(api_key="fake", api_base=None, model="x")
        paper = _make_paper()
        paper.tldr = "Existing TLDR."
        with patch.object(gen, "_get_client") as mock_client:
            assert gen.generate(paper) == "Existing TLDR."
            mock_client.assert_not_called()

    def test_generate_papers_counts_enriched(self):
        """generate_papers returns the count of papers enriched."""
        gen = TldrGenerator(api_key="fake", api_base=None, model="x")
        papers = [_make_paper(arxiv_id=f"2401.0000{i}") for i in range(3)]
        papers[1].tldr = "Already set."  # should be skipped, not counted
        with patch("openai.OpenAI"):
            with patch.object(gen, "_get_client") as mock_get:
                mock_client = MagicMock()
                mock_client.chat.completions.create = MagicMock(
                    return_value=_fake_openai_response("Generated.")
                )
                mock_get.return_value = mock_client
                count = gen.generate_papers(papers)
        # 2 newly generated (papers[0] and papers[2]); papers[1] skipped.
        assert count == 2
        assert papers[0].tldr == "Generated."
        assert papers[1].tldr == "Already set."
        assert papers[2].tldr == "Generated."

    def test_generate_papers_empty_list(self):
        gen = TldrGenerator(api_key="fake", api_base=None, model="x")
        assert gen.generate_papers([]) == 0

    def test_token_cap_bounds(self):
        """max_tokens char-budget translates to a bounded token cap."""
        # Tiny budget floors at _MIN_TOKENS.
        gen = TldrGenerator(api_key="fake", api_base=None, model="x", max_tokens=10)
        assert gen._token_cap() >= 32
        # Huge budget ceilings at _MAX_TOKENS.
        gen = TldrGenerator(api_key="fake", api_base=None, model="x", max_tokens=10_000)
        assert gen._token_cap() <= 400

    def test_api_base_passed_to_client(self):
        """When api_base is set, it's passed as base_url to the client."""
        gen = TldrGenerator(
            api_key="fake",
            api_base="https://dashscope.example.com/v1",
            model="qwen-turbo-latest",
        )
        paper = _make_paper()
        with patch("openai.OpenAI") as mock_openai:
            mock_client = MagicMock()
            mock_client.chat.completions.create = MagicMock(
                return_value=_fake_openai_response("ok")
            )
            mock_openai.return_value = mock_client
            gen.generate(paper)
        call_kwargs = mock_openai.call_args.kwargs
        assert call_kwargs["base_url"] == "https://dashscope.example.com/v1"
        assert call_kwargs["api_key"] == "fake"

    def test_prompt_includes_title_and_abstract(self):
        """The user message carries the paper's title and abstract."""
        gen = TldrGenerator(api_key="fake", api_base=None, model="x")
        paper = _make_paper(summary="A unique abstract phrase about cats.")
        with patch("openai.OpenAI"):
            with patch.object(gen, "_get_client") as mock_get:
                mock_client = MagicMock()
                mock_client.chat.completions.create = MagicMock(
                    return_value=_fake_openai_response("ok")
                )
                mock_get.return_value = mock_client
                gen.generate(paper)
        messages = mock_client.chat.completions.create.call_args.kwargs["messages"]
        user_msg = next(m["content"] for m in messages if m["role"] == "user")
        assert "Test Paper" in user_msg
        assert "A unique abstract phrase about cats." in user_msg


class TestGenerateTldrsConvenience:
    """Tests for the module-level generate_tldrs convenience function."""

    def test_no_api_key_config_returns_zero(self):
        """A config with no llm_api_key yields 0 enriched, no client built."""
        config = MagicMock()
        config.llm_api_key = None
        config.llm_api_base = None
        config.llm_model = "qwen-turbo-latest"
        config.tldr_language = "English"
        config.tldr_max_tokens = 600
        paper = _make_paper()
        assert generate_tldrs([paper], config) == 0
        assert paper.tldr is None

    def test_threads_config_fields(self):
        """Config fields reach the underlying client call."""
        config = MagicMock()
        config.llm_api_key = "fake"
        config.llm_api_base = "https://example.com/v1"
        config.llm_model = "my-model"
        config.tldr_language = "French"
        config.tldr_max_tokens = 400
        paper = _make_paper()
        with patch("openai.OpenAI") as mock_openai:
            mock_client = MagicMock()
            mock_client.chat.completions.create = MagicMock(
                return_value=_fake_openai_response("résumé")
            )
            mock_openai.return_value = mock_client
            count = generate_tldrs([paper], config)
        assert count == 1
        assert paper.tldr == "résumé"
        kwargs = mock_client.chat.completions.create.call_args.kwargs
        assert kwargs["model"] == "my-model"

"""Tests for LLM-based affiliation extraction."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from alithia_agent.paperscout.affiliation_llm import AffiliationLLMExtractor


def _fake_openai_response(text: str) -> MagicMock:
    """Build a fake openai chat.completions.create return value."""
    msg = MagicMock()
    msg.content = text
    choice = MagicMock()
    choice.message = msg
    resp = MagicMock()
    resp.choices = [choice]
    return resp


def _make_extractor() -> AffiliationLLMExtractor:
    return AffiliationLLMExtractor(
        api_key="fake-key",
        api_base="https://dashscope.example.com/compatible-mode/v1",
        model="qwen-turbo-latest",
    )


class TestClientConstruction:
    def test_no_api_key_is_noop(self):
        """Without a key the client is never built and extraction is empty."""
        ext = AffiliationLLMExtractor(api_key=None, api_base=None, model="x")
        assert ext._get_client() is None
        assert ext._disabled is True
        assert ext.extract_batch([("2401.00001", r"\author{X}")]) == {}

    def test_api_base_passed_to_client(self):
        """The configured base_url is forwarded to OpenAI()."""
        ext = _make_extractor()
        with patch("openai.OpenAI") as mock_openai:
            mock_client = MagicMock()
            mock_client.chat.completions.create.return_value = _fake_openai_response("[]")
            mock_openai.return_value = mock_client

            ext.extract_batch([("2401.00001", r"\author{X}")])

            _, kwargs = mock_openai.call_args
            assert kwargs["api_key"] == "fake-key"
            assert kwargs["base_url"] == "https://dashscope.example.com/compatible-mode/v1"
            assert kwargs["timeout"] == 120.0


class TestResponseParsing:
    def test_json_array_mapped_by_arxiv_id(self):
        ext = _make_extractor()
        payload = (
            '[{"arxiv_id": "2401.00001", "affiliations": ["OpenAI"]}, '
            '{"arxiv_id": "2401.00002", "affiliations": ["Stanford University"]}]'
        )
        with patch("openai.OpenAI") as mock_openai:
            mock_client = MagicMock()
            mock_client.chat.completions.create.return_value = _fake_openai_response(payload)
            mock_openai.return_value = mock_client

            result = ext.extract_batch([("2401.00001", "tex1"), ("2401.00002", "tex2")])

        assert result["2401.00001"] == ["OpenAI"]
        assert result["2401.00002"] == ["Stanford University"]

    def test_markdown_fence_stripped(self):
        """A ```json ... ``` fenced response still parses."""
        ext = _make_extractor()
        payload = '```json\n[{"arxiv_id": "2401.00001", "affiliations": ["MIT"]}]\n```'
        with patch("openai.OpenAI") as mock_openai:
            mock_client = MagicMock()
            mock_client.chat.completions.create.return_value = _fake_openai_response(payload)
            mock_openai.return_value = mock_client

            result = ext.extract_batch([("2401.00001", "tex")])

        assert result["2401.00001"] == ["MIT"]

    def test_non_json_response_returns_empty(self):
        """If the model returns prose instead of JSON, no affiliations."""
        ext = _make_extractor()
        with patch("openai.OpenAI") as mock_openai:
            mock_client = MagicMock()
            mock_client.chat.completions.create.return_value = _fake_openai_response(
                "Sorry, I cannot help with that."
            )
            mock_openai.return_value = mock_client

            result = ext.extract_batch([("2401.00001", "tex")])

        assert result == {}
        assert mock_client.chat.completions.create.call_count == 2

    def test_partial_garbage_recovers_array_span(self):
        """Leading prose + trailing JSON array is recovered via the [...] fallback."""
        ext = _make_extractor()
        payload = (
            "Here are the affiliations:\n"
            '[{"arxiv_id": "2401.00001", "affiliations": ["Google Brain"]}]'
        )
        with patch("openai.OpenAI") as mock_openai:
            mock_client = MagicMock()
            mock_client.chat.completions.create.return_value = _fake_openai_response(payload)
            mock_openai.return_value = mock_client

            result = ext.extract_batch([("2401.00001", "tex")])

        assert result["2401.00001"] == ["Google Brain"]

    def test_arxiv_id_without_version_suffix(self):
        """Model ids without the vN suffix map back to the input arxiv_id."""
        ext = _make_extractor()
        payload = '[{"arxiv_id": "1706.03762", "affiliations": ["Google Brain"]}]'
        with patch("openai.OpenAI") as mock_openai:
            mock_client = MagicMock()
            mock_client.chat.completions.create.return_value = _fake_openai_response(payload)
            mock_openai.return_value = mock_client

            result = ext.extract_batch([("1706.03762v1", "tex")])

        assert result["1706.03762v1"] == ["Google Brain"]


class TestNormalization:
    def test_dedup_case_insensitive(self):
        ext = _make_extractor()
        payload = (
            '[{"arxiv_id": "2401.00001", "affiliations": '
            '["Google Brain", "google brain", "GOOGLE BRAIN"]}]'
        )
        with patch("openai.OpenAI") as mock_openai:
            mock_client = MagicMock()
            mock_client.chat.completions.create.return_value = _fake_openai_response(payload)
            mock_openai.return_value = mock_client

            result = ext.extract_batch([("2401.00001", "tex")])

        assert result["2401.00001"] == ["Google Brain"]

    def test_cap_at_ten(self):
        import json as _json

        ext = _make_extractor()
        affs = [f"University number {i}" for i in range(15)]
        payload = _json.dumps([{"arxiv_id": "2401.00001", "affiliations": affs}])
        with patch("openai.OpenAI") as mock_openai:
            mock_client = MagicMock()
            mock_client.chat.completions.create.return_value = _fake_openai_response(payload)
            mock_openai.return_value = mock_client

            result = ext.extract_batch([("2401.00001", "tex")])

        assert len(result["2401.00001"]) == 10

    def test_strips_and_drops_empty(self):
        ext = _make_extractor()
        payload = (
            '[{"arxiv_id": "2401.00001", "affiliations": ["  Stanford University  ", "", "   "]}]'
        )
        with patch("openai.OpenAI") as mock_openai:
            mock_client = MagicMock()
            mock_client.chat.completions.create.return_value = _fake_openai_response(payload)
            mock_openai.return_value = mock_client

            result = ext.extract_batch([("2401.00001", "tex")])

        assert result["2401.00001"] == ["Stanford University"]


class TestBatching:
    def test_many_papers_split_into_multiple_requests(self):
        """More than _BATCH_PAPERS triggers >1 LLM call; results merge."""
        from alithia_agent.paperscout.affiliation_llm import _BATCH_PAPERS

        ext = _make_extractor()
        n = _BATCH_PAPERS + 3
        papers = [(f"2401.{i:05d}", f"tex{i}") for i in range(1, n + 1)]

        call_count = {"n": 0}

        def fake_create(*args, **kwargs):
            import json as _json
            import re

            call_count["n"] += 1
            # Echo back whichever ids are in this batch's user message.
            user_msg = kwargs["messages"][1]["content"]
            ids = [m.group(1) for m in re.finditer(r"### arxiv_id: (\S+)", user_msg)]
            arr = [{"arxiv_id": i, "affiliations": [f"Lab-{i}"]} for i in ids]
            return _fake_openai_response(_json.dumps(arr))

        with patch("openai.OpenAI") as mock_openai:
            mock_client = MagicMock()
            mock_client.chat.completions.create.side_effect = fake_create
            mock_openai.return_value = mock_client

            result = ext.extract_batch(papers)

        assert call_count["n"] == 2  # ceil(n / batch) = 2
        assert len(result) == n
        assert result["2401.00001"] == ["Lab-2401.00001"]

    def test_empty_input_returns_empty(self):
        ext = _make_extractor()
        assert ext.extract_batch([]) == {}


class TestApiErrors:
    def test_request_exception_returns_empty(self):
        ext = _make_extractor()
        with patch("openai.OpenAI") as mock_openai:
            mock_client = MagicMock()
            mock_client.chat.completions.create.side_effect = RuntimeError("boom")
            mock_openai.return_value = mock_client

            result = ext.extract_batch([("2401.00001", "tex")])

        assert result == {}
        assert mock_client.chat.completions.create.call_count == 2

    def test_retry_succeeds_on_second_attempt(self):
        ext = _make_extractor()
        payload = '[{"arxiv_id": "2401.00001", "affiliations": ["MIT"]}]'
        with patch("openai.OpenAI") as mock_openai:
            mock_client = MagicMock()
            mock_client.chat.completions.create.side_effect = [
                RuntimeError("transient"),
                _fake_openai_response(payload),
            ]
            mock_openai.return_value = mock_client

            result = ext.extract_batch([("2401.00001", "tex")])

        assert result["2401.00001"] == ["MIT"]
        assert mock_client.chat.completions.create.call_count == 2

    def test_empty_content_returns_empty(self):
        ext = _make_extractor()
        with patch("openai.OpenAI") as mock_openai:
            mock_client = MagicMock()
            mock_client.chat.completions.create.return_value = _fake_openai_response("")
            mock_openai.return_value = mock_client

            result = ext.extract_batch([("2401.00001", "tex")])

        assert result == {}
        assert mock_client.chat.completions.create.call_count == 2


class TestSourceTrimming:
    def test_long_source_truncated(self):
        """A source over the cap is trimmed to the cap length."""
        long_tex = "x" * 10_000
        trimmed = AffiliationLLMExtractor._trim_source(long_tex)
        assert len(trimmed) <= 6000

    def test_short_source_unchanged(self):
        short_tex = r"\author{OpenAI}"
        assert AffiliationLLMExtractor._trim_source(short_tex) == short_tex

    def test_empty_source(self):
        assert AffiliationLLMExtractor._trim_source("") == ""

    def test_late_author_block_preserved(self):
        """Author markup deep in the file is kept, not cut by a head-only slice."""
        from pathlib import Path

        tex = (
            Path(__file__)
            .parent.joinpath("fixtures", "attention_1706.03762.tex")
            .read_text(encoding="utf-8")
        )
        trimmed = AffiliationLLMExtractor._trim_source(tex)
        assert r"\author{" in trimmed
        assert "Google Brain" in trimmed
        assert len(trimmed) <= 6000

    def test_all_fixtures_retain_author_block(self):
        """Every real-paper fixture keeps its author/affiliation region."""
        from pathlib import Path

        fixtures_dir = Path(__file__).parent / "fixtures"
        for path in sorted(fixtures_dir.glob("*.tex")):
            tex = path.read_text(encoding="utf-8")
            trimmed = AffiliationLLMExtractor._trim_source(tex)
            assert r"\author" in trimmed, f"{path.name}: author block missing after trim"
            assert len(trimmed) <= 6000, f"{path.name}: trim exceeded cap"


class TestFixturePrompts:
    """Real .tex fixtures are fed to the LLM path (client mocked)."""

    def test_attention_fixture_in_user_message(self):
        from pathlib import Path

        tex = (
            Path(__file__)
            .parent.joinpath("fixtures", "attention_1706.03762.tex")
            .read_text(encoding="utf-8")
        )
        ext = _make_extractor()
        captured: dict[str, str] = {}

        def fake_create(*args, **kwargs):
            captured["user"] = kwargs["messages"][1]["content"]
            return _fake_openai_response(
                '[{"arxiv_id": "1706.03762", "affiliations": ["Google Brain"]}]'
            )

        with patch("openai.OpenAI") as mock_openai:
            mock_client = MagicMock()
            mock_client.chat.completions.create.side_effect = fake_create
            mock_openai.return_value = mock_client

            result = ext.extract_batch([("1706.03762", tex)])

        assert "1706.03762" in captured["user"]
        assert r"\author{" in captured["user"]
        assert result["1706.03762"] == ["Google Brain"]

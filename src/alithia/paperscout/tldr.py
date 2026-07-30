"""LLM-based TLDR generation for PaperScout papers.

Generates a short plain-text TLDR for each paper's abstract via an
OpenAI-compatible chat completion, populating ``ArxivPaper.tldr``. The email
renderer prefers ``tldr`` over the raw ``summary`` (see
``email._get_tldr``), so once populated the digest shows generated summaries
automatically.

Design notes:
- Uses a **sync** ``openai.OpenAI`` client because ``content_generation_node``
  is a sync LangGraph node (converting it to async would cascade into the
  graph runtime). Digests are small (≤ ``max_papers``), so sequential calls
  are acceptable.
- Built from ``PaperScoutRuntimeConfig``'s ``llm_api_key`` / ``llm_api_base``
  / ``llm_model`` fields, which default to a qwen/DashScope-compatible
  endpoint. ``openai`` is a declared dependency.
- **Graceful fallback**: if no API key is configured, or any call fails, the
  paper's ``tldr`` is left unset and the renderer falls back to a truncated
  ``summary``. TLDR generation never breaks the digest.
"""

from __future__ import annotations

import logging
from typing import Any

from alithia.models import ArxivPaper

logger = logging.getLogger(__name__)

# Approximate chars-per-token for translating the char-budget config
# (``tldr_max_tokens``, despite the name used as a char budget elsewhere) into
# a token cap for the completion request. Conservative to bound cost.
_CHARS_PER_TOKEN = 4
# Hard floor/ceiling on the token cap so a misconfigured max_tokens can't
# produce empty or runaway completions.
_MIN_TOKENS = 32
_MAX_TOKENS = 400

# System prompt instructing the model to produce a concise plain-text TLDR.
_SYSTEM_PROMPT = (
    "You write concise paper TLDRs for a research digest. Given a paper's "
    "title and abstract, write a one-to-two sentence plain-text summary of "
    "the key idea, in {language}. No preamble, no bullet points, no "
    "markdown. Output only the summary."
)


class TldrGenerator:
    """Generate LLM TLDRs for papers via an OpenAI-compatible endpoint.

    The OpenAI client is constructed lazily on first use so that instances
    built without an API key (or in environments without ``openai``
    installed) are still safe to construct and call — ``generate`` just
    returns ``None``.
    """

    def __init__(
        self,
        api_key: str | None,
        api_base: str | None,
        model: str,
        language: str = "English",
        max_tokens: int = 600,
    ) -> None:
        self._api_key = api_key
        self._api_base = api_base
        self._model = model
        self._language = language
        self._max_tokens = max_tokens
        self._client: Any | None = None  # constructed lazily
        self._disabled = False  # set True if construction/import fails

    def _get_client(self) -> Any | None:
        """Get or create the OpenAI client. Returns None if unavailable."""
        if self._disabled:
            return None
        if self._client is not None:
            return self._client
        if not self._api_key:
            logger.debug("TLDR generation disabled: no llm_api_key configured")
            self._disabled = True
            return None
        try:
            from openai import OpenAI

            kwargs: dict[str, Any] = {"api_key": self._api_key}
            if self._api_base:
                kwargs["base_url"] = self._api_base
            self._client = OpenAI(**kwargs)
        except ImportError:
            logger.warning("openai not installed, TLDR generation disabled")
            self._disabled = True
            return None
        except Exception as e:  # pragma: no cover - defensive
            logger.warning(f"Failed to construct OpenAI client, TLDR disabled: {e}")
            self._disabled = True
            return None
        return self._client

    def _token_cap(self) -> int:
        """Translate the char budget into a bounded token cap for the request."""
        cap = self._max_tokens // _CHARS_PER_TOKEN
        return max(_MIN_TOKENS, min(cap, _MAX_TOKENS))

    def _build_user_message(self, paper: ArxivPaper) -> str:
        title = paper.title.strip() or "(untitled)"
        abstract = (paper.summary or "").strip()
        return f"Title: {title}\n\nAbstract: {abstract}"

    def generate(self, paper: ArxivPaper) -> str | None:
        """Generate a TLDR for one paper.

        Returns the generated text, or ``None`` on any failure (in which case
        ``paper.tldr`` is left untouched so the renderer falls back to
        ``summary``).
        """
        if paper.tldr:  # already has one (e.g. from a prior run)
            return paper.tldr
        if not paper.summary or not paper.summary.strip():
            logger.debug(f"No abstract to summarize for {paper.arxiv_id}")
            return None

        client = self._get_client()
        if client is None:
            return None

        try:
            response = client.chat.completions.create(
                model=self._model,
                messages=[
                    {
                        "role": "system",
                        "content": _SYSTEM_PROMPT.format(language=self._language),
                    },
                    {"role": "user", "content": self._build_user_message(paper)},
                ],
                max_tokens=self._token_cap(),
                temperature=0.3,
            )
            text = response.choices[0].message.content
            if text:
                text = text.strip()
            if not text:
                return None
            paper.tldr = text
            return text
        except Exception as e:
            logger.warning(
                f"TLDR generation failed for {paper.arxiv_id}: {e}; falling back to summary"
            )
            return None

    def generate_papers(self, papers: list[ArxivPaper]) -> int:
        """Populate ``paper.tldr`` for each paper; return the count **newly**
        generated.

        Papers that already have a TLDR or have no abstract are skipped
        (and not counted). Failures on individual papers are logged and
        don't abort the batch.
        """
        if not papers:
            return 0
        enriched = 0
        for paper in papers:
            if paper.tldr:  # already has one — skip, don't count
                continue
            if self.generate(paper) is not None:
                enriched += 1
        logger.info(f"TLDR generation: {enriched}/{len(papers)} papers enriched")
        return enriched


def generate_tldrs(papers: list[ArxivPaper], config: Any) -> int:
    """Convenience: build a generator from a runtime config and enrich papers.

    ``config`` is a ``PaperScoutRuntimeConfig`` (or any object with
    ``llm_api_key``, ``llm_api_base``, ``llm_model``, ``tldr_language``,
    ``tldr_max_tokens`` attributes). Returns the count enriched. Safe to call
    with no API key configured (returns 0, no client built).
    """
    generator = TldrGenerator(
        api_key=getattr(config, "llm_api_key", None),
        api_base=getattr(config, "llm_api_base", None),
        model=getattr(config, "llm_model", "qwen-turbo-latest"),
        language=getattr(config, "tldr_language", "English"),
        max_tokens=getattr(config, "tldr_max_tokens", 600),
    )
    return generator.generate_papers(papers)


__all__ = ["TldrGenerator", "generate_tldrs"]

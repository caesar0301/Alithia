"""LLM-based author affiliation extraction for PaperScout papers.

Reads the ArXiv LaTeX source of each paper and asks an OpenAI-compatible
chat model to extract author affiliations. Many papers store affiliations in
ways no regex can robustly reach (Mistral/Mixtral bury them in ``%``
comments inside ``\\author{}``; ICML templates use
``\\icmlaffiliation{key}{Name}``; GPT-4 TR puts ``OpenAI`` inline inside
``\\author{...\\thanks{...}}``). A single LLM call over the concatenated
sources handles all of these and returns structured JSON mapped back to each
paper.

Design notes:
- Uses a **sync** ``openai.OpenAI`` client, mirroring ``tldr.py``. The
  PaperScout data-collection node is async, but it ``await``s the source
  fetch (httpx) and calls this extractor synchronously in between — the LLM
  call is a single batched request, so blocking briefly is acceptable.
- **Batched**: many papers' sources are packed into one request (capped at
  ``_BATCH_PAPERS`` per call) returning a JSON array, so N papers cost
  ``ceil(N / _BATCH_PAPERS)`` requests, not N.
- **Graceful fallback**: no API key, ``openai`` missing, non-JSON response,
  or any error → that paper (or all papers) get no affiliations. Extraction
  never breaks the digest; the renderer shows "Unknown Affiliation".
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

logger = logging.getLogger(__name__)

# Maximum papers packed into a single LLM request. Bounds prompt size and
# limits the blast radius of one bad response.
_BATCH_PAPERS = 8

# Per-paper source cap (chars). Affiliation markup lives in the header
# (\\author/\\affiliation/\\institute/\\icmlaffiliation near the top), so we
# keep the first chunk and drop the bulk body.
_MAX_TEX_CHARS = 6000

# Affiliation cap per paper (matches the legacy MAX_AFFILIATIONS).
_MAX_AFFILIATIONS = 10

# LaTeX commands that typically carry author/institution markup.
_AFFIL_CMD_RE = re.compile(
    r"\\(?:author|affiliation|institute|icmlaffiliation|institutename|thanks)\b",
    re.IGNORECASE,
)
# End of the author/preamble block where affiliations usually live.
_DOC_START_RE = re.compile(r"\\(?:begin\{document\}|maketitle)\b")

_SYSTEM_PROMPT = (
    "You extract author affiliations from LaTeX paper sources for a research "
    "digest. For each paper you are given its arXiv id and LaTeX source. "
    "Identify the institutions the authors are affiliated with (universities, "
    "company labs, institutes). Ignore author names, emails, URLs, funding "
    "acknowledgements and contribution notes. Read affiliations even when "
    "they appear inside LaTeX comments (% lines) or ICML \\icmlaffiliation "
    "mappings. Return ONLY a JSON array — no prose, no markdown fences — of "
    'objects: {"arxiv_id": "...", "affiliations": ["...", "..."]}. One '
    "object per input paper, even if its affiliations list is empty."
)


class AffiliationLLMExtractor:
    """Extract affiliations from LaTeX sources via an OpenAI-compatible LLM.

    The client is constructed lazily so an instance without an API key (or in
    an environment without ``openai``) is safe to build and call — extraction
    just returns nothing.
    """

    def __init__(
        self,
        api_key: str | None,
        api_base: str | None,
        model: str,
    ) -> None:
        self._api_key = api_key
        self._api_base = api_base
        self._model = model
        self._client: Any | None = None
        self._disabled = False

    def _get_client(self) -> Any | None:
        """Get or create the OpenAI client. Returns None if unavailable."""
        if self._disabled:
            return None
        if self._client is not None:
            return self._client
        if not self._api_key:
            logger.debug("Affiliation LLM disabled: no llm_api_key configured")
            self._disabled = True
            return None
        try:
            from openai import OpenAI

            kwargs: dict[str, Any] = {"api_key": self._api_key}
            if self._api_base:
                kwargs["base_url"] = self._api_base
            self._client = OpenAI(**kwargs)
        except ImportError:
            logger.warning("openai not installed, affiliation LLM disabled")
            self._disabled = True
            return None
        except Exception as e:  # pragma: no cover - defensive
            logger.warning(f"Failed to construct OpenAI client, affiliation LLM disabled: {e}")
            self._disabled = True
            return None
        return self._client

    def _build_user_message(self, papers_tex: list[tuple[str, str]]) -> str:
        """Pack multiple papers' sources into one user message."""
        parts: list[str] = []
        for arxiv_id, tex in papers_tex:
            snippet = self._trim_source(tex)
            parts.append(f"### arxiv_id: {arxiv_id}\n{snippet}")
        return (
            "Extract author affiliations from each of the following LaTeX "
            "sources. Return the JSON array now.\n\n" + "\n\n".join(parts)
        )

    @staticmethod
    def _trim_source(tex: str) -> str:
        """Keep the affiliation-bearing header of a .tex source.

        Real papers often place ``\\author{}`` far into the file (after long
        comment blocks or included chunks). A naive ``tex[:6000]`` cut misses
        them. We keep the author/preamble region (including ``%`` comment
        lines where some templates hide affiliations), any
        ``\\icmlaffiliation`` lines elsewhere, and the ``\\title`` line.
        """
        if not tex:
            return ""
        if len(tex) <= _MAX_TEX_CHARS:
            return tex

        lines = tex.splitlines(keepends=True)
        keep = [False] * len(lines)

        marker_indices = [
            i for i, line in enumerate(lines) if _AFFIL_CMD_RE.search(line)
        ]
        if not marker_indices:
            return tex[:_MAX_TEX_CHARS]

        first_marker = min(marker_indices)
        # Include a little context before the first marker (e.g. \\title).
        region_start = max(0, first_marker - 40)
        region_end = len(lines)
        for i in range(first_marker, len(lines)):
            if _DOC_START_RE.search(lines[i]):
                region_end = i + 1
                break

        for i in range(region_start, region_end):
            keep[i] = True

        # ICML-style mappings can live outside the author block.
        for i, line in enumerate(lines):
            if "\\icmlaffiliation" in line:
                for j in range(max(0, i - 2), min(len(lines), i + 3)):
                    keep[j] = True

        result = "".join(line for line, k in zip(lines, keep) if k)
        if not result.strip():
            return tex[:_MAX_TEX_CHARS]
        if len(result) > _MAX_TEX_CHARS:
            return result[:_MAX_TEX_CHARS]
        return result

    @staticmethod
    def _parse_response(text: str) -> list[dict[str, Any]]:
        """Parse the model's JSON-array response, tolerating junk.

        Returns a list of ``{"arxiv_id", "affiliations"}`` dicts. Any
        unrecoverable failure returns ``[]`` (caller maps missing ids to no
        affiliations).
        """
        if not text:
            return []
        text = text.strip()
        # Strip a leading ```json / ``` fence if the model added one.
        if text.startswith("```"):
            text = re.sub(r"^```[a-zA-Z]*\n?", "", text)
            text = re.sub(r"\n?```$", "", text).strip()
        # First try a direct parse.
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            # Fall back to the first balanced [...] span.
            m = re.search(r"\[.*\]", text, re.DOTALL)
            if not m:
                logger.warning("Affiliation LLM response was not JSON; got no array")
                return []
            try:
                data = json.loads(m.group(0))
            except json.JSONDecodeError:
                logger.warning("Affiliation LLM response JSON array could not be parsed")
                return []
        if not isinstance(data, list):
            logger.warning("Affiliation LLM response JSON was not an array")
            return []
        return data

    @staticmethod
    def _normalize_affiliations(raw: Any) -> list[str]:
        """Coerce a paper's raw affiliations value into a clean, deduped list."""
        if not isinstance(raw, list):
            return []
        seen: set[str] = set()
        out: list[str] = []
        for item in raw:
            if not isinstance(item, str):
                continue
            name = item.strip()
            if not name:
                continue
            key = name.lower()
            if key in seen:
                continue
            seen.add(key)
            out.append(name)
            if len(out) >= _MAX_AFFILIATIONS:
                break
        return out

    def _extract_one_batch(self, papers_tex: list[tuple[str, str]]) -> dict[str, list[str]]:
        """Run one LLM request over one batch; return {arxiv_id: [affs]}."""
        client = self._get_client()
        if client is None:
            return {}
        try:
            response = client.chat.completions.create(
                model=self._model,
                messages=[
                    {"role": "system", "content": _SYSTEM_PROMPT},
                    {"role": "user", "content": self._build_user_message(papers_tex)},
                ],
                temperature=0.0,
            )
            text = response.choices[0].message.content or ""
        except Exception as e:
            logger.warning(f"Affiliation LLM request failed: {e}")
            return {}

        results: dict[str, list[str]] = {}
        for entry in self._parse_response(text):
            if not isinstance(entry, dict):
                continue
            arxiv_id = entry.get("arxiv_id")
            if not isinstance(arxiv_id, str):
                continue
            arxiv_id = arxiv_id.strip()
            if not arxiv_id:
                continue
            results[arxiv_id] = self._normalize_affiliations(entry.get("affiliations"))
        return results

    def extract_batch(self, papers_tex: list[tuple[str, str]]) -> dict[str, list[str]]:
        """Extract affiliations for many papers, batching into few requests.

        Args:
            papers_tex: list of ``(arxiv_id, latex_source)``.

        Returns:
            Mapping ``{arxiv_id: [affiliation, ...]}``. Papers whose id the
            model didn't return (or that landed in a failed batch) are simply
            absent — callers treat absence as "no affiliations".
        """
        if not papers_tex:
            return {}
        merged: dict[str, list[str]] = {}
        for i in range(0, len(papers_tex), _BATCH_PAPERS):
            batch = papers_tex[i : i + _BATCH_PAPERS]
            merged.update(self._extract_one_batch(batch))
        logger.info(
            f"Affiliation LLM: {len(merged)}/{len(papers_tex)} papers got affiliations"
        )
        return merged


__all__ = ["AffiliationLLMExtractor"]

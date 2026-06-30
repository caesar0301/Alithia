"""Extract author affiliations from ArXiv LaTeX source files.

Downloads each paper's source tarball from ArXiv, extracts the ``.tex``
files, and asks an LLM to read the LaTeX and return author affiliations.
Parsing is delegated to :mod:`affiliation_llm` because real-world LaTeX
stores affiliations in too many forms for a regex to reach reliably
(comment-hidden blocks, ICML ``\\icmlaffiliation`` mappings, inline
``\\author{Org\\thanks{...}}``). The LLM packs many papers into one batched
JSON request; see :class:`AffiliationLLMExtractor`.

This module owns the **network and source-extraction layer** only:

- :meth:`AffiliationExtractor.fetch_source` — download the source tarball.
- :meth:`AffiliationExtractor.extract_tex_files` — unpack ``.tex`` contents
  (``.tar.gz`` or single gzipped ``.tex``).
- :meth:`AffiliationExtractor.enrich_papers` — orchestrate fetch + LLM
  extraction for a batch of papers, populating ``paper.affiliations``.

Falls back gracefully: PDF-only source, a fetch error, a missing LLM API
key, or a failed LLM call all leave ``affiliations`` unset, which the email
renderer shows as "Unknown Affiliation". Extraction never breaks the digest.
"""

from __future__ import annotations

import logging
import tarfile
import tempfile
from pathlib import Path
from typing import Any

from alithia_agent.models import ArxivPaper
from alithia_agent.paperscout.affiliation_llm import AffiliationLLMExtractor

logger = logging.getLogger(__name__)

# ArXiv source URL pattern
ARXIV_SOURCE_URL = "https://arxiv.org/src/{arxiv_id}"

# Rate limiting to respect ArXiv
ARXIV_RATE_LIMIT_SECONDS = 0.5

# Maximum affiliations kept per paper.
MAX_AFFILIATIONS = 10

# Number of papers whose sources are fetched concurrently per batch, to
# respect ArXiv rate limits before the batched LLM call.
FETCH_BATCH_SIZE = 5


class AffiliationExtractor:
    """Fetch ArXiv LaTeX sources and extract affiliations via an LLM.

    The HTTP client is created lazily. The LLM extractor is constructed from
    ``llm_config`` (``{api_key, api_base, model}``); if omitted or without an
    API key, sources are still fetched but no affiliations are extracted.
    """

    def __init__(
        self,
        http_client: Any | None = None,
        llm_config: dict[str, Any] | None = None,
    ) -> None:
        """Initialize affiliation extractor.

        Args:
            http_client: Optional httpx.AsyncClient for ArXiv source fetches.
                        If None, creates its own client.
            llm_config: Optional ``{"api_key", "api_base", "model"}`` for the
                        LLM affiliation extractor. When None or without an
                        ``api_key``, affiliation extraction is a no-op
                        (sources are still fetched).
        """
        self._client = http_client
        self._owns_client = http_client is None
        cfg = llm_config or {}
        self._llm = AffiliationLLMExtractor(
            api_key=cfg.get("api_key"),
            api_base=cfg.get("api_base"),
            model=cfg.get("model", "qwen-turbo-latest"),
        )

    async def _get_client(self) -> Any:
        """Get or create HTTP client."""
        if self._client is None:
            try:
                import httpx

                self._client = httpx.AsyncClient(timeout=30.0)
            except ImportError:
                logger.warning("httpx not installed, affiliation extraction disabled")
                return None
        return self._client

    async def close(self) -> None:
        """Close HTTP client if we own it."""
        if self._owns_client and self._client:
            await self._client.aclose()
            self._client = None

    async def fetch_source(self, arxiv_id: str) -> bytes | None:
        """Fetch source tarball from ArXiv.

        Args:
            arxiv_id: ArXiv paper ID (e.g., "2301.07041v1")

        Returns:
            Source tarball bytes, or None if unavailable.
        """
        client = await self._get_client()
        if client is None:
            return None

        url = ARXIV_SOURCE_URL.format(arxiv_id=arxiv_id)

        try:
            response = await client.get(url)
            if response.status_code == 200:
                content_type = response.headers.get("content-type", "")

                # Check if it's a tarball (LaTeX source)
                if "application/gzip" in content_type or "application/x-tar" in content_type:
                    return response.content

                # If it's PDF, no LaTeX source available
                if "application/pdf" in content_type:
                    logger.debug(f"ArXiv {arxiv_id} has PDF-only source, no LaTeX")
                    return None

                # Unknown format - try to process anyway
                return response.content

            elif response.status_code == 404:
                logger.debug(f"ArXiv source not found for {arxiv_id}")
                return None
            else:
                logger.warning(f"ArXiv source fetch error: {response.status_code} for {arxiv_id}")
                return None

        except Exception as e:
            logger.error(f"Error fetching ArXiv source for {arxiv_id}: {e}")
            return None

    def extract_tex_files(self, tarball_bytes: bytes) -> list[str]:
        """Extract .tex file contents from tarball.

        Handles two ArXiv source formats:
        - ``.tar.gz`` of multiple files (the common case).
        - A single gzipped ``.tex`` file (older submissions; ArXiv serves
          these as ``application/gzip`` but they are NOT tar archives, so
          ``tarfile.open`` raises ``ReadError``). We fall back to
          ``gzip``-decompressing the whole blob as one .tex file.

        Args:
            tarball_bytes: Raw tarball data

        Returns:
            List of .tex file contents as strings.
        """
        tex_contents: list[str] = []

        with tempfile.NamedTemporaryFile(suffix=".tar.gz", delete=False) as tmp:
            tmp.write(tarball_bytes)
            tmp_path = tmp.name

        try:
            with tarfile.open(tmp_path, "r:gz") as tar:
                for member in tar.getmembers():
                    if member.isfile() and member.name.endswith(".tex"):
                        try:
                            f = tar.extractfile(member)
                            if f:
                                content = f.read().decode("utf-8", errors="ignore")
                                tex_contents.append(content)
                        except Exception as e:
                            logger.debug(f"Error reading {member.name}: {e}")

        except tarfile.TarError as e:
            # Not a tar archive — likely a single gzipped .tex file.
            logger.debug(f"Not a tar.gz ({e}); trying single-file gzip fallback")
            tex_contents = self._extract_single_gzip_tex(tmp_path)
        except Exception as e:
            logger.error(f"Unexpected error extracting tex files: {e}")
        finally:
            Path(tmp_path).unlink(missing_ok=True)

        return tex_contents

    @staticmethod
    def _extract_single_gzip_tex(path: str) -> list[str]:
        """Decompress a single gzipped .tex file (ArXiv's non-tar source form)."""
        import gzip

        try:
            with gzip.open(path, "rt", encoding="utf-8", errors="ignore") as f:
                return [f.read()]
        except Exception as e:
            logger.warning(f"Single-file gzip fallback failed: {e}")
            return []

    async def _fetch_source_for(self, paper: ArxivPaper) -> tuple[str, str] | None:
        """Fetch and flatten one paper's .tex sources into ``(arxiv_id, tex)``.

        Returns None when there is no usable LaTeX source (PDF-only, 404,
        fetch error, or no .tex files inside).
        """
        try:
            tarball = await self.fetch_source(paper.arxiv_id)
            if tarball is None:
                return None
            tex_files = self.extract_tex_files(tarball)
            if not tex_files:
                logger.debug(f"No .tex files found for {paper.arxiv_id}")
                return None
            # Concatenate all .tex files (the affiliation markup may live in
            # a separate authors.tex; the LLM trim keeps the prompt bounded).
            return paper.arxiv_id, "\n".join(tex_files)
        except Exception as e:
            logger.warning(f"Error fetching source for {paper.arxiv_id}: {e}")
            return None

    async def enrich_paper(self, paper: ArxivPaper) -> ArxivPaper:
        """Enrich a single paper with affiliations.

        Args:
            paper: ArxivPaper to enrich

        Returns:
            Same paper with affiliations field populated (if found).
        """
        if paper.affiliations:  # Already has affiliations
            return paper

        result = await self._fetch_source_for(paper)
        if result is None:
            return paper
        _, tex = result

        mapping = self._llm.extract_batch([(paper.arxiv_id, tex)])
        affs = mapping.get(paper.arxiv_id, [])
        if affs:
            paper.affiliations = affs[:MAX_AFFILIATIONS]
        return paper

    async def enrich_papers(
        self,
        papers: list[ArxivPaper],
        batch_size: int = FETCH_BATCH_SIZE,
    ) -> list[ArxivPaper]:
        """Enrich multiple papers with affiliations.

        Fetches each paper's LaTeX source (rate-limited batches), then issues
        a single batched LLM request per fetch batch to extract affiliations.

        Args:
            papers: List of ArxivPaper objects to enrich
            batch_size: Number of papers whose sources are fetched concurrently

        Returns:
            List of enriched papers (same objects, modified in place).
        """
        if not papers:
            return papers

        import asyncio

        logger.info(f"Extracting affiliations for {len(papers)} papers")

        enriched_count = 0

        for i in range(0, len(papers), batch_size):
            batch = papers[i : i + batch_size]
            need = [p for p in batch if not p.affiliations]
            if not need:
                continue

            # Fetch sources concurrently (rate-limited by batch_size).
            fetch_results = await asyncio.gather(
                *(self._fetch_source_for(p) for p in need)
            )
            papers_tex = [r for r in fetch_results if r is not None]

            # One batched LLM request for everything we fetched this round.
            if papers_tex:
                mapping = self._llm.extract_batch(papers_tex)
                for paper in need:
                    affs = mapping.get(paper.arxiv_id, [])
                    if affs:
                        paper.affiliations = affs[:MAX_AFFILIATIONS]

            for paper in batch:
                if paper.affiliations:
                    enriched_count += 1

            if i + batch_size < len(papers):
                await asyncio.sleep(ARXIV_RATE_LIMIT_SECONDS)

            logger.info(
                f"Affiliation extraction progress: {enriched_count}/{len(papers)} "
                f"(batch {i // batch_size + 1})"
            )

        logger.info(
            f"Affiliation extraction complete: {enriched_count}/{len(papers)} papers enriched"
        )

        return papers


async def enrich_papers_with_affiliations(papers: list[ArxivPaper]) -> list[ArxivPaper]:
    """Async function to enrich papers with affiliations.

    Convenience wrapper with no LLM config: sources are fetched but
    affiliations are left unset (no API key). Prefer constructing an
    :class:`AffiliationExtractor` with ``llm_config`` for real extraction.

    Args:
        papers: List of ArxivPaper objects to enrich

    Returns:
        List of enriched papers.
    """
    extractor = AffiliationExtractor()
    try:
        return await extractor.enrich_papers(papers)
    finally:
        await extractor.close()


__all__ = ["AffiliationExtractor", "enrich_papers_with_affiliations"]

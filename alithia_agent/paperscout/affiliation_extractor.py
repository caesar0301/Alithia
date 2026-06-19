"""Extract author affiliations from ArXiv LaTeX source files.

Downloads source tarball from ArXiv and parses .tex files to extract
institution affiliations. Falls back gracefully if source is PDF-only or
parsing fails.
"""

from __future__ import annotations

import logging
import re
import tarfile
import tempfile
from pathlib import Path
from typing import Any

from alithia_agent.models import ArxivPaper

logger = logging.getLogger(__name__)

# ArXiv source URL pattern
ARXIV_SOURCE_URL = "https://arxiv.org/src/{arxiv_id}"

# Rate limiting to respect ArXiv
ARXIV_RATE_LIMIT_SECONDS = 0.5

# Common LaTeX affiliation patterns
# LaTeX commands like \affiliation are single backslash in the actual string
# Regex: \\affiliation matches \affiliation in string (single backslash)
AFFILIATION_PATTERNS = [
    # Explicit affiliation command (most common)
    r"\\affiliation\{([^}]+)\}",
    r"\\affil\{([^}]+)\}",
    # ACM style with optional arg: \affiliation[...]{...}
    r"\\affiliation(?:\[[^\]]*\])?\{([^}]+)\}",
    # Institute command
    r"\\institute\{([^}]+)\}",
    r"\\institut\{([^}]+)\}",
    # Institution command
    r"\\institution\{([^}]+)\}",
]

# Author block pattern - LaTeX \author{...}
# \author in string (single backslash) is matched by \\author in regex
AUTHOR_BLOCK_PATTERN = re.compile(r"\\author\{(.+?)\}", re.DOTALL | re.IGNORECASE)

# Common institution name cleanup patterns
INSTITUTION_CLEANUP = [
    (r"\\texttt\{[^}]+\}", ""),  # Remove emails wrapped in \texttt{}
    (r"\\footnote(?:mark|text)?(?:\[[^\]]+\])?\{[^}]+\}", ""),  # Remove footnotes
    (r"\\thanks\{[^}]+\}", ""),  # Remove thanks
    (r"\\hspace\{[^}]+\}", ""),  # Remove spacing
    (r"\{[^}]*\}", ""),  # Remove remaining braces content
    (r"\\\\", " "),  # LaTeX line breaks -> space
    (r"\s+", " "),  # Normalize whitespace
    (r"^\s+|\s+$", ""),  # Strip leading/trailing
]


class AffiliationExtractor:
    """Extract affiliations from ArXiv LaTeX source files."""

    def __init__(self, http_client: Any | None = None):
        """Initialize affiliation extractor.

        Args:
            http_client: Optional httpx.AsyncClient for HTTP requests.
                        If None, creates its own client.
        """
        self._client = http_client
        self._owns_client = http_client is None

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

        Args:
            tarball_bytes: Raw tarball data

        Returns:
            List of .tex file contents as strings.
        """
        tex_contents: list[str] = []

        try:
            with tempfile.NamedTemporaryFile(suffix=".tar.gz", delete=False) as tmp:
                tmp.write(tarball_bytes)
                tmp_path = tmp.name

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

            # Clean up temp file
            Path(tmp_path).unlink(missing_ok=True)

        except tarfile.TarError as e:
            logger.warning(f"Error extracting tarball: {e}")
        except Exception as e:
            logger.error(f"Unexpected error extracting tex files: {e}")

        return tex_contents

    def parse_affiliations_from_tex(self, tex_content: str) -> list[str]:
        """Parse affiliations from LaTeX content.

        Handles multiple LaTeX author/affiliation formats:
        - NIPS/NeurIPS: \\author{...} with inline institutions
        - ACM: \\affiliation{...}
        - IEEE: \\institute{...}
        - Custom conference styles

        Args:
            tex_content: Content of a .tex file

        Returns:
            List of institution names.
        """
        affiliations: list[str] = []

        # Try explicit affiliation commands first (most reliable)
        for pattern in AFFILIATION_PATTERNS:
            matches = re.findall(pattern, tex_content, re.IGNORECASE)
            for match in matches:
                if isinstance(match, tuple):
                    # Take first non-empty element
                    for part in match:
                        if part and not self._is_email(part):
                            cleaned = self._clean_institution(part)
                            if cleaned and len(cleaned) > 2:
                                affiliations.append(cleaned)
                            break
                elif match and not self._is_email(match):
                    cleaned = self._clean_institution(match)
                    if cleaned and len(cleaned) > 2:
                        affiliations.append(cleaned)

        # Try author block parsing (NIPS/NeurIPS inline style)
        author_blocks = AUTHOR_BLOCK_PATTERN.findall(tex_content)
        for block in author_blocks:
            block_affiliations = self._parse_author_block(block)
            affiliations.extend(block_affiliations)

        # Deduplicate while preserving order
        seen = set()
        unique = []
        for aff in affiliations:
            normalized = aff.lower().strip()
            if normalized not in seen and len(normalized) > 2:
                seen.add(normalized)
                unique.append(aff)

        return unique[:10]  # Limit to 10 institutions

    def _parse_author_block(self, block: str) -> list[str]:
        """Parse affiliations from an author block.

        Common formats:
        1. Author Name\\Institution\\email (LaTeX line breaks)
        2. Author Name\\footnote...\\Institution
        3. \\And separator between authors

        Args:
            block: Content inside \\author{...}

        Returns:
            List of institution names.
        """
        affiliations: list[str] = []

        # Split by \And or \AND to process each author separately
        # \And in string -> regex \\And
        authors = re.split(r"\\And|\\AND", block)

        for author_section in authors:
            # Look for institution lines (between \\ markers)
            # LaTeX line break \\ in string -> regex \\\\
            lines = re.split(r"\\\\", author_section)

            for line in lines:
                line = line.strip()
                if not line:
                    continue

                # Skip emails
                if self._is_email(line):
                    continue

                # Skip footnote markers
                if re.match(r"\\footnote(?:mark|text)?", line):
                    continue

                # Skip thanks
                if re.match(r"\\thanks", line):
                    continue

                # Clean the line
                cleaned = self._clean_institution(line)

                # Check if it looks like an institution
                if self._looks_like_institution(cleaned):
                    affiliations.append(cleaned)

        return affiliations

    def _is_email(self, text: str) -> bool:
        """Check if text looks like an email address."""
        text = text.lower().strip()
        # Remove \\texttt{} wrapper if present
        text = re.sub(r"\\texttt\{([^}]+)\}", r"\1", text)
        return "@" in text and "." in text

    def _clean_institution(self, text: str) -> str:
        """Clean institution name from LaTeX formatting."""
        cleaned = text.strip()

        # Apply cleanup patterns
        for pattern, replacement in INSTITUTION_CLEANUP:
            cleaned = re.sub(pattern, replacement, cleaned)

        # Remove common LaTeX commands
        cleaned = re.sub(r"\\[a-zA-Z]+\{([^}]*)\}", r"\1", cleaned)
        cleaned = re.sub(r"\\[a-zA-Z]+", "", cleaned)

        # Normalize whitespace
        cleaned = re.sub(r"\s+", " ", cleaned).strip()

        return cleaned

    def _looks_like_institution(self, text: str) -> bool:
        """Heuristic to check if text looks like an institution name."""
        if not text or len(text) < 3:
            return False

        # Common institution keywords
        institution_keywords = [
            "university",
            "institute",
            "laboratory",
            "lab",
            "research",
            "college",
            "school",
            "center",
            "centre",
            "department",
            "google",
            "meta",
            "facebook",
            "amazon",
            "microsoft",
            "apple",
            "deepmind",
            "openai",
            "nvidia",
            "ibm",
            "intel",
            "adobe",
            "eth",
            "mit",
            "stanford",
            "berkeley",
            "cmu",
            "caltech",
            "harvard",
            "princeton",
            "yale",
            "oxford",
            "cambridge",
            "tsinghua",
            "peking",
            "tokyo",
            "singapore",
            "nus",
        ]

        text_lower = text.lower()

        # Check for keywords
        for keyword in institution_keywords:
            if keyword in text_lower:
                return True

        # Check if it's a proper noun-like structure (capitalized words)
        words = text.split()
        if len(words) >= 2:
            capitalized = sum(1 for w in words if w and w[0].isupper())
            if capitalized >= len(words) * 0.5:
                return True

        return False

    async def enrich_paper(self, paper: ArxivPaper) -> ArxivPaper:
        """Enrich a single paper with affiliations.

        Args:
            paper: ArxivPaper to enrich

        Returns:
            Same paper with affiliations field populated (if found).
        """
        if paper.affiliations:  # Already has affiliations
            return paper

        arxiv_id = paper.arxiv_id
        logger.debug(f"Extracting affiliations for {arxiv_id}")

        try:
            # Fetch source
            tarball = await self.fetch_source(arxiv_id)
            if tarball is None:
                return paper

            # Extract tex files
            tex_files = self.extract_tex_files(tarball)
            if not tex_files:
                logger.debug(f"No .tex files found for {arxiv_id}")
                return paper

            # Parse affiliations
            all_affiliations: list[str] = []
            for tex_content in tex_files:
                affiliations = self.parse_affiliations_from_tex(tex_content)
                all_affiliations.extend(affiliations)

            # Deduplicate
            seen = set()
            unique = []
            for aff in all_affiliations:
                normalized = aff.lower().strip()
                if normalized not in seen:
                    seen.add(normalized)
                    unique.append(aff)

            if unique:
                paper.affiliations = unique[:10]
                logger.debug(f"Found {len(paper.affiliations)} affiliations for {arxiv_id}")

            return paper

        except Exception as e:
            logger.warning(f"Error extracting affiliations for {arxiv_id}: {e}")
            return paper

    async def enrich_papers(
        self,
        papers: list[ArxivPaper],
        batch_size: int = 5,
    ) -> list[ArxivPaper]:
        """Enrich multiple papers with affiliations.

        Processes papers in batches to respect ArXiv rate limits.

        Args:
            papers: List of ArxivPaper objects to enrich
            batch_size: Number of papers to process concurrently

        Returns:
            List of enriched papers (same objects, modified in place).
        """
        if not papers:
            return papers

        import asyncio

        logger.info(f"Extracting affiliations for {len(papers)} papers")

        enriched_count = 0

        # Process in batches with rate limiting
        for i in range(0, len(papers), batch_size):
            batch = papers[i : i + batch_size]

            # Process batch concurrently
            tasks = [self.enrich_paper(paper) for paper in batch]
            await asyncio.gather(*tasks)

            # Count enriched
            for paper in batch:
                if paper.affiliations:
                    enriched_count += 1

            # Rate limiting between batches
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

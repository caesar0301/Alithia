"""Paper handler for ArXiv and DOI sources.

Uses arxiv SDK for reliable downloads with rich metadata.

RFC Reference: RFC-011 Section 10.2
"""

from __future__ import annotations

import logging
import re
from datetime import datetime
from pathlib import Path

import arxiv

from alithia.omr.collection.handlers.base_handler import Artifact, BaseHandler

logger = logging.getLogger(__name__)


def extract_arxiv_id(source: str) -> str | None:
    """Extract arxiv ID from source string.

    Args:
        source: Input source (URL or ID).

    Returns:
        Arxiv ID if found, None otherwise.
    """
    patterns = [
        r"arxiv\.org/abs/(\d{4}\.\d{4,5})",  # https://arxiv.org/abs/2402.12345
        r"arxiv\.org/pdf/(\d{4}\.\d{4,5})",  # https://arxiv.org/pdf/2402.12345
        r"arxiv:(\d{4}\.\d{4,5})",  # arxiv:2402.12345
        r"(\d{4}\.\d{4,5})",  # 2402.12345 (bare)
    ]

    for pattern in patterns:
        match = re.search(pattern, source.lower())
        if match:
            return match.group(1)

    return None


def extract_doi(source: str) -> str | None:
    """Extract DOI from source string.

    Args:
        source: Input source (URL or ID).

    Returns:
        DOI if found, None otherwise.
    """
    patterns = [
        r"doi\.org/(10\.\d{4,}/[^\s]+)",  # https://doi.org/10.xxxx/...
        r"doi:(10\.\d{4,}/[^\s]+)",  # doi:10.xxxx/...
        r"(10\.\d{4,}/[^\s]+)",  # Bare DOI
    ]

    for pattern in patterns:
        match = re.search(pattern, source)
        if match:
            return match.group(1).rstrip("/")  # Clean trailing slash

    return None


class PaperHandler(BaseHandler):
    """Handler for ArXiv papers, DOIs, and PDF URLs.

    RFC Reference: RFC-011 Section 10.2
    """

    async def collect(self, source: str, workspace: Path) -> Artifact:
        """Collect paper from source.

        Args:
            source: ArXiv URL/ID or DOI.
            workspace: Project workspace path.

        Returns:
            Paper artifact with metadata.
        """
        # Try arxiv first
        arxiv_id = extract_arxiv_id(source)
        if arxiv_id:
            return await self._collect_arxiv(arxiv_id, workspace)

        # Try DOI
        doi = extract_doi(source)
        if doi:
            return await self._collect_doi(doi, workspace)

        # Try as direct PDF URL
        if source.lower().endswith(".pdf"):
            return await self._collect_pdf_url(source, workspace)

        raise ValueError(f"Cannot identify paper source type: {source}")

    async def _collect_arxiv(self, arxiv_id: str, workspace: Path) -> Artifact:
        """Collect paper from ArXiv using SDK.

        Args:
            arxiv_id: ArXiv paper ID.
            workspace: Project workspace path.

        Returns:
            Paper artifact.
        """
        self.logger.info(f"Collecting arxiv paper: {arxiv_id}")

        try:
            # Use arxiv SDK
            search = arxiv.Search(id_list=[arxiv_id])
            paper = next(search.results())

            # Build metadata
            metadata = {
                "id": f"arxiv-{arxiv_id}",
                "arxiv_id": arxiv_id,
                "title": paper.title,
                "authors": [a.name for a in paper.authors],
                "summary": (
                    paper.summary[:500] + "..." if len(paper.summary) > 500 else paper.summary
                ),
                "doi": paper.doi or None,
                "categories": list(paper.categories),
                "published": paper.published.isoformat() if paper.published else None,
                "updated": paper.updated.isoformat() if paper.updated else None,
                "pdf_url": paper.pdf_url,
                "entry_url": paper.entry_url,
                "source_url": f"https://arxiv.org/abs/{arxiv_id}",
                "collected_at": datetime.now().isoformat(),
                "collected_by": "omr-collection/paper-handler",
                "source_type": "paper",
            }

            # Download PDF
            pdf_dir = workspace / "raw" / "paper"
            pdf_dir.mkdir(parents=True, exist_ok=True)
            pdf_path = pdf_dir / f"{arxiv_id}.pdf"

            try:
                paper.download_pdf(dirpath=str(pdf_dir), filename=f"{arxiv_id}.pdf")
                metadata["pdf_path"] = str(pdf_path)
            except Exception as e:
                self.logger.warning(f"Failed to download PDF: {e}")
                metadata["pdf_path"] = None

            # Generate content
            content = f"""# {paper.title}

**ArXiv ID**: {arxiv_id}
**Authors**: {", ".join(a.name for a in paper.authors)}
**Published**: {paper.published.strftime("%Y-%m-%d") if paper.published else "Unknown"}

## Abstract

{paper.summary}

## Links

- [ArXiv Page](https://arxiv.org/abs/{arxiv_id})
- [PDF](https://arxiv.org/pdf/{arxiv_id}.pdf)
{f"- [DOI](https://doi.org/{paper.doi})" if paper.doi else ""}
"""

            # Write artifact
            filename = f"arxiv-{arxiv_id}"
            artifact_path = self.write_artifact(workspace, "paper", filename, content, metadata)

            return Artifact(str(artifact_path), "paper", metadata, content)

        except Exception as e:
            self.logger.error(f"Failed to collect arxiv paper {arxiv_id}: {e}")
            raise

    async def _collect_doi(self, doi: str, workspace: Path) -> Artifact:
        """Collect paper from DOI (placeholder implementation).

        Args:
            doi: Paper DOI.
            workspace: Project workspace path.

        Returns:
            Paper artifact.
        """
        self.logger.info(f"Collecting DOI paper: {doi}")

        # Placeholder: DOI resolution requires external API (Crossref, Semantic Scholar)
        # For now, create stub artifact
        doi_slug = self.slugify(doi.replace("/", "-"))

        metadata = {
            "id": f"doi-{doi_slug}",
            "doi": doi,
            "collected_at": datetime.now().isoformat(),
            "collected_by": "omr-collection/paper-handler",
            "source_type": "paper",
            "status": "stub",  # Requires external DOI resolution
        }

        content = f"""# DOI Paper (Stub)

**DOI**: {doi}

Note: DOI resolution requires external API. This is a stub artifact.
Use ArXiv IDs for full collection support.
"""

        filename = f"doi-{doi_slug}"
        artifact_path = self.write_artifact(workspace, "paper", filename, content, metadata)

        return Artifact(str(artifact_path), "paper", metadata, content)

    async def _collect_pdf_url(self, source: str, workspace: Path) -> Artifact:
        """Collect paper from direct PDF URL.

        Args:
            source: PDF URL.
            workspace: Project workspace path.

        Returns:
            Paper artifact.
        """
        self.logger.info(f"Collecting PDF from URL: {source}")

        # Generate filename from URL hash
        url_hash = self.hash_source(source)
        filename = f"pdf-{url_hash}"

        metadata = {
            "id": filename,
            "pdf_url": source,
            "collected_at": datetime.now().isoformat(),
            "collected_by": "omr-collection/paper-handler",
            "source_type": "paper",
        }

        content = f"""# PDF Paper (Direct URL)

**Source URL**: {source}

Note: Direct PDF URLs require download for metadata extraction.
"""

        artifact_path = self.write_artifact(workspace, "paper", filename, content, metadata)

        return Artifact(str(artifact_path), "paper", metadata, content)


__all__ = ["PaperHandler", "extract_arxiv_id", "extract_doi"]

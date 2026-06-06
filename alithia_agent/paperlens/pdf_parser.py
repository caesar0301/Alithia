"""PDF parser using Docling with IBM Granite VLM.

Parses PDFs and extracts structured content with LLM metadata enhancement.
"""

from __future__ import annotations

import hashlib
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

from alithia_agent.models import AcademicPaper, PaperMetadata, PaperContent
from alithia_agent.models.metadata import FileMetadata

logger = logging.getLogger(__name__)


class DoclingParser:
    """PDF parser using Docling with IBM Granite VLM.

    Features:
    - IBM Granite Docling 258M for multimodal document understanding
    - LLM fallback for incomplete metadata
    - Hash-based caching support
    """

    def __init__(self, llm: Any | None = None):
        """Initialize PDF parser.

        Args:
            llm: Optional LLM client for metadata enhancement.
        """
        self.llm = llm

        # Initialize Docling converter
        try:
            from docling.datamodel.base_models import InputFormat
            from docling.datamodel.pipeline_options import VlmPipelineOptions
            from docling.document_converter import DocumentConverter, PdfFormatOption
            from docling.pipeline.vlm_pipeline import VlmPipeline

            pipeline_options = VlmPipelineOptions()
            self.converter = DocumentConverter(
                format_options={
                    InputFormat.PDF: PdfFormatOption(
                        pipeline_cls=VlmPipeline,
                        pipeline_options=pipeline_options,
                    )
                }
            )
            logger.info("Docling initialized with VlmPipeline (IBM Granite)")

        except Exception as e:
            logger.warning(f"IBM Granite VLM unavailable ({e}), using default")
            from docling.document_converter import DocumentConverter
            self.converter = DocumentConverter()

        if self.llm is None:
            logger.warning("No LLM provided - metadata enhancement disabled")

    def parse_file(self, path: Path) -> AcademicPaper | None:
        """Parse single PDF file.

        Args:
            path: Path to PDF file.

        Returns:
            AcademicPaper or None if parsing fails.
        """
        logger.info(f"Parsing {path.name}")
        errors: list[str] = []
        parse_timestamp = datetime.now()

        try:
            # Compute file metadata
            stat = path.stat()
            with open(path, "rb") as f:
                md5_hash = hashlib.md5(f.read()).hexdigest()

            file_metadata = FileMetadata(
                file_path=path,
                file_name=path.name,
                file_size=stat.st_size,
                last_modified=datetime.fromtimestamp(stat.st_mtime),
                md5_hash=md5_hash,
            )

            # Convert PDF with Docling
            try:
                doc = self.converter.convert(str(path)).document
            except Exception as e:
                error_msg = f"Docling conversion failed: {e}"
                logger.error(error_msg)
                errors.append(error_msg)
                return None

            # Extract content
            content = self._extract_content(doc)

            # Extract metadata
            paper_metadata = self._extract_metadata(doc)

            # LLM enhancement if incomplete
            if self._is_metadata_incomplete(paper_metadata) and self.llm:
                logger.info("Enhancing metadata with LLM")
                try:
                    llm_metadata = self._extract_metadata_with_llm(content.full_text)
                    paper_metadata = self._merge_metadata(paper_metadata, llm_metadata)
                    logger.info("Metadata enhanced")
                except Exception as e:
                    error_msg = f"LLM metadata extraction failed: {e}"
                    logger.warning(error_msg)
                    errors.append(error_msg)

            # Create AcademicPaper
            paper = AcademicPaper(
                title=paper_metadata.title,
                authors=paper_metadata.authors,
                abstract=paper_metadata.abstract,
                year=paper_metadata.year,
                keywords=paper_metadata.keywords,
                doi=paper_metadata.doi,
                full_text=content.full_text,
                sections=content.sections,
                figures=content.figures,
                tables=content.tables,
                source="pdf",
                source_url=str(path),
                parsed_at=parse_timestamp,
                parsing_errors=errors,
            )

            return paper

        except Exception as e:
            error_msg = f"Parse error: {e}"
            logger.error(error_msg)
            errors.append(error_msg)
            return None

    def _extract_metadata(self, doc: Any) -> PaperMetadata:
        """Extract metadata from Docling document."""
        metadata = PaperMetadata()

        try:
            if hasattr(doc, "title") and doc.title:
                metadata.title = doc.title.strip()

            if hasattr(doc, "authors") and doc.authors:
                metadata.authors = [a.strip() for a in doc.authors if a.strip()]

            if hasattr(doc, "date") and doc.date:
                try:
                    metadata.year = int(str(doc.date)[:4])
                except (ValueError, TypeError):
                    pass

            if hasattr(doc, "abstract") and doc.abstract:
                metadata.abstract = doc.abstract.strip()

            if hasattr(doc, "doi") and doc.doi:
                metadata.doi = doc.doi.strip()

        except Exception as e:
            logger.warning(f"Metadata extraction error: {e}")

        return metadata

    def _extract_content(self, doc: Any) -> PaperContent:
        """Extract content from Docling document."""
        content = PaperContent(full_text="")

        try:
            if hasattr(doc, "export_to_markdown"):
                content.full_text = doc.export_to_markdown()
            elif hasattr(doc, "export_to_text"):
                content.full_text = doc.export_to_text()
            else:
                content.full_text = str(doc)

        except Exception as e:
            logger.warning(f"Content extraction error: {e}")

        return content

    def _is_metadata_incomplete(self, metadata: PaperMetadata) -> bool:
        """Check if metadata needs LLM enhancement."""
        return not metadata.title or not metadata.abstract or len(metadata.authors) == 0

    def _extract_metadata_with_llm(self, full_text: str) -> PaperMetadata:
        """Extract metadata using LLM.

        Args:
            full_text: Full paper text (truncated to 8000 chars).

        Returns:
            PaperMetadata from LLM extraction.
        """
        truncated = full_text[:8000] if len(full_text) > 8000 else full_text

        prompt = f"""Extract the following metadata from this academic paper:

Paper text:
{truncated}

Please extract:
- Title (exact title, required)
- Authors (list of names, required)
- Year (publication year, if present)
- Abstract (summary, required)
- Keywords (topics, if present)
- DOI (if present)

Return as JSON."""

        # Call LLM (implementation depends on LLM client type)
        # This is a placeholder - actual implementation depends on soothe LLM interface
        if hasattr(self.llm, "structured_completion"):
            return self.llm.structured_completion(
                messages=[{"role": "user", "content": prompt}],
                response_model=PaperMetadata,
                temperature=0.1,
                max_tokens=500,
            )
        else:
            logger.warning("LLM does not support structured_completion")
            return PaperMetadata()

    def _merge_metadata(
        self,
        docling_meta: PaperMetadata,
        llm_meta: PaperMetadata,
    ) -> PaperMetadata:
        """Merge Docling and LLM metadata (Docling takes precedence)."""
        merged = llm_meta.model_dump()
        docling_data = docling_meta.model_dump()

        for key, value in docling_data.items():
            if value:  # Override if truthy
                merged[key] = value

        return PaperMetadata(**merged)


__all__ = ["DoclingParser"]
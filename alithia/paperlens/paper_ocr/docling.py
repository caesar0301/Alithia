import hashlib
from datetime import datetime
from pathlib import Path
from typing import Optional

from noesium.core.llm import BaseLLMClient
from noesium.core.utils import get_logger

from alithia.paperlens.models import AcademicPaper, FileMetadata, PaperContent, PaperMetadata
from alithia.paperlens.paper_ocr.base import PaperOcrBase

logger = get_logger(__name__)


class DoclingOcr(PaperOcrBase):
    """PDF parser using Docling with IBM Granite VLM."""

    def __init__(self, llm: Optional[BaseLLMClient] = None):
        super().__init__()
        self.llm = llm
        if self.llm is None:
            logger.warning("No LLM - metadata extraction limited")

        try:
            from docling.datamodel.base_models import InputFormat
            from docling.datamodel.pipeline_options import VlmPipelineOptions
            from docling.document_converter import DocumentConverter, PdfFormatOption
            from docling.pipeline.vlm_pipeline import VlmPipeline

            # Use IBM Granite Docling 258M - a multimodal model specifically designed for document conversion
            # See: https://huggingface.co/ibm-granite/granite-docling-258M
            pipeline_options = VlmPipelineOptions()
            self.converter = DocumentConverter(
                format_options={
                    InputFormat.PDF: PdfFormatOption(
                        pipeline_cls=VlmPipeline,
                        pipeline_options=pipeline_options,
                    )
                }
            )
        except Exception as e:
            logger.warning(f"IBM Granite Docling VLM unavailable ({e}), using default")
            from docling.document_converter import DocumentConverter

            self.converter = DocumentConverter()

    def parse_file(self, file_path: Path) -> Optional[AcademicPaper]:
        """Parse PDF and extract structured content.

        Args:
            pdf_path: Path to PDF file

        Returns:
            AcademicPaper or None if parsing fails
        """
        logger.info(f"Parsing {file_path.name}")
        errors = []
        parse_timestamp = datetime.now()

        try:
            # Compute file metadata
            stat = file_path.stat()
            with open(file_path, "rb") as f:
                md5_hash = hashlib.md5(f.read()).hexdigest()

            file_metadata = FileMetadata(
                file_path=file_path,
                file_name=file_path.name,
                file_size=stat.st_size,
                last_modified=datetime.fromtimestamp(stat.st_mtime),
                md5_hash=md5_hash,
            )

            # Convert PDF with docling
            try:
                doc = self.converter.convert(str(file_path)).document
            except Exception as e:
                error_msg = f"Docling conversion failed: {str(e)}"
                logger.error(error_msg)
                errors.append(error_msg)
                return None

            # Extract content and metadata
            content = self._extract_content(doc)
            paper_metadata = self._extract_metadata(doc)

            # LLM fallback for incomplete metadata
            if self._is_metadata_incomplete(paper_metadata):
                if self.llm is not None:
                    logger.info("Enhancing metadata with LLM")
                    try:
                        llm_metadata = self._extract_metadata_with_llm(content.full_text)
                        paper_metadata = self._merge_metadata(paper_metadata, llm_metadata)
                        logger.info("Metadata enhanced")
                    except Exception as e:
                        error_msg = f"LLM extraction failed: {str(e)}"
                        logger.warning(error_msg)
                        errors.append(error_msg)
                else:
                    logger.warning("Metadata incomplete and no LLM available for metadata enhancement")

            paper = AcademicPaper(
                file_metadata=file_metadata,
                paper_metadata=paper_metadata,
                content=content,
                parse_timestamp=parse_timestamp,
                parsing_errors=errors,
            )
            return paper
        except Exception as e:
            error_msg = f"Parse error: {str(e)}"
            logger.error(error_msg)
            errors.append(error_msg)
            return None

    def _extract_metadata(self, doc) -> PaperMetadata:
        """Extract metadata from docling document."""
        metadata = PaperMetadata()

        try:
            if hasattr(doc, "title") and doc.title:
                metadata.title = doc.title.strip()

            if hasattr(doc, "authors") and doc.authors:
                metadata.authors = [author.strip() for author in doc.authors if author.strip()]

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

    def _extract_content(self, doc) -> PaperContent:
        """Extract full text content from docling document."""
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
        """Check if metadata needs LLM enhancement.

        Args:
            metadata: PaperMetadata to check

        Returns:
            True if incomplete (missing title, abstract, or authors)
        """
        return not metadata.title or not metadata.abstract or len(metadata.authors) == 0

    def _extract_metadata_with_llm(self, full_text: str) -> PaperMetadata:
        """Extract metadata using LLM structured completion.

        Args:
            full_text: Full text of paper

        Returns:
            PaperMetadata extracted by LLM
        """
        truncated_text = full_text[:8000] if len(full_text) > 8000 else full_text
        prompt = f"""Extract the following metadata from this academic paper:

Paper text:
{truncated_text}

Please extract:
- Title (exact title of the paper, required)
- Authors (list of all author names, required)
- Year (publication year as 4-digit integer, if present)
- Abstract (the paper's abstract or summary, required)
- Keywords (list of key topics or keywords, if present)
- DOI (Digital Object Identifier, if present)
- Venue (journal or conference name, if present)

If any field is not found or unclear, leave it empty."""

        messages = [{"role": "user", "content": prompt}]

        llm_response = self.llm.structured_completion(
            messages=messages, response_model=PaperMetadata, temperature=0.1, max_tokens=1000
        )

        return llm_response

    def _merge_metadata(self, docling_metadata: PaperMetadata, llm_metadata: PaperMetadata) -> PaperMetadata:
        """Merge docling and LLM metadata (docling takes precedence).

        Args:
            docling_metadata: Metadata from docling
            llm_metadata: Metadata from LLM

        Returns:
            Merged PaperMetadata
        """
        # Start with LLM, override with docling where available
        merged_data = llm_metadata.model_dump()
        docling_data = docling_metadata.model_dump()

        for key, value in docling_data.items():
            if value:  # Override if truthy
                merged_data[key] = value

        return PaperMetadata(**merged_data)

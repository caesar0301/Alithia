"""PaperLens workflow nodes.

5-node linear pipeline:
validate_input → parse_pdfs → calculate_similarity → rank_results → generate_summary
"""

from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Any

from alithia.models import AcademicPaper, ArxivPaper, ScoredPaper
from alithia.paperlens.events import (
    PaperLensCompleteEvent,
    PaperLensErrorEvent,
    PaperLensPaperParsedEvent,
    PaperLensRankEvent,
    PaperLensStepEvent,
)
from alithia.paperlens.pdf_parser import DoclingParser
from alithia.paperlens.similarity import SimilarityEngine
from alithia.paperlens.state import AgentState

logger = logging.getLogger(__name__)


def _emit_step(step: str, status: str) -> None:
    """Emit workflow step event."""
    PaperLensStepEvent(step=step, status=status)  # Registers with soothe
    logger.info(f"[{step}] {status}")


def _emit_paper_parsed(paper_title: str, file_name: str) -> None:
    """Emit paper parsed event."""
    PaperLensPaperParsedEvent(paper_title=paper_title, file_name=file_name)  # Registers
    logger.info(f"Parsed: {paper_title} ({file_name})")


def _emit_rank(rank: int, paper_title: str, score: float) -> None:
    """Emit rank event."""
    PaperLensRankEvent(rank=rank, paper_title=paper_title, score=score)  # Registers
    logger.info(f"Rank #{rank}: {paper_title} (score: {score:.2f})")


def _emit_error(error_message: str, step: str, paper_id: str | None = None) -> None:
    """Emit error event."""
    PaperLensErrorEvent(error_message=error_message, step=step, paper_id=paper_id)  # Registers
    logger.error(f"Error in {step}: {error_message}")


def _emit_complete(papers_count: int) -> None:
    """Emit complete event."""
    PaperLensCompleteEvent(papers_count=papers_count)  # Registers
    logger.info(f"Completed: {papers_count} papers analyzed")


def make_nodes(config: Any, llm: Any | None = None) -> dict[str, Any]:
    """Create workflow node functions.

    Args:
        config: PaperLensConfig.
        llm: Optional LLM client for metadata enhancement.

    Returns:
        Dict mapping node names to functions.
    """
    parser = DoclingParser(llm=llm)
    similarity_engine = SimilarityEngine(
        model_name=config.sbert_model,
        use_gpu=config.use_gpu,
    )

    def validate_input_node(state: AgentState) -> dict[str, Any]:
        """Validate input: PDF path exists, query non-empty."""
        _emit_step("validate_input", "Validating input")

        errors: list[str] = []
        pdf_path = Path(state["pdf_path"])
        query = state["query"]

        # Check PDF path
        if not pdf_path.exists():
            error = f"PDF path does not exist: {pdf_path}"
            _emit_error(error, "validate_input")
            errors.append(error)

        # Check query
        if not query or len(query.strip()) < 3:
            error = "Query must be at least 3 characters"
            _emit_error(error, "validate_input")
            errors.append(error)

        if errors:
            return {"errors": errors}

        _emit_step("validate_input", "Input validated")
        return {"info": ["Input validated successfully"]}

    def parse_pdfs_node(state: AgentState) -> dict[str, Any]:
        """Parse PDFs from directory or file."""
        _emit_step("parse_pdfs", "Starting PDF parsing")

        pdf_path = Path(state["pdf_path"])
        config = state["config"]
        metrics = state.get("metrics", {})

        # Find PDF files
        pdf_files: list[Path] = []
        if pdf_path.is_file():
            if pdf_path.suffix.lower() == ".pdf":
                pdf_files = [pdf_path]
        else:
            pattern = "**/*.pdf" if config.recursive_scan else "*.pdf"
            pdf_files = list(pdf_path.glob(pattern))

        pdf_files = pdf_files[: config.max_papers * 2]  # Limit for safety

        metrics["pdfs_found"] = len(pdf_files)
        _emit_step("parse_pdfs", f"Found {len(pdf_files)} PDF files")

        # Parse PDFs
        parsed_papers: list[AcademicPaper] = []
        parse_times: list[float] = []
        parse_errors: list[str] = []

        for pdf_file in pdf_files:
            start_time = time.time()

            try:
                paper = parser.parse_file(pdf_file)
                if paper:
                    parsed_papers.append(paper)
                    parse_times.append(time.time() - start_time)
                    _emit_paper_parsed(paper.display_title, pdf_file.name)

            except Exception as e:
                error = f"Failed to parse {pdf_file.name}: {e}"
                _emit_error(error, "parse_pdfs", pdf_file.name)
                parse_errors.append(error)

        metrics["pdfs_parsed"] = len(parsed_papers)
        metrics["pdfs_failed"] = len(parse_errors)
        metrics["avg_parse_time_ms"] = (
            sum(parse_times) * 1000 / len(parse_times) if parse_times else 0
        )

        _emit_step("parse_pdfs", f"Parsed {len(parsed_papers)} papers successfully")

        return {
            "parsed_papers": parsed_papers,
            "errors": parse_errors,
            "metrics": metrics,
            "info": [f"Parsed {len(parsed_papers)} papers"],
        }

    def calculate_similarity_node(state: AgentState) -> dict[str, Any]:
        """Calculate similarity scores."""
        _emit_step("calculate_similarity", "Calculating similarity scores")

        query = state["query"]
        papers = state["parsed_papers"]
        metrics = state.get("metrics", {})

        if not papers:
            _emit_step("calculate_similarity", "No papers to score")
            return {
                "papers_with_scores": [],
                "info": ["No papers to score"],
            }

        try:
            scored = similarity_engine.calculate_scores(query, papers)

            metrics["avg_similarity_score"] = (
                sum(p.score for p in scored) / len(scored) if scored else 0
            )
            metrics["top_score"] = scored[0].score if scored else 0

            _emit_step("calculate_similarity", f"Scored {len(scored)} papers")

            return {
                "papers_with_scores": scored,
                "metrics": metrics,
                "info": [f"Calculated similarity for {len(scored)} papers"],
            }

        except Exception as e:
            _emit_error(str(e), "calculate_similarity")
            # Fallback: assign default scores
            scored = [
                ScoredPaper(paper=p, score=5.0, relevance_factors={"error_fallback": 5.0})
                for p in papers
            ]
            return {
                "papers_with_scores": scored,
                "errors": [f"Similarity calculation failed: {e}"],
            }

    def rank_results_node(state: AgentState) -> dict[str, Any]:
        """Rank papers by score."""
        _emit_step("rank_results", "Ranking papers")

        scored = state["papers_with_scores"]
        config = state["config"]
        max_results = config.max_papers

        if not scored:
            _emit_step("rank_results", "No papers to rank")
            return {"ranked_papers": []}

        # Sort and take top N
        sorted_papers = sorted(scored, key=lambda x: x.score, reverse=True)[:max_results]

        # Assign ranks
        for i, paper in enumerate(sorted_papers, start=1):
            paper.rank = i
            _emit_rank(i, paper.paper_title, paper.score)

        _emit_step("rank_results", f"Ranked {len(sorted_papers)} papers")

        return {
            "ranked_papers": sorted_papers,
            "info": [f"Ranked {len(sorted_papers)} papers"],
        }

    def generate_summary_node(state: AgentState) -> dict[str, Any]:
        """Generate formatted summary."""
        _emit_step("generate_summary", "Generating summary")

        ranked = state["ranked_papers"]
        config = state["config"]
        query = state["query"]
        metrics = state.get("metrics", {})

        # Calculate total processing time
        metrics["total_processing_time_ms"] = 0  # Would track actual time in production

        if not ranked:
            content = "No papers found matching your query.\n"
            _emit_complete(0)
            return {"response_content": content, "metrics": metrics}

        # Generate output based on format
        if config.output_format == "json":
            content = _generate_json_summary(query, ranked, metrics)
        else:
            content = _generate_markdown_summary(query, ranked, metrics)

        _emit_complete(len(ranked))

        return {
            "response_content": content,
            "metrics": metrics,
            "info": [f"Generated summary with {len(ranked)} papers"],
        }

    return {
        "validate_input": validate_input_node,
        "parse_pdfs": parse_pdfs_node,
        "calculate_similarity": calculate_similarity_node,
        "rank_results": rank_results_node,
        "generate_summary": generate_summary_node,
    }


def _generate_markdown_summary(
    query: str,
    ranked: list[ScoredPaper],
    metrics: dict[str, Any],
) -> str:
    """Generate markdown summary output."""
    lines = [
        "# PaperLens Results",
        "",
        f'Query: "{query}"',
        "",
        f"## Top {len(ranked)} Papers",
        "",
    ]

    for paper in ranked:
        # Get source - handle union type
        source = "unknown"
        if isinstance(paper.paper, AcademicPaper):
            source = paper.paper.source
        elif isinstance(paper.paper, ArxivPaper):
            source = "arxiv"

        lines.extend(
            [
                f"### {paper.rank}. {paper.paper_title} — Score: {paper.score:.2f}",
                f"- **Authors**: {paper.paper_authors}",
                f"- **Source**: {source}",
            ]
        )

        if paper.paper.abstract:
            abstract_preview = (
                paper.paper.abstract[:300] + "..."
                if len(paper.paper.abstract) > 300
                else paper.paper.abstract
            )
            lines.append(f"- **Abstract**: {abstract_preview}")

        lines.append("")

    lines.extend(
        [
            "---",
            "",
            f"Papers analyzed: {metrics.get('pdfs_parsed', 0)}",
            f"Top score: {metrics.get('top_score', 0):.2f}",
        ]
    )

    return "\n".join(lines)


def _generate_json_summary(
    query: str,
    ranked: list[ScoredPaper],
    metrics: dict[str, Any],
) -> str:
    """Generate JSON summary output."""
    import json

    data = {
        "query": query,
        "papers_count": len(ranked),
        "top_papers": [
            {
                "rank": p.rank,
                "title": p.paper_title,
                "authors": p.paper.authors,
                "score": p.score,
                "abstract": p.paper.abstract[:200] if p.paper.abstract else None,
            }
            for p in ranked
        ],
        "metrics": metrics,
    }

    return json.dumps(data, indent=2)


__all__ = ["make_nodes"]

"""
Alithia - AI-Powered Research Companion

Main entry point for all Alithia agents.
"""

import argparse
import asyncio
import sys
from pathlib import Path
from typing import List

from noesium.core.utils import get_logger

logger = get_logger(__name__)


def create_paperscout_parser(subparsers):
    """Create argument parser for paperscout agent."""
    parser = subparsers.add_parser(
        "paperscout_agent",
        help="Personalized arXiv recommendation agent",
        description="PaperScout - A personalized arXiv recommendation agent that delivers daily paper recommendations.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run with environment variables (defaults to yesterday)
  python -m alithia.run paperscout_agent
  
  # Run with configuration file
  python -m alithia.run paperscout_agent --config config.json
  
  # Run with custom date range
  python -m alithia.run paperscout_agent --from-date 2024-01-01 --to-date 2024-01-07
        """,
    )
    parser.add_argument("-c", "--config", type=str, help="Configuration file path (JSON)")
    parser.add_argument(
        "--from-date",
        type=str,
        help="Start date for paper query (YYYY-MM-DD format). Defaults to yesterday if not specified.",
    )
    parser.add_argument(
        "--to-date",
        type=str,
        help="End date for paper query (YYYY-MM-DD format). Defaults to from-date if not specified.",
    )
    parser.add_argument(
        "--fill-gaps",
        action="store_true",
        help="Run Gap Scanner to fill missing notification dates",
    )
    return parser


def create_paperlens_parser(subparsers):
    """Create argument parser for paperlens agent."""
    parser = subparsers.add_parser(
        "paperlens_agent",
        help="Deep paper interaction and discovery tool",
        description="PaperLens - Find relevant research papers using semantic similarity",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python -m alithia.run paperlens_agent -i research_topic.txt -d ./papers
  python -m alithia.run paperlens_agent -i topic.txt -d ./papers -n 20
  python -m alithia.run paperlens_agent -i topic.txt -d ./papers --model all-mpnet-base-v2
        """,
    )

    parser.add_argument(
        "-i",
        "--input",
        type=Path,
        required=True,
        help="Input file containing research topic (text/paragraph)",
    )

    parser.add_argument(
        "-d",
        "--directory",
        type=Path,
        required=True,
        help="Directory containing PDF papers",
    )

    parser.add_argument(
        "-n",
        "--top-n",
        type=int,
        default=10,
        help="Number of top papers to display (default: 10)",
    )

    parser.add_argument(
        "--model",
        type=str,
        default="all-MiniLM-L6-v2",
        help="Sentence transformer model to use (default: all-MiniLM-L6-v2)",
    )

    parser.add_argument(
        "--no-recursive",
        action="store_true",
        help="Don't search subdirectories for PDFs",
    )

    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Enable verbose logging",
    )

    parser.add_argument(
        "--force-gpu",
        action="store_true",
        help="Force GPU usage even if CUDA compatibility issues are detected",
    )

    return parser


def run_paperscout_agent(args):
    """Run the paperscout agent."""
    from alithia.config_loader import load_config
    from alithia.constants import (
        ALITHIA_MAX_PAPERS,
        ALITHIA_MAX_PAPERS_QUERIED,
        DEFAULT_ARXIV_QUERY,
        DEFAULT_SEND_EMPTY,
    )
    from alithia.paperscout.agent import PaperScoutAgent
    from alithia.paperscout.state import PaperScoutConfig
    from alithia.researcher.profile import ResearcherProfile
    from alithia.storage.factory import get_storage_backend

    config_dict = load_config(args.config)

    try:
        paperscout_settings = config_dict.get("paperscout_agent", config_dict.get("arxrec", {}))

        from_date = getattr(args, "from_date", None) or paperscout_settings.get("from_date")
        to_date = getattr(args, "to_date", None) or paperscout_settings.get("to_date")

        config = PaperScoutConfig(
            user_profile=ResearcherProfile.from_config(config_dict),
            query=paperscout_settings.get("query", DEFAULT_ARXIV_QUERY),
            max_papers=paperscout_settings.get("max_papers", ALITHIA_MAX_PAPERS),
            max_papers_queried=paperscout_settings.get("max_papers_queried", ALITHIA_MAX_PAPERS_QUERIED),
            send_empty=paperscout_settings.get("send_empty", DEFAULT_SEND_EMPTY),
            ignore_patterns=paperscout_settings.get("ignore_patterns", []),
            from_date=from_date,
            to_date=to_date,
            gap_scan_window_days=paperscout_settings.get("gap_scan_window_days", 7),
            debug=config_dict.get("debug", False),
        )
    except Exception as e:
        logger.error(f"Failed to create PaperScoutConfig: {e}")
        sys.exit(1)

    # Initialize storage
    try:
        storage = get_storage_backend(config_dict)
        storage.connect()
    except Exception:
        storage = None

    user_id = config_dict.get("storage", {}).get("user_id", config.user_profile.email or "default")
    agent = PaperScoutAgent(storage=storage, user_id=user_id)

    try:
        # Gap fill mode
        if getattr(args, "fill_gaps", False):
            from alithia.paperscout.gap_scanner import GapScanner

            if not storage:
                logger.error("Storage required for gap scanning")
                sys.exit(1)

            scanner = GapScanner(storage, user_id)
            results = asyncio.run(scanner.fill_gaps(config, agent))
            for d, status in sorted(results.items()):
                print(f"  {d.isoformat()}: {status}")
            return

        logger.info("Starting Alithia research agent...")
        result = agent.run(config)

        if result["success"]:
            logger.info("Research agent completed successfully")
            logger.info(f"Email sent with {result['summary']['papers_scored']} papers")

            if result["errors"]:
                logger.warning(f"{len(result['errors'])} warnings occurred")
                for error in result["errors"]:
                    logger.warning(f"   - {error}")
        else:
            logger.error("Research agent failed")
            logger.error(f"Error: {result['error']}")

            if result["errors"]:
                for error in result["errors"]:
                    logger.error(f"   - {error}")
            sys.exit(1)

    except KeyboardInterrupt:
        logger.info("Research agent interrupted by user")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        sys.exit(1)
    finally:
        if storage:
            storage.disconnect()


def run_paperlens_agent(args):
    """Run the paperlens agent."""
    from alithia.paperlens.engine import PaperLensEngine
    from alithia.paperlens.models import AcademicPaper

    def load_research_topic(input_file: Path) -> str:
        """Load research topic from input file."""
        if not input_file.exists():
            logger.error(f"Input file does not exist: {input_file}")
            sys.exit(1)

        with open(input_file, "r", encoding="utf-8") as f:
            topic = f.read().strip()

        if not topic:
            logger.error("Input file is empty")
            sys.exit(1)

        logger.info(f"Loaded research topic ({len(topic)} characters)")
        return topic

    def display_results(papers: List[AcademicPaper], research_topic: str):
        """Display the ranked papers in a formatted way."""
        print("\n" + "=" * 80)
        print("PAPERLENS - Research Paper Discovery Results")
        print("=" * 80)
        print(f"\nResearch Topic:\n{research_topic[:200]}{'...' if len(research_topic) > 200 else ''}\n")
        print(f"Found {len(papers)} relevant papers:\n")
        print("=" * 80)

        for i, paper in enumerate(papers, 1):
            print(f"\n[{i}] {paper.display_title}")
            print(f"    Authors: {paper.display_authors}")
            if paper.paper_metadata.year:
                print(f"    Year: {paper.paper_metadata.year}")
            if paper.paper_metadata.venue:
                print(f"    Venue: {paper.paper_metadata.venue}")
            print(f"    Similarity Score: {paper.similarity_score:.4f}")
            print(f"    File: {paper.file_metadata.file_path}")

            if paper.paper_metadata.abstract:
                abstract = paper.paper_metadata.abstract
                if len(abstract) > 300:
                    abstract = abstract[:300] + "..."
                print(f"    Abstract: {abstract}")

            if paper.parsing_errors:
                print(f"    ⚠️  Parsing warnings: {len(paper.parsing_errors)}")

        print("\n" + "=" * 80)

    # Load research topic
    research_topic = load_research_topic(args.input)

    # Initialize engine
    engine = PaperLensEngine(sbert_model=args.model, force_gpu=args.force_gpu)

    # Scan and parse PDFs
    papers = engine.scan_pdf_directory(args.directory, recursive=not args.no_recursive)

    if not papers:
        logger.error("No papers were successfully parsed. Exiting.")
        sys.exit(1)

    # Calculate similarity
    papers = engine.calculate_similarity(research_topic, papers)

    # Rank papers
    top_papers = engine.rank_papers(papers, top_n=args.top_n)

    # Display results
    display_results(top_papers, research_topic)


def create_sync_parser(subparsers):
    """Create argument parser for sync service."""
    parser = subparsers.add_parser(
        "sync",
        help="Sync connected services",
        description="Sync data from connected services (Zotero, Google Scholar) to local storage.",
    )
    parser.add_argument("-c", "--config", type=str, help="Configuration file path (JSON)")
    parser.add_argument(
        "--connector",
        choices=["zotero", "google_scholar"],
        help="Sync specific connector only",
    )
    parser.add_argument("--full", action="store_true", help="Force full sync (ignore incremental state)")
    parser.add_argument("--status", action="store_true", help="Show last sync status for all connectors")
    return parser


def create_dashboard_parser(subparsers):
    """Create argument parser for dashboard."""
    parser = subparsers.add_parser(
        "dashboard",
        help="Start Alithia Dashboard",
        description="Start the Alithia Dashboard web server.",
    )
    parser.add_argument("-c", "--config", type=str, help="Configuration file path (JSON)")
    parser.add_argument("--port", type=int, default=8080, help="Server port (default: 8080)")
    parser.add_argument("--host", default="0.0.0.0", help="Server host (default: 0.0.0.0)")
    parser.add_argument("--dev", action="store_true", help="Enable auto-reload for development")
    return parser


def run_sync(args):
    """Run the sync service."""
    from alithia.config_loader import load_config
    from alithia.researcher.profile import ResearcherProfile
    from alithia.storage.factory import get_storage_backend
    from alithia.sync.orchestrator import SyncOrchestrator

    config_dict = load_config(args.config)
    storage = get_storage_backend(config_dict)
    storage.connect()

    try:
        user_id = config_dict.get("storage", {}).get("user_id", "default")
        profile = ResearcherProfile.from_config(config_dict)
        orchestrator = SyncOrchestrator(storage, user_id, profile)

        if args.status:
            for status in orchestrator.get_status():
                synced = status["last_synced"] or "never"
                configured = "configured" if status["configured"] else "not configured"
                print(f"{status['connector']}: {configured}, last synced {synced}")
            return

        if args.connector:
            results = [asyncio.run(orchestrator.sync_one(args.connector, force_full=args.full))]
        else:
            results = asyncio.run(orchestrator.sync_all(force_full=args.full))

        for r in results:
            print(f"{r.connector_name}: {r.status.value} ({r.items_synced}/{r.items_total} items)")
            if r.error_message:
                print(f"  Error: {r.error_message}")
    finally:
        storage.disconnect()


def run_dashboard(args):
    """Start the Dashboard server."""
    import os

    import uvicorn

    if args.dev:
        # Use import string for reload mode
        # Set config path as environment variable for the factory to use
        os.environ["ALITHIA_CONFIG_PATH"] = args.config or "alithia_config.json"
        uvicorn.run(
            "alithia.dashboard.app:create_app",
            factory=True,
            host=args.host,
            port=args.port,
            reload=True,
        )
    else:
        from alithia.config_loader import load_config
        from alithia.storage.factory import get_storage_backend

        config_dict = load_config(args.config)
        storage = get_storage_backend(config_dict)
        storage.connect()

        try:
            from alithia.dashboard.app import create_app

            app = create_app(config_dict, storage)
            uvicorn.run(app, host=args.host, port=args.port, reload=False)
        finally:
            storage.disconnect()


def main():
    """Main entry point for Alithia."""
    parser = argparse.ArgumentParser(
        prog="alithia",
        description="Alithia - AI-Powered Research Companion",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Available Commands:
  paperscout_agent  Personalized arXiv recommendation agent
  paperlens_agent   Deep paper interaction and discovery tool
  sync              Sync connected services (Zotero, Google Scholar)
  dashboard         Start Alithia Dashboard web server

Examples:
  python -m alithia.run paperscout_agent --config config.json
  python -m alithia.run paperlens_agent -i topic.txt -d ./papers
  python -m alithia.run sync --config config.json
  python -m alithia.run dashboard --config config.json

For more information on each command, use:
  python -m alithia.run <command> --help
        """,
    )

    # Create subparsers for different agents
    subparsers = parser.add_subparsers(dest="agent", help="Command to run", required=True)

    # Add agent parsers
    create_paperscout_parser(subparsers)
    create_paperlens_parser(subparsers)
    create_sync_parser(subparsers)
    create_dashboard_parser(subparsers)

    # Parse arguments
    args = parser.parse_args()

    # Route to appropriate agent
    if args.agent == "paperscout_agent":
        run_paperscout_agent(args)
    elif args.agent == "paperlens_agent":
        run_paperlens_agent(args)
    elif args.agent == "sync":
        run_sync(args)
    elif args.agent == "dashboard":
        run_dashboard(args)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()

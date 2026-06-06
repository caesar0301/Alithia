"""CLI entry point for alithia-agent.

Usage:
    python -m alithia_agent --subagent paperscout
    python -m alithia_agent --subagent paperlens --query "transformers" --pdf-path ~/papers

Exit codes:
    0: Success
    1: Argument/config error
    2: Execution error
    3: Config validation error
    4: Input validation error
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import date
from pathlib import Path
from typing import Any

from alithia_agent.config import load_config, Config, ConfigError
from alithia_agent import ALITHIA_HOME, SOOTHE_HOME

logger = logging.getLogger(__name__)

# Exit codes
EXIT_SUCCESS = 0
EXIT_ARG_ERROR = 1
EXIT_EXEC_ERROR = 2
EXIT_CONFIG_ERROR = 3
EXIT_VALIDATION_ERROR = 4


def setup_logging(verbose: bool, quiet: bool) -> None:
    """Configure logging based on verbosity."""
    if quiet:
        level = logging.ERROR
    elif verbose:
        level = logging.DEBUG
    else:
        level = logging.INFO

    # Log to ALITHIA_HOME/logs/alithia.log
    log_dir = ALITHIA_HOME / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "alithia.log"

    logging.basicConfig(
        level=level,
        format="[%(levelname)s] %(message)s",
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(log_file),
        ],
    )
    logger.info(f"ALITHIA_HOME: {ALITHIA_HOME}")
    logger.info(f"SOOTHE_HOME: {SOOTHE_HOME}")


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        prog="alithia_agent",
        description="CLI research assistant for paper discovery and analysis",
    )

    # Global options
    parser.add_argument(
        "--config",
        type=str,
        default=None,
        help="Configuration file path (default: ~/.alithia/config.json)",
    )
    parser.add_argument(
        "--subagent",
        choices=["paperscout", "paperlens"],
        required=True,
        help="Subagent to invoke",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Show detailed progress",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress all output except errors",
    )
    parser.add_argument(
        "--output",
        choices=["stdout", "json", "none"],
        default="stdout",
        help="Output format",
    )
    parser.add_argument(
        "--user-id",
        type=str,
        default=None,
        help="Override user identifier",
    )
    parser.add_argument(
        "--version",
        action="version",
        version="alithia-agent 1.0.0",
    )

    # PaperScout-specific options
    paperscout_group = parser.add_argument_group("PaperScout options")
    paperscout_group.add_argument(
        "--categories",
        type=str,
        help="ArXiv categories (comma-separated: cs.AI,cs.LG)",
    )
    paperscout_group.add_argument(
        "--max-papers",
        type=int,
        help="Maximum papers in digest",
    )
    paperscout_group.add_argument(
        "--lookback",
        type=int,
        help="Days to look back",
    )
    paperscout_group.add_argument(
        "--dry-run",
        action="store_true",
        help="Run without sending email",
    )
    paperscout_group.add_argument(
        "--fill-gaps",
        action="store_true",
        help="Fill missed notification dates",
    )

    # PaperLens-specific options
    paperlens_group = parser.add_argument_group("PaperLens options")
    paperlens_group.add_argument(
        "--query",
        type=str,
        help="Research topic for similarity matching (required for paperlens)",
    )
    paperlens_group.add_argument(
        "--pdf-path",
        type=str,
        help="Path to PDF file or directory (required for paperlens)",
    )
    paperlens_group.add_argument(
        "--recursive",
        action="store_true",
        default=True,
        help="Search subdirectories",
    )
    paperlens_group.add_argument(
        "--no-recursive",
        action="store_false",
        dest="recursive",
        help="Do not search subdirectories",
    )
    paperlens_group.add_argument(
        "--max-results",
        type=int,
        default=50,
        help="Maximum results to return",
    )
    paperlens_group.add_argument(
        "--format",
        choices=["markdown", "json"],
        default="markdown",
        help="Output format",
    )

    return parser.parse_args()


def build_cli_overrides(args: argparse.Namespace) -> dict[str, Any]:
    """Build CLI overrides dict for config merge."""
    overrides: dict[str, Any] = {}

    # User ID override
    if args.user_id:
        overrides["storage"] = {"user_id": args.user_id}

    # PaperScout overrides
    if args.subagent == "paperscout":
        paperscout_overrides: dict[str, Any] = {}

        if args.categories:
            paperscout_overrides["query"] = args.categories.replace(",", "+")
        if args.max_papers:
            paperscout_overrides["max_papers"] = args.max_papers
        if args.lookback:
            paperscout_overrides["lookback_days"] = args.lookback
        if args.dry_run:
            paperscout_overrides["send_email"] = False

        if paperscout_overrides:
            overrides["paperscout_agent"] = paperscout_overrides

    # PaperLens overrides
    if args.subagent == "paperlens":
        paperlens_overrides: dict[str, Any] = {}

        if args.max_results:
            paperlens_overrides["max_papers"] = args.max_results
        paperlens_overrides["recursive_scan"] = args.recursive
        paperlens_overrides["output_format"] = args.format

        if paperlens_overrides:
            overrides["paperlens_agent"] = paperlens_overrides

    return overrides


def format_output(result: dict[str, Any], output_format: str) -> str:
    """Format workflow result for output."""
    if output_format == "json":
        return json.dumps(result, indent=2, default=str)
    elif output_format == "none":
        return ""

    # stdout format (markdown-ish)
    lines = []

    # Info messages
    if "info" in result:
        for msg in result["info"]:
            lines.append(msg)

    # Errors
    if result.get("errors"):
        lines.append("\nErrors:")
        for err in result["errors"]:
            lines.append(f"  ERROR: {err}")

    # Metrics
    if "metrics" in result:
        lines.append("\nMetrics:")
        for key, value in result["metrics"].items():
            lines.append(f"  {key}: {value}")

    # Response content (for PaperLens)
    if "response_content" in result:
        lines.append("\n" + result["response_content"])

    return "\n".join(lines)


async def run_paperscout(config: Config, args: argparse.Namespace) -> dict[str, Any]:
    """Run PaperScout subagent."""
    from alithia_agent.storage import initialize_storage
    from alithia_agent.paperscout.implementation import create_paperscout_subagent
    from alithia_agent.paperscout import build_runtime_config

    # Initialize storage
    storage = initialize_storage(config.storage.user_id)

    # Build runtime config from global config
    runtime_config = build_runtime_config(config)

    # Create subagent
    subagent = create_paperscout_subagent(
        config=runtime_config,
        store=storage,
        user_id=config.storage.user_id,
    )

    # Build initial state
    initial_state: dict[str, Any] = {
        "config": runtime_config,
        "user_id": config.storage.user_id,
        "errors": [],
        "info": [],
        "metrics": {},
        "messages": [],
        "discovered_papers": [],
        "zotero_papers": [],
        "scored_papers": [],
        "email_content": None,
    }

    # Run workflow
    runnable = subagent["runnable"]
    result = await runnable.ainvoke(initial_state)

    return result


async def run_paperlens(config: Config, args: argparse.Namespace) -> dict[str, Any]:
    """Run PaperLens subagent."""
    from alithia_agent.paperlens.implementation import create_paperlens_subagent
    from alithia_agent.paperlens import build_runtime_config

    # Validate required arguments
    if not args.query:
        print("ERROR: --query is required for paperlens")
        sys.exit(EXIT_ARG_ERROR)
    if not args.pdf_path:
        print("ERROR: --pdf-path is required for paperlens")
        sys.exit(EXIT_ARG_ERROR)

    # Validate pdf_path exists
    pdf_path = Path(args.pdf_path)
    if not pdf_path.exists():
        print(f"ERROR: PDF path does not exist: {args.pdf_path}")
        sys.exit(EXIT_VALIDATION_ERROR)

    # Build runtime config from global config
    runtime_config = build_runtime_config(config)

    # Create subagent
    subagent = create_paperlens_subagent(
        config=runtime_config,
        user_id=config.storage.user_id,
    )

    # Build initial state
    initial_state: dict[str, Any] = {
        "config": runtime_config,
        "user_id": config.storage.user_id,
        "query": args.query,
        "pdf_path": str(pdf_path),
        "errors": [],
        "info": [],
        "metrics": {},
        "messages": [],
        "parsed_papers": [],
        "papers_with_scores": [],
        "ranked_papers": [],
        "response_content": "",
    }

    # Run workflow
    runnable = subagent["runnable"]
    result = await runnable.ainvoke(initial_state)

    return result


async def main_async() -> int:
    """Async main entry point."""
    args = parse_args()

    # Setup logging
    setup_logging(args.verbose, args.quiet)

    # Load config
    try:
        cli_overrides = build_cli_overrides(args)
        config = load_config(args.config, cli_overrides)
    except ConfigError as e:
        print(str(e))
        return EXIT_CONFIG_ERROR

    # Run subagent
    try:
        if args.subagent == "paperscout":
            result = await run_paperscout(config, args)
        elif args.subagent == "paperlens":
            result = await run_paperlens(config, args)
        else:
            print(f"ERROR: Unknown subagent: {args.subagent}")
            return EXIT_ARG_ERROR

        # Format and print output
        if args.output != "none":
            output = format_output(result, args.output)
            print(output)

        # Check for errors
        if result.get("errors"):
            return EXIT_EXEC_ERROR

        return EXIT_SUCCESS

    except Exception as e:
        logger.error(f"Execution error: {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        return EXIT_EXEC_ERROR


def main() -> None:
    """Main entry point."""
    import asyncio
    exit_code = asyncio.run(main_async())
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
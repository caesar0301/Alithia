"""CLI entry point for alithia-agent.

Usage:
    # Intent-based routing (automatic):
    python -m alithia_agent "Find new papers about transformers"
    python -m alithia_agent "Rank my PDFs in ~/research by relevance"

    # Explicit subagent invocation:
    python -m alithia_agent --subagent paperscout "Check for new papers"
    python -m alithia_agent --subagent paperlens "Analyze ~/papers directory"

Exit codes:
    0: Success
    1: Argument/config error
    2: Execution error
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
from typing import Any

from alithia_agent.agent import AlithiaAgent
from alithia_agent import ALITHIA_HOME, SOOTHE_HOME

logger = logging.getLogger(__name__)

# Exit codes
EXIT_SUCCESS = 0
EXIT_ARG_ERROR = 1
EXIT_EXEC_ERROR = 2


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
        description="CLI research assistant powered by soothe framework",
    )

    # Positional argument: natural language prompt
    parser.add_argument(
        "prompt",
        type=str,
        nargs="?",
        help="Natural language prompt for the research assistant",
    )

    # Global options
    parser.add_argument(
        "--config",
        type=str,
        default=None,
        help="Alithia config file path (default: ~/.alithia/config.yml)",
    )
    parser.add_argument(
        "--subagent",
        choices=["paperscout", "paperlens"],
        default=None,
        help="Explicitly invoke a specific subagent (bypasses intent routing)",
    )
    parser.add_argument(
        "--thread-id",
        type=str,
        default=None,
        help="Thread identifier for persistence",
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
        "--version",
        action="version",
        version="alithia-agent 1.0.0",
    )

    # Legacy compatibility: --user-id for storage
    parser.add_argument(
        "--user-id",
        type=str,
        default=None,
        help="Override user identifier for storage",
    )

    return parser.parse_args()


async def run_agent(args: argparse.Namespace) -> int:
    """Run alithia agent with user input.

    Args:
        args: Parsed CLI arguments.

    Returns:
        Exit code (0 for success, non-zero for errors).
    """
    # Create alithia agent
    agent = AlithiaAgent.create(args.config)

    # Build stream config
    stream_mode = ["messages", "updates", "custom"]

    # Run user input through soothe's agent loop
    result_stream = agent.run(
        user_input=args.prompt,
        thread_id=args.thread_id,
        stream_mode=stream_mode,
        subagent=args.subagent,  # Explicit override if provided
    )

    # Process stream
    output_parts: list[Any] = []
    errors: list[str] = []

    async for chunk in result_stream:
        if args.output == "json":
            output_parts.append(chunk)
        else:
            # Format for stdout
            if isinstance(chunk, dict):
                # Handle different chunk types
                if "content" in chunk:
                    print(chunk["content"], end="", flush=True)
                elif "event" in chunk:
                    # Soothe event - extract summary if available
                    event = chunk.get("event", {})
                    if isinstance(event, dict) and "summary" in event:
                        if args.verbose:
                            print(f"\n[{event.get('type', 'event')}] {event['summary']}")
                elif "error" in chunk:
                    errors.append(chunk["error"])
                    if args.verbose:
                        print(f"\n[ERROR] {chunk['error']}")
            elif hasattr(chunk, "content"):
                # LangChain message
                print(chunk.content, end="", flush=True)

    # JSON output
    if args.output == "json":
        print(json.dumps(output_parts, indent=2, default=str))

    # Check for errors
    if errors:
        logger.error(f"Execution completed with {len(errors)} errors")
        return EXIT_EXEC_ERROR

    return EXIT_SUCCESS


async def main_async() -> int:
    """Async main entry point."""
    args = parse_args()

    # Setup logging
    setup_logging(args.verbose, args.quiet)

    # Validate prompt
    if not args.prompt:
        print("ERROR: Please provide a prompt")
        print("\nExamples:")
        print("  alithia-agent 'Find new papers about transformers'")
        print("  alithia-agent 'Rank my PDFs by relevance'")
        print("  alithia-agent --subagent paperscout 'Check for new papers'")
        return EXIT_ARG_ERROR

    # Run agent
    try:
        return await run_agent(args)

    except KeyboardInterrupt:
        logger.info("Execution interrupted by user")
        return EXIT_EXEC_ERROR

    except Exception as e:
        logger.error(f"Execution error: {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        return EXIT_EXEC_ERROR


def main() -> None:
    """Main entry point."""
    exit_code = asyncio.run(main_async())
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
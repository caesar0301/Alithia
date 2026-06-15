"""CLI entry point for alithia-agent.

Usage:
    # Intent-based routing (automatic):
    python -m alithia_agent "Find new papers about transformers"
    python -m alithia_agent "Rank my PDFs in ~/research by relevance"

    # Explicit subagent invocation:
    python -m alithia_agent --subagent paperscout "Check for new papers"
    python -m alithia_agent --subagent paperlens "Analyze ~/papers directory"

    # Daemon management:
    python -m alithia_agent start     # Start daemon (background)
    python -m alithia_agent stop      # Stop daemon
    python -m alithia_agent restart   # Restart daemon
    python -m alithia_agent status    # Show daemon status

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
import os
import signal
import subprocess
import sys
from pathlib import Path
from typing import Any

from alithia_agent import ALITHIA_HOME, SOOTHE_HOME
from alithia_agent.agent import AlithiaAgent

logger = logging.getLogger(__name__)

# Exit codes
EXIT_SUCCESS = 0
EXIT_ARG_ERROR = 1
EXIT_EXEC_ERROR = 2

# Daemon PID file path
DAEMON_PID_FILE = ALITHIA_HOME / "daemon.pid"


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

    # Positional argument: command
    parser.add_argument(
        "command",
        type=str,
        nargs="?",
        default="run",
        help="Command: 'run' (default), 'start', 'stop', 'restart', 'status', 'daemon'",
    )

    # Optional second positional for prompt (when command is 'run')
    parser.add_argument(
        "prompt",
        type=str,
        nargs="?",
        default=None,
        help="Natural language prompt for the research assistant (for 'run' command)",
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
        version="alithia-agent 0.3.1",
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

    # Run user input through soothe's agent loop
    result_stream = await agent.run(
        user_input=args.prompt,
        thread_id=args.thread_id,
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


def get_daemon_pid() -> int | None:
    """Get daemon PID from PID file.

    Returns:
        PID if running, None if not running or no PID file.
    """
    if not DAEMON_PID_FILE.exists():
        return None

    try:
        pid = int(DAEMON_PID_FILE.read_text().strip())
        # Check if process is still running
        os.kill(pid, 0)  # Signal 0 just checks if process exists
        return pid
    except (ValueError, OSError):
        # Invalid PID or process not running
        return None


def is_daemon_running() -> bool:
    """Check if daemon is running.

    Returns:
        True if daemon is running, False otherwise.
    """
    return get_daemon_pid() is not None


def stop_daemon(args: argparse.Namespace) -> int:
    """Stop daemon by sending SIGTERM.

    Args:
        args: Parsed CLI arguments.

    Returns:
        Exit code.
    """
    pid = get_daemon_pid()

    if pid is None:
        print("Daemon is not running")
        return EXIT_SUCCESS

    print(f"Stopping daemon (PID: {pid})...")

    try:
        # Send SIGTERM for graceful shutdown
        os.kill(pid, signal.SIGTERM)

        # Wait for process to terminate (up to 10 seconds)
        import time

        for _ in range(10):
            try:
                os.kill(pid, 0)  # Check if still running
                time.sleep(1)
            except OSError:
                # Process terminated
                print("Daemon stopped")
                return EXIT_SUCCESS

        # Force kill if still running
        print("Daemon not responding, sending SIGKILL...")
        os.kill(pid, signal.SIGKILL)
        time.sleep(1)
        print("Daemon killed")
        return EXIT_SUCCESS

    except OSError as e:
        print(f"Error stopping daemon: {e}")
        return EXIT_EXEC_ERROR


def start_daemon(args: argparse.Namespace) -> int:
    """Start daemon in background.

    Args:
        args: Parsed CLI arguments.

    Returns:
        Exit code.
    """
    # Check if already running
    if is_daemon_running():
        pid = get_daemon_pid()
        print(f"Daemon already running (PID: {pid})")
        return EXIT_SUCCESS

    # Build command
    cmd = [sys.executable, "-m", "alithia_agent", "daemon"]
    if args.config:
        cmd.extend(["--config", args.config])
    if args.verbose:
        cmd.append("--verbose")

    print("Starting alithia-agent daemon...")

    # Start daemon in background
    try:
        # Use subprocess to start daemon detached
        subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,  # Detach from parent process
        )

        # Wait a moment and check if started
        import time

        time.sleep(2)

        pid = get_daemon_pid()
        if pid:
            print(f"Daemon started (PID: {pid})")
            return EXIT_SUCCESS
        else:
            print("Daemon failed to start. Check logs at ~/.alithia/logs/daemon.log")
            return EXIT_EXEC_ERROR

    except Exception as e:
        print(f"Error starting daemon: {e}")
        return EXIT_EXEC_ERROR


def restart_daemon(args: argparse.Namespace) -> int:
    """Restart daemon (stop then start).

    Args:
        args: Parsed CLI arguments.

    Returns:
        Exit code.
    """
    print("Restarting alithia-agent daemon...")

    # Stop if running
    if is_daemon_running():
        stop_result = stop_daemon(args)
        if stop_result != EXIT_SUCCESS:
            return stop_result

    # Start
    return start_daemon(args)


async def run_daemon_command_async(args: argparse.Namespace) -> int:
    """Run daemon service from async context (direct daemon command).

    Args:
        args: Parsed CLI arguments.

    Returns:
        Exit code.
    """
    from alithia_agent.daemon.service import DaemonService

    config_path = Path(args.config) if args.config else None

    logger.info("Daemon command invoked")

    try:
        service = DaemonService(config_path=config_path)
        return await service.run()
    except Exception as e:
        logger.exception(f"Daemon failed: {e}")
        return EXIT_EXEC_ERROR


def run_status_command(args: argparse.Namespace) -> int:
    """Show daemon/scheduler status.

    Args:
        args: Parsed CLI arguments.

    Returns:
        Exit code.
    """
    from alithia_agent.daemon.service import get_daemon_status

    config_path = Path(args.config) if args.config else None

    # Check running status from PID file
    pid = get_daemon_pid()
    running = pid is not None

    # Get config-based status
    config_status = get_daemon_status(config_path=config_path)

    status = {
        "running": running,
        "pid": pid,
        "pid_file": str(DAEMON_PID_FILE),
        "config": config_status.get("config", {}),
    }

    if args.output == "json":
        print(json.dumps(status, indent=2, default=str))
    else:
        print("Alithia-Agent Daemon Status")
        print("=" * 40)

        if running:
            print(f"Status: RUNNING (PID: {pid})")
        else:
            print("Status: NOT RUNNING")

        config = status.get("config", {})
        print("\nConfiguration:")
        print(f"  Scheduler enabled: {config.get('scheduler_enabled', False)}")
        print(f"  Schedule: {config.get('schedule', 'N/A')}")
        print(f"  Retry window: {config.get('retry_window_days', 'N/A')} days")
        print(f"  Big bang: {config.get('big_bang', 'N/A')}")

        print()
        print("Commands:")
        print("  alithia-agent start    # Start daemon")
        print("  alithia-agent stop     # Stop daemon")
        print("  alithia-agent restart  # Restart daemon")

    return EXIT_SUCCESS


async def main_async() -> int:
    """Async main entry point."""
    args = parse_args()

    # Setup logging
    setup_logging(args.verbose, args.quiet)

    # Handle different commands
    command = args.command

    if command == "daemon":
        # Run daemon service directly (foreground, async)
        return await run_daemon_command_async(args)

    elif command == "start":
        # Start daemon in background
        return start_daemon(args)

    elif command == "stop":
        # Stop daemon
        return stop_daemon(args)

    elif command == "restart":
        # Restart daemon
        return restart_daemon(args)

    elif command == "status":
        # Show daemon status
        return run_status_command(args)

    elif command == "run":
        # Default: run agent with prompt
        if not args.prompt:
            print("ERROR: Please provide a prompt")
            print("\nExamples:")
            print("  alithia-agent 'Find new papers about transformers'")
            print("  alithia-agent 'Rank my PDFs by relevance'")
            print("  alithia-agent --subagent paperscout 'Check for new papers'")
            print("\nDaemon commands:")
            print("  alithia-agent start    # Start background daemon")
            print("  alithia-agent stop     # Stop daemon")
            print("  alithia-agent restart  # Restart daemon")
            print("  alithia-agent status   # Show daemon status")
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

    else:
        # Unknown command - treat as prompt
        args.prompt = command
        command = "run"

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

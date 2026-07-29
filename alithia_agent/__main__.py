"""CLI entry point for alithia-agent.

Usage:
    # Query path (explicit user request through soothe-nano):
    python -m alithia_agent "Find new papers about transformers"
    python -m alithia_agent "Rank my PDFs in ~/research by relevance"

    # Optional local subagent hint (biases the prompt; not soothed routing):
    python -m alithia_agent --subagent paperscout "Check for new papers"
    python -m alithia_agent --subagent paperlens "Analyze ~/papers directory"

    # Alithia PaperScout scheduler daemon:
    python -m alithia_agent daemon start    # Start daemon (background)
    python -m alithia_agent daemon stop     # Stop daemon
    python -m alithia_agent daemon restart  # Restart daemon
    python -m alithia_agent daemon status   # Show daemon status

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
import time
from pathlib import Path
from typing import Any

from alithia_agent import ALITHIA_HOME, SOOTHE_HOME
from alithia_agent.agent import AlithiaAgent
from alithia_agent.cli_colors import bold, cyan, dim, green, red, supports_color, yellow
from alithia_agent.logging_config import DEFAULT_LOG_FILE, configure_logging

logger = logging.getLogger(__name__)

# Exit codes
EXIT_SUCCESS = 0
EXIT_ARG_ERROR = 1
EXIT_EXEC_ERROR = 2

# Daemon PID file path
DAEMON_PID_FILE = ALITHIA_HOME / "daemon.pid"


def setup_logging(verbose: bool, quiet: bool, *, lightweight: bool = False) -> None:
    """Configure logging based on verbosity and command type."""
    if quiet:
        level = logging.ERROR
    elif verbose:
        level = logging.DEBUG
    elif lightweight:
        level = logging.WARNING
    else:
        level = logging.INFO

    log_file = None if lightweight and not verbose else ALITHIA_HOME / DEFAULT_LOG_FILE
    configure_logging(level=level, log_file=log_file, console=True)

    if verbose:
        logger.debug(f"ALITHIA_HOME: {ALITHIA_HOME}")
        logger.debug(f"SOOTHE_HOME: {SOOTHE_HOME}")


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        prog="alithia-agent",
        description="CLI research assistant powered by soothe-nano",
    )

    # Global options
    parser.add_argument(
        "--config",
        type=str,
        default=None,
        help="Alithia config file path (default: ~/.alithia/config.yml)",
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

    # Create subparsers for commands
    subparsers = parser.add_subparsers(
        dest="command",
        title="commands",
        description="Available commands",
    )

    # 'run' command (default) - for running agent with prompt
    run_parser = subparsers.add_parser(
        "run",
        help="Run agent with a prompt (default command)",
    )
    run_parser.add_argument(
        "prompt",
        type=str,
        nargs="?",
        default=None,
        help="Natural language prompt for the research assistant",
    )
    run_parser.add_argument(
        "--subagent",
        choices=["paperscout", "paperlens"],
        default=None,
        help="Hint a specific subagent in the query (local convenience)",
    )
    run_parser.add_argument(
        "--thread-id",
        type=str,
        default=None,
        help="Thread identifier for persistence",
    )
    run_parser.add_argument(
        "--user-id",
        type=str,
        default=None,
        help="Override user identifier for storage",
    )

    # 'daemon' command with subcommands
    daemon_parser = subparsers.add_parser(
        "daemon",
        help="Daemon management commands",
    )
    daemon_subparsers = daemon_parser.add_subparsers(
        dest="daemon_command",
        title="daemon commands",
        description="Daemon management operations",
    )

    # daemon start
    daemon_subparsers.add_parser(
        "start",
        help="Start daemon in background",
    )

    # daemon stop
    daemon_subparsers.add_parser(
        "stop",
        help="Stop daemon gracefully",
    )

    # daemon restart
    daemon_subparsers.add_parser(
        "restart",
        help="Restart daemon",
    )

    # daemon status
    daemon_subparsers.add_parser(
        "status",
        help="Show daemon status",
    )

    # daemon run (foreground mode for debugging)
    daemon_subparsers.add_parser(
        "run",
        help="Run daemon in foreground (for debugging)",
    )

    # If no command provided, default to 'run'
    args = parser.parse_args()

    if args.command is None:
        # No command provided, treat positional args as prompt for 'run'
        args.command = "run"
        # Re-parse to get prompt from remaining args
        remaining = parser.parse_known_args()[1]
        if remaining:
            args.prompt = remaining[0]
        else:
            args.prompt = None
        # Add missing run command attributes
        if not hasattr(args, "subagent"):
            args.subagent = None
        if not hasattr(args, "thread_id"):
            args.thread_id = None
        if not hasattr(args, "user_id"):
            args.user_id = None

    return args


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
    cmd = [sys.executable, "-m", "alithia_agent", "daemon", "run"]
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
        time.sleep(2)

        pid = get_daemon_pid()
        if pid:
            print(f"Daemon started (PID: {pid})")
            return EXIT_SUCCESS
        else:
            print(f"Daemon failed to start. Check logs at ~/.alithia/{DEFAULT_LOG_FILE}")
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


async def run_daemon_foreground(args: argparse.Namespace) -> int:
    """Run daemon service in foreground (for debugging).

    Args:
        args: Parsed CLI arguments.

    Returns:
        Exit code.
    """
    from alithia_agent.daemon.service import DaemonService

    config_path = Path(args.config) if args.config else None

    logger.info("Daemon running in foreground mode")

    try:
        service = DaemonService(config_path=config_path)
        return await service.run()
    except Exception as e:
        logger.exception(f"Daemon failed: {e}")
        return EXIT_EXEC_ERROR


def run_daemon_status(args: argparse.Namespace) -> int:
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
        color = supports_color()
        print(bold(cyan("Alithia-Agent Daemon Status", enabled=color)))
        print(dim("=" * 40, enabled=color))

        if running:
            status_text = green("RUNNING", enabled=color)
            pid_text = yellow(str(pid), enabled=color)
            print(f"Status: {status_text} (PID: {pid_text})")
        else:
            print(f"Status: {red('NOT RUNNING', enabled=color)}")

        config = status.get("config", {})
        print()
        print(bold("Configuration:", enabled=color))

        scheduler_enabled = config.get("scheduler_enabled", False)
        enabled_text = (
            green("True", enabled=color) if scheduler_enabled else red("False", enabled=color)
        )
        schedule = config.get("schedule", "N/A")
        retry_days = config.get("retry_window_days", "N/A")
        big_bang = config.get("big_bang", "N/A")

        print(f"  {dim('Scheduler enabled:', enabled=color)} {enabled_text}")
        print(f"  {dim('Schedule:', enabled=color)} {cyan(str(schedule), enabled=color)}")
        print(
            f"  {dim('Retry window:', enabled=color)} {cyan(f'{retry_days} days', enabled=color)}"
        )
        print(f"  {dim('Big bang:', enabled=color)} {cyan(str(big_bang), enabled=color)}")

    return EXIT_SUCCESS


async def run_agent(args: argparse.Namespace) -> int:
    """Run alithia agent with user input.

    Args:
        args: Parsed CLI arguments.

    Returns:
        Exit code (0 for success, non-zero for errors).
    """
    from alithia_agent.stream import consume_stream_stdout

    agent = AlithiaAgent.create(args.config, verbose=args.verbose)

    result_stream = agent.run(
        user_input=args.prompt,
        thread_id=args.thread_id,
        subagent=args.subagent,
    )

    output_parts: list[Any] = []
    errors: list[str] = []

    async for chunk in result_stream:
        if args.output == "json":
            output_parts.append(chunk)
            continue
        if args.output == "none":
            continue
        try:
            consume_stream_stdout(chunk, verbose=args.verbose)
        except Exception as e:
            errors.append(str(e))
            if args.verbose:
                print(f"\n[ERROR] {e}")

    if args.output == "json":
        print(json.dumps(output_parts, indent=2, default=str))
    elif args.output == "stdout":
        print()

    if errors:
        logger.error("Execution completed with %d errors", len(errors))
        return EXIT_EXEC_ERROR

    return EXIT_SUCCESS


async def main_async() -> int:
    """Async main entry point."""
    args = parse_args()

    lightweight_daemon = args.command == "daemon" and getattr(args, "daemon_command", None) in (
        "start",
        "stop",
        "restart",
        "status",
    )
    setup_logging(args.verbose, args.quiet, lightweight=lightweight_daemon)

    # Handle different commands
    command = args.command

    if command == "daemon":
        # Daemon subcommands
        daemon_cmd = args.daemon_command

        if daemon_cmd == "start":
            return start_daemon(args)

        elif daemon_cmd == "stop":
            return stop_daemon(args)

        elif daemon_cmd == "restart":
            return restart_daemon(args)

        elif daemon_cmd == "status":
            return run_daemon_status(args)

        elif daemon_cmd == "run":
            # Run daemon in foreground (async)
            return await run_daemon_foreground(args)

        else:
            print("ERROR: Missing daemon subcommand")
            print("\nDaemon commands:")
            print("  alithia-agent daemon start    # Start daemon in background")
            print("  alithia-agent daemon stop     # Stop daemon")
            print("  alithia-agent daemon restart  # Restart daemon")
            print("  alithia-agent daemon status   # Show daemon status")
            print("  alithia-agent daemon run      # Run in foreground (debug)")
            return EXIT_ARG_ERROR

    elif command == "run":
        # Run agent with prompt
        if not args.prompt:
            print("ERROR: Please provide a prompt")
            print("\nExamples:")
            print("  alithia-agent 'Find new papers about transformers'")
            print("  alithia-agent 'Rank my PDFs by relevance'")
            print("  alithia-agent --subagent paperscout 'Check for new papers'")
            print("\nDaemon commands:")
            print("  alithia-agent daemon start    # Start daemon")
            print("  alithia-agent daemon stop     # Stop daemon")
            print("  alithia-agent daemon status   # Show status")
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
        # Treat as prompt for run command
        args.prompt = command
        args.subagent = None
        args.thread_id = None
        args.user_id = None

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

"""Daemon module for background paper scanning.

Provides a background process that monitors calendar-based paper scanning
using paperscout with SQLite state persistence.

Components:
- GapScanner: Detects missing notification dates
- PaperScoutScheduler: Async loop for daily paper discovery
- DaemonService: Main daemon orchestration with signal handling
"""

from alithia_agent.daemon.gap_scanner import GapScanner
from alithia_agent.daemon.scheduler import PaperScoutScheduler
from alithia_agent.daemon.service import DaemonService

__all__ = [
    "GapScanner",
    "PaperScoutScheduler",
    "DaemonService",
]

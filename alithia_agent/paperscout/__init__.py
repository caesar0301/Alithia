"""PaperScout subagent for ArXiv paper discovery and email notifications.

A soothe framework subagent that:
1. Validates Zotero/SMTP configuration
2. Fetches papers from ArXiv API
3. Analyzes user's Zotero library for relevance profiling
4. Ranks papers using FastEmbed embeddings
5. Sends email digest notifications
"""

from alithia_agent.paperscout.implementation import create_paperscout_subagent
from alithia_agent.paperscout.runner import PaperScoutRunResult, run_paperscout_for_dates
from alithia_agent.paperscout.state import (
    AgentState,
    PaperScoutConfig,  # Legacy alias
    PaperScoutRuntimeConfig,
    SmtpConfig,  # Legacy alias
    SmtpRuntimeConfig,
    ZoteroConfig,  # Legacy alias
    ZoteroRuntimeConfig,
    build_runtime_config,
)

__all__ = [
    "create_paperscout_subagent",
    "PaperScoutRunResult",
    "run_paperscout_for_dates",
    "PaperScoutRuntimeConfig",
    "PaperScoutConfig",
    "SmtpRuntimeConfig",
    "SmtpConfig",
    "ZoteroRuntimeConfig",
    "ZoteroConfig",
    "AgentState",
    "build_runtime_config",
]

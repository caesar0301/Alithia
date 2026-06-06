"""PaperScout subagent for ArXiv paper discovery and email notifications.

A soothe framework subagent that:
1. Validates Zotero/SMTP configuration
2. Fetches papers from ArXiv API
3. Analyzes user's Zotero library for relevance profiling
4. Ranks papers using sentence embeddings
5. Sends email digest notifications
"""

from alithia_agent.paperscout.implementation import create_paperscout_subagent
from alithia_agent.paperscout.state import (
    PaperScoutConfig,
    SmtpConfig,
    ZoteroConfig,
    AgentState,
)

__all__ = [
    "create_paperscout_subagent",
    "PaperScoutConfig",
    "SmtpConfig",
    "ZoteroConfig",
    "AgentState",
]
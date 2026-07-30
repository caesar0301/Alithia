"""Research interests knowledge base (RFC-010).

Public API:
    ResearchInterest            -- one knowledge unit (parsed from a .md file).
    load_research_interests     -- scan a directory of *.md into units.
    sync_zotero_to_markdown     -- normalize a Zotero library into *.md.
    SyncResult                  -- outcome of a Zotero sync.

Interests are the primary, human-editable knowledge source for PaperScout
matching. Zotero is an optional contributor that, when configured, is synced
into the same Markdown format at startup and unified with hand-written
interests into one corpus the reranker scores against. See RFC-010.
"""

from alithia.research_interests.loader import load_research_interests
from alithia.research_interests.model import ResearchInterest
from alithia.research_interests.zotero_sync import SyncResult, sync_zotero_to_markdown

__all__ = [
    "ResearchInterest",
    "load_research_interests",
    "sync_zotero_to_markdown",
    "SyncResult",
]

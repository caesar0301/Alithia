"""Example: Run PaperScout workflow to fetch and email ArXiv paper digest.

This example demonstrates the complete PaperScout workflow:
1. Load configuration from ~/.alithia/config.yml
2. Fetch papers from ArXiv API (multiple categories)
3. Analyze user's Zotero library for relevance profiling
4. Rank papers using FastEmbed embeddings (or keyword fallback)
5. Send HTML email digest via SMTP

Usage:
    uv run python examples/run_paperscout_digest.py

Customization:
    Modify the parameters below to adjust:
    - LOOKBACK_DAYS: How many days to look back for papers
    - MAX_PAPERS: Maximum papers to include in digest
    - MAX_QUERIED: Maximum papers to query from each ArXiv category

Requirements:
    - Valid ~/.alithia/config.yml with:
        - Zotero API credentials (zotero_id, zotero_key)
        - SMTP credentials (smtp_server, smtp_port, sender, sender_password)
        - LLM API credentials (optional, for enhanced TLDR generation)

Environment:
    The script uses a mock store (no persistence) for demonstration.
    In production, use the PostgreSQL store from alithia.storage.
"""

import asyncio
import logging
import sys
from pathlib import Path

# Add project root to path (before local imports)  # noqa: E402
sys.path.insert(0, str(Path(__file__).parent.parent))  # noqa: E402

from alithia.config import load_config
from alithia.paperscout.implementation import create_paperscout_graph
from alithia.paperscout.state import AgentState, PaperScoutRuntimeConfig

# Configuration parameters (adjust as needed)
LOOKBACK_DAYS = 7  # Days to look back for new papers
MAX_PAPERS = 10  # Maximum papers to include in digest
MAX_QUERIED = 100  # Maximum papers to query from each category

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)s %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


class MockStore:
    """In-memory mock store for demonstration (no persistence).

    In production, use AsyncPersistStore from alithia.storage
    for PostgreSQL-backed persistence with exactly-once semantics.
    """

    def __init__(self):
        self._data: dict[str, any] = {}

    async def load(self, key: str):
        """Load data from store."""
        return self._data.get(key)

    async def save(self, key: str, data):
        """Save data to store."""
        self._data[key] = data
        logger.debug(f"MockStore: saved {key}")


async def run_paperscout_digest():
    """Execute PaperScout workflow and send email digest."""
    # Load configuration
    config_path = str(Path.home() / ".alithia" / "config.yml")
    logger.info(f"Loading config from {config_path}")

    config = load_config(config_path)
    runtime_config = PaperScoutRuntimeConfig.build_runtime_config(config)

    # Override parameters for this example
    runtime_config.lookback_days = LOOKBACK_DAYS
    runtime_config.max_papers = MAX_PAPERS
    runtime_config.max_papers_queried = MAX_QUERIED

    logger.info("=" * 60)
    logger.info("PaperScout Configuration")
    logger.info("=" * 60)
    logger.info(f"ArXiv categories: {runtime_config.arxiv_categories}")
    logger.info(f"Max papers in digest: {runtime_config.max_papers}")
    logger.info(f"Max papers queried: {runtime_config.max_papers_queried}")
    logger.info(f"Lookback period: {runtime_config.lookback_days} days")
    logger.info(f"Send email: {runtime_config.send_email}")
    logger.info(f"Recipient: {runtime_config.recipient_email}")
    logger.info("=" * 60)

    # Create workflow graph
    store = MockStore()
    graph = create_paperscout_graph(store, user_id="example_user", config=runtime_config)
    compiled = graph.compile()

    # Initialize workflow state
    initial_state: AgentState = {
        "messages": [],
        "config": runtime_config,
        "user_id": "example_user",
        "discovered_papers": [],
        "zotero_papers": [],
        "scored_papers": [],
        "email_content": None,
        "errors": [],
        "info": [],
        "metrics": {},
    }

    # Execute workflow
    logger.info("Starting PaperScout workflow...")
    logger.info("")

    result = await compiled.ainvoke(initial_state)

    # Print results
    logger.info("")
    logger.info("=" * 60)
    logger.info("Workflow Results")
    logger.info("=" * 60)

    # Check for errors
    errors = result.get("errors", [])
    if errors:
        logger.error(f"Errors encountered: {errors}")
        return result

    # Print metrics
    metrics = result.get("metrics", {})
    logger.info(f"Source: {metrics.get('source', 'unknown')}")
    logger.info(f"ArXiv papers found: {metrics.get('arxiv_found', 0)}")
    logger.info(f"New papers (not emailed before): {metrics.get('arxiv_new', 0)}")
    logger.info(f"Zotero corpus size: {metrics.get('zotero_corpus', 0)}")
    logger.info(f"Papers scored: {metrics.get('papers_scored', 0)}")
    logger.info(f"Papers selected for digest: {metrics.get('papers_selected', 0)}")
    if metrics.get("avg_score"):
        logger.info(f"Average score: {metrics.get('avg_score', 0):.2f}")

    # Check email status
    if metrics.get("email_sent"):
        logger.info("")
        logger.info(f"✅ Email sent to: {metrics.get('recipient', 'unknown')}")

        email = result.get("email_content")
        if email:
            logger.info(f"   Subject: {email.subject}")
            logger.info(f"   Papers: {len(email.papers)}")
    else:
        logger.info("")
        logger.info("No email sent (either disabled or no papers found)")

    # Print top papers
    scored = result.get("scored_papers", [])
    if scored:
        logger.info("")
        logger.info("=" * 60)
        logger.info("Top Papers in Digest")
        logger.info("=" * 60)
        for i, sp in enumerate(scored, 1):
            title = sp.paper.title[:60] + "..." if len(sp.paper.title) > 60 else sp.paper.title
            logger.info(f"{i:2d}. [{sp.score:.1f}] {title}")
            if hasattr(sp.paper, "arxiv_id"):
                logger.info(f"    arXiv: {sp.paper.arxiv_id}")

    logger.info("")
    logger.info("=" * 60)
    logger.info("Workflow completed successfully!")
    logger.info("=" * 60)

    return result


if __name__ == "__main__":
    asyncio.run(run_paperscout_digest())

"""
Constants and default values for the Alithia research companion.

This module centralizes all default configuration values used throughout the application.
"""

# ===========================
# PaperScout Agent Defaults
# ===========================

# Maximum number of papers to include in final recommendations
ALITHIA_MAX_PAPERS = 25

# Maximum number of papers to query from ArXiv API
ALITHIA_MAX_PAPERS_QUERIED = 500

# Default ArXiv query categories
DEFAULT_ARXIV_QUERY = "cs.AI+cs.CV+cs.LG+cs.CL"

# Whether to send email notification after discovering papers
DEFAULT_SEND_EMAIL = True

# Whether to send email when no papers are found
DEFAULT_SEND_EMPTY = False


# ===========================
# ArXiv Fetcher Defaults
# ===========================

# Default maximum results for ArXiv API queries
DEFAULT_ARXIV_MAX_RESULTS = 500

# Default retry settings for ArXiv fetcher
DEFAULT_MAX_RETRIES = 3
DEFAULT_RETRY_DELAY = 1.0  # seconds
DEFAULT_REQUEST_TIMEOUT = 30  # seconds

# Batch size for fetching paper details from ArXiv
ARXIV_BATCH_SIZE = 50

# ArXiv page size for web scraping
ARXIV_PAGE_SIZE = 50


# ===========================
# PaperLens Agent Defaults
# ===========================

# Default sentence transformer model
DEFAULT_SBERT_MODEL = "all-MiniLM-L6-v2"

# Default number of top papers to display
DEFAULT_TOP_N = 10


# ===========================
# Storage Defaults
# ===========================

# Default SQLite database path
DEFAULT_SQLITE_PATH = "data/alithia.db"

# Default query history limit
DEFAULT_QUERY_HISTORY_LIMIT = 50


# ===========================
# Email Defaults
# ===========================

# Default SMTP port
DEFAULT_SMTP_PORT = 587


# ===========================
# Debug Settings
# ===========================

# Number of papers to limit in debug mode
DEBUG_MAX_PAPERS = 5

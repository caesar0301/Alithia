<div align="center">
  <img src="docs/logos/alithia-logo.jpg" alt="Alithia Logo" width="200" />
</div>

# Alithia Research Companion

[![PyPI version](https://img.shields.io/pypi/v/alithia.svg)](https://pypi.org/project/alithia/)

![Alithia Overview](docs/screenshots/ss-overview.jpg)

**Time**, is one of the most valuable resources for a human researcher, best spent
on thinking, exploring, and creating in the world of ideas. With Alithia, we
aim to open a new frontier in research assistance. Alithia aspires to be your
powerful research companion: from reading papers to pursuing interest-driven
deep investigations, from reproducing experiments to detecting fabricated
results, from tracking down relevant papers to monitoring industrial
breakthroughs. At its core, Alithia forges a strong and instant link between your personal
research profile, the latest state-of-the-art developments, and pervasive cloud
resources, ensuring you stay informed, empowered, and ahead.

## Features

Alithia connects your personal research profile with publicly available academic resources, leveraging cloud infrastructure to automate the research workflow.

### AI Agents

* **PaperScout** — Personalized ArXiv paper recommendations delivered via email
  * Analyzes your Zotero library to understand research interests
  * Monitors ArXiv for new papers matching your profile
  * Ranks papers by relevance using embeddings + LLM
  * Sends daily curated digests with TLDR summaries

* **PaperLens** — Deep paper interaction and analysis
  * Parses PDFs using Docling with IBM Granite VLM
  * Extracts text, figures, tables, and equations
  * Semantic search across your paper collection
  * Interactive Q&A for paper exploration

### Researcher Profile

* Research interests, expertise, and preferences
* Connected services:
  * LLM (OpenAI compatible APIs)
  * Zotero personal library
  * Email notifications (SMTP)
  * GitHub profile
  * Google Scholar profile
* Gems — Save and organize research ideas and digests

### Academic Data Sources

* **arXiv** — Latest papers from cs.AI, cs.CV, cs.LG, and more
* **Google Scholar** — Profile sync and publication tracking
* **Web search** — Tavily and other search engines
* **Researcher homepages** — Automated discovery

## Usage

### Docker (Recommended)

The easiest way to run Alithia is using Docker:

```bash
docker pull ghcr.io/caesar0301/alithia:latest
```

Run the dashboard:

```bash
docker run -d -p 8080:8080 \
  -v $(pwd)/alithia_config.json:/app/config.json \
  ghcr.io/caesar0301/alithia:latest \
  python -m alithia.run dashboard --config /app/config.json
```

### Running from Source

#### Installation

Alithia uses optional dependencies to keep the base installation lightweight. The default installation includes PaperScout agent dependencies.

**Recommended: Default Installation**

For most users, install with default dependencies (includes PaperScout agent: ArXiv fetching, Zotero integration, email notifications, etc.):

```bash
pip install alithia[default]
```

**Optional Features:**

Install with PaperLens support (PDF analysis and deep paper interaction):

```bash
pip install alithia[docling]
```

Install all features:

```bash
pip install alithia[all]
```

#### Configuration

Create a JSON configuration with your credentials. See [alithia_config_example.json](alithia_config_example.json) for a complete example.

#### Running the Dashboard

Production mode:

```bash
python -m alithia.run dashboard --config alithia_config.json
```

Open http://localhost:8080 in your browser.

Development mode (with auto-reload):

```bash
python -m alithia.run dashboard --config alithia_config.json --dev
```

For frontend development, see [DEVELOPMENT.md](DEVELOPMENT.md).

## Storage Backend

Alithia supports three storage backends for persistent data storage with automatic fallback support. By default, **SQLite** is used for local development, while **Supabase** or **PostgreSQL** can be configured for production use. This enables:

- **Persistent caching** of Zotero libraries and parsed papers
- **Continuous paper feeding** that handles ArXiv indexing delays
- **Deduplication** to prevent duplicate email notifications
- **Query history** tracking for PaperLens interactions
- **Google Scholar profile synchronization**
- **Dashboard background task management**

### Supported Backends

| Backend | Description | Use Case |
|---------|-------------|----------|
| **SQLite** | Local file-based (default) | Works offline, no setup |
| **Supabase** | Cloud PostgreSQL | Multi-user, full-text search |
| **PostgreSQL** | Self-hosted | Full infrastructure control |

### Configuration

**SQLite (default)** — No config needed:

```json
{
  "storage": {
    "backend": "sqlite",
    "user_id": "your_email@example.com"
  }
}
```

**Supabase:**

```json
{
  "storage": {
    "backend": "supabase",
    "user_id": "your_email@example.com",
    "supabase": {
      "url": "https://xxxxx.supabase.co",
      "service_role_key": "your_key"
    }
  }
}
```

**PostgreSQL:**

```json
{
  "storage": {
    "backend": "postgres",
    "user_id": "you@example.com",
    "postgres": {
      "dsn": "postgresql://user:pass@host:5432/db"
    }
  }
}
```

See [docs/STORAGE_SETUP.md](docs/STORAGE_SETUP.md) for storage details.

## Development

For development setup, contributing guidelines, and building the frontend, see [DEVELOPMENT.md](DEVELOPMENT.md).

## License

MIT

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests
5. Submit a pull request

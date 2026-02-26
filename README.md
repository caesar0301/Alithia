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

In Alithia, we connect each researcher's profile with publicly available academic resources, leveraging widely accessible cloud infrastructure to automate the entire process. In its current version, Alithia is designed to support the following features:

* Researcher Profile
  * Basic profile: research interests, expertise, language
  * Connected (personal) services:
    * LLM (OpenAI compatible)
    * Zotero library
    * Email notification
    * GitHub profile
    * Google Scholar profile
    * X account message stream
  * Gems (general research digest or ideas)
* Academic Resources
  * arXiv papers
  * Google Scholar search
  * Web search engines (e.g., tavily)
  * Individual researcher homepage

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

This installs:
- `arxiv` - ArXiv paper fetching
- `pyzotero` - Zotero library integration
- `scikit-learn` - Machine learning utilities
- `sentence-transformers` - Embedding models
- `feedparser` - RSS feed parsing
- `beautifulsoup4` & `lxml` - Web scraping
- `tiktoken` - Token counting
- And other PaperScout dependencies

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
| **SQLite** | Local file-based database | Default, works offline, no setup required |
| **Supabase** | Cloud PostgreSQL service | Multi-user, automatic backups, full-text search |
| **PostgreSQL** | Self-hosted PostgreSQL | Full control over database infrastructure |

### Configuration

Configure storage in your config file:

```json
{
  "storage": {
    "backend": "supabase",
    "fallback_to_sqlite": true,
    "user_id": "your_email@example.com",
    "sqlite_path": "data/alithia.db"
  }
}
```

**Options:**
- `backend`: `"sqlite"`, `"supabase"`, or `"postgres"`
- `fallback_to_sqlite`: Auto-fallback to SQLite if primary backend fails (default: `true`)
- `user_id`: User identifier for data isolation
- `sqlite_path`: Path for SQLite database (default: `"data/alithia.db"`)

#### Supabase Configuration

```json
{
  "storage": {
    "backend": "supabase",
    "user_id": "your_email@example.com"
  },
  "supabase": {
    "url": "https://xxxxx.supabase.co",
    "service_role_key": "your_service_role_key"
  }
}
```

#### PostgreSQL Configuration

```json
{
  "storage": {
    "backend": "postgres",
    "user_id": "your_email@example.com"
  },
  "postgres": {
    "dsn": "postgresql://user:password@host:port/database"
  }
}
```

Or use individual fields:

```json
{
  "postgres": {
    "host": "localhost",
    "port": 5432,
    "user": "postgres",
    "password": "password",
    "database": "alithia"
  }
}
```

### Database Migrations

Run all migration files in order to set up your database schema:

1. `alithia/storage/migrations/001_initial_schema.sql` - Core schema (Paperscout, PaperLens)
2. `alithia/storage/migrations/002_paperscout_v2.sql` - PaperScout v2 enhancements
3. `alithia/storage/migrations/003_sync_service.sql` - Google Scholar sync tables
4. `alithia/storage/migrations/004_dashboard.sql` - Dashboard task tracking

**For Supabase:** Copy each migration file's contents to the Supabase SQL Editor and run in order.

**For PostgreSQL:** Run with `psql`:

```bash
psql -U postgres -d alithia -f alithia/storage/migrations/001_initial_schema.sql
psql -U postgres -d alithia -f alithia/storage/migrations/002_paperscout_v2.sql
psql -U postgres -d alithia -f alithia/storage/migrations/003_sync_service.sql
psql -U postgres -d alithia -f alithia/storage/migrations/004_dashboard.sql
```

**SQLite** is auto-initialized on first run with the current schema.

For detailed Supabase setup instructions, see [docs/SUPABASE_SETUP.md](docs/SUPABASE_SETUP.md).

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

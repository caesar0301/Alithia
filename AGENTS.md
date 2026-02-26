# Alithia Research Assistant

## Project Overview

Alithia is a **multi-agent, AI-powered research companion** designed to cover the entire academic workflow — from **monitoring** new developments, to **recommending** relevant papers, to **deeply understanding** and interacting with them. The project is modular, extensible, and future-proof, with each agent performing a specialized role while sharing a common embedding-based knowledge store and user interest profile.

## Architecture

### Core Components

- **Config Loader**: Loads user API keys, preferences, scheduling options
- **Researcher Profile**: User research interests, expertise, and connected services
- **Storage Backend**: Multi-backend storage system (SQLite, Supabase, PostgreSQL) for persistent caching
- **Sync Service**: Orchestrates synchronization of academic profiles (Zotero, Google Scholar, GitHub)
- **Dashboard**: Web interface for managing profiles, viewing papers, and interacting with agents
- **Common Utils**: PDF parsing, LLM integration, rate-limit handling

### Agent System

The project currently implements two main agents:

1. **PaperScout** - Personalized ArXiv Recommendation Agent ✅ **Implemented**
2. **PaperLens** - Deep Paper Interaction Agent ✅ **Implemented**

**Planned Agents:**
3. **Pulse** - Proactive Topic Monitoring Agent (planned)

## Current Implementation Status

### ✅ **Available Now**
- **PaperScout**: Fully functional ArXiv recommendation system with email notifications
- **PaperLens**: Complete PDF analysis and semantic search tool with IBM Granite VLM
- **Researcher Profile**: User profile management with connected services
- **Storage Backend**: Multi-backend support (SQLite, Supabase, PostgreSQL) with automatic fallback
- **Sync Service**: Google Scholar profile synchronization
- **Dashboard**: Web interface for research management
- **Testing Suite**: Comprehensive unit and integration tests

### 🚧 **In Development/Planned**
- **Pulse**: Topic monitoring agent (not yet implemented)
- **Additional Sync Connectors**: More academic profile integrations
- **Advanced Features**: Multi-language, collaborative mode, offline support

## Project Structure

```
alithia/
├── config_loader.py       # Configuration management
├── constants.py           # Application constants
├── dashboard/             # Web dashboard (FastAPI + WebSocket)
│   ├── app.py            # FastAPI application
│   ├── agent_dispatcher.py
│   ├── scheduler.py      # Task scheduling
│   ├── task_manager.py   # Background task management
│   ├── websocket_hub.py  # WebSocket communication
│   └── routers/          # API route handlers
├── models/                # Shared data models
├── paperlens/             # PaperLens agent ✅ IMPLEMENTED
│   ├── engine.py         # Core PDF processing engine
│   ├── models.py         # Paper data models
│   └── paper_ocr/        # PDF parsing with Docling
├── paperscout/            # PaperScout agent ✅ IMPLEMENTED
│   ├── agent.py          # Main agent logic
│   ├── arxiv_paper.py    # ArXiv paper data models
│   ├── email_utils.py    # Email functionality
│   ├── models.py         # Core data models
│   ├── nodes.py          # LangGraph workflow nodes
│   ├── reranker.py       # Paper ranking algorithms
│   └── state.py          # Agent state management
├── researcher/            # Researcher profile management
│   └── profile.py        # Researcher profile models
├── run/                   # Main entrypoint
│   └── __main__.py       # CLI: python -m alithia.run
├── storage/               # Storage backend system
│   ├── base.py           # Abstract storage interface
│   ├── factory.py        # Storage backend factory
│   ├── sqlite.py         # SQLite implementation
│   ├── supabase.py       # Supabase implementation
│   ├── postgres.py       # PostgreSQL implementation
│   └── migrations/       # Database migration files
├── sync/                  # Sync service
│   ├── base.py           # Base sync connector
│   ├── orchestrator.py   # Sync orchestration
│   └── connectors/       # Platform-specific connectors
│       ├── zotero.py     # Zotero connector
│       └── scholar.py    # Google Scholar connector
└── utils/                 # Shared utilities
    ├── llm_utils.py      # LLM integration helpers
    └── zotero_client.py  # Zotero API client
```

**Note**: Pulse agent is not yet implemented - it exists only in the documentation as a planned feature.

## Key Technologies

- **Web Framework**: FastAPI for dashboard backend
- **Orchestration**: LangGraph for agent workflows
- **PDF Processing**: Docling with IBM Granite Docling 258M VLM model
- **Embeddings**: Sentence Transformers (all-MiniLM-L6-v2 by default)
- **LLM Integration**: cogents-core for standardized LLM interface
- **Email**: SMTP for notifications
- **Data Sources**: ArXiv, Zotero, Google Scholar
- **Storage**: SQLite, Supabase, PostgreSQL with automatic fallback
- **Frontend**: React with Vite (dashboard-frontend/)

## Storage Backend

Alithia supports three storage backends for persistent data:

| Backend | Description | Use Case |
|---------|-------------|----------|
| **SQLite** | Local file-based database | Default, works offline, no setup required |
| **Supabase** | Cloud PostgreSQL service | Multi-user, automatic backups, full-text search |
| **PostgreSQL** | Self-hosted PostgreSQL | Full control over database infrastructure |

### Storage Features

- **Persistent caching** of Zotero libraries and parsed papers
- **Continuous paper feeding** that handles ArXiv indexing delays
- **Deduplication** to prevent duplicate email notifications
- **Query history** tracking for PaperLens interactions
- **Google Scholar profile synchronization**
- **Dashboard background task management

### Database Schema

The storage system uses migrations to manage schema evolution:

1. **001_initial_schema.sql** - Core schema for Paperscout and PaperLens
   - `zotero_papers`: Cache of user's Zotero library papers
   - `arxiv_processed_ranges`: Tracks processed ArXiv date ranges
   - `arxiv_papers_emailed`: Deduplication table for email notifications
   - `parsed_papers`: Cache of parsed PDF papers
   - `query_history`: User query history for PaperLens interactions

2. **002_paperscout_v2.sql** - PaperScout v2 enhancements
   - `assessed_papers`: Stores papers with relevance scores
   - `notification_records`: Ensures exactly-once email delivery

3. **003_sync_service.sql** - Sync service tables
   - `scholar_profiles`: Google Scholar profile data
   - `scholar_publications`: Google Scholar publication records
   - `sync_log`: Records of sync operations

4. **004_dashboard.sql** - Dashboard functionality
   - `background_tasks`: Background task tracking for the dashboard

## Configuration

### Environment Variables

The project uses a JSON configuration system. Key configuration areas:

```json
{
  "storage": {
    "backend": "sqlite",
    "fallback_to_sqlite": true,
    "user_id": "your_email@example.com"
  },
  "zotero": {
    "user_id": "your_zotero_user_id",
    "api_key": "your_zotero_api_key"
  },
  "llm": {
    "api_key": "your_api_key",
    "base_url": "https://api.openai.com/v1",
    "model": "gpt-4o-mini"
  },
  "email": {
    "smtp_server": "smtp.gmail.com",
    "smtp_port": 587,
    "username": "your_email@gmail.com",
    "password": "your_app_password"
  },
  "paperscout": {
    "query": "cs.AI+cs.CV+cs.LG+cs.CL",
    "max_papers": 50,
    "send_empty": false
  }
}
```

### Supabase Configuration

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

### PostgreSQL Configuration

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

## Agent Workflows

### PaperScout Workflow ✅ **Implemented**

1. **Profile Analysis**: Extract research interests from Zotero library
2. **Data Collection**: Fetch papers from ArXiv RSS feed
3. **Relevance Assessment**: Score papers using sentence embeddings
4. **Content Generation**: Generate TLDR summaries using LLM
5. **Communication**: Send email with recommendations

**CLI Usage**: `python -m alithia.run paperscout --config alithia_config.json`

**GitHub Actions**: Runs automatically daily at 01:00 UTC

### PaperLens Workflow ✅ **Implemented**

1. **PDF Parsing**: Extract structured content using Docling with IBM Granite VLM
2. **Content Analysis**: Process text, figures, tables, equations with multimodal understanding
3. **Semantic Search**: Find relevant sections using embeddings
4. **Interactive Q&A**: Provide conversational interface for paper exploration

**CLI Usage**: `python -m alithia.run paperlens --config alithia_config.json --query "your question" --pdfs ./papers`

### Pulse Workflow ❌ **Not Implemented**

*This agent is planned but not yet implemented in the current codebase.*

## Dashboard

Alithia provides a web dashboard for managing your research profile, viewing papers, and interacting with agents.

### Features

- **Profile Management**: Configure research interests and connected services
- **Paper Browser**: View and search through cached papers
- **Agent Control**: Trigger and monitor agent runs
- **Task Management**: View background task status and progress
- **Real-time Updates**: WebSocket-based live updates

### Running the Dashboard

**Production mode:**

```bash
python -m alithia.run dashboard --config alithia_config.json
```

**Development mode (with auto-reload):**

```bash
python -m alithia.run dashboard --config alithia_config.json --dev
```

Open http://localhost:8080 in your browser.

For frontend development, see [DEVELOPMENT.md](DEVELOPMENT.md).

## Data Models

### Core Models

- **AcademicPaper**: Complete paper representation with metadata and content
- **PaperMetadata**: Title, authors, abstract, DOI, publication info
- **PaperContent**: Full text and structured content
- **FileMetadata**: File system information (path, size, hash)

### Agent-Specific Models

- **ArxivPaper**: ArXiv-specific paper data with TLDR generation
- **ScoredPaper**: Paper with relevance scoring
- **ResearcherProfile**: User research interests and preferences

## API Integration

### ArXiv Integration

- **RSS Feed**: Fetches latest papers from specified categories
- **Metadata Extraction**: Parses paper information from ArXiv entries
- **PDF Download**: Retrieves paper PDFs for processing

### Zotero Integration

- **Library Sync**: Retrieves user's paper collection
- **Interest Profiling**: Analyzes library to determine research interests
- **Pattern Matching**: Applies ignore patterns for filtering

### Google Scholar Integration

- **Profile Sync**: Fetches researcher profile data
- **Publication Tracking**: Monitors publication history
- **Citation Analysis**: Tracks citation metrics

### LLM Integration

- **cogents-core**: Standardized LLM interface
- **Multiple Providers**: OpenAI, OpenRouter, local models
- **Rate Limiting**: Built-in handling for API limits

## Development Guidelines

### Code Structure

- **Modular Design**: Each agent is self-contained with clear interfaces
- **State Management**: Centralized state using LangGraph StateGraph
- **Error Handling**: Comprehensive error logging and graceful degradation
- **Testing**: Unit and integration tests for each component

### Adding New Features

1. **Identify Agent**: Determine which agent should handle the feature
2. **Create Node**: Add new LangGraph node if needed
3. **Update State**: Modify state models if required
4. **Add Tests**: Create comprehensive test coverage
5. **Update Documentation**: Document new functionality

### Common Patterns

- **Configuration**: Use `load_config()` for all configuration needs
- **Logging**: Use standard logging for consistent logging
- **Error Handling**: Wrap operations in try-catch with proper error reporting
- **Data Models**: Use dataclasses for structured data representation

## Testing

### Running Tests

```bash
# Unit tests
pytest tests/unit/

# Integration tests
pytest tests/integration/

# All tests
pytest

# Specific test file
pytest tests/unit/test_paper_models.py
```

### Test Structure

- **Unit Tests**: Test individual components in isolation
- **Integration Tests**: Test agent workflows end-to-end
- **Mocking**: Use mocks for external API calls

## Deployment

### GitHub Actions

The project uses GitHub Actions for automated deployment:

- **Daily Papers**: Runs ArXiv recommendations daily at 01:00 UTC
- **Configuration**: Uses repository secrets for sensitive data
- **Email Delivery**: Sends results via configured SMTP

### Local Development

```bash
# Install dependencies
pip install -e ".[default,dev]"

# Run PaperScout agent
python -m alithia.run paperscout --config alithia_config.json

# Run PaperLens
python -m alithia.run paperlens --config alithia_config.json --query "your question" --pdfs ./papers

# Run Dashboard
python -m alithia.run dashboard --config alithia_config.json

# Run tests
pytest
```

**Note**: Pulse agent is not available for local development as it's not yet implemented.

### Docker Support

```bash
# Pull the image
docker pull ghcr.io/caesar0301/alithia:latest

# Run the dashboard
docker run -d -p 8080:8080 \
  -v $(pwd)/alithia_config.json:/app/config.json \
  ghcr.io/caesar0301/alithia:latest \
  python -m alithia.run dashboard --config /app/config.json
```

## Troubleshooting

### Common Issues

1. **Configuration Errors**: Check JSON syntax and required fields
2. **API Limits**: Monitor rate limiting and implement backoff
3. **PDF Parsing**: Verify docling installation and IBM Granite model availability
4. **Email Delivery**: Check SMTP credentials and firewall settings
5. **Storage Issues**: Check database connection and migration status

### Debug Mode

Enable debug logging by setting appropriate log levels in configuration.

## Performance Considerations

### PDF Processing

- **IBM Granite VLM**: Optimized for multimodal document understanding
- **Batch Processing**: Efficient processing of multiple PDFs
- **Memory Management**: Proper cleanup of large documents

### Embedding Generation

- **Sentence Transformers**: Fast and efficient embedding generation
- **Batch Processing**: Process multiple texts simultaneously
- **Caching**: Storage backend caches embeddings for repeated queries

## Future Roadmap

### Currently Implemented ✅

- **PaperScout**: Personalized ArXiv recommendation agent
- **PaperLens**: Deep paper interaction and analysis agent
- **IBM Granite VLM**: Optimized PDF parsing with multimodal understanding
- **LangGraph Integration**: Agent workflow orchestration
- **Storage Backend**: Multi-backend support (SQLite, Supabase, PostgreSQL)
- **Sync Service**: Google Scholar profile synchronization
- **Dashboard**: Web interface for research management
- **Comprehensive Testing**: Unit and integration test suites

### Planned Features 🚧

- **Pulse**: Proactive topic monitoring agent (not yet implemented)
- **Additional Sync Connectors**: More academic profile integrations
- **Multi-language Support**: International paper processing
- **Collaborative Mode**: Share digests with research groups
- **Offline Mode**: Local LLM and embedding support

### Extension Points

- **New Data Sources**: Add support for additional academic databases
- **Custom Models**: Integrate specialized models for specific domains
- **Workflow Customization**: Allow users to define custom agent workflows
- **API Endpoints**: REST API for external integrations

## Contributing

### Development Setup

1. Fork the repository
2. Create a feature branch
3. Install dependencies with `pip install -e ".[default,dev]"`
4. Make changes with proper testing
5. Submit a pull request

### Code Standards

- **Python**: Follow PEP 8 and use Black for formatting
- **Type Hints**: Use type annotations for all functions
- **Documentation**: Update docstrings and README files
- **Testing**: Maintain test coverage above 80%
- **Comments & Logging**: Keep sharp and brief - avoid redundancy, remove obvious explanations, use concise language
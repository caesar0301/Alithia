# Alithia Research Assistant

## Project Overview

Alithia is a **multi-agent, AI-powered research companion** designed to cover the entire academic workflow — from **monitoring** new developments, to **recommending** relevant papers, to **deeply understanding** and interacting with them. The project is modular, extensible, and future-proof, with each agent performing a specialized role while sharing a common embedding-based knowledge store and user interest profile.

## Architecture

### Core Components

- **Config Manager**: Loads user API keys, preferences, scheduling options
- **Vector Store**: Centralized database for embeddings of papers and user interest profiles
- **Interest Model**: Dynamically updated from Zotero sync, Lens conversation history, and Pulse topic interactions
- **LangGraph Orchestration**: Manages modular workflows for each agent
- **Common Utils**: PDF parsing, diagram OCR, summarization, rate-limit handling

### Agent System

The project currently implements two main agents:

1. **AlithiaPaperScout** - Personalized ArXiv Recommendation Agent ✅ **Implemented**
2. **AlithiaLens** - Deep Paper Interaction Agent (PaperLens) ✅ **Implemented**

**Planned Agents:**
3. **AlithiaPulse** - Proactive Topic Monitoring Agent (planned)

## Current Implementation Status

### ✅ **Available Now**
- **AlithiaPaperScout**: Fully functional ArXiv recommendation system
- **AlithiaLens**: Complete PDF analysis and semantic search tool
- **Core Infrastructure**: Configuration, researcher profiles, utilities
- **Testing Suite**: Comprehensive unit and integration tests

### 🚧 **In Development/Planned**
- **AlithiaPulse**: Topic monitoring agent (not yet implemented)
- **Vector Store Integration**: Pinecone/Weaviate support
- **Advanced Features**: Multi-language, collaborative mode, offline support

## Project Structure

```
alithia/
├── core/                    # Shared infrastructure
│   ├── config_loader.py     # Configuration management
│   └── researcher/          # Researcher profile management
│       ├── connection.py    # Database connections
│       └── profile.py       # Researcher profile models
├── run/                    # Main entrypoint
│   └── __main__.py         # CLI: python -m alithia.run
├── paperscout/                  # AlithiaPaperScout agent ✅ IMPLEMENTED
│   ├── agent.py            # Main agent logic
│   ├── arxiv_paper.py      # ArXiv paper data models
│   ├── email_utils.py      # Email functionality
│   ├── models.py           # Core data models
│   ├── nodes.py            # LangGraph workflow nodes
│   ├── reranker.py         # Paper ranking algorithms
│   └── state.py            # Agent state management
├── paperlens/              # AlithiaLens agent ✅ IMPLEMENTED
│   ├── engine.py           # Core PDF processing engine
│   ├── models.py           # Paper data models
│   └── README.md           # Detailed documentation
├── utils/                  # Shared utilities
│   ├── llm_utils.py        # LLM integration helpers
│   └── zotero_client.py    # Zotero API client
└── tests/                  # Comprehensive test suite
    ├── integration/        # End-to-end tests
    └── unit/              # Unit tests
```

**Note**: Pulse agent is not yet implemented - it exists only in the documentation as a planned feature.

## Key Technologies

- **Orchestration**: LangGraph for agent workflows
- **PDF Processing**: Docling with IBM Granite Docling 258M VLM model
- **Embeddings**: Sentence Transformers (all-MiniLM-L6-v2 by default)
- **LLM Integration**: cogents-core for standardized LLM interface
- **Email**: SMTP for notifications
- **Data Sources**: ArXiv, Zotero, Google Scholar
- **Vector Storage**: Pinecone/Weaviate (planned)
- **Package Management**: pip with pyenv-managed Python

## Recent Updates

### PaperLens Engine Optimization (Latest)

The PaperLens engine has been optimized to use **IBM Granite Docling 258M VLM model** for enhanced PDF parsing:

- **Model**: `ibm-granite/granite-docling-258M`
- **Configuration**: Uses `VlmPipelineOptions` with `vlm_model="granite_docling"`
- **Purpose**: Enhanced PDF parsing with better layout understanding and multimodal analysis
- **Integration**: Properly configured via post-initialization pipeline options setting
- **Fallback**: Gracefully falls back to default docling settings if VLM pipeline is unavailable

### Project Structure Improvements

- **Modular Design**: Clear separation between agents and shared infrastructure
- **Comprehensive Testing**: Unit and integration test suites
- **Documentation**: Detailed README files for each major component
- **Configuration**: Flexible JSON-based configuration system

## Configuration

### Environment Variables

The project uses a JSON configuration system. Key configuration areas:

```json
{
  "zotero": {
    "user_id": "your_zotero_user_id",
    "api_key": "your_zotero_api_key"
  },
  "llm": {
    "provider": "openai",
    "api_key": "your_api_key",
    "model": "gpt-4"
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

### Configuration Loading

Use `alithia.config_loader.load_config()` to load configuration from:
1. Environment variables
2. Configuration file (JSON)
3. Default values

## Agent Workflows

### AlithiaPaperScout Workflow ✅ **Implemented**

1. **Profile Analysis**: Extract research interests from Zotero library
2. **Data Collection**: Fetch papers from ArXiv RSS feed
3. **Relevance Assessment**: Score papers using sentence embeddings
4. **Content Generation**: Generate TLDR summaries using LLM
5. **Communication**: Send email with recommendations

**CLI Usage**: `python -m alithia.run paperscout_agent [-c CONFIG]`

### AlithiaLens Workflow ✅ **Implemented**

1. **PDF Parsing**: Extract structured content using Docling with IBM Granite VLM
2. **Content Analysis**: Process text, figures, tables, equations with multimodal understanding
3. **Semantic Search**: Find relevant sections using embeddings
4. **Interactive Q&A**: Provide conversational interface for paper exploration

**CLI Usage**: `python -m alithia.run paperlens_agent -i INPUT -d DIRECTORY [options]`

### AlithiaPulse Workflow ❌ **Not Implemented**

*This agent is planned but not yet implemented in the current codebase.*

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
- **Logging**: Use `cogents_core.utils.get_logger()` for consistent logging
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
# Install Python via pyenv
pyenv install 3.11
pyenv local 3.11

# Create and activate virtual environment
python -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -e ".[default,dev]"

# Run ArXiv agent (requires configuration)
python -m alithia.run paperscout_agent
python -m alithia.run paperscout_agent --config config.json

# Run PaperLens (requires input file and PDF directory)
python -m alithia.run paperlens_agent -i topic.txt -d ./papers
python -m alithia.run paperlens_agent -i topic.txt -d ./papers -n 20 --verbose

# Run tests
pytest
pytest tests/unit/
pytest tests/integration/
```

**Note**: Pulse agent is not available for local development as it's not yet implemented.

### Docker Support

```bash
# Build and run with Docker Compose
docker-compose up
```

## Troubleshooting

### Common Issues

1. **Configuration Errors**: Check JSON syntax and required fields
2. **API Limits**: Monitor rate limiting and implement backoff
3. **PDF Parsing**: Verify docling installation and IBM Granite model availability
4. **Email Delivery**: Check SMTP credentials and firewall settings

### Debug Mode

Enable debug logging by setting `debug: true` in configuration or using `-v` flag for CLI tools.

## Performance Considerations

### PDF Processing

- **IBM Granite VLM**: Optimized for multimodal document understanding
- **Batch Processing**: Efficient processing of multiple PDFs
- **Memory Management**: Proper cleanup of large documents

### Embedding Generation

- **Sentence Transformers**: Fast and efficient embedding generation
- **Batch Processing**: Process multiple texts simultaneously
- **Caching**: Consider caching embeddings for repeated queries

## Future Roadmap

### Currently Implemented ✅

- **AlithiaPaperScout**: Personalized ArXiv recommendation agent
- **AlithiaLens**: Deep paper interaction and analysis agent
- **IBM Granite VLM**: Optimized PDF parsing with multimodal understanding
- **LangGraph Integration**: Agent workflow orchestration
- **Comprehensive Testing**: Unit and integration test suites

### Planned Features 🚧

- **AlithiaPulse**: Proactive topic monitoring agent (not yet implemented)
- **Vector Store**: Pinecone/Weaviate integration for embeddings
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

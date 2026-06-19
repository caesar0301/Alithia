# Alithia Agent

CLI research assistant for paper discovery and analysis.

## Features

- **PaperScout**: ArXiv paper discovery with email notifications
- **PaperLens**: Local PDF analysis with similarity ranking
- **DeepXiv**: Academic paper search and progressive reading toolkit (arXiv, bioRxiv, medRxiv, PMC)

## Available Plugins

Alithia provides the following integrated plugins:

| Plugin | Type | Description | Source |
|--------|------|-------------|--------|
| paperscout | Subagent | Daily ArXiv paper recommendations based on Zotero library | Built-in |
| paperlens | Subagent | Local PDF analysis and similarity ranking | Built-in |
| deepxiv | Tools | Academic paper search with TLDRs and section-level access | [Migrated from soothe.toolkits](docs/migration-deepxiv-to-alithia.md) |

## Installation

```bash
pip install alithia
```

## Usage

```bash
# Run PaperScout for daily paper recommendations
python -m alithia_agent --subagent paperscout

# Run PaperLens to analyze local PDFs
python -m alithia_agent --subagent paperlens --query "transformers" --pdf-path ~/papers
```

## Configuration

Configuration is stored in `~/.alithia/config.json`. See the documentation for full configuration options.

## License

MIT
# Alithia Agent

CLI research assistant for paper discovery and analysis.

## Features

- **PaperScout**: ArXiv paper discovery with email notifications
- **PaperLens**: Local PDF analysis with similarity ranking

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
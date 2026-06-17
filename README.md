# Alithia Agent

CLI research assistant for paper discovery and analysis.

## Quick Start

```bash
# Install
pip install alithia

# Intent-based routing (automatic)
python -m alithia_agent "Find new papers about transformers"
python -m alithia_agent "Rank my PDFs in ~/research by relevance"
python -m alithia_agent "Start research about agent memory"

# Explicit subagent invocation
python -m alithia_agent --subagent paperscout "Check for new papers"
python -m alithia_agent --subagent paperlens "Analyze ~/papers directory"
python -m alithia_agent --subagent omr "https://arxiv.org/abs/2402.12345"

# Daemon management
python -m alithia_agent daemon start    # Start background daemon
python -m alithia_agent daemon status   # Check daemon status
python -m alithia_agent daemon stop     # Stop daemon
```

## Subagents

| Subagent | Purpose |
|----------|---------|
| **paperscout** | ArXiv paper discovery with email notifications |
| **paperlens** | Local PDF analysis with semantic similarity ranking |
| **omr** | Structured research workflow (literature review, hypothesis validation) |

## Configuration

Config file: `~/.alithia/config.yml`

## License

MIT
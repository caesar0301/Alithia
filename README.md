# Alithia Agent

CLI research assistant for paper discovery and analysis, powered by
[soothe-nano](https://github.com/mirasoth/soothe-nano) (same host style as FlowJet).

**Boundary:** Alithia runs soothe-nano **in-process** only. It does **not** talk to
soothed / soothe-daemon.

## Features

- **PaperScout**: ArXiv paper discovery with email notifications
- **PaperLens**: Local PDF analysis with similarity ranking
- **DeepXiv**: Academic paper search via nano’s built-in toolkit (arXiv, bioRxiv, medRxiv, PMC)
- **OmniResearch (omr)**: Structured research workflows with pattern routing (Evidence-First, Idea-First, Decision-First, Experiment-First, Rapid-Prototype). See [RFC-011](docs/specs/RFC-011-omni-research-subagent.md).

## Plugins

Paperscout and paperlens register as `soothe.plugins` entry points and load inside
the alithia nano agent:

| Plugin | Type | Description |
|--------|------|-------------|
| paperscout | Subagent | Daily ArXiv recommendations from research interests / Zotero |
| paperlens | Subagent | Local PDF analysis and similarity ranking |
| omr | Subagent | Structured research workflow with pattern routing (Evidence-First, etc.) |
| deepxiv | Tools | Nano built-in academic search / section reading (enabled by default) |

## Installation

```bash
pip install alithia
# or: uv sync
```

## Usage

```bash
# Query path — user request through in-process soothe-nano
alithia-agent "Find new papers about transformers"
alithia-agent -c ~/.alithia/config.yml "Rank my PDFs in ~/research by relevance"
alithia-agent --soothe-config ./nano.yml "Find new papers about transformers"

# Optional local subagent hint (biases the prompt; not soothed routing)
alithia-agent --subagent paperscout "Check for new papers"
alithia-agent --subagent omr "Start research about agent memory"

# Alithia PaperScout scheduler daemon (domain cron; not soothed)
alithia-agent daemon start
alithia-agent daemon status
alithia-agent daemon stop
```

## Configuration

| Flag / file | Role |
|-------------|------|
| `-c` / `--config` → `~/.alithia/config.yml` | Domain: paperscout / paperlens / storage / daemon |
| `--soothe-config` → `~/.alithia/soothe/config/nano.yml` | Soothe-nano providers / router |

```bash
mkdir -p ~/.alithia/soothe/config
cp nano.yml ~/.alithia/soothe/config/nano.yml
```

`SOOTHE_HOME` is set to `~/.alithia/soothe` automatically. Paperscout/paperlens and
deepxiv tools are enabled in code defaults when omitted from `nano.yml`.

## License

MIT

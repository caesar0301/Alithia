# RFC-005-cli-interface: Command Line Interface

**Status**: Draft
**Authors**: Claude
**Created**: 2026-06-06
**Last Updated**: 2026-06-06
**Depends on**: RFC-002-world-view
**Supersedes**: ---
**Stage**: Core
**Kind**: Implementation Interface Design

---

## 1. Abstract

Alithia-agent is invoked via CLI using Python's module entry point. This RFC defines the command line interface contracts: entry point invocation, subagent selection, configuration loading, output formats, error handling, and exit codes. The CLI provides a unified interface to invoke PaperScout and PaperLens subagents with user-controlled parameters.

---

## 2. Scope and Non-Goals

### 2.1 Scope

This RFC defines:

* Entry point invocation pattern (`python -m alithia_agent`)
* Subagent selection mechanism (`--subagent` flag)
* Configuration file handling (`--config` flag)
* Per-subagent arguments and flags
* Output formats (stdout, JSON, quiet mode)
* Error message formatting and exit codes
* Help text and documentation structure

### 2.2 Non-Goals

This RFC does **not** define:

* Web dashboard or REST API interfaces
* Interactive REPL or shell mode
* Shell completion scripts (bash/zsh)
* Logging implementation details
* Background/daemon execution mode

---

## 3. Background & Motivation

Alithia-agent is a pure CLI tool designed for:
- **Developer workflow**: Quick invocation from terminal
- **Automation**: Integration with cron, GitHub Actions, scripts
- **Portability**: Standard Python module entry point

The CLI must support both subagents (PaperScout, PaperLens) with their distinct parameters while providing a consistent interface pattern.

---

## 4. Entry Point

### 4.1 Invocation Pattern

```bash
python -m alithia_agent [OPTIONS] [SUBAGENT] [SUBAGENT_OPTIONS]
```

### 4.2 Module Structure

```python
# alithia_agent/__main__.py
def main():
    """CLI entry point."""
    args = parse_args()
    config = load_config(args.config)
    
    if args.subagent == "paperscout":
        run_paperscout(config, args)
    elif args.subagent == "paperlens":
        run_paperlens(config, args)
    else:
        print_help()
        sys.exit(1)

if __name__ == "__main__":
    main()
```

### 4.3 Exit Codes

| Code | Meaning |
|------|---------|
| `0` | Success |
| `1` | General error (invalid args, config error) |
| `2` | Subagent execution error (API failure, etc.) |
| `3` | Configuration validation error |
| `4` | Input validation error (invalid path, etc.) |

---

## 5. Global Options

### 5.1 Option Flags

| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `--config` | `str` | `~/.alithia/config.json` | Configuration file path |
| `--subagent` | `str` | Required | Subagent to invoke (`paperscout`, `paperlens`) |
| `--verbose` | `bool` | False | Enable verbose output (step-by-step progress) |
| `--quiet` | `bool` | False | Suppress all output except errors |
| `--output` | `str` | `stdout` | Output format (`stdout`, `json`, `none`) |
| `--user-id` | `str` | From config | Override user identifier |
| `--help` | `bool` | — | Show help message |
| `--version` | `bool` | — | Show version and exit |

### 5.2 Argument Parsing

```python
def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="alithia_agent",
        description="CLI research assistant for paper discovery and analysis",
    )
    
    # Global options
    parser.add_argument("--config", type=str, default="~/.alithia/config.json")
    parser.add_argument("--subagent", choices=["paperscout", "paperlens"], required=True)
    parser.add_argument("--verbose", action="store_true")
    parser.add_argument("--quiet", action="store_true")
    parser.add_argument("--output", choices=["stdout", "json", "none"], default="stdout")
    parser.add_argument("--user-id", type=str)
    parser.add_argument("--version", action="version", version="alithia-agent 1.0.0")
    
    # Subagent-specific parsers
    subparsers = parser.add_subparsers(dest="subagent")
    
    paperscout_parser = subparsers.add_parser("paperscout")
    add_paperscout_args(paperscout_parser)
    
    paperlens_parser = subparsers.add_parser("paperlens")
    add_paperlens_args(paperlens_parser)
    
    return parser.parse_args()
```

---

## 6. PaperScout CLI Interface

### 6.1 Subagent Options

| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `--categories` | `str` | From config | ArXiv categories (comma-separated: `cs.AI,cs.LG`) |
| `--max-papers` | `int` | From config | Papers to include in digest |
| `--lookback` | `int` | From config | Days to look back |
| `--send-email` | `bool` | True | Enable email notification |
| `--no-email` | `bool` | — | Disable email (dry run) |
| `--dry-run` | `bool` | — | Run without sending email |
| `--fill-gaps` | `bool` | — | Fill missed notification dates |

### 6.2 Argument Parser

```python
def add_paperscout_args(parser: argparse.ArgumentParser):
    parser.add_argument("--categories", type=str)
    parser.add_argument("--max-papers", type=int)
    parser.add_argument("--lookback", type=int)
    parser.add_argument("--send-email", action="store_true", default=True)
    parser.add_argument("--no-email", "--dry-run", action="store_true")
    parser.add_argument("--fill-gaps", action="store_true")
```

### 6.3 Output Format

**stdout mode**:
```
[profile_analysis] Configuration validated
[data_collection] Found 45 papers from ArXiv
[data_collection] Loaded 128 papers from Zotero
[relevance_assessment] Ranked 45 papers, selected top 25
[content_generation] Generated digest with 25 papers
[communication] Email sent to user@example.com

Papers sent: 25
Top paper: "Attention Is All You Need" (score: 8.72)
```

**json mode**:
```json
{
  "success": true,
  "papers_count": 25,
  "top_score": 8.72,
  "top_paper": "Attention Is All You Need",
  "email_sent": true,
  "metrics": {
    "pdfs_found": 45,
    "pdfs_parsed": 45,
    "avg_similarity_score": 6.34
  }
}
```

---

## 7. PaperLens CLI Interface

### 7.1 Subagent Options

| Flag | Type | Required | Description |
|------|------|----------|-------------|
| `--query` | `str` | Yes | Research topic/question for similarity |
| `--pdf-path` | `str` | Yes | Path to PDF file or directory |
| `--recursive` | `bool` | No (default True) | Search subdirectories |
| `--max-results` | `int` | No (default 50) | Maximum papers to return |
| `--format` | `str` | No (default `markdown`) | Output format (`markdown`, `json`) |

### 7.2 Argument Parser

```python
def add_paperlens_args(parser: argparse.ArgumentParser):
    parser.add_argument("--query", type=str, required=True)
    parser.add_argument("--pdf-path", type=str, required=True)
    parser.add_argument("--recursive", action="store_true", default=True)
    parser.add_argument("--no-recursive", action="store_false", dest="recursive")
    parser.add_argument("--max-results", type=int, default=50)
    parser.add_argument("--format", choices=["markdown", "json"], default="markdown")
```

### 7.3 Output Format

**markdown mode**:
```markdown
# PaperLens Results

Query: "transformer architectures for vision"

## Top 5 Papers

### 1. Vision Transformer (ViT) — Score: 9.23
- **Authors**: Dosovitskiy et al.
- **arXiv**: 2010.11929
- **TLDR**: An image is worth 16x16 words: transformers for image recognition...

### 2. Swin Transformer — Score: 8.67
- **Authors**: Liu et al.
- **arXiv**: 2103.14030
- **TLDR**: Hierarchical vision transformer using shifted windows...

---

Papers analyzed: 23
Processing time: 45.2s
```

**json mode**:
```json
{
  "query": "transformer architectures for vision",
  "papers_count": 23,
  "top_papers": [
    {
      "title": "Vision Transformer (ViT)",
      "authors": ["Dosovitskiy", "..."],
      "score": 9.23,
      "file_name": "vit.pdf"
    }
  ],
  "metrics": {
    "pdfs_found": 23,
    "pdfs_parsed": 23,
    "avg_parse_time_ms": 1978,
    "total_processing_time_ms": 45200
  }
}
```

---

## 8. Error Output

### 8.1 Error Message Format

**stdout mode**:
```
ERROR: Configuration validation failed
  - Missing required field: zotero.api_key
  - Missing required field: smtp.password

Exit code: 3
```

**json mode**:
```json
{
  "success": false,
  "error": {
    "code": 3,
    "message": "Configuration validation failed",
    "details": [
      "Missing required field: zotero.api_key",
      "Missing required field: smtp.password"
    ]
  }
}
```

### 8.2 Error Categories

| Error Type | Exit Code | Example Message |
|------------|-----------|-----------------|
| **Argument error** | 1 | `ERROR: --query is required for paperlens` |
| **Config error** | 3 | `ERROR: Config file not found: /path/config.json` |
| **Validation error** | 4 | `ERROR: PDF path does not exist: /path/to/papers` |
| **Execution error** | 2 | `ERROR: ArXiv API rate limit exceeded` |

---

## 9. Verbosity Levels

### 9.1 Output Control

| Level | Flag | Output |
|-------|------|--------|
| **Quiet** | `--quiet` | Only errors, no progress |
| **Normal** | (default) | Step progress + summary |
| **Verbose** | `--verbose` | Detailed step-by-step with timing |

### 9.2 Verbose Output Example

```
[profile_analysis] Starting validation (0.00s)
[profile_analysis] Checking Zotero config (0.01s)
[profile_analysis] Checking SMTP config (0.01s)
[profile_analysis] Validation complete (0.02s)

[data_collection] Querying ArXiv categories: cs.AI, cs.CV, cs.LG (0.00s)
[data_collection] ArXiv returned 45 papers (2.34s)
[data_collection] Checking cache for emailed papers (0.05s)
[data_collection] 12 papers already emailed, 33 new (0.06s)
[data_collection] Fetching Zotero library (0.00s)
[data_collection] Zotero returned 128 papers (1.23s)
[data_collection] Complete (3.68s)

...
```

---

## 10. Version and Help

### 10.1 Version Output

```
alithia-agent 1.0.0
Python 3.11.4
soothe-sdk 0.3.0
langgraph 0.2.5

Storage: ~/.alithia/alithia.db
```

### 10.2 Help Output

```
alithia-agent — CLI research assistant for paper discovery and analysis

Usage:
  python -m alithia_agent --subagent <name> [options]

Subagents:
  paperscout    Discover papers from ArXiv, send email digest
  paperlens     Analyze local PDFs, rank by relevance to query

Global Options:
  --config PATH     Configuration file (default: ~/.alithia/config.json)
  --verbose         Show detailed progress
  --quiet           Suppress all output except errors
  --output FORMAT   Output format: stdout, json, none
  --user-id ID      Override user identifier
  --version         Show version and exit
  --help            Show this help

PaperScout Options:
  --categories CATS   ArXiv categories (comma-separated)
  --max-papers N      Papers in digest (default: 25)
  --lookback DAYS     Days to look back (default: 7)
  --dry-run           Run without sending email

PaperLens Options:
  --query TEXT        Research topic (required)
  --pdf-path PATH     PDF directory or file (required)
  --max-results N     Maximum results (default: 50)
  --format FORMAT     Output: markdown, json

Examples:
  python -m alithia_agent paperscout --dry-run
  python -m alithia_agent paperlens --query "vision transformers" --pdf-path ~/papers
```

---

## 11. Integration with Subagents

### 11.1 Invocation Flow

```python
def run_paperscout(config: dict, args: argparse.Namespace):
    # Merge CLI args into config
    paperscout_config = merge_config(config.get("paperscout", {}), args)
    
    # Create subagent
    from soothe_community.paperscout import create_paperscout_subagent
    subagent = create_paperscout_subagent(config=paperscout_config, ...)
    
    # Execute workflow
    result = subagent["runnable"].invoke(initial_state)
    
    # Format output
    format_output(result, args.output)

def run_paperlens(config: dict, args: argparse.Namespace):
    # Merge CLI args into config
    paperlens_config = merge_config(config.get("paperlens", {}), args)
    
    # Create subagent
    from soothe_community.paperlens import create_paperlens_subagent
    subagent = create_paperlens_subagent(config=paperlens_config, ...)
    
    # Build initial state with query and pdf_path
    initial_state = {
        "query": args.query,
        "pdf_path": args.pdf_path,
        ...
    }
    
    # Execute workflow
    result = subagent["runnable"].invoke(initial_state)
    
    # Format output
    format_output(result, args.output)
```

### 11.2 Config Merge Logic

```python
def merge_config(base_config: dict, args: argparse.Namespace) -> dict:
    """Merge CLI args into base config (CLI takes precedence)."""
    merged = base_config.copy()
    
    # Map CLI args to config keys
    arg_to_config = {
        "categories": "arxiv_categories",  # PaperScout
        "max_papers": "max_papers",        # PaperScout
        "lookback": "lookback_days",       # PaperScout
        "max_results": "max_papers",       # PaperLens
        "recursive": "recursive_scan",     # PaperLens
    }
    
    for arg_name, config_key in arg_to_config.items():
        arg_value = getattr(args, arg_name, None)
        if arg_value is not None:
            merged[config_key] = arg_value
    
    return merged
```

---

## 12. Dependencies

### 12.1 Required Dependencies

| Package | Purpose | Source |
|---------|---------|--------|
| `argparse` | Argument parsing | Python stdlib |
| `sys` | Exit codes | Python stdlib |
| `json` | Output formatting | Python stdlib |

---

## 13. Relationship to Other RFCs

| RFC | Relationship |
|-----|--------------|
| RFC-002-world-view | Implements CLI interface per conceptual model |
| RFC-006-configuration | Uses config loading defined there |
| RFC-001-paperlens-workflow | Invokes PaperLens subagent |
| RFC-003-paperscout-workflow | Invokes PaperScout subagent |

---

## 14. Open Questions

None. CLI design follows standard Python patterns.

---

## 15. Conclusion

Alithia-agent CLI provides a unified entry point (`python -m alithia_agent`) with:

1. **Subagent selection**: `--subagent paperscout` or `--subagent paperlens`
2. **Config override**: CLI args take precedence over config file
3. **Output control**: `--verbose`, `--quiet`, `--output json`
4. **Exit codes**: 0=success, 1=arg error, 2=execution error, 3=config error, 4=validation error
5. **Per-subagent options**: Specific flags for PaperScout and PaperLens

> **The CLI is the primary user interface for alithia-agent — a standard Python module entry point with clear subagent selection, flexible output formats, and informative error handling.**
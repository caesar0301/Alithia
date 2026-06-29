# RFC-006-configuration: Configuration Management

**Status**: Draft
**Authors**: Claude
**Created**: 2026-06-06
**Last Updated**: 2026-06-29
**Depends on**: RFC-002-world-view, RFC-010-research-interests-knowledge
**Supersedes**: ---
**Stage**: Core
**Kind**: Architecture Design

---

## 1. Abstract

Alithia-agent configuration is managed via JSON files with environment variable substitution support. This RFC defines the configuration architecture: file location, schema structure, validation rules, environment integration, default values, and merge precedence between config file and CLI arguments.

---

## 2. Scope and Non-Goals

### 2.1 Scope

This RFC defines:

* Configuration file location and discovery
* JSON schema structure for all config sections
* Environment variable substitution syntax
* Validation rules and error handling
* Default values for optional settings
* Config merge precedence (file vs CLI vs defaults)
* Sensitive credential handling (API keys)

### 2.2 Non-Goals

This RFC does **not** define:

* YAML or TOML configuration formats (JSON only)
* Interactive configuration wizard
* Configuration hot-reloading
* Remote configuration fetching
* Configuration encryption

---

## 3. Background & Motivation

Alithia-agent requires configuration for:
- **API credentials**: ArXiv (no auth), Zotero (API key), SMTP (password)
- **Subagent settings**: Categories, limits, timeouts
- **Storage settings**: Database path, user ID
- **Output preferences**: Email recipient, TLDR language

A JSON-based config system with environment substitution:
- Is human-readable and editable
- Supports secret injection from environment
- Works with existing deployment tools (Docker, GitHub Actions)

---

## 4. Design Principles

1. **JSON native**: Configuration files are JSON for simplicity
2. **Environment injection**: Secrets via `${VAR_NAME}` syntax
3. **Validation early**: Config validated at startup, not runtime
4. **Defaults documented**: All optional fields have documented defaults
5. **CLI override**: CLI arguments take precedence over file config
6. **Fail fast**: Missing required fields cause immediate error

---

## 5. Configuration Architecture

### 5.1 File Location

| Location | Priority | Use Case |
|----------|----------|----------|
| `~/.alithia/config.json` | Default | User's primary config |
| `--config PATH` | Override | CLI-specified config |
| `.env` (environment) | Injection | Secrets only (not full config) |

### 5.2 Config Discovery Flow

```python
def find_config_path(cli_path: str | None) -> Path:
    if cli_path:
        path = Path(cli_path)
        if not path.exists():
            raise ConfigError(f"Config file not found: {path}")
        return path
    
    default_path = Path.home() / ".alithia" / "config.json"
    if default_path.exists():
        return default_path
    
    # No config file - use defaults + environment
    return None
```

### 5.3 Component Structure

```
config/
├── __init__.py          # Config module entry
├── loader.py            # ConfigLoader class
├── schema.py            # Config schemas (Pydantic models)
├── validator.py         # Validation logic
├── defaults.py          # Default values
└── env_substitution.py  # Environment variable expansion
```

---

## 6. Configuration Schema

### 6.1 Top-Level Structure

```json
{
  "storage": { ... },
  "paperscout": { ... },
  "paperlens": { ... },
  "zotero": { ... },
  "smtp": { ... },
  "llm": { ... }
}
```

### 6.2 Storage Config

```json
{
  "storage": {
    "backend": "sqlite",
    "path": "~/.alithia/alithia.db",
    "user_id": "user@example.com"
  }
}
```

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `backend` | `str` | No | `sqlite` | Storage backend type |
| `path` | `str` | No | `~/.alithia/alithia.db` | Database path |
| `user_id` | `str` | No | `"default"` | User identifier |

### 6.3 Zotero Config (Optional)

> **RFC-010 change**: Zotero is now **optional** at every layer (schema, runtime
> config, `profile_analysis`, validator). When configured, the library is synced
> into `~/.alithia/research_interests/zotero/*.md` at run time and unified with
> hand-written interest files. When absent, PaperScout ranks against the
> hand-written interests alone. See [RFC-010-research-interests-knowledge](RFC-010-research-interests-knowledge.md).

```json
{
  "zotero": {
    "api_key": "${ZOTERO_API_KEY}",
    "library_id": "${ZOTERO_LIBRARY_ID}",
    "library_type": "user"
  }
}
```

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `api_key` | `str` | No (optional) | — | Zotero API key (env injected). Omit to run interests-only. |
| `library_id` | `str` | No (optional) | — | Library ID (env injected). |
| `library_type` | `str` | No | `user` | `user` or `group` |

### 6.3.1 Research Interests (Markdown, not a config field)

> **RFC-010 change**: The `research_interests: list[str]` config field was
> **removed** from `ResearcherProfileConfig`. Interests are read exclusively
> from the `~/.alithia/research_interests/` Markdown directory (one file per
> knowledge unit, YAML frontmatter + body). A config that still carries a
> legacy `research_interests` list key is tolerated via `extra="allow"` and
> ignored. Run `python scripts/migrate_research_interests.py` to seed Markdown
> files. See [RFC-010](RFC-010-research-interests-knowledge.md) §5, §11.
>
> The `expertise_level` field was also removed (it was never read at runtime).

### 6.4 SMTP Config

```json
{
  "smtp": {
    "host": "${SMTP_HOST}",
    "port": 587,
    "user": "${SMTP_USER}",
    "password": "${SMTP_PASSWORD}",
    "use_tls": true
  }
}
```

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `host` | `str` | Yes | — | SMTP server hostname |
| `port` | `int` | No | `587` | SMTP port |
| `user` | `str` | Yes | — | SMTP username |
| `password` | `str` | Yes | — | SMTP password (env injected) |
| `use_tls` | `bool` | No | `true` | Enable TLS |

### 6.5 LLM Config

```json
{
  "llm": {
    "provider": "openai",
    "api_key": "${OPENAI_API_KEY}",
    "base_url": "https://api.openai.com/v1",
    "model": "gpt-4o-mini",
    "max_tokens": 150,
    "temperature": 0.1
  }
}
```

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `provider` | `str` | No | `openai` | LLM provider |
| `api_key` | `str` | Yes (for LLM) | — | API key (env injected) |
| `base_url` | `str` | No | Provider default | API base URL |
| `model` | `str` | No | `gpt-4o-mini` | Model name |
| `max_tokens` | `int` | No | `150` | Max response tokens |
| `temperature` | `float` | No | `0.1` | Response temperature |

### 6.6 PaperScout Config

```json
{
  "paperscout": {
    "arxiv_categories": ["cs.AI", "cs.CV", "cs.LG", "cs.CL"],
    "max_papers": 25,
    "max_papers_queried": 500,
    "send_email": true,
    "send_empty": false,
    "recipient_email": null,
    "lookback_days": 7,
    "gap_window_days": 7,
    "emailed_papers_retention_days": 30,
    "tldr_max_tokens": 150,
    "tldr_language": "English"
  }
}
```

(Full schema in RFC-003-paperscout-workflow Section 8.1)

### 6.7 PaperLens Config

```json
{
  "paperlens": {
    "pdf_extensions": ["pdf"],
    "recursive_scan": true,
    "max_papers": 50,
    "batch_size": 8,
    "sbert_model": "all-MiniLM-L6-v2",
    "use_gpu": false,
    "llm_enhance_metadata": true,
    "llm_max_tokens": 500,
    "output_format": "markdown",
    "include_full_text": false
  }
}
```

(Full schema in RFC-001-paperlens-workflow Section 8.1)

---

## 7. Environment Variable Substitution

### 7.1 Syntax

| Pattern | Behavior |
|---------|----------|
| `${VAR_NAME}` | Substitute with environment variable value |
| `${VAR_NAME:default}` | Substitute with value or `default` if unset |
| `$VAR_NAME` | NOT supported (use `${}` syntax only) |

### 7.2 Implementation

```python
import re
import os

ENV_PATTERN = re.compile(r'\$\{([A-Za-z_][A-Za-z0-9_]*)(?:([^:]*))?\}')

def substitute_env(value: str) -> str:
    """Recursively substitute environment variables in string."""
    def replace(match):
        var_name = match.group(1)
        default = match.group(2)
        
        env_value = os.environ.get(var_name)
        if env_value is not None:
            return env_value
        if default is not None:
            return default
        raise ConfigError(f"Environment variable not set: {var_name}")
    
    return ENV_PATTERN.sub(replace, value)

def process_config_env(config: dict) -> dict:
    """Process all string values in config for env substitution."""
    def process_value(value):
        if isinstance(value, str):
            return substitute_env(value)
        elif isinstance(value, dict):
            return {k: process_value(v) for k, v in value.items()}
        elif isinstance(value, list):
            return [process_value(v) for v in value]
        else:
            return value
    
    return process_value(config)
```

### 7.3 Required Environment Variables

| Variable | Required By | Use Case |
|----------|-------------|----------|
| `ZOTERO_API_KEY` | PaperScout (optional) | Zotero library access — only if zotero configured (RFC-010) |
| `ZOTERO_LIBRARY_ID` | PaperScout (optional) | Library identification — only if zotero configured |
| `SMTP_HOST` | PaperScout | Email delivery |
| `SMTP_USER` | PaperScout | Email auth |
| `SMTP_PASSWORD` | PaperScout | Email auth |
| `OPENAI_API_KEY` | Both | LLM metadata enhancement |

---

## 8. Validation

### 8.1 Validation Rules

| Rule | Implementation |
|------|----------------|
| Required fields | Pydantic model validation (missing → error) |
| Type checking | Pydantic automatic type coercion/validation |
| Range constraints | Pydantic `Field(ge=1, le=100)` constraints |
| Enum constraints | Pydantic `Literal` or enum types |
| Cross-field validation | Pydantic `@model_validator` for dependencies |

### 8.2 Validation Implementation

```python
from pydantic import BaseModel, Field, ValidationError, model_validator

class Config(BaseModel):
    """Root configuration model."""
    
    storage: StorageConfig = Field(default_factory=StorageConfig)
    zotero: ZoteroConfig | None = None
    smtp: SmtpConfig | None = None
    llm: LlmConfig | None = None
    paperscout: PaperScoutConfig = Field(default_factory=PaperScoutConfig)
    paperlens: PaperLensConfig = Field(default_factory=PaperLensConfig)
    
    @model_validator(mode="after")
    def validate_paperscout_dependencies(self):
        """PaperScout requires smtp if send_email=True. Zotero is OPTIONAL
        (RFC-010): the run succeeds with research-interests markdown alone,
        with zotero alone, or with both. The "no knowledge source" check is
        enforced at runtime in profile_analysis_node, not here, because it
        depends on the on-disk interests directory."""
        if self.paperscout.send_email:
            if not self.smtp:
                raise ValueError("smtp config required when paperscout.send_email=True")
        return self

def validate_config(config_dict: dict) -> Config:
    """Validate config dict against schema."""
    try:
        return Config(**config_dict)
    except ValidationError as e:
        errors = []
        for error in e.errors():
            loc = ".".join(str(x) for x in error["loc"])
            msg = error["msg"]
            errors.append(f"{loc}: {msg}")
        raise ConfigError(f"Config validation failed:\n" + "\n".join(errors))
```

### 8.3 Validation Error Format

```
Config validation failed:
  - zotero.api_key: Field required
  - smtp.password: Field required
  - paperscout.max_papers: Input should be greater than or equal to 1
  - paperscout.lookback_days: Input should be less than or equal to 30
```

---

## 9. Config Merge Precedence

### 9.1 Precedence Order (highest to lowest)

1. **CLI arguments**: Direct user input
2. **Config file values**: JSON file settings
3. **Environment variables**: For secrets only
4. **Default values**: Hardcoded defaults

### 9.2 Merge Implementation

```python
def merge_configs(
    defaults: dict,
    file_config: dict | None,
    cli_args: dict,
) -> dict:
    """Merge configs with precedence: CLI > file > defaults."""
    merged = defaults.copy()
    
    # Apply file config (if exists)
    if file_config:
        merged = deep_merge(merged, file_config)
    
    # Apply CLI overrides (highest precedence)
    merged = deep_merge(merged, cli_args)
    
    return merged

def deep_merge(base: dict, override: dict) -> dict:
    """Deep merge two dicts (override takes precedence)."""
    result = base.copy()
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = value
    return result
```

---

## 10. Default Values

### 10.1 Defaults Definition

```python
DEFAULT_CONFIG = {
    "storage": {
        "backend": "sqlite",
        "path": "~/.alithia/alithia.db",
        "user_id": "default",
    },
    "paperscout": {
        "arxiv_categories": ["cs.AI", "cs.CV", "cs.LG", "cs.CL"],
        "max_papers": 25,
        "max_papers_queried": 500,
        "send_email": True,
        "send_empty": False,
        "lookback_days": 7,
        "gap_window_days": 7,
        "emailed_papers_retention_days": 30,
        "tldr_max_tokens": 150,
        "tldr_language": "English",
    },
    "paperlens": {
        "pdf_extensions": ["pdf"],
        "recursive_scan": True,
        "max_papers": 50,
        "batch_size": 8,
        "sbert_model": "all-MiniLM-L6-v2",
        "use_gpu": False,
        "llm_enhance_metadata": True,
        "llm_max_tokens": 500,
        "output_format": "markdown",
        "include_full_text": False,
    },
    "smtp": {
        "port": 587,
        "use_tls": True,
    },
    "llm": {
        "provider": "openai",
        "model": "gpt-4o-mini",
        "max_tokens": 150,
        "temperature": 0.1,
    },
}
```

---

## 11. Configuration Loading Flow

### 11.1 Complete Flow

```python
class ConfigLoader:
    def load(self, cli_path: str | None = None, cli_args: dict = None) -> Config:
        # 1. Find config file
        config_path = find_config_path(cli_path)
        
        # 2. Load file if exists
        file_config = {}
        if config_path:
            file_config = self._load_file(config_path)
            file_config = process_config_env(file_config)
        
        # 3. Merge with defaults
        merged = merge_configs(DEFAULT_CONFIG, file_config, cli_args or {})
        
        # 4. Validate
        validated_config = validate_config(merged)
        
        return validated_config
    
    def _load_file(self, path: Path) -> dict:
        try:
            with open(path) as f:
                return json.load(f)
        except json.JSONDecodeError as e:
            raise ConfigError(f"Invalid JSON in config file: {e}")
```

### 11.2 Flow Diagram

```
CLI Path? → Load File → Env Substitution → Merge Defaults → Merge CLI → Validate → Config
    │           │              │                │              │           │
    No          Skip           Skip             Apply          Apply       Return
```

---

## 12. Sensitive Credential Handling

### 12.1 Credential Sources

| Credential | Source | Storage |
|------------|--------|---------|
| API keys | Environment | Never in config file |
| Passwords | Environment | Never in config file |
| Library ID | Environment or config | Either |
| Recipient email | Config file | Non-sensitive |

### 12.2 Best Practices

| Practice | Rule |
|----------|------|
| Environment first | Secrets MUST use `${VAR_NAME}` syntax |
| No plaintext secrets | Config files MUST NOT contain plaintext passwords/keys |
| .env file support | `.env` file can set environment for local dev |
| Docker secrets | Use Docker secrets or env vars in containers |
| GitHub Actions | Use repository secrets for CI |

### 12.3 Example .env File

```bash
# ~/.alithia/.env (for local development)
ZOTERO_API_KEY=abc123xyz
ZOTERO_LIBRARY_ID=12345
SMTP_HOST=smtp.gmail.com
SMTP_USER=user@gmail.com
SMTP_PASSWORD=app_password_here
OPENAI_API_KEY=sk-...
```

---

## 13. Error Handling

### 13.1 Error Categories

| Category | Example | Handling |
|----------|---------|----------|
| **File not found** | Config file missing | Use defaults (if no required fields) |
| **Invalid JSON** | Syntax error in file | Raise ConfigError with details |
| **Missing env var** | `${ZOTERO_API_KEY}` unset | Raise ConfigError with variable name |
| **Validation error** | Field constraint violated | Raise ConfigError with field names |

### 13.2 ConfigError Class

```python
class ConfigError(Exception):
    """Configuration error with structured details."""
    
    def __init__(self, message: str, details: list[str] = None):
        self.message = message
        self.details = details or []
        super().__init__(self.format_message())
    
    def format_message(self) -> str:
        if self.details:
            return f"{self.message}\n" + "\n".join(f"  - {d}" for d in self.details)
        return self.message
```

---

## 14. Integration Points

### 14.1 CLI Integration

```python
# Called from CLI entry point
config = ConfigLoader().load(cli_path=args.config, cli_args=cli_overrides)
```

### 14.2 Subagent Integration

```python
# Passed to subagent factory
subagent = create_paperscout_subagent(config=config.paperscout, ...)
```

---

## 15. Dependencies

### 15.1 Required Dependencies

| Package | Purpose | Source |
|---------|---------|--------|
| `pydantic` | Schema validation | pip |
| `json` | File parsing | stdlib |
| `os` | Environment access | stdlib |
| `re` | Pattern matching | stdlib |

---

## 16. Relationship to Other RFCs

| RFC | Relationship |
|-----|--------------|
| RFC-002-world-view | Implements Config abstraction |
| RFC-005-cli-interface | CLI provides config overrides |
| RFC-001-paperlens-workflow | Uses PaperLensConfig schema |
| RFC-003-paperscout-workflow | Uses PaperScoutConfig schema |
| RFC-004-storage-layer | Uses StorageConfig schema |

---

## 17. Open Questions

None. JSON + environment substitution is the chosen approach.

---

## 18. Conclusion

Alithia-agent configuration uses JSON files with environment variable substitution for secrets. The architecture:

1. **File-based**: `~/.alithia/config.json` or CLI-specified path
2. **Env injection**: `${VAR_NAME}` syntax for secrets
3. **Pydantic validation**: Schema enforcement with error details
4. **Merge precedence**: CLI > file > defaults
5. **Fail fast**: Missing required fields cause immediate error

> **Configuration is JSON with environment injection — secrets never in files, validation at startup, CLI overrides file values.**
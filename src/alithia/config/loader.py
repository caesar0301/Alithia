"""Configuration loader.

YAML file loading with environment variable substitution.
Merge precedence: CLI > file > defaults.
"""

from __future__ import annotations

import logging
import os
import re
from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError

from alithia.config.schema import (
    Config,
    ConfigError,
)

logger = logging.getLogger(__name__)

# Environment variable pattern: ${VAR_NAME} or ${VAR_NAME:default}
ENV_PATTERN = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)(?::([^}]*))?\}")


def substitute_env(value: str) -> str:
    """Substitute environment variables in string.

    Args:
        value: String with ${VAR_NAME} or ${VAR_NAME:default} patterns.

    Returns:
        String with environment variables substituted.

    Raises:
        ConfigError: If variable not set and no default provided.
    """

    def replace(match: re.Match[str]) -> str:
        var_name = match.group(1)
        default = match.group(2)

        env_value = os.environ.get(var_name)
        if env_value is not None:
            return env_value
        if default is not None:
            return default
        raise ConfigError(f"Environment variable not set: {var_name}")

    return ENV_PATTERN.sub(replace, value)


def process_config_env(config: dict[str, Any]) -> dict[str, Any]:
    """Process all string values in config for env substitution.

    Args:
        config: Configuration dictionary.

    Returns:
        Configuration with environment variables substituted.
    """

    def process_value(value: Any) -> Any:
        if isinstance(value, str):
            return substitute_env(value)
        elif isinstance(value, dict):
            return {k: process_value(v) for k, v in value.items()}
        elif isinstance(value, list):
            return [process_value(v) for v in value]
        else:
            return value

    return process_value(config)  # type: ignore[no-any-return]


def deep_merge(base: dict, override: dict) -> dict:
    """Deep merge two dicts (override takes precedence).

    Args:
        base: Base dictionary.
        override: Override dictionary.

    Returns:
        Merged dictionary.
    """
    result = base.copy()
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = value
    return result


# Default configuration values (aligned with existing alithia config)
DEFAULT_CONFIG = {
    "researcher_profile": {
        # research_interests are now Markdown files under
        # ~/.alithia/research_interests/ (RFC-010); not a config list.
        "language": "English",
    },
    "storage": {
        "backend": "sqlite",
        "fallback_to_sqlite": False,
        "sqlite_path": "data/alithia.db",
        "user_id": "default_user",
    },
    "paperscout_agent": {
        "query": "cs.AI+cs.CV+cs.LG+cs.CL",
        "max_papers": 25,
        "max_papers_queried": 500,
        "send_email": False,
        "send_empty": False,
        "ignore_patterns": [],
        "lookback_days": 7,
        "gap_window_days": 7,
        "emailed_papers_retention_days": 30,
        "tldr_max_tokens": 150,
        "tldr_language": "English",
    },
    "paperlens_agent": {
        "sbert_model": "all-MiniLM-L6-v2",
        "force_gpu": False,
        "top_n": 10,
        "pdf_extensions": ["pdf"],
        "recursive_scan": True,
        "max_papers": 50,
        "batch_size": 8,
        "llm_enhance_metadata": True,
        "llm_max_tokens": 500,
        "output_format": "markdown",
        "include_full_text": False,
    },
    "turnstile": {
        "enabled": False,
        "site_key": "",
        "secret_key": "",
    },
    "debug": False,
}


class ConfigLoader:
    """Configuration loader with file, env, and CLI support.

    Load order:
    1. Default values
    2. Config file (if exists)
    3. Environment variable substitution
    4. CLI argument overrides
    5. Pydantic validation
    """

    def find_config_path(self, cli_path: str | None = None) -> Path | None:
        """Find configuration file path.

        Args:
            cli_path: CLI-specified config path.

        Returns:
            Path to config file, or None if not found.
        """
        from alithia import ALITHIA_HOME

        if cli_path:
            path = Path(cli_path)
            if not path.exists():
                raise ConfigError(f"Config file not found: {path}")
            return path

        # YAML-only configuration path
        yaml_path = ALITHIA_HOME / "config.yml"
        if yaml_path.exists():
            return yaml_path

        return None

    def load_file(self, path: Path) -> dict[str, Any]:
        """Load YAML configuration file.

        Args:
            path: Path to config file.

        Returns:
            Configuration dictionary.

        Raises:
            ConfigError: If file cannot be parsed.
        """
        try:
            if path.suffix not in (".yml", ".yaml"):
                raise ConfigError(
                    f"Unsupported config format: {path.suffix or '<none>'}. "
                    "Use a YAML config file (.yml or .yaml)."
                )

            with open(path) as f:
                loaded = yaml.safe_load(f)

            if loaded is None:
                return {}
            if not isinstance(loaded, dict):
                raise ConfigError("Invalid YAML config: root must be a mapping/object.")
            return loaded  # type: ignore[no-any-return]

        except yaml.YAMLError as e:
            raise ConfigError(f"Invalid YAML in config file: {e}")

    def load(
        self,
        cli_path: str | None = None,
        cli_args: dict[str, Any] | None = None,
    ) -> Config:
        """Load configuration with full merge and validation.

        Args:
            cli_path: CLI-specified config file path.
            cli_args: CLI argument overrides.

        Returns:
            Validated Config object.

        Raises:
            ConfigError: If configuration is invalid.
        """
        # 1. Find config file
        config_path = self.find_config_path(cli_path)

        # 2. Load file if exists
        file_config: dict[str, Any] = {}
        if config_path:
            file_config = self.load_file(config_path)
            file_config = process_config_env(file_config)

        # 3. Merge with defaults
        merged = deep_merge(DEFAULT_CONFIG, file_config)

        # 4. Apply CLI overrides
        if cli_args:
            merged = deep_merge(merged, cli_args)

        # 5. Validate
        try:
            return Config(**merged)
        except ValidationError as e:
            errors = []
            for error in e.errors():
                loc = ".".join(str(x) for x in error["loc"])
                msg = error["msg"]
                errors.append(f"{loc}: {msg}")
            raise ConfigError("Config validation failed", errors)


def load_config(
    config_path: str | None = None,
    cli_overrides: dict[str, Any] | None = None,
) -> Config:
    """Convenience function to load configuration.

    Args:
        config_path: Optional config file path.
        cli_overrides: Optional CLI argument overrides.

    Returns:
        Validated Config object.
    """
    loader = ConfigLoader()
    return loader.load(cli_path=config_path, cli_args=cli_overrides)


__all__ = [
    "ConfigLoader",
    "load_config",
    "substitute_env",
    "process_config_env",
    "deep_merge",
    "DEFAULT_CONFIG",
]

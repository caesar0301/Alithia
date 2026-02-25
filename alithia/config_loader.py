import logging
import os
import sys
from typing import Any, Dict, Optional

from dotenv import load_dotenv

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv(override=True)
os.environ["TOKENIZERS_PARALLELISM"] = "false"


def get_env(key: str, default=None):
    """
    Get environment variable, handling empty strings as None.

    Args:
        key: Environment variable key
        default: Default value if not found

    Returns:
        Environment variable value or default
    """
    value = os.environ.get(key)
    if value == "" or value is None:
        return default
    return value


def load_config(config_path: Optional[str] = None) -> Dict[str, Any]:
    """
    Load configuration from JSON file or environment variables.

    By default, looks for 'alithia_config.json' in the current working directory.
    """
    if config_path and not os.path.exists(config_path):
        raise FileNotFoundError(f"Config file not found: {config_path}")

    # Build configuration
    env_config = _build_config_from_envs()

    # Use config_path if provided, otherwise look in current working directory
    config_file = config_path or "alithia_config.json"
    if os.path.exists(config_file):
        file_dict = _load_config_from_file(config_file)
        # merge file config and env config with env config taking precedence
        config_dict = _merge_configs(file_dict, env_config)
    else:
        config_dict = env_config

    # Migrate legacy top-level "supabase" into "storage.supabase"
    if "supabase" in config_dict and "supabase" not in config_dict.get("storage", {}):
        config_dict.setdefault("storage", {})["supabase"] = config_dict.pop("supabase")

    # Enable debug logging if specified
    if config_dict.get("debug", False):
        logging.getLogger().setLevel(logging.DEBUG)
        logger.debug(f"Final configuration: {config_dict}")

    return config_dict


def _load_config_from_file(config_path: str) -> Dict[str, Any]:
    """
    Load configuration from JSON file.

    Args:
        config_path: Path to configuration file

    Returns:
        Configuration dictionary
    """
    import json

    try:
        with open(config_path, "r") as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Failed to load config file {config_path}: {e}")
        sys.exit(1)


def _build_config_from_envs() -> Dict[str, Any]:
    """
    Build configuration dictionary from environment variables.

    Returns:
        Configuration dictionary in nested format
    """
    config = {}

    # Map environment variables to nested config structure
    env_mapping = {
        # Researcher profile - basic info
        "researcher_profile.research_interests": "ALITHIA_RESEARCH_INTERESTS",
        "researcher_profile.expertise_level": "ALITHIA_EXPERTISE_LEVEL",
        "researcher_profile.language": "ALITHIA_LANGUAGE",
        "researcher_profile.email": "ALITHIA_EMAIL",
        # Researcher profile - LLM settings
        "researcher_profile.llm.openai_api_key": "ALITHIA_OPENAI_API_KEY",
        "researcher_profile.llm.openai_api_base": "ALITHIA_OPENAI_API_BASE",
        "researcher_profile.llm.model_name": "ALITHIA_MODEL_NAME",
        # Researcher profile - Zotero settings
        "researcher_profile.zotero.zotero_id": "ALITHIA_ZOTERO_ID",
        "researcher_profile.zotero.zotero_key": "ALITHIA_ZOTERO_KEY",
        # Researcher profile - Email notification settings
        "researcher_profile.email_notification.smtp_server": "ALITHIA_SMTP_SERVER",
        "researcher_profile.email_notification.smtp_port": "ALITHIA_SMTP_PORT",
        "researcher_profile.email_notification.sender": "ALITHIA_SENDER",
        "researcher_profile.email_notification.sender_password": "ALITHIA_SENDER_PASSWORD",
        # Storage settings (supabase is nested under storage)
        "storage.backend": "ALITHIA_STORAGE_BACKEND",
        "storage.fallback_to_sqlite": "ALITHIA_STORAGE_FALLBACK_TO_SQLITE",
        "storage.sqlite_path": "ALITHIA_STORAGE_SQLITE_PATH",
        "storage.user_id": "ALITHIA_STORAGE_USER_ID",
        "storage.supabase.url": "ALITHIA_SUPABASE_URL",
        "storage.supabase.anon_key": "ALITHIA_SUPABASE_ANON_KEY",
        "storage.supabase.service_role_key": "ALITHIA_SUPABASE_SERVICE_ROLE_KEY",
        # PaperScout agent settings
        "paperscout_agent.query": "ALITHIA_ARXIV_QUERY",
        "paperscout_agent.max_papers": "ALITHIA_MAX_PAPERS",
        "paperscout_agent.max_papers_queried": "ALITHIA_MAX_PAPERS_QUERIED",
        "paperscout_agent.send_email": "ALITHIA_SEND_EMAIL",
        "paperscout_agent.send_empty": "ALITHIA_SEND_EMPTY",
        "paperscout_agent.ignore_patterns": "ALITHIA_ZOTERO_IGNORE",
        # Turnstile settings
        "turnstile.enabled": "ALITHIA_TURNSTILE_ENABLED",
        "turnstile.site_key": "ALITHIA_TURNSTILE_SITE_KEY",
        "turnstile.secret_key": "ALITHIA_TURNSTILE_SECRET_KEY",
        # General settings
        "debug": "ALITHIA_DEBUG",
    }

    for config_key, env_key in env_mapping.items():
        value = get_env(env_key)
        if value is not None:
            # Convert string values to appropriate types
            if config_key in [
                "researcher_profile.email_notification.smtp_port",
                "paperscout_agent.max_papers",
                "paperscout_agent.max_papers_queried",
            ]:
                try:
                    value = int(value)
                except ValueError:
                    continue
            elif config_key in [
                "paperscout_agent.send_email",
                "paperscout_agent.send_empty",
                "storage.fallback_to_sqlite",
                "turnstile.enabled",
                "debug",
            ]:
                value = str(value).lower() in ["true", "1", "yes"]
            elif config_key == "paperscout_agent.ignore_patterns" and value:
                value = [pattern.strip() for pattern in value.split(",") if pattern.strip()]
            elif config_key == "researcher_profile.research_interests" and value:
                value = [interest.strip() for interest in value.split(",") if interest.strip()]

            # Set nested value
            _set_nested_value(config, config_key, value)

    return config


def _set_nested_value(config: Dict[str, Any], key: str, value: Any) -> None:
    """
    Set a nested value in a dictionary using dot notation.

    Args:
        config: Configuration dictionary
        key: Dot-separated key (e.g., "llm.openai_api_key")
        value: Value to set
    """
    keys = key.split(".")
    current = config

    for k in keys[:-1]:
        if k not in current:
            current[k] = {}
        current = current[k]

    current[keys[-1]] = value


def _merge_configs(file_config: Dict[str, Any], env_config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Merge file config and environment config with environment taking precedence.

    Args:
        file_config: Configuration from file
        env_config: Configuration from environment variables

    Returns:
        Merged configuration
    """
    merged = file_config.copy()

    def merge_nested(target: Dict[str, Any], source: Dict[str, Any]) -> None:
        for key, value in source.items():
            if key in target and isinstance(target[key], dict) and isinstance(value, dict):
                merge_nested(target[key], value)
            else:
                target[key] = value

    merge_nested(merged, env_config)
    return merged

import json
import os
import tempfile
from unittest import mock

import pytest

from alithia.config_loader import (
    _build_config_from_envs,
    _load_config_from_file,
    _merge_configs,
    _set_nested_value,
    get_env,
    load_config,
)


@pytest.mark.unit
def test_get_env_returns_value():
    """Test that get_env returns the environment variable value."""
    with mock.patch.dict(os.environ, {"TEST_KEY": "test_value"}):
        assert get_env("TEST_KEY") == "test_value"


@pytest.mark.unit
def test_get_env_returns_default_for_missing_key():
    """Test that get_env returns default value for missing keys."""
    with mock.patch.dict(os.environ, {}, clear=False):
        assert get_env("NONEXISTENT_KEY", "default") == "default"


@pytest.mark.unit
def test_get_env_returns_default_for_empty_string():
    """Test that get_env treats empty strings as None and returns default."""
    with mock.patch.dict(os.environ, {"EMPTY_KEY": ""}, clear=False):
        assert get_env("EMPTY_KEY", "default") == "default"


@pytest.mark.unit
def test_set_nested_value_flat_key():
    """Test setting a flat key in config dictionary."""
    config = {}
    _set_nested_value(config, "key", "value")
    assert config == {"key": "value"}


@pytest.mark.unit
def test_set_nested_value_nested_key():
    """Test setting a nested key using dot notation."""
    config = {}
    _set_nested_value(config, "llm.openai_api_key", "test_key")
    assert config == {"llm": {"openai_api_key": "test_key"}}


@pytest.mark.unit
def test_set_nested_value_deeply_nested_key():
    """Test setting a deeply nested key with multiple levels."""
    config = {}
    _set_nested_value(config, "a.b.c.d", "value")
    assert config == {"a": {"b": {"c": {"d": "value"}}}}


@pytest.mark.unit
def test_set_nested_value_overwrites_existing():
    """Test that setting a nested value overwrites existing values."""
    config = {"llm": {"openai_api_key": "old_key"}}
    _set_nested_value(config, "llm.openai_api_key", "new_key")
    assert config == {"llm": {"openai_api_key": "new_key"}}


@pytest.mark.unit
def test_merge_configs_simple_values():
    """Test merging simple configuration values."""
    file_config = {"key1": "value1", "key2": "value2"}
    env_config = {"key2": "env_value2", "key3": "env_value3"}

    merged = _merge_configs(file_config, env_config)

    assert merged == {
        "key1": "value1",
        "key2": "env_value2",  # env takes precedence
        "key3": "env_value3",
    }


@pytest.mark.unit
def test_merge_configs_nested_values():
    """Test merging nested configuration values."""
    file_config = {
        "llm": {"openai_api_key": "file_key", "model_name": "gpt-3.5"},
        "zotero": {"zotero_id": "file_id"},
    }
    env_config = {
        "llm": {"openai_api_key": "env_key"},
        "zotero": {"zotero_key": "env_key"},
    }

    merged = _merge_configs(file_config, env_config)

    assert merged == {
        "llm": {"openai_api_key": "env_key", "model_name": "gpt-3.5"},
        "zotero": {"zotero_id": "file_id", "zotero_key": "env_key"},
    }


@pytest.mark.unit
def test_merge_configs_env_takes_precedence():
    """Test that environment config takes precedence in merging."""
    file_config = {"llm": {"model_name": "gpt-3.5", "openai_api_key": "file_key"}}
    env_config = {"llm": {"openai_api_key": "env_key"}}

    merged = _merge_configs(file_config, env_config)

    assert merged["llm"]["openai_api_key"] == "env_key"
    assert merged["llm"]["model_name"] == "gpt-3.5"


@pytest.mark.unit
def test_load_config_from_file_valid_json():
    """Test loading valid JSON configuration file."""
    config_data = {
        "research_interests": ["AI", "ML"],
        "llm": {"openai_api_key": "test_key"},
    }

    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(config_data, f)
        temp_path = f.name

    try:
        loaded_config = _load_config_from_file(temp_path)
        assert loaded_config == config_data
    finally:
        os.unlink(temp_path)


@pytest.mark.unit
def test_load_config_from_file_nonexistent():
    """Test that loading a non-existent file raises SystemExit."""
    with pytest.raises(SystemExit):
        _load_config_from_file("/path/that/does/not/exist.json")


@pytest.mark.unit
def test_load_config_from_file_invalid_json():
    """Test that loading invalid JSON raises SystemExit."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        f.write("{invalid json content")
        temp_path = f.name

    try:
        with pytest.raises(SystemExit):
            _load_config_from_file(temp_path)
    finally:
        os.unlink(temp_path)


@pytest.mark.unit
def test_build_config_from_envs_research_interests():
    """Test building config from environment variables - research interests."""
    env_vars = {
        "ALITHIA_RESEARCH_INTERESTS": "AI,Machine Learning,Computer Vision",
    }

    with mock.patch.dict(os.environ, env_vars, clear=False):
        config = _build_config_from_envs()
        assert config["researcher_profile"]["research_interests"] == ["AI", "Machine Learning", "Computer Vision"]


@pytest.mark.unit
def test_build_config_from_envs_integer_conversion():
    """Test that integer values are correctly converted."""
    env_vars = {
        "ALITHIA_SMTP_PORT": "587",
        "ALITHIA_MAX_PAPERS": "50",
        "ALITHIA_MAX_PAPERS_QUERIED": "200",
    }

    with mock.patch.dict(os.environ, env_vars, clear=False):
        config = _build_config_from_envs()
        assert config["researcher_profile"]["email_notification"]["smtp_port"] == 587
        assert config["paperscout_agent"]["max_papers"] == 50
        assert config["paperscout_agent"]["max_papers_queried"] == 200
        assert isinstance(config["researcher_profile"]["email_notification"]["smtp_port"], int)
        assert isinstance(config["paperscout_agent"]["max_papers"], int)
        assert isinstance(config["paperscout_agent"]["max_papers_queried"], int)


@pytest.mark.unit
def test_build_config_from_envs_boolean_conversion():
    """Test that boolean values are correctly converted."""
    test_cases = [
        ("true", True),
        ("True", True),
        ("1", True),
        ("yes", True),
        ("false", False),
        ("False", False),
        ("0", False),
        ("no", False),
    ]

    for env_value, expected in test_cases:
        env_vars = {"ALITHIA_SEND_EMPTY": env_value}
        with mock.patch.dict(os.environ, env_vars, clear=False):
            config = _build_config_from_envs()
            assert config["paperscout_agent"]["send_empty"] is expected


@pytest.mark.unit
def test_build_config_from_envs_ignore_patterns():
    """Test that ignore patterns are converted to list."""
    env_vars = {
        "ALITHIA_ZOTERO_IGNORE": "pattern1,pattern2,pattern3",
    }

    with mock.patch.dict(os.environ, env_vars, clear=False):
        config = _build_config_from_envs()
        assert config["paperscout_agent"]["ignore_patterns"] == ["pattern1", "pattern2", "pattern3"]


@pytest.mark.unit
def test_build_config_from_envs_integer_conversion_invalid():
    """Test that invalid integer values are skipped."""
    env_vars = {
        "ALITHIA_SMTP_PORT": "not_a_number",
    }

    with mock.patch.dict(os.environ, env_vars, clear=False):
        config = _build_config_from_envs()
        # Invalid integer values should be skipped
        assert (
            "researcher_profile" not in config
            or "email_notification" not in config.get("researcher_profile", {})
            or "smtp_port" not in config.get("researcher_profile", {}).get("email_notification", {})
        )


@pytest.mark.unit
def test_build_config_from_envs_all_llm_settings():
    """Test building all LLM settings from environment."""
    env_vars = {
        "ALITHIA_OPENAI_API_KEY": "test_key",
        "ALITHIA_OPENAI_API_BASE": "https://api.example.com/v1",
        "ALITHIA_MODEL_NAME": "gpt-4o",
    }

    with mock.patch.dict(os.environ, env_vars, clear=False):
        config = _build_config_from_envs()
        assert config["researcher_profile"]["llm"]["openai_api_key"] == "test_key"
        assert config["researcher_profile"]["llm"]["openai_api_base"] == "https://api.example.com/v1"
        assert config["researcher_profile"]["llm"]["model_name"] == "gpt-4o"


@pytest.mark.unit
def test_build_config_from_envs_all_zotero_settings():
    """Test building all Zotero settings from environment."""
    env_vars = {
        "ALITHIA_ZOTERO_ID": "test_id",
        "ALITHIA_ZOTERO_KEY": "test_key",
    }

    with mock.patch.dict(os.environ, env_vars, clear=False):
        config = _build_config_from_envs()
        assert config["researcher_profile"]["zotero"]["zotero_id"] == "test_id"
        assert config["researcher_profile"]["zotero"]["zotero_key"] == "test_key"


@pytest.mark.unit
def test_build_config_from_envs_all_email_notification_settings():
    """Test building all email notification settings from environment."""
    env_vars = {
        "ALITHIA_EMAIL": "user@example.com",
        "ALITHIA_SMTP_SERVER": "smtp.example.com",
        "ALITHIA_SMTP_PORT": "587",
        "ALITHIA_SENDER": "sender@example.com",
        "ALITHIA_SENDER_PASSWORD": "password",
    }

    with mock.patch.dict(os.environ, env_vars, clear=False):
        config = _build_config_from_envs()
        assert config["researcher_profile"]["email"] == "user@example.com"
        assert config["researcher_profile"]["email_notification"]["smtp_server"] == "smtp.example.com"
        assert config["researcher_profile"]["email_notification"]["smtp_port"] == 587
        assert config["researcher_profile"]["email_notification"]["sender"] == "sender@example.com"
        assert config["researcher_profile"]["email_notification"]["sender_password"] == "password"
        # Receiver is now the same as researcher email, not in email_notification
        assert "receiver" not in config["researcher_profile"]["email_notification"]


@pytest.mark.unit
def test_build_config_from_envs_debug_flag():
    """Test that debug flag is correctly converted."""
    env_vars = {"ALITHIA_DEBUG": "true"}

    with mock.patch.dict(os.environ, env_vars, clear=False):
        config = _build_config_from_envs()
        assert config["debug"] is True


@pytest.mark.unit
def test_load_config_with_nonexistent_file_raises_error():
    """Test that providing a non-existent config file raises FileNotFoundError."""
    with pytest.raises(FileNotFoundError):
        load_config("/path/that/does/not/exist.json")


@pytest.mark.unit
def test_load_config_env_only():
    """Test loading config from environment variables only."""
    env_vars = {
        "ALITHIA_OPENAI_API_KEY": "test_key",
        "ALITHIA_MODEL_NAME": "gpt-4o",
        "ALITHIA_ZOTERO_ID": "zotero_123",
    }

    with tempfile.TemporaryDirectory() as temp_dir:
        # Create a temporary directory without a config file
        with mock.patch.dict(os.environ, env_vars, clear=False):
            config = load_config()

            assert config["researcher_profile"]["llm"]["openai_api_key"] == "test_key"
            assert config["researcher_profile"]["llm"]["model_name"] == "gpt-4o"
            assert config["researcher_profile"]["zotero"]["zotero_id"] == "zotero_123"


@pytest.mark.unit
def test_load_config_file_only():
    """Test loading config from JSON file only."""
    config_data = {
        "researcher_profile": {
            "research_interests": ["AI", "ML"],
            "llm": {
                "openai_api_key": "file_key",
                "model_name": "gpt-3.5",
            },
            "zotero": {
                "zotero_id": "file_id",
                "zotero_key": "file_key",
            },
        }
    }

    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(config_data, f)
        temp_path = f.name

    try:
        with mock.patch.dict(os.environ, {}, clear=True):
            config = load_config(temp_path)

            assert config["researcher_profile"]["research_interests"] == ["AI", "ML"]
            assert config["researcher_profile"]["llm"]["openai_api_key"] == "file_key"
            assert config["researcher_profile"]["llm"]["model_name"] == "gpt-3.5"
            assert config["researcher_profile"]["zotero"]["zotero_id"] == "file_id"
    finally:
        os.unlink(temp_path)


@pytest.mark.unit
def test_load_config_env_overrides_file():
    """Test that environment variables take precedence over file config."""
    config_data = {
        "researcher_profile": {
            "llm": {
                "openai_api_key": "file_key",
                "model_name": "gpt-3.5",
            },
            "zotero": {
                "zotero_id": "file_id",
                "zotero_key": "file_key",
            },
        }
    }

    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(config_data, f)
        temp_path = f.name

    try:
        env_vars = {
            "ALITHIA_OPENAI_API_KEY": "env_key",
            "ALITHIA_ZOTERO_ID": "env_id",
        }

        with mock.patch.dict(os.environ, env_vars, clear=True):
            config = load_config(temp_path)

            # Environment values should override file values
            assert config["researcher_profile"]["llm"]["openai_api_key"] == "env_key"
            assert config["researcher_profile"]["zotero"]["zotero_id"] == "env_id"

            # File values should remain for non-overridden keys
            assert config["researcher_profile"]["llm"]["model_name"] == "gpt-3.5"
            assert config["researcher_profile"]["zotero"]["zotero_key"] == "file_key"
    finally:
        os.unlink(temp_path)


@pytest.mark.unit
def test_load_config_merged_nested_structures():
    """Test loading and merging complex nested structures."""
    config_data = {
        "researcher_profile": {
            "llm": {
                "openai_api_key": "file_key",
                "model_name": "gpt-3.5",
                "openai_api_base": "https://api.openai.com/v1",
            },
            "email_notification": {
                "smtp_server": "smtp.example.com",
                "smtp_port": 587,
                "sender": "sender@example.com",
            },
        }
    }

    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(config_data, f)
        temp_path = f.name

    try:
        env_vars = {
            "ALITHIA_OPENAI_API_KEY": "env_key",
            "ALITHIA_SMTP_SERVER": "smtp.env.com",
        }

        with mock.patch.dict(os.environ, env_vars, clear=True):
            config = load_config(temp_path)

            # Check merged LLM config
            assert config["researcher_profile"]["llm"]["openai_api_key"] == "env_key"
            assert config["researcher_profile"]["llm"]["model_name"] == "gpt-3.5"
            assert config["researcher_profile"]["llm"]["openai_api_base"] == "https://api.openai.com/v1"

            # Check merged email notification config
            assert config["researcher_profile"]["email_notification"]["smtp_server"] == "smtp.env.com"
            assert config["researcher_profile"]["email_notification"]["smtp_port"] == 587
            assert config["researcher_profile"]["email_notification"]["sender"] == "sender@example.com"
    finally:
        os.unlink(temp_path)


@pytest.mark.unit
def test_load_config_general_settings():
    """Test loading general settings from both sources."""
    config_data = {
        "researcher_profile": {
            "research_interests": ["File Interest"],
            "expertise_level": "beginner",
            "language": "English",
            "email": "file@example.com",
        }
    }

    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(config_data, f)
        temp_path = f.name

    try:
        env_vars = {
            "ALITHIA_EMAIL": "env@example.com",
            "ALITHIA_RESEARCH_INTERESTS": "AI,ML,CV",
        }

        with mock.patch.dict(os.environ, env_vars, clear=True):
            config = load_config(temp_path)

            # Environment overrides for email
            assert config["researcher_profile"]["email"] == "env@example.com"

            # Environment overrides for research interests
            assert config["researcher_profile"]["research_interests"] == ["AI", "ML", "CV"]

            # File values for non-overridden keys
            assert config["researcher_profile"]["expertise_level"] == "beginner"
            assert config["researcher_profile"]["language"] == "English"
    finally:
        os.unlink(temp_path)


@pytest.mark.unit
def test_load_config_paperscout_settings():
    """Test loading paperscout-specific settings."""
    config_data = {
        "paperscout_agent": {
            "query": "cs.AI+cs.CV",
            "max_papers": 50,
            "max_papers_queried": 200,
            "send_empty": False,
            "ignore_patterns": ["pattern1", "pattern2"],
        }
    }

    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(config_data, f)
        temp_path = f.name

    try:
        env_vars = {
            "ALITHIA_ARXIV_QUERY": "cs.LG",
            "ALITHIA_MAX_PAPERS": "100",
            "ALITHIA_MAX_PAPERS_QUERIED": "300",
            "ALITHIA_SEND_EMPTY": "true",
            "ALITHIA_ZOTERO_IGNORE": "ignore1,ignore2",
        }

        with mock.patch.dict(os.environ, env_vars, clear=False):
            config = load_config(temp_path)

            # Environment variables should override file config
            assert config["paperscout_agent"]["query"] == "cs.LG"
            assert config["paperscout_agent"]["max_papers"] == 100
            assert config["paperscout_agent"]["max_papers_queried"] == 300
            assert config["paperscout_agent"]["send_empty"] is True
            assert config["paperscout_agent"]["ignore_patterns"] == ["ignore1", "ignore2"]
    finally:
        os.unlink(temp_path)


@pytest.mark.unit
def test_load_config_with_whitespace_in_lists():
    """Test that list conversion handles whitespace correctly."""
    env_vars = {
        "ALITHIA_RESEARCH_INTERESTS": "  AI  ,  Machine Learning  ,  Computer Vision  ",
        "ALITHIA_ZOTERO_IGNORE": "  pattern1  ,  pattern2  ",
    }

    with tempfile.TemporaryDirectory():
        with mock.patch.dict(os.environ, env_vars, clear=False):
            config = _build_config_from_envs()

            # Whitespace should be stripped
            assert config["researcher_profile"]["research_interests"] == ["AI", "Machine Learning", "Computer Vision"]
            assert config["paperscout_agent"]["ignore_patterns"] == ["pattern1", "pattern2"]


@pytest.mark.unit
def test_load_config_empty_list_handling():
    """Test that empty lists in env are handled correctly."""
    env_vars = {
        "ALITHIA_RESEARCH_INTERESTS": "",  # Empty string should be treated as None
        "ALITHIA_ZOTERO_IGNORE": "   ,   ,   ",  # Only whitespace should result in empty list
    }

    with tempfile.TemporaryDirectory():
        with mock.patch.dict(os.environ, env_vars, clear=False):
            config = _build_config_from_envs()

            # Empty research interests should not be in config
            assert "researcher_profile" not in config or "research_interests" not in config.get(
                "researcher_profile", {}
            )

            # Whitespace-only patterns should result in empty list
            assert config["paperscout_agent"]["ignore_patterns"] == []


@pytest.mark.unit
def test_build_config_from_envs_supabase_settings():
    """Test that Supabase settings are loaded under storage.supabase."""
    env_vars = {
        "ALITHIA_SUPABASE_URL": "https://test-project.supabase.co",
        "ALITHIA_SUPABASE_ANON_KEY": "test_anon_key_12345",
        "ALITHIA_SUPABASE_SERVICE_ROLE_KEY": "test_service_role_key_67890",
    }

    with mock.patch.dict(os.environ, env_vars, clear=False):
        config = _build_config_from_envs()

        assert "storage" in config
        assert "supabase" in config["storage"]
        assert config["storage"]["supabase"]["url"] == "https://test-project.supabase.co"
        assert config["storage"]["supabase"]["anon_key"] == "test_anon_key_12345"
        assert config["storage"]["supabase"]["service_role_key"] == "test_service_role_key_67890"


@pytest.mark.unit
def test_build_config_from_envs_storage_settings():
    """Test that storage settings are loaded from environment variables."""
    env_vars = {
        "ALITHIA_STORAGE_BACKEND": "supabase",
        "ALITHIA_STORAGE_FALLBACK_TO_SQLITE": "true",
        "ALITHIA_STORAGE_SQLITE_PATH": "data/custom.db",
        "ALITHIA_STORAGE_USER_ID": "custom_user",
    }

    with mock.patch.dict(os.environ, env_vars, clear=False):
        config = _build_config_from_envs()

        assert "storage" in config
        assert config["storage"]["backend"] == "supabase"
        assert config["storage"]["fallback_to_sqlite"] is True
        assert config["storage"]["sqlite_path"] == "data/custom.db"
        assert config["storage"]["user_id"] == "custom_user"


@pytest.mark.unit
def test_build_config_from_envs_storage_boolean_conversion():
    """Test boolean conversion for storage.fallback_to_sqlite."""
    test_cases = [
        ("true", True),
        ("True", True),
        ("TRUE", True),
        ("1", True),
        ("yes", True),
        ("false", False),
        ("False", False),
        ("0", False),
        ("no", False),
        ("", False),  # Empty string defaults to False
    ]

    for value_str, expected in test_cases:
        env_vars = {"ALITHIA_STORAGE_FALLBACK_TO_SQLITE": value_str}

        with mock.patch.dict(os.environ, env_vars, clear=False):
            config = _build_config_from_envs()

            if value_str == "":
                # Empty string should not add the key
                assert "storage" not in config or "fallback_to_sqlite" not in config.get("storage", {})
            else:
                assert (
                    config["storage"]["fallback_to_sqlite"] == expected
                ), f"Expected {expected} for value '{value_str}', got {config['storage']['fallback_to_sqlite']}"


@pytest.mark.unit
def test_load_config_storage_env_overrides_file():
    """Test that storage env variables override file configuration."""
    file_content = {
        "storage": {
            "backend": "sqlite",
            "sqlite_path": "data/file.db",
            "supabase": {
                "url": "https://file-project.supabase.co",
                "anon_key": "file_anon_key",
            },
        },
    }

    env_vars = {
        "ALITHIA_SUPABASE_URL": "https://env-project.supabase.co",
        "ALITHIA_STORAGE_BACKEND": "supabase",
    }

    with tempfile.TemporaryDirectory() as tmpdir:
        config_file = os.path.join(tmpdir, "config.json")
        with open(config_file, "w") as f:
            json.dump(file_content, f)

        with mock.patch.dict(os.environ, env_vars, clear=False):
            config = load_config(config_file)

            # Env should override file
            assert config["storage"]["supabase"]["url"] == "https://env-project.supabase.co"
            assert config["storage"]["backend"] == "supabase"

            # File values should remain for non-overridden keys
            assert config["storage"]["supabase"]["anon_key"] == "file_anon_key"
            assert config["storage"]["sqlite_path"] == "data/file.db"


@pytest.mark.unit
def test_load_config_all_storage_settings():
    """Test loading all storage and supabase settings together."""
    env_vars = {
        "ALITHIA_SUPABASE_URL": "https://complete-test.supabase.co",
        "ALITHIA_SUPABASE_ANON_KEY": "complete_anon_key",
        "ALITHIA_SUPABASE_SERVICE_ROLE_KEY": "complete_service_key",
        "ALITHIA_STORAGE_BACKEND": "supabase",
        "ALITHIA_STORAGE_FALLBACK_TO_SQLITE": "yes",
        "ALITHIA_STORAGE_SQLITE_PATH": "data/alithia.db",
        "ALITHIA_STORAGE_USER_ID": "test_user_id",
    }

    with mock.patch.dict(os.environ, env_vars, clear=False):
        config = _build_config_from_envs()

        # Supabase is now nested under storage.supabase
        assert config["storage"]["supabase"]["url"] == "https://complete-test.supabase.co"
        assert config["storage"]["supabase"]["anon_key"] == "complete_anon_key"
        assert config["storage"]["supabase"]["service_role_key"] == "complete_service_key"

        # Check all storage settings
        assert config["storage"]["backend"] == "supabase"
        assert config["storage"]["fallback_to_sqlite"] is True
        assert config["storage"]["sqlite_path"] == "data/alithia.db"
        assert config["storage"]["user_id"] == "test_user_id"


@pytest.mark.unit
def test_load_config_legacy_supabase_migration():
    """Test that legacy top-level supabase config is migrated into storage.supabase."""
    file_content = {
        "supabase": {
            "url": "https://legacy-project.supabase.co",
            "anon_key": "legacy_anon_key",
        },
        "storage": {
            "backend": "supabase",
        },
    }

    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(file_content, f)
        temp_path = f.name

    try:
        with mock.patch.dict(os.environ, {}, clear=True):
            config = load_config(temp_path)

            # Legacy supabase should be moved under storage.supabase
            assert "supabase" not in config
            assert config["storage"]["supabase"]["url"] == "https://legacy-project.supabase.co"
            assert config["storage"]["supabase"]["anon_key"] == "legacy_anon_key"
    finally:
        os.unlink(temp_path)

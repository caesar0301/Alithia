"""AlithiaAgent wrapper class for soothe framework integration.

Provides branded CLI entry point that:
- Sets SOOTHE_HOME to ~/.alithia/soothe/
- Loads alithia domain config from ~/.alithia/config.yml
- Registers paperscout/paperlens plugins in soothe's global registry
- Creates and manages soothe CoreAgent for execution
"""

from __future__ import annotations

import logging
import os
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

from alithia_agent import ALITHIA_HOME, SOOTHE_HOME
from alithia_agent.config import load_config, Config
from alithia_agent.storage import AlithiaStore

# Soothe imports - handle gracefully if not fully available
try:
    from soothe.core import CoreAgent, create_soothe_agent
    from soothe.config.settings import SootheConfig
    HAS_SOOTHE = True
except ImportError as e:
    HAS_SOOTHE = False
    CoreAgent = None  # type: ignore
    create_soothe_agent = None  # type: ignore
    SootheConfig = None  # type: ignore

logger = logging.getLogger(__name__)


class AlithiaAgent:
    """Alithia research assistant powered by soothe framework.

    Wraps soothe's CoreAgent with alithia-specific initialization:
    - Uses SOOTHE_HOME=~/.alithia/soothe/ (set in __init__.py)
    - Loads alithia domain config from ~/.alithia/config.yml
    - Registers paperscout/paperlens plugins in soothe's global registry
    - Provides branded execution interface with alithia defaults

    Example:
        agent = AlithiaAgent()
        async for chunk in agent.run("Find new papers about transformers"):
            print(chunk)
    """

    def __init__(self, config_path: str | None = None) -> None:
        """Initialize AlithiaAgent.

        Args:
            config_path: Optional override for alithia config path.

        Note:
            SOOTHE_HOME is already set in alithia_agent.__init__.py
            before any soothe imports happen.

        Raises:
            RuntimeError: If soothe framework is not available.
        """
        if not HAS_SOOTHE:
            raise RuntimeError(
                "Soothe framework not available. "
                "Install soothe package to use AlithiaAgent."
            )

        # Ensure soothe directories exist
        self._setup_soothe_directories()

        # Load alithia domain config
        self._alithia_config = load_config(config_path)

        # Register alithia plugins in soothe's global registry
        # This must happen BEFORE create_soothe_agent()
        self._register_plugins()

        # Load soothe config (from SOOTHE_HOME/config/config.yml)
        soothe_config_path = SOOTHE_HOME / "config" / "config.yml"
        if soothe_config_path.exists():
            self._soothe_config = SootheConfig.from_file(soothe_config_path)
        else:
            # Create default soothe config
            self._soothe_config = self._create_default_soothe_config()
            logger.warning(
                f"Soothe config not found at {soothe_config_path}. "
                "Using defaults. Create config.yml for customization."
            )

        # Create soothe CoreAgent
        self._core_agent = self._create_core_agent()

        logger.info(f"AlithiaAgent initialized (SOOTHE_HOME={SOOTHE_HOME})")

    def _setup_soothe_directories(self) -> None:
        """Ensure soothe directory structure exists."""
        (SOOTHE_HOME / "config").mkdir(parents=True, exist_ok=True)
        (SOOTHE_HOME / "logs").mkdir(parents=True, exist_ok=True)
        (ALITHIA_HOME / "data").mkdir(parents=True, exist_ok=True)

    def _register_plugins(self) -> None:
        """Register alithia plugins in soothe's global registry."""
        from alithia_agent.plugins import register_alithia_plugins

        register_alithia_plugins()
        logger.debug("Alithia plugins registered in soothe global registry")

    def _create_default_soothe_config(self) -> Any:
        """Create default soothe configuration.

        Returns:
            SootheConfig with minimal defaults for alithia.
        """
        # Create default config with OpenAI provider (can be overridden)
        default_config = {
            "providers": {
                "openai": {
                    "api_key": os.environ.get("OPENAI_API_KEY", ""),
                },
            },
            "models": {
                "default": "openai:gpt-4o-mini",
            },
            "subagents": {
                "paperscout": {
                    "enabled": True,
                    "triggers": ["new papers", "arxiv", "paper digest", "daily papers"],
                },
                "paperlens": {
                    "enabled": True,
                    "triggers": ["rank papers", "analyze pdf", "similar papers", "local papers"],
                },
            },
            "tools": ["file_ops", "websearch"],
            "memory": {"enabled": False},
            "planner": {"enabled": True},
        }

        return SootheConfig(**default_config)

    def _create_core_agent(self) -> Any:
        """Create soothe CoreAgent with alithia configuration.

        Returns:
            CoreAgent instance with registered plugins.
        """
        # Create storage implementing AsyncPersistStore
        store = AlithiaStore(self._alithia_config.storage.user_id)

        # Create CoreAgent with alithia-specific kwargs
        # These kwargs are passed to subagent factories
        agent = create_soothe_agent(
            self._soothe_config,
            # Pass alithia config to subagent factories via kwargs
            alithia_config=self._alithia_config.model_dump(),
            store=store,
            user_id=self._alithia_config.storage.user_id,
        )

        logger.debug("CoreAgent created with alithia configuration")
        return agent

    async def run(
        self,
        user_input: str,
        *,
        thread_id: str | None = None,
        stream_mode: list[str] | None = None,
        subagent: str | None = None,
    ) -> AsyncIterator[Any]:
        """Run user input through soothe's agent loop.

        Args:
            user_input: Natural language input from user.
            thread_id: Optional thread identifier for persistence.
            stream_mode: Optional stream mode (default: ["messages", "updates"]).
            subagent: Optional explicit subagent name (bypasses intent routing).

        Returns:
            AsyncIterator of stream events from soothe execution.
        """
        config: dict[str, Any] = {}

        if thread_id:
            config["configurable"] = {"thread_id": thread_id}

        # If explicit subagent requested, add execution hint
        if subagent:
            if "configurable" not in config:
                config["configurable"] = {}
            config["configurable"]["soothe_step_subagent"] = subagent

        if stream_mode is None:
            stream_mode = ["messages", "updates"]

        logger.info(f"Running user input: {user_input[:50]}...")

        return self._core_agent.astream(
            user_input,
            config or None,
            stream_mode=stream_mode,
        )

    @property
    def core_agent(self) -> Any:
        """Access underlying soothe CoreAgent."""
        return self._core_agent

    @property
    def alithia_config(self) -> Config:
        """Access alithia domain configuration."""
        return self._alithia_config

    @classmethod
    def create(cls, config_path: str | None = None) -> "AlithiaAgent":
        """Factory method for AlithiaAgent.

        Args:
            config_path: Optional config file path override.

        Returns:
            AlithiaAgent instance.
        """
        return cls(config_path)


__all__ = ["AlithiaAgent"]
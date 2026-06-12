"""AlithiaAgent wrapper class for soothe framework integration.

Provides branded CLI entry point that:
- Sets SOOTHE_HOME to ~/.alithia/soothe/
- Loads alithia domain config from ~/.alithia/config.yml
- Registers paperscout/paperlens plugins in soothe's global registry
- Creates and manages soothe SootheRunner for protocol-orchestrated execution
"""

from __future__ import annotations

import logging
import os
from collections.abc import AsyncIterator
from typing import Any

from alithia_agent import ALITHIA_HOME, SOOTHE_HOME
from alithia_agent.config import Config, load_config

# Soothe imports - handle gracefully if not fully available
try:
    from soothe.config.settings import SootheConfig
    from soothe.runner import SootheRunner

    HAS_SOOTHE = True
except ImportError:
    HAS_SOOTHE = False
    SootheRunner = None  # type: ignore
    SootheConfig = None  # type: ignore

logger = logging.getLogger(__name__)


class AlithiaAgent:
    """Alithia research assistant powered by soothe framework.

    Wraps soothe's SootheRunner with alithia-specific initialization:
    - Uses SOOTHE_HOME=~/.alithia/soothe/ (set in __init__.py)
    - Loads alithia domain config from ~/.alithia/config.yml
    - Registers paperscout/paperlens plugins in soothe's global registry
    - Provides branded execution interface with alithia defaults

    Example:
        agent = AlithiaAgent()
        async for chunk in agent.run("Find new papers about transformers"):
            print(chunk)

        # Explicitly route to paperscout subagent
        async for chunk in agent.run("arxiv daily papers", subagent="paperscout"):
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
                "Soothe framework not available. Install soothe package to use AlithiaAgent."
            )

        # Ensure soothe directories exist
        self._setup_soothe_directories()

        # Load alithia domain config
        self._alithia_config = load_config(config_path)

        # Register alithia plugins in soothe's global registry
        # This must happen BEFORE SootheRunner initialization
        self._register_plugins()

        # Load soothe config (from SOOTHE_HOME/config/config.yml)
        soothe_config_path = SOOTHE_HOME / "config" / "config.yml"
        if soothe_config_path.exists():
            self._soothe_config = SootheConfig.from_yaml_file(str(soothe_config_path))
        else:
            # Create default soothe config
            self._soothe_config = self._create_default_soothe_config()
            logger.warning(
                f"Soothe config not found at {soothe_config_path}. "
                "Using defaults. Create config.yml for customization."
            )

        # Create soothe SootheRunner (Layer 2 with protocol orchestration)
        self._runner = self._create_runner()

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
        # Create default config matching SootheConfig structure
        # providers: list of ModelProviderConfig
        # tools: ToolsConfig with enabled tool categories
        # subagents: dict of SubagentConfig
        default_config = {
            "providers": [
                {
                    "name": "openai",
                    "api_key": os.environ.get("OPENAI_API_KEY", ""),
                },
            ],
            "router": {"default": "openai:gpt-4o-mini"},
            "subagents": {
                "paperscout": {
                    "enabled": True,
                },
                "paperlens": {
                    "enabled": True,
                },
            },
            "tools": {
                "file_ops": {"enabled": True},
                "wizsearch": {"enabled": True},
            },
            "memory": [],  # No memory plugins by default
            "debug": False,
        }

        return SootheConfig(**default_config)

    def _create_runner(self) -> Any:
        """Create soothe SootheRunner with alithia configuration.

        SootheRunner is Layer 2 of soothe architecture, providing:
        - Protocol orchestration (intent classification, goal engine)
        - Canonical StreamChunk format with soothe.* events
        - preferred_subagent parameter for explicit routing

        Returns:
            SootheRunner instance ready for astream() execution.
        """
        # SootheRunner handles all agent creation internally
        # Plugins were registered earlier in _register_plugins()
        runner = SootheRunner(self._soothe_config)

        logger.debug("SootheRunner created with alithia configuration")
        return runner

    async def run(
        self,
        user_input: str,
        *,
        thread_id: str | None = None,
        subagent: str | None = None,
    ) -> AsyncIterator[Any]:
        """Run user input through soothe's runner loop.

        Args:
            user_input: Natural language input from user.
            thread_id: Optional thread identifier for persistence.
            subagent: Optional explicit subagent name (bypasses intent routing).
                When specified, uses SootheRunner's preferred_subagent parameter
                which sets routing_hint="subagent" in RoutingClassification.

        Returns:
            AsyncIterator of StreamChunk tuples from soothe execution.
            Each chunk is (namespace, mode, data) in canonical format.
        """
        logger.info(f"Running user input: {user_input[:50]}...")

        # Use SootheRunner.astream() with preferred_subagent for explicit routing
        # This is the clean Layer 2 API that handles RoutingClassification internally
        return self._runner.astream(  # type: ignore[no-any-return]
            user_input,
            thread_id=thread_id,
            preferred_subagent=subagent,  # Explicit routing when provided
        )

    @property
    def runner(self) -> Any:
        """Access underlying soothe SootheRunner."""
        return self._runner

    @property
    def alithia_config(self) -> Config:
        """Access alithia domain configuration."""
        return self._alithia_config

    @classmethod
    def create(cls, config_path: str | None = None) -> AlithiaAgent:
        """Factory method for AlithiaAgent.

        Args:
            config_path: Optional config file path override.

        Returns:
            AlithiaAgent instance.
        """
        return cls(config_path)


__all__ = ["AlithiaAgent"]

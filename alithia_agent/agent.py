"""Alithia agent bootstrap on soothe-nano (flowjet-style host).

Provides branded CLI entry that:
- Uses SOOTHE_HOME=~/.alithia/soothe/ (set in ``alithia_agent.__init__``)
- Loads nano.yml via the same resolution order as flowjet-agent
- Loads alithia domain config from ~/.alithia/config.yml
- Enables paperscout/paperlens plugins and nano deepxiv tools
- Builds an in-process SootheNanoAgent via create_nano_agent

Alithia does not use soothed / soothe-daemon.
"""

from __future__ import annotations

import logging
import os
import uuid
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any, Literal

from langchain_core.messages import HumanMessage
from soothe_nano import SootheNanoAgent, create_nano_agent
from soothe_nano.config import SOOTHE_HOME, SootheConfig
from soothe_nano.config.models import SubagentConfig

from alithia_agent import ALITHIA_HOME
from alithia_agent.config import Config
from alithia_agent.config import load_config as load_alithia_config
from alithia_agent.soothe_defaults import apply_soothe_home_defaults

logger = logging.getLogger(__name__)

_RESEARCH_SYSTEM_PROMPT = """\
You are Alithia, a research assistant for academic paper discovery and analysis.

Guidelines:
- Be direct and concise. Lead with answers, not preambles.
- Prefer paperscout for ArXiv digests, daily papers, and email notifications.
- Prefer paperlens for ranking or analyzing local PDF collections.
- Use deepxiv tools for targeted academic paper search and section reading.
- Never reference your internal architecture, frameworks, or technical stack.
"""


# ---------------------------------------------------------------------------
# nano.yml (soothe-nano) — same API surface as flowjet-agent
# ---------------------------------------------------------------------------


def default_config_path() -> Path:
    """Return ``$SOOTHE_HOME/config/nano.yml``.

    Alithia sets ``SOOTHE_HOME`` to ``~/.alithia/soothe`` before nano imports.
    Reads the live env so late redirects / tests still resolve correctly.
    """
    home = Path(os.environ.get("SOOTHE_HOME", str(SOOTHE_HOME))).expanduser()
    return home / "config" / "nano.yml"


def load_config(config_path: str | Path | None = None) -> SootheConfig:
    """Load ``SootheConfig`` from nano.yml, or bootstrap from env when missing.

    Resolution order (matches flowjet-agent):
    1. Explicit ``config_path``
    2. ``$SOOTHE_HOME/config/nano.yml`` (default ``~/.alithia/soothe/config/nano.yml``)
    3. ``SootheConfig()`` zero-config from ``OPENAI_API_KEY`` / ``ANTHROPIC_API_KEY``
    """
    path = Path(config_path).expanduser() if config_path else default_config_path()
    if path.is_file():
        return SootheConfig.from_yaml_file(str(path))
    if config_path is not None:
        raise FileNotFoundError(f"Config not found: {path}")
    return SootheConfig()


# Backward-compatible aliases
default_nano_config_path = default_config_path
load_nano_config = load_config


def apply_alithia_defaults(config: SootheConfig) -> SootheConfig:
    """Apply alithia CLI defaults without requiring them in ``nano.yml``.

    - SQLite checkpointer / durability
    - Enable paperscout / paperlens subagents
    - Enable nano built-in deepxiv tools
    - Research-oriented system prompt when unset / stock default
    - Redirect memory paths under ``$SOOTHE_HOME``
    """
    soothe_home = Path(os.environ.get("SOOTHE_HOME", str(SOOTHE_HOME))).expanduser()

    durability = config.agent.protocols.durability.model_copy(
        update={"backend": "sqlite", "checkpointer": "sqlite"}
    )
    protocols = config.agent.protocols.model_copy(update={"durability": durability})
    agent_updates: dict[str, Any] = {"protocols": protocols}
    prompt = (config.agent.system_prompt or "").strip()
    if not prompt or "Soothe" in prompt:
        agent_updates["system_prompt"] = _RESEARCH_SYSTEM_PROMPT
    agent = config.agent.model_copy(update=agent_updates)

    persistence = config.persistence.model_copy(update={"default_backend": "sqlite"})

    subagents = dict(config.subagents)
    for name in ("paperscout", "paperlens"):
        existing = subagents.get(name)
        if existing is None:
            subagents[name] = SubagentConfig(enabled=True)
        elif not existing.enabled:
            subagents[name] = existing.model_copy(update={"enabled": True})

    tools = config.tools
    deepxiv = tools.deepxiv.model_copy(update={"enabled": True})
    tools = tools.model_copy(update={"deepxiv": deepxiv})

    updated = config.model_copy(
        update={
            "agent": agent,
            "persistence": persistence,
            "subagents": subagents,
            "tools": tools,
        }
    )
    apply_soothe_home_defaults(updated, soothe_home)
    return updated


def build_agent(
    config: SootheConfig,
    *,
    verbose: bool = False,
) -> SootheNanoAgent:
    """Build a soothe-nano agent with alithia plugins enabled."""
    from alithia_agent.plugin_registration import register_alithia_plugins

    register_alithia_plugins()
    agent = create_nano_agent(apply_alithia_defaults(config))
    if verbose:
        names = []
        for s in agent.subagents:
            if isinstance(s, dict):
                names.append(s.get("name", "?"))
            else:
                names.append(getattr(s, "name", "?"))
        logger.debug("Nano agent ready (subagents=%s)", names)
    return agent


class AlithiaAgent:
    """Alithia research assistant powered by soothe-nano.

    Example:
        agent = AlithiaAgent()
        async for chunk in agent.run("Find new papers about transformers"):
            print(chunk)
    """

    def __init__(
        self,
        config_path: str | Path | None = None,
        *,
        alithia_config_path: str | Path | None = None,
        verbose: bool = False,
    ) -> None:
        """Initialize AlithiaAgent.

        Args:
            config_path: Optional override for nano.yml (soothe-nano).
            alithia_config_path: Optional override for domain ``~/.alithia/config.yml``.
            verbose: Log extra bootstrap detail.
        """
        self._setup_directories()
        self._alithia_config = load_alithia_config(
            str(alithia_config_path) if alithia_config_path else None
        )
        self._nano_config = load_config(config_path)
        self._verbose = verbose
        self._agent = build_agent(self._nano_config, verbose=verbose)
        logger.info(
            "AlithiaAgent initialized (SOOTHE_HOME=%s, nano.yml=%s)",
            os.environ.get("SOOTHE_HOME", SOOTHE_HOME),
            default_config_path(),
        )

    def _setup_directories(self) -> None:
        """Ensure alithia / soothe directory structure exists."""
        home = Path(os.environ.get("SOOTHE_HOME", str(SOOTHE_HOME))).expanduser()
        (home / "config").mkdir(parents=True, exist_ok=True)
        (home / "logs").mkdir(parents=True, exist_ok=True)
        (home / "memory").mkdir(parents=True, exist_ok=True)
        (home / "data").mkdir(parents=True, exist_ok=True)
        (ALITHIA_HOME / "data").mkdir(parents=True, exist_ok=True)

    async def run(
        self,
        user_input: str,
        *,
        thread_id: str | None = None,
        subagent: str | None = None,
    ) -> AsyncIterator[Any]:
        """Run user input through the in-process nano agent.

        Args:
            user_input: Natural language input from user.
            thread_id: Optional thread identifier for persistence.
            subagent: Optional local convenience hint appended to the query
                (biases the model toward a named specialist). Not soothed routing.

        Yields:
            Nano ``astream`` chunks ``(namespace, mode, data)``.
        """
        prompt = user_input
        if subagent:
            prompt = f"[Please use the {subagent} subagent for this request.]\n\n{user_input}"
        tid = thread_id or f"alithia-{uuid.uuid4().hex[:12]}"
        logger.info("Running user input (thread=%s): %s...", tid, prompt[:50])
        config = {"configurable": {"thread_id": tid}}
        async for chunk in self._agent.astream(
            {"messages": [HumanMessage(content=prompt)]},
            config=config,
            stream_mode=["messages", "updates", "custom"],
            subgraphs=True,
        ):
            yield chunk

    async def run_paperscout(
        self,
        *,
        from_date: str,
        to_date: str | None = None,
        source: Literal["manual", "scheduler", "scheduler_retry", "gap_fill"] = "manual",
    ) -> Any:
        """Run PaperScout directly for an explicit date range (daemon path)."""
        from alithia_agent.paperscout.runner import run_paperscout_for_dates
        from alithia_agent.storage.sqlite import AlithiaStore

        resolved_to_date = to_date or from_date
        store = AlithiaStore(
            user_id=self._alithia_config.storage.user_id,
        )

        return await run_paperscout_for_dates(
            self._alithia_config,
            store,
            self._alithia_config.storage.user_id,
            from_date=from_date,
            to_date=resolved_to_date,
            source=source,
        )

    @property
    def nano_agent(self) -> SootheNanoAgent:
        """Access underlying soothe-nano agent."""
        return self._agent

    @property
    def runner(self) -> SootheNanoAgent:
        """Backward-compatible alias for ``nano_agent``."""
        return self._agent

    @property
    def alithia_config(self) -> Config:
        """Access alithia domain configuration."""
        return self._alithia_config

    @classmethod
    def create(
        cls,
        config_path: str | Path | None = None,
        **kwargs: Any,
    ) -> AlithiaAgent:
        """Factory method for AlithiaAgent.

        Args:
            config_path: Optional nano.yml path (same as flowjet ``-c``).
        """
        return cls(config_path, **kwargs)


__all__ = [
    "AlithiaAgent",
    "apply_alithia_defaults",
    "build_agent",
    "default_config_path",
    "default_nano_config_path",
    "load_config",
    "load_nano_config",
]

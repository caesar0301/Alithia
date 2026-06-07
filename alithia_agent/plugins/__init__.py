"""Alithia plugins for soothe framework integration.

Provides plugin registration for paperscout and paperlens subagents.
Plugins are registered via:
1. Entry points in pyproject.toml (preferred, when package is installed)
2. Manual registration fallback (for development without install)
"""

from __future__ import annotations

import importlib.metadata
import logging

logger = logging.getLogger(__name__)


def _check_entry_points_registered() -> bool:
    """Check if alithia plugins are registered via entry points.

    Returns:
        True if plugins are discoverable via soothe.plugins entry points.
    """
    try:
        entry_points = importlib.metadata.entry_points(group="soothe.plugins")
        for ep in entry_points:
            if ep.name in ("paperscout", "paperlens"):
                logger.debug(f"Found {ep.name} in soothe.plugins entry points")
                return True
    except Exception:
        pass
    return False


def register_alithia_plugins() -> None:
    """Register alithia plugins in soothe's global registry.

    Uses entry points when package is installed (preferred).
    Falls back to manual registration for development without install.

    Note:
        When running via `uv run` or `pip install -e .`, entry points
        are automatically registered. Manual registration is only needed
        when running directly from source without installation.
    """
    # Check if already registered via entry points
    if _check_entry_points_registered():
        logger.info("Alithia plugins available via entry points (no manual registration needed)")
        return

    logger.info("Entry points not found, using manual plugin registration")

    try:
        # Create registry if not initialized
        import soothe.plugin.global_registry as gr_module
        from soothe.plugin.registry import PluginRegistry

        if gr_module._global_registry is None:
            gr_module._global_registry = PluginRegistry()
            logger.debug("Created new global plugin registry")

        registry = gr_module._global_registry

        # Import and register paperscout plugin
        from alithia_agent.plugins.paperscout import PaperScoutPlugin

        registry.register(
            PaperScoutPlugin._plugin_manifest,
            source="config",
            priority=30,  # PRIORITY_CONFIG level
        )
        logger.info("Manually registered paperscout plugin")

        # Import and register paperlens plugin
        from alithia_agent.plugins.paperlens import PaperLensPlugin

        registry.register(
            PaperLensPlugin._plugin_manifest,
            source="config",
            priority=30,
        )
        logger.info("Manually registered paperlens plugin")

    except ImportError as e:
        logger.warning(f"Could not register alithia plugins: {e}")
        raise


__all__ = ["register_alithia_plugins"]

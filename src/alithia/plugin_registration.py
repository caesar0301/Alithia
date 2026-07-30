"""Alithia plugin registration for soothe-nano.

Plugins are registered via:
1. Entry points in pyproject.toml (preferred, when package is installed)
2. Manual registration fallback (for development without install)
"""

from __future__ import annotations

import importlib.metadata
import logging

logger = logging.getLogger(__name__)

_ALITHIA_PLUGIN_NAMES = frozenset({"paperscout", "paperlens", "omr"})


def _check_entry_points_registered() -> bool:
    """Return True if any alithia plugin is discoverable via soothe.plugins."""
    try:
        entry_points = importlib.metadata.entry_points(group="soothe.plugins")
        for ep in entry_points:
            if ep.name in _ALITHIA_PLUGIN_NAMES:
                logger.debug("Found %s in soothe.plugins entry points", ep.name)
                return True
    except Exception:
        pass
    return False


def register_alithia_plugins() -> None:
    """Register alithia plugins in soothe-nano's global registry when needed.

    Uses entry points when the package is installed (preferred). Falls back to
    manual registration for development without install.

    Note:
        ``create_nano_agent`` also loads plugins via entry points. Manual
        registration is only needed when running from source without install.
    """
    if _check_entry_points_registered():
        logger.info("Alithia plugins available via entry points (no manual registration needed)")
        return

    logger.info("Entry points not found, using manual plugin registration")

    try:
        import soothe_nano.plugin.global_registry as gr_module
        from soothe_nano.plugin.registry import PluginRegistry

        if gr_module._global_registry is None:
            gr_module._global_registry = PluginRegistry()
            logger.debug("Created new global plugin registry")

        registry = gr_module._global_registry

        from alithia.paperscout import PaperScoutPlugin

        registry.register(
            getattr(PaperScoutPlugin, "_plugin_manifest"),
            source="config",
            priority=30,
        )
        logger.info("Manually registered paperscout plugin")

        from alithia.paperlens import PaperLensPlugin

        registry.register(
            getattr(PaperLensPlugin, "_plugin_manifest"),
            source="config",
            priority=30,
        )
        logger.info("Manually registered paperlens plugin")

        from alithia.omr import OmniResearchPlugin

        registry.register(
            getattr(OmniResearchPlugin, "_plugin_manifest"),
            source="config",
            priority=30,
        )
        logger.info("Manually registered omr plugin")

    except ImportError as e:
        logger.warning("Could not register alithia plugins: %s", e)
        raise


__all__ = ["register_alithia_plugins"]

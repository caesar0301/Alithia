"""Alithia plugins for soothe framework integration.

Provides plugin registration for paperscout and paperlens subagents.
Uses soothe's global registry for discovery by AgentBuilder.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def register_alithia_plugins() -> None:
    """Register alithia plugins in soothe's global registry.

    This function must be called BEFORE create_soothe_agent() is invoked,
    as AgentBuilder._load_plugins() uses the global registry for discovery.

    Registration uses priority=30 (PRIORITY_CONFIG level) for explicit
    in-app registration (not entry_point or filesystem discovery).
    """
    try:
        from soothe.plugin.global_registry import get_plugin_registry, _global_registry
        from soothe.plugin import PluginRegistry

        # Try to get existing registry, or create one if not initialized
        try:
            registry = get_plugin_registry()
        except RuntimeError:
            # Registry not initialized yet - we need to create one
            # The _global_registry variable is the internal singleton
            import soothe.plugin.global_registry as gr_module
            if gr_module._global_registry is None:
                gr_module._global_registry = PluginRegistry()
            registry = gr_module._global_registry
            logger.info("Created new global plugin registry for alithia plugins")

        # Import and register paperscout plugin
        from alithia_agent.plugins.paperscout import PaperScoutPlugin
        registry.register(
            PaperScoutPlugin._plugin_manifest,
            source="config",
            priority=30,
        )
        logger.info("Registered paperscout plugin in soothe global registry")

        # Import and register paperlens plugin
        from alithia_agent.plugins.paperlens import PaperLensPlugin
        registry.register(
            PaperLensPlugin._plugin_manifest,
            source="config",
            priority=30,
        )
        logger.info("Registered paperlens plugin in soothe global registry")

    except ImportError as e:
        logger.warning(f"Could not register alithia plugins: {e}")
        raise


__all__ = ["register_alithia_plugins"]
"""Resolve alithia domain config and store for plugin factories."""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


def resolve_alithia_runtime(
    *,
    alithia_config: Any | None = None,
    store: Any | None = None,
    user_id: str | None = None,
) -> tuple[Any, Any | None, str]:
    """Return ``(Config, AlithiaStore|None, user_id)`` for plugin factories.

    When kwargs omit domain objects (normal nano host path), load from
    ``ALITHIA_HOME/config.yml`` and construct an ``AlithiaStore``.
    """
    from alithia.config import Config, load_config

    cfg: Config
    if alithia_config is None:
        cfg = load_config()
    elif isinstance(alithia_config, Config):
        cfg = alithia_config
    elif isinstance(alithia_config, dict):
        try:
            cfg = Config(**alithia_config)
        except Exception as e:
            logger.warning("Could not parse alithia_config dict: %s; loading defaults", e)
            cfg = load_config()
    else:
        cfg = load_config()

    uid = user_id or cfg.storage.user_id or "default"

    resolved_store = store
    if resolved_store is None:
        try:
            from alithia.storage.sqlite import AlithiaStore

            resolved_store = AlithiaStore(user_id=uid)
        except Exception as e:
            logger.warning("Could not construct AlithiaStore: %s", e)
            resolved_store = None

    return cfg, resolved_store, uid


__all__ = ["resolve_alithia_runtime"]

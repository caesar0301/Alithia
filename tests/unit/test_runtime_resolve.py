"""Tests for plugin runtime config/store self-loading."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from alithia.config.schema import Config, PaperScoutAgentConfig
from alithia.runtime_resolve import resolve_alithia_runtime


def _minimal_config(**kwargs: object) -> Config:
    return Config(
        paperscout_agent=PaperScoutAgentConfig(send_email=False),
        **kwargs,  # type: ignore[arg-type]
    )


def test_resolve_loads_config_when_kwargs_omitted() -> None:
    cfg = _minimal_config()
    store = MagicMock(name="store")
    with (
        patch("alithia.config.load_config", return_value=cfg) as load,
        patch("alithia.storage.sqlite.AlithiaStore", return_value=store),
    ):
        out_cfg, out_store, uid = resolve_alithia_runtime()
    load.assert_called_once()
    assert out_cfg is cfg
    assert out_store is store
    assert uid == cfg.storage.user_id


def test_resolve_uses_provided_config_dict_and_store() -> None:
    store = MagicMock(name="store")
    cfg_dict = _minimal_config().model_dump()
    out_cfg, out_store, uid = resolve_alithia_runtime(
        alithia_config=cfg_dict,
        store=store,
        user_id="alice",
    )
    assert isinstance(out_cfg, Config)
    assert out_store is store
    assert uid == "alice"

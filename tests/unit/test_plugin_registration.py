"""Tests for alithia plugin registration against soothe-nano APIs."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from alithia.plugin_registration import (
    _check_entry_points_registered,
    register_alithia_plugins,
)


def test_check_entry_points_registered_true_when_present() -> None:
    ep = MagicMock()
    ep.name = "paperscout"
    with patch("importlib.metadata.entry_points", return_value=[ep]):
        assert _check_entry_points_registered() is True


def test_check_entry_points_registered_false_when_empty() -> None:
    with patch("importlib.metadata.entry_points", return_value=[]):
        assert _check_entry_points_registered() is False


def test_register_skips_manual_when_entry_points_present() -> None:
    with patch(
        "alithia.plugin_registration._check_entry_points_registered",
        return_value=True,
    ):
        # Should return early without touching soothe_nano registry.
        register_alithia_plugins()


def test_register_manual_fallback_registers_manifests() -> None:
    registry = MagicMock()
    paperscout_cls = MagicMock()
    paperscout_cls._plugin_manifest = object()
    paperlens_cls = MagicMock()
    paperlens_cls._plugin_manifest = object()

    with (
        patch(
            "alithia.plugin_registration._check_entry_points_registered",
            return_value=False,
        ),
        patch("soothe_nano.plugin.global_registry._global_registry", None),
        patch(
            "soothe_nano.plugin.registry.PluginRegistry",
            return_value=registry,
        ),
        patch(
            "alithia.paperscout.PaperScoutPlugin",
            paperscout_cls,
        ),
        patch(
            "alithia.paperlens.PaperLensPlugin",
            paperlens_cls,
        ),
    ):
        register_alithia_plugins()

    assert registry.register.call_count == 2

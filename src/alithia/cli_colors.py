"""Minimal ANSI color helpers for CLI output."""

from __future__ import annotations

import os
import sys

_RESET = "\033[0m"
_BOLD = "\033[1m"
_DIM = "\033[2m"
_RED = "\033[31m"
_GREEN = "\033[32m"
_YELLOW = "\033[33m"
_BLUE = "\033[34m"
_CYAN = "\033[36m"


def supports_color() -> bool:
    """Return whether ANSI colors should be emitted on stdout."""
    if os.environ.get("NO_COLOR"):
        return False
    if os.environ.get("FORCE_COLOR"):
        return True
    return hasattr(sys.stdout, "isatty") and sys.stdout.isatty()


def _apply(text: str, codes: str, enabled: bool) -> str:
    if not enabled:
        return text
    return f"{codes}{text}{_RESET}"


def bold(text: str, *, enabled: bool | None = None) -> str:
    return _apply(text, _BOLD, enabled if enabled is not None else supports_color())


def dim(text: str, *, enabled: bool | None = None) -> str:
    return _apply(text, _DIM, enabled if enabled is not None else supports_color())


def red(text: str, *, enabled: bool | None = None) -> str:
    return _apply(text, _RED, enabled if enabled is not None else supports_color())


def green(text: str, *, enabled: bool | None = None) -> str:
    return _apply(text, _GREEN, enabled if enabled is not None else supports_color())


def yellow(text: str, *, enabled: bool | None = None) -> str:
    return _apply(text, _YELLOW, enabled if enabled is not None else supports_color())


def blue(text: str, *, enabled: bool | None = None) -> str:
    return _apply(text, _BLUE, enabled if enabled is not None else supports_color())


def cyan(text: str, *, enabled: bool | None = None) -> str:
    return _apply(text, _CYAN, enabled if enabled is not None else supports_color())


__all__ = [
    "bold",
    "blue",
    "cyan",
    "dim",
    "green",
    "red",
    "supports_color",
    "yellow",
]

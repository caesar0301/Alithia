"""Minimal stream helpers for alithia-agent CLI over soothe-nano."""

from __future__ import annotations

import sys
from typing import Any, TextIO

from langchain_core.messages import AIMessage, AIMessageChunk


def _message_text(msg: Any) -> str:
    """Extract plain text from a LangChain message / chunk."""
    content = getattr(msg, "content", None)
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for block in content:
            if isinstance(block, str):
                parts.append(block)
            elif isinstance(block, dict) and block.get("type") == "text":
                parts.append(str(block.get("text", "")))
        return "".join(parts)
    return ""


def format_stream_chunk(chunk: Any) -> str | None:
    """Return printable text from a nano astream chunk, or None to skip."""
    if not isinstance(chunk, tuple) or len(chunk) != 3:
        return None
    _namespace, mode, data = chunk
    if mode != "messages":
        return None
    # messages mode: (message, metadata) or bare message
    msg = data[0] if isinstance(data, tuple) and data else data
    if isinstance(msg, (AIMessage, AIMessageChunk)):
        text = _message_text(msg)
        return text or None
    return None


def consume_stream_stdout(
    chunk: Any,
    *,
    verbose: bool = False,
    out: TextIO | None = None,
    err: TextIO | None = None,
) -> None:
    """Write stream chunk to stdout/stderr for the CLI."""
    stdout = out or sys.stdout
    stderr = err or sys.stderr

    if isinstance(chunk, tuple) and len(chunk) == 3:
        _namespace, mode, data = chunk
        if mode == "custom" and isinstance(data, dict) and verbose:
            et = data.get("type", "event")
            summary = data.get("summary") or data.get("status") or ""
            stderr.write(f"\n[{et}] {summary}\n")
            stderr.flush()
            return

    text = format_stream_chunk(chunk)
    if text:
        stdout.write(text)
        stdout.flush()


__all__ = ["consume_stream_stdout", "format_stream_chunk"]

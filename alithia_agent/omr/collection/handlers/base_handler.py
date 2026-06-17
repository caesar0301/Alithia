"""Base handler for collection sources.

Abstract base class with retry logic and artifact generation.

RFC Reference: RFC-010 Section 10.1
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import re
from abc import ABC, abstractmethod
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import Any, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")


class Artifact:
    """Collection artifact with metadata."""

    def __init__(
        self,
        path: str,
        source_type: str,
        metadata: dict[str, Any],
        content: str | None = None,
    ) -> None:
        self.path = path
        self.source_type = source_type
        self.metadata = metadata
        self.content = content

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "source_type": self.source_type,
            "metadata": self.metadata,
        }


class BaseHandler(ABC):
    """Abstract base class for collection handlers.

    RFC Reference: RFC-010 Section 10.1
    """

    max_retries: int = 2
    retry_delay: float = 2.0

    def __init__(self) -> None:
        self.logger = logging.getLogger(f"{self.__class__.__module__}.{self.__class__.__name__}")

    @abstractmethod
    async def collect(self, source: str, workspace: Path) -> Artifact:
        """Collect material from source and store in workspace.

        Args:
            source: Input URL/DOI/ID
            workspace: Project workspace path

        Returns:
            Artifact with metadata and file path
        """
        pass

    async def with_retry(self, fn: Callable[[], T]) -> T:
        """Execute function with retry logic.

        Args:
            fn: Async function to execute.

        Returns:
            Function result.

        Raises:
            Exception: If all retries exhausted.
        """
        last_error: Exception | None = None

        for attempt in range(self.max_retries + 1):
            try:
                return await fn()
            except Exception as e:
                last_error = e
                self.logger.warning(f"Attempt {attempt + 1} failed: {e}")
                if attempt < self.max_retries:
                    await asyncio.sleep(self.retry_delay)

        raise last_error if last_error else RuntimeError("All retries failed")

    def slugify(self, text: str) -> str:
        """Convert text to lowercase-hyphenated slug.

        Args:
            text: Input text.

        Returns:
            Slugified text.
        """
        cleaned = re.sub(r"[^\w\s-]", "", text.lower())
        cleaned = re.sub(r"[\s_]+", "-", cleaned)
        return re.sub(r"-+", "-", cleaned).strip("-")

    def hash_source(self, source: str) -> str:
        """Generate short hash from source string.

        Args:
            source: Input source URL/ID.

        Returns:
            Short hex hash (8 chars).
        """
        return hashlib.md5(source.encode()).hexdigest()[:8]

    def format_artifact(
        self,
        content: str,
        metadata: dict[str, Any],
    ) -> str:
        """Format artifact as markdown with YAML frontmatter.

        Args:
            content: Markdown content.
            metadata: Artifact metadata.

        Returns:
            Complete artifact markdown string.
        """
        frontmatter = "---\n"
        for key, value in metadata.items():
            if isinstance(value, list):
                frontmatter += f"{key}: [{', '.join(str(v) for v in value)}]\n"
            elif isinstance(value, datetime):
                frontmatter += f"{key}: {value.isoformat()}\n"
            else:
                frontmatter += f"{key}: {value}\n"
        frontmatter += "---\n\n"

        return frontmatter + content

    def write_artifact(
        self,
        workspace: Path,
        category: str,
        filename: str,
        content: str,
        metadata: dict[str, Any],
    ) -> Path:
        """Write artifact to workspace.

        Args:
            workspace: Workspace root path.
            category: Category directory (paper/web/github/dataset).
            filename: Artifact filename.
            content: Markdown content.
            metadata: Artifact metadata.

        Returns:
            Path to written artifact.
        """
        artifact_dir = workspace / "raw" / category
        artifact_dir.mkdir(parents=True, exist_ok=True)

        artifact_path = artifact_dir / f"{filename}.md"
        formatted = self.format_artifact(content, metadata)
        artifact_path.write_text(formatted)

        self.logger.info(f"Wrote artifact: {artifact_path}")
        return artifact_path

    def create_error_artifact(
        self,
        workspace: Path,
        source: str,
        error_message: str,
        category: str,
        retry_attempts: int,
    ) -> Artifact:
        """Create error artifact for failed collection.

        Args:
            workspace: Workspace root path.
            source: Original source that failed.
            error_message: Error description.
            category: Source category.
            retry_attempts: Number of retries attempted.

        Returns:
            Error artifact.
        """
        error_dir = workspace / "raw" / "failed"
        error_dir.mkdir(parents=True, exist_ok=True)

        filename = f"url-{self.hash_source(source)}-error"
        metadata = {
            "id": filename,
            "source": source,
            "source_type": category,
            "status": "failed",
            "error": error_message,
            "retry_attempts": retry_attempts,
            "collected_at": datetime.now().isoformat(),
            "collected_by": "omr-collection",
        }

        content = f"""# Collection Failure

**URL**: {source}
**Source Type**: {category}
**Status**: failed
**Error**: {error_message}
**Retry Attempts**: {retry_attempts}
**Collected At**: {metadata["collected_at"]}
"""

        artifact_path = self.write_artifact(workspace, "failed", filename, content, metadata)

        return Artifact(str(artifact_path), "failed", metadata)


__all__ = ["Artifact", "BaseHandler"]

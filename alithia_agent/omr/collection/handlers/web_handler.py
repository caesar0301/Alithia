"""Web handler for generic HTTP/HTTPS sources.

Fetches webpage content and converts to markdown.

RFC Reference: RFC-010 Section 10.2
"""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path

import httpx

from alithia_agent.omr.collection.handlers.base_handler import Artifact, BaseHandler

logger = logging.getLogger(__name__)

try:
    import html2text

    HAS_HTML2TEXT = True
except ImportError:
    HAS_HTML2TEXT = False
    html2text = None  # type: ignore


class WebHandler(BaseHandler):
    """Handler for generic web URLs.

    RFC Reference: RFC-010 Section 10.2
    """

    def __init__(self) -> None:
        super().__init__()
        self.h2t = html2text.HTML2Text() if HAS_HTML2TEXT else None
        if self.h2t:
            self.h2t.ignore_links = False
            self.h2t.ignore_images = False
            self.h2t.body_width = 0  # No line wrapping

    async def collect(self, source: str, workspace: Path) -> Artifact:
        """Collect webpage content.

        Args:
            source: Web URL.
            workspace: Project workspace path.

        Returns:
            Web artifact with content.
        """
        return await self.with_retry(lambda: self._collect_web(source, workspace))

    async def _collect_web(self, source: str, workspace: Path) -> Artifact:
        """Fetch webpage and convert to markdown.

        Args:
            source: Web URL.
            workspace: Project workspace path.

        Returns:
            Web artifact.
        """
        self.logger.info(f"Collecting webpage: {source}")

        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
            response = await client.get(source)

            if response.status_code != 200:
                raise ValueError(f"HTTP error: {response.status_code}")

            html_content = response.text

        # Convert to markdown
        if HAS_HTML2TEXT and self.h2t:
            markdown_content = self.h2t.handle(html_content)
        else:
            # Fallback: just use raw HTML
            markdown_content = f"```html\n{html_content[:5000]}\n```"

        # Extract title from HTML
        title = self._extract_title(html_content) or source

        # Build metadata
        url_hash = self.hash_source(source)
        metadata = {
            "id": f"url-{url_hash}",
            "source_url": source,
            "title": title,
            "content_type": response.headers.get("content-type", ""),
            "content_length": len(html_content),
            "markdown_length": len(markdown_content),
            "collected_at": datetime.now().isoformat(),
            "collected_by": "omr-collection/web-handler",
            "source_type": "web",
        }

        # Generate content
        content = f"""# {title}

**Source URL**: {source}
**Collected At**: {metadata["collected_at"]}

## Content

{markdown_content}

## Links

- [Original Page]({source})
"""

        # Write artifact
        filename = f"url-{url_hash}"
        artifact_path = self.write_artifact(workspace, "web", filename, content, metadata)

        return Artifact(str(artifact_path), "web", metadata, content)

    def _extract_title(self, html: str) -> str | None:
        """Extract title from HTML content.

        Args:
            html: HTML content.

        Returns:
            Extracted title or None.
        """
        import re

        # Try <title> tag
        title_match = re.search(r"<title[^>]*>(.*?)</title>", html, re.IGNORECASE | re.DOTALL)
        if title_match:
            title = title_match.group(1).strip()
            # Remove HTML entities
            title = re.sub(r"&[a-zA-Z]+;", "", title)
            return title[:100]  # Limit length

        # Try <h1> tag
        h1_match = re.search(r"<h1[^>]*>(.*?)</h1>", html, re.IGNORECASE | re.DOTALL)
        if h1_match:
            title = h1_match.group(1).strip()
            title = re.sub(r"<[^>]+>", "", title)  # Remove inner tags
            return title[:100]

        return None


__all__ = ["WebHandler"]

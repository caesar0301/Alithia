"""GitHub handler for repository sources.

Fetches README and metadata via GitHub API.

RFC Reference: RFC-011 Section 10.2
"""

from __future__ import annotations

import logging
import re
from datetime import datetime
from pathlib import Path

import httpx

from alithia.omr.collection.handlers.base_handler import Artifact, BaseHandler

logger = logging.getLogger(__name__)


def extract_github_repo(source: str) -> str | None:
    """Extract GitHub repo name (owner/repo) from source.

    Args:
        source: GitHub URL.

    Returns:
        Repo name (owner/repo) if found, None otherwise.
    """
    patterns = [
        r"github\.com/([^/]+/[^/?#]+)",  # https://github.com/owner/repo
    ]

    for pattern in patterns:
        match = re.search(pattern, source)
        if match:
            repo = match.group(1).rstrip("/")
            return repo

    return None


class GitHubHandler(BaseHandler):
    """Handler for GitHub repository URLs.

    RFC Reference: RFC-011 Section 10.2
    """

    GITHUB_API_BASE = "https://api.github.com"

    async def collect(self, source: str, workspace: Path) -> Artifact:
        """Collect GitHub repo metadata and README.

        Args:
            source: GitHub URL.
            workspace: Project workspace path.

        Returns:
            GitHub artifact with metadata.
        """
        repo_name = extract_github_repo(source)
        if not repo_name:
            raise ValueError(f"Cannot extract GitHub repo from: {source}")

        return await self._collect_repo(repo_name, workspace)

    async def _collect_repo(self, repo_name: str, workspace: Path) -> Artifact:
        """Collect repo via GitHub API.

        Args:
            repo_name: Repo name (owner/repo).
            workspace: Project workspace path.

        Returns:
            GitHub artifact.
        """
        self.logger.info(f"Collecting GitHub repo: {repo_name}")

        async with httpx.AsyncClient(timeout=30.0) as client:
            # Fetch repo metadata
            repo_url = f"{self.GITHUB_API_BASE}/repos/{repo_name}"
            repo_response = await client.get(repo_url)

            if repo_response.status_code != 200:
                raise ValueError(f"GitHub API error: {repo_response.status_code}")

            repo_data = repo_response.json()

            # Fetch README
            readme_url = f"{self.GITHUB_API_BASE}/repos/{repo_name}/readme"
            readme_response = await client.get(readme_url)

            readme_content = ""
            if readme_response.status_code == 200:
                readme_data = readme_response.json()
                readme_content = readme_data.get("content", "")

                # Decode base64 content
                import base64

                try:
                    readme_content = base64.b64decode(readme_content).decode("utf-8")
                except Exception:
                    readme_content = "README could not be decoded"

        # Build metadata
        metadata = {
            "id": f"github-{repo_name.replace('/', '-')}",
            "repo_name": repo_name,
            "full_name": repo_data.get("full_name"),
            "description": repo_data.get("description"),
            "stars": repo_data.get("stargazers_count"),
            "language": repo_data.get("language"),
            "license": (
                repo_data.get("license", {}).get("spdx_id") if repo_data.get("license") else None
            ),
            "topics": repo_data.get("topics", []),
            "homepage": repo_data.get("homepage"),
            "default_branch": repo_data.get("default_branch"),
            "created_at": repo_data.get("created_at"),
            "updated_at": repo_data.get("updated_at"),
            "pushed_at": repo_data.get("pushed_at"),
            "source_url": f"https://github.com/{repo_name}",
            "collected_at": datetime.now().isoformat(),
            "collected_by": "omr-collection/github-handler",
            "source_type": "github",
        }

        # Build homepage link (Python 3.11 compatible)
        homepage = repo_data.get("homepage")
        homepage_link = f"- [Homepage]({homepage})" if homepage else ""

        # Generate content
        content = f"""# {repo_data.get("full_name", repo_name)}

**Stars**: {repo_data.get("stargazers_count", 0)}
**Language**: {repo_data.get("language", "Unknown")}
**License**: {metadata.get("license", "Unknown")}

## Description

{repo_data.get("description", "No description available.")}

## README

{readme_content[:2000]}{"..." if len(readme_content) > 2000 else ""}

## Links

- [GitHub Repository](https://github.com/{repo_name})
{homepage_link}
"""

        # Write artifact
        filename = f"github-{repo_name.replace('/', '-')}"
        artifact_path = self.write_artifact(workspace, "github", filename, content, metadata)

        return Artifact(str(artifact_path), "github", metadata, content)


__all__ = ["GitHubHandler", "extract_github_repo"]

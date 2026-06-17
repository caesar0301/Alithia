"""HuggingFace handler for dataset and model sources.

Fetches README and card metadata.

RFC Reference: RFC-010 Section 10.2
"""

from __future__ import annotations

import logging
import re
from datetime import datetime
from pathlib import Path

import httpx

from alithia_agent.omr.collection.handlers.base_handler import Artifact, BaseHandler

logger = logging.getLogger(__name__)


def extract_hf_name(source: str) -> tuple[str | None, str | None]:
    """Extract HuggingFace name and type from source.

    Args:
        source: HuggingFace URL.

    Returns:
        Tuple of (name, type) where type is 'dataset' or 'model'.
    """
    patterns = [
        (r"huggingface\.co/datasets/([^/?#]+)", "dataset"),
        (r"huggingface\.co/([^/?#]+)", "model"),  # Models are default HF path
        (r"hf\.co/datasets/([^/?#]+)", "dataset"),
        (r"hf\.co/([^/?#]+)", "model"),
    ]

    for pattern, hf_type in patterns:
        match = re.search(pattern, source)
        if match:
            name = match.group(1).rstrip("/")
            return name, hf_type

    return None, None


class HuggingFaceHandler(BaseHandler):
    """Handler for HuggingFace dataset/model URLs.

    RFC Reference: RFC-010 Section 10.2
    """

    HF_API_BASE = "https://huggingface.co/api"

    async def collect(self, source: str, workspace: Path) -> Artifact:
        """Collect HuggingFace dataset/model metadata.

        Args:
            source: HuggingFace URL.
            workspace: Project workspace path.

        Returns:
            HuggingFace artifact with metadata.
        """
        hf_name, hf_type = extract_hf_name(source)
        if not hf_name:
            raise ValueError(f"Cannot extract HuggingFace name from: {source}")

        return await self._collect_hf(hf_name, hf_type or "model", workspace)

    async def _collect_hf(self, hf_name: str, hf_type: str, workspace: Path) -> Artifact:
        """Collect via HuggingFace API.

        Args:
            hf_name: HF name (org/name or name).
            hf_type: 'dataset' or 'model'.
            workspace: Project workspace path.

        Returns:
            HuggingFace artifact.
        """
        self.logger.info(f"Collecting HuggingFace {hf_type}: {hf_name}")

        async with httpx.AsyncClient(timeout=30.0) as client:
            # Fetch card info
            if hf_type == "dataset":
                card_url = f"{self.HF_API_BASE}/datasets/{hf_name}"
            else:
                card_url = f"{self.HF_API_BASE}/models/{hf_name}"

            card_response = await client.get(card_url)

            card_data = {}
            if card_response.status_code == 200:
                card_data = card_response.json()

            # Try to fetch README content
            readme_url = f"https://huggingface.co/{hf_name}/raw/main/README.md"
            readme_response = await client.get(readme_url)

            readme_content = ""
            if readme_response.status_code == 200:
                readme_content = readme_response.text

        # Build metadata
        metadata = {
            "id": f"hf-{hf_type}-{hf_name.replace('/', '-')}",
            "hf_name": hf_name,
            "hf_type": hf_type,
            "author": hf_name.split("/")[0] if "/" in hf_name else None,
            "downloads": card_data.get("downloads"),
            "likes": card_data.get("likes"),
            "tags": card_data.get("tags", []),
            "library_name": card_data.get("library_name"),
            "pipeline_tag": card_data.get("pipeline_tag"),
            "source_url": f"https://huggingface.co/{hf_name}",
            "collected_at": datetime.now().isoformat(),
            "collected_by": "omr-collection/huggingface-handler",
            "source_type": "dataset",
        }

        # Generate content
        content = f"""# {hf_name}

**Type**: {hf_type}
**Downloads**: {metadata.get("downloads", "Unknown")}
**Likes**: {metadata.get("likes", 0)}

## README

{readme_content[:2000]}{"..." if len(readme_content) > 2000 else ""}

## Links

- [HuggingFace Page](https://huggingface.co/{hf_name})
"""

        # Write artifact (datasets go in dataset dir)
        category = "dataset" if hf_type == "dataset" else "dataset"
        filename = f"hf-{hf_name.replace('/', '-')}"
        artifact_path = self.write_artifact(workspace, category, filename, content, metadata)

        return Artifact(str(artifact_path), category, metadata, content)


__all__ = ["HuggingFaceHandler", "extract_hf_name"]

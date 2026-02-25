"""
Normalized Zotero paper model.

Bridges raw Zotero API responses, storage schema, and reranker expectations
with a single canonical type.
"""

import json
from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class ZoteroPaper(BaseModel):
    """Normalized representation of a Zotero library paper."""

    zotero_item_key: str
    title: str
    authors: List[str]
    abstract: str
    url: Optional[str] = None
    tags: List[str] = Field(default_factory=list)
    date_added: Optional[datetime] = None
    collection_paths: List[str] = Field(default_factory=list)

    @classmethod
    def from_zotero_api(cls, raw_item: Dict[str, Any], paths: Optional[List[str]] = None) -> Optional["ZoteroPaper"]:
        """
        Convert raw Zotero API item to ZoteroPaper.

        Returns None if the item has no abstract.
        """
        data = raw_item.get("data", raw_item)
        abstract = data.get("abstractNote", "").strip()
        if not abstract:
            return None

        item_key = data.get("key", raw_item.get("key", ""))
        title = data.get("title", "").strip()
        url = data.get("url", "")

        authors = []
        for creator in data.get("creators", []):
            name = creator.get("name", "")
            if not name:
                first = creator.get("firstName", "")
                last = creator.get("lastName", "")
                name = f"{first} {last}".strip()
            if name:
                authors.append(name)

        tags = [t.get("tag", "") for t in data.get("tags", []) if t.get("tag")]

        date_added = None
        date_str = data.get("dateAdded", "")
        if date_str:
            try:
                date_added = datetime.strptime(date_str, "%Y-%m-%dT%H:%M:%SZ")
            except (ValueError, TypeError):
                pass

        return cls(
            zotero_item_key=item_key,
            title=title,
            authors=authors,
            abstract=abstract,
            url=url,
            tags=tags,
            date_added=date_added,
            collection_paths=paths or [],
        )

    def to_storage_dict(self) -> Dict[str, Any]:
        """Serialize to flat dict matching storage schema columns."""
        return {
            "zotero_item_key": self.zotero_item_key,
            "title": self.title,
            "authors": self.authors,
            "abstract": self.abstract,
            "url": self.url or "",
            "tags": self.tags,
            "date_added": self.date_added.isoformat() if self.date_added else None,
            "collection_paths": self.collection_paths,
        }

    @classmethod
    def from_storage_dict(cls, row: Dict[str, Any]) -> "ZoteroPaper":
        """Deserialize from storage row."""
        authors = row.get("authors", [])
        if isinstance(authors, str):
            authors = json.loads(authors)

        tags = row.get("tags", [])
        if isinstance(tags, str):
            tags = json.loads(tags)

        collection_paths = row.get("collection_paths", [])
        if isinstance(collection_paths, str):
            collection_paths = json.loads(collection_paths)

        date_added = row.get("date_added")
        if isinstance(date_added, str) and date_added:
            try:
                date_added = datetime.fromisoformat(date_added)
            except (ValueError, TypeError):
                date_added = None

        return cls(
            zotero_item_key=row.get("zotero_item_key", ""),
            title=row.get("title", ""),
            authors=authors,
            abstract=row.get("abstract", ""),
            url=row.get("url", ""),
            tags=tags,
            date_added=date_added,
            collection_paths=collection_paths,
        )

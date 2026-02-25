"""
Google Scholar data fetcher.

Strategy: SerpAPI (if key provided) -> scholarly library (fallback).
"""

from typing import Any, Dict, List, Optional, Tuple

from cogents_core.utils import get_logger

logger = get_logger(__name__)


def get_scholar_data(
    scholar_id: str, serpapi_key: Optional[str] = None
) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
    """
    Fetch Scholar profile and publications.

    Returns:
        (profile_dict, list_of_publication_dicts)
    """
    if serpapi_key:
        return _fetch_via_serpapi(scholar_id, serpapi_key)
    return _fetch_via_scholarly(scholar_id)


def _fetch_via_serpapi(
    scholar_id: str, api_key: str
) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
    """Fetch using SerpAPI (reliable, paid)."""
    try:
        from serpapi import GoogleSearch
    except ImportError:
        raise ImportError(
            "google-search-results is not installed. "
            "Install with: pip install google-search-results"
        )

    params = {
        "engine": "google_scholar_author",
        "author_id": scholar_id,
        "api_key": api_key,
    }

    search = GoogleSearch(params)
    results = search.get_dict()

    author = results.get("author", {})
    profile = {
        "name": author.get("name", ""),
        "affiliation": author.get("affiliations", ""),
        "interests": [i.get("title", "") for i in author.get("interests", [])],
        "h_index": None,
        "i10_index": None,
        "total_citations": 0,
    }

    cited_by = results.get("cited_by", {})
    table = cited_by.get("table", [])
    for entry in table:
        if "citations" in entry:
            h_val = entry.get("h_index")
            i10_val = entry.get("i10_index")
            if h_val is not None:
                profile["h_index"] = h_val
            if i10_val is not None:
                profile["i10_index"] = i10_val
    if table:
        all_citations = table[0].get("citations", {})
        profile["total_citations"] = all_citations.get("all", 0)

    publications = []
    for article in results.get("articles", []):
        publications.append({
            "title": article.get("title", ""),
            "authors": article.get("authors", "").split(", ") if article.get("authors") else [],
            "year": _parse_year(article.get("year")),
            "citation_count": article.get("cited_by", {}).get("value", 0),
            "venue": article.get("publication", ""),
            "url": article.get("link"),
            "scholar_id": article.get("citation_id"),
        })

    return profile, publications


def _fetch_via_scholarly(
    scholar_id: str,
) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
    """Fetch using scholarly library (free, may hit rate limits)."""
    try:
        from scholarly import scholarly
    except ImportError:
        raise ImportError(
            "scholarly is not installed. Install with: pip install scholarly"
        )

    author = scholarly.search_author_id(scholar_id)
    author = scholarly.fill(author, sections=["basics", "indices", "publications"])

    profile = {
        "name": author.get("name", ""),
        "affiliation": author.get("affiliation", ""),
        "interests": author.get("interests", []),
        "h_index": author.get("hindex"),
        "i10_index": author.get("i10index"),
        "total_citations": author.get("citedby", 0),
    }

    publications = []
    for pub in author.get("publications", []):
        bib = pub.get("bib", {})
        publications.append({
            "title": bib.get("title", ""),
            "authors": bib.get("author", "").split(" and ") if bib.get("author") else [],
            "year": _parse_year(bib.get("pub_year")),
            "citation_count": pub.get("num_citations", 0),
            "venue": bib.get("venue", bib.get("journal", "")),
            "url": pub.get("pub_url"),
            "scholar_id": pub.get("author_pub_id"),
        })

    return profile, publications


def _parse_year(value) -> Optional[int]:
    if value is None:
        return None
    try:
        return int(value)
    except (ValueError, TypeError):
        return None

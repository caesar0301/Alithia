"""Evidence node implementation for OmniResearch workflow.

Extracts evidence from collected materials with minimal parsing boundary.
Generates evidence-map.md and research-brief.md.

RFC Reference: RFC-010 Section 5.2, Section 7.1
"""

from __future__ import annotations

import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from alithia_agent.omr.skill_tree import SkillTree

logger = logging.getLogger(__name__)


def read_artifact(artifact_info: dict) -> str:
    """Read artifact content from path.

    Args:
        artifact_info: Dict with 'path' key.

    Returns:
        Artifact markdown content.
    """
    path = Path(artifact_info.get("path", ""))
    if path.exists():
        return path.read_text()
    return ""


def extract_claims(content: str) -> list[dict[str, Any]]:
    """Extract claims from paper content (minimal parsing).

    This follows the minimal parsing boundary: extracts claims,
    citations, and assigns confidence levels without semantic analysis.

    Args:
        content: Paper markdown content.

    Returns:
        List of extracted claims with confidence.
    """
    claims = []

    # Simple claim patterns (no semantic analysis)
    claim_patterns = [
        r"We (show|prove|demonstrate|find|observe|report) that ([^.]+\.)",
        r"Our (results|findings|experiments) (show|indicate|suggest|demonstrate) ([^.]+\.)",
        r"This (paper|work|study) (proposes|presents|introduces) ([^.]+\.)",
    ]

    for pattern in claim_patterns:
        matches = re.finditer(pattern, content, re.IGNORECASE)
        for match in matches:
            claim_text = match.group(0)
            # Assign confidence based on claim verb
            if any(v in claim_text.lower() for v in ["prove", "demonstrate", "show"]):
                confidence = "proven"
            elif any(v in claim_text.lower() for v in ["suggest", "indicate", "observe"]):
                confidence = "suggested"
            else:
                confidence = "inferred"

            claims.append(
                {
                    "text": claim_text,
                    "confidence": confidence,
                    "source_location": match.start(),
                }
            )

    return claims[:20]  # Limit to top 20 claims


def extract_citations(content: str) -> list[str]:
    """Extract citations from content.

    Args:
        content: Paper markdown content.

    Returns:
        List of citation strings.
    """
    # Simple citation patterns
    patterns = [
        r"\[([^\]]+)\]",  # Bracket citations [Author, Year]
        r"\((\d{4})\)",  # Year citations (2024)
        r"et al\.?",  # et al references
    ]

    citations = []
    for pattern in patterns:
        matches = re.findall(pattern, content)
        citations.extend(matches[:5])  # Limit per pattern

    return citations[:15]


EVIDENCE_MAP_TEMPLATE = """# Evidence Map: {research_topic}

**Generated**: {timestamp}
**Sources**: {total_sources} materials

---

## Evidence Summary

| Category | Count | Claims Extracted |
|----------|-------|------------------|
{category_table}

---

## Evidence by Source

{evidence_by_source}

---

## Confidence Levels

| Level | Meaning |
|-------|---------|
| **PROVEN** | Strong evidence, directly demonstrated |
| **SUGGESTED** | Moderate evidence, indicated by results |
| **INFERRED** | Weak evidence, derived interpretation |

---

## Gaps

_Note: Gap analysis requires manual review._
"""


def generate_evidence_map(
    research_topic: str,
    materials: dict[str, list[dict]],
    claims_by_source: dict[str, list[dict]],
) -> str:
    """Generate evidence-map.md content.

    Args:
        research_topic: Research topic string.
        materials: Collected materials by category.
        claims_by_source: Extracted claims by source.

    Returns:
        Evidence map markdown content.
    """
    timestamp = datetime.now().isoformat()
    total_sources = sum(len(v) for v in materials.values())

    # Build category table
    category_table = ""
    for category, items in materials.items():
        claims_count = sum(len(claims_by_source.get(a.get("path", ""), [])) for a in items)
        category_table += f"| {category} | {len(items)} | {claims_count} |\n"

    # Build evidence by source
    evidence_by_source = ""
    for category, items in materials.items():
        if not items:
            continue

        evidence_by_source += f"\n### {category.upper()}\n\n"

        for item in items[:10]:  # Limit display
            path = item.get("path", "")
            metadata = item.get("metadata", {})
            title = metadata.get("title", path.split("/")[-1])

            claims = claims_by_source.get(path, [])
            evidence_by_source += f"\n#### {title}\n\n"

            if claims:
                for claim in claims[:5]:
                    evidence_by_source += f"- [{claim['confidence'].upper()}] {claim['text']}\n"
            else:
                evidence_by_source += "_No claims extracted._\n"

    return EVIDENCE_MAP_TEMPLATE.format(
        research_topic=research_topic,
        timestamp=timestamp,
        total_sources=total_sources,
        category_table=category_table,
        evidence_by_source=evidence_by_source,
    )


RESEARCH_BRIEF_TEMPLATE = """# Research Brief: {research_topic}

**Generated**: {timestamp}
**Sources**: {total_sources} materials
**Claims Extracted**: {total_claims}

---

## Research Question

**Primary Question**: What is the current state of knowledge regarding {research_topic}?

_Note: Research question should be refined based on evidence review._

---

## Scope

### Included

- Academic papers from ArXiv ({paper_count} sources)
- Web resources ({web_count} sources)
- GitHub repositories ({github_count} sources)
- HuggingFace datasets/models ({dataset_count} sources)

### Excluded

- _Define exclusion criteria based on research goals._

---

## Evidence Landscape

### Strong Evidence (PROVEN)

_Evidence with direct demonstration._

_Review claims marked PROVEN in evidence-map.md._

### Moderate Evidence (SUGGESTED)

_Evidence indicated by results._

_Review claims marked SUGGESTED in evidence-map.md._

### Weak Evidence (INFERRED)

_Interpretation-based evidence._

_Review claims marked INFERRED in evidence-map.md._

---

## Key Findings

_Extract key findings after reviewing evidence-map.md._

---

## Open Questions

- What aspects of {research_topic} are underexplored?
- What methodological limitations exist in current research?
- What are the most promising directions for future work?

---

## Next Steps

1. Refine research question based on evidence landscape
2. Identify gaps requiring additional collection
3. Proceed to Gate A: Research Planning

---

## Gate A Criteria

| Criterion | Status |
|-----------|--------|
| evidence-map.md exists | PASS |
| >=5 sources collected | {gate_status} |
"""


def generate_research_brief(
    research_topic: str,
    materials: dict[str, list[dict]],
    claims_by_source: dict[str, list[dict]],
) -> str:
    """Generate research-brief.md content.

    Args:
        research_topic: Research topic string.
        materials: Collected materials.
        claims_by_source: Extracted claims.

    Returns:
        Research brief markdown content.
    """
    timestamp = datetime.now().isoformat()
    total_sources = sum(len(v) for v in materials.values())
    total_claims = sum(len(v) for v in claims_by_source.values())

    return RESEARCH_BRIEF_TEMPLATE.format(
        research_topic=research_topic,
        timestamp=timestamp,
        total_sources=total_sources,
        total_claims=total_claims,
        paper_count=len(materials.get("paper", [])),
        web_count=len(materials.get("web", [])),
        github_count=len(materials.get("github", [])),
        dataset_count=len(materials.get("dataset", [])),
        gate_status="PASS" if total_sources >= 5 else "FAIL",
    )


async def evidence_node(state: dict) -> dict:
    """Evidence node implementation.

    Extracts evidence with minimal parsing and generates brief.

    Args:
        state: Current agent state.

    Returns:
        Updated agent state with evidence_map, research_brief.
    """
    workspace_path = Path(state["workspace_path"])
    research_topic = state["research_topic"]
    raw_materials = state["raw_materials"]

    # Read all artifacts and extract claims
    claims_by_source: dict[str, list[dict[str, Any]]] = {}

    for category, items in raw_materials.items():
        for item in items:
            content = read_artifact(item)
            if content:
                claims = extract_claims(content)
                if claims:
                    claims_by_source[item.get("path", "")] = claims

    # Generate evidence map
    evidence_map_content = generate_evidence_map(research_topic, raw_materials, claims_by_source)
    evidence_map_path = workspace_path / "docs" / "evidence-map.md"
    evidence_map_path.write_text(evidence_map_content)

    # Generate research brief
    brief_content = generate_research_brief(research_topic, raw_materials, claims_by_source)
    brief_path = workspace_path / "docs" / "research-brief.md"
    brief_path.write_text(brief_content)

    # Update skill tree
    skill_tree_path = workspace_path / "skill-tree.json"
    skill_tree = SkillTree(skill_tree_path)
    skill_tree.mark_completed("omr-evidence")

    # Build evidence map dict for state
    total_sources = sum(len(v) for v in raw_materials.values())
    total_claims = sum(len(v) for v in claims_by_source.values())

    proven_count = sum(
        1 for c in claims_by_source.values() for claim in c if claim["confidence"] == "proven"
    )
    suggested_count = sum(
        1 for c in claims_by_source.values() for claim in c if claim["confidence"] == "suggested"
    )
    inferred_count = sum(
        1 for c in claims_by_source.values() for claim in c if claim["confidence"] == "inferred"
    )

    evidence_map = {
        "total_sources": total_sources,
        "total_claims": total_claims,
        "claims_by_confidence": {
            "proven": proven_count,
            "suggested": suggested_count,
            "inferred": inferred_count,
        },
    }

    # Update state
    state["evidence_map"] = evidence_map
    state["research_brief"] = {
        "research_question": research_topic,
        "scope": {"included": list(raw_materials.keys()), "excluded": []},
        "evidence_references": list(claims_by_source.keys())[:10],
    }
    state["skill_tree"] = skill_tree.state
    state["current_skill"] = "omr-evidence"
    state["completed_skills"].append("omr-evidence")
    state["metrics"]["evidence_time"] = datetime.now().isoformat()

    # Summary info
    summary_msg = f"Evidence extracted: {total_claims} claims from {total_sources} sources"
    state["info"].append(summary_msg)

    logger.info(f"Evidence extraction complete: {total_claims} claims")

    return state


__all__ = [
    "evidence_node",
    "extract_claims",
    "extract_citations",
    "generate_evidence_map",
    "generate_research_brief",
]

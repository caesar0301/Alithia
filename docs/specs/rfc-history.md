# alithia-agent RFC Change History

This document tracks all RFC lifecycle events in chronological order (newest first).

---

## Event Types

| Event | Description |
|-------|-------------|
| **Created** | New RFC document created |
| **Updated** | Draft or Review RFC modified |
| **Frozen** | RFC status changed to Frozen |
| **Version Released** | New version of frozen RFC created |
| **Deprecated** | RFC deprecated |
| **Reference Updated** | Supporting doc (index, namings, etc.) updated |

---

## Change History

| Date | Event | RFC | Description |
|------|-------|-----|-------------|
| 2026-06-29 | Updated | RFC-010, RFC-006 | Removed deprecated code/config: dropped the `research_interests` list + `expertise_level` from `ResearcherProfileConfig` and loader defaults; removed the `SmtpConfig`/`ZoteroConfig`/`PaperScoutConfig` legacy aliases. Existing configs still load via `extra="allow"`. |
| 2026-06-29 | Updated | RFC-010, RFC-003 | Cut: removed the legacy `zotero_papers` corpus slot + `PaperReranker(corpus=)` param. Zotero items now flow only through the markdown sync → `ResearchInterest(source="zotero")` units → the single interests-only matching logic. Eliminates the cache-double-count risk. |
| 2026-06-29 | Created | RFC-010-research-interests-knowledge | Research interests as Markdown knowledge base; Zotero optional; unified-corpus matching |
| 2026-06-29 | Updated | RFC-003-paperscout-workflow | AgentState gains research_interests; data flow adds Zotero→Markdown sync; §11.2 zotero invariant honored; §13.1 pyzotero optional |
| 2026-06-29 | Updated | RFC-006-configuration | Zotero optional; deprecated research_interests list → Markdown; §8.2 validator drops hard zotero gate |
| 2026-06-29 | Updated | RFC-008-data-models | Added ResearchInterest model (§5.4, cross-refs RFC-010) |
| 2026-06-29 | Reference Updated | rfc-index, rfc-history | Added RFC-010 row; updated counts and dependency graph |
| 2026-06-18 | Reference Updated | RFC-007, RFC-009 | Added DeepXiv plugin documentation (migrated from soothe.toolkits) |
| 2026-06-18 | Created | Migration Doc | DeepXiv migration documentation: moved from soothe.toolkits to alithia_agent.plugins.deepxiv |
| 2026-06-06 | Created | RFC-008-data-models | Shared data model contracts (paper types, metadata, notifications) |
| 2026-06-06 | Created | RFC-007-plugin-integration | Soothe framework integration contracts (@plugin, @subagent, AsyncPersistStore) |
| 2026-06-06 | Created | RFC-006-configuration | Configuration management architecture (JSON + env substitution) |
| 2026-06-06 | Created | RFC-005-cli-interface | CLI interface contracts (entry point, flags, output formats) |
| 2026-06-06 | Created | RFC-004-storage-layer | SQLite storage architecture (schema, migrations, key-value patterns) |
| 2026-06-06 | Created | RFC-003-paperscout-workflow | PaperScout subagent architecture (recovered from existing code) |
| 2026-06-06 | Created | RFC-002-world-view | System vision and conceptual model RFC |
| 2026-06-06 | Created | RFC-001-paperlens-workflow | PaperLens subagent architecture RFC created from brainstorming |
| 2026-06-06 | Created | Infrastructure | Platonic Coding initialized for alithia-agent |

---

## Version Update Records

_No versioned RFC updates yet._

---

## RFC Summary Statistics

| Metric | Value |
|--------|-------|
| Total RFCs created | 10 |
| Conceptual Design | 1 |
| Architecture Design | 6 |
| Implementation Interface Design | 3 |
| Total lines | ~4,200 |

---

## Related Documents

- [rfc-standard.md](rfc-standard.md) - RFC process and conventions
- [rfc-index.md](rfc-index.md) - RFC index
- [rfc-namings.md](rfc-namings.md) - Terminology reference
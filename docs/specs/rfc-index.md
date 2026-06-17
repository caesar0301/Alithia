# alithia-agent RFC Index

Master index of all RFC specifications.

---

## Active RFCs

| RFC | Title | Kind | Status | Created | Last Updated |
|-----|-------|------|--------|---------|--------------|
| [RFC-001-paperlens-workflow](RFC-001-paperlens-workflow.md) | PaperLens Subagent Architecture | Architecture Design | Draft | 2026-06-06 | 2026-06-06 |
| [RFC-002-world-view](RFC-002-world-view.md) | Alithia Agent System Vision | Conceptual Design | Draft | 2026-06-06 | 2026-06-06 |
| [RFC-003-paperscout-workflow](RFC-003-paperscout-workflow.md) | PaperScout Subagent Architecture | Architecture Design | Draft | 2026-06-06 | 2026-06-06 |
| [RFC-004-storage-layer](RFC-004-storage-layer.md) | SQLite Storage Architecture | Architecture Design | Draft | 2026-06-06 | 2026-06-06 |
| [RFC-005-cli-interface](RFC-005-cli-interface.md) | Command Line Interface | Implementation Interface Design | Draft | 2026-06-06 | 2026-06-06 |
| [RFC-006-configuration](RFC-006-configuration.md) | Configuration Management | Architecture Design | Draft | 2026-06-06 | 2026-06-06 |
| [RFC-007-plugin-integration](RFC-007-plugin-integration.md) | Soothe Framework Integration | Implementation Interface Design | Draft | 2026-06-06 | 2026-06-06 |
| [RFC-008-data-models](RFC-008-data-models.md) | Shared Data Model Contracts | Implementation Interface Design | Draft | 2026-06-06 | 2026-06-06 |
| [RFC-009-soothe-integration](RFC-009-soothe-integration.md) | Soothe Framework Integration Architecture | Architecture Design | Draft | 2026-06-07 | 2026-06-07 |
| [RFC-010-omni-research-subagent](RFC-010-omni-research-subagent.md) | OmniResearch Soothe Subagent Architecture | Architecture Design | Draft | 2026-06-17 | 2026-06-17 |

---

## RFC Dependency Graph

```
RFC-002-world-view (Conceptual — foundation, no dependencies)
    │
    ├── RFC-001-paperlens-workflow ──────────────┐
    │                                            │
    ├── RFC-003-paperscout-workflow ─────────────┤
    │                                            │
    ├── RFC-004-storage-layer ───────────────────┤
    │                                            │
    ├── RFC-005-cli-interface ───────────────────┤  (all depend on RFC-002)
    │                                            │
    ├── RFC-006-configuration ───────────────────┤
    │                                            │
    ├── RFC-007-plugin-integration ──────────────┤
    │                                            │
    ├── RFC-008-data-models ─────────────────────┤
    │                                            │
    ├── RFC-009-soothe-integration ──────────────┤
    │                                            │
    └── RFC-010-omni-research-subagent ──────────┘
        (depends on RFC-002, RFC-007, RFC-009)
```

---

## Supporting Documents

| Document | Purpose |
|----------|---------|
| [rfc-standard.md](rfc-standard.md) | RFC process and conventions |
| [rfc-namings.md](rfc-namings.md) | Terminology reference |
| [rfc-history.md](rfc-history.md) | Change history |
| [rfc-index.md](rfc-index.md) | This document |

---

## Status Legend

| Status | Meaning |
|--------|---------|
| **Draft** | Work in progress, subject to change |
| **Review** | Complete, ready for review |
| **Frozen** | Immutable production reference |
| **Deprecated** | No longer active |

---

## Quick Links

### By Kind

- **Conceptual Design**: [RFC-002-world-view](RFC-002-world-view.md)
- **Architecture Design**: [RFC-001-paperlens-workflow](RFC-001-paperlens-workflow.md), [RFC-003-paperscout-workflow](RFC-003-paperscout-workflow.md), [RFC-004-storage-layer](RFC-004-storage-layer.md), [RFC-006-configuration](RFC-006-configuration.md), [RFC-009-soothe-integration](RFC-009-soothe-integration.md), [RFC-010-omni-research-subagent](RFC-010-omni-research-subagent.md)
- **Implementation Interface Design**: [RFC-005-cli-interface](RFC-005-cli-interface.md), [RFC-007-plugin-integration](RFC-007-plugin-integration.md), [RFC-008-data-models](RFC-008-data-models.md)

### By Status

- **Draft**: All RFCs (001-010)
- **Review**: _None yet_
- **Frozen**: _None yet_

### By Stage

- **Core**: RFC-002, RFC-001, RFC-004, RFC-005, RFC-006, RFC-007, RFC-008, RFC-009, RFC-010
- **DataCollection**: RFC-003
- **Relevance**: RFC-003
- **Notification**: RFC-003

---

## RFC Summary

| Kind | Count | Purpose |
|------|-------|---------|
| Conceptual Design | 1 | System vision, principles, taxonomy, invariants |
| Architecture Design | 6 | Workflow architecture, storage, configuration, soothe integration, omr subagent |
| Implementation Interface Design | 3 | CLI, plugin integration, data models |

**Total: 10 RFCs**

---

## Related Documents

- [rfc-standard.md](rfc-standard.md) - RFC process and conventions
- [rfc-history.md](rfc-history.md) - Change history
- [rfc-namings.md](rfc-namings.md) - Terminology reference
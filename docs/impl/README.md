# Alithia Implementation Guides

This directory contains implementation guides that translate RFC specifications into concrete, project-specific designs.

## Purpose

Implementation guides bridge the gap between abstract specs (RFCs) and actual code. They provide:

- Concrete module/package structure
- Type definitions with full field specifications
- Interface/trait/class definitions
- Implementation details and algorithms
- Error handling strategies
- Testing approaches

## Relationship to Specs

```
RFC Specification (abstract, what)
        |
        v
Implementation Guide (concrete, how)   <-- This directory
        |
        v
Actual Code (executable)
```

Implementation guides **supersede** RFC specs with concrete details but **MUST NOT contradict** them.

## Creating a New Guide

Use the **platonic-impl-guide** skill to create implementation guides:

```
Use platonic-impl-guide to create a guide for RFC-NNNN targeting the <module-name> module.
```

## Guide Template

Use the **platonic-impl-guide** skill which includes its own template for generating implementation guides.

## Available Guides

| Guide | Source RFC | Description |
|-------|-----------|-------------|
| [paperscout-impl.md](paperscout-impl.md) | RFC-0002 | PaperScout agent: workflow, storage, Gap Scanner, exactly-once email |
| [sync-persistence-impl.md](sync-persistence-impl.md) | RFC-0001, RFC-0002 | Syncing service: Zotero, Google Scholar connectors, persistence layer |
| [dashboard-impl.md](dashboard-impl.md) | RFC-0004 | Dashboard: FastAPI backend, task monitoring, Paper Trend calendar, AI Agent |

## Naming Convention

Name guides descriptively, referencing the feature or RFC:

- `paperscout-impl.md` - PaperScout agent implementation
- `sync-persistence-impl.md` - Syncing service and connected services persistence
- `dashboard-impl.md` - Dashboard web interface implementation
- `paperlens-impl.md` - PaperLens agent implementation (planned)
- `storage-impl.md` - Storage layer implementation (planned)
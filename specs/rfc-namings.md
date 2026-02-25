# Alithia Terminology Reference

Authoritative terminology reference for Alithia RFC specifications.

---

## Rules

1. All RFCs **MUST** use the terms defined here when referring to project concepts
2. New terms introduced in an RFC **MUST** be registered in this document
3. Deprecated terms **MUST** be removed when the defining RFC is deprecated
4. This document reflects the **current** state of terminology (not historical)

---

## Terms

### Core Concepts

| Term | Source RFC | Brief Description |
|------|-----------|-------------------|
| **Research Profile** | RFC-0001 | User's research interests, expertise, and connected services configuration |
| **Connected Service** | RFC-0001 | External service integration (LLM, Zotero, Email, etc.) |
| **Gem** | RFC-0001 | General research digest or idea captured by the system |
| **Research Assistant** | RFC-0001 | AI agent that helps researchers discover, explore, and analyze academic content |

### Agent Types

| Term | Source RFC | Brief Description |
|------|-----------|-------------------|
| **PaperScout** | RFC-0001, RFC-0002 | Agent responsible for paper discovery from ArXiv and user notification |
| **PaperLens** | RFC-0001, RFC-0003 | Agent that helps read papers and perform deep research about related topics |
| **Dashboard** | RFC-0001, RFC-0004 | Web-based interface providing task monitoring, profile management, paper trend visualization, and AI-integrated research |

### PaperScout Domain

| Term | Source RFC | Brief Description |
|------|-----------|-------------------|
| **Paper Query** | RFC-0002 | User-defined search criteria for paper discovery |
| **Daily Query** | RFC-0002 | Paper query scheduled for daily execution |
| **Paper Relevance Assessment** | RFC-0002 | LLM-based evaluation of paper relevance to user profile |
| **Gap Scanner** | RFC-0002 | Service that detects and fills missing daily paper recommendations |
| **Recommendation Slot** | RFC-0001, RFC-0002 | A single day's worth of paper recommendations for a query |

### PaperLens Domain

| Term | Source RFC | Brief Description |
|------|-----------|-------------------|
| **Paper OCR** | RFC-0003 | PDF parsing and content extraction component |
| **Deep Research** | RFC-0003 | Extended investigation into paper-related topics |
| **Query History** | RFC-0003 | Record of user interactions and research queries |

### Dashboard Domain

| Term | Source RFC | Brief Description |
|------|-----------|-------------------|
| **Background Task** | RFC-0001, RFC-0004 | A trackable unit of work dispatched from the Dashboard to an agent or service |
| **Paper Trend** | RFC-0001, RFC-0004 | Calendar-based visualization of daily paper discovery results from PaperScout |
| **AI Agent Button** | RFC-0001, RFC-0004 | Persistent UI element that provides contextual AI assistance on any Dashboard page |
| **Agent Dispatcher** | RFC-0001, RFC-0004 | Service that routes Dashboard user actions to the correct agent invocation |
| **Task Manager** | RFC-0004 | Backend service that wraps agent operations into trackable Background Tasks |
| **Real-Time Manager** | RFC-0004 | Service that delivers live updates from backend to frontend via WebSocket or SSE |

### Storage

| Term | Source RFC | Brief Description |
|------|-----------|-------------------|
| **Storage Backend** | RFC-0001, RFC-0002 | Persistent state storage (Supabase or SQLite fallback) |
| **User Profile Sync** | RFC-0002 | Asynchronous synchronization of user data from external services |
| **Paper Record** | RFC-0001 | Persisted metadata and assessment for a discovered paper |

---

## Usage Guidelines

- **Capitalization**: Use the capitalization shown in the Term column when referring to defined terms
- **First use**: On first use in an RFC, link to this document or the defining RFC
- **Synonyms**: Avoid synonyms; use the canonical term from this table

---

## Related Documents

- [rfc-standard.md](rfc-standard.md) - RFC process and conventions
- [rfc-index.md](rfc-index.md) - RFC index
- [rfc-history.md](rfc-history.md) - Change history

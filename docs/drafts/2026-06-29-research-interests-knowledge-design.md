# Design Draft: Research Interests as Markdown Knowledge

**Date**: 2026-06-29
**Author**: Claude (platonic-coding)
**Status**: Design draft — for RFC-010

---

## 1. Problem

Today, `research_interests` in `~/.alithia/config.yml` is a **dead field**: declared in
`config/schema.py:106` and `loader.py:101` but never read by any node, reranker, prompt, or
filter. The actual relevance signal in PaperScout is **100% the Zotero library corpus**
(embedding cosine similarity + time-decay; keyword-overlap fallback). Two consequences:

1. Research interests carry zero weight in matching.
2. Zotero is a **hard gate**: `profile_analysis_node` (`nodes.py:99`) fails the run when
   `config.zotero` is unset — even though the schema marks it `Optional`, RFC-003 §11.2
   *already* declares the invariant *"Zotero unavailable → MUST continue with ArXiv-only"*, and
   `validate_paperscout_config.py` only warns. Three layers disagree.

## 2. Goal

Make research interests the **primary, human-editable knowledge source** for paper matching,
expressed as a directory of Markdown files with YAML frontmatter. Make Zotero an **optional
contributor** that, when configured, is synced into the same Markdown format at startup and
unified with hand-written interests into one corpus the reranker scores against.

## 3. Confirmed design decisions (from user)

| # | Decision | Choice |
|---|----------|--------|
| A | Zotero sync granularity | **One `.md` per Zotero item**, written under `research_interests/zotero/<key>.md`. Uniform with hand-written files → uniform embedding granularity. |
| B | ArXiv fetch scope | **Unchanged** — still driven by `paperscout_agent.query`. Interests drive **ranking only**, not what is fetched. |
| C | Deliverables | **Full spec-driven lifecycle**: design draft → RFC-010 → IG-010 → code + tests → migrate `~/.alithia` config → update RFC-003/006/008 + index/history. |

## 4. The Markdown knowledge format

Location: `~/.alithia/research_interests/` (a new subdirectory of `ALITHIA_HOME`).

Every file is one **knowledge unit** = one corpus embedding. Two origins:

- **Hand-written**: authored by the user, e.g. `multimodal-learning.md`.
- **Zotero-generated**: written by the sync step, e.g. `zotero/ABC123.md`.

### 4.1 File schema (YAML frontmatter + body)

```markdown
---
title: "Multimodal Representation Learning"
source: manual            # manual | zotero
weight: 1.0               # multiplier on this unit's similarity (default 1.0)
arxiv_categories: [cs.CV, cs.CL]   # optional; NOT used for fetch (decision B), informational
tags: [vision-language, contrastive]
notes: "Prioritize cross-modal alignment and evaluation benchmarks."
date_added: 2026-06-29    # for recency/time-decay ordering; manual files may omit
---

<free-form markdown body — the "knowledge text" that gets embedded.>

## Why I care
Cross-modal alignment is the bottleneck for generalist agents...

## Subtopics
- Contrastive pretraining (CLIP, SigLIP)
- Evaluation benchmarks (VQA, MMMU)
```

### 4.2 Frontmatter contract

| Field | Type | Required | Default | Notes |
|-------|------|----------|---------|-------|
| `title` | `str` | yes | — | Unit label; also displayed. |
| `source` | `Literal["manual","zotero"]` | no | `manual` | Provenance; drives sync pruning. |
| `weight` | `float` | no | `1.0` | ≥0. Multiplier on this unit's contribution. |
| `arxiv_categories` | `list[str]` | no | `[]` | Informational only — does **not** drive fetch (decision B). |
| `tags` | `list[str]` | no | `[]` | Extra keywords; appended to embedded text. |
| `notes` | `str` | no | `""` | Short priority/context note; prepended to body text. |
| `date_added` | `date` | no | `None` | Recency ordering; manual files may omit (treated as oldest). |
| `zotero_item_key` | `str` | only if `source=zotero` | — | Provenance key; used by re-sync to prune stale files. |

The **embedded text** for a unit = `notes` + body markdown (stripped of frontmatter) + `" ".join(tags)`.

## 5. Architecture

### 5.1 New module: `alithia_agent/research_interests/`

```
alithia_agent/research_interests/
├── __init__.py        # public API: load_research_interests, ResearchInterest, sync_zotero
├── model.py           # ResearchInterest pydantic model (frontmatter contract §4.2)
├── loader.py          # scan dir → parse frontmatter → list[ResearchInterest]
└── zotero_sync.py     # fetch Zotero library → write zotero/<key>.md → prune stale
```

### 5.2 `ResearchInterest` model (`model.py`)

Pydantic v2, `extra="allow"` (house style for data models, RFC-008 §11.1). Carries the parsed
frontmatter **plus** the computed `searchable_text` (notes + body + tags) the reranker embeds.
Method contract mirrors `ZoteroPaper.get_searchable_text()`.

### 5.3 `loader.py` — `load_research_interests(dir: Path) -> list[ResearchInterest]`

- `rglob("*.md")` over `research_interests/`.
- Parse YAML frontmatter (reuse `yaml.safe_load` on the `---`-delimited block; body = rest).
- Skip files missing `title`; log a warning.
- Returns units in stable order (sorted by path).
- **Pure function, no network, no side effects** → trivially unit-testable.

### 5.4 `zotero_sync.py` — `sync_zotero_to_markdown(config, dir) -> SyncResult`

- Called once at startup **before** the PaperScout run (see §5.6 wiring).
- If `profile.zotero` unset → no-op (returns empty result). This is the "zotero optional" path.
- Else: fetch library via `pyzotero` (move the top-level `from pyzotero import zotero` import
  from `nodes.py:14` **into** this function — true optional dependency), respecting the existing
  24h `paperscout:zotero:{user_id}` SQLite cache.
- For each item: write `research_interests/zotero/<item_key>.md` with `source: zotero`,
  `zotero_item_key`, `title`, `tags`, `date_added`, and body = abstract.
- **Prune**: delete `zotero/*.md` whose `zotero_item_key` is no longer in the fetched set
  (handles items removed from the library). Never touch hand-written files.

### 5.5 Reranker unification (`paperscout/reranker.py`)

Add a second corpus input. `PaperReranker.__init__` gains:

```python
def __init__(self, papers, corpus, *, interests: list[ResearchInterest] | None = None, ...):
```

Matching logic:
- **Unified corpus** = `[interest_unit for i in interests] + [zotero_paper for p in corpus]`.
  Each unit contributes one embedding row, exactly as Zotero abstracts do today.
- Each unit carries its `weight` (zotero units default 1.0; manual units honor frontmatter).
- Time-decay still applies, keyed by `date_added` where present; manual units without a date
  sort to the recency bottom (lowest decay weight).
- Empty unified corpus → existing `score=5.0` fallback (now a *genuine* degenerate state, not
  the default — because interests are always loaded if any `.md` exists).
- `relevance_factors` gains `interests_count` and `interest_weight` for observability.

This keeps the proven embedding algorithm intact — interests are simply additional, often
higher-signal, corpus rows.

### 5.6 PaperScout wiring (`paperscout/nodes.py` + `state.py`)

**`state.py`** — `PaperScoutRuntimeConfig` gains:

```python
research_interests_dir: str | None = None   # resolved path under ALITHIA_HOME
```

`build_runtime_config` sets it from `ALITHIA_HOME / "research_interests"`.

**`nodes.py`** changes:
1. `profile_analysis_node`: drop the hard Zotero gate (`nodes.py:99-100`). New rule:
   - If **no** `research_interests_dir`/files **and** no `zotero` → emit a single error
     *"No knowledge source: add research_interests markdown or configure zotero"* (fail fast —
     matches RFC-006 §4.6 "fail fast").
   - Otherwise pass; Zotero absent is fine if interests exist, and vice versa.
2. `data_collection_node`: after ArXiv fetch, call `sync_zotero_to_markdown(...)` (no-op if
   unconfigured), then `load_research_interests(dir)`; store both `zotero_papers` (legacy,
   may be empty) and a new `research_interests` list in state.
3. `relevance_assessment_node`: pass `interests=state["research_interests"]` to the reranker.

**`AgentState`** gains `research_interests: list[ResearchInterest]` (TypedDict field, default `[]`).

### 5.7 Optional-dependency hygiene

- `pyzotero` import moves out of `nodes.py` module scope into `zotero_sync.py`'s function body
  and the existing `data_collection_node` zotero branch. Uninstalling `pyzotero` no longer
  breaks importing `paperscout.nodes`.
- `paperscout/__init__.py:60` plugin `dependencies`: move `pyzotero>=1.5.0` to a comment noting
  it's optional for the zotero-sync path (keep `pyzotero` in `pyproject.toml` core deps for now —
  no packaging breakage; just stop hard-requiring it at runtime).

## 6. Backward compatibility & migration

### 6.1 Config migration (`~/.alithia/config.yml`)

- **Zotero**: keep the existing `researcher_profile.zotero` block — now genuinely optional.
- **`research_interests` list**: deprecated as a config field. Migrate its 3 values
  (`AI`, `Machine Learning`, `Computer Vision`) into seed Markdown files under
  `~/.alithia/research_interests/`. Keep accepting the old list (loader ignores it; the field
  stays in the schema with a deprecation note so existing configs don't fail validation).

### 6.2 Seed files created during migration

```
~/.alithia/research_interests/
├── 01-ai.md
├── 02-machine-learning.md
└── 03-computer-vision.md
```
Each seeded with a frontmatter `title` + a short body explaining the interest (so it actually
embeds as meaningful text, unlike the bare 2-word config strings).

### 6.3 What does NOT change

- ArXiv fetch categories, date logic, email/SMTP, notification exactly-once, affiliation
  extraction, storage schema, CLI, daemon.
- `ZoteroPaper` model and the `zotero_papers` state slot (kept for the corpus branch + cache).
- `pyproject.toml` deps (no new packages; `pyyaml` already a dep for frontmatter parsing).

## 7. Testing strategy (unit, no network)

- `test_research_interests_loader`: parse a tmp dir of sample `.md` files (valid, missing
  title, malformed YAML, zotero subfolder) → assert parsed units + text.
- `test_research_interests_model`: frontmatter defaults, weight clamp, `searchable_text`.
- `test_zotero_sync`: mock `pyzotero` → assert files written, stale pruned, no-op when
  unconfigured, never touches hand-written files.
- `test_reranker_unified`: interests-only corpus ranks by interest similarity; mixed
  zotero+interests; weights applied; empty-everything → 5.0 fallback.
- `test_profile_analysis_optional_zotero`: no zotero + has interests → passes; neither → fails
  with the new error; existing zotero path still passes.
- Existing paperscout tests stay green (zotero fixtures still valid; interests default `[]`).

## 8. Spec lifecycle (decision C)

1. **This draft** → `docs/drafts/2026-06-29-research-interests-knowledge-design.md`.
2. **RFC-010** `docs/specs/RFC-010-research-interests-knowledge.md` (Architecture Design,
   Stage: Relevance) — the Markdown format, sync contract, unified-corpus matching rule,
   optional-zotero invariant.
3. **IG-010** `docs/impl/IG-010-research-interests.md` — file-by-file implementation guide +
   test plan.
4. **Code + tests** per IG-010.
5. **Migrate** `~/.alithia/config.yml` + seed `~/.alithia/research_interests/*.md`.
6. **Update existing RFCs** (all Draft → editable in place):
   - RFC-003 §11.2: align the documented Zotero invariant with the now-honored behavior;
     §7.1 state gains `research_interests`; §13.1 mark `pyzotero` optional.
   - RFC-006 §6.3/§8.2: Zotero optional; new `research_interests_dir` note; deprecate the list.
   - RFC-008 §5: add `ResearchInterest` model to shared contracts (or cross-ref RFC-010).
   - `rfc-index.md` + `rfc-history.md`: add RFC-010 row/event.

## 9. Open questions (resolved by user choices)

- Fetch scope from interests? → **No** (decision B), keep config query.
- Zotero file granularity? → **One per item** (decision A).
- Spec depth? → **Full lifecycle** (decision C).

No remaining open questions.

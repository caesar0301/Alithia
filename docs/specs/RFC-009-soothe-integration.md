# RFC-009-soothe-integration: Soothe-Nano Host Architecture

**Status**: Draft
**Authors**: Claude, Xiaming Chen
**Created**: 2026-06-07
**Last Updated**: 2026-07-29
**Depends on**: RFC-002-world-view, RFC-007-plugin-integration
**Supersedes**: ---
**Stage**: Core
**Kind**: Architecture Design

---

## 1. Abstract

Alithia-agent is a branded CLI host over **soothe-nano** (`create_nano_agent`), not full soothe StrangeLoop / `SootheRunner`, and not soothed. Paperscout and paperlens register as nano plugins via `@plugin/@subagent` and `soothe.plugins` entry points. Interactive queries run in-process; the alithia PaperScout scheduler daemon routes scheduled digests directly to the paperscout workflow.

---

## 2. Scope and Non-Goals

### 2.1 Scope

This RFC defines:

* Directory layout with nano runtime under `~/.alithia/soothe/`
* AlithiaAgent / `build_agent` wrapper that sets `SOOTHE_HOME` and enables plugins
* Plugin registration via entry points + soothe-nano plugin registry
* Dual configuration: alithia domain config + `nano.yml`
* CLI query path and alithia daemon scheduler path
* Storage integration for domain persistence

### 2.2 Non-Goals

This RFC does **not** define:

* soothed / soothe-daemon / soothe-client integration (soothed is **invisible** to alithia)
* StrangeLoop / goal-engine orchestration from full soothe
* Changes to paperscout/paperlens LangGraph workflow logic beyond factory wiring
* Multi-user or deployment scenarios — single-user CLI remains the scope

---

## 3. Background & Motivation

### 3.1 Prior gap

Earlier designs wrapped full soothe `SootheRunner`. That pulled a heavy stack and coupled alithia to host features it does not need. FlowJet showed a lighter pattern: depend on `soothe-nano` and host `create_nano_agent` in-process.

### 3.2 Desired architecture

Alithia-agent should:

- Use soothe-nano in-process for interactive queries
- Register paperscout/paperlens as discoverable `soothe.plugins`
- Keep branded CLI `alithia-agent` and domain config under `~/.alithia/`
- Keep the PaperScout scheduler as an **alithia** daemon (not soothed)
- Prefer nano’s built-in deepxiv toolkit for academic tools

---

## 4. Architecture Overview

### 4.1 System context

```
User query ──► alithia-agent CLI ──► create_nano_agent
                                      │
                                      ├─ paperscout plugin (soothe.plugins)
                                      ├─ paperlens plugin
                                      └─ nano deepxiv tools

alithia-agent daemon ──► PaperScoutScheduler ──► paperscout/runner.py
```

### 4.2 Invocation paths (alithia-only)

1. **Query / explicit request** — `alithia-agent QUERY…` builds nano in-process. The user query is the request; nano may `task` paperscout/paperlens via normal plugin behavior.
2. **Daemon routing** — `alithia-agent daemon {start,stop,…}` runs the alithia PaperScout scheduler, which calls `paperscout/runner.py` directly.

Optional `--subagent NAME` is a local prompt bias only — not soothed `preferred_subagent` / middleware enforcement.

### 4.3 Layout

```
~/.alithia/
  config.yml                 # domain (paperscout, paperlens, storage, daemon)
  data/alithia.db
  soothe/                    # SOOTHE_HOME
    config/nano.yml          # providers / router / optional overrides
    logs/
    memory/
    data/
```

---

## 5. Component contracts

### 5.1 Agent bootstrap

* `load_config` / `default_config_path` → `SootheConfig` from `$SOOTHE_HOME/config/nano.yml` (flowjet-style; env zero-config fallback)
* `apply_alithia_defaults` enables paperscout/paperlens, deepxiv tools, sqlite durability
* `build_agent` → `create_nano_agent(...)`
* CLI: `-c/--config` selects domain `~/.alithia/config.yml`; `--soothe-config` selects nano.yml
* `register_alithia_plugins` uses entry points, with manual fallback for editable installs

### 5.2 Plugin factories

Factories self-load `ALITHIA_HOME/config.yml` and construct `AlithiaStore` when kwargs omit `alithia_config` / `store`, so both the nano query path and daemon/runner path work without host-specific kwargs.

### 5.3 Events

Subagent events use `soothe_sdk.core.events.SubagentEvent` and register via `soothe_nano.events.catalog.register_event`.

---

## 6. Out of scope reminders

* No soothed WebSocket client, `loop_input`, or QueryEngine
* No dependency on the full `soothe` package
* PaperScout cron is owned by alithia’s daemon module

---

## 7. References

* RFC-007-plugin-integration
* flowjet-agent (`create_nano_agent` host pattern)
* soothe-nano package documentation

# Daemon Retry Refinement for ArXiv Availability Lag

**Status**: Draft  
**Date**: 2026-06-12  
**Scope**: Alithia daemon + PaperScout scheduling/retry behavior

## 1. Problem

Alithia runs a daily daemon that triggers PaperScout at day granularity. ArXiv availability can lag by multiple days, so a day may initially return no papers even though papers for that day become available later. Current gap retry behavior is window-based and does not clearly model "unretrieved" versus "terminally retrieved" days.

## 2. Goals

- Keep daily scheduling behavior intact.
- Define unretrieved day explicitly: day without successful terminal retrieval (`sent`).
- Retry unretrieved days until retrieved, with bounded policy:
  - max retry age: 30 days
  - max retries dispatched per scheduler run: 3 days
- Treat `empty` (0 papers) and `failed` (execution error) as retriable.
- Keep compatibility with current daemon architecture and storage.

## 3. Non-Goals

- Changing PaperScout ranking, digest formatting, or prompt behavior.
- Adding cross-user distributed scheduling.
- Introducing external queue infrastructure.

## 4. Functional Rules

### 4.1 Day State Model

Each `(user_id, query_categories, notification_date)` day uses one of:

- `pending`: run dispatched, completion not finalized yet.
- `empty`: run succeeded, 0 papers found, retriable.
- `failed`: run errored, retriable.
- `sent`: run succeeded with papers, terminal success.

### 4.2 Unretrieved Definition

A day is **unretrieved** when latest status is not `sent`.

### 4.3 Retry Boundaries

- Eligible retry range: within last `max_retry_age_days` (30).
- Respect `big_bang`: do not retry days before big bang.
- Exclude today.
- Per scheduler cycle, dispatch at most `max_retries_per_run` (3) backlog days.
- Retry priority: oldest unretrieved days first.

### 4.4 Daily + Backlog Execution

Per daily scheduler cycle:

1. Dispatch yesterday with source `scheduler`.
2. Compute unretrieved backlog days in eligibility range.
3. Exclude day already handled in this cycle.
4. Dispatch up to 3 oldest with source `scheduler_retry`.

## 5. Architecture Changes

### 5.1 Scheduler (`PaperScoutScheduler`)

- Keep existing daily trigger timing unchanged.
- Replace "missing notification only" retry behavior with "not sent yet" backlog selection.
- Apply per-run cap and deterministic ordering (oldest first).

### 5.2 Gap Scanner (`GapScanner`)

- Shift responsibility from "missing notification slots" to "unretrieved date selection."
- Query storage for dates in range where latest status is `pending|empty|failed` or no record exists.
- Keep `big_bang` filtering in scanner-level logic.

### 5.3 Dispatcher / Daemon Service

- Preserve run-source tagging (`scheduler`, `scheduler_retry`).
- Status transition updates:
  - run start: `pending`
  - run success with papers: `sent`
  - run success with 0 papers: `empty`
  - run error: `failed`

## 6. Data Flow

1. Scheduler wakes at configured UTC time.
2. Scheduler dispatches yesterday.
3. Daemon writes `pending`.
4. PaperScout runs and writes terminal status (`sent|empty|failed`).
5. Scheduler asks scanner for unretrieved days in 30-day range.
6. Scheduler dispatches up to 3 oldest backlog days.
7. Same status update cycle applies for each backlog day.

## 7. Configuration Design

Add under `daemon.scheduler`:

```yaml
daemon:
  scheduler:
    enabled: true
    hour: 23
    minute: 0
    timezone: UTC
    retry_window_days: 3  # legacy key, deprecated for unretrieved logic
    max_retry_age_days: 30
    max_retries_per_run: 3
```

### 7.1 Config Compatibility

- Keep `retry_window_days` temporarily for backward compatibility.
- New logic uses `max_retry_age_days` and `max_retries_per_run`.
- If new keys absent, default to:
  - `max_retry_age_days = 30`
  - `max_retries_per_run = 3`

## 8. Error Handling and Reliability

- **Idempotent retries**: rerunning same day is allowed until day reaches `sent`.
- **Crash safety**: if daemon crashes after `pending`, day stays retriable in later cycles.
- **Load protection**: hard cap of 3 retry dispatches per run prevents runaway backlog processing.
- **Observability**: logs should include day, source, status transition, and retry selection summary.

## 9. Test Strategy

### 9.1 Unit Tests

- Scanner returns unretrieved days only (not `sent`).
- Age cap and big-bang boundaries are respected.
- Scheduler enforces max 3 retries per run.
- Retry ordering is oldest-first.

### 9.2 Integration Tests

- Daily run + lag simulation: day transitions `empty -> sent` when papers later become available.
- Failed day transitions `failed -> sent` after successful retry.
- Multi-day backlog is drained progressively across cycles with cap applied.

### 9.3 Regression Tests

- Existing daily schedule timing and status reporting remain unchanged.
- Config without new keys still runs using default values.

## 10. Open Decisions

None for current scope. Policies are fixed by approved requirements:

- unretrieved = no terminal successful retrieval (`sent`)
- retry until retrieved with 30-day cap
- `empty` and `failed` both retriable
- retry cap 3 days per scheduler run

## 11. Implementation Notes (for next phase)

- Prefer additive schema changes in `DaemonSchedulerConfig`.
- Update scanner API to return unretrieved candidates (possibly with helper methods for filtering and sorting).
- Keep migration low-risk: introduce new behavior behind deterministic defaults and preserve CLI/daemon interfaces.

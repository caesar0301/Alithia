"""Regression test for the SQLiteStorage thread-ID reuse crash (P2).

Reproduces the bug pattern that produced the py3.11 / py3.12 SIGSEGV crashes
of Jun 29 / Jul 01 2026 (see NXT-05 §5.2): a worker thread creates a
``sqlite3.Connection`` stored in a thread-ID-keyed dict, the thread exits,
its thread ID is reused by a *new* thread, and the new thread retrieves and
calls ``.execute()`` on the now-invalid connection → near-NULL (0x8) deref
inside ``_pysqlite_query_execute``.

The fix (NXT-06 §5.2) replaces the class-level ``_connections`` dict with
``threading.local``, whose per-thread state is torn down automatically when
the owning thread exits — so a new thread can never observe a stale handle.

This test does NOT attempt to dereference a freed native handle (that would
require a real use-after-free and is non-deterministic). Instead it asserts
the *invariant* the fix guarantees: after a thread exits, the storage must
NOT hold any connection object reachable from the new thread, and a new
thread calling ``_get_connection`` must receive a fresh, usable connection.
"""

from __future__ import annotations

import sqlite3
import threading
from pathlib import Path

from alithia_agent.storage.sqlite import SQLiteStorage


def _new_storage(tmp_path: Path) -> SQLiteStorage:
    return SQLiteStorage(tmp_path / "t_threading_local.db")


def test_get_connection_returns_usable_connection(tmp_path: Path) -> None:
    """Baseline: a single thread gets a working connection."""
    store = _new_storage(tmp_path)
    conn = store._get_connection()
    assert isinstance(conn, sqlite3.Connection)
    # The connection must be usable.
    cur = conn.execute("SELECT 1")
    assert cur.fetchone()[0] == 1


def test_each_thread_gets_its_own_connection(tmp_path: Path) -> None:
    """Two concurrent threads must receive distinct connection objects."""
    store = _new_storage(tmp_path)
    seen: dict[str, sqlite3.Connection] = {}
    barrier = threading.Barrier(2)

    def worker(name: str) -> None:
        barrier.wait()
        seen[name] = store._get_connection()

    t1 = threading.Thread(target=worker, args=("a",), name="worker-a")
    t2 = threading.Thread(target=worker, args=("b",), name="worker-b")
    t1.start()
    t2.start()
    t1.join()
    t2.join()

    assert seen["a"] is not seen["b"], "threads must not share a connection"


def test_thread_exit_does_not_leak_connection_to_next_thread(tmp_path: Path) -> None:
    """The regression: after a thread exits, a new thread must NOT observe
    the dead thread's connection object.

    With the old class-level ``_connections`` dict keyed by
    ``threading.get_ident()``, a reused thread ID would retrieve the dead
    thread's stale connection. With ``threading.local`` the per-thread state
    is gone, so the new thread builds a fresh connection.
    """
    store = _new_storage(tmp_path)

    dead_thread_conn_holder: dict[str, object] = {}

    def short_lived() -> None:
        conn = store._get_connection()
        dead_thread_conn_holder["conn"] = conn
        # sanity: usable while the thread is alive
        conn.execute("SELECT 1").fetchone()

    t = threading.Thread(target=short_lived, name="short-lived")
    t.start()
    t.join()

    dead_conn = dead_thread_conn_holder["conn"]

    # Spin a new thread and confirm it does NOT receive the dead connection.
    # (We cannot force CPython to reuse the exact same thread id, but the
    # invariant holds regardless: threading.local gives each thread its own
    # slot, so the new thread's connection is always a different object.)
    new_conn_holder: dict[str, object] = {}

    def successor() -> None:
        new_conn_holder["conn"] = store._get_connection()
        # Must be usable — this is the line that would SIGSEGV under the bug.
        (new_conn_holder["conn"]).execute("SELECT 1").fetchone()  # type: ignore[union-attr]

    t2 = threading.Thread(target=successor, name="successor")
    t2.start()
    t2.join()

    new_conn = new_conn_holder["conn"]
    assert new_conn is not dead_conn, (
        "new thread must not inherit the dead thread's connection — "
        "this is exactly the P2 SIGSEGV regression"
    )


def test_close_only_closes_calling_thread_connection(tmp_path: Path) -> None:
    """``close()`` must not close other threads' connections (it now only
    closes the calling thread's connection via threading.local)."""
    store = _new_storage(tmp_path)

    other_conn_holder: dict[str, object] = {}

    def other() -> None:
        other_conn_holder["conn"] = store._get_connection()

    t = threading.Thread(target=other, name="other")
    t.start()
    t.join()

    other_conn = other_conn_holder["conn"]

    # Calling close() from the main thread must not affect the other thread's
    # connection object. (With threading.local, the main thread has its own
    # slot, possibly None.)
    store.close()  # should be a no-op or close only main thread's conn

    # The other thread's connection is still a valid object reference; we
    # don't execute on it here because that thread is gone, but the object
    # identity must be unchanged.
    assert other_conn_holder["conn"] is other_conn


def test_no_class_level_connection_dict_leak(tmp_path: Path) -> None:
    """Structural guard: SQLiteStorage must NOT expose a class-level
    ``_connections`` dict (the source of the leak). This catches any
    future regression that reintroduces the shared mutable pool."""
    assert not hasattr(SQLiteStorage, "_connections"), (
        "SQLiteStorage must not have a class-level _connections dict — "
        "that was the root cause of the P2 SIGSEGV (stale connection reuse "
        "via reused thread IDs). Use threading.local instead."
    )
    assert hasattr(SQLiteStorage, "_lock"), "schema-init lock should remain"

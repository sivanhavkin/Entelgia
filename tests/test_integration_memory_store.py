#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Unit tests for entelgia/integration_memory_store.py and
the memory integration hooks added to IntegrationCore.

Covers:
  1.  IntegrationMemoryStore initialises with empty entries when file absent
  2.  store_entry appends an entry and auto-assigns id + timestamp
  3.  store_entry evicts the oldest entry when max_entries is exceeded
  4.  retrieve_by_agent returns only matching-agent entries, newest first
  5.  retrieve_relevant filters by agent + tag intersection
  6.  retrieve_relevant falls back to retrieve_by_agent when tags is None
  7.  format_context returns empty string for empty list
  8.  format_context produces [MEMORY] prefixed lines
  9.  save/load round-trip preserves entries
  10. make_entry builds entry dict from ControlDecision + IntegrationState
  11. IntegrationCore.attach_memory_store wires the store
  12. IntegrationCore.get_memory_context returns empty string without store
  13. IntegrationCore.get_memory_context returns context after store is wired
  14. IntegrationCore.record_decision is a no-op without a store
  15. IntegrationCore.record_decision persists entry when store is attached
  16. load handles corrupt JSON gracefully (empty store, no exception)
  17. auto_save=False does not write on store_entry
"""

from __future__ import annotations

import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

from entelgia.integration_core import (
    ControlDecision,
    IntegrationCore,
    IntegrationMode,
    IntegrationState,
)
from entelgia.integration_memory_store import IntegrationMemoryStore


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _temp_store(auto_save: bool = True) -> tuple:
    """Return (store, tmp_path) using a fresh temporary file."""
    fd, path = tempfile.mkstemp(suffix=".json")
    os.close(fd)
    os.unlink(path)  # remove so IntegrationMemoryStore creates it fresh
    store = IntegrationMemoryStore(path=path, auto_save=auto_save)
    return store, path


def _sample_entry(agent: str = "Socrates", mode: str = "NORMAL", tags=None) -> dict:
    return {
        "agent": agent,
        "active_mode": mode,
        "decision_reason": f"Test entry for {agent}",
        "priority_level": 0,
        "regenerate": False,
        "suppress_personality": False,
        "enforce_fixy": False,
        "stagnation": 0.1,
        "loop_count": 0,
        "unresolved": 0,
        "fatigue": 0.0,
        "energy": 90.0,
        "tags": tags or [],
    }


# ---------------------------------------------------------------------------
# 1. Initialises empty when file absent
# ---------------------------------------------------------------------------


def test_init_no_file_creates_empty_store():
    store, path = _temp_store()
    try:
        assert store._entries == []
        assert os.path.exists(path)
    finally:
        os.unlink(path)


# ---------------------------------------------------------------------------
# 2. store_entry appends and auto-assigns id + timestamp
# ---------------------------------------------------------------------------


def test_store_entry_appends_and_assigns_id_timestamp():
    store, path = _temp_store()
    try:
        entry = _sample_entry()
        store.store_entry(entry)
        assert len(store._entries) == 1
        stored = store._entries[0]
        assert "id" in stored
        assert "timestamp" in stored
        assert stored["agent"] == "Socrates"
    finally:
        os.unlink(path)


# ---------------------------------------------------------------------------
# 3. store_entry evicts oldest when max_entries exceeded
# ---------------------------------------------------------------------------


def test_store_entry_evicts_oldest_at_max():
    store, path = _temp_store(auto_save=False)
    store._max_entries = 3
    try:
        for i in range(4):
            e = _sample_entry(agent="Socrates")
            e["decision_reason"] = f"entry {i}"
            store.store_entry(e)
        assert len(store._entries) == 3
        # Oldest (entry 0) should be gone
        reasons = [e["decision_reason"] for e in store._entries]
        assert "entry 0" not in reasons
        assert "entry 3" in reasons
    finally:
        os.unlink(path)


# ---------------------------------------------------------------------------
# 4. retrieve_by_agent returns matching-agent entries newest first
# ---------------------------------------------------------------------------


def test_retrieve_by_agent_filters_by_agent():
    store, path = _temp_store(auto_save=False)
    try:
        store.store_entry(_sample_entry(agent="Socrates", mode="NORMAL"))
        store.store_entry(_sample_entry(agent="Athena", mode="ATTACK_OVERRIDE"))
        store.store_entry(_sample_entry(agent="Socrates", mode="LOW_COMPLEXITY"))

        results = store.retrieve_by_agent("Socrates", limit=10)
        assert len(results) == 2
        assert all(e["agent"] == "Socrates" for e in results)
        # Newest first
        assert results[0]["active_mode"] == "LOW_COMPLEXITY"
    finally:
        os.unlink(path)


def test_retrieve_by_agent_respects_limit():
    store, path = _temp_store(auto_save=False)
    try:
        for _ in range(5):
            store.store_entry(_sample_entry(agent="Socrates"))
        results = store.retrieve_by_agent("Socrates", limit=2)
        assert len(results) == 2
    finally:
        os.unlink(path)


# ---------------------------------------------------------------------------
# 5. retrieve_relevant filters by agent + tag
# ---------------------------------------------------------------------------


def test_retrieve_relevant_filters_by_tag():
    store, path = _temp_store(auto_save=False)
    try:
        store.store_entry(_sample_entry(agent="Socrates", tags=["loop"]))
        store.store_entry(_sample_entry(agent="Socrates", tags=["stagnation"]))
        store.store_entry(_sample_entry(agent="Socrates", tags=[]))

        results = store.retrieve_relevant("Socrates", tags=["loop"])
        assert len(results) == 1
        assert results[0]["tags"] == ["loop"]
    finally:
        os.unlink(path)


# ---------------------------------------------------------------------------
# 6. retrieve_relevant falls back when tags is None
# ---------------------------------------------------------------------------


def test_retrieve_relevant_no_tags_falls_back():
    store, path = _temp_store(auto_save=False)
    try:
        store.store_entry(_sample_entry(agent="Socrates"))
        store.store_entry(_sample_entry(agent="Socrates"))
        results = store.retrieve_relevant("Socrates", tags=None, limit=5)
        assert len(results) == 2
    finally:
        os.unlink(path)


# ---------------------------------------------------------------------------
# 7. format_context returns empty string for empty list
# ---------------------------------------------------------------------------


def test_format_context_empty():
    store, path = _temp_store(auto_save=False)
    try:
        assert store.format_context([]) == ""
    finally:
        os.unlink(path)


# ---------------------------------------------------------------------------
# 8. format_context produces [MEMORY] prefixed lines
# ---------------------------------------------------------------------------


def test_format_context_produces_memory_lines():
    store, path = _temp_store(auto_save=False)
    try:
        entry = _sample_entry(agent="Socrates", mode="CONCRETE_OVERRIDE")
        entry["timestamp"] = "2025-01-01T12:00:00+00:00"
        context = store.format_context([entry])
        assert context.startswith("[MEMORY]")
        assert "Socrates" in context
        assert "CONCRETE_OVERRIDE" in context
    finally:
        os.unlink(path)


# ---------------------------------------------------------------------------
# 9. save / load round-trip
# ---------------------------------------------------------------------------


def test_save_load_roundtrip():
    store, path = _temp_store(auto_save=False)
    try:
        store.store_entry(_sample_entry(agent="Athena", mode="RESOLUTION_OVERRIDE"))
        store.save()

        store2 = IntegrationMemoryStore(path=path, auto_save=False)
        assert len(store2._entries) == 1
        assert store2._entries[0]["agent"] == "Athena"
        assert store2._entries[0]["active_mode"] == "RESOLUTION_OVERRIDE"
    finally:
        os.unlink(path)


# ---------------------------------------------------------------------------
# 10. make_entry builds entry from ControlDecision + IntegrationState
# ---------------------------------------------------------------------------


def test_make_entry_from_decision_and_state():
    decision = ControlDecision(
        active_mode=IntegrationMode.ATTACK_OVERRIDE,
        decision_reason="Stagnation detected.",
        priority_level=8,
        regenerate=False,
        suppress_personality=True,
        enforce_fixy=False,
    )
    state = IntegrationState(
        agent_name="Socrates",
        stagnation=0.4,
        loop_count=1,
        unresolved=2,
        fatigue=0.3,
        energy=70.0,
    )
    entry = IntegrationMemoryStore.make_entry(
        agent="Socrates", decision=decision, state=state, tags=["stagnation"]
    )
    assert entry["agent"] == "Socrates"
    assert entry["active_mode"] == IntegrationMode.ATTACK_OVERRIDE
    assert entry["priority_level"] == 8
    assert entry["stagnation"] == pytest.approx(0.4)
    assert entry["tags"] == ["stagnation"]


# ---------------------------------------------------------------------------
# 11. IntegrationCore.attach_memory_store wires store
# ---------------------------------------------------------------------------


def test_attach_memory_store():
    core = IntegrationCore()
    assert core._memory_store is None

    store, path = _temp_store(auto_save=False)
    try:
        core.attach_memory_store(store)
        assert core._memory_store is store
    finally:
        os.unlink(path)


# ---------------------------------------------------------------------------
# 12. get_memory_context returns empty string without store
# ---------------------------------------------------------------------------


def test_get_memory_context_no_store():
    core = IntegrationCore()
    assert core.get_memory_context("Socrates") == ""


# ---------------------------------------------------------------------------
# 13. get_memory_context returns context after store is wired
# ---------------------------------------------------------------------------


def test_get_memory_context_with_store():
    core = IntegrationCore()
    store, path = _temp_store(auto_save=False)
    try:
        e = _sample_entry(agent="Socrates", mode="LOW_COMPLEXITY")
        e["timestamp"] = "2025-06-01T09:00:00+00:00"
        store.store_entry(e)
        core.attach_memory_store(store)

        ctx = core.get_memory_context("Socrates")
        assert "[MEMORY]" in ctx
        assert "Socrates" in ctx
    finally:
        os.unlink(path)


# ---------------------------------------------------------------------------
# 14. record_decision is a no-op without a store
# ---------------------------------------------------------------------------


def test_record_decision_no_store():
    core = IntegrationCore()
    decision = ControlDecision()
    state = IntegrationState(agent_name="Socrates")
    # Should not raise
    core.record_decision("Socrates", decision, state)


# ---------------------------------------------------------------------------
# 15. record_decision persists entry when store is attached
# ---------------------------------------------------------------------------


def test_record_decision_persists_entry():
    core = IntegrationCore()
    store, path = _temp_store(auto_save=False)
    try:
        core.attach_memory_store(store)

        decision = ControlDecision(
            active_mode=IntegrationMode.RESOLUTION_OVERRIDE,
            decision_reason="Unresolved tensions.",
            priority_level=6,
        )
        state = IntegrationState(agent_name="Athena", unresolved=4)
        core.record_decision("Athena", decision, state, tags=["unresolved"])

        assert len(store._entries) == 1
        stored = store._entries[0]
        assert stored["agent"] == "Athena"
        assert stored["active_mode"] == IntegrationMode.RESOLUTION_OVERRIDE
        assert stored["tags"] == ["unresolved"]
        assert "id" in stored
        assert "timestamp" in stored
    finally:
        os.unlink(path)


# ---------------------------------------------------------------------------
# 16. load handles corrupt JSON gracefully
# ---------------------------------------------------------------------------


def test_load_corrupt_json_graceful():
    fd, path = tempfile.mkstemp(suffix=".json")
    os.close(fd)
    with open(path, "w") as fh:
        fh.write("{NOT VALID JSON")
    try:
        store = IntegrationMemoryStore(path=path, auto_save=False)
        assert store._entries == []
    finally:
        os.unlink(path)


# ---------------------------------------------------------------------------
# 17. auto_save=False does not write on store_entry
# ---------------------------------------------------------------------------


def test_auto_save_false_does_not_write():
    store, path = _temp_store(auto_save=False)
    try:
        # Record the file mtime before storing
        mtime_before = os.path.getmtime(path)

        import time
        time.sleep(0.05)  # ensure detectable mtime change

        store.store_entry(_sample_entry())
        mtime_after = os.path.getmtime(path)

        assert mtime_before == mtime_after, (
            "File should NOT have been written when auto_save=False"
        )
    finally:
        os.unlink(path)

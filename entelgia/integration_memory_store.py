#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
IntegrationMemoryStore — JSON-backed memory for IntegrationCore.

Persists past control decisions and agent state snapshots to a JSON file so
that IntegrationCore can surface relevant historical context when building
prompt overlays.

Each entry records what happened on a past turn (which rule fired, what the
active mode was, which agent was speaking, and key signal values) together
with optional free-form tags for later retrieval.

Schema (per entry)
------------------
  id            : str   — UUID4 identifier
  agent         : str   — agent name (e.g. "Socrates", "Athena")
  timestamp     : str   — ISO-8601 UTC timestamp
  active_mode   : str   — IntegrationMode value (e.g. "CONCRETE_OVERRIDE")
  decision_reason : str — human-readable reason from ControlDecision
  priority_level  : int — numeric rule priority
  regenerate      : bool
  suppress_personality : bool
  enforce_fixy    : bool
  stagnation      : float
  loop_count      : int
  unresolved      : int
  fatigue         : float
  energy          : float
  tags            : list[str]  — optional caller-supplied labels

Public API
----------
IntegrationMemoryStore(path)          — load-on-construction from JSON file
  .load()                             — (re)load from disk
  .save()                             — persist to disk
  .store_entry(entry: dict)           — append a new entry (auto-assigns id/timestamp)
  .retrieve_by_agent(agent, limit=5)  — most-recent entries for an agent
  .retrieve_relevant(agent, tags, limit=3) — entries matching agent + any supplied tag
  .format_context(entries)            — format list of entries as overlay text block
  .make_entry(agent, decision, state) — build a well-formed entry dict from live objects

Logging tags
------------
[INTEGRATION-MEMORY-LOAD]   — file loaded successfully
[INTEGRATION-MEMORY-SAVE]   — file saved successfully
[INTEGRATION-MEMORY-STORE]  — new entry appended
[INTEGRATION-MEMORY-EVICT]  — oldest entry removed to respect max_entries
[INTEGRATION-MEMORY-QUERY]  — retrieval call completed
"""

from __future__ import annotations

import json
import logging
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------


def _default_memory_path() -> str:
    """Return a writable path for the integration memory JSON file.

    Resolution order (first match wins):
    1. ``ENTELGIA_RUNTIME_DIR`` environment variable
    2. ``XDG_STATE_HOME`` (Linux standard)
    3. ``LOCALAPPDATA`` (Windows)
    4. ``~/.entelgia`` (universal fallback)
    """
    candidates = [
        os.getenv("ENTELGIA_RUNTIME_DIR"),
        os.getenv("XDG_STATE_HOME") and str(Path(os.getenv("XDG_STATE_HOME")) / "entelgia"),
        os.getenv("LOCALAPPDATA") and str(Path(os.getenv("LOCALAPPDATA")) / "entelgia"),
        str(Path.home() / ".entelgia"),
    ]
    base = next(p for p in candidates if p)
    return str(Path(base) / "integration_memory.json")


_DEFAULT_MAX_ENTRIES: int = 500
_CONTEXT_PREFIX: str = "[MEMORY]"

# ---------------------------------------------------------------------------
# IntegrationMemoryStore
# ---------------------------------------------------------------------------


class IntegrationMemoryStore:
    """JSON-backed store for IntegrationCore memory entries.

    Parameters
    ----------
    path:
        Absolute or relative path to the JSON memory file.  Defaults to a
        user-writable location resolved from the ``ENTELGIA_RUNTIME_DIR``,
        ``XDG_STATE_HOME``, or ``LOCALAPPDATA`` environment variables, falling
        back to ``~/.entelgia/integration_memory.json``.  The parent directory
        is created automatically if it does not exist.
    auto_save:
        When ``True`` (default) the store writes back to disk after every
        :meth:`store_entry` call.  Set to ``False`` to batch-save manually
        via :meth:`save`.

    Notes
    -----
    The file is created automatically (with an empty entry list) if it does
    not exist yet, so callers do not need to create it manually.
    """

    def __init__(
        self,
        path: Optional[str] = None,
        auto_save: bool = True,
    ) -> None:
        self._path = path if path is not None else _default_memory_path()
        self._auto_save = auto_save
        self._entries: List[Dict[str, Any]] = []
        self._max_entries: int = _DEFAULT_MAX_ENTRIES
        self.load()

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def load(self) -> None:
        """Load entries from the JSON file.

        If the file does not exist an empty store is initialised and
        persisted so that subsequent saves succeed.
        """
        if not os.path.exists(self._path):
            logger.info(
                "[INTEGRATION-MEMORY-LOAD] file not found — initialising empty store at %s",
                self._path,
            )
            self._entries = []
            self._max_entries = _DEFAULT_MAX_ENTRIES
            self.save()
            return

        try:
            with open(self._path, "r", encoding="utf-8") as fh:
                data = json.load(fh)
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning(
                "[INTEGRATION-MEMORY-LOAD] failed to load %s — %s; using empty store",
                self._path,
                exc,
            )
            self._entries = []
            self._max_entries = _DEFAULT_MAX_ENTRIES
            return

        self._max_entries = int(data.get("max_entries", _DEFAULT_MAX_ENTRIES))
        self._entries = list(data.get("entries", []))
        logger.info(
            "[INTEGRATION-MEMORY-LOAD] loaded %d entries from %s",
            len(self._entries),
            self._path,
        )

    def save(self) -> None:
        """Write the current state back to the JSON file."""
        data: Dict[str, Any] = {
            "version": "1.0",
            "description": (
                "Integration memory store for IntegrationCore. "
                "Persists past control decisions and agent state snapshots."
            ),
            "max_entries": self._max_entries,
            "entries": self._entries,
        }
        try:
            parent_dir = os.path.dirname(self._path)
            if parent_dir:
                os.makedirs(parent_dir, exist_ok=True)
            with open(self._path, "w", encoding="utf-8") as fh:
                json.dump(data, fh, indent=2, ensure_ascii=False)
        except OSError as exc:
            logger.warning(
                "[INTEGRATION-MEMORY-SAVE] failed to write %s — %s",
                self._path,
                exc,
            )
            return
        logger.debug(
            "[INTEGRATION-MEMORY-SAVE] saved %d entries to %s",
            len(self._entries),
            self._path,
        )

    # ------------------------------------------------------------------
    # Write
    # ------------------------------------------------------------------

    def store_entry(self, entry: Dict[str, Any]) -> None:
        """Append *entry* to the store.

        A unique ``id`` and a UTC ``timestamp`` are injected automatically
        if not already present.  The store is trimmed to ``max_entries``
        by evicting the oldest entry when the limit is exceeded.

        Parameters
        ----------
        entry:
            Dict conforming to the entry schema described in the module
            docstring.  Unknown keys are preserved as-is.
        """
        if "id" not in entry:
            entry = dict(entry)
            entry["id"] = str(uuid.uuid4())
        if "timestamp" not in entry:
            entry = dict(entry)
            entry["timestamp"] = datetime.now(timezone.utc).isoformat()

        self._entries.append(entry)
        logger.debug(
            "[INTEGRATION-MEMORY-STORE] id=%s agent=%s mode=%s",
            entry.get("id"),
            entry.get("agent"),
            entry.get("active_mode"),
        )

        # Evict oldest entries when cap is reached
        if len(self._entries) > self._max_entries:
            evicted = self._entries.pop(0)
            logger.debug(
                "[INTEGRATION-MEMORY-EVICT] removed oldest entry id=%s",
                evicted.get("id"),
            )

        if self._auto_save:
            self.save()

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    def retrieve_by_agent(
        self,
        agent: str,
        limit: int = 5,
    ) -> List[Dict[str, Any]]:
        """Return the *limit* most-recent entries for *agent*.

        Parameters
        ----------
        agent:
            Agent name to filter on (case-insensitive).
        limit:
            Maximum number of entries to return.  Entries are returned in
            reverse-chronological order (newest first).

        Returns
        -------
        list[dict]
            Matching entries, newest first.
        """
        agent_lower = agent.lower()
        matches = [
            e for e in self._entries
            if str(e.get("agent", "")).lower() == agent_lower
        ]
        result = list(reversed(matches[-limit:]))
        logger.debug(
            "[INTEGRATION-MEMORY-QUERY] agent=%s limit=%d found=%d",
            agent,
            limit,
            len(result),
        )
        return result

    def retrieve_relevant(
        self,
        agent: str,
        tags: Optional[List[str]] = None,
        limit: int = 3,
    ) -> List[Dict[str, Any]]:
        """Return entries matching *agent* and any element of *tags*.

        When *tags* is ``None`` or empty this falls back to
        :meth:`retrieve_by_agent`.

        Parameters
        ----------
        agent:
            Agent name to filter on (case-insensitive).
        tags:
            List of tag strings.  An entry matches when its ``tags`` list
            contains at least one of the supplied tags.
        limit:
            Maximum number of entries to return.

        Returns
        -------
        list[dict]
            Matching entries, newest first.
        """
        if not tags:
            return self.retrieve_by_agent(agent, limit=limit)

        tag_set = {t.lower() for t in tags}
        agent_lower = agent.lower()
        matches = [
            e for e in self._entries
            if str(e.get("agent", "")).lower() == agent_lower
            and tag_set.intersection(
                {str(t).lower() for t in e.get("tags", [])}
            )
        ]
        result = list(reversed(matches[-limit:]))
        logger.debug(
            "[INTEGRATION-MEMORY-QUERY] agent=%s tags=%s limit=%d found=%d",
            agent,
            tags,
            limit,
            len(result),
        )
        return result

    # ------------------------------------------------------------------
    # Formatting
    # ------------------------------------------------------------------

    def format_context(self, entries: List[Dict[str, Any]]) -> str:
        """Return a compact text block summarising *entries* for prompt injection.

        Each entry is rendered on a single line as::

            [MEMORY] <timestamp> <agent>: mode=<mode> reason=<reason>

        Parameters
        ----------
        entries:
            List of entry dicts as returned by :meth:`retrieve_by_agent` or
            :meth:`retrieve_relevant`.

        Returns
        -------
        str
            Multi-line context block, or an empty string when *entries* is empty.
        """
        if not entries:
            return ""
        lines = []
        for e in entries:
            ts = str(e.get("timestamp", ""))[:19].replace("T", " ")
            agent = e.get("agent", "?")
            mode = e.get("active_mode", "NORMAL")
            reason = str(e.get("decision_reason", "")).strip()
            # Normalize internal whitespace (newlines/tabs → single space) so
            # the injected overlay always fits on a single line.
            reason = " ".join(reason.split())
            # Truncate long reasons to keep the overlay compact
            if len(reason) > 120:
                reason = reason[:117] + "..."
            lines.append(
                f"{_CONTEXT_PREFIX} {ts} {agent}: mode={mode} reason={reason}"
            )
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Factory helper
    # ------------------------------------------------------------------

    @staticmethod
    def make_entry(
        agent: str,
        decision: Any,
        state: Any,
        tags: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Build a well-formed entry dict from live :class:`ControlDecision`
        and :class:`IntegrationState` objects.

        Parameters
        ----------
        agent:
            Agent name.
        decision:
            A ``ControlDecision`` instance (or any object with matching attrs).
        state:
            An ``IntegrationState`` instance (or any object with matching attrs).
        tags:
            Optional list of tag strings to attach.

        Returns
        -------
        dict
            Entry ready to pass to :meth:`store_entry`.
        """
        return {
            "agent": agent,
            "active_mode": getattr(decision, "active_mode", "NORMAL"),
            "decision_reason": getattr(decision, "decision_reason", ""),
            "priority_level": int(getattr(decision, "priority_level", 0)),
            "regenerate": bool(getattr(decision, "regenerate", False)),
            "suppress_personality": bool(
                getattr(decision, "suppress_personality", False)
            ),
            "enforce_fixy": bool(getattr(decision, "enforce_fixy", False)),
            "stagnation": float(getattr(state, "stagnation", 0.0)),
            "loop_count": int(getattr(state, "loop_count", 0)),
            "unresolved": int(getattr(state, "unresolved", 0)),
            "fatigue": float(getattr(state, "fatigue", 0.0)),
            "energy": float(getattr(state, "energy", 100.0)),
            "tags": list(tags) if tags else [],
        }

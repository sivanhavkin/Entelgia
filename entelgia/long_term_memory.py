#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Personal Long-Term Memory System 🧠 (v2.5.0)

Provides psychoanalytically-inspired memory regulation mechanisms:
  - DefenseMechanism  — classifies memories as repressed or suppressed
  - FreudianSlip      — surfaces defended memories probabilistically
  - SelfReplication   — promotes recurring-pattern memories to consciousness

All classes operate on plain data structures so they can be used independently
of the SQLite backend and are fully testable without a live database.
"""

from __future__ import annotations

import random
import re
from typing import Any, Dict, List, Optional, Tuple


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_PAINFUL_EMOTIONS: frozenset = frozenset(
    {"anger", "fear", "shame", "guilt", "anxiety"}
)
_REPRESSION_INTENSITY_THRESHOLD: float = 0.75

_FORBIDDEN_KEYWORDS: frozenset = frozenset(
    {"forbidden", "secret", "dangerous"}
)

_SLIP_CANDIDATE_LIMIT: int = 30
_REPLICATION_CANDIDATE_LIMIT: int = 50
_REPLICATION_MIN_KEYWORD_LEN: int = 4
_REPLICATION_MIN_OCCURRENCES: int = 2
_REPLICATION_MAX_PROMOTED: int = 3


# ---------------------------------------------------------------------------
# DefenseMechanism
# ---------------------------------------------------------------------------


class DefenseMechanism:
    """Classifies every memory write into the unconscious layer.

    *Repressed*  — high-intensity painful emotion (intensity > 0.75).
    *Suppressed* — content contains forbidden/secret/dangerous keywords.

    Both flags may be set simultaneously.
    """

    def analyze(
        self,
        content: str,
        emotion: Optional[str] = None,
        emotion_intensity: float = 0.0,
    ) -> Tuple[int, int]:
        """Return ``(intrusive, suppressed)`` flag tuple (0 or 1 each).

        Parameters
        ----------
        content:
            Raw text of the memory.
        emotion:
            Emotion label, e.g. ``"anger"`` or ``"joy"``.
        emotion_intensity:
            Normalised float in [0, 1].
        """
        intrusive = 0
        suppressed = 0

        # Repression: painful emotion above intensity threshold
        if (
            emotion is not None
            and emotion.lower() in _PAINFUL_EMOTIONS
            and emotion_intensity > _REPRESSION_INTENSITY_THRESHOLD
        ):
            intrusive = 1

        # Suppression: forbidden keywords in content
        content_lower = content.lower()
        if any(kw in content_lower for kw in _FORBIDDEN_KEYWORDS):
            suppressed = 1

        return intrusive, suppressed


# ---------------------------------------------------------------------------
# FreudianSlip
# ---------------------------------------------------------------------------


class FreudianSlip:
    """Surfaces a defended memory fragment after non-Fixy agent turns.

    Rolls a probability (``slip_probability``) against the
    ``_SLIP_CANDIDATE_LIMIT`` most-recent unconscious memories that carry at
    least one defense flag.  When triggered, the chosen fragment is returned
    (to be promoted to the conscious layer by the caller).
    """

    def __init__(self, slip_probability: float = 0.15) -> None:
        self.slip_probability = slip_probability

    def attempt_slip(
        self, recent_memories: List[Dict[str, Any]]
    ) -> Optional[Dict[str, Any]]:
        """Attempt to surface a defended memory.

        Parameters
        ----------
        recent_memories:
            The caller should supply up to ``_SLIP_CANDIDATE_LIMIT`` recent
            unconscious memory dicts.  Each dict should contain at least the
            keys ``"content"``, ``"intrusive"`` (int), and ``"suppressed"``
            (int).

        Returns
        -------
        The slipped memory dict (with ``source`` set to ``"freudian_slip"``)
        or ``None`` if no slip occurs.
        """
        candidates = [
            m
            for m in recent_memories[: _SLIP_CANDIDATE_LIMIT]
            if m.get("intrusive", 0) or m.get("suppressed", 0)
        ]
        if not candidates:
            return None

        # Weight by defense flags
        weights = [
            int(m.get("intrusive", 0)) + int(m.get("suppressed", 0))
            for m in candidates
        ]
        total = sum(weights)
        if total == 0:
            return None

        if random.random() >= self.slip_probability:
            return None

        chosen = random.choices(candidates, weights=weights, k=1)[0]
        result = dict(chosen)
        result["source"] = "freudian_slip"
        return result

    def format_slip(self, memory: Dict[str, Any]) -> str:
        """Return a printable ``[SLIP]`` string for the slipped memory."""
        content = str(memory.get("content", "")).strip()
        return f"[SLIP] {content}"


# ---------------------------------------------------------------------------
# SelfReplication
# ---------------------------------------------------------------------------


class SelfReplication:
    """Promotes recurring-pattern memories to the conscious layer.

    Scans the ``_REPLICATION_CANDIDATE_LIMIT`` most-recent unconscious
    memories for recurring keyword patterns (≥ 4-char Latin words appearing
    in ≥ 2 entries), then promotes up to ``_REPLICATION_MAX_PROMOTED``
    pattern-matching high-importance memories to conscious.

    Runs every ``self_replicate_every_n_turns`` turns (default: 10).
    Printed as ``[SELF-REPL]`` in cyan by the caller.
    """

    def __init__(self, every_n_turns: int = 10) -> None:
        self.every_n_turns = every_n_turns

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_keywords(text: str) -> List[str]:
        """Return lowercase Latin words of length >= 4."""
        return [
            w.lower()
            for w in re.findall(rf"[A-Za-z]{{{_REPLICATION_MIN_KEYWORD_LEN},}}", text)
        ]

    def _find_recurring_keywords(
        self, memories: List[Dict[str, Any]]
    ) -> List[str]:
        """Find keywords that appear in at least ``_REPLICATION_MIN_OCCURRENCES`` entries."""
        keyword_counts: Dict[str, int] = {}
        for mem in memories:
            seen = set(self._extract_keywords(str(mem.get("content", ""))))
            for kw in seen:
                keyword_counts[kw] = keyword_counts.get(kw, 0) + 1

        return [
            kw
            for kw, count in keyword_counts.items()
            if count >= _REPLICATION_MIN_OCCURRENCES
        ]

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def replicate(
        self, recent_memories: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Return up to ``_REPLICATION_MAX_PROMOTED`` memories to promote.

        Parameters
        ----------
        recent_memories:
            Up to ``_REPLICATION_CANDIDATE_LIMIT`` recent unconscious memory
            dicts, each containing at least ``"content"`` and ``"importance"``
            (float).

        Returns
        -------
        List of memory dicts (copies) with ``source`` set to
        ``"self_replication"``, sorted by descending importance.
        """
        candidates = recent_memories[:_REPLICATION_CANDIDATE_LIMIT]
        recurring = set(self._find_recurring_keywords(candidates))
        if not recurring:
            return []

        matched = [
            m
            for m in candidates
            if recurring.intersection(
                set(self._extract_keywords(str(m.get("content", ""))))
            )
        ]

        # Sort by importance descending
        matched.sort(key=lambda m: float(m.get("importance", 0.0)), reverse=True)
        promoted = matched[:_REPLICATION_MAX_PROMOTED]

        result = []
        for m in promoted:
            copy = dict(m)
            copy["source"] = "self_replication"
            result.append(copy)
        return result

    def format_replication(self, memory: Dict[str, Any]) -> str:
        """Return a printable ``[SELF-REPL]`` string for the promoted memory."""
        content = str(memory.get("content", "")).strip()
        return f"[SELF-REPL] {content}"

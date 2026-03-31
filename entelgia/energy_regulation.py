#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Energy-Based Agent Regulation System (v2.5.0)

Provides energy tracking, safety supervision, and dream-cycle consolidation
for Entelgia agents.

Classes:
    FixyRegulator  — Meta-level energy supervisor.
    EntelgiaAgent  — Agent with energy tracking and dream cycle consolidation.
"""

from __future__ import annotations

import logging
import math
import random
from typing import Dict, List, Optional

_logger = logging.getLogger(__name__)


class FixyRegulator:
    """Meta-level energy supervisor.

    Monitors *energy_level* against a configurable safety threshold.
    Triggers a dream cycle when energy is too low, and performs a stochastic
    hallucination-risk check (p=0.10) when energy drops below 60 %.
    """

    DEFAULT_SAFETY_THRESHOLD: float = 35.0
    HALLUCINATION_RISK_PROBABILITY: float = 0.10
    HALLUCINATION_RISK_ENERGY_CUTOFF: float = 60.0

    def __init__(self, safety_threshold: float = DEFAULT_SAFETY_THRESHOLD) -> None:
        self.safety_threshold = safety_threshold

    def check_stability(self, agent: "EntelgiaAgent") -> Optional[str]:
        """Evaluate agent energy and apply regulation if necessary.

        Returns a status string when an action is taken, otherwise None.
        """
        if agent.energy_level <= self.safety_threshold:
            agent._run_dream_cycle()
            return "DREAM_TRIGGERED"

        if agent.energy_level < self.HALLUCINATION_RISK_ENERGY_CUTOFF:
            if random.random() < self.HALLUCINATION_RISK_PROBABILITY:
                return "HALLUCINATION_RISK_DETECTED"

        return None


class EntelgiaAgent:
    """Agent with energy tracking and dream cycle consolidation.

    Attributes:
        name              — Agent identifier.
        energy_level      — Current energy (starts at 100.0).
        conscious_memory  — Active inputs accumulated during processing.
        subconscious_store — Pending memories awaiting integration.
        long_term_memory  — Persistent store for critical memories promoted
                            from short-term memory during dream cycles.
        regulator         — Associated :class:`FixyRegulator` instance.
    """

    ENERGY_DRAIN_MIN: float = 8.0
    ENERGY_DRAIN_MAX: float = 15.0
    INITIAL_ENERGY: float = 100.0
    DREAM_RESOLVE_TOP_K: int = 5
    DREAM_WEIGHT_REDUCTION: float = 0.3

    def __init__(
        self,
        name: str,
        energy_drain_min: float = ENERGY_DRAIN_MIN,
        energy_drain_max: float = ENERGY_DRAIN_MAX,
        safety_threshold: float = FixyRegulator.DEFAULT_SAFETY_THRESHOLD,
    ) -> None:
        self.name = name
        self.energy_drain_min = energy_drain_min
        self.energy_drain_max = energy_drain_max
        self.energy_level: float = self.INITIAL_ENERGY
        self.conscious_memory: List[str] = []
        self.subconscious_store: List[str] = []
        self.long_term_memory: List[str] = []
        self.unresolved_topics: List[Dict] = []
        self.dream_resolutions: List[Dict] = []
        self.regulator = FixyRegulator(safety_threshold=safety_threshold)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _drain_energy(self) -> float:
        """Decrease energy by a random amount within the configured range."""
        drain = random.uniform(self.energy_drain_min, self.energy_drain_max)
        self.energy_level = max(0.0, self.energy_level - drain)
        return drain

    def _is_relevant(self, memory: Optional[str]) -> bool:
        """Return True if *memory* is emotionally or operationally relevant.

        Override in subclasses for richer relevance scoring.
        Entries that are empty or contain only whitespace are considered
        irrelevant and will be forgotten during dream integration.
        """
        return bool(memory and memory.strip())

    def _is_critical(self, memory: Optional[str]) -> bool:
        """Return True if *memory* is critical enough to be promoted to LTM.

        A memory is considered critical when it is relevant (non-empty) and
        contains at least one word of four or more characters, indicating
        substantive, non-trivial content.  Override in subclasses to apply
        richer emotional- or importance-based scoring.
        """
        if not self._is_relevant(memory):
            return False
        assert memory is not None
        return any(len(word) >= 4 for word in memory.split())

    def _score_unresolved(self, item: Dict) -> float:
        """Compute a salience score for an unresolved topic.

        Higher scores indicate topics that should be prioritised during dream
        processing.  The score combines intensity, conflict pressure, and a
        logarithmic repetition bonus.
        """
        intensity = float(item.get("intensity", 0.0))
        conflict = float(item.get("conflict", 0.0))
        repetition = int(item.get("repetition", 1))
        return intensity + conflict + math.log(repetition + 1)

    def _select_top_unresolved(self, k: Optional[int] = None) -> List[Dict]:
        """Return the top *k* unresolved topics sorted by salience score."""
        if k is None:
            k = self.DREAM_RESOLVE_TOP_K
        pending = [
            t for t in self.unresolved_topics if t.get("status") == "unresolved"
        ]
        pending.sort(key=self._score_unresolved, reverse=True)
        return pending[:k]

    def _generate_dream_insight(self, item: Dict) -> str:
        """Return a reframed abstraction of an unresolved topic.

        Produces a deterministic dream-reflection string that names the topic,
        its registered intensity and conflict level, and suggests it may repay
        closer examination — without requiring a live LLM.
        """
        topic = item.get("topic", "")
        intensity = float(item.get("intensity", 0.0))
        conflict = float(item.get("conflict", 0.0))
        return (
            f"Dream reflection on '{topic}': "
            f"intensity {intensity:.2f}, conflict {conflict:.2f} — "
            "this thread may hold unexamined assumptions worth revisiting."
        )

    def _run_dream_cycle(self) -> None:
        """Integrate subconscious memories into conscious memory and recharge.

        During the dream cycle memories undergo integration:

        - Subconscious memories are transferred to conscious memory.
        - Critical and relevant STM entries are promoted to long-term memory.
        - Short-term memory entries that are not emotionally or operationally
          relevant are forgotten; no long-term memories are hard-deleted.
        - Unresolved topics are processed: the top-k items (by salience) are
          reframed, marked as ``"integrated"``, and their weight is reduced;
          they are preserved in the store — never deleted.
        - Energy is restored to full.
        """
        # ── Unresolved topic integration ──────────────────────────────────────────
        top_unresolved = self._select_top_unresolved()
        resolved_this_cycle = 0
        for item in top_unresolved:
            insight = self._generate_dream_insight(item)
            item["status"] = "integrated"
            item["weight"] = item.get("weight", 1.0) * self.DREAM_WEIGHT_REDUCTION
            self.dream_resolutions.append(
                {
                    "type": "dream_resolution",
                    "topic": item.get("topic", ""),
                    "insight": insight,
                }
            )
            resolved_this_cycle += 1
        total_integrated = sum(
            1 for t in self.unresolved_topics if t.get("status") == "integrated"
        )
        remaining = sum(
            1 for t in self.unresolved_topics if t.get("status") == "unresolved"
        )
        _logger.info(
            "[DREAM-RESOLVE] agent=%s resolved=%d integrated=%d remaining=%d",
            self.name,
            resolved_this_cycle,
            total_integrated,
            remaining,
        )
        # ─────────────────────────────────────────────────────────────────────────
        # Integrate subconscious into conscious layer
        self.conscious_memory.extend(self.subconscious_store)
        # Promote critical entries from STM to long-term memory
        for entry in self.conscious_memory:
            if self._is_critical(entry) and entry not in self.long_term_memory:
                self.long_term_memory.append(entry)
        # Forget STM entries that are not emotionally or operationally relevant
        self.conscious_memory = [
            m for m in self.conscious_memory if self._is_relevant(m)
        ]
        self.subconscious_store = []
        # Restore energy to full
        self.energy_level = self.INITIAL_ENERGY

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def process_step(self, input_text: str) -> str:
        """Process one input step.

        Drains energy, appends *input_text* to memory, checks stability.
        Returns ``"RECHARGED_AND_READY"`` after a forced dream cycle,
        otherwise returns ``"OK"``.
        """
        self._drain_energy()
        self.conscious_memory.append(input_text)
        result = self.regulator.check_stability(self)
        if result == "DREAM_TRIGGERED":
            return "RECHARGED_AND_READY"
        return "OK"

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

import random
from typing import List, Optional


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
        regulator         — Associated :class:`FixyRegulator` instance.
    """

    ENERGY_DRAIN_MIN: float = 8.0
    ENERGY_DRAIN_MAX: float = 15.0
    INITIAL_ENERGY: float = 100.0

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
        self.regulator = FixyRegulator(safety_threshold=safety_threshold)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _drain_energy(self) -> float:
        """Decrease energy by a random amount within the configured range."""
        drain = random.uniform(self.energy_drain_min, self.energy_drain_max)
        self.energy_level = max(0.0, self.energy_level - drain)
        return drain

    def _run_dream_cycle(self) -> None:
        """Consolidate subconscious memories into conscious memory and recharge."""
        # Move pending memories to conscious layer
        self.conscious_memory.extend(self.subconscious_store)
        # Keep only the most recent entries to avoid unbounded growth
        keep = getattr(self.regulator, "dream_keep_memories", 5)
        self.conscious_memory = self.conscious_memory[-keep:]
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

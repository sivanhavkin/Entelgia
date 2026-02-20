#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Energy-Based Agent Regulation for Entelgia
Provides energy tracking, dream cycle consolidation, and safety regulation.

Integration points:
- FixyRegulator  -> extends/composes with InteractiveFixy
- EntelgiaAgent  -> used by Entelgia_production_meta.py agent instances
- dream_cycle()  -> integrates with EnhancedMemoryIntegration
"""

import random
from typing import List


class FixyRegulator:
    """
    Safety regulator that monitors agent stability and triggers a dream cycle when needed.

    Acts as a meta-level supervisor (similar to InteractiveFixy in the main system),
    but focused on energy thresholds rather than dialogue quality patterns.

    Future: Compose with or extend entelgia.fixy_interactive.InteractiveFixy.
    """

    def __init__(
        self,
        threshold: float = 35.0,
        hallucination_energy_cap: float = 60.0,
        hallucination_probability: float = 0.1,
    ):
        self.name = "Fixy"
        self.safety_threshold = threshold  # Safety threshold, slightly above the default minimum
        self.hallucination_energy_cap = hallucination_energy_cap
        self.hallucination_probability = hallucination_probability

    def inspect_agent(self, target_agent: "EntelgiaAgent") -> bool:
        """
        Check whether the agent is stable enough to continue processing.

        Args:
            target_agent: The agent to inspect.

        Returns:
            True if a dream cycle (recharge) should be triggered, False otherwise.
        """
        # If energy is too low, Fixy forces a "sleep" (dream cycle)
        if target_agent.energy_level <= self.safety_threshold:
            return True  # Trigger forced dream cycle

        # Consistency check (currently mocked as a random probability)
        if random.random() < self.hallucination_probability and target_agent.energy_level < self.hallucination_energy_cap:
            return True

        return False


class EntelgiaAgent:
    """
    Agent with energy tracking and dream cycle consolidation.

    Represents the internal state of a dialogue agent (e.g., Socrates, Athena).
    Tracks conscious memory and energy, and delegates stability checks to FixyRegulator.

    Future integration:
    - Use entelgia.enhanced_personas.get_persona() to initialize persona data.
    - Feed conscious_memory into entelgia.context_manager.ContextManager.
    - Move subconscious_store integration to EnhancedMemoryIntegration.
    """

    def __init__(self, name: str, role: str, energy_safety_threshold: float = 35.0):
        self.name = name
        self.role = role
        self.energy_level: float = 100.0
        self.conscious_memory: List[str] = []
        self.subconscious_store: List[str] = []
        self.regulator = FixyRegulator(threshold=energy_safety_threshold)

    def process_step(
        self,
        input_text: str,
        drain_min: float = 8.0,
        drain_max: float = 15.0,
    ) -> str:
        """
        Process one dialogue step: consume energy, record input, and check stability.

        Args:
            input_text: The input query or message for this turn.
            drain_min: Minimum energy drained per step.
            drain_max: Maximum energy drained per step.

        Returns:
            Status string indicating the outcome of this step.
        """
        # Basic energy drain per action
        self.energy_level -= random.uniform(drain_min, drain_max)
        self.conscious_memory.append(input_text)

        # Fixy regulator checks the agent's stability
        if self.regulator.inspect_agent(self):
            self.dream_cycle()
            return "RECHARGED_AND_READY"

        return f"[{self.name}] Active and processing..."

    def dream_cycle(self, keep_memories: int = 5) -> None:
        """
        Internal consolidation process: forgetting and memory integration.

        Clears old conscious memories (keeping the last ``keep_memories`` entries),
        moves insights from the subconscious store to the conscious layer, and
        restores full energy.

        Future: Integrate with EnhancedMemoryIntegration for meaningful LTM transfer.

        Args:
            keep_memories: Number of recent conscious memories to retain.
        """
        # Forgetting phase: clear old context, keep last N entries
        self.conscious_memory = self.conscious_memory[-keep_memories:]

        # Integration phase: move insights from subconscious to conscious layer
        if self.subconscious_store:
            self.conscious_memory.extend(self.subconscious_store)
            self.subconscious_store = []

        # Full energy restore
        self.energy_level = 100.0

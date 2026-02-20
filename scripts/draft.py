#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Draft: Energy-Based Agent Regulation for Entelgia
Prototype for energy tracking, dream cycle consolidation, and safety regulation.

This module is intended to be integrated into the main Entelgia system
as an extension to InteractiveFixy and the agent persona layer.

Future integration points:
- FixyRegulator  -> entelgia.fixy_interactive.InteractiveFixy (extend or compose)
- EntelgiaAgent  -> Entelgia_production_meta.py agent instances
- dream_cycle()  -> entelgia.context_manager.EnhancedMemoryIntegration
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

    def __init__(self, threshold: float = 35.0):
        self.name = "Fixy"
        self.safety_threshold = (
            threshold  # Safety threshold, slightly above the default minimum
        )

    def inspect_agent(self, target_agent: "EntelgiaAgent") -> bool:
        """
        Check whether the agent is stable enough to continue processing.

        Args:
            target_agent: The agent to inspect.

        Returns:
            True if a dream cycle (recharge) should be triggered, False otherwise.
        """
        print(
            f"[{self.name}] Inspecting {target_agent.name}... Current Energy: {target_agent.energy_level:.1f}%"
        )

        # If energy is too low, Fixy forces a "sleep" (dream cycle)
        if target_agent.energy_level <= self.safety_threshold:
            print(
                f"[{self.name}] WARNING: {target_agent.name} is unstable due to low energy. FORCING RECHARGE."
            )
            return True  # Trigger forced dream cycle

        # Consistency check (currently mocked as a random probability)
        if random.random() < 0.1 and target_agent.energy_level < 60:
            print(
                f"[{self.name}] Hallucination risk detected. Suspending dialogue for Dream Cycle."
            )
            return True

        return False


class EntelgiaAgent:
    """
    Prototype agent with energy tracking and dream cycle consolidation.

    Represents the internal state of a dialogue agent (e.g., Socrates, Athena).
    Tracks conscious memory and energy, and delegates stability checks to FixyRegulator.

    Future integration:
    - Use entelgia.enhanced_personas.get_persona() to initialize persona data.
    - Feed conscious_memory into entelgia.context_manager.ContextManager.
    - Move subconscious_store integration to EnhancedMemoryIntegration.
    """

    def __init__(self, name: str, role: str):
        self.name = name
        self.role = role
        self.energy_level: float = 100.0
        self.conscious_memory: List[str] = []
        self.subconscious_store: List[str] = []
        self.forgotten_memories: List[str] = []  # De-prioritised but never deleted
        self.regulator = FixyRegulator()  # Each agent is supervised by a FixyRegulator

    def process_step(self, input_text: str) -> str:
        """
        Process one dialogue step: consume energy, record input, and check stability.

        Args:
            input_text: The input query or message for this turn.

        Returns:
            Status string indicating the outcome of this step.
        """
        # Basic energy drain per action
        self.energy_level -= random.uniform(8, 15)
        self.conscious_memory.append(input_text)

        # Fixy regulator checks the agent's stability
        should_recharge = self.regulator.inspect_agent(self)

        if should_recharge:
            self.dream_cycle()
            return "RECHARGED_AND_READY"

        return f"[{self.name}] Active and processing..."

    def dream_cycle(self):
        """
        Internal consolidation process: memory synchronisation without deletion.

        Synchronises STM (conscious_memory) and LTM (subconscious_store):
        - Emotionally relevant STM entries are collected and promoted to LTM.
        - Unimportant entries are de-prioritised (marked as forgotten) but never deleted.
        - All memories of every type are preserved intact; no entry is removed.
        - Energy is fully restored.

        Future: Integrate with EnhancedMemoryIntegration for meaningful LTM transfer.
        """
        print(f"\n--- STARTING DREAM CYCLE: {self.name} ---")

        # Emotional keywords used to assess relevance of each STM entry
        emotional_keywords = {
            "fear", "joy", "anger", "love", "sad", "happy", "afraid", "anxious",
            "excited", "curious", "worried", "trust", "disgust", "surprise",
            "ethics", "meaningful", "important", "significant",
        }

        # --- Sync phase: collect emotionally relevant STM entries into LTM ---
        promoted = 0
        deprioritised = 0
        for entry in self.conscious_memory:
            lower = entry.lower()
            is_relevant = any(kw in lower for kw in emotional_keywords)
            if is_relevant:
                # Promote to LTM (subconscious_store) if not already present
                if entry not in self.subconscious_store:
                    self.subconscious_store.append(entry)
                    promoted += 1
            else:
                # De-prioritise: record in forgotten_memories but do NOT delete
                if entry not in self.forgotten_memories:
                    self.forgotten_memories.append(entry)
                    deprioritised += 1

        print(
            f"-> [Sync] {promoted} emotionally relevant STM entries promoted to LTM; "
            f"{deprioritised} entries de-prioritised (all memories preserved)."
        )

        # Full energy restore
        self.energy_level = 100.0
        print(f"--- {self.name} IS NOW FULLY RECHARGED ---\n")


# Example run
socrates = EntelgiaAgent("Socrates", "Analytic")

for turn in range(1, 8):
    print(f"--- Turn {turn} ---")
    status = socrates.process_step("User query about ethics...")
    if status == "RECHARGED_AND_READY":
        print("System Note: Dialogue paused for internal consolidation.")

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Energy Regulation Demo 📖

Demonstrates a Socrates agent depleting energy over 8 turns and recovering
through a dream cycle using the Energy-Based Agent Regulation System (v2.5.0).

Run with:
    python examples/demo_energy_regulation.py
"""

from entelgia.energy_regulation import EntelgiaAgent, FixyRegulator


def main():
    print("=" * 60)
    print("⚡ Energy-Based Agent Regulation Demo (v2.5.0)")
    print("=" * 60)

    # Create a Socrates agent with default safety threshold (35.0)
    agent = EntelgiaAgent(
        name="Socrates",
        energy_drain_min=8.0,
        energy_drain_max=15.0,
        safety_threshold=FixyRegulator.DEFAULT_SAFETY_THRESHOLD,
    )

    inputs = [
        "What is virtue?",
        "Can virtue be taught?",
        "Is knowledge the same as virtue?",
        "What does the unexamined life mean?",
        "How do we define justice?",
        "Is the soul immortal?",
        "What is the nature of beauty?",
        "Can we know anything for certain?",
    ]

    print(f"\nAgent: {agent.name}")
    print(f"Initial energy: {agent.energy_level:.1f}")
    print(f"Safety threshold: {agent.regulator.safety_threshold:.1f}")
    print("-" * 60)

    for turn, text in enumerate(inputs, start=1):
        result = agent.process_step(text)
        status = "⚡ RECHARGED" if result == "RECHARGED_AND_READY" else "  OK"
        print(
            f"Turn {turn:2d} | Energy: {agent.energy_level:6.1f} | "
            f"{status} | Input: {text[:40]}"
        )

    print("-" * 60)
    print(f"Final energy: {agent.energy_level:.1f}")
    print(f"Conscious memories: {len(agent.conscious_memory)}")
    print("\nDemo complete. ✅")


if __name__ == "__main__":
    main()

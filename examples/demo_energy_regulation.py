#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Demo: Energy-Based Agent Regulation in Entelgia

Shows how FixyRegulator and EntelgiaAgent work together to model cognitive
fatigue and recovery through dream cycle consolidation.

Run:
    python examples/demo_energy_regulation.py
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from entelgia import FixyRegulator, EntelgiaAgent


def run_demo():
    print("=" * 60)
    print("  Entelgia — Energy Regulation Demo (v2.5.0)")
    print("=" * 60)

    # Create an agent with default safety threshold (35%)
    socrates = EntelgiaAgent("Socrates", "Analytic")
    print(f"\nAgent '{socrates.name}' initialized. Energy: {socrates.energy_level:.1f}%")
    print(f"Safety threshold: {socrates.regulator.safety_threshold:.1f}%\n")

    user_queries = [
        "What is the nature of justice?",
        "Can virtue be taught?",
        "What is the relationship between knowledge and belief?",
        "Is the soul immortal?",
        "What constitutes a good life?",
        "How do we know what we know?",
        "What is the definition of piety?",
        "Is courage always a virtue?",
    ]

    for i, query in enumerate(user_queries, start=1):
        print(f"--- Turn {i} ---")
        print(f"  Input: {query}")
        print(f"  Energy before: {socrates.energy_level:.1f}%")

        status = socrates.process_step(query)

        print(f"  Status: {status}")
        print(f"  Energy after: {socrates.energy_level:.1f}%")

        if status == "RECHARGED_AND_READY":
            print("  [System] Dream cycle completed — agent is recharged.\n")
        else:
            print()

    print("=" * 60)
    print(f"  Final energy: {socrates.energy_level:.1f}%")
    print(f"  Conscious memories retained: {len(socrates.conscious_memory)}")
    print("=" * 60)


if __name__ == "__main__":
    run_demo()

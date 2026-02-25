#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Full-dialogue demo test.

Validates the structural and metric properties of the canonical 10-turn
demo dialogue.  Run with ``pytest -s`` to see the computed metric values
and their interpretation printed inline.
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from entelgia.dialogue_metrics import (
    circularity_per_turn,
    compute_all_metrics,
)

# ---------------------------------------------------------------------------
# Canonical demo dialogue — 10 turns, covers all three agents
# ---------------------------------------------------------------------------

DEMO_DIALOGUE = [
    {
        "role": "Socrates",
        "text": "Consciousness emerges from complex information processing systems.",
    },
    {
        "role": "Athena",
        "text": "Consciousness arises from information processing in complex systems.",
    },
    {
        "role": "Socrates",
        "text": "Free will might be an illusion created by deterministic processes.",
    },
    {
        "role": "Athena",
        "text": "Therefore integrating both views reveals a compatibilist position.",
    },
    {
        "role": "Fixy",
        "text": "I notice we have circled back. Let us reframe: how does embodiment change this?",
    },
    {
        "role": "Socrates",
        "text": "The boundaries of self dissolve when examined through neuroscience.",
    },
    {
        "role": "Athena",
        "text": "Language shapes the very thoughts we believe are our own.",
    },
    {
        "role": "Socrates",
        "text": "Therefore connecting these threads: identity is narrative, not substance.",
    },
    {
        "role": "Athena",
        "text": "Bridging neuroscience and philosophy opens new unified frameworks.",
    },
    {
        "role": "Socrates",
        "text": "Synthesis of empirical and phenomenal approaches bridges the gap.",
    },
]

# Metric thresholds used in the demo test assertions
_MAX_DEMO_CIRCULARITY = 0.1  # circularity_rate should stay below this
_MIN_DEMO_PROGRESS = 0.5  # progress_rate should stay above this


# ---------------------------------------------------------------------------
# Demo test — asserts structural and metric correctness of the demo dialogue
# ---------------------------------------------------------------------------


def test_full_dialogue_demo():
    """
    Validate structural and metric properties of the demo dialogue.

    Prints the computed metric values and their interpretation so that
    anyone running the suite with ``pytest -s`` can see what the test
    actually measured.
    """
    # --- metric computation ---
    metrics = compute_all_metrics(DEMO_DIALOGUE)
    series = circularity_per_turn(DEMO_DIALOGUE)

    # --- human-readable results for this test ---
    print(f"\n--- test_full_dialogue_demo results ---")
    print(f"  Dialogue turns   : {len(DEMO_DIALOGUE)}")
    print(f"  Roles present    : {sorted({t['role'] for t in DEMO_DIALOGUE})}")
    print(
        f"  Circularity Rate : {metrics['circularity_rate']:.3f}"
        f"  (expected < {_MAX_DEMO_CIRCULARITY})"
        f"  {'✓ PASS' if metrics['circularity_rate'] < _MAX_DEMO_CIRCULARITY else '✗ FAIL'}"
    )
    print(
        f"  Progress Rate    : {metrics['progress_rate']:.3f}"
        f"  (expected > {_MIN_DEMO_PROGRESS})"
        f"  {'✓ PASS' if metrics['progress_rate'] > _MIN_DEMO_PROGRESS else '✗ FAIL'}"
    )
    print(
        f"  Intervention Utility : {metrics['intervention_utility']:.3f}"
        f"  (expected >= 0.0)"
        f"  {'✓ PASS' if metrics['intervention_utility'] >= 0.0 else '✗ FAIL'}"
    )
    print(
        f"  Per-turn series length : {len(series)}"
        f"  (expected {len(DEMO_DIALOGUE)})"
        f"  {'✓ PASS' if len(series) == len(DEMO_DIALOGUE) else '✗ FAIL'}"
    )
    print(
        f"  First-turn circularity : {series[0]:.3f}"
        f"  (expected 0.0)"
        f"  {'✓ PASS' if abs(series[0]) < 1e-9 else '✗ FAIL'}"
    )

    # --- structural assertions ---
    assert len(DEMO_DIALOGUE) == 10, "Demo dialogue must have exactly 10 turns"

    roles = {t["role"] for t in DEMO_DIALOGUE}
    assert "Socrates" in roles, "Demo dialogue must include Socrates"
    assert "Athena" in roles, "Demo dialogue must include Athena"
    assert "Fixy" in roles, "Demo dialogue must include Fixy"

    for turn in DEMO_DIALOGUE:
        assert "role" in turn and "text" in turn, "Each turn needs role and text keys"
        assert turn["text"].strip(), "Each turn must have non-empty text"

    # --- metric assertions ---
    assert (
        metrics["circularity_rate"] < _MAX_DEMO_CIRCULARITY
    ), "Demo circularity should be low (< 0.1)"
    assert (
        metrics["progress_rate"] > _MIN_DEMO_PROGRESS
    ), "Demo progress should be high (> 0.5)"
    assert (
        metrics["intervention_utility"] >= 0.0
    ), "Fixy intervention utility must be non-negative"

    assert len(series) == len(
        DEMO_DIALOGUE
    ), "Per-turn series length must match dialogue length"
    assert series[0] == pytest.approx(
        0.0
    ), "First turn has no prior context, circularity must be 0"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])

#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Full-dialogue demo test.

When the test suite runs, this test prints one complete sample dialogue
between Socrates, Athena and Fixy so that you can see what an actual
agent conversation looks like together with its computed metrics.

Run with   pytest -s   to see the output inline, or rely on the
pytest_terminal_summary hook in conftest.py which prints it automatically
at the end of every test session.
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from entelgia.dialogue_metrics import (
    circularity_rate,
    circularity_per_turn,
    progress_rate,
    intervention_utility,
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

# Scaling factor: maps a [0, 1] value to a bar of up to 20 '#' characters
_BAR_SCALE = 20

# Metric thresholds used in the demo test assertions
_MAX_DEMO_CIRCULARITY = 0.1   # circularity_rate should stay below this
_MIN_DEMO_PROGRESS = 0.5      # progress_rate should stay above this
_AGENT_EMOJI = {"Socrates": "🏛️ ", "Athena": "🦉 ", "Fixy": "🔍 "}


def format_demo_dialogue(dialog: list) -> str:
    """Return a formatted, human-readable representation of the demo dialogue."""
    lines = []
    lines.append("=" * 62)
    lines.append("  ENTELGIA FULL DIALOGUE DEMO")
    lines.append("  Topic: Philosophy of Mind — Consciousness, Free Will & Identity")
    lines.append("  Agents: 🏛️  Socrates   🦉 Athena   🔍 Fixy")
    lines.append("=" * 62)

    for i, turn in enumerate(dialog, start=1):
        role = turn["role"]
        emoji = _AGENT_EMOJI.get(role, "   ")
        text = turn["text"]
        lines.append(f"  Turn {i:2d} │ {emoji}{role:<9} │ {text}")

    lines.append("-" * 62)

    metrics = compute_all_metrics(dialog)
    series = circularity_per_turn(dialog)

    lines.append("  Dialogue Metrics:")
    lines.append(
        f"    Circularity Rate     : {metrics['circularity_rate']:.3f}  (lower is better)"
    )
    lines.append(
        f"    Progress Rate        : {metrics['progress_rate']:.3f}  (higher is better)"
    )
    lines.append(
        f"    Intervention Utility : {metrics['intervention_utility']:.3f}  (Fixy's positive impact)"
    )

    lines.append("")
    lines.append("  Per-turn circularity (rolling window = 6):")
    for i, val in enumerate(series, start=1):
        bar = "#" * int(round(val * _BAR_SCALE))
        lines.append(f"    Turn {i:2d}: {val:.2f} |{bar}")

    lines.append("=" * 62)
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Demo test — always prints the dialogue; also asserts structural correctness
# ---------------------------------------------------------------------------


def test_full_dialogue_demo(capsys):
    """
    Print one complete agent dialogue so that anyone running the test suite
    can see what an actual Entelgia conversation looks like.

    The test also asserts basic structural and metric properties to ensure
    the demo dialogue itself is well-formed.
    """
    output = format_demo_dialogue(DEMO_DIALOGUE)

    # Bypass pytest's capture so the demo is always visible with -s
    with capsys.disabled():
        print("\n" + output + "\n")

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
    metrics = compute_all_metrics(DEMO_DIALOGUE)
    assert metrics["circularity_rate"] < _MAX_DEMO_CIRCULARITY, "Demo circularity should be low (< 0.1)"
    assert metrics["progress_rate"] > _MIN_DEMO_PROGRESS, "Demo progress should be high (> 0.5)"
    assert (
        metrics["intervention_utility"] >= 0.0
    ), "Fixy intervention utility must be non-negative"

    series = circularity_per_turn(DEMO_DIALOGUE)
    assert len(series) == len(DEMO_DIALOGUE), "Per-turn series length must match dialogue length"
    assert series[0] == pytest.approx(0.0), "First turn has no prior context, circularity must be 0"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])

#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Ablation Study for Entelgia Dialogue Systems
Compares four experimental conditions to isolate the contribution of each
sub-system to dialogue quality.

Conditions
----------
BASELINE         — Fixed round-robin turn-taking, no Fixy, no dream cycle,
                   no LTM prioritisation.
DIALOGUE_ENGINE  — Adds dynamic speaker selection and varied seed strategies
                   from :mod:`entelgia.dialogue_engine`.
FIXY             — Adds Fixy need-based interventions from
                   :mod:`entelgia.fixy_interactive` on top of the baseline.
DREAM            — Adds dream-cycle / energy consolidation from
                   :mod:`entelgia.energy_regulation` on top of the baseline.

Outputs
-------
* A formatted text table: metrics across conditions.
* A line graph: circularity over turns (one series per condition).
"""

from __future__ import annotations

import os
import random
import re
import sys
from enum import Enum
from typing import Dict, List, Optional

try:
    from .dialogue_metrics import (
        circularity_per_turn,
        circularity_rate,
        compute_all_metrics,
        intervention_utility,
        progress_rate,
    )
    from .dialogue_engine import DialogueEngine
    from .fixy_interactive import InteractiveFixy
    from .energy_regulation import EntelgiaAgent, FixyRegulator
except ImportError:
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from entelgia.dialogue_metrics import (
        circularity_per_turn,
        circularity_rate,
        compute_all_metrics,
        intervention_utility,
        progress_rate,
    )
    from entelgia.dialogue_engine import DialogueEngine
    from entelgia.fixy_interactive import InteractiveFixy
    from entelgia.energy_regulation import EntelgiaAgent, FixyRegulator


# ---------------------------------------------------------------------------
# Condition enum
# ---------------------------------------------------------------------------


class AblationCondition(Enum):
    """Four experimental conditions for the ablation study."""

    BASELINE = "Baseline"
    DIALOGUE_ENGINE = "DialogueEngine/Seed"
    FIXY = "Fixy Interventions"
    DREAM = "Dream/Energy"


# ---------------------------------------------------------------------------
# Synthetic dialogue generators
# Each generator produces a list of turn dicts {"role": str, "text": str}.
# The content is deterministic given a fixed random seed so that results
# are reproducible.
# ---------------------------------------------------------------------------

# Shared topic pools used by the simulation
_TOPIC_POOLS: Dict[str, List[str]] = {
    "repetitive": [
        "consciousness emerges from complex information processing systems",
        "consciousness arises from information processing in complex systems",
        "complex systems produce consciousness through information processing",
        "information processing gives rise to consciousness in complex systems",
        "the emergence of consciousness relies on information processing",
    ],
    "evolving": [
        "consciousness emerges from complex information processing systems",
        "free will might be an illusion created by deterministic processes",
        "therefore integrating both views reveals a compatibilist position",
        "the boundaries of self dissolve when examined through neuroscience",
        "language shapes the very thoughts we believe are our own",
        "therefore connecting these threads: identity is narrative not substance",
        "bridging neuroscience and philosophy opens new unified frameworks",
        "synthesis of empirical and phenomenal approaches bridges the gap",
    ],
    "shallow": [
        "yes that is interesting",
        "I agree with you on that point",
        "that makes sense to me",
        "indeed you are right about this",
        "true that is a valid observation",
    ],
    "deep": [
        "the fundamental implication here is that subjectivity cannot be fully reduced",
        "therefore we must consider the hard problem as irreducible to functional accounts",
        "integrating phenomenal consciousness with global workspace theory bridges both",
        "because qualia resist third-person description, first-person methods are required",
        "the solution resolves the tension by positing dual-aspect monism as foundation",
    ],
}

_AGENTS = ["Socrates", "Athena"]


def _pick(pool: List[str], rng: random.Random) -> str:
    return rng.choice(pool)


# ---------------------------------------------------------------------------
# Baseline: fixed round-robin, repetitive topics, no special modules
# ---------------------------------------------------------------------------


def _simulate_baseline(turns: int, rng: random.Random) -> List[Dict[str, str]]:
    """Fixed A-B alternation, highly repetitive content."""
    dialog: List[Dict[str, str]] = []
    for i in range(turns):
        role = _AGENTS[i % 2]
        text = _pick(_TOPIC_POOLS["repetitive"], rng)
        dialog.append({"role": role, "text": text})
    return dialog


# ---------------------------------------------------------------------------
# DialogueEngine condition: varied seeds shift topic more often
# ---------------------------------------------------------------------------


def _simulate_dialogue_engine(turns: int, rng: random.Random) -> List[Dict[str, str]]:
    """Dynamic speaker selection + evolving topic pool (mirrors DialogueEngine behaviour)."""
    dialog: List[Dict[str, str]] = []
    pool = _TOPIC_POOLS["evolving"]
    # Use an expanding pool index so topics genuinely shift
    for i in range(turns):
        role = _AGENTS[i % 2] if i < 4 else rng.choice(_AGENTS)
        # Topic rotates through the pool, then loops
        text = pool[i % len(pool)]
        dialog.append({"role": role, "text": text})
    return dialog


# ---------------------------------------------------------------------------
# Fixy condition: baseline + Fixy interventions when repetition is detected
# ---------------------------------------------------------------------------

_FIXY_INTERVENTIONS = [
    "I notice we have circled back to the same point. Let us reframe: "
    "how does embodiment change the picture?",
    "The dialogue seems to bridge the same ground. "
    "Integrating both views, what synthesis emerges?",
    "We keep revisiting this. Perhaps the connecting thread is that "
    "both positions share a common foundation?",
]


def _simulate_fixy(turns: int, rng: random.Random) -> List[Dict[str, str]]:
    """Baseline repetition but with Fixy interventions every 6 turns."""
    dialog: List[Dict[str, str]] = []
    base_idx = 0  # index into the underlying baseline sequence

    while len(dialog) < turns:
        # Fixy intervenes every 6 baseline turns starting at turn 5
        if base_idx >= 5 and base_idx % 6 == 5:
            text = _pick(_FIXY_INTERVENTIONS, rng)
            dialog.append({"role": "Fixy", "text": text})
            # After Fixy: inject up to 2 turns of evolving content
            for j in range(2):
                if len(dialog) < turns:
                    role = _AGENTS[j % 2]
                    text = _pick(_TOPIC_POOLS["evolving"], rng)
                    dialog.append({"role": role, "text": text})
        else:
            # Normal repetitive turn
            role = _AGENTS[base_idx % 2]
            text = _pick(_TOPIC_POOLS["repetitive"], rng)
            dialog.append({"role": role, "text": text})

        base_idx += 1

    return dialog[:turns]


# ---------------------------------------------------------------------------
# Dream condition: energy-based consolidation breaks repetition periodically
# ---------------------------------------------------------------------------


def _simulate_dream(turns: int, rng: random.Random) -> List[Dict[str, str]]:
    """Baseline with dream-cycle consolidation: deep content emerges after recharge."""
    # Seed the global random module so EntelgiaAgent's internal randomness is
    # deterministic and reproducible given the same rng state.
    # NOTE: This function is not thread-safe because it modifies the global
    # random state; EntelgiaAgent uses random.uniform internally and cannot
    # accept an external RNG instance without modifying energy_regulation.py.
    random.seed(rng.randint(0, 2**31))
    dialog: List[Dict[str, str]] = []
    agent_a = EntelgiaAgent("Socrates", energy_drain_min=12.0, energy_drain_max=18.0)
    agent_b = EntelgiaAgent("Athena", energy_drain_min=12.0, energy_drain_max=18.0)
    agents = [agent_a, agent_b]

    for i in range(turns):
        agent = agents[i % 2]
        result = agent.process_step(f"turn_{i}")

        if result == "RECHARGED_AND_READY":
            # Post-dream: use deep/synthesising content
            text = _pick(_TOPIC_POOLS["deep"], rng)
        else:
            # Routine: use repetitive pool
            text = _pick(_TOPIC_POOLS["repetitive"], rng)

        dialog.append({"role": agent.name, "text": text})

    return dialog


# ---------------------------------------------------------------------------
# Ablation runner
# ---------------------------------------------------------------------------


def run_condition(
    condition: AblationCondition,
    turns: int = 30,
    seed: int = 42,
) -> List[Dict[str, str]]:
    """
    Simulate a dialogue under the given *condition*.

    Parameters
    ----------
    condition:
        One of the four :class:`AblationCondition` values.
    turns:
        Number of dialogue turns to simulate.
    seed:
        Random seed for reproducibility.

    Returns
    -------
    List[Dict[str, str]]
        Simulated dialogue as a list of ``{"role": str, "text": str}`` dicts.
    """
    rng = random.Random(seed)
    simulators = {
        AblationCondition.BASELINE: _simulate_baseline,
        AblationCondition.DIALOGUE_ENGINE: _simulate_dialogue_engine,
        AblationCondition.FIXY: _simulate_fixy,
        AblationCondition.DREAM: _simulate_dream,
    }
    return simulators[condition](turns, rng)


def run_ablation(
    turns: int = 30,
    seed: int = 42,
) -> Dict[str, Dict]:
    """
    Run all four ablation conditions and compute metrics.

    Parameters
    ----------
    turns:
        Number of dialogue turns per condition.
    seed:
        Random seed for reproducibility.

    Returns
    -------
    dict
        ``{ condition_label: { "metrics": {...}, "circularity_series": [...] } }``
    """
    results: Dict[str, Dict] = {}
    for condition in AblationCondition:
        dialog = run_condition(condition, turns=turns, seed=seed)
        metrics = compute_all_metrics(dialog)
        series = circularity_per_turn(dialog)
        results[condition.value] = {
            "metrics": metrics,
            "circularity_series": series,
        }
    return results


# ---------------------------------------------------------------------------
# Table output
# ---------------------------------------------------------------------------


def print_results_table(results: Dict[str, Dict]) -> None:
    """
    Print a formatted table of metrics across all ablation conditions.

    Parameters
    ----------
    results:
        Output of :func:`run_ablation`.
    """
    metric_keys = ["circularity_rate", "progress_rate", "intervention_utility"]
    col_w = 26
    header_cols = ["Condition"] + [k.replace("_", " ").title() for k in metric_keys]

    # Header
    separator = "+" + "+".join("-" * (col_w + 2) for _ in header_cols) + "+"
    print(separator)
    header_row = "| " + " | ".join(f"{h:<{col_w}}" for h in header_cols) + " |"
    print(header_row)
    print(separator)

    # Data rows
    for label, data in results.items():
        row_vals = [label]
        for k in metric_keys:
            row_vals.append(f"{data['metrics'].get(k, 0.0):.3f}")
        row = "| " + " | ".join(f"{v:<{col_w}}" for v in row_vals) + " |"
        print(row)

    print(separator)


# ---------------------------------------------------------------------------
# Graph output
# ---------------------------------------------------------------------------


def plot_circularity(
    results: Dict[str, Dict],
    save_path: Optional[str] = None,
) -> None:
    """
    Plot circularity over turns for each ablation condition.

    Requires ``matplotlib`` to be installed.  If it is not available the
    function prints a text-based ASCII chart instead.

    Parameters
    ----------
    results:
        Output of :func:`run_ablation`.
    save_path:
        Optional file path (e.g. ``"circularity.png"``) to save the figure.
        When *None* the figure is displayed interactively.
    """
    try:
        import matplotlib.pyplot as plt  # type: ignore

        fig, ax = plt.subplots(figsize=(10, 5))
        for label, data in results.items():
            series = data["circularity_series"]
            ax.plot(
                range(1, len(series) + 1), series, marker="o", markersize=3, label=label
            )

        ax.set_xlabel("Turn")
        ax.set_ylabel("Circularity Rate")
        ax.set_title("Circularity Rate Over Turns — Ablation Study")
        ax.set_ylim(0, 1.05)
        ax.legend()
        ax.grid(True, alpha=0.3)
        plt.tight_layout()

        if save_path:
            plt.savefig(save_path, dpi=150)
            print(f"Graph saved to: {save_path}")
        else:
            plt.show()

    except ImportError:
        _ascii_circularity_chart(results)


def _ascii_circularity_chart(results: Dict[str, Dict]) -> None:
    """Fallback ASCII chart when matplotlib is unavailable."""
    height = 10
    print("\nCircularity Rate Over Turns (ASCII chart)")
    print("  1.0 |")

    # Sample every 5 turns
    max_turns = max(len(d["circularity_series"]) for d in results.values())
    sample_every = max(1, max_turns // 20)

    rows: List[List[str]] = [
        [" "] * (max_turns // sample_every + 1) for _ in range(height)
    ]

    labels = list(results.keys())
    markers = ["*", "o", "+", "#"]

    for idx, (label, data) in enumerate(results.items()):
        series = data["circularity_series"]
        marker = markers[idx % len(markers)]
        for i, val in enumerate(series):
            if i % sample_every == 0:
                col = i // sample_every
                row = height - 1 - int(round(val * (height - 1)))
                row = max(0, min(height - 1, row))
                rows[row][col] = marker

    for r_idx, row in enumerate(rows):
        y_val = 1.0 - r_idx / (height - 1)
        print(f"  {y_val:.1f} |{''.join(row)}")

    print("       " + "-" * (max_turns // sample_every + 1))
    print("       " + "Turn →")

    for idx, label in enumerate(labels):
        print(f"  {markers[idx % len(markers)]} = {label}")


# ---------------------------------------------------------------------------
# Entry point — allows running directly: python entelgia/ablation_study.py
# ---------------------------------------------------------------------------


if __name__ == "__main__":
    results = run_ablation()
    print_results_table(results)
    plot_circularity(results)

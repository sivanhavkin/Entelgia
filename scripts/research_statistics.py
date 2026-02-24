#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Entelgia Research Statistics Script
=====================================
Examines all possible statistics factors that can be measured across the
Entelgia dialogue system and presents them in a comprehensive CMD table.

Measured Factors
----------------
Dialogue Quality Metrics (from entelgia.dialogue_metrics):
  circularity_rate      — Fraction of turn-pairs with high topic overlap.
  progress_rate         — Forward steps (topic shifts, synthesis, resolution) per turn.
  intervention_utility  — Avg circularity reduction after Fixy interventions.

Dialogue Characteristics:
  total_turns           — Total number of dialogue turns.
  avg_turn_length       — Average character length per turn.
  vocab_diversity       — Unique words / total words (type-token ratio).
  unique_speakers       — Number of distinct speakers in the dialogue.
  conflict_rate         — Fraction of turns containing conflict markers.
  depth_rate            — Fraction of turns containing depth/reasoning markers.
  synthesis_rate        — Fraction of turns containing synthesis/integration markers.
  fixy_interventions    — Number of Fixy turns.

Energy System Metrics (from entelgia.energy_regulation):
  avg_energy            — Average energy level across all agent steps.
  min_energy            — Minimum energy level reached.
  dream_cycle_count     — Number of dream cycles triggered.
  ltm_size              — Long-term memory entries after all turns.
  conscious_mem_size    — Conscious memory entries after all turns.

Conditions simulate the four ablation conditions from the ablation study so
that results are directly comparable.
"""

from __future__ import annotations

import os
import random
import re
import sys
from enum import Enum
from typing import Dict, List, Tuple

# ---------------------------------------------------------------------------
# Path setup — allows running as `python scripts/research_statistics.py`
# from the project root without installing the package.
# ---------------------------------------------------------------------------

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_SCRIPT_DIR)
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from entelgia.dialogue_metrics import (  # noqa: E402
    circularity_rate,
    compute_all_metrics,
    intervention_utility,
    progress_rate,
)
from entelgia.energy_regulation import EntelgiaAgent  # noqa: E402

# ---------------------------------------------------------------------------
# Condition enum (mirrors AblationCondition in ablation_study.py)
# ---------------------------------------------------------------------------


class ResearchCondition(Enum):
    """Four experimental conditions for the research statistics study."""

    BASELINE = "Baseline"
    DIALOGUE_ENGINE = "DialogueEngine/Seed"
    FIXY = "Fixy Interventions"
    DREAM = "Dream/Energy"


# ---------------------------------------------------------------------------
# Shared topic pools (identical to ablation_study.py for comparability)
# ---------------------------------------------------------------------------

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
# Dialogue simulators (identical logic to ablation_study.py)
# ---------------------------------------------------------------------------

_FIXY_INTERVENTIONS = [
    "I notice we have circled back to the same point. Let us reframe: "
    "how does embodiment change the picture?",
    "The dialogue seems to bridge the same ground. "
    "Integrating both views, what synthesis emerges?",
    "We keep revisiting this. Perhaps the connecting thread is that "
    "both positions share a common foundation?",
]


def _simulate_baseline(turns: int, rng: random.Random) -> List[Dict[str, str]]:
    dialog: List[Dict[str, str]] = []
    for i in range(turns):
        role = _AGENTS[i % 2]
        text = _pick(_TOPIC_POOLS["repetitive"], rng)
        dialog.append({"role": role, "text": text})
    return dialog


def _simulate_dialogue_engine(turns: int, rng: random.Random) -> List[Dict[str, str]]:
    dialog: List[Dict[str, str]] = []
    pool = _TOPIC_POOLS["evolving"]
    for i in range(turns):
        role = _AGENTS[i % 2] if i < 4 else rng.choice(_AGENTS)
        text = pool[i % len(pool)]
        dialog.append({"role": role, "text": text})
    return dialog


def _simulate_fixy(turns: int, rng: random.Random) -> List[Dict[str, str]]:
    dialog: List[Dict[str, str]] = []
    base_idx = 0

    while len(dialog) < turns:
        if base_idx >= 5 and base_idx % 6 == 5:
            text = _pick(_FIXY_INTERVENTIONS, rng)
            dialog.append({"role": "Fixy", "text": text})
            for j in range(2):
                if len(dialog) < turns:
                    role = _AGENTS[j % 2]
                    text = _pick(_TOPIC_POOLS["evolving"], rng)
                    dialog.append({"role": role, "text": text})
        else:
            role = _AGENTS[base_idx % 2]
            text = _pick(_TOPIC_POOLS["repetitive"], rng)
            dialog.append({"role": role, "text": text})
        base_idx += 1

    return dialog[:turns]


def _simulate_dream(turns: int, rng: random.Random) -> List[Dict[str, str]]:
    # NOTE: EntelgiaAgent uses random.uniform internally and cannot accept an
    # external RNG instance.  Seeding the global random module from rng keeps
    # results deterministic and reproducible given the same seed parameter.
    random.seed(rng.randint(0, 2**31))
    dialog: List[Dict[str, str]] = []
    agent_a = EntelgiaAgent("Socrates", energy_drain_min=12.0, energy_drain_max=18.0)
    agent_b = EntelgiaAgent("Athena", energy_drain_min=12.0, energy_drain_max=18.0)
    agents = [agent_a, agent_b]

    for i in range(turns):
        agent = agents[i % 2]
        result = agent.process_step(f"turn_{i}")
        if result == "RECHARGED_AND_READY":
            text = _pick(_TOPIC_POOLS["deep"], rng)
        else:
            text = _pick(_TOPIC_POOLS["repetitive"], rng)
        dialog.append({"role": agent.name, "text": text})

    return dialog


def simulate_condition(
    condition: ResearchCondition,
    turns: int = 30,
    seed: int = 42,
) -> List[Dict[str, str]]:
    """Return a synthetic dialogue for the given condition."""
    rng = random.Random(seed)
    simulators = {
        ResearchCondition.BASELINE: _simulate_baseline,
        ResearchCondition.DIALOGUE_ENGINE: _simulate_dialogue_engine,
        ResearchCondition.FIXY: _simulate_fixy,
        ResearchCondition.DREAM: _simulate_dream,
    }
    return simulators[condition](turns, rng)


# ---------------------------------------------------------------------------
# Marker sets for dialogue-characteristic metrics
# ---------------------------------------------------------------------------

_CONFLICT_MARKERS = frozenset(
    [
        "no",
        "but",
        "disagree",
        "however",
        "wrong",
        "incorrect",
        "actually",
        "contrary",
        "opposite",
        "mistake",
        "error",
    ]
)
_DEPTH_MARKERS = frozenset(
    [
        "why",
        "because",
        "how",
        "reason",
        "therefore",
        "implies",
        "consequence",
        "deeper",
        "fundamental",
        "underlying",
        "depth",
        "foundation",
        "implication",
    ]
)
_SYNTHESIS_MARKERS = frozenset(
    [
        "therefore",
        "integrating",
        "combining",
        "synthesis",
        "synthesize",
        "connect",
        "connecting",
        "both",
        "together",
        "unified",
        "merging",
        "bridge",
        "converge",
        "overall",
    ]
)


def _marker_rate(dialog: List[Dict[str, str]], markers: frozenset) -> float:
    """Fraction of turns whose text contains at least one marker word."""
    if not dialog:
        return 0.0
    hits = sum(
        1
        for t in dialog
        if markers & set(re.findall(r"\b\w+\b", t.get("text", "").lower()))
    )
    return hits / len(dialog)


# ---------------------------------------------------------------------------
# Energy-system statistics collector
# ---------------------------------------------------------------------------


def _energy_stats(
    turns: int,
    seed: int = 42,
    drain_min: float = EntelgiaAgent.ENERGY_DRAIN_MIN,
    drain_max: float = EntelgiaAgent.ENERGY_DRAIN_MAX,
) -> Dict[str, float]:
    """
    Simulate an energy-tracking run and collect energy-system statistics.

    Parameters
    ----------
    turns:
        Number of dialogue turns to simulate.
    seed:
        Random seed for reproducibility.
    drain_min, drain_max:
        Energy drain range per step (varies by condition).

    Returns a dict with avg_energy, min_energy, dream_cycle_count,
    ltm_size, and conscious_mem_size.
    """
    rng = random.Random(seed)
    # NOTE: EntelgiaAgent uses random.uniform internally; seed the global
    # random module from rng to keep the simulation deterministic and
    # reproducible given the same seed parameter.
    random.seed(rng.randint(0, 2**31))

    agent_a = EntelgiaAgent(
        "Socrates", energy_drain_min=drain_min, energy_drain_max=drain_max
    )
    agent_b = EntelgiaAgent(
        "Athena", energy_drain_min=drain_min, energy_drain_max=drain_max
    )
    agents = [agent_a, agent_b]

    energy_readings: List[float] = []
    dream_cycles = 0

    for i in range(turns):
        agent = agents[i % 2]
        result = agent.process_step(f"turn_{i}")
        energy_readings.append(agent.energy_level)
        if result == "RECHARGED_AND_READY":
            dream_cycles += 1

    avg_e = sum(energy_readings) / len(energy_readings) if energy_readings else 0.0
    min_e = min(energy_readings) if energy_readings else 0.0
    ltm = len(agent_a.long_term_memory) + len(agent_b.long_term_memory)
    cmem = len(agent_a.conscious_memory) + len(agent_b.conscious_memory)

    return {
        "avg_energy": avg_e,
        "min_energy": min_e,
        "dream_cycle_count": float(dream_cycles),
        "ltm_size": float(ltm),
        "conscious_mem_size": float(cmem),
    }


# Energy-drain parameters per condition
_CONDITION_DRAIN: Dict[str, Tuple[float, float]] = {
    ResearchCondition.BASELINE.value: (
        EntelgiaAgent.ENERGY_DRAIN_MIN,
        EntelgiaAgent.ENERGY_DRAIN_MAX,
    ),
    ResearchCondition.DIALOGUE_ENGINE.value: (
        EntelgiaAgent.ENERGY_DRAIN_MIN,
        EntelgiaAgent.ENERGY_DRAIN_MAX,
    ),
    ResearchCondition.FIXY.value: (
        EntelgiaAgent.ENERGY_DRAIN_MIN,
        EntelgiaAgent.ENERGY_DRAIN_MAX,
    ),
    ResearchCondition.DREAM.value: (12.0, 18.0),  # higher drain for Dream condition
}


# ---------------------------------------------------------------------------
# Full statistics computation
# ---------------------------------------------------------------------------


def compute_all_statistics(
    dialog: List[Dict[str, str]],
    energy_stats: Dict[str, float],
) -> Dict[str, float]:
    """
    Compute every measurable statistic for a dialogue.

    Parameters
    ----------
    dialog:
        Simulated dialogue turns.
    energy_stats:
        Pre-computed energy-system statistics dict.

    Returns
    -------
    dict
        All statistics as float values.
    """
    # --- Core dialogue metrics ---
    base = compute_all_metrics(dialog)

    # --- Dialogue characteristics ---
    total_turns = float(len(dialog))
    texts = [t.get("text", "") for t in dialog]
    total_chars = sum(len(tx) for tx in texts)
    avg_turn_length = total_chars / total_turns if total_turns else 0.0

    all_words = re.findall(r"\b[a-z]+\b", " ".join(texts).lower())
    vocab_diversity = len(set(all_words)) / len(all_words) if all_words else 0.0

    unique_speakers = float(len({t.get("role", "") for t in dialog}))
    fixy_interventions = float(sum(1 for t in dialog if t.get("role") == "Fixy"))

    conflict_rate = _marker_rate(dialog, _CONFLICT_MARKERS)
    depth_rate = _marker_rate(dialog, _DEPTH_MARKERS)
    synthesis_rate = _marker_rate(dialog, _SYNTHESIS_MARKERS)

    return {
        # Core metrics
        "circularity_rate": base["circularity_rate"],
        "progress_rate": base["progress_rate"],
        "intervention_utility": base["intervention_utility"],
        # Dialogue characteristics
        "total_turns": total_turns,
        "avg_turn_length": avg_turn_length,
        "vocab_diversity": vocab_diversity,
        "unique_speakers": unique_speakers,
        "fixy_interventions": fixy_interventions,
        "conflict_rate": conflict_rate,
        "depth_rate": depth_rate,
        "synthesis_rate": synthesis_rate,
        # Energy system
        "avg_energy": energy_stats["avg_energy"],
        "min_energy": energy_stats["min_energy"],
        "dream_cycle_count": energy_stats["dream_cycle_count"],
        "ltm_size": energy_stats["ltm_size"],
        "conscious_mem_size": energy_stats["conscious_mem_size"],
    }


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------


def run_research(
    turns: int = 30,
    seed: int = 42,
) -> Dict[str, Dict[str, float]]:
    """
    Run all four conditions and return full statistics for each.

    Energy-system metrics are computed independently per condition using
    the drain parameters appropriate for that condition.

    Returns
    -------
    dict
        ``{ condition_label: { stat_name: float, ... } }``
    """
    results: Dict[str, Dict[str, float]] = {}
    for condition in ResearchCondition:
        dialog = simulate_condition(condition, turns=turns, seed=seed)
        drain_min, drain_max = _CONDITION_DRAIN[condition.value]
        e_stats = _energy_stats(turns, seed, drain_min=drain_min, drain_max=drain_max)
        stats = compute_all_statistics(dialog, e_stats)
        results[condition.value] = stats
    return results


# ---------------------------------------------------------------------------
# Table printer
# ---------------------------------------------------------------------------

# Human-readable labels and format spec for each statistic
_STAT_META: List[Tuple[str, str, str]] = [
    # (key, display_label, format_spec)
    # ── Core Dialogue Metrics ──────────────────────────────────────────────
    ("circularity_rate", "Circularity Rate", ".3f"),
    ("progress_rate", "Progress Rate", ".3f"),
    ("intervention_utility", "Intervention Utility", ".3f"),
    # ── Dialogue Characteristics ───────────────────────────────────────────
    ("total_turns", "Total Turns", ".0f"),
    ("avg_turn_length", "Avg Turn Length (chars)", ".1f"),
    ("vocab_diversity", "Vocab Diversity (TTR)", ".3f"),
    ("unique_speakers", "Unique Speakers", ".0f"),
    ("fixy_interventions", "Fixy Interventions", ".0f"),
    ("conflict_rate", "Conflict Rate", ".3f"),
    ("depth_rate", "Depth Rate", ".3f"),
    ("synthesis_rate", "Synthesis Rate", ".3f"),
    # ── Energy-System Metrics ──────────────────────────────────────────────
    ("avg_energy", "Avg Energy (%)", ".1f"),
    ("min_energy", "Min Energy (%)", ".1f"),
    ("dream_cycle_count", "Dream Cycles", ".0f"),
    ("ltm_size", "LTM Size (entries)", ".0f"),
    ("conscious_mem_size", "Conscious Mem (entries)", ".0f"),
]

# Section divider rows: (insert_before_key, section_title)
_SECTION_HEADERS: Dict[str, str] = {
    "circularity_rate": "CORE DIALOGUE METRICS",
    "total_turns": "DIALOGUE CHARACTERISTICS",
    "avg_energy": "ENERGY-SYSTEM METRICS",
}


def print_statistics_table(results: Dict[str, Dict[str, float]]) -> None:
    """
    Print a full-width statistics table with all measurable factors.

    Parameters
    ----------
    results:
        Output of :func:`run_research`.
    """
    conditions = list(results.keys())
    stat_col_w = 28  # width of the Statistic column
    val_col_w = 24  # width of each condition-value column

    all_cols = ["Statistic"] + conditions
    col_widths = [stat_col_w] + [val_col_w] * len(conditions)

    def separator() -> str:
        return "+" + "+".join("-" * (w + 2) for w in col_widths) + "+"

    def header_row() -> str:
        cells = [f"{h:<{col_widths[i]}}" for i, h in enumerate(all_cols)]
        return "| " + " | ".join(cells) + " |"

    def section_row(title: str) -> str:
        total_inner = sum(col_widths) + (len(col_widths) - 1) * 3
        label = f"  {title}  "
        padded = label.center(total_inner)
        return "|" + padded + "|"

    def data_row(label: str, values: List[str]) -> str:
        cells = [f"{label:<{stat_col_w}}"] + [f"{v:<{val_col_w}}" for v in values]
        return "| " + " | ".join(cells) + " |"

    sep = separator()
    print("\n" + sep)
    print(header_row())
    print(sep)

    for key, display_label, fmt in _STAT_META:
        if key in _SECTION_HEADERS:
            print(section_row(_SECTION_HEADERS[key]))
            print(sep)

        values = [format(results[c].get(key, 0.0), fmt) for c in conditions]
        print(data_row(display_label, values))

    print(sep)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> None:
    print("\n" + "=" * 80)
    print("ENTELGIA — Research Statistics: All Measurable Factors")
    print("  Simulates four dialogue conditions and reports every available metric.")
    print("=" * 80)

    results = run_research()
    print_statistics_table(results)

    print("\nLegend")
    print("  Circularity Rate      : fraction of turn-pairs with ≥50% keyword overlap")
    print(
        "  Progress Rate         : forward steps (topic shift / synthesis / resolution) per turn"
    )
    print(
        "  Intervention Utility  : avg circularity reduction after Fixy interventions"
    )
    print("  Vocab Diversity (TTR) : unique words / total words (type-token ratio)")
    print("  Conflict Rate         : fraction of turns with conflict markers")
    print("  Depth Rate            : fraction of turns with depth/reasoning markers")
    print(
        "  Synthesis Rate        : fraction of turns with synthesis/integration markers"
    )
    print(
        "  Avg/Min Energy        : agent energy level (%) — Dream condition only varies"
    )
    print("  Dream Cycles          : number of energy-recharge cycles triggered")
    print("  LTM Size              : long-term memory entries after all turns")
    print("  Conscious Mem         : conscious memory entries after all turns\n")


if __name__ == "__main__":
    main()

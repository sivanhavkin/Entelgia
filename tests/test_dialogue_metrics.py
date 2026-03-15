#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Tests for entelgia/dialogue_metrics.py and entelgia/ablation_study.py.

Covers:
  - circularity_rate: identical, distinct, and mixed dialogues
  - circularity_per_turn: series length and monotonicity edge cases
  - progress_rate: topic shifts, synthesis markers, question resolution
  - intervention_utility: Fixy absent, Fixy present, improvement vs. degradation
  - compute_all_metrics: keys present and values in expected range
  - AblationCondition enum values
  - run_condition: returns correct number of turns for each condition
  - run_ablation: structure, reproducibility, and condition ordering
  - print_results_table: smoke-test (no crash, expected columns present)
  - plot_circularity: ASCII fallback smoke-test
"""

import sys
import os
import io
from contextlib import redirect_stdout
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

from entelgia.dialogue_metrics import (
    circularity_rate,
    circularity_per_turn,
    progress_rate,
    intervention_utility,
    compute_all_metrics,
    _keywords,
    _jaccard,
)
from entelgia.ablation_study import (
    AblationCondition,
    run_condition,
    run_ablation,
    print_results_table,
    plot_circularity,
    _ascii_circularity_chart,
)

# ---------------------------------------------------------------------------
# Helper factories
# ---------------------------------------------------------------------------


def _make_dialog(texts, roles=None):
    """Build a dialogue list from a list of text strings."""
    if roles is None:
        cycle = ["Socrates", "Athena"]
        roles = [cycle[i % 2] for i in range(len(texts))]
    return [{"role": r, "text": t} for r, t in zip(roles, texts)]


# ---------------------------------------------------------------------------
# Terminal display helpers – tables and ASCII bar charts
# ---------------------------------------------------------------------------


def _print_table(headers, rows, title=None):
    """Print a neatly formatted ASCII table to stdout."""
    if title:
        print(f"\n  ╔{'═' * (len(title) + 4)}╗")
        print(f"  ║  {title}  ║")
        print(f"  ╚{'═' * (len(title) + 4)}╝")
    col_widths = [len(str(h)) for h in headers]
    for row in rows:
        for i, cell in enumerate(row):
            col_widths[i] = max(col_widths[i], len(str(cell)))
    sep = "─┼─".join("─" * w for w in col_widths)
    header_line = " │ ".join(str(h).ljust(col_widths[i]) for i, h in enumerate(headers))
    print(f"  {header_line}")
    print(f"  {sep}")
    for row in rows:
        print(
            "  "
            + " │ ".join(str(cell).ljust(col_widths[i]) for i, cell in enumerate(row))
        )
    print()


def _print_bar_chart(data_pairs, title=None, max_width=36):
    """Print a horizontal ASCII bar chart.  *data_pairs* is [(label, value), ...]."""
    if title:
        print(f"\n  📊 {title}")
        print(f"  {'─' * 52}")
    if not data_pairs:
        return
    max_val = max(v for _, v in data_pairs) or 1.0
    for label, value in data_pairs:
        bar_len = max(1, int(round((value / max_val) * max_width)))
        bar = "█" * bar_len
        print(f"  {str(label):>10} │ {bar:<{max_width}} {value:.4f}")
    print()


# ---------------------------------------------------------------------------
# _keywords helper
# ---------------------------------------------------------------------------


class TestKeywords:
    def test_only_long_words(self):
        kw = _keywords("hi the consciousness emerges")
        _print_table(
            ["Word", "In keywords?", "Expected"],
            [
                ["consciousness", str("consciousness" in kw), "True"],
                ["emerges", str("emerges" in kw), "True"],
                ["the", str("the" in kw), "False"],
                ["hi", str("hi" in kw), "False"],
            ],
            title="test_only_long_words",
        )
        assert "consciousness" in kw
        assert "emerges" in kw
        # short words excluded
        assert "the" not in kw
        assert "hi" not in kw

    def test_lowercases(self):
        kw = _keywords("Consciousness EMERGES")
        _print_table(
            ["Word", "In keywords?", "Expected"],
            [
                ["consciousness", str("consciousness" in kw), "True"],
                ["emerges", str("emerges" in kw), "True"],
            ],
            title="test_lowercases",
        )
        assert "consciousness" in kw
        assert "emerges" in kw


# ---------------------------------------------------------------------------
# _jaccard helper
# ---------------------------------------------------------------------------


class TestJaccard:
    def test_identical_sets(self):
        a = frozenset(["consciousness", "emerges"])
        result = _jaccard(a, a)
        _print_table(
            ["Set A", "Set B", "Jaccard", "Expected"],
            [[str(set(a)), str(set(a)), f"{result:.4f}", "1.0000"]],
            title="test_identical_sets",
        )
        assert result == pytest.approx(1.0)

    def test_disjoint_sets(self):
        a = frozenset(["consciousness"])
        b = frozenset(["freedom"])
        result = _jaccard(a, b)
        _print_table(
            ["Set A", "Set B", "Jaccard", "Expected"],
            [[str(set(a)), str(set(b)), f"{result:.4f}", "0.0000"]],
            title="test_disjoint_sets",
        )
        assert result == pytest.approx(0.0)

    def test_partial_overlap(self):
        a = frozenset(["consciousness", "emerges", "complex"])
        b = frozenset(["consciousness", "emerges", "freedom"])
        result = _jaccard(a, b)
        intersection = len(a & b)
        union = len(a | b)
        _print_table(
            ["Set A", "Set B", "Intersection", "Union", "Jaccard", "Expected"],
            [
                [
                    str(sorted(a)),
                    str(sorted(b)),
                    str(intersection),
                    str(union),
                    f"{result:.4f}",
                    f"{intersection/union:.4f}",
                ]
            ],
            title="test_partial_overlap",
        )
        # intersection=2, union=4
        assert result == pytest.approx(2 / 4)

    def test_empty_sets(self):
        result = _jaccard(frozenset(), frozenset())
        _print_table(
            ["Set A", "Set B", "Jaccard", "Expected"],
            [["(empty)", "(empty)", f"{result:.4f}", "0.0000"]],
            title="test_empty_sets",
        )
        assert result == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# circularity_rate
# ---------------------------------------------------------------------------


class TestCircularityRate:
    def test_empty_dialog(self):
        result = circularity_rate([])
        _print_table(
            ["Input", "circularity_rate", "Expected"],
            [["(empty dialog)", f"{result:.4f}", "0.0000"]],
            title="test_empty_dialog (circularity_rate)",
        )
        assert circularity_rate([]) == pytest.approx(0.0)

    def test_single_turn(self):
        d = _make_dialog(["consciousness emerges from complex systems"])
        result = circularity_rate(d)
        _print_table(
            ["Turns", "Text (truncated)", "circularity_rate", "Expected"],
            [["1", d[0]["text"][:40], f"{result:.4f}", "0.0000"]],
            title="test_single_turn (circularity_rate)",
        )
        assert result == pytest.approx(0.0)

    def test_identical_turns_high_circularity(self):
        text = "consciousness emerges from complex information processing systems"
        d = _make_dialog([text] * 6)
        rate = circularity_rate(d)
        _print_table(
            ["Turns", "Text (truncated)", "circularity_rate", "Threshold", "Pass?"],
            [
                [
                    "6 (identical)",
                    text[:40] + "...",
                    f"{rate:.4f}",
                    ">= 0.8",
                    "✓" if rate >= 0.8 else "✗",
                ]
            ],
            title="test_identical_turns_high_circularity",
        )
        assert rate >= 0.8, f"Expected high circularity, got {rate}"

    def test_completely_distinct_turns_low_circularity(self):
        texts = [
            "consciousness emerges from complex information processing",
            "democracy requires freedom participation equality justice",
            "mathematics underpins physics through elegant formalism",
            "literature reveals hidden depths human experience narrative",
        ]
        d = _make_dialog(texts)
        rate = circularity_rate(d)
        _print_table(
            ["Turn", "Text (truncated)", "circularity_rate", "Threshold", "Pass?"],
            [
                [
                    str(i + 1),
                    t[:40] + "...",
                    f"{rate:.4f}" if i == 0 else "",
                    "< 0.4" if i == 0 else "",
                    "✓" if rate < 0.4 else "✗" if i == 0 else "",
                ]
                for i, t in enumerate(texts)
            ],
            title="test_completely_distinct_turns_low_circularity",
        )
        assert rate < 0.4, f"Expected low circularity, got {rate}"

    def test_custom_threshold(self):
        text = "consciousness emerges from complex information"
        d = _make_dialog([text] * 4)
        rate_05 = circularity_rate(d, threshold=0.5)
        rate_99 = circularity_rate(d, threshold=0.99)
        _print_table(
            ["Threshold", "circularity_rate", "Pass?"],
            [
                ["0.5", f"{rate_05:.4f}", "✓" if rate_05 >= 0.8 else "✗"],
                ["0.99", f"{rate_99:.4f}", "✓" if rate_99 >= 0.8 else "✗"],
            ],
            title="test_custom_threshold",
        )
        # Should be circular at 0.5 threshold
        assert circularity_rate(d, threshold=0.5) >= 0.8
        # Even at very tight threshold (0.99) all-identical turns stay circular
        assert circularity_rate(d, threshold=0.99) >= 0.8

    def test_result_in_range(self):
        texts = [
            "consciousness emerges from complex information processing",
            "consciousness emerges from complex information processing",
            "democracy freedom justice equality participation society",
        ]
        d = _make_dialog(texts)
        rate = circularity_rate(d)
        _print_table(
            ["Turns", "circularity_rate", "Range", "Pass?"],
            [
                [
                    "3 (2 identical + 1 distinct)",
                    f"{rate:.4f}",
                    "[0.0, 1.0]",
                    "✓" if 0.0 <= rate <= 1.0 else "✗",
                ]
            ],
            title="test_result_in_range (circularity_rate)",
        )
        assert 0.0 <= rate <= 1.0


# ---------------------------------------------------------------------------
# circularity_per_turn
# ---------------------------------------------------------------------------


class TestCircularityPerTurn:
    def test_series_length_equals_dialog_length(self):
        texts = ["consciousness emerges"] * 10
        d = _make_dialog(texts)
        series = circularity_per_turn(d)
        _print_table(
            ["Turn", "circularity_per_turn"],
            [[str(i + 1), f"{v:.4f}"] for i, v in enumerate(series)],
            title="test_series_length_equals_dialog_length",
        )
        assert len(series) == len(d)

    def test_empty_dialog(self):
        result = circularity_per_turn([])
        _print_table(
            ["Input", "Result", "Expected"],
            [["(empty)", str(result), "[]"]],
            title="test_empty_dialog (circularity_per_turn)",
        )
        assert result == []

    def test_first_turn_is_zero(self):
        d = _make_dialog(["consciousness emerges from complex information"])
        series = circularity_per_turn(d)
        _print_table(
            ["Turn", "circularity_per_turn", "Expected"],
            [["1", f"{series[0]:.4f}", "0.0000"]],
            title="test_first_turn_is_zero",
        )
        assert series[0] == pytest.approx(0.0)

    def test_values_in_range(self):
        texts = ["consciousness emerges"] * 8
        d = _make_dialog(texts)
        series = circularity_per_turn(d)
        _print_table(
            ["Turn", "Value", "In [0,1]?"],
            [
                [str(i + 1), f"{v:.4f}", "✓" if 0.0 <= v <= 1.0 else "✗"]
                for i, v in enumerate(series)
            ],
            title="test_values_in_range (circularity_per_turn)",
        )
        for v in series:
            assert 0.0 <= v <= 1.0


# ---------------------------------------------------------------------------
# progress_rate
# ---------------------------------------------------------------------------


class TestProgressRate:
    def test_empty_or_single_turn(self):
        r_empty = progress_rate([])
        d = _make_dialog(["consciousness emerges"])
        r_single = progress_rate(d)
        _print_table(
            ["Input", "progress_rate", "Expected"],
            [
                ["(empty)", f"{r_empty:.4f}", "0.0000"],
                ["(single turn)", f"{r_single:.4f}", "0.0000"],
            ],
            title="test_empty_or_single_turn (progress_rate)",
        )
        assert progress_rate([]) == pytest.approx(0.0)
        assert r_single == pytest.approx(0.0)

    def test_synthesis_marker_increases_progress(self):
        texts = [
            "consciousness emerges from complex information processing",
            "therefore integrating both views reveals a unified framework",
        ]
        d = _make_dialog(texts)
        rate = progress_rate(d)
        _print_table(
            ["Turn", "Text (truncated)", "progress_rate", "Pass?"],
            [
                ["1", texts[0][:45] + "...", "", ""],
                [
                    "2 (synthesis)",
                    texts[1][:45] + "...",
                    f"{rate:.4f}",
                    "✓" if rate > 0.0 else "✗",
                ],
            ],
            title="test_synthesis_marker_increases_progress",
        )
        assert rate > 0.0

    def test_topic_shift_counts_as_progress(self):
        texts = [
            "consciousness emerges from complex information processing systems",
            "democracy freedom justice equality participation requires balance",
        ]
        d = _make_dialog(texts)
        rate = progress_rate(d)
        _print_table(
            ["Turn", "Text (truncated)", "progress_rate", "Pass?"],
            [
                ["1", texts[0][:40] + "...", "", ""],
                [
                    "2 (topic shift)",
                    texts[1][:40] + "...",
                    f"{rate:.4f}",
                    "✓" if rate > 0.0 else "✗",
                ],
            ],
            title="test_topic_shift_counts_as_progress",
        )
        assert rate > 0.0

    def test_question_resolution(self):
        texts = [
            "what is the nature of consciousness and why does it arise?",
            "because neural correlates explain the binding problem solution",
        ]
        d = _make_dialog(texts)
        rate = progress_rate(d)
        _print_table(
            ["Turn", "Text (truncated)", "progress_rate", "Pass?"],
            [
                ["1 (question)", texts[0][:45] + "...", "", ""],
                [
                    "2 (answer)",
                    texts[1][:45] + "...",
                    f"{rate:.4f}",
                    "✓" if rate > 0.0 else "✗",
                ],
            ],
            title="test_question_resolution",
        )
        assert rate > 0.0

    def test_repetitive_dialog_low_progress(self):
        text = "consciousness emerges from complex information processing"
        d = _make_dialog([text] * 8)
        rate = progress_rate(d)
        _print_table(
            ["Turns", "Text (truncated)", "progress_rate", "Expected"],
            [["8 (identical)", text[:40] + "...", f"{rate:.4f}", "0.0000"]],
            title="test_repetitive_dialog_low_progress",
        )
        assert rate == pytest.approx(0.0)

    def test_result_in_range(self):
        texts = [
            "consciousness emerges from complex information processing systems",
            "therefore integrating both views reveals a unified bridge framework",
            "democracy freedom justice equality participation society requires",
            "mathematics physics formalism elegant theories explain universe",
        ]
        d = _make_dialog(texts)
        rate = progress_rate(d)
        _print_table(
            ["Turns", "progress_rate", "Range", "Pass?"],
            [
                [
                    "4 (diverse)",
                    f"{rate:.4f}",
                    "[0.0, 1.0]",
                    "✓" if 0.0 <= rate <= 1.0 else "✗",
                ]
            ],
            title="test_result_in_range (progress_rate)",
        )
        assert 0.0 <= rate <= 1.0


# ---------------------------------------------------------------------------
# intervention_utility
# ---------------------------------------------------------------------------


class TestInterventionUtility:
    def test_no_fixy_turns(self):
        texts = ["consciousness emerges"] * 10
        d = _make_dialog(texts)
        result = intervention_utility(d)
        _print_table(
            ["Scenario", "Fixy turns?", "intervention_utility", "Expected"],
            [["10 identical turns", "No", f"{result:.4f}", "0.0000"]],
            title="test_no_fixy_turns",
        )
        assert result == pytest.approx(0.0)

    def test_fixy_reduces_circularity(self):
        # Before Fixy: repetitive; after Fixy: diverse
        repetitive = "consciousness emerges from complex information processing"
        diverse = [
            "democracy freedom justice participation society balance equality",
            "mathematics physics formalism theories explain universe natural",
            "language shapes thought structures meaning narrative identity self",
            "neuroscience biology evolution adaptation survival reproduction",
        ]
        turns_before = [{"role": "Socrates", "text": repetitive}] * 5
        fixy_turn = [
            {"role": "Fixy", "text": "Let us reframe and integrate diverse views"}
        ]
        turns_after = [{"role": "Athena", "text": t} for t in diverse] + [
            {
                "role": "Socrates",
                "text": "freedom justice democracy social contract theory",
            }
        ]
        dialog = turns_before + fixy_turn + turns_after
        utility = intervention_utility(dialog, window=5)
        _print_table(
            ["Scenario", "Turns before", "Fixy?", "Turns after", "utility", "Pass?"],
            [
                [
                    "repetitive→diverse",
                    "5",
                    "Yes",
                    str(len(turns_after)),
                    f"{utility:.4f}",
                    "✓" if utility > 0.0 else "✗",
                ]
            ],
            title="test_fixy_reduces_circularity",
        )
        assert utility > 0.0, f"Expected positive utility, got {utility}"

    def test_multiple_fixy_turns(self):
        repetitive = "consciousness emerges from complex information processing"
        diverse = "democracy freedom justice participation equality society"
        dialog = []
        for i in range(20):
            if i in (6, 13):
                dialog.append(
                    {"role": "Fixy", "text": "Let us reframe and bridge perspectives"}
                )
            elif i > 6:
                dialog.append(
                    {"role": _make_dialog([diverse])[0]["role"], "text": diverse}
                )
            else:
                dialog.append({"role": "Socrates", "text": repetitive})
        utility = intervention_utility(dialog, window=4)
        _print_table(
            ["Scenario", "Total turns", "Fixy at turns", "utility", "Is float?"],
            [
                [
                    "2 Fixy interventions",
                    "20",
                    "7, 14",
                    f"{utility:.4f}",
                    str(isinstance(utility, float)),
                ]
            ],
            title="test_multiple_fixy_turns",
        )
        # Should return a float (sign depends on simulation)
        assert isinstance(utility, float)

    def test_result_is_float(self):
        d = _make_dialog(["consciousness emerges"] * 10)
        d[4]["role"] = "Fixy"
        result = intervention_utility(d)
        _print_table(
            ["Scenario", "intervention_utility", "Is float?"],
            [
                [
                    "10 turns, 1 Fixy at pos 4",
                    f"{result:.4f}",
                    str(isinstance(result, float)),
                ]
            ],
            title="test_result_is_float",
        )
        assert isinstance(result, float)


# ---------------------------------------------------------------------------
# compute_all_metrics
# ---------------------------------------------------------------------------


class TestComputeAllMetrics:
    def test_keys_present(self):
        d = _make_dialog(["consciousness emerges from complex"] * 5)
        metrics = compute_all_metrics(d)
        _print_table(
            ["Key", "Present?", "Expected"],
            [
                [k, str(k in metrics), "True"]
                for k in ["circularity_rate", "progress_rate", "intervention_utility"]
            ],
            title="test_keys_present",
        )
        assert set(metrics.keys()) == {
            "circularity_rate",
            "progress_rate",
            "intervention_utility",
        }

    def test_values_are_floats_in_range(self):
        texts = [
            "consciousness emerges from complex information processing systems",
            "therefore integrating views reveals bridge unified framework foundation",
            "democracy freedom justice equality participation society requires balance",
        ]
        d = _make_dialog(texts)
        metrics = compute_all_metrics(d)
        _print_table(
            ["Metric", "Value", "Is float?", "In [-1.0, 1.0]?"],
            [
                [
                    k,
                    f"{v:.4f}",
                    str(isinstance(v, float)),
                    "✓" if -1.0 <= v <= 1.0 else "✗",
                ]
                for k, v in metrics.items()
            ],
            title="test_values_are_floats_in_range",
        )
        for k, v in metrics.items():
            assert isinstance(v, float), f"{k} is not float"
            assert -1.0 <= v <= 1.0, f"{k}={v} out of range"


# ---------------------------------------------------------------------------
# AblationCondition enum
# ---------------------------------------------------------------------------


class TestAblationCondition:
    def test_all_four_conditions_defined(self):
        conditions = set(c.value for c in AblationCondition)
        _print_table(
            ["Condition value", "Present?"],
            [
                ["Baseline", str("Baseline" in conditions)],
                ["DialogueEngine/Seed", str("DialogueEngine/Seed" in conditions)],
                ["Fixy Interventions", str("Fixy Interventions" in conditions)],
                ["Dream/Energy", str("Dream/Energy" in conditions)],
            ],
            title="test_all_four_conditions_defined",
        )
        assert "Baseline" in conditions
        assert "DialogueEngine/Seed" in conditions
        assert "Fixy Interventions" in conditions
        assert "Dream/Energy" in conditions

    def test_enum_has_four_members(self):
        count = len(AblationCondition)
        _print_table(
            ["Enum member count", "Expected"],
            [[str(count), "4"]],
            title="test_enum_has_four_members",
        )
        assert count == 4


# ---------------------------------------------------------------------------
# run_condition
# ---------------------------------------------------------------------------


class TestRunCondition:
    @pytest.mark.parametrize("condition", list(AblationCondition))
    def test_returns_correct_number_of_turns(self, condition):
        dialog = run_condition(condition, turns=20, seed=0)
        _print_table(
            ["Condition", "Turns returned", "Expected"],
            [[condition.value, str(len(dialog)), "20"]],
            title=f"test_returns_correct_number_of_turns  [{condition.value}]",
        )
        assert len(dialog) == 20

    @pytest.mark.parametrize("condition", list(AblationCondition))
    def test_turns_have_role_and_text(self, condition):
        dialog = run_condition(condition, turns=10, seed=0)
        rows = [
            [str(i + 1), t["role"], t["text"][:30] + "...", "✓"]
            for i, t in enumerate(dialog)
        ]
        _print_table(
            ["Turn", "Role", "Text (truncated)", "Has role+text?"],
            rows,
            title=f"test_turns_have_role_and_text  [{condition.value}]",
        )
        for turn in dialog:
            assert "role" in turn
            assert "text" in turn
            assert isinstance(turn["role"], str)
            assert isinstance(turn["text"], str)

    def test_reproducible_with_same_seed(self):
        d1 = run_condition(AblationCondition.BASELINE, turns=15, seed=7)
        d2 = run_condition(AblationCondition.BASELINE, turns=15, seed=7)
        _print_table(
            ["Run", "Seed", "Turns", "Match?"],
            [
                ["Run 1", "7", str(len(d1)), ""],
                ["Run 2", "7", str(len(d2)), str(d1 == d2)],
            ],
            title="test_reproducible_with_same_seed",
        )
        assert d1 == d2

    def test_different_seeds_differ(self):
        d1 = run_condition(AblationCondition.BASELINE, turns=15, seed=1)
        d2 = run_condition(AblationCondition.BASELINE, turns=15, seed=2)
        # At least some turns should differ (random element)
        texts1 = [t["text"] for t in d1]
        texts2 = [t["text"] for t in d2]
        _print_table(
            ["Seed", "Turns", "Texts differ from other?"],
            [
                ["1", str(len(d1)), str(texts1 != texts2)],
                ["2", str(len(d2)), str(texts1 != texts2)],
            ],
            title="test_different_seeds_differ",
        )
        # Baseline pool is 5 items picked randomly, so they will likely differ
        assert texts1 != texts2

    def test_fixy_condition_contains_fixy_role(self):
        dialog = run_condition(AblationCondition.FIXY, turns=30, seed=0)
        roles = {t["role"] for t in dialog}
        _print_table(
            ["Condition", "Roles present", "Fixy in roles?"],
            [[AblationCondition.FIXY.value, str(sorted(roles)), str("Fixy" in roles)]],
            title="test_fixy_condition_contains_fixy_role",
        )
        assert "Fixy" in roles

    def test_baseline_no_fixy_role(self):
        dialog = run_condition(AblationCondition.BASELINE, turns=30, seed=0)
        roles = {t["role"] for t in dialog}
        _print_table(
            ["Condition", "Roles present", "Fixy absent?"],
            [
                [
                    AblationCondition.BASELINE.value,
                    str(sorted(roles)),
                    str("Fixy" not in roles),
                ]
            ],
            title="test_baseline_no_fixy_role",
        )
        assert "Fixy" not in roles


# ---------------------------------------------------------------------------
# run_ablation
# ---------------------------------------------------------------------------


class TestRunAblation:
    def test_returns_all_four_conditions(self):
        results = run_ablation(turns=10, seed=0)
        expected_labels = {c.value for c in AblationCondition}
        _print_table(
            ["Condition label", "Present?"],
            [[label, str(label in results)] for label in sorted(expected_labels)],
            title="test_returns_all_four_conditions",
        )
        assert set(results.keys()) == expected_labels

    def test_each_condition_has_metrics_and_series(self):
        results = run_ablation(turns=10, seed=0)
        _print_table(
            ["Condition", "Has 'metrics'?", "Has 'circularity_series'?"],
            [
                [label, str("metrics" in data), str("circularity_series" in data)]
                for label, data in results.items()
            ],
            title="test_each_condition_has_metrics_and_series",
        )
        for label, data in results.items():
            assert "metrics" in data, f"Missing 'metrics' for {label}"
            assert (
                "circularity_series" in data
            ), f"Missing 'circularity_series' for {label}"

    def test_circularity_series_length(self):
        results = run_ablation(turns=15, seed=0)
        _print_table(
            ["Condition", "Series length", "Expected"],
            [
                [label, str(len(data["circularity_series"])), "15"]
                for label, data in results.items()
            ],
            title="test_circularity_series_length",
        )
        for label, data in results.items():
            assert (
                len(data["circularity_series"]) == 15
            ), f"Wrong series length for {label}"

    def test_reproducible(self):
        r1 = run_ablation(turns=10, seed=99)
        r2 = run_ablation(turns=10, seed=99)
        _print_table(
            ["Condition", "Run1 circularity_rate", "Run2 circularity_rate", "Match?"],
            [
                [
                    label,
                    f"{r1[label]['metrics']['circularity_rate']:.4f}",
                    f"{r2[label]['metrics']['circularity_rate']:.4f}",
                    str(r1[label]["metrics"] == r2[label]["metrics"]),
                ]
                for label in r1
            ],
            title="test_reproducible",
        )
        for label in r1:
            assert r1[label]["metrics"] == r2[label]["metrics"]

    def test_baseline_higher_circularity_than_dialogue_engine(self):
        results = run_ablation(turns=30, seed=42)
        baseline_cr = results["Baseline"]["metrics"]["circularity_rate"]
        de_cr = results["DialogueEngine/Seed"]["metrics"]["circularity_rate"]
        _print_table(
            ["Condition", "circularity_rate", "Pass?"],
            [
                ["Baseline", f"{baseline_cr:.4f}", ""],
                [
                    "DialogueEngine/Seed",
                    f"{de_cr:.4f}",
                    "✓" if baseline_cr > de_cr else "✗",
                ],
            ],
            title="test_baseline_higher_circularity_than_dialogue_engine",
        )
        _print_bar_chart(
            [
                (label, data["metrics"]["circularity_rate"])
                for label, data in results.items()
            ],
            title="Circularity rate by condition",
        )
        assert (
            baseline_cr > de_cr
        ), f"Expected Baseline ({baseline_cr:.3f}) > DialogueEngine ({de_cr:.3f})"


# ---------------------------------------------------------------------------
# print_results_table
# ---------------------------------------------------------------------------


class TestPrintResultsTable:
    def test_smoke_no_crash(self):
        results = run_ablation(turns=10, seed=0)
        buf = io.StringIO()
        with redirect_stdout(buf):
            print_results_table(results)
        output = buf.getvalue()
        _print_table(
            ["Expected string", "Found?"],
            [
                ["Baseline", str("Baseline" in output)],
                ["Circularity", str("Circularity" in output)],
                ["Progress", str("Progress" in output)],
            ],
            title="test_smoke_no_crash (print_results_table)",
        )
        assert "Baseline" in output
        assert "Circularity" in output
        assert "Progress" in output

    def test_all_conditions_in_output(self):
        results = run_ablation(turns=10, seed=0)
        buf = io.StringIO()
        with redirect_stdout(buf):
            print_results_table(results)
        output = buf.getvalue()
        _print_table(
            ["Condition", "Found in output?"],
            [
                [condition.value, str(condition.value in output)]
                for condition in AblationCondition
            ],
            title="test_all_conditions_in_output",
        )
        for condition in AblationCondition:
            assert (
                condition.value in output
            ), f"Condition '{condition.value}' missing from table"


# ---------------------------------------------------------------------------
# plot_circularity / ASCII fallback
# ---------------------------------------------------------------------------


class TestPlotCircularity:
    def test_ascii_fallback_smoke(self):
        results = run_ablation(turns=10, seed=0)
        buf = io.StringIO()
        with redirect_stdout(buf):
            _ascii_circularity_chart(results)
        output = buf.getvalue()
        _print_table(
            ["Expected string", "Found?"],
            [["Circularity", str("Circularity" in output)]],
            title="test_ascii_fallback_smoke",
        )
        assert "Circularity" in output

    def test_plot_circularity_uses_ascii_when_matplotlib_absent(self):
        results = run_ablation(turns=10, seed=0)
        buf = io.StringIO()
        with patch.dict("sys.modules", {"matplotlib": None, "matplotlib.pyplot": None}):
            with redirect_stdout(buf):
                plot_circularity(results)
        output = buf.getvalue()
        _print_table(
            ["Scenario", "Output length", "Has output?"],
            [
                [
                    "matplotlib absent → ASCII fallback",
                    str(len(output)),
                    str(len(output) > 0),
                ]
            ],
            title="test_plot_circularity_uses_ascii_when_matplotlib_absent",
        )
        assert len(output) > 0


# ---------------------------------------------------------------------------
# Dialogue Metrics Demo — exact output validation
# ---------------------------------------------------------------------------

#: The canonical sample dialogue used by the __main__ demo in dialogue_metrics.py.
_DEMO_DIALOG = [
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


class TestDialogueMetricsDemo:
    """Validate the exact metric values and per-turn series shown in the demo table."""

    def test_circularity_rate(self):
        rate = circularity_rate(_DEMO_DIALOG)
        _print_table(
            ["Metric", "Got", "Expected", "Pass?"],
            [
                [
                    "circularity_rate",
                    f"{rate:.3f}",
                    "0.022",
                    "✓" if abs(rate - 0.022) < 1e-3 else "✗",
                ]
            ],
            title="test_circularity_rate (demo)",
        )
        assert rate == pytest.approx(0.022, abs=1e-3), f"Expected 0.022, got {rate:.3f}"

    def test_progress_rate(self):
        rate = progress_rate(_DEMO_DIALOG)
        _print_table(
            ["Metric", "Got", "Expected", "Pass?"],
            [
                [
                    "progress_rate",
                    f"{rate:.3f}",
                    "0.889",
                    "✓" if abs(rate - 0.889) < 1e-3 else "✗",
                ]
            ],
            title="test_progress_rate (demo)",
        )
        assert rate == pytest.approx(0.889, abs=1e-3), f"Expected 0.889, got {rate:.3f}"

    def test_intervention_utility(self):
        utility = intervention_utility(_DEMO_DIALOG)
        _print_table(
            ["Metric", "Got", "Expected", "Pass?"],
            [
                [
                    "intervention_utility",
                    f"{utility:.3f}",
                    "0.167",
                    "✓" if abs(utility - 0.167) < 1e-3 else "✗",
                ]
            ],
            title="test_intervention_utility (demo)",
        )
        assert utility == pytest.approx(
            0.167, abs=1e-3
        ), f"Expected 0.167, got {utility:.3f}"

    def test_per_turn_circularity_series_length(self):
        series = circularity_per_turn(_DEMO_DIALOG)
        _print_table(
            ["Metric", "Got", "Expected", "Pass?"],
            [
                [
                    "series length",
                    str(len(series)),
                    "10",
                    "✓" if len(series) == 10 else "✗",
                ]
            ],
            title="test_per_turn_circularity_series_length (demo)",
        )
        assert len(series) == 10

    def test_per_turn_circularity_values(self):
        expected = [0.00, 1.00, 0.33, 0.17, 0.10, 0.07, 0.00, 0.00, 0.00, 0.00]
        series = circularity_per_turn(_DEMO_DIALOG)
        _print_table(
            ["Turn", "Expected", "Got", "Pass?"],
            [
                [
                    str(i + 1),
                    f"{exp:.2f}",
                    f"{got:.2f}",
                    "✓" if abs(got - exp) < 0.01 else "✗",
                ]
                for i, (got, exp) in enumerate(zip(series, expected))
            ],
            title="test_per_turn_circularity_values (demo)",
        )
        _print_bar_chart(
            [(f"T{i+1}", v) for i, v in enumerate(series)],
            title="Per-turn circularity series  (demo dialog, turns 1→10)",
        )
        for i, (got, exp) in enumerate(zip(series, expected), start=1):
            assert got == pytest.approx(
                exp, abs=0.01
            ), f"Turn {i}: expected {exp:.2f}, got {got:.2f}"

    def test_demo_stdout_contains_header_and_metrics(self):
        """Smoke-test: running the demo block produces the expected header and metric lines."""
        import subprocess
        import sys

        result = subprocess.run(
            [sys.executable, "entelgia/dialogue_metrics.py"],
            capture_output=True,
            text=True,
            cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        )
        output = result.stdout
        _print_table(
            ["Expected string", "Found?"],
            [
                ["Dialogue Metrics Demo", str("Dialogue Metrics Demo" in output)],
                [
                    "Circularity Rate    : 0.022",
                    str("Circularity Rate    : 0.022" in output),
                ],
                [
                    "Progress Rate       : 0.889",
                    str("Progress Rate       : 0.889" in output),
                ],
                [
                    "Intervention Utility: 0.167",
                    str("Intervention Utility: 0.167" in output),
                ],
            ],
            title="test_demo_stdout_contains_header_and_metrics",
        )
        assert "Dialogue Metrics Demo" in output
        assert "Circularity Rate    : 0.022" in output
        assert "Progress Rate       : 0.889" in output
        assert "Intervention Utility: 0.167" in output

    def test_demo_stdout_per_turn_bars(self):
        """The per-turn bar chart lines are present in the demo output."""
        import subprocess
        import sys

        result = subprocess.run(
            [sys.executable, "entelgia/dialogue_metrics.py"],
            capture_output=True,
            text=True,
            cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        )
        output = result.stdout
        _print_table(
            ["Expected bar-chart line", "Found?"],
            [
                [
                    "Turn  2: 1.00 |####################",
                    str("Turn  2: 1.00 |####################" in output),
                ],
                ["Turn  3: 0.33 |#######", str("Turn  3: 0.33 |#######" in output)],
                ["Turn  7: 0.00 |", str("Turn  7: 0.00 |" in output)],
            ],
            title="test_demo_stdout_per_turn_bars",
        )
        assert "Turn  2: 1.00 |####################" in output
        assert "Turn  3: 0.33 |#######" in output
        assert "Turn  7: 0.00 |" in output


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s", "--override-ini=addopts="])

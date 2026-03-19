# tests/test_ablation_study.py
"""
Tests for entelgia/ablation_study.py

Covers:
- AblationCondition enum values
- run_condition — returns list of dicts for each condition
- run_ablation — runs all four conditions and returns metrics dict
- print_results_table — outputs a formatted table without errors
"""

from __future__ import annotations

import io
import sys
import os
from contextlib import redirect_stdout
from typing import Dict, List

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from entelgia.ablation_study import (
    AblationCondition,
    run_ablation,
    run_condition,
    print_results_table,
    plot_circularity,
    _ascii_circularity_chart,
)

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
        print(f"  {str(label):>22} │ {bar:<{max_width}} {value:.4f}")
    print()


# ---------------------------------------------------------------------------
# AblationCondition enum
# ---------------------------------------------------------------------------


class TestAblationCondition:
    """AblationCondition must expose the four required conditions."""

    def test_four_conditions_exist(self):
        conditions = list(AblationCondition)
        assert len(conditions) == 4

    def test_baseline_condition(self):
        assert AblationCondition.BASELINE.value == "Baseline"

    def test_dialogue_engine_condition(self):
        assert AblationCondition.DIALOGUE_ENGINE.value == "DialogueEngine/Seed"

    def test_fixy_condition(self):
        assert AblationCondition.FIXY.value == "Fixy Interventions"

    def test_dream_condition(self):
        assert AblationCondition.DREAM.value == "Dream/Energy"


# ---------------------------------------------------------------------------
# run_condition
# ---------------------------------------------------------------------------


class TestRunCondition:
    """run_condition should produce a list of dialogue turn dicts."""

    @pytest.mark.parametrize(
        "condition",
        [
            AblationCondition.BASELINE,
            AblationCondition.DIALOGUE_ENGINE,
            AblationCondition.FIXY,
            AblationCondition.DREAM,
        ],
    )
    def test_returns_list(self, condition):
        result = run_condition(condition, turns=5, seed=0)
        assert isinstance(result, list)

    @pytest.mark.parametrize(
        "condition",
        [
            AblationCondition.BASELINE,
            AblationCondition.DIALOGUE_ENGINE,
            AblationCondition.FIXY,
            AblationCondition.DREAM,
        ],
    )
    def test_each_turn_has_role_and_text(self, condition):
        result = run_condition(condition, turns=5, seed=0)
        for turn in result:
            assert "role" in turn
            assert "text" in turn
            assert isinstance(turn["role"], str)
            assert isinstance(turn["text"], str)

    def test_turns_count_respected(self):
        result = run_condition(AblationCondition.BASELINE, turns=10, seed=42)
        assert len(result) == 10

    def test_baseline_is_deterministic(self):
        a = run_condition(AblationCondition.BASELINE, turns=8, seed=99)
        b = run_condition(AblationCondition.BASELINE, turns=8, seed=99)
        assert a == b

    def test_different_seeds_give_different_results(self):
        a = run_condition(AblationCondition.BASELINE, turns=8, seed=1)
        b = run_condition(AblationCondition.BASELINE, turns=8, seed=2)
        # Very unlikely to be identical with different seeds
        assert a != b


# ---------------------------------------------------------------------------
# run_ablation
# ---------------------------------------------------------------------------


class TestRunAblation:
    """run_ablation must return a dict with an entry for each condition."""

    def setup_method(self):
        # Use minimal turns for speed
        self.results = run_ablation(turns=5, seed=42)

    def test_returns_dict(self):
        assert isinstance(self.results, dict)

    def test_all_conditions_present(self):
        for condition in AblationCondition:
            assert condition.value in self.results

    def test_each_entry_has_metrics(self):
        for condition in AblationCondition:
            entry = self.results[condition.value]
            assert "metrics" in entry
            assert isinstance(entry["metrics"], dict)

    def test_each_entry_has_circularity_series(self):
        for condition in AblationCondition:
            entry = self.results[condition.value]
            assert "circularity_series" in entry
            assert isinstance(entry["circularity_series"], list)
        _print_table(
            ["Condition", "Series Length"],
            [
                [label, str(len(data["circularity_series"]))]
                for label, data in self.results.items()
            ],
            title="test_each_entry_has_circularity_series",
        )

    def test_metrics_contain_circularity_rate(self):
        for condition in AblationCondition:
            metrics = self.results[condition.value]["metrics"]
            assert "circularity_rate" in metrics
        _print_table(
            ["Condition", "Circularity Rate"],
            [
                [label, f"{data['metrics']['circularity_rate']:.4f}"]
                for label, data in self.results.items()
            ],
            title="test_metrics_contain_circularity_rate",
        )
        _print_bar_chart(
            [
                (label, data["metrics"]["circularity_rate"])
                for label, data in self.results.items()
            ],
            title="Circularity Rate by Condition",
        )

    def test_metrics_contain_progress_rate(self):
        for condition in AblationCondition:
            metrics = self.results[condition.value]["metrics"]
            assert "progress_rate" in metrics
        _print_table(
            ["Condition", "Progress Rate"],
            [
                [label, f"{data['metrics']['progress_rate']:.4f}"]
                for label, data in self.results.items()
            ],
            title="test_metrics_contain_progress_rate",
        )
        _print_bar_chart(
            [
                (label, data["metrics"]["progress_rate"])
                for label, data in self.results.items()
            ],
            title="Progress Rate by Condition",
        )

    def test_metrics_values_are_numeric(self):
        for condition in AblationCondition:
            metrics = self.results[condition.value]["metrics"]
            for key, val in metrics.items():
                assert isinstance(
                    val, (int, float)
                ), f"Metric {key!r} for {condition.value!r} is not numeric: {val!r}"
        metric_keys = ["circularity_rate", "progress_rate", "intervention_utility"]
        _print_table(
            ["Condition"] + [k.replace("_", " ").title() for k in metric_keys],
            [
                [label] + [f"{data['metrics'].get(k, 0.0):.4f}" for k in metric_keys]
                for label, data in self.results.items()
            ],
            title="test_metrics_values_are_numeric — Full Metrics",
        )

    def test_deterministic(self):
        a = run_ablation(turns=5, seed=7)
        b = run_ablation(turns=5, seed=7)
        _print_table(
            ["Condition", "Run1 circularity_rate", "Run2 circularity_rate", "Match?"],
            [
                [
                    label,
                    f"{a[label]['metrics']['circularity_rate']:.4f}",
                    f"{b[label]['metrics']['circularity_rate']:.4f}",
                    "✓" if a[label]["metrics"] == b[label]["metrics"] else "✗",
                ]
                for label in a
            ],
            title="test_deterministic",
        )
        assert a == b


# ---------------------------------------------------------------------------
# print_results_table
# ---------------------------------------------------------------------------


class TestPrintResultsTable:
    """print_results_table should produce tabular output without errors."""

    def test_no_exception(self):
        results = run_ablation(turns=5, seed=0)
        buf = io.StringIO()
        with redirect_stdout(buf):
            print_results_table(results)

    def test_output_is_non_empty(self):
        results = run_ablation(turns=5, seed=0)
        buf = io.StringIO()
        with redirect_stdout(buf):
            print_results_table(results)
        output = buf.getvalue()
        assert len(output) > 0

    def test_output_contains_condition_names(self):
        results = run_ablation(turns=5, seed=0)
        buf = io.StringIO()
        with redirect_stdout(buf):
            print_results_table(results)
        output = buf.getvalue()
        assert "Baseline" in output
        assert "Fixy" in output

    def test_print_full_results(self):
        """Print the complete ablation study results table and circularity chart."""
        results = run_ablation(turns=30, seed=42)
        print("\n" + "=" * 70)
        print("  ABLATION STUDY RESULTS  (turns=30, seed=42)")
        print("=" * 70)
        print_results_table(results)
        print()
        _ascii_circularity_chart(results)


if __name__ == "__main__":
    print("\n" + "=" * 70)
    print("  ABLATION STUDY — FULL RESULTS  (turns=30, seed=42)")
    print("=" * 70 + "\n")
    results = run_ablation(turns=30, seed=42)
    print_results_table(results)
    print()
    _ascii_circularity_chart(results)
    print("\n" + "=" * 70)
    print("  Running pytest suite…")
    print("=" * 70 + "\n")
    pytest.main([__file__, "-v", "-s", "--override-ini=addopts="])

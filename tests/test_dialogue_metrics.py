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
# _keywords helper
# ---------------------------------------------------------------------------


class TestKeywords:
    def test_only_long_words(self):
        kw = _keywords("hi the consciousness emerges")
        assert "consciousness" in kw
        assert "emerges" in kw
        # short words excluded
        assert "the" not in kw
        assert "hi" not in kw

    def test_lowercases(self):
        kw = _keywords("Consciousness EMERGES")
        assert "consciousness" in kw
        assert "emerges" in kw


# ---------------------------------------------------------------------------
# _jaccard helper
# ---------------------------------------------------------------------------


class TestJaccard:
    def test_identical_sets(self):
        a = frozenset(["consciousness", "emerges"])
        assert _jaccard(a, a) == pytest.approx(1.0)

    def test_disjoint_sets(self):
        a = frozenset(["consciousness"])
        b = frozenset(["freedom"])
        assert _jaccard(a, b) == pytest.approx(0.0)

    def test_partial_overlap(self):
        a = frozenset(["consciousness", "emerges", "complex"])
        b = frozenset(["consciousness", "emerges", "freedom"])
        # intersection=2, union=4
        assert _jaccard(a, b) == pytest.approx(2 / 4)

    def test_empty_sets(self):
        assert _jaccard(frozenset(), frozenset()) == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# circularity_rate
# ---------------------------------------------------------------------------


class TestCircularityRate:
    def test_empty_dialog(self):
        assert circularity_rate([]) == pytest.approx(0.0)

    def test_single_turn(self):
        d = _make_dialog(["consciousness emerges from complex systems"])
        assert circularity_rate(d) == pytest.approx(0.0)

    def test_identical_turns_high_circularity(self):
        text = "consciousness emerges from complex information processing systems"
        d = _make_dialog([text] * 6)
        rate = circularity_rate(d)
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
        assert rate < 0.4, f"Expected low circularity, got {rate}"

    def test_custom_threshold(self):
        text = "consciousness emerges from complex information"
        d = _make_dialog([text] * 4)
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
        assert 0.0 <= rate <= 1.0


# ---------------------------------------------------------------------------
# circularity_per_turn
# ---------------------------------------------------------------------------


class TestCircularityPerTurn:
    def test_series_length_equals_dialog_length(self):
        texts = ["consciousness emerges"] * 10
        d = _make_dialog(texts)
        series = circularity_per_turn(d)
        assert len(series) == len(d)

    def test_empty_dialog(self):
        assert circularity_per_turn([]) == []

    def test_first_turn_is_zero(self):
        d = _make_dialog(["consciousness emerges from complex information"])
        series = circularity_per_turn(d)
        assert series[0] == pytest.approx(0.0)

    def test_values_in_range(self):
        texts = ["consciousness emerges"] * 8
        d = _make_dialog(texts)
        series = circularity_per_turn(d)
        for v in series:
            assert 0.0 <= v <= 1.0


# ---------------------------------------------------------------------------
# progress_rate
# ---------------------------------------------------------------------------


class TestProgressRate:
    def test_empty_or_single_turn(self):
        assert progress_rate([]) == pytest.approx(0.0)
        d = _make_dialog(["consciousness emerges"])
        assert progress_rate(d) == pytest.approx(0.0)

    def test_synthesis_marker_increases_progress(self):
        texts = [
            "consciousness emerges from complex information processing",
            "therefore integrating both views reveals a unified framework",
        ]
        d = _make_dialog(texts)
        assert progress_rate(d) > 0.0

    def test_topic_shift_counts_as_progress(self):
        texts = [
            "consciousness emerges from complex information processing systems",
            "democracy freedom justice equality participation requires balance",
        ]
        d = _make_dialog(texts)
        assert progress_rate(d) > 0.0

    def test_question_resolution(self):
        texts = [
            "what is the nature of consciousness and why does it arise?",
            "because neural correlates explain the binding problem solution",
        ]
        d = _make_dialog(texts)
        assert progress_rate(d) > 0.0

    def test_repetitive_dialog_low_progress(self):
        text = "consciousness emerges from complex information processing"
        d = _make_dialog([text] * 8)
        assert progress_rate(d) == pytest.approx(0.0)

    def test_result_in_range(self):
        texts = [
            "consciousness emerges from complex information processing systems",
            "therefore integrating both views reveals a unified bridge framework",
            "democracy freedom justice equality participation society requires",
            "mathematics physics formalism elegant theories explain universe",
        ]
        d = _make_dialog(texts)
        rate = progress_rate(d)
        assert 0.0 <= rate <= 1.0


# ---------------------------------------------------------------------------
# intervention_utility
# ---------------------------------------------------------------------------


class TestInterventionUtility:
    def test_no_fixy_turns(self):
        texts = ["consciousness emerges"] * 10
        d = _make_dialog(texts)
        assert intervention_utility(d) == pytest.approx(0.0)

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
        # Should return a float (sign depends on simulation)
        assert isinstance(utility, float)

    def test_result_is_float(self):
        d = _make_dialog(["consciousness emerges"] * 10)
        d[4]["role"] = "Fixy"
        assert isinstance(intervention_utility(d), float)


# ---------------------------------------------------------------------------
# compute_all_metrics
# ---------------------------------------------------------------------------


class TestComputeAllMetrics:
    def test_keys_present(self):
        d = _make_dialog(["consciousness emerges from complex"] * 5)
        metrics = compute_all_metrics(d)
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
        for k, v in metrics.items():
            assert isinstance(v, float), f"{k} is not float"
            assert -1.0 <= v <= 1.0, f"{k}={v} out of range"


# ---------------------------------------------------------------------------
# AblationCondition enum
# ---------------------------------------------------------------------------


class TestAblationCondition:
    def test_all_four_conditions_defined(self):
        conditions = set(c.value for c in AblationCondition)
        assert "Baseline" in conditions
        assert "DialogueEngine/Seed" in conditions
        assert "Fixy Interventions" in conditions
        assert "Dream/Energy" in conditions

    def test_enum_has_four_members(self):
        assert len(AblationCondition) == 4


# ---------------------------------------------------------------------------
# run_condition
# ---------------------------------------------------------------------------


class TestRunCondition:
    @pytest.mark.parametrize("condition", list(AblationCondition))
    def test_returns_correct_number_of_turns(self, condition):
        dialog = run_condition(condition, turns=20, seed=0)
        assert len(dialog) == 20

    @pytest.mark.parametrize("condition", list(AblationCondition))
    def test_turns_have_role_and_text(self, condition):
        dialog = run_condition(condition, turns=10, seed=0)
        for turn in dialog:
            assert "role" in turn
            assert "text" in turn
            assert isinstance(turn["role"], str)
            assert isinstance(turn["text"], str)

    def test_reproducible_with_same_seed(self):
        d1 = run_condition(AblationCondition.BASELINE, turns=15, seed=7)
        d2 = run_condition(AblationCondition.BASELINE, turns=15, seed=7)
        assert d1 == d2

    def test_different_seeds_differ(self):
        d1 = run_condition(AblationCondition.BASELINE, turns=15, seed=1)
        d2 = run_condition(AblationCondition.BASELINE, turns=15, seed=2)
        # At least some turns should differ (random element)
        texts1 = [t["text"] for t in d1]
        texts2 = [t["text"] for t in d2]
        # Baseline pool is 5 items picked randomly, so they will likely differ
        assert texts1 != texts2

    def test_fixy_condition_contains_fixy_role(self):
        dialog = run_condition(AblationCondition.FIXY, turns=30, seed=0)
        roles = {t["role"] for t in dialog}
        assert "Fixy" in roles

    def test_baseline_no_fixy_role(self):
        dialog = run_condition(AblationCondition.BASELINE, turns=30, seed=0)
        roles = {t["role"] for t in dialog}
        assert "Fixy" not in roles


# ---------------------------------------------------------------------------
# run_ablation
# ---------------------------------------------------------------------------


class TestRunAblation:
    def test_returns_all_four_conditions(self):
        results = run_ablation(turns=10, seed=0)
        expected_labels = {c.value for c in AblationCondition}
        assert set(results.keys()) == expected_labels

    def test_each_condition_has_metrics_and_series(self):
        results = run_ablation(turns=10, seed=0)
        for label, data in results.items():
            assert "metrics" in data, f"Missing 'metrics' for {label}"
            assert (
                "circularity_series" in data
            ), f"Missing 'circularity_series' for {label}"

    def test_circularity_series_length(self):
        results = run_ablation(turns=15, seed=0)
        for label, data in results.items():
            assert (
                len(data["circularity_series"]) == 15
            ), f"Wrong series length for {label}"

    def test_reproducible(self):
        r1 = run_ablation(turns=10, seed=99)
        r2 = run_ablation(turns=10, seed=99)
        for label in r1:
            assert r1[label]["metrics"] == r2[label]["metrics"]

    def test_baseline_higher_circularity_than_dialogue_engine(self):
        results = run_ablation(turns=30, seed=42)
        baseline_cr = results["Baseline"]["metrics"]["circularity_rate"]
        de_cr = results["DialogueEngine/Seed"]["metrics"]["circularity_rate"]
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
        assert "Baseline" in output
        assert "Circularity" in output
        assert "Progress" in output

    def test_all_conditions_in_output(self):
        results = run_ablation(turns=10, seed=0)
        buf = io.StringIO()
        with redirect_stdout(buf):
            print_results_table(results)
        output = buf.getvalue()
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
        assert "Circularity" in output

    def test_plot_circularity_uses_ascii_when_matplotlib_absent(self):
        results = run_ablation(turns=10, seed=0)
        buf = io.StringIO()
        with patch.dict("sys.modules", {"matplotlib": None, "matplotlib.pyplot": None}):
            with redirect_stdout(buf):
                plot_circularity(results)
        output = buf.getvalue()
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
        assert rate == pytest.approx(0.022, abs=1e-3), f"Expected 0.022, got {rate:.3f}"

    def test_progress_rate(self):
        rate = progress_rate(_DEMO_DIALOG)
        assert rate == pytest.approx(0.889, abs=1e-3), f"Expected 0.889, got {rate:.3f}"

    def test_intervention_utility(self):
        utility = intervention_utility(_DEMO_DIALOG)
        assert utility == pytest.approx(
            0.167, abs=1e-3
        ), f"Expected 0.167, got {utility:.3f}"

    def test_per_turn_circularity_series_length(self):
        series = circularity_per_turn(_DEMO_DIALOG)
        assert len(series) == 10

    def test_per_turn_circularity_values(self):
        expected = [0.00, 1.00, 0.33, 0.17, 0.10, 0.07, 0.00, 0.00, 0.00, 0.00]
        series = circularity_per_turn(_DEMO_DIALOG)
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
        assert "Turn  2: 1.00 |####################" in output
        assert "Turn  3: 0.33 |#######" in output
        assert "Turn  7: 0.00 |" in output


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

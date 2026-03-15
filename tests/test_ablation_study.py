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
)

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

    def test_metrics_contain_circularity_rate(self):
        for condition in AblationCondition:
            metrics = self.results[condition.value]["metrics"]
            assert "circularity_rate" in metrics

    def test_metrics_contain_progress_rate(self):
        for condition in AblationCondition:
            metrics = self.results[condition.value]["metrics"]
            assert "progress_rate" in metrics

    def test_metrics_values_are_numeric(self):
        for condition in AblationCondition:
            metrics = self.results[condition.value]["metrics"]
            for key, val in metrics.items():
                assert isinstance(
                    val, (int, float)
                ), f"Metric {key!r} for {condition.value!r} is not numeric: {val!r}"

    def test_deterministic(self):
        a = run_ablation(turns=5, seed=7)
        b = run_ablation(turns=5, seed=7)
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


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])

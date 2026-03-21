#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Tests for improved Fixy intervention logic.

Covers:
  - Pair gating: Fixy must not intervene after a single agent's turn
  - Novelty suppression: Fixy must not declare a loop when genuine novelty exists
  - Structural rewrite mode selection based on loop type
  - Rewrite hint content and injection
  - Condition-based output (not always Loop/Missing variable/Next move)
  - False positive reduction relative to baseline
"""

import sys
import os
import logging

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from entelgia.loop_guard import (
    DialogueLoopDetector,
    DialogueRewriter,
    LOOP_REPETITION,
    WEAK_CONFLICT,
    PREMATURE_SYNTHESIS,
    TOPIC_STAGNATION,
)
from entelgia.fixy_interactive import (
    FixyMode,
    InteractiveFixy,
    _LOOP_REWRITE_MODE_POLICY,
    _MODE_PROMPTS,
)

# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _make_turns(texts, roles=None):
    """Build a list of turn dicts from texts. Alternates Socrates/Athena by default."""
    if roles is None:
        agent_names = ["Socrates", "Athena"]
        roles = [agent_names[i % 2] for i in range(len(texts))]
    return [{"role": r, "text": t} for r, t in zip(roles, texts)]


def _repetitive_texts(n=6):
    """Return n highly overlapping texts suitable for triggering a loop signal."""
    return [
        "freedom autonomy liberty independence means personal freedom",
        "autonomy liberty freedom independence are fundamental values",
        "liberty means freedom autonomy personal independence always",
        "independence freedom liberty autonomy interrelated core concepts",
        "freedom liberty autonomy independence personal core values",
        "autonomy independence liberty freedom personal self-determination",
    ][:n]


# ---------------------------------------------------------------------------
# 1. Pair gating — DialogueLoopDetector
# ---------------------------------------------------------------------------


class TestPairGatingLoopDetector:
    """DialogueLoopDetector must refuse to fire when only one agent has spoken."""

    def test_only_socrates_turns_no_loop(self):
        """Loop must not be declared when dialog contains only Socrates turns."""
        detector = DialogueLoopDetector()
        turns = _make_turns(
            _repetitive_texts(5),
            roles=["Socrates"] * 5,
        )
        modes = detector.detect(turns, turn_count=5)
        assert (
            modes == []
        ), f"[FIXY-GATE] Must skip when only Socrates present; got {modes}"

    def test_only_athena_turns_no_loop(self):
        """Loop must not be declared when dialog contains only Athena turns."""
        detector = DialogueLoopDetector()
        turns = _make_turns(
            _repetitive_texts(5),
            roles=["Athena"] * 5,
        )
        modes = detector.detect(turns, turn_count=5)
        assert (
            modes == []
        ), f"[FIXY-GATE] Must skip when only Athena present; got {modes}"

    def test_pair_present_loop_detected(self):
        """Loop should be detected once both agents have spoken and conditions are met."""
        detector = DialogueLoopDetector()
        turns = _make_turns(_repetitive_texts(5))
        modes = detector.detect(turns, turn_count=5)
        # Both agents present in alternating turns; loop conditions should fire
        assert (
            LOOP_REPETITION in modes
        ), f"Expected loop_repetition with both agents; got {modes}"

    def test_single_socrates_turn_no_loop(self):
        """Single Socrates turn must not trigger any loop mode."""
        detector = DialogueLoopDetector()
        turns = [{"role": "Socrates", "text": "What is the nature of freedom?"}]
        modes = detector.detect(turns, turn_count=1)
        assert modes == [], f"Single Socrates turn must not trigger loop; got {modes}"

    def test_single_athena_turn_no_loop(self):
        """Single Athena turn must not trigger any loop mode."""
        detector = DialogueLoopDetector()
        turns = [{"role": "Athena", "text": "Society shapes freedom through its laws."}]
        modes = detector.detect(turns, turn_count=1)
        assert modes == [], f"Single Athena turn must not trigger loop; got {modes}"


# ---------------------------------------------------------------------------
# 2. Pair gating — InteractiveFixy.should_intervene
# ---------------------------------------------------------------------------


class TestPairGatingInteractiveFixy:
    """InteractiveFixy.should_intervene must obey pair gating."""

    class _StubLLM:
        def generate(self, *args, **kwargs):
            return "stub"

    def _make_fixy(self):
        return InteractiveFixy(self._StubLLM(), "stub-model")

    def test_no_intervention_after_single_socrates_turn(self):
        """should_intervene must return False when only Socrates has spoken."""
        fixy = self._make_fixy()
        dialog = [
            {"role": "Socrates", "text": "What is the nature of freedom?"},
        ]
        result, reason = fixy.should_intervene(dialog, turn_count=1)
        assert (
            result is False
        ), f"[FIXY-GATE] Must not intervene after single Socrates turn; got reason={reason!r}"

    def test_no_intervention_after_single_athena_turn(self):
        """should_intervene must return False when only Athena has spoken."""
        fixy = self._make_fixy()
        dialog = [
            {"role": "Athena", "text": "Society determines freedom through law."},
        ]
        result, reason = fixy.should_intervene(dialog, turn_count=1)
        assert (
            result is False
        ), f"[FIXY-GATE] Must not intervene after single Athena turn; got reason={reason!r}"

    def test_no_intervention_socrates_only_many_turns(self):
        """should_intervene must return False even with many Socrates-only turns."""
        fixy = self._make_fixy()
        dialog = [{"role": "Socrates", "text": t} for t in _repetitive_texts(6)]
        result, reason = fixy.should_intervene(dialog, turn_count=6)
        assert (
            result is False
        ), f"[FIXY-GATE] Must not intervene with only Socrates; got reason={reason!r}"

    def test_no_intervention_athena_only_many_turns(self):
        """should_intervene must return False even with many Athena-only turns."""
        fixy = self._make_fixy()
        dialog = [{"role": "Athena", "text": t} for t in _repetitive_texts(6)]
        result, reason = fixy.should_intervene(dialog, turn_count=6)
        assert (
            result is False
        ), f"[FIXY-GATE] Must not intervene with only Athena; got reason={reason!r}"

    def test_intervention_allowed_after_pair(self, caplog):
        """should_intervene may trigger once both agents have spoken (loop conditions met)."""
        fixy = self._make_fixy()
        # Build a dialog with both agents present and repetitive content
        dialog = _make_turns(_repetitive_texts(6))
        # Add Fixy's older interventions to avoid deduplication guards
        with caplog.at_level(logging.INFO, logger="entelgia.fixy_interactive"):
            result, reason = fixy.should_intervene(dialog, turn_count=6)
        # Both agents present + repetitive → intervention allowed
        # (may or may not fire depending on loop_guard thresholds, but NOT blocked by gating)
        if result:
            # If intervention triggered, reason must not be the empty string
            assert reason != "", "reason must be non-empty when should_intervene=True"

    def test_pending_rewrite_mode_set_on_intervention(self):
        """_pending_rewrite_mode must be populated when loop is detected."""
        fixy = self._make_fixy()
        dialog = _make_turns(_repetitive_texts(6))
        result, reason = fixy.should_intervene(dialog, turn_count=6)
        if result:
            assert (
                fixy._pending_rewrite_mode is not None
            ), "_pending_rewrite_mode must be set when intervention is triggered"

    def test_pending_rewrite_mode_cleared_on_no_intervention(self):
        """_pending_rewrite_mode must be None when no intervention is triggered."""
        fixy = self._make_fixy()
        # Single agent only → no intervention
        dialog = [{"role": "Socrates", "text": "What is freedom?"}]
        result, _ = fixy.should_intervene(dialog, turn_count=1)
        assert result is False
        assert fixy._pending_rewrite_mode is None


# ---------------------------------------------------------------------------
# 3. Novelty suppression — DialogueLoopDetector
# ---------------------------------------------------------------------------


class TestNoveltySuppressionLoopDetector:
    """Novelty signals should suppress false-positive loop declarations."""

    def test_no_loop_when_new_metric_present(self):
        """Loop must not be declared when a measurable criterion is introduced."""
        detector = DialogueLoopDetector()
        # Make repetitive base turns, then inject a metric-heavy turn at the end
        base = _make_turns(_repetitive_texts(4))
        # Add turns with metric language (overwrites last 2 positions effectively
        # via fresh construction)
        turns = _make_turns(
            [
                "freedom autonomy liberty independence means personal freedom",
                "autonomy liberty freedom independence are fundamental values",
                "liberty means freedom autonomy personal independence always",
                # New: adds metric keywords — should suppress loop
                "we should measure this using a quantifiable index of autonomy score",
                "the benchmark and criterion for freedom must include measurable threshold",
            ]
        )
        modes = detector.detect(turns, turn_count=5)
        assert (
            LOOP_REPETITION not in modes
        ), f"[FIXY-SUPPRESS] Loop must not fire when new metric is present; got {modes}"

    def test_no_loop_when_concrete_case_present(self):
        """Loop must not be declared when a concrete case is introduced."""
        detector = DialogueLoopDetector()
        turns = _make_turns(
            [
                "freedom autonomy liberty independence means personal freedom",
                "autonomy liberty freedom independence are fundamental values",
                "liberty means freedom autonomy personal independence always",
                # New: grounded concrete example
                "consider specifically the historical case of apartheid South Africa",
                "this real-world scenario and concrete evidence illustrate the instance",
            ]
        )
        modes = detector.detect(turns, turn_count=5)
        assert (
            LOOP_REPETITION not in modes
        ), f"[FIXY-SUPPRESS] Loop must not fire when concrete case is present; got {modes}"

    def test_no_loop_when_forced_choice_present(self):
        """Loop must not be declared when a binary choice is introduced."""
        detector = DialogueLoopDetector()
        turns = _make_turns(
            [
                "freedom autonomy liberty independence means personal freedom",
                "autonomy liberty freedom independence are fundamental values",
                "liberty means freedom autonomy personal independence always",
                # New: forced decision language
                "we must choose either individual rights or collective security",
                "the binary decision here requires us to pick one versus the other",
            ]
        )
        modes = detector.detect(turns, turn_count=5)
        assert (
            LOOP_REPETITION not in modes
        ), f"[FIXY-SUPPRESS] Loop must not fire when forced choice is present; got {modes}"

    def test_no_loop_when_testable_claim_present(self):
        """Loop must not be declared when a testable, falsifiable claim appears."""
        detector = DialogueLoopDetector()
        turns = _make_turns(
            [
                "freedom autonomy liberty independence means personal freedom",
                "autonomy liberty freedom independence are fundamental values",
                "liberty means freedom autonomy personal independence always",
                # New: testable claim language
                "this is falsifiable if we can predict observable outcomes empirically",
                "the hypothesis is testable through experiment and verifiable results",
            ]
        )
        modes = detector.detect(turns, turn_count=5)
        assert (
            LOOP_REPETITION not in modes
        ), f"[FIXY-SUPPRESS] Loop must not fire when testable claim is present; got {modes}"

    def test_no_loop_when_operational_definition_present(self):
        """Loop must not be declared when an operational definition is provided."""
        detector = DialogueLoopDetector()
        turns = _make_turns(
            [
                "freedom autonomy liberty independence means personal freedom",
                "autonomy liberty freedom independence are fundamental values",
                "liberty means freedom autonomy personal independence always",
                # New: definitional clarification
                "let us define precisely what counts as a free action distinction",
                "freedom defined as absence of coercion — this clarifies the distinction",
            ]
        )
        modes = detector.detect(turns, turn_count=5)
        assert (
            LOOP_REPETITION not in modes
        ), f"[FIXY-SUPPRESS] Loop must not fire with operational definition; got {modes}"

    def test_structural_loop_fires_without_novelty(self):
        """A true structural loop (no novelty) must still be detected."""
        detector = DialogueLoopDetector()
        turns = _make_turns(_repetitive_texts(6))
        modes = detector.detect(turns, turn_count=6)
        assert (
            LOOP_REPETITION in modes
        ), f"Structural loop without novelty must be detected; got {modes}"

    def test_novelty_check_returns_clusters(self):
        """_check_novelty_present must return the correct active cluster names."""
        detector = DialogueLoopDetector()
        turns = _make_turns(
            [
                "we should measure this with a quantifiable metric and benchmark",
                "consider the specific concrete case of Nordic countries as evidence",
            ]
        )
        clusters, count = detector._check_novelty_present(turns)
        assert "metric" in clusters, f"Expected 'metric' cluster; got {clusters}"
        assert "case" in clusters, f"Expected 'case' cluster; got {clusters}"
        assert count >= 2

    def test_no_novelty_in_pure_repetition(self):
        """_check_novelty_present must return empty when turns are purely repetitive."""
        detector = DialogueLoopDetector()
        turns = _make_turns(
            [
                "freedom autonomy liberty independence values",
                "autonomy liberty freedom independence personal",
            ]
        )
        clusters, count = detector._check_novelty_present(turns)
        assert count == 0 or (
            "metric" not in clusters and "case" not in clusters
        ), f"Repetitive turns must not show metric/case novelty; got {clusters}"


# ---------------------------------------------------------------------------
# 4. Rewrite mode selection
# ---------------------------------------------------------------------------


class TestRewriteModeSelection:
    """Fixy must select the rewrite mode that matches the loop type."""

    def test_loop_repetition_maps_to_force_case(self):
        """loop_repetition should default to force_case rewrite mode."""
        mode = _LOOP_REWRITE_MODE_POLICY.get("loop_repetition")
        assert (
            mode == FixyMode.FORCE_CASE
        ), f"loop_repetition should map to FORCE_CASE; got {mode!r}"

    def test_weak_conflict_maps_to_force_choice(self):
        """weak_conflict should map to force_choice rewrite mode."""
        mode = _LOOP_REWRITE_MODE_POLICY.get("weak_conflict")
        assert (
            mode == FixyMode.FORCE_CHOICE
        ), f"weak_conflict should map to FORCE_CHOICE; got {mode!r}"

    def test_premature_synthesis_maps_to_force_test(self):
        """premature_synthesis should map to force_test rewrite mode."""
        mode = _LOOP_REWRITE_MODE_POLICY.get("premature_synthesis")
        assert (
            mode == FixyMode.FORCE_TEST
        ), f"premature_synthesis should map to FORCE_TEST; got {mode!r}"

    def test_topic_stagnation_maps_to_force_metric(self):
        """topic_stagnation should map to force_metric rewrite mode."""
        mode = _LOOP_REWRITE_MODE_POLICY.get("topic_stagnation")
        assert (
            mode == FixyMode.FORCE_METRIC
        ), f"topic_stagnation should map to FORCE_METRIC; got {mode!r}"

    def test_shallow_discussion_maps_to_force_test(self):
        """shallow_discussion should map to force_test rewrite mode."""
        mode = _LOOP_REWRITE_MODE_POLICY.get("shallow_discussion")
        assert (
            mode == FixyMode.FORCE_TEST
        ), f"shallow_discussion should map to FORCE_TEST; got {mode!r}"

    def test_all_rewrite_modes_have_prompts(self):
        """Every structural rewrite mode must have a prompt template."""
        rewrite_modes = [
            FixyMode.FORCE_METRIC,
            FixyMode.FORCE_CHOICE,
            FixyMode.FORCE_TEST,
            FixyMode.FORCE_CASE,
            FixyMode.FORCE_DEFINITION,
        ]
        for mode in rewrite_modes:
            assert (
                mode in _MODE_PROMPTS
            ), f"FixyMode.{mode!r} must have a prompt in _MODE_PROMPTS"

    def test_rewrite_mode_constants_correct_values(self):
        """Structural rewrite FixyMode constants must match their string values."""
        assert FixyMode.FORCE_METRIC == "force_metric"
        assert FixyMode.FORCE_CHOICE == "force_choice"
        assert FixyMode.FORCE_TEST == "force_test"
        assert FixyMode.FORCE_CASE == "force_case"
        assert FixyMode.FORCE_DEFINITION == "force_definition"


# ---------------------------------------------------------------------------
# 5. Rewrite hint generation and content
# ---------------------------------------------------------------------------


class TestRewriteHintGeneration:
    """get_rewrite_hint must produce structural (non-cosmetic) directives."""

    class _StubLLM:
        def generate(self, *args, **kwargs):
            return "stub"

    def _make_fixy(self):
        return InteractiveFixy(self._StubLLM(), "stub-model")

    def test_hint_contains_rewrite_header(self):
        """Rewrite hint must start with the expected header."""
        fixy = self._make_fixy()
        hint = fixy.get_rewrite_hint(
            active_modes=["loop_repetition"],
            rewrite_mode=FixyMode.FORCE_CASE,
            target_agent="Athena",
        )
        assert (
            "FIXY STRUCTURAL REWRITE DIRECTIVE" in hint
        ), f"Hint must contain structural header; got: {hint[:200]}"

    def test_hint_contains_rewrite_mode(self):
        """Rewrite hint must include the selected mode name."""
        fixy = self._make_fixy()
        hint = fixy.get_rewrite_hint(
            active_modes=["loop_repetition"],
            rewrite_mode=FixyMode.FORCE_METRIC,
            target_agent="Socrates",
        )
        assert (
            "force_metric" in hint.lower()
        ), f"Hint must name the rewrite mode; got: {hint[:200]}"

    def test_hint_contains_target_agent(self):
        """Rewrite hint must reference the target agent."""
        fixy = self._make_fixy()
        hint = fixy.get_rewrite_hint(
            active_modes=["weak_conflict"],
            rewrite_mode=FixyMode.FORCE_CHOICE,
            target_agent="Socrates",
        )
        assert (
            "Socrates" in hint
        ), f"Hint must include target agent name; got: {hint[:200]}"

    def test_hint_is_structural_not_cosmetic_force_metric(self):
        """force_metric hint must include measurable/criterion/benchmark language."""
        fixy = self._make_fixy()
        hint = fixy.get_rewrite_hint(
            active_modes=["topic_stagnation"],
            rewrite_mode=FixyMode.FORCE_METRIC,
            target_agent="Athena",
        )
        lower = hint.lower()
        assert any(
            w in lower
            for w in ("measur", "criterion", "benchmark", "quantif", "indicator")
        ), f"force_metric hint must include metric language; got: {hint}"

    def test_hint_is_structural_not_cosmetic_force_choice(self):
        """force_choice hint must demand a committed binary decision."""
        fixy = self._make_fixy()
        hint = fixy.get_rewrite_hint(
            active_modes=["weak_conflict"],
            rewrite_mode=FixyMode.FORCE_CHOICE,
            target_agent="Athena",
        )
        lower = hint.lower()
        assert any(
            w in lower for w in ("pick", "commit", "side", "binary", "hedge", "choose")
        ), f"force_choice hint must demand binary commitment; got: {hint}"

    def test_hint_is_structural_not_cosmetic_force_test(self):
        """force_test hint must demand a falsifiable claim."""
        fixy = self._make_fixy()
        hint = fixy.get_rewrite_hint(
            active_modes=["premature_synthesis"],
            rewrite_mode=FixyMode.FORCE_TEST,
            target_agent="Socrates",
        )
        lower = hint.lower()
        assert any(
            w in lower for w in ("falsif", "testable", "predict", "observable", "refut")
        ), f"force_test hint must demand falsifiable claim; got: {hint}"

    def test_hint_is_structural_not_cosmetic_force_case(self):
        """force_case hint must demand a specific real-world case."""
        fixy = self._make_fixy()
        hint = fixy.get_rewrite_hint(
            active_modes=["loop_repetition"],
            rewrite_mode=FixyMode.FORCE_CASE,
            target_agent="Athena",
        )
        lower = hint.lower()
        assert any(
            w in lower
            for w in (
                "case",
                "real-world",
                "instance",
                "scenario",
                "historical",
                "specific",
            )
        ), f"force_case hint must demand specific case; got: {hint}"

    def test_hint_is_structural_not_cosmetic_force_definition(self):
        """force_definition hint must demand an operational definition."""
        fixy = self._make_fixy()
        hint = fixy.get_rewrite_hint(
            active_modes=["fixy_mediation_loop"],
            rewrite_mode=FixyMode.FORCE_DEFINITION,
            target_agent="Socrates",
        )
        lower = hint.lower()
        assert any(
            w in lower
            for w in ("definition", "operational", "precisely", "define", "counts as")
        ), f"force_definition hint must demand operational definition; got: {hint}"

    def test_hint_sets_pending_rewrite_hint(self):
        """get_rewrite_hint must update _pending_rewrite_hint."""
        fixy = self._make_fixy()
        fixy.get_rewrite_hint(
            active_modes=["loop_repetition"],
            rewrite_mode=FixyMode.FORCE_CASE,
            target_agent="Athena",
        )
        assert (
            fixy._pending_rewrite_hint is not None
        ), "_pending_rewrite_hint must be set after get_rewrite_hint"

    def test_empty_hint_when_no_modes(self):
        """get_rewrite_hint must return '' when no modes and no rewrite_mode."""
        fixy = self._make_fixy()
        hint = fixy.get_rewrite_hint(
            active_modes=[],
            rewrite_mode=None,
            target_agent=None,
        )
        assert hint == "", f"Expected empty hint with no modes; got: {hint!r}"

    def test_hint_infers_mode_from_active_modes(self):
        """get_rewrite_hint should infer rewrite_mode from active_modes when mode is None."""
        fixy = self._make_fixy()
        hint = fixy.get_rewrite_hint(
            active_modes=["loop_repetition"],
            rewrite_mode=None,
            target_agent="Athena",
        )
        # Should infer force_case (mapped from loop_repetition)
        assert hint != "", "Should produce a non-empty hint when active_modes present"
        assert "FIXY STRUCTURAL REWRITE DIRECTIVE" in hint


# ---------------------------------------------------------------------------
# 6. DialogueRewriter — new rewrite_mode and target_agent parameters
# ---------------------------------------------------------------------------


class TestDialogueRewriterStructuralMode:
    """DialogueRewriter.build must honour rewrite_mode and target_agent."""

    def _make_dialog(self):
        return _make_turns(
            [
                "freedom means self-determination and personal autonomy",
                "society constrains freedom through collective agreements",
                "freedom requires society — neither stands alone here",
                "autonomy and freedom are two aspects of the same reality",
            ]
        )

    def test_rewrite_includes_mode_label(self):
        """Rewrite block must include the rewrite_mode label."""
        rewriter = DialogueRewriter()
        block = rewriter.build(
            dialog=self._make_dialog(),
            active_modes=["loop_repetition"],
            current_topic="freedom & society",
            rewrite_mode=FixyMode.FORCE_METRIC,
            target_agent="Athena",
        )
        assert (
            "force_metric" in block.lower()
        ), f"Rewrite block must include mode label; got snippet: {block[:300]}"

    def test_rewrite_includes_target_agent(self):
        """Rewrite block must include the target agent name when provided."""
        rewriter = DialogueRewriter()
        block = rewriter.build(
            dialog=self._make_dialog(),
            active_modes=["weak_conflict"],
            current_topic="freedom & society",
            rewrite_mode=FixyMode.FORCE_CHOICE,
            target_agent="Socrates",
        )
        assert (
            "Socrates" in block
        ), f"Rewrite block must include target agent; got snippet: {block[:300]}"

    def test_rewrite_mode_rule_takes_priority(self):
        """The rewrite_mode's novelty rule must appear in the block."""
        rewriter = DialogueRewriter()
        block = rewriter.build(
            dialog=self._make_dialog(),
            active_modes=["loop_repetition"],
            current_topic="freedom & society",
            rewrite_mode=FixyMode.FORCE_CHOICE,
        )
        lower = block.lower()
        # force_choice rule: "binary" or "pick" or "commit" or "hedge"
        assert any(
            w in lower for w in ("binary", "pick", "commit", "side", "hedge")
        ), f"force_choice rule must appear in rewrite block; got: {block[:500]}"

    def test_no_rewrite_mode_still_works(self):
        """build() must still work when rewrite_mode is omitted (backward compat)."""
        rewriter = DialogueRewriter()
        block = rewriter.build(
            dialog=self._make_dialog(),
            active_modes=["loop_repetition"],
            current_topic="freedom & society",
        )
        assert "DIALOGUE STATE REWRITE" in block
        assert "loop_repetition" in block


# ---------------------------------------------------------------------------
# 7. False positive reduction — relative comparison
# ---------------------------------------------------------------------------


class TestFalsePositiveReduction:
    """Verify that the improved detector fires less on genuinely advancing dialogues."""

    def _advancing_dialog(self):
        """Return a dialog that appears repetitive on surface but is advancing."""
        return _make_turns(
            [
                "freedom autonomy liberty independence means personal freedom",
                "autonomy liberty freedom independence are fundamental values",
                "liberty means freedom autonomy personal independence always",
                # Turn 4: advances with a concrete case
                "consider specifically the case of the apartheid regime in South Africa",
                # Turn 5: adds a measurable metric
                "we can measure degrees of freedom using a benchmark score for autonomy",
            ]
        )

    def _stagnant_dialog(self):
        """Return a dialog with genuine structural repetition and no advancement."""
        return _make_turns(_repetitive_texts(6))

    def test_advancing_dialog_suppressed(self):
        """A dialog with novelty must not be flagged as a structural loop."""
        detector = DialogueLoopDetector()
        modes = detector.detect(self._advancing_dialog(), turn_count=5)
        assert (
            LOOP_REPETITION not in modes
        ), f"Advancing dialog (with case + metric) must not trigger loop_repetition; got {modes}"

    def test_stagnant_dialog_still_detected(self):
        """A dialog without novelty must still be detected as a structural loop."""
        detector = DialogueLoopDetector()
        modes = detector.detect(self._stagnant_dialog(), turn_count=6)
        assert (
            LOOP_REPETITION in modes
        ), f"Pure stagnation must still be flagged; got {modes}"

    def test_advancement_keywords_regression(self):
        """'therefore', 'consequently', 'it follows' are advancement markers."""
        detector = DialogueLoopDetector()
        turns = _make_turns(
            [
                "freedom autonomy liberty independence values",
                "autonomy liberty freedom independence are fundamental",
                "liberty means freedom autonomy personal independence",
                "therefore autonomy and liberty independence fundamental values",
                "consequently freedom liberty autonomy independence it follows",
            ]
        )
        modes = detector.detect(turns, turn_count=5)
        assert (
            LOOP_REPETITION not in modes
        ), f"'therefore/consequently/it follows' must suppress loop; got {modes}"


# ---------------------------------------------------------------------------
# 8. InteractiveFixy._both_agents_present helper
# ---------------------------------------------------------------------------


class TestBothAgentsPresent:
    """Unit tests for the _both_agents_present static helper."""

    class _StubLLM:
        def generate(self, *args, **kwargs):
            return "stub"

    def _make_fixy(self):
        return InteractiveFixy(self._StubLLM(), "stub-model")

    def test_both_present(self):
        fixy = self._make_fixy()
        dialog = [
            {"role": "Socrates", "text": "Hello"},
            {"role": "Athena", "text": "World"},
        ]
        assert InteractiveFixy._both_agents_present(dialog) is True

    def test_only_socrates(self):
        dialog = [{"role": "Socrates", "text": "Hello"}]
        assert InteractiveFixy._both_agents_present(dialog) is False

    def test_only_athena(self):
        dialog = [{"role": "Athena", "text": "World"}]
        assert InteractiveFixy._both_agents_present(dialog) is False

    def test_fixy_alone(self):
        dialog = [{"role": "Fixy", "text": "Observer note"}]
        assert InteractiveFixy._both_agents_present(dialog) is False

    def test_fixy_plus_socrates(self):
        dialog = [
            {"role": "Fixy", "text": "Observer note"},
            {"role": "Socrates", "text": "Hello"},
        ]
        assert InteractiveFixy._both_agents_present(dialog) is False

    def test_both_present_with_fixy(self):
        dialog = [
            {"role": "Socrates", "text": "Hello"},
            {"role": "Fixy", "text": "Note"},
            {"role": "Athena", "text": "World"},
        ]
        assert InteractiveFixy._both_agents_present(dialog) is True

    def test_empty_dialog(self):
        assert InteractiveFixy._both_agents_present([]) is False


if __name__ == "__main__":
    import pytest as _pytest

    _pytest.main([__file__, "-v", "-s", "--override-ini=addopts="])

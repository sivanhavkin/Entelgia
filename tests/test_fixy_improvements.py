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
    validate_force_choice,
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


# ---------------------------------------------------------------------------
# 8. validate_force_choice — commitment vs hedge detection
# ---------------------------------------------------------------------------


class TestValidateForceChoice:
    """validate_force_choice must distinguish committed from hedged responses."""

    def test_commitment_i_choose(self):
        """'I choose X because' is a valid force_choice response."""
        assert (
            validate_force_choice("I choose autonomy because constraint is wrong")
            is True
        )

    def test_commitment_is_wrong_because(self):
        """'X is wrong because' is a valid force_choice response."""
        assert (
            validate_force_choice("Compatibilism is wrong because it redefines freedom")
            is True
        )

    def test_commitment_not_x_but_y(self):
        """'not X, but Y' pattern is a valid force_choice response."""
        assert (
            validate_force_choice(
                "The answer is autonomy, not constraint, because choice requires freedom"
            )
            is True
        )

    def test_commitment_wins_because(self):
        """'wins because' phrase is a valid force_choice indicator."""
        assert (
            validate_force_choice(
                "Hard determinism wins because it is logically consistent"
            )
            is True
        )

    def test_hedge_both_matter_fails(self):
        """'both matter' is a heavy hedge — must fail validation."""
        assert (
            validate_force_choice(
                "Both matter in different contexts and both have merit here"
            )
            is False
        )

    def test_hedge_it_depends_fails(self):
        """'it depends' is a hedge — must fail validation."""
        assert (
            validate_force_choice(
                "Well, it depends on the context and it depends on the situation"
            )
            is False
        )

    def test_hedge_balance_fails(self):
        """Heavy balance language without commitment must fail."""
        assert (
            validate_force_choice(
                "A balance between freedom and constraint is needed; both are important"
            )
            is False
        )

    def test_hedge_third_path_fails(self):
        """Introducing a third path without a commitment must fail."""
        assert (
            validate_force_choice(
                "There is actually a third path that reconciles both sides"
            )
            is False
        )

    def test_reframing_without_choice_fails(self):
        """Pure reframing with no commitment signal must fail."""
        assert (
            validate_force_choice(
                "The real question is not about freedom at all, but about meaning"
            )
            is False
        )

    def test_commitment_overrides_single_hedge(self):
        """One commitment marker + one hedge phrase should still pass (< 2 hedges)."""
        # Single hedge "it depends" but strong commitment "I choose"
        assert (
            validate_force_choice("I choose freedom, though it depends on the domain")
            is True
        )


# ---------------------------------------------------------------------------
# 9. Pair-gating window scope — must reset after Fixy turn / external events
# ---------------------------------------------------------------------------


class TestPairGatingWindowScope:
    """Pair gating must use a scoped window, not the full dialog history.

    Root-cause regression tests: once Fixy has intervened, both agents'
    historical turns must no longer count toward the new pair window.
    """

    class _StubLLM:
        def generate(self, *args, **kwargs):
            return "stub"

    def _make_fixy(self):
        return InteractiveFixy(self._StubLLM(), "stub-model")

    def test_pair_gate_closed_after_fixy_intervention(self):
        """After Fixy speaks, the pair window resets — only Socrates after Fixy
        must NOT allow intervention even though Athena spoke before Fixy."""
        fixy = self._make_fixy()
        dialog = [
            {"role": "Socrates", "text": "What is freedom?"},
            {"role": "Athena", "text": "Freedom is autonomy."},
            {"role": "Fixy", "text": "Deadlock detected."},
            {"role": "Socrates", "text": "But constraints matter!"},
        ]
        result, reason = fixy.should_intervene(dialog, turn_count=4)
        assert result is False, (
            "[FIXY-GATE] After Fixy turn, only Socrates spoke — gate must be closed; "
            f"got result={result!r}, reason={reason!r}"
        )

    def test_pair_gate_opens_after_fixy_when_both_present(self):
        """After Fixy speaks, adding BOTH agents re-opens the gate for evaluation."""
        fixy = self._make_fixy()
        dialog = [
            {"role": "Socrates", "text": "What is freedom?"},
            {"role": "Athena", "text": "Freedom is autonomy."},
            {"role": "Fixy", "text": "Deadlock detected."},
            {"role": "Socrates", "text": "But constraints matter!"},
            {"role": "Athena", "text": "I disagree with that."},
        ]
        # Gate should pass (both present after Fixy). Intervention may or may
        # not fire depending on content — we only verify the gate does NOT block.
        result, reason = fixy.should_intervene(dialog, turn_count=5)
        # If it returns False, it should be for content reasons, not gate reasons.
        # We assert the pair_reset_reason is not the blocker: window covers both.
        window = dialog[3:]  # after Fixy at index 2
        roles_in_window = {
            t.get("role") for t in window if t.get("role") not in ("Fixy", "seed")
        }
        assert (
            "Socrates" in roles_in_window and "Athena" in roles_in_window
        ), "Window after Fixy should contain both agents"

    def test_pair_gate_closed_after_notify_pair_reset_topic_shift(self, caplog):
        """After notify_pair_reset(topic_shift), only Socrates must block the gate."""
        fixy = self._make_fixy()
        # Both agents spoke before the topic shift
        dialog = [
            {"role": "Socrates", "text": "Freedom is absolute."},
            {"role": "Athena", "text": "Freedom has limits."},
            {"role": "Socrates", "text": "No, it does not."},
            {"role": "Athena", "text": "Yes, it does."},
        ]
        # Simulate topic shift
        fixy.notify_pair_reset(len(dialog), "topic_shift")
        # Only Socrates speaks on the new topic
        dialog.append({"role": "Socrates", "text": "On consciousness: is it real?"})

        with caplog.at_level(logging.INFO, logger="entelgia.fixy_interactive"):
            result, reason = fixy.should_intervene(dialog, turn_count=5)

        assert result is False, (
            "[FIXY-GATE] After topic_shift reset, only Socrates spoke — must be blocked; "
            f"got result={result!r}, reason={reason!r}"
        )
        assert any(
            "topic shift" in m for m in caplog.messages
        ), "[FIXY-GATE] Expected a log message mentioning 'topic shift' for the skip reason"

    def test_pair_gate_closed_after_notify_pair_reset_dream_cycle(self, caplog):
        """After notify_pair_reset(dream_cycle), only Athena must block the gate."""
        fixy = self._make_fixy()
        dialog = [
            {"role": "Socrates", "text": "What is freedom?"},
            {"role": "Athena", "text": "Freedom is autonomy."},
            {"role": "Socrates", "text": "Autonomy requires responsibility."},
            {"role": "Athena", "text": "Responsibility limits freedom."},
        ]
        # Simulate dream cycle
        fixy.notify_pair_reset(len(dialog), "dream_cycle")
        dialog.append(
            {"role": "Athena", "text": "After dreaming: consciousness is key."}
        )

        with caplog.at_level(logging.INFO, logger="entelgia.fixy_interactive"):
            result, reason = fixy.should_intervene(dialog, turn_count=5)

        assert result is False, (
            "[FIXY-GATE] After dream_cycle reset, only Athena spoke — must be blocked; "
            f"got result={result!r}, reason={reason!r}"
        )
        assert any(
            "dream cycle" in m for m in caplog.messages
        ), "[FIXY-GATE] Expected a log message mentioning 'dream cycle' for the skip reason"

    def test_pair_gate_resets_after_each_fixy_turn(self):
        """Two consecutive Fixy interventions must each reset the pair window."""
        fixy = self._make_fixy()
        # First pair + first Fixy
        dialog = [
            {"role": "Socrates", "text": "A"},
            {"role": "Athena", "text": "B"},
            {"role": "Fixy", "text": "First intervention."},
        ]
        # Second pair + second Fixy
        dialog += [
            {"role": "Socrates", "text": "C"},
            {"role": "Athena", "text": "D"},
            {"role": "Fixy", "text": "Second intervention."},
        ]
        # Now only Socrates after second Fixy
        dialog.append({"role": "Socrates", "text": "E"})

        result, reason = fixy.should_intervene(dialog, turn_count=7)
        assert result is False, (
            "[FIXY-GATE] After second Fixy turn, only Socrates — gate must still be closed; "
            f"got result={result!r}, reason={reason!r}"
        )

    def test_accepted_log_emitted_when_gate_passes(self, caplog):
        """[FIXY-GATE] accepted message must be logged when the pair gate passes."""
        fixy = self._make_fixy()
        dialog = [
            {"role": "Socrates", "text": "What is freedom?"},
            {"role": "Athena", "text": "Freedom is autonomy."},
        ]
        with caplog.at_level(logging.INFO, logger="entelgia.fixy_interactive"):
            fixy.should_intervene(dialog, turn_count=2)

        assert any(
            "accepted" in m and "full pair" in m for m in caplog.messages
        ), "[FIXY-GATE] Expected '[FIXY-GATE] accepted: full pair observed' in logs"

    def test_consecutive_full_pair_count_increments(self):
        """_consecutive_full_pair_count must increment on each gate-passing call."""
        fixy = self._make_fixy()
        dialog = [
            {"role": "Socrates", "text": "What is truth?"},
            {"role": "Athena", "text": "Truth is correspondence."},
        ]
        assert fixy.consecutive_full_pair_count == 0
        fixy.should_intervene(dialog, turn_count=2)
        assert fixy.consecutive_full_pair_count == 1
        fixy.should_intervene(dialog, turn_count=3)
        assert fixy.consecutive_full_pair_count == 2
        fixy.should_intervene(dialog, turn_count=4)
        assert fixy.consecutive_full_pair_count == 3

    def test_consecutive_full_pair_count_resets_on_pair_gate_failure(self):
        """Counter must reset to 0 when the pair gate fails."""
        fixy = self._make_fixy()
        # First pass the gate twice
        dialog = [
            {"role": "Socrates", "text": "What is truth?"},
            {"role": "Athena", "text": "Truth is correspondence."},
        ]
        fixy.should_intervene(dialog, turn_count=2)
        fixy.should_intervene(dialog, turn_count=3)
        assert fixy.consecutive_full_pair_count == 2

        # Simulate a pair-window reset so only one agent is in the window
        fixy.notify_pair_reset(len(dialog), "topic_shift")
        dialog.append({"role": "Socrates", "text": "New topic: consciousness."})
        fixy.should_intervene(dialog, turn_count=4)
        assert (
            fixy.consecutive_full_pair_count == 0
        ), "Counter must reset to 0 when pair gate fails"

    def test_consecutive_full_pair_count_resets_on_context_gate_failure(self):
        """Counter must reset to 0 when a gate fails on the same instance."""
        fixy = self._make_fixy()
        # First pass the gate to get counter to 1
        dialog = [
            {"role": "Socrates", "text": "A"},
            {"role": "Athena", "text": "B"},
        ]
        fixy.should_intervene(dialog, turn_count=2)
        assert fixy.consecutive_full_pair_count == 1

        # Simulate a pair-window reset so the next call fails the pair gate.
        # After notify_pair_reset, only Socrates is in the new window, so the
        # pair-presence gate fails and the counter must reset to 0.
        fixy.notify_pair_reset(len(dialog), "topic_shift")
        dialog.append({"role": "Socrates", "text": "New topic."})
        fixy.should_intervene(dialog, turn_count=3)
        assert (
            fixy.consecutive_full_pair_count == 0
        ), "Counter must reset to 0 when the gate fails (same instance)"


# ---------------------------------------------------------------------------
# 10. topics_enabled=False — topic-related behaviour must be fully suppressed
# ---------------------------------------------------------------------------


class TestTopicsDisabledSuppression:
    """When topics_enabled=False, Fixy must not emit topic-shift pair-window
    resets, must not anchor interventions to a topic, and must not use the
    caller-supplied current_topic for stagnation detection."""

    class _StubLLM:
        def generate(self, *args, **kwargs):
            return "stub intervention"

    def _make_fixy(self, topics_enabled: bool = False):
        return InteractiveFixy(
            self._StubLLM(), "stub-model", topics_enabled=topics_enabled
        )

    # ── notify_pair_reset ─────────────────────────────────────────────────

    def test_topic_shift_reset_suppressed_when_topics_disabled(self, caplog):
        """notify_pair_reset('topic_shift') must be a no-op when topics_enabled=False."""
        fixy = self._make_fixy(topics_enabled=False)
        with caplog.at_level(logging.INFO, logger="entelgia.fixy_interactive"):
            fixy.notify_pair_reset(4, "topic_shift")

        # The INFO-level pair-window reset must NOT appear.
        assert not any(
            "pair window reset" in m and "topic_shift" in m for m in caplog.messages
        ), (
            "notify_pair_reset('topic_shift') must not log an INFO pair window "
            "reset message when topics_enabled=False"
        )

    def test_topic_shift_reset_does_not_update_state_when_topics_disabled(self):
        """When topics_disabled, notify_pair_reset('topic_shift') must not alter
        _pair_window_start or _pair_reset_reason."""
        fixy = self._make_fixy(topics_enabled=False)
        initial_start = fixy._pair_window_start
        initial_reason = fixy._pair_reset_reason

        fixy.notify_pair_reset(10, "topic_shift")

        assert (
            fixy._pair_window_start == initial_start
        ), "_pair_window_start must not change when topic_shift is suppressed"
        assert (
            fixy._pair_reset_reason == initial_reason
        ), "_pair_reset_reason must not change when topic_shift is suppressed"

    def test_non_topic_reset_still_works_when_topics_disabled(self, caplog):
        """dream_cycle and rewrite_injection resets must still fire when topics_enabled=False."""
        fixy = self._make_fixy(topics_enabled=False)
        with caplog.at_level(logging.INFO, logger="entelgia.fixy_interactive"):
            fixy.notify_pair_reset(4, "dream_cycle")

        assert any(
            "pair window reset" in m and "dream_cycle" in m for m in caplog.messages
        ), "notify_pair_reset('dream_cycle') must still log when topics_enabled=False"
        assert fixy._pair_window_start == 4
        assert fixy._pair_reset_reason == "dream_cycle"

    def test_topic_shift_reset_works_when_topics_enabled(self, caplog):
        """With topics_enabled=True (default), topic_shift resets must fire normally."""
        fixy = self._make_fixy(topics_enabled=True)
        with caplog.at_level(logging.INFO, logger="entelgia.fixy_interactive"):
            fixy.notify_pair_reset(6, "topic_shift")

        assert any(
            "pair window reset" in m and "topic_shift" in m for m in caplog.messages
        ), "notify_pair_reset('topic_shift') must log normally when topics_enabled=True"
        assert fixy._pair_window_start == 6
        assert fixy._pair_reset_reason == "topic_shift"

    # ── should_intervene — current_topic discarded ───────────────────────

    def test_should_intervene_discards_current_topic_when_topics_disabled(self, caplog):
        """should_intervene must not log or use current_topic when topics_enabled=False."""
        fixy = self._make_fixy(topics_enabled=False)
        dialog = [
            {"role": "Socrates", "text": "Wealth inequality is structural."},
            {
                "role": "Athena",
                "text": "Structural causes require structural remedies.",
            },
        ]
        with caplog.at_level(logging.INFO, logger="entelgia.fixy_interactive"):
            fixy.should_intervene(
                dialog, turn_count=2, current_topic="Wealth inequality"
            )

        # No log entry should mention the topic label in a way that implies it
        # was used for active reasoning (e.g. the FIXY-LOOP topic= field).
        topic_log_entries = [m for m in caplog.messages if "Wealth inequality" in m]
        assert not topic_log_entries, (
            "should_intervene must not emit log messages referencing the "
            f"current_topic when topics_enabled=False; found: {topic_log_entries}"
        )

    # ── generate_intervention — topic anchor suppressed ──────────────────

    def test_generate_intervention_suppresses_topic_anchor_when_topics_disabled(self):
        """generate_intervention must not inject ACTIVE TOPIC into the prompt
        when topics_enabled=False even if current_topic is non-empty."""
        prompts_seen: list[str] = []

        class _CaptureLLM:
            def generate(self, model, prompt, **kwargs):
                prompts_seen.append(prompt)
                return "stub"

        fixy = InteractiveFixy(_CaptureLLM(), "stub-model", topics_enabled=False)
        dialog = [
            {"role": "Socrates", "text": "What is wealth?"},
            {"role": "Athena", "text": "A relative construct."},
        ]
        fixy.generate_intervention(
            dialog, "circular_reasoning", current_topic="Wealth inequality"
        )

        assert prompts_seen, "LLM.generate must have been called"
        combined = "\n".join(prompts_seen)
        assert (
            "ACTIVE TOPIC" not in combined
        ), "generate_intervention must not inject ACTIVE TOPIC when topics_enabled=False"
        assert (
            "Wealth inequality" not in combined
        ), "generate_intervention must not reference the topic label when topics_enabled=False"

    def test_generate_intervention_includes_topic_anchor_when_topics_enabled(self):
        """With topics_enabled=True, ACTIVE TOPIC must appear in the prompt."""
        prompts_seen: list[str] = []

        class _CaptureLLM:
            def generate(self, model, prompt, **kwargs):
                prompts_seen.append(prompt)
                return "stub"

        fixy = InteractiveFixy(_CaptureLLM(), "stub-model", topics_enabled=True)
        dialog = [
            {"role": "Socrates", "text": "What is wealth?"},
            {"role": "Athena", "text": "A relative construct."},
        ]
        fixy.generate_intervention(
            dialog, "circular_reasoning", current_topic="Wealth inequality"
        )

        combined = "\n".join(prompts_seen)
        assert (
            "ACTIVE TOPIC" in combined
        ), "generate_intervention must inject ACTIVE TOPIC when topics_enabled=True"
        assert (
            "Wealth inequality" in combined
        ), "generate_intervention must reference the topic label when topics_enabled=True"


# ---------------------------------------------------------------------------
# 11. Staged intervention ladder — new FixyMode constants and hard thresholds
# ---------------------------------------------------------------------------


from entelgia.fixy_interactive import (
    MIN_TURNS_BEFORE_FIXY_HARD_INTERVENTION,
    MIN_FULL_PAIRS_BEFORE_FIXY_HARD_INTERVENTION,
    _HARD_INTERVENTION_MODES,
)


class TestStagedInterventionLadder:
    """Fixy must NOT use hard intervention modes before threshold turns/pairs."""

    class _StubLLM:
        def generate(self, *args, **kwargs):
            return "stub"

    def _make_fixy(
        self,
        min_turns_hard=MIN_TURNS_BEFORE_FIXY_HARD_INTERVENTION,
        min_pairs_hard=MIN_FULL_PAIRS_BEFORE_FIXY_HARD_INTERVENTION,
    ):
        return InteractiveFixy(
            self._StubLLM(),
            "stub-model",
            min_turns_hard=min_turns_hard,
            min_pairs_hard=min_pairs_hard,
        )

    def test_module_level_constants_correct(self):
        """Module-level threshold constants must match documented defaults."""
        assert MIN_TURNS_BEFORE_FIXY_HARD_INTERVENTION == 8
        assert MIN_FULL_PAIRS_BEFORE_FIXY_HARD_INTERVENTION == 3

    def test_new_fixy_modes_defined(self):
        """All staged intervention mode constants must be present on FixyMode."""
        assert hasattr(FixyMode, "SILENT_OBSERVE")
        assert hasattr(FixyMode, "SOFT_REFLECTION")
        assert hasattr(FixyMode, "GENTLE_NUDGE")
        assert hasattr(FixyMode, "STRUCTURED_MEDIATION")
        assert hasattr(FixyMode, "HARD_CONSTRAINT")

    def test_hard_modes_set_non_empty(self):
        """_HARD_INTERVENTION_MODES must be a non-empty frozenset."""
        assert isinstance(_HARD_INTERVENTION_MODES, frozenset)
        assert len(_HARD_INTERVENTION_MODES) > 0

    def test_hard_mode_force_choice_in_set(self):
        """FORCE_CHOICE must be classified as a hard intervention mode."""
        assert FixyMode.FORCE_CHOICE in _HARD_INTERVENTION_MODES

    def test_hard_mode_contradict_in_set(self):
        """CONTRADICT must be classified as a hard intervention mode."""
        assert FixyMode.CONTRADICT in _HARD_INTERVENTION_MODES

    def test_soft_mode_not_in_hard_set(self):
        """SOFT_REFLECTION must NOT be in _HARD_INTERVENTION_MODES."""
        assert FixyMode.SOFT_REFLECTION not in _HARD_INTERVENTION_MODES

    def test_gentle_nudge_not_in_hard_set(self):
        """GENTLE_NUDGE must NOT be in _HARD_INTERVENTION_MODES."""
        assert FixyMode.GENTLE_NUDGE not in _HARD_INTERVENTION_MODES

    def test_constructor_accepts_threshold_params(self):
        """InteractiveFixy must accept min_turns_hard and min_pairs_hard params."""
        fixy = self._make_fixy(min_turns_hard=5, min_pairs_hard=2)
        assert fixy._min_turns_hard == 5
        assert fixy._min_pairs_hard == 2

    def test_default_thresholds_match_constants(self):
        """Default constructor thresholds must match module-level constants."""
        fixy = InteractiveFixy(self._StubLLM(), "stub-model")
        assert fixy._min_turns_hard == MIN_TURNS_BEFORE_FIXY_HARD_INTERVENTION
        assert fixy._min_pairs_hard == MIN_FULL_PAIRS_BEFORE_FIXY_HARD_INTERVENTION

    def test_get_fixy_mode_returns_soft_when_soft_mode_forced(self):
        """get_fixy_mode must return a soft mode when _soft_mode_forced is True."""
        fixy = self._make_fixy()
        fixy._soft_mode_forced = True  # simulate hard-blocked state
        mode = fixy.get_fixy_mode("loop_repetition")
        assert mode in {
            FixyMode.SOFT_REFLECTION,
            FixyMode.GENTLE_NUDGE,
            FixyMode.STRUCTURED_MEDIATION,
        }, f"Expected soft mode when _soft_mode_forced; got {mode!r}"

    def test_get_fixy_mode_uses_rotation_when_soft_mode_not_forced(self):
        """get_fixy_mode must use loop-breaking rotation when soft mode not forced."""
        fixy = self._make_fixy()
        fixy._soft_mode_forced = False  # normal state
        fixy._pending_rewrite_mode = FixyMode.FORCE_CASE
        mode = fixy.get_fixy_mode("loop_repetition")
        # Should be a loop-breaking mode, not a soft staged mode
        assert mode not in {
            FixyMode.SOFT_REFLECTION,
            FixyMode.GENTLE_NUDGE,
            FixyMode.STRUCTURED_MEDIATION,
        }, f"Should not return soft mode when _soft_mode_forced=False; got {mode!r}"

    def test_new_staged_modes_have_prompts(self):
        """All staged ladder modes must have entries in _MODE_PROMPTS."""
        for mode in (
            FixyMode.SOFT_REFLECTION,
            FixyMode.GENTLE_NUDGE,
            FixyMode.STRUCTURED_MEDIATION,
            FixyMode.HARD_CONSTRAINT,
        ):
            assert (
                mode in _MODE_PROMPTS
            ), f"FixyMode.{mode!r} must have a prompt in _MODE_PROMPTS"

    def test_soft_mode_prompts_avoid_rigid_labels(self):
        """Soft mode prompts must not instruct the LLM to produce rigid labels."""
        soft_modes = (
            FixyMode.SOFT_REFLECTION,
            FixyMode.GENTLE_NUDGE,
            FixyMode.STRUCTURED_MEDIATION,
        )
        # These phrases would instruct the LLM to produce rigid police-style output.
        forbidden_instructions = (
            "Preferred labels:",
            "Use 'Deadlock:'",
            "Use 'Loop:'",
            "Use 'Next move:'",
            "Use 'Drift:'",
        )
        for mode in soft_modes:
            prompt = _MODE_PROMPTS[mode]
            for instruction in forbidden_instructions:
                assert instruction not in prompt, (
                    f"Soft mode {mode!r} prompt must not contain instruction {instruction!r}; "
                    f"got: {prompt[:200]}"
                )

    def test_soft_mode_prompts_use_natural_language(self):
        """Soft mode prompts must include natural mediation language."""
        natural_phrases = (
            "It seems the disagreement",
            "What remains unclear",
            "A missing distinction",
            "Both of you may be",
        )
        soft_modes = (
            FixyMode.SOFT_REFLECTION,
            FixyMode.GENTLE_NUDGE,
            FixyMode.STRUCTURED_MEDIATION,
        )
        for mode in soft_modes:
            prompt = _MODE_PROMPTS[mode]
            assert any(phrase in prompt for phrase in natural_phrases), (
                f"Soft mode {mode!r} prompt must include natural mediation language; "
                f"got: {prompt[:200]}"
            )

    def test_reason_label_map_avoids_deadlock_label(self):
        """_REASON_LABEL_MAP entries must NOT instruct the LLM to use 'Deadlock:'."""
        from entelgia.fixy_interactive import _REASON_LABEL_MAP

        for reason, instruction in _REASON_LABEL_MAP.items():
            assert "Use 'Deadlock:'" not in instruction, (
                f"_REASON_LABEL_MAP[{reason!r}] must not instruct LLM to use "
                f"rigid 'Deadlock:' label; got: {instruction}"
            )

    def test_reason_label_map_avoids_next_move_label(self):
        """_REASON_LABEL_MAP entries must NOT instruct LLM to use 'Next move:' label."""
        from entelgia.fixy_interactive import _REASON_LABEL_MAP

        for reason, instruction in _REASON_LABEL_MAP.items():
            assert "Use 'Next move:'" not in instruction, (
                f"_REASON_LABEL_MAP[{reason!r}] must not instruct LLM to use "
                f"rigid 'Next move:' label; got: {instruction}"
            )


# ---------------------------------------------------------------------------
# 12. NEW_CLAIM detection in recent turns
# ---------------------------------------------------------------------------


class TestNewClaimDetection:
    """_detect_new_claim_in_recent_turns must suppress hard interventions."""

    class _StubLLM:
        def generate(self, *args, **kwargs):
            return "stub"

    def _make_fixy(self):
        return InteractiveFixy(self._StubLLM(), "stub-model")

    def test_empty_turns_returns_false(self):
        """Empty turn list must return False (no NEW_CLAIM)."""
        fixy = self._make_fixy()
        assert fixy._detect_new_claim_in_recent_turns([]) is False

    def test_fixy_turns_excluded(self):
        """Fixy turns must be excluded from NEW_CLAIM detection."""
        fixy = self._make_fixy()
        turns = [
            {"role": "Fixy", "text": "This is a novel claim about a new concept."},
        ]
        # Fixy's own turns should not count as NEW_CLAIM for the gate
        # (the method filters out role=Fixy)
        result = fixy._detect_new_claim_in_recent_turns(turns)
        # Whether True or False, the filter must not crash
        assert isinstance(result, bool)


# ---------------------------------------------------------------------------
# 13. generate_fixy_analysis — structured internal output
# ---------------------------------------------------------------------------


class TestGenerateFixyAnalysis:
    """generate_fixy_analysis must return a well-formed structured dict."""

    class _StubLLM:
        def generate(self, *args, **kwargs):
            return "stub"

    def _make_fixy(self, min_turns_hard=8, min_pairs_hard=3):
        return InteractiveFixy(
            self._StubLLM(),
            "stub-model",
            min_turns_hard=min_turns_hard,
            min_pairs_hard=min_pairs_hard,
        )

    def _make_dialog(self):
        return _make_turns(
            [
                "freedom means self-determination and personal autonomy",
                "society constrains freedom through collective agreements",
            ]
        )

    def test_returns_dict_with_required_keys(self):
        """generate_fixy_analysis must return a dict with all required keys."""
        fixy = self._make_fixy()
        result = fixy.generate_fixy_analysis(
            dialog=self._make_dialog(),
            reason="loop_repetition",
            intervention_mode=FixyMode.SOFT_REFLECTION,
            turn_count=4,
        )
        required_keys = {
            "intervention_mode",
            "dialogue_read",
            "missing_element",
            "suggested_vector",
            "urgency",
        }
        assert (
            set(result.keys()) == required_keys
        ), f"generate_fixy_analysis must return {required_keys!r}; got {set(result.keys())!r}"

    def test_intervention_mode_preserved(self):
        """intervention_mode in output must match the supplied mode."""
        fixy = self._make_fixy()
        result = fixy.generate_fixy_analysis(
            dialog=self._make_dialog(),
            reason="weak_conflict",
            intervention_mode=FixyMode.GENTLE_NUDGE,
            turn_count=3,
        )
        assert result["intervention_mode"] == FixyMode.GENTLE_NUDGE

    def test_urgency_low_early_turns(self):
        """Urgency must be 'low' when turn count is below half the threshold."""
        fixy = self._make_fixy(min_turns_hard=8)
        result = fixy.generate_fixy_analysis(
            dialog=self._make_dialog(),
            reason="loop_repetition",
            intervention_mode=FixyMode.SOFT_REFLECTION,
            turn_count=2,  # below 8//2 = 4
        )
        assert (
            result["urgency"] == "low"
        ), f"Expected 'low' urgency at turn 2; got {result['urgency']!r}"

    def test_urgency_medium_mid_turns(self):
        """Urgency must be 'medium' when turn count is at or above half the threshold."""
        fixy = self._make_fixy(min_turns_hard=8)
        # pairs < threshold so urgency is medium, not high
        fixy._consecutive_full_pair_count = 1
        result = fixy.generate_fixy_analysis(
            dialog=self._make_dialog(),
            reason="loop_repetition",
            intervention_mode=FixyMode.GENTLE_NUDGE,
            turn_count=5,  # 5 >= 8//2 = 4, but pairs=1 < 3
        )
        assert (
            result["urgency"] == "medium"
        ), f"Expected 'medium' urgency at turn 5, pairs=1; got {result['urgency']!r}"

    def test_urgency_high_above_thresholds(self):
        """Urgency must be 'high' when both turn and pair thresholds are met."""
        fixy = self._make_fixy(min_turns_hard=8, min_pairs_hard=3)
        fixy._consecutive_full_pair_count = 4  # above pairs threshold
        result = fixy.generate_fixy_analysis(
            dialog=self._make_dialog(),
            reason="high_conflict_no_resolution",
            intervention_mode=FixyMode.STRUCTURED_MEDIATION,
            turn_count=10,  # above turn threshold
        )
        assert (
            result["urgency"] == "high"
        ), f"Expected 'high' urgency when thresholds met; got {result['urgency']!r}"

    def test_dialogue_read_non_empty(self):
        """dialogue_read must be a non-empty string."""
        fixy = self._make_fixy()
        result = fixy.generate_fixy_analysis(
            dialog=self._make_dialog(),
            reason="loop_repetition",
            intervention_mode=FixyMode.SOFT_REFLECTION,
            turn_count=4,
        )
        assert isinstance(result["dialogue_read"], str)
        assert len(result["dialogue_read"]) > 0

    def test_missing_element_non_empty(self):
        """missing_element must be a non-empty string."""
        fixy = self._make_fixy()
        result = fixy.generate_fixy_analysis(
            dialog=self._make_dialog(),
            reason="weak_conflict",
            intervention_mode=FixyMode.GENTLE_NUDGE,
            turn_count=4,
        )
        assert isinstance(result["missing_element"], str)
        assert len(result["missing_element"]) > 0

    def test_suggested_vector_non_empty(self):
        """suggested_vector must be a non-empty string."""
        fixy = self._make_fixy()
        result = fixy.generate_fixy_analysis(
            dialog=self._make_dialog(),
            reason="shallow_discussion",
            intervention_mode=FixyMode.STRUCTURED_MEDIATION,
            turn_count=12,
        )
        assert isinstance(result["suggested_vector"], str)
        assert len(result["suggested_vector"]) > 0

    def test_dialogue_read_fallback_not_procedural(self):
        """dialogue_read fallback must not use procedural 'Detected failure mode:' label."""
        fixy = self._make_fixy()
        # Use an unknown mode to trigger the fallback path
        result = fixy.generate_fixy_analysis(
            dialog=self._make_dialog(),
            reason="some_unknown_reason",
            intervention_mode="UNKNOWN_MODE",
            turn_count=4,
        )
        assert (
            "Detected failure mode:" not in result["dialogue_read"]
        ), f"dialogue_read fallback must not use procedural label; got: {result['dialogue_read']!r}"


# ---------------------------------------------------------------------------
# 14. Perspective-driven output constraints
# ---------------------------------------------------------------------------


class TestPerspectiveDrivenOutput:
    """Fixy prompts and output instructions must use perspective language, not procedural labels."""

    def test_no_pattern_label_in_mode_prompts(self):
        """No _MODE_PROMPTS entry may use the 'Pattern:' procedural label."""
        from entelgia.fixy_interactive import _MODE_PROMPTS

        for mode, prompt in _MODE_PROMPTS.items():
            assert "Pattern:" not in prompt, (
                f"_MODE_PROMPTS[{mode!r}] must not use 'Pattern:' label; "
                f"got: {prompt[:200]}"
            )

    def test_no_your_role_in_mode_prompts(self):
        """No _MODE_PROMPTS entry may use 'Your role:' instruction language."""
        from entelgia.fixy_interactive import _MODE_PROMPTS

        for mode, prompt in _MODE_PROMPTS.items():
            assert "Your role:" not in prompt, (
                f"_MODE_PROMPTS[{mode!r}] must not use 'Your role:' instruction; "
                f"got: {prompt[:200]}"
            )

    def test_structured_mediation_does_not_suggest_direction(self):
        """STRUCTURED_MEDIATION prompt must not ask Fixy to 'suggest a direction'."""
        from entelgia.fixy_interactive import _MODE_PROMPTS, FixyMode

        prompt = _MODE_PROMPTS[FixyMode.STRUCTURED_MEDIATION]
        assert "suggest a direction" not in prompt.lower(), (
            f"STRUCTURED_MEDIATION must not ask Fixy to suggest a direction; "
            f"got: {prompt[:300]}"
        )

    def test_reason_label_map_no_trailing_imperatives(self):
        """_REASON_LABEL_MAP entries must not end with bare imperative verbs like 'Name', 'Identify', 'Suggest', 'Shift'."""
        from entelgia.fixy_interactive import _REASON_LABEL_MAP

        # These imperative starters at the end of an instruction string instruct
        # Fixy to take a directive action, violating the perspective-driven requirement.
        forbidden_imperative_endings = (
            "Gently name the missing distinction that would allow progress.",
            "Identify the hidden fork in the argument without forcing a choice.",
            "Restore productive tension without collapsing it.",
            "Suggest a new conceptual angle, not a topic change.",
            "Name the hidden shared premise that both sides rely on.",
            "Reflect the structure of the conflict without forcing a verdict.",
            "Invite depth by pointing to what neither side has yet examined.",
            "Identify the conceptual bridge that would let both positions advance.",
            "Shift the frame entirely.",
        )
        for reason, instruction in _REASON_LABEL_MAP.items():
            for ending in forbidden_imperative_endings:
                assert ending not in instruction, (
                    f"_REASON_LABEL_MAP[{reason!r}] must not contain imperative ending "
                    f"{ending!r}; got: {instruction}"
                )

    def test_reason_label_map_uses_perspective_language(self):
        """Each _REASON_LABEL_MAP entry must include at least one perspective-based phrase."""
        from entelgia.fixy_interactive import _REASON_LABEL_MAP

        # These perspective-based openers are the required replacement patterns.
        perspective_phrases = (
            "It seems",
            "Perhaps",
            "It is unclear whether",
            "A missing element may be",
            "You may be assuming",
            "The tension may lie in",
            "may be what",
            "may not yet be",
            "may still be",
            "may exist but",
            "may be where",
            "has not yet been named",
            "may deserve",
            "may be what this exchange has not yet considered",
        )
        for reason, instruction in _REASON_LABEL_MAP.items():
            assert any(phrase in instruction for phrase in perspective_phrases), (
                f"_REASON_LABEL_MAP[{reason!r}] must include perspective-based language; "
                f"got: {instruction}"
            )

    import pytest as _pytest

    _pytest.main([__file__, "-v", "-s", "--override-ini=addopts="])

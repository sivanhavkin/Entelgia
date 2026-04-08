#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Unit tests for entelgia/integration_core.py (ExecutiveCortex).

Covers:
  1. IntegrationState construction from raw dict (happy path + unknown keys)
  2. ControlDecision defaults
  3. Rule: loop + semantic_repeat -> CONCRETE_OVERRIDE
  4. Rule: semantic_repeat + stagnation -> PERSONALITY_SUPPRESSION
  5. Rule: unresolved + low progress -> REQUIRE_BRANCH_CLOSURE
  6. Rule: fatigue -> LOW_COMPLEXITY
  7. Rule: is_loop + compliance flags no longer trigger FIXY_AUTHORITY_OVERRIDE
     (that rule was removed; FIXY_AUTHORITY_OVERRIDE is deprecated)
  8. Rule: stagnation — REQUIRE_STRUCTURAL_CHALLENGE only when reasoning_delta is
     "moderate"/"strong"; generic stagnation without evidence → REQUIRE_FORCED_CHOICE
  9. Rule: pressure misalignment -> overlay injected, mode=NORMAL
  10. No override when all signals are nominal -> mode=NORMAL, no regen
  11. build_prompt_overlay returns decision.prompt_overlay
  12. should_regenerate returns True iff decision.regenerate is True
  13. Priority: CONCRETE_OVERRIDE beats REQUIRE_STRUCTURAL_CHALLENGE
  14. Priority: CONCRETE_OVERRIDE beats REQUIRE_STRUCTURAL_CHALLENGE (semantic_repeat+loop_count)
  15. make_integration_state factory helper
  16. evaluate_turn accepts state_dict directly (integration path)
  17. Overlay text is imperative (no "consider")
  18. FIXY_AUTHORITY_OVERRIDE is deprecated; enforce_fixy is not forced
"""

from __future__ import annotations

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

from entelgia.integration_core import (
    ControlDecision,
    IntegrationCore,
    IntegrationMode,
    IntegrationState,
    make_integration_state,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def core() -> IntegrationCore:
    return IntegrationCore()


def _nominal_signals() -> dict:
    """Signal dict with all values well within safe ranges."""
    return {
        "semantic_repeat": False,
        "structural_repeat": False,
        "loop_count": 0,
        "progress_after": 0.8,
        "unresolved": 0,
        "pressure": 3.0,
        "fatigue": 0.1,
        "stagnation": 0.0,
        "linguistic_score": 0.9,
        "dialogue_score": 0.8,
        "alignment": "aligned",
        "move_type": "NEW_CLAIM",
        "compliance": True,
        "is_loop": False,
        "abstraction_detected": False,
        "energy": 90.0,
        "status": "active",
    }


# ---------------------------------------------------------------------------
# 1. IntegrationState construction
# ---------------------------------------------------------------------------


class TestIntegrationStateConstruction:
    def test_from_nominal_dict(self):
        state = IntegrationCore._build_state("Socrates", _nominal_signals())
        assert state.agent_name == "Socrates"
        assert state.semantic_repeat is False
        assert state.loop_count == 0
        assert state.energy == 90.0

    def test_unknown_keys_are_silently_dropped(self):
        signals = _nominal_signals()
        signals["nonexistent_key"] = "should be ignored"
        # Should not raise
        state = IntegrationCore._build_state("Athena", signals)
        assert state.agent_name == "Athena"
        assert not hasattr(state, "nonexistent_key")

    def test_missing_keys_fall_back_to_defaults(self):
        state = IntegrationCore._build_state("Fixy", {})
        assert state.semantic_repeat is False
        assert state.loop_count == 0
        assert state.fatigue == 0.0
        assert state.compliance is True


# ---------------------------------------------------------------------------
# 2. ControlDecision defaults
# ---------------------------------------------------------------------------


class TestControlDecisionDefaults:
    def test_all_flags_default_false(self):
        d = ControlDecision()
        assert d.allow_response is True
        assert d.regenerate is False
        assert d.suppress_personality is False
        assert d.enforce_fixy is False
        assert d.force_concrete_mode is False
        assert d.force_resolution_mode is False
        assert d.force_attack_mode is False
        assert d.low_complexity_mode is False

    def test_default_mode_is_normal(self):
        d = ControlDecision()
        assert d.active_mode == IntegrationMode.NORMAL

    def test_default_priority_is_zero(self):
        d = ControlDecision()
        assert d.priority_level == 0


# ---------------------------------------------------------------------------
# 3. Rule: loop + semantic_repeat -> CONCRETE_OVERRIDE
# ---------------------------------------------------------------------------


class TestRuleLoopConcrete:
    def test_triggers_concrete_override(self, core):
        signals = _nominal_signals()
        signals["semantic_repeat"] = True
        signals["loop_count"] = 1
        decision = core.evaluate_turn("Socrates", signals)
        assert decision.active_mode == IntegrationMode.CONCRETE_OVERRIDE
        assert decision.force_concrete_mode is True

    def test_no_trigger_when_loop_count_zero(self, core):
        signals = _nominal_signals()
        signals["semantic_repeat"] = True
        signals["loop_count"] = 0
        decision = core.evaluate_turn("Socrates", signals)
        assert decision.active_mode != IntegrationMode.CONCRETE_OVERRIDE

    def test_no_trigger_without_semantic_repeat(self, core):
        signals = _nominal_signals()
        signals["semantic_repeat"] = False
        signals["loop_count"] = 3
        decision = core.evaluate_turn("Socrates", signals)
        assert decision.active_mode != IntegrationMode.CONCRETE_OVERRIDE


# ---------------------------------------------------------------------------
# 4. Rule: semantic_repeat + stagnation -> PERSONALITY_SUPPRESSION
# ---------------------------------------------------------------------------


class TestRulePersonalitySuppression:
    def test_triggers_personality_suppression(self, core):
        signals = _nominal_signals()
        signals["semantic_repeat"] = True
        signals["loop_count"] = 0  # loop_count < 1 so CONCRETE_OVERRIDE won't fire
        signals["stagnation"] = 0.30
        decision = core.evaluate_turn("Athena", signals)
        assert decision.active_mode == IntegrationMode.PERSONALITY_SUPPRESSION
        assert decision.suppress_personality is True

    def test_not_triggered_when_stagnation_below_threshold(self, core):
        signals = _nominal_signals()
        signals["semantic_repeat"] = True
        signals["loop_count"] = 0
        signals["stagnation"] = 0.10
        decision = core.evaluate_turn("Athena", signals)
        assert decision.active_mode != IntegrationMode.PERSONALITY_SUPPRESSION


# ---------------------------------------------------------------------------
# 5. Rule: unresolved + low progress -> REQUIRE_BRANCH_CLOSURE
# ---------------------------------------------------------------------------


class TestRuleResolutionOverride:
    def test_triggers_branch_closure(self, core):
        signals = _nominal_signals()
        signals["unresolved"] = 3
        signals["progress_after"] = 0.3
        decision = core.evaluate_turn("Socrates", signals)
        assert decision.active_mode == IntegrationMode.REQUIRE_BRANCH_CLOSURE
        assert decision.force_resolution_mode is True

    def test_not_triggered_when_progress_sufficient(self, core):
        signals = _nominal_signals()
        signals["unresolved"] = 4
        signals["progress_after"] = 0.7
        decision = core.evaluate_turn("Socrates", signals)
        assert decision.active_mode != IntegrationMode.REQUIRE_BRANCH_CLOSURE
        assert decision.active_mode != IntegrationMode.RESOLUTION_OVERRIDE

    def test_not_triggered_when_unresolved_below_threshold(self, core):
        signals = _nominal_signals()
        signals["unresolved"] = 2
        signals["progress_after"] = 0.2
        decision = core.evaluate_turn("Socrates", signals)
        assert decision.active_mode != IntegrationMode.REQUIRE_BRANCH_CLOSURE
        assert decision.active_mode != IntegrationMode.RESOLUTION_OVERRIDE


# ---------------------------------------------------------------------------
# 6. Rule: fatigue -> LOW_COMPLEXITY
# ---------------------------------------------------------------------------


class TestRuleFatigueMode:
    def test_triggers_low_complexity(self, core):
        signals = _nominal_signals()
        signals["fatigue"] = 0.70
        decision = core.evaluate_turn("Socrates", signals)
        assert decision.active_mode == IntegrationMode.LOW_COMPLEXITY
        assert decision.low_complexity_mode is True

    def test_not_triggered_below_threshold(self, core):
        signals = _nominal_signals()
        signals["fatigue"] = 0.55
        decision = core.evaluate_turn("Socrates", signals)
        assert decision.active_mode != IntegrationMode.LOW_COMPLEXITY


# ---------------------------------------------------------------------------
# 7. Rule: FIXY_AUTHORITY_OVERRIDE is no longer a hard rule
#    The old rule (is_loop + compliance=False -> FIXY_AUTHORITY_OVERRIDE) was
#    removed.  Fixy is now a conversational participant only; the controller
#    no longer forces Fixy intervention or sets enforce_fixy based on is_loop.
# ---------------------------------------------------------------------------


class TestRuleFixyAuthority:
    def test_fixy_authority_not_triggered_by_loop_noncompliance(self, core):
        """FIXY_AUTHORITY_OVERRIDE is no longer triggered as a hard rule."""
        signals = _nominal_signals()
        signals["is_loop"] = True
        signals["compliance"] = False
        decision = core.evaluate_turn("Socrates", signals)
        assert decision.active_mode != IntegrationMode.FIXY_AUTHORITY_OVERRIDE

    def test_not_triggered_when_compliant(self, core):
        signals = _nominal_signals()
        signals["is_loop"] = True
        signals["compliance"] = True
        decision = core.evaluate_turn("Socrates", signals)
        assert decision.active_mode != IntegrationMode.FIXY_AUTHORITY_OVERRIDE

    def test_not_triggered_when_no_loop(self, core):
        signals = _nominal_signals()
        signals["is_loop"] = False
        signals["compliance"] = False
        decision = core.evaluate_turn("Socrates", signals)
        assert decision.active_mode != IntegrationMode.FIXY_AUTHORITY_OVERRIDE


# ---------------------------------------------------------------------------
# 8. Rule: stagnation — REQUIRE_STRUCTURAL_CHALLENGE only with adversarial evidence
# ---------------------------------------------------------------------------


class TestRuleStagnationAttack:
    def test_stagnation_alone_does_not_trigger_structural_challenge(self, core):
        """Generic stagnation without reasoning evidence should NOT produce
        REQUIRE_STRUCTURAL_CHALLENGE.  Epistemic fallback (REQUIRE_FORCED_CHOICE)
        is expected instead."""
        signals = _nominal_signals()
        signals["stagnation"] = 0.40
        # reasoning_delta is None (default) → no adversarial evidence
        decision = core.evaluate_turn("Socrates", signals)
        assert decision.active_mode not in (
            IntegrationMode.ATTACK_OVERRIDE,
            IntegrationMode.REQUIRE_STRUCTURAL_CHALLENGE,
        )
        # Epistemic fallback should be selected
        assert decision.active_mode == IntegrationMode.REQUIRE_FORCED_CHOICE

    def test_triggers_structural_challenge_with_moderate_delta(self, core):
        """When reasoning_delta is 'moderate', adversarial pressure is genuinely
        needed — REQUIRE_STRUCTURAL_CHALLENGE should fire."""
        signals = _nominal_signals()
        signals["stagnation"] = 0.40
        signals["reasoning_delta"] = "moderate"
        decision = core.evaluate_turn("Socrates", signals)
        assert decision.active_mode == IntegrationMode.REQUIRE_STRUCTURAL_CHALLENGE
        assert decision.force_attack_mode is True
        assert decision.suppress_personality is True

    def test_triggers_structural_challenge_with_strong_delta(self, core):
        """When reasoning_delta is 'strong', adversarial pressure is genuinely
        needed — REQUIRE_STRUCTURAL_CHALLENGE should fire."""
        signals = _nominal_signals()
        signals["stagnation"] = 0.40
        signals["reasoning_delta"] = "strong"
        decision = core.evaluate_turn("Socrates", signals)
        assert decision.active_mode == IntegrationMode.REQUIRE_STRUCTURAL_CHALLENGE
        assert decision.force_attack_mode is True

    def test_not_triggered_below_threshold(self, core):
        signals = _nominal_signals()
        signals["stagnation"] = 0.10
        decision = core.evaluate_turn("Socrates", signals)
        assert decision.active_mode not in (
            IntegrationMode.ATTACK_OVERRIDE,
            IntegrationMode.REQUIRE_STRUCTURAL_CHALLENGE,
        )

    def test_recovery_suppresses_structural_challenge_even_with_moderate_delta(self, core):
        """REQUIRE_STRUCTURAL_CHALLENGE must be blocked during post-dream recovery
        even when reasoning_delta is 'moderate'."""
        signals = _nominal_signals()
        signals["stagnation"] = 0.40
        signals["reasoning_delta"] = "moderate"
        signals["post_dream_recovery_turns"] = 1
        decision = core.evaluate_turn("Socrates", signals)
        assert decision.active_mode not in (
            IntegrationMode.ATTACK_OVERRIDE,
            IntegrationMode.REQUIRE_STRUCTURAL_CHALLENGE,
        )


# ---------------------------------------------------------------------------
# 9. Rule: pressure misalignment -> overlay injected, mode=NORMAL
# ---------------------------------------------------------------------------


class TestRulePressureMisalignment:
    def test_overlay_injected_on_misalignment(self, core):
        signals = _nominal_signals()
        signals["alignment"] = "internal_not_expressed"
        decision = core.evaluate_turn("Athena", signals)
        assert decision.prompt_overlay != ""
        assert decision.active_mode == IntegrationMode.NORMAL

    def test_no_overlay_when_aligned(self, core):
        signals = _nominal_signals()
        signals["alignment"] = "aligned"
        decision = core.evaluate_turn("Athena", signals)
        assert decision.active_mode == IntegrationMode.NORMAL
        # overlay may be empty when no rules fire
        assert decision.prompt_overlay == ""


# ---------------------------------------------------------------------------
# 10. Nominal signals -> NORMAL, no regeneration
# ---------------------------------------------------------------------------


class TestNominalSignals:
    def test_normal_mode(self, core):
        decision = core.evaluate_turn("Socrates", _nominal_signals())
        assert decision.active_mode == IntegrationMode.NORMAL
        assert decision.regenerate is False
        assert decision.suppress_personality is False
        assert decision.enforce_fixy is False

    def test_allow_response_default_true(self, core):
        decision = core.evaluate_turn("Athena", _nominal_signals())
        assert decision.allow_response is True


# ---------------------------------------------------------------------------
# 11. build_prompt_overlay
# ---------------------------------------------------------------------------


class TestBuildPromptOverlay:
    def test_returns_decision_prompt_overlay(self, core):
        signals = _nominal_signals()
        signals["fatigue"] = 0.8
        decision = core.evaluate_turn("Socrates", signals)
        overlay = core.build_prompt_overlay(decision)
        assert overlay == decision.prompt_overlay
        assert len(overlay) > 0

    def test_empty_string_when_normal(self, core):
        decision = core.evaluate_turn("Socrates", _nominal_signals())
        overlay = core.build_prompt_overlay(decision)
        assert overlay == ""


# ---------------------------------------------------------------------------
# 12. should_regenerate
# ---------------------------------------------------------------------------


class TestShouldRegenerate:
    def test_loop_concrete_triggers_no_regen_by_default(self, core):
        """Loop detection does not automatically force regenerate=True.
        Regeneration is driven by validate_generated_output, not the rule engine."""
        signals = _nominal_signals()
        signals["semantic_repeat"] = True
        signals["loop_count"] = 1
        decision = core.evaluate_turn("Socrates", signals)
        # CONCRETE_OVERRIDE fires but does not force regenerate=True;
        # that is the caller's responsibility after validate_generated_output.
        assert decision.active_mode == IntegrationMode.CONCRETE_OVERRIDE
        assert decision.regenerate is False
        assert core.should_regenerate(decision) is False

    def test_false_on_nominal(self, core):
        decision = core.evaluate_turn("Socrates", _nominal_signals())
        assert core.should_regenerate(decision) is False


# ---------------------------------------------------------------------------
# 13. Priority: CONCRETE_OVERRIDE beats REQUIRE_STRUCTURAL_CHALLENGE
# ---------------------------------------------------------------------------


class TestPriorityFixyBeforeConcrete:
    def test_concrete_wins_over_structural_challenge(self, core):
        signals = _nominal_signals()
        # Both rules would fire
        signals["semantic_repeat"] = True
        signals["loop_count"] = 2
        signals["stagnation"] = 0.40  # would trigger epistemic fallback alone
        decision = core.evaluate_turn("Socrates", signals)
        # semantic_repeat + loop_count >= 1 fires CONCRETE_OVERRIDE (via personality suppression)
        assert decision.active_mode in (
            IntegrationMode.CONCRETE_OVERRIDE,
            IntegrationMode.PERSONALITY_SUPPRESSION,
        )


# ---------------------------------------------------------------------------
# 14. Priority: CONCRETE_OVERRIDE beats REQUIRE_STRUCTURAL_CHALLENGE
# ---------------------------------------------------------------------------


class TestPriorityConcreteBeforeAttack:
    def test_concrete_wins(self, core):
        signals = _nominal_signals()
        signals["semantic_repeat"] = True
        signals["loop_count"] = 1
        signals["stagnation"] = 0.30  # would trigger epistemic fallback alone
        decision = core.evaluate_turn("Socrates", signals)
        # semantic_repeat + loop_count >= 1 should fire CONCRETE_OVERRIDE first
        assert decision.active_mode == IntegrationMode.CONCRETE_OVERRIDE


# ---------------------------------------------------------------------------
# 15. make_integration_state factory
# ---------------------------------------------------------------------------


class TestMakeIntegrationState:
    def test_creates_correct_state(self):
        state = make_integration_state("Athena", fatigue=0.7, is_loop=True)
        assert state.agent_name == "Athena"
        assert state.fatigue == 0.7
        assert state.is_loop is True

    def test_unknown_kwargs_ignored(self):
        state = make_integration_state("Fixy", unknown_field=42)
        assert not hasattr(state, "unknown_field")


# ---------------------------------------------------------------------------
# 16. evaluate_turn integration path (state_dict directly and IntegrationState)
# ---------------------------------------------------------------------------


class TestEvaluateTurnIntegrationPath:
    def test_returns_control_decision(self, core):
        decision = core.evaluate_turn("Socrates", _nominal_signals())
        assert isinstance(decision, ControlDecision)

    def test_decision_reason_populated(self, core):
        decision = core.evaluate_turn("Socrates", _nominal_signals())
        assert decision.decision_reason  # non-empty string

    def test_accepts_integration_state_directly(self, core):
        """evaluate_turn must accept an IntegrationState (not only a dict)."""
        state = IntegrationState(
            agent_name="Socrates",
            semantic_repeat=True,
            loop_count=2,
            stagnation=0.3,
        )
        decision = core.evaluate_turn("Socrates", state)
        assert isinstance(decision, ControlDecision)
        # semantic_repeat=True + loop_count=2 should fire CONCRETE_OVERRIDE
        assert decision.active_mode == IntegrationMode.CONCRETE_OVERRIDE

    def test_integration_state_agent_name_used_directly(self, core):
        """When an IntegrationState is passed the agent_name arg is ignored."""
        state = IntegrationState(agent_name="Athena", fatigue=0.8)
        decision = core.evaluate_turn("ignored_name", state)
        assert decision.active_mode == IntegrationMode.LOW_COMPLEXITY

    def test_dict_and_state_produce_same_result(self, core):
        """Dict path and IntegrationState path must yield identical decisions."""
        signals = _nominal_signals()
        signals["is_loop"] = True
        signals["compliance"] = False
        decision_from_dict = core.evaluate_turn("Socrates", signals)

        state = make_integration_state("Socrates", **signals)
        decision_from_state = core.evaluate_turn("Socrates", state)

        assert decision_from_dict.active_mode == decision_from_state.active_mode
        assert decision_from_dict.regenerate == decision_from_state.regenerate


# ---------------------------------------------------------------------------
# 17. Overlay text is imperative (no "consider")
# ---------------------------------------------------------------------------


class TestOverlayTextIsImperative:
    ACTIVE_MODES = [
        {"fatigue": 0.9},
        {"semantic_repeat": True, "loop_count": 1},
        {"unresolved": 3, "progress_after": 0.2},
        {"stagnation": 0.5},
    ]

    @pytest.mark.parametrize("overrides", ACTIVE_MODES)
    def test_no_consider_in_overlay(self, core, overrides):
        signals = {**_nominal_signals(), **overrides}
        decision = core.evaluate_turn("Socrates", signals)
        assert "consider" not in decision.prompt_overlay.lower()

    @pytest.mark.parametrize("overrides", ACTIVE_MODES)
    def test_overlay_is_directive(self, core, overrides):
        signals = {**_nominal_signals(), **overrides}
        decision = core.evaluate_turn("Socrates", signals)
        text = decision.prompt_overlay.lower()
        # At least one imperative marker must be present
        assert any(
            marker in text
            for marker in ("must", "do not", "required", "override", "forbidden")
        ), f"No imperative marker found in overlay: {decision.prompt_overlay!r}"


# ---------------------------------------------------------------------------
# 18. FIXY_AUTHORITY_OVERRIDE is deprecated; enforce_fixy is no longer set
# ---------------------------------------------------------------------------


class TestFixyAuthorityEnforcesFlag:
    def test_enforce_fixy_not_forced_by_loop_noncompliance(self, core):
        """The old FIXY_AUTHORITY_OVERRIDE rule is gone.
        enforce_fixy is no longer set by the rule engine."""
        signals = _nominal_signals()
        signals["is_loop"] = True
        signals["compliance"] = False
        decision = core.evaluate_turn("Socrates", signals)
        assert decision.enforce_fixy is False


# ---------------------------------------------------------------------------
# 19. prepare_generation_state builds IntegrationState identically to
#     _build_state (public alias).
# ---------------------------------------------------------------------------


class TestPrepareGenerationState:
    def test_returns_integration_state(self, core):
        state = core.prepare_generation_state("Socrates", _nominal_signals())
        assert isinstance(state, IntegrationState)

    def test_agent_name_is_preserved(self, core):
        state = core.prepare_generation_state("Athena", _nominal_signals())
        assert state.agent_name == "Athena"

    def test_unknown_keys_are_dropped(self, core):
        signals = {**_nominal_signals(), "ghost_key": 99}
        state = core.prepare_generation_state("Socrates", signals)
        assert not hasattr(state, "ghost_key")

    def test_missing_keys_use_defaults(self, core):
        state = core.prepare_generation_state("Socrates", {"agent_name": "Socrates"})
        assert state.semantic_repeat is False
        assert state.loop_count == 0


# ---------------------------------------------------------------------------
# 20. pre_generation_decision produces the same ControlDecision as
#     evaluate_turn for identical inputs (same rule engine, different log
#     tags).
# ---------------------------------------------------------------------------


class TestPreGenerationDecision:
    def test_normal_signals_give_normal_mode(self, core):
        decision = core.pre_generation_decision("Socrates", _nominal_signals())
        assert decision.active_mode == IntegrationMode.NORMAL

    def test_loop_signals_give_concrete_override(self, core):
        signals = {**_nominal_signals(), "semantic_repeat": True, "loop_count": 1}
        decision = core.pre_generation_decision("Socrates", signals)
        assert decision.active_mode == IntegrationMode.CONCRETE_OVERRIDE

    def test_fixy_authority_not_triggered_on_loop_noncompliance(self, core):
        """FIXY_AUTHORITY_OVERRIDE is no longer triggered by is_loop + compliance=False."""
        signals = {**_nominal_signals(), "is_loop": True, "compliance": False}
        decision = core.pre_generation_decision("Socrates", signals)
        assert decision.active_mode != IntegrationMode.FIXY_AUTHORITY_OVERRIDE

    def test_same_result_as_evaluate_turn(self, core):
        signals = {**_nominal_signals(), "semantic_repeat": True, "loop_count": 2}
        d_pre = core.pre_generation_decision("Socrates", signals)
        d_post = core.evaluate_turn("Socrates", signals)
        assert d_pre.active_mode == d_post.active_mode
        assert d_pre.priority_level == d_post.priority_level

    def test_accepts_integration_state_directly(self, core):
        state = IntegrationState(
            agent_name="Athena",
            semantic_repeat=True,
            loop_count=1,
        )
        decision = core.pre_generation_decision("Athena", state)
        assert decision.active_mode == IntegrationMode.CONCRETE_OVERRIDE


# ---------------------------------------------------------------------------
# 21. build_generation_overlay returns the decision's overlay text.
# ---------------------------------------------------------------------------


class TestBuildGenerationOverlay:
    def test_returns_overlay_from_decision(self, core):
        signals = {**_nominal_signals(), "semantic_repeat": True, "loop_count": 1}
        decision = core.pre_generation_decision("Socrates", signals)
        overlay = core.build_generation_overlay(decision)
        assert overlay == decision.prompt_overlay

    def test_returns_empty_string_for_normal_mode(self, core):
        decision = core.pre_generation_decision("Socrates", _nominal_signals())
        overlay = core.build_generation_overlay(decision)
        assert overlay == ""


# ---------------------------------------------------------------------------
# 22. validate_generated_output — per-mode compliance checks.
# ---------------------------------------------------------------------------


class TestValidateGeneratedOutput:
    def _decision_for(self, core, overrides):
        signals = {**_nominal_signals(), **overrides}
        return core.pre_generation_decision("Socrates", signals)

    def test_normal_mode_is_compliant_for_clean_text(self, core):
        decision = core.pre_generation_decision("Socrates", _nominal_signals())
        compliant, _ = core.validate_generated_output("Any text at all.", decision)
        assert compliant is True

    def test_normal_mode_fails_quality_gate_on_banned_patterns(self, core):
        decision = core.pre_generation_decision("Socrates", _nominal_signals())
        # Two or more banned rhetorical scaffolding patterns → non-compliant
        text = (
            "We must consider the implications carefully. "
            "One might argue that underlying assumptions are at play here. "
            "It is worth noting that further analysis is needed."
        )
        compliant, reason = core.validate_generated_output(text, decision)
        assert compliant is False
        assert "QUALITY_GATE" in reason

    def test_normal_mode_single_banned_pattern_still_compliant(self, core):
        decision = core.pre_generation_decision("Socrates", _nominal_signals())
        # Only one banned pattern → threshold not reached, still compliant
        text = "One might argue that this is a philosophical question."
        compliant, _ = core.validate_generated_output(text, decision)
        assert compliant is True

    # CONCRETE_OVERRIDE ───────────────────────────────────────────────────────

    def test_concrete_override_passes_with_concrete_signal(self, core):
        decision = self._decision_for(
            core, {"semantic_repeat": True, "loop_count": 1}
        )
        assert decision.active_mode == IntegrationMode.CONCRETE_OVERRIDE
        # A genuine example: named role + concrete action + situated context
        text = (
            "For example, a teacher decides to give extra homework to struggling "
            "students during the morning session."
        )
        compliant, _ = core.validate_generated_output(text, decision)
        assert compliant is True

    def test_concrete_override_fails_with_pure_abstraction(self, core):
        decision = self._decision_for(
            core, {"semantic_repeat": True, "loop_count": 1}
        )
        text = "This is an abstract philosophical argument without any grounding."
        compliant, reason = core.validate_generated_output(text, decision)
        assert compliant is False
        assert "concrete" in reason.lower()

    # REQUIRE_BRANCH_CLOSURE (replaces RESOLUTION_OVERRIDE for unresolved+low-progress) ──

    def test_branch_closure_passes_with_resolution_signal(self, core):
        decision = self._decision_for(
            core, {"unresolved": 3, "progress_after": 0.2}
        )
        assert decision.active_mode == IntegrationMode.REQUIRE_BRANCH_CLOSURE
        # "settled" is in _VALIDATE_BRANCH_CLOSURE_STATE_MARKERS and "conclude" is
        # in _VALIDATE_BRANCH_CLOSURE_SIGNALS — both constraints are satisfied.
        compliant, _ = core.validate_generated_output(
            "Therefore we can conclude that the argument is settled.", decision
        )
        assert compliant is True

    def test_branch_closure_fails_without_closure_signal(self, core):
        decision = self._decision_for(
            core, {"unresolved": 3, "progress_after": 0.2}
        )
        text = "I still think there are many open questions here."
        compliant, reason = core.validate_generated_output(text, decision)
        # REQUIRE_BRANCH_CLOSURE now enforces a hard text gate (PATCH 1)
        assert compliant is False
        assert "STATE-TRANSITION-FAIL" in reason or "closure" in reason.lower()

    # REQUIRE_STRUCTURAL_CHALLENGE (only fires with adversarial evidence) ──

    def test_structural_challenge_passes_with_challenge_signal(self, core):
        # reasoning_delta="moderate" provides adversarial evidence
        decision = self._decision_for(
            core, {"stagnation": 0.5, "reasoning_delta": "moderate"}
        )
        assert decision.active_mode == IntegrationMode.REQUIRE_STRUCTURAL_CHALLENGE
        text = "That reasoning is flawed because it ignores the empirical evidence."
        compliant, _ = core.validate_generated_output(text, decision)
        assert compliant is True

    def test_structural_challenge_fails_without_challenge(self, core):
        # reasoning_delta="moderate" provides adversarial evidence
        decision = self._decision_for(
            core, {"stagnation": 0.5, "reasoning_delta": "moderate"}
        )
        assert decision.active_mode == IntegrationMode.REQUIRE_STRUCTURAL_CHALLENGE
        text = "I largely agree with what you have said and find it reasonable."
        compliant, reason = core.validate_generated_output(text, decision)
        assert compliant is False
        assert "challenge" in reason.lower()

    # LOW_COMPLEXITY ──────────────────────────────────────────────────────────

    def test_low_complexity_passes_for_short_response(self, core):
        decision = self._decision_for(core, {"fatigue": 0.9})
        assert decision.active_mode == IntegrationMode.LOW_COMPLEXITY
        text = " ".join(["word"] * 50)
        compliant, _ = core.validate_generated_output(text, decision)
        assert compliant is True

    def test_low_complexity_fails_for_overlong_response(self, core):
        decision = self._decision_for(core, {"fatigue": 0.9})
        text = " ".join(["word"] * 200)
        compliant, reason = core.validate_generated_output(text, decision)
        assert compliant is False
        assert "long" in reason.lower() or "words" in reason.lower()

    # Deprecated FIXY_AUTHORITY_OVERRIDE — no longer triggered as a hard rule ──

    def test_deprecated_fixy_authority_mode_is_never_triggered(self, core):
        """FIXY_AUTHORITY_OVERRIDE is no longer triggered by any rule."""
        signals = {**_nominal_signals(), "is_loop": True, "compliance": False}
        decision = self._decision_for(core, {"is_loop": True, "compliance": False})
        assert decision.active_mode != IntegrationMode.FIXY_AUTHORITY_OVERRIDE


# ---------------------------------------------------------------------------
# 23. should_regenerate_after_validation — returns False for NORMAL mode,
#     True when the output violated the active mode.
# ---------------------------------------------------------------------------


class TestShouldRegenerateAfterValidation:
    def test_normal_mode_clean_text_never_triggers_regen(self, core):
        decision = core.pre_generation_decision("Socrates", _nominal_signals())
        result = core.should_regenerate_after_validation("Any text.", decision)
        assert result is False

    def test_normal_mode_triggers_regen_on_banned_patterns(self, core):
        decision = core.pre_generation_decision("Socrates", _nominal_signals())
        # Two or more banned rhetorical scaffolding patterns → regen
        text = (
            "We must consider the implications carefully. "
            "One might argue that underlying assumptions are at play here. "
            "It is worth noting that further analysis is needed."
        )
        result = core.should_regenerate_after_validation(text, decision)
        assert result is True

    def test_normal_mode_short_text_never_triggers_regen(self, core):
        decision = core.pre_generation_decision("Socrates", _nominal_signals())
        # Below _QUALITY_GATE_MIN_WORDS → bypass quality gate
        result = core.should_regenerate_after_validation("Too short.", decision)
        assert result is False

    def test_compliant_output_does_not_trigger_regen(self, core):
        signals = {**_nominal_signals(), "semantic_repeat": True, "loop_count": 1}
        decision = core.pre_generation_decision("Socrates", signals)
        # Genuine example: named role + concrete action + situation
        text = (
            "For example, a doctor decides to run additional tests "
            "during last week's emergency consultation."
        )
        result = core.should_regenerate_after_validation(text, decision)
        assert result is False

    def test_non_compliant_output_triggers_regen(self, core):
        signals = {**_nominal_signals(), "semantic_repeat": True, "loop_count": 1}
        decision = core.pre_generation_decision("Socrates", signals)
        text = "The essence of this concept is purely abstract and philosophical."
        result = core.should_regenerate_after_validation(text, decision)
        assert result is True


# ---------------------------------------------------------------------------
# 24. build_stronger_overlay — prefix is prepended to the original overlay.
# ---------------------------------------------------------------------------


class TestBuildStrongerOverlay:
    def test_contains_original_overlay(self, core):
        signals = {**_nominal_signals(), "semantic_repeat": True, "loop_count": 1}
        decision = core.pre_generation_decision("Socrates", signals)
        stronger = core.build_stronger_overlay(decision)
        assert decision.prompt_overlay in stronger

    def test_stronger_than_original(self, core):
        signals = {**_nominal_signals(), "semantic_repeat": True, "loop_count": 1}
        decision = core.pre_generation_decision("Socrates", signals)
        stronger = core.build_stronger_overlay(decision)
        assert len(stronger) > len(decision.prompt_overlay)

    def test_prefix_signals_regeneration_requirement(self, core):
        signals = {**_nominal_signals(), "stagnation": 0.5}
        decision = core.pre_generation_decision("Socrates", signals)
        stronger = core.build_stronger_overlay(decision)
        # Must communicate that a prior attempt failed
        assert any(
            phrase in stronger.upper()
            for phrase in ("REGENERATION", "STRICT", "MANDATORY", "PREVIOUS")
        )

    def test_normal_mode_with_advisory_overlay_includes_quality_gate(self, core):
        """NORMAL mode with a non-empty advisory overlay must also include quality-gate instructions."""
        decision = core.pre_generation_decision("Socrates", _nominal_signals())
        # Patch in an advisory overlay (simulates pressure-misalignment guidance)
        from dataclasses import replace
        decision_with_advisory = replace(decision, prompt_overlay="Advisory: stay on topic.")
        stronger = core.build_stronger_overlay(decision_with_advisory)
        assert "Advisory: stay on topic." in stronger
        assert "FORBIDDEN" in stronger or "banned" in stronger.lower() or "scaffolding" in stronger.lower()

    def test_normal_mode_empty_overlay_uses_quality_gate(self, core):
        """NORMAL mode with no overlay falls back entirely to quality-gate overlay."""
        decision = core.pre_generation_decision("Socrates", _nominal_signals())
        assert decision.prompt_overlay == ""
        stronger = core.build_stronger_overlay(decision)
        assert "scaffolding" in stronger.lower() or "banned" in stronger.lower()


# ---------------------------------------------------------------------------
# 25. Agent-binding: pre_generation_decision uses agent_name from input
#     and the cortex decision is specific to that agent (not Fixy).
# ---------------------------------------------------------------------------


class TestAgentBinding:
    def test_decision_carries_correct_agent_in_state(self, core):
        """pre_generation_decision must not silently re-bind to a different agent."""
        socrates_signals = {**_nominal_signals(), "semantic_repeat": True, "loop_count": 1}
        decision_soc = core.pre_generation_decision("Socrates", socrates_signals)

        athena_signals = {**_nominal_signals()}
        decision_ath = core.pre_generation_decision("Athena", athena_signals)

        # Both decisions are valid; the mode depends on signals, not on name alone
        assert decision_soc.active_mode == IntegrationMode.CONCRETE_OVERRIDE
        assert decision_ath.active_mode == IntegrationMode.NORMAL

    def test_fixy_name_does_not_bypass_rule_engine(self, core):
        """IntegrationCore must produce the same rule result regardless of name."""
        signals = {**_nominal_signals(), "semantic_repeat": True, "loop_count": 1}
        # Even if called with Fixy's name (gate is upstream in the main loop),
        # the rule engine should fire normally.
        decision = core.pre_generation_decision("Fixy", signals)
        assert decision.active_mode == IntegrationMode.CONCRETE_OVERRIDE

    def test_stronger_overlay_is_agent_agnostic(self, core):
        """build_stronger_overlay prefix must not hardcode a speaker name."""
        # Use semantic_repeat + loop_count to reliably trigger CONCRETE_OVERRIDE
        signals = {**_nominal_signals(), "semantic_repeat": True, "loop_count": 1}
        decision = core.pre_generation_decision("Socrates", signals)
        stronger = core.build_stronger_overlay(decision)
        # Verify behaviour: the added prefix must signal a failed prior attempt.
        # Extract the prefix by removing the original overlay from the end.
        prefix = stronger[: stronger.index(decision.prompt_overlay)]
        assert any(
            phrase in prefix.upper()
            for phrase in ("REGENERATION", "STRICT", "MANDATORY", "PREVIOUS")
        ), f"Prefix does not signal a required retry: {prefix!r}"
        # The prefix must not route regeneration to a specific agent.
        assert "Socrates" not in prefix
        assert "Athena" not in prefix
        assert "Fixy" not in prefix
        # The stronger overlay is strictly longer than the base overlay.
        assert len(stronger) > len(decision.prompt_overlay)


# ---------------------------------------------------------------------------
# 26. EscalationLevel enum
# ---------------------------------------------------------------------------


class TestEscalationLevelEnum:
    def test_values_are_ordered(self):
        from entelgia.integration_core import EscalationLevel
        assert EscalationLevel.NORMAL < EscalationLevel.CONCRETE_OVERRIDE
        assert EscalationLevel.CONCRETE_OVERRIDE < EscalationLevel.STRICT_CONCRETE
        assert EscalationLevel.STRICT_CONCRETE < EscalationLevel.FORMAT_ENFORCED
        assert EscalationLevel.FORMAT_ENFORCED < EscalationLevel.HARD_OVERRIDE

    def test_level_values(self):
        from entelgia.integration_core import EscalationLevel
        assert int(EscalationLevel.NORMAL) == 0
        assert int(EscalationLevel.CONCRETE_OVERRIDE) == 1
        assert int(EscalationLevel.STRICT_CONCRETE) == 2
        assert int(EscalationLevel.FORMAT_ENFORCED) == 3
        assert int(EscalationLevel.HARD_OVERRIDE) == 4


# ---------------------------------------------------------------------------
# 27. ControlDecision carries escalation_level field
# ---------------------------------------------------------------------------


class TestControlDecisionEscalationField:
    def test_default_escalation_level_is_zero(self):
        d = ControlDecision()
        assert d.escalation_level == 0

    def test_escalation_level_set_on_loop_count_1(self, core):
        signals = {**_nominal_signals(), "semantic_repeat": True, "loop_count": 1}
        decision = core.evaluate_turn("Socrates", signals)
        assert decision.escalation_level == 1

    def test_escalation_level_set_on_loop_count_2(self, core):
        signals = {**_nominal_signals(), "semantic_repeat": True, "loop_count": 2}
        decision = core.evaluate_turn("Socrates", signals)
        assert decision.escalation_level == 2

    def test_escalation_level_set_on_loop_count_3(self, core):
        signals = {**_nominal_signals(), "semantic_repeat": True, "loop_count": 3}
        decision = core.evaluate_turn("Socrates", signals)
        assert decision.escalation_level == 3

    def test_escalation_level_set_on_loop_count_4(self, core):
        signals = {**_nominal_signals(), "semantic_repeat": True, "loop_count": 4}
        decision = core.evaluate_turn("Socrates", signals)
        assert decision.escalation_level == 4


# ---------------------------------------------------------------------------
# 28. Personality suppression at escalation_level >= 3
# ---------------------------------------------------------------------------


class TestPersonalitySuppressionEscalation:
    def test_no_suppress_at_level_1(self, core):
        signals = {**_nominal_signals(), "semantic_repeat": True, "loop_count": 1}
        decision = core.evaluate_turn("Socrates", signals)
        assert decision.escalation_level == 1
        assert decision.suppress_personality is False

    def test_no_suppress_at_level_2(self, core):
        signals = {**_nominal_signals(), "semantic_repeat": True, "loop_count": 2}
        decision = core.evaluate_turn("Socrates", signals)
        assert decision.escalation_level == 2
        assert decision.suppress_personality is False

    def test_suppress_at_level_3(self, core):
        signals = {**_nominal_signals(), "semantic_repeat": True, "loop_count": 3}
        decision = core.evaluate_turn("Socrates", signals)
        assert decision.escalation_level == 3
        assert decision.suppress_personality is True

    def test_suppress_at_level_4(self, core):
        signals = {**_nominal_signals(), "semantic_repeat": True, "loop_count": 4}
        decision = core.evaluate_turn("Socrates", signals)
        assert decision.escalation_level == 4
        assert decision.suppress_personality is True


# ---------------------------------------------------------------------------
# 29. Escalation-level overlay content
# ---------------------------------------------------------------------------


class TestEscalationOverlayContent:
    def test_level_1_overlay_is_soft(self, core):
        signals = {**_nominal_signals(), "semantic_repeat": True, "loop_count": 1}
        decision = core.evaluate_turn("Socrates", signals)
        assert decision.escalation_level == 1
        overlay = decision.prompt_overlay.lower()
        assert "concrete" in overlay or "example" in overlay or "abstract" in overlay

    def test_level_2_overlay_requires_structured_example(self, core):
        signals = {**_nominal_signals(), "semantic_repeat": True, "loop_count": 2}
        decision = core.evaluate_turn("Socrates", signals)
        assert decision.escalation_level == 2
        overlay = decision.prompt_overlay.lower()
        assert "person" in overlay or "action" in overlay or "situation" in overlay

    def test_level_3_overlay_has_strict_format(self, core):
        signals = {**_nominal_signals(), "semantic_repeat": True, "loop_count": 3}
        decision = core.evaluate_turn("Socrates", signals)
        assert decision.escalation_level == 3
        overlay = decision.prompt_overlay
        assert "[SCENARIO]" in overlay or "STRICT" in overlay.upper() or "FORMAT" in overlay.upper()

    def test_level_4_overlay_is_hard_override(self, core):
        signals = {**_nominal_signals(), "semantic_repeat": True, "loop_count": 4}
        decision = core.evaluate_turn("Socrates", signals)
        assert decision.escalation_level == 4
        overlay = decision.prompt_overlay.upper()
        assert "HARD OVERRIDE" in overlay or "PERSONALITY" in overlay or "DISABLED" in overlay


# ---------------------------------------------------------------------------
# 30. detect_pseudo_compliance function
# ---------------------------------------------------------------------------


class TestDetectPseudoCompliance:
    def test_genuine_example_is_not_pseudo(self):
        from entelgia.integration_core import detect_pseudo_compliance
        # Has: trigger ("for example"), person (role "a teacher"), action ("decides"),
        # situation ("during the morning session")
        text = (
            "For example, a teacher decides to give extra homework "
            "during the morning session."
        )
        assert detect_pseudo_compliance(text) is False

    def test_no_trigger_is_never_pseudo(self):
        from entelgia.integration_core import detect_pseudo_compliance
        text = "The argument relies on abstract principles and logical deduction."
        assert detect_pseudo_compliance(text) is False

    def test_trigger_without_person_is_pseudo(self):
        from entelgia.integration_core import detect_pseudo_compliance
        # Has trigger but no named person / role, no action, no situation
        text = "Imagine an abstract system where all inputs map to outputs."
        assert detect_pseudo_compliance(text) is True

    def test_trigger_with_person_and_action_but_no_situation_is_pseudo(self):
        from entelgia.integration_core import detect_pseudo_compliance
        # Has trigger, person (role), action, but NO situational anchor
        text = "For example, a teacher decides to assign homework."
        assert detect_pseudo_compliance(text) is True

    def test_pure_abstraction_with_no_trigger_not_pseudo(self):
        from entelgia.integration_core import detect_pseudo_compliance
        text = (
            "This is purely philosophical: the mind and body are fundamentally different."
        )
        assert detect_pseudo_compliance(text) is False

    def test_named_person_with_action_and_situation_is_not_pseudo(self):
        from entelgia.integration_core import detect_pseudo_compliance
        text = (
            "Imagine John walks into the office on Monday and opens the quarterly report."
        )
        assert detect_pseudo_compliance(text) is False


# ---------------------------------------------------------------------------
# 31. escalate_decision method
# ---------------------------------------------------------------------------


class TestEscalateDecision:
    def test_escalate_increments_level(self, core):
        signals = {**_nominal_signals(), "semantic_repeat": True, "loop_count": 1}
        decision = core.evaluate_turn("Socrates", signals)
        assert decision.escalation_level == 1
        escalated = core.escalate_decision(decision)
        assert escalated.escalation_level == 2

    def test_escalate_sets_regenerate_true(self, core):
        signals = {**_nominal_signals(), "semantic_repeat": True, "loop_count": 1}
        decision = core.evaluate_turn("Socrates", signals)
        escalated = core.escalate_decision(decision)
        assert escalated.regenerate is True

    def test_escalate_caps_at_level_4(self, core):
        from entelgia.integration_core import EscalationLevel
        signals = {**_nominal_signals(), "semantic_repeat": True, "loop_count": 4}
        decision = core.evaluate_turn("Socrates", signals)
        assert decision.escalation_level == int(EscalationLevel.HARD_OVERRIDE)
        escalated = core.escalate_decision(decision)
        assert escalated.escalation_level == int(EscalationLevel.HARD_OVERRIDE)

    def test_escalate_to_level_3_suppresses_personality(self, core):
        signals = {**_nominal_signals(), "semantic_repeat": True, "loop_count": 2}
        decision = core.evaluate_turn("Socrates", signals)
        assert decision.escalation_level == 2
        assert decision.suppress_personality is False
        escalated = core.escalate_decision(decision)
        assert escalated.escalation_level == 3
        assert escalated.suppress_personality is True

    def test_escalate_injects_failure_memory(self, core):
        signals = {**_nominal_signals(), "semantic_repeat": True, "loop_count": 1}
        decision = core.evaluate_turn("Socrates", signals)
        escalated = core.escalate_decision(decision)
        assert "previous attempts" in escalated.prompt_overlay.lower()

    def test_escalate_overlay_is_stronger_than_base(self, core):
        signals = {**_nominal_signals(), "semantic_repeat": True, "loop_count": 1}
        decision = core.evaluate_turn("Socrates", signals)
        escalated = core.escalate_decision(decision)
        assert len(escalated.prompt_overlay) > 0
        assert "do not repeat" in escalated.prompt_overlay.lower() or \
               "failed to comply" in escalated.prompt_overlay.lower()


# ---------------------------------------------------------------------------
# 32. build_escalation_overlay
# ---------------------------------------------------------------------------


class TestBuildEscalationOverlay:
    def test_level_0_returns_empty(self, core):
        decision = ControlDecision(escalation_level=0)
        overlay = core.build_escalation_overlay(decision)
        assert overlay == ""

    def test_level_1_returns_nonempty(self, core):
        decision = ControlDecision(escalation_level=1)
        overlay = core.build_escalation_overlay(decision)
        assert len(overlay) > 0

    def test_level_4_overlay_contains_hard_override(self, core):
        decision = ControlDecision(escalation_level=4)
        overlay = core.build_escalation_overlay(decision)
        assert "HARD OVERRIDE" in overlay or "disabled" in overlay.lower() or \
               "personality" in overlay.lower()


# ---------------------------------------------------------------------------
# 33. record_response_hash — same-reasoning detection
# ---------------------------------------------------------------------------


class TestRecordResponseHash:
    def test_different_responses_no_repeat(self):
        core = IntegrationCore()
        assert core.record_response_hash("Socrates believed in questioning everything.") is False
        assert core.record_response_hash("Athena represents wisdom and strategy.") is False
        assert core.record_response_hash("The dialectic method reveals hidden assumptions.") is False

    def test_same_response_three_times_triggers_repeat(self):
        core = IntegrationCore()
        text = "Consciousness arises from neural activity in the brain."
        core.record_response_hash(text)
        core.record_response_hash(text)
        result = core.record_response_hash(text)
        assert result is True

    def test_fresh_core_no_history(self):
        core = IntegrationCore()
        assert core.record_response_hash("A unique first response here.") is False


# ---------------------------------------------------------------------------
# 34. Pseudo-compliance causes non-compliance in validate_generated_output
# ---------------------------------------------------------------------------


class TestPseudoComplianceValidation:
    def test_pseudo_compliant_response_fails_validation(self, core):
        signals = {**_nominal_signals(), "semantic_repeat": True, "loop_count": 1}
        decision = core.pre_generation_decision("Socrates", signals)
        assert decision.active_mode == IntegrationMode.CONCRETE_OVERRIDE
        # Pseudo-compliance: has "for example" but no person / action / situation
        text = "For example, imagine a world where all decisions are optimal."
        compliant, reason = core.validate_generated_output(text, decision)
        assert compliant is False
        assert "pseudo" in reason.lower() or "compliance" in reason.lower()

    def test_pseudo_compliant_response_triggers_regen(self, core):
        signals = {**_nominal_signals(), "semantic_repeat": True, "loop_count": 1}
        decision = core.pre_generation_decision("Socrates", signals)
        text = "For example, think of an abstract system where nothing is concrete."
        result = core.should_regenerate_after_validation(text, decision)
        assert result is True


# ---------------------------------------------------------------------------
# 35. STRUCTURE_LOCK — structural section-header enforcement (level >= 3)
# ---------------------------------------------------------------------------


class TestStructureLock:
    """Validate STRUCTURE_LOCK behaviour in validate_generated_output.

    STRUCTURE_LOCK activates at escalation_level >= 3 and requires the
    response to contain every header listed in _STRUCTURE_LOCK_SECTIONS
    ([PERSON], [ACTION], [OUTCOME]) regardless of the active mode.
    """

    def _decision_at_level(self, core, loop_count: int):
        """Return a ControlDecision whose escalation_level equals loop_count."""
        signals = {**_nominal_signals(), "semantic_repeat": True, "loop_count": loop_count}
        return core.evaluate_turn("Socrates", signals)

    # Level < 3 — no STRUCTURE_LOCK

    def test_level_2_does_not_enforce_section_headers(self, core):
        decision = self._decision_at_level(core, 2)
        assert decision.escalation_level == 2
        # Response with no section headers but a genuine concrete signal must still pass
        text = (
            "For example, a teacher decides to give extra homework to struggling "
            "students during the morning session."
        )
        compliant, _ = core.validate_generated_output(text, decision)
        assert compliant is True

    # Level 3 — STRUCTURE_LOCK active

    def test_level_3_structure_lock_activates(self, core):
        decision = self._decision_at_level(core, 3)
        assert decision.escalation_level == 3

    def test_level_3_passes_when_all_sections_present(self, core):
        decision = self._decision_at_level(core, 3)
        text = (
            "[PERSON]\nJane, a nurse at City Hospital\n\n"
            "[ACTION]\nShe administered the vaccine to 30 patients in one morning\n\n"
            "[OUTCOME]\nAll patients recovered without complications"
        )
        compliant, reason = core.validate_generated_output(text, decision)
        assert compliant is True, reason

    def test_level_3_fails_when_person_section_missing(self, core):
        decision = self._decision_at_level(core, 3)
        text = (
            "[ACTION]\nShe administered the vaccine\n\n"
            "[OUTCOME]\nAll patients recovered"
        )
        compliant, reason = core.validate_generated_output(text, decision)
        assert compliant is False
        assert "[PERSON]" in reason.upper()

    def test_level_3_fails_when_action_section_missing(self, core):
        decision = self._decision_at_level(core, 3)
        text = (
            "[PERSON]\nJane, a nurse\n\n"
            "[OUTCOME]\nAll patients recovered"
        )
        compliant, reason = core.validate_generated_output(text, decision)
        assert compliant is False
        assert "[ACTION]" in reason.upper()

    def test_level_3_fails_when_outcome_section_missing(self, core):
        decision = self._decision_at_level(core, 3)
        text = (
            "[PERSON]\nJane, a nurse\n\n"
            "[ACTION]\nShe administered the vaccine"
        )
        compliant, reason = core.validate_generated_output(text, decision)
        assert compliant is False
        assert "[OUTCOME]" in reason.upper()

    def test_level_3_fails_for_abstract_prose_without_headers(self, core):
        decision = self._decision_at_level(core, 3)
        text = (
            "For example, consider a medical professional in a real hospital "
            "who specifically administers vaccines according to a protocol."
        )
        compliant, reason = core.validate_generated_output(text, decision)
        assert compliant is False
        assert "STRUCTURE_LOCK" in reason

    def test_level_3_section_headers_case_insensitive(self, core):
        """Section headers should be matched case-insensitively."""
        decision = self._decision_at_level(core, 3)
        text = (
            "[person]\nJane, a nurse\n\n"
            "[action]\nShe administered the vaccine\n\n"
            "[outcome]\nAll patients recovered"
        )
        compliant, reason = core.validate_generated_output(text, decision)
        assert compliant is True, reason

    # Level 4 — STRUCTURE_LOCK still active

    def test_level_4_also_enforces_section_headers(self, core):
        decision = self._decision_at_level(core, 4)
        assert decision.escalation_level == 4
        text = "Concrete action: a doctor prescribed medication."
        compliant, reason = core.validate_generated_output(text, decision)
        assert compliant is False
        assert "STRUCTURE_LOCK" in reason

    def test_level_4_passes_when_all_sections_present(self, core):
        decision = self._decision_at_level(core, 4)
        text = (
            "[PERSON]\nDr Smith, a cardiologist\n\n"
            "[ACTION]\nHe prescribed beta-blockers to a patient\n\n"
            "[OUTCOME]\nThe patient's blood pressure stabilised within a week"
        )
        compliant, reason = core.validate_generated_output(text, decision)
        assert compliant is True, reason

    # should_regenerate_after_validation integration

    def test_structure_lock_triggers_regen_on_missing_headers(self, core):
        decision = self._decision_at_level(core, 3)
        text = (
            "For example, a teacher decides to give extra homework to struggling "
            "students during the morning session."
        )
        result = core.should_regenerate_after_validation(text, decision)
        assert result is True

    def test_level_3_overlay_uses_structured_headers(self, core):
        """Verify the Level-3 overlay advertises the current structured sections."""
        decision = self._decision_at_level(core, 3)
        assert "[PERSON]" in decision.prompt_overlay
        assert "[ACTION]" in decision.prompt_overlay
        assert "[OUTCOME]" in decision.prompt_overlay
        assert "[SCENARIO]" not in decision.prompt_overlay

    # ----------------------------------------------------------------
    # Section-content quality validation
    # ----------------------------------------------------------------

    def test_person_section_with_generic_placeholder_fails(self, core):
        """[PERSON] body containing 'a person' is rejected."""
        decision = self._decision_at_level(core, 3)
        text = (
            "[PERSON]\na person in a situation\n\n"
            "[ACTION]\nShe administered the vaccine\n\n"
            "[OUTCOME]\nAll patients recovered"
        )
        compliant, reason = core.validate_generated_output(text, decision)
        assert compliant is False
        assert "content violation" in reason.lower() or "placeholder" in reason.lower()

    def test_person_section_with_someone_placeholder_fails(self, core):
        """[PERSON] body containing 'someone' is rejected."""
        decision = self._decision_at_level(core, 3)
        text = (
            "[PERSON]\nSomeone from the hospital\n\n"
            "[ACTION]\nShe administered the vaccine\n\n"
            "[OUTCOME]\nAll patients recovered"
        )
        compliant, reason = core.validate_generated_output(text, decision)
        assert compliant is False

    def test_person_section_with_an_individual_placeholder_fails(self, core):
        """[PERSON] body containing 'an individual' is rejected."""
        decision = self._decision_at_level(core, 3)
        text = (
            "[PERSON]\nAn individual working in healthcare\n\n"
            "[ACTION]\nShe administered the vaccine\n\n"
            "[OUTCOME]\nAll patients recovered"
        )
        compliant, reason = core.validate_generated_output(text, decision)
        assert compliant is False

    def test_action_section_with_something_placeholder_fails(self, core):
        """[ACTION] body containing 'something' is rejected."""
        decision = self._decision_at_level(core, 3)
        text = (
            "[PERSON]\nJane, a nurse at City Hospital\n\n"
            "[ACTION]\nShe did something with the patients\n\n"
            "[OUTCOME]\nAll patients recovered"
        )
        compliant, reason = core.validate_generated_output(text, decision)
        assert compliant is False

    def test_action_section_with_some_action_placeholder_fails(self, core):
        """[ACTION] body containing 'some action' is rejected."""
        decision = self._decision_at_level(core, 3)
        text = (
            "[PERSON]\nJane, a nurse\n\n"
            "[ACTION]\nShe performed some action\n\n"
            "[OUTCOME]\nThe result followed"
        )
        compliant, reason = core.validate_generated_output(text, decision)
        assert compliant is False

    def test_action_section_without_concrete_verb_fails(self, core):
        """[ACTION] with no observable action verb is rejected."""
        decision = self._decision_at_level(core, 3)
        text = (
            "[PERSON]\nJane, a nurse\n\n"
            "[ACTION]\nThe situation continued in the ward\n\n"
            "[OUTCOME]\nThe ward fell silent"
        )
        compliant, reason = core.validate_generated_output(text, decision)
        assert compliant is False
        assert "action verb" in reason.lower() or "ACTION" in reason

    def test_outcome_section_with_abstract_reflection_fails(self, core):
        """[OUTCOME] consisting of abstract reflection is rejected."""
        decision = self._decision_at_level(core, 3)
        text = (
            "[PERSON]\nJane, a nurse\n\n"
            "[ACTION]\nShe administered the vaccine\n\n"
            "[OUTCOME]\nThis reminds us of the importance of healthcare workers"
        )
        compliant, reason = core.validate_generated_output(text, decision)
        assert compliant is False
        assert "abstract" in reason.lower() or "reflection" in reason.lower()

    def test_outcome_section_with_raises_question_fails(self, core):
        """[OUTCOME] with 'raises the question' is rejected."""
        decision = self._decision_at_level(core, 3)
        text = (
            "[PERSON]\nJane, a nurse\n\n"
            "[ACTION]\nShe administered the vaccine\n\n"
            "[OUTCOME]\nThis raises the question of whether vaccines are always safe"
        )
        compliant, reason = core.validate_generated_output(text, decision)
        assert compliant is False

    def test_outcome_section_with_challenges_us_fails(self, core):
        """[OUTCOME] with 'challenges us to' is rejected."""
        decision = self._decision_at_level(core, 3)
        text = (
            "[PERSON]\nJane, a nurse\n\n"
            "[ACTION]\nShe administered the vaccine\n\n"
            "[OUTCOME]\nThis challenges us to rethink public health policy"
        )
        compliant, reason = core.validate_generated_output(text, decision)
        assert compliant is False

    def test_all_sections_concrete_content_passes(self, core):
        """Explicit positive: all sections have concrete, specific content."""
        decision = self._decision_at_level(core, 3)
        text = (
            "[PERSON]\nDr Sarah Chen, a paediatrician at St Mary's Hospital\n\n"
            "[ACTION]\nShe prescribed a two-week course of antibiotics to a child with pneumonia\n\n"
            "[OUTCOME]\nThe child's fever broke within 48 hours and she was discharged"
        )
        compliant, reason = core.validate_generated_output(text, decision)
        assert compliant is True, reason

    def test_content_validation_triggers_regen_on_generic_placeholder(self, core):
        """should_regenerate_after_validation returns True for generic-placeholder content."""
        decision = self._decision_at_level(core, 3)
        text = (
            "[PERSON]\nSomeone\n\n"
            "[ACTION]\nDid something\n\n"
            "[OUTCOME]\nSomething happened"
        )
        result = core.should_regenerate_after_validation(text, decision)
        assert result is True

    def test_section_name_in_body_does_not_satisfy_header_check(self, core):
        """A section name mentioned inside a body paragraph must not count as a header."""
        decision = self._decision_at_level(core, 3)
        # [person] appears mid-sentence, not at a line start — must not satisfy check
        text = (
            "We can refer to [person] and [action] and [outcome] in our analysis\n"
            "but without actual section headers the format is invalid."
        )
        compliant, reason = core.validate_generated_output(text, decision)
        assert compliant is False
        assert "STRUCTURE_LOCK" in reason

    def test_action_verb_third_person_singular_passes(self, core):
        """[ACTION] with a 3rd-person singular verb form (-s) must be accepted."""
        decision = self._decision_at_level(core, 3)
        text = (
            "[PERSON]\nDr Lee, a surgeon\n\n"
            "[ACTION]\nShe administers the anaesthetic before the operation\n\n"
            "[OUTCOME]\nThe patient loses consciousness within 60 seconds"
        )
        compliant, reason = core.validate_generated_output(text, decision)
        assert compliant is True, reason

    def test_action_verb_progressive_form_passes(self, core):
        """[ACTION] with a progressive verb form (-ing) must be accepted."""
        decision = self._decision_at_level(core, 3)
        text = (
            "[PERSON]\nDr Lee, a surgeon\n\n"
            "[ACTION]\nShe is administering the anaesthetic to the patient\n\n"
            "[OUTCOME]\nThe patient becomes sedated within 60 seconds"
        )
        compliant, reason = core.validate_generated_output(text, decision)
        assert compliant is True, reason


# ---------------------------------------------------------------------------
# 36. check_loop_rejection — hard loop gate
# ---------------------------------------------------------------------------


class TestCheckLoopRejection:
    """Tests for IntegrationCore.check_loop_rejection (hard loop gate).

    A response is valid only when:
      (1) structure valid
      (2) content valid
      (3) NOT a semantic loop (is_loop=True AND reasoning_delta in ("none","weak"))
    All three must pass.
    """

    @pytest.fixture
    def core(self) -> IntegrationCore:
        return IntegrationCore()

    def test_loop_with_none_delta_is_rejected(self, core):
        """is_loop=True + reasoning_delta='none' → should_reject=True."""
        reject, reason = core.check_loop_rejection(is_loop=True, reasoning_delta="none")
        assert reject is True
        assert "SEMANTIC LOOP" in reason

    def test_loop_with_weak_delta_is_rejected(self, core):
        """is_loop=True + reasoning_delta='weak' → should_reject=True."""
        reject, reason = core.check_loop_rejection(is_loop=True, reasoning_delta="weak")
        assert reject is True
        assert "SEMANTIC LOOP" in reason

    def test_loop_with_moderate_delta_is_accepted(self, core):
        """is_loop=True + reasoning_delta='moderate' → should_reject=False."""
        reject, reason = core.check_loop_rejection(is_loop=True, reasoning_delta="moderate")
        assert reject is False
        assert reason == ""

    def test_loop_with_strong_delta_is_accepted(self, core):
        """is_loop=True + reasoning_delta='strong' → should_reject=False."""
        reject, reason = core.check_loop_rejection(is_loop=True, reasoning_delta="strong")
        assert reject is False
        assert reason == ""

    def test_no_loop_with_none_delta_is_accepted(self, core):
        """is_loop=False even with delta='none' → should_reject=False (no loop flagged)."""
        reject, reason = core.check_loop_rejection(is_loop=False, reasoning_delta="none")
        assert reject is False

    def test_no_loop_with_weak_delta_is_accepted(self, core):
        """is_loop=False + reasoning_delta='weak' → should_reject=False."""
        reject, reason = core.check_loop_rejection(is_loop=False, reasoning_delta="weak")
        assert reject is False

    def test_loop_with_null_delta_is_accepted(self, core):
        """reasoning_delta=None (unknown) → should_reject=False regardless of is_loop."""
        reject, reason = core.check_loop_rejection(is_loop=True, reasoning_delta=None)
        assert reject is False

    def test_move_type_is_forwarded_in_log_without_error(self, core):
        """move_type param should not raise an error."""
        reject, _ = core.check_loop_rejection(
            is_loop=True, reasoning_delta="weak", move_type="example_only"
        )
        assert reject is True


# ---------------------------------------------------------------------------
# 37. build_loop_break_overlay — escalating loop-break overlays
# ---------------------------------------------------------------------------


class TestBuildLoopBreakOverlay:
    """Tests for IntegrationCore.build_loop_break_overlay."""

    @pytest.fixture
    def core(self) -> IntegrationCore:
        return IntegrationCore()

    def test_attempt_0_returns_first_break_overlay(self, core):
        overlay = core.build_loop_break_overlay(regen_attempt=0)
        assert "SEMANTIC LOOP REJECTED" in overlay
        assert overlay  # non-empty

    def test_attempt_1_returns_hard_break_overlay(self, core):
        overlay = core.build_loop_break_overlay(regen_attempt=1)
        assert "CRITICAL" in overlay
        assert "SECOND TIME" in overlay

    def test_attempt_2_returns_failsafe_overlay(self, core):
        overlay = core.build_loop_break_overlay(regen_attempt=2)
        assert "ESCALATION" in overlay or "REPEATED" in overlay

    def test_attempt_beyond_max_returns_failsafe(self, core):
        overlay = core.build_loop_break_overlay(regen_attempt=99)
        assert overlay  # non-empty; same as failsafe


# ---------------------------------------------------------------------------
# 38. build_loop_escalation_overlay — post-max-attempts escalation overlay
# ---------------------------------------------------------------------------


class TestBuildLoopEscalationOverlay:
    """Tests for IntegrationCore.build_loop_escalation_overlay."""

    @pytest.fixture
    def core(self) -> IntegrationCore:
        return IntegrationCore()

    def test_returns_non_empty_string(self, core):
        overlay = core.build_loop_escalation_overlay()
        assert isinstance(overlay, str)
        assert overlay

    def test_contains_loop_escalation_signal(self, core):
        overlay = core.build_loop_escalation_overlay()
        assert "LOOP ESCALATION" in overlay

    def test_enforces_no_questions_constraint(self, core):
        overlay = core.build_loop_escalation_overlay()
        assert "No philosophical questions" in overlay or "no questions" in overlay.lower()

    def test_enforces_personality_suppression(self, core):
        overlay = core.build_loop_escalation_overlay()
        assert "Personality style is disabled" in overlay or "personality" in overlay.lower()


# ---------------------------------------------------------------------------
# 39. get_loop_reset_fallback — system fallback for unresolvable loops
# ---------------------------------------------------------------------------


class TestGetLoopResetFallback:
    """Tests for IntegrationCore.get_loop_reset_fallback."""

    @pytest.fixture
    def core(self) -> IntegrationCore:
        return IntegrationCore()

    def test_returns_non_empty_string(self, core):
        text = core.get_loop_reset_fallback()
        assert isinstance(text, str)
        assert text

    def test_contains_reset_or_repeat_signal(self, core):
        text = core.get_loop_reset_fallback()
        lower = text.lower()
        assert "repeat" in lower or "reset" in lower or "progress" in lower

    def test_is_idempotent(self, core):
        assert core.get_loop_reset_fallback() == core.get_loop_reset_fallback()


# ---------------------------------------------------------------------------
# 40. ControlDecision carries is_loop and reasoning_delta from loop rule
# ---------------------------------------------------------------------------


class TestControlDecisionLoopFields:
    """is_loop and reasoning_delta are populated by _decide_loop_concrete."""

    @pytest.fixture
    def core(self) -> IntegrationCore:
        return IntegrationCore()

    def test_loop_decision_carries_is_loop_true(self, core):
        state = IntegrationState(
            agent_name="Socrates",
            semantic_repeat=True,
            loop_count=1,
            is_loop=True,
            reasoning_delta="weak",
        )
        decision = core.evaluate_turn("Socrates", state)
        assert decision.is_loop is True

    def test_loop_decision_carries_reasoning_delta(self, core):
        state = IntegrationState(
            agent_name="Socrates",
            semantic_repeat=True,
            loop_count=1,
            is_loop=True,
            reasoning_delta="none",
        )
        decision = core.evaluate_turn("Socrates", state)
        assert decision.reasoning_delta == "none"

    def test_non_loop_decision_has_default_is_loop_false(self, core):
        """A decision produced by a non-loop rule must have is_loop=False by default."""
        state = IntegrationState(
            agent_name="Socrates",
            semantic_repeat=False,
            loop_count=0,
            stagnation=0.0,
        )
        decision = core.evaluate_turn("Socrates", state)
        assert decision.is_loop is False
        assert decision.reasoning_delta is None


# ---------------------------------------------------------------------------
# New: _read_fixy_soft_signal — controller-owned Fixy hint mapping
# ---------------------------------------------------------------------------


class TestReadFixySoftSignal:
    """Unit tests for IntegrationCore._read_fixy_soft_signal.

    Verifies that the static method correctly maps Fixy's last utterance to a
    preferred IntegrationMode hint.  The mapping is controller-owned; Fixy
    never calls enforcement functions directly.
    """

    def _parse_fixy_hint(self, text: Optional[str]) -> Optional[IntegrationMode]:
        return IntegrationCore._read_fixy_soft_signal(text)

    # None / empty input ──────────────────────────────────────────────────────

    def test_none_returns_none(self):
        assert self._parse_fixy_hint(None) is None

    def test_empty_string_returns_none(self):
        assert self._parse_fixy_hint("") is None

    def test_unrelated_text_returns_none(self):
        assert self._parse_fixy_hint("Everything is fine here, good conversation.") is None

    # REQUIRE_NEW_VARIABLE ────────────────────────────────────────────────────

    def test_missing_variable_maps_to_require_new_variable(self):
        assert self._parse_fixy_hint("I notice a missing variable in this argument.") == IntegrationMode.REQUIRE_NEW_VARIABLE

    def test_new_variable_maps_to_require_new_variable(self):
        assert self._parse_fixy_hint("A new variable should be introduced here.") == IntegrationMode.REQUIRE_NEW_VARIABLE

    def test_new_dimension_maps_to_require_new_variable(self):
        assert self._parse_fixy_hint("Consider a new dimension that has not been addressed.") == IntegrationMode.REQUIRE_NEW_VARIABLE

    def test_introduce_a_variable_maps_to_require_new_variable(self):
        assert self._parse_fixy_hint("We should introduce a variable to distinguish these cases.") == IntegrationMode.REQUIRE_NEW_VARIABLE

    def test_new_concept_maps_to_require_new_variable(self):
        assert self._parse_fixy_hint("Introduce a new concept to break out of this loop.") == IntegrationMode.REQUIRE_NEW_VARIABLE

    # REQUIRE_TEST ─────────────────────────────────────────────────────────────

    def test_falsif_maps_to_require_test(self):
        assert self._parse_fixy_hint("This claim is not falsifiable as stated.") == IntegrationMode.REQUIRE_TEST

    def test_testable_maps_to_require_test(self):
        assert self._parse_fixy_hint("The argument needs a testable criterion.") == IntegrationMode.REQUIRE_TEST

    def test_no_criterion_maps_to_require_test(self):
        assert self._parse_fixy_hint("There is no criterion for distinguishing these positions.") == IntegrationMode.REQUIRE_TEST

    def test_cannot_be_tested_maps_to_require_test(self):
        assert self._parse_fixy_hint("This position cannot be tested against evidence.") == IntegrationMode.REQUIRE_TEST

    def test_untestable_maps_to_require_test(self):
        assert self._parse_fixy_hint("The claim is untestable in its current form.") == IntegrationMode.REQUIRE_TEST

    # REQUIRE_CONCRETE_CASE ────────────────────────────────────────────────────

    def test_abstract_loop_maps_to_require_concrete_case(self):
        assert self._parse_fixy_hint("We are stuck in an abstract loop without grounding.") == IntegrationMode.REQUIRE_CONCRETE_CASE

    def test_conceptual_fog_maps_to_require_concrete_case(self):
        assert self._parse_fixy_hint("There is too much conceptual fog here.") == IntegrationMode.REQUIRE_CONCRETE_CASE

    def test_too_abstract_maps_to_require_concrete_case(self):
        assert self._parse_fixy_hint("The discussion is too abstract to make progress.") == IntegrationMode.REQUIRE_CONCRETE_CASE

    def test_no_concrete_maps_to_require_concrete_case(self):
        assert self._parse_fixy_hint("No concrete example has been offered.") == IntegrationMode.REQUIRE_CONCRETE_CASE

    def test_concretize_maps_to_require_concrete_case(self):
        assert self._parse_fixy_hint("We need to concretize this argument.") == IntegrationMode.REQUIRE_CONCRETE_CASE

    # REQUIRE_BRANCH_CLOSURE ──────────────────────────────────────────────────

    def test_no_closure_maps_to_require_branch_closure(self):
        assert self._parse_fixy_hint("There is no closure to this line of argument.") == IntegrationMode.REQUIRE_BRANCH_CLOSURE

    def test_open_branch_maps_to_require_branch_closure(self):
        assert self._parse_fixy_hint("An open branch has been left unaddressed for too long.") == IntegrationMode.REQUIRE_BRANCH_CLOSURE

    def test_endless_recursion_maps_to_require_branch_closure(self):
        assert self._parse_fixy_hint("This is endless recursion without termination.") == IntegrationMode.REQUIRE_BRANCH_CLOSURE

    def test_unresolved_maps_to_require_branch_closure(self):
        assert self._parse_fixy_hint("The original question remains unresolved.") == IntegrationMode.REQUIRE_BRANCH_CLOSURE

    def test_no_resolution_maps_to_require_branch_closure(self):
        assert self._parse_fixy_hint("We have no resolution to the core tension.") == IntegrationMode.REQUIRE_BRANCH_CLOSURE

    # Priority: REQUIRE_TEST is highest ─────────────────────────────────────

    def test_test_takes_priority_over_new_variable(self):
        """REQUIRE_TEST has higher priority than REQUIRE_NEW_VARIABLE.
        When a message contains both variable and falsifiability signals,
        REQUIRE_TEST wins."""
        msg = "We are missing a new variable and the claim is not falsifiable."
        assert self._parse_fixy_hint(msg) == IntegrationMode.REQUIRE_TEST

    def test_test_takes_priority_over_branch_closure(self):
        """REQUIRE_TEST has higher priority than REQUIRE_BRANCH_CLOSURE."""
        msg = "There is no closure, and the claim is not falsifiable."
        assert self._parse_fixy_hint(msg) == IntegrationMode.REQUIRE_TEST

    # Case-insensitivity ───────────────────────────────────────────────────────

    def test_matching_is_case_insensitive(self):
        assert self._parse_fixy_hint("MISSING VARIABLE present here.") == IntegrationMode.REQUIRE_NEW_VARIABLE
        assert self._parse_fixy_hint("NOT FALSIFIABLE.") == IntegrationMode.REQUIRE_TEST
        assert self._parse_fixy_hint("ABSTRACT LOOP detected.") == IntegrationMode.REQUIRE_CONCRETE_CASE
        assert self._parse_fixy_hint("NO CLOSURE found.") == IntegrationMode.REQUIRE_BRANCH_CLOSURE


# ---------------------------------------------------------------------------
# New: soft Fixy signal integration with stagnation intervention
# ---------------------------------------------------------------------------


class TestFixySoftSignalIntegration:
    """Verify that fixy_last_message influences stagnation intervention selection
    when stagnation is active and no other higher-priority rule fires."""

    def _stagnation_signals(self, fixy_msg: Optional[str] = None) -> dict:
        """Return signals that will trigger _rule_stagnation()."""
        signals = _nominal_signals()
        signals["stagnation"] = 0.30  # above _STAGNATION_SUPPRESS_THRESHOLD
        if fixy_msg is not None:
            signals["fixy_last_message"] = fixy_msg
        return signals

    def test_no_fixy_hint_gives_epistemic_fallback(self, core):
        """Without a Fixy hint and no adversarial evidence, epistemic fallback fires."""
        decision = core.evaluate_turn("Socrates", self._stagnation_signals())
        # reasoning_delta=None → no adversarial evidence → REQUIRE_FORCED_CHOICE
        assert decision.active_mode == IntegrationMode.REQUIRE_FORCED_CHOICE
        assert decision.active_mode not in (
            IntegrationMode.ATTACK_OVERRIDE,
            IntegrationMode.REQUIRE_STRUCTURAL_CHALLENGE,
        )

    def test_missing_variable_hint_selects_require_new_variable(self, core):
        decision = core.evaluate_turn(
            "Socrates", self._stagnation_signals("I notice a missing variable here.")
        )
        assert decision.active_mode == IntegrationMode.REQUIRE_NEW_VARIABLE

    def test_hidden_variable_hint_selects_require_new_variable(self, core):
        decision = core.evaluate_turn(
            "Socrates", self._stagnation_signals("There is a hidden variable here.")
        )
        assert decision.active_mode == IntegrationMode.REQUIRE_NEW_VARIABLE

    def test_no_falsifiability_hint_selects_require_test(self, core):
        decision = core.evaluate_turn(
            "Socrates", self._stagnation_signals("The claim is not falsifiable.")
        )
        assert decision.active_mode == IntegrationMode.REQUIRE_TEST

    def test_falsifiability_keyword_selects_require_test(self, core):
        decision = core.evaluate_turn(
            "Socrates",
            self._stagnation_signals("We need to check the falsifiability of this claim."),
        )
        assert decision.active_mode == IntegrationMode.REQUIRE_TEST

    def test_observable_condition_selects_require_test(self, core):
        decision = core.evaluate_turn(
            "Socrates",
            self._stagnation_signals("What observable condition would refute this?"),
        )
        assert decision.active_mode == IntegrationMode.REQUIRE_TEST

    def test_measurable_selects_require_test(self, core):
        decision = core.evaluate_turn(
            "Socrates",
            self._stagnation_signals("Is this claim measurable?"),
        )
        assert decision.active_mode == IntegrationMode.REQUIRE_TEST

    def test_experiment_selects_require_test(self, core):
        decision = core.evaluate_turn(
            "Socrates",
            self._stagnation_signals("Can we design an experiment to verify this?"),
        )
        assert decision.active_mode == IntegrationMode.REQUIRE_TEST

    def test_conceptual_fog_hint_selects_require_concrete_case(self, core):
        decision = core.evaluate_turn(
            "Socrates", self._stagnation_signals("Too much conceptual fog here.")
        )
        assert decision.active_mode == IntegrationMode.REQUIRE_CONCRETE_CASE

    def test_too_abstract_hint_selects_require_concrete_case(self, core):
        decision = core.evaluate_turn(
            "Socrates",
            self._stagnation_signals("This is too abstract to be useful."),
        )
        assert decision.active_mode == IntegrationMode.REQUIRE_CONCRETE_CASE

    def test_no_closure_hint_selects_require_branch_closure(self, core):
        decision = core.evaluate_turn(
            "Socrates", self._stagnation_signals("There is no closure to this branch.")
        )
        assert decision.active_mode == IntegrationMode.REQUIRE_BRANCH_CLOSURE

    def test_circular_hint_selects_require_branch_closure(self, core):
        decision = core.evaluate_turn(
            "Socrates",
            self._stagnation_signals("The dialogue is becoming circular."),
        )
        assert decision.active_mode == IntegrationMode.REQUIRE_BRANCH_CLOSURE

    def test_looping_without_resolution_selects_branch_closure(self, core):
        decision = core.evaluate_turn(
            "Socrates",
            self._stagnation_signals("We are looping without resolution."),
        )
        assert decision.active_mode == IntegrationMode.REQUIRE_BRANCH_CLOSURE

    def test_priority_test_over_new_variable(self, core):
        """REQUIRE_TEST has higher priority than REQUIRE_NEW_VARIABLE."""
        decision = core.evaluate_turn(
            "Socrates",
            self._stagnation_signals(
                "There is a missing variable and the claim is not falsifiable."
            ),
        )
        assert decision.active_mode == IntegrationMode.REQUIRE_TEST

    def test_priority_test_over_branch_closure(self, core):
        """REQUIRE_TEST has higher priority than REQUIRE_BRANCH_CLOSURE."""
        decision = core.evaluate_turn(
            "Socrates",
            self._stagnation_signals(
                "No closure, and I need falsifiability here."
            ),
        )
        assert decision.active_mode == IntegrationMode.REQUIRE_TEST

    def test_priority_branch_closure_over_concrete_case(self, core):
        """REQUIRE_BRANCH_CLOSURE has higher priority than REQUIRE_CONCRETE_CASE."""
        decision = core.evaluate_turn(
            "Socrates",
            self._stagnation_signals(
                "Too abstract and there is no closure on the open branch."
            ),
        )
        assert decision.active_mode == IntegrationMode.REQUIRE_BRANCH_CLOSURE

    def test_unrelated_fixy_hint_falls_through_to_epistemic_fallback(self, core):
        """An unrecognised Fixy hint falls through; epistemic fallback fires."""
        decision = core.evaluate_turn(
            "Socrates",
            self._stagnation_signals("Interesting point, keep going."),
        )
        # No matching hint → falls through; reasoning_delta=None → REQUIRE_FORCED_CHOICE
        assert decision.active_mode == IntegrationMode.REQUIRE_FORCED_CHOICE
        assert decision.active_mode not in (
            IntegrationMode.ATTACK_OVERRIDE,
            IntegrationMode.REQUIRE_STRUCTURAL_CHALLENGE,
        )

    def test_post_dream_recovery_suppresses_structural_challenge(self, core):
        """Post-dream recovery prevents REQUIRE_STRUCTURAL_CHALLENGE from firing."""
        signals = self._stagnation_signals()
        signals["post_dream_recovery_turns"] = 1
        decision = core.evaluate_turn("Socrates", signals)
        # In recovery → DREAM_RECOVERY fires before stagnation rule
        assert decision.active_mode == IntegrationMode.DREAM_RECOVERY
        assert decision.active_mode != IntegrationMode.REQUIRE_STRUCTURAL_CHALLENGE

    def test_recovery_guard_in_decide_from_mode_blocks_attack(self, core):
        """The defence-in-depth guard in _decide_from_mode blocks adversarial modes
        when post_dream_recovery_turns > 0."""
        from entelgia.integration_core import IntegrationState
        state = IntegrationState(
            agent_name="Socrates",
            stagnation=0.40,
            reasoning_delta="moderate",
            post_dream_recovery_turns=2,
        )
        decision = core._decide_from_mode(state, IntegrationMode.REQUIRE_STRUCTURAL_CHALLENGE)
        # Should be downgraded to REQUIRE_CONCRETE_CASE by the recovery guard
        assert decision.active_mode == IntegrationMode.REQUIRE_CONCRETE_CASE
        assert decision.force_attack_mode is False

    def test_adversarial_delta_in_recovery_falls_back_to_concrete_case(self, core):
        """When reasoning_delta is moderate/strong but post_dream recovery is active,
        _decide_stagnation_intervention must fall back to REQUIRE_CONCRETE_CASE
        (not REQUIRE_FORCED_CHOICE) so the agent is guided toward concreteness."""
        from entelgia.integration_core import IntegrationState
        state = IntegrationState(
            agent_name="Athena",
            stagnation=0.45,
            reasoning_delta="moderate",
            abstraction_detected=False,
            semantic_repeat=False,
            unresolved=0,
            post_dream_recovery_turns=1,
        )
        decision = core._decide_stagnation_intervention(state, in_recovery=True)
        assert decision.active_mode == IntegrationMode.REQUIRE_CONCRETE_CASE
        assert decision.active_mode not in (
            IntegrationMode.REQUIRE_STRUCTURAL_CHALLENGE,
            IntegrationMode.ATTACK_OVERRIDE,
            IntegrationMode.REQUIRE_FORCED_CHOICE,
        )

    def test_adversarial_delta_in_recovery_strong_delta_concrete_case(self, core):
        """Same as above but with reasoning_delta='strong'."""
        from entelgia.integration_core import IntegrationState
        state = IntegrationState(
            agent_name="Socrates",
            stagnation=0.55,
            reasoning_delta="strong",
            abstraction_detected=False,
            semantic_repeat=False,
            unresolved=0,
            post_dream_recovery_turns=2,
        )
        decision = core._decide_stagnation_intervention(state, in_recovery=True)
        assert decision.active_mode == IntegrationMode.REQUIRE_CONCRETE_CASE
        assert decision.active_mode != IntegrationMode.REQUIRE_FORCED_CHOICE


# ---------------------------------------------------------------------------
# Output contract enforcement (PATCH 1 — state-transition contracts)
# ---------------------------------------------------------------------------


class TestOutputContracts:
    """Validate the new per-mode output contracts introduced by PATCH 1."""

    def _decision_for(self, core, overrides):
        signals = {**_nominal_signals(), **overrides}
        return core.pre_generation_decision("Socrates", signals)

    # REQUIRE_TEST ────────────────────────────────────────────────────────────

    def test_require_test_passes_with_all_required_fields(self, core):
        """PATCH 1 — REQUIRE_TEST requires ALL structural fields to be present."""
        decision = ControlDecision(
            active_mode=IntegrationMode.REQUIRE_TEST,
            prompt_overlay="",
        )
        text = (
            "* Hypothesis: early intervention reduces escalation.\n"
            "* Test: run a controlled study with two cohorts.\n"
            "* Expected outcome: the intervention group shows lower escalation rates.\n"
            "* If true: the hypothesis is supported and the mechanism is confirmed.\n"
            "* If false: the hypothesis must be revised or discarded."
        )
        compliant, reason = core.validate_generated_output(text, decision)
        assert compliant is True
        assert "STATE-TRANSITION-SUCCESS" in reason
        assert "valid_test=True" in reason

    def test_require_test_fails_without_all_required_fields(self, core):
        """PATCH 1 — Missing any required field causes non-compliance."""
        decision = ControlDecision(
            active_mode=IntegrationMode.REQUIRE_TEST,
            prompt_overlay="",
        )
        # Has some signals but missing required structural fields
        text = "We can test this: if the intervention is effective, we should observe a measurable improvement."
        compliant, reason = core.validate_generated_output(text, decision)
        assert compliant is False
        assert "STATE-TRANSITION-FAIL" in reason
        assert "no concrete test" in reason

    def test_require_test_fails_without_test_signal(self, core):
        decision = ControlDecision(
            active_mode=IntegrationMode.REQUIRE_TEST,
            prompt_overlay="",
        )
        text = "I believe this is an important philosophical position worth considering."
        compliant, reason = core.validate_generated_output(text, decision)
        assert compliant is False
        assert "STATE-TRANSITION-FAIL" in reason
        assert "no concrete test" in reason

    def test_require_test_fails_when_missing_if_true_and_if_false(self, core):
        """PATCH 1 — Output with hypothesis and test but no if-true/if-false fails."""
        decision = ControlDecision(
            active_mode=IntegrationMode.REQUIRE_TEST,
            prompt_overlay="",
        )
        text = (
            "* Hypothesis: early intervention helps.\n"
            "* Test: run a controlled study.\n"
            "* Expected outcome: lower escalation."
        )
        compliant, reason = core.validate_generated_output(text, decision)
        assert compliant is False
        assert "STATE-TRANSITION-FAIL" in reason

    # REQUIRE_CONCRETE_CASE ───────────────────────────────────────────────────

    def test_require_concrete_case_passes_with_real_case(self, core):
        decision = ControlDecision(
            active_mode=IntegrationMode.REQUIRE_CONCRETE_CASE,
            prompt_overlay="",
        )
        # Uses "specifically" — a concrete signal not in _PSEUDO_COMPLIANCE_TRIGGERS,
        # so detect_pseudo_compliance does not fire.
        text = (
            "Specifically, a nurse reported a medication error during the morning shift. "
            "The incident was escalated and the patient received corrective treatment."
        )
        compliant, reason = core.validate_generated_output(text, decision)
        assert compliant is True
        assert "STATE-TRANSITION-SUCCESS" in reason

    def test_require_concrete_case_fails_with_pure_abstraction(self, core):
        decision = ControlDecision(
            active_mode=IntegrationMode.REQUIRE_CONCRETE_CASE,
            prompt_overlay="",
        )
        text = "This is an abstract claim about human behaviour that applies generally."
        compliant, reason = core.validate_generated_output(text, decision)
        assert compliant is False
        assert "STATE-TRANSITION-FAIL" in reason

    # REQUIRE_COUNTEREXAMPLE (evidence contract) ──────────────────────────────

    def test_require_counterexample_passes_with_causal_explanation(self, core):
        decision = ControlDecision(
            active_mode=IntegrationMode.REQUIRE_COUNTEREXAMPLE,
            prompt_overlay="",
        )
        text = "This outcome results because of feedback loops — delayed signals cause overcorrection."
        compliant, reason = core.validate_generated_output(text, decision)
        assert compliant is True
        assert "STATE-TRANSITION-SUCCESS" in reason

    def test_require_counterexample_passes_with_evidence_keyword(self, core):
        decision = ControlDecision(
            active_mode=IntegrationMode.REQUIRE_COUNTEREXAMPLE,
            prompt_overlay="",
        )
        text = "The evidence demonstrates that early intervention reduces escalation."
        compliant, _ = core.validate_generated_output(text, decision)
        assert compliant is True

    def test_require_counterexample_fails_with_empty_assertion(self, core):
        decision = ControlDecision(
            active_mode=IntegrationMode.REQUIRE_COUNTEREXAMPLE,
            prompt_overlay="",
        )
        text = "I think this is simply how things are and always will be."
        compliant, reason = core.validate_generated_output(text, decision)
        assert compliant is False
        assert "STATE-TRANSITION-FAIL" in reason
        assert "no concrete mechanism" in reason

    # REQUIRE_FORCED_CHOICE ───────────────────────────────────────────────────

    def test_require_forced_choice_passes_with_committed_choice_and_justification(self, core):
        """PATCH 1 — REQUIRE_FORCED_CHOICE requires commitment AND justification."""
        decision = ControlDecision(
            active_mode=IntegrationMode.REQUIRE_FORCED_CHOICE,
            prompt_overlay="",
        )
        text = (
            "I choose option A: individual agency is primary, because structural forces "
            "cannot override a determined will. Structural forces are secondary."
        )
        compliant, reason = core.validate_generated_output(text, decision)
        assert compliant is True
        assert "STATE-TRANSITION-SUCCESS" in reason

    def test_require_forced_choice_fails_without_justification(self, core):
        """PATCH 1 — Commitment without justification fails."""
        decision = ControlDecision(
            active_mode=IntegrationMode.REQUIRE_FORCED_CHOICE,
            prompt_overlay="",
        )
        text = "I choose option A. Structural forces are secondary."
        compliant, reason = core.validate_generated_output(text, decision)
        assert compliant is False
        assert "STATE-TRANSITION-FAIL" in reason
        assert "no justification" in reason

    def test_require_forced_choice_passes_with_position_and_reason(self, core):
        """Position + 'because' clause satisfies the justification requirement."""
        decision = ControlDecision(
            active_mode=IntegrationMode.REQUIRE_FORCED_CHOICE,
            prompt_overlay="",
        )
        text = "My position is that determinism is correct, because causal chains are complete. Free will is an illusion."
        compliant, _ = core.validate_generated_output(text, decision)
        assert compliant is True

    def test_require_forced_choice_fails_with_hedging(self, core):
        decision = ControlDecision(
            active_mode=IntegrationMode.REQUIRE_FORCED_CHOICE,
            prompt_overlay="",
        )
        text = "Both perspectives have valid points. We should consider them together."
        compliant, reason = core.validate_generated_output(text, decision)
        assert compliant is False
        assert "STATE-TRANSITION-FAIL" in reason
        assert "no committed choice" in reason

    # REQUIRE_BRANCH_CLOSURE ──────────────────────────────────────────────────

    def test_require_branch_closure_passes_with_conclusion_and_state_marker(self, core):
        """PATCH 1 — REQUIRE_BRANCH_CLOSURE requires closure signal AND state marker."""
        decision = self._decision_for(
            core, {"unresolved": 3, "progress_after": 0.2}
        )
        assert decision.active_mode == IntegrationMode.REQUIRE_BRANCH_CLOSURE
        text = (
            "To conclude this open question: the causal link is not established — "
            "I am closing this thread as resolved."
        )
        compliant, reason = core.validate_generated_output(text, decision)
        assert compliant is True
        assert "STATE-TRANSITION-SUCCESS" in reason

    def test_require_branch_closure_passes_with_resolved_signal(self, core):
        decision = self._decision_for(
            core, {"unresolved": 3, "progress_after": 0.2}
        )
        text = "The earlier open question is now resolved: the mechanism is feedback delay."
        compliant, _ = core.validate_generated_output(text, decision)
        assert compliant is True

    def test_require_branch_closure_fails_without_state_marker(self, core):
        """PATCH 1 — Closure intent without an explicit state marker fails."""
        decision = self._decision_for(
            core, {"unresolved": 3, "progress_after": 0.2}
        )
        text = "To conclude this open question: the causal link is not established. I am closing this thread."
        compliant, reason = core.validate_generated_output(text, decision)
        assert compliant is False
        assert "STATE-TRANSITION-FAIL" in reason
        assert "state marker" in reason

    def test_require_branch_closure_fails_without_closure_signal(self, core):
        decision = self._decision_for(
            core, {"unresolved": 3, "progress_after": 0.2}
        )
        text = "I still think there are many open questions here."
        compliant, reason = core.validate_generated_output(text, decision)
        assert compliant is False
        assert "STATE-TRANSITION-FAIL" in reason


# ---------------------------------------------------------------------------
# PATCH 5 — Rhetorical escape detection in intervention modes
# ---------------------------------------------------------------------------


class TestRhetoricalEscapeDetection:
    """PATCH 5 — Outputs using 'show me', 'consider X', 'imagine if' etc. during
    intervention modes must be rejected as non-compliant."""

    def _intervention_decision(self, mode: IntegrationMode) -> ControlDecision:
        return ControlDecision(active_mode=mode, prompt_overlay="")

    def test_show_me_rejected_in_require_test_mode(self):
        core = IntegrationCore()
        decision = self._intervention_decision(IntegrationMode.REQUIRE_TEST)
        text = "Show me one example where this has been falsified and I will reconsider."
        compliant, reason = core.validate_generated_output(text, decision)
        assert compliant is False
        assert "STATE-TRANSITION-FAIL" in reason
        assert "rhetorical escape" in reason

    def test_consider_this_rejected_in_require_forced_choice_mode(self):
        core = IntegrationCore()
        decision = self._intervention_decision(IntegrationMode.REQUIRE_FORCED_CHOICE)
        text = "Consider this perspective before making a final commitment."
        compliant, reason = core.validate_generated_output(text, decision)
        assert compliant is False
        assert "rhetorical escape" in reason

    def test_imagine_if_rejected_in_require_branch_closure_mode(self):
        core = IntegrationCore()
        decision = self._intervention_decision(IntegrationMode.REQUIRE_BRANCH_CLOSURE)
        text = "Imagine if we had resolved that earlier — but I will not close it now."
        compliant, reason = core.validate_generated_output(text, decision)
        assert compliant is False
        assert "rhetorical escape" in reason

    def test_rhetorical_escape_not_triggered_in_normal_mode(self):
        """PATCH 5 — Rhetorical escape check only fires in intervention modes."""
        core = IntegrationCore()
        decision = ControlDecision(active_mode=IntegrationMode.NORMAL, prompt_overlay="")
        # Even with "consider this" in the text, NORMAL mode goes through quality gate only
        text = "Consider this a short answer."
        compliant, _ = core.validate_generated_output(text, decision)
        # NORMAL mode with short text passes quality gate regardless
        assert compliant is True

    def test_restate_opponent_rejected_in_require_concrete_case(self):
        """PATCH 5 — Restating the opponent's words is a rhetorical escape."""
        core = IntegrationCore()
        decision = self._intervention_decision(IntegrationMode.REQUIRE_CONCRETE_CASE)
        text = "As you said earlier, the argument rests on abstraction — so to use your framing."
        compliant, reason = core.validate_generated_output(text, decision)
        assert compliant is False
        assert "rhetorical escape" in reason


# ---------------------------------------------------------------------------
# PATCH 4 — Force outcome condition rule
# ---------------------------------------------------------------------------


class TestForceOutcomeRule:
    """PATCH 4 — When turns > threshold + stagnation persists, or unresolved overloads,
    the cortex enforces an outcome mode unconditionally."""

    def test_force_outcome_triggers_on_long_stagnant_conversation(self):
        """turns > FORCE_OUTCOME_TURNS_THRESHOLD and stagnation >= threshold fires."""
        from entelgia.integration_core import (
            _FORCE_OUTCOME_TURNS_THRESHOLD,
            _FORCE_OUTCOME_STAGNATION_THRESHOLD,
        )
        core = IntegrationCore()
        signals = {
            **_nominal_signals(),
            "turn_count": _FORCE_OUTCOME_TURNS_THRESHOLD + 1,
            "stagnation": _FORCE_OUTCOME_STAGNATION_THRESHOLD,
        }
        decision = core.pre_generation_decision("Socrates", signals)
        assert decision.active_mode in (
            IntegrationMode.REQUIRE_BRANCH_CLOSURE,
            IntegrationMode.REQUIRE_FORCED_CHOICE,
        )

    def test_force_outcome_triggers_on_unresolved_overload(self):
        """unresolved >= FORCE_OUTCOME_UNRESOLVED_THRESHOLD fires regardless of turns."""
        from entelgia.integration_core import _FORCE_OUTCOME_UNRESOLVED_THRESHOLD
        core = IntegrationCore()
        signals = {
            **_nominal_signals(),
            "unresolved": _FORCE_OUTCOME_UNRESOLVED_THRESHOLD,
            "turn_count": 0,  # early in conversation
        }
        decision = core.pre_generation_decision("Socrates", signals)
        assert decision.active_mode in (
            IntegrationMode.REQUIRE_BRANCH_CLOSURE,
            IntegrationMode.REQUIRE_FORCED_CHOICE,
        )

    def test_force_outcome_selects_branch_closure_when_unresolved_items_present(self):
        """With unresolved items, force-outcome chooses REQUIRE_BRANCH_CLOSURE."""
        from entelgia.integration_core import (
            _FORCE_OUTCOME_TURNS_THRESHOLD,
            _FORCE_OUTCOME_STAGNATION_THRESHOLD,
            _UNRESOLVED_RESOLUTION_TRIGGER,
        )
        core = IntegrationCore()
        signals = {
            **_nominal_signals(),
            "turn_count": _FORCE_OUTCOME_TURNS_THRESHOLD + 1,
            "stagnation": _FORCE_OUTCOME_STAGNATION_THRESHOLD,
            "unresolved": _UNRESOLVED_RESOLUTION_TRIGGER,
        }
        decision = core.pre_generation_decision("Socrates", signals)
        assert decision.active_mode == IntegrationMode.REQUIRE_BRANCH_CLOSURE

    def test_force_outcome_selects_forced_choice_without_unresolved(self):
        """Without unresolved items, force-outcome falls back to REQUIRE_FORCED_CHOICE."""
        from entelgia.integration_core import (
            _FORCE_OUTCOME_TURNS_THRESHOLD,
            _FORCE_OUTCOME_STAGNATION_THRESHOLD,
        )
        core = IntegrationCore()
        signals = {
            **_nominal_signals(),
            "turn_count": _FORCE_OUTCOME_TURNS_THRESHOLD + 1,
            "stagnation": _FORCE_OUTCOME_STAGNATION_THRESHOLD,
            "unresolved": 0,
        }
        decision = core.pre_generation_decision("Socrates", signals)
        assert decision.active_mode == IntegrationMode.REQUIRE_FORCED_CHOICE

    def test_force_outcome_does_not_trigger_below_threshold(self):
        """Below both thresholds, force-outcome rule does not fire."""
        from entelgia.integration_core import (
            _FORCE_OUTCOME_TURNS_THRESHOLD,
            _FORCE_OUTCOME_STAGNATION_THRESHOLD,
            _FORCE_OUTCOME_UNRESOLVED_THRESHOLD,
        )
        core = IntegrationCore()
        signals = {
            **_nominal_signals(),
            # Keep stagnation below _STAGNATION_SUPPRESS_THRESHOLD (0.25) to avoid
            # triggering other stagnation rules at the same time.
            "stagnation": 0.1,
            "turn_count": _FORCE_OUTCOME_TURNS_THRESHOLD - 1,
            "unresolved": min(_FORCE_OUTCOME_UNRESOLVED_THRESHOLD - 1, 1),
        }
        decision = core.pre_generation_decision("Socrates", signals)
        # Should be NORMAL (no other trigger active in nominal signals)
        assert decision.active_mode == IntegrationMode.NORMAL


# ---------------------------------------------------------------------------
# PATCH 6 — Logging: valid_test=True in REQUIRE_TEST success
# ---------------------------------------------------------------------------


class TestPatch6Logging:
    """PATCH 6 — Structured log fields emitted for state transitions."""

    def test_require_test_success_log_includes_valid_test_flag(self):
        """[STATE-TRANSITION-SUCCESS] for REQUIRE_TEST includes valid_test=True."""
        core = IntegrationCore()
        decision = ControlDecision(
            active_mode=IntegrationMode.REQUIRE_TEST,
            prompt_overlay="",
        )
        text = (
            "* Hypothesis: intervention reduces escalation.\n"
            "* Test: run a controlled trial.\n"
            "* Expected outcome: lower rates in treatment group.\n"
            "* If true: hypothesis confirmed.\n"
            "* If false: hypothesis must be revised."
        )
        compliant, reason = core.validate_generated_output(text, decision)
        assert compliant is True
        assert "valid_test=True" in reason

    def test_state_transition_fail_in_reason_string(self):
        """[STATE-TRANSITION-FAIL] appears in reason when mode contract is violated."""
        core = IntegrationCore()
        decision = ControlDecision(
            active_mode=IntegrationMode.REQUIRE_TEST,
            prompt_overlay="",
        )
        text = "This is a purely philosophical position."
        compliant, reason = core.validate_generated_output(text, decision)
        assert compliant is False
        assert "STATE-TRANSITION-FAIL" in reason

    def test_require_test_all_fields_present_passes_contract(self):
        """Full structured test with all 5 fields passes the PATCH 1 contract."""
        core = IntegrationCore()
        decision = ControlDecision(
            active_mode=IntegrationMode.REQUIRE_TEST,
            prompt_overlay="",
        )
        text = (
            "Hypothesis: X causes Y.\n"
            "Test: apply X to group A and not group B.\n"
            "Expected outcome: group A shows higher Y.\n"
            "If true: causal link is supported.\n"
            "If false: alternative explanations must be explored."
        )
        compliant, reason = core.validate_generated_output(text, decision)
        assert compliant is True
        assert "STATE-TRANSITION-SUCCESS" in reason

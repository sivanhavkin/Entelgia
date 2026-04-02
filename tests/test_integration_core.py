#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Unit tests for entelgia/integration_core.py (ExecutiveCortex).

Covers:
  1. IntegrationState construction from raw dict (happy path + unknown keys)
  2. ControlDecision defaults
  3. Rule: loop + semantic_repeat -> CONCRETE_OVERRIDE
  4. Rule: semantic_repeat + stagnation -> PERSONALITY_SUPPRESSION
  5. Rule: unresolved + low progress -> RESOLUTION_OVERRIDE
  6. Rule: fatigue -> LOW_COMPLEXITY
  7. Rule: is_loop + superficial compliance -> FIXY_AUTHORITY_OVERRIDE + regenerate=True
  8. Rule: stagnation alone -> ATTACK_OVERRIDE
  9. Rule: pressure misalignment -> overlay injected, mode=NORMAL
  10. No override when all signals are nominal -> mode=NORMAL, no regen
  11. build_prompt_overlay returns decision.prompt_overlay
  12. should_regenerate returns True iff decision.regenerate is True
  13. Priority: FIXY_AUTHORITY_OVERRIDE beats CONCRETE_OVERRIDE
  14. Priority: CONCRETE_OVERRIDE beats ATTACK_OVERRIDE
  15. make_integration_state factory helper
  16. evaluate_turn accepts state_dict directly (integration path)
  17. Overlay text is imperative (no "consider")
  18. FIXY_AUTHORITY_OVERRIDE forces enforce_fixy=True
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
# 5. Rule: unresolved + low progress -> RESOLUTION_OVERRIDE
# ---------------------------------------------------------------------------


class TestRuleResolutionOverride:
    def test_triggers_resolution_override(self, core):
        signals = _nominal_signals()
        signals["unresolved"] = 3
        signals["progress_after"] = 0.3
        decision = core.evaluate_turn("Socrates", signals)
        assert decision.active_mode == IntegrationMode.RESOLUTION_OVERRIDE
        assert decision.force_resolution_mode is True

    def test_not_triggered_when_progress_sufficient(self, core):
        signals = _nominal_signals()
        signals["unresolved"] = 4
        signals["progress_after"] = 0.7
        decision = core.evaluate_turn("Socrates", signals)
        assert decision.active_mode != IntegrationMode.RESOLUTION_OVERRIDE

    def test_not_triggered_when_unresolved_below_threshold(self, core):
        signals = _nominal_signals()
        signals["unresolved"] = 2
        signals["progress_after"] = 0.2
        decision = core.evaluate_turn("Socrates", signals)
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
# 7. Rule: is_loop + superficial compliance -> FIXY_AUTHORITY_OVERRIDE
# ---------------------------------------------------------------------------


class TestRuleFixyAuthority:
    def test_triggers_fixy_authority(self, core):
        signals = _nominal_signals()
        signals["is_loop"] = True
        signals["compliance"] = False
        decision = core.evaluate_turn("Socrates", signals)
        assert decision.active_mode == IntegrationMode.FIXY_AUTHORITY_OVERRIDE
        assert decision.enforce_fixy is True
        assert decision.regenerate is True

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
# 8. Rule: stagnation alone -> ATTACK_OVERRIDE
# ---------------------------------------------------------------------------


class TestRuleStagnationAttack:
    def test_triggers_attack_override(self, core):
        signals = _nominal_signals()
        signals["stagnation"] = 0.40
        decision = core.evaluate_turn("Socrates", signals)
        assert decision.active_mode == IntegrationMode.ATTACK_OVERRIDE
        assert decision.force_attack_mode is True
        assert decision.suppress_personality is True

    def test_not_triggered_below_threshold(self, core):
        signals = _nominal_signals()
        signals["stagnation"] = 0.10
        decision = core.evaluate_turn("Socrates", signals)
        assert decision.active_mode != IntegrationMode.ATTACK_OVERRIDE


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
    def test_true_when_fixy_authority(self, core):
        signals = _nominal_signals()
        signals["is_loop"] = True
        signals["compliance"] = False
        decision = core.evaluate_turn("Socrates", signals)
        assert core.should_regenerate(decision) is True

    def test_false_on_nominal(self, core):
        decision = core.evaluate_turn("Socrates", _nominal_signals())
        assert core.should_regenerate(decision) is False


# ---------------------------------------------------------------------------
# 13. Priority: FIXY_AUTHORITY_OVERRIDE beats CONCRETE_OVERRIDE
# ---------------------------------------------------------------------------


class TestPriorityFixyBeforeConcrete:
    def test_fixy_wins(self, core):
        signals = _nominal_signals()
        # Both rules would fire
        signals["is_loop"] = True
        signals["compliance"] = False
        signals["semantic_repeat"] = True
        signals["loop_count"] = 2
        decision = core.evaluate_turn("Socrates", signals)
        assert decision.active_mode == IntegrationMode.FIXY_AUTHORITY_OVERRIDE


# ---------------------------------------------------------------------------
# 14. Priority: CONCRETE_OVERRIDE beats ATTACK_OVERRIDE
# ---------------------------------------------------------------------------


class TestPriorityConcreteBeforeAttack:
    def test_concrete_wins(self, core):
        signals = _nominal_signals()
        signals["semantic_repeat"] = True
        signals["loop_count"] = 1
        signals["stagnation"] = 0.30  # would trigger ATTACK_OVERRIDE alone
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
        {"is_loop": True, "compliance": False},
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
# 18. FIXY_AUTHORITY_OVERRIDE enforces enforce_fixy=True
# ---------------------------------------------------------------------------


class TestFixyAuthorityEnforcesFlag:
    def test_enforce_fixy_is_true(self, core):
        signals = _nominal_signals()
        signals["is_loop"] = True
        signals["compliance"] = False
        decision = core.evaluate_turn("Socrates", signals)
        assert decision.enforce_fixy is True

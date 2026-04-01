#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Tests for Soft Fixy Enforcement v1.

Covers:
  1. MOVE_TYPES list completeness
  2. FixyGuidance dataclass construction and field access
  3. _build_guidance — maps reasons to correct (goal, preferred_move, confidence)
  4. _build_guidance — confidence boost when same goal recurs in recent_fixy_goals
  5. record_agent_move — resets ignored_guidance_count on compliance
  6. record_agent_move — increments ignored_guidance_count on non-compliance
  7. record_agent_move — boosts confidence after 2+ ignored turns
  8. should_intervene — populates fixy_guidance on intervention
  9. should_intervene — fixy_guidance is None when no intervention
  10. SeedGenerator — guidance biases strategy weights (preferred move gets boost)
  11. SeedGenerator — backward compat when fixy_guidance=None
  12. DialogueEngine.generate_seed — passes guidance through to SeedGenerator
"""

import sys
import os
import random

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from entelgia.fixy_interactive import (
    MOVE_TYPES,
    FixyGuidance,
    InteractiveFixy,
    _REASON_GUIDANCE_MAP,
)
from entelgia.dialogue_engine import SeedGenerator, DialogueEngine


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _make_turns(texts, roles=None):
    """Build a list of turn dicts. Alternates Socrates/Athena by default."""
    if roles is None:
        agent_names = ["Socrates", "Athena"]
        roles = [agent_names[i % 2] for i in range(len(texts))]
    return [{"role": r, "text": t} for r, t in zip(roles, texts)]


def _make_fixy(tmp_path=None):
    """Build a minimal InteractiveFixy with a stub LLM."""

    class _StubLLM:
        def generate(self, model, prompt, **kw):
            return "stub"

    return InteractiveFixy(llm=_StubLLM(), model="stub-model")


class _FakeSpeaker:
    name = "Socrates"

    def conflict_index(self):
        return 5.0


# ---------------------------------------------------------------------------
# 1. MOVE_TYPES completeness
# ---------------------------------------------------------------------------


class TestMoveTypes:
    def test_required_move_types_present(self):
        required = {"NEW_CLAIM", "DIRECT_ATTACK", "EXAMPLE", "TEST", "CONCESSION", "NEW_FRAME"}
        assert required.issubset(set(MOVE_TYPES)), (
            f"Missing required move types: {required - set(MOVE_TYPES)}"
        )

    def test_move_types_are_strings(self):
        for mt in MOVE_TYPES:
            assert isinstance(mt, str)

    def test_no_duplicate_move_types(self):
        assert len(MOVE_TYPES) == len(set(MOVE_TYPES)), "MOVE_TYPES contains duplicates"


# ---------------------------------------------------------------------------
# 2. FixyGuidance dataclass
# ---------------------------------------------------------------------------


class TestFixyGuidance:
    def test_construction(self):
        g = FixyGuidance(
            goal="define_test",
            preferred_move="TEST",
            confidence=0.7,
            reason="premature_synthesis",
        )
        assert g.goal == "define_test"
        assert g.preferred_move == "TEST"
        assert g.confidence == pytest.approx(0.7)
        assert g.reason == "premature_synthesis"

    def test_confidence_mutable(self):
        g = FixyGuidance(goal="x", preferred_move="TEST", confidence=0.5, reason="y")
        g.confidence = 0.9
        assert g.confidence == pytest.approx(0.9)


# ---------------------------------------------------------------------------
# 3 & 4. _build_guidance
# ---------------------------------------------------------------------------


class TestBuildGuidance:
    def test_known_reason_returns_guidance(self):
        fixy = _make_fixy()
        g = fixy._build_guidance("premature_synthesis")
        assert g is not None
        assert g.preferred_move == "TEST"
        assert g.goal == "define_test"
        assert 0.0 < g.confidence <= 1.0

    def test_unknown_reason_returns_none(self):
        fixy = _make_fixy()
        g = fixy._build_guidance("nonexistent_reason")
        assert g is None

    def test_all_mapped_reasons_build_guidance(self):
        fixy = _make_fixy()
        for reason in _REASON_GUIDANCE_MAP:
            g = fixy._build_guidance(reason)
            assert g is not None, f"No guidance for reason {reason!r}"
            assert g.preferred_move in MOVE_TYPES, (
                f"preferred_move {g.preferred_move!r} not in MOVE_TYPES"
            )

    def test_confidence_boosted_on_goal_recurrence(self):
        fixy = _make_fixy()
        # First call — baseline confidence
        g1 = fixy._build_guidance("premature_synthesis")
        base_confidence = _REASON_GUIDANCE_MAP["premature_synthesis"][2]
        assert g1 is not None
        assert g1.confidence == pytest.approx(base_confidence)

        # Second call with same reason — same goal recurs, confidence should rise
        g2 = fixy._build_guidance("premature_synthesis")
        assert g2 is not None
        assert g2.confidence > base_confidence

    def test_goal_appended_to_recent_fixy_goals(self):
        fixy = _make_fixy()
        assert len(fixy.recent_fixy_goals) == 0
        fixy._build_guidance("loop_repetition")
        assert len(fixy.recent_fixy_goals) == 1
        fixy._build_guidance("loop_repetition")
        assert len(fixy.recent_fixy_goals) == 2

    def test_recent_fixy_goals_maxlen(self):
        fixy = _make_fixy()
        for _ in range(10):
            fixy._build_guidance("loop_repetition")
        assert len(fixy.recent_fixy_goals) == 3  # maxlen=3


# ---------------------------------------------------------------------------
# 5, 6 & 7. record_agent_move
# ---------------------------------------------------------------------------


class TestRecordAgentMove:
    def test_no_guidance_is_noop(self):
        fixy = _make_fixy()
        fixy.record_agent_move("TEST")  # should not raise

    def test_matching_move_resets_counter(self):
        fixy = _make_fixy()
        fixy.fixy_guidance = FixyGuidance(
            goal="define_test", preferred_move="TEST", confidence=0.7,
            reason="premature_synthesis"
        )
        fixy.ignored_guidance_count = 3
        fixy.record_agent_move("TEST")
        assert fixy.ignored_guidance_count == 0

    def test_non_matching_move_increments_counter(self):
        fixy = _make_fixy()
        fixy.fixy_guidance = FixyGuidance(
            goal="define_test", preferred_move="TEST", confidence=0.7,
            reason="premature_synthesis"
        )
        fixy.record_agent_move("NEW_CLAIM")
        assert fixy.ignored_guidance_count == 1

    def test_two_ignored_turns_boosts_confidence(self):
        fixy = _make_fixy()
        fixy.fixy_guidance = FixyGuidance(
            goal="define_test", preferred_move="TEST", confidence=0.7,
            reason="premature_synthesis"
        )
        fixy.record_agent_move("NEW_CLAIM")   # count = 1
        fixy.record_agent_move("NEW_CLAIM")   # count = 2 → boost
        assert fixy.fixy_guidance.confidence > 0.7

    def test_confidence_capped_at_one(self):
        fixy = _make_fixy()
        fixy.fixy_guidance = FixyGuidance(
            goal="define_test", preferred_move="TEST", confidence=0.99,
            reason="premature_synthesis"
        )
        fixy.ignored_guidance_count = 2
        fixy.record_agent_move("NEW_CLAIM")  # ignored_count = 3, boost
        assert fixy.fixy_guidance.confidence <= 1.0


# ---------------------------------------------------------------------------
# 8 & 9. should_intervene populates fixy_guidance
# ---------------------------------------------------------------------------


class TestShouldInterveneSetsGuidance:
    def _repetitive_dialog(self, n=6):
        texts = [
            "freedom autonomy liberty independence means personal freedom",
            "autonomy liberty freedom independence are fundamental values",
            "liberty means freedom autonomy personal independence always",
            "independence freedom liberty autonomy interrelated core concepts",
            "freedom liberty autonomy independence personal core values",
            "autonomy independence liberty freedom personal self-determination",
        ][:n]
        return _make_turns(texts)

    def test_guidance_populated_on_intervention(self):
        fixy = _make_fixy()
        dialog = self._repetitive_dialog(6)
        result, reason = fixy.should_intervene(dialog, turn_count=6)
        if result:
            # If Fixy decided to intervene, guidance must be set
            assert fixy.fixy_guidance is not None

    def test_guidance_none_when_no_intervention(self):
        fixy = _make_fixy()
        # Very short dialogue — pair gate not met
        dialog = _make_turns(["hello there"], roles=["Socrates"])
        result, _ = fixy.should_intervene(dialog, turn_count=1)
        assert result is False
        # guidance should remain None (not set for non-interventions)
        assert fixy.fixy_guidance is None

    def test_guidance_preferred_move_in_move_types(self):
        fixy = _make_fixy()
        dialog = self._repetitive_dialog(6)
        result, reason = fixy.should_intervene(dialog, turn_count=6)
        if result and fixy.fixy_guidance is not None:
            assert fixy.fixy_guidance.preferred_move in MOVE_TYPES


# ---------------------------------------------------------------------------
# 10 & 11. SeedGenerator guidance biasing
# ---------------------------------------------------------------------------


class TestSeedGeneratorGuidance:
    def test_guidance_none_backward_compat(self):
        sg = SeedGenerator()
        speaker = _FakeSpeaker()
        recent = _make_turns(["hello"], roles=["Socrates"])
        seed = sg.generate_seed("free will", recent, speaker, turn_count=2)
        assert isinstance(seed, str)
        assert len(seed) > 0

    def test_guidance_biases_strategy(self):
        """Guidance with TEST preferred_move must shift distribution toward
        explore_implication / question_assumption and away from agree_and_expand."""
        sg = SeedGenerator()
        guidance = FixyGuidance(
            goal="define_test", preferred_move="TEST", confidence=1.0,
            reason="premature_synthesis"
        )
        speaker = _FakeSpeaker()
        recent = _make_turns(
            ["The claim here is that freedom presupposes responsibility."],
            roles=["Socrates"]
        )

        # Run many iterations and collect chosen strategies
        random.seed(42)
        strategies_without = []
        strategies_with = []
        for _ in range(200):
            # Capture the strategy by monkeypatching choices
            selected = []

            original_choices = random.choices

            def capturing_choices(population, weights=None, k=1):
                result = original_choices(population, weights=weights, k=k)
                selected.extend(result)
                return result

            random.choices = capturing_choices
            sg.generate_seed("free will", recent, speaker, turn_count=2)
            random.choices = original_choices
            strategies_without.append(selected[0] if selected else None)

        random.seed(42)
        for _ in range(200):
            selected = []
            original_choices = random.choices

            def capturing_choices(population, weights=None, k=1):
                result = original_choices(population, weights=weights, k=k)
                selected.extend(result)
                return result

            random.choices = capturing_choices
            sg.generate_seed(
                "free will", recent, speaker, turn_count=2, fixy_guidance=guidance
            )
            random.choices = original_choices
            strategies_with.append(selected[0] if selected else None)

        boosted = {"explore_implication", "question_assumption"}
        without_boost_count = sum(1 for s in strategies_without if s in boosted)
        with_boost_count = sum(1 for s in strategies_with if s in boosted)

        # With TEST guidance the boosted strategies should appear more often
        assert with_boost_count > without_boost_count, (
            f"Expected more boosted strategies with guidance: "
            f"without={without_boost_count}, with={with_boost_count}"
        )

    def test_guidance_does_not_force_single_strategy(self):
        """Even with guidance, multiple strategies should still appear."""
        sg = SeedGenerator()
        guidance = FixyGuidance(
            goal="define_test", preferred_move="TEST", confidence=1.0,
            reason="premature_synthesis"
        )
        speaker = _FakeSpeaker()
        recent = _make_turns(
            ["Some claim about freedom."],
            roles=["Socrates"]
        )
        strategies_seen = set()
        random.seed(0)
        for _ in range(100):
            selected = []
            original_choices = random.choices

            def capturing_choices(population, weights=None, k=1):
                result = original_choices(population, weights=weights, k=k)
                selected.extend(result)
                return result

            random.choices = capturing_choices
            sg.generate_seed(
                "free will", recent, speaker, turn_count=2, fixy_guidance=guidance
            )
            random.choices = original_choices
            if selected:
                strategies_seen.add(selected[0])

        # Must see at least 2 distinct strategies (not locked to one)
        assert len(strategies_seen) >= 2, (
            f"Strategy selection is too deterministic: {strategies_seen}"
        )


# ---------------------------------------------------------------------------
# 12. DialogueEngine.generate_seed passes guidance through
# ---------------------------------------------------------------------------


class TestDialogueEngineGuidancePassthrough:
    def test_guidance_forwarded_no_error(self):
        engine = DialogueEngine()
        guidance = FixyGuidance(
            goal="break_repetition", preferred_move="NEW_FRAME", confidence=0.6,
            reason="loop_repetition"
        )
        speaker = _FakeSpeaker()
        dialog = _make_turns(["hello there"], roles=["Socrates"])
        seed = engine.generate_seed(
            "free will", dialog, speaker, turn_count=2, fixy_guidance=guidance
        )
        assert isinstance(seed, str)
        assert len(seed) > 0

    def test_backward_compat_no_guidance(self):
        engine = DialogueEngine()
        speaker = _FakeSpeaker()
        dialog = _make_turns(["hello there"], roles=["Socrates"])
        seed = engine.generate_seed("free will", dialog, speaker, turn_count=2)
        assert isinstance(seed, str)

#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Tests for Soft Fixy Enforcement v1 and v2.

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

  Soft Fixy v2:
  13. build_guidance_prompt_hint — returns correct hint for each move type
  14. build_guidance_prompt_hint — returns empty string when guidance is None
  15. SeedGenerator.generate_seed — includes hint text when fixy_guidance exists
  16. SeedGenerator.generate_seed — no hint when fixy_guidance is None
  17. score_progress — soft penalty when ignored_guidance_count >= 2
  18. score_progress — stronger penalty when ignored_guidance_count >= 3
  19. score_progress — mismatch penalty when actual move != preferred move
  20. score_progress — compliance reward when actual move == preferred move
  21. score_progress — backward compat when no guidance (existing callers unchanged)
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
    build_guidance_prompt_hint,
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


# ===========================================================================
# Soft Fixy v2 tests
# ===========================================================================

# ---------------------------------------------------------------------------
# 13 & 14. build_guidance_prompt_hint
# ---------------------------------------------------------------------------


class TestBuildGuidancePromptHint:
    def test_returns_empty_when_no_guidance(self):
        assert build_guidance_prompt_hint(None) == ""

    def test_example_hint(self):
        g = FixyGuidance(goal="g", preferred_move="EXAMPLE", confidence=0.8, reason="r")
        hint = build_guidance_prompt_hint(g)
        assert hint != ""
        assert "example" in hint.lower()

    def test_test_hint(self):
        g = FixyGuidance(goal="g", preferred_move="TEST", confidence=0.8, reason="r")
        hint = build_guidance_prompt_hint(g)
        assert hint != ""
        assert any(kw in hint.lower() for kw in ("falsifiable", "observable", "prove"))

    def test_concession_hint(self):
        g = FixyGuidance(goal="g", preferred_move="CONCESSION", confidence=0.8, reason="r")
        hint = build_guidance_prompt_hint(g)
        assert hint != ""
        assert any(kw in hint.lower() for kw in ("weakness", "blind spot", "acknowledge"))

    def test_new_frame_hint(self):
        g = FixyGuidance(goal="g", preferred_move="NEW_FRAME", confidence=0.8, reason="r")
        hint = build_guidance_prompt_hint(g)
        assert hint != ""
        assert any(kw in hint.lower() for kw in ("frame", "domain", "shift"))

    def test_direct_attack_hint(self):
        g = FixyGuidance(goal="g", preferred_move="DIRECT_ATTACK", confidence=0.8, reason="r")
        hint = build_guidance_prompt_hint(g)
        assert hint != ""
        assert any(kw in hint.lower() for kw in ("challenge", "assumption", "directly"))

    def test_new_claim_hint(self):
        g = FixyGuidance(goal="g", preferred_move="NEW_CLAIM", confidence=0.8, reason="r")
        hint = build_guidance_prompt_hint(g)
        assert hint != ""
        assert any(kw in hint.lower() for kw in ("new", "distinction", "variable"))

    def test_all_move_types_covered(self):
        """Every MOVE_TYPE must produce a non-empty hint."""
        for move in MOVE_TYPES:
            g = FixyGuidance(goal="g", preferred_move=move, confidence=0.7, reason="r")
            hint = build_guidance_prompt_hint(g)
            assert hint != "", f"No hint defined for move type {move!r}"

    def test_unknown_move_returns_empty(self):
        g = FixyGuidance(goal="g", preferred_move="UNKNOWN_MOVE_XYZ", confidence=0.5, reason="r")
        hint = build_guidance_prompt_hint(g)
        assert hint == ""


# ---------------------------------------------------------------------------
# 15 & 16. SeedGenerator.generate_seed includes / excludes hint
# ---------------------------------------------------------------------------


class TestSeedGeneratorGuidanceHint:
    def test_hint_present_in_seed_when_guidance_given(self):
        sg = SeedGenerator()
        guidance = FixyGuidance(
            goal="define_test", preferred_move="TEST", confidence=0.9,
            reason="premature_synthesis"
        )
        speaker = _FakeSpeaker()
        recent = _make_turns(["consciousness is fundamental"], roles=["Socrates"])
        seed = sg.generate_seed("free will", recent, speaker, turn_count=2,
                                fixy_guidance=guidance)
        # The seed should contain the guidance hint text
        expected_hint = build_guidance_prompt_hint(guidance)
        assert expected_hint in seed, (
            f"Expected hint {expected_hint!r} to appear in seed {seed!r}"
        )

    def test_no_hint_in_seed_when_no_guidance(self):
        sg = SeedGenerator()
        speaker = _FakeSpeaker()
        recent = _make_turns(["consciousness is fundamental"], roles=["Socrates"])
        seed = sg.generate_seed("free will", recent, speaker, turn_count=2)
        assert "[GUIDANCE HINT]" not in seed, (
            "No guidance hint should appear when fixy_guidance is None"
        )

    def test_hint_not_added_for_unknown_move(self):
        """If build_guidance_prompt_hint returns empty, no hint tag should appear."""
        sg = SeedGenerator()
        guidance = FixyGuidance(
            goal="g", preferred_move="UNKNOWN_MOVE_XYZ", confidence=0.5, reason="r"
        )
        speaker = _FakeSpeaker()
        recent = _make_turns(["some text"], roles=["Socrates"])
        seed = sg.generate_seed("free will", recent, speaker, turn_count=2,
                                fixy_guidance=guidance)
        assert "[GUIDANCE HINT]" not in seed


# ---------------------------------------------------------------------------
# 17–21. score_progress guidance-based adjustments
# ---------------------------------------------------------------------------


class TestScoreProgressGuidanceAdjustments:
    """Tests for Soft Fixy v2 progress score adjustments."""

    def _make_mem(self):
        from entelgia.progress_enforcer import ClaimsMemory
        return ClaimsMemory()

    def test_no_penalty_with_zero_ignored(self):
        """Baseline: no penalty when ignored_guidance_count=0."""
        from entelgia.progress_enforcer import score_progress
        mem = self._make_mem()
        guidance = FixyGuidance(goal="g", preferred_move="NEW_FRAME", confidence=0.5, reason="r")
        score_no_penalty = score_progress(
            "The brain computes representations independently of experience.",
            [], mem, ignored_guidance_count=0,
        )
        score_with_guidance = score_progress(
            "The brain computes representations independently of experience.",
            [], self._make_mem(), fixy_guidance=guidance, ignored_guidance_count=0,
        )
        # Both should be valid floats in [0, 1]
        assert 0.0 <= score_no_penalty <= 1.0
        assert 0.0 <= score_with_guidance <= 1.0

    def test_penalty_applied_at_count_2(self):
        """Score must be lower when ignored_guidance_count >= 2."""
        from entelgia.progress_enforcer import score_progress
        text = "The brain computes representations independently of experience."
        score_base = score_progress(text, [], self._make_mem(), ignored_guidance_count=0)
        score_penalised = score_progress(text, [], self._make_mem(), ignored_guidance_count=2)
        # The penalty multiplier is 0.85 — score should decrease
        assert score_penalised <= score_base, (
            f"Expected penalty at count=2: base={score_base:.3f}, "
            f"penalised={score_penalised:.3f}"
        )

    def test_stronger_penalty_at_count_3(self):
        """Score at count=3 must be <= score at count=2."""
        from entelgia.progress_enforcer import score_progress
        text = "The brain computes representations independently of experience."
        score_2 = score_progress(text, [], self._make_mem(), ignored_guidance_count=2)
        score_3 = score_progress(text, [], self._make_mem(), ignored_guidance_count=3)
        assert score_3 <= score_2, (
            f"Expected score at count=3 <= count=2: "
            f"count2={score_2:.3f}, count3={score_3:.3f}"
        )

    def test_score_capped_at_count_3(self):
        """Score must not exceed 0.55 when ignored_guidance_count >= 3."""
        from entelgia.progress_enforcer import score_progress
        # Use a highly positive text to get a high base score
        text = (
            "I reject the claim entirely. Consciousness cannot be physical "
            "because physical systems are closed under causation. Therefore, "
            "qualia are irreducible. This is a falsifiable claim: if you can "
            "produce a physical account of phenomenal redness, I retract."
        )
        score_capped = score_progress(text, [], self._make_mem(), ignored_guidance_count=3)
        assert score_capped <= 0.55, (
            f"Expected score capped at 0.55 with ignored_count=3, got {score_capped:.3f}"
        )

    def test_score_never_zeroed(self):
        """Penalty must not zero out the score (system must remain non-blocking)."""
        from entelgia.progress_enforcer import score_progress
        text = "The brain computes representations independently of experience."
        score = score_progress(text, [], self._make_mem(), ignored_guidance_count=10)
        assert score > 0.0, "Penalty must not zero the progress score"

    def test_mismatch_penalty_applied(self):
        """Score is reduced when actual move differs from preferred_move."""
        from entelgia.progress_enforcer import score_progress, classify_move
        # Use a text that very reliably classifies as PARAPHRASE / BALANCED_RESTATEMENT
        # (low-value move) and prefer TEST (a different move type).
        text = "Both perspectives have merit and should be weighed carefully."
        actual_move = classify_move(text, [])
        # Ensure our chosen text does NOT classify as TEST; if the classifier
        # is ever changed, we still want the test to be meaningful.
        preferred = "TEST" if actual_move != "TEST" else "EXAMPLE"
        guidance = FixyGuidance(
            goal="g", preferred_move=preferred, confidence=1.0, reason="r"
        )
        score_with_guidance = score_progress(text, [], self._make_mem(), fixy_guidance=guidance)
        score_no_guidance = score_progress(text, [], self._make_mem())
        assert score_with_guidance <= score_no_guidance, (
            f"Mismatch penalty not applied: no_guidance={score_no_guidance:.3f}, "
            f"with_guidance={score_with_guidance:.3f} "
            f"(actual_move={actual_move!r}, preferred={preferred!r})"
        )

    def test_compliance_reward_applied(self):
        """Score increases slightly when actual move matches preferred_move."""
        from entelgia.progress_enforcer import score_progress, classify_move
        text = "Consciousness is irreducibly subjective and cannot be explained physically."
        mem = self._make_mem()
        actual_move = classify_move(text, [])
        guidance = FixyGuidance(
            goal="g", preferred_move=actual_move, confidence=1.0, reason="r"
        )
        score_with_guidance = score_progress(text, [], mem, fixy_guidance=guidance)
        score_no_guidance = score_progress(text, [], self._make_mem())
        assert score_with_guidance >= score_no_guidance, (
            f"Compliance reward not applied: no_guidance={score_no_guidance:.3f}, "
            f"with_guidance={score_with_guidance:.3f} (move={actual_move!r})"
        )

    def test_backward_compat_no_guidance_no_ignored(self):
        """Calling score_progress without new params behaves as before."""
        from entelgia.progress_enforcer import score_progress
        mem = self._make_mem()
        score = score_progress(
            "The brain computes representations independently of experience.",
            [], mem,
        )
        assert 0.0 <= score <= 1.0

    def test_score_always_in_range(self):
        """score_progress must always return a value in [0.0, 1.0]."""
        from entelgia.progress_enforcer import score_progress
        texts = [
            "yes",
            "I completely reject this. Freedom is an illusion.",
            "Both sides have merit and should be balanced carefully.",
        ]
        for text in texts:
            for count in (0, 2, 3, 5):
                score = score_progress(text, [], self._make_mem(),
                                       ignored_guidance_count=count)
                assert 0.0 <= score <= 1.0, (
                    f"score={score} out of range for text={text!r}, count={count}"
                )

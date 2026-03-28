#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Tests for entelgia/response_evaluator.py.

Covers:
  Step 1 — evaluate_response (linguistic quality)
  1. evaluate_response — return type and range
  2. Empty / trivial inputs
  3. Lexical diversity contribution
  4. Specificity contribution (numbers, named entities)
  5. Depth / length contribution
  6. Hedge penalty
  7. Short vs. rich responses produce different scores

  Step 2 — evaluate_dialogue_movement
  8. is_new_claim — similarity threshold
  9. is_semantic_repeat — similarity threshold
  10. creates_pressure — keyword detection
  11. shows_resolution — keyword detection
  12. evaluate_dialogue_movement — range, base score, bonuses, penalties
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

import entelgia.response_evaluator as resp_eval
from entelgia.response_evaluator import (
    evaluate_response,
    evaluate_dialogue_movement,
    evaluate_dialogue_movement_with_signals,
    is_new_claim,
    is_semantic_repeat,
    creates_pressure,
    shows_resolution,
)


# ---------------------------------------------------------------------------
# 1.  Return type and range
# ---------------------------------------------------------------------------


class TestReturnTypeAndRange:
    def test_returns_float(self):
        result = evaluate_response("The mind is distinct from the body.", [])
        assert isinstance(result, float)

    def test_within_range(self):
        result = evaluate_response("Consciousness cannot be reduced to neurons.", [])
        assert 0.0 <= result <= 1.0

    def test_range_with_many_sentences(self):
        rich = (
            "The classical argument posits that consciousness is irreducible. "
            "Chalmers identified this as the hard problem. "
            "Dennett, by contrast, argues for heterophenomenology. "
            "The debate touches on ontology and phenomenal experience alike. "
            "Neither position has been empirically settled."
        )
        result = evaluate_response(rich, ["Previous turn text."])
        assert 0.0 <= result <= 1.0


# ---------------------------------------------------------------------------
# 2.  Empty / trivial inputs
# ---------------------------------------------------------------------------


class TestEmptyInputs:
    def test_empty_string_returns_zero(self):
        assert evaluate_response("", []) == 0.0

    def test_whitespace_only_returns_zero(self):
        assert evaluate_response("   \n\t  ", []) == 0.0

    def test_single_word(self):
        result = evaluate_response("Yes.", [])
        assert 0.0 <= result <= 1.0

    def test_context_not_required(self):
        # context may be empty; function must not raise
        result = evaluate_response("The brain is physical.", [])
        assert isinstance(result, float)


# ---------------------------------------------------------------------------
# 3.  Lexical diversity
# ---------------------------------------------------------------------------


class TestLexicalDiversity:
    def test_repetitive_text_scores_lower_than_diverse(self):
        repetitive = "freedom freedom freedom freedom freedom freedom freedom freedom"
        diverse = (
            "Freedom implies autonomy, responsibility, and the absence of coercion."
        )
        score_rep = evaluate_response(repetitive, [])
        score_div = evaluate_response(diverse, [])
        assert score_div > score_rep

    def test_all_stop_words(self):
        # A sentence of only stop-words has zero content-word diversity.
        stop_only = "and the a is it in of to for by"
        result = evaluate_response(stop_only, [])
        # Should be a valid float but likely low
        assert 0.0 <= result <= 1.0


# ---------------------------------------------------------------------------
# 4.  Specificity
# ---------------------------------------------------------------------------


class TestSpecificity:
    def test_text_with_numbers_not_zero(self):
        text = "Aristotle identified 4 causes in 350 BCE that shaped Western metaphysics."
        result = evaluate_response(text, [])
        assert result > 0.0

    def test_text_with_named_concepts(self):
        text = "Kant argued that causality is a category imposed by the mind on experience."
        result = evaluate_response(text, [])
        assert result > 0.0


# ---------------------------------------------------------------------------
# 5.  Depth / length
# ---------------------------------------------------------------------------


class TestDepthScore:
    def test_very_short_text_low_depth(self):
        # Under _DEPTH_LOW words → partial depth credit only
        short = "Yes."
        long = " ".join(["word"] * 100)
        score_short = resp_eval._depth_score(len(resp_eval._tokenize(short)))
        score_long = resp_eval._depth_score(len(resp_eval._tokenize(long)))
        assert score_long > score_short

    def test_ideal_length_full_depth(self):
        # Between _DEPTH_LOW and _DEPTH_HIGH → full credit
        score = resp_eval._depth_score(150)
        assert score == 1.0

    def test_very_long_text_penalised(self):
        score_ideal = resp_eval._depth_score(200)
        score_long = resp_eval._depth_score(700)
        assert score_ideal > score_long


# ---------------------------------------------------------------------------
# 6.  Hedge penalty
# ---------------------------------------------------------------------------


class TestHedgePenalty:
    def test_hedge_phrases_detected(self):
        text_with_hedges = "Perhaps this is true. Maybe it could be argued otherwise."
        text_clean = "This claim is directly supported by empirical evidence."
        pen_hedge = resp_eval._hedge_penalty(text_with_hedges)
        pen_clean = resp_eval._hedge_penalty(text_clean)
        assert pen_hedge > pen_clean

    def test_hedge_penalty_capped_at_030(self):
        # Many hedge phrases should not exceed 0.30
        text = " ".join(["perhaps maybe kind of sort of"] * 10)
        assert resp_eval._hedge_penalty(text) <= 0.30

    def test_hedged_response_scores_lower(self):
        hedged = (
            "Perhaps it could be argued that, in a sense, maybe consciousness "
            "is somewhat related to brain activity, though one could argue otherwise."
        )
        direct = (
            "Consciousness is causally produced by neural activity. "
            "This conclusion follows from decades of neuroscience research."
        )
        assert evaluate_response(direct, []) > evaluate_response(hedged, [])


# ---------------------------------------------------------------------------
# 7.  Richer responses outscore sparse ones
# ---------------------------------------------------------------------------


class TestRichVsSparse:
    def test_rich_response_beats_sparse(self):
        sparse = "I think so."
        rich = (
            "The hard problem of consciousness, as formulated by Chalmers in 1995, "
            "distinguishes between the easy problems — explaining cognition, behaviour, "
            "and attention — and the hard problem of explaining why there is subjective "
            "experience at all. This distinction has driven 30 years of debate between "
            "physicalists such as Dennett and dualists such as Foster."
        )
        assert evaluate_response(rich, []) > evaluate_response(sparse, [])


# ===========================================================================
# Step 2 — Dialogue movement helpers
# ===========================================================================


class TestIsNewClaim:
    def test_no_context_always_new(self):
        # Without prior context there can be no similarity → new claim
        assert is_new_claim("Consciousness is irreducible.", []) is True

    def test_identical_text_not_new_claim(self):
        text = "free will is an illusion constructed by the narrative self"
        # Same text repeated → high similarity → NOT a new claim
        assert is_new_claim(text, [text]) is False

    def test_different_text_is_new_claim(self):
        last = "determinism implies that no one is morally responsible for their actions"
        response = "quantum indeterminacy opens the door to genuine freedom"
        assert is_new_claim(response, [last]) is True


class TestIsSemanticRepeat:
    def test_no_context_not_a_repeat(self):
        assert is_semantic_repeat("some response", []) is False

    def test_identical_to_recent_is_repeat(self):
        text = "the mind is identical to brain processes and nothing more"
        # Identical text → maximum overlap → repeat
        assert is_semantic_repeat(text, [text]) is True

    def test_unrelated_text_not_a_repeat(self):
        history = ["free will requires alternative possibilities"]
        response = "quantum mechanics is irrelevant to biological systems"
        assert is_semantic_repeat(response, history) is False


class TestCreatesPressure:
    def test_contradiction_keyword_triggers(self):
        assert creates_pressure("This is a contradiction in your argument.") is True

    def test_however_triggers(self):
        assert creates_pressure("However, that cannot be reconciled with evidence.") is True

    def test_fails_triggers(self):
        # "fails" is a known pressure keyword; substring match is intentional
        # for this measurement-only heuristic.
        assert creates_pressure("Your premise fails to account for counterexamples.") is True

    def test_neutral_text_no_pressure(self):
        assert creates_pressure("Consciousness is a fascinating topic.") is False

    def test_case_insensitive(self):
        assert creates_pressure("HOWEVER, the argument is inconsistent.") is True


class TestShowsResolution:
    def test_we_conclude_triggers(self):
        assert shows_resolution("We conclude that dualism cannot be sustained.") is True

    def test_we_must_reject_triggers(self):
        assert shows_resolution("We must reject the premise entirely.") is True

    def test_cannot_both_triggers(self):
        assert shows_resolution("We cannot both accept determinism and moral responsibility.") is True

    def test_i_was_wrong_triggers(self):
        assert shows_resolution("I was wrong about the nature of qualia.") is True

    def test_neutral_no_resolution(self):
        assert shows_resolution("This is an interesting position to consider.") is False

    def test_case_insensitive(self):
        assert shows_resolution("THEREFORE WE MUST abandon the old model.") is True


class TestEvaluateDialogueMovement:
    def test_returns_float(self):
        result = evaluate_dialogue_movement("The mind is distinct from the body.", [])
        assert isinstance(result, float)

    def test_within_range(self):
        result = evaluate_dialogue_movement("Some response.", [])
        assert 0.0 <= result <= 1.0

    def test_empty_returns_zero(self):
        assert evaluate_dialogue_movement("", []) == 0.0

    def test_whitespace_returns_zero(self):
        assert evaluate_dialogue_movement("   ", []) == 0.0

    def test_base_score_no_context(self):
        # No context → is_new_claim returns True (+0.15); no repeat penalty.
        # Score is at least base (0.40) + new_claim bonus (0.15) = 0.55,
        # possibly higher if pressure keywords happen to match.
        text = "Consciousness is irreducible."
        result = evaluate_dialogue_movement(text, [])
        assert result >= 0.55

    def test_pressure_increases_score(self):
        no_pressure = "The mind and brain are related."
        with_pressure = "However, this cannot be reconciled — it is a contradiction."
        ctx = ["some prior statement about mind and brain"]
        score_np = evaluate_dialogue_movement(no_pressure, ctx)
        score_p = evaluate_dialogue_movement(with_pressure, ctx)
        assert score_p > score_np

    def test_resolution_increases_score(self):
        no_res = "The debate continues."
        with_res = "We conclude that the materialist account fails."
        ctx = ["prior turn text"]
        assert evaluate_dialogue_movement(with_res, ctx) > evaluate_dialogue_movement(no_res, ctx)

    def test_semantic_repeat_decreases_score(self):
        # Identical text → semantic repeat penalty
        text = "the mind is identical to brain processes and nothing more"
        score_fresh = evaluate_dialogue_movement(text, [])
        score_repeat = evaluate_dialogue_movement(text, [text])
        assert score_fresh > score_repeat

    def test_score_clamped_to_one(self):
        # A response with pressure AND resolution AND new claim could theoretically
        # exceed 1.0 before clamping (0.4 + 0.15 + 0.15 + 0.25 = 0.95 ≤ 1.0 — stays safe).
        text = (
            "However, we conclude that the argument is a contradiction and "
            "we must reject it entirely."
        )
        result = evaluate_dialogue_movement(text, [])
        assert result <= 1.0

    def test_score_clamped_to_zero(self):
        # Force max penalties: repeat in small window + no bonuses
        text = "yes of course certainly"
        result = evaluate_dialogue_movement(text, [text])
        assert result >= 0.0


# ---------------------------------------------------------------------------
# 13.  evaluate_dialogue_movement_with_signals
# ---------------------------------------------------------------------------


class TestEvaluateDialogueMovementWithSignals:
    def test_returns_dict_with_expected_keys(self):
        result = evaluate_dialogue_movement_with_signals("The mind is distinct from the body.", [])
        assert set(result.keys()) == {"score", "new_claim", "pressure", "resolution", "semantic_repeat"}

    def test_score_matches_evaluate_dialogue_movement(self):
        text = "However, we cannot reconcile these views."
        ctx = ["prior turn about mind and body"]
        assert evaluate_dialogue_movement_with_signals(text, ctx)["score"] == pytest.approx(
            evaluate_dialogue_movement(text, ctx)
        )

    def test_score_within_range(self):
        result = evaluate_dialogue_movement_with_signals("Some response.", [])
        assert 0.0 <= result["score"] <= 1.0

    def test_empty_returns_zero_score_and_false_flags(self):
        result = evaluate_dialogue_movement_with_signals("", [])
        assert result["score"] == 0.0
        assert result["new_claim"] is False
        assert result["pressure"] is False
        assert result["resolution"] is False
        assert result["semantic_repeat"] is False

    def test_whitespace_returns_zero_score_and_false_flags(self):
        result = evaluate_dialogue_movement_with_signals("   ", [])
        assert result["score"] == 0.0
        assert result["new_claim"] is False

    def test_pressure_flag_set(self):
        result = evaluate_dialogue_movement_with_signals(
            "However, this cannot be reconciled — it is a contradiction.", []
        )
        assert result["pressure"] is True

    def test_resolution_flag_set(self):
        result = evaluate_dialogue_movement_with_signals(
            "We conclude that the materialist account fails.", []
        )
        assert result["resolution"] is True

    def test_semantic_repeat_flag_set(self):
        text = "the mind is identical to brain processes and nothing more"
        result = evaluate_dialogue_movement_with_signals(text, [text])
        assert result["semantic_repeat"] is True

    def test_new_claim_flag_set_no_context(self):
        result = evaluate_dialogue_movement_with_signals("Consciousness is irreducible.", [])
        assert result["new_claim"] is True

    def test_signal_types_are_bool_and_float(self):
        result = evaluate_dialogue_movement_with_signals("Some claim here.", [])
        assert isinstance(result["score"], float)
        assert isinstance(result["new_claim"], bool)
        assert isinstance(result["pressure"], bool)
        assert isinstance(result["resolution"], bool)
        assert isinstance(result["semantic_repeat"], bool)

    def test_score_consistent_with_flags(self):
        # Verify that the score reflects the component signals correctly.
        text = "However, we conclude that the argument fails entirely."
        ctx = ["some unrelated prior claim about knowledge"]
        result = evaluate_dialogue_movement_with_signals(text, ctx)
        # Recompute expected score manually
        expected = 0.40
        if result["new_claim"]:
            expected += 0.15
        if result["pressure"]:
            expected += 0.15
        if result["resolution"]:
            expected += 0.25
        if result["semantic_repeat"]:
            expected -= 0.20
        assert result["score"] == pytest.approx(max(0.0, min(1.0, expected)))

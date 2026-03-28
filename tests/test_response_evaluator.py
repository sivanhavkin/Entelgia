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

  Step 4 — compute_resolution_alignment / compute_semantic_repeat_alignment
  13. compute_resolution_alignment — all outcomes
  14. compute_semantic_repeat_alignment — all outcomes
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
    compute_pressure_alignment,
    compute_resolution_alignment,
    compute_semantic_repeat_alignment,
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

    # --- new structural / phrase-fragment checks ---

    def test_you_assume_triggers(self):
        assert creates_pressure("You assume that freedom and causation are compatible.") is True

    def test_why_assume_triggers(self):
        assert creates_pressure("Why assume that the two can coexist?") is True

    def test_what_if_triggers(self):
        assert creates_pressure("What if the entire framing is flawed?") is True

    def test_how_do_you_know_triggers(self):
        assert creates_pressure("How do you know the premise is sound?") is True

    def test_are_you_not_just_triggers(self):
        assert creates_pressure("Are you not just restating the same assumption?") is True

    def test_doesnt_that_triggers(self):
        assert creates_pressure("Doesn't that contradict what you said before?") is True

    def test_why_overlook_triggers(self):
        assert creates_pressure("Why overlook the structural dependency here?") is True

    def test_cannot_hold_triggers(self):
        assert creates_pressure("That framing cannot hold under scrutiny.") is True

    def test_pull_in_opposite_directions_triggers(self):
        assert creates_pressure("These two drives pull in opposite directions.") is True

    def test_already_stacked_triggers(self):
        assert creates_pressure("The argument is already stacked against coherence.") is True

    def test_rhetorical_question_negation_triggers(self):
        # Negation-contracted rhetorical question via regex pattern
        assert creates_pressure("Isn't that precisely the problem?") is True

    def test_hidden_premise_triggers(self):
        assert creates_pressure("There is a hidden premise you have not addressed.") is True

    def test_you_are_assuming_triggers(self):
        assert creates_pressure("You are assuming the very thing in question.") is True

    # --- Layer 4: rhetorical-question structural rule ---

    def test_assume_with_question_triggers(self):
        # "assume" + "?" — caught by Layer 4 even without "you assume" prefix
        assert creates_pressure("Does the view not assume a stable ground?") is True

    def test_bare_why_question_triggers(self):
        # "why" + "?" — epistemic challenge via Layer 4
        assert creates_pressure("Why does this paradox remain unresolved?") is True

    def test_does_this_not_triggers(self):
        # "does this not" + "?" — reframing prompt, Layer 4
        assert creates_pressure("Does this not undermine your entire framework?") is True

    def test_does_this_not_assumption_triggers(self):
        # "does this not" + "?" variant from problem statement
        assert creates_pressure("Does this not reveal an assumption in the framing?") is True

    def test_rhetorical_question_no_pressure_without_marker(self):
        # A question without any challenging marker should not trigger Layer 4
        assert creates_pressure("Is consciousness related to matter?") is False

    def test_marker_without_question_no_layer4_pressure(self):
        # "assume" without "?" does not trigger Layer 4 (no question present).
        # "we assume" also does not match _PRESSURE_PHRASES ("you assume" /
        # "why assume"), so no other layer fires either → overall False.
        assert creates_pressure("We assume the argument holds in all cases.") is False

    # --- word-family matching (Layer 4) ---

    def test_assumption_word_family_with_question_triggers(self):
        # "assumption" contains "assum" prefix; ? present → Layer 4 fires.
        assert creates_pressure("Does this not rest on a false assumption?") is True

    def test_assumptions_word_family_with_question_triggers(self):
        assert creates_pressure("What are the assumptions behind that claim?") is True

    def test_justification_word_family_with_question_triggers(self):
        # "justification" contains "justif" prefix; ? present → Layer 4 fires.
        assert creates_pressure("Is there any justification for that position?") is True

    def test_justify_word_family_with_question_triggers(self):
        assert creates_pressure("Can you justify that leap?") is True

    def test_definition_word_family_with_question_triggers(self):
        # "definition" contains "defin" prefix; ? present → Layer 4 fires.
        assert creates_pressure("What definition of freedom are you using?") is True

    def test_define_word_family_with_question_triggers(self):
        assert creates_pressure("How do you define consciousness here?") is True

    def test_agreement_word_family_with_question_triggers(self):
        # "agreement" contains "agre" prefix; ? present → Layer 4 fires.
        assert creates_pressure("Is there any agreement on what that term means?") is True

    def test_agree_word_family_with_question_triggers(self):
        assert creates_pressure("Why would you agree with an unstable premise?") is True

    def test_are_we_just_triggers(self):
        # "are we just" + "?" → Layer 4 fires.
        assert creates_pressure("Are we just restating the same problem?") is True

    # --- structural challenge phrases (Layer 2) ---

    def test_quietly_assumes_triggers(self):
        assert creates_pressure("The argument quietly assumes a fixed reference frame.") is True

    def test_risks_sneaking_in_triggers(self):
        assert creates_pressure(
            "That move risks sneaking in the very premise we are questioning."
        ) is True

    def test_just_swaps_one_anchor_triggers(self):
        assert creates_pressure(
            "This just swaps one anchor for another without resolving the tension."
        ) is True

    def test_what_happens_if_triggers(self):
        assert creates_pressure("What happens if the ground condition is removed?") is True

    # --- structural regex patterns (Layer 3) ---

    def test_treats_as_if_triggers(self):
        # "treats X as if" exposes a hidden assumption.
        assert creates_pressure("That view treats consciousness as if it were divisible.") is True

    def test_treat_as_if_triggers(self):
        assert creates_pressure("You treat the concept as if it had a fixed referent.") is True

    def test_if_does_that_mean_triggers(self):
        # Conditional challenge: "if … does that mean"
        assert creates_pressure("If determinism is true, does that mean agency is illusory?") is True

    def test_if_what_happens_triggers(self):
        # Conditional challenge: "if … what happens"
        assert creates_pressure("If we remove the axiom, what happens to the proof?") is True

    def test_if_then_conditional_triggers(self):
        # Conditional challenge: "if …, then"
        assert creates_pressure("If the premise fails, then the whole structure collapses.") is True

    def test_plain_question_no_challenge_no_pressure(self):
        # A purely neutral question with no challenge markers must not trigger.
        assert creates_pressure("Is consciousness a product of the brain?") is False

    # --- assertion-based challenge phrases (Layer 5) ---

    def test_misses_that_triggers(self):
        # "misses that" — declarative challenge to the other claim, no "?" needed.
        assert creates_pressure("That argument misses that agency requires more than causation.") is True

    def test_ignores_that_triggers(self):
        # "ignores that" — exposes an unconsidered factor.
        assert creates_pressure("The position ignores that experience is not reducible to function.") is True

    def test_assumes_that_triggers(self):
        # "assumes that" — exposes a hidden premise without a question mark.
        assert creates_pressure("The view assumes that consciousness is substrate-independent.") is True

    def test_you_seem_to_triggers(self):
        # "you seem to" — implicit challenge to framing or stance.
        assert creates_pressure("You seem to conflate correlation with causation here.") is True

    def test_theres_no_guarantee_triggers(self):
        # "there's no guarantee" — challenges the reliability of the claim.
        assert creates_pressure("There's no guarantee that the framework survives this counterexample.") is True

    def test_there_is_no_guarantee_triggers(self):
        # "there is no guarantee" — uncontracted variant.
        assert creates_pressure("There is no guarantee that coherence is preserved under revision.") is True

    def test_fails_to_consider_triggers(self):
        # "fails to consider" — explicit declarative critique of omission.
        assert creates_pressure("This account fails to consider the role of embodiment.") is True

    def test_overlooks_triggers(self):
        # "overlooks" — exposes an unconsidered dimension.
        assert creates_pressure("The argument overlooks the distinction between types and tokens.") is True

    def test_assertion_no_question_mark_still_triggers(self):
        # Core requirement: assertion phrases must fire without any "?" present.
        sentence = "That account misses that identity requires continuity over time."
        assert "?" not in sentence
        assert creates_pressure(sentence) is True

    def test_assertion_case_insensitive(self):
        # Assertion-phrase matching must be case-insensitive.
        assert creates_pressure("THAT FRAMING IGNORES THAT CONTEXT SHAPES MEANING.") is True


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

    # --- new structural / phrase-fragment checks ---

    def test_one_must_yield_triggers(self):
        assert shows_resolution("One must yield when the evidence is this clear.") is True

    def test_one_excludes_the_other_triggers(self):
        assert shows_resolution("Freedom and strict determinism: one excludes the other.") is True

    def test_one_force_always_has_to_yield_triggers(self):
        assert shows_resolution("One force always has to yield in this system.") is True

    def test_cannot_operate_simultaneously_triggers(self):
        assert shows_resolution("The two principles cannot operate simultaneously.") is True

    def test_you_cannot_have_both_triggers(self):
        assert shows_resolution("You cannot have both radical freedom and causal closure.") is True

    def test_the_loop_closes_triggers(self):
        assert shows_resolution("At this point the loop closes and no new options remain.") is True

    def test_the_drive_fades_triggers(self):
        assert shows_resolution("Without resolution the drive fades and the argument stalls.") is True

    def test_one_side_has_to_give_triggers(self):
        assert shows_resolution("One side has to give; the two positions are irreconcilable.") is True

    def test_this_narrows_the_issue_to_triggers(self):
        assert shows_resolution("This narrows the issue to a single unavoidable question.") is True

    def test_cannot_coexist_triggers(self):
        assert shows_resolution("These two values cannot coexist within the same framework.") is True

    def test_must_give_way_triggers(self):
        assert shows_resolution("Something must give way if progress is to be made.") is True

    def test_forced_to_choose_triggers(self):
        assert shows_resolution("We are forced to choose between coherence and completeness.") is True

    def test_either_or_exclusion_regex_triggers(self):
        assert shows_resolution("Either the claim holds, or the whole argument collapses.") is True

    def test_one_side_collapse_regex_triggers(self):
        assert shows_resolution("One side must yield when the evidence accumulates.") is True


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


# ---------------------------------------------------------------------------
# 14.  compute_pressure_alignment
# ---------------------------------------------------------------------------


class TestComputePressureAlignment:
    # --- high band (>= 4.5) ---

    def test_aligned_when_meta_high_and_dialogue_true(self):
        assert compute_pressure_alignment(6.0, True) == "aligned"

    def test_aligned_at_high_threshold_with_dialogue_true(self):
        assert compute_pressure_alignment(4.5, True) == "aligned"

    def test_internal_not_expressed_when_meta_high_and_dialogue_false(self):
        assert compute_pressure_alignment(7.5, False) == "internal_not_expressed"

    def test_internal_not_expressed_at_high_threshold_dialogue_false(self):
        assert compute_pressure_alignment(4.5, False) == "internal_not_expressed"

    # --- low band (<= 2.5) ---

    def test_text_more_pressured_when_meta_low_and_dialogue_true(self):
        assert compute_pressure_alignment(1.0, True) == "text_more_pressured_than_state"

    def test_text_more_pressured_at_low_threshold_dialogue_true(self):
        assert compute_pressure_alignment(2.5, True) == "text_more_pressured_than_state"

    def test_neutral_when_meta_low_and_dialogue_false(self):
        assert compute_pressure_alignment(1.0, False) == "neutral"

    def test_neutral_at_zero_pressure(self):
        assert compute_pressure_alignment(0.0, False) == "neutral"

    def test_neutral_at_low_threshold_dialogue_false(self):
        assert compute_pressure_alignment(2.5, False) == "neutral"

    # --- uncertain band (2.5 < meta_pressure < 4.5) ---

    def test_weak_alignment_in_uncertain_band_dialogue_true(self):
        assert compute_pressure_alignment(3.5, True) == "weak_alignment"

    def test_weak_alignment_in_uncertain_band_dialogue_false(self):
        assert compute_pressure_alignment(3.5, False) == "weak_alignment"

    def test_weak_alignment_just_above_low_threshold(self):
        assert compute_pressure_alignment(2.51, True) == "weak_alignment"

    def test_weak_alignment_just_below_high_threshold(self):
        assert compute_pressure_alignment(4.49, False) == "weak_alignment"

    # --- general ---

    def test_returns_string(self):
        result = compute_pressure_alignment(3.0, False)
        assert isinstance(result, str)

    def test_all_five_outcomes_are_distinct(self):
        outcomes = {
            compute_pressure_alignment(8.0, True),    # aligned
            compute_pressure_alignment(8.0, False),   # internal_not_expressed
            compute_pressure_alignment(1.0, True),    # text_more_pressured_than_state
            compute_pressure_alignment(3.5, True),    # weak_alignment
            compute_pressure_alignment(1.0, False),   # neutral
        }
        assert len(outcomes) == 5


# ---------------------------------------------------------------------------
# 13. compute_resolution_alignment
# ---------------------------------------------------------------------------


class TestComputeResolutionAlignment:
    # --- state expects resolution, no stagnation ---

    def test_aligned_when_state_expects_and_text_resolves(self):
        # high unresolved + high conflict + low stagnation + text resolves → aligned
        assert compute_resolution_alignment(True, 2, 5.0, 0.2) == "aligned"

    def test_resolution_not_expressed_when_state_expects_but_text_does_not(self):
        # high unresolved + high conflict + low stagnation + no text resolution → under-detection
        assert compute_resolution_alignment(False, 3, 6.0, 0.1) == "resolution_not_expressed"

    # --- state does NOT expect resolution ---

    def test_text_resolved_no_state_pressure_when_no_state_but_text_resolves(self):
        # low unresolved + high conflict → state does not expect resolution
        assert compute_resolution_alignment(True, 1, 5.0, 0.2) == "text_resolved_no_state_pressure"

    def test_text_resolved_no_state_pressure_when_low_conflict(self):
        # high unresolved but low conflict → state does not expect resolution
        assert compute_resolution_alignment(True, 3, 2.0, 0.2) == "text_resolved_no_state_pressure"

    def test_neutral_when_neither_state_nor_text(self):
        # low everything → neutral
        assert compute_resolution_alignment(False, 0, 1.0, 0.0) == "neutral"

    # --- uncertain band (high stagnation alongside high state expectation) ---

    def test_weak_alignment_when_state_expects_but_stagnation_high(self):
        # high unresolved + high conflict + high stagnation → ambiguous
        assert compute_resolution_alignment(True, 2, 5.0, 0.6) == "weak_alignment"

    def test_weak_alignment_at_stagnation_boundary(self):
        assert compute_resolution_alignment(False, 2, 4.0, 0.5) == "weak_alignment"

    # --- boundary values ---

    def test_aligned_at_exact_thresholds(self):
        # exactly at unresolved=2, conflict=4.0, stagnation just below 0.5
        assert compute_resolution_alignment(True, 2, 4.0, 0.49) == "aligned"

    def test_neutral_just_below_unresolved_threshold(self):
        assert compute_resolution_alignment(False, 1, 5.0, 0.0) == "neutral"

    def test_neutral_just_below_conflict_threshold(self):
        assert compute_resolution_alignment(False, 3, 3.99, 0.0) == "neutral"

    # --- general ---

    def test_returns_string(self):
        assert isinstance(compute_resolution_alignment(False, 0, 0.0, 0.0), str)

    def test_all_five_outcomes_are_distinct(self):
        outcomes = {
            compute_resolution_alignment(True, 2, 5.0, 0.2),   # aligned
            compute_resolution_alignment(False, 2, 5.0, 0.2),  # resolution_not_expressed
            compute_resolution_alignment(True, 1, 5.0, 0.2),   # text_resolved_no_state_pressure
            compute_resolution_alignment(True, 2, 5.0, 0.6),   # weak_alignment
            compute_resolution_alignment(False, 0, 1.0, 0.0),  # neutral
        }
        assert len(outcomes) == 5


# ---------------------------------------------------------------------------
# 14. compute_semantic_repeat_alignment
# ---------------------------------------------------------------------------


class TestComputeSemanticRepeatAlignment:
    # --- state expects repeat (high stagnation, low conflict/unresolved) ---

    def test_aligned_when_stagnation_high_and_text_repeat(self):
        # high stagnation + low conflict + low unresolved + text is repeat → aligned
        assert compute_semantic_repeat_alignment(True, 0.7, 2.0, 1) == "aligned"

    def test_repeat_not_detected_when_stagnation_high_but_text_not_repeat(self):
        # high stagnation but text not flagged → under-detection
        assert compute_semantic_repeat_alignment(False, 0.8, 2.0, 1) == "repeat_not_detected"

    # --- state does NOT expect repeat ---

    def test_text_repeat_no_stagnation_when_low_stagnation_and_text_repeat(self):
        # low stagnation + text flagged as repeat → over-detection or local word-overlap
        assert compute_semantic_repeat_alignment(True, 0.2, 2.0, 1) == "text_repeat_no_stagnation"

    def test_neutral_when_neither_stagnation_nor_text_repeat(self):
        assert compute_semantic_repeat_alignment(False, 0.0, 1.0, 0) == "neutral"

    # --- uncertain band (high stagnation + high conflict + high unresolved) ---

    def test_weak_alignment_when_stagnation_and_conflict_and_unresolved_all_high(self):
        # could be circular disagreement rather than simple repetition
        assert compute_semantic_repeat_alignment(True, 0.7, 5.0, 3) == "weak_alignment"

    def test_weak_alignment_at_conflict_boundary(self):
        assert compute_semantic_repeat_alignment(False, 0.5, 4.0, 2) == "weak_alignment"

    # --- boundary values ---

    def test_aligned_at_stagnation_boundary(self):
        # exactly at stagnation=0.5, conflict below threshold
        assert compute_semantic_repeat_alignment(True, 0.5, 3.0, 1) == "aligned"

    def test_neutral_just_below_stagnation_threshold(self):
        assert compute_semantic_repeat_alignment(False, 0.49, 2.0, 1) == "neutral"

    def test_aligned_when_stagnation_high_conflict_high_but_unresolved_low(self):
        # high conflict but unresolved=1 → uncertain condition NOT met → aligned
        assert compute_semantic_repeat_alignment(True, 0.7, 5.0, 1) == "aligned"

    def test_aligned_when_stagnation_high_unresolved_high_but_conflict_low(self):
        # high unresolved but conflict < 4.0 → uncertain condition NOT met → aligned
        assert compute_semantic_repeat_alignment(True, 0.7, 3.0, 3) == "aligned"

    # --- general ---

    def test_returns_string(self):
        assert isinstance(compute_semantic_repeat_alignment(False, 0.0, 0.0, 0), str)

    def test_all_five_outcomes_are_distinct(self):
        outcomes = {
            compute_semantic_repeat_alignment(True, 0.7, 2.0, 1),   # aligned
            compute_semantic_repeat_alignment(False, 0.8, 2.0, 1),  # repeat_not_detected
            compute_semantic_repeat_alignment(True, 0.2, 2.0, 1),   # text_repeat_no_stagnation
            compute_semantic_repeat_alignment(True, 0.7, 5.0, 3),   # weak_alignment
            compute_semantic_repeat_alignment(False, 0.0, 1.0, 0),  # neutral
        }
        assert len(outcomes) == 5

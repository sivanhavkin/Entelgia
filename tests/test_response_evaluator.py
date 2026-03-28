#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Tests for entelgia/response_evaluator.py.

Covers:
  1. evaluate_response — return type and range
  2. Empty / trivial inputs
  3. Lexical diversity contribution
  4. Specificity contribution (numbers, named entities)
  5. Depth / length contribution
  6. Hedge penalty
  7. Short vs. rich responses produce different scores
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

import entelgia.response_evaluator as resp_eval
from entelgia.response_evaluator import evaluate_response


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

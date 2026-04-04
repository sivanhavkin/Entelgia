#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Tests for dynamic continuation context helpers.

Coverage:
  1. extract_continuation_context — empty turns returns empty non-topic fields
  2. extract_continuation_context — seed-role entries are skipped
  3. extract_continuation_context — extracts last_claim from a declarative sentence > 20 chars
  4. extract_continuation_context — extracts unresolved_question from a sentence ending with ?
  5. extract_continuation_context — extracts tension_point via adversative marker
  6. extract_continuation_context — dominant_topic is taken from the topic argument
  7. build_continuation_prompt — returns "" for empty context
  8. build_continuation_prompt — returns "" when only empty strings are in context
  9. build_continuation_prompt — includes continuation instruction + topic line for topic-only context
 10. build_continuation_prompt — includes all four fields when all are populated
 11. SeedGenerator.generate_seed — uses continuation prompt (not TOPIC: header) when real turns exist
 12. SeedGenerator.generate_seed — first session (seed-only / no real turns) uses TOPIC: header, not continuation instruction
 13. SeedGenerator.generate_seed — first session with no memory preserves topic in seed
 14. SeedGenerator.generate_seed — strategy instruction keywords still present after continuation prefix
"""

import random

import pytest

from entelgia.dialogue_engine import (
    SeedGenerator,
    build_continuation_prompt,
    extract_continuation_context,
    _CONTINUATION_INSTRUCTION,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _speaker():
    class _MockSpeaker:
        def conflict_index(self):
            return 5.0

    return _MockSpeaker()


def _turn(text, role="Socrates", emotion="neutral"):
    return {"role": role, "text": text, "emotion": emotion}


def _seed_turn(text="philosophy of mind"):
    return {"role": "seed", "text": text}


# ---------------------------------------------------------------------------
# 1. Empty turns → non-topic fields are empty strings
# ---------------------------------------------------------------------------


def test_extract_empty_turns_returns_empty_signal_fields():
    ctx = extract_continuation_context([], topic="freedom")
    assert ctx["dominant_topic"] == "freedom"
    assert ctx["last_claim"] == ""
    assert ctx["unresolved_question"] == ""
    assert ctx["tension_point"] == ""


# ---------------------------------------------------------------------------
# 2. Seed-role entries are skipped
# ---------------------------------------------------------------------------


def test_extract_skips_seed_role_entries():
    """Seed entries must not be treated as real speaker turns."""
    turns = [_seed_turn("philosophy of mind")]
    ctx = extract_continuation_context(turns, topic="freedom")
    assert ctx["last_claim"] == ""
    assert ctx["unresolved_question"] == ""
    assert ctx["tension_point"] == ""


# ---------------------------------------------------------------------------
# 3. Extracts last_claim from declarative sentence > 20 chars
# ---------------------------------------------------------------------------


def test_extract_last_claim_from_declarative_sentence():
    long_claim = "Freedom requires the absence of external coercion."
    turns = [_turn(long_claim)]
    ctx = extract_continuation_context(turns, topic="freedom")
    assert ctx["last_claim"] == long_claim


def test_extract_ignores_short_sentences_for_last_claim():
    turns = [_turn("Short.")]
    ctx = extract_continuation_context(turns, topic="freedom")
    assert ctx["last_claim"] == ""


# ---------------------------------------------------------------------------
# 4. Extracts unresolved_question from a sentence ending with ?
# ---------------------------------------------------------------------------


def test_extract_unresolved_question_from_question_sentence():
    question = "Can determinism be reconciled with moral responsibility?"
    turns = [_turn(question)]
    ctx = extract_continuation_context(turns, topic="freedom")
    assert ctx["unresolved_question"] == question


def test_extract_ignores_non_question_sentences_for_unresolved_question():
    turns = [_turn("This is not a question at all.")]
    ctx = extract_continuation_context(turns, topic="freedom")
    assert ctx["unresolved_question"] == ""


# ---------------------------------------------------------------------------
# 5. Extracts tension_point via adversative marker
# ---------------------------------------------------------------------------


def test_extract_tension_point_via_but():
    sentence = "Freedom is important, but it can conflict with social order."
    turns = [_turn(sentence)]
    ctx = extract_continuation_context(turns, topic="freedom")
    assert ctx["tension_point"] == sentence


def test_extract_tension_point_via_however():
    sentence = "Autonomy is valued, however, its limits remain contested."
    turns = [_turn(sentence)]
    ctx = extract_continuation_context(turns, topic="freedom")
    assert ctx["tension_point"] == sentence


def test_extract_tension_point_not_set_without_adversative():
    turns = [_turn("Autonomy is valued and widely discussed in ethics.")]
    ctx = extract_continuation_context(turns, topic="freedom")
    assert ctx["tension_point"] == ""


# ---------------------------------------------------------------------------
# 6. dominant_topic is taken from the topic argument
# ---------------------------------------------------------------------------


def test_extract_dominant_topic_from_argument():
    ctx = extract_continuation_context([], topic="epistemic injustice")
    assert ctx["dominant_topic"] == "epistemic injustice"


def test_extract_dominant_topic_empty_when_no_topic():
    ctx = extract_continuation_context([])
    assert ctx["dominant_topic"] == ""


# ---------------------------------------------------------------------------
# 7. build_continuation_prompt — empty context returns ""
# ---------------------------------------------------------------------------


def test_build_empty_context_returns_empty_string():
    ctx = {
        "dominant_topic": "",
        "last_claim": "",
        "unresolved_question": "",
        "tension_point": "",
    }
    assert build_continuation_prompt(ctx) == ""


# ---------------------------------------------------------------------------
# 8. build_continuation_prompt — all-empty values return ""
# ---------------------------------------------------------------------------


def test_build_all_empty_values_returns_empty_string():
    assert build_continuation_prompt({}) == ""


# ---------------------------------------------------------------------------
# 9. build_continuation_prompt — topic-only context includes instruction + topic line
# ---------------------------------------------------------------------------


def test_build_topic_only_context():
    ctx = {
        "dominant_topic": "free will",
        "last_claim": "",
        "unresolved_question": "",
        "tension_point": "",
    }
    result = build_continuation_prompt(ctx)
    assert _CONTINUATION_INSTRUCTION in result
    assert "The previous discussion focused on: free will." in result
    assert "The last claim made was" not in result
    assert "An unresolved question remains" not in result
    assert "The tension point was" not in result


# ---------------------------------------------------------------------------
# 10. build_continuation_prompt — full context includes all four fields
# ---------------------------------------------------------------------------


def test_build_full_context_includes_all_fields():
    ctx = {
        "dominant_topic": "free will",
        "last_claim": "Determinism entails that all events are causally necessitated.",
        "unresolved_question": "Can moral responsibility survive determinism?",
        "tension_point": "Free will seems intuitive, but determinism appears scientifically sound.",
    }
    result = build_continuation_prompt(ctx)
    assert _CONTINUATION_INSTRUCTION in result
    assert "The previous discussion focused on: free will." in result
    assert "The last claim made was: Determinism" in result
    assert "An unresolved question remains: Can moral" in result
    assert "The tension point was: Free will" in result


# ---------------------------------------------------------------------------
# 11. SeedGenerator — continuation prompt used when real turns exist
# ---------------------------------------------------------------------------


def test_seed_generator_uses_continuation_when_real_turns_exist():
    sg = SeedGenerator()
    turns = [
        _turn(
            "Freedom requires the absence of external coercion, "
            "but society imposes necessary constraints."
        )
    ]
    seed = sg.generate_seed("freedom", turns, _speaker(), turn_count=3)
    assert _CONTINUATION_INSTRUCTION in seed
    assert "The previous discussion focused on: freedom." in seed
    # TOPIC: header must NOT be present — it was replaced
    assert "TOPIC:" not in seed


# ---------------------------------------------------------------------------
# 12. SeedGenerator — first session (seed-only / no real turns) uses TOPIC: header
# ---------------------------------------------------------------------------


def test_seed_generator_first_session_no_real_turns_uses_topic_header():
    """When only a seed-role entry is in recent_turns, fall back to TOPIC: header."""
    sg = SeedGenerator()
    turns = [_seed_turn("philosophy of mind")]
    seed = sg.generate_seed("free will", turns, _speaker(), turn_count=1)
    # Must NOT inject the continuation instruction on the first session
    assert _CONTINUATION_INSTRUCTION not in seed
    # The topic must still anchor the seed
    assert "free will" in seed


# ---------------------------------------------------------------------------
# 13. SeedGenerator — empty dialog (no turns at all) uses TOPIC: header
# ---------------------------------------------------------------------------


def test_seed_generator_empty_dialog_uses_topic_header():
    sg = SeedGenerator()
    seed = sg.generate_seed("consciousness", [], _speaker(), turn_count=0)
    assert _CONTINUATION_INSTRUCTION not in seed
    assert "consciousness" in seed


# ---------------------------------------------------------------------------
# 14. Strategy instruction keywords still present after continuation prefix
# ---------------------------------------------------------------------------

_STRATEGY_KEYWORDS = {
    "BUILD",
    "QUESTION",
    "INTEGRATE",
    "DISAGREE",
    "EXPLORE",
    "CONNECT",
    "REFLECT",
}


def test_seed_generator_strategy_keyword_present_with_continuation():
    """Strategy instruction keywords must survive the continuation prefix injection."""
    sg = SeedGenerator()
    turns = [
        _turn(
            "Consciousness may be an emergent property of complex information processing, "
            "but this view struggles to explain subjective experience."
        )
    ]
    found_keywords = set()
    saved_state = random.getstate()
    try:
        random.seed(0)
        for turn_count in range(1, 50):
            seed = sg.generate_seed("consciousness", turns, _speaker(), turn_count=turn_count)
            for kw in _STRATEGY_KEYWORDS:
                if kw in seed:
                    found_keywords.add(kw)
            if found_keywords == _STRATEGY_KEYWORDS:
                break
    finally:
        random.setstate(saved_state)

    assert found_keywords, "No strategy keywords found in seeds after continuation injection"
    # At least two distinct keywords must appear across 50 iterations
    assert len(found_keywords) >= 2, (
        f"Expected multiple strategy keywords, found: {found_keywords}"
    )

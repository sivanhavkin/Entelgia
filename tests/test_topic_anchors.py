#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Tests for the Topic Anchors and Forbidden Carryover mechanism.

Validates:
  A. TOPIC_ANCHORS covers all topics in TOPIC_CLUSTERS.
  B. _contains_any() correctly detects anchor concepts in text (case-insensitive).
  C. _contains_any() returns False when no anchors present.
  D. _build_compact_prompt injects CURRENT TOPIC + required concepts.
  E. _build_compact_prompt injects forbidden carryover on topic change.
  F. No forbidden carryover injected when topic is unchanged.
  G. No forbidden carryover injected on first turn (_last_topic is empty).
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from unittest.mock import MagicMock, patch

import Entelgia_production_meta as _meta
from Entelgia_production_meta import (
    TOPIC_ANCHORS,
    TOPIC_CLUSTERS,
    Agent,
    BehaviorCore,
    Config,
    ConsciousCore,
    EmotionCore,
    LanguageCore,
    _contains_any,
)


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------


def _make_agent(name: str = "Socrates", last_topic: str = "") -> Agent:
    """Return a minimal Agent whose LLM and memory calls are fully mocked."""
    cfg = Config()

    llm_mock = MagicMock()
    llm_mock.generate.return_value = "I reflect on this philosophical question."

    memory_mock = MagicMock()
    memory_mock.get_agent_state.return_value = {
        "id_strength": 5.0,
        "ego_strength": 5.0,
        "superego_strength": 5.0,
        "self_awareness": 0.55,
    }
    memory_mock.ltm_recent.return_value = []
    memory_mock.stm_load.return_value = []

    emotion_mock = MagicMock(spec=EmotionCore)
    emotion_mock.infer.return_value = ("neutral", 0.3)

    behavior_mock = MagicMock(spec=BehaviorCore)
    language_mock = LanguageCore()
    conscious_mock = ConsciousCore()

    agent = Agent(
        name=name,
        model="phi3",
        color="",
        llm=llm_mock,
        memory=memory_mock,
        emotion=emotion_mock,
        behavior=behavior_mock,
        language=language_mock,
        conscious=conscious_mock,
        persona="A philosopher who seeks truth.",
        use_enhanced=False,
        cfg=cfg,
    )
    agent._last_topic = last_topic
    agent.topic_style = ""
    return agent


# ---------------------------------------------------------------------------
# TOPIC_ANCHORS structure tests
# ---------------------------------------------------------------------------


class TestTopicAnchors:
    """TOPIC_ANCHORS structure and coverage validation."""

    def test_topic_anchors_is_dict(self):
        assert isinstance(TOPIC_ANCHORS, dict)

    def test_topic_anchors_is_non_empty(self):
        assert len(TOPIC_ANCHORS) > 0

    def test_every_topic_cluster_topic_has_anchors(self):
        """Every topic in TOPIC_CLUSTERS must appear in TOPIC_ANCHORS."""
        all_cluster_topics = {
            topic
            for topics in TOPIC_CLUSTERS.values()
            for topic in topics
        }
        missing = all_cluster_topics - set(TOPIC_ANCHORS.keys())
        assert not missing, f"Missing TOPIC_ANCHORS entries for: {missing}"

    def test_each_anchor_list_is_non_empty(self):
        """Every topic must have at least one anchor keyword."""
        for topic, anchors in TOPIC_ANCHORS.items():
            assert len(anchors) >= 1, f"Empty anchors for topic {topic!r}"

    def test_anchor_keywords_are_strings(self):
        """All anchor keywords must be non-empty strings."""
        for topic, anchors in TOPIC_ANCHORS.items():
            for kw in anchors:
                assert isinstance(kw, str) and kw.strip(), (
                    f"Invalid anchor keyword {kw!r} in topic {topic!r}"
                )

    def test_ai_alignment_anchors_match_spec(self):
        """AI alignment anchors must include the exact terms from the problem spec."""
        required = {
            "objective misspecification",
            "reward hacking",
            "corrigibility",
            "outer alignment",
            "inner alignment",
            "value learning",
            "specification gaming",
            "human intent",
        }
        actual = set(TOPIC_ANCHORS.get("AI alignment", []))
        assert required.issubset(actual), (
            f"AI alignment anchors missing required terms: {required - actual}"
        )


# ---------------------------------------------------------------------------
# _contains_any helper tests
# ---------------------------------------------------------------------------


class TestContainsAny:
    """_contains_any() function validation."""

    def test_returns_true_on_exact_match(self):
        assert _contains_any("corrigibility is important", ["corrigibility"])

    def test_returns_true_case_insensitive(self):
        assert _contains_any("CORRIGIBILITY matters", ["corrigibility"])
        assert _contains_any("Reward Hacking is bad", ["reward hacking"])

    def test_returns_true_on_substring_match(self):
        assert _contains_any(
            "The concept of inner alignment is tricky", ["inner alignment"]
        )

    def test_returns_false_when_no_match(self):
        assert not _contains_any(
            "Redundancy and real-time monitoring prevent failures",
            ["corrigibility", "reward hacking", "outer alignment"],
        )

    def test_returns_false_on_empty_concepts(self):
        assert not _contains_any("any text at all", [])

    def test_returns_false_on_empty_text(self):
        assert not _contains_any("", ["corrigibility"])

    def test_multi_concept_first_match(self):
        """Returns True if any matching concept is found."""
        assert _contains_any(
            "value learning is central",
            ["objective misspecification", "reward hacking", "value learning"],
        )

    def test_partial_word_no_false_positive_for_substrings(self):
        """'corrigibility' (13 chars) must NOT be found inside 'corrigible' (10 chars).

        Note: 'corrigible' is a PREFIX of 'corrigibility', but the search text
        'corrigible agents' is shorter than 'corrigibility', so there is no match.
        """
        assert _contains_any("corrigible agents", ["corrigibility"]) is False


# ---------------------------------------------------------------------------
# Prompt injection tests (via _build_compact_prompt)
# ---------------------------------------------------------------------------


class TestBuildCompactPromptTopicAnchors:
    """_build_compact_prompt injects topic anchor requirements."""

    def test_anchor_requirement_injected_for_known_topic(self):
        cfg = Config()
        agent = _make_agent()
        seed = "TOPIC: AI alignment\nDiscuss the implications."
        with patch.object(_meta, "CFG", cfg):
            prompt = agent._build_compact_prompt(seed, [])

        assert "CURRENT TOPIC: AI alignment" in prompt
        assert "must explicitly engage with at least one" in prompt
        assert "corrigibility" in prompt
        assert "reward hacking" in prompt

    def test_no_anchor_requirement_for_unknown_topic(self):
        cfg = Config()
        agent = _make_agent()
        seed = "TOPIC: Some unknown topic\nDiscuss."
        with patch.object(_meta, "CFG", cfg):
            prompt = agent._build_compact_prompt(seed, [])

        assert "CURRENT TOPIC:" not in prompt
        assert "must explicitly engage" not in prompt

    def test_no_anchor_requirement_when_no_topic_in_seed(self):
        cfg = Config()
        agent = _make_agent()
        seed = "What is consciousness?"
        with patch.object(_meta, "CFG", cfg):
            prompt = agent._build_compact_prompt(seed, [])

        assert "CURRENT TOPIC:" not in prompt
        assert "must explicitly engage" not in prompt

    def test_forbidden_carryover_injected_on_topic_change(self):
        cfg = Config()
        agent = _make_agent(last_topic="Autonomous systems")
        seed = "TOPIC: AI alignment\nDiscuss."
        with patch.object(_meta, "CFG", cfg):
            prompt = agent._build_compact_prompt(seed, [])

        assert "Do NOT reuse concepts from previous discussions" in prompt
        # Autonomous systems anchors should appear as forbidden
        for concept in TOPIC_ANCHORS["Autonomous systems"]:
            assert concept in prompt, f"Expected forbidden concept {concept!r} in prompt"

    def test_no_forbidden_carryover_when_topic_unchanged(self):
        cfg = Config()
        agent = _make_agent(last_topic="AI alignment")
        seed = "TOPIC: AI alignment\nDiscuss."
        with patch.object(_meta, "CFG", cfg):
            prompt = agent._build_compact_prompt(seed, [])

        assert "Do NOT reuse concepts from previous discussions" not in prompt

    def test_no_forbidden_carryover_on_first_turn(self):
        cfg = Config()
        agent = _make_agent(last_topic="")
        seed = "TOPIC: AI alignment\nDiscuss."
        with patch.object(_meta, "CFG", cfg):
            prompt = agent._build_compact_prompt(seed, [])

        assert "Do NOT reuse concepts from previous discussions" not in prompt


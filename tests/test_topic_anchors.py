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
import logging

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

    def test_risk_and_decision_making_anchors_include_broad_terms(self):
        """Risk and decision making anchors must include broader vocabulary
        to prevent false-positive TOPIC-MISMATCH on valid responses that
        use common risk/decision language instead of narrow technical terms."""
        required = {
            "risk",
            "tradeoff",
            "trade-off",
            "safety",
            "reliability",
        }
        actual = set(TOPIC_ANCHORS.get("Risk and decision making", []))
        assert required.issubset(actual), (
            f"Risk and decision making anchors missing broad terms: {required - actual}"
        )

    def test_risk_and_decision_making_anchors_match_autonomous_vehicle_response(self):
        """A response about autonomous vehicle design risk tradeoffs must match
        the Risk and decision making anchors (regression for TOPIC-MISMATCH false positive)."""
        av_response = (
            "In analyzing the design of autonomous vehicles, I observe a tradeoff between "
            "robust architectural redundancy and real-time monitoring capabilities. While "
            "redundancy ensures reliability through multiple systems, it may not fully address "
            "immediate sensor malfunctions. Integrating a code of ethics into system policies "
            "could mitigate these issues but introduces complexity in incentive structures for "
            "manufacturers and users. Balancing these factors requires careful policy-making to "
            "allocate resources effectively, ensuring both safety and ethical compliance without "
            "excessive cost or market disruption."
        )
        anchors = TOPIC_ANCHORS.get("Risk and decision making", [])
        assert _contains_any(av_response, anchors), (
            "Autonomous vehicle risk-tradeoff response should match Risk and decision making anchors"
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


# ---------------------------------------------------------------------------
# Topic-mismatch persist warning tests (Agent.speak)
# ---------------------------------------------------------------------------


class TestTopicMismatchPersistWarning:
    """Agent.speak emits [TOPIC-MISMATCH-PERSIST] when regenerated response
    also fails the anchor check."""

    # A prior turn for Socrates is required so the validation is not skipped
    # (it is intentionally skipped on the first turn — see TestTopicMismatchFirstTurn).
    _PRIOR_TURN = [{"role": "Socrates", "text": "I have thought about this before."}]

    def test_persist_warning_logged_when_regen_also_fails(self, caplog):
        """If both the initial and regenerated responses miss the anchors,
        a [TOPIC-MISMATCH-PERSIST] warning must be emitted."""
        agent = _make_agent()
        # Both calls return a response with no anchor for 'AI alignment'
        agent.llm.generate.return_value = (
            "Redundancy and real-time monitoring prevent failures."
        )
        seed = "TOPIC: AI alignment\nDiscuss."
        with caplog.at_level(logging.WARNING, logger="entelgia"):
            with patch.object(_meta, "CFG", Config()):
                agent.speak(seed, self._PRIOR_TURN)

        persist_msgs = [r.message for r in caplog.records if "TOPIC-MISMATCH-PERSIST" in r.message]
        assert persist_msgs, (
            "Expected [TOPIC-MISMATCH-PERSIST] warning when regenerated response "
            "also lacks required topic anchors"
        )

    def test_no_persist_warning_when_regen_succeeds(self, caplog):
        """If the regenerated response contains the required anchors,
        no [TOPIC-MISMATCH-PERSIST] warning must be emitted."""
        agent = _make_agent()
        # First call misses anchors; second call (regeneration) includes one
        agent.llm.generate.side_effect = [
            "Redundancy and real-time monitoring prevent failures.",
            "Corrigibility is the key concept for AI alignment.",
        ]
        seed = "TOPIC: AI alignment\nDiscuss."
        with caplog.at_level(logging.WARNING, logger="entelgia"):
            with patch.object(_meta, "CFG", Config()):
                agent.speak(seed, self._PRIOR_TURN)

        persist_msgs = [r.message for r in caplog.records if "TOPIC-MISMATCH-PERSIST" in r.message]
        assert not persist_msgs, (
            "Expected no [TOPIC-MISMATCH-PERSIST] warning when regenerated "
            "response satisfies topic anchors"
        )


# ---------------------------------------------------------------------------
# Hard-recovery tests (Agent.speak)
# ---------------------------------------------------------------------------


class TestTopicHardRecovery:
    """Agent.speak applies [TOPIC-HARD-RECOVERY] when both initial and
    regenerated responses fail the anchor check."""

    _PRIOR_TURN = [{"role": "Socrates", "text": "I have thought about this before."}]

    def test_hard_recovery_logged_when_regen_also_fails(self, caplog):
        """[TOPIC-HARD-RECOVERY] must be logged when both attempts miss anchors."""
        agent = _make_agent()
        # All calls return a generic response with no anchor for 'AI alignment'
        agent.llm.generate.return_value = (
            "Redundancy and real-time monitoring prevent failures."
        )
        seed = "TOPIC: AI alignment\nDiscuss."
        with caplog.at_level(logging.WARNING, logger="entelgia"):
            with patch.object(_meta, "CFG", Config()):
                agent.speak(seed, self._PRIOR_TURN)

        recovery_msgs = [r.message for r in caplog.records if "TOPIC-HARD-RECOVERY" in r.message]
        assert recovery_msgs, (
            "Expected [TOPIC-HARD-RECOVERY] warning when both initial and "
            "regenerated responses lack required topic anchors"
        )

    def test_hard_recovery_uses_strict_prompt(self, caplog):
        """When hard recovery triggers, the LLM must be called a third time
        with a prompt containing the required strict enforcement elements."""
        agent = _make_agent()
        captured_prompts = []

        def capturing_generate(model, prompt, **kwargs):
            captured_prompts.append(prompt)
            return "Redundancy and real-time monitoring prevent failures."

        agent.llm.generate.side_effect = capturing_generate
        seed = "TOPIC: AI alignment\nDiscuss."
        with caplog.at_level(logging.WARNING, logger="entelgia"):
            with patch.object(_meta, "CFG", Config()):
                agent.speak(seed, self._PRIOR_TURN)

        # Three calls: initial, regen, hard-recovery
        assert len(captured_prompts) == 3, (
            f"Expected exactly 3 LLM calls (initial + regen + hard-recovery), "
            f"got {len(captured_prompts)}"
        )
        hard_prompt = captured_prompts[2]
        assert "STRICT TOPIC ENFORCEMENT" in hard_prompt
        assert "AI alignment" in hard_prompt
        assert "2-4 sentences" in hard_prompt
        assert "balanced approach" in hard_prompt
        assert "underlying assumptions" in hard_prompt
        assert "ethical considerations" in hard_prompt
        assert "flexible systems" in hard_prompt

    def test_hard_recovery_output_used(self, caplog):
        """The output returned by speak() after hard recovery must be the
        response from the third (strict) LLM call, not the second generic one."""
        agent = _make_agent()
        hard_recovery_text = "Corrigibility ensures AI systems remain correctable by humans."
        agent.llm.generate.side_effect = [
            "Redundancy and real-time monitoring prevent failures.",  # initial
            "Redundancy and real-time monitoring prevent failures.",  # regen
            hard_recovery_text,                                       # hard recovery
        ]
        seed = "TOPIC: AI alignment\nDiscuss."
        with caplog.at_level(logging.WARNING, logger="entelgia"):
            with patch.object(_meta, "CFG", Config()):
                result = agent.speak(seed, self._PRIOR_TURN)

        assert hard_recovery_text in result, (
            "Expected the hard-recovery response to be used as the final output"
        )

    def test_no_hard_recovery_when_regen_succeeds(self, caplog):
        """[TOPIC-HARD-RECOVERY] must NOT be logged when the regenerated
        response satisfies the anchor check."""
        agent = _make_agent()
        agent.llm.generate.side_effect = [
            "Redundancy and real-time monitoring prevent failures.",
            "Corrigibility is the key concept for AI alignment.",
        ]
        seed = "TOPIC: AI alignment\nDiscuss."
        with caplog.at_level(logging.WARNING, logger="entelgia"):
            with patch.object(_meta, "CFG", Config()):
                agent.speak(seed, self._PRIOR_TURN)

        recovery_msgs = [r.message for r in caplog.records if "TOPIC-HARD-RECOVERY" in r.message]
        assert not recovery_msgs, (
            "Expected no [TOPIC-HARD-RECOVERY] when the regenerated response "
            "satisfies the anchor check"
        )

    def test_hard_recovery_anchors_slice(self, caplog):
        """The strict prompt must include 3-5 required topic anchors from
        TOPIC_ANCHORS (at most 5, i.e. the first slice of the anchor list)."""
        agent = _make_agent()
        captured_prompts = []

        def capturing_generate(model, prompt, **kwargs):
            captured_prompts.append(prompt)
            return "Redundancy and real-time monitoring prevent failures."

        agent.llm.generate.side_effect = capturing_generate
        seed = "TOPIC: AI alignment\nDiscuss."
        with caplog.at_level(logging.WARNING, logger="entelgia"):
            with patch.object(_meta, "CFG", Config()):
                agent.speak(seed, self._PRIOR_TURN)

        hard_prompt = captured_prompts[2]
        expected_anchors = TOPIC_ANCHORS["AI alignment"][:5]
        for anchor in expected_anchors:
            assert anchor in hard_prompt, (
                f"Expected anchor {anchor!r} in hard-recovery prompt"
            )


# ---------------------------------------------------------------------------
# First-turn topic anchor skip tests (Agent.speak)
# ---------------------------------------------------------------------------


class TestTopicMismatchFirstTurn:
    """Agent.speak must NOT run topic anchor validation on the agent's first turn.

    On the first turn ``own_texts`` is empty (the agent has not spoken yet).
    Firing the anchor check at that point would produce [TOPIC-MISMATCH] /
    [TOPIC-MISMATCH-PERSIST] log entries before the agent has said anything —
    the bug reported in the issue.
    """

    def test_no_mismatch_warning_on_first_turn(self, caplog):
        """No [TOPIC-MISMATCH] warning when the agent speaks for the first time,
        even if the response lacks required topic anchors."""
        agent = _make_agent()
        # Response deliberately contains no anchor concepts for 'AI alignment'
        agent.llm.generate.return_value = (
            "Redundancy and real-time monitoring prevent failures."
        )
        seed = "TOPIC: AI alignment\nDiscuss."
        # Empty dialog_tail → agent has not spoken yet (first turn)
        with caplog.at_level(logging.WARNING, logger="entelgia"):
            with patch.object(_meta, "CFG", Config()):
                agent.speak(seed, [])

        mismatch_msgs = [
            r.message for r in caplog.records if "TOPIC-MISMATCH" in r.message
        ]
        assert not mismatch_msgs, (
            "Expected no [TOPIC-MISMATCH] warning on the agent's first turn; "
            "validation should be skipped before the agent has spoken at all"
        )

    def test_no_persist_warning_on_first_turn(self, caplog):
        """No [TOPIC-MISMATCH-PERSIST] warning on the agent's first turn."""
        agent = _make_agent()
        agent.llm.generate.return_value = (
            "Redundancy and real-time monitoring prevent failures."
        )
        seed = "TOPIC: AI alignment\nDiscuss."
        with caplog.at_level(logging.WARNING, logger="entelgia"):
            with patch.object(_meta, "CFG", Config()):
                agent.speak(seed, [])

        persist_msgs = [
            r.message for r in caplog.records if "TOPIC-MISMATCH-PERSIST" in r.message
        ]
        assert not persist_msgs, (
            "Expected no [TOPIC-MISMATCH-PERSIST] warning on the agent's first turn"
        )

    def test_validation_runs_from_second_turn_onwards(self, caplog):
        """[TOPIC-MISMATCH] warning IS emitted once the agent has a prior turn."""
        agent = _make_agent()
        agent.llm.generate.return_value = (
            "Redundancy and real-time monitoring prevent failures."
        )
        seed = "TOPIC: AI alignment\nDiscuss."
        prior_turn = [{"role": "Socrates", "text": "I have previously spoken on this."}]
        with caplog.at_level(logging.WARNING, logger="entelgia"):
            with patch.object(_meta, "CFG", Config()):
                agent.speak(seed, prior_turn)

        mismatch_msgs = [
            r.message for r in caplog.records if "TOPIC-MISMATCH" in r.message
        ]
        assert mismatch_msgs, (
            "Expected [TOPIC-MISMATCH] warning on the agent's second turn when "
            "the response lacks required topic anchors"
        )


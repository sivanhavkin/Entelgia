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
    TOPIC_CYCLE,
    TOPIC_FALLBACK_TEMPLATES,
    Agent,
    BehaviorCore,
    Config,
    ConsciousCore,
    EmotionCore,
    LanguageCore,
    _contains_any,
    _topic_relevance_score,
    _validate_topic_compliance,
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
            topic for topics in TOPIC_CLUSTERS.values() for topic in topics
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
                assert (
                    isinstance(kw, str) and kw.strip()
                ), f"Invalid anchor keyword {kw!r} in topic {topic!r}"

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
        assert required.issubset(
            actual
        ), f"AI alignment anchors missing required terms: {required - actual}"

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
        assert required.issubset(
            actual
        ), f"Risk and decision making anchors missing broad terms: {required - actual}"

    def test_risk_and_decision_making_anchors_match_autonomous_vehicle_response(self):
        """A response about autonomous vehicle design risk tradeoffs must match
        the Risk and decision making anchors (regression for TOPIC-MISMATCH false positive).
        """
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
        assert _contains_any(
            av_response, anchors
        ), "Autonomous vehicle risk-tradeoff response should match Risk and decision making anchors"


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

        assert "Topic constraint:" in prompt
        assert "The active topic is: AI alignment." in prompt
        assert "must stay within this topic" in prompt
        assert "corrigibility" in prompt
        assert "reward hacking" in prompt

    def test_no_anchor_requirement_for_unknown_topic(self):
        cfg = Config()
        agent = _make_agent()
        seed = "TOPIC: Some unknown topic\nDiscuss."
        with patch.object(_meta, "CFG", cfg):
            prompt = agent._build_compact_prompt(seed, [])

        assert "Topic constraint:" not in prompt
        assert "The active topic is:" not in prompt

    def test_no_anchor_requirement_when_no_topic_in_seed(self):
        cfg = Config()
        agent = _make_agent()
        seed = "What is consciousness?"
        with patch.object(_meta, "CFG", cfg):
            prompt = agent._build_compact_prompt(seed, [])

        assert "Topic constraint:" not in prompt
        assert "The active topic is:" not in prompt

    def test_forbidden_carryover_injected_on_topic_change(self):
        cfg = Config()
        agent = _make_agent(last_topic="Autonomous systems")
        seed = "TOPIC: AI alignment\nDiscuss."
        with patch.object(_meta, "CFG", cfg):
            prompt = agent._build_compact_prompt(seed, [])

        assert "Do NOT reuse concepts from previous discussions" in prompt
        # Autonomous systems anchors should appear as forbidden
        for concept in TOPIC_ANCHORS["Autonomous systems"]:
            assert (
                concept in prompt
            ), f"Expected forbidden concept {concept!r} in prompt"

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
    """Agent.speak applies graded topic compliance and logs [TOPIC-HARD-RECOVERY]
    or [TOPIC-SOFT-REANCHOR] when the initial response is off-topic.

    Note: The old [TOPIC-MISMATCH-PERSIST] log entry is replaced by the graded
    enforcement ladder introduced in v3.0.0.
    """

    # A prior turn for Socrates is required so the validation is not skipped
    # (it is intentionally skipped on the first turn — see TestTopicMismatchFirstTurn).
    _PRIOR_TURN = [{"role": "Socrates", "text": "I have thought about this before."}]

    def test_persist_warning_logged_when_regen_also_fails(self, caplog):
        """If the initial response is severely off-topic (score < 0.50), a
        [TOPIC-HARD-RECOVERY] warning must be emitted (the old [TOPIC-MISMATCH-PERSIST]
        is superseded by the graded enforcement flow)."""
        agent = _make_agent()
        # Both calls return a response with no anchor for 'AI alignment'
        agent.llm.generate.return_value = (
            "Redundancy and real-time monitoring prevent failures."
        )
        seed = "TOPIC: AI alignment\nDiscuss."
        with caplog.at_level(logging.WARNING, logger="entelgia"):
            with patch.object(_meta, "CFG", Config()):
                agent.speak(seed, self._PRIOR_TURN)

        recovery_msgs = [
            r.message for r in caplog.records
            if "TOPIC-HARD-RECOVERY" in r.message or "TOPIC-SOFT-REANCHOR" in r.message
        ]
        assert recovery_msgs, (
            "Expected [TOPIC-HARD-RECOVERY] or [TOPIC-SOFT-REANCHOR] warning when "
            "initial response lacks required topic anchors"
        )

    def test_no_persist_warning_when_regen_succeeds(self, caplog):
        """If the initial response is already accepted, no recovery warning is emitted."""
        agent = _make_agent()
        # Single call returns a response that IS on-topic
        agent.llm.generate.return_value = "Corrigibility is the key concept for AI alignment."
        seed = "TOPIC: AI alignment\nDiscuss."
        with caplog.at_level(logging.WARNING, logger="entelgia"):
            with patch.object(_meta, "CFG", Config()):
                agent.speak(seed, self._PRIOR_TURN)

        recovery_msgs = [
            r.message for r in caplog.records
            if "TOPIC-HARD-RECOVERY" in r.message or "TOPIC-SOFT-REANCHOR" in r.message
        ]
        assert not recovery_msgs, (
            "Expected no recovery warning when initial response satisfies topic anchors"
        )


# ---------------------------------------------------------------------------
# Hard-recovery tests (Agent.speak)
# ---------------------------------------------------------------------------


class TestTopicHardRecovery:
    """Agent.speak applies [TOPIC-HARD-RECOVERY] when the initial response scores
    below the soft re-anchor threshold (< 0.50)."""

    _PRIOR_TURN = [{"role": "Socrates", "text": "I have thought about this before."}]

    def test_hard_recovery_logged_when_regen_also_fails(self, caplog):
        """[TOPIC-HARD-RECOVERY] must be logged when the initial response is
        severely off-topic (score < 0.50)."""
        agent = _make_agent()
        # All calls return a generic response with no anchor for 'AI alignment'
        agent.llm.generate.return_value = (
            "Redundancy and real-time monitoring prevent failures."
        )
        seed = "TOPIC: AI alignment\nDiscuss."
        with caplog.at_level(logging.WARNING, logger="entelgia"):
            with patch.object(_meta, "CFG", Config()):
                agent.speak(seed, self._PRIOR_TURN)

        recovery_msgs = [
            r.message for r in caplog.records if "TOPIC-HARD-RECOVERY" in r.message
        ]
        assert recovery_msgs, (
            "Expected [TOPIC-HARD-RECOVERY] warning when initial response is "
            "severely off-topic (score < 0.50)"
        )

    def test_hard_recovery_uses_strict_prompt(self, caplog):
        """When hard recovery triggers, the LLM must be called a second time
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

        # Two calls: initial (score < 0.50 → hard recovery) + hard-recovery prompt
        assert len(captured_prompts) == 2, (
            f"Expected exactly 2 LLM calls (initial + hard-recovery), "
            f"got {len(captured_prompts)}"
        )
        hard_prompt = captured_prompts[1]
        assert "STRICT TOPIC ENFORCEMENT" in hard_prompt
        assert "AI alignment" in hard_prompt
        assert "2-4 sentences" in hard_prompt
        assert "balanced approach" in hard_prompt
        assert "underlying assumptions" in hard_prompt
        assert "ethical considerations" in hard_prompt
        assert "flexible systems" in hard_prompt

    def test_hard_recovery_output_used(self, caplog):
        """The output returned by speak() after hard recovery must be the
        response from the second (strict) LLM call."""
        agent = _make_agent()
        hard_recovery_text = (
            "Corrigibility ensures AI systems remain correctable by humans."
        )
        agent.llm.generate.side_effect = [
            "Redundancy and real-time monitoring prevent failures.",  # initial
            hard_recovery_text,  # hard recovery
        ]
        seed = "TOPIC: AI alignment\nDiscuss."
        with caplog.at_level(logging.WARNING, logger="entelgia"):
            with patch.object(_meta, "CFG", Config()):
                result = agent.speak(seed, self._PRIOR_TURN)

        assert (
            hard_recovery_text in result
        ), "Expected the hard-recovery response to be used as the final output"

    def test_no_hard_recovery_when_initial_accepted(self, caplog):
        """[TOPIC-HARD-RECOVERY] must NOT be logged when the initial response
        satisfies the topic compliance threshold (score >= 0.70)."""
        agent = _make_agent()
        # Directly on-topic: has AI alignment anchor
        agent.llm.generate.return_value = "Corrigibility is the key concept for AI alignment."
        seed = "TOPIC: AI alignment\nDiscuss."
        with caplog.at_level(logging.WARNING, logger="entelgia"):
            with patch.object(_meta, "CFG", Config()):
                agent.speak(seed, self._PRIOR_TURN)

        recovery_msgs = [
            r.message for r in caplog.records if "TOPIC-HARD-RECOVERY" in r.message
        ]
        assert not recovery_msgs, (
            "Expected no [TOPIC-HARD-RECOVERY] when the initial response "
            "satisfies the topic compliance threshold"
        )

    def test_hard_recovery_anchors_slice(self, caplog):
        """The strict prompt must include up to 5 required topic anchors from
        TOPIC_ANCHORS (i.e. the first slice of the anchor list)."""
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

        assert len(captured_prompts) == 2, (
            f"Expected 2 LLM calls; got {len(captured_prompts)}"
        )
        hard_prompt = captured_prompts[1]
        expected_anchors = TOPIC_ANCHORS["AI alignment"][:5]
        for anchor in expected_anchors:
            assert (
                anchor in hard_prompt
            ), f"Expected anchor {anchor!r} in hard-recovery prompt"


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
        assert (
            not persist_msgs
        ), "Expected no [TOPIC-MISMATCH-PERSIST] warning on the agent's first turn"

    def test_validation_runs_from_second_turn_onwards(self, caplog):
        """A recovery warning IS emitted once the agent has a prior turn and the
        response is off-topic."""
        agent = _make_agent()
        agent.llm.generate.return_value = (
            "Redundancy and real-time monitoring prevent failures."
        )
        seed = "TOPIC: AI alignment\nDiscuss."
        prior_turn = [{"role": "Socrates", "text": "I have previously spoken on this."}]
        with caplog.at_level(logging.WARNING, logger="entelgia"):
            with patch.object(_meta, "CFG", Config()):
                agent.speak(seed, prior_turn)

        recovery_msgs = [
            r.message for r in caplog.records
            if "TOPIC-HARD-RECOVERY" in r.message or "TOPIC-SOFT-REANCHOR" in r.message
        ]
        assert recovery_msgs, (
            "Expected a recovery warning on the agent's second turn when "
            "the response lacks required topic anchors"
        )


# ---------------------------------------------------------------------------
# _topic_relevance_score tests
# ---------------------------------------------------------------------------


class TestTopicRelevanceScore:
    """_topic_relevance_score() counts distinct anchor term matches."""

    def test_returns_zero_for_no_match(self):
        anchors = ["corrigibility", "reward hacking", "value learning"]
        assert _topic_relevance_score("Nothing relevant here.", anchors) == 0

    def test_returns_one_for_single_match(self):
        anchors = ["corrigibility", "reward hacking", "value learning"]
        assert _topic_relevance_score("Corrigibility is important.", anchors) == 1

    def test_returns_two_for_two_matches(self):
        anchors = ["corrigibility", "reward hacking", "value learning"]
        assert (
            _topic_relevance_score(
                "Corrigibility and reward hacking are related.", anchors
            )
            == 2
        )

    def test_case_insensitive(self):
        anchors = ["Corrigibility", "Reward Hacking"]
        assert _topic_relevance_score("CORRIGIBILITY and REWARD HACKING.", anchors) == 2

    def test_counts_all_unique_anchors(self):
        anchors = TOPIC_ANCHORS["AI alignment"]
        text = " ".join(anchors)  # all anchors present
        assert _topic_relevance_score(text, anchors) == len(anchors)


# ---------------------------------------------------------------------------
# _validate_topic_compliance 3-layer tests
# ---------------------------------------------------------------------------


class TestValidateTopicCompliance:
    """_validate_topic_compliance() 3-layer validation tests."""

    def test_passes_when_anchor_present(self):
        """Layer 1: response with current-topic anchor passes."""
        assert _validate_topic_compliance(
            "Corrigibility is the key to AI alignment.",
            "AI alignment",
        )

    def test_fails_when_no_anchor(self):
        """Layer 1: response with no anchor for topic fails."""
        assert not _validate_topic_compliance(
            "Redundancy and real-time monitoring prevent failures.",
            "AI alignment",
        )

    def test_passes_for_unknown_topic(self):
        """No anchors defined for topic → passes by default."""
        assert _validate_topic_compliance("Anything at all.", "NonExistentTopic")

    def test_layer2_fails_on_carryover_dominance(self):
        """Layer 2: fails when prev-topic anchors dominate over current-topic anchors."""
        # "AI alignment" anchors: corrigibility, reward hacking, ...
        # "Autonomous systems" anchors: self-direction, automation, control systems, ...
        # Build a text that has 2+ prev anchors but only 1 current anchor
        text = (
            "Self-direction and automation are key to control systems. "
            "Corrigibility is relevant here."
        )
        # current_topic=AI alignment (1 hit), prev_topic=Autonomous systems (3 hits)
        result = _validate_topic_compliance(
            text, "AI alignment", prev_topic="Autonomous systems"
        )
        assert not result, (
            "Expected compliance failure when previous-topic anchors (3) dominate "
            "current-topic anchors (1)"
        )

    def test_layer2_passes_when_current_dominates(self):
        """Layer 2: passes when current-topic anchors >= prev-topic anchors."""
        # 2 AI alignment hits, 2 Autonomous systems hits → current not less than prev
        text = (
            "Corrigibility and reward hacking are crucial for AI alignment. "
            "Self-direction and automation also matter."
        )
        result = _validate_topic_compliance(
            text, "AI alignment", prev_topic="Autonomous systems"
        )
        assert (
            result
        ), "Expected compliance pass when current-topic anchors are not fewer than prev-topic"

    def test_layer2_skipped_when_prev_topic_empty(self):
        """Layer 2: carryover check is skipped when prev_topic is empty."""
        text = "Corrigibility is the key to AI alignment."
        assert _validate_topic_compliance(text, "AI alignment", prev_topic="")

    def test_layer2_skipped_when_same_topic(self):
        """Layer 2: carryover check is skipped when prev_topic == current topic."""
        text = "Corrigibility is the key to AI alignment."
        assert _validate_topic_compliance(
            text, "AI alignment", prev_topic="AI alignment"
        )

    def test_layer2_skipped_when_prev_topic_has_no_anchors(self):
        """Layer 2: skipped when prev_topic has no anchors in TOPIC_ANCHORS."""
        text = "Corrigibility is important."
        assert _validate_topic_compliance(
            text, "AI alignment", prev_topic="UnknownPrevTopic"
        )


# ---------------------------------------------------------------------------
# TOPIC_FALLBACK_TEMPLATES structure tests
# ---------------------------------------------------------------------------


class TestTopicFallbackTemplates:
    """TOPIC_FALLBACK_TEMPLATES structure and coverage tests."""

    def test_is_dict(self):
        assert isinstance(TOPIC_FALLBACK_TEMPLATES, dict)

    def test_is_non_empty(self):
        assert len(TOPIC_FALLBACK_TEMPLATES) > 0

    def test_every_key_has_non_empty_string(self):
        for topic, text in TOPIC_FALLBACK_TEMPLATES.items():
            assert (
                isinstance(text, str) and text.strip()
            ), f"Empty fallback template for topic {topic!r}"

    def test_every_fallback_passes_compliance(self):
        """Every fallback template must pass _validate_topic_compliance for its own topic."""
        for topic, text in TOPIC_FALLBACK_TEMPLATES.items():
            if TOPIC_ANCHORS.get(topic):
                assert _validate_topic_compliance(
                    text, topic
                ), f"Fallback template for {topic!r} does not pass its own topic compliance check"

    def test_all_topic_clusters_topics_covered(self):
        """Every topic in TOPIC_CLUSTERS should have a fallback template."""
        all_cluster_topics = {t for topics in TOPIC_CLUSTERS.values() for t in topics}
        missing = all_cluster_topics - set(TOPIC_FALLBACK_TEMPLATES.keys())
        assert not missing, f"Missing TOPIC_FALLBACK_TEMPLATES entries for: {missing}"


# ---------------------------------------------------------------------------
# [TOPIC-FALLBACK] log and template output tests
# ---------------------------------------------------------------------------


class TestTopicFallbackPipeline:
    """Agent.speak uses topic-safe fallback when hard recovery also fails."""

    _PRIOR_TURN = [{"role": "Socrates", "text": "I have previously spoken."}]

    def test_fallback_logged_when_hard_recovery_fails(self, caplog):
        """[TOPIC-FALLBACK] must be logged when hard recovery also misses the topic."""
        agent = _make_agent()
        # All three LLM calls return an off-topic response
        agent.llm.generate.return_value = (
            "Redundancy and real-time monitoring prevent failures."
        )
        seed = "TOPIC: AI alignment\nDiscuss."
        with caplog.at_level(logging.WARNING, logger="entelgia"):
            with patch.object(_meta, "CFG", Config()):
                agent.speak(seed, self._PRIOR_TURN)

        fallback_msgs = [
            r.message for r in caplog.records if "TOPIC-FALLBACK" in r.message
        ]
        assert (
            fallback_msgs
        ), "Expected [TOPIC-FALLBACK] warning when hard recovery also fails"

    def test_fallback_template_used_as_output(self, caplog):
        """The final output after total failure must be the fallback template."""
        agent = _make_agent()
        agent.llm.generate.return_value = (
            "Redundancy and real-time monitoring prevent failures."
        )
        seed = "TOPIC: AI alignment\nDiscuss."
        with caplog.at_level(logging.WARNING, logger="entelgia"):
            with patch.object(_meta, "CFG", Config()):
                result = agent.speak(seed, self._PRIOR_TURN)

        expected_fallback = TOPIC_FALLBACK_TEMPLATES["AI alignment"]
        assert expected_fallback in result, (
            "Expected the topic-safe fallback template to be the final output "
            f"when all recovery attempts fail. Got: {result!r}"
        )

    def test_fallback_not_triggered_when_hard_recovery_passes(self, caplog):
        """[TOPIC-FALLBACK] must NOT be logged when hard recovery produces a valid response."""
        agent = _make_agent()
        agent.llm.generate.side_effect = [
            "Redundancy and real-time monitoring prevent failures.",  # initial (score=0.0)
            "Corrigibility ensures AI systems remain correctable by humans.",  # hard recovery
        ]
        seed = "TOPIC: AI alignment\nDiscuss."
        with caplog.at_level(logging.WARNING, logger="entelgia"):
            with patch.object(_meta, "CFG", Config()):
                result = agent.speak(seed, self._PRIOR_TURN)

        fallback_msgs = [
            r.message for r in caplog.records if "TOPIC-FALLBACK" in r.message
        ]
        assert (
            not fallback_msgs
        ), "Expected no [TOPIC-FALLBACK] when hard recovery response passes validation"
        assert (
            "Corrigibility" in result
        ), "Expected hard-recovery response to be used when it passes validation"

    def test_generic_fallback_for_unknown_topic(self, caplog):
        """When topic has no template entry, a generic fallback sentence is used."""
        agent = _make_agent()
        # Use a topic not in TOPIC_FALLBACK_TEMPLATES but in TOPIC_ANCHORS
        # Manually inject a fake anchor to force the fallback path
        fake_topic = "AI alignment"
        fake_anchors = ["corrigibility"]
        agent.llm.generate.return_value = "Nothing about AI here at all."
        seed = f"TOPIC: {fake_topic}\nDiscuss."
        # Remove from TOPIC_FALLBACK_TEMPLATES temporarily to test generic fallback
        import Entelgia_production_meta as _meta_module

        original = _meta_module.TOPIC_FALLBACK_TEMPLATES.pop(fake_topic, None)
        try:
            with caplog.at_level(logging.WARNING, logger="entelgia"):
                with patch.object(_meta, "CFG", Config()):
                    result = agent.speak(seed, self._PRIOR_TURN)
            assert (
                fake_topic in result
            ), "Expected the generic fallback to mention the topic name"
        finally:
            if original is not None:
                _meta_module.TOPIC_FALLBACK_TEMPLATES[fake_topic] = original


# ---------------------------------------------------------------------------
# Hard recovery forbidden abstractions and anchor requirement tests
# ---------------------------------------------------------------------------


class TestHardRecoveryPromptEnhancements:
    """Hard recovery prompt includes expanded forbidden list and 2-anchor requirement."""

    _PRIOR_TURN = [{"role": "Socrates", "text": "I have thought about this before."}]

    def test_hard_recovery_includes_expanded_forbidden_terms(self, caplog):
        """The strict prompt must contain 'empirical evidence suggests' and 'holistic view'."""
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

        # Two calls: initial + hard recovery
        assert len(captured_prompts) == 2, (
            f"Expected 2 LLM calls (initial + hard-recovery); got {len(captured_prompts)}"
        )
        hard_prompt = captured_prompts[1]
        assert (
            "empirical evidence suggests" in hard_prompt
        ), "Expected 'empirical evidence suggests' in hard-recovery forbidden list"
        assert (
            "holistic view" in hard_prompt
        ), "Expected 'holistic view' in hard-recovery forbidden list"

    def test_hard_recovery_requires_two_anchors(self, caplog):
        """Hard recovery prompt must say 'at least two' topic anchors, not 'at least one'."""
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

        assert len(captured_prompts) == 2
        hard_prompt = captured_prompts[1]
        assert (
            "at least two" in hard_prompt
        ), "Expected hard-recovery prompt to require 'at least two' topic anchors"


# ---------------------------------------------------------------------------
# Topic pool coverage test (topic selection fix)
# ---------------------------------------------------------------------------


class TestTopicPoolCoverage:
    """Topic rotation must draw from all TOPIC_CLUSTERS, not just TOPIC_CYCLE."""

    def test_topic_cycle_is_subset_of_topic_clusters(self):
        """Every topic in TOPIC_CYCLE must appear in TOPIC_CLUSTERS."""
        all_cluster_topics = {t for topics in TOPIC_CLUSTERS.values() for t in topics}
        missing = set(TOPIC_CYCLE) - all_cluster_topics
        assert (
            not missing
        ), f"TOPIC_CYCLE entries not found in TOPIC_CLUSTERS: {missing}"

    def test_topic_clusters_has_more_topics_than_topic_cycle(self):
        """TOPIC_CLUSTERS must have significantly more topics than TOPIC_CYCLE."""
        all_cluster_topics = {t for topics in TOPIC_CLUSTERS.values() for t in topics}
        assert len(all_cluster_topics) > len(TOPIC_CYCLE), (
            "TOPIC_CLUSTERS should define more topics than TOPIC_CYCLE; "
            f"got {len(all_cluster_topics)} vs {len(TOPIC_CYCLE)}"
        )

    def test_all_topic_clusters_topics_have_anchors(self):
        """Every topic in TOPIC_CLUSTERS must have a TOPIC_ANCHORS entry."""
        all_cluster_topics = {t for topics in TOPIC_CLUSTERS.values() for t in topics}
        missing_anchors = all_cluster_topics - set(TOPIC_ANCHORS.keys())
        assert (
            not missing_anchors
        ), f"Topics in TOPIC_CLUSTERS missing TOPIC_ANCHORS entries: {missing_anchors}"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s", "--override-ini=addopts="])

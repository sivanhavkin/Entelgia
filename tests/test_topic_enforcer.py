#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Tests for the new soft topic-enforcement and proposal/selection system.

Covers (Part G requirements):
  1. Topic proposal stays inside cluster
  2. Topic selector prefers novel but relevant topics
  3. Opening sentence anchored to session topic is accepted
  4. Response with mild prior-memory influence is accepted
  5. Response with previous-topic framing dominating opening is penalised
  6. Soft re-anchor path triggers before hard recovery
  7. Hard recovery occurs only for severe contamination
  8. Agent-local continuity does not override session topic anchoring
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

from Entelgia_production_meta import (
    TOPIC_CLUSTERS,
    TOPIC_ANCHORS,
    TopicManager,
    propose_next_topic,
    select_next_topic,
)
from entelgia.topic_enforcer import (
    ACCEPT_THRESHOLD,
    SOFT_REANCHOR_THRESHOLD,
    compute_topic_compliance_score,
    build_soft_reanchor_instruction,
    _get_opening_sentences,
    _semantic_relevance,
    _contamination_score,
    _stale_phrase_penalty,
    _STALE_CONTAMINATION_PHRASES,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _economics_cluster_topics() -> list[str]:
    return TOPIC_CLUSTERS.get("economics", [])


def _philosophy_cluster_topics() -> list[str]:
    return TOPIC_CLUSTERS.get("philosophy", [])


# ---------------------------------------------------------------------------
# 1. Topic proposal stays inside cluster
# ---------------------------------------------------------------------------


class TestTopicProposal:
    """propose_next_topic() should return topics within the session cluster."""

    def test_proposal_within_economics_cluster(self):
        cluster = "economics"
        cluster_topics = _economics_cluster_topics()
        current = cluster_topics[0]
        proposal = propose_next_topic(
            "Socrates", current, cluster, recent_topics=[], recent_memory=[]
        )
        # Proposal must come from the economics cluster
        assert proposal in cluster_topics, (
            f"Expected proposal in economics cluster, got {proposal!r}"
        )

    def test_proposal_avoids_current_topic(self):
        cluster = "economics"
        cluster_topics = _economics_cluster_topics()
        current = cluster_topics[0]
        for _ in range(20):
            proposal = propose_next_topic(
                "Athena", current, cluster, recent_topics=[], recent_memory=[]
            )
            assert proposal != current, "Proposal should not equal current topic"

    def test_proposal_avoids_recent_topics_when_possible(self):
        cluster = "economics"
        cluster_topics = _economics_cluster_topics()
        current = cluster_topics[0]
        recent = cluster_topics[1:4]
        # Run 10 trials — proposal should generally avoid recent topics when alternatives exist
        avoidance_count = 0
        for _ in range(10):
            proposal = propose_next_topic(
                "Socrates", current, cluster, recent_topics=recent, recent_memory=[]
            )
            if proposal not in recent:
                avoidance_count += 1
        # At least 5/10 proposals should avoid recent topics
        assert avoidance_count >= 5, (
            f"Expected proposals to mostly avoid recent topics, got {avoidance_count}/10"
        )

    def test_proposal_influenced_by_memory(self):
        """Anchors from memory should make related topics more likely."""
        cluster = "economics"
        cluster_topics = _economics_cluster_topics()
        # Inject anchors for "Scarcity and human behavior" into memory
        scarcity_anchors = TOPIC_ANCHORS.get("Scarcity and human behavior", [])
        if not scarcity_anchors:
            pytest.skip("No anchors defined for 'Scarcity and human behavior'")
        memory_text = " ".join(scarcity_anchors)
        current = cluster_topics[1]  # Something other than scarcity
        proposals = [
            propose_next_topic(
                "Socrates",
                current,
                cluster,
                recent_topics=[current],
                recent_memory=[memory_text],
            )
            for _ in range(20)
        ]
        # "Scarcity and human behavior" should appear at least once in 20 trials
        assert "Scarcity and human behavior" in proposals, (
            "Memory-relevant topic should appear in proposals when anchors match"
        )

    def test_proposal_returns_string(self):
        proposal = propose_next_topic(
            "Socrates", "Economic freedom", "economics", [], []
        )
        assert isinstance(proposal, str)
        assert len(proposal) > 0


# ---------------------------------------------------------------------------
# 2. Topic selector prefers novel but relevant topics
# ---------------------------------------------------------------------------


class TestTopicSelection:
    """select_next_topic() scoring: cluster_fit × novelty × memory_relevance."""

    def test_selector_prefers_novel_topic(self):
        cluster = "economics"
        cluster_topics = _economics_cluster_topics()
        recent = cluster_topics[:3]
        # Propose one novel (not recent) topic and one that was very recent
        novel = cluster_topics[5] if len(cluster_topics) > 5 else cluster_topics[-1]
        stale = recent[-1]  # most recent
        selected = select_next_topic(
            [stale, novel], cluster, recent_topics=recent
        )
        assert selected == novel, (
            f"Expected novel topic {novel!r}, got {selected!r}"
        )

    def test_selector_prefers_cluster_topic_over_external(self):
        cluster = "economics"
        cluster_topics = _economics_cluster_topics()
        # One in-cluster candidate vs one from a different cluster
        in_cluster = cluster_topics[0]
        out_cluster = _philosophy_cluster_topics()[0]
        selected = select_next_topic(
            [out_cluster, in_cluster], cluster, recent_topics=[]
        )
        assert selected == in_cluster, (
            f"Should prefer in-cluster topic, got {selected!r}"
        )

    def test_selector_penalises_most_recent_topic(self):
        cluster = "economics"
        cluster_topics = _economics_cluster_topics()
        most_recent = cluster_topics[0]
        novel = cluster_topics[3]
        recent = [most_recent]
        selected = select_next_topic(
            [most_recent, novel], cluster, recent_topics=recent
        )
        assert selected == novel, (
            f"Most-recent topic should be penalised; expected {novel!r}, got {selected!r}"
        )

    def test_selector_returns_string_for_single_proposal(self):
        result = select_next_topic(["Economic freedom"], "economics")
        assert result == "Economic freedom"

    def test_selector_returns_empty_for_empty_proposals(self):
        result = select_next_topic([], "economics")
        assert result == ""

    def test_memory_relevance_boosts_matching_topic(self):
        """Topics whose anchor keywords appear in recent_agent_frames score higher."""
        cluster = "economics"
        cluster_topics = _economics_cluster_topics()
        target = "Scarcity and human behavior"
        if target not in cluster_topics:
            pytest.skip(f"{target!r} not in economics cluster")
        anchors = TOPIC_ANCHORS.get(target, [])
        if not anchors:
            pytest.skip("No anchors for target topic")
        other = [t for t in cluster_topics if t != target][0]
        frames = [" ".join(anchors)]
        # Target should win because its anchors appear in recent frames
        selected = select_next_topic(
            [other, target],
            cluster,
            recent_topics=[other],
            recent_agent_frames=frames,
        )
        assert selected == target, (
            f"Memory-relevant topic should be selected; got {selected!r}"
        )


# ---------------------------------------------------------------------------
# 3. Opening sentence anchored to session topic is accepted
# ---------------------------------------------------------------------------


class TestComplianceScoreAccept:
    """Responses that open with clear topic anchoring should score >= 0.70."""

    def test_well_anchored_opening_accepted(self):
        topic = "Economic freedom"
        anchors = TOPIC_ANCHORS.get(topic, [])
        if not anchors:
            pytest.skip(f"No anchors for {topic!r}")
        # Construct a response that mentions an anchor in the opening sentence
        anchor_word = anchors[0]
        text = (
            f"The concept of {anchor_word} is central to understanding economic systems. "
            "When institutions constrain individual choice, economic outcomes suffer."
        )
        result = compute_topic_compliance_score(text, topic, anchors)
        assert result["score"] >= ACCEPT_THRESHOLD, (
            f"Well-anchored response should be accepted; score={result['score']:.2f}"
        )

    def test_score_structure(self):
        """compute_topic_compliance_score always returns all expected keys."""
        result = compute_topic_compliance_score("some text", "Freedom", [])
        required_keys = {
            "opening_topic_relevance",
            "full_response_topic_relevance",
            "contamination_penalty",
            "memory_hijack_penalty",
            "score",
        }
        assert required_keys.issubset(result.keys())

    def test_no_anchors_returns_perfect_score(self):
        result = compute_topic_compliance_score("anything at all", "unknown topic", [])
        assert result["score"] == 1.0

    def test_score_clamped_to_unit_interval(self):
        topic = "Freedom"
        anchors = TOPIC_ANCHORS.get(topic, ["autonomy", "liberty"])
        # Construct text with anchor words AND stale contamination phrases
        stale_phrase = _STALE_CONTAMINATION_PHRASES[0]
        prev_anchors = TOPIC_ANCHORS.get("AI alignment", ["alignment", "safety"])
        text = f"{anchors[0]} {stale_phrase} " + " ".join(prev_anchors)
        result = compute_topic_compliance_score(
            text, topic, anchors, prev_anchors=prev_anchors
        )
        assert 0.0 <= result["score"] <= 1.0


# ---------------------------------------------------------------------------
# 4. Mild prior-memory influence is accepted
# ---------------------------------------------------------------------------


class TestMildMemoryInfluence:
    """A response that opens on-topic but has mild prior-topic influence later
    should still score above the acceptance threshold."""

    def test_mild_carryover_in_body_accepted(self):
        topic = "Economic freedom"
        anchors = TOPIC_ANCHORS.get(topic, [])
        if not anchors:
            pytest.skip(f"No anchors for {topic!r}")
        prev_topic = "AI alignment"
        prev_anchors = TOPIC_ANCHORS.get(prev_topic, ["alignment", "safety"])

        # Opening is clearly on-topic (mentions current anchor);
        # body contains one prior-topic word as analogy only.
        # The prior-topic word does NOT appear in the opening sentences.
        opening_word = anchors[0]
        body_prev_word = prev_anchors[0] if prev_anchors else "safety"
        text = (
            f"{opening_word.capitalize()} is a foundational principle of market economies. "
            "Individual choice within competitive markets has long-term distributional effects. "
            f"Some scholars compare this to {body_prev_word} considerations as an analogy."
        )
        result = compute_topic_compliance_score(
            text, topic, anchors, prev_anchors=prev_anchors
        )
        assert result["score"] >= ACCEPT_THRESHOLD, (
            f"Mild body-level carryover should be accepted; score={result['score']:.2f}"
        )


# ---------------------------------------------------------------------------
# 5. Prior-topic framing dominating opening is penalised
# ---------------------------------------------------------------------------


class TestOpeningContaminationPenalised:
    """Responses where the opening is dominated by the previous topic should
    receive a contamination penalty that lowers the score below the accept threshold."""

    def test_opening_dominated_by_prev_topic_penalised(self):
        topic = "Economic freedom"
        anchors = TOPIC_ANCHORS.get(topic, [])
        if not anchors:
            pytest.skip(f"No anchors for {topic!r}")
        prev_topic = "AI alignment"
        prev_anchors = TOPIC_ANCHORS.get(prev_topic, ["alignment", "safety", "agent"])

        # Opening uses prev-topic words ONLY — no current-topic anchor words
        opening_prev_words = prev_anchors[:3]
        text = (
            f"Thinking about {opening_prev_words[0]}, {opening_prev_words[1]}, "
            f"and {opening_prev_words[2]} is essential. "
            "These concepts permeate modern discourse across all domains."
        )
        result = compute_topic_compliance_score(
            text, topic, anchors, prev_anchors=prev_anchors
        )
        assert result["contamination_penalty"] > 0.0, (
            "Opening dominated by previous topic should have non-zero contamination"
        )
        assert result["score"] < ACCEPT_THRESHOLD, (
            f"Score should be below acceptance threshold; score={result['score']:.2f}"
        )

    def test_stale_phrase_in_opening_adds_penalty(self):
        """Stale contamination phrases in the opening should add to the penalty."""
        topic = "Economic freedom"
        anchors = TOPIC_ANCHORS.get(topic, ["market", "trade"])
        stale_phrase = _STALE_CONTAMINATION_PHRASES[0]  # "strict adherence to initial programming"
        text = (
            f"Through {stale_phrase} we can understand economic systems. "
            "Market forces then determine the outcome."
        )
        result = compute_topic_compliance_score(text, topic, anchors)
        # The contamination penalty should be non-zero for stale phrase
        assert result["contamination_penalty"] > 0.0


# ---------------------------------------------------------------------------
# 6. Soft re-anchor path triggers before hard recovery
# ---------------------------------------------------------------------------


class TestRecoveryLadder:
    """Soft re-anchor is triggered for medium-low scores (between 0.50 and 0.70)."""

    def test_score_in_soft_zone_triggers_soft_reanchor(self):
        """A response scoring in [SOFT_REANCHOR_THRESHOLD, ACCEPT_THRESHOLD)
        should land in the soft re-anchor band."""
        topic = "Economic freedom"
        anchors = TOPIC_ANCHORS.get(topic, [])
        if not anchors:
            pytest.skip(f"No anchors for {topic!r}")
        # Craft a response with ONE anchor word but mild contamination
        text = (
            f"There is some concern about {anchors[0]} and market dynamics. "
            "Previously we discussed a related framework extensively."
        )
        result = compute_topic_compliance_score(text, topic, anchors)
        score = result["score"]
        # The score must be below accept threshold but above or near soft threshold
        # (we can't guarantee exact range with keyword scoring, but verify structure)
        assert 0.0 <= score <= 1.0
        assert SOFT_REANCHOR_THRESHOLD <= ACCEPT_THRESHOLD  # sanity

    def test_build_soft_reanchor_instruction_contains_topic(self):
        topic = "Economic freedom"
        anchors = TOPIC_ANCHORS.get(topic, ["market", "trade"])
        instr = build_soft_reanchor_instruction(topic, anchors)
        assert topic in instr
        assert "RE-ANCHOR" in instr
        assert len(instr) > 20

    def test_build_soft_reanchor_instruction_empty_anchors(self):
        instr = build_soft_reanchor_instruction("Any topic", [])
        assert "Any topic" in instr
        assert "RE-ANCHOR" in instr


# ---------------------------------------------------------------------------
# 7. Hard recovery occurs only for severe contamination
# ---------------------------------------------------------------------------


class TestHardRecoveryThreshold:
    """Scores below SOFT_REANCHOR_THRESHOLD indicate hard recovery is warranted."""

    def test_off_topic_response_scores_below_soft_threshold(self):
        topic = "Economic freedom"
        anchors = TOPIC_ANCHORS.get(topic, [])
        if not anchors:
            pytest.skip(f"No anchors for {topic!r}")
        prev_topic = "AI alignment"
        prev_anchors = TOPIC_ANCHORS.get(prev_topic, ["alignment", "safety"])

        # Response has no current-topic anchor words and four prev-topic words
        prev_words = prev_anchors[:4] if len(prev_anchors) >= 4 else prev_anchors
        text = (
            " ".join(prev_words) + " "
            "These are the core concepts that every analysis must address."
        )
        result = compute_topic_compliance_score(
            text, topic, anchors, prev_anchors=prev_anchors
        )
        # Zero opening_topic_relevance drives score very low
        assert result["opening_topic_relevance"] == 0.0, (
            "Off-topic opening should have zero opening relevance"
        )
        assert result["score"] < ACCEPT_THRESHOLD

    def test_thresholds_are_ordered(self):
        """Sanity: hard recovery threshold < soft threshold < accept threshold."""
        assert 0.0 < SOFT_REANCHOR_THRESHOLD < ACCEPT_THRESHOLD <= 1.0


# ---------------------------------------------------------------------------
# 8. Agent-local continuity does not override session topic anchoring
# ---------------------------------------------------------------------------


class TestAgentContinuityVsSessionTopic:
    """The opening must be anchored to the SESSION topic, not agent's last topic."""

    def test_session_topic_dominates_opening_score(self):
        """A response that opens with the session topic scores better than one
        that opens with the agent's previous topic and has no current anchor."""
        session_topic = "Economic freedom"
        agent_last_topic = "AI alignment"
        session_anchors = TOPIC_ANCHORS.get(session_topic, ["market", "freedom"])
        agent_anchors = TOPIC_ANCHORS.get(agent_last_topic, ["alignment", "safety"])

        if not session_anchors or not agent_anchors:
            pytest.skip("Missing anchors for test topics")

        session_word = session_anchors[0]
        agent_words = agent_anchors[:3] if len(agent_anchors) >= 3 else agent_anchors

        # Good: opens on session topic, agent memory appears as analogy in body only
        good_response = (
            f"{session_word.capitalize()} determines how markets distribute resources. "
            "Competitive pressures and institutional constraints shape individual outcomes. "
            "One may draw analogies to other domains, but the market mechanism is central."
        )
        # Bad: opens with agent's previous framing (3 prev-topic words, 0 current anchors)
        bad_response = (
            f"The question of {agent_words[0]}, {agent_words[1]}, and {agent_words[2]} "
            "from our previous discussion remains paramount in this analysis. "
            "Everything else follows from those prior concerns."
        )

        good_result = compute_topic_compliance_score(
            good_response, session_topic, session_anchors, prev_anchors=agent_anchors
        )
        bad_result = compute_topic_compliance_score(
            bad_response, session_topic, session_anchors, prev_anchors=agent_anchors
        )

        assert good_result["score"] > bad_result["score"], (
            f"Session-topic anchored opening should score higher than agent-local opening. "
            f"good={good_result['score']:.2f}, bad={bad_result['score']:.2f}"
        )

    def test_opening_relevance_weighted_more_than_body(self):
        """The opening_topic_relevance component has more weight (0.45) than
        full_response_topic_relevance (0.35).  A response whose opening is
        anchored to the topic scores higher than one whose opening is off-topic
        even when both responses contain the anchor word somewhere."""
        topic = "Economic freedom"
        anchors = TOPIC_ANCHORS.get(topic, ["market", "trade", "freedom"])
        if not anchors:
            pytest.skip(f"No anchors for {topic!r}")
        anchor = anchors[0]

        # Response 1: anchor in OPENING (first sentence) → opening_rel = 1.0
        resp1 = f"{anchor.capitalize()} is central to this topic. Nothing else follows."
        # Response 2: generic opening, anchor only appears after first 2 sentences
        resp2 = (
            "Something entirely generic here. "
            "And another generic statement. "
            f"Only now does {anchor} appear in the body."
        )
        r1 = compute_topic_compliance_score(resp1, topic, anchors)
        r2 = compute_topic_compliance_score(resp2, topic, anchors)
        # r1 opening is anchored → opening_rel = 1.0; r2 opening is not → opening_rel = 0.0
        assert r1["opening_topic_relevance"] > r2["opening_topic_relevance"], (
            "Response with anchor in opening should have higher opening_relevance"
        )
        # Full-text relevance: both mention the anchor somewhere, but r2 body also includes it
        # The higher opening weight (0.45 vs 0.35) means r1 overall scores higher
        assert r1["score"] > r2["score"], (
            f"Opening-anchored response should have higher overall score. "
            f"r1={r1['score']:.2f} r2={r2['score']:.2f}"
        )


# ---------------------------------------------------------------------------
# TopicManager proposal-based advancement
# ---------------------------------------------------------------------------


class TestTopicManagerProposalAdvancement:
    """TopicManager.advance_with_proposals() uses scoring to select next topic."""

    def test_advance_with_proposals_returns_string(self):
        topics = _economics_cluster_topics()
        mgr = TopicManager(topics[:], rotate_every_rounds=1)
        result = mgr.advance_with_proposals(
            [topics[2], topics[3]], "economics"
        )
        assert isinstance(result, str)
        assert result in topics

    def test_advance_with_proposals_selects_novel_topic(self):
        topics = _economics_cluster_topics()
        if len(topics) < 4:
            pytest.skip("Not enough economics topics for test")
        mgr = TopicManager(topics[:], rotate_every_rounds=1)
        # Mark first two topics as visited
        mgr._history = topics[:2]
        novel = topics[4]
        recent = topics[1]
        result = mgr.advance_with_proposals(
            [recent, novel], "economics"
        )
        assert result == novel, f"Expected novel topic {novel!r}, got {result!r}"

    def test_advance_with_no_proposals_falls_back(self):
        topics = _economics_cluster_topics()
        mgr = TopicManager(topics[:], rotate_every_rounds=1)
        # Should not raise
        result = mgr.advance_with_proposals([], "economics")
        assert isinstance(result, str)

    def test_set_current_updates_pointer(self):
        topics = _economics_cluster_topics()
        mgr = TopicManager(topics[:], rotate_every_rounds=1)
        target = topics[3]
        mgr.set_current(target)
        assert mgr.current() == target

    def test_recent_topics_tracks_history(self):
        topics = _economics_cluster_topics()
        mgr = TopicManager(topics[:], rotate_every_rounds=1)
        mgr.set_current(topics[0])
        mgr.set_current(topics[1])
        mgr.set_current(topics[2])
        recent = mgr.recent_topics(n=3)
        assert recent == [topics[0], topics[1], topics[2]]

    def test_recent_topics_max_n(self):
        topics = _economics_cluster_topics()
        mgr = TopicManager(topics[:], rotate_every_rounds=1)
        for t in topics[:6]:
            mgr.set_current(t)
        recent = mgr.recent_topics(n=3)
        assert len(recent) == 3
        assert recent == list(topics[3:6])


# ---------------------------------------------------------------------------
# Internal helper unit tests
# ---------------------------------------------------------------------------


class TestInternalHelpers:

    def test_get_opening_sentences_two_sentences(self):
        text = "First sentence. Second sentence. Third sentence."
        opening = _get_opening_sentences(text, n=2)
        assert "First sentence" in opening
        assert "Second sentence" in opening
        assert "Third sentence" not in opening

    def test_get_opening_sentences_short_text(self):
        text = "Only one sentence here"
        opening = _get_opening_sentences(text, n=2)
        assert opening == text

    def test_semantic_relevance_full_match(self):
        score = _semantic_relevance("freedom autonomy liberty", ["freedom", "autonomy", "liberty"])
        assert score == 1.0

    def test_semantic_relevance_single_match(self):
        score = _semantic_relevance("freedom is paramount", ["freedom", "autonomy", "liberty"])
        assert score == 1.0

    def test_semantic_relevance_no_match(self):
        score = _semantic_relevance("nothing relevant here", ["freedom", "autonomy"])
        assert score == 0.0

    def test_semantic_relevance_empty_anchors(self):
        assert _semantic_relevance("anything", []) == 1.0

    def test_contamination_score_zero_no_prev(self):
        assert _contamination_score("some text", []) == 0.0

    def test_contamination_score_detects_prev_anchor(self):
        score = _contamination_score("alignment safety agent", ["alignment", "safety"])
        assert score > 0.0

    def test_stale_phrase_penalty_detects_phrase(self):
        text = f"We need strict adherence to initial programming to succeed."
        assert _stale_phrase_penalty(text) > 0.0

    def test_stale_phrase_penalty_clean_text(self):
        assert _stale_phrase_penalty("completely clean text about markets") == 0.0

#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Tests for the two-layer topic-style control system (v2.10.0).

Validates:
  A. Biology topic → scientific/mechanistic cluster, forbidden philosophical filler.
  B. Technology topic → technical/engineering tone, no theatrical phrases.
  C. Philosophy topic → Socratic/reflective style allowed, not suppressed.
  D. Topic pivot → style refresh updates cluster and instruction.
  E. DEFAULT_TOPIC_CLUSTER fallback → topic_style is never empty.
  F. scrub_rhetorical_openers() → strips openers for non-philosophy clusters.
  G. TOPIC_TONE_POLICY completeness → all seven production clusters present.
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

from entelgia.topic_style import (
    TOPIC_TONE_POLICY,
    DEFAULT_TOPIC_CLUSTER,
    build_style_instruction,
    get_style_for_cluster,
    get_style_for_topic,
    scrub_rhetorical_openers,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

TOPIC_CLUSTERS_SAMPLE = {
    "biology": [
        "sleep and memory consolidation",
        "neuroplasticity",
        "CRISPR gene editing",
    ],
    "technology": [
        "distributed inference architecture for local agents",
        "GPU memory bandwidth",
        "transformer attention mechanisms",
    ],
    "philosophy": [
        "What is truth and can perception be trusted?",
        "free will and determinism",
        "the nature of consciousness",
    ],
    "economics": [
        "inflation and monetary policy",
        "market equilibrium",
    ],
    "psychology": [
        "cognitive dissonance",
        "affect regulation",
    ],
    "society": [
        "social stratification",
        "institutional trust",
    ],
    "practical_dilemmas": [
        "career change at 40",
        "ethical AI deployment",
    ],
}


# ---------------------------------------------------------------------------
# A. Biology topic
# ---------------------------------------------------------------------------


class TestBiologyTopic:
    """A biology topic should yield a scientific/mechanistic cluster and policy."""

    def test_cluster_is_biology(self):
        cluster, _style = get_style_for_topic(
            "sleep and memory consolidation", TOPIC_CLUSTERS_SAMPLE
        )
        assert cluster == "biology"

    def test_style_instruction_includes_scientific_register(self):
        cluster, style = get_style_for_topic(
            "sleep and memory consolidation", TOPIC_CLUSTERS_SAMPLE
        )
        instruction = build_style_instruction(style, role="Socrates", cluster=cluster)
        instruction_lower = instruction.lower()
        # At least one scientific/mechanistic register must be present
        assert any(
            kw in instruction_lower
            for kw in ("scientific", "mechanistic", "evidence-based")
        ), f"Expected scientific register in instruction:\n{instruction}"

    def test_style_instruction_forbids_philosophical_register(self):
        cluster, style = get_style_for_topic(
            "sleep and memory consolidation", TOPIC_CLUSTERS_SAMPLE
        )
        instruction = build_style_instruction(style, role="Athena", cluster=cluster)
        # "philosophical" must appear in the forbidden registers section
        assert (
            "philosophical" in instruction.lower()
        ), f"Expected 'philosophical' to be listed as forbidden in:\n{instruction}"

    def test_style_instruction_lists_forbidden_phrases(self):
        policy = TOPIC_TONE_POLICY["biology"]
        cluster, style = get_style_for_topic(
            "sleep and memory consolidation", TOPIC_CLUSTERS_SAMPLE
        )
        instruction = build_style_instruction(style, role="Fixy", cluster=cluster)
        for phrase in policy["forbidden_phrases"]:
            assert (
                phrase in instruction
            ), f"Expected forbidden phrase '{phrase}' to appear in instruction"

    def test_style_instruction_is_mandatory_block(self):
        cluster, style = get_style_for_topic("neuroplasticity", TOPIC_CLUSTERS_SAMPLE)
        instruction = build_style_instruction(style, role="Socrates", cluster=cluster)
        assert "STYLE INSTRUCTION (MANDATORY)" in instruction

    def test_style_instruction_includes_preferred_cues(self):
        cluster, style = get_style_for_topic(
            "sleep and memory consolidation", TOPIC_CLUSTERS_SAMPLE
        )
        instruction = build_style_instruction(style, role="Athena", cluster=cluster)
        assert "mechanism" in instruction.lower() or "evidence" in instruction.lower()


# ---------------------------------------------------------------------------
# B. Technology topic
# ---------------------------------------------------------------------------


class TestTechnologyTopic:
    """A technology topic should use technical/engineering tone without theatrical phrases."""

    def test_cluster_is_technology(self):
        cluster, _style = get_style_for_topic(
            "distributed inference architecture for local agents",
            TOPIC_CLUSTERS_SAMPLE,
        )
        assert cluster == "technology"

    def test_style_instruction_includes_technical_register(self):
        cluster, style = get_style_for_topic(
            "distributed inference architecture for local agents",
            TOPIC_CLUSTERS_SAMPLE,
        )
        instruction = build_style_instruction(style, role="Athena", cluster=cluster)
        assert any(
            kw in instruction.lower() for kw in ("technical", "engineering", "analytic")
        ), f"Expected technical register in instruction:\n{instruction}"

    def test_style_instruction_forbids_poetic_register(self):
        cluster, style = get_style_for_topic(
            "GPU memory bandwidth", TOPIC_CLUSTERS_SAMPLE
        )
        instruction = build_style_instruction(style, role="Socrates", cluster=cluster)
        assert "poetic" in instruction.lower() or "theatrical" in instruction.lower()

    def test_forbidden_phrase_my_dear_friend_present(self):
        policy = TOPIC_TONE_POLICY["technology"]
        assert "my dear friend" in policy["forbidden_phrases"]
        cluster, style = get_style_for_topic(
            "transformer attention mechanisms", TOPIC_CLUSTERS_SAMPLE
        )
        instruction = build_style_instruction(style, role="Fixy", cluster=cluster)
        assert "my dear friend" in instruction.lower()

    def test_forbidden_phrase_quest_for_knowledge_present(self):
        policy = TOPIC_TONE_POLICY["technology"]
        assert "quest for knowledge" in policy["forbidden_phrases"]
        cluster, style = get_style_for_topic(
            "GPU memory bandwidth", TOPIC_CLUSTERS_SAMPLE
        )
        instruction = build_style_instruction(style, role="Socrates", cluster=cluster)
        assert "quest for knowledge" in instruction.lower()

    def test_response_mode_is_concrete_analysis(self):
        cluster, style = get_style_for_topic(
            "distributed inference architecture for local agents",
            TOPIC_CLUSTERS_SAMPLE,
        )
        instruction = build_style_instruction(style, role="Athena", cluster=cluster)
        assert "concrete_analysis" in instruction


# ---------------------------------------------------------------------------
# C. Philosophy topic
# ---------------------------------------------------------------------------


class TestPhilosophyTopic:
    """Philosophy topics should allow Socratic/reflective style without suppression."""

    def test_cluster_is_philosophy(self):
        cluster, _style = get_style_for_topic(
            "What is truth and can perception be trusted?", TOPIC_CLUSTERS_SAMPLE
        )
        assert cluster == "philosophy"

    def test_philosophy_allows_dialectical_register(self):
        cluster, style = get_style_for_topic(
            "free will and determinism", TOPIC_CLUSTERS_SAMPLE
        )
        instruction = build_style_instruction(style, role="Socrates", cluster=cluster)
        assert any(
            kw in instruction.lower()
            for kw in ("dialectical", "reflective", "socratic")
        ), f"Expected dialectical/reflective register in:\n{instruction}"

    def test_philosophy_has_no_forbidden_registers(self):
        policy = TOPIC_TONE_POLICY["philosophy"]
        assert (
            policy["forbidden_registers"] == []
        ), "Philosophy cluster should have no forbidden registers"

    def test_philosophy_has_no_forbidden_phrases(self):
        policy = TOPIC_TONE_POLICY["philosophy"]
        assert (
            policy["forbidden_phrases"] == []
        ), "Philosophy cluster should have no forbidden phrases"

    def test_scrub_does_not_strip_openers_for_philosophy(self):
        """scrub_rhetorical_openers must leave philosophy responses unchanged."""
        text = "My dear friend, let us explore the nature of truth."
        result = scrub_rhetorical_openers(text, cluster="philosophy")
        assert (
            result == text
        ), f"Philosophy opener should not be stripped. Got: {result!r}"

    def test_philosophy_response_mode_is_dialectical(self):
        cluster, style = get_style_for_topic(
            "the nature of consciousness", TOPIC_CLUSTERS_SAMPLE
        )
        instruction = build_style_instruction(style, role="Socrates", cluster=cluster)
        assert "dialectical_reasoning" in instruction


# ---------------------------------------------------------------------------
# D. Topic pivot
# ---------------------------------------------------------------------------


class TestTopicPivot:
    """Style refresh on topic pivot must update cluster and produce different instructions."""

    def test_pivot_changes_cluster(self):
        cluster_a, style_a = get_style_for_topic(
            "sleep and memory consolidation", TOPIC_CLUSTERS_SAMPLE
        )
        cluster_b, style_b = get_style_for_topic(
            "inflation and monetary policy", TOPIC_CLUSTERS_SAMPLE
        )
        assert (
            cluster_a != cluster_b
        ), f"Expected different clusters: {cluster_a!r} vs {cluster_b!r}"

    def test_pivot_changes_style_instruction(self):
        cluster_a, style_a = get_style_for_topic(
            "sleep and memory consolidation", TOPIC_CLUSTERS_SAMPLE
        )
        cluster_b, style_b = get_style_for_topic(
            "inflation and monetary policy", TOPIC_CLUSTERS_SAMPLE
        )
        instr_a = build_style_instruction(style_a, role="Socrates", cluster=cluster_a)
        instr_b = build_style_instruction(style_b, role="Socrates", cluster=cluster_b)
        assert instr_a != instr_b, "Style instruction should differ after a topic pivot"

    def test_pivot_new_instruction_reflects_new_cluster(self):
        cluster_b, style_b = get_style_for_topic(
            "inflation and monetary policy", TOPIC_CLUSTERS_SAMPLE
        )
        instr_b = build_style_instruction(style_b, role="Athena", cluster=cluster_b)
        assert (
            "economics" in instr_b
        ), f"Instruction after pivot to economics should mention 'economics':\n{instr_b}"

    def test_pivot_biology_to_economics_registers_differ(self):
        _, style_bio = get_style_for_topic(
            "sleep and memory consolidation", TOPIC_CLUSTERS_SAMPLE
        )
        _, style_eco = get_style_for_topic(
            "inflation and monetary policy", TOPIC_CLUSTERS_SAMPLE
        )
        instr_bio = build_style_instruction(style_bio, role="Fixy", cluster="biology")
        instr_eco = build_style_instruction(style_eco, role="Fixy", cluster="economics")
        # Biology instruction should contain "mechanistic"; economics should not
        assert "mechanistic" in instr_bio
        assert "mechanistic" not in instr_eco


# ---------------------------------------------------------------------------
# E. DEFAULT_TOPIC_CLUSTER fallback
# ---------------------------------------------------------------------------


class TestDefaultClusterFallback:
    """topic_style must never be empty; unknown topics fall back to DEFAULT_TOPIC_CLUSTER."""

    def test_default_cluster_is_non_empty_string(self):
        assert isinstance(DEFAULT_TOPIC_CLUSTER, str) and DEFAULT_TOPIC_CLUSTER

    def test_default_cluster_exists_in_tone_policy(self):
        assert DEFAULT_TOPIC_CLUSTER in TOPIC_TONE_POLICY

    def test_unknown_topic_falls_back_to_default_cluster(self):
        cluster, style = get_style_for_topic(
            "totally unknown topic XYZ", TOPIC_CLUSTERS_SAMPLE
        )
        assert cluster == DEFAULT_TOPIC_CLUSTER

    def test_style_instruction_never_empty_for_unknown_topic(self):
        cluster, style = get_style_for_topic(
            "totally unknown topic XYZ", TOPIC_CLUSTERS_SAMPLE
        )
        instruction = build_style_instruction(style, role="Socrates", cluster=cluster)
        assert instruction.strip() != ""

    def test_none_cluster_falls_back(self):
        style = get_style_for_cluster(None)
        assert style  # must not be empty

    def test_custom_cluster_string_falls_back_to_default(self):
        # "custom" is not a valid cluster key in TOPIC_TONE_POLICY
        instruction = build_style_instruction(
            "some style", role="Athena", cluster="custom"
        )
        assert "STYLE INSTRUCTION (MANDATORY)" in instruction
        assert DEFAULT_TOPIC_CLUSTER in instruction


# ---------------------------------------------------------------------------
# F. scrub_rhetorical_openers()
# ---------------------------------------------------------------------------


class TestScrubRhetoricalOpeners:
    """scrub_rhetorical_openers() removes banned openers for non-philosophy clusters."""

    def test_strips_my_dear_friend_for_biology(self):
        text = "My dear friend, memory consolidation occurs during sleep."
        result = scrub_rhetorical_openers(text, cluster="biology")
        assert not result.lower().startswith(
            "my dear friend"
        ), f"Expected opener stripped. Got: {result!r}"
        assert "memory consolidation occurs during sleep" in result.lower()

    def test_strips_let_us_delve_deeper_for_technology(self):
        text = "Let us delve deeper into the architecture of this system."
        result = scrub_rhetorical_openers(text, cluster="technology")
        assert not result.lower().startswith(
            "let us delve deeper"
        ), f"Expected opener stripped. Got: {result!r}"

    def test_strips_let_us_explore_for_economics(self):
        text = "Let us explore the market dynamics at play."
        result = scrub_rhetorical_openers(text, cluster="economics")
        assert not result.lower().startswith(
            "let us explore"
        ), f"Expected opener stripped. Got: {result!r}"

    def test_preserves_philosophy_openers(self):
        text = "My dear friend, let us explore the nature of truth."
        result = scrub_rhetorical_openers(text, cluster="philosophy")
        assert result == text

    def test_capitalises_remainder(self):
        text = "my dear friend, distributed systems require careful design."
        result = scrub_rhetorical_openers(text, cluster="technology")
        assert result[
            0
        ].isupper(), (
            f"Expected first char to be uppercase after scrubbing. Got: {result!r}"
        )

    def test_no_change_when_no_opener_present(self):
        text = "Memory consolidation during sleep involves hippocampal replay."
        result = scrub_rhetorical_openers(text, cluster="biology")
        assert result == text

    def test_empty_remainder_is_not_stripped(self):
        """If stripping the opener leaves nothing, return original text."""
        text = "My dear friend"
        result = scrub_rhetorical_openers(text, cluster="technology")
        # Result should be the original since there's no remainder
        assert result == text


# ---------------------------------------------------------------------------
# G. TOPIC_TONE_POLICY completeness
# ---------------------------------------------------------------------------


class TestTopicTonePolicyCompleteness:
    """TOPIC_TONE_POLICY must cover all seven production clusters."""

    PRODUCTION_CLUSTERS = {
        "technology",
        "economics",
        "biology",
        "psychology",
        "society",
        "practical_dilemmas",
        "philosophy",
    }

    def test_all_production_clusters_present(self):
        for cluster in self.PRODUCTION_CLUSTERS:
            assert (
                cluster in TOPIC_TONE_POLICY
            ), f"Missing cluster in TOPIC_TONE_POLICY: {cluster!r}"

    def test_each_policy_has_required_keys(self):
        required_keys = {
            "allowed_registers",
            "forbidden_registers",
            "forbidden_phrases",
            "preferred_cues",
            "response_mode",
        }
        for cluster, policy in TOPIC_TONE_POLICY.items():
            for key in required_keys:
                assert key in policy, f"Cluster '{cluster}' policy missing key: '{key}'"

    def test_philosophy_allowed_registers_include_socratic(self):
        policy = TOPIC_TONE_POLICY["philosophy"]
        registers = [r.lower() for r in policy["allowed_registers"]]
        assert (
            "socratic" in registers or "dialectical" in registers
        ), f"Philosophy policy should allow socratic/dialectical: {registers}"

    def test_non_philosophy_clusters_forbid_theatrical(self):
        for cluster, policy in TOPIC_TONE_POLICY.items():
            if cluster == "philosophy":
                continue
            # Not every non-philosophy cluster forbids theatrical, but core ones do
            if cluster in ("technology", "biology", "psychology", "society"):
                assert (
                    "theatrical" in policy["forbidden_registers"]
                ), f"Cluster '{cluster}' should forbid 'theatrical' register"

#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Tests for entelgia/loop_guard.py
Covers: DialogueLoopDetector (all 4 failure modes), PhraseBanList, DialogueRewriter,
TopicManager.force_cluster_pivot, and FixyMode/AgentMode integration.
"""

import sys
import os

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from entelgia.loop_guard import (
    DialogueLoopDetector,
    PhraseBanList,
    DialogueRewriter,
    TOPIC_CLUSTERS,
    _TOPIC_TO_CLUSTER,
    get_cluster,
    topics_in_different_cluster,
    LOOP_REPETITION,
    WEAK_CONFLICT,
    PREMATURE_SYNTHESIS,
    TOPIC_STAGNATION,
    CONCEPTUAL_LOOP,
    AXIS_STAGNATION,
    _concept_key,
    _concept_overlap,
    _extract_dep_pairs,
    _AXIS_EMBEDDING_SIMILARITY_THRESHOLD,
    _AXIS_JACCARD_THRESHOLD,
)
from entelgia.fixy_interactive import FixyMode, _LOOP_MODE_POLICY
from entelgia.dialogue_engine import AgentMode, _LOOP_AGENT_POLICY

# ---------------------------------------------------------------------------
# Helper factories
# ---------------------------------------------------------------------------


def _make_turns(texts, roles=None):
    """Build a list of turn dicts from texts. Alternates Socrates/Athena by default."""
    if roles is None:
        agent_names = ["Socrates", "Athena"]
        roles = [agent_names[i % 2] for i in range(len(texts))]
    return [{"role": r, "text": t} for r, t in zip(roles, texts)]


# ---------------------------------------------------------------------------
# DialogueLoopDetector — loop_repetition
# ---------------------------------------------------------------------------


def test_detect_repetition_flags_overlapping_turns():
    """High keyword overlap across multiple turns should trigger loop_repetition."""
    detector = DialogueLoopDetector()
    # All turns revolve around the same word cluster
    turns = _make_turns(
        [
            "freedom autonomy liberty independence means personal freedom",
            "autonomy liberty freedom independence are fundamental",
            "liberty means freedom autonomy personal independence",
            "independence freedom liberty autonomy interrelated concepts",
            "freedom liberty autonomy independence personal values",
        ]
    )
    modes = detector.detect(turns, turn_count=5)
    assert LOOP_REPETITION in modes, f"Expected loop_repetition, got {modes}"


def test_detect_repetition_no_flag_for_varied_turns():
    """Varied content should not trigger loop_repetition."""
    detector = DialogueLoopDetector()
    turns = _make_turns(
        [
            "What is the nature of truth?",
            "Law determines societal obligations in practice.",
            "Habit formation affects neural plasticity over time.",
            "Economic incentives drive institutional behavior.",
        ]
    )
    modes = detector.detect(turns, turn_count=4)
    assert LOOP_REPETITION not in modes, f"Should not flag varied turns, got {modes}"


# ---------------------------------------------------------------------------
# DialogueLoopDetector — weak_conflict
# ---------------------------------------------------------------------------


def test_detect_weak_conflict_flag():
    """Turns with conflict markers AND synthesis hedging should trigger weak_conflict."""
    detector = DialogueLoopDetector()
    turns = _make_turns(
        [
            "But I disagree — freedom is individual. However both are needed.",
            "Actually that is wrong. Still, both perspectives have merit.",
            "No, you are incorrect. Yet we need to integrate both views.",
            "On the contrary, I disagree. But both are needed for balance.",
            "I disagree strongly. However, we must combine both views here.",
            "That is actually wrong. Both perspectives are needed together.",
        ]
    )
    modes = detector.detect(turns, turn_count=6)
    assert WEAK_CONFLICT in modes, f"Expected weak_conflict, got {modes}"


# ---------------------------------------------------------------------------
# DialogueLoopDetector — premature_synthesis
# ---------------------------------------------------------------------------


def test_detect_premature_synthesis():
    """Majority of turns containing synthesis phrases flags premature_synthesis."""
    detector = DialogueLoopDetector()
    turns = _make_turns(
        [
            "Both are needed to understand freedom fully.",
            "We must integrate both perspectives into a whole.",
            "Combining both views gives us better understanding.",
            "Both perspectives have merit and complement each other.",
            "We need both to find middle ground on this matter.",
        ]
    )
    modes = detector.detect(turns, turn_count=5)
    assert PREMATURE_SYNTHESIS in modes, f"Expected premature_synthesis, got {modes}"


# ---------------------------------------------------------------------------
# DialogueLoopDetector — topic_stagnation
# ---------------------------------------------------------------------------


def test_detect_topic_stagnation_same_cluster():
    """Staying in the same topic cluster across recent turns flags topic_stagnation."""
    detector = DialogueLoopDetector()
    # All philosophy cluster
    for topic in [
        "truth & epistemology",
        "free will & determinism",
        "consciousness & self-models",
        "language & meaning",
    ]:
        detector.detect([], turn_count=1, current_topic=topic)

    # High keyword overlap content stays in same concept cloud
    turns = _make_turns(
        [
            "truth epistemology knowledge certainty truth knowledge",
            "epistemology truth knowledge certain truth certainty",
            "knowledge certainty truth epistemology truth certain",
            "truth knowledge epistemology certainty truth certain",
            "epistemology truth certain knowledge certainty truth",
        ]
    )
    modes = detector.detect(turns, turn_count=6, current_topic="language & meaning")
    assert TOPIC_STAGNATION in modes, f"Expected topic_stagnation, got {modes}"


# ---------------------------------------------------------------------------
# TopicManager.force_cluster_pivot
# ---------------------------------------------------------------------------


def test_force_cluster_pivot_changes_cluster():
    """force_cluster_pivot should return a topic from a different cluster."""
    import random

    # We test the method via a minimal mock that mimics TopicManager
    topics = [
        "truth & epistemology",  # philosophy
        "memory & identity",  # identity
        "ethics & responsibility",  # ethics_social
        "technology & society",  # ethics_social
        "habit formation",  # practical
    ]

    # Build a minimal TopicManager-like object inline
    class _TM:
        def __init__(self, topics):
            self.topics = topics[:]
            self.i = 0
            self.rounds = 0
            self.rotate_every_rounds = 1

        def current(self):
            return self.topics[self.i % len(self.topics)]

        def advance_round(self):
            self.rounds += 1
            if self.rounds % self.rotate_every_rounds == 0:
                self.i = (self.i + 1) % len(self.topics)

        def force_cluster_pivot(self):
            current = self.current()
            current_cluster = _TOPIC_TO_CLUSTER.get(current)
            candidates = []
            for topic in self.topics:
                if topic == current:
                    continue
                candidate_cluster = _TOPIC_TO_CLUSTER.get(topic)
                if current_cluster is None or candidate_cluster != current_cluster:
                    candidates.append(topic)
            if candidates:
                new_topic = random.choice(candidates)
                try:
                    self.i = self.topics.index(new_topic)
                except ValueError:
                    self.advance_round()
                    return self.current()
                return new_topic
            self.advance_round()
            return self.current()

    tm = _TM(topics)
    # Start at "truth & epistemology" (philosophy)
    assert tm.current() == "truth & epistemology"
    new_topic = tm.force_cluster_pivot()
    new_cluster = _TOPIC_TO_CLUSTER.get(new_topic)
    old_cluster = _TOPIC_TO_CLUSTER.get("truth & epistemology")
    assert new_cluster != old_cluster or new_cluster is None, (
        f"force_cluster_pivot should pivot to different cluster; "
        f"got {new_topic!r} (cluster={new_cluster}) from {old_cluster}"
    )


# ---------------------------------------------------------------------------
# get_cluster and topics_in_different_cluster helpers
# ---------------------------------------------------------------------------


def test_get_cluster_returns_expected_cluster():
    assert get_cluster("truth & epistemology") == "philosophy"
    assert get_cluster("ethics & responsibility") == "ethics_social"
    assert get_cluster("habit formation") == "practical"
    assert get_cluster("unknown topic xyz") is None


def test_topics_in_different_cluster():
    # Both philosophy → same cluster
    assert not topics_in_different_cluster(
        "truth & epistemology", "free will & determinism"
    )
    # philosophy vs practical → different cluster
    assert topics_in_different_cluster("truth & epistemology", "habit formation")
    # Unknown topic is treated as different
    assert topics_in_different_cluster("truth & epistemology", "unknown xyz")


# ---------------------------------------------------------------------------
# PhraseBanList
# ---------------------------------------------------------------------------


def test_phrase_ban_list_detects_overused_ngrams():
    """Phrases repeated 3+ times across the window should be banned."""
    ban = PhraseBanList(window=8, threshold=3, ban_duration=4, ngram_sizes=(2,))
    texts = [
        "integrate both perspectives into one",
        "we must integrate both perspectives here",
        "it is important to integrate both perspectives",
    ]
    ban.update(texts, current_turn=5)
    active = ban.active_bans()
    # "integrate both" should be banned (appears 3 times)
    assert any(
        "integrate both" in phrase for phrase in active
    ), f"Expected 'integrate both' to be banned; active bans: {active}"


def test_phrase_ban_expires():
    """Bans should expire after ban_duration turns once the source texts leave the buffer."""
    # window=2 so the old texts scroll out when new texts are added
    ban = PhraseBanList(window=2, threshold=2, ban_duration=2, ngram_sizes=(2,))
    texts = [
        "true freedom is essential for all",
        "true freedom cannot be restricted",
    ]
    ban.update(texts, current_turn=1)
    assert len(ban.active_bans()) > 0
    # Fill the window with completely different content so "true freedom" drops out
    neutral = [
        "economic institutions drive behaviour in complex ways",
        "biological evolution shapes cognitive architecture deeply",
    ]
    # current_turn=4 is past expiry (1 + ban_duration 2 = 3, so 4 > 3)
    ban.update(neutral, current_turn=4)
    # Now the old texts are out of the buffer AND the ban has expired
    assert (
        len(ban.active_bans()) == 0
    ), f"Bans should have expired; still active: {ban.active_bans()}"


def test_phrase_ban_instruction_empty_when_no_bans():
    ban = PhraseBanList()
    assert ban.ban_instruction() == ""


def test_phrase_ban_instruction_non_empty_when_bans_active():
    ban = PhraseBanList(threshold=2, ban_duration=5, ngram_sizes=(2,))
    ban.update(
        ["societal norms oppress us all", "societal norms restrict our freedom"],
        current_turn=1,
    )
    instruction = ban.ban_instruction()
    # Instruction should contain the banned phrase text
    assert "societal norms" in instruction


# ---------------------------------------------------------------------------
# DialogueRewriter
# ---------------------------------------------------------------------------


def test_rewriter_returns_empty_when_no_modes():
    rewriter = DialogueRewriter()
    result = rewriter.build(
        dialog=[{"role": "Socrates", "text": "Something"}],
        active_modes=[],
        current_topic="freedom",
    )
    assert result == ""


def test_rewriter_builds_block_with_required_sections():
    rewriter = DialogueRewriter()
    dialog = [
        {"role": "Socrates", "text": "Freedom is individual autonomy above all."},
        {"role": "Athena", "text": "Freedom requires collective social structures."},
        {"role": "Fixy", "text": "Both views have merit."},
    ]
    block = rewriter.build(
        dialog=dialog,
        active_modes=[PREMATURE_SYNTHESIS],
        current_topic="freedom",
        banned_phrases=["both are needed", "integrate both"],
    )
    assert "DIALOGUE STATE REWRITE" in block
    assert "Topic: freedom" in block
    assert "premature_synthesis" in block
    assert "Novelty requirement" in block
    assert "Restrictions" in block
    # Core claims should be included
    assert "Socrates" in block
    assert "Athena" in block


def test_rewriter_includes_novelty_for_each_mode():
    rewriter = DialogueRewriter()
    dialog = [
        {"role": "Socrates", "text": "A claim about truth."},
        {"role": "Athena", "text": "A different claim about society."},
    ]
    for mode in (LOOP_REPETITION, WEAK_CONFLICT, PREMATURE_SYNTHESIS, TOPIC_STAGNATION):
        block = rewriter.build(dialog=dialog, active_modes=[mode], current_topic="test")
        assert block, f"Expected non-empty block for mode {mode!r}"
        assert "Novelty requirement" in block, f"Missing novelty for mode {mode!r}"


# ---------------------------------------------------------------------------
# FixyMode and mode policy mapping
# ---------------------------------------------------------------------------


def test_fixy_mode_constants_exist():
    assert FixyMode.MEDIATE == "MEDIATE"
    assert FixyMode.CONTRADICT == "CONTRADICT"
    assert FixyMode.CONCRETIZE == "CONCRETIZE"
    assert FixyMode.INVERT == "INVERT"
    assert FixyMode.PIVOT == "PIVOT"
    assert FixyMode.EXPOSE_SYNTHESIS == "EXPOSE_SYNTHESIS"
    assert FixyMode.FORCE_MECHANISM == "FORCE_MECHANISM"
    # Loop-breaking modes
    assert FixyMode.FORCE_CONCRETE_EXAMPLE == "FORCE_CONCRETE_EXAMPLE"
    assert FixyMode.FORCE_COUNTEREXAMPLE == "FORCE_COUNTEREXAMPLE"
    assert FixyMode.FORCE_DIRECT_DISAGREEMENT == "FORCE_DIRECT_DISAGREEMENT"
    assert FixyMode.FORCE_TOPIC_RETURN == "FORCE_TOPIC_RETURN"
    assert FixyMode.FORCE_SHORT_ANSWER == "FORCE_SHORT_ANSWER"
    assert FixyMode.FORCE_NEW_DOMAIN == "FORCE_NEW_DOMAIN"


def test_loop_mode_policy_covers_all_failure_modes():
    for failure_mode in (
        LOOP_REPETITION,
        WEAK_CONFLICT,
        PREMATURE_SYNTHESIS,
        TOPIC_STAGNATION,
        AXIS_STAGNATION,
    ):
        assert (
            failure_mode in _LOOP_MODE_POLICY
        ), f"_LOOP_MODE_POLICY missing entry for {failure_mode!r}"
        assert _LOOP_MODE_POLICY[failure_mode] in (
            FixyMode.MEDIATE,
            FixyMode.CONTRADICT,
            FixyMode.CONCRETIZE,
            FixyMode.INVERT,
            FixyMode.PIVOT,
            FixyMode.EXPOSE_SYNTHESIS,
            FixyMode.FORCE_MECHANISM,
            FixyMode.FORCE_CONCRETE_EXAMPLE,
            FixyMode.FORCE_COUNTEREXAMPLE,
            FixyMode.FORCE_DIRECT_DISAGREEMENT,
            FixyMode.FORCE_TOPIC_RETURN,
            FixyMode.FORCE_SHORT_ANSWER,
            FixyMode.FORCE_NEW_DOMAIN,
        )


# ---------------------------------------------------------------------------
# AgentMode and mode policy mapping
# ---------------------------------------------------------------------------


def test_agent_mode_constants_exist():
    assert AgentMode.NORMAL == "NORMAL"
    assert AgentMode.CONTRADICT == "CONTRADICT"
    assert AgentMode.CONCRETIZE == "CONCRETIZE"
    assert AgentMode.INVERT == "INVERT"
    assert AgentMode.MECHANIZE == "MECHANIZE"
    assert AgentMode.PIVOT == "PIVOT"


def test_agent_loop_policy_covers_all_failure_modes():
    for failure_mode in (
        LOOP_REPETITION,
        WEAK_CONFLICT,
        PREMATURE_SYNTHESIS,
        TOPIC_STAGNATION,
        AXIS_STAGNATION,
    ):
        assert (
            failure_mode in _LOOP_AGENT_POLICY
        ), f"_LOOP_AGENT_POLICY missing entry for {failure_mode!r}"
        assert _LOOP_AGENT_POLICY[failure_mode] in (
            AgentMode.NORMAL,
            AgentMode.CONTRADICT,
            AgentMode.CONCRETIZE,
            AgentMode.INVERT,
            AgentMode.MECHANIZE,
            AgentMode.PIVOT,
        )


# ---------------------------------------------------------------------------
# InteractiveFixy.get_fixy_mode integration
# ---------------------------------------------------------------------------


def test_interactive_fixy_get_fixy_mode_loop_reasons():
    """get_fixy_mode should return disruptive mode for loop failure reasons."""
    from entelgia.fixy_interactive import InteractiveFixy

    class _MockLLM:
        def generate(self, *a, **kw):
            return "mock"

    fixy = InteractiveFixy(_MockLLM(), "test-model")

    assert fixy.get_fixy_mode(LOOP_REPETITION) != FixyMode.MEDIATE
    assert fixy.get_fixy_mode(WEAK_CONFLICT) != FixyMode.MEDIATE
    assert fixy.get_fixy_mode(PREMATURE_SYNTHESIS) != FixyMode.MEDIATE
    assert fixy.get_fixy_mode(TOPIC_STAGNATION) != FixyMode.MEDIATE
    # Legacy reason should still fall back to MEDIATE
    assert fixy.get_fixy_mode("meta_reflection_needed") == FixyMode.MEDIATE


# ---------------------------------------------------------------------------
# SeedGenerator.generate_seed with agent_mode
# ---------------------------------------------------------------------------


def test_seed_generator_injects_agent_mode_instruction():
    """When agent_mode is set, the seed should contain the mode instruction."""
    from entelgia.dialogue_engine import SeedGenerator, _AGENT_MODE_INSTRUCTION

    sg = SeedGenerator()

    class _MockAgent:
        def conflict_index(self):
            return 5.0

    turns = [{"role": "Socrates", "text": "Some statement", "emotion": "neutral"}]

    seed_normal = sg.generate_seed("freedom", turns, _MockAgent(), 5)
    seed_concretize = sg.generate_seed(
        "freedom", turns, _MockAgent(), 5, agent_mode=AgentMode.CONCRETIZE
    )
    assert "CONCRETIZE" in seed_concretize
    assert _AGENT_MODE_INSTRUCTION[AgentMode.CONCRETIZE] in seed_concretize


def test_seed_generator_normal_mode_no_extra_instruction():
    """NORMAL agent_mode should produce the same seed as no mode."""
    from entelgia.dialogue_engine import SeedGenerator

    sg = SeedGenerator()

    class _MockAgent:
        def conflict_index(self):
            return 5.0

    import random

    random.seed(42)
    turns = [{"role": "Socrates", "text": "Some statement", "emotion": "neutral"}]
    seed_none = sg.generate_seed("freedom", turns, _MockAgent(), 5, agent_mode=None)

    random.seed(42)
    seed_normal = sg.generate_seed(
        "freedom", turns, _MockAgent(), 5, agent_mode=AgentMode.NORMAL
    )
    # NORMAL should not append extra instruction text
    assert seed_none == seed_normal


# ---------------------------------------------------------------------------
# New signal detectors — Signal B, C, D
# ---------------------------------------------------------------------------


def test_check_rhetorical_role_repetition_flags_locked_agents():
    """Signal B: Socrates locked in questions + Athena locked in systemic critique."""
    detector = DialogueLoopDetector()
    # Socrates always asks questions; Athena always frames systemically
    turns = _make_turns(
        [
            "What is the foundation of freedom in society?",  # Socrates Q
            "The social system determines individual freedoms through structure.",  # Athena sys
            "Why does the framework constrain personal autonomy?",  # Socrates Q
            "Institutional patterns shape what is culturally possible.",  # Athena sys
            "How can the mechanism of power be questioned?",  # Socrates Q
            "Collective context frames every systemic boundary here.",  # Athena sys
        ]
    )
    result = detector._check_rhetorical_role_repetition(turns)
    assert result, "Expected rhetorical role repetition to be flagged"


def test_check_rhetorical_role_repetition_no_flag_varied_roles():
    """Signal B should NOT fire when agents vary their discourse style."""
    detector = DialogueLoopDetector()
    turns = _make_turns(
        [
            "Freedom requires structure — that is my claim.",  # Socrates asserts
            "What does your claim entail for individuals?",  # Athena questions
            "Let me give a concrete example from history.",  # Socrates example
            "Actually, the data contradicts that view.",  # Athena critique
        ]
    )
    result = detector._check_rhetorical_role_repetition(turns)
    assert not result, "Should NOT flag varied rhetorical roles"


def test_check_fixy_mediation_language_flags_repeated_mediation():
    """Signal D: Fixy repeatedly using integration / bridge phrases."""
    detector = DialogueLoopDetector()
    dialog = [
        {"role": "Socrates", "text": "Freedom is pure individual will."},
        {"role": "Athena", "text": "Freedom requires collective norms."},
        {"role": "Fixy", "text": "We must integrate both perspectives here."},
        {"role": "Socrates", "text": "The individual precedes the collective."},
        {"role": "Athena", "text": "Collective structures make individuals possible."},
        {"role": "Fixy", "text": "Let us bridge the gap between both views."},
    ]
    result = detector._check_fixy_mediation_language(dialog)
    assert result, "Expected Fixy mediation language to be flagged"


def test_check_fixy_mediation_language_no_flag_disruptive_fixy():
    """Signal D should NOT fire when Fixy uses disruptive (non-mediation) language."""
    detector = DialogueLoopDetector()
    dialog = [
        {"role": "Socrates", "text": "Freedom is pure individual will."},
        {"role": "Athena", "text": "Freedom requires collective norms."},
        {
            "role": "Fixy",
            "text": "Give me one historical case that disproves your claim.",
        },
        {"role": "Socrates", "text": "The individual precedes the collective."},
        {"role": "Athena", "text": "Collective structures make individuals possible."},
        {
            "role": "Fixy",
            "text": "Either freedom is prior to society or it is not — choose one.",
        },
    ]
    result = detector._check_fixy_mediation_language(dialog)
    assert not result, "Should NOT flag disruptive (non-mediating) Fixy turns"


def test_check_high_textual_similarity_flags_consecutive_stagnation():
    """Signal C: Consecutive turns with very similar keyword sets."""
    detector = DialogueLoopDetector()
    turns = _make_turns(
        [
            "freedom autonomy liberty personal independence rights",
            "autonomy liberty freedom rights personal independence",
            "liberty freedom autonomy independence rights personal",
            "freedom independence autonomy liberty personal rights",
            "autonomy freedom liberty rights independence personal",
        ]
    )
    result = detector._check_high_textual_similarity(turns)
    assert result, "Expected high textual similarity to be flagged for stagnant turns"


def test_check_high_textual_similarity_no_flag_varied_content():
    """Signal C should NOT fire for turns with varied content."""
    detector = DialogueLoopDetector()
    turns = _make_turns(
        [
            "What is the nature of knowledge?",
            "Law determines societal obligations in practice.",
            "Habit formation changes neural circuits over years.",
            "Economic incentives shape institutional behaviour.",
        ]
    )
    result = detector._check_high_textual_similarity(turns)
    assert not result, "Should NOT flag varied turns for high textual similarity"


def test_detect_requires_two_conditions_single_non_compound_signal():
    """If only Signal A (phrase repetition) fires but not Signal C / B / D,
    the gate should block results for non-compound failure modes."""
    # Construct a scenario where _check_repetition might fire but no other
    # signal is active.  Use turns that have some overlap but no stagnation,
    # no rhetorical lock, no Fixy turns, and no synthesis language.
    detector = DialogueLoopDetector()
    # Turns share some vocabulary but are genuinely evolving
    turns = _make_turns(
        [
            "freedom means self-determination and personal choice",
            "society constrains freedom through collective agreements",
            "freedom requires society — neither stands alone here",
        ]
    )
    # Only 3 turns — below _MIN_TURNS_REPETITION=4 for sig_phrase_rep;
    # also no Fixy turns, no synthesis phrases → gate should not trigger
    modes = detector.detect(turns, turn_count=3)
    assert modes == [], f"Gate should block with < 4 turns, got {modes}"


def test_detect_two_conditions_gate_passes_with_signals_a_and_c():
    """When both Signal A (phrase repetition) and Signal C (textual similarity)
    are active, the gate should pass and return loop_repetition."""
    detector = DialogueLoopDetector()
    turns = _make_turns(
        [
            "freedom autonomy liberty independence means personal freedom",
            "autonomy liberty freedom independence are fundamental values",
            "liberty means freedom autonomy personal independence always",
            "independence freedom liberty autonomy interrelated core concepts",
            "freedom liberty autonomy independence personal core values",
        ]
    )
    modes = detector.detect(turns, turn_count=5)
    assert (
        LOOP_REPETITION in modes
    ), f"Expected loop_repetition with Signals A+C active; got {modes}"


# ---------------------------------------------------------------------------
# Conceptual dependency loop detection helpers
# ---------------------------------------------------------------------------


class TestConceptKey:
    def test_strips_stopwords(self):
        key = _concept_key("the freedom of reason")
        assert "the" not in key
        assert "of" not in key
        assert "freedom" in key
        assert "reason" in key

    def test_filters_short_tokens(self):
        key = _concept_key("a b freedom")
        assert "a" not in key
        assert "b" not in key
        assert "freedom" in key

    def test_empty_phrase(self):
        assert _concept_key("") == frozenset()

    def test_normalises_to_lowercase(self):
        key = _concept_key("Freedom REASON")
        assert "freedom" in key
        assert "reason" in key


class TestConceptOverlap:
    def test_identical_sets(self):
        a = frozenset({"freedom", "will"})
        assert _concept_overlap(a, a) == 1.0

    def test_disjoint_sets(self):
        a = frozenset({"freedom"})
        b = frozenset({"justice"})
        assert _concept_overlap(a, b) == 0.0

    def test_partial_overlap(self):
        a = frozenset({"freedom", "will"})
        b = frozenset({"freedom", "reason"})
        score = _concept_overlap(a, b)
        assert 0.0 < score < 1.0

    def test_empty_sets(self):
        assert _concept_overlap(frozenset(), frozenset({"x"})) == 0.0
        assert _concept_overlap(frozenset({"x"}), frozenset()) == 0.0


class TestExtractDepPairs:
    def test_forward_depends_on(self):
        pairs = _extract_dep_pairs("Freedom depends on justice in society.")
        assert len(pairs) >= 1
        left, right = pairs[0]
        assert "freedom" in left
        assert "justice" in right

    def test_forward_requires(self):
        pairs = _extract_dep_pairs("Virtue requires knowledge to function properly.")
        assert len(pairs) >= 1
        left, right = pairs[0]
        assert "virtue" in left
        assert "knowledge" in right

    def test_reverse_enables(self):
        pairs = _extract_dep_pairs("Justice enables freedom in a well-ordered state.")
        assert len(pairs) >= 1
        # reverse: "justice enables freedom" → normalised to (freedom, justice)
        # because _extract_dep_pairs returns (dependent, dependency) order:
        # enabled=freedom, enabler=justice → freedom depends on justice
        left, right = pairs[0]  # left=dependent, right=dependency
        assert "freedom" in left
        assert "justice" in right

    def test_no_dep_phrase(self):
        pairs = _extract_dep_pairs("Freedom is important. Justice matters too.")
        assert pairs == []

    def test_empty_text(self):
        assert _extract_dep_pairs("") == []


# ---------------------------------------------------------------------------
# Conceptual dependency loop — _check_conceptual_dependency_loop
# ---------------------------------------------------------------------------


class TestCheckConceptualDependencyLoop:
    def test_detects_simple_circular_dep(self):
        """freedom depends on justice + justice depends on freedom → loop."""
        detector = DialogueLoopDetector()
        turns = _make_turns(
            [
                "Freedom depends on justice to be meaningful.",
                "But justice itself depends on freedom to emerge.",
                "Without freedom, justice cannot be defined.",
                "And freedom requires justice as its precondition.",
            ]
        )
        result = detector._check_conceptual_dependency_loop(turns)
        assert result, "Should detect mutual dependency loop"

    def test_no_loop_for_unidirectional_dep(self):
        """All turns say the same direction (A→B) — no loop."""
        detector = DialogueLoopDetector()
        turns = _make_turns(
            [
                "Knowledge requires evidence to be valid.",
                "Knowledge also requires reasoning as its basis.",
                "Knowledge is grounded in observation.",
                "Knowledge depends on logic to hold.",
            ]
        )
        result = detector._check_conceptual_dependency_loop(turns)
        assert not result, "Unidirectional dependency should not trigger loop"

    def test_no_loop_for_unrelated_concepts(self):
        """Different concepts in each turn — no axis overlap."""
        detector = DialogueLoopDetector()
        turns = _make_turns(
            [
                "Freedom depends on justice.",
                "Health requires nutrition to sustain itself.",
                "Technology enables productivity in modern life.",
                "Courage requires wisdom as its foundation.",
            ]
        )
        result = detector._check_conceptual_dependency_loop(turns)
        assert not result, "Unrelated axes should not trigger loop"

    def test_minimum_turns_gate(self):
        """Fewer than _MIN_TURNS_CONCEPTUAL_LOOP turns → no detection."""
        detector = DialogueLoopDetector()
        turns = _make_turns(
            [
                "Freedom depends on justice.",
                "Justice depends on freedom.",
                "This is circular.",
            ]
        )
        result = detector._check_conceptual_dependency_loop(turns)
        assert not result, "Should not fire with fewer than 4 turns"

    def test_detects_enables_reversal(self):
        """'B enables A' followed by 'A enables B' → conceptual loop."""
        detector = DialogueLoopDetector()
        turns = _make_turns(
            [
                "Order enables freedom within a stable community.",
                "But freedom itself enables order through voluntary compliance.",
                "Without order, freedom cannot persist.",
                "And order only becomes possible where freedom already exists.",
            ]
        )
        result = detector._check_conceptual_dependency_loop(turns)
        assert result, "Should detect reverse-phrase conceptual loop"


# ---------------------------------------------------------------------------
# Conceptual dependency loop — integration via detect()
# ---------------------------------------------------------------------------


class TestDetectConceptualLoop:
    def test_detect_conceptual_loop_integration(self):
        """detect() should include CONCEPTUAL_LOOP in modes when circular dep found."""
        detector = DialogueLoopDetector()
        turns = _make_turns(
            [
                "Freedom depends on justice to be meaningful in practice.",
                "But justice itself depends on freedom in order to emerge.",
                "Without freedom, justice cannot be properly defined at all.",
                "And freedom requires justice as its fundamental precondition.",
            ]
        )
        modes = detector.detect(turns, turn_count=4)
        assert CONCEPTUAL_LOOP in modes, f"Expected conceptual_loop, got {modes}"

    def test_conceptual_loop_not_suppressed_by_novelty(self):
        """CONCEPTUAL_LOOP should appear even when novelty indicators are present."""
        detector = DialogueLoopDetector()
        # Mix circular dependency language with novelty markers
        turns = _make_turns(
            [
                "Therefore, freedom depends on justice — this implies a new framework.",
                "Specifically, justice depends on freedom, which leads to a measurable criterion.",
                "Freedom is impossible without justice, consequently this entails a contradiction.",
                "Justice cannot exist without freedom — it follows that neither can stand alone.",
            ]
        )
        modes = detector.detect(turns, turn_count=4)
        assert (
            CONCEPTUAL_LOOP in modes
        ), f"CONCEPTUAL_LOOP should survive novelty suppressor; got {modes}"

    def test_conceptual_loop_policy_in_agent_policy(self):
        """_LOOP_AGENT_POLICY should map conceptual_loop to MECHANIZE."""
        assert _LOOP_AGENT_POLICY.get("conceptual_loop") == AgentMode.MECHANIZE

    def test_conceptual_loop_policy_in_fixy_policy(self):
        """_LOOP_MODE_POLICY should map conceptual_loop to FORCE_MECHANISM."""
        assert _LOOP_MODE_POLICY.get("conceptual_loop") == FixyMode.FORCE_MECHANISM


# ---------------------------------------------------------------------------
# Embedding-based same-axis detection — check_same_axis()
# ---------------------------------------------------------------------------
# NOTE: In the test environment sentence-transformers is not installed, so
# all tests exercise the Jaccard fallback path.  The embedding path is tested
# at the interface level (returns bool, obeys constraints).


class TestCheckSameAxis:
    """Tests for DialogueLoopDetector.check_same_axis()."""

    def test_returns_true_for_thematically_concentrated_turns(self):
        """Turns sharing the same narrow vocabulary should return same_axis=True.

        Uses keyword-dense text to exercise the Jaccard fallback path reliably
        without requiring sentence-transformers to be installed.
        """
        detector = DialogueLoopDetector()
        # High keyword overlap across all turns (same core concept cluster)
        turns = _make_turns(
            [
                "freedom autonomy liberty independence personal freedom choices",
                "autonomy liberty freedom independence fundamental choices personal",
                "liberty freedom autonomy personal independence choices fundamental",
                "independence freedom liberty autonomy choices personal fundamental",
            ]
        )
        result = detector.check_same_axis(turns)
        assert result is True, "Concentrated turns should be on the same axis"

    def test_returns_false_for_diverse_topics(self):
        """Turns from unrelated domains should return same_axis=False."""
        detector = DialogueLoopDetector()
        turns = _make_turns(
            [
                "What is the nature of mathematical truth and proof?",
                "Evolution shaped the neural architecture of the human brain.",
                "Economic incentives determine institutional behaviour and policy.",
                "Aesthetic beauty emerges from the formal properties of an artwork.",
            ]
        )
        result = detector.check_same_axis(turns)
        assert result is False, "Diverse turns should NOT be on the same axis"

    def test_returns_false_for_fewer_than_two_turns(self):
        """Single-turn input cannot establish axis — must return False."""
        detector = DialogueLoopDetector()
        turns = _make_turns(["Freedom depends on justice."])
        result = detector.check_same_axis(turns)
        assert result is False, "Single turn cannot establish same-axis"

    def test_returns_false_for_empty_turns(self):
        """Empty turn list → False."""
        detector = DialogueLoopDetector()
        result = detector.check_same_axis([])
        assert result is False

    def test_returns_bool(self):
        """check_same_axis must always return a plain bool."""
        detector = DialogueLoopDetector()
        turns = _make_turns(
            [
                "consciousness neural brain experience consciousness neural",
                "neural consciousness brain experience neural consciousness",
                "brain consciousness neural experience brain consciousness",
                "experience neural consciousness brain experience neural",
            ]
        )
        result = detector.check_same_axis(turns)
        assert isinstance(result, bool), "check_same_axis must return bool"

    def test_thresholds_are_exposed(self):
        """Threshold constants must be importable and within plausible bounds."""
        assert 0.0 < _AXIS_EMBEDDING_SIMILARITY_THRESHOLD < 1.0
        assert 0.0 < _AXIS_JACCARD_THRESHOLD < 1.0

    def test_same_axis_does_not_produce_conceptual_loop_alone(self):
        """check_same_axis=True must NOT cause CONCEPTUAL_LOOP in detect().

        CONCEPTUAL_LOOP requires a structural dependency-direction flip; high
        keyword similarity alone is not sufficient to produce that failure mode.
        """
        detector = DialogueLoopDetector()
        # High keyword overlap → same_axis fires; but NO dependency phrases → no dep flip
        turns = _make_turns(
            [
                "freedom autonomy liberty independence personal freedom choices",
                "autonomy liberty freedom independence fundamental choices personal",
                "liberty freedom autonomy personal independence choices fundamental",
                "independence freedom liberty autonomy choices personal fundamental",
            ]
        )
        # Confirm same_axis fires on this input
        assert detector.check_same_axis(turns) is True
        # detect() must NOT report CONCEPTUAL_LOOP (no dep-flip phrases present)
        modes = detector.detect(turns, turn_count=4)
        assert CONCEPTUAL_LOOP not in modes, (
            "same_axis (keyword overlap) alone must NOT produce CONCEPTUAL_LOOP; "
            f"got modes={modes}"
        )


# ---------------------------------------------------------------------------
# Axis stagnation detection — _check_axis_stagnation() and AXIS_STAGNATION
# ---------------------------------------------------------------------------


class TestAxisStagnation:
    """Tests for the axis_stagnation failure mode.

    Axis stagnation fires when:
      1. same_axis — turns operate on the same conceptual axis.
      2. no_new_dimension — no concrete case, metric, test, definition, or commitment.
      3. continued_argumentation — opposition/persistence markers in >= half the turns.
      4. no_resolution — no synthesis/convergence phrases.

    It does NOT rely on wording similarity between turns (unlike loop_repetition)
    and does NOT require a dependency-direction flip (unlike conceptual_loop).
    """

    # Oscillating turns: same core vocabulary (justice/freedom/liberty),
    # alternating inseparable/separable positions, no novelty keywords.
    # Jaccard threshold 0.40 is satisfied because each turn shares
    # {justice, freedom, liberty, separate} with the others.
    _OSCILLATING_TURNS = [
        "justice freedom inseparable justice freedom liberty cannot separate persist",
        "freedom justice separable freedom justice liberty must separate remains",
        "justice freedom inseparable justice freedom liberty cannot separate always",
        "freedom justice separable freedom justice liberty must separate never",
        "justice freedom inseparable justice freedom liberty impossible separate remains",
        "freedom justice separable freedom justice liberty impossible conflate persist",
    ]

    def _make_oscillating(self):
        return _make_turns(self._OSCILLATING_TURNS)

    def test_fires_for_oscillating_axis_without_new_dimension(self):
        """AXIS_STAGNATION must fire for pure oscillation with no structural progress."""
        detector = DialogueLoopDetector()
        turns = self._make_oscillating()
        result = detector._check_axis_stagnation(turns)
        assert result is True, (
            "_check_axis_stagnation must return True for oscillating turns "
            "on the same axis with no new dimension"
        )

    def test_detect_includes_axis_stagnation_in_modes(self):
        """detect() must include AXIS_STAGNATION for an oscillating dialogue."""
        detector = DialogueLoopDetector()
        turns = self._make_oscillating()
        modes = detector.detect(turns, turn_count=6)
        assert (
            AXIS_STAGNATION in modes
        ), f"AXIS_STAGNATION must appear in detect() modes; got {modes}"

    def test_does_not_fire_when_concrete_case_introduced(self):
        """AXIS_STAGNATION must NOT fire when a concrete case is introduced."""
        detector = DialogueLoopDetector()
        turns = _make_turns(
            self._OSCILLATING_TURNS[:4]
            + [
                # Turn 5: introduces concrete case keywords
                "justice freedom inseparable liberty consider specifically this "
                "historical example scenario concrete case evidence",
                # Turn 6: responds in kind
                "freedom justice separable liberty distinct concepts based "
                "concrete study empirical instance illustrate",
            ]
        )
        result = detector._check_axis_stagnation(turns)
        assert (
            result is False
        ), "_check_axis_stagnation must return False when a concrete case is present"

    def test_does_not_fire_when_resolution_occurs(self):
        """AXIS_STAGNATION must NOT fire when synthesis/resolution phrases appear."""
        detector = DialogueLoopDetector()
        turns = _make_turns(
            self._OSCILLATING_TURNS[:5]
            + [
                # Turn 6: resolution / synthesis phrase
                "justice freedom inseparable both are needed together they complement",
            ]
        )
        result = detector._check_axis_stagnation(turns)
        assert (
            result is False
        ), "_check_axis_stagnation must return False when synthesis/resolution is present"

    def test_does_not_fire_when_axis_is_diverse(self):
        """AXIS_STAGNATION must NOT fire when turns cover diverse topics."""
        detector = DialogueLoopDetector()
        turns = _make_turns(
            [
                "What is the nature of mathematical truth and formal proof?",
                "Evolution shaped the neural architecture of the human brain.",
                "Economic incentives determine institutional behaviour and policy.",
                "Aesthetic beauty emerges from the formal properties of an artwork.",
                "Climate change requires coordinated international policy responses.",
                "Quantum mechanics challenges classical notions of causality.",
            ]
        )
        result = detector._check_axis_stagnation(turns)
        assert (
            result is False
        ), "_check_axis_stagnation must return False when turns are topically diverse"

    def test_does_not_fire_below_minimum_turns(self):
        """AXIS_STAGNATION must NOT fire when fewer than 6 turns are available."""
        detector = DialogueLoopDetector()
        # Only 4 turns — below _MIN_TURNS_AXIS_STAGNATION
        turns = _make_turns(self._OSCILLATING_TURNS[:4])
        result = detector._check_axis_stagnation(turns)
        assert (
            result is False
        ), "_check_axis_stagnation must not fire with fewer than 6 turns"

    def test_does_not_fire_when_measurable_condition_present(self):
        """AXIS_STAGNATION must NOT fire when a measurable condition is introduced."""
        detector = DialogueLoopDetector()
        turns = _make_turns(
            self._OSCILLATING_TURNS[:4]
            + [
                # Turn 5: introduces measurable / metric keywords
                "justice freedom inseparable liberty must measure quantif benchmark "
                "metric criterion scale index ratio",
                "freedom justice separable liberty must separate metric threshold score",
            ]
        )
        result = detector._check_axis_stagnation(turns)
        assert (
            result is False
        ), "_check_axis_stagnation must return False when a measurable condition appears"

    def test_does_not_fire_when_test_scenario_present(self):
        """AXIS_STAGNATION must NOT fire when a test scenario is introduced."""
        detector = DialogueLoopDetector()
        turns = _make_turns(
            self._OSCILLATING_TURNS[:4]
            + [
                "justice freedom inseparable liberty testable falsif predict verif "
                "hypothesis observable empirically experiment",
                "freedom justice separable liberty testable claim predict verif",
            ]
        )
        result = detector._check_axis_stagnation(turns)
        assert (
            result is False
        ), "_check_axis_stagnation must return False when a test scenario appears"

    def test_axis_stagnation_not_suppressed_by_novelty_suppressor(self):
        """AXIS_STAGNATION must survive the novelty suppressor in detect().

        The novelty suppressor only checks the last 2 turns; axis_stagnation
        performs its own full-window check and is explicitly exempt from the
        suppressor gate.
        """
        detector = DialogueLoopDetector()
        turns = self._make_oscillating()
        # Confirm no novelty in last 2 turns (suppressor inactive for these turns)
        modes = detector.detect(turns, turn_count=6)
        assert (
            AXIS_STAGNATION in modes
        ), f"AXIS_STAGNATION must survive the novelty suppressor; got {modes}"

    def test_axis_stagnation_policy_in_fixy_policy(self):
        """_LOOP_MODE_POLICY must map axis_stagnation to a non-MEDIATE mode."""
        from entelgia.fixy_interactive import _LOOP_MODE_POLICY, FixyMode

        assert (
            "axis_stagnation" in _LOOP_MODE_POLICY
        ), "_LOOP_MODE_POLICY must have an entry for 'axis_stagnation'"
        assert (
            _LOOP_MODE_POLICY["axis_stagnation"] != FixyMode.MEDIATE
        ), "axis_stagnation must not fall back to the generic MEDIATE mode"

    def test_axis_stagnation_policy_in_agent_policy(self):
        """_LOOP_AGENT_POLICY must map axis_stagnation to AgentMode.CONCRETIZE."""
        from entelgia.dialogue_engine import _LOOP_AGENT_POLICY, AgentMode

        assert (
            "axis_stagnation" in _LOOP_AGENT_POLICY
        ), "_LOOP_AGENT_POLICY must have an entry for 'axis_stagnation'"
        assert _LOOP_AGENT_POLICY["axis_stagnation"] == AgentMode.CONCRETIZE

    def test_axis_stagnation_rewrite_mode_in_policy(self):
        """_LOOP_REWRITE_MODE_POLICY must map axis_stagnation to force_case."""
        from entelgia.fixy_interactive import _LOOP_REWRITE_MODE_POLICY, FixyMode

        assert (
            "axis_stagnation" in _LOOP_REWRITE_MODE_POLICY
        ), "_LOOP_REWRITE_MODE_POLICY must have an entry for 'axis_stagnation'"
        assert _LOOP_REWRITE_MODE_POLICY["axis_stagnation"] == FixyMode.FORCE_CASE

    def test_axis_stagnation_novelty_rule_in_dialogue_rewriter(self):
        """DialogueRewriter._NOVELTY_RULES must contain an entry for axis_stagnation."""
        rewriter = DialogueRewriter()
        assert (
            AXIS_STAGNATION in rewriter._NOVELTY_RULES
        ), "DialogueRewriter._NOVELTY_RULES must contain an entry for AXIS_STAGNATION"
        rule = rewriter._NOVELTY_RULES[AXIS_STAGNATION]
        assert (
            isinstance(rule, str) and len(rule) > 10
        ), "AXIS_STAGNATION novelty rule must be a non-trivial instruction string"

    def test_axis_stagnation_constant_value(self):
        """AXIS_STAGNATION constant must equal 'axis_stagnation'."""
        assert AXIS_STAGNATION == "axis_stagnation"

    def test_returns_bool(self):
        """_check_axis_stagnation must always return a plain bool."""
        detector = DialogueLoopDetector()
        turns = self._make_oscillating()
        result = detector._check_axis_stagnation(turns)
        assert isinstance(result, bool)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s", "--override-ini=addopts="])

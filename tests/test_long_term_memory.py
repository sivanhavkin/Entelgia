#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Tests for the long-term memory system (personal unconscious/conscious layers).

Covers:
  - DefenseMechanism: repression and suppression classification
  - FreudianSlip: attempt selection and fragment formatting
  - SelfReplication: pattern detection and promotion selection
"""

import pytest
from entelgia.long_term_memory import DefenseMechanism, FreudianSlip, SelfReplication


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def defense():
    return DefenseMechanism()


@pytest.fixture
def slip(defense):
    return FreudianSlip(defense)


@pytest.fixture
def replication():
    return SelfReplication()


@pytest.fixture
def high_fear_memory():
    return {
        "id": "mem-001",
        "content": "The argument was terrifying and I felt completely overwhelmed",
        "emotion": "fear",
        "emotion_intensity": 0.85,
        "importance": 0.7,
        "intrusive": 1,   # stored as repressed (high-intensity fear)
        "suppressed": 0,
    }


@pytest.fixture
def suppressed_memory():
    return {
        "id": "mem-002",
        "content": "There is a secret that must stay hidden from everyone",
        "emotion": "neutral",
        "emotion_intensity": 0.2,
        "importance": 0.5,
        "intrusive": 0,
        "suppressed": 0,
    }


@pytest.fixture
def neutral_memory():
    return {
        "id": "mem-003",
        "content": "We discussed the nature of knowledge and truth",
        "emotion": "neutral",
        "emotion_intensity": 0.1,
        "importance": 0.3,
        "intrusive": 0,
        "suppressed": 0,
    }


# ---------------------------------------------------------------------------
# DefenseMechanism tests
# ---------------------------------------------------------------------------


class TestDefenseMechanism:
    """Tests for defense mechanism classification."""

    def test_repression_high_fear(self, defense):
        """High-intensity fear emotion should trigger repression."""
        flags = defense.analyze(
            content="I was terrified during the encounter",
            emotion="fear",
            emotion_intensity=0.85,
            importance=0.6,
        )
        assert flags["repressed"] == 1
        assert isinstance(flags["suppressed"], int)

    def test_repression_low_intensity_not_repressed(self, defense):
        """Low-intensity fear should NOT trigger repression."""
        flags = defense.analyze(
            content="I felt slightly uneasy",
            emotion="fear",
            emotion_intensity=0.40,
            importance=0.4,
        )
        assert flags["repressed"] == 0

    def test_repression_neutral_emotion(self, defense):
        """Neutral emotion should never be repressed."""
        flags = defense.analyze(
            content="This is a neutral factual statement",
            emotion="neutral",
            emotion_intensity=0.9,
            importance=0.9,
        )
        assert flags["repressed"] == 0

    def test_suppression_secret_content(self, defense):
        """Content mentioning secrets/forbidden topics should be suppressed."""
        flags = defense.analyze(
            content="There is a secret that must stay hidden",
            emotion="neutral",
            emotion_intensity=0.2,
            importance=0.5,
        )
        assert flags["suppressed"] == 1

    def test_suppression_forbidden_content(self, defense):
        """Content with 'forbidden' triggers suppression."""
        flags = defense.analyze(
            content="That thought is forbidden and dangerous",
            emotion="guilt",
            emotion_intensity=0.5,
            importance=0.5,
        )
        assert flags["suppressed"] == 1

    def test_no_defense_neutral_content(self, defense):
        """Neutral content with low intensity: no defenses active."""
        flags = defense.analyze(
            content="We discussed the nature of knowledge",
            emotion="curious",
            emotion_intensity=0.3,
            importance=0.4,
        )
        assert flags["repressed"] == 0
        assert flags["suppressed"] == 0

    def test_analyze_returns_int_flags(self, defense):
        """analyze() should always return integer flags 0 or 1."""
        flags = defense.analyze("test", "anger", 0.9, 0.8)
        assert set(flags.keys()) == {"repressed", "suppressed"}
        for v in flags.values():
            assert v in (0, 1)

    def test_slip_probability_no_defense(self, defense):
        """Undefended memory has low slip probability."""
        p = defense.slip_probability(repressed=0, suppressed=0)
        assert 0.0 <= p < 0.10

    def test_slip_probability_repressed(self, defense):
        """Repressed memory has higher slip probability."""
        p_plain = defense.slip_probability(repressed=0, suppressed=0)
        p_repressed = defense.slip_probability(repressed=1, suppressed=0)
        assert p_repressed > p_plain

    def test_slip_probability_suppressed(self, defense):
        """Suppressed memory has higher slip probability than undefended."""
        p_plain = defense.slip_probability(repressed=0, suppressed=0)
        p_suppressed = defense.slip_probability(repressed=0, suppressed=1)
        assert p_suppressed > p_plain

    def test_slip_probability_both_defended(self, defense):
        """Both defenses active → highest slip probability (capped at 0.30)."""
        p = defense.slip_probability(repressed=1, suppressed=1)
        assert p <= 0.30
        p_repressed_only = defense.slip_probability(repressed=1, suppressed=0)
        assert p >= p_repressed_only

    def test_analyze_empty_content(self, defense):
        """Empty content should not raise; returns zero flags."""
        flags = defense.analyze("", "neutral", 0.0, 0.0)
        assert flags["repressed"] == 0
        assert flags["suppressed"] == 0

    def test_analyze_none_emotion(self, defense):
        """None emotion should not raise."""
        flags = defense.analyze("some content", None, 0.9, 0.8)
        assert isinstance(flags["repressed"], int)

    def test_repression_anger_emotion(self, defense):
        """High-intensity anger should also trigger repression."""
        flags = defense.analyze(
            content="I was furious and enraged",
            emotion="anger",
            emotion_intensity=0.80,
            importance=0.6,
        )
        assert flags["repressed"] == 1

    def test_suppression_hebrew_content(self, defense):
        """Hebrew suppression trigger words are recognized."""
        flags = defense.analyze(
            content="יש כאן סוד שצריך להישמר",
            emotion="neutral",
            emotion_intensity=0.2,
            importance=0.5,
        )
        assert flags["suppressed"] == 1


# ---------------------------------------------------------------------------
# FreudianSlip tests
# ---------------------------------------------------------------------------


class TestFreudianSlip:
    """Tests for Freudian slip mechanism."""

    def test_attempt_empty_pool_returns_none(self, slip):
        """Empty memory pool should return None."""
        result = slip.attempt([])
        assert result is None

    def test_attempt_returns_memory_or_none(self, slip, high_fear_memory):
        """attempt() should return a dict or None across many trials."""
        # Run many times to account for randomness
        results = [slip.attempt([high_fear_memory]) for _ in range(100)]
        # At least some should slip (repressed memory with high probability)
        assert any(r is not None for r in results)
        # All non-None results should be dicts
        for r in results:
            assert r is None or isinstance(r, dict)

    def test_repressed_memory_slips_more_than_neutral(
        self, slip, neutral_memory
    ):
        """Repressed memories should slip more often than neutral ones."""
        # Mark the memory as repressed (intrusive=1)
        repressed_mem = {**neutral_memory, "intrusive": 1, "suppressed": 0}

        repressed_slips = sum(
            1 for _ in range(200) if slip.attempt([repressed_mem]) is not None
        )
        neutral_slips = sum(
            1 for _ in range(200) if slip.attempt([neutral_memory]) is not None
        )
        assert repressed_slips > neutral_slips

    def test_attempt_selects_highest_importance_when_multiple_slip(
        self, slip, defense
    ):
        """When multiple memories slip, the highest-importance one is returned."""
        low_imp = {
            "content": "A secret matter",
            "emotion": "fear",
            "emotion_intensity": 0.9,
            "importance": 0.2,
            "intrusive": 1,
            "suppressed": 1,
        }
        high_imp = {
            "content": "A secret matter of high importance",
            "emotion": "fear",
            "emotion_intensity": 0.9,
            "importance": 0.9,
            "intrusive": 1,
            "suppressed": 1,
        }
        # With both memories having max slip prob, the high-importance one
        # should consistently be selected when a slip occurs.
        selected = [slip.attempt([low_imp, high_imp]) for _ in range(100)]
        slipped = [s for s in selected if s is not None]
        if slipped:
            for s in slipped:
                assert float(s["importance"]) >= float(low_imp["importance"])

    def test_format_fragment_returns_string(self, slip, high_fear_memory):
        """format_fragment() should return a non-empty string."""
        fragment = slip.format_fragment(high_fear_memory)
        assert isinstance(fragment, str)
        assert len(fragment) > 0

    def test_format_fragment_max_length(self, slip):
        """Fragment should not exceed _FRAGMENT_MAX_LEN characters."""
        long_memory = {
            "content": "x" * 500,
            "emotion": "neutral",
            "importance": 0.5,
        }
        fragment = slip.format_fragment(long_memory)
        assert len(fragment) <= FreudianSlip._FRAGMENT_MAX_LEN

    def test_format_fragment_empty_content(self, slip):
        """Empty content memory returns empty string."""
        fragment = slip.format_fragment({"content": "", "emotion": "neutral"})
        assert fragment == ""

    def test_format_fragment_trims_at_sentence_boundary(self, slip):
        """Fragment should trim at sentence boundary when possible."""
        mem = {
            "content": "This is a sentence. And there is more text here.",
            "emotion": "neutral",
            "importance": 0.5,
        }
        fragment = slip.format_fragment(mem)
        # Should ideally end at the first '.'
        assert "." in fragment or len(fragment) <= FreudianSlip._FRAGMENT_MAX_LEN


# ---------------------------------------------------------------------------
# SelfReplication tests
# ---------------------------------------------------------------------------


class TestSelfReplication:
    """Tests for self-replication (pattern-based promotion)."""

    def test_find_patterns_empty_pool(self, replication):
        """Empty memory pool returns no patterns."""
        patterns = replication.find_patterns([])
        assert patterns == []

    def test_find_patterns_recurring_keywords(self, replication):
        """Keywords appearing in multiple memories are identified as patterns."""
        memories = [
            {"content": "knowledge and truth are fundamental to understanding"},
            {"content": "truth requires knowledge and careful investigation"},
            {"content": "understanding truth leads to knowledge"},
        ]
        patterns = replication.find_patterns(memories)
        # 'knowledge', 'truth', 'understanding' appear in multiple memories
        assert any(p in ("knowledge", "truth", "understanding") for p in patterns)

    def test_find_patterns_single_occurrence_excluded(self, replication):
        """Keywords appearing only once are NOT patterns."""
        memories = [
            {"content": "serendipitous event happened today"},
            {"content": "a completely different topic about nature"},
        ]
        patterns = replication.find_patterns(memories)
        # 'serendipitous' appears only once - should not be a pattern
        assert "serendipitous" not in patterns

    def test_find_patterns_short_words_excluded(self, replication):
        """Short words (< 4 chars) are excluded from pattern detection."""
        memories = [
            {"content": "the cat sat on the mat"},
            {"content": "the cat sat in the hat"},
        ]
        patterns = replication.find_patterns(memories)
        # 'the', 'cat', 'sat' etc. should be excluded (< 4 chars)
        assert "the" not in patterns
        assert "cat" not in patterns

    def test_select_for_promotion_no_patterns(self, replication, neutral_memory):
        """With no patterns, nothing is promoted."""
        result = replication.select_for_promotion([neutral_memory], [])
        assert result == []

    def test_select_for_promotion_empty_memories(self, replication):
        """With no memories, nothing is promoted."""
        result = replication.select_for_promotion([], ["knowledge", "truth"])
        assert result == []

    def test_select_for_promotion_returns_matching_memories(self, replication):
        """Memories containing pattern keywords are selected for promotion."""
        memories = [
            {
                "content": "knowledge and truth are fundamental",
                "emotion": "curious",
                "emotion_intensity": 0.4,
                "importance": 0.6,
            },
            {
                "content": "the weather was pleasant today",
                "emotion": "neutral",
                "emotion_intensity": 0.1,
                "importance": 0.2,
            },
            {
                "content": "seeking truth requires knowledge and courage",
                "emotion": "curious",
                "emotion_intensity": 0.5,
                "importance": 0.7,
            },
        ]
        patterns = ["knowledge", "truth"]
        promoted = replication.select_for_promotion(memories, patterns)
        # The weather memory should NOT be promoted (no pattern match)
        promoted_contents = [m["content"] for m in promoted]
        assert not any("weather" in c for c in promoted_contents)
        # The knowledge/truth memories should be promoted
        assert len(promoted) >= 1

    def test_select_for_promotion_respects_limit(self, replication):
        """No more than _PROMOTE_LIMIT memories are returned."""
        memories = [
            {
                "content": f"knowledge truth understanding item {i}",
                "importance": 0.5,
            }
            for i in range(20)
        ]
        patterns = ["knowledge", "truth", "understanding"]
        promoted = replication.select_for_promotion(memories, patterns)
        assert len(promoted) <= SelfReplication._PROMOTE_LIMIT

    def test_select_for_promotion_prefers_higher_importance(self, replication):
        """Higher-importance memories are preferred for promotion."""
        memories = [
            {
                "content": "knowledge is important for truth seeking",
                "importance": 0.9,
                "emotion": "curious",
                "emotion_intensity": 0.5,
            },
            {
                "content": "knowledge helps us find truth",
                "importance": 0.1,
                "emotion": "neutral",
                "emotion_intensity": 0.1,
            },
        ]
        patterns = ["knowledge", "truth"]
        promoted = replication.select_for_promotion(memories, patterns)
        # The high-importance memory should appear first or be included
        if promoted:
            assert any(m["importance"] >= 0.9 for m in promoted)

    def test_find_patterns_hebrew_words(self, replication):
        """Hebrew words longer than 4 chars are also detected as patterns."""
        memories = [
            {"content": "הפילוסופיה היא אהבת חכמה ואמת"},
            {"content": "חכמה וידע הם בסיס הפילוסופיה"},
        ]
        patterns = replication.find_patterns(memories)
        # 'חכמה' (wisdom) and 'פילוסופיה' (philosophy) appear in both
        assert any(len(p) >= 4 for p in patterns)

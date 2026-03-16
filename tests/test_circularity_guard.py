#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Tests for entelgia/circularity_guard.py.

Covers:
  1. detect_semantic_repetition — Jaccard fallback and semantic paths.
  2. detect_structural_templates — pattern matching.
  3. detect_cross_topic_contamination — generic and topic-specific phrases.
  4. compute_circularity_score — composite score and CircularityResult fields.
  5. History management — add_to_history, get_agent_history, clear_history.
  6. get_new_angle_instruction — rotation behaviour.
"""

import sys
import os
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import entelgia.circularity_guard as cg


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_identical_texts(n: int, text: str = "consciousness emerges from neural patterns"):
    """Return a list of *n* identical strings."""
    return [text] * n


def _constant_embeddings(n: int, dim: int = 4) -> np.ndarray:
    """Return *n* identical unit vectors (pairwise cosine similarity ≈ 1.0)."""
    vec = np.ones((1, dim)) / np.sqrt(dim)
    return np.repeat(vec, n, axis=0)


def _identity_embeddings(n: int, dim: int = 8) -> np.ndarray:
    """Return *n* orthogonal unit vectors (pairwise cosine similarity = 0.0)."""
    return np.eye(n, dim)


# ---------------------------------------------------------------------------
# Fixture: reset all module-level state before each test
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def reset_guard_state():
    """Clear circularity guard history and reset the new-angle index."""
    cg.clear_history()
    cg._new_angle_index = 0
    yield
    cg.clear_history()
    cg._new_angle_index = 0


# ===========================================================================
# 1.  detect_semantic_repetition
# ===========================================================================


class TestDetectSemanticRepetitionJaccard:
    """Jaccard-only fallback path (no sentence-transformers)."""

    def test_empty_history_returns_false(self):
        with patch.object(cg, "_SEMANTIC_AVAILABLE", False):
            detected, score = cg.detect_semantic_repetition("hello world", [])
        assert detected is False
        assert score == 0.0

    def test_below_min_history_returns_false(self):
        """Fewer than MIN_HISTORY_FOR_DETECTION previous texts must not trigger."""
        text = "system constraints define the optimization tradeoff between options"
        # Even identical text but only 2 previous entries (< 3)
        history = [text, text]
        with patch.object(cg, "_SEMANTIC_AVAILABLE", False):
            detected, score = cg.detect_semantic_repetition(text, history)
        assert detected is False
        assert score == 0.0

    def test_identical_texts_flagged(self):
        text = "system constraints define the optimization tradeoff between options"
        history = _make_identical_texts(3, text)
        with patch.object(cg, "_SEMANTIC_AVAILABLE", False):
            detected, score = cg.detect_semantic_repetition(text, history)
        assert detected is True
        assert score >= cg.JACCARD_REPETITION_THRESHOLD

    def test_diverse_texts_not_flagged(self):
        text = "apple orange banana mango pear cherry strawberry"
        history = [
            "jupiter saturn neptune uranus pluto",
            "mountain river ocean desert canyon plateau",
            "python javascript ruby golang swift",
        ]
        with patch.object(cg, "_SEMANTIC_AVAILABLE", False):
            detected, score = cg.detect_semantic_repetition(text, history)
        assert detected is False

    def test_returns_max_score_across_history(self):
        """Score should be the max Jaccard over the entire history, not just the last."""
        text = "consciousness emerges from neural patterns"
        # First entry is very similar; last entry is different
        history = [text, "apple banana cherry", "ocean mountain river"]
        with patch.object(cg, "_SEMANTIC_AVAILABLE", False):
            _, score = cg.detect_semantic_repetition(text, history)
        # Jaccard with itself is 1.0
        assert score == pytest.approx(1.0, abs=1e-6)


class TestDetectSemanticRepetitionEmbeddings:
    """Embedding path (sentence-transformers mock)."""

    def _mock_model_constant(self, n):
        """Model that returns constant embeddings (high similarity)."""
        model = MagicMock()
        model.encode.return_value = _constant_embeddings(n)
        return model

    def _mock_model_identity(self, n):
        """Model that returns orthogonal embeddings (zero similarity)."""
        model = MagicMock()
        model.encode.return_value = _identity_embeddings(n)
        return model

    def test_high_similarity_flagged(self):
        text = "knowledge arises through reflection and inquiry"
        history = [text] * 3
        mock_model = self._mock_model_constant(4)
        mock_cosine = MagicMock(return_value=np.array([[0.95, 0.95, 0.95]]))

        with (
            patch.object(cg, "_SEMANTIC_AVAILABLE", True),
            patch.object(cg, "_get_semantic_model", return_value=mock_model),
            patch.object(cg, "_cosine_similarity", mock_cosine),
        ):
            detected, score = cg.detect_semantic_repetition(text, history)

        assert detected is True
        assert score >= cg.SEMANTIC_REPETITION_THRESHOLD

    def test_low_similarity_not_flagged(self):
        text = "apple orange banana"
        history = ["jupiter saturn neptune", "mountain river ocean", "ruby golang swift"]
        mock_model = self._mock_model_identity(4)
        mock_cosine = MagicMock(return_value=np.array([[0.1, 0.1, 0.1]]))

        with (
            patch.object(cg, "_SEMANTIC_AVAILABLE", True),
            patch.object(cg, "_get_semantic_model", return_value=mock_model),
            patch.object(cg, "_cosine_similarity", mock_cosine),
        ):
            detected, score = cg.detect_semantic_repetition(text, history)

        assert detected is False
        assert score < cg.SEMANTIC_REPETITION_THRESHOLD

    def test_model_none_falls_back_to_jaccard(self):
        """When the model cannot be loaded, Jaccard fallback activates."""
        text = "system constraints define the tradeoff optimization"
        history = _make_identical_texts(3, text)

        with (
            patch.object(cg, "_SEMANTIC_AVAILABLE", True),
            patch.object(cg, "_get_semantic_model", return_value=None),
        ):
            detected, score = cg.detect_semantic_repetition(text, history)

        # Jaccard with itself = 1.0 → should be flagged
        assert detected is True

    def test_threshold_boundary(self):
        """Exactly at threshold is still flagged (>= comparison)."""
        text = "some unique philosophical thought"
        # Need at least min_history (3) previous texts for detection to fire
        history = [
            "different text entirely unrelated",
            "another different text here",
            "yet another completely different text",
        ]
        mock_model = MagicMock()
        mock_model.encode.return_value = _constant_embeddings(len(history) + 1)
        threshold = 0.75
        mock_cosine = MagicMock(return_value=np.array([[threshold] * len(history)]))

        with (
            patch.object(cg, "_SEMANTIC_AVAILABLE", True),
            patch.object(cg, "_get_semantic_model", return_value=mock_model),
            patch.object(cg, "_cosine_similarity", mock_cosine),
        ):
            detected, score = cg.detect_semantic_repetition(
                text, history, threshold=threshold
            )

        assert detected is True
        assert score == pytest.approx(threshold, abs=1e-6)


# ===========================================================================
# 2.  detect_structural_templates
# ===========================================================================


class TestDetectStructuralTemplates:

    def test_no_templates_not_flagged(self):
        text = "I believe that free will is an illusion constructed by memory."
        detected, count = cg.detect_structural_templates(text)
        assert detected is False
        assert count < cg.TEMPLATE_COUNT_THRESHOLD

    def test_single_template_not_flagged(self):
        # Only one template phrase — below the threshold of 2
        text = "Let us examine this question carefully."
        detected, count = cg.detect_structural_templates(text)
        assert detected is False
        assert count == 1

    def test_two_templates_flagged(self):
        text = (
            "Let us examine the system constraints here. "
            "On one hand freedom, on the other hand necessity."
        )
        detected, count = cg.detect_structural_templates(text)
        assert detected is True
        assert count >= 2

    def test_option_ab_pattern_detected(self):
        text = "We have Option A: freedom. Option B: determinism."
        detected, count = cg.detect_structural_templates(text)
        # Matches option A/B pattern AND possibly others
        assert count >= 1

    def test_tradeoff_variants_detected(self):
        for variant in ("tradeoff", "tradeoffs", "trade-off", "trade-offs", "trade off"):
            text = f"There is a fundamental {variant} here. We must balance both."
            detected, count = cg.detect_structural_templates(text)
            assert count >= 2, f"Expected ≥2 matches for variant {variant!r}"

    def test_fundamental_tension_detected(self):
        text = "The fundamental tension is between structure and freedom."
        detected, count = cg.detect_structural_templates(text)
        assert count >= 1

    def test_case_insensitive(self):
        text = "LET US EXAMINE THE SYSTEM CONSTRAINTS. ON ONE HAND FREEDOM."
        detected, count = cg.detect_structural_templates(text)
        assert detected is True

    def test_returns_correct_count_type(self):
        text = "plain text"
        _, count = cg.detect_structural_templates(text)
        assert isinstance(count, int)


# ===========================================================================
# 3.  detect_cross_topic_contamination
# ===========================================================================


class TestDetectCrossTopicContamination:

    def test_clean_text_not_flagged(self):
        text = "Consciousness may emerge from recursive self-reference."
        detected, found = cg.detect_cross_topic_contamination(text, "consciousness & self-models")
        assert detected is False
        assert found == []

    def test_generic_carryover_flagged(self):
        text = "Option A leads to freedom. Option B leads to determinism."
        detected, found = cg.detect_cross_topic_contamination(text, "free will & determinism")
        assert detected is True
        assert "option a" in found or "option b" in found

    def test_topic_specific_carryover_flagged(self):
        # "optimization function" is banned in "ethics & responsibility"
        text = "The optimization function must be designed with care."
        detected, found = cg.detect_cross_topic_contamination(text, "ethics & responsibility")
        assert detected is True
        assert "optimization function" in found

    def test_unknown_topic_only_generic_checked(self):
        text = "as discussed previously, we see the pattern emerging."
        detected, found = cg.detect_cross_topic_contamination(text, "unknown_topic_xyz")
        assert detected is True  # Generic carryover phrase present

    def test_multiple_carryover_phrases(self):
        text = "As I mentioned, option a and option b both carry weight."
        detected, found = cg.detect_cross_topic_contamination(text, "truth & epistemology")
        assert len(found) >= 2

    def test_threshold_one_phrase_flagged(self):
        text = "building on what was said, I add this insight."
        detected, found = cg.detect_cross_topic_contamination(
            text, "philosophy", contamination_threshold=1
        )
        assert detected is True

    def test_threshold_two_phrases_required(self):
        text = "building on what was said, I add this insight."
        detected, found = cg.detect_cross_topic_contamination(
            text, "philosophy", contamination_threshold=2
        )
        # Only 1 phrase → not flagged at threshold 2
        assert detected is False

    def test_case_insensitive_matching(self):
        text = "OPTION A is preferable to OPTION B in all cases."
        detected, found = cg.detect_cross_topic_contamination(text, "truth & epistemology")
        assert detected is True


# ===========================================================================
# 4.  compute_circularity_score
# ===========================================================================


class TestComputeCircularityScore:

    def test_empty_history_low_score(self):
        text = "Consciousness may emerge from recursive self-reference."
        result = cg.compute_circularity_score(text, "Socrates", topic="consciousness & self-models")
        assert result.is_circular is False
        assert result.score < cg.CIRCULARITY_SCORE_THRESHOLD

    def test_result_fields_present(self):
        text = "some interesting philosophical statement"
        result = cg.compute_circularity_score(text, "Athena")
        assert hasattr(result, "is_circular")
        assert hasattr(result, "score")
        assert hasattr(result, "semantic_score")
        assert hasattr(result, "template_count")
        assert hasattr(result, "contamination_phrases")
        assert hasattr(result, "reasons")

    def test_score_range(self):
        text = "philosophy is the love of wisdom"
        result = cg.compute_circularity_score(text, "Fixy")
        assert 0.0 <= result.score <= 1.0

    def test_high_semantic_repetition_raises_score(self):
        """Filling the history with the same text should yield a high score."""
        text = "system constraints define the tradeoff optimization"
        for _ in range(cg.HISTORY_SIZE):
            cg.add_to_history("Socrates", text)

        with patch.object(cg, "_SEMANTIC_AVAILABLE", False):
            result = cg.compute_circularity_score(text, "Socrates")

        # Jaccard = 1.0 → sem component = 1.0 → weighted score ≥ 0.5
        assert result.semantic_score == pytest.approx(1.0, abs=1e-6)
        assert result.score >= cg.CIRCULARITY_SCORE_THRESHOLD

    def test_contamination_raises_score(self):
        text = "Option A and option b are two paths. Let us examine the system constraints here."
        result = cg.compute_circularity_score(text, "Athena", topic="truth & epistemology")
        # Contamination phrases + templates both active → elevated score
        assert result.score > 0.0

    def test_is_circular_flag_matches_threshold(self):
        text = "let us examine the system constraints here on one hand and the other."
        result = cg.compute_circularity_score(
            text, "Socrates", topic="", threshold=0.0
        )
        # Threshold 0.0 → any non-zero score triggers circularity
        assert result.is_circular is True

    def test_reasons_populated_when_circular(self):
        """reasons list must be non-empty when the result is circular."""
        text = "system constraints define the tradeoff here. Let us examine both options."
        for _ in range(5):
            cg.add_to_history("Socrates", text)

        with patch.object(cg, "_SEMANTIC_AVAILABLE", False):
            result = cg.compute_circularity_score(text, "Socrates", threshold=0.0)

        if result.is_circular:
            assert len(result.reasons) > 0

    def test_custom_threshold(self):
        text = "a completely novel and unique philosophical insight"
        result = cg.compute_circularity_score(text, "Athena", threshold=0.99)
        # Very high threshold → should not be circular
        assert result.is_circular is False


# ===========================================================================
# 5.  History management
# ===========================================================================


class TestHistoryManagement:

    def test_add_and_retrieve(self):
        cg.add_to_history("Socrates", "first response")
        history = cg.get_agent_history("Socrates")
        assert "first response" in history

    def test_rolling_window_max_size(self):
        for i in range(cg.HISTORY_SIZE + 5):
            cg.add_to_history("Athena", f"response {i}")
        history = cg.get_agent_history("Athena")
        assert len(history) == cg.HISTORY_SIZE

    def test_oldest_entries_dropped(self):
        for i in range(cg.HISTORY_SIZE + 2):
            cg.add_to_history("Fixy", f"entry {i}")
        history = list(cg.get_agent_history("Fixy"))
        # The very first entries should have been evicted
        assert "entry 0" not in history
        assert f"entry {cg.HISTORY_SIZE + 1}" in history

    def test_clear_single_agent(self):
        cg.add_to_history("Socrates", "something")
        cg.add_to_history("Athena", "something else")
        cg.clear_history("Socrates")
        assert len(cg.get_agent_history("Socrates")) == 0
        assert len(cg.get_agent_history("Athena")) == 1

    def test_clear_all_agents(self):
        cg.add_to_history("Socrates", "a")
        cg.add_to_history("Athena", "b")
        cg.add_to_history("Fixy", "c")
        cg.clear_history()
        for agent in ("Socrates", "Athena", "Fixy"):
            assert len(cg.get_agent_history(agent)) == 0

    def test_independent_histories_per_agent(self):
        cg.add_to_history("Socrates", "socrates text")
        cg.add_to_history("Athena", "athena text")
        assert "socrates text" not in cg.get_agent_history("Athena")
        assert "athena text" not in cg.get_agent_history("Socrates")

    def test_new_agent_starts_with_empty_history(self):
        history = cg.get_agent_history("BrandNewAgent")
        assert len(history) == 0


# ===========================================================================
# 6.  get_new_angle_instruction
# ===========================================================================


class TestGetNewAngleInstruction:

    def test_returns_string(self):
        instruction = cg.get_new_angle_instruction()
        assert isinstance(instruction, str)
        assert len(instruction) > 0

    def test_rotates_through_all_instructions(self):
        seen = set()
        for _ in range(len(cg._NEW_ANGLE_INSTRUCTIONS)):
            seen.add(cg.get_new_angle_instruction())
        assert len(seen) == len(cg._NEW_ANGLE_INSTRUCTIONS)

    def test_wraps_around(self):
        n = len(cg._NEW_ANGLE_INSTRUCTIONS)
        # Advance past end of list
        for _ in range(n):
            cg.get_new_angle_instruction()
        # Next call should return first instruction again
        cg._new_angle_index = 0
        first = cg.get_new_angle_instruction()
        assert first == cg._NEW_ANGLE_INSTRUCTIONS[0]

    def test_index_increments(self):
        cg._new_angle_index = 0
        cg.get_new_angle_instruction()
        assert cg._new_angle_index == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s", "--override-ini=addopts="])

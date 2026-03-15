#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Tests for the semantic similarity layer added to _detect_repetition
in InteractiveFixy (entelgia/fixy_interactive.py).

Covers:
  1. Jaccard-only fallback when sentence-transformers is unavailable.
  2. Combined score path when sentence-transformers IS available.
  3. Threshold behaviour: combined_score > 0.5 triggers repetition.
  4. No repetition detected when turns are semantically distinct.
  5. _semantic_similarity returns 0.0 gracefully when unavailable.
  6. _encode_turns returns None gracefully when unavailable.
"""

import sys
import os
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import entelgia.fixy_interactive as _fi

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_turns(texts):
    """Convert a list of strings into turn dicts."""
    return [{"role": "agent", "text": t} for t in texts]


def _identity_embeddings(n: int, dim: int = 4) -> np.ndarray:
    """
    Return n orthogonal unit vectors (identity rows) as mock embeddings.
    Cosine similarity between any two distinct rows is 0.0.
    """
    mat = np.eye(n, dim)
    return mat


def _constant_embeddings(n: int, value: float = 1.0, dim: int = 4) -> np.ndarray:
    """Return n identical unit vectors so pairwise cosine similarity ≈ 1.0."""
    vec = np.full((1, dim), value / dim)
    return np.repeat(vec, n, axis=0)


# ---------------------------------------------------------------------------
# 1. _semantic_similarity graceful fallback when library is absent
# ---------------------------------------------------------------------------


class TestSemanticSimilarityFallback:
    def test_returns_zero_when_unavailable(self):
        """When _SEMANTIC_AVAILABLE is False, _semantic_similarity must return 0.0."""
        with patch.object(_fi, "_SEMANTIC_AVAILABLE", False):
            result = _fi._semantic_similarity("hello world", "hello world")
        assert result == 0.0

    def test_returns_zero_when_model_is_none(self):
        """When _SEMANTIC_AVAILABLE is True but model is None, return 0.0."""
        with (
            patch.object(_fi, "_SEMANTIC_AVAILABLE", True),
            patch.object(_fi, "_get_semantic_model", return_value=None),
        ):
            result = _fi._semantic_similarity("hello world", "hello world")
        assert result == 0.0

    def test_returns_float_between_0_and_1(self):
        """_semantic_similarity must always return a value in [0, 1]."""
        if not _fi._SEMANTIC_AVAILABLE:
            pytest.skip("sentence-transformers not installed")

        mock_model = MagicMock()
        vec_a = np.array([1.0, 0.0])
        vec_b = np.array([0.5, 0.5])
        mock_model.encode.return_value = np.array([vec_a, vec_b])

        mock_cosine = MagicMock(return_value=np.array([[0.7071]]))

        with (
            patch.object(_fi, "_SEMANTIC_AVAILABLE", True),
            patch.object(_fi, "_get_semantic_model", return_value=mock_model),
            patch.object(_fi, "_cosine_similarity", mock_cosine),
        ):
            result = _fi._semantic_similarity("foo", "bar")

        assert 0.0 <= result <= 1.0
        assert abs(result - 0.7071) < 1e-3


# ---------------------------------------------------------------------------
# 2. _encode_turns graceful fallback when library is absent
# ---------------------------------------------------------------------------


class TestEncodeTurnsFallback:
    def test_returns_none_when_unavailable(self):
        """When _SEMANTIC_AVAILABLE is False, _encode_turns must return None."""
        turns = _make_turns(["hello world", "foo bar"])
        with patch.object(_fi, "_SEMANTIC_AVAILABLE", False):
            result = _fi._encode_turns(turns)
        assert result is None

    def test_returns_none_when_model_is_none(self):
        """When model is None, _encode_turns must return None."""
        turns = _make_turns(["hello world", "foo bar"])
        with (
            patch.object(_fi, "_SEMANTIC_AVAILABLE", True),
            patch.object(_fi, "_get_semantic_model", return_value=None),
        ):
            result = _fi._encode_turns(turns)
        assert result is None


# ---------------------------------------------------------------------------
# 3. _detect_repetition – Jaccard-only fallback (no sentence-transformers)
# ---------------------------------------------------------------------------


class TestDetectRepetitionJaccardFallback:
    """When _SEMANTIC_AVAILABLE is False, behaviour must match the original Jaccard logic."""

    def _make_fixy(self):
        return _fi.InteractiveFixy(llm=MagicMock(), model="mock-model")

    def test_not_repetitive_with_few_turns(self):
        fixy = self._make_fixy()
        turns = _make_turns(["hello world", "foo bar", "baz qux"])
        with patch.object(_fi, "_SEMANTIC_AVAILABLE", False):
            assert fixy._detect_repetition(turns) is False

    def test_repetitive_with_high_jaccard_overlap(self):
        """4+ turns that are nearly identical should be flagged as repetitive."""
        fixy = self._make_fixy()
        text = "consciousness emerges from complex neural interactions patterns"
        turns = _make_turns([text] * 5)
        with patch.object(_fi, "_SEMANTIC_AVAILABLE", False):
            result = fixy._detect_repetition(turns)
        assert result is True

    def test_not_repetitive_with_diverse_turns(self):
        """Completely different texts should not be flagged."""
        fixy = self._make_fixy()
        turns = _make_turns(
            [
                "apple orange banana mango",
                "python javascript ruby golang",
                "mountain river ocean desert",
                "jupiter saturn neptune uranus",
            ]
        )
        with patch.object(_fi, "_SEMANTIC_AVAILABLE", False):
            result = fixy._detect_repetition(turns)
        assert result is False


# ---------------------------------------------------------------------------
# 4. _detect_repetition – combined score path (sentence-transformers present)
# ---------------------------------------------------------------------------


class TestDetectRepetitionCombinedScore:
    """When _SEMANTIC_AVAILABLE is True, the combined score must drive the decision."""

    def _make_fixy(self):
        return _fi.InteractiveFixy(llm=MagicMock(), model="mock-model")

    def _mock_cosine_high(self):
        """Return a mock _cosine_similarity that always yields 0.8."""
        return MagicMock(return_value=np.array([[0.8]]))

    def _mock_cosine_low(self):
        """Return a mock _cosine_similarity that always yields 0.1."""
        return MagicMock(return_value=np.array([[0.1]]))

    def _mock_cosine_zero(self):
        """Return a mock _cosine_similarity that always yields 0.0."""
        return MagicMock(return_value=np.array([[0.0]]))

    def test_high_semantic_similarity_triggers_repetition(self):
        """
        Identical Jaccard (=1.0) + high semantic (0.8) → combined 0.9 > 0.5 → repetitive.
        """
        fixy = self._make_fixy()
        text = "knowledge arises through reflection experience inquiry"
        turns = _make_turns([text] * 5)
        embeddings = _constant_embeddings(5)

        with (
            patch.object(_fi, "_SEMANTIC_AVAILABLE", True),
            patch.object(_fi, "_encode_turns", return_value=embeddings),
            patch.object(_fi, "_cosine_similarity", self._mock_cosine_high()),
        ):
            result = fixy._detect_repetition(turns)

        assert result is True

    def test_low_combined_score_not_repetitive(self):
        """
        Low Jaccard + low semantic similarity → combined < 0.5 → not repetitive.
        """
        fixy = self._make_fixy()
        turns = _make_turns(
            [
                "apple orange mango banana cherry",
                "python javascript ruby golang swift",
                "mountain river ocean desert canyon",
                "jupiter saturn neptune uranus pluto",
            ]
        )
        embeddings = _identity_embeddings(4)

        with (
            patch.object(_fi, "_SEMANTIC_AVAILABLE", True),
            patch.object(_fi, "_encode_turns", return_value=embeddings),
            patch.object(_fi, "_cosine_similarity", self._mock_cosine_low()),
        ):
            result = fixy._detect_repetition(turns)

        assert result is False

    def test_combined_score_boundary_exactly_05(self):
        """
        Jaccard=1.0, semantic=0.0 → combined=0.5, which is NOT > 0.5 → not repetitive.
        """
        fixy = self._make_fixy()
        text = "philosophy mind consciousness reality existence truth"
        turns = _make_turns([text] * 5)
        embeddings = _constant_embeddings(5)

        with (
            patch.object(_fi, "_SEMANTIC_AVAILABLE", True),
            patch.object(_fi, "_encode_turns", return_value=embeddings),
            patch.object(_fi, "_cosine_similarity", self._mock_cosine_zero()),
        ):
            # combined = 0.5 * 1.0 + 0.5 * 0.0 = 0.5; strict > 0.5 → False
            result = fixy._detect_repetition(turns)

        assert result is False

    def test_short_turns_returns_false_immediately(self):
        """Fewer than 4 turns should return False before any encoding is attempted."""
        fixy = self._make_fixy()
        turns = _make_turns(["same text here"] * 3)
        mock_encode = MagicMock()

        with (
            patch.object(_fi, "_SEMANTIC_AVAILABLE", True),
            patch.object(_fi, "_encode_turns", mock_encode),
        ):
            result = fixy._detect_repetition(turns)

        assert result is False
        mock_encode.assert_not_called()

    def test_encode_returns_none_falls_back_to_jaccard(self):
        """
        If _encode_turns returns None (e.g. model load failure), fall back to Jaccard.
        Identical turns → Jaccard=1.0 > 0.5 → repetitive.
        """
        fixy = self._make_fixy()
        text = "consciousness emerges from complex neural interactions patterns"
        turns = _make_turns([text] * 5)

        with (
            patch.object(_fi, "_SEMANTIC_AVAILABLE", True),
            patch.object(_fi, "_encode_turns", return_value=None),
        ):
            result = fixy._detect_repetition(turns)

        assert result is True


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s", "--override-ini=addopts="])

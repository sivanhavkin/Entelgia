#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Tests for entelgia/circularity_guard.py.

Covers:
  1. detect_semantic_repetition — delta-based Jaccard fallback and semantic paths.
  2. detect_structural_templates — rhetorical patterns only (technical vocab excluded).
  3. detect_cross_topic_contamination — generic, leaked-template, and topic-specific phrases.
  4. compute_circularity_score — composite score, CircularityResult fields, adaptive threshold.
  5. History management — add_to_history, get_agent_history, clear_history.
  6. get_new_angle_instruction — rotation behaviour.
  7. New tests (A–F per spec):
     A. Semantic false-positive reduction — same-topic diverse reasoning not over-flagged.
     B. Rhetorical vs technical vocabulary distinction.
     C. Contamination leak detection (Option A/B, forgiveness, peace and harmony, prefix).
     D. Adaptive threshold grows with history size.
     E. First-turn-after-topic-change leniency.
     F. CircularityResult includes threshold and sub-scores.
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


def _make_identical_texts(
    n: int, text: str = "consciousness emerges from neural patterns"
):
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
# 1.  detect_semantic_repetition  (delta-based scoring)
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
        history = [text, text]  # only 2 entries < 3
        with patch.object(cg, "_SEMANTIC_AVAILABLE", False):
            detected, score = cg.detect_semantic_repetition(text, history)
        assert detected is False
        assert score == 0.0

    def test_identical_texts_flagged(self):
        """3 identical previous texts → high delta → flagged."""
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

    def test_delta_score_uses_max_over_history(self):
        """Score is derived from the max Jaccard over entire history, not just last entry.

        history[0] is identical to text → max Jaccard = 1.0
        history[1] and history[2] are dissimilar → low avg_last3
        → high delta → detected
        """
        text = "consciousness emerges from neural patterns"
        history = [text, "apple banana cherry", "ocean mountain river"]
        with patch.object(cg, "_SEMANTIC_AVAILABLE", False):
            detected, score = cg.detect_semantic_repetition(text, history)
        # max_jaccard=1.0, avg_last3=(1.0+0+0)/3≈0.33, delta≈0.835 → flagged
        assert detected is True
        assert score > cg.JACCARD_REPETITION_THRESHOLD

    def test_delta_reduces_score_for_consistently_similar_history(self):
        """When all history entries are similar, delta is smaller than raw max."""
        text = "the nature of consciousness is deeply contested"
        # Three slightly similar philosophical texts → avg is non-trivial
        history = [
            "consciousness is a deeply contested philosophical topic",
            "the nature of mind remains philosophically contentious",
            "philosophers dispute the definition of consciousness",
        ]
        with patch.object(cg, "_SEMANTIC_AVAILABLE", False):
            _, delta = cg.detect_semantic_repetition(text, history)
        # Jaccard sims are moderate; delta should be lower than max_jaccard
        jaccards = [cg._jaccard(text, h) for h in history]
        max_j = max(jaccards)
        assert delta <= max_j  # delta always ≤ max


class TestDetectSemanticRepetitionEmbeddings:
    """Embedding path (sentence-transformers mock)."""

    def _mock_model_constant(self, n):
        model = MagicMock()
        model.encode.return_value = _constant_embeddings(n)
        return model

    def _mock_model_identity(self, n):
        model = MagicMock()
        model.encode.return_value = _identity_embeddings(n)
        return model

    def test_high_similarity_flagged(self):
        """High cosine with all 3 history items → delta ≈ 0.475 → flagged."""
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

        # delta = max(0, 0.95 - 0.95*0.5) = 0.475 ≥ SEMANTIC_REPETITION_THRESHOLD (0.45)
        assert detected is True
        assert score >= cg.SEMANTIC_REPETITION_THRESHOLD

    def test_low_similarity_not_flagged(self):
        text = "apple orange banana"
        history = [
            "jupiter saturn neptune",
            "mountain river ocean",
            "ruby golang swift",
        ]
        mock_model = self._mock_model_identity(4)
        mock_cosine = MagicMock(return_value=np.array([[0.1, 0.1, 0.1]]))

        with (
            patch.object(cg, "_SEMANTIC_AVAILABLE", True),
            patch.object(cg, "_get_semantic_model", return_value=mock_model),
            patch.object(cg, "_cosine_similarity", mock_cosine),
        ):
            detected, score = cg.detect_semantic_repetition(text, history)

        # delta = max(0, 0.1 - 0.05) = 0.05 < 0.45
        assert detected is False
        assert score < cg.SEMANTIC_REPETITION_THRESHOLD

    def test_semantic_path_with_model_failure_falls_back_to_jaccard(self):
        """When model is None on the semantic path, Jaccard fallback activates."""
        text = "system constraints define the tradeoff optimization"
        history = _make_identical_texts(3, text)

        with (
            patch.object(cg, "_SEMANTIC_AVAILABLE", True),
            patch.object(cg, "_get_semantic_model", return_value=None),
        ):
            detected, score = cg.detect_semantic_repetition(text, history)

        # Jaccard delta = max(0, 1.0 - 0.5) = 0.5 ≥ 0.40 → flagged
        assert detected is True

    def test_threshold_boundary(self):
        """Exactly at threshold is still flagged (>= comparison).

        Mock cosines are chosen so the delta formula produces exactly 0.75:
          sims = [0.0, 0.5, 1.0]
          max_sim = 1.0
          avg_last3 = (0.0 + 0.5 + 1.0) / 3 = 0.5
          delta = max(0, 1.0 - 0.5 * 0.5) = max(0, 0.75) = 0.75
        """
        text = "some unique philosophical thought"
        history = [
            "different text entirely unrelated",
            "another different text here",
            "yet another completely different text",
        ]
        mock_model = MagicMock()
        mock_model.encode.return_value = _constant_embeddings(len(history) + 1)
        threshold = 0.75
        mock_cosine = MagicMock(return_value=np.array([[0.0, 0.5, 1.0]]))

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
# 2.  detect_structural_templates  (rhetorical patterns only)
# ===========================================================================


class TestDetectStructuralTemplates:

    def test_no_templates_not_flagged(self):
        text = "I believe that free will is an illusion constructed by memory."
        detected, count = cg.detect_structural_templates(text)
        assert detected is False
        assert count < cg.TEMPLATE_COUNT_THRESHOLD

    def test_single_template_not_flagged(self):
        text = "Let us examine this question carefully."
        detected, count = cg.detect_structural_templates(text)
        assert detected is False
        assert count == 1

    def test_two_rhetorical_patterns_flagged(self):
        text = (
            "Let us examine the question here. "
            "On one hand freedom, on the other hand necessity."
        )
        detected, count = cg.detect_structural_templates(text)
        assert detected is True
        assert count >= 2

    @pytest.mark.parametrize(
        "variant",
        ["tradeoff", "tradeoffs", "trade-off", "trade-offs", "trade off"],
    )
    def test_tradeoff_variants_do_not_alone_raise_structural_count(self, variant):
        """Technical vocabulary (tradeoff) is NOT a rhetorical pattern."""
        text = f"There is a {variant} here."
        _, count = cg.detect_structural_templates(text)
        # "there is a tradeoff" does NOT match the rhetorical pattern
        # (the pattern requires "there is/are (two|a fundamental|a tension between)")
        assert count == 0, f"Technical term '{variant}' should NOT count as rhetorical"

    def test_tradeoff_with_rhetorical_context_flagged(self):
        """Two true rhetorical patterns still fire even when tradeoff is present."""
        text = "There is a fundamental tradeoff here. We must balance both."
        # "there is a fundamental" → rhetorical ✓
        # "we must balance" → rhetorical ✓
        detected, count = cg.detect_structural_templates(text)
        assert count >= 2

    def test_system_constraint_not_rhetorical(self):
        """'system constraint' is technical vocabulary, not a rhetorical pattern."""
        text = "The system constraint here is significant."
        _, count = cg.detect_structural_templates(text)
        assert count == 0

    def test_fundamental_tension_detected(self):
        text = "The fundamental tension is between structure and freedom."
        detected, count = cg.detect_structural_templates(text)
        assert count >= 1

    def test_in_our_scrutiny_detected(self):
        text = "In our scrutiny of this question, we find deep contradictions."
        detected, count = cg.detect_structural_templates(text)
        assert count >= 1

    def test_duplicated_speaker_prefix_detected(self):
        text = "Fixy: Fixy: This should not repeat the speaker prefix."
        detected, count = cg.detect_structural_templates(text)
        assert count >= 1

    def test_on_the_one_hand_detected(self):
        text = "On the one hand we have freedom; on the other hand necessity."
        detected, count = cg.detect_structural_templates(text)
        assert count >= 1

    def test_let_us_define_detected(self):
        text = "Let us define our terms before proceeding."
        _, count = cg.detect_structural_templates(text)
        assert count >= 1

    def test_let_us_scrutinize_detected(self):
        text = "Let us scrutinize the underlying assumptions."
        _, count = cg.detect_structural_templates(text)
        assert count >= 1

    def test_case_insensitive(self):
        text = "LET US EXAMINE THIS. ON ONE HAND FREEDOM."
        detected, count = cg.detect_structural_templates(text)
        assert detected is True

    def test_returns_correct_count_type(self):
        _, count = cg.detect_structural_templates("plain text")
        assert isinstance(count, int)


# ===========================================================================
# 3.  detect_cross_topic_contamination
# ===========================================================================


class TestDetectCrossTopicContamination:

    def test_clean_text_not_flagged(self):
        text = "Consciousness may emerge from recursive self-reference."
        detected, found = cg.detect_cross_topic_contamination(
            text, "consciousness & self-models"
        )
        assert detected is False
        assert found == []

    def test_generic_carryover_option_a_b_flagged(self):
        text = "Option A leads to freedom. Option B leads to determinism."
        detected, found = cg.detect_cross_topic_contamination(
            text, "free will & determinism"
        )
        assert detected is True
        assert "option a" in found or "option b" in found

    def test_generic_scenario_a_b_flagged(self):
        text = "Scenario A is optimal. Scenario B is suboptimal."
        detected, found = cg.detect_cross_topic_contamination(
            text, "ethics & responsibility"
        )
        assert detected is True
        assert "scenario a" in found or "scenario b" in found

    def test_generic_in_the_previous_topic_flagged(self):
        text = "In the previous topic we discussed autonomy."
        detected, found = cg.detect_cross_topic_contamination(
            text, "ethics & responsibility"
        )
        assert detected is True
        assert "in the previous topic" in found

    def test_leaked_template_forgiveness_flagged(self):
        text = "We should practice forgiveness and move forward."
        detected, found = cg.detect_cross_topic_contamination(text, "AI alignment")
        assert detected is True
        assert "forgiveness" in found

    def test_leaked_template_peace_and_harmony_flagged(self):
        text = "We seek peace and harmony in our reasoning."
        detected, found = cg.detect_cross_topic_contamination(
            text, "consciousness & self-models"
        )
        assert detected is True
        assert "peace and harmony" in found

    def test_leaked_template_our_community_flagged(self):
        text = "Our community values both freedom and safety."
        detected, found = cg.detect_cross_topic_contamination(
            text, "free will & determinism"
        )
        assert detected is True
        assert "our community" in found

    def test_leaked_template_practical_dilemma_flagged(self):
        text = "This is a practical dilemma that requires resolution."
        detected, found = cg.detect_cross_topic_contamination(
            text, "truth & epistemology"
        )
        assert detected is True
        assert "practical dilemma" in found

    def test_topic_specific_carryover_flagged(self):
        text = "The optimization function must be designed with care."
        detected, found = cg.detect_cross_topic_contamination(
            text, "ethics & responsibility"
        )
        assert detected is True
        assert "optimization function" in found

    def test_unknown_topic_only_generic_checked(self):
        text = "as discussed previously, we see the pattern emerging."
        detected, found = cg.detect_cross_topic_contamination(text, "unknown_topic_xyz")
        assert detected is True

    def test_multiple_carryover_phrases(self):
        text = "As I mentioned, option a and option b both carry weight."
        detected, found = cg.detect_cross_topic_contamination(
            text, "truth & epistemology"
        )
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
        detected, found = cg.detect_cross_topic_contamination(
            text, "truth & epistemology"
        )
        assert detected is True


# ===========================================================================
# 4.  compute_circularity_score
# ===========================================================================


class TestComputeCircularityScore:

    def test_empty_history_low_score(self):
        text = "Consciousness may emerge from recursive self-reference."
        result = cg.compute_circularity_score(
            text, "Socrates", topic="consciousness & self-models"
        )
        assert result.is_circular is False
        assert result.score < result.threshold  # uses dynamic threshold

    def test_result_fields_present(self):
        text = "some interesting philosophical statement"
        result = cg.compute_circularity_score(text, "Athena")
        assert hasattr(result, "is_circular")
        assert hasattr(result, "score")
        assert hasattr(result, "semantic_score")
        assert hasattr(result, "template_count")
        assert hasattr(result, "contamination_phrases")
        assert hasattr(result, "threshold")
        assert hasattr(result, "reasons")

    def test_score_range(self):
        text = "philosophy is the love of wisdom"
        result = cg.compute_circularity_score(text, "Fixy")
        assert 0.0 <= result.score <= 1.0

    def test_high_semantic_repetition_raises_score(self):
        """Filling the history with identical text raises the semantic component."""
        text = "the question of being is central to metaphysics"
        for _ in range(cg.HISTORY_SIZE):
            cg.add_to_history("Socrates", text)

        with patch.object(cg, "_SEMANTIC_AVAILABLE", False):
            result = cg.compute_circularity_score(text, "Socrates")

        # With 10 identical texts: Jaccard delta = max(0, 1.0 - 1.0*0.5) = 0.5
        assert result.semantic_score == pytest.approx(0.5, abs=0.05)
        # Semantic component (0.5 * 0.5 = 0.25) is non-zero
        assert result.score > 0.0

    def test_contamination_raises_score(self):
        text = "Option A and option b are two paths. On the one hand freedom."
        result = cg.compute_circularity_score(
            text, "Athena", topic="truth & epistemology"
        )
        assert result.score > 0.0

    def test_is_circular_flag_matches_explicit_threshold(self):
        text = "let us examine the question on one hand and the other."
        result = cg.compute_circularity_score(text, "Socrates", topic="", threshold=0.0)
        assert result.is_circular is True

    def test_reasons_populated_when_circular(self):
        text = "Let us examine both options on one hand and the other."
        for _ in range(5):
            cg.add_to_history("Socrates", text)

        with patch.object(cg, "_SEMANTIC_AVAILABLE", False):
            result = cg.compute_circularity_score(text, "Socrates", threshold=0.0)

        if result.is_circular:
            assert len(result.reasons) > 0

    def test_custom_threshold_prevents_flagging(self):
        text = "a completely novel and unique philosophical insight"
        result = cg.compute_circularity_score(text, "Athena", threshold=0.99)
        assert result.is_circular is False

    def test_threshold_stored_in_result(self):
        """CircularityResult.threshold must equal the threshold used in the check."""
        text = "a test statement"
        result = cg.compute_circularity_score(text, "Socrates", threshold=0.42)
        assert result.threshold == pytest.approx(0.42, abs=1e-6)

    def test_dynamic_threshold_used_when_none_passed(self):
        """When threshold=None, the dynamic threshold is recorded in the result."""
        text = "a test statement"
        result = cg.compute_circularity_score(text, "Socrates")
        expected = cg.get_dynamic_threshold(len(list(cg.get_agent_history("Socrates"))))
        assert result.threshold == pytest.approx(expected, abs=1e-6)


# ===========================================================================
# 5.  History management
# ===========================================================================


class TestHistoryManagement:

    def test_add_and_retrieve(self):
        cg.add_to_history("Socrates", "first response")
        assert "first response" in cg.get_agent_history("Socrates")

    def test_rolling_window_max_size(self):
        for i in range(cg.HISTORY_SIZE + 5):
            cg.add_to_history("Athena", f"response {i}")
        assert len(cg.get_agent_history("Athena")) == cg.HISTORY_SIZE

    def test_oldest_entries_dropped(self):
        for i in range(cg.HISTORY_SIZE + 2):
            cg.add_to_history("Fixy", f"entry {i}")
        history = list(cg.get_agent_history("Fixy"))
        assert "entry 0" not in history
        assert f"entry {cg.HISTORY_SIZE + 1}" in history

    def test_clear_single_agent(self):
        cg.add_to_history("Socrates", "something")
        cg.add_to_history("Athena", "something else")
        cg.clear_history("Socrates")
        assert len(cg.get_agent_history("Socrates")) == 0
        assert len(cg.get_agent_history("Athena")) == 1

    def test_clear_all_agents(self):
        for agent in ("Socrates", "Athena", "Fixy"):
            cg.add_to_history(agent, "x")
        cg.clear_history()
        for agent in ("Socrates", "Athena", "Fixy"):
            assert len(cg.get_agent_history(agent)) == 0

    def test_independent_histories_per_agent(self):
        cg.add_to_history("Socrates", "socrates text")
        cg.add_to_history("Athena", "athena text")
        assert "socrates text" not in cg.get_agent_history("Athena")
        assert "athena text" not in cg.get_agent_history("Socrates")

    def test_new_agent_starts_with_empty_history(self):
        assert len(cg.get_agent_history("BrandNewAgent")) == 0


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
        """After exhausting all instructions, the sequence restarts."""
        n = len(cg._NEW_ANGLE_INSTRUCTIONS)
        first_pass = [cg.get_new_angle_instruction() for _ in range(n)]
        second_pass = [cg.get_new_angle_instruction() for _ in range(n)]
        assert first_pass == second_pass

    def test_index_increments(self):
        cg._new_angle_index = 0
        cg.get_new_angle_instruction()
        assert cg._new_angle_index == 1


# ===========================================================================
# 7A.  Semantic false-positive reduction
# ===========================================================================


class TestSemanticFalsePositiveReduction:
    """Same-topic but differently-reasoned texts should not be over-flagged."""

    def test_same_topic_different_reasoning_not_flagged(self):
        """Two on-topic texts with distinct vocabulary are not circular."""
        topic_texts = [
            "free will emerges from the complexity of neural computation",
            "determinism holds that all events are causally necessitated",
            "compatibilism reconciles freedom with a causal universe",
        ]
        new_text = "libertarian free will posits agent causation beyond physics"
        with patch.object(cg, "_SEMANTIC_AVAILABLE", False):
            detected, score = cg.detect_semantic_repetition(new_text, topic_texts)
        # All texts are on-topic so avg is elevated, keeping delta low
        assert detected is False

    def test_delta_score_lower_than_raw_max_for_on_topic_history(self):
        """Delta scoring should return a score ≤ raw max Jaccard."""
        history = [
            "consciousness and its neural correlates remain controversial",
            "the hard problem of consciousness resists physicalist explanations",
            "integrated information theory proposes a mathematical measure of experience",
        ]
        text = "consciousness is not reducible to physical brain states"
        with patch.object(cg, "_SEMANTIC_AVAILABLE", False):
            _, delta = cg.detect_semantic_repetition(text, history)

        jaccards = [cg._jaccard(text, h) for h in history]
        assert delta <= max(jaccards)

    def test_truly_circular_text_still_flagged(self):
        """Even with delta scoring, genuinely identical text is flagged."""
        text = "consciousness emerges from neural patterns interactions"
        history = _make_identical_texts(3, text)
        with patch.object(cg, "_SEMANTIC_AVAILABLE", False):
            detected, _ = cg.detect_semantic_repetition(text, history)
        assert detected is True


# ===========================================================================
# 7B.  Rhetorical vs technical vocabulary
# ===========================================================================


class TestRhetoricalVsTechnicalVocabulary:
    """Technical terms alone should not strongly raise the structural score."""

    def test_pure_technical_text_has_zero_structural_score(self):
        text = (
            "The tradeoff between system architecture optimization "
            "and failure mode analysis is significant."
        )
        _, count = cg.detect_structural_templates(text)
        assert count == 0

    def test_rhetorical_opening_raises_structural_score(self):
        text = "Let us examine the issue on one hand and the other hand."
        detected, count = cg.detect_structural_templates(text)
        assert detected is True
        assert count >= 2

    def test_technical_terms_do_not_contribute_to_count(self):
        """Even with many technical terms, count stays zero."""
        text = (
            "Optimization, tradeoffs, architecture, failure modes, "
            "and system constraints are all technical considerations."
        )
        _, count = cg.detect_structural_templates(text)
        assert count == 0

    def test_mixed_technical_and_rhetorical_only_counts_rhetorical(self):
        """The structural count reflects only the rhetorical patterns."""
        text = (
            "Let us examine the tradeoff here. "
            "The optimization architecture is complex."
        )
        _, count = cg.detect_structural_templates(text)
        # Only "let us examine" is rhetorical; technical terms do not add to count
        assert count == 1


# ===========================================================================
# 7C.  Contamination leak detection
# ===========================================================================


class TestContaminationLeakDetection:
    """Specific leaked templates must be reliably caught."""

    def test_option_a_b_caught(self):
        text = "We face two paths: Option A leads to utility, Option B leads to virtue."
        detected, found = cg.detect_cross_topic_contamination(
            text, "ethics & responsibility"
        )
        assert detected is True
        assert "option a" in found or "option b" in found

    def test_scenario_a_b_caught(self):
        text = (
            "Scenario A achieves short-term goals. Scenario B achieves long-term goals."
        )
        detected, found = cg.detect_cross_topic_contamination(text, "AI alignment")
        assert detected is True
        assert "scenario a" in found or "scenario b" in found

    def test_forgiveness_caught(self):
        text = "Through forgiveness we reach a higher state of understanding."
        detected, found = cg.detect_cross_topic_contamination(
            text, "free will & determinism"
        )
        assert detected is True
        assert "forgiveness" in found

    def test_peace_and_harmony_caught(self):
        text = "We aspire to peace and harmony between reason and emotion."
        detected, found = cg.detect_cross_topic_contamination(
            text, "truth & epistemology"
        )
        assert detected is True
        assert "peace and harmony" in found

    def test_our_community_caught(self):
        text = "Our community should engage with these philosophical questions."
        detected, found = cg.detect_cross_topic_contamination(
            text, "consciousness & self-models"
        )
        assert detected is True
        assert "our community" in found

    def test_duplicated_prefix_detected_structurally(self):
        """Fixy: Fixy: duplicated prefix is caught by the structural guard."""
        text = "Fixy: Fixy: I need to note a structural repetition here."
        _, count = cg.detect_structural_templates(text)
        assert count >= 1

    def test_clean_on_topic_text_has_no_contamination(self):
        text = "Free will and determinism are traditional philosophical opponents."
        detected, found = cg.detect_cross_topic_contamination(
            text, "free will & determinism"
        )
        assert detected is False
        assert found == []


# ===========================================================================
# 7D.  Adaptive threshold
# ===========================================================================


class TestAdaptiveThreshold:
    """Threshold must grow with history size and be capped at 0.70."""

    def test_zero_history_threshold(self):
        assert cg.get_dynamic_threshold(0) == pytest.approx(0.55, abs=1e-6)

    def test_threshold_grows_with_history(self):
        t5 = cg.get_dynamic_threshold(5)
        t10 = cg.get_dynamic_threshold(10)
        assert t10 > t5

    def test_threshold_capped_at_070(self):
        assert cg.get_dynamic_threshold(100) == pytest.approx(0.70, abs=1e-6)
        assert cg.get_dynamic_threshold(200) == pytest.approx(0.70, abs=1e-6)

    def test_threshold_formula(self):
        for n in (0, 3, 5, 10, 15):
            expected = min(0.70, 0.55 + 0.01 * n)
            assert cg.get_dynamic_threshold(n) == pytest.approx(expected, abs=1e-9)

    def test_higher_threshold_means_fewer_false_positives(self):
        """A text that is circular at low threshold is not flagged at high threshold."""
        text = "Let us examine the fundamental tension on one hand and the other."
        # Force threshold low enough to flag
        result_low = cg.compute_circularity_score(text, "Socrates", threshold=0.0)
        # Force threshold high enough to not flag
        result_high = cg.compute_circularity_score(text, "Socrates", threshold=0.99)
        assert result_low.is_circular is True
        assert result_high.is_circular is False

    def test_dynamic_threshold_used_in_compute(self):
        """compute_circularity_score uses get_dynamic_threshold when threshold=None."""
        for hist_size in (0, 5, 10):
            cg.clear_history("TestAgent")
            for i in range(hist_size):
                cg.add_to_history("TestAgent", f"response {i}")
            text = "a plain neutral response"
            result = cg.compute_circularity_score(text, "TestAgent")
            expected_thr = cg.get_dynamic_threshold(hist_size)
            assert result.threshold == pytest.approx(expected_thr, abs=1e-9)


# ===========================================================================
# 7E.  First-turn-after-topic-change leniency
# ===========================================================================


class TestFirstTurnAfterTopicChange:

    def test_first_turn_score_is_reduced(self):
        """Score on the first turn after topic change is multiplied by FIRST_TURN_SCORE_FACTOR."""
        text = "Let us examine the fundamental tension on one hand and the other."
        # Get a baseline score without the leniency flag
        result_normal = cg.compute_circularity_score(text, "Socrates", threshold=0.0)
        # Get the score with the leniency flag
        result_first = cg.compute_circularity_score(
            text, "Socrates", threshold=0.0, first_turn_after_topic_change=True
        )
        assert result_first.score < result_normal.score
        assert result_first.score == pytest.approx(
            result_normal.score * cg.FIRST_TURN_SCORE_FACTOR, abs=1e-6
        )

    def test_first_turn_less_likely_to_be_flagged(self):
        """A borderline-circular response is not flagged on the first turn after topic change."""
        # Use a text that scores just above the dynamic threshold
        text = "Let us examine the fundamental tension on one hand and the other."

        # Find the score without leniency for an empty history
        result_normal = cg.compute_circularity_score(text, "A", threshold=None)
        # Apply leniency — score must be lower
        result_lenient = cg.compute_circularity_score(
            text, "A", threshold=None, first_turn_after_topic_change=True
        )
        assert result_lenient.score < result_normal.score

    def test_no_leniency_when_flag_is_false(self):
        """Without the flag the score must be unchanged (FIRST_TURN_SCORE_FACTOR not applied)."""
        text = "Let us examine the fundamental tension on one hand and the other."
        r1 = cg.compute_circularity_score(text, "B", threshold=0.0)
        r2 = cg.compute_circularity_score(
            text, "B", threshold=0.0, first_turn_after_topic_change=False
        )
        assert r1.score == pytest.approx(r2.score, abs=1e-9)


# ===========================================================================
# 7F.  CircularityResult includes threshold and detailed sub-scores
# ===========================================================================


class TestCircularityResultFields:

    def test_threshold_field_present(self):
        result = cg.compute_circularity_score("some text", "Socrates")
        assert hasattr(result, "threshold")
        assert isinstance(result.threshold, float)

    def test_threshold_matches_explicit_value(self):
        result = cg.compute_circularity_score("some text", "Socrates", threshold=0.63)
        assert result.threshold == pytest.approx(0.63, abs=1e-6)

    def test_semantic_score_is_delta_not_raw_max(self):
        """semantic_score is the delta score, not raw max similarity."""
        text = "identical text" * 5
        for _ in range(5):
            cg.add_to_history("Fixy", text)

        with patch.object(cg, "_SEMANTIC_AVAILABLE", False):
            result = cg.compute_circularity_score(text, "Fixy")

        # delta = max(0, 1.0 - 1.0*0.5) = 0.5
        assert result.semantic_score == pytest.approx(0.5, abs=0.05)
        # NOT 1.0 (which would be the raw max Jaccard)
        assert result.semantic_score < 1.0

    def test_all_fields_have_correct_types(self):
        result = cg.compute_circularity_score(
            "Let us examine this question.", "Athena", topic="truth & epistemology"
        )
        assert isinstance(result.is_circular, bool)
        assert isinstance(result.score, float)
        assert isinstance(result.semantic_score, float)
        assert isinstance(result.template_count, int)
        assert isinstance(result.contamination_phrases, list)
        assert isinstance(result.threshold, float)
        assert isinstance(result.reasons, list)

    def test_score_is_in_valid_range(self):
        result = cg.compute_circularity_score("plain text here", "Socrates")
        assert 0.0 <= result.score <= 1.0

    def test_is_circular_consistent_with_score_and_threshold(self):
        """is_circular == (score >= threshold) must always hold."""
        for threshold_val in (0.0, 0.3, 0.5, 0.7, 0.99):
            result = cg.compute_circularity_score(
                "Let us examine the fundamental tension on one hand.",
                "Socrates",
                threshold=threshold_val,
            )
            assert result.is_circular == (result.score >= threshold_val)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s", "--override-ini=addopts="])

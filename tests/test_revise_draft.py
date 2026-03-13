# tests/test_revise_draft.py
"""
Tests for the revise_draft() post-generation revision layer.

Validates:
  1. Filler phrase removal (academic / LLM boilerplate stripped).
  2. Near-duplicate sentence deduplication (overlap >= 0.70 removed).
  3. Agent-specific voice guards applied correctly.
  4. Sentence-count enforcement (max 4 sentences).
  5. Safe fallback: blank / very short input returned unchanged.
  6. Raw draft stored on _last_raw_draft; speak() returns revised text.
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

from Entelgia_production_meta import (
    revise_draft,
    _split_sentences,
    _sentence_overlap,
)


# ---------------------------------------------------------------------------
# _split_sentences
# ---------------------------------------------------------------------------


class TestSplitSentences:
    def test_single_sentence(self):
        assert _split_sentences("Hello world.") == ["Hello world."]

    def test_multiple_sentences(self):
        result = _split_sentences("One thing. Another thing! A third?")
        assert result == ["One thing.", "Another thing!", "A third?"]

    def test_empty_string(self):
        assert _split_sentences("") == []

    def test_no_terminal_punctuation(self):
        result = _split_sentences("Just a fragment")
        assert result == ["Just a fragment"]


# ---------------------------------------------------------------------------
# _sentence_overlap
# ---------------------------------------------------------------------------


class TestSentenceOverlap:
    def test_identical_sentences(self):
        assert _sentence_overlap("the cat sat", "the cat sat") == pytest.approx(1.0)

    def test_no_overlap(self):
        assert _sentence_overlap("apple orange", "dog cat fish") == pytest.approx(0.0)

    def test_partial_overlap(self):
        score = _sentence_overlap("the cat sat on the mat", "the cat ran away")
        assert 0.0 < score < 1.0

    def test_empty_strings(self):
        assert _sentence_overlap("", "") == pytest.approx(0.0)
        assert _sentence_overlap("hello", "") == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# revise_draft – filler removal
# ---------------------------------------------------------------------------


class TestFillerRemoval:
    def test_removes_it_is_important_to_note(self):
        text = "It is important to note that consciousness is complex."
        result = revise_draft(text, "Socrates")
        assert "It is important to note" not in result
        assert "consciousness" in result

    def test_removes_in_conclusion(self):
        text = "In conclusion, the argument holds. This is significant."
        result = revise_draft(text, "Athena")
        assert "In conclusion" not in result

    def test_removes_furthermore(self):
        text = "The mind is vast. Furthermore, it is infinite."
        result = revise_draft(text, "Fixy")
        assert "Furthermore" not in result

    def test_removes_it_should_be_noted(self):
        text = "It should be noted that time is limited."
        result = revise_draft(text, "Socrates")
        assert "It should be noted" not in result
        assert "time" in result

    def test_removes_firstly_secondly(self):
        text = "Firstly, we exist. Secondly, we think. Thirdly, we question."
        result = revise_draft(text, "Socrates")
        assert "Firstly" not in result
        assert "Secondly" not in result
        assert "Thirdly" not in result

    def test_preserves_core_content(self):
        text = "In other words, being precedes essence."
        result = revise_draft(text, "Athena")
        assert "being" in result
        assert "essence" in result


# ---------------------------------------------------------------------------
# revise_draft – deduplication
# ---------------------------------------------------------------------------


class TestDeduplication:
    def test_removes_near_duplicate_sentence(self):
        text = (
            "The self is constructed through experience. "
            "The self is built through experience. "
            "Meaning emerges from encounter."
        )
        result = revise_draft(text, "Athena")
        sentences = _split_sentences(result)
        # Both near-duplicates should collapse to one; final sentence preserved
        assert len(sentences) <= 2

    def test_keeps_distinct_sentences(self):
        text = (
            "Consciousness is hard to define. "
            "Memory shapes identity. "
            "Language mediates thought."
        )
        result = revise_draft(text, "Socrates")
        sentences = _split_sentences(result)
        assert len(sentences) == 3

    def test_identical_sentences_deduplicated(self):
        text = "Being precedes essence. Being precedes essence."
        result = revise_draft(text, "Athena")
        sentences = _split_sentences(result)
        assert len(sentences) == 1


# ---------------------------------------------------------------------------
# revise_draft – voice guards
# ---------------------------------------------------------------------------


class TestVoiceGuards:
    def test_socrates_strips_therefore_at_start(self):
        text = "Therefore, truth is unknowable."
        result = revise_draft(text, "Socrates")
        assert not result.lower().startswith("therefore")

    def test_socrates_strips_clearly_at_start(self):
        text = "Clearly, the argument is sound."
        result = revise_draft(text, "Socrates")
        assert not result.lower().startswith("clearly")

    def test_fixy_strips_perhaps_at_start(self):
        text = "Perhaps the loop is caused by drift."
        result = revise_draft(text, "Fixy")
        assert not result.lower().startswith("perhaps")

    def test_athena_strips_fact_label(self):
        text = "Fact: systems self-organise."
        result = revise_draft(text, "Athena")
        assert not result.lower().startswith("fact:")

    def test_no_guard_for_unknown_agent(self):
        text = "Therefore, this holds true."
        result = revise_draft(text, "UnknownAgent")
        # No guard applied; content preserved
        assert "holds true" in result


# ---------------------------------------------------------------------------
# revise_draft – sentence-count cap
# ---------------------------------------------------------------------------


class TestSentenceCap:
    def test_five_sentences_trimmed_to_four(self):
        text = "One. Two. Three. Four. Five."
        result = revise_draft(text, "Socrates")
        sentences = _split_sentences(result)
        assert len(sentences) <= 4

    def test_two_sentences_unchanged_count(self):
        text = "Existence is relational. Meaning arises between beings."
        result = revise_draft(text, "Athena")
        sentences = _split_sentences(result)
        assert len(sentences) == 2


# ---------------------------------------------------------------------------
# revise_draft – edge cases / fallback
# ---------------------------------------------------------------------------


class TestEdgeCases:
    def test_empty_string_returned_unchanged(self):
        assert revise_draft("", "Socrates") == ""

    def test_very_short_text_returned_unchanged(self):
        assert revise_draft("Hi.", "Fixy") == "Hi."

    def test_result_ends_with_punctuation(self):
        text = "The question is whether being can be known"
        result = revise_draft(text, "Socrates")
        assert result[-1] in ".!?"

    def test_text_already_punctuated_not_double_punctuated(self):
        text = "What is the nature of time?"
        result = revise_draft(text, "Socrates")
        assert not result.endswith("?.")

    def test_all_filler_not_emptied(self):
        # Edge: even after stripping filler, content should survive
        text = "It is important to note that the mind is real."
        result = revise_draft(text, "Athena")
        assert result.strip() != ""
        assert "mind" in result


# ---------------------------------------------------------------------------
# revise_draft – _last_raw_draft attribute
# ---------------------------------------------------------------------------


class TestRawDraftAttribute:
    """Verify that Agent stores the raw draft and returns revised text."""

    def _make_agent(self):
        """Build a minimal Agent with mocked dependencies."""
        from unittest.mock import MagicMock
        from Entelgia_production_meta import (
            Agent,
            Config,
            ConsciousCore,
            EmotionCore,
            LanguageCore,
        )

        cfg = Config()
        llm = MagicMock()
        # revise_draft may differ from raw if filler is present
        raw = "It is important to note that reality is constructed. Furthermore, it shifts."
        llm.generate.return_value = raw

        memory = MagicMock()
        memory.stm_load.return_value = []
        memory.ltm_recent.return_value = []
        memory.get_agent_state.return_value = {
            "id": 0,
            "ego": 0.5,
            "superego": 0.3,
            "id_drive": 0.5,
        }
        emotion = MagicMock(spec=EmotionCore)
        emotion.infer.return_value = ("neutral", 0.3)
        behavior = MagicMock()
        language = LanguageCore()
        conscious = ConsciousCore()

        agent = Agent(
            name="Socrates",
            model="test-model",
            color="",
            llm=llm,
            memory=memory,
            emotion=emotion,
            behavior=behavior,
            language=language,
            conscious=conscious,
            persona="Test",
            cfg=cfg,
        )
        return agent, cfg, raw

    def test_last_raw_draft_populated_after_speak(self):
        import Entelgia_production_meta as _meta
        from unittest.mock import patch

        agent, cfg, raw = self._make_agent()
        with patch.object(_meta, "CFG", cfg):
            agent.speak("What is truth?", [])
        # _last_raw_draft should hold the pre-revision text
        assert agent._last_raw_draft == raw

    def test_speak_returns_revised_not_raw(self):
        import Entelgia_production_meta as _meta
        from unittest.mock import patch

        agent, cfg, raw = self._make_agent()
        with patch.object(_meta, "CFG", cfg):
            result = agent.speak("What is truth?", [])
        # Revised text must not contain the filler phrase
        assert "It is important to note" not in result
        assert "Furthermore" not in result

    def test_raw_draft_differs_from_revised(self):
        import Entelgia_production_meta as _meta
        from unittest.mock import patch

        agent, cfg, raw = self._make_agent()
        with patch.object(_meta, "CFG", cfg):
            result = agent.speak("What is truth?", [])
        # The raw draft (with filler) should be different from the revised output
        assert agent._last_raw_draft != result

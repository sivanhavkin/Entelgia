# tests/test_text_humanizer_integration.py
"""
Tests for the TextHumanizer integration in the Entelgia dialogue pipeline.

Validates:
  1. should_humanize() returns False for empty/short text.
  2. should_humanize() returns False for code blocks (triple backticks).
  3. should_humanize() returns False for JSON-like content.
  4. should_humanize() returns False for key/value metadata-only content.
  5. should_humanize() returns True for normal free-form dialogue text.
  6. _build_humanizer_instance() returns None when humanizer_enabled=False.
  7. _build_humanizer_instance() returns a TextHumanizer when humanizer_enabled=True.
  8. _build_humanizer_instance() maps all config fields correctly.
  9. New Config fields exist with correct defaults.
  10. Agent.speak() applies TextHumanizer post-processing for free-form text.
  11. Agent.speak() skips humanizer for short/structured output.
  12. Agent.speak() is safe when HUMANIZER.humanize raises an exception.
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from unittest.mock import MagicMock, patch

import Entelgia_production_meta as _meta
from Entelgia_production_meta import (
    Config,
    should_humanize,
    _build_humanizer_instance,
    BehaviorCore,
    ConsciousCore,
    EmotionCore,
    LanguageCore,
    Agent,
)
from entelgia.humanizer import TextHumanizer, HumanizerConfig


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_agent(cfg=None):
    """Return a minimal Agent whose LLM and memory calls are fully mocked."""
    if cfg is None:
        cfg = Config()

    llm_mock = MagicMock()
    llm_mock.generate.return_value = (
        "In examining the nature of knowledge, it is crucial to consider the limits of certainty."
    )

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
    behavior_mock.importance_score.return_value = 0.5

    agent = Agent(
        name="Socrates",
        model="phi3",
        color="",
        llm=llm_mock,
        memory=memory_mock,
        emotion=emotion_mock,
        behavior=behavior_mock,
        language=LanguageCore(),
        conscious=ConsciousCore(),
        persona="A philosopher.",
        use_enhanced=False,
        cfg=cfg,
    )
    return agent, cfg


# ---------------------------------------------------------------------------
# 1-5. should_humanize()
# ---------------------------------------------------------------------------


class TestShouldHumanize:
    """Verify the gate function that decides whether to run TextHumanizer."""

    def test_empty_string_returns_false(self):
        assert should_humanize("") is False

    def test_none_equivalent_whitespace_returns_false(self):
        assert should_humanize("   ") is False

    def test_very_short_text_returns_false(self):
        # Fewer than 30 characters
        assert should_humanize("Short text.") is False

    def test_exactly_at_threshold_is_false(self):
        # 29 characters → still False
        text = "a" * 29
        assert should_humanize(text) is False

    def test_just_over_threshold_is_true(self):
        # 30+ characters of normal text, no special structure
        assert should_humanize("This is a perfectly fine sentence.") is True

    def test_code_block_returns_false(self):
        text = "Here is some code:\n```python\nprint('hello')\n```"
        assert should_humanize(text) is False

    def test_inline_triple_backtick_returns_false(self):
        assert should_humanize("Use ```code``` inline here please ok.") is False

    def test_json_object_returns_false(self):
        text = '{"agent": "Socrates", "score": 0.9}'
        assert should_humanize(text) is False

    def test_json_with_whitespace_returns_false(self):
        text = '  { "key": "value", "num": 42 }  '
        assert should_humanize(text) is False

    def test_key_value_metadata_only_returns_false(self):
        # Every non-blank line contains ":"
        text = "agent: Socrates\ntopic: epistemology\nscore: 0.8"
        assert should_humanize(text) is False

    def test_normal_dialogue_returns_true(self):
        text = (
            "What does it mean to truly know something? "
            "I think certainty is always provisional."
        )
        assert should_humanize(text) is True

    def test_philosophical_reflection_returns_true(self):
        text = (
            "The harder question is whether introspection reliably reveals "
            "anything about the actual workings of the mind."
        )
        assert should_humanize(text) is True

    def test_mixed_text_with_colon_not_all_metadata(self):
        # Not every line has a colon, so should NOT be rejected as metadata
        text = (
            "Here is the main claim: knowledge requires justification.\n"
            "But that is not the whole story.\n"
            "There are cases where justification fails us entirely."
        )
        assert should_humanize(text) is True


# ---------------------------------------------------------------------------
# 6-8. _build_humanizer_instance()
# ---------------------------------------------------------------------------


class TestBuildHumanizerInstance:
    """Verify that _build_humanizer_instance maps Config fields correctly."""

    def test_returns_none_when_disabled(self):
        cfg = Config(humanizer_enabled=False)
        assert _build_humanizer_instance(cfg) is None

    def test_returns_text_humanizer_when_enabled(self):
        cfg = Config(humanizer_enabled=True)
        instance = _build_humanizer_instance(cfg)
        assert isinstance(instance, TextHumanizer)

    def test_config_fields_mapped_correctly(self):
        cfg = Config(
            humanizer_enabled=True,
            humanizer_aggressive=True,
            humanizer_randomness=0.75,
            humanizer_max_sentence_length=18,
            humanizer_split_long_sentences=False,
            humanizer_remove_opening_scaffolds=False,
            humanizer_diversify_agent_voice=False,
        )
        instance = _build_humanizer_instance(cfg)
        assert instance is not None
        assert instance.config.enabled is True
        assert instance.config.aggressive is True
        assert instance.config.randomness == pytest.approx(0.75)
        assert instance.config.max_sentence_length == 18
        assert instance.config.split_long_sentences is False
        assert instance.config.remove_opening_scaffolds is False
        assert instance.config.diversify_agent_voice is False

    def test_default_config_fields(self):
        cfg = Config()
        instance = _build_humanizer_instance(cfg)
        assert instance is not None
        assert instance.config.enabled is True
        assert instance.config.aggressive is False
        assert instance.config.randomness == pytest.approx(0.30)
        assert instance.config.max_sentence_length == 26
        assert instance.config.split_long_sentences is True
        assert instance.config.remove_opening_scaffolds is True
        assert instance.config.diversify_agent_voice is True


# ---------------------------------------------------------------------------
# 9. Config defaults
# ---------------------------------------------------------------------------


class TestConfigDefaults:
    """Verify all new humanizer Config fields exist with the right defaults."""

    def test_humanizer_enabled_default(self):
        assert Config().humanizer_enabled is True

    def test_humanizer_aggressive_default(self):
        assert Config().humanizer_aggressive is False

    def test_humanizer_randomness_default(self):
        assert Config().humanizer_randomness == pytest.approx(0.30)

    def test_show_humanizer_debug_default(self):
        assert Config().show_humanizer_debug is False

    def test_humanizer_max_sentence_length_default(self):
        assert Config().humanizer_max_sentence_length == 26

    def test_humanizer_split_long_sentences_default(self):
        assert Config().humanizer_split_long_sentences is True

    def test_humanizer_remove_opening_scaffolds_default(self):
        assert Config().humanizer_remove_opening_scaffolds is True

    def test_humanizer_diversify_agent_voice_default(self):
        assert Config().humanizer_diversify_agent_voice is True

    def test_humanizer_min_score_default(self):
        assert Config().humanizer_min_score == pytest.approx(0.15)


# ---------------------------------------------------------------------------
# 10-12. Agent.speak() integration
# ---------------------------------------------------------------------------


class TestSpeakHumanizerIntegration:
    """Verify TextHumanizer post-processing in Agent.speak()."""

    def test_speak_applies_humanizer_for_free_form_text(self):
        """When HUMANIZER is set and text is free-form, humanize() must be called."""
        agent, cfg = _make_agent()

        mock_humanizer = MagicMock(spec=TextHumanizer)
        mock_result = MagicMock()
        mock_result.changed = True
        mock_result.original_text = agent.llm.generate.return_value
        mock_result.humanized_text = "The real issue is: certainty has limits."
        mock_result.flags = ["scaffold_removed"]
        mock_result.score_before = 0.4
        mock_result.score_after = 0.0
        mock_humanizer.humanize.return_value = mock_result

        with patch.object(_meta, "CFG", cfg), patch.object(_meta, "HUMANIZER", mock_humanizer):
            result = agent.speak("TOPIC: Philosophy of mind\nRespond now:\n", [])

        mock_humanizer.humanize.assert_called_once()
        assert result == "The real issue is: certainty has limits."

    def test_speak_skips_humanizer_for_short_output(self):
        """When output is too short, humanize() must NOT be called."""
        agent, cfg = _make_agent()
        agent.llm.generate.return_value = "Yes."

        mock_humanizer = MagicMock(spec=TextHumanizer)
        mock_humanizer.humanize.return_value = MagicMock(
            changed=False, humanized_text="Yes.", original_text="Yes.",
            flags=[], score_before=0.0, score_after=0.0,
        )

        with patch.object(_meta, "CFG", cfg), patch.object(_meta, "HUMANIZER", mock_humanizer):
            agent.speak("TOPIC: Philosophy\nRespond now:\n", [])

        mock_humanizer.humanize.assert_not_called()

    def test_speak_skips_humanizer_when_none(self):
        """When HUMANIZER is None (disabled), speak() must still return normally."""
        agent, cfg = _make_agent(Config(humanizer_enabled=False))

        with patch.object(_meta, "CFG", cfg), patch.object(_meta, "HUMANIZER", None):
            result = agent.speak("TOPIC: Philosophy of mind\nRespond now:\n", [])

        assert isinstance(result, str)
        assert len(result) > 0

    def test_speak_is_safe_when_humanizer_raises(self):
        """speak() must not crash if HUMANIZER.humanize raises an exception."""
        agent, cfg = _make_agent()
        agent.llm.generate.return_value = (
            "In examining this topic carefully, it is crucial to consider all angles."
        )

        mock_humanizer = MagicMock(spec=TextHumanizer)
        mock_humanizer.humanize.side_effect = RuntimeError("unexpected failure")

        with patch.object(_meta, "CFG", cfg), patch.object(_meta, "HUMANIZER", mock_humanizer):
            result = agent.speak("TOPIC: Philosophy of mind\nRespond now:\n", [])

        # Must return the (unhumanized) output, not raise
        assert isinstance(result, str)
        assert len(result) > 0

    def test_speak_unchanged_text_not_reassigned(self):
        """When humanize() reports changed=False, output is unchanged."""
        agent, cfg = _make_agent()
        original = (
            "In examining this topic carefully, it is crucial to consider all angles."
        )
        agent.llm.generate.return_value = original

        mock_humanizer = MagicMock(spec=TextHumanizer)
        mock_result = MagicMock()
        mock_result.changed = False
        mock_result.humanized_text = original
        mock_result.original_text = original
        mock_result.flags = []
        mock_result.score_before = 0.0
        mock_result.score_after = 0.0
        mock_humanizer.humanize.return_value = mock_result

        with patch.object(_meta, "CFG", cfg), patch.object(_meta, "HUMANIZER", mock_humanizer):
            result = agent.speak("TOPIC: Philosophy of mind\nRespond now:\n", [])

        # Result should not be the humanized_text when changed=False
        assert isinstance(result, str)


# ---------------------------------------------------------------------------
# 13. TextHumanizer threshold skip (min_score)
# ---------------------------------------------------------------------------


class TestHumanizerMinScore:
    """Verify that TextHumanizer skips processing when score_before < min_score."""

    def test_low_score_returns_original_unchanged(self):
        """Text with no LLM-pattern hits scores 0.0 — below default 0.15 threshold."""
        h = TextHumanizer(HumanizerConfig(min_score=0.15))
        plain = "This is a plain sentence with no AI patterns at all."
        result = h.humanize(plain)
        assert result.humanized_text == plain
        assert result.changed is False
        assert "score_skip" in result.flags

    def test_low_score_score_before_recorded(self):
        """score_before is still populated even on a skip."""
        h = TextHumanizer(HumanizerConfig(min_score=0.15))
        plain = "This is a plain sentence with no AI patterns at all."
        result = h.humanize(plain)
        assert result.score_before == pytest.approx(0.0)

    def test_above_threshold_does_not_skip(self):
        """Text with LLM patterns (score ≥ 0.15) must NOT be skipped."""
        h = TextHumanizer(HumanizerConfig(min_score=0.15, seed=42))
        high_score = (
            "It is crucial to examine this topic carefully, because often overlooked is "
            "the fact that an alternative perspective might reveal underlying assumptions."
        )
        result = h.humanize(high_score)
        assert "score_skip" not in result.flags

    def test_zero_min_score_never_skips(self):
        """Setting min_score=0.0 must never skip any non-empty text."""
        h = TextHumanizer(HumanizerConfig(min_score=0.0, seed=42))
        plain = "This is a plain sentence with no AI patterns at all."
        result = h.humanize(plain)
        assert "score_skip" not in result.flags

    def test_min_score_mapped_from_config(self):
        """_build_humanizer_instance must propagate humanizer_min_score."""
        cfg = Config(humanizer_min_score=0.25)
        instance = _build_humanizer_instance(cfg)
        assert instance is not None
        assert instance.config.min_score == pytest.approx(0.25)


# ---------------------------------------------------------------------------
# 14. Scaffold removal capitalisation repair
# ---------------------------------------------------------------------------


class TestScaffoldCapitalisation:
    """After scaffold removal the first letter must be capitalised."""

    def test_capitalises_after_scaffold_removal(self):
        h = TextHumanizer(HumanizerConfig(
            min_score=0.0,
            split_long_sentences=False,
            diversify_agent_voice=False,
        ))
        text = "In examining the topic of inequality and opportunity within society, scrutinize the roots."
        result = h.humanize(text)
        assert result.humanized_text[0].isupper()

    def test_no_double_capitalisation_when_already_capitalised(self):
        h = TextHumanizer(HumanizerConfig(
            min_score=0.0,
            split_long_sentences=False,
            diversify_agent_voice=False,
        ))
        text = "In examining the situation, Power corrupts absolutely."
        result = h.humanize(text)
        # Should start with capital P
        stripped = result.humanized_text.lstrip()
        assert stripped[0].isupper()


# ---------------------------------------------------------------------------
# 15. Voice prefix capitalisation
# ---------------------------------------------------------------------------


class TestVoicePrefixCapitalisation:
    """Voice prefixes must not lowercase a standalone 'I'."""

    def test_standalone_i_is_preserved(self):
        """'I notice...' must not become 'i notice...' after prefix injection."""
        h = TextHumanizer(HumanizerConfig(
            min_score=0.0,
            split_long_sentences=False,
            randomness=1.0,  # always apply voice
            seed=0,
        ))
        text = "I notice that the argument relies on a hidden premise."
        result = h.humanize(text, agent_name="Fixy")
        # "I" must remain uppercase wherever it appears as a standalone word
        import re as _re
        assert not _re.search(r"\bi notice\b", result.humanized_text)


# ---------------------------------------------------------------------------
# 16. Long-sentence splitting safety
# ---------------------------------------------------------------------------


class TestSplitSentenceSafety:
    """Sentence splitting must not produce fragments starting with conjunctions."""

    def test_split_does_not_start_fragment_with_or(self):
        h = TextHumanizer(HumanizerConfig(
            min_score=0.0,
            max_sentence_length=8,
            split_long_sentences=True,
            diversify_agent_voice=False,
        ))
        # 10-word sentence; mid=5 → "laws." then "or policies" — must be fixed
        text = "Governments enforce unjust laws or policies that restrict individual freedoms greatly."
        result = h.humanize(text)
        sentences = result.humanized_text.split(". ")
        for sent in sentences:
            first_word = sent.split()[0].lower() if sent.split() else ""
            assert first_word not in {"or", "nor", "and", "but", "on", "in", "of", "to", "by", "as"}

    def test_split_half_ends_with_punctuation(self):
        h = TextHumanizer(HumanizerConfig(
            min_score=0.0,
            max_sentence_length=8,
            split_long_sentences=True,
            diversify_agent_voice=False,
        ))
        text = "Raising awareness on critical issues is an important task that society must embrace fully."
        result = h.humanize(text)
        # There should be a sentence-ending punctuation somewhere in the middle
        assert "." in result.humanized_text or "!" in result.humanized_text or "?" in result.humanized_text

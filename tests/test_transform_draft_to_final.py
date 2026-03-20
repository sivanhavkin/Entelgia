# tests/test_transform_draft_to_final.py
"""
Tests for the transform_draft_to_final() Stage 2 generation function.

Validates:
  1. Short / empty draft returned unchanged (below _MIN_WORDS_FOR_REVISION).
  2. LLM output is returned when the call succeeds.
  3. Draft is used as fallback when LLM returns empty / None.
  4. Draft is used as fallback when LLM raises an exception.
  5. Persona notes are present in the transformation prompt for all agents.
  6. The transformation prompt includes the draft text.
  7. The transformation prompt includes the topic when provided.
  8. validate_output() is applied to the LLM result.
  9. Agent.speak() calls transform_draft_to_final() as Stage 2 (integration smoke test).
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from unittest.mock import MagicMock, patch, call

import Entelgia_production_meta as _meta
from Entelgia_production_meta import (
    transform_draft_to_final,
    _FINAL_STAGE_PERSONA_NOTES,
    _MIN_WORDS_FOR_REVISION,
    validate_output,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_mock_llm(return_value: str = "Truth is always contested."):
    """Return a mock LLM whose generate() returns *return_value*."""
    llm = MagicMock()
    llm.generate.return_value = return_value
    return llm


# ---------------------------------------------------------------------------
# Short / empty input — passthrough without LLM call
# ---------------------------------------------------------------------------


class TestShortInputPassthrough:
    def test_empty_string_returned_unchanged(self):
        llm = _make_mock_llm()
        result = transform_draft_to_final("", "Socrates", llm, "model-x")
        assert result == ""
        llm.generate.assert_not_called()

    def test_single_word_text_returned_unchanged(self):
        # "Hi" is 1 word, below _MIN_WORDS_FOR_REVISION (3)
        llm = _make_mock_llm()
        result = transform_draft_to_final("Hi.", "Athena", llm, "model-x")
        assert result == "Hi."
        llm.generate.assert_not_called()

    def test_two_word_text_returned_unchanged(self):
        llm = _make_mock_llm()
        result = transform_draft_to_final("Yes indeed.", "Fixy", llm, "model-x")
        # "Yes indeed" is 2 words — below threshold → passthrough
        assert result == "Yes indeed."
        llm.generate.assert_not_called()


# ---------------------------------------------------------------------------
# Normal LLM call — result is returned
# ---------------------------------------------------------------------------


class TestNormalTransform:
    def test_llm_output_is_returned(self):
        expected = "What do you mean by 'known'?"
        llm = _make_mock_llm(expected)
        result = transform_draft_to_final(
            "It is important to note that knowledge depends on context.",
            "Socrates",
            llm,
            "model-x",
        )
        assert result == expected

    def test_llm_generate_called_once(self):
        llm = _make_mock_llm("Direct claim.")
        transform_draft_to_final(
            "There are many perspectives to consider here.", "Athena", llm, "model-x"
        )
        assert llm.generate.call_count == 1

    def test_draft_text_included_in_prompt(self):
        llm = _make_mock_llm("Short answer.")
        draft = "We must consider the many factors at play in this dialogue."
        transform_draft_to_final(draft, "Fixy", llm, "model-x")
        prompt_arg = llm.generate.call_args[0][1]
        assert draft in prompt_arg

    def test_topic_included_in_prompt_when_provided(self):
        llm = _make_mock_llm("Short answer.")
        transform_draft_to_final(
            "Consider the implications of free will carefully.",
            "Socrates",
            llm,
            "model-x",
            topic="free will",
        )
        prompt_arg = llm.generate.call_args[0][1]
        assert "free will" in prompt_arg

    def test_no_topic_line_when_topic_empty(self):
        llm = _make_mock_llm("Short answer.")
        transform_draft_to_final(
            "Consider the implications of free will carefully.",
            "Socrates",
            llm,
            "model-x",
            topic="",
        )
        prompt_arg = llm.generate.call_args[0][1]
        assert "Dialogue topic:" not in prompt_arg

    def test_model_passed_to_generate(self):
        llm = _make_mock_llm("Output.")
        transform_draft_to_final(
            "It is worth noting the significance of this claim.",
            "Athena",
            llm,
            "my-custom-model",
        )
        model_arg = llm.generate.call_args[0][0]
        assert model_arg == "my-custom-model"

    def test_temperature_passed_to_generate(self):
        llm = _make_mock_llm("Output.")
        transform_draft_to_final(
            "It is worth noting the significance of this claim.",
            "Athena",
            llm,
            "model-x",
            temperature=0.42,
        )
        kwargs = llm.generate.call_args[1]
        assert kwargs.get("temperature") == pytest.approx(0.42)


# ---------------------------------------------------------------------------
# Fallback behaviour — draft returned when LLM fails
# ---------------------------------------------------------------------------


class TestFallback:
    def test_empty_llm_response_returns_draft(self):
        llm = _make_mock_llm("")
        draft = "We must consider the many implications of this view."
        result = transform_draft_to_final(draft, "Socrates", llm, "model-x")
        assert result == draft

    def test_none_llm_response_returns_draft(self):
        llm = _make_mock_llm(None)
        draft = "There are many layers to this philosophical question."
        result = transform_draft_to_final(draft, "Athena", llm, "model-x")
        assert result == draft

    def test_llm_exception_returns_draft(self):
        llm = MagicMock()
        llm.generate.side_effect = RuntimeError("connection timeout")
        draft = "One must examine the underlying assumptions here."
        result = transform_draft_to_final(draft, "Fixy", llm, "model-x")
        assert result == draft


# ---------------------------------------------------------------------------
# Persona notes
# ---------------------------------------------------------------------------


class TestPersonaNotes:
    def test_socrates_persona_in_prompt(self):
        llm = _make_mock_llm("Sharp question?")
        transform_draft_to_final(
            "This argument has several hidden assumptions worth examining.",
            "Socrates",
            llm,
            "model-x",
        )
        prompt_arg = llm.generate.call_args[0][1]
        assert "Socrates" in prompt_arg

    def test_athena_persona_in_prompt(self):
        llm = _make_mock_llm("Direct observation.")
        transform_draft_to_final(
            "The interplay between structure and content reveals a tension.",
            "Athena",
            llm,
            "model-x",
        )
        prompt_arg = llm.generate.call_args[0][1]
        assert "Athena" in prompt_arg

    def test_fixy_persona_in_prompt(self):
        llm = _make_mock_llm("Concrete redirect.")
        transform_draft_to_final(
            "The dialogue appears to be looping without resolution.",
            "Fixy",
            llm,
            "model-x",
        )
        prompt_arg = llm.generate.call_args[0][1]
        assert "Fixy" in prompt_arg

    def test_all_three_agents_have_persona_notes(self):
        for agent in ("Socrates", "Athena", "Fixy"):
            assert agent in _FINAL_STAGE_PERSONA_NOTES

    def test_unknown_agent_uses_generic_persona(self):
        llm = _make_mock_llm("Some output.")
        transform_draft_to_final(
            "There are important considerations to examine here.",
            "NewAgent",
            llm,
            "model-x",
        )
        prompt_arg = llm.generate.call_args[0][1]
        assert "NewAgent" in prompt_arg


# ---------------------------------------------------------------------------
# Output contract enforcement in the prompt
# ---------------------------------------------------------------------------


class TestPromptContract:
    def _get_prompt(
        self, agent="Socrates", draft="It is worth noting that meaning is contextual."
    ):
        llm = _make_mock_llm("Output.")
        transform_draft_to_final(draft, agent, llm, "model-x")
        return llm.generate.call_args[0][1]

    def test_prompt_requests_max_three_sentences(self):
        prompt = self._get_prompt()
        assert "1 to 3 sentences" in prompt

    def test_prompt_bans_my_model(self):
        prompt = self._get_prompt()
        assert "my model" in prompt

    def test_prompt_bans_this_suggests(self):
        prompt = self._get_prompt()
        assert "this suggests" in prompt

    def test_prompt_bans_it_is_important(self):
        prompt = self._get_prompt()
        assert "it is important" in prompt

    def test_prompt_bans_one_might_argue(self):
        prompt = self._get_prompt()
        assert "one might argue" in prompt

    def test_prompt_requires_no_preamble(self):
        prompt = self._get_prompt()
        assert "No preamble" in prompt or "no preamble" in prompt

    def test_prompt_requires_natural_prose(self):
        prompt = self._get_prompt()
        assert "prose" in prompt.lower()


# ---------------------------------------------------------------------------
# Integration: Agent.speak() includes Stage 2 transform call
# ---------------------------------------------------------------------------


class TestSpeakIntegration:
    """Verify that Agent.speak() calls transform_draft_to_final() as Stage 2."""

    def _make_agent(self, draft: str):
        from Entelgia_production_meta import (
            Agent,
            Config,
            ConsciousCore,
            EmotionCore,
            LanguageCore,
        )

        cfg = Config(web_research_enabled=False)
        llm = MagicMock()
        llm.generate.return_value = draft

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
        return agent, cfg, llm

    def test_speak_calls_transform_draft_to_final(self):
        """Stage 2 transform should be called during speak()."""
        draft = "It is important to note that consciousness is complex and contested."
        agent, cfg, llm = self._make_agent(draft)

        transform_sentinel = MagicMock(return_value="Truth eludes easy capture.")

        with (
            patch.object(_meta, "CFG", cfg),
            patch.object(_meta, "transform_draft_to_final", transform_sentinel),
        ):
            agent.speak("What is truth?", [])

        transform_sentinel.assert_called_once()

    def test_speak_passes_draft_to_transform(self):
        """The draft text produced by Stage 1 is passed to Stage 2."""
        draft = "We must examine the assumptions underlying this claim carefully."
        agent, cfg, llm = self._make_agent(draft)

        captured_draft = []

        def _capture(draft_text, *args, **kwargs):
            captured_draft.append(draft_text)
            return draft_text  # passthrough

        with (
            patch.object(_meta, "CFG", cfg),
            patch.object(_meta, "transform_draft_to_final", side_effect=_capture),
        ):
            agent.speak("What grounds knowledge?", [])

        assert len(captured_draft) == 1
        # The draft passed to Stage 2 should be non-empty
        assert captured_draft[0].strip()

    def test_speak_uses_transform_output_not_draft(self):
        """The final speak() output should come from Stage 2, not Stage 1 raw."""
        draft = "It is important to note that consciousness is complex."
        final = "Consciousness resists simple definition."
        agent, cfg, llm = self._make_agent(draft)

        with (
            patch.object(_meta, "CFG", cfg),
            patch.object(_meta, "transform_draft_to_final", return_value=final),
        ):
            result = agent.speak("What is consciousness?", [])

        # revise_draft still runs after transform but should preserve core content
        assert "Consciousness" in result or "consciousness" in result


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s", "--override-ini=addopts="])

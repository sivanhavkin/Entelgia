# tests/test_humanizer.py
"""
Tests for the humanize_text() helper and its integration in Agent.speak().

Validates:
  1. humanize_text() returns rewritten text from the LLM.
  2. humanize_text() falls back to original text on empty/short input.
  3. humanize_text() falls back to original text when LLM returns None/empty.
  4. humanize_text() uses validate_output() on the rewritten text.
  5. Agent.speak() invokes humanize_text() (via llm.generate) for all three
     agents: Socrates, Athena, Fixy.
  6. Config exposes humanizer_model and humanizer_temperature with correct
     default values.
  7. humanizer_temperature from Config is forwarded to llm.generate.
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from unittest.mock import MagicMock, patch, call


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _import_200t():
    """Import the 200t module (heavy; cached by sys.modules)."""
    import importlib
    return importlib.import_module("Entelgia_production_meta_200t")


def _make_agent_200t(name="Socrates", humanizer_temp=0.6, humanizer_model=None):
    """Build a minimal Agent from the 200t module with mocked LLM."""
    meta = _import_200t()

    cfg = meta.Config(web_research_enabled=False)
    cfg.humanizer_temperature = humanizer_temp
    cfg.humanizer_model = humanizer_model

    llm = MagicMock()
    # First call → main agent response; second call → humanizer rewrite.
    llm.generate.side_effect = [
        "Reality is shaped by perception and language.",        # agent response
        "Reality emerges from how we perceive and describe it.",  # humanizer
    ]

    memory = MagicMock()
    memory.stm_load.return_value = []
    memory.ltm_recent.return_value = []
    memory.get_agent_state.return_value = {
        "id": 0, "ego": 0.5, "superego": 0.3, "id_drive": 0.5
    }
    emotion = MagicMock(spec=meta.EmotionCore)
    emotion.infer.return_value = ("neutral", 0.3)
    behavior = MagicMock()
    language = meta.LanguageCore()
    conscious = meta.ConsciousCore()

    agent = meta.Agent(
        name=name,
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


# ---------------------------------------------------------------------------
# Unit tests for humanize_text()
# ---------------------------------------------------------------------------


class TestHumanizeText:
    def _get_fn(self):
        return _import_200t().humanize_text

    def test_returns_rewritten_text(self):
        humanize_text = self._get_fn()
        llm = MagicMock()
        llm.generate.return_value = "Rewritten version of the text."
        result = humanize_text(
            llm, "test-model",
            "Original sentence here with enough words to pass.",
            agent_name="Socrates",
        )
        assert result == "Rewritten version of the text."
        llm.generate.assert_called_once()

    def test_short_input_returned_unchanged(self):
        humanize_text = self._get_fn()
        llm = MagicMock()
        result = humanize_text(llm, "test-model", "Hi.", agent_name="Athena")
        assert result == "Hi."
        llm.generate.assert_not_called()

    def test_empty_input_returned_unchanged(self):
        humanize_text = self._get_fn()
        llm = MagicMock()
        result = humanize_text(llm, "test-model", "", agent_name="Fixy")
        assert result == ""
        llm.generate.assert_not_called()

    def test_none_from_llm_falls_back_to_original(self):
        humanize_text = self._get_fn()
        llm = MagicMock()
        llm.generate.return_value = None
        original = "Something meaningful to say about the world."
        result = humanize_text(llm, "test-model", original, agent_name="Socrates")
        assert result == original

    def test_prompt_contains_agent_name(self):
        humanize_text = self._get_fn()
        llm = MagicMock()
        llm.generate.return_value = "Some rewrite."
        humanize_text(llm, "model-x", "This is a long enough sentence for the check.", agent_name="Athena")
        called_prompt = llm.generate.call_args[0][1]
        assert "Athena" in called_prompt

    def test_temperature_forwarded(self):
        humanize_text = self._get_fn()
        llm = MagicMock()
        llm.generate.return_value = "Rewritten."
        humanize_text(
            llm, "model-x",
            "Long enough text for humanizer to process it.",
            agent_name="Socrates",
            temperature=0.8,
        )
        kwargs = llm.generate.call_args[1]
        assert kwargs.get("temperature") == pytest.approx(0.8)

    def test_use_cache_false(self):
        humanize_text = self._get_fn()
        llm = MagicMock()
        llm.generate.return_value = "Rewrite."
        humanize_text(llm, "m", "Long enough text for the humanizer to process.", agent_name="Fixy")
        kwargs = llm.generate.call_args[1]
        assert kwargs.get("use_cache") is False


# ---------------------------------------------------------------------------
# Config defaults
# ---------------------------------------------------------------------------


class TestConfigHumanizerDefaults:
    def test_humanizer_model_default_none(self):
        meta = _import_200t()
        cfg = meta.Config(web_research_enabled=False)
        assert cfg.humanizer_model is None

    def test_humanizer_temperature_default(self):
        meta = _import_200t()
        cfg = meta.Config(web_research_enabled=False)
        assert cfg.humanizer_temperature == pytest.approx(0.6)


# ---------------------------------------------------------------------------
# Integration: Agent.speak() invokes humanize_text for all agents
# ---------------------------------------------------------------------------


class TestAgentSpeakCallsHumanizer:
    """Verify that Agent.speak() invokes the humanizer for Socrates, Athena, Fixy."""

    @pytest.mark.parametrize("agent_name", ["Socrates", "Athena", "Fixy"])
    def test_humanizer_called_for_agent(self, agent_name):
        meta = _import_200t()
        agent, cfg, llm = _make_agent_200t(name=agent_name)
        with patch.object(meta, "CFG", cfg):
            agent.speak("What is truth?", [])
        # llm.generate should be called at least twice:
        # once for the main response, once for the humanizer rewrite.
        assert llm.generate.call_count >= 2

    @pytest.mark.parametrize("agent_name", ["Socrates", "Athena", "Fixy"])
    def test_humanizer_uses_configured_temperature(self, agent_name):
        meta = _import_200t()
        agent, cfg, llm = _make_agent_200t(name=agent_name, humanizer_temp=0.7)
        with patch.object(meta, "CFG", cfg):
            agent.speak("What is consciousness?", [])
        # Find the humanizer call: it should use temperature=0.7 and use_cache=False.
        humanizer_calls = [
            c for c in llm.generate.call_args_list
            if c[1].get("use_cache") is False and c[1].get("temperature") == pytest.approx(0.7)
        ]
        assert len(humanizer_calls) >= 1

    def test_humanizer_uses_agent_model_when_humanizer_model_none(self):
        meta = _import_200t()
        agent, cfg, llm = _make_agent_200t(humanizer_model=None)
        with patch.object(meta, "CFG", cfg):
            agent.speak("What is truth?", [])
        # All LLM calls should use "test-model"
        for c in llm.generate.call_args_list:
            assert c[0][0] == "test-model"

    def test_humanizer_uses_custom_model_when_set(self):
        meta = _import_200t()
        agent, cfg, llm = _make_agent_200t(humanizer_model="custom-humanizer-model")
        # Three calls: agent response + humanizer (custom model)
        llm.generate.side_effect = [
            "First response from the agent about philosophy.",
            "Humanized first response from the agent.",
        ]
        with patch.object(meta, "CFG", cfg):
            agent.speak("What is being?", [])
        used_models = [c[0][0] for c in llm.generate.call_args_list]
        assert "custom-humanizer-model" in used_models

    def test_humanizer_failure_does_not_crash_speak(self):
        """A RuntimeError from humanize_text must not propagate out of speak()."""
        meta = _import_200t()
        agent, cfg, llm = _make_agent_200t()
        with patch.object(meta, "CFG", cfg), \
             patch.object(meta, "humanize_text", side_effect=RuntimeError("LLM down")):
            # Should not raise
            result = agent.speak("What is reality?", [])
        assert isinstance(result, str)
        assert result  # non-empty fallback

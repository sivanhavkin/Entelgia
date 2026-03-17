# tests/test_humanizer.py
"""
Tests for the SKILL.md-derived Humanizer rewrite pass in Entelgia_production_meta_200t.

Validates:
  1. _extract_humanizer_sections() removes frontmatter, Output Format, and Full Example.
  2. _load_skill_humanizer_guidance() returns guidance containing SKILL.md content.
  3. humanize_text() prompt contains the unique marker from a temporary SKILL.md.
  4. humanize_text() forwards humanizer_temperature to llm.generate.
  5. humanize_text() uses cfg.humanizer_model when set, else falls back to agent model.
  6. humanize_text() is non-fatal: returns original text when llm.generate raises.
  7. Cache: SKILL.md is only read once when mtime is unchanged (second call hits cache).
  8. Agent.speak() does not crash when humanize_text raises an unexpected exception.

All tests are offline: LLM.generate is always mocked.
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from unittest.mock import MagicMock, patch, call

import Entelgia_production_meta_200t as _meta200t
from Entelgia_production_meta_200t import (
    Agent,
    BehaviorCore,
    Config,
    ConsciousCore,
    EmotionCore,
    LanguageCore,
    _build_humanizer_prompt_section,
    _extract_humanizer_sections,
    _find_skill_md_path,
    _load_skill_humanizer_guidance,
    _SkillCache,
    _skill_cache,
    humanize_text,
    preload_humanizer_skill_md,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_SAMPLE_SKILL_MD = """\
---
name: humanizer
version: 2.2.0
description: |
  Remove signs of AI-generated writing.
allowed-tools:
  - Read
---

# Humanizer: Remove AI Writing Patterns

UNIQUE_SKILL_MARKER_123

You are a writing editor.

## Your Task

Rewrite text to be human.

## PERSONALITY AND SOUL

Add voice and personality.

## CONTENT PATTERNS

### 1. Undue Emphasis

Remove overblown significance claims.

## Process

1. Read carefully
2. Identify patterns
3. Rewrite

## Output Format

Provide:
1. Draft rewrite

---

## Full Example

**Before (AI-sounding):**
> Great question! This is pivotal.

**After:**
> This happened.

## Reference

Wikipedia guide.
"""


def _make_agent_200t(humanizer_model=None, humanizer_temperature=0.6):
    """Return a minimal Agent200t whose LLM and memory calls are fully mocked."""
    cfg = Config(
        humanizer_model=humanizer_model,
        humanizer_temperature=humanizer_temperature,
    )

    llm_mock = MagicMock()
    llm_mock.generate.return_value = "I think about this carefully."

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

    language_mock = LanguageCore()
    conscious_mock = ConsciousCore()

    agent = Agent(
        name="Socrates",
        model="phi3",
        color="",
        llm=llm_mock,
        memory=memory_mock,
        emotion=emotion_mock,
        behavior=behavior_mock,
        language=language_mock,
        conscious=conscious_mock,
        persona="A philosopher.",
        use_enhanced=False,
        cfg=cfg,
    )
    return agent, cfg


# ---------------------------------------------------------------------------
# 1. _extract_humanizer_sections
# ---------------------------------------------------------------------------


class TestExtractHumanizerSections:
    """Verify that section extraction strips the right content."""

    def test_strips_yaml_frontmatter(self):
        result = _extract_humanizer_sections(_SAMPLE_SKILL_MD)
        assert "name: humanizer" not in result
        assert "allowed-tools" not in result

    def test_excludes_full_example_and_after(self):
        result = _extract_humanizer_sections(_SAMPLE_SKILL_MD)
        assert "## Full Example" not in result
        assert "Great question!" not in result
        assert "## Reference" not in result

    def test_excludes_output_format(self):
        result = _extract_humanizer_sections(_SAMPLE_SKILL_MD)
        assert "## Output Format" not in result

    def test_includes_your_task(self):
        result = _extract_humanizer_sections(_SAMPLE_SKILL_MD)
        assert "Your Task" in result

    def test_includes_personality_and_soul(self):
        result = _extract_humanizer_sections(_SAMPLE_SKILL_MD)
        assert "PERSONALITY AND SOUL" in result

    def test_includes_process(self):
        result = _extract_humanizer_sections(_SAMPLE_SKILL_MD)
        assert "## Process" in result

    def test_includes_content_patterns(self):
        result = _extract_humanizer_sections(_SAMPLE_SKILL_MD)
        assert "CONTENT PATTERNS" in result

    def test_preserves_unique_marker(self):
        result = _extract_humanizer_sections(_SAMPLE_SKILL_MD)
        assert "UNIQUE_SKILL_MARKER_123" in result


# ---------------------------------------------------------------------------
# 2. _load_skill_humanizer_guidance (with monkeypatched path)
# ---------------------------------------------------------------------------


class TestLoadSkillGuidance:
    """Verify caching behaviour and graceful fallback."""

    def test_returns_guidance_from_temp_file(self, tmp_path, monkeypatch):
        skill_file = tmp_path / "SKILL.md"
        skill_file.write_text(_SAMPLE_SKILL_MD, encoding="utf-8")

        # Reset module cache so previous test state doesn't interfere
        _skill_cache.last_path = None
        _skill_cache.last_mtime = None
        _skill_cache.extracted_guidance = ""

        monkeypatch.setattr(_meta200t, "_find_skill_md_path", lambda: skill_file)
        guidance = _load_skill_humanizer_guidance()
        assert "UNIQUE_SKILL_MARKER_123" in guidance

    def test_returns_empty_string_when_file_missing(self, monkeypatch):
        _skill_cache.last_path = None
        _skill_cache.last_mtime = None
        _skill_cache.extracted_guidance = ""

        monkeypatch.setattr(_meta200t, "_find_skill_md_path", lambda: None)
        guidance = _load_skill_humanizer_guidance()
        assert guidance == ""

    def test_cache_hit_does_not_reread(self, tmp_path, monkeypatch):
        """File should only be read once when mtime is unchanged."""
        skill_file = tmp_path / "SKILL.md"
        skill_file.write_text(_SAMPLE_SKILL_MD, encoding="utf-8")

        _skill_cache.last_path = None
        _skill_cache.last_mtime = None
        _skill_cache.extracted_guidance = ""

        monkeypatch.setattr(_meta200t, "_find_skill_md_path", lambda: skill_file)

        read_count = {"n": 0}
        original_read_text = skill_file.__class__.read_text

        def counting_read_text(self, **kwargs):
            read_count["n"] += 1
            return original_read_text(self, **kwargs)

        monkeypatch.setattr(skill_file.__class__, "read_text", counting_read_text)

        _load_skill_humanizer_guidance()
        _load_skill_humanizer_guidance()

        assert read_count["n"] == 1, "SKILL.md should only be read once (cache hit)"

    def test_graceful_fallback_on_read_error(self, tmp_path, monkeypatch):
        """Guidance is "" and no exception propagates when read fails."""
        skill_file = tmp_path / "SKILL.md"
        skill_file.write_text("dummy", encoding="utf-8")

        _skill_cache.last_path = None
        _skill_cache.last_mtime = None
        _skill_cache.extracted_guidance = ""

        monkeypatch.setattr(_meta200t, "_find_skill_md_path", lambda: skill_file)

        def boom(*args, **kwargs):
            raise OSError("disk error")

        monkeypatch.setattr(skill_file.__class__, "read_text", boom)

        guidance = _load_skill_humanizer_guidance()
        assert guidance == ""


# ---------------------------------------------------------------------------
# 2b. preload_humanizer_skill_md
# ---------------------------------------------------------------------------


class TestPreloadHumanizerSkillMd:
    """Verify preload helper populates cache and is safe when file is absent."""

    def test_preload_populates_cache_when_file_exists(self, tmp_path, monkeypatch):
        """preload_humanizer_skill_md() should fill _skill_cache.extracted_guidance."""
        skill_file = tmp_path / "SKILL.md"
        skill_file.write_text(_SAMPLE_SKILL_MD, encoding="utf-8")

        _skill_cache.last_path = None
        _skill_cache.last_mtime = None
        _skill_cache.extracted_guidance = ""

        monkeypatch.setattr(_meta200t, "_find_skill_md_path", lambda: skill_file)

        preload_humanizer_skill_md()

        assert "UNIQUE_SKILL_MARKER_123" in _skill_cache.extracted_guidance

    def test_preload_does_not_raise_when_file_missing(self, monkeypatch):
        """preload_humanizer_skill_md() must not raise even if SKILL.md is absent."""
        _skill_cache.last_path = None
        _skill_cache.last_mtime = None
        _skill_cache.extracted_guidance = ""

        monkeypatch.setattr(_meta200t, "_find_skill_md_path", lambda: None)

        # Should complete without raising any exception
        preload_humanizer_skill_md()

        assert _skill_cache.extracted_guidance == ""


# ---------------------------------------------------------------------------
# 3. humanize_text – prompt contains SKILL.md marker
# ---------------------------------------------------------------------------


class TestHumanizeTextPromptContent:
    """Verify that the LLM receives a prompt derived from SKILL.md."""

    def test_prompt_contains_skill_marker(self, tmp_path, monkeypatch):
        skill_file = tmp_path / "SKILL.md"
        skill_file.write_text(_SAMPLE_SKILL_MD, encoding="utf-8")

        _skill_cache.last_path = None
        _skill_cache.last_mtime = None
        _skill_cache.extracted_guidance = ""

        monkeypatch.setattr(_meta200t, "_find_skill_md_path", lambda: skill_file)

        llm_mock = MagicMock()
        llm_mock.generate.return_value = "Rewritten response."
        cfg = Config()

        humanize_text("Some AI-sounding text.", llm_mock, "phi3", cfg)

        assert llm_mock.generate.call_count == 1
        prompt_used = llm_mock.generate.call_args[0][1]
        assert "UNIQUE_SKILL_MARKER_123" in prompt_used, (
            "Prompt must contain content from SKILL.md"
        )

    def test_prompt_uses_fallback_when_no_skill_file(self, monkeypatch):
        """When SKILL.md is absent the fallback prompt header must appear."""
        _skill_cache.last_path = None
        _skill_cache.last_mtime = None
        _skill_cache.extracted_guidance = ""

        monkeypatch.setattr(_meta200t, "_find_skill_md_path", lambda: None)

        llm_mock = MagicMock()
        llm_mock.generate.return_value = "Rewritten."
        cfg = Config()

        humanize_text("Some text.", llm_mock, "phi3", cfg)

        prompt_used = llm_mock.generate.call_args[0][1]
        assert "writing editor" in prompt_used.lower()

    def test_returns_original_on_empty_input(self, monkeypatch):
        monkeypatch.setattr(_meta200t, "_find_skill_md_path", lambda: None)
        llm_mock = MagicMock()
        cfg = Config()
        assert humanize_text("", llm_mock, "phi3", cfg) == ""
        assert humanize_text("   ", llm_mock, "phi3", cfg) == "   "
        llm_mock.generate.assert_not_called()


# ---------------------------------------------------------------------------
# 4. Temperature forwarding
# ---------------------------------------------------------------------------


class TestHumanizeTemperature:
    """Verify that cfg.humanizer_temperature is forwarded to llm.generate."""

    def test_temperature_forwarded(self, monkeypatch):
        _skill_cache.last_path = None
        _skill_cache.last_mtime = None
        _skill_cache.extracted_guidance = ""

        monkeypatch.setattr(_meta200t, "_find_skill_md_path", lambda: None)

        llm_mock = MagicMock()
        llm_mock.generate.return_value = "Rewritten."
        cfg = Config(humanizer_temperature=0.42)

        humanize_text("Test text.", llm_mock, "phi3", cfg)

        kwargs = llm_mock.generate.call_args[1]
        assert kwargs.get("temperature") == pytest.approx(0.42)

    def test_default_temperature_is_0_6(self, monkeypatch):
        _skill_cache.last_path = None
        _skill_cache.last_mtime = None
        _skill_cache.extracted_guidance = ""

        monkeypatch.setattr(_meta200t, "_find_skill_md_path", lambda: None)

        llm_mock = MagicMock()
        llm_mock.generate.return_value = "Rewritten."
        cfg = Config()  # default humanizer_temperature=0.6

        humanize_text("Test text.", llm_mock, "phi3", cfg)

        kwargs = llm_mock.generate.call_args[1]
        assert kwargs.get("temperature") == pytest.approx(0.6)


# ---------------------------------------------------------------------------
# 5. Model selection
# ---------------------------------------------------------------------------


class TestHumanizeModelSelection:
    """Verify cfg.humanizer_model is used when set, else agent model is used."""

    def test_uses_humanizer_model_when_set(self, monkeypatch):
        _skill_cache.last_path = None
        _skill_cache.last_mtime = None
        _skill_cache.extracted_guidance = ""

        monkeypatch.setattr(_meta200t, "_find_skill_md_path", lambda: None)

        llm_mock = MagicMock()
        llm_mock.generate.return_value = "Rewritten."
        cfg = Config(humanizer_model="llama3:latest")

        humanize_text("Test text.", llm_mock, "phi3", cfg)

        model_used = llm_mock.generate.call_args[0][0]
        assert model_used == "llama3:latest"

    def test_uses_agent_model_when_humanizer_model_is_none(self, monkeypatch):
        _skill_cache.last_path = None
        _skill_cache.last_mtime = None
        _skill_cache.extracted_guidance = ""

        monkeypatch.setattr(_meta200t, "_find_skill_md_path", lambda: None)

        llm_mock = MagicMock()
        llm_mock.generate.return_value = "Rewritten."
        cfg = Config(humanizer_model=None)

        humanize_text("Test text.", llm_mock, "phi3:mini", cfg)

        model_used = llm_mock.generate.call_args[0][0]
        assert model_used == "phi3:mini"


# ---------------------------------------------------------------------------
# 6. Fail-safe: humanize_text does not propagate exceptions
# ---------------------------------------------------------------------------


class TestHumanizeFailSafe:
    """humanize_text must return the original text when llm.generate raises."""

    def test_returns_original_on_llm_exception(self, monkeypatch):
        _skill_cache.last_path = None
        _skill_cache.last_mtime = None
        _skill_cache.extracted_guidance = ""

        monkeypatch.setattr(_meta200t, "_find_skill_md_path", lambda: None)

        llm_mock = MagicMock()
        llm_mock.generate.side_effect = RuntimeError("LLM crashed")
        cfg = Config()

        original = "The original response text."
        result = humanize_text(original, llm_mock, "phi3", cfg)
        assert result == original

    def test_returns_original_when_generate_returns_empty(self, monkeypatch):
        _skill_cache.last_path = None
        _skill_cache.last_mtime = None
        _skill_cache.extracted_guidance = ""

        monkeypatch.setattr(_meta200t, "_find_skill_md_path", lambda: None)

        llm_mock = MagicMock()
        llm_mock.generate.return_value = ""
        cfg = Config()

        original = "Some text."
        result = humanize_text(original, llm_mock, "phi3", cfg)
        assert result == original


# ---------------------------------------------------------------------------
# 7. Agent.speak() embeds SKILL.md style guidance in the main prompt
# ---------------------------------------------------------------------------


class TestSpeakHumanizerPromptInjection:
    """Agent.speak() must embed humanizer style guidelines into the main prompt.

    The old two-pass approach (generate → separate humanize_text LLM call) is
    replaced by injecting _build_humanizer_prompt_section() into the prompt
    before the single LLM generation call.
    """

    def test_speak_completes_normally(self, monkeypatch):
        """speak() must return a non-empty string with no errors."""
        agent, cfg = _make_agent_200t()

        with patch.object(_meta200t, "CFG", cfg):
            result = agent.speak(
                "TOPIC: Philosophy of mind\nRespond now:\n", []
            )

        assert isinstance(result, str)
        assert len(result) > 0

    def test_speak_prompt_contains_skill_guidance(self, tmp_path, monkeypatch):
        """The LLM prompt must contain SKILL.md content (injected before generation)."""
        skill_file = tmp_path / "SKILL.md"
        skill_file.write_text(_SAMPLE_SKILL_MD, encoding="utf-8")

        _skill_cache.last_path = None
        _skill_cache.last_mtime = None
        _skill_cache.extracted_guidance = ""

        monkeypatch.setattr(_meta200t, "_find_skill_md_path", lambda: skill_file)

        agent, cfg = _make_agent_200t()
        captured_prompts = []

        original_generate = agent.llm.generate.side_effect

        def capturing_generate(model, prompt, **kwargs):
            captured_prompts.append(prompt)
            return "I think about this carefully."

        agent.llm.generate.side_effect = capturing_generate

        with patch.object(_meta200t, "CFG", cfg):
            agent.speak("TOPIC: Philosophy of mind\nRespond now:\n", [])

        assert captured_prompts, "LLM generate must have been called"
        main_prompt = captured_prompts[0]
        assert "UNIQUE_SKILL_MARKER_123" in main_prompt, (
            "Main generation prompt must contain SKILL.md content"
        )

    def test_speak_only_one_llm_call_per_turn(self, monkeypatch):
        """speak() must make exactly one LLM call (no second humanizer call)."""
        monkeypatch.setattr(_meta200t, "_find_skill_md_path", lambda: None)

        agent, cfg = _make_agent_200t()

        with patch.object(_meta200t, "CFG", cfg):
            agent.speak("TOPIC: Philosophy of mind\nRespond now:\n", [])

        assert agent.llm.generate.call_count == 1, (
            "speak() should make exactly one LLM call — humanizer is now prompt-injected"
        )

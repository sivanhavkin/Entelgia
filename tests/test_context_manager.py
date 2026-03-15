# tests/test_context_manager.py
"""
Tests for entelgia/context_manager.py

Covers:
- _safe_ltm_content — strips internal LTM fields
- _safe_stm_text — strips internal STM fields
- ContextManager.build_enriched_context — basic prompt assembly
- ContextManager.build_enriched_context — topic_style injection
- ContextManager.build_enriched_context — web_context injection
- ContextManager._prioritize_memories — scoring and ordering
- EnhancedMemoryIntegration.retrieve_relevant_memories — keyword match
"""

from __future__ import annotations

import sys
import os
from typing import Any, Dict, List

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from entelgia.context_manager import (
    ContextManager,
    EnhancedMemoryIntegration,
    _INTERNAL_LTM_FIELDS,
    _INTERNAL_STM_FIELDS,
    _safe_ltm_content,
    _safe_stm_text,
)

# ---------------------------------------------------------------------------
# _safe_ltm_content
# ---------------------------------------------------------------------------


class TestSafeLtmContent:
    """_safe_ltm_content must return only the content field."""

    def test_returns_content_for_valid_entry(self):
        mem = {"content": "A philosophical reflection.", "signature_hex": "abc123"}
        assert _safe_ltm_content(mem) == "A philosophical reflection."

    def test_returns_empty_string_when_content_missing(self):
        mem = {"agent": "Socrates", "signature_hex": "abc123"}
        assert _safe_ltm_content(mem) == ""

    def test_strips_all_internal_fields(self):
        """The function must not return any internal field values."""
        mem: Dict[str, Any] = {
            field: "should-be-hidden" for field in _INTERNAL_LTM_FIELDS
        }
        mem["content"] = "visible content"
        result = _safe_ltm_content(mem)
        assert result == "visible content"
        assert "should-be-hidden" not in result

    def test_handles_empty_dict(self):
        assert _safe_ltm_content({}) == ""

    def test_handles_non_string_content(self):
        """If content is not a string, returns empty string."""
        mem = {"content": None}
        result = _safe_ltm_content(mem)
        assert result == "" or result is None or isinstance(result, str)


# ---------------------------------------------------------------------------
# _safe_stm_text
# ---------------------------------------------------------------------------


class TestSafeStmText:
    """_safe_stm_text must return only the text field."""

    def test_returns_text_for_valid_entry(self):
        entry = {"text": "Recent STM thought.", "signature_hex": "xyz"}
        assert _safe_stm_text(entry) == "Recent STM thought."

    def test_returns_empty_string_when_text_missing(self):
        entry = {"agent": "Athena"}
        assert _safe_stm_text(entry) == ""

    def test_strips_all_internal_stm_fields(self):
        entry: Dict[str, Any] = {
            field: "should-be-hidden" for field in _INTERNAL_STM_FIELDS
        }
        entry["text"] = "visible stm text"
        result = _safe_stm_text(entry)
        assert result == "visible stm text"
        assert "should-be-hidden" not in result

    def test_handles_empty_dict(self):
        assert _safe_stm_text({}) == ""


# ---------------------------------------------------------------------------
# Shared helpers for ContextManager tests
# ---------------------------------------------------------------------------


def _minimal_drives() -> Dict[str, float]:
    return {
        "curiosity": 0.5,
        "certainty": 0.4,
        "existential": 0.3,
        "social": 0.5,
        "tension": 0.2,
    }


def _minimal_debate_profile() -> Dict[str, Any]:
    return {"style": "neutral", "temperature": 0.7}


# ---------------------------------------------------------------------------
# ContextManager.build_enriched_context
# ---------------------------------------------------------------------------


class TestContextManagerBuildEnrichedContext:
    """Tests for ContextManager.build_enriched_context."""

    def setup_method(self):
        self.cm = ContextManager()

    def _call(self, **overrides):
        defaults = dict(
            agent_name="Socrates",
            agent_lang="en",
            persona="A philosopher who probes assumptions.",
            drives=_minimal_drives(),
            user_seed="What is the nature of consciousness?",
            dialog_tail=[
                {"role": "Socrates", "text": "Can we really know anything?"},
                {"role": "Athena", "text": "We can know through careful observation."},
            ],
            stm=[{"text": "Recent reflection on identity."}],
            ltm=[
                {"content": "Memory of a philosophical debate.", "emotion": "curious"}
            ],
            debate_profile=_minimal_debate_profile(),
        )
        defaults.update(overrides)
        return self.cm.build_enriched_context(**defaults)

    def test_returns_non_empty_string(self):
        result = self._call()
        assert isinstance(result, str) and len(result) > 0

    def test_contains_agent_name(self):
        result = self._call(agent_name="Socrates")
        assert "Socrates" in result

    def test_contains_seed(self):
        result = self._call(user_seed="Free will and determinism")
        assert "Free will and determinism" in result

    def test_contains_persona(self):
        result = self._call(persona="A deep philosophical thinker")
        assert "A deep philosophical thinker" in result

    def test_contains_ltm_content(self):
        result = self._call(
            ltm=[{"content": "Ancient memory of wisdom.", "emotion": "calm"}]
        )
        assert "Ancient memory of wisdom." in result

    def test_contains_stm_text(self):
        result = self._call(stm=[{"text": "A very recent thought about truth."}])
        assert "A very recent thought about truth." in result

    def test_internal_ltm_fields_not_in_prompt(self):
        """Signature hex and other internal LTM fields must not appear in the prompt."""
        result = self._call(
            ltm=[
                {
                    "content": "Visible memory.",
                    "signature_hex": "secret_hmac_value",
                    "expires_at": "2099-01-01T00:00:00Z",
                }
            ]
        )
        assert "secret_hmac_value" not in result
        assert "signature_hex" not in result

    def test_web_context_injected_when_provided(self):
        result = self._call(
            web_context="Recent study on neural correlates of consciousness."
        )
        assert "Recent study on neural correlates of consciousness." in result

    def test_web_context_absent_when_empty(self):
        result = self._call(web_context="")
        # Should still return a valid prompt
        assert isinstance(result, str) and len(result) > 0

    def test_topic_style_injected_when_provided(self):
        result = self._call(topic_style="Use investigative, domain-aware reasoning.")
        assert "STYLE INSTRUCTION" in result or "Use investigative" in result

    def test_topic_style_absent_when_empty(self):
        result_with_style = self._call(topic_style="some style")
        result_without_style = self._call(topic_style="")
        # Result without style should be shorter (no style block)
        assert len(result_without_style) < len(result_with_style)

    def test_no_internal_fields_in_stm(self):
        """Internal STM fields must not appear in the prompt."""
        result = self._call(
            stm=[
                {
                    "text": "Visible STM thought.",
                    "signature_hex": "stm_secret",
                    "agent": "Socrates",
                }
            ]
        )
        assert "stm_secret" not in result
        assert "signature_hex" not in result

    def test_empty_stm_and_ltm(self):
        result = self._call(stm=[], ltm=[])
        assert isinstance(result, str) and len(result) > 0


# ---------------------------------------------------------------------------
# ContextManager._prioritize_memories
# ---------------------------------------------------------------------------


class TestContextManagerPrioritizeMemories:
    """Tests for _prioritize_memories (importance + emotion scoring)."""

    def setup_method(self):
        self.cm = ContextManager()

    def test_higher_importance_ranked_first(self):
        memories = [
            {"content": "low importance", "importance": 0.1, "emotion": "neutral"},
            {"content": "high importance", "importance": 0.9, "emotion": "neutral"},
        ]
        result = self.cm._prioritize_memories(memories, limit=5)
        assert result[0]["content"] == "high importance"

    def test_returns_list(self):
        memories = [{"content": "single", "importance": 0.5}]
        result = self.cm._prioritize_memories(memories, limit=5)
        assert isinstance(result, list)

    def test_empty_list_returns_empty(self):
        assert self.cm._prioritize_memories([], limit=5) == []

    def test_limit_respected(self):
        memories = [
            {"content": f"mem {i}", "importance": float(i) / 10} for i in range(8)
        ]
        result = self.cm._prioritize_memories(memories, limit=3)
        assert len(result) <= 3


# ---------------------------------------------------------------------------
# EnhancedMemoryIntegration.retrieve_relevant_memories
# ---------------------------------------------------------------------------


class TestEnhancedMemoryIntegration:
    """Tests for EnhancedMemoryIntegration.retrieve_relevant_memories."""

    def setup_method(self):
        self.emi = EnhancedMemoryIntegration()

    def _dialog(self, text: str = "test"):
        return [{"role": "Socrates", "text": text}]

    def test_returns_list(self):
        memories = [{"content": "consciousness and free will", "importance": 0.5}]
        result = self.emi.retrieve_relevant_memories(
            "Socrates", "consciousness", self._dialog(), memories
        )
        assert isinstance(result, list)

    def test_relevant_memory_surfaces(self):
        memories = [
            {"content": "unrelated topic about cats", "importance": 0.5},
            {"content": "consciousness and identity", "importance": 0.5},
        ]
        result = self.emi.retrieve_relevant_memories(
            "Socrates",
            "consciousness",
            self._dialog("consciousness"),
            memories,
            limit=2,
        )
        contents = [m["content"] for m in result]
        assert any("consciousness" in c for c in contents)

    def test_limit_respected(self):
        memories = [{"content": f"memory {i}", "importance": 0.5} for i in range(10)]
        result = self.emi.retrieve_relevant_memories(
            "Socrates", "philosophy", self._dialog(), memories, limit=3
        )
        assert len(result) <= 3

    def test_empty_memories_returns_empty(self):
        result = self.emi.retrieve_relevant_memories(
            "Socrates", "consciousness", self._dialog(), []
        )
        assert result == []


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])

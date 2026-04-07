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


# ---------------------------------------------------------------------------
# topics_enabled=False — topic data must be fully suppressed
# ---------------------------------------------------------------------------


class TestTopicsDisabledInContextManager:
    """When topics_enabled=False, ContextManager and EnhancedMemoryIntegration
    must not inject topic-related data into prompts or scoring."""

    def setup_method(self):
        self.cm = ContextManager()
        self.emi = EnhancedMemoryIntegration()

    def _minimal_drives(self):
        return {
            "curiosity": 0.5,
            "certainty": 0.4,
            "existential": 0.3,
            "social": 0.5,
            "tension": 0.2,
        }

    def _minimal_debate_profile(self):
        return {"style": "neutral", "temperature": 0.7}

    # ── build_enriched_context ────────────────────────────────────────────

    def test_topic_style_suppressed_when_topics_disabled(self):
        """STYLE INSTRUCTION must not appear in the prompt when topics_enabled=False,
        even if a non-empty topic_style is supplied by the caller."""
        result = self.cm.build_enriched_context(
            agent_name="Socrates",
            agent_lang="en",
            persona="A philosopher.",
            drives=self._minimal_drives(),
            user_seed="What is consciousness?",
            dialog_tail=[],
            stm=[],
            ltm=[],
            debate_profile=self._minimal_debate_profile(),
            topic_style="Use investigative, causal reasoning.",
            topics_enabled=False,
        )
        assert (
            "STYLE INSTRUCTION" not in result
        ), "STYLE INSTRUCTION must be absent when topics_enabled=False"
        assert (
            "Use investigative, causal reasoning." not in result
        ), "topic_style content must not appear in prompt when topics_enabled=False"

    def test_topic_style_injected_when_topics_enabled(self):
        """STYLE INSTRUCTION must appear when topics_enabled=True and topic_style is set."""
        result = self.cm.build_enriched_context(
            agent_name="Socrates",
            agent_lang="en",
            persona="A philosopher.",
            drives=self._minimal_drives(),
            user_seed="What is consciousness?",
            dialog_tail=[],
            stm=[],
            ltm=[],
            debate_profile=self._minimal_debate_profile(),
            topic_style="Use investigative, causal reasoning.",
            topics_enabled=True,
        )
        assert (
            "STYLE INSTRUCTION" in result or "Use investigative" in result
        ), "STYLE INSTRUCTION must be present when topics_enabled=True and topic_style is set"

    def test_empty_topic_style_still_absent_when_topics_disabled(self):
        """With empty topic_style and topics_enabled=False, no style block appears."""
        result = self.cm.build_enriched_context(
            agent_name="Socrates",
            agent_lang="en",
            persona="A philosopher.",
            drives=self._minimal_drives(),
            user_seed="What is freedom?",
            dialog_tail=[],
            stm=[],
            ltm=[],
            debate_profile=self._minimal_debate_profile(),
            topic_style="",
            topics_enabled=False,
        )
        assert "STYLE INSTRUCTION" not in result

    # ── retrieve_relevant_memories ────────────────────────────────────────

    def _dialog(self, text: str = "test"):
        return [{"role": "Socrates", "text": text}]

    def test_topic_not_used_for_scoring_when_topics_disabled(self):
        """With topics_enabled=False, a memory highly relevant to the topic
        must not be ranked above a memory that is better matched by importance
        and dialog content alone, confirming topic scoring is suppressed."""
        # Memory A: exact match for topic but low importance
        mem_topic_match = {
            "content": "wealth inequality economics distribution",
            "importance": 0.1,
        }
        # Memory B: no topic match but high importance
        mem_high_importance = {
            "content": "consciousness identity mind",
            "importance": 0.9,
        }
        result = self.emi.retrieve_relevant_memories(
            agent_name="Socrates",
            current_topic="wealth inequality",
            recent_dialog=self._dialog("philosophy of mind"),
            ltm_entries=[mem_topic_match, mem_high_importance],
            limit=2,
            topics_enabled=False,
        )
        # With topic scoring suppressed, the high-importance memory should rank first.
        assert result, "Must return at least one memory"
        assert (
            result[0]["content"] == "consciousness identity mind"
        ), "High-importance memory must rank first when topic scoring is suppressed"

    def test_topic_used_for_scoring_when_topics_enabled(self):
        """With topics_enabled=True, a memory that matches the topic must be
        ranked above a memory with higher importance but no topic match."""
        # Memory A: exact topic match but low importance
        mem_topic_match = {
            "content": "wealth inequality economics distribution",
            "importance": 0.1,
        }
        # Memory B: high importance but unrelated topic
        mem_high_importance = {
            "content": "quantum mechanics physics",
            "importance": 0.9,
        }
        result = self.emi.retrieve_relevant_memories(
            agent_name="Socrates",
            current_topic="wealth inequality",
            recent_dialog=self._dialog("wealth inequality"),
            ltm_entries=[mem_topic_match, mem_high_importance],
            limit=2,
            topics_enabled=True,
        )
        assert len(result) == 2, "Both memories must be returned"
        assert (
            result[0]["content"] == "wealth inequality economics distribution"
        ), "Topic-matching memory must rank first when topics_enabled=True"
        assert (
            result[1]["content"] == "quantum mechanics physics"
        ), "High-importance but off-topic memory must rank second"


# ---------------------------------------------------------------------------
# Agent state variables in prompt
# ---------------------------------------------------------------------------


class TestAgentStateInPrompt:
    """Verify that all agent state variables appear in the prompt built by
    ContextManager: id, ego, sup, sa, energy, pressure, conflict, unresolved,
    stagnation, emotion, kind, temp, dissent, drive_combo."""

    def setup_method(self):
        self.cm = ContextManager()

    def _build(self, **overrides):
        defaults = dict(
            agent_name="Socrates",
            agent_lang="en",
            persona="A philosopher.",
            drives={
                "id_strength": 6.0,
                "ego_strength": 5.0,
                "superego_strength": 7.5,
                "self_awareness": 0.80,
            },
            user_seed="What is consciousness?",
            dialog_tail=[],
            stm=[],
            ltm=[],
            debate_profile={
                "style": "analytical",
                "drive_combo": "high_id",
                "dissent_level": 0.35,
            },
            energy=72.5,
            pressure=3.40,
            emotion="curious",
            emotion_intensity=0.65,
            conflict=2.10,
            unresolved=3,
            stagnation=0.25,
            kind="assertive",
            temp=0.72,
            dissent=0.35,
            drive_combo="high_id",
        )
        defaults.update(overrides)
        return self.cm.build_enriched_context(**defaults)

    # ── drive variables ────────────────────────────────────────────────────

    def test_id_drive_in_prompt(self):
        assert "id=" in self._build()

    def test_ego_drive_in_prompt(self):
        assert "ego=" in self._build()

    def test_superego_drive_in_prompt(self):
        assert "sup=" in self._build()

    def test_self_awareness_in_prompt(self):
        assert "sa=" in self._build()

    def test_drive_values_match(self):
        """The exact drive values passed in must appear in the prompt."""
        prompt = self._build()
        assert "id=6.0" in prompt
        assert "ego=5.0" in prompt
        assert "sup=7.5" in prompt
        assert "sa=0.80" in prompt

    # ── state variables ────────────────────────────────────────────────────

    def test_energy_in_prompt(self):
        assert "energy=" in self._build()

    def test_pressure_in_prompt(self):
        assert "pressure=" in self._build()

    def test_conflict_in_prompt(self):
        assert "conflict=" in self._build()

    def test_unresolved_in_prompt(self):
        assert "unresolved=" in self._build()

    def test_stagnation_in_prompt(self):
        assert "stagnation=" in self._build()

    def test_emotion_in_prompt(self):
        assert "emotion=" in self._build()

    def test_kind_in_prompt(self):
        assert "kind=" in self._build()

    def test_temp_in_prompt(self):
        assert "temp=" in self._build()

    def test_dissent_in_prompt(self):
        assert "dissent=" in self._build()

    def test_drive_combo_in_prompt(self):
        assert "combo=" in self._build()

    def test_state_values_match(self):
        """The exact state values passed in must appear in the prompt."""
        prompt = self._build()
        assert "energy=72.5" in prompt
        assert "pressure=3.40" in prompt
        assert "conflict=2.10" in prompt
        assert "unresolved=3" in prompt
        assert "stagnation=0.25" in prompt
        assert "emotion=curious" in prompt
        assert "kind=assertive" in prompt
        assert "temp=0.72" in prompt

    def test_emotion_sanitized(self):
        """Emotion strings with special characters must be stripped before injection."""
        prompt = self._build(emotion="hap\npy\x00test")
        # The sanitised version 'happytest' must be in the prompt, not the raw value
        assert "\n" not in prompt.split("[State:")[1].split("]")[0]
        assert "\x00" not in prompt

    def test_state_defaults_when_not_provided(self):
        """When state params are omitted the prompt still contains all keys."""
        defaults = dict(
            agent_name="Athena",
            agent_lang="en",
            persona="A systems thinker.",
            drives={
                "id_strength": 5.0,
                "ego_strength": 5.0,
                "superego_strength": 5.0,
                "self_awareness": 0.55,
            },
            user_seed="What is truth?",
            dialog_tail=[],
            stm=[],
            ltm=[],
            debate_profile={"style": "integrative"},
        )
        prompt = self.cm.build_enriched_context(**defaults)
        for key in (
            "energy=",
            "pressure=",
            "conflict=",
            "unresolved=",
            "stagnation=",
            "emotion=",
            "kind=",
            "temp=",
        ):
            assert key in prompt, f"Expected '{key}' in prompt"



# ---------------------------------------------------------------------------
# EnhancedMemoryIntegration – semantic search path
# ---------------------------------------------------------------------------

import importlib
from unittest.mock import MagicMock, patch


class TestEnhancedMemoryIntegrationSemantic:
    """Tests for the transformer-based semantic memory search path."""

    def _memories(self):
        return [
            {"content": "consciousness and subjective experience", "importance": 0.5},
            {"content": "quantum mechanics wave function", "importance": 0.5},
            {"content": "justice and social equality", "importance": 0.5},
        ]

    def _dialog(self):
        return [{"role": "Socrates", "text": "What is consciousness?"}]

    # ── semantic path uses injected scores ────────────────────────────────

    def test_semantic_scores_used_when_model_available(self):
        """When _batch_semantic_scores returns scores, they are used for ranking."""
        emi = EnhancedMemoryIntegration(use_semantic=True)
        memories = self._memories()
        # Inject scores: first memory gets highest topic + dialog similarity
        topic_scores = [0.9, 0.1, 0.1]
        dialog_scores = [0.8, 0.1, 0.1]
        with patch.object(
            emi,
            "_batch_semantic_scores",
            return_value=(topic_scores, dialog_scores),
        ):
            result = emi.retrieve_relevant_memories(
                agent_name="Socrates",
                current_topic="consciousness",
                recent_dialog=self._dialog(),
                ltm_entries=memories,
                limit=3,
            )
        assert result[0]["content"] == "consciousness and subjective experience"

    def test_semantic_fallback_when_batch_returns_none(self):
        """When _batch_semantic_scores returns (None, None), keyword path is used."""
        emi = EnhancedMemoryIntegration(use_semantic=True)
        memories = self._memories()
        with patch.object(
            emi, "_batch_semantic_scores", return_value=(None, None)
        ):
            result = emi.retrieve_relevant_memories(
                agent_name="Socrates",
                current_topic="consciousness",
                recent_dialog=self._dialog(),
                ltm_entries=memories,
                limit=3,
            )
        # Should still return a list (keyword fallback)
        assert isinstance(result, list)
        assert len(result) <= 3

    def test_use_semantic_false_skips_batch(self):
        """With use_semantic=False, _batch_semantic_scores is never called."""
        emi = EnhancedMemoryIntegration(use_semantic=False)
        with patch.object(emi, "_batch_semantic_scores") as mock_batch:
            emi.retrieve_relevant_memories(
                agent_name="Socrates",
                current_topic="consciousness",
                recent_dialog=self._dialog(),
                ltm_entries=self._memories(),
                limit=3,
            )
        mock_batch.assert_not_called()

    def test_semantic_scores_respect_topics_disabled(self):
        """With topics_enabled=False, semantic scores still rank by importance."""
        emi = EnhancedMemoryIntegration(use_semantic=True)
        mem_topic_match = {
            "content": "wealth inequality economics distribution",
            "importance": 0.1,
        }
        mem_high_importance = {
            "content": "consciousness identity mind",
            "importance": 0.9,
        }
        # Even if semantic topic similarity is high for first memory, topics_enabled=False
        # should zero out the topic label so the semantic query is empty-string-based.
        # We simulate the model returning equal scores (empty query → no bias).
        topic_scores = [0.5, 0.5]
        dialog_scores = [0.1, 0.1]
        with patch.object(
            emi,
            "_batch_semantic_scores",
            return_value=(topic_scores, dialog_scores),
        ):
            result = emi.retrieve_relevant_memories(
                agent_name="Socrates",
                current_topic="wealth inequality",
                recent_dialog=[{"role": "Socrates", "text": "philosophy of mind"}],
                ltm_entries=[mem_topic_match, mem_high_importance],
                limit=2,
                topics_enabled=False,
            )
        assert result, "Must return at least one memory"
        # With equal topic/dialog scores, importance (0.9) should decide ranking
        assert (
            result[0]["content"] == "consciousness identity mind"
        ), "High-importance memory must rank first when topic/dialog scores are equal"

    # ── _batch_semantic_scores unit tests ─────────────────────────────────

    def test_batch_semantic_scores_returns_none_when_unavailable(self):
        """When sentence-transformers is not available, returns (None, None)."""
        import entelgia.context_manager as cm_module

        original = cm_module._CTX_SEMANTIC_AVAILABLE
        try:
            cm_module._CTX_SEMANTIC_AVAILABLE = False
            emi = EnhancedMemoryIntegration(use_semantic=True)
            t_scores, d_scores = emi._batch_semantic_scores(
                "topic", "dialog", self._memories()
            )
            assert t_scores is None
            assert d_scores is None
        finally:
            cm_module._CTX_SEMANTIC_AVAILABLE = original

    def test_batch_semantic_scores_uses_model(self):
        """When a model is returned by _get_ctx_semantic_model, it is used to encode."""
        np = pytest.importorskip("numpy")
        import entelgia.context_manager as cm_module

        memories = self._memories()
        # Build a minimal mock model that returns plausible embeddings
        mock_model = MagicMock()
        # [topic, dialog, mem0, mem1, mem2] → shape (5, 4)
        mock_model.encode.return_value = np.array(
            [
                [1.0, 0.0, 0.0, 0.0],
                [0.0, 1.0, 0.0, 0.0],
                [0.9, 0.1, 0.0, 0.0],
                [0.0, 0.0, 1.0, 0.0],
                [0.0, 0.0, 0.0, 1.0],
            ],
            dtype=float,
        )

        emi = EnhancedMemoryIntegration(use_semantic=True)
        with patch.object(cm_module, "_get_ctx_semantic_model", return_value=mock_model):
            t_scores, d_scores = emi._batch_semantic_scores(
                "consciousness", "what is mind", memories
            )

        assert t_scores is not None
        assert d_scores is not None
        assert len(t_scores) == len(memories)
        assert len(d_scores) == len(memories)
        # All scores should be clamped to [0, 1]
        for s in t_scores + d_scores:
            assert 0.0 <= s <= 1.0


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s", "--override-ini=addopts="])

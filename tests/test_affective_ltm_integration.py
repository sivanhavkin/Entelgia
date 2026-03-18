# tests/test_affective_ltm_integration.py
"""
Tests for the affective LTM supplement integrated into Agent._build_compact_prompt()
and Agent._build_enhanced_prompt().

Covers:
1. Existing behavior is unchanged when use_affective_ltm=False.
2. When enabled, affective retrieval augments (not replaces) the memory context.
3. Empty affective results do not break the prompt pipeline.
4. Deduplication is applied (exact id and exact content).
5. Size limit is respected (affective_ltm_limit).
6. The [AFFECTIVE-LTM] log line is emitted when enabled.
"""

import sys
import os
import logging
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_memory(mem_id, content, importance=0.5, emotion_intensity=0.5, topic=""):
    """Construct a minimal LTM memory dict."""
    return {
        "id": mem_id,
        "content": content,
        "topic": topic,
        "importance": importance,
        "emotion_intensity": emotion_intensity,
        "emotion": "neutral",
    }


def _make_agent(cfg_overrides=None):
    """
    Build a minimal Agent-like object that exercises the affective LTM logic
    without needing a live LLM or SQLite database.

    Rather than instantiating the full Agent class (which requires an LLM,
    database, etc.), we assemble just enough state so that
    _build_compact_prompt() can be called in isolation.
    """
    # Inline import to avoid module-level side effects at collection time.
    import Entelgia_production_meta as mod

    # ── Minimal Config ──────────────────────────────────────────────────────
    cfg = mod.Config.__new__(mod.Config)
    # Apply dataclass defaults manually to avoid __post_init__ side effects.
    defaults = {
        "use_affective_ltm": True,
        "affective_emotion_weight": 0.4,
        "affective_ltm_limit": 3,
        "affective_ltm_min_score": 0.2,
        "show_pronoun": False,
        "web_research_enabled": False,
        "web_research_max_results": 3,
    }
    if cfg_overrides:
        defaults.update(cfg_overrides)
    for k, v in defaults.items():
        setattr(cfg, k, v)

    # Patch module-level CFG
    mod.CFG = cfg

    # ── Minimal memory mock ─────────────────────────────────────────────────
    memory = MagicMock()
    memory.stm_load.return_value = []
    memory.ltm_recent.return_value = []
    memory.ltm_search_affective.return_value = []

    # ── Minimal Agent stub ──────────────────────────────────────────────────
    agent = MagicMock(spec=mod.Agent)
    agent.name = "Socrates"
    agent.persona = "Philosopher"
    agent.persona_dict = None
    agent.drives = {
        "id_strength": 5.0,
        "ego_strength": 5.0,
        "superego_strength": 5.0,
        "self_awareness": 0.55,
    }
    agent.use_enhanced = False
    agent.context_mgr = None
    agent.memory = memory
    agent._last_emotion = "curious"
    agent._last_emotion_intensity = 0.6
    agent.topic_style = ""
    agent.topic_cluster = ""
    agent._last_topic = ""

    # Bind the real method to our stub so it uses the actual implementation.
    agent._build_compact_prompt = mod.Agent._build_compact_prompt.__get__(
        agent, mod.Agent
    )
    agent._fetch_affective_ltm_supplement = (
        mod.Agent._fetch_affective_ltm_supplement.__get__(agent, mod.Agent)
    )
    # _extract_topic_from_seed is a @staticmethod; assign the underlying function
    agent._extract_topic_from_seed = mod.Agent._extract_topic_from_seed
    agent.debate_profile = MagicMock(
        return_value={
            "style": "reflective",
            "tone": "calm",
            "depth": 0.7,
        }
    )

    return agent, memory, cfg


# ---------------------------------------------------------------------------
# Tests: use_affective_ltm=False (disabled)
# ---------------------------------------------------------------------------


class TestAffectiveLTMDisabled:
    """When use_affective_ltm=False, ltm_search_affective must not be called."""

    def test_affective_retrieval_not_called_when_disabled(self):
        """ltm_search_affective is never called when feature is disabled."""
        agent, memory, cfg = _make_agent({"use_affective_ltm": False})
        memory.ltm_recent.return_value = [
            _make_memory(1, "Recent memory about consciousness.")
        ]

        prompt = agent._build_compact_prompt("TOPIC: Free will\nWhat is free will?", [])

        memory.ltm_search_affective.assert_not_called()

    def test_recent_ltm_still_included_when_disabled(self):
        """Existing recent memories still appear in prompt when feature disabled."""
        agent, memory, cfg = _make_agent({"use_affective_ltm": False})
        memory.ltm_recent.return_value = [
            _make_memory(1, "Plato believed in the immortality of the soul.")
        ]

        prompt = agent._build_compact_prompt("TOPIC: Free will\nWhat is free will?", [])

        assert "Plato believed in the immortality" in prompt

    def test_prompt_format_unchanged_when_disabled(self):
        """Prompt structure is identical to pre-feature baseline when disabled."""
        agent, memory, cfg = _make_agent({"use_affective_ltm": False})
        memory.ltm_recent.return_value = []

        prompt = agent._build_compact_prompt("What is truth?", [])

        assert "PERSONA:" in prompt
        assert "SEED:" in prompt


# ---------------------------------------------------------------------------
# Tests: use_affective_ltm=True, normal augmentation
# ---------------------------------------------------------------------------


class TestAffectiveLTMAugmentation:
    """When enabled and affective results exist, they augment recent memories."""

    def test_affective_memories_appended_to_recent(self):
        """Affective memories appear after recent memories in merged bundle."""
        agent, memory, cfg = _make_agent()
        recent_mem = _make_memory(1, "Recent memory about logic.", importance=0.3,
                                   emotion_intensity=0.1)
        affective_mem = _make_memory(
            2, "Emotionally salient memory about grief.", importance=0.5,
            emotion_intensity=0.9
        )
        memory.ltm_recent.return_value = [recent_mem]
        memory.ltm_search_affective.return_value = [affective_mem]

        prompt = agent._build_compact_prompt("What is truth?", [])

        assert "Recent memory about logic." in prompt
        assert "Emotionally salient memory about grief." in prompt

    def test_ltm_search_affective_called_with_agent_name(self):
        """ltm_search_affective is called with the correct agent name."""
        agent, memory, cfg = _make_agent()
        memory.ltm_search_affective.return_value = []

        agent._build_compact_prompt("What is truth?", [])

        memory.ltm_search_affective.assert_called_once()
        call_args = memory.ltm_search_affective.call_args
        assert call_args[0][0] == "Socrates" or call_args[1].get("agent") == "Socrates"

    def test_recent_ltm_still_present_when_affective_enabled(self):
        """Recent memories are never dropped when affective retrieval is enabled."""
        agent, memory, cfg = _make_agent()
        recent_mem = _make_memory(1, "Recent philosophical insight.")
        memory.ltm_recent.return_value = [recent_mem]
        memory.ltm_search_affective.return_value = []

        prompt = agent._build_compact_prompt("What is justice?", [])

        assert "Recent philosophical insight." in prompt


# ---------------------------------------------------------------------------
# Tests: empty affective results
# ---------------------------------------------------------------------------


class TestAffectiveLTMEmptyResults:
    """Empty affective results must not break the pipeline."""

    def test_empty_affective_results_no_error(self):
        """No exception raised when ltm_search_affective returns empty list."""
        agent, memory, cfg = _make_agent()
        memory.ltm_recent.return_value = [
            _make_memory(1, "Regular memory.")
        ]
        memory.ltm_search_affective.return_value = []

        prompt = agent._build_compact_prompt("What is knowledge?", [])

        assert "Regular memory." in prompt

    def test_empty_affective_and_empty_recent_no_error(self):
        """No exception when both sources return empty."""
        agent, memory, cfg = _make_agent()
        memory.ltm_recent.return_value = []
        memory.ltm_search_affective.return_value = []

        prompt = agent._build_compact_prompt("What is knowledge?", [])

        assert "PERSONA:" in prompt


# ---------------------------------------------------------------------------
# Tests: fallback when ltm_search_affective raises
# ---------------------------------------------------------------------------


class TestAffectiveLTMFallback:
    """Errors from ltm_search_affective must not propagate; fallback is silent."""

    def test_exception_in_affective_retrieval_does_not_break_prompt(self):
        """Prompt is still produced even if ltm_search_affective raises."""
        agent, memory, cfg = _make_agent()
        memory.ltm_recent.return_value = [_make_memory(1, "Safe memory.")]
        memory.ltm_search_affective.side_effect = RuntimeError("DB error")

        prompt = agent._build_compact_prompt("What is truth?", [])

        assert "Safe memory." in prompt
        assert "PERSONA:" in prompt

    def test_recent_ltm_preserved_on_affective_error(self):
        """Recent memories remain when affective retrieval errors."""
        agent, memory, cfg = _make_agent()
        recent_mem = _make_memory(1, "Preserved on error.")
        memory.ltm_recent.return_value = [recent_mem]
        memory.ltm_search_affective.side_effect = Exception("Network failure")

        prompt = agent._build_compact_prompt("What is virtue?", [])

        assert "Preserved on error." in prompt


# ---------------------------------------------------------------------------
# Tests: deduplication
# ---------------------------------------------------------------------------


class TestAffectiveLTMDeduplication:
    """Affective memories that duplicate recent memories must be excluded."""

    def test_duplicate_by_id_excluded(self):
        """Memory already in recent list (same id) is not added twice."""
        agent, memory, cfg = _make_agent()
        mem = _make_memory(42, "Unique content about justice.", importance=0.8,
                            emotion_intensity=0.9)
        memory.ltm_recent.return_value = [mem]
        # Return the same memory from affective as well
        memory.ltm_search_affective.return_value = [mem]

        prompt = agent._build_compact_prompt("What is justice?", [])

        # Content appears exactly once
        assert prompt.count("Unique content about justice.") == 1

    def test_duplicate_by_content_excluded(self):
        """Memory with same content but different id is not added twice."""
        agent, memory, cfg = _make_agent()
        content = "The unexamined life is not worth living."
        recent_mem = _make_memory(1, content, importance=0.4, emotion_intensity=0.3)
        affective_mem = _make_memory(99, content, importance=0.9, emotion_intensity=0.95)
        memory.ltm_recent.return_value = [recent_mem]
        memory.ltm_search_affective.return_value = [affective_mem]

        prompt = agent._build_compact_prompt("What is wisdom?", [])

        assert prompt.count(content) == 1


# ---------------------------------------------------------------------------
# Tests: size limit
# ---------------------------------------------------------------------------


class TestAffectiveLTMSizeLimit:
    """Number of affective memories added must not exceed affective_ltm_limit."""

    def test_affective_limit_respected(self):
        """At most affective_ltm_limit new affective memories are added."""
        limit = 2
        agent, memory, cfg = _make_agent({"affective_ltm_limit": limit})
        memory.ltm_recent.return_value = []
        # Return more candidates than the limit
        candidates = [
            _make_memory(i, f"Affective memory #{i}.", importance=0.8,
                          emotion_intensity=0.8)
            for i in range(1, 10)
        ]
        memory.ltm_search_affective.return_value = candidates

        prompt = agent._build_compact_prompt("What is truth?", [])

        # Count how many affective memories appear
        included = sum(
            1 for i in range(1, 10) if f"Affective memory #{i}." in prompt
        )
        assert included <= limit


# ---------------------------------------------------------------------------
# Tests: minimum score filter
# ---------------------------------------------------------------------------


class TestAffectiveLTMMinScore:
    """Memories below affective_ltm_min_score must be excluded."""

    def test_low_score_memories_excluded(self):
        """Memory with combined score below threshold is not included."""
        agent, memory, cfg = _make_agent(
            {"affective_ltm_min_score": 0.5, "affective_emotion_weight": 0.4}
        )
        memory.ltm_recent.return_value = []
        # score = 0.1 * 0.6 + 0.05 * 0.4 = 0.06 + 0.02 = 0.08 < 0.5
        low_score_mem = _make_memory(
            1, "Low importance low emotion memory.", importance=0.1,
            emotion_intensity=0.05
        )
        memory.ltm_search_affective.return_value = [low_score_mem]

        prompt = agent._build_compact_prompt("What is beauty?", [])

        assert "Low importance low emotion memory." not in prompt

    def test_high_score_memories_included(self):
        """Memory with combined score at or above threshold is included."""
        agent, memory, cfg = _make_agent(
            {"affective_ltm_min_score": 0.2, "affective_emotion_weight": 0.4}
        )
        memory.ltm_recent.return_value = []
        # score = 0.5 * 0.6 + 0.5 * 0.4 = 0.5 >= 0.2
        high_score_mem = _make_memory(
            2, "High salience emotional memory.", importance=0.5,
            emotion_intensity=0.5
        )
        memory.ltm_search_affective.return_value = [high_score_mem]

        prompt = agent._build_compact_prompt("What is truth?", [])

        assert "High salience emotional memory." in prompt


# ---------------------------------------------------------------------------
# Tests: logging
# ---------------------------------------------------------------------------


class TestAffectiveLTMLogging:
    """The [AFFECTIVE-LTM] log line must be emitted when feature is enabled."""

    def test_affective_log_line_emitted_when_enabled(self, caplog):
        """AFFECTIVE-LTM log record is present when retrieval runs."""
        agent, memory, cfg = _make_agent()
        memory.ltm_search_affective.return_value = [
            _make_memory(10, "Emotionally vivid recollection.", importance=0.7,
                          emotion_intensity=0.8)
        ]

        with caplog.at_level(logging.INFO):
            agent._build_compact_prompt("What is courage?", [])

        affective_logs = [
            r for r in caplog.records if "[AFFECTIVE-LTM]" in r.getMessage()
        ]
        assert len(affective_logs) >= 1
        log_msg = affective_logs[0].getMessage()
        assert "agent=Socrates" in log_msg
        assert "emotion=" in log_msg
        assert "retrieved=" in log_msg
        assert "used=" in log_msg

    def test_no_affective_log_when_disabled(self, caplog):
        """No AFFECTIVE-LTM log line when use_affective_ltm=False."""
        agent, memory, cfg = _make_agent({"use_affective_ltm": False})
        memory.ltm_search_affective.return_value = [
            _make_memory(10, "Should not appear.")
        ]

        with caplog.at_level(logging.INFO):
            agent._build_compact_prompt("What is courage?", [])

        affective_logs = [
            r for r in caplog.records if "[AFFECTIVE-LTM]" in r.getMessage()
        ]
        assert len(affective_logs) == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s", "--override-ini=addopts="])

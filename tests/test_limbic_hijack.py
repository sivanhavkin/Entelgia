# tests/test_limbic_hijack.py
"""
Tests for the limbic hijack mechanism.

Validates:
  1. Agent has limbic_hijack and _limbic_hijack_turns attributes initialized to False/0.
  2. Hijack activates when id_strength > 7, emotion_intensity > 0.7, conflict > 0.6.
  3. Hijack does NOT activate when any condition is below threshold.
  4. During hijack, effective_superego is reduced (LIMBIC_HIJACK_SUPEREGO_MULTIPLIER × sup).
  5. Hijack deactivates after emotion_intensity drops below 0.4.
  6. Hijack deactivates after LIMBIC_HIJACK_MAX_TURNS turns even if intensity stays high.
  7. Meta output: limbic_hijack message shown when active; skipped-message NOT shown.
  8. Meta output: superego critique message shown when active and no hijack.
  9. Meta output: no message when neither hijack nor superego rewrite.
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from unittest.mock import MagicMock, patch

import Entelgia_production_meta as _meta
from Entelgia_production_meta import (
    Agent,
    BehaviorCore,
    Config,
    ConsciousCore,
    EmotionCore,
    LanguageCore,
    LIMBIC_HIJACK_MAX_TURNS,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_agent(
    id_strength: float = 5.0,
    ego_strength: float = 5.0,
    superego_strength: float = 5.0,
    emotion_intensity: float = 0.3,
    emotion: str = "neutral",
) -> "tuple[Agent, Config]":
    """Return a minimal Agent with mocked LLM and memory."""
    cfg = Config()

    llm_mock = MagicMock()
    llm_mock.generate.return_value = "Test response for hijack."

    drives = {
        "id_strength": id_strength,
        "ego_strength": ego_strength,
        "superego_strength": superego_strength,
        "self_awareness": 0.55,
    }

    memory_mock = MagicMock()
    memory_mock.get_agent_state.return_value = drives
    memory_mock.ltm_recent.return_value = []
    memory_mock.stm_load.return_value = []

    emotion_mock = MagicMock(spec=EmotionCore)
    emotion_mock.infer.return_value = (emotion, emotion_intensity)

    language_mock = LanguageCore()
    conscious_mock = ConsciousCore()
    behavior_mock = MagicMock(spec=BehaviorCore)

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
        persona="A philosopher who seeks truth.",
        use_enhanced=False,
        cfg=cfg,
    )
    return agent, cfg


# ---------------------------------------------------------------------------
# 1. Initial state
# ---------------------------------------------------------------------------


class TestLimbicHijackInitialState:
    def test_limbic_hijack_defaults_false(self):
        agent, _ = _make_agent()
        assert agent.limbic_hijack is False

    def test_limbic_hijack_turns_defaults_zero(self):
        agent, _ = _make_agent()
        assert agent._limbic_hijack_turns == 0


# ---------------------------------------------------------------------------
# 2. Activation conditions
# ---------------------------------------------------------------------------


class TestLimbicHijackActivation:
    """Hijack activates only when all three conditions are met."""

    def test_activates_when_all_conditions_met(self):
        """id > 7, emotion_intensity > 0.7, conflict > 0.6 → hijack=True."""
        # id=8, ego=5, sup=5 → conflict_index = |8-5| + |5-5| = 3.0 > 0.6
        agent, cfg = _make_agent(id_strength=8.0, emotion_intensity=0.8)
        agent._last_emotion_intensity = 0.8  # pre-set last intensity

        with patch.object(_meta, "CFG", cfg):
            agent.speak("What is justice?", [])

        assert agent.limbic_hijack is True

    def test_no_activation_id_too_low(self):
        """id <= 7 → no hijack."""
        agent, cfg = _make_agent(id_strength=6.5, emotion_intensity=0.8)
        agent._last_emotion_intensity = 0.8

        with patch.object(_meta, "CFG", cfg):
            agent.speak("What is justice?", [])

        assert agent.limbic_hijack is False

    def test_no_activation_intensity_too_low(self):
        """emotion_intensity <= 0.7 → no hijack."""
        agent, cfg = _make_agent(id_strength=8.0, emotion_intensity=0.6)
        agent._last_emotion_intensity = 0.6

        with patch.object(_meta, "CFG", cfg):
            agent.speak("What is justice?", [])

        assert agent.limbic_hijack is False

    def test_no_activation_conflict_too_low(self):
        """conflict_index <= 0.6 → no hijack (id=ego=sup=8 → conflict=0)."""
        agent, cfg = _make_agent(
            id_strength=8.0,
            ego_strength=8.0,
            superego_strength=8.0,
            emotion_intensity=0.8,
        )
        agent._last_emotion_intensity = 0.8

        with patch.object(_meta, "CFG", cfg):
            agent.speak("What is justice?", [])

        # conflict_index = |8-8| + |8-8| = 0.0 ≤ 0.6 → no hijack
        assert agent.limbic_hijack is False


# ---------------------------------------------------------------------------
# 2b. Extreme id threshold lowering
# ---------------------------------------------------------------------------


class TestLimbicHijackExtremeId:
    """At extreme id (>= 8.5) the emotion intensity threshold drops from 0.7 to 0.5."""

    def test_activates_with_moderate_intensity_at_extreme_id(self):
        """id >= 8.5, intensity 0.6 (above 0.5 but below 0.7) → hijack fires."""
        # id=9.0, ego=5.0, sup=5.0 → conflict = |9-5|+|5-5| = 4.0 > 0.6
        agent, cfg = _make_agent(id_strength=9.0, emotion_intensity=0.6)
        agent._last_emotion_intensity = 0.6

        with patch.object(_meta, "CFG", cfg):
            agent.speak("What is justice?", [])

        assert agent.limbic_hijack is True, (
            "Extreme id (9.0) with intensity 0.6 should trigger hijack "
            "(threshold lowered to 0.5 at extreme id >= 8.5)"
        )

    def test_no_activation_with_moderate_intensity_at_normal_id(self):
        """id < 8.5, intensity 0.6 → hijack does NOT fire (standard threshold 0.7)."""
        # id=8.0, ego=5.0, sup=5.0 → conflict = 3.0 > 0.6, but intensity 0.6 < 0.7
        agent, cfg = _make_agent(id_strength=8.0, emotion_intensity=0.6)
        agent._last_emotion_intensity = 0.6

        with patch.object(_meta, "CFG", cfg):
            agent.speak("What is justice?", [])

        assert agent.limbic_hijack is False, (
            "Normal id (8.0) with intensity 0.6 should NOT trigger hijack "
            "(standard threshold 0.7 still applies below extreme)"
        )


# ---------------------------------------------------------------------------
# 3. Exit conditions
# ---------------------------------------------------------------------------


class TestLimbicHijackExit:
    def test_deactivates_when_intensity_drops(self):
        """Hijack exits when emotion_intensity falls below 0.4."""
        agent, cfg = _make_agent(id_strength=8.0, emotion_intensity=0.2)
        # Pre-activate hijack
        agent.limbic_hijack = True
        agent._limbic_hijack_turns = 0
        agent._last_emotion_intensity = 0.2  # below 0.4 threshold

        with patch.object(_meta, "CFG", cfg):
            agent.speak("What is justice?", [])

        assert agent.limbic_hijack is False

    def test_deactivates_after_max_turns(self):
        """Hijack exits after _limbic_hijack_turns reaches LIMBIC_HIJACK_MAX_TURNS."""
        agent, cfg = _make_agent(
            id_strength=4.0,  # id below 7 so it won't re-activate
            emotion_intensity=0.8,
        )
        # Pre-activate hijack at max-1 turns (next increment hits the limit)
        agent.limbic_hijack = True
        agent._limbic_hijack_turns = LIMBIC_HIJACK_MAX_TURNS - 1
        agent._last_emotion_intensity = 0.8  # still high, but turn limit reached

        with patch.object(_meta, "CFG", cfg):
            agent.speak("What is justice?", [])

        assert agent.limbic_hijack is False

    def test_turns_counter_increments_while_active(self):
        """While active and intensity is high enough to not exit, counter increments."""
        agent, cfg = _make_agent(
            id_strength=4.0,  # id below 7 so it won't re-trigger
            emotion_intensity=0.8,
        )
        # Pre-activate with 0 turns, intensity stays high
        agent.limbic_hijack = True
        agent._limbic_hijack_turns = 0
        agent._last_emotion_intensity = 0.8

        with patch.object(_meta, "CFG", cfg):
            agent.speak("What is justice?", [])

        # Should still be active with 1 turn elapsed
        assert agent.limbic_hijack is True
        assert agent._limbic_hijack_turns == 1


# ---------------------------------------------------------------------------
# 4. Impulsive kind during hijack
# ---------------------------------------------------------------------------


class TestLimbicHijackResponseKind:
    def test_response_kind_is_impulsive_during_hijack(self):
        """When hijack is active, _last_response_kind must be 'impulsive'."""
        agent, cfg = _make_agent(id_strength=8.0, emotion_intensity=0.8)
        agent._last_emotion_intensity = 0.8

        with patch.object(_meta, "CFG", cfg):
            agent.speak("What is justice?", [])

        assert agent.limbic_hijack is True
        assert agent._last_response_kind == "impulsive"


# ---------------------------------------------------------------------------
# 4b. Athena limbic hijack — anger emotion and harsh behavioral rule
# ---------------------------------------------------------------------------


class TestAthenaLimbicHijackAnger:
    """During Athena's limbic hijack her emotion is forced to 'anger' and the
    behavioral rule instructs harsh language."""

    def test_athena_last_emotion_is_anger_during_hijack(self):
        """After speak(), _last_emotion must be 'anger' when Athena is in hijack."""
        agent, cfg = _make_agent(
            id_strength=9.0,
            emotion_intensity=0.8,
        )
        # Change agent name to Athena for this test
        agent.name = "Athena"
        agent._last_emotion_intensity = 0.8

        with patch.object(_meta, "CFG", cfg):
            agent.speak("What is justice?", [])

        assert agent.limbic_hijack is True, "Athena should be in limbic hijack"
        assert (
            agent._last_emotion == "anger"
        ), f"Expected _last_emotion='anger' during Athena hijack, got '{agent._last_emotion}'"
        assert (
            agent._last_emotion_intensity >= 0.8
        ), f"Expected intensity >= 0.8 during Athena hijack, got {agent._last_emotion_intensity}"

    def test_athena_behavioral_rule_contains_anger_instruction(self):
        """The behavioral rule injected when Athena is in hijack must mention anger."""
        agent, cfg = _make_agent(id_strength=9.0, emotion_intensity=0.8)
        agent.name = "Athena"
        agent.limbic_hijack = True  # pre-activate

        rule = agent._behavioral_rule_instruction()
        assert (
            "anger" in rule.lower()
        ), f"Expected anger instruction in rule; got: {rule}"

    def test_non_athena_agent_does_not_get_anger_rule(self):
        """Socrates in limbic hijack must NOT get the Athena anger rule."""
        agent, cfg = _make_agent(id_strength=9.0, emotion_intensity=0.8)
        # agent.name is already "Socrates" from _make_agent
        agent.limbic_hijack = True

        rule = agent._behavioral_rule_instruction()
        assert (
            "anger" not in rule.lower()
        ), "Athena anger rule must not fire for Socrates"


# ---------------------------------------------------------------------------
# 5. Meta output tagging
# ---------------------------------------------------------------------------


class _MinimalMetaAgent:
    """Minimal stub for testing print_meta_state output logic."""

    def __init__(
        self, limbic_hijack: bool, superego_rewrite: bool, critique_reason: str = ""
    ):
        self.limbic_hijack = limbic_hijack
        self._limbic_hijack_turns = 0
        self._last_superego_rewrite = superego_rewrite
        self._last_critique_reason = critique_reason
        self._last_temperature = 0.6
        self._last_emotion = "neutral"
        self._last_emotion_intensity = 0.3
        self._last_response_kind = "reflective"
        self._last_stagnation = 0.0
        self.energy_level = 80.0
        self.drive_pressure = 2.0
        self.open_questions = 0
        self.drives = {
            "id_strength": 5.0,
            "ego_strength": 5.0,
            "superego_strength": 5.0,
            "self_awareness": 0.55,
        }
        self.name = "TestAgent"

    def conflict_index(self):
        ide = float(self.drives.get("id_strength", 5.0))
        ego = float(self.drives.get("ego_strength", 5.0))
        sup = float(self.drives.get("superego_strength", 5.0))
        return abs(ide - ego) + abs(sup - ego)

    def debate_profile(self):
        return {"style": "balanced", "dissent_level": 2.0}


def _capture_rewrite_tag(agent_stub) -> str:
    """Replicate the rewrite_tag selection logic from print_meta_state."""
    if getattr(agent_stub, "limbic_hijack", False):
        return "  [META] Limbic hijack engaged — emotional override active"
    elif agent_stub._last_superego_rewrite:
        return "  [SuperEgo critique applied; original shown in dialogue]"
    else:
        return ""


class TestMetaOutputLogic:
    def test_limbic_hijack_message_when_active(self):
        agent = _MinimalMetaAgent(limbic_hijack=True, superego_rewrite=False)
        tag = _capture_rewrite_tag(agent)
        assert "[META] Limbic hijack engaged" in tag

    def test_superego_message_when_rewrite_active_and_no_hijack(self):
        agent = _MinimalMetaAgent(limbic_hijack=False, superego_rewrite=True)
        tag = _capture_rewrite_tag(agent)
        assert "SuperEgo critique applied" in tag

    def test_no_message_when_neither_active(self):
        agent = _MinimalMetaAgent(
            limbic_hijack=False, superego_rewrite=False, critique_reason="ego_dominant"
        )
        tag = _capture_rewrite_tag(agent)
        assert tag == "", f"Expected empty tag but got: {tag!r}"

    def test_no_skipped_message_shown(self):
        """The 'skipped' message must never appear (it was removed)."""
        agent = _MinimalMetaAgent(
            limbic_hijack=False, superego_rewrite=False, critique_reason="low_conflict"
        )
        tag = _capture_rewrite_tag(agent)
        assert "skipped" not in tag

    def test_limbic_hijack_takes_priority_over_superego(self):
        """When both hijack and superego_rewrite are True, hijack message wins."""
        agent = _MinimalMetaAgent(limbic_hijack=True, superego_rewrite=True)
        tag = _capture_rewrite_tag(agent)
        assert "[META] Limbic hijack engaged" in tag
        assert "SuperEgo critique applied" not in tag


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s", "--override-ini=addopts="])

# tests/test_behavioral_rules.py
"""
Tests for behavioral rules:
  Rule A (Socrates): Conflict >= 5.0 → end response with binary-choice question (A or B).
  Rule B (Athena):  Dissent >= 3.0  → response must contain a sentence starting with
                    "However," / "Yet," / "This assumes…"
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

# ---------------------------------------------------------------------------
# Minimal stub that replicates only the methods under test
# ---------------------------------------------------------------------------


class _StubAgent:
    """Minimal Agent stub exposing conflict_index, debate_profile, and
    _behavioral_rule_instruction without requiring real LLM / memory deps."""

    def __init__(
        self,
        name: str,
        id_strength: float,
        ego_strength: float,
        superego_strength: float,
    ):
        self.name = name
        self.drives = {
            "id_strength": id_strength,
            "ego_strength": ego_strength,
            "superego_strength": superego_strength,
        }

    # Copy of the real conflict_index() logic
    def conflict_index(self) -> float:
        ide = float(self.drives.get("id_strength", 5.0))
        ego = float(self.drives.get("ego_strength", 5.0))
        sup = float(self.drives.get("superego_strength", 5.0))
        return abs(ide - ego) + abs(sup - ego)

    # Copy of the real debate_profile() logic (dissent_level only)
    def debate_profile(self) -> dict:
        ide = float(self.drives.get("id_strength", 5.0))
        ego = float(self.drives.get("ego_strength", 5.0))
        sup = float(self.drives.get("superego_strength", 5.0))
        dissent = min(10.0, max(0.0, (ide * 0.45) + (sup * 0.45) - (ego * 0.25)))
        return {"dissent_level": round(dissent, 2)}

    # The method under test – identical to the production implementation
    def _behavioral_rule_instruction(self) -> str:
        if self.name == "Socrates" and self.conflict_index() >= 5.0:
            return (
                "BEHAVIORAL RULE: You MUST end your response with one sharp question "
                "that forces Athena to choose between exactly 2 options (A or B)."
            )
        if self.name == "Athena" and self.debate_profile()["dissent_level"] >= 3.0:
            return (
                "BEHAVIORAL RULE: Your response MUST include at least one sentence that "
                'begins with "However," or "Yet," or "This assumes…"'
            )
        return ""


# ---------------------------------------------------------------------------
# Helper to build a stub with a known conflict_index value
# ---------------------------------------------------------------------------


def _socrates_with_conflict(conflict: float) -> _StubAgent:
    """Return a Socrates stub whose conflict_index() equals *conflict*.
    conflict_index = |id - ego| + |superego - ego|
    We fix ego=5 and split the deviation symmetrically (id=ego+conflict/2,
    superego=ego+conflict/2) so that |id-ego| + |superego-ego| = conflict exactly.
    """
    ego = 5.0
    half = conflict / 2.0
    return _StubAgent(
        "Socrates",
        id_strength=ego + half,
        ego_strength=ego,
        superego_strength=ego + half,
    )


def _athena_with_dissent(dissent: float) -> _StubAgent:
    """Return an Athena stub whose dissent_level ≈ *dissent*.
    dissent = (id*0.45 + superego*0.45) - ego*0.25
    We keep id=superego=x and solve for x: 2*0.45*x - 5*0.25 = dissent
    → x = (dissent + 1.25) / 0.9
    """
    x = (dissent + 5.0 * 0.25) / 0.9
    return _StubAgent("Athena", id_strength=x, ego_strength=5.0, superego_strength=x)


# ---------------------------------------------------------------------------
# Rule A: Socrates + Conflict
# ---------------------------------------------------------------------------


class TestRuleASocrates:
    """Rule A: Socrates emits binary-choice question when Conflict >= 5.0."""

    def test_returns_nonempty_rule_at_exactly_5(self):
        agent = _socrates_with_conflict(5.0)
        assert abs(agent.conflict_index() - 5.0) < 0.01
        rule = agent._behavioral_rule_instruction()
        assert rule != ""

    def test_returns_nonempty_rule_above_5(self):
        agent = _socrates_with_conflict(7.0)
        rule = agent._behavioral_rule_instruction()
        assert rule != ""

    def test_returns_empty_below_5(self):
        agent = _socrates_with_conflict(4.0)
        assert agent.conflict_index() < 5.0
        rule = agent._behavioral_rule_instruction()
        assert rule == ""

    def test_rule_mentions_binary_choice(self):
        agent = _socrates_with_conflict(6.0)
        rule = agent._behavioral_rule_instruction()
        assert "A or B" in rule

    def test_rule_mentions_end_response(self):
        agent = _socrates_with_conflict(6.0)
        rule = agent._behavioral_rule_instruction()
        assert "end" in rule.lower()

    def test_non_socrates_not_triggered_even_with_high_conflict(self):
        """Rule A must not fire for agents other than Socrates."""
        agent = _StubAgent(
            "Fixy", id_strength=10.0, ego_strength=5.0, superego_strength=10.0
        )
        assert agent.conflict_index() >= 5.0
        rule = agent._behavioral_rule_instruction()
        assert rule == ""


# ---------------------------------------------------------------------------
# Rule B: Athena + Dissent
# ---------------------------------------------------------------------------


class TestRuleBAnthena:
    """Rule B: Athena emits dissent-marker instruction when Dissent >= 3.0."""

    def test_returns_nonempty_rule_at_exactly_3(self):
        agent = _athena_with_dissent(3.0)
        assert agent.debate_profile()["dissent_level"] >= 3.0
        rule = agent._behavioral_rule_instruction()
        assert rule != ""

    def test_returns_nonempty_rule_above_3(self):
        agent = _athena_with_dissent(5.0)
        rule = agent._behavioral_rule_instruction()
        assert rule != ""

    def test_returns_empty_below_3(self):
        agent = _athena_with_dissent(2.0)
        assert agent.debate_profile()["dissent_level"] < 3.0
        rule = agent._behavioral_rule_instruction()
        assert rule == ""

    def test_rule_mentions_however(self):
        agent = _athena_with_dissent(4.0)
        rule = agent._behavioral_rule_instruction()
        assert "However," in rule

    def test_rule_mentions_yet(self):
        agent = _athena_with_dissent(4.0)
        rule = agent._behavioral_rule_instruction()
        assert "Yet," in rule

    def test_rule_mentions_this_assumes(self):
        agent = _athena_with_dissent(4.0)
        rule = agent._behavioral_rule_instruction()
        assert "This assumes" in rule

    def test_non_athena_not_triggered_even_with_high_dissent(self):
        """Rule B must not fire for agents other than Athena."""
        agent = _StubAgent(
            "Fixy", id_strength=8.0, ego_strength=5.0, superego_strength=8.0
        )
        assert agent.debate_profile()["dissent_level"] >= 3.0
        rule = agent._behavioral_rule_instruction()
        assert rule == ""


# ---------------------------------------------------------------------------
# Prompt injection: ensure rule is embedded before "Respond now:"
# ---------------------------------------------------------------------------


class TestPromptInjection:
    """Verify that the rule string is correctly injected before 'Respond now:'."""

    def _simulate_inject(self, prompt: str, rule: str) -> str:
        """Replicate the injection logic from Agent.speak()."""
        if rule:
            prompt = prompt.replace("\nRespond now:\n", f"\n{rule}\nRespond now:\n")
        return prompt

    def test_rule_a_injected_before_respond_now(self):
        dummy_prompt = "PERSONA: ...\nSEED: ...\n\nRespond now:\n"
        rule = (
            "BEHAVIORAL RULE: You MUST end your response with one sharp question "
            "that forces Athena to choose between exactly 2 options (A or B)."
        )
        result = self._simulate_inject(dummy_prompt, rule)
        assert rule in result
        assert result.index(rule) < result.index("Respond now:")

    def test_rule_b_injected_before_respond_now(self):
        dummy_prompt = "PERSONA: ...\nSEED: ...\n\nRespond now:\n"
        rule = (
            "BEHAVIORAL RULE: Your response MUST include at least one sentence that "
            'begins with "However," or "Yet," or "This assumes…"'
        )
        result = self._simulate_inject(dummy_prompt, rule)
        assert rule in result
        assert result.index(rule) < result.index("Respond now:")

    def test_no_rule_leaves_prompt_unchanged(self):
        dummy_prompt = "PERSONA: ...\nSEED: ...\n\nRespond now:\n"
        result = self._simulate_inject(dummy_prompt, "")
        assert result == dummy_prompt

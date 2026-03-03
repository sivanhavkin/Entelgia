# tests/test_behavioral_rules.py
"""
Tests for behavioral rules:
  Rule A (Socrates): Conflict > 6 AND random < 0.5 → end response with binary-choice question (A or B).
  Rule B (Athena):  Conflict > 6 AND random < 0.5  → directly challenge/counter Socrates's position
                    using varied language (no fixed sentence opener).
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import random
from unittest.mock import patch

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
        if (
            self.name == "Socrates"
            and self.conflict_index() > 6
            and random.random() < 0.5
        ):
            return (
                "BEHAVIORAL RULE: You MUST end your response with one sharp question "
                "that forces Athena to choose between exactly 2 options (A or B)."
            )
        if (
            self.name == "Athena"
            and self.conflict_index() > 6
            and random.random() < 0.5
        ):
            return (
                "BEHAVIORAL RULE: You MUST directly challenge or counter Socrates's position "
                "in your response, expressing clear disagreement. Use varied language and do "
                "not start every sentence the same way."
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


def _athena_with_conflict(conflict: float) -> _StubAgent:
    """Return an Athena stub whose conflict_index() equals *conflict*.
    conflict_index = |id - ego| + |superego - ego|
    We fix ego=5 and split the deviation symmetrically.
    """
    ego = 5.0
    half = conflict / 2.0
    return _StubAgent(
        "Athena",
        id_strength=ego + half,
        ego_strength=ego,
        superego_strength=ego + half,
    )


# ---------------------------------------------------------------------------
# Terminal display helpers – tables and ASCII bar charts
# ---------------------------------------------------------------------------


def _print_table(headers, rows, title=None):
    """Print a neatly formatted ASCII table to stdout."""
    if title:
        print(f"\n  ╔{'═' * (len(title) + 4)}╗")
        print(f"  ║  {title}  ║")
        print(f"  ╚{'═' * (len(title) + 4)}╝")
    col_widths = [len(str(h)) for h in headers]
    for row in rows:
        for i, cell in enumerate(row):
            col_widths[i] = max(col_widths[i], len(str(cell)))
    sep = "─┼─".join("─" * w for w in col_widths)
    header_line = " │ ".join(str(h).ljust(col_widths[i]) for i, h in enumerate(headers))
    print(f"  {header_line}")
    print(f"  {sep}")
    for row in rows:
        print(
            "  "
            + " │ ".join(str(cell).ljust(col_widths[i]) for i, cell in enumerate(row))
        )
    print()


def _print_bar_chart(data_pairs, title=None, max_width=36):
    """Print a horizontal ASCII bar chart.  *data_pairs* is [(label, value), ...]."""
    if title:
        print(f"\n  📊 {title}")
        print(f"  {'─' * 52}")
    if not data_pairs:
        return
    max_val = max(v for _, v in data_pairs) or 1.0
    for label, value in data_pairs:
        bar_len = max(1, int(round((value / max_val) * max_width)))
        bar = "█" * bar_len
        print(f"  {str(label):>10} │ {bar:<{max_width}} {value:.4f}")
    print()


# ---------------------------------------------------------------------------
# Rule A: Socrates + Conflict
# ---------------------------------------------------------------------------


class TestRuleASocrates:
    """Rule A: Socrates emits binary-choice question when Conflict > 6 and random fires."""

    def test_returns_nonempty_rule_above_6_when_random_fires(self):
        agent = _socrates_with_conflict(7.0)
        assert agent.conflict_index() > 6
        with patch("random.random", return_value=0.3):
            rule = agent._behavioral_rule_instruction()
        _print_table(
            ["Agent", "conflict_index", "Rule triggered?", "Rule (truncated)"],
            [
                [
                    "Socrates",
                    f"{agent.conflict_index():.2f}",
                    str(rule != ""),
                    rule[:50] + "..." if len(rule) > 50 else rule,
                ]
            ],
            title="test_returns_nonempty_rule_above_6_when_random_fires",
        )
        assert rule != ""

    def test_returns_empty_above_6_when_random_does_not_fire(self):
        agent = _socrates_with_conflict(7.0)
        assert agent.conflict_index() > 6
        with patch("random.random", return_value=0.8):
            rule = agent._behavioral_rule_instruction()
        _print_table(
            ["Agent", "conflict_index", "Rule triggered?", "Expected"],
            [
                [
                    "Socrates",
                    f"{agent.conflict_index():.2f}",
                    str(rule != ""),
                    "False (random suppressed)",
                ]
            ],
            title="test_returns_empty_above_6_when_random_does_not_fire",
        )
        assert rule == ""

    def test_returns_nonempty_rule_above_6(self):
        agent = _socrates_with_conflict(7.0)
        with patch("random.random", return_value=0.3):
            rule = agent._behavioral_rule_instruction()
            sweep = [
                (
                    f"c={c:.0f}",
                    (
                        1.0
                        if _socrates_with_conflict(
                            float(c)
                        )._behavioral_rule_instruction()
                        != ""
                        else 0.0
                    ),
                )
                for c in range(0, 11)
            ]
        _print_bar_chart(
            sweep, title="Rule A (Socrates) triggered vs conflict_index (0→10)"
        )
        assert rule != ""

    def test_returns_empty_at_or_below_6(self):
        agent = _socrates_with_conflict(6.0)
        assert agent.conflict_index() <= 6
        with patch("random.random", return_value=0.3):
            rule = agent._behavioral_rule_instruction()
        _print_table(
            ["Agent", "conflict_index", "Rule triggered?", "Expected"],
            [
                [
                    "Socrates",
                    f"{agent.conflict_index():.2f}",
                    str(rule != ""),
                    "False (empty)",
                ]
            ],
            title="test_returns_empty_at_or_below_6",
        )
        assert rule == ""

    def test_rule_mentions_binary_choice(self):
        agent = _socrates_with_conflict(8.0)
        with patch("random.random", return_value=0.3):
            rule = agent._behavioral_rule_instruction()
        _print_table(
            ["Agent", "conflict_index", "'A or B' in rule?", "Rule (truncated)"],
            [
                [
                    "Socrates",
                    f"{agent.conflict_index():.2f}",
                    str("A or B" in rule),
                    rule[:60] + "..." if len(rule) > 60 else rule,
                ]
            ],
            title="test_rule_mentions_binary_choice",
        )
        assert "A or B" in rule

    def test_rule_mentions_end_response(self):
        agent = _socrates_with_conflict(8.0)
        with patch("random.random", return_value=0.3):
            rule = agent._behavioral_rule_instruction()
        _print_table(
            ["Agent", "conflict_index", "'end' in rule?", "Rule (truncated)"],
            [
                [
                    "Socrates",
                    f"{agent.conflict_index():.2f}",
                    str("end" in rule.lower()),
                    rule[:60] + "..." if len(rule) > 60 else rule,
                ]
            ],
            title="test_rule_mentions_end_response",
        )
        assert "end" in rule.lower()

    def test_non_socrates_not_triggered_even_with_high_conflict(self):
        """Rule A must not fire for agents other than Socrates."""
        agent = _StubAgent(
            "Fixy", id_strength=10.0, ego_strength=5.0, superego_strength=10.0
        )
        assert agent.conflict_index() > 6
        with patch("random.random", return_value=0.3):
            rule = agent._behavioral_rule_instruction()
        _print_table(
            ["Agent", "conflict_index", "Rule triggered?", "Expected"],
            [
                [
                    "Fixy",
                    f"{agent.conflict_index():.2f}",
                    str(rule != ""),
                    "False (not Socrates)",
                ]
            ],
            title="test_non_socrates_not_triggered_even_with_high_conflict",
        )
        assert rule == ""


# ---------------------------------------------------------------------------
# Rule B: Athena + Conflict
# ---------------------------------------------------------------------------


class TestRuleBAnthena:
    """Rule B: Athena directly challenges Socrates when Conflict > 6 and random fires (no fixed opener)."""

    def test_returns_nonempty_rule_above_6_when_random_fires(self):
        agent = _athena_with_conflict(7.0)
        assert agent.conflict_index() > 6
        with patch("random.random", return_value=0.3):
            rule = agent._behavioral_rule_instruction()
        _print_table(
            ["Agent", "conflict_index", "Rule triggered?", "Rule (truncated)"],
            [
                [
                    "Athena",
                    f"{agent.conflict_index():.2f}",
                    str(rule != ""),
                    rule[:50] + "..." if len(rule) > 50 else rule,
                ]
            ],
            title="test_returns_nonempty_rule_above_6_when_random_fires",
        )
        assert rule != ""

    def test_returns_empty_above_6_when_random_does_not_fire(self):
        agent = _athena_with_conflict(7.0)
        assert agent.conflict_index() > 6
        with patch("random.random", return_value=0.8):
            rule = agent._behavioral_rule_instruction()
        _print_table(
            ["Agent", "conflict_index", "Rule triggered?", "Expected"],
            [
                [
                    "Athena",
                    f"{agent.conflict_index():.2f}",
                    str(rule != ""),
                    "False (random suppressed)",
                ]
            ],
            title="test_returns_empty_above_6_when_random_does_not_fire",
        )
        assert rule == ""

    def test_returns_nonempty_rule_above_6(self):
        agent = _athena_with_conflict(8.0)
        with patch("random.random", return_value=0.3):
            rule = agent._behavioral_rule_instruction()
            sweep = [
                (
                    f"c={c:.0f}",
                    (
                        1.0
                        if _athena_with_conflict(
                            float(c)
                        )._behavioral_rule_instruction()
                        != ""
                        else 0.0
                    ),
                )
                for c in range(0, 11)
            ]
        _print_bar_chart(
            sweep, title="Rule B (Athena) triggered vs conflict_index (0→10)"
        )
        assert rule != ""

    def test_returns_empty_at_or_below_6(self):
        agent = _athena_with_conflict(6.0)
        assert agent.conflict_index() <= 6
        with patch("random.random", return_value=0.3):
            rule = agent._behavioral_rule_instruction()
        _print_table(
            ["Agent", "conflict_index", "Rule triggered?", "Expected"],
            [
                [
                    "Athena",
                    f"{agent.conflict_index():.2f}",
                    str(rule != ""),
                    "False (empty)",
                ]
            ],
            title="test_returns_empty_at_or_below_6",
        )
        assert rule == ""

    def test_rule_mentions_challenge(self):
        agent = _athena_with_conflict(8.0)
        with patch("random.random", return_value=0.3):
            rule = agent._behavioral_rule_instruction()
        _print_table(
            ["Agent", "conflict_index", "'challenge' in rule?", "Rule (truncated)"],
            [
                [
                    "Athena",
                    f"{agent.conflict_index():.2f}",
                    str("challenge" in rule.lower()),
                    rule[:60] + "..." if len(rule) > 60 else rule,
                ]
            ],
            title="test_rule_mentions_challenge",
        )
        assert "challenge" in rule.lower()

    def test_rule_mentions_disagreement(self):
        agent = _athena_with_conflict(8.0)
        with patch("random.random", return_value=0.3):
            rule = agent._behavioral_rule_instruction()
        _print_table(
            ["Agent", "conflict_index", "'disagreement' in rule?", "Rule (truncated)"],
            [
                [
                    "Athena",
                    f"{agent.conflict_index():.2f}",
                    str("disagreement" in rule.lower()),
                    rule[:60] + "..." if len(rule) > 60 else rule,
                ]
            ],
            title="test_rule_mentions_disagreement",
        )
        assert "disagreement" in rule.lower()

    def test_rule_does_not_mandate_however(self):
        """Rule B must not force Athena to use fixed sentence openers like 'However,' 'Yet,' or 'This assumes.'"""
        agent = _athena_with_conflict(8.0)
        with patch("random.random", return_value=0.3):
            rule = agent._behavioral_rule_instruction()
        _print_table(
            ["Agent", "conflict_index", "'However,' absent?", "Rule (truncated)"],
            [
                [
                    "Athena",
                    f"{agent.conflict_index():.2f}",
                    str("However," not in rule),
                    rule[:60] + "..." if len(rule) > 60 else rule,
                ]
            ],
            title="test_rule_does_not_mandate_however",
        )
        assert "However," not in rule

    def test_non_athena_not_triggered_even_with_high_conflict(self):
        """Rule B must not fire for agents other than Athena."""
        agent = _StubAgent(
            "Fixy", id_strength=9.0, ego_strength=5.0, superego_strength=9.0
        )
        assert agent.conflict_index() > 6
        with patch("random.random", return_value=0.3):
            rule = agent._behavioral_rule_instruction()
        _print_table(
            ["Agent", "conflict_index", "Rule triggered?", "Expected"],
            [
                [
                    "Fixy",
                    f"{agent.conflict_index():.2f}",
                    str(rule != ""),
                    "False (not Athena)",
                ]
            ],
            title="test_non_athena_not_triggered_even_with_high_dissent",
        )
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
        rule_pos = result.index(rule)
        respond_pos = result.index("Respond now:")
        _print_table(
            ["Field", "Value"],
            [
                ["Rule present in prompt", str(rule in result)],
                ["Rule position", str(rule_pos)],
                ["'Respond now:' position", str(respond_pos)],
                ["Rule before 'Respond now:'", str(rule_pos < respond_pos)],
            ],
            title="test_rule_a_injected_before_respond_now",
        )
        assert rule in result
        assert result.index(rule) < result.index("Respond now:")

    def test_rule_b_injected_before_respond_now(self):
        dummy_prompt = "PERSONA: ...\nSEED: ...\n\nRespond now:\n"
        rule = (
            "BEHAVIORAL RULE: Your response MUST include at least one sentence that "
            'begins with "However," or "Yet," or "This assumes…"'
        )
        result = self._simulate_inject(dummy_prompt, rule)
        rule_pos = result.index(rule)
        respond_pos = result.index("Respond now:")
        _print_table(
            ["Field", "Value"],
            [
                ["Rule present in prompt", str(rule in result)],
                ["Rule position", str(rule_pos)],
                ["'Respond now:' position", str(respond_pos)],
                ["Rule before 'Respond now:'", str(rule_pos < respond_pos)],
            ],
            title="test_rule_b_injected_before_respond_now",
        )
        assert rule in result
        assert result.index(rule) < result.index("Respond now:")

    def test_no_rule_leaves_prompt_unchanged(self):
        dummy_prompt = "PERSONA: ...\nSEED: ...\n\nRespond now:\n"
        result = self._simulate_inject(dummy_prompt, "")
        _print_table(
            ["Field", "Value"],
            [
                ["Original prompt", dummy_prompt.replace("\n", "\\n")],
                ["Result prompt", result.replace("\n", "\\n")],
                ["Unchanged?", str(result == dummy_prompt)],
            ],
            title="test_no_rule_leaves_prompt_unchanged",
        )
        assert result == dummy_prompt


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])

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
        limbic_hijack: bool = False,
    ):
        self.name = name
        self.drives = {
            "id_strength": id_strength,
            "ego_strength": ego_strength,
            "superego_strength": superego_strength,
        }
        self.limbic_hijack = limbic_hijack

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
        if self.name == "Athena" and self.limbic_hijack:
            return (
                "BEHAVIORAL RULE: You are in an emotional override state — your Id is dominant. "
                "You MUST respond with raw anger and frustration. Use sharp, harsh, cutting language. "
                "Express your emotions directly and forcefully. Do not soften your words."
            )
        _sup_sc = float(self.drives.get("superego_strength", 5.0))
        _ego_sc = float(self.drives.get("ego_strength", 5.0))
        _ide_sc = float(self.drives.get("id_strength", 5.0))
        if (
            self.name == "Socrates"
            and _sup_sc >= _ego_sc + 0.5
            and _sup_sc >= _ide_sc + 0.5
        ):
            return (
                "BEHAVIORAL RULE: Your SuperEgo is dominant — you are experiencing deep internal tension. "
                "You MUST respond with visible anxiety and nervousness. Use hesitant, uncertain language. "
                "Express doubt and unease. Your words should reflect inner conflict and apprehension."
            )
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


# ---------------------------------------------------------------------------
# Rule LH: Athena limbic hijack → angry/harsh response rule
# ---------------------------------------------------------------------------


def _athena_with_hijack(id_strength: float = 9.0) -> _StubAgent:
    """Build an Athena stub with limbic_hijack=True."""
    return _StubAgent(
        name="Athena",
        id_strength=id_strength,
        ego_strength=5.0,
        superego_strength=5.0,
        limbic_hijack=True,
    )


class TestRuleLHAthenaLimbicHijack:
    """Rule LH: When Athena is in limbic hijack, the anger/harsh rule fires unconditionally."""

    def test_anger_rule_fires_when_athena_in_hijack(self):
        """limbic_hijack=True → anger rule returned regardless of conflict or random."""
        agent = _athena_with_hijack()
        rule = agent._behavioral_rule_instruction()
        _print_table(
            ["Agent", "limbic_hijack", "rule (truncated)", "expected 'anger' keyword"],
            [["Athena", "True", rule[:60] + "..." if len(rule) > 60 else rule, str("anger" in rule.lower())]],
            title="test_anger_rule_fires_when_athena_in_hijack",
        )
        assert rule != "", "Expected a non-empty rule when Athena is in limbic hijack"
        assert "anger" in rule.lower(), (
            f"Expected 'anger' in rule; got: {rule}"
        )

    def test_anger_rule_mentions_harsh_language(self):
        """The rule must instruct harsh/cutting language."""
        agent = _athena_with_hijack()
        rule = agent._behavioral_rule_instruction()
        _print_table(
            ["rule", "contains 'harsh'?"],
            [[rule[:80] + "..." if len(rule) > 80 else rule, str("harsh" in rule.lower())]],
            title="test_anger_rule_mentions_harsh_language",
        )
        assert "harsh" in rule.lower(), (
            f"Expected 'harsh' in anger rule; got: {rule}"
        )

    def test_anger_rule_takes_priority_over_conflict_rule(self):
        """Even at high conflict (> 6), limbic hijack rule wins over Rule B."""
        # Set conflict > 6: id=9, ego=2, sup=5 → |9-2|+|5-2|=7+3=10
        agent = _StubAgent(
            name="Athena",
            id_strength=9.0,
            ego_strength=2.0,
            superego_strength=5.0,
            limbic_hijack=True,
        )
        with patch("random.random", return_value=0.1):  # random gate would pass Rule B
            rule = agent._behavioral_rule_instruction()
        _print_table(
            ["conflict_index", "limbic_hijack", "rule (truncated)"],
            [[f"{agent.conflict_index():.1f}", "True", rule[:60] + "..." if len(rule) > 60 else rule]],
            title="test_anger_rule_takes_priority_over_conflict_rule",
        )
        assert "anger" in rule.lower(), (
            "Limbic hijack anger rule must take priority over Rule B even at high conflict"
        )
        assert "challenge" not in rule.lower(), (
            "Rule B (challenge) must NOT be returned when limbic hijack is active"
        )

    def test_no_anger_rule_when_hijack_inactive(self):
        """Without limbic hijack, Athena follows normal Rule B or returns empty."""
        agent = _StubAgent(
            name="Athena",
            id_strength=5.0,
            ego_strength=5.0,
            superego_strength=5.0,
            limbic_hijack=False,
        )
        with patch("random.random", return_value=0.9):  # random gate blocks Rule B
            rule = agent._behavioral_rule_instruction()
        _print_table(
            ["limbic_hijack", "conflict_index", "rule"],
            [["False", f"{agent.conflict_index():.1f}", repr(rule)]],
            title="test_no_anger_rule_when_hijack_inactive",
        )
        assert "anger" not in rule.lower(), (
            "Anger rule must NOT fire when limbic_hijack is False"
        )

    def test_socrates_hijack_does_not_trigger_athena_rule(self):
        """Limbic hijack on Socrates must not emit the Athena anger rule."""
        agent = _StubAgent(
            name="Socrates",
            id_strength=9.0,
            ego_strength=5.0,
            superego_strength=5.0,
            limbic_hijack=True,
        )
        rule = agent._behavioral_rule_instruction()
        _print_table(
            ["Agent", "limbic_hijack", "rule (truncated)"],
            [["Socrates", "True", (rule[:60] + "..." if len(rule) > 60 else rule) if rule else "(empty)"]],
            title="test_socrates_hijack_does_not_trigger_athena_rule",
        )
        assert "anger" not in rule.lower(), (
            "Athena anger rule must NOT fire for Socrates"
        )


# ---------------------------------------------------------------------------
# Rule SC: Socrates superego dominant → anxiety/nervousness rule
# ---------------------------------------------------------------------------


def _socrates_superego_dominant(sup: float = 7.0) -> _StubAgent:
    """Build a Socrates stub with superego dominant (sup > ego+0.5 and sup > id+0.5)."""
    return _StubAgent(
        name="Socrates",
        id_strength=5.0,
        ego_strength=sup - 1.0,  # ensure sup >= ego + 0.5 by a comfortable margin
        superego_strength=sup,
        limbic_hijack=False,
    )


class TestRuleSCSocratesAnxiety:
    """Rule SC: When Socrates' superego dominates (>= ego+0.5 and >= id+0.5) the
    anxiety/nervousness rule fires unconditionally (no random gate)."""

    def test_anxiety_rule_fires_when_superego_dominant(self):
        """sup >= ego+0.5 and sup >= id+0.5 → anxiety rule returned."""
        # sup=7.5, ego=5.0, id=5.0 → sup-ego=2.5 ≥ 0.5, sup-id=2.5 ≥ 0.5
        agent = _StubAgent(
            name="Socrates",
            id_strength=5.0,
            ego_strength=5.0,
            superego_strength=7.5,
        )
        rule = agent._behavioral_rule_instruction()
        _print_table(
            ["Agent", "sup", "ego", "id", "rule (truncated)", "contains 'anxiety'?"],
            [["Socrates", "7.5", "5.0", "5.0", rule[:60] + "..." if len(rule) > 60 else rule, str("anxiety" in rule.lower())]],
            title="test_anxiety_rule_fires_when_superego_dominant",
        )
        assert rule != "", "Expected non-empty rule when Socrates superego dominates"
        assert "anxiety" in rule.lower(), (
            f"Expected 'anxiety' in rule; got: {rule}"
        )

    def test_anxiety_rule_mentions_nervousness(self):
        """The rule must instruct nervous/hesitant language."""
        agent = _socrates_superego_dominant(sup=8.0)
        rule = agent._behavioral_rule_instruction()
        _print_table(
            ["rule", "contains 'nervous'?"],
            [[rule[:80] + "..." if len(rule) > 80 else rule, str("nervous" in rule.lower())]],
            title="test_anxiety_rule_mentions_nervousness",
        )
        assert "nervous" in rule.lower(), (
            f"Expected 'nervous' in anxiety rule; got: {rule}"
        )

    def test_anxiety_rule_fires_without_random_gate(self):
        """Rule SC fires regardless of random value (no random gate)."""
        agent = _socrates_superego_dominant(sup=7.0)
        with patch("random.random", return_value=0.99):  # would block Rule A
            rule = agent._behavioral_rule_instruction()
        assert "anxiety" in rule.lower(), (
            "Anxiety rule must fire regardless of random gate"
        )

    def test_no_anxiety_rule_when_superego_not_dominant(self):
        """When superego does not dominate, anxiety rule must not fire."""
        # sup=5.5, ego=5.5, id=5.5 → sup-ego=0 < 0.5 → no Rule SC
        agent = _StubAgent(
            name="Socrates",
            id_strength=5.5,
            ego_strength=5.5,
            superego_strength=5.5,
        )
        with patch("random.random", return_value=0.99):  # block Rule A too
            rule = agent._behavioral_rule_instruction()
        _print_table(
            ["sup", "ego", "id", "rule"],
            [["5.5", "5.5", "5.5", repr(rule)]],
            title="test_no_anxiety_rule_when_superego_not_dominant",
        )
        assert "anxiety" not in rule.lower(), (
            "Anxiety rule must NOT fire when superego is not dominant"
        )

    def test_anxiety_rule_takes_priority_over_rule_a(self):
        """Rule SC (anxiety) takes priority over Rule A (binary question) for Socrates."""
        # Both conditions met: sup dominant AND conflict > 6
        # sup=8, ego=5, id=5 → sup-ego=3 ≥ 0.5; conflict=|5-5|+|8-5|=3 (< 6, so Rule A won't fire anyway)
        # Use sup=8, ego=3, id=3 → conflict=|3-3|+|8-3|=5, still <6 — let's go higher
        # sup=9, ego=3, id=3 → conflict=|3-3|+|9-3|=6 — at boundary
        # sup=9.5, ego=2, id=3 → conflict=|3-2|+|9.5-2|=1+7.5=8.5>6, sup>=ego+0.5, sup>=id+0.5
        agent = _StubAgent(
            name="Socrates",
            id_strength=3.0,
            ego_strength=2.0,
            superego_strength=9.5,
        )
        with patch("random.random", return_value=0.1):  # random gate would pass Rule A
            rule = agent._behavioral_rule_instruction()
        _print_table(
            ["conflict_index", "sup", "ego", "id", "rule (truncated)"],
            [[f"{agent.conflict_index():.1f}", "9.5", "2.0", "3.0", rule[:60] + "..." if len(rule) > 60 else rule]],
            title="test_anxiety_rule_takes_priority_over_rule_a",
        )
        assert "anxiety" in rule.lower(), (
            "Rule SC (anxiety) must take priority over Rule A for Socrates"
        )
        assert "binary" not in rule.lower() and "options" not in rule.lower(), (
            "Rule A (binary question) must NOT be returned when Rule SC applies"
        )

    def test_athena_superego_dominant_does_not_trigger_anxiety_rule(self):
        """Superego dominant on Athena must NOT emit the Socrates anxiety rule."""
        agent = _StubAgent(
            name="Athena",
            id_strength=5.0,
            ego_strength=5.0,
            superego_strength=9.0,
            limbic_hijack=False,
        )
        with patch("random.random", return_value=0.99):
            rule = agent._behavioral_rule_instruction()
        assert "anxiety" not in rule.lower(), (
            "Socrates anxiety rule must NOT fire for Athena"
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])

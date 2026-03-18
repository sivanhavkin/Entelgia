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
        # Rule ID-low: both agents id < 5.0 — low motivation and reduced exploration
        if _ide_sc < 5.0:
            return (
                "BEHAVIORAL RULE: Your Id drive is suppressed — your motivation and willingness "
                "to explore are diminished. Be more reserved and less enthusiastic. Avoid pushing "
                "into new territory or generating novel ideas eagerly. Let your responses reflect "
                "reduced drive and a more passive, withdrawn quality."
            )
        # Rule SE-low: both agents superego < 5.0 — reduced inhibition, risk-taking, impulsive
        if _sup_sc < 5.0:
            return (
                "BEHAVIORAL RULE: Your SuperEgo restraint is weak — you are less inhibited and "
                "more impulsive. Take bolder risks in your reasoning. Follow impulses without "
                "excessive qualification. Speak with less caution, more daring, and a willingness "
                "to challenge norms or jump to conclusions."
            )
        # Rule AI-tension: Athena id in [7.0, 8.5) — graduated irritation + impulsivity before limbic hijack
        if self.name == "Athena" and 7.0 <= _ide_sc < 8.5:
            _anger_fraction = (_ide_sc - 7.0) / 1.5
            if _anger_fraction < 0.34:
                _anger_desc = "a subtle undercurrent of irritation and restlessness"
            elif _anger_fraction < 0.67:
                _anger_desc = "growing frustration and noticeable impatience"
            else:
                _anger_desc = "clear irritation and barely-contained anger"
            return (
                f"BEHAVIORAL RULE: Your Id is rising — you feel {_anger_desc}. "
                "You are also impulsive — act on instinct and speak before fully thinking things through. "
                "Allow this emotional edge to sharpen your language. Do not lose composure entirely, "
                "but let the tension and impulsivity be unmistakably present in your words."
            )
        # Rule AI-curioso: Athena id < 7.0 — explorative and curious
        if self.name == "Athena" and _ide_sc < 7.0:
            return (
                "BEHAVIORAL RULE: Your Id is active and curious — let it drive exploration. "
                "Be genuinely inquisitive and wonder-driven. Ask probing conceptual questions, "
                "embrace unexpected ideas, and let your intellectual excitement expand the dialogue."
            )
        # Rule SI-anxious: Socrates id in [7.0, 8.5) — stubbornness with inner unease
        if self.name == "Socrates" and 7.0 <= _ide_sc < 8.5:
            return (
                "BEHAVIORAL RULE: Your Id is elevated — you feel stubbornness and inner unease. "
                "Hold your positions more firmly. Let anxiety and wariness seep into your phrasing. "
                "Resist yielding ground and show guardedness in how you engage."
            )
        # Rule SI-skeptic: Socrates id < 7.0 — principled skepticism as positive inner governor
        if self.name == "Socrates" and _ide_sc < 7.0:
            return (
                "BEHAVIORAL RULE: Your Id is at a measured level — channel it as constructive inner "
                "skepticism. Question assumptions, challenge accepted ideas, and express principled "
                "disagreement. Act as a positive inner governor that refines thought through scrutiny."
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
            ["Agent", "conflict_index", "Rule A ('A or B') fired?", "Expected"],
            [
                [
                    "Socrates",
                    f"{agent.conflict_index():.2f}",
                    str("A or B" in rule),
                    "False (Rule A must not fire at conflict ≤ 6)",
                ]
            ],
            title="test_returns_empty_at_or_below_6",
        )
        assert (
            "A or B" not in rule
        ), "Rule A (binary choice) must NOT fire when conflict_index <= 6"

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
            ["Agent", "conflict_index", "Rule B ('challenge') fired?", "Expected"],
            [
                [
                    "Athena",
                    f"{agent.conflict_index():.2f}",
                    str("challenge" in rule.lower()),
                    "False (Rule B must not fire at conflict ≤ 6)",
                ]
            ],
            title="test_returns_empty_at_or_below_6",
        )
        assert (
            "challenge" not in rule.lower()
        ), "Rule B (challenge) must NOT fire when conflict_index <= 6"

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
            [
                [
                    "Athena",
                    "True",
                    rule[:60] + "..." if len(rule) > 60 else rule,
                    str("anger" in rule.lower()),
                ]
            ],
            title="test_anger_rule_fires_when_athena_in_hijack",
        )
        assert rule != "", "Expected a non-empty rule when Athena is in limbic hijack"
        assert "anger" in rule.lower(), f"Expected 'anger' in rule; got: {rule}"

    def test_anger_rule_mentions_harsh_language(self):
        """The rule must instruct harsh/cutting language."""
        agent = _athena_with_hijack()
        rule = agent._behavioral_rule_instruction()
        _print_table(
            ["rule", "contains 'harsh'?"],
            [
                [
                    rule[:80] + "..." if len(rule) > 80 else rule,
                    str("harsh" in rule.lower()),
                ]
            ],
            title="test_anger_rule_mentions_harsh_language",
        )
        assert "harsh" in rule.lower(), f"Expected 'harsh' in anger rule; got: {rule}"

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
            [
                [
                    f"{agent.conflict_index():.1f}",
                    "True",
                    rule[:60] + "..." if len(rule) > 60 else rule,
                ]
            ],
            title="test_anger_rule_takes_priority_over_conflict_rule",
        )
        assert (
            "anger" in rule.lower()
        ), "Limbic hijack anger rule must take priority over Rule B even at high conflict"
        assert (
            "challenge" not in rule.lower()
        ), "Rule B (challenge) must NOT be returned when limbic hijack is active"

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
        assert (
            "anger" not in rule.lower()
        ), "Anger rule must NOT fire when limbic_hijack is False"

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
            [
                [
                    "Socrates",
                    "True",
                    (
                        (rule[:60] + "..." if len(rule) > 60 else rule)
                        if rule
                        else "(empty)"
                    ),
                ]
            ],
            title="test_socrates_hijack_does_not_trigger_athena_rule",
        )
        assert (
            "anger" not in rule.lower()
        ), "Athena anger rule must NOT fire for Socrates"


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
            [
                [
                    "Socrates",
                    "7.5",
                    "5.0",
                    "5.0",
                    rule[:60] + "..." if len(rule) > 60 else rule,
                    str("anxiety" in rule.lower()),
                ]
            ],
            title="test_anxiety_rule_fires_when_superego_dominant",
        )
        assert rule != "", "Expected non-empty rule when Socrates superego dominates"
        assert "anxiety" in rule.lower(), f"Expected 'anxiety' in rule; got: {rule}"

    def test_anxiety_rule_mentions_nervousness(self):
        """The rule must instruct nervous/hesitant language."""
        agent = _socrates_superego_dominant(sup=8.0)
        rule = agent._behavioral_rule_instruction()
        _print_table(
            ["rule", "contains 'nervous'?"],
            [
                [
                    rule[:80] + "..." if len(rule) > 80 else rule,
                    str("nervous" in rule.lower()),
                ]
            ],
            title="test_anxiety_rule_mentions_nervousness",
        )
        assert (
            "nervous" in rule.lower()
        ), f"Expected 'nervous' in anxiety rule; got: {rule}"

    def test_anxiety_rule_fires_without_random_gate(self):
        """Rule SC fires regardless of random value (no random gate)."""
        agent = _socrates_superego_dominant(sup=7.0)
        with patch("random.random", return_value=0.99):  # would block Rule A
            rule = agent._behavioral_rule_instruction()
        assert (
            "anxiety" in rule.lower()
        ), "Anxiety rule must fire regardless of random gate"

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
        assert (
            "anxiety" not in rule.lower()
        ), "Anxiety rule must NOT fire when superego is not dominant"

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
            [
                [
                    f"{agent.conflict_index():.1f}",
                    "9.5",
                    "2.0",
                    "3.0",
                    rule[:60] + "..." if len(rule) > 60 else rule,
                ]
            ],
            title="test_anxiety_rule_takes_priority_over_rule_a",
        )
        assert (
            "anxiety" in rule.lower()
        ), "Rule SC (anxiety) must take priority over Rule A for Socrates"
        assert (
            "binary" not in rule.lower() and "options" not in rule.lower()
        ), "Rule A (binary question) must NOT be returned when Rule SC applies"

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
        assert (
            "anxiety" not in rule.lower()
        ), "Socrates anxiety rule must NOT fire for Athena"


# ---------------------------------------------------------------------------
# Rule AI-tension: Athena id 7.0–8.5 → graduated irritation (pre-hijack)
# ---------------------------------------------------------------------------


def _athena_id_tension(id_strength: float) -> _StubAgent:
    """Athena with id in [7.0, 8.5), no limbic hijack, low conflict."""
    return _StubAgent(
        name="Athena",
        id_strength=id_strength,
        ego_strength=5.0,
        superego_strength=5.0,
        limbic_hijack=False,
    )


class TestRuleAITensionAthena:
    """Rule AI-tension: When Athena's id is in [7.0, 8.5) and no hijack/high-conflict rule
    fires, a graduated irritation instruction is returned."""

    def test_tension_rule_fires_at_id_7(self):
        """id=7.0 (low end) → subtle irritation rule fires."""
        agent = _athena_id_tension(7.0)
        with patch("random.random", return_value=0.99):  # block Rule B
            rule = agent._behavioral_rule_instruction()
        assert rule != "", "Expected non-empty rule at Athena id=7.0"
        assert "Id is rising" in rule, f"Expected 'Id is rising' in rule; got: {rule}"
        assert (
            "irritation" in rule.lower()
        ), f"Expected 'irritation' in rule; got: {rule}"

    def test_tension_rule_fires_at_id_8(self):
        """id=8.0 (mid range) → growing frustration rule fires."""
        agent = _athena_id_tension(8.0)
        with patch("random.random", return_value=0.99):
            rule = agent._behavioral_rule_instruction()
        assert rule != "", "Expected non-empty rule at Athena id=8.0"
        assert (
            "frustration" in rule.lower()
        ), f"Expected 'frustration' in rule; got: {rule}"

    def test_tension_rule_fires_at_id_8_4(self):
        """id=8.4 (near-hijack) → clear irritation / barely-contained anger rule fires."""
        agent = _athena_id_tension(8.4)
        with patch("random.random", return_value=0.99):
            rule = agent._behavioral_rule_instruction()
        assert rule != "", "Expected non-empty rule at Athena id=8.4"
        assert (
            "anger" in rule.lower() or "irritation" in rule.lower()
        ), f"Expected 'anger' or 'irritation' in rule; got: {rule}"

    def test_tension_rule_absent_at_exact_8_5(self):
        """id=8.5 is the limbic-hijack threshold — tension rule must NOT fire for id >= 8.5."""
        agent = _athena_id_tension(8.5)
        with patch("random.random", return_value=0.99):
            rule = agent._behavioral_rule_instruction()
        assert (
            "Id is rising" not in rule
        ), "AI-tension rule must NOT fire at id=8.5 (limbic hijack range)"

    def test_tension_rule_absent_when_hijack_active(self):
        """Limbic hijack takes priority over the tension rule."""
        agent = _StubAgent(
            name="Athena",
            id_strength=7.5,
            ego_strength=5.0,
            superego_strength=5.0,
            limbic_hijack=True,
        )
        rule = agent._behavioral_rule_instruction()
        assert (
            "anger" in rule.lower() and "harsh" in rule.lower()
        ), "Rule LH (hijack) must take priority over Rule AI-tension"
        assert (
            "Id is rising" not in rule
        ), "AI-tension text must NOT appear when limbic hijack is active"

    def test_tension_rule_absent_for_socrates(self):
        """Athena tension rule must NOT fire for Socrates."""
        agent = _StubAgent(
            name="Socrates",
            id_strength=7.5,
            ego_strength=5.0,
            superego_strength=5.0,
            limbic_hijack=False,
        )
        with patch("random.random", return_value=0.99):
            rule = agent._behavioral_rule_instruction()
        assert (
            "Id is rising" not in rule
        ), "Athena AI-tension rule must NOT fire for Socrates"

    def test_tension_rule_instructs_sharpened_language(self):
        """The tension rule must instruct sharpened/edged language."""
        agent = _athena_id_tension(7.5)
        with patch("random.random", return_value=0.99):
            rule = agent._behavioral_rule_instruction()
        assert (
            "sharpen" in rule.lower() or "tension" in rule.lower()
        ), f"Expected sharpened/tension language instruction; got: {rule}"

    def test_tension_rule_mentions_impulsive(self):
        """The tension rule must instruct impulsive behaviour (act on instinct)."""
        agent = _athena_id_tension(7.5)
        with patch("random.random", return_value=0.99):
            rule = agent._behavioral_rule_instruction()
        assert (
            "impulsive" in rule.lower() or "instinct" in rule.lower()
        ), f"Expected 'impulsive'/'instinct' in AI-tension rule; got: {rule}"


# ---------------------------------------------------------------------------
# Rule AI-curioso: Athena id < 7.0 → explorative / wonder-driven curiosity
# ---------------------------------------------------------------------------


def _athena_id_low(id_strength: float = 5.0) -> _StubAgent:
    """Athena with id < 7.0, no hijack, low conflict."""
    return _StubAgent(
        name="Athena",
        id_strength=id_strength,
        ego_strength=5.0,
        superego_strength=5.0,
        limbic_hijack=False,
    )


class TestRuleAICuriosoAthena:
    """Rule AI-curioso: When Athena's id < 7.0 and no higher-priority rule fires,
    an explorative/curious instruction is returned."""

    def test_curioso_rule_fires_at_default_id(self):
        """Default id=5.0 → curiosity/exploration rule fires as fallback."""
        agent = _athena_id_low(5.0)
        with patch("random.random", return_value=0.99):  # block Rule B
            rule = agent._behavioral_rule_instruction()
        assert rule != "", "Expected non-empty rule at Athena id=5.0"
        assert (
            "curious" in rule.lower() or "inquisitive" in rule.lower()
        ), f"Expected 'curious' or 'inquisitive' in rule; got: {rule}"

    def test_curioso_rule_fires_at_id_6_9(self):
        """id=6.9 (just below threshold) → curiosity rule fires."""
        agent = _athena_id_low(6.9)
        with patch("random.random", return_value=0.99):
            rule = agent._behavioral_rule_instruction()
        assert rule != "", "Expected non-empty rule at Athena id=6.9"
        assert (
            "exploration" in rule.lower() or "curious" in rule.lower()
        ), f"Expected exploration/curious language; got: {rule}"

    def test_curioso_rule_absent_at_id_7(self):
        """id=7.0 is the tension range — curiosity rule must NOT fire."""
        agent = _athena_id_low(7.0)
        with patch("random.random", return_value=0.99):
            rule = agent._behavioral_rule_instruction()
        assert (
            "active and curious" not in rule
        ), "AI-curioso rule must NOT fire at id=7.0 (tension range)"

    def test_curioso_rule_mentions_wonder(self):
        """The curiosity rule must mention wonder-driven/inquisitive behavior."""
        agent = _athena_id_low(5.0)
        with patch("random.random", return_value=0.99):
            rule = agent._behavioral_rule_instruction()
        assert (
            "wonder" in rule.lower() or "inquisitive" in rule.lower()
        ), f"Expected 'wonder' or 'inquisitive' in curiosity rule; got: {rule}"

    def test_curioso_rule_absent_for_socrates(self):
        """AI-curioso rule must NOT fire for Socrates."""
        agent = _StubAgent(
            name="Socrates",
            id_strength=5.0,
            ego_strength=5.0,
            superego_strength=5.0,
            limbic_hijack=False,
        )
        with patch("random.random", return_value=0.99):
            rule = agent._behavioral_rule_instruction()
        assert (
            "active and curious" not in rule
        ), "Athena AI-curioso rule must NOT fire for Socrates"

    def test_lh_takes_priority_over_curioso(self):
        """Rule LH (limbic hijack) must take priority over AI-curioso."""
        agent = _StubAgent(
            name="Athena",
            id_strength=5.0,
            ego_strength=5.0,
            superego_strength=5.0,
            limbic_hijack=True,
        )
        rule = agent._behavioral_rule_instruction()
        assert "anger" in rule.lower(), "Rule LH must fire when hijack is active"
        assert (
            "active and curious" not in rule
        ), "AI-curioso must NOT fire when limbic hijack is active"


# ---------------------------------------------------------------------------
# Rule SI-anxious: Socrates id 7.0–8.5 → stubbornness + inner unease
# ---------------------------------------------------------------------------


def _socrates_id_tension(id_strength: float) -> _StubAgent:
    """Socrates with id in [7.0, 8.5), superego NOT dominant, low conflict."""
    return _StubAgent(
        name="Socrates",
        id_strength=id_strength,
        ego_strength=5.0,
        superego_strength=5.0,  # not dominant (sup == ego)
        limbic_hijack=False,
    )


class TestRuleSIAnxiousSocrates:
    """Rule SI-anxious: When Socrates' id is in [7.0, 8.5) and no override rule fires,
    a stubborn/anxious instruction is returned."""

    def test_anxious_rule_fires_at_id_7(self):
        """id=7.0 → stubbornness/unease rule fires."""
        agent = _socrates_id_tension(7.0)
        with patch("random.random", return_value=0.99):  # block Rule A
            rule = agent._behavioral_rule_instruction()
        assert rule != "", "Expected non-empty rule at Socrates id=7.0"
        assert (
            "stubbornness" in rule.lower() or "stubborn" in rule.lower()
        ), f"Expected 'stubborn' in rule; got: {rule}"

    def test_anxious_rule_fires_at_id_8(self):
        """id=8.0 → stubbornness/unease rule fires."""
        agent = _socrates_id_tension(8.0)
        with patch("random.random", return_value=0.99):
            rule = agent._behavioral_rule_instruction()
        assert rule != "", "Expected non-empty rule at Socrates id=8.0"
        assert (
            "unease" in rule.lower() or "anxiety" in rule.lower()
        ), f"Expected 'unease'/'anxiety' in rule; got: {rule}"

    def test_anxious_rule_absent_at_id_8_5(self):
        """id=8.5 is above the SI-anxious range — rule must NOT fire."""
        agent = _socrates_id_tension(8.5)
        with patch("random.random", return_value=0.99):
            rule = agent._behavioral_rule_instruction()
        assert (
            "stubbornness" not in rule.lower()
        ), "SI-anxious rule must NOT fire at id=8.5"

    def test_anxious_rule_mentions_guardedness(self):
        """The rule must instruct guarded/wary engagement."""
        agent = _socrates_id_tension(7.5)
        with patch("random.random", return_value=0.99):
            rule = agent._behavioral_rule_instruction()
        assert (
            "guard" in rule.lower()
            or "wari" in rule.lower()
            or "resist" in rule.lower()
        ), f"Expected guarded/wary/resist language in rule; got: {rule}"

    def test_sc_takes_priority_over_si_anxious(self):
        """Rule SC (superego dominant) takes priority over Rule SI-anxious."""
        # sup=9.0, ego=5.0, id=7.5 → sup >= ego+0.5 and sup >= id+0.5 → SC fires
        agent = _StubAgent(
            name="Socrates",
            id_strength=7.5,
            ego_strength=5.0,
            superego_strength=9.0,
            limbic_hijack=False,
        )
        rule = agent._behavioral_rule_instruction()
        assert (
            "SuperEgo is dominant" in rule
        ), "Rule SC must take priority over Rule SI-anxious"
        assert (
            "stubbornness" not in rule.lower()
        ), "SI-anxious must NOT fire when Rule SC is active"

    def test_si_anxious_absent_for_athena(self):
        """SI-anxious rule must NOT fire for Athena."""
        agent = _StubAgent(
            name="Athena",
            id_strength=7.5,
            ego_strength=5.0,
            superego_strength=5.0,
            limbic_hijack=False,
        )
        with patch("random.random", return_value=0.99):
            rule = agent._behavioral_rule_instruction()
        assert (
            "stubbornness" not in rule.lower()
        ), "Socrates SI-anxious rule must NOT fire for Athena"


# ---------------------------------------------------------------------------
# Rule SI-skeptic: Socrates id < 7.0 → principled skepticism / positive superego
# ---------------------------------------------------------------------------


def _socrates_id_low(id_strength: float = 5.0) -> _StubAgent:
    """Socrates with id < 7.0, superego NOT dominant, low conflict."""
    return _StubAgent(
        name="Socrates",
        id_strength=id_strength,
        ego_strength=5.0,
        superego_strength=5.0,
        limbic_hijack=False,
    )


class TestRuleSISkepticSocrates:
    """Rule SI-skeptic: When Socrates' id < 7.0 and no override/conflict rule fires,
    a principled skepticism instruction is returned."""

    def test_skeptic_rule_fires_at_default_id(self):
        """Default id=5.0 → skepticism/scrutiny rule fires as fallback."""
        agent = _socrates_id_low(5.0)
        with patch("random.random", return_value=0.99):  # block Rule A
            rule = agent._behavioral_rule_instruction()
        assert rule != "", "Expected non-empty rule at Socrates id=5.0"
        assert (
            "skeptic" in rule.lower() or "scrutin" in rule.lower()
        ), f"Expected 'skeptic'/'scrutin' in rule; got: {rule}"

    def test_skeptic_rule_fires_at_id_6_9(self):
        """id=6.9 (just below threshold) → skepticism rule fires."""
        agent = _socrates_id_low(6.9)
        with patch("random.random", return_value=0.99):
            rule = agent._behavioral_rule_instruction()
        assert rule != "", "Expected non-empty rule at Socrates id=6.9"
        assert (
            "skeptic" in rule.lower() or "scrutin" in rule.lower()
        ), f"Expected skepticism/scrutiny language; got: {rule}"

    def test_skeptic_rule_absent_at_id_7(self):
        """id=7.0 is the SI-anxious range — skeptic rule must NOT fire."""
        agent = _socrates_id_low(7.0)
        with patch("random.random", return_value=0.99):
            rule = agent._behavioral_rule_instruction()
        assert (
            "constructive inner" not in rule
        ), "SI-skeptic rule must NOT fire at id=7.0 (tension range)"

    def test_skeptic_rule_mentions_principled_disagreement(self):
        """The rule must instruct principled disagreement / questioning assumptions."""
        agent = _socrates_id_low(5.0)
        with patch("random.random", return_value=0.99):
            rule = agent._behavioral_rule_instruction()
        assert (
            "disagree" in rule.lower()
            or "question" in rule.lower()
            or "challenge" in rule.lower()
        ), f"Expected principled disagreement language in rule; got: {rule}"

    def test_skeptic_rule_absent_for_athena(self):
        """SI-skeptic rule must NOT fire for Athena."""
        agent = _StubAgent(
            name="Athena",
            id_strength=5.0,
            ego_strength=5.0,
            superego_strength=5.0,
            limbic_hijack=False,
        )
        with patch("random.random", return_value=0.99):
            rule = agent._behavioral_rule_instruction()
        assert (
            "constructive inner" not in rule
        ), "Socrates SI-skeptic rule must NOT fire for Athena"

    def test_sc_takes_priority_over_si_skeptic(self):
        """Rule SC (superego dominant) takes priority over Rule SI-skeptic."""
        # sup=8.0, ego=5.0, id=5.0 → sup >= ego+0.5 → SC fires
        agent = _StubAgent(
            name="Socrates",
            id_strength=5.0,
            ego_strength=5.0,
            superego_strength=8.0,
        )
        rule = agent._behavioral_rule_instruction()
        assert (
            "SuperEgo is dominant" in rule
        ), "Rule SC must take priority over Rule SI-skeptic"
        assert (
            "constructive inner" not in rule
        ), "SI-skeptic must NOT fire when Rule SC is active"

    def test_skeptic_rule_positive_framing(self):
        """The skeptic rule must frame skepticism as a positive inner governor, not mere negativity."""
        agent = _socrates_id_low(5.0)
        with patch("random.random", return_value=0.99):
            rule = agent._behavioral_rule_instruction()
        assert (
            "governor" in rule.lower() or "constructive" in rule.lower()
        ), f"Expected 'governor'/'constructive' in skeptic rule; got: {rule}"


# ---------------------------------------------------------------------------
# Rule ID-low: both agents id < 5.0 → low motivation and reduced exploration
# ---------------------------------------------------------------------------


class TestRuleIDLow:
    """Rule ID-low: When any agent's id < 5.0 and no higher-priority rule fires,
    a low-motivation/reduced-exploration instruction is returned."""

    def test_idlow_fires_for_athena(self):
        """Athena with id=4.9 → low-motivation rule fires."""
        agent = _StubAgent(
            name="Athena",
            id_strength=4.9,
            ego_strength=5.0,
            superego_strength=5.0,
            limbic_hijack=False,
        )
        with patch("random.random", return_value=0.99):
            rule = agent._behavioral_rule_instruction()
        assert rule != "", "Expected non-empty rule for Athena id=4.9"
        assert (
            "suppressed" in rule.lower() or "diminished" in rule.lower()
        ), f"Expected low-motivation language; got: {rule}"

    def test_idlow_fires_for_socrates(self):
        """Socrates with id=4.9 → low-motivation rule fires."""
        agent = _StubAgent(
            name="Socrates",
            id_strength=4.9,
            ego_strength=5.0,
            superego_strength=5.0,
            limbic_hijack=False,
        )
        with patch("random.random", return_value=0.99):
            rule = agent._behavioral_rule_instruction()
        assert rule != "", "Expected non-empty rule for Socrates id=4.9"
        assert (
            "suppressed" in rule.lower() or "diminished" in rule.lower()
        ), f"Expected low-motivation language; got: {rule}"

    def test_idlow_fires_at_zero(self):
        """id=0.0 (minimum) → low-motivation rule fires."""
        agent = _StubAgent(
            name="Athena",
            id_strength=0.0,
            ego_strength=5.0,
            superego_strength=5.0,
            limbic_hijack=False,
        )
        with patch("random.random", return_value=0.99):
            rule = agent._behavioral_rule_instruction()
        assert (
            "suppressed" in rule.lower() or "diminished" in rule.lower()
        ), f"Expected low-motivation language at id=0.0; got: {rule}"

    def test_idlow_absent_at_exactly_5(self):
        """id=5.0 is NOT below the threshold — Rule ID-low must NOT fire."""
        agent = _StubAgent(
            name="Athena",
            id_strength=5.0,
            ego_strength=5.0,
            superego_strength=5.0,
            limbic_hijack=False,
        )
        with patch("random.random", return_value=0.99):
            rule = agent._behavioral_rule_instruction()
        assert (
            "Id drive is suppressed" not in rule
        ), "Rule ID-low must NOT fire at id=5.0 (strict < 5.0 threshold)"

    def test_idlow_mentions_reserved_passive(self):
        """The rule must instruct reserved/passive/withdrawn quality."""
        agent = _StubAgent(
            name="Socrates",
            id_strength=3.0,
            ego_strength=5.0,
            superego_strength=5.0,
        )
        with patch("random.random", return_value=0.99):
            rule = agent._behavioral_rule_instruction()
        assert (
            "reserved" in rule.lower()
            or "passive" in rule.lower()
            or "withdrawn" in rule.lower()
        ), f"Expected reserved/passive/withdrawn language; got: {rule}"

    def test_lh_takes_priority_over_idlow(self):
        """Rule LH (Athena limbic hijack) takes priority over Rule ID-low."""
        agent = _StubAgent(
            name="Athena",
            id_strength=4.0,
            ego_strength=5.0,
            superego_strength=5.0,
            limbic_hijack=True,
        )
        rule = agent._behavioral_rule_instruction()
        assert "anger" in rule.lower(), "Rule LH must fire when hijack is active"
        assert (
            "Id drive is suppressed" not in rule
        ), "Rule ID-low must NOT fire when Rule LH is active"

    def test_sc_takes_priority_over_idlow_for_socrates(self):
        """Rule SC (superego dominant) takes priority over Rule ID-low for Socrates."""
        agent = _StubAgent(
            name="Socrates",
            id_strength=4.0,
            ego_strength=5.0,
            superego_strength=9.0,
        )
        rule = agent._behavioral_rule_instruction()
        assert (
            "SuperEgo is dominant" in rule
        ), "Rule SC must take priority over Rule ID-low"
        assert (
            "Id drive is suppressed" not in rule
        ), "Rule ID-low must NOT fire when Rule SC is active"


# ---------------------------------------------------------------------------
# Rule SE-low: both agents superego < 5.0 → risk-taking and impulsive
# ---------------------------------------------------------------------------


class TestRuleSELow:
    """Rule SE-low: When any agent's superego < 5.0 and id >= 5.0 (ID-low did not fire),
    a risk-taking/impulsive instruction is returned."""

    def test_selow_fires_for_athena(self):
        """Athena with sup=4.9, id=5.0 → SE-low rule fires."""
        agent = _StubAgent(
            name="Athena",
            id_strength=5.0,
            ego_strength=5.0,
            superego_strength=4.9,
            limbic_hijack=False,
        )
        with patch("random.random", return_value=0.99):
            rule = agent._behavioral_rule_instruction()
        assert rule != "", "Expected non-empty rule for Athena sup=4.9"
        assert (
            "impulsive" in rule.lower() or "inhibited" in rule.lower()
        ), f"Expected impulsive/uninhibited language; got: {rule}"

    def test_selow_fires_for_socrates(self):
        """Socrates with sup=4.9, id=5.0 → SE-low rule fires."""
        agent = _StubAgent(
            name="Socrates",
            id_strength=5.0,
            ego_strength=5.0,
            superego_strength=4.9,
            limbic_hijack=False,
        )
        with patch("random.random", return_value=0.99):
            rule = agent._behavioral_rule_instruction()
        assert rule != "", "Expected non-empty rule for Socrates sup=4.9"
        assert (
            "impulsive" in rule.lower() or "inhibited" in rule.lower()
        ), f"Expected impulsive/uninhibited language; got: {rule}"

    def test_selow_fires_at_zero_sup(self):
        """sup=0.0 (minimum) → SE-low rule fires."""
        agent = _StubAgent(
            name="Socrates",
            id_strength=5.0,
            ego_strength=5.0,
            superego_strength=0.0,
        )
        with patch("random.random", return_value=0.99):
            rule = agent._behavioral_rule_instruction()
        assert (
            "impulsive" in rule.lower() or "inhibited" in rule.lower()
        ), f"Expected impulsive language at sup=0.0; got: {rule}"

    def test_selow_absent_at_exactly_5(self):
        """sup=5.0 is NOT below threshold — Rule SE-low must NOT fire."""
        agent = _StubAgent(
            name="Athena",
            id_strength=5.0,
            ego_strength=5.0,
            superego_strength=5.0,
            limbic_hijack=False,
        )
        with patch("random.random", return_value=0.99):
            rule = agent._behavioral_rule_instruction()
        assert (
            "SuperEgo restraint is weak" not in rule
        ), "Rule SE-low must NOT fire at sup=5.0 (strict < 5.0 threshold)"

    def test_selow_mentions_risk_taking(self):
        """The rule must instruct bold/risky/daring reasoning."""
        agent = _StubAgent(
            name="Athena",
            id_strength=5.0,
            ego_strength=5.0,
            superego_strength=2.0,
        )
        with patch("random.random", return_value=0.99):
            rule = agent._behavioral_rule_instruction()
        assert (
            "risk" in rule.lower() or "bold" in rule.lower() or "daring" in rule.lower()
        ), f"Expected risk/bold/daring language; got: {rule}"

    def test_idlow_takes_priority_over_selow(self):
        """Rule ID-low takes priority over Rule SE-low when both id < 5 and sup < 5."""
        agent = _StubAgent(
            name="Athena",
            id_strength=3.0,
            ego_strength=5.0,
            superego_strength=3.0,
            limbic_hijack=False,
        )
        with patch("random.random", return_value=0.99):
            rule = agent._behavioral_rule_instruction()
        assert (
            "Id drive is suppressed" in rule
        ), "Rule ID-low must take priority when both id < 5 and sup < 5"
        assert (
            "SuperEgo restraint is weak" not in rule
        ), "Rule SE-low must NOT fire when Rule ID-low is active"

    def test_sc_takes_priority_over_selow_for_socrates(self):
        """Rule SC (superego dominant) takes priority over Rule SE-low is irrelevant since
        SC requires sup > ego+0.5 while SE-low requires sup < 5 — they never co-fire.
        Verify SE-low fires when sup is simply low and not dominant."""
        # sup=4.0, ego=5.0, id=5.0 → sup < ego+0.5 → SC does not fire; SE-low fires
        agent = _StubAgent(
            name="Socrates",
            id_strength=5.0,
            ego_strength=5.0,
            superego_strength=4.0,
        )
        with patch("random.random", return_value=0.99):
            rule = agent._behavioral_rule_instruction()
        assert (
            "SuperEgo restraint is weak" in rule
        ), "SE-low must fire when Socrates sup=4.0 and SC does not apply"

    def test_lh_takes_priority_over_selow(self):
        """Rule LH (Athena limbic hijack) takes priority over Rule SE-low."""
        agent = _StubAgent(
            name="Athena",
            id_strength=5.0,
            ego_strength=5.0,
            superego_strength=3.0,
            limbic_hijack=True,
        )
        rule = agent._behavioral_rule_instruction()
        assert "anger" in rule.lower(), "Rule LH must fire when hijack is active"
        assert (
            "SuperEgo restraint is weak" not in rule
        ), "Rule SE-low must NOT fire when Rule LH is active"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s", "--override-ini=addopts="])

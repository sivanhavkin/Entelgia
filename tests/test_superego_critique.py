# tests/test_superego_critique.py
"""
Tests for the SuperEgo critique decision logic.

Validates:
  1. Repro bug: ego dominant → critique must NOT fire.
  2. Positive: superego dominant by margin → critique fires.
  3. Margin boundary: gap below / above margin → fire / skip.
  4. Conflict-min: superego dominant but conflict too low → skip.
  5. Disabled flag: critique_enabled=False → always skip.
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
    CritiqueDecision,
    EmotionCore,
    LanguageCore,
    evaluate_superego_critique,
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
# Helpers
# ---------------------------------------------------------------------------


def _decision(
    id_strength: float,
    ego_strength: float,
    superego_strength: float,
    conflict: float,
    enabled: bool = True,
    dominance_margin: float = 0.5,
    conflict_min: float = 2.0,
) -> CritiqueDecision:
    return evaluate_superego_critique(
        id_strength=id_strength,
        ego_strength=ego_strength,
        superego_strength=superego_strength,
        conflict=conflict,
        enabled=enabled,
        dominance_margin=dominance_margin,
        conflict_min=conflict_min,
    )


# ---------------------------------------------------------------------------
# 1. Repro bug test
# ---------------------------------------------------------------------------


class TestEgoDominantScenario:
    """ego=9.3, superego=8.8, id=2.5, conflict=7.3 → Ego dominant → NO critique."""

    def test_critique_not_applied_when_ego_dominant(self):
        dec = _decision(
            id_strength=2.5,
            ego_strength=9.3,
            superego_strength=8.8,
            conflict=7.3,
        )
        _print_table(
            ["id", "ego", "superego", "conflict", "should_apply", "reason", "expected"],
            [["2.5", "9.3", "8.8", "7.3", str(dec.should_apply), dec.reason, "False"]],
            title="test_critique_not_applied_when_ego_dominant",
        )
        assert (
            dec.should_apply is False
        ), f"Expected critique NOT applied when Ego is dominant, got reason={dec.reason}"

    def test_reason_mentions_ego_dominant(self):
        dec = _decision(
            id_strength=2.5,
            ego_strength=9.3,
            superego_strength=8.8,
            conflict=7.3,
        )
        _print_table(
            ["id", "ego", "superego", "conflict", "reason", "contains_Ego?"],
            [["2.5", "9.3", "8.8", "7.3", dec.reason, str("Ego" in dec.reason)]],
            title="test_reason_mentions_ego_dominant",
        )
        assert (
            "Ego" in dec.reason
        ), f"Expected reason to identify Ego as dominant drive, got: {dec.reason}"


# ---------------------------------------------------------------------------
# 2. Positive test
# ---------------------------------------------------------------------------


class TestPositiveCritique:
    """superego=9.4, ego=8.6, id=2.0, conflict=6.0 → SuperEgo dominant → critique applied."""

    def test_critique_applied_when_superego_dominant(self):
        dec = _decision(
            id_strength=2.0,
            ego_strength=8.6,
            superego_strength=9.4,
            conflict=6.0,
        )
        _print_table(
            ["id", "ego", "superego", "conflict", "should_apply", "reason", "expected"],
            [["2.0", "8.6", "9.4", "6.0", str(dec.should_apply), dec.reason, "True"]],
            title="test_critique_applied_when_superego_dominant",
        )
        assert (
            dec.should_apply is True
        ), f"Expected critique applied when SuperEgo is dominant, got reason={dec.reason}"

    def test_reason_is_superego_dominant(self):
        dec = _decision(
            id_strength=2.0,
            ego_strength=8.6,
            superego_strength=9.4,
            conflict=6.0,
        )
        _print_table(
            ["id", "ego", "superego", "conflict", "reason", "expected"],
            [["2.0", "8.6", "9.4", "6.0", dec.reason, "superego_dominant"]],
            title="test_reason_is_superego_dominant",
        )
        assert dec.reason == "superego_dominant"


# ---------------------------------------------------------------------------
# 3. Margin boundary tests
# ---------------------------------------------------------------------------


class TestDominanceMargin:
    """superego=9.0, ego=8.7, id=1.0, conflict=6.0 → gap 0.3."""

    @pytest.mark.parametrize(
        "margin,expected_apply",
        [
            (0.5, False),  # gap 0.3 < margin 0.5 → skip
            (0.2, True),  # gap 0.3 >= margin 0.2 → apply
        ],
    )
    def test_margin_boundary(self, margin: float, expected_apply: bool):
        dec = _decision(
            id_strength=1.0,
            ego_strength=8.7,
            superego_strength=9.0,
            conflict=6.0,
            dominance_margin=margin,
        )
        _print_table(
            [
                "id",
                "ego",
                "superego",
                "conflict",
                "margin",
                "should_apply",
                "reason",
                "expected",
            ],
            [
                [
                    "1.0",
                    "8.7",
                    "9.0",
                    "6.0",
                    str(margin),
                    str(dec.should_apply),
                    dec.reason,
                    str(expected_apply),
                ]
            ],
            title="test_margin_boundary",
        )
        assert dec.should_apply is expected_apply, (
            f"margin={margin}: expected should_apply={expected_apply}, "
            f"got {dec.should_apply} (reason={dec.reason})"
        )

    def test_exact_margin_boundary_applies(self):
        """Gap equal to margin → should_apply (>= comparison)."""
        dec = _decision(
            id_strength=1.0,
            ego_strength=8.5,
            superego_strength=9.0,  # gap exactly 0.5
            conflict=6.0,
            dominance_margin=0.5,
        )
        _print_table(
            [
                "id",
                "ego",
                "superego",
                "conflict",
                "margin",
                "gap",
                "should_apply",
                "reason",
                "expected",
            ],
            [
                [
                    "1.0",
                    "8.5",
                    "9.0",
                    "6.0",
                    "0.5",
                    "0.5",
                    str(dec.should_apply),
                    dec.reason,
                    "True",
                ]
            ],
            title="test_exact_margin_boundary_applies",
        )
        assert (
            dec.should_apply is True
        ), f"Gap equal to margin should trigger critique, got reason={dec.reason}"


# ---------------------------------------------------------------------------
# 4. Conflict-min test
# ---------------------------------------------------------------------------


class TestConflictMin:
    """SuperEgo dominant but conflict < conflict_min → skip with conflict reason."""

    def test_low_conflict_skips_critique(self):
        dec = _decision(
            id_strength=1.0,
            ego_strength=5.0,
            superego_strength=9.0,
            conflict=1.0,  # below default 2.0
            conflict_min=2.0,
        )
        _print_table(
            [
                "id",
                "ego",
                "superego",
                "conflict",
                "conflict_min",
                "should_apply",
                "reason",
                "expected",
            ],
            [
                [
                    "1.0",
                    "5.0",
                    "9.0",
                    "1.0",
                    "2.0",
                    str(dec.should_apply),
                    dec.reason,
                    "False",
                ]
            ],
            title="test_low_conflict_skips_critique",
        )
        assert dec.should_apply is False

    def test_low_conflict_reason_contains_conflict(self):
        dec = _decision(
            id_strength=1.0,
            ego_strength=5.0,
            superego_strength=9.0,
            conflict=1.0,
            conflict_min=2.0,
        )
        _print_table(
            [
                "id",
                "ego",
                "superego",
                "conflict",
                "conflict_min",
                "reason",
                "contains_conflict?",
            ],
            [
                [
                    "1.0",
                    "5.0",
                    "9.0",
                    "1.0",
                    "2.0",
                    dec.reason,
                    str("conflict" in dec.reason.lower()),
                ]
            ],
            title="test_low_conflict_reason_contains_conflict",
        )
        assert (
            "conflict" in dec.reason.lower()
        ), f"Expected reason to mention conflict, got: {dec.reason}"

    def test_conflict_at_minimum_applies(self):
        """Conflict exactly at conflict_min → critique fires."""
        dec = _decision(
            id_strength=1.0,
            ego_strength=5.0,
            superego_strength=9.0,
            conflict=2.0,
            conflict_min=2.0,
        )
        _print_table(
            [
                "id",
                "ego",
                "superego",
                "conflict",
                "conflict_min",
                "should_apply",
                "reason",
                "expected",
            ],
            [
                [
                    "1.0",
                    "5.0",
                    "9.0",
                    "2.0",
                    "2.0",
                    str(dec.should_apply),
                    dec.reason,
                    "True",
                ]
            ],
            title="test_conflict_at_minimum_applies",
        )
        assert (
            dec.should_apply is True
        ), f"Conflict at minimum should trigger critique, got reason={dec.reason}"


# ---------------------------------------------------------------------------
# 5. Disabled flag
# ---------------------------------------------------------------------------


class TestCritiqueDisabled:
    """enabled=False must always return should_apply=False."""

    def test_disabled_skips_even_when_superego_dominant(self):
        dec = _decision(
            id_strength=1.0,
            ego_strength=5.0,
            superego_strength=9.0,
            conflict=8.0,
            enabled=False,
        )
        _print_table(
            [
                "id",
                "ego",
                "superego",
                "conflict",
                "enabled",
                "should_apply",
                "reason",
                "expected",
            ],
            [
                [
                    "1.0",
                    "5.0",
                    "9.0",
                    "8.0",
                    "False",
                    str(dec.should_apply),
                    dec.reason,
                    "False",
                ]
            ],
            title="test_disabled_skips_even_when_superego_dominant",
        )
        assert dec.should_apply is False

    def test_disabled_reason(self):
        dec = _decision(
            id_strength=1.0,
            ego_strength=5.0,
            superego_strength=9.0,
            conflict=8.0,
            enabled=False,
        )
        _print_table(
            ["id", "ego", "superego", "conflict", "enabled", "reason", "expected"],
            [["1.0", "5.0", "9.0", "8.0", "False", dec.reason, "disabled"]],
            title="test_disabled_reason",
        )
        assert dec.reason == "disabled"


# ---------------------------------------------------------------------------
# 6. CritiqueDecision importability
# ---------------------------------------------------------------------------


class TestCritiqueDecisionDataclass:
    def test_fields(self):
        cd = CritiqueDecision(should_apply=True, reason="superego_dominant")
        _print_table(
            ["field", "value", "expected"],
            [
                ["should_apply", str(cd.should_apply), "True"],
                ["reason", cd.reason, "superego_dominant"],
                ["critic", cd.critic, "superego"],
            ],
            title="test_fields",
        )
        assert cd.should_apply is True
        assert cd.reason == "superego_dominant"
        assert cd.critic == "superego"

    def test_evaluate_returns_critique_decision(self):
        result = evaluate_superego_critique(
            id_strength=2.0,
            ego_strength=5.0,
            superego_strength=9.0,
            conflict=5.0,
        )
        _print_table(
            ["result_type", "should_apply", "reason", "expected_type"],
            [
                [
                    type(result).__name__,
                    str(result.should_apply),
                    result.reason,
                    "CritiqueDecision",
                ]
            ],
            title="test_evaluate_returns_critique_decision",
        )
        assert isinstance(result, CritiqueDecision)


# ---------------------------------------------------------------------------
# 7. Agent.speak() stale-state regression
# ---------------------------------------------------------------------------


def _make_agent(ego_dominant: bool = True) -> "tuple[Agent, Config]":
    """Return a minimal Agent whose LLM and memory calls are fully mocked."""
    cfg = Config()

    # Stub LLM: generate() returns a canned response
    llm_mock = MagicMock()
    llm_mock.generate.return_value = "I think deeply about this matter."

    # Drives that make Ego dominant (no critique should fire)
    if ego_dominant:
        drives = {
            "id_strength": 2.7,
            "ego_strength": 9.3,
            "superego_strength": 8.7,
            "self_awareness": 0.55,
        }
    else:
        # Drives that make SuperEgo dominant (critique should fire)
        drives = {
            "id_strength": 2.0,
            "ego_strength": 8.0,
            "superego_strength": 9.5,
            "self_awareness": 0.55,
        }

    memory_mock = MagicMock()
    memory_mock.get_agent_state.return_value = drives
    memory_mock.ltm_recent.return_value = []
    memory_mock.stm_load.return_value = []

    emotion_mock = MagicMock(spec=EmotionCore)
    emotion_mock.infer.return_value = ("neutral", 0.3)

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


class TestAgentSpeakCritiqueStateReset:
    """Regression: stale _last_superego_rewrite must not leak across turns."""

    def test_stale_rewrite_flag_cleared_when_ego_dominant(self):
        """
        Simulate a previous turn where critique was applied (True), then drive
        conditions become Ego-dominant.  After speak(), flag must be False.
        """
        agent, cfg = _make_agent(ego_dominant=True)

        # Simulate stale state from a previous turn
        agent._last_superego_rewrite = True
        agent._last_critique_reason = "superego_dominant"

        with patch.object(_meta, "CFG", cfg):
            agent.speak("What is justice?", [])

        _print_table(
            ["stale_rewrite_before", "_last_superego_rewrite", "expected"],
            [["True", str(agent._last_superego_rewrite), "False"]],
            title="test_stale_rewrite_flag_cleared_when_ego_dominant",
        )
        assert agent._last_superego_rewrite is False, (
            "Expected _last_superego_rewrite=False when Ego is dominant; "
            "stale True value from previous turn must not persist."
        )
        assert (
            agent._last_critique_reason != "superego_dominant"
        ), "_last_critique_reason must reflect the current turn, not the previous one."

    def test_critique_reason_reflects_current_turn(self):
        """After speak() with Ego-dominant drives, reason must not be superego_dominant."""
        agent, cfg = _make_agent(ego_dominant=True)

        # Simulate stale state from a previous turn
        agent._last_superego_rewrite = True
        agent._last_critique_reason = "superego_dominant"

        with patch.object(_meta, "CFG", cfg):
            agent.speak("What is justice?", [])

        _print_table(
            ["stale_reason_before", "_last_critique_reason", "is_stale?"],
            [
                [
                    "superego_dominant",
                    agent._last_critique_reason,
                    str(agent._last_critique_reason == "superego_dominant"),
                ]
            ],
            title="test_critique_reason_reflects_current_turn",
        )
        assert (
            agent._last_critique_reason != "superego_dominant"
        ), "_last_critique_reason must reflect the current turn, not the previous one."

    def test_critique_applied_when_superego_dominant(self):
        """When SuperEgo dominates, critique should be applied after speak()."""
        agent, cfg = _make_agent(ego_dominant=False)

        # Start from a clean slate (no previous stale state)
        agent._last_superego_rewrite = False
        agent._last_critique_reason = ""

        with patch.object(_meta, "CFG", cfg):
            agent.speak("What is justice?", [])

        _print_table(
            [
                "_last_superego_rewrite",
                "expected",
                "_last_critique_reason",
                "expected_reason",
            ],
            [
                [
                    str(agent._last_superego_rewrite),
                    "True",
                    agent._last_critique_reason,
                    "superego_dominant",
                ]
            ],
            title="test_critique_applied_when_superego_dominant",
        )
        assert (
            agent._last_superego_rewrite is True
        ), "Expected _last_superego_rewrite=True when SuperEgo is dominant."
        assert agent._last_critique_reason == "superego_dominant"

    def test_fields_reset_at_start_regardless_of_prior_state(self):
        """
        Even if the first speak() sets rewrite=True, the next speak() with
        ego-dominant drives must reset it to False.
        """
        agent, cfg = _make_agent(ego_dominant=True)

        # First: manually place agent in the 'rewrite was True' state
        agent._last_superego_rewrite = True
        agent._last_critique_reason = "superego_dominant"

        # Second call: ego is dominant → rewrite must be False
        with patch.object(_meta, "CFG", cfg):
            agent.speak("Explain virtue.", [])

        _print_table(
            [
                "stale_rewrite_before",
                "_last_superego_rewrite",
                "_last_critique_reason",
                "is_stale_reason?",
            ],
            [
                [
                    "True",
                    str(agent._last_superego_rewrite),
                    agent._last_critique_reason,
                    str(agent._last_critique_reason == "superego_dominant"),
                ]
            ],
            title="test_fields_reset_at_start_regardless_of_prior_state",
        )
        assert agent._last_superego_rewrite is False
        assert agent._last_critique_reason != "superego_dominant"


# ---------------------------------------------------------------------------
# 8. Consecutive SuperEgo streak limit
# ---------------------------------------------------------------------------


class TestSuperEgoConsecutiveStreakLimit:
    """
    After 2 consecutive SuperEgo rewrites the counter reaches its limit.
    Turn 3+ must show the ORIGINAL text (no rewrite call) and set
    _superego_streak_suppressed=True.  When a non-critique turn occurs
    the counter resets so the next critique turn rewrites again.
    """

    def _make_superego_agent(self):
        """Agent with SuperEgo-dominant drives so critique fires every turn."""
        return _make_agent(ego_dominant=False)

    def test_first_two_turns_apply_rewrite(self):
        """Turns 1 and 2: rewrite applied, _last_superego_rewrite=True."""
        agent, cfg = self._make_superego_agent()
        with patch.object(_meta, "CFG", cfg):
            for turn in range(1, 3):
                agent.speak("What is justice?", [])
                assert (
                    agent._last_superego_rewrite is True
                ), f"Turn {turn}: expected rewrite applied"
                assert (
                    agent._superego_streak_suppressed is False
                ), f"Turn {turn}: suppressed flag must be False when rewrite applies"

    def test_third_turn_suppresses_rewrite(self):
        """Turn 3: critique would fire but streak >= 2, so original shown."""
        agent, cfg = self._make_superego_agent()
        with patch.object(_meta, "CFG", cfg):
            agent.speak("What is justice?", [])  # turn 1
            agent.speak("What is justice?", [])  # turn 2
            # Capture LLM call count before turn 3
            calls_before = agent.llm.generate.call_count
            agent.speak("What is justice?", [])  # turn 3 — suppressed

        _print_table(
            [
                "_last_superego_rewrite",
                "_superego_streak_suppressed",
                "extra_llm_calls",
                "expected_rewrite",
                "expected_suppressed",
            ],
            [
                [
                    str(agent._last_superego_rewrite),
                    str(agent._superego_streak_suppressed),
                    str(agent.llm.generate.call_count - calls_before),
                    "False",
                    "True",
                ]
            ],
            title="test_third_turn_suppresses_rewrite",
        )
        assert (
            agent._last_superego_rewrite is False
        ), "Turn 3: _last_superego_rewrite must be False when streak limit reached"
        assert (
            agent._superego_streak_suppressed is True
        ), "Turn 3: _superego_streak_suppressed must be True"
        # Only one LLM call (main response), no extra rewrite call
        assert (
            agent.llm.generate.call_count - calls_before == 1
        ), "Turn 3: LLM must not be called a second time for the rewrite"

    def test_counter_resets_after_non_critique_turn(self):
        """
        After two critique turns (streak=2), a non-critique (ego-dominant) turn
        resets the counter.  The following critique turn applies the rewrite again.
        """
        # Two agents: one shares the LLM mock so we can count calls
        agent_sup, cfg_sup = self._make_superego_agent()
        agent_ego, cfg_ego = _make_agent(ego_dominant=True)
        # Share llm mock so we can inspect counts on the superego agent
        with patch.object(_meta, "CFG", cfg_sup):
            agent_sup.speak("What is justice?", [])  # turn 1 — rewrite
            agent_sup.speak("What is justice?", [])  # turn 2 — rewrite
            assert agent_sup._consecutive_superego_rewrites == 2

            # Manually simulate a non-critique turn by patching evaluate_superego_critique
            with patch.object(
                _meta,
                "evaluate_superego_critique",
                return_value=_meta.CritiqueDecision(
                    should_apply=False, reason="ego_dominant"
                ),
            ):
                agent_sup.speak("What is virtue?", [])  # non-critique turn

            assert (
                agent_sup._consecutive_superego_rewrites == 0
            ), "Counter must reset to 0 after a non-critique turn"

            # Next critique turn should apply the rewrite again
            agent_sup.speak("What is justice?", [])  # turn after reset
            assert (
                agent_sup._last_superego_rewrite is True
            ), "After counter reset, first critique turn must apply rewrite again"
            assert agent_sup._superego_streak_suppressed is False


# ---------------------------------------------------------------------------
# 9. Extreme superego tightened thresholds
# ---------------------------------------------------------------------------


class TestSuperegoCritiqueAtExtreme:
    """
    At extreme superego (>= 8.5 for Socrates) the critique call uses:
      - dominance_margin = 0.2  (vs normal 0.5)
      - conflict_min    = 1.0  (vs normal 2.0)
    This allows the internal governor to fire even when superego only narrowly
    dominates or conflict is below the normal minimum.
    """

    def test_tight_margin_fires_when_superego_barely_dominant(self):
        """sup=8.5, ego=8.3: gap=0.2 meets extreme margin=0.2 → fires."""
        # With normal margin=0.5: 8.5 < 8.3+0.5=8.8 → no fire
        # With extreme margin=0.2: 8.5 >= 8.3+0.2=8.5 → fires
        dec = _decision(
            id_strength=5.5,
            ego_strength=8.3,
            superego_strength=8.5,
            conflict=3.0,
            dominance_margin=0.2,
            conflict_min=1.0,
        )
        _print_table(
            ["id", "ego", "sup", "conflict", "margin", "should_apply", "reason"],
            [["5.5", "8.3", "8.5", "3.0", "0.2", str(dec.should_apply), dec.reason]],
            title="test_tight_margin_fires_when_superego_barely_dominant",
        )
        assert dec.should_apply is True, (
            f"Tight margin (0.2) should allow critique at sup=8.5, ego=8.3; "
            f"got reason={dec.reason}"
        )

    def test_normal_margin_suppresses_barely_dominant_superego(self):
        """Same drives but normal margin=0.5: 8.5 < 8.3+0.5=8.8 → no fire."""
        dec = _decision(
            id_strength=5.5,
            ego_strength=8.3,
            superego_strength=8.5,
            conflict=3.0,
            dominance_margin=0.5,
            conflict_min=2.0,
        )
        _print_table(
            ["id", "ego", "sup", "conflict", "margin", "should_apply", "reason"],
            [["5.5", "8.3", "8.5", "3.0", "0.5", str(dec.should_apply), dec.reason]],
            title="test_normal_margin_suppresses_barely_dominant_superego",
        )
        assert dec.should_apply is False, (
            f"Normal margin (0.5) should suppress barely-dominant superego; "
            f"got reason={dec.reason}"
        )

    def test_low_conflict_fires_with_extreme_conflict_min(self):
        """conflict=1.5 fires when conflict_min=1.0 (extreme) but sup is clearly dominant."""
        dec = _decision(
            id_strength=5.0,
            ego_strength=8.5,
            superego_strength=9.2,
            conflict=1.5,
            dominance_margin=0.2,
            conflict_min=1.0,
        )
        _print_table(
            ["id", "ego", "sup", "conflict", "conflict_min", "should_apply", "reason"],
            [["5.0", "8.5", "9.2", "1.5", "1.0", str(dec.should_apply), dec.reason]],
            title="test_low_conflict_fires_with_extreme_conflict_min",
        )
        assert dec.should_apply is True, (
            f"Extreme conflict_min (1.0) should allow critique at conflict=1.5; "
            f"got reason={dec.reason}"
        )

    def test_normal_conflict_min_suppresses_low_conflict(self):
        """Same drives but normal conflict_min=2.0: conflict=1.5 < 2.0 → no fire."""
        dec = _decision(
            id_strength=5.0,
            ego_strength=8.5,
            superego_strength=9.2,
            conflict=1.5,
            dominance_margin=0.2,
            conflict_min=2.0,
        )
        _print_table(
            ["id", "ego", "sup", "conflict", "conflict_min", "should_apply", "reason"],
            [["5.0", "8.5", "9.2", "1.5", "2.0", str(dec.should_apply), dec.reason]],
            title="test_normal_conflict_min_suppresses_low_conflict",
        )
        assert dec.should_apply is False, (
            f"Normal conflict_min (2.0) should suppress critique at conflict=1.5; "
            f"got reason={dec.reason}"
        )


# ---------------------------------------------------------------------------
# 10. Socrates anxiety emotion during superego critique
# ---------------------------------------------------------------------------


class TestSocratesAnxietyDuringCritique:
    """When Socrates' superego critique fires, _last_emotion must be 'fear'
    and the critique prompt must include the anxious-tone instruction."""

    def test_socrates_last_emotion_is_fear_when_critique_fires(self):
        """After speak() with superego-dominant drives, _last_emotion='fear'."""
        agent, cfg = _make_agent(ego_dominant=False)  # superego dominant

        with patch.object(_meta, "CFG", cfg):
            agent.speak("What is justice?", [])

        assert (
            agent._last_superego_rewrite is True
        ), "Superego critique must have fired for this test to be valid"
        assert agent._last_emotion == "fear", (
            f"Expected _last_emotion='fear' when Socrates critique fires; "
            f"got '{agent._last_emotion}'"
        )
        assert agent._last_emotion_intensity >= 0.8, (
            f"Expected intensity >= 0.8 during Socrates critique; "
            f"got {agent._last_emotion_intensity}"
        )

    def test_socrates_emotion_not_fear_when_critique_does_not_fire(self):
        """When critique does not fire, the emotion is taken from inference (not forced)."""
        agent, cfg = _make_agent(ego_dominant=True)  # ego dominant, no critique

        with patch.object(_meta, "CFG", cfg):
            agent.speak("What is justice?", [])

        assert (
            agent._last_superego_rewrite is False
        ), "Critique must NOT have fired for this test to be valid"
        # Emotion comes from inference mock ("neutral"), not forced to "fear"
        assert agent._last_emotion == "neutral", (
            f"Expected _last_emotion='neutral' when critique does not fire; "
            f"got '{agent._last_emotion}'"
        )

    def test_critique_prompt_for_socrates_mentions_anxious_tone(self):
        """The critique LLM call for Socrates must include the anxious-tone instruction."""
        agent, cfg = _make_agent(ego_dominant=False)

        with patch.object(_meta, "CFG", cfg):
            agent.speak("What is justice?", [])

        # Inspect all generate() calls to find the critique prompt
        all_calls = agent.llm.generate.call_args_list
        critique_prompts = [
            (
                call.args[1]
                if call.args and len(call.args) > 1
                else call.kwargs.get("prompt", "")
            )
            for call in all_calls
        ]
        anxiety_in_critique = any(
            "anxious" in p.lower() or "nervous" in p.lower() for p in critique_prompts
        )
        assert (
            anxiety_in_critique
        ), "At least one LLM call to Socrates' critique prompt must mention 'anxious' or 'nervous'"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])

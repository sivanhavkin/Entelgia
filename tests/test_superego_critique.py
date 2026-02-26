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

from Entelgia_production_meta import CritiqueDecision, evaluate_superego_critique


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
        assert dec.should_apply is False, (
            f"Expected critique NOT applied when Ego is dominant, got reason={dec.reason}"
        )

    def test_reason_mentions_ego_dominant(self):
        dec = _decision(
            id_strength=2.5,
            ego_strength=9.3,
            superego_strength=8.8,
            conflict=7.3,
        )
        assert "Ego" in dec.reason, (
            f"Expected reason to identify Ego as dominant drive, got: {dec.reason}"
        )


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
        assert dec.should_apply is True, (
            f"Expected critique applied when SuperEgo is dominant, got reason={dec.reason}"
        )

    def test_reason_is_superego_dominant(self):
        dec = _decision(
            id_strength=2.0,
            ego_strength=8.6,
            superego_strength=9.4,
            conflict=6.0,
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
            (0.2, True),   # gap 0.3 >= margin 0.2 → apply
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
        assert dec.should_apply is True, (
            f"Gap equal to margin should trigger critique, got reason={dec.reason}"
        )


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
        assert dec.should_apply is False

    def test_low_conflict_reason_contains_conflict(self):
        dec = _decision(
            id_strength=1.0,
            ego_strength=5.0,
            superego_strength=9.0,
            conflict=1.0,
            conflict_min=2.0,
        )
        assert "conflict" in dec.reason.lower(), (
            f"Expected reason to mention conflict, got: {dec.reason}"
        )

    def test_conflict_at_minimum_applies(self):
        """Conflict exactly at conflict_min → critique fires."""
        dec = _decision(
            id_strength=1.0,
            ego_strength=5.0,
            superego_strength=9.0,
            conflict=2.0,
            conflict_min=2.0,
        )
        assert dec.should_apply is True, (
            f"Conflict at minimum should trigger critique, got reason={dec.reason}"
        )


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
        assert dec.should_apply is False

    def test_disabled_reason(self):
        dec = _decision(
            id_strength=1.0,
            ego_strength=5.0,
            superego_strength=9.0,
            conflict=8.0,
            enabled=False,
        )
        assert dec.reason == "disabled"


# ---------------------------------------------------------------------------
# 6. CritiqueDecision importability
# ---------------------------------------------------------------------------


class TestCritiqueDecisionDataclass:
    def test_fields(self):
        cd = CritiqueDecision(should_apply=True, reason="superego_dominant")
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
        assert isinstance(result, CritiqueDecision)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])

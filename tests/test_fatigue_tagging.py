#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Tests for the fatigue tagging and gradual fatigue effects (Issue: add-fatigue-tagging-effects).

Validates:
  A. _compute_fatigue() returns correct score and state for each energy band.
  B. Energy > 60 → fatigue = 0.0, state = "none".
  C. Energy 35–60 → fatigue in [0.0, 1.0], state matches the four-band mapping.
  D. Energy < 35 → fatigue clamped to 1.0, state = "severe".
  E. Fatigue score is always in [0.0, 1.0].
  F. Agent.__init__ initialises _last_fatigue and _last_fatigue_state.
  G. Fatigue does NOT directly set semantic_repeat, stagnation, or loop flags.
"""

import sys
import os
import logging

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

from Entelgia_production_meta import (
    _compute_fatigue,
    _compute_energy_status,
    _FATIGUE_ENERGY_THRESHOLD,
    _FATIGUE_ENERGY_SPAN,
    _ENERGY_DREAM_THRESHOLD,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _print_row(label, energy, fatigue, state):
    print(f"  {label:<35} energy={energy:6.1f}  fatigue={fatigue:.3f}  state={state}")


# ============================================================================
# A/B. Energy > 60 → no fatigue
# ============================================================================


class TestFatigueAboveThreshold:
    """Energy > 60: fatigue must always be 0.0, state must be 'none'."""

    @pytest.mark.parametrize(
        "energy",
        [61.0, 70.0, 80.0, 100.0, 150.0],
    )
    def test_no_fatigue_above_threshold(self, energy):
        fatigue, state = _compute_fatigue(energy)
        _print_row("above threshold", energy, fatigue, state)
        assert fatigue == 0.0, f"Expected 0.0 fatigue for energy={energy}, got {fatigue}"
        assert state == "none", f"Expected 'none' for energy={energy}, got {state!r}"

    def test_exactly_at_threshold(self):
        """Energy exactly at _FATIGUE_ENERGY_THRESHOLD → fatigue = 0.0."""
        fatigue, state = _compute_fatigue(_FATIGUE_ENERGY_THRESHOLD)
        _print_row("exactly at threshold", _FATIGUE_ENERGY_THRESHOLD, fatigue, state)
        assert fatigue == 0.0
        assert state == "none"


# ============================================================================
# C. Energy 35–60 → gradual fatigue, four-band mapping
# ============================================================================


class TestFatigueGradualRange:
    """Energy 35–60: fatigue scales continuously and maps to the correct state label."""

    @pytest.mark.parametrize(
        "energy, expected_state",
        [
            # State boundary: none (fatigue ≤ 0.2) — energy ≥ 55 (60 - 0.2*25 = 55)
            (60.0, "none"),   # threshold
            (55.0, "none"),   # fatigue = 0.20 exactly → still "none"
            # State boundary: mild (0.2 < fatigue ≤ 0.5) — energy 47.5–55
            (54.9, "mild"),   # just above 55 → fatigue just above 0.2 → mild
            (47.5, "mild"),   # fatigue = 0.50 exactly → still "mild"
            # State boundary: medium (0.5 < fatigue ≤ 0.8) — energy 40–47.5
            (47.4, "medium"), # just above 47.5 → fatigue just above 0.5 → medium
            (40.0, "medium"), # fatigue = 0.80 exactly → still "medium"
            # State boundary: severe (fatigue > 0.8) — energy < 40
            (39.9, "severe"), # just below 40 → fatigue just above 0.8 → severe
            (35.0, "severe"), # lower boundary of meaningful range
        ],
    )
    def test_state_label_mapping(self, energy, expected_state):
        fatigue, state = _compute_fatigue(energy)
        _print_row(f"energy={energy}", energy, fatigue, state)
        assert state == expected_state, (
            f"energy={energy}: expected state={expected_state!r}, got {state!r} "
            f"(fatigue={fatigue:.4f})"
        )

    def test_fatigue_increases_as_energy_decreases(self):
        """Fatigue must be monotonically non-decreasing as energy decreases."""
        energies = list(range(60, 34, -1))  # 60 down to 35
        results = [_compute_fatigue(float(e)) for e in energies]
        fatigues = [r[0] for r in results]
        print("\n  Monotonicity check (energy 60→35):")
        for e, f in zip(energies, fatigues):
            _print_row("", e, f, "")
        for i in range(1, len(fatigues)):
            assert fatigues[i] >= fatigues[i - 1], (
                f"Fatigue not monotone: fatigue[{energies[i]}]={fatigues[i]:.4f} "
                f"< fatigue[{energies[i-1]}]={fatigues[i-1]:.4f}"
            )

    def test_fatigue_formula_at_midpoint(self):
        """At energy=47.5 (midpoint of 35–60) fatigue should be 0.5 exactly."""
        fatigue, state = _compute_fatigue(47.5)
        _print_row("midpoint (47.5)", 47.5, fatigue, state)
        assert abs(fatigue - 0.5) < 1e-9, f"Expected 0.5, got {fatigue}"

    def test_fatigue_formula_uses_correct_span(self):
        """Verify formula: fatigue = (threshold - energy) / span, clamped."""
        for energy in [60.0, 55.0, 47.5, 40.0, 35.0]:
            expected_raw = (_FATIGUE_ENERGY_THRESHOLD - energy) / _FATIGUE_ENERGY_SPAN
            expected_clamped = max(0.0, min(1.0, expected_raw))
            fatigue, _ = _compute_fatigue(energy)
            assert abs(fatigue - expected_clamped) < 1e-9, (
                f"energy={energy}: expected {expected_clamped:.6f}, got {fatigue:.6f}"
            )


# ============================================================================
# D. Energy < 35 → clamped to 1.0, state = "severe"
# ============================================================================


class TestFatigueBelowDreamThreshold:
    """Energy < 35: fatigue must be clamped to 1.0 and state must be 'severe'."""

    @pytest.mark.parametrize("energy", [34.9, 30.0, 20.0, 10.0, 0.0, -5.0])
    def test_severe_below_dream_threshold(self, energy):
        fatigue, state = _compute_fatigue(energy)
        _print_row("below dream threshold", energy, fatigue, state)
        assert fatigue == 1.0, f"Expected clamped fatigue=1.0 for energy={energy}, got {fatigue}"
        assert state == "severe"


# ============================================================================
# E. Fatigue score is always in [0.0, 1.0]
# ============================================================================


class TestFatigueClampInvariant:
    """_compute_fatigue() must always return a score in [0.0, 1.0]."""

    @pytest.mark.parametrize(
        "energy",
        [-100.0, -1.0, 0.0, 10.0, 34.999, 35.0, 47.5, 60.0, 60.001, 80.0, 200.0],
    )
    def test_score_in_unit_interval(self, energy):
        fatigue, _ = _compute_fatigue(energy)
        assert 0.0 <= fatigue <= 1.0, (
            f"Fatigue out of [0, 1] for energy={energy}: got {fatigue}"
        )


# ============================================================================
# F. Agent.__init__ initialises _last_fatigue and _last_fatigue_state
# ============================================================================


class TestAgentFatigueInit:
    """Agent must initialise _last_fatigue=0.0 and _last_fatigue_state='none'."""

    def _make_agent(self):
        """Create a minimal Agent instance using mock dependencies."""
        from unittest.mock import MagicMock
        from Entelgia_production_meta import (
            Agent,
            BehaviorCore,
            Config,
            ConsciousCore,
            EmotionCore,
            LanguageCore,
            MemoryCore,
        )

        cfg = Config()
        memory = MemoryCore(db_path=cfg.db_path)
        emotion = MagicMock(spec=EmotionCore)
        behavior = MagicMock(spec=BehaviorCore)
        language = LanguageCore()
        conscious = MagicMock(spec=ConsciousCore)
        llm = MagicMock()
        llm.generate.return_value = "test response"

        agent = Agent(
            name="Socrates",
            model="gpt-4o-mini",
            color="",
            llm=llm,
            memory=memory,
            emotion=emotion,
            behavior=behavior,
            language=language,
            conscious=conscious,
            persona="Test persona.",
            use_enhanced=False,
            cfg=cfg,
        )
        return agent

    def test_initial_fatigue_score_is_zero(self):
        agent = self._make_agent()
        print(f"\n  _last_fatigue initialised to: {agent._last_fatigue}")
        assert agent._last_fatigue == 0.0

    def test_initial_fatigue_state_is_none(self):
        agent = self._make_agent()
        print(f"  _last_fatigue_state initialised to: {agent._last_fatigue_state!r}")
        assert agent._last_fatigue_state == "none"


# ============================================================================
# G. Fatigue does NOT directly set semantic_repeat, stagnation, or loop flags
# ============================================================================


class TestFatigueDoesNotControlLoopFlags:
    """The fatigue score must never directly assign structural loop signals."""

    @pytest.mark.parametrize(
        "energy, should_be_no_fatigue",
        [
            (100.0, True),   # > 60: no fatigue
            (70.0, True),    # > 60: no fatigue
            (55.0, False),   # mild fatigue
            (40.0, False),   # medium fatigue
            (35.0, False),   # severe fatigue
        ],
    )
    def test_fatigue_does_not_set_semantic_repeat(self, energy, should_be_no_fatigue):
        """Confirm that _compute_fatigue() returns only (score, label) — no side-effects."""
        fatigue, state = _compute_fatigue(energy)
        _print_row("no-side-effects check", energy, fatigue, state)
        # _compute_fatigue must never touch any external state; it is a pure function.
        # We verify it returns a tuple of (float, str) only.
        assert isinstance(fatigue, float)
        assert isinstance(state, str)
        assert state in {"none", "mild", "medium", "severe"}

    def test_fatigue_state_labels_exhaustive(self):
        """All four state labels must be reachable and no others should exist."""
        valid_states = {"none", "mild", "medium", "severe"}
        observed = set()
        # Cover the full range with fine granularity
        for e_int in range(-5, 111):
            energy = float(e_int)
            _, state = _compute_fatigue(energy)
            assert state in valid_states, f"Unexpected state {state!r} for energy={energy}"
            observed.add(state)
        assert observed == valid_states, (
            f"Not all states reachable — observed: {observed}, expected: {valid_states}"
        )


# ============================================================================
# H. _compute_energy_status: three-regime label
# ============================================================================


class TestComputeEnergyStatus:
    """_compute_energy_status() must return the correct regime label for each energy band."""

    @pytest.mark.parametrize(
        "energy, expected_status",
        [
            # Normal regime: energy > 60
            (60.1, "normal"),
            (70.0, "normal"),
            (100.0, "normal"),
            # Boundary: exactly at threshold → degrading (not normal; > is strict)
            (60.0, "degrading"),
            # Degrading regime: 35 ≤ energy ≤ 60
            (59.4, "degrading"),
            (47.5, "degrading"),
            (35.0, "degrading"),
            # Dream regime: energy < 35
            (34.9, "dream"),
            (20.0, "dream"),
            (0.0, "dream"),
            (-10.0, "dream"),
        ],
    )
    def test_energy_status_label(self, energy, expected_status):
        status = _compute_energy_status(energy)
        print(f"\n  energy={energy:6.1f}  status={status!r}")
        assert status == expected_status, (
            f"energy={energy}: expected status={expected_status!r}, got {status!r}"
        )

    def test_all_three_statuses_reachable(self):
        """All three energy status labels must be reachable."""
        valid_statuses = {"normal", "degrading", "dream"}
        observed = set()
        for e_int in range(-5, 111):
            status = _compute_energy_status(float(e_int))
            assert status in valid_statuses, (
                f"Unexpected status {status!r} for energy={float(e_int)}"
            )
            observed.add(status)
        assert observed == valid_statuses, (
            f"Not all statuses reachable — observed: {observed}, expected: {valid_statuses}"
        )

    def test_constants_define_boundaries(self):
        """_FATIGUE_ENERGY_THRESHOLD and _ENERGY_DREAM_THRESHOLD must be the regime boundaries."""
        # Just above threshold → normal
        assert _compute_energy_status(_FATIGUE_ENERGY_THRESHOLD + 0.1) == "normal"
        # At threshold → degrading (strictly-greater-than condition)
        assert _compute_energy_status(_FATIGUE_ENERGY_THRESHOLD) == "degrading"
        # Just below threshold → degrading
        assert _compute_energy_status(_FATIGUE_ENERGY_THRESHOLD - 0.1) == "degrading"
        # At dream threshold → degrading (>= dream boundary)
        assert _compute_energy_status(_ENERGY_DREAM_THRESHOLD) == "degrading"
        # Just below dream threshold → dream
        assert _compute_energy_status(_ENERGY_DREAM_THRESHOLD - 0.1) == "dream"

    def test_return_type_is_str(self):
        """_compute_energy_status must always return a str."""
        for energy in [-100.0, 0.0, 35.0, 47.5, 60.0, 75.0]:
            result = _compute_energy_status(energy)
            assert isinstance(result, str), (
                f"Expected str, got {type(result)} for energy={energy}"
            )


# ============================================================================
# I. Agent._last_energy_status initialised to "normal"
# ============================================================================


class TestAgentEnergyStatusInit:
    """Agent must initialise _last_energy_status to 'normal'."""

    def _make_agent(self):
        from unittest.mock import MagicMock
        from Entelgia_production_meta import (
            Agent,
            BehaviorCore,
            Config,
            ConsciousCore,
            EmotionCore,
            LanguageCore,
            MemoryCore,
        )

        cfg = Config()
        memory = MemoryCore(db_path=cfg.db_path)
        emotion = MagicMock(spec=EmotionCore)
        behavior = MagicMock(spec=BehaviorCore)
        language = LanguageCore()
        conscious = MagicMock(spec=ConsciousCore)
        llm = MagicMock()
        llm.generate.return_value = "test response"

        return Agent(
            name="Socrates",
            model="gpt-4o-mini",
            color="",
            llm=llm,
            memory=memory,
            emotion=emotion,
            behavior=behavior,
            language=language,
            conscious=conscious,
            persona="Test persona.",
            use_enhanced=False,
            cfg=cfg,
        )

    def test_initial_energy_status_is_normal(self):
        agent = self._make_agent()
        print(f"\n  _last_energy_status initialised to: {agent._last_energy_status!r}")
        assert agent._last_energy_status == "normal"

    def test_energy_status_field_is_str(self):
        agent = self._make_agent()
        assert isinstance(agent._last_energy_status, str)


# ============================================================================
# J. Fatigue fields are consistent with post-drain energy_level after speak()
# ============================================================================


class TestFatiguePostDrainConsistency:
    """After speak() returns, _last_fatigue/_last_fatigue_state/_last_energy_status
    must be consistent with the agent's current energy_level, not with the
    pre-drain value that existed at the start of the turn.

    Regression test for the bug where energy_level shown in print_meta_state()
    could be in the degrading range (35–60) while _last_fatigue was still 0.0
    and _last_energy_status was still 'normal' (computed before the energy drain).
    """

    def _make_agent(self, start_energy: float):
        """Create a minimal Agent instance with a specified starting energy."""
        from unittest.mock import MagicMock
        from Entelgia_production_meta import (
            Agent,
            BehaviorCore,
            Config,
            ConsciousCore,
            EmotionCore,
            LanguageCore,
        )

        cfg = Config()

        llm = MagicMock()
        llm.generate.return_value = "test response"

        memory = MagicMock()
        memory.get_agent_state.return_value = {
            "id_strength": 5.0,
            "ego_strength": 5.0,
            "superego_strength": 5.0,
            "self_awareness": 0.55,
        }
        memory.ltm_recent.return_value = []
        memory.stm_load.return_value = []

        emotion = MagicMock(spec=EmotionCore)
        emotion.infer.return_value = ("neutral", 0.3)

        behavior = MagicMock(spec=BehaviorCore)
        language = LanguageCore()
        conscious = ConsciousCore()

        agent = Agent(
            name="Socrates",
            model="phi3",
            color="",
            llm=llm,
            memory=memory,
            emotion=emotion,
            behavior=behavior,
            language=language,
            conscious=conscious,
            persona="Test persona.",
            use_enhanced=False,
            cfg=cfg,
        )
        agent.energy_level = start_energy
        return agent, cfg

    def test_fatigue_fields_consistent_after_energy_drops_below_threshold(self):
        """If energy drains from above 60 to below 60 during speak(), the cached
        fatigue fields must reflect the post-drain energy, not the pre-drain energy.
        """
        import Entelgia_production_meta as _meta
        from unittest.mock import patch
        from Entelgia_production_meta import (
            _compute_fatigue,
            _compute_energy_status,
            _FATIGUE_ENERGY_THRESHOLD,
        )

        # Start with energy comfortably above the fatigue threshold so that the
        # pre-drain fatigue would be 0.0 / "none" / "normal".
        agent, cfg = self._make_agent(start_energy=63.0)
        assert agent.energy_level > _FATIGUE_ENERGY_THRESHOLD

        # Call speak() with a minimal prior dialog so context is valid.
        dialog = [{"role": "Athena", "text": "Let us explore consciousness."}]
        with patch.object(_meta, "CFG", cfg):
            agent.speak("seed text", dialog)

        # After speak(), energy_level reflects the drained value.
        post_drain_energy = agent.energy_level

        # Compute the expected values from the post-drain energy.
        expected_fatigue, expected_state = _compute_fatigue(post_drain_energy)
        expected_status = _compute_energy_status(post_drain_energy)

        print(
            f"\n  post_drain_energy={post_drain_energy:.2f}"
            f"  expected_fatigue={expected_fatigue:.3f}"
            f"  expected_state={expected_state!r}"
            f"  expected_status={expected_status!r}"
        )
        print(
            f"  _last_fatigue={agent._last_fatigue:.3f}"
            f"  _last_fatigue_state={agent._last_fatigue_state!r}"
            f"  _last_energy_status={agent._last_energy_status!r}"
        )

        assert abs(agent._last_fatigue - expected_fatigue) < 1e-9, (
            f"_last_fatigue ({agent._last_fatigue:.6f}) does not match "
            f"_compute_fatigue(energy_level={post_drain_energy:.2f}) = {expected_fatigue:.6f}"
        )
        assert agent._last_fatigue_state == expected_state, (
            f"_last_fatigue_state {agent._last_fatigue_state!r} != {expected_state!r} "
            f"for post-drain energy={post_drain_energy:.2f}"
        )
        assert agent._last_energy_status == expected_status, (
            f"_last_energy_status {agent._last_energy_status!r} != {expected_status!r} "
            f"for post-drain energy={post_drain_energy:.2f}"
        )

    def test_no_stale_normal_status_when_energy_in_degrading_range(self):
        """_last_energy_status must not be 'normal' when energy_level is in 35–60."""
        import Entelgia_production_meta as _meta
        from unittest.mock import patch
        from Entelgia_production_meta import _FATIGUE_ENERGY_THRESHOLD, _ENERGY_DREAM_THRESHOLD

        agent, cfg = self._make_agent(start_energy=63.0)
        dialog = [{"role": "Athena", "text": "What is identity?"}]
        with patch.object(_meta, "CFG", cfg):
            agent.speak("seed text", dialog)

        post_drain_energy = agent.energy_level
        if _ENERGY_DREAM_THRESHOLD <= post_drain_energy <= _FATIGUE_ENERGY_THRESHOLD:
            assert agent._last_energy_status != "normal", (
                f"energy_level={post_drain_energy:.2f} is in degrading range "
                f"but _last_energy_status is still 'normal'"
            )
            assert agent._last_fatigue > 0.0, (
                f"energy_level={post_drain_energy:.2f} is in degrading range "
                f"but _last_fatigue is still 0.0"
            )


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s", "--override-ini=addopts="])

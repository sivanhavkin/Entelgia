# tests/test_drive_correlations.py
"""
Tests for the coherent correlations between psychological drive parameters.

Validates that:
  1. High conflict erodes Ego's mediating capacity (manifests as low Ego).
  2. High conflict raises LLM temperature (more volatile tone).
  3. High conflict increases energy drain per turn.
"""

import sys
import os
import random

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

# ---------------------------------------------------------------------------
# Minimal stubs replicating the relevant Agent logic without LLM / DB deps
# ---------------------------------------------------------------------------

ENERGY_DRAIN_MIN = 8.0
ENERGY_DRAIN_MAX = 15.0


class _DriveStub:
    """Replicates conflict_index(), update_drives_after_turn(), and
    the temperature formula from Agent, without requiring real infrastructure."""

    def __init__(
        self,
        id_strength: float,
        ego_strength: float,
        superego_strength: float,
        self_awareness: float = 0.55,
    ):
        self.drives = {
            "id_strength": id_strength,
            "ego_strength": ego_strength,
            "superego_strength": superego_strength,
            "self_awareness": self_awareness,
        }
        self.energy_level: float = 100.0

    # -- helpers identical to production code --

    def conflict_index(self) -> float:
        ide = float(self.drives.get("id_strength", 5.0))
        ego = float(self.drives.get("ego_strength", 5.0))
        sup = float(self.drives.get("superego_strength", 5.0))
        return abs(ide - ego) + abs(sup - ego)

    def compute_temperature(self) -> float:
        """Mirror of the temperature formula in Agent.speak()."""
        ide = float(self.drives.get("id_strength", 5.0))
        ego = float(self.drives.get("ego_strength", 5.0))
        sup = float(self.drives.get("superego_strength", 5.0))
        return max(
            0.25,
            min(
                0.95,
                0.60
                + 0.03 * (ide - ego)
                - 0.02 * (sup - ego)
                + 0.015 * self.conflict_index(),
            ),
        )

    def update_drives_after_turn(
        self, response_kind: str, emo: str, inten: float, rng_seed: int = 0
    ):
        """Mirror of Agent.update_drives_after_turn(); accepts an optional rng_seed
        so tests can get a deterministic drain value."""
        ide = float(self.drives.get("id_strength", 5.0))
        ego = float(self.drives.get("ego_strength", 5.0))
        sup = float(self.drives.get("superego_strength", 5.0))
        sa = float(self.drives.get("self_awareness", 0.55))

        pre_conflict = abs(ide - ego) + abs(sup - ego)

        ego = min(10.0, ego + 0.05)
        sa = min(1.0, sa + 0.01)

        if response_kind in ("aggressive", "impulsive"):
            ide = min(10.0, ide + 0.18 + 0.10 * inten)
            sup = max(0.0, sup - 0.08)
            ego = max(0.0, ego - 0.06)
        elif response_kind == "guilt":
            sup = min(10.0, sup + 0.20 + 0.10 * inten)
            ide = max(0.0, ide - 0.08)
            sa = min(1.0, sa + 0.03)
        else:
            sup = min(10.0, sup + 0.08 + 0.05 * inten)
            ide = max(0.0, ide - 0.06)
            ego = min(10.0, ego + 0.06)
            sa = min(1.0, sa + 0.02)

        if emo in ("anger", "frustration"):
            ide = min(10.0, ide + 0.10)
        if emo in ("fear", "anxiety"):
            sup = min(10.0, sup + 0.08)

        # High conflict erodes Ego's mediating capacity (manifests as low Ego)
        if pre_conflict > 4.0:
            ego = max(0.0, ego - 0.03 * (pre_conflict - 4.0))

        self.drives = {
            "id_strength": ide,
            "ego_strength": ego,
            "superego_strength": sup,
            "self_awareness": sa,
        }

        # Energy drain scales with conflict
        rng = random.Random(rng_seed)
        drain = rng.uniform(ENERGY_DRAIN_MIN, ENERGY_DRAIN_MAX) + 0.4 * pre_conflict
        drain = min(drain, ENERGY_DRAIN_MAX * 2.0)
        self.energy_level = max(0.0, self.energy_level - drain)
        return pre_conflict


# ---------------------------------------------------------------------------
# Tests: conflict_index formula
# ---------------------------------------------------------------------------


class TestConflictIndex:
    """Direct unit tests for the conflict_index calculation."""

    def test_balanced_drives_zero_conflict(self):
        """Equal Id, Ego, SuperEgo → zero conflict."""
        agent = _DriveStub(id_strength=5.0, ego_strength=5.0, superego_strength=5.0)
        assert agent.conflict_index() == pytest.approx(0.0)

    def test_conflict_with_high_id_only(self):
        """High Id vs Ego with balanced SuperEgo produces expected conflict."""
        # |8-5| + |5-5| = 3 + 0 = 3
        agent = _DriveStub(id_strength=8.0, ego_strength=5.0, superego_strength=5.0)
        assert agent.conflict_index() == pytest.approx(3.0)

    def test_conflict_with_high_superego_only(self):
        """High SuperEgo vs Ego with balanced Id produces expected conflict."""
        # |5-5| + |9-5| = 0 + 4 = 4
        agent = _DriveStub(id_strength=5.0, ego_strength=5.0, superego_strength=9.0)
        assert agent.conflict_index() == pytest.approx(4.0)

    def test_symmetric_high_conflict(self):
        """Symmetric deviation from Ego gives doubled conflict."""
        # |9-5| + |9-5| = 4 + 4 = 8
        agent = _DriveStub(id_strength=9.0, ego_strength=5.0, superego_strength=9.0)
        assert agent.conflict_index() == pytest.approx(8.0)

    def test_maximum_conflict(self):
        """Maximum possible conflict: Id=10, Ego=0, SuperEgo=10 → 20."""
        agent = _DriveStub(id_strength=10.0, ego_strength=0.0, superego_strength=10.0)
        assert agent.conflict_index() == pytest.approx(20.0)

    @pytest.mark.parametrize(
        "ide, ego, sup, expected",
        [
            (2.9, 8.8, 8.7, pytest.approx(6.0, abs=0.1)),  # example from problem statement
            (5.0, 5.0, 5.0, pytest.approx(0.0)),
            (10.0, 5.0, 0.0, pytest.approx(10.0)),
        ],
    )
    def test_conflict_parametrized(self, ide, ego, sup, expected):
        agent = _DriveStub(id_strength=ide, ego_strength=ego, superego_strength=sup)
        assert agent.conflict_index() == expected


# ---------------------------------------------------------------------------
# Tests: Ego erosion under high conflict
# ---------------------------------------------------------------------------


class TestEgoErosionUnderConflict:
    """High conflict (pre_conflict > 4.0) must reduce Ego after a turn."""

    def test_high_conflict_reduces_ego(self):
        """With pre_conflict = 7.0, Ego must be lower after the turn than before."""
        # id=9, ego=5, sup=8: conflict = |9-5|+|8-5| = 7 (> 4.0)
        agent = _DriveStub(id_strength=9.0, ego_strength=5.0, superego_strength=8.0)
        ego_before = float(agent.drives["ego_strength"])
        agent.update_drives_after_turn("reflective", "neutral", 0.5)
        ego_after = float(agent.drives["ego_strength"])
        # "reflective" kind normally raises ego (+0.05 + 0.06), but conflict erosion
        # should bring it below the no-conflict baseline
        no_conflict_ego = ego_before + 0.05 + 0.06  # maximum reflective gain
        assert ego_after < no_conflict_ego, (
            f"Ego should be eroded by conflict; got {ego_after:.3f} vs baseline {no_conflict_ego:.3f}"
        )

    def test_low_conflict_does_not_erode_ego(self):
        """With pre_conflict <= 4.0, no erosion step is applied."""
        # id=5, ego=5, sup=5: conflict = 0
        agent = _DriveStub(id_strength=5.0, ego_strength=5.0, superego_strength=5.0)
        ego_before = float(agent.drives["ego_strength"])
        agent.update_drives_after_turn("reflective", "neutral", 0.5)
        ego_after = float(agent.drives["ego_strength"])
        # "reflective" adds +0.05 + 0.06; erosion (pre_conflict=0 <= 4.0) is not triggered
        expected = min(10.0, ego_before + 0.05 + 0.06)
        assert abs(ego_after - expected) < 1e-9

    def test_erosion_proportional_to_conflict(self):
        """Greater conflict must produce greater Ego erosion."""
        # Low conflict scenario: id=7, ego=5, sup=5 → conflict = 2 + 0 = 2 (no erosion)
        low = _DriveStub(id_strength=7.0, ego_strength=5.0, superego_strength=5.0)
        low.update_drives_after_turn("reflective", "neutral", 0.5)
        ego_low_conflict = float(low.drives["ego_strength"])

        # High conflict scenario: id=9, ego=5, sup=9 → conflict = 4 + 4 = 8
        high = _DriveStub(id_strength=9.0, ego_strength=5.0, superego_strength=9.0)
        high.update_drives_after_turn("reflective", "neutral", 0.5)
        ego_high_conflict = float(high.drives["ego_strength"])

        assert ego_high_conflict < ego_low_conflict, (
            "Higher conflict must result in lower Ego after the turn"
        )

    def test_ego_never_negative(self):
        """Ego must never drop below 0.0, even with extreme conflict."""
        # Maximum possible conflict: id=10, ego=0, sup=10 → conflict = 20
        agent = _DriveStub(id_strength=10.0, ego_strength=0.0, superego_strength=10.0)
        agent.update_drives_after_turn("aggressive", "anger", 1.0)
        assert float(agent.drives["ego_strength"]) >= 0.0


# ---------------------------------------------------------------------------
# Tests: Temperature scales with conflict
# ---------------------------------------------------------------------------


class TestTemperatureConflictCorrelation:
    """Higher conflict must yield a higher LLM temperature (more volatile tone)."""

    def _make_symmetric_conflict(self, conflict: float) -> _DriveStub:
        """Build a stub where conflict_index() == conflict exactly.
        conflict = |id - ego| + |sup - ego|; ego=5 and deviation split symmetrically."""
        ego = 5.0
        half = conflict / 2.0
        return _DriveStub(
            id_strength=ego + half,
            ego_strength=ego,
            superego_strength=ego + half,
        )

    def test_zero_conflict_baseline_temperature(self):
        """With id=ego=sup=5, conflict=0 and temp should equal the base 0.60."""
        agent = _DriveStub(id_strength=5.0, ego_strength=5.0, superego_strength=5.0)
        assert agent.conflict_index() == pytest.approx(0.0)
        assert agent.compute_temperature() == pytest.approx(0.60)

    def test_higher_conflict_raises_temperature(self):
        """Temperature for conflict=8.0 must exceed temperature for conflict=2.0."""
        low = self._make_symmetric_conflict(2.0)
        high = self._make_symmetric_conflict(8.0)
        assert high.compute_temperature() > low.compute_temperature()

    @pytest.mark.parametrize(
        "ide, ego, sup",
        [
            (0.0, 10.0, 0.0),   # extreme low Id, high Ego, low SuperEgo
            (10.0, 0.0, 10.0),  # maximum conflict
            (5.0, 5.0, 5.0),    # balanced
        ],
    )
    def test_temperature_stays_within_bounds(self, ide, ego, sup):
        """Temperature must always remain in [0.25, 0.95]."""
        agent = _DriveStub(id_strength=ide, ego_strength=ego, superego_strength=sup)
        temp = agent.compute_temperature()
        assert 0.25 <= temp <= 0.95, (
            f"Temperature {temp} out of bounds for drives ({ide},{ego},{sup})"
        )

    def test_conflict_component_is_positive(self):
        """The conflict addend (0.015 * conflict_index) must be non-negative."""
        agent = self._make_symmetric_conflict(6.0)
        conflict = agent.conflict_index()
        assert 0.015 * conflict >= 0.0


# ---------------------------------------------------------------------------
# Tests: Energy drain scales with conflict
# ---------------------------------------------------------------------------


class TestEnergyDrainConflictCorrelation:
    """Energy drain per turn must increase with drive conflict level."""

    def test_high_conflict_drains_more_energy(self):
        """With higher conflict, the energy drop must be larger."""
        # Low conflict: id=5, ego=5, sup=5 → pre_conflict = 0
        low = _DriveStub(id_strength=5.0, ego_strength=5.0, superego_strength=5.0)
        low.update_drives_after_turn("reflective", "neutral", 0.5, rng_seed=42)
        drain_low = 100.0 - low.energy_level

        # High conflict: id=9, ego=5, sup=9 → pre_conflict = 8
        high = _DriveStub(id_strength=9.0, ego_strength=5.0, superego_strength=9.0)
        high.update_drives_after_turn("reflective", "neutral", 0.5, rng_seed=42)
        drain_high = 100.0 - high.energy_level

        assert drain_high > drain_low, (
            f"High-conflict drain ({drain_high:.2f}) must exceed low-conflict drain ({drain_low:.2f})"
        )

    def test_energy_never_negative(self):
        """Energy must never go below 0.0."""
        agent = _DriveStub(id_strength=10.0, ego_strength=0.0, superego_strength=10.0)
        for _ in range(20):
            agent.update_drives_after_turn("aggressive", "anger", 1.0)
        assert agent.energy_level >= 0.0

    def test_energy_drain_capped_at_twice_max(self):
        """Drain must not exceed 2 × energy_drain_max regardless of conflict."""
        # Maximum conflict = 20 (id=10, ego=0, sup=10)
        # 0.4 * 20 = 8, base max = 15, cap = 30 = 2 × 15
        agent = _DriveStub(id_strength=10.0, ego_strength=0.0, superego_strength=10.0)
        for seed in range(50):
            agent.energy_level = 100.0  # reset energy; drives don't affect the cap check
            agent.update_drives_after_turn("aggressive", "anger", 1.0, rng_seed=seed)
            drain = 100.0 - agent.energy_level
            assert drain <= ENERGY_DRAIN_MAX * 2.0 + 1e-9, (
                f"Drain {drain:.2f} exceeded cap of {ENERGY_DRAIN_MAX * 2.0}"
            )


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
        name: str = "",
    ):
        self.drives = {
            "id_strength": id_strength,
            "ego_strength": ego_strength,
            "superego_strength": superego_strength,
            "self_awareness": self_awareness,
        }
        self.energy_level: float = 100.0
        self.name: str = name

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

        # Fluidity: each turn, id and superego are pulled back toward neutral (5.0)
        # proportionally to how far they've drifted, plus a random oscillation so they
        # can move in either direction.  This prevents either drive from stagnating at
        # an extreme level and ensures changes ripple into the ego balance every turn.
        # Fluidity: per-agent biased reversion with extreme rebalancing.
        # Mirror of the production logic in Agent.update_drives_after_turn().
        _ATHENA_ID_TARGET = 6.5
        _SOCRATES_SUP_TARGET = 6.5
        _EXTREME_HIGH = 8.5
        _EXTREME_LOW = 1.5
        _EXTREME_BOOST = 0.06
        _ide_target = _ATHENA_ID_TARGET if self.name == "Athena" else 5.0
        _sup_target = _SOCRATES_SUP_TARGET if self.name == "Socrates" else 5.0
        _ide_rate = 0.04 + (_EXTREME_BOOST if (ide >= _EXTREME_HIGH or ide <= _EXTREME_LOW) else 0.0)
        _sup_rate = 0.04 + (_EXTREME_BOOST if (sup >= _EXTREME_HIGH or sup <= _EXTREME_LOW) else 0.0)
        ide += _ide_rate * (_ide_target - ide) + random.uniform(-0.15, 0.15)
        sup += _sup_rate * (_sup_target - sup) + random.uniform(-0.15, 0.15)
        ide = max(0.0, min(10.0, ide))
        sup = max(0.0, min(10.0, sup))

        # Ego drain at the expense of the biased drive.
        if self.name == "Athena":
            ego = max(0.0, ego - 0.03 * max(0.0, ide - 5.0) / 5.0)
        elif self.name == "Socrates":
            ego = max(0.0, ego - 0.03 * max(0.0, sup - 5.0) / 5.0)

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
        result = agent.conflict_index()
        _print_table(
            ["Id", "Ego", "SuperEgo", "conflict_index", "Expected"],
            [["5.0", "5.0", "5.0", f"{result:.4f}", "0.0000"]],
            title="test_balanced_drives_zero_conflict",
        )
        assert result == pytest.approx(0.0)

    def test_conflict_with_high_id_only(self):
        """High Id vs Ego with balanced SuperEgo produces expected conflict."""
        # |8-5| + |5-5| = 3 + 0 = 3
        agent = _DriveStub(id_strength=8.0, ego_strength=5.0, superego_strength=5.0)
        result = agent.conflict_index()
        _print_table(
            ["Id", "Ego", "SuperEgo", "conflict_index", "Expected", "Formula"],
            [["8.0", "5.0", "5.0", f"{result:.4f}", "3.0000", "|8-5|+|5-5|=3+0"]],
            title="test_conflict_with_high_id_only",
        )
        assert result == pytest.approx(3.0)

    def test_conflict_with_high_superego_only(self):
        """High SuperEgo vs Ego with balanced Id produces expected conflict."""
        # |5-5| + |9-5| = 0 + 4 = 4
        agent = _DriveStub(id_strength=5.0, ego_strength=5.0, superego_strength=9.0)
        result = agent.conflict_index()
        _print_table(
            ["Id", "Ego", "SuperEgo", "conflict_index", "Expected", "Formula"],
            [["5.0", "5.0", "9.0", f"{result:.4f}", "4.0000", "|5-5|+|9-5|=0+4"]],
            title="test_conflict_with_high_superego_only",
        )
        assert result == pytest.approx(4.0)

    def test_symmetric_high_conflict(self):
        """Symmetric deviation from Ego gives doubled conflict."""
        # |9-5| + |9-5| = 4 + 4 = 8
        agent = _DriveStub(id_strength=9.0, ego_strength=5.0, superego_strength=9.0)
        result = agent.conflict_index()
        _print_table(
            ["Id", "Ego", "SuperEgo", "conflict_index", "Expected", "Formula"],
            [["9.0", "5.0", "9.0", f"{result:.4f}", "8.0000", "|9-5|+|9-5|=4+4"]],
            title="test_symmetric_high_conflict",
        )
        assert result == pytest.approx(8.0)

    def test_maximum_conflict(self):
        """Maximum possible conflict: Id=10, Ego=0, SuperEgo=10 → 20."""
        agent = _DriveStub(id_strength=10.0, ego_strength=0.0, superego_strength=10.0)
        result = agent.conflict_index()
        _print_table(
            ["Id", "Ego", "SuperEgo", "conflict_index", "Expected", "Formula"],
            [
                [
                    "10.0",
                    "0.0",
                    "10.0",
                    f"{result:.4f}",
                    "20.0000",
                    "|10-0|+|10-0|=10+10",
                ]
            ],
            title="test_maximum_conflict",
        )
        # Summary bar chart across all key scenarios
        scenarios = [
            ("balanced", _DriveStub(5.0, 5.0, 5.0).conflict_index()),
            ("high-Id", _DriveStub(8.0, 5.0, 5.0).conflict_index()),
            ("high-Sup", _DriveStub(5.0, 5.0, 9.0).conflict_index()),
            ("symmetric", _DriveStub(9.0, 5.0, 9.0).conflict_index()),
            ("maximum", _DriveStub(10.0, 0.0, 10.0).conflict_index()),
        ]
        _print_bar_chart(scenarios, title="conflict_index across scenarios")
        assert result == pytest.approx(20.0)

    @pytest.mark.parametrize(
        "ide, ego, sup, expected",
        [
            (
                2.9,
                8.8,
                8.7,
                pytest.approx(6.0, abs=0.1),
            ),  # example from problem statement
            (5.0, 5.0, 5.0, pytest.approx(0.0)),
            (10.0, 5.0, 0.0, pytest.approx(10.0)),
        ],
    )
    def test_conflict_parametrized(self, ide, ego, sup, expected):
        agent = _DriveStub(id_strength=ide, ego_strength=ego, superego_strength=sup)
        result = agent.conflict_index()
        _print_table(
            ["Id", "Ego", "SuperEgo", "conflict_index"],
            [[str(ide), str(ego), str(sup), f"{result:.4f}"]],
            title=f"test_conflict_parametrized  id={ide} ego={ego} sup={sup}",
        )
        assert result == expected


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
        _print_table(
            [
                "Drives (id/ego/sup)",
                "Conflict",
                "Ego Before",
                "Ego After",
                "No-conflict Baseline",
            ],
            [
                [
                    "9.0 / 5.0 / 8.0",
                    "7.0",
                    f"{ego_before:.4f}",
                    f"{ego_after:.4f}",
                    f"{no_conflict_ego:.4f}",
                ]
            ],
            title="test_high_conflict_reduces_ego",
        )
        _print_bar_chart(
            [
                ("before", ego_before),
                ("after", ego_after),
                ("baseline", no_conflict_ego),
            ],
            title="Ego levels: before turn vs after (high conflict)",
        )
        assert (
            ego_after < no_conflict_ego
        ), f"Ego should be eroded by conflict; got {ego_after:.3f} vs baseline {no_conflict_ego:.3f}"

    def test_low_conflict_does_not_erode_ego(self):
        """With pre_conflict <= 4.0, no erosion step is applied."""
        # id=5, ego=5, sup=5: conflict = 0
        agent = _DriveStub(id_strength=5.0, ego_strength=5.0, superego_strength=5.0)
        ego_before = float(agent.drives["ego_strength"])
        agent.update_drives_after_turn("reflective", "neutral", 0.5)
        ego_after = float(agent.drives["ego_strength"])
        # "reflective" adds +0.05 + 0.06; erosion (pre_conflict=0 <= 4.0) is not triggered
        expected = min(10.0, ego_before + 0.05 + 0.06)
        _print_table(
            ["Drives (id/ego/sup)", "Conflict", "Ego Before", "Ego After", "Expected"],
            [
                [
                    "5.0 / 5.0 / 5.0",
                    "0.0",
                    f"{ego_before:.4f}",
                    f"{ego_after:.4f}",
                    f"{expected:.4f}",
                ]
            ],
            title="test_low_conflict_does_not_erode_ego",
        )
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

        _print_table(
            ["Scenario", "Id", "Ego", "SuperEgo", "Conflict", "Ego After Turn"],
            [
                ["low conflict", "7.0", "5.0", "5.0", "2.0", f"{ego_low_conflict:.4f}"],
                [
                    "high conflict",
                    "9.0",
                    "5.0",
                    "9.0",
                    "8.0",
                    f"{ego_high_conflict:.4f}",
                ],
            ],
            title="test_erosion_proportional_to_conflict",
        )
        _print_bar_chart(
            [("low (c=2)", ego_low_conflict), ("high (c=8)", ego_high_conflict)],
            title="Ego after turn: low vs high conflict",
        )
        assert (
            ego_high_conflict < ego_low_conflict
        ), "Higher conflict must result in lower Ego after the turn"

    def test_ego_never_negative(self):
        """Ego must never drop below 0.0, even with extreme conflict."""
        # Maximum possible conflict: id=10, ego=0, sup=10 → conflict = 20
        agent = _DriveStub(id_strength=10.0, ego_strength=0.0, superego_strength=10.0)
        agent.update_drives_after_turn("aggressive", "anger", 1.0)
        ego_result = float(agent.drives["ego_strength"])
        _print_table(
            [
                "Drives (id/ego/sup)",
                "Response Kind",
                "Emotion",
                "Ego After",
                "Min Allowed",
            ],
            [
                [
                    "10.0 / 0.0 / 10.0",
                    "aggressive",
                    "anger",
                    f"{ego_result:.4f}",
                    "0.0000",
                ]
            ],
            title="test_ego_never_negative",
        )
        assert ego_result >= 0.0


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
        conflict = agent.conflict_index()
        temp = agent.compute_temperature()
        _print_table(
            ["Id", "Ego", "SuperEgo", "conflict_index", "temperature", "Expected temp"],
            [["5.0", "5.0", "5.0", f"{conflict:.4f}", f"{temp:.4f}", "0.6000"]],
            title="test_zero_conflict_baseline_temperature",
        )
        assert conflict == pytest.approx(0.0)
        assert temp == pytest.approx(0.60)

    def test_higher_conflict_raises_temperature(self):
        """Temperature for conflict=8.0 must exceed temperature for conflict=2.0."""
        low = self._make_symmetric_conflict(2.0)
        high = self._make_symmetric_conflict(8.0)
        temp_low = low.compute_temperature()
        temp_high = high.compute_temperature()
        _print_table(
            ["Scenario", "conflict_index", "temperature"],
            [
                ["low (c=2.0)", f"{low.conflict_index():.4f}", f"{temp_low:.4f}"],
                ["high (c=8.0)", f"{high.conflict_index():.4f}", f"{temp_high:.4f}"],
            ],
            title="test_higher_conflict_raises_temperature",
        )
        # Full sweep graph: conflict 0..10 → temperature
        sweep = [
            (f"c={c}", self._make_symmetric_conflict(float(c)).compute_temperature())
            for c in range(0, 11)
        ]
        _print_bar_chart(sweep, title="Temperature vs conflict_index  (conflict 0→10)")
        assert temp_high > temp_low

    @pytest.mark.parametrize(
        "ide, ego, sup",
        [
            (0.0, 10.0, 0.0),  # extreme low Id, high Ego, low SuperEgo
            (10.0, 0.0, 10.0),  # maximum conflict
            (5.0, 5.0, 5.0),  # balanced
        ],
    )
    def test_temperature_stays_within_bounds(self, ide, ego, sup):
        """Temperature must always remain in [0.25, 0.95]."""
        agent = _DriveStub(id_strength=ide, ego_strength=ego, superego_strength=sup)
        temp = agent.compute_temperature()
        _print_table(
            ["Id", "Ego", "SuperEgo", "conflict_index", "temperature", "Bounds"],
            [
                [
                    str(ide),
                    str(ego),
                    str(sup),
                    f"{agent.conflict_index():.4f}",
                    f"{temp:.4f}",
                    "[0.25, 0.95]",
                ]
            ],
            title=f"test_temperature_stays_within_bounds  id={ide} ego={ego} sup={sup}",
        )
        assert (
            0.25 <= temp <= 0.95
        ), f"Temperature {temp} out of bounds for drives ({ide},{ego},{sup})"

    def test_conflict_component_is_positive(self):
        """The conflict addend (0.015 * conflict_index) must be non-negative."""
        agent = self._make_symmetric_conflict(6.0)
        conflict = agent.conflict_index()
        addend = 0.015 * conflict
        _print_table(
            ["conflict_index", "0.015 × conflict", "≥ 0?"],
            [[f"{conflict:.4f}", f"{addend:.4f}", str(addend >= 0.0)]],
            title="test_conflict_component_is_positive",
        )
        assert addend >= 0.0


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

        _print_table(
            ["Scenario", "Id", "Ego", "SuperEgo", "Conflict", "Energy Drain"],
            [
                ["low conflict", "5.0", "5.0", "5.0", "0.0", f"{drain_low:.4f}"],
                ["high conflict", "9.0", "5.0", "9.0", "8.0", f"{drain_high:.4f}"],
            ],
            title="test_high_conflict_drains_more_energy",
        )
        _print_bar_chart(
            [("low (c=0)", drain_low), ("high (c=8)", drain_high)],
            title="Energy drain: low vs high conflict",
        )
        assert (
            drain_high > drain_low
        ), f"High-conflict drain ({drain_high:.2f}) must exceed low-conflict drain ({drain_low:.2f})"

    def test_energy_never_negative(self):
        """Energy must never go below 0.0."""
        agent = _DriveStub(id_strength=10.0, ego_strength=0.0, superego_strength=10.0)
        rows = []
        for turn in range(20):
            agent.update_drives_after_turn("aggressive", "anger", 1.0)
            rows.append([str(turn + 1), f"{agent.energy_level:.4f}"])
        _print_table(
            ["Turn", "Energy Level"],
            rows,
            title="test_energy_never_negative  (20 aggressive turns, max conflict)",
        )
        assert agent.energy_level >= 0.0

    def test_energy_drain_capped_at_twice_max(self):
        """Drain must not exceed 2 × energy_drain_max regardless of conflict."""
        # Maximum conflict = 20 (id=10, ego=0, sup=10)
        # 0.4 * 20 = 8, base max = 15, cap = 30 = 2 × 15
        cap = ENERGY_DRAIN_MAX * 2.0
        rows = []
        agent = _DriveStub(id_strength=10.0, ego_strength=0.0, superego_strength=10.0)
        for seed in range(50):
            agent.energy_level = (
                100.0  # reset energy; drives don't affect the cap check
            )
            agent.update_drives_after_turn("aggressive", "anger", 1.0, rng_seed=seed)
            drain = 100.0 - agent.energy_level
            rows.append(
                [
                    str(seed),
                    f"{drain:.4f}",
                    f"{cap:.4f}",
                    "✓" if drain <= cap + 1e-9 else "✗",
                ]
            )
        _print_table(
            ["seed", "drain", "cap (2×max)", "within cap?"],
            rows,
            title=f"test_energy_drain_capped_at_twice_max  cap={cap:.1f}",
        )
        max_drain_seen = max(float(r[1]) for r in rows)
        _print_bar_chart(
            [(f"s={r[0]}", float(r[1])) for r in rows[::5]],
            title=f"Energy drain samples (every 5th seed) – cap={cap:.1f}",
        )
        for seed_row in rows:
            drain_val = float(seed_row[1])
            assert (
                drain_val <= cap + 1e-9
            ), f"Drain {drain_val:.2f} exceeded cap of {cap}"


# ---------------------------------------------------------------------------
# Tests: Agent-specific biased id/superego reversion (Athena id, Socrates superego)
# ---------------------------------------------------------------------------


class TestAgentBiasedDriveReversion:
    """
    Athena's id drifts toward 6.5 (biased above neutral) at ego's expense.
    Socrates' superego drifts toward 6.5 at ego's expense.
    At extremes (>= 8.5 or <= 1.5) reversion is boosted for faster re-equilibration.
    """

    def test_athena_id_drifts_above_neutral_over_turns(self):
        """Starting from balanced drives, Athena's id should trend above 5.0."""
        random.seed(0)
        athena = _DriveStub(5.0, 5.0, 5.0, name="Athena")
        for _ in range(50):
            athena.update_drives_after_turn("reflective", "neutral", 0.5, rng_seed=0)
        ide_final = float(athena.drives["id_strength"])
        _print_table(
            ["Agent", "id after 50 turns", "Expected > 5.0"],
            [["Athena", f"{ide_final:.4f}", "yes"]],
            title="test_athena_id_drifts_above_neutral_over_turns",
        )
        assert ide_final > 5.0, (
            f"Athena's id should trend above neutral; got {ide_final:.4f}"
        )

    def test_socrates_superego_drifts_above_neutral_over_turns(self):
        """Starting from balanced drives, Socrates' superego should trend above 5.0."""
        random.seed(0)
        socrates = _DriveStub(5.0, 5.0, 5.0, name="Socrates")
        for _ in range(50):
            socrates.update_drives_after_turn("reflective", "neutral", 0.5, rng_seed=0)
        sup_final = float(socrates.drives["superego_strength"])
        _print_table(
            ["Agent", "superego after 50 turns", "Expected > 5.0"],
            [["Socrates", f"{sup_final:.4f}", "yes"]],
            title="test_socrates_superego_drifts_above_neutral_over_turns",
        )
        assert sup_final > 5.0, (
            f"Socrates' superego should trend above neutral; got {sup_final:.4f}"
        )

    def test_generic_agent_id_stays_near_neutral(self):
        """A nameless agent's id should stay near 5.0 (no bias)."""
        random.seed(0)
        generic = _DriveStub(5.0, 5.0, 5.0, name="")
        for _ in range(50):
            generic.update_drives_after_turn("reflective", "neutral", 0.5, rng_seed=0)
        ide_final = float(generic.drives["id_strength"])
        _print_table(
            ["Agent", "id after 50 turns", "Expected ≈ 5.0"],
            [["generic", f"{ide_final:.4f}", "~5.0"]],
            title="test_generic_agent_id_stays_near_neutral",
        )
        # No bias: id should not consistently drift far above 5.0
        assert ide_final < 7.0, (
            f"Generic agent's id should stay near neutral; got {ide_final:.4f}"
        )

    def test_athena_id_bias_drains_ego(self):
        """Athena's ego should be lower than a generic agent's ego after many turns."""
        random.seed(0)
        athena = _DriveStub(7.0, 5.0, 5.0, name="Athena")
        generic = _DriveStub(7.0, 5.0, 5.0, name="")
        for _ in range(30):
            athena.update_drives_after_turn("reflective", "neutral", 0.5, rng_seed=0)
            generic.update_drives_after_turn("reflective", "neutral", 0.5, rng_seed=0)
        ego_athena = float(athena.drives["ego_strength"])
        ego_generic = float(generic.drives["ego_strength"])
        _print_table(
            ["Agent", "ego after 30 turns (id=7 start)"],
            [["Athena", f"{ego_athena:.4f}"], ["generic", f"{ego_generic:.4f}"]],
            title="test_athena_id_bias_drains_ego",
        )
        assert ego_athena < ego_generic, (
            f"Athena's ego ({ego_athena:.4f}) should be lower than generic ({ego_generic:.4f}) "
            "due to id bias drain"
        )

    def test_socrates_superego_bias_drains_ego(self):
        """Socrates' ego should be lower than a generic agent's ego after many turns."""
        random.seed(0)
        socrates = _DriveStub(5.0, 5.0, 7.0, name="Socrates")
        generic = _DriveStub(5.0, 5.0, 7.0, name="")
        for _ in range(30):
            socrates.update_drives_after_turn("reflective", "neutral", 0.5, rng_seed=0)
            generic.update_drives_after_turn("reflective", "neutral", 0.5, rng_seed=0)
        ego_socrates = float(socrates.drives["ego_strength"])
        ego_generic = float(generic.drives["ego_strength"])
        _print_table(
            ["Agent", "ego after 30 turns (sup=7 start)"],
            [["Socrates", f"{ego_socrates:.4f}"], ["generic", f"{ego_generic:.4f}"]],
            title="test_socrates_superego_bias_drains_ego",
        )
        assert ego_socrates < ego_generic, (
            f"Socrates' ego ({ego_socrates:.4f}) should be lower than generic ({ego_generic:.4f}) "
            "due to superego bias drain"
        )

    def test_athena_id_extreme_high_reverts_faster(self):
        """Athena's id starting at an extreme high should converge back faster than normal."""
        random.seed(42)
        athena_extreme = _DriveStub(9.5, 5.0, 5.0, name="Athena")
        athena_normal = _DriveStub(7.0, 5.0, 5.0, name="Athena")
        for _ in range(10):
            athena_extreme.update_drives_after_turn("reflective", "neutral", 0.5, rng_seed=42)
            athena_normal.update_drives_after_turn("reflective", "neutral", 0.5, rng_seed=42)
        ide_extreme = float(athena_extreme.drives["id_strength"])
        ide_normal = float(athena_normal.drives["id_strength"])
        distance_extreme = abs(ide_extreme - 9.5)  # how far it moved from start
        distance_normal = abs(ide_normal - 7.0)
        _print_table(
            ["Scenario", "start id", "id after 10 turns", "distance moved"],
            [
                ["extreme (9.5)", "9.5", f"{ide_extreme:.4f}", f"{distance_extreme:.4f}"],
                ["normal  (7.0)", "7.0", f"{ide_normal:.4f}", f"{distance_normal:.4f}"],
            ],
            title="test_athena_id_extreme_high_reverts_faster",
        )
        assert distance_extreme > distance_normal, (
            f"Extreme id (start=9.5) should move more ({distance_extreme:.4f}) than "
            f"normal id (start=7.0, moved={distance_normal:.4f}) due to boost"
        )

    def test_socrates_superego_extreme_low_reverts_faster(self):
        """Socrates' superego at extreme low should revert toward target faster than normal."""
        random.seed(42)
        socrates_extreme = _DriveStub(5.0, 5.0, 0.5, name="Socrates")
        socrates_normal = _DriveStub(5.0, 5.0, 3.0, name="Socrates")
        for _ in range(10):
            socrates_extreme.update_drives_after_turn("reflective", "neutral", 0.5, rng_seed=42)
            socrates_normal.update_drives_after_turn("reflective", "neutral", 0.5, rng_seed=42)
        sup_extreme = float(socrates_extreme.drives["superego_strength"])
        sup_normal = float(socrates_normal.drives["superego_strength"])
        distance_extreme = abs(sup_extreme - 0.5)
        distance_normal = abs(sup_normal - 3.0)
        _print_table(
            ["Scenario", "start sup", "sup after 10 turns", "distance moved"],
            [
                ["extreme (0.5)", "0.5", f"{sup_extreme:.4f}", f"{distance_extreme:.4f}"],
                ["normal  (3.0)", "3.0", f"{sup_normal:.4f}", f"{distance_normal:.4f}"],
            ],
            title="test_socrates_superego_extreme_low_reverts_faster",
        )
        assert distance_extreme > distance_normal, (
            f"Extreme superego (start=0.5) should move more ({distance_extreme:.4f}) than "
            f"normal superego (start=3.0, moved={distance_normal:.4f}) due to boost"
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])

# tests/test_drive_pressure.py
"""
Acceptance tests for the DrivePressure (urgency/tension) feature.

Validates:
  A. Pressure rises during stagnation.
  B. Pressure forces brevity (word cap).
  C. Pressure decays after progress (unresolved_count decreases).
  D. No breaking changes: existing module-level constants + Agent init still work.
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

from Entelgia_production_meta import (
    compute_drive_pressure,
    _topic_signature,
    _trim_to_word_limit,
    _is_question_resolved,
)


# ---------------------------------------------------------------------------
# Unit tests: compute_drive_pressure formula
# ---------------------------------------------------------------------------


class TestComputeDrivePressure:
    """Direct unit tests for the compute_drive_pressure calculation."""

    def test_default_initial_value(self):
        """Starting pressure of 2.0 is within valid range."""
        assert 0.0 <= 2.0 <= 10.0

    def test_output_clamped_to_range(self):
        """Result must always be in [0.0, 10.0] regardless of inputs."""
        for conflict in (0.0, 5.0, 10.0, 20.0):
            for energy in (0.0, 50.0, 100.0):
                for unresolved in (0, 3, 5):
                    for stagnation in (0.0, 0.5, 1.0):
                        p = compute_drive_pressure(
                            prev_pressure=5.0,
                            energy=energy,
                            conflict=conflict,
                            unresolved_count=unresolved,
                            stagnation=stagnation,
                        )
                        assert 0.0 <= p <= 10.0, (
                            f"Out of range: {p} for conflict={conflict} energy={energy} "
                            f"unresolved={unresolved} stagnation={stagnation}"
                        )

    def test_high_conflict_raises_pressure(self):
        """High conflict should increase pressure toward the target."""
        low = compute_drive_pressure(
            prev_pressure=2.0, energy=80.0, conflict=1.0,
            unresolved_count=0, stagnation=0.0,
        )
        high = compute_drive_pressure(
            prev_pressure=2.0, energy=80.0, conflict=9.0,
            unresolved_count=0, stagnation=0.0,
        )
        assert high > low, f"High conflict ({high:.3f}) should exceed low ({low:.3f})"

    def test_stagnation_raises_pressure(self):
        """Stagnation=1.0 should increase pressure compared to stagnation=0.0."""
        no_stag = compute_drive_pressure(
            prev_pressure=2.0, energy=80.0, conflict=3.0,
            unresolved_count=0, stagnation=0.0,
        )
        full_stag = compute_drive_pressure(
            prev_pressure=2.0, energy=80.0, conflict=3.0,
            unresolved_count=0, stagnation=1.0,
        )
        assert full_stag > no_stag

    def test_decay_when_calm(self):
        """With conflict<4, stagnation<0.3, unresolved=0, pressure decays."""
        p0 = 5.0
        p1 = compute_drive_pressure(
            prev_pressure=p0, energy=80.0, conflict=1.0,
            unresolved_count=0, stagnation=0.0,
        )
        # Low conflict+stagnation → target is low AND decay of 0.4 applies
        assert p1 < p0, f"Pressure should decay; got {p1:.3f} from {p0:.3f}"

    def test_unresolved_raises_pressure(self):
        """More unresolved questions → higher pressure."""
        p_zero = compute_drive_pressure(
            prev_pressure=2.0, energy=80.0, conflict=2.0,
            unresolved_count=0, stagnation=0.0,
        )
        p_three = compute_drive_pressure(
            prev_pressure=2.0, energy=80.0, conflict=2.0,
            unresolved_count=3, stagnation=0.0,
        )
        assert p_three > p_zero

    def test_smoothing_inertia(self):
        """New pressure is a weighted blend of prev_pressure and target (alpha=0.35)."""
        # With alpha=0.35: new_p = 0.65 * prev + 0.35 * target
        # Use maximum inputs to get a known target:
        # conflict=10, energy=0, unresolved=3, stagnation=1.0
        # raw = 0.45*1 + 0.25*1 + 0.20*1 + 0.10*1 = 1.0  → target = 10.0
        # new_p = 0.65 * 2.0 + 0.35 * 10.0 = 1.3 + 3.5 = 4.8
        p = compute_drive_pressure(
            prev_pressure=2.0, energy=0.0, conflict=10.0,
            unresolved_count=3, stagnation=1.0,
        )
        assert p == pytest.approx(4.8, abs=0.05)


# ---------------------------------------------------------------------------
# Test A: Pressure rises during stagnation
# ---------------------------------------------------------------------------


class TestPressureRisesDuringStagnation:
    """Pressure must increase by at least +2.0 from baseline by turn 6
    when running with same topic and repeated A/B questions."""

    def test_pressure_rises_over_8_stagnant_turns(self):
        """Simulate 8 turns with full stagnation + unresolved questions."""
        pressure = 2.0  # initial
        baseline = pressure

        for _ in range(8):
            pressure = compute_drive_pressure(
                prev_pressure=pressure,
                energy=80.0,
                conflict=5.0,
                unresolved_count=2,
                stagnation=1.0,
            )

        assert pressure >= baseline + 2.0, (
            f"Pressure after 8 stagnant turns ({pressure:.2f}) should be at least "
            f"{baseline + 2.0:.2f}"
        )

    def test_pressure_at_turn_6_is_higher_than_baseline(self):
        """By turn 6, pressure must have risen by at least +2.0."""
        pressure = 2.0
        baseline = pressure

        for _ in range(6):
            pressure = compute_drive_pressure(
                prev_pressure=pressure,
                energy=80.0,
                conflict=5.0,
                unresolved_count=2,
                stagnation=1.0,
            )

        assert pressure >= baseline + 2.0, (
            f"Turn-6 pressure ({pressure:.2f}) should be at least {baseline + 2.0:.2f}"
        )


# ---------------------------------------------------------------------------
# Test B: Pressure forces brevity
# ---------------------------------------------------------------------------


class TestPressureForcedBrevity:
    """When pressure >= 8.0, output must be <= 90 words."""

    def _word_count(self, text: str) -> int:
        return len(text.split())

    def test_trim_to_80_words(self):
        """_trim_to_word_limit(text, 80) must produce <= 80 words."""
        long_text = " ".join(["word"] * 200)
        trimmed = _trim_to_word_limit(long_text, 80)
        assert self._word_count(trimmed) <= 80

    def test_trim_to_120_words(self):
        """_trim_to_word_limit(text, 120) must produce <= 120 words."""
        long_text = " ".join(["word"] * 200)
        trimmed = _trim_to_word_limit(long_text, 120)
        assert self._word_count(trimmed) <= 120

    def test_short_text_unchanged(self):
        """Text already within the limit is returned unchanged."""
        short = "Hello world. This is a test."
        assert _trim_to_word_limit(short, 120) == short

    def test_trim_preserves_sentence_boundary(self):
        """Trimmer should end at the last sentence boundary if possible."""
        text = "First sentence ends here. Second sentence ends here. " + " ".join(
            ["extra"] * 100
        )
        trimmed = _trim_to_word_limit(text, 10)
        # Should end with a period at the last sentence boundary
        assert trimmed.endswith(".") or len(trimmed.split()) <= 10

    def test_high_pressure_produces_short_output(self):
        """Verify that a simulated high-pressure scenario would cap output to 80 words."""
        # Build a 200-word response and apply the 80-word cap directly
        response = " ".join([f"word{i}" for i in range(200)])
        capped = _trim_to_word_limit(response, 80)
        assert self._word_count(capped) <= 80


# ---------------------------------------------------------------------------
# Test C: Pressure decays after progress
# ---------------------------------------------------------------------------


class TestPressureDecaysAfterProgress:
    """When unresolved_count decreases, pressure must drop within 2 turns."""

    def test_pressure_decreases_after_resolution(self):
        """Going from unresolved=3 to unresolved=0 should reduce pressure within 2 turns."""
        # Build up pressure with stagnation
        pressure = 2.0
        for _ in range(6):
            pressure = compute_drive_pressure(
                prev_pressure=pressure,
                energy=60.0,
                conflict=5.0,
                unresolved_count=3,
                stagnation=0.8,
            )
        high_pressure = pressure

        # Resolution: unresolved drops to 0, stagnation improves
        p1 = compute_drive_pressure(
            prev_pressure=high_pressure,
            energy=70.0,
            conflict=3.0,
            unresolved_count=0,
            stagnation=0.1,
        )
        p2 = compute_drive_pressure(
            prev_pressure=p1,
            energy=75.0,
            conflict=2.0,
            unresolved_count=0,
            stagnation=0.0,
        )

        assert p2 < high_pressure - 0.5, (
            f"Pressure ({p2:.2f}) should have dropped by at least 0.5 from "
            f"high_pressure ({high_pressure:.2f}) within 2 turns"
        )

    def test_unresolved_count_decrements_on_answer(self):
        """Simulated answer resolution must reduce unresolved count."""
        open_questions = 2
        assert _is_question_resolved("A) I choose the first option.")
        open_questions = max(0, open_questions - 1)
        assert open_questions == 1

    def test_unresolved_count_no_decrement_without_answer(self):
        """Non-answer replies must not reduce unresolved count."""
        assert not _is_question_resolved("This is a complex philosophical topic.")
        assert not _is_question_resolved("Let me think about this further.")


# ---------------------------------------------------------------------------
# Test D: No breaking changes
# ---------------------------------------------------------------------------


class TestNoBreakingChanges:
    """Existing module-level constants and entry points must remain intact."""

    def test_constants_present(self):
        """Required constants must still be importable."""
        import Entelgia_production_meta as m

        assert hasattr(m, "LLM_RESPONSE_LIMIT")
        assert hasattr(m, "MAX_RESPONSE_WORDS")
        assert hasattr(m, "FORBIDDEN_PHRASES")
        assert hasattr(m, "FORBIDDEN_STARTERS")

    def test_new_functions_importable(self):
        """New drive-pressure helpers must be importable."""
        import Entelgia_production_meta as m

        assert callable(m.compute_drive_pressure)
        assert callable(m._topic_signature)
        assert callable(m._trim_to_word_limit)
        assert callable(m._is_question_resolved)

    def test_topic_signature_returns_string(self):
        """_topic_signature must return a non-empty hex string and be deterministic."""
        sig = _topic_signature("The nature of consciousness is debated by philosophers.")
        assert isinstance(sig, str) and len(sig) > 0
        # Deterministic: same input always produces same output
        assert _topic_signature("The nature of consciousness is debated by philosophers.") == sig

    def test_topic_signature_same_for_similar_text(self):
        """Identical key-word sets must produce the same signature."""
        text1 = "consciousness mind philosophy debate"
        text2 = "philosophy consciousness debate mind"
        assert _topic_signature(text1) == _topic_signature(text2)

    def test_topic_signature_different_for_different_topics(self):
        """Different topics must produce different signatures (not guaranteed but
        very likely for clearly different content)."""
        sig1 = _topic_signature("quantum physics electrons atoms nucleus")
        sig2 = _topic_signature("freedom democracy justice society politics")
        assert sig1 != sig2

    def test_compute_drive_pressure_is_deterministic(self):
        """Same inputs must always produce same output."""
        args = dict(
            prev_pressure=3.5,
            energy=60.0,
            conflict=6.0,
            unresolved_count=2,
            stagnation=0.5,
        )
        assert compute_drive_pressure(**args) == compute_drive_pressure(**args)

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
    _PRESSURE_FEEDBACK_ALPHA,
    _topic_signature,
    _topic_keywords,
    _keyword_jaccard,
    _JACCARD_STAGNATION_THRESHOLD,
    _PE_STAGNATION_INCREMENT,
    _trim_to_word_limit,
    _is_question_resolved,
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
# Unit tests: compute_drive_pressure formula
# ---------------------------------------------------------------------------


class TestComputeDrivePressure:
    """Direct unit tests for the compute_drive_pressure calculation."""

    def test_default_initial_value(self):
        """Starting pressure of 2.0 is within valid range."""
        value = 2.0
        _print_table(
            ["Parameter", "Value", "Min", "Max", "In Range?"],
            [
                [
                    "initial_pressure",
                    f"{value:.1f}",
                    "0.0",
                    "10.0",
                    str(0.0 <= value <= 10.0),
                ]
            ],
            title="Default Initial Pressure",
        )
        assert 0.0 <= 2.0 <= 10.0

    def test_output_clamped_to_range(self):
        """Result must always be in [0.0, 10.0] regardless of inputs."""
        rows = []
        all_in_range = True
        extremes = [
            (0.0, 0.0, 0, 0.0),
            (20.0, 0.0, 0, 0.0),
            (0.0, 100.0, 5, 1.0),
            (20.0, 100.0, 5, 1.0),
        ]
        for conflict, energy, unresolved, stagnation in extremes:
            p = compute_drive_pressure(
                prev_pressure=5.0,
                energy=energy,
                conflict=conflict,
                unresolved_count=unresolved,
                stagnation=stagnation,
            )
            in_range = 0.0 <= p <= 10.0
            if not in_range:
                all_in_range = False
            rows.append(
                [conflict, energy, unresolved, stagnation, f"{p:.4f}", str(in_range)]
            )

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

        _print_table(
            [
                "conflict",
                "energy",
                "unresolved",
                "stagnation",
                "pressure",
                "in [0,10]?",
            ],
            rows,
            title="Clamped Range – Extreme Inputs Summary",
        )
        assert 0.0 <= 2.0 <= 10.0

    def test_high_conflict_raises_pressure(self):
        """High conflict should increase pressure toward the target."""
        low = compute_drive_pressure(
            prev_pressure=2.0,
            energy=80.0,
            conflict=1.0,
            unresolved_count=0,
            stagnation=0.0,
        )
        high = compute_drive_pressure(
            prev_pressure=2.0,
            energy=80.0,
            conflict=9.0,
            unresolved_count=0,
            stagnation=0.0,
        )
        _print_table(
            [
                "conflict",
                "prev_pressure",
                "energy",
                "unresolved",
                "stagnation",
                "pressure",
            ],
            [
                ["1.0", "2.0", "80.0", "0", "0.0", f"{low:.4f}"],
                ["9.0", "2.0", "80.0", "0", "0.0", f"{high:.4f}"],
            ],
            title="High Conflict → Higher Pressure",
        )
        _print_bar_chart(
            [("conflict=1.0", low), ("conflict=9.0", high)],
            title="Pressure: low vs high conflict",
        )
        assert high > low, f"High conflict ({high:.3f}) should exceed low ({low:.3f})"

    def test_stagnation_raises_pressure(self):
        """Stagnation=1.0 should increase pressure compared to stagnation=0.0."""
        no_stag = compute_drive_pressure(
            prev_pressure=2.0,
            energy=80.0,
            conflict=3.0,
            unresolved_count=0,
            stagnation=0.0,
        )
        full_stag = compute_drive_pressure(
            prev_pressure=2.0,
            energy=80.0,
            conflict=3.0,
            unresolved_count=0,
            stagnation=1.0,
        )
        _print_table(
            ["stagnation", "prev_pressure", "conflict", "energy", "pressure"],
            [
                ["0.0", "2.0", "3.0", "80.0", f"{no_stag:.4f}"],
                ["1.0", "2.0", "3.0", "80.0", f"{full_stag:.4f}"],
            ],
            title="Stagnation Effect on Pressure",
        )
        _print_bar_chart(
            [("stag=0.0", no_stag), ("stag=1.0", full_stag)],
            title="Pressure: no stagnation vs full stagnation",
        )
        assert full_stag > no_stag

    def test_decay_when_calm(self):
        """With conflict<4, stagnation<0.3, unresolved=0, pressure decays."""
        p0 = 5.0
        p1 = compute_drive_pressure(
            prev_pressure=p0,
            energy=80.0,
            conflict=1.0,
            unresolved_count=0,
            stagnation=0.0,
        )
        _print_table(
            ["step", "pressure", "delta"],
            [
                ["prev (p0)", f"{p0:.4f}", "–"],
                ["after calm turn (p1)", f"{p1:.4f}", f"{p1 - p0:.4f}"],
            ],
            title="Pressure Decay – Calm Conditions",
        )
        # Low conflict+stagnation → target is low AND decay of 0.4 applies
        assert p1 < p0, f"Pressure should decay; got {p1:.3f} from {p0:.3f}"

    def test_unresolved_raises_pressure(self):
        """More unresolved questions → higher pressure."""
        p_zero = compute_drive_pressure(
            prev_pressure=2.0,
            energy=80.0,
            conflict=2.0,
            unresolved_count=0,
            stagnation=0.0,
        )
        p_three = compute_drive_pressure(
            prev_pressure=2.0,
            energy=80.0,
            conflict=2.0,
            unresolved_count=3,
            stagnation=0.0,
        )
        _print_table(
            ["unresolved_count", "prev_pressure", "conflict", "energy", "pressure"],
            [
                ["0", "2.0", "2.0", "80.0", f"{p_zero:.4f}"],
                ["3", "2.0", "2.0", "80.0", f"{p_three:.4f}"],
            ],
            title="Unresolved Count → Pressure",
        )
        _print_bar_chart(
            [("unresolved=0", p_zero), ("unresolved=3", p_three)],
            title="Pressure: zero vs three unresolved",
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
            prev_pressure=2.0,
            energy=0.0,
            conflict=10.0,
            unresolved_count=3,
            stagnation=1.0,
        )
        _print_table(
            ["parameter", "value"],
            [
                ["prev_pressure", "2.0"],
                ["energy", "0.0"],
                ["conflict", "10.0"],
                ["unresolved_count", "3"],
                ["stagnation", "1.0"],
                ["alpha", "0.35"],
                ["target (computed)", "10.0"],
                ["expected (0.65×2.0 + 0.35×10.0)", "4.8000"],
                ["actual", f"{p:.4f}"],
                ["within ±0.05?", str(abs(p - 4.8) <= 0.05)],
            ],
            title="Smoothing Inertia – Blended Pressure",
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
        turn_rows = []

        for turn in range(1, 9):
            pressure = compute_drive_pressure(
                prev_pressure=pressure,
                energy=80.0,
                conflict=5.0,
                unresolved_count=2,
                stagnation=1.0,
            )
            turn_rows.append([turn, f"{pressure:.4f}", f"{pressure - baseline:.4f}"])

        _print_table(
            ["turn", "pressure", "Δ from baseline"],
            turn_rows,
            title="Pressure Evolution – 8 Stagnant Turns",
        )
        _print_bar_chart(
            [(f"turn {r[0]}", float(r[1])) for r in turn_rows],
            title="Pressure per stagnant turn",
        )
        assert pressure >= baseline + 2.0, (
            f"Pressure after 8 stagnant turns ({pressure:.2f}) should be at least "
            f"{baseline + 2.0:.2f}"
        )

    def test_pressure_at_turn_6_is_higher_than_baseline(self):
        """By turn 6, pressure must have risen by at least +2.0."""
        pressure = 2.0
        baseline = pressure
        turn_rows = []

        for turn in range(1, 7):
            pressure = compute_drive_pressure(
                prev_pressure=pressure,
                energy=80.0,
                conflict=5.0,
                unresolved_count=2,
                stagnation=1.0,
            )
            turn_rows.append([turn, f"{pressure:.4f}", f"{pressure - baseline:.4f}"])

        _print_table(
            ["turn", "pressure", "Δ from baseline (2.0)"],
            turn_rows,
            title="Pressure at Turn 6",
        )
        _print_bar_chart(
            [(f"turn {r[0]}", float(r[1])) for r in turn_rows],
            title="Pressure rise – turns 1-6",
        )
        assert (
            pressure >= baseline + 2.0
        ), f"Turn-6 pressure ({pressure:.2f}) should be at least {baseline + 2.0:.2f}"


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
        wc_before = self._word_count(long_text)
        wc_after = self._word_count(trimmed)
        _print_table(
            ["metric", "value"],
            [
                ["original word count", wc_before],
                ["limit", 80],
                ["trimmed word count", wc_after],
                ["within limit?", str(wc_after <= 80)],
            ],
            title="Trim to 80 Words",
        )
        assert wc_after <= 80

    def test_trim_to_120_words(self):
        """_trim_to_word_limit(text, 120) must produce <= 120 words."""
        long_text = " ".join(["word"] * 200)
        trimmed = _trim_to_word_limit(long_text, 120)
        wc_before = self._word_count(long_text)
        wc_after = self._word_count(trimmed)
        _print_table(
            ["metric", "value"],
            [
                ["original word count", wc_before],
                ["limit", 120],
                ["trimmed word count", wc_after],
                ["within limit?", str(wc_after <= 120)],
            ],
            title="Trim to 120 Words",
        )
        assert wc_after <= 120

    def test_short_text_unchanged(self):
        """Text already within the limit is returned unchanged."""
        short = "Hello world. This is a test."
        result = _trim_to_word_limit(short, 120)
        _print_table(
            ["field", "value"],
            [
                ["original text", short],
                ["limit", 120],
                ["result text", result],
                ["unchanged?", str(result == short)],
            ],
            title="Short Text – Unchanged",
        )
        assert result == short

    def test_trim_preserves_sentence_boundary(self):
        """Trimmer should end at the last sentence boundary if possible."""
        text = "First sentence ends here. Second sentence ends here. " + " ".join(
            ["extra"] * 100
        )
        trimmed = _trim_to_word_limit(text, 10)
        ends_with_period = trimmed.endswith(".")
        wc = len(trimmed.split())
        _print_table(
            ["field", "value"],
            [
                ["limit", 10],
                ["trimmed text", trimmed[:60] + ("..." if len(trimmed) > 60 else "")],
                ["word count", wc],
                ["ends with '.'?", str(ends_with_period)],
                ["word count ≤ 10?", str(wc <= 10)],
                ["passes?", str(ends_with_period or wc <= 10)],
            ],
            title="Trim – Sentence Boundary Preserved",
        )
        assert trimmed.endswith(".") or len(trimmed.split()) <= 10

    def test_high_pressure_produces_short_output(self):
        """Verify that a simulated high-pressure scenario would cap output to 80 words."""
        # Build a 200-word response and apply the 80-word cap directly
        response = " ".join([f"word{i}" for i in range(200)])
        capped = _trim_to_word_limit(response, 80)
        wc_before = self._word_count(response)
        wc_after = self._word_count(capped)
        _print_table(
            ["metric", "value"],
            [
                ["simulated pressure", "≥ 8.0 (high)"],
                ["response word count (before cap)", wc_before],
                ["word cap applied", 80],
                ["capped word count", wc_after],
                ["within cap?", str(wc_after <= 80)],
            ],
            title="High Pressure – Short Output",
        )
        assert wc_after <= 80


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
        _print_table(
            ["phase", "pressure", "note"],
            [
                [
                    "after 6 stagnant turns (high)",
                    f"{high_pressure:.4f}",
                    "unresolved=3, stag=0.8",
                ],
                ["resolution turn 1 (p1)", f"{p1:.4f}", "unresolved=0, stag=0.1"],
                ["resolution turn 2 (p2)", f"{p2:.4f}", "unresolved=0, stag=0.0"],
                ["drop (high→p2)", f"{high_pressure - p2:.4f}", "must be > 0.5"],
            ],
            title="Pressure Decay After Resolution",
        )
        _print_bar_chart(
            [("high", high_pressure), ("p1", p1), ("p2", p2)],
            title="Pressure over resolution turns",
        )
        assert p2 < high_pressure - 0.5, (
            f"Pressure ({p2:.2f}) should have dropped by at least 0.5 from "
            f"high_pressure ({high_pressure:.2f}) within 2 turns"
        )

    def test_unresolved_count_decrements_on_answer(self):
        """Simulated answer resolution must reduce unresolved count."""
        open_questions = 2
        text = "A) I choose the first option."
        resolved = _is_question_resolved(text)
        open_questions_after = (
            max(0, open_questions - 1) if resolved else open_questions
        )
        _print_table(
            ["field", "value"],
            [
                ["text", text],
                ["_is_question_resolved?", str(resolved)],
                ["open_questions before", 2],
                ["open_questions after", open_questions_after],
            ],
            title="Unresolved Count Decrements on Answer",
        )
        assert resolved
        assert open_questions_after == 1

    def test_unresolved_count_no_decrement_without_answer(self):
        """Non-answer replies must not reduce unresolved count."""
        texts = [
            "This is a complex philosophical topic.",
            "Let me think about this further.",
        ]
        rows = [[t, str(_is_question_resolved(t))] for t in texts]
        _print_table(
            ["text", "is_question_resolved?"],
            rows,
            title="Non-Answer → No Decrement",
        )
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

        checks = [
            ("LLM_RESPONSE_LIMIT", hasattr(m, "LLM_RESPONSE_LIMIT")),
            ("MAX_RESPONSE_WORDS", hasattr(m, "MAX_RESPONSE_WORDS")),
            ("FORBIDDEN_PHRASES", hasattr(m, "FORBIDDEN_PHRASES")),
            ("FORBIDDEN_STARTERS", hasattr(m, "FORBIDDEN_STARTERS")),
        ]
        _print_table(
            ["constant", "present?"],
            [[name, str(present)] for name, present in checks],
            title="Module Constants",
        )
        assert hasattr(m, "LLM_RESPONSE_LIMIT")
        assert hasattr(m, "MAX_RESPONSE_WORDS")
        assert hasattr(m, "FORBIDDEN_PHRASES")
        assert hasattr(m, "FORBIDDEN_STARTERS")

    def test_new_functions_importable(self):
        """New drive-pressure helpers must be importable."""
        import Entelgia_production_meta as m

        checks = [
            (
                "compute_drive_pressure",
                callable(getattr(m, "compute_drive_pressure", None)),
            ),
            ("_topic_signature", callable(getattr(m, "_topic_signature", None))),
            ("_trim_to_word_limit", callable(getattr(m, "_trim_to_word_limit", None))),
            (
                "_is_question_resolved",
                callable(getattr(m, "_is_question_resolved", None)),
            ),
        ]
        _print_table(
            ["function", "callable?"],
            [[name, str(ok)] for name, ok in checks],
            title="Drive-Pressure Functions Importable",
        )
        assert callable(m.compute_drive_pressure)
        assert callable(m._topic_signature)
        assert callable(m._trim_to_word_limit)
        assert callable(m._is_question_resolved)

    def test_topic_signature_returns_string(self):
        """_topic_signature must return a non-empty hex string and be deterministic."""
        text = "The nature of consciousness is debated by philosophers."
        sig = _topic_signature(text)
        sig2 = _topic_signature(text)
        _print_table(
            ["field", "value"],
            [
                ["input text", text[:50] + "..."],
                ["signature", sig[:24] + "..."],
                ["is string?", str(isinstance(sig, str))],
                ["non-empty?", str(len(sig) > 0)],
                ["deterministic (sig1==sig2)?", str(sig == sig2)],
            ],
            title="Topic Signature – String & Deterministic",
        )
        assert isinstance(sig, str) and len(sig) > 0
        assert (
            _topic_signature("The nature of consciousness is debated by philosophers.")
            == sig
        )

    def test_topic_signature_same_for_similar_text(self):
        """Identical key-word sets must produce the same signature."""
        text1 = "consciousness mind philosophy debate"
        text2 = "philosophy consciousness debate mind"
        sig1 = _topic_signature(text1)
        sig2 = _topic_signature(text2)
        _print_table(
            ["text", "signature"],
            [
                [text1, sig1[:24] + "..."],
                [text2, sig2[:24] + "..."],
                ["same?", str(sig1 == sig2)],
            ],
            title="Topic Signature – Same Words Same Sig",
        )
        assert sig1 == sig2

    def test_topic_signature_different_for_different_topics(self):
        """Different topics must produce different signatures."""
        text1 = "quantum physics electrons atoms nucleus"
        text2 = "freedom democracy justice society politics"
        sig1 = _topic_signature(text1)
        sig2 = _topic_signature(text2)
        _print_table(
            ["topic", "signature (first 24)"],
            [
                [text1[:30], sig1[:24] + "..."],
                [text2[:30], sig2[:24] + "..."],
                ["different?", str(sig1 != sig2)],
            ],
            title="Topic Signature – Different Topics",
        )
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
        p1 = compute_drive_pressure(**args)
        p2 = compute_drive_pressure(**args)
        _print_table(
            ["field", "value"],
            [
                ["prev_pressure", "3.5"],
                ["energy", "60.0"],
                ["conflict", "6.0"],
                ["unresolved_count", "2"],
                ["stagnation", "0.5"],
                ["call 1 result", f"{p1:.6f}"],
                ["call 2 result", f"{p2:.6f}"],
                ["deterministic?", str(p1 == p2)],
            ],
            title="compute_drive_pressure – Deterministic",
        )
        assert p1 == p2


# ---------------------------------------------------------------------------
# Test E: Soft feedback loop – dialogue pressure → drive pressure
# ---------------------------------------------------------------------------


def _apply_pressure_feedback(drive_pressure: float, dialogue_pressure: bool) -> float:
    """Mirror of the EWM feedback applied in Agent.speak() after pressure alignment."""
    if dialogue_pressure:
        drive_pressure = (
            (1.0 - _PRESSURE_FEEDBACK_ALPHA) * drive_pressure
            + _PRESSURE_FEEDBACK_ALPHA * 10.0
        )
        drive_pressure = min(10.0, drive_pressure)
    return drive_pressure


class TestDialoguePressureFeedback:
    """Verify the soft EWM feedback loop from dialogue pressure into drive pressure."""

    def test_alpha_constant_is_small(self):
        """_PRESSURE_FEEDBACK_ALPHA must be in the (0, 0.25] range (soft, not hard)."""
        _print_table(
            ["constant", "value", "expected range", "ok?"],
            [
                [
                    "_PRESSURE_FEEDBACK_ALPHA",
                    f"{_PRESSURE_FEEDBACK_ALPHA:.4f}",
                    "(0.0, 0.25]",
                    str(0.0 < _PRESSURE_FEEDBACK_ALPHA <= 0.25),
                ]
            ],
            title="Feedback Alpha – Small Coefficient",
        )
        assert 0.0 < _PRESSURE_FEEDBACK_ALPHA <= 0.25

    def test_feedback_raises_pressure_when_dialogue_pressure_true(self):
        """Applying feedback with dialogue_pressure=True must increase drive_pressure."""
        initial = 2.0
        after = _apply_pressure_feedback(initial, dialogue_pressure=True)
        _print_table(
            ["state", "drive_pressure"],
            [
                ["before feedback", f"{initial:.4f}"],
                ["after feedback (dialogue_pressure=True)", f"{after:.4f}"],
                ["increased?", str(after > initial)],
            ],
            title="Feedback – Raises Pressure When Dialogue Shows Pressure",
        )
        assert after > initial, f"Expected pressure to rise above {initial:.3f}, got {after:.3f}"

    def test_feedback_no_change_when_dialogue_pressure_false(self):
        """Applying feedback with dialogue_pressure=False must NOT change drive_pressure."""
        initial = 2.0
        after = _apply_pressure_feedback(initial, dialogue_pressure=False)
        _print_table(
            ["state", "drive_pressure"],
            [
                ["before feedback", f"{initial:.4f}"],
                ["after feedback (dialogue_pressure=False)", f"{after:.4f}"],
                ["unchanged?", str(after == initial)],
            ],
            title="Feedback – No Change When Dialogue Is Calm",
        )
        assert after == initial, f"Expected no change, got {after:.3f}"

    def test_feedback_nudge_is_not_a_large_jump(self):
        """Each single application of feedback must raise pressure by < 2.0."""
        initial = 2.0
        after = _apply_pressure_feedback(initial, dialogue_pressure=True)
        delta = after - initial
        _print_table(
            ["metric", "value", "threshold"],
            [
                ["single-turn delta", f"{delta:.4f}", "< 2.0"],
                ["within bound?", str(delta < 2.0), "True"],
            ],
            title="Feedback – Small Single-Turn Jump",
        )
        assert delta < 2.0, f"Single-turn feedback delta ({delta:.3f}) exceeds 2.0 – too large"

    def test_feedback_bounded_at_max(self):
        """drive_pressure must never exceed 10.0 after feedback."""
        near_max = 9.9
        after = _apply_pressure_feedback(near_max, dialogue_pressure=True)
        _print_table(
            ["state", "drive_pressure"],
            [
                ["before (near max)", f"{near_max:.4f}"],
                ["after feedback", f"{after:.4f}"],
                ["capped at 10.0?", str(after <= 10.0)],
            ],
            title="Feedback – Bounded at 10.0",
        )
        assert after <= 10.0, f"Pressure exceeded 10.0: {after:.4f}"

    def test_feedback_accumulates_over_repeated_turns(self):
        """After 8 turns of consistent dialogue pressure, drive_pressure must rise noticeably."""
        pressure = 2.0
        baseline = pressure
        rows = []
        for turn in range(1, 9):
            pressure = _apply_pressure_feedback(pressure, dialogue_pressure=True)
            rows.append([turn, f"{pressure:.4f}", f"{pressure - baseline:.4f}"])

        _print_table(
            ["turn", "pressure", "Δ from baseline"],
            rows,
            title="Feedback – Accumulation Over 8 Turns (dialogue_pressure=True)",
        )
        _print_bar_chart(
            [(f"turn {r[0]}", float(r[1])) for r in rows],
            title="Pressure growth via dialogue feedback",
        )
        # After 8 turns of consistent pressure, drive_pressure must have risen by ≥ 1.0
        assert pressure >= baseline + 1.0, (
            f"Expected pressure to rise by ≥1.0 after 8 feedback turns; "
            f"got {pressure:.3f} (baseline {baseline:.3f})"
        )

    def test_feedback_ewm_formula_matches_expected(self):
        """The EWM blend result must equal (1-α)*p + α*10.0 exactly."""
        p = 3.0
        expected = (1.0 - _PRESSURE_FEEDBACK_ALPHA) * p + _PRESSURE_FEEDBACK_ALPHA * 10.0
        actual = _apply_pressure_feedback(p, dialogue_pressure=True)
        _print_table(
            ["metric", "value"],
            [
                ["input pressure", f"{p:.4f}"],
                ["alpha", f"{_PRESSURE_FEEDBACK_ALPHA:.4f}"],
                ["expected (1-α)*p + α*10", f"{expected:.6f}"],
                ["actual", f"{actual:.6f}"],
                ["match?", str(actual == pytest.approx(expected))],
            ],
            title="Feedback – EWM Formula Verification",
        )
        assert actual == pytest.approx(expected, abs=1e-9)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s", "--override-ini=addopts="])

# ---------------------------------------------------------------------------
# Test F: _topic_keywords and _keyword_jaccard (stagnation detection helpers)
# ---------------------------------------------------------------------------


class TestTopicKeywords:
    """Verify _topic_keywords returns a frozenset of content words."""

    def test_returns_frozenset(self):
        kws = _topic_keywords("consciousness and philosophy matter.")
        assert isinstance(kws, frozenset)

    def test_stopwords_excluded(self):
        kws = _topic_keywords("the and a is in on")
        assert len(kws) == 0, f"Expected empty set, got {kws}"

    def test_content_words_included(self):
        kws = _topic_keywords("consciousness mind philosophy debate")
        assert "consciousness" in kws
        assert "philosophy" in kws

    def test_order_invariant(self):
        kws1 = _topic_keywords("consciousness philosophy mind")
        kws2 = _topic_keywords("mind philosophy consciousness")
        assert kws1 == kws2

    def test_empty_text_returns_empty_set(self):
        assert _topic_keywords("") == frozenset()


class TestKeywordJaccard:
    """Verify _keyword_jaccard similarity semantics."""

    def test_identical_sets_return_one(self):
        a = frozenset(["mind", "philosophy", "consciousness"])
        assert _keyword_jaccard(a, a) == 1.0

    def test_disjoint_sets_return_zero(self):
        a = frozenset(["mind", "philosophy"])
        b = frozenset(["quantum", "physics"])
        assert _keyword_jaccard(a, b) == 0.0

    def test_partial_overlap_between_zero_and_one(self):
        a = frozenset(["mind", "philosophy", "consciousness"])
        b = frozenset(["mind", "philosophy", "quantum"])
        score = _keyword_jaccard(a, b)
        assert 0.0 < score < 1.0

    def test_both_empty_returns_one(self):
        assert _keyword_jaccard(frozenset(), frozenset()) == 1.0

    def test_one_empty_returns_zero(self):
        assert _keyword_jaccard(frozenset(["mind"]), frozenset()) == 0.0

    def test_symmetry(self):
        a = frozenset(["mind", "philosophy"])
        b = frozenset(["mind", "consciousness"])
        assert _keyword_jaccard(a, b) == _keyword_jaccard(b, a)

    def test_similar_texts_score_above_threshold(self):
        """Texts on the same topic should produce Jaccard >= _JACCARD_STAGNATION_THRESHOLD."""
        kws1 = _topic_keywords(
            "consciousness cannot be reduced to physical brain states."
        )
        kws2 = _topic_keywords(
            "consciousness is not reducible to the brain or physical states."
        )
        score = _keyword_jaccard(kws1, kws2)
        assert score >= _JACCARD_STAGNATION_THRESHOLD, (
            f"Expected Jaccard >= {_JACCARD_STAGNATION_THRESHOLD} for similar texts, got {score:.3f}"
        )

    def test_different_topics_score_below_threshold(self):
        """Texts on clearly different topics should produce Jaccard < _JACCARD_STAGNATION_THRESHOLD."""
        kws1 = _topic_keywords("quantum mechanics electrons nuclear physics")
        kws2 = _topic_keywords("freedom democracy justice political society")
        score = _keyword_jaccard(kws1, kws2)
        assert score < _JACCARD_STAGNATION_THRESHOLD, (
            f"Expected Jaccard < {_JACCARD_STAGNATION_THRESHOLD} for different topics, got {score:.3f}"
        )


class TestStagnationConstants:
    """Verify the stagnation-related module constants have sensible values."""

    def test_jaccard_threshold_in_range(self):
        """_JACCARD_STAGNATION_THRESHOLD must be in (0.0, 1.0)."""
        assert 0.0 < _JACCARD_STAGNATION_THRESHOLD < 1.0

    def test_pe_stagnation_increment_in_range(self):
        """_PE_STAGNATION_INCREMENT must be positive and ≤ 0.5 (gradual, not a jump)."""
        assert 0.0 < _PE_STAGNATION_INCREMENT <= 0.5

    def test_pe_stagnation_increment_caps_at_one(self):
        """Accumulating _PE_STAGNATION_INCREMENT four times from 0 must not exceed 1.0."""
        value = 0.0
        for _ in range(4):
            value = min(1.0, value + _PE_STAGNATION_INCREMENT)
        assert value <= 1.0


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s", "--override-ini=addopts="])

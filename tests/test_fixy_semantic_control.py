#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Tests for FixySemanticController (entelgia/fixy_semantic_control.py).

Covers:
  Validation
  1.  Concrete example text → compliant for EXAMPLE
  2.  Abstract philosophical text → non-compliant for EXAMPLE
  3.  Real falsifiable condition → compliant for TEST
  4.  Vague "this should be tested" → non-compliant for TEST
  5.  True concession → compliant for CONCESSION
  6.  Fake concession → partial or non-compliant for CONCESSION
  7.  Non-validated move type → default compliant result

  Loop detection
  8.  Same argument rewritten 2–3 ways → is_loop=True
  9.  Clearly new distinction → is_loop=False
  10. No recent texts → is_loop=False

  Heuristics
  11. quick_example_hint — positive signal
  12. quick_example_hint — negative signal
  13. quick_test_hint — positive signal
  14. quick_test_hint — negative signal

  Safe JSON parsing
  15. Malformed JSON in validation → fallback result
  16. Malformed JSON in loop check → fallback result
  17. LLM exception in validation → fallback result
  18. LLM exception in loop detection → fallback result

  apply_validation_to_progress
  19. Full compliance raises score
  20. Partial compliance lowers score
  21. Non-compliance multiplies score by 0.85
  22. Repeated non-compliance caps score at 0.55
  23. validation_not_required_for_move_type leaves score unchanged
  24. no_guidance_active leaves score unchanged

  apply_loop_to_progress
  25. No loop → score unchanged
  26. Low-confidence loop → ×0.75 only
  27. High-confidence loop → ×0.75 and cap at 0.50
  28. Loop result with is_loop=False → no change

  InteractiveFixy integration
  29. record_guidance_compliance — full compliance resets ignored_guidance_count
  30. record_guidance_compliance — non-compliance increments ignored_guidance_count
  31. record_guidance_compliance — partial compliance leaves ignored_guidance_count unchanged
  32. record_guidance_compliance — non-compliance boosts confidence after 2 ignores
  33. record_guidance_compliance — skips when no guidance active
  34. record_guidance_compliance — skips for validation_not_required reason
  35. record_semantic_loop — loop increments semantic_loop_count
  36. record_semantic_loop — non-loop leaves semantic_loop_count unchanged
  37. record_semantic_loop — loop boosts guidance confidence
  38. record_semantic_loop — no crash when guidance is None

  evaluate_reply
  39. No guidance active → neutral validation result
  40. Loop check skipped when no trigger conditions
  41. Loop check runs when stagnation > 0
  42. Loop check runs when repeated_moves=True
  43. Loop check runs when ignored_recently=True
  44. Loop check runs when unresolved_rising=True

  score_progress integration
  45. Semantic loop lowers progress score
  46. Full compliance boosts progress score
  47. Non-compliance lowers progress score
  48. Backward compatibility — validation_result=None leaves score unchanged
  49. Backward compatibility — loop_result=None leaves score unchanged
  50. Score never goes below 0.0 after loop adjustment

  Constants
  51. VALIDATED_MOVE_TYPES content check
  52. LOOP_BREAKING_MOVES content check
"""

import sys
import os
import json

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from entelgia.fixy_semantic_control import (
    ValidationResult,
    LoopCheckResult,
    FixySemanticController,
    VALIDATED_MOVE_TYPES,
    LOOP_BREAKING_MOVES,
    quick_example_hint,
    quick_test_hint,
    apply_validation_to_progress,
    apply_loop_to_progress,
)
from entelgia.fixy_interactive import FixyGuidance, InteractiveFixy
import entelgia.progress_enforcer as pe

# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


class _ReturnLLM:
    """Stub LLM that returns a preset JSON string."""

    def __init__(self, payload: dict):
        self._payload = payload

    def generate(self, model, prompt, **kw):
        return json.dumps(self._payload)


class _RaiseLLM:
    """Stub LLM that always raises on generate()."""

    def generate(self, model, prompt, **kw):
        raise RuntimeError("LLM unavailable")


class _GarbageLLM:
    """Stub LLM that returns unparseable text."""

    def generate(self, model, prompt, **kw):
        return "not json at all!!!"


def _make_fixy():
    return InteractiveFixy(llm=_RaiseLLM(), model="stub")


def _make_guidance(preferred_move="EXAMPLE", confidence=0.8):
    return FixyGuidance(
        goal="test_goal",
        preferred_move=preferred_move,
        confidence=confidence,
        reason="loop_repetition",
    )


# ---------------------------------------------------------------------------
# 1. Concrete example text → compliant for EXAMPLE
# ---------------------------------------------------------------------------


def test_example_compliant():
    llm = _ReturnLLM(
        {"compliant": True, "partial": False, "confidence": 0.9, "reason": "real_case"}
    )
    ctrl = FixySemanticController(llm=llm, model="stub")
    result = ctrl.validate_guidance_compliance(
        "Socrates",
        "Last year, my colleague tried a 30-day meditation challenge and found her anxiety dropped measurably.",
        "EXAMPLE",
    )
    assert result.compliant is True
    assert result.partial is False
    assert result.confidence == pytest.approx(0.9)
    assert result.expected_move == "EXAMPLE"


# ---------------------------------------------------------------------------
# 2. Abstract philosophical text → non-compliant for EXAMPLE
# ---------------------------------------------------------------------------


def test_example_non_compliant():
    llm = _ReturnLLM(
        {
            "compliant": False,
            "partial": False,
            "confidence": 0.85,
            "reason": "only_abstraction",
        }
    )
    ctrl = FixySemanticController(llm=llm, model="stub")
    result = ctrl.validate_guidance_compliance(
        "Athena",
        "The concept of freedom is fundamentally about autonomy and self-determination.",
        "EXAMPLE",
    )
    assert result.compliant is False
    assert result.confidence >= 0.0


# ---------------------------------------------------------------------------
# 3. Real falsifiable condition → compliant for TEST
# ---------------------------------------------------------------------------


def test_test_compliant():
    llm = _ReturnLLM(
        {
            "compliant": True,
            "partial": False,
            "confidence": 0.88,
            "reason": "falsifiable_condition",
        }
    )
    ctrl = FixySemanticController(llm=llm, model="stub")
    result = ctrl.validate_guidance_compliance(
        "Socrates",
        "If the intervention works, we should observe a statistically significant drop in cortisol levels within two weeks.",
        "TEST",
    )
    assert result.compliant is True
    assert result.expected_move == "TEST"


# ---------------------------------------------------------------------------
# 4. Vague "this should be tested" → non-compliant for TEST
# ---------------------------------------------------------------------------


def test_test_non_compliant():
    llm = _ReturnLLM(
        {
            "compliant": False,
            "partial": False,
            "confidence": 0.8,
            "reason": "vague_call_for_evidence",
        }
    )
    ctrl = FixySemanticController(llm=llm, model="stub")
    result = ctrl.validate_guidance_compliance(
        "Athena",
        "This claim really should be tested somehow, don't you think?",
        "TEST",
    )
    assert result.compliant is False


# ---------------------------------------------------------------------------
# 5. True concession → compliant for CONCESSION
# ---------------------------------------------------------------------------


def test_concession_compliant():
    llm = _ReturnLLM(
        {
            "compliant": True,
            "partial": False,
            "confidence": 0.91,
            "reason": "genuine_limitation_acknowledged",
        }
    )
    ctrl = FixySemanticController(llm=llm, model="stub")
    result = ctrl.validate_guidance_compliance(
        "Socrates",
        "I must concede that my argument fails to account for cases where social context overrides individual agency.",
        "CONCESSION",
    )
    assert result.compliant is True
    assert result.expected_move == "CONCESSION"


# ---------------------------------------------------------------------------
# 6. Fake concession → partial or non-compliant for CONCESSION
# ---------------------------------------------------------------------------


def test_concession_fake():
    llm = _ReturnLLM(
        {
            "compliant": False,
            "partial": True,
            "confidence": 0.72,
            "reason": "concession_immediately_cancelled",
        }
    )
    ctrl = FixySemanticController(llm=llm, model="stub")
    result = ctrl.validate_guidance_compliance(
        "Athena",
        "One might say my view has limits, but actually it handles every case perfectly.",
        "CONCESSION",
    )
    # partial or non-compliant both satisfy the spec
    assert result.partial is True or result.compliant is False


# ---------------------------------------------------------------------------
# 7. Non-validated move type → default compliant result
# ---------------------------------------------------------------------------


def test_non_validated_move_type():
    ctrl = FixySemanticController(llm=_RaiseLLM(), model="stub")
    for move in ("NEW_CLAIM", "DIRECT_ATTACK", "NEW_FRAME", "REFRAME"):
        result = ctrl.validate_guidance_compliance("Socrates", "Some text here.", move)
        assert result.compliant is True
        assert result.confidence == pytest.approx(0.5)
        assert result.reason == "validation_not_required_for_move_type"


# ---------------------------------------------------------------------------
# 8. Same argument rewritten 2–3 ways → is_loop=True
# ---------------------------------------------------------------------------


def test_loop_detected():
    llm = _ReturnLLM(
        {
            "is_loop": True,
            "confidence": 0.87,
            "reason": "same_core_argument_rephrased",
        }
    )
    ctrl = FixySemanticController(llm=llm, model="stub")
    recent = [
        "Consciousness depends entirely on the brain's physical states.",
        "All mental events are ultimately reducible to neural activity.",
    ]
    result = ctrl.detect_semantic_loop(
        "Socrates",
        "Every aspect of the mind is just the brain doing its thing.",
        recent,
    )
    assert result.is_loop is True
    assert result.confidence >= 0.5


# ---------------------------------------------------------------------------
# 9. Clearly new distinction → is_loop=False
# ---------------------------------------------------------------------------


def test_loop_not_detected():
    llm = _ReturnLLM(
        {
            "is_loop": False,
            "confidence": 0.83,
            "reason": "introduces_new_framework",
        }
    )
    ctrl = FixySemanticController(llm=llm, model="stub")
    recent = [
        "Consciousness depends entirely on the brain's physical states.",
    ]
    result = ctrl.detect_semantic_loop(
        "Athena",
        "But consider the distinction between access consciousness and phenomenal consciousness — that reframes the entire problem.",
        recent,
    )
    assert result.is_loop is False


# ---------------------------------------------------------------------------
# 10. No recent texts → is_loop=False (no comparison possible)
# ---------------------------------------------------------------------------


def test_loop_no_recent_texts():
    ctrl = FixySemanticController(llm=_RaiseLLM(), model="stub")
    result = ctrl.detect_semantic_loop("Socrates", "Some reply.", [])
    assert result.is_loop is False
    assert result.reason == "no_recent_texts_to_compare"


# ---------------------------------------------------------------------------
# 11-14. Heuristics
# ---------------------------------------------------------------------------


def test_quick_example_hint_positive():
    assert quick_example_hint("For example, when I started running every day...")


def test_quick_example_hint_negative():
    assert not quick_example_hint("Abstract reasoning about the nature of freedom.")


def test_quick_test_hint_positive():
    assert quick_test_hint(
        "If the treatment works, then we would show a measurable effect."
    )


def test_quick_test_hint_negative():
    assert not quick_test_hint("I think this requires more philosophical analysis.")


# ---------------------------------------------------------------------------
# 15. Malformed JSON in validation → fallback result
# ---------------------------------------------------------------------------


def test_validation_malformed_json():
    ctrl = FixySemanticController(llm=_GarbageLLM(), model="stub")
    result = ctrl.validate_guidance_compliance("Socrates", "Some text.", "EXAMPLE")
    assert result.compliant is False
    assert result.partial is True
    assert result.confidence == pytest.approx(0.3)
    assert result.reason == "validator_parse_failed"


# ---------------------------------------------------------------------------
# 16. Malformed JSON in loop check → fallback result
# ---------------------------------------------------------------------------


def test_loop_malformed_json():
    ctrl = FixySemanticController(llm=_GarbageLLM(), model="stub")
    result = ctrl.detect_semantic_loop("Socrates", "Some text.", ["Previous text."])
    assert result.is_loop is False
    assert result.confidence == pytest.approx(0.3)
    assert result.reason == "loop_parse_failed"


# ---------------------------------------------------------------------------
# 17. LLM exception in validation → fallback result
# ---------------------------------------------------------------------------


def test_validation_llm_exception():
    ctrl = FixySemanticController(llm=_RaiseLLM(), model="stub")
    result = ctrl.validate_guidance_compliance("Athena", "Some text.", "EXAMPLE")
    assert result.compliant is False
    assert result.partial is True
    assert result.confidence == pytest.approx(0.3)
    assert result.reason == "validator_parse_failed"


# ---------------------------------------------------------------------------
# 18. LLM exception in loop detection → fallback result
# ---------------------------------------------------------------------------


def test_loop_llm_exception():
    ctrl = FixySemanticController(llm=_RaiseLLM(), model="stub")
    result = ctrl.detect_semantic_loop("Socrates", "Some text.", ["Previous."])
    assert result.is_loop is False
    assert result.confidence == pytest.approx(0.3)
    assert result.reason == "loop_parse_failed"


# ---------------------------------------------------------------------------
# 19-24. apply_validation_to_progress
# ---------------------------------------------------------------------------


def test_apply_validation_full_compliance_raises():
    result = ValidationResult(
        speaker="Socrates",
        expected_move="EXAMPLE",
        compliant=True,
        partial=False,
        confidence=0.8,
        reason="concrete_example",
    )
    base = 0.6
    adjusted = apply_validation_to_progress(base, result, ignored_guidance_count=0)
    assert adjusted > base
    assert adjusted == pytest.approx(base + 0.05 * 0.8, abs=1e-6)


def test_apply_validation_partial_lowers():
    result = ValidationResult(
        speaker="Socrates",
        expected_move="EXAMPLE",
        compliant=True,
        partial=True,
        confidence=0.7,
        reason="abstract_example",
    )
    base = 0.6
    adjusted = apply_validation_to_progress(base, result, 0)
    assert adjusted == pytest.approx(base - 0.03, abs=1e-6)


def test_apply_validation_non_compliance_multiplies():
    result = ValidationResult(
        speaker="Athena",
        expected_move="EXAMPLE",
        compliant=False,
        partial=False,
        confidence=0.9,
        reason="no_example_found",
    )
    base = 0.6
    adjusted = apply_validation_to_progress(base, result, 0)
    assert adjusted == pytest.approx(base * 0.85, abs=1e-6)


def test_apply_validation_repeated_non_compliance_caps():
    result = ValidationResult(
        speaker="Socrates",
        expected_move="EXAMPLE",
        compliant=False,
        partial=False,
        confidence=0.9,
        reason="no_example",
    )
    # Even with a high base score, repeated non-compliance (>=3) caps at 0.55
    adjusted = apply_validation_to_progress(0.9, result, ignored_guidance_count=3)
    assert adjusted <= 0.55


def test_apply_validation_not_required_unchanged():
    result = ValidationResult(
        speaker="Socrates",
        expected_move="NEW_CLAIM",
        compliant=True,
        partial=False,
        confidence=0.5,
        reason="validation_not_required_for_move_type",
    )
    base = 0.7
    assert apply_validation_to_progress(base, result, 0) == pytest.approx(base)


def test_apply_validation_no_guidance_unchanged():
    result = ValidationResult(
        speaker="Socrates",
        expected_move="",
        compliant=True,
        partial=False,
        confidence=0.5,
        reason="no_guidance_active",
    )
    base = 0.7
    assert apply_validation_to_progress(base, result, 0) == pytest.approx(base)


# ---------------------------------------------------------------------------
# 25-28. apply_loop_to_progress
# ---------------------------------------------------------------------------


def test_apply_loop_no_loop():
    result = LoopCheckResult(
        speaker="Socrates", is_loop=False, confidence=0.8, reason="new_argument"
    )
    base = 0.7
    assert apply_loop_to_progress(base, result) == pytest.approx(base)


def test_apply_loop_low_confidence():
    result = LoopCheckResult(
        speaker="Socrates", is_loop=True, confidence=0.5, reason="possible_loop"
    )
    base = 0.8
    adjusted = apply_loop_to_progress(base, result)
    assert adjusted == pytest.approx(base * 0.75, abs=1e-6)
    # Below confidence threshold — no cap at 0.50
    assert adjusted > 0.50


def test_apply_loop_high_confidence():
    result = LoopCheckResult(
        speaker="Socrates", is_loop=True, confidence=0.85, reason="definite_loop"
    )
    base = 0.8
    adjusted = apply_loop_to_progress(base, result)
    # ×0.75 then cap at 0.50
    assert adjusted <= 0.50


def test_apply_loop_false_no_change():
    result = LoopCheckResult(
        speaker="Athena", is_loop=False, confidence=0.9, reason="new_claim"
    )
    base = 0.65
    assert apply_loop_to_progress(base, result) == pytest.approx(base)


# ---------------------------------------------------------------------------
# 29. record_guidance_compliance — full compliance resets ignored_guidance_count
# ---------------------------------------------------------------------------


def test_record_guidance_compliance_full_resets():
    fixy = _make_fixy()
    fixy.fixy_guidance = _make_guidance("EXAMPLE", 0.8)
    fixy.ignored_guidance_count = 3
    result = ValidationResult(
        speaker="Socrates",
        expected_move="EXAMPLE",
        compliant=True,
        partial=False,
        confidence=0.9,
        reason="concrete_example",
    )
    fixy.record_guidance_compliance(result)
    assert fixy.ignored_guidance_count == 0


# ---------------------------------------------------------------------------
# 30. record_guidance_compliance — non-compliance increments
# ---------------------------------------------------------------------------


def test_record_guidance_compliance_non_increments():
    fixy = _make_fixy()
    fixy.fixy_guidance = _make_guidance("EXAMPLE", 0.8)
    fixy.ignored_guidance_count = 0
    result = ValidationResult(
        speaker="Socrates",
        expected_move="EXAMPLE",
        compliant=False,
        partial=False,
        confidence=0.85,
        reason="no_example",
    )
    fixy.record_guidance_compliance(result)
    assert fixy.ignored_guidance_count == 1


# ---------------------------------------------------------------------------
# 31. record_guidance_compliance — partial compliance leaves count unchanged
# ---------------------------------------------------------------------------


def test_record_guidance_compliance_partial_unchanged():
    fixy = _make_fixy()
    fixy.fixy_guidance = _make_guidance("EXAMPLE", 0.8)
    fixy.ignored_guidance_count = 2
    result = ValidationResult(
        speaker="Socrates",
        expected_move="EXAMPLE",
        compliant=True,
        partial=True,
        confidence=0.6,
        reason="abstract_example",
    )
    fixy.record_guidance_compliance(result)
    assert fixy.ignored_guidance_count == 2


# ---------------------------------------------------------------------------
# 32. record_guidance_compliance — non-compliance boosts confidence after 2 ignores
# ---------------------------------------------------------------------------


def test_record_guidance_compliance_boosts_confidence():
    fixy = _make_fixy()
    fixy.fixy_guidance = _make_guidance("EXAMPLE", 0.7)
    fixy.ignored_guidance_count = 2  # already at 2
    result = ValidationResult(
        speaker="Socrates",
        expected_move="EXAMPLE",
        compliant=False,
        partial=False,
        confidence=0.85,
        reason="no_example",
    )
    fixy.record_guidance_compliance(result)
    # ignored_guidance_count is now 3 (>= 2), so confidence should boost
    assert fixy.fixy_guidance.confidence > 0.7


# ---------------------------------------------------------------------------
# 33. record_guidance_compliance — skips when no guidance active
# ---------------------------------------------------------------------------


def test_record_guidance_compliance_no_guidance():
    fixy = _make_fixy()
    fixy.fixy_guidance = None
    fixy.ignored_guidance_count = 1
    result = ValidationResult(
        speaker="Socrates",
        expected_move="EXAMPLE",
        compliant=True,
        partial=False,
        confidence=0.9,
        reason="concrete_example",
    )
    fixy.record_guidance_compliance(result)
    # No change when guidance is None
    assert fixy.ignored_guidance_count == 1


# ---------------------------------------------------------------------------
# 34. record_guidance_compliance — skips for validation_not_required reason
# ---------------------------------------------------------------------------


def test_record_guidance_compliance_skips_not_required():
    fixy = _make_fixy()
    fixy.fixy_guidance = _make_guidance("NEW_CLAIM", 0.8)
    fixy.ignored_guidance_count = 2
    result = ValidationResult(
        speaker="Socrates",
        expected_move="NEW_CLAIM",
        compliant=True,
        partial=False,
        confidence=0.5,
        reason="validation_not_required_for_move_type",
    )
    fixy.record_guidance_compliance(result)
    assert fixy.ignored_guidance_count == 2  # unchanged


# ---------------------------------------------------------------------------
# 35. record_semantic_loop — loop increments semantic_loop_count
# ---------------------------------------------------------------------------


def test_record_semantic_loop_increments():
    fixy = _make_fixy()
    fixy.fixy_guidance = _make_guidance("EXAMPLE", 0.7)
    result = LoopCheckResult(
        speaker="Socrates", is_loop=True, confidence=0.82, reason="same_core_arg"
    )
    fixy.record_semantic_loop(result)
    assert fixy.semantic_loop_count == 1


# ---------------------------------------------------------------------------
# 36. record_semantic_loop — non-loop leaves count unchanged
# ---------------------------------------------------------------------------


def test_record_semantic_loop_no_loop():
    fixy = _make_fixy()
    result = LoopCheckResult(
        speaker="Athena", is_loop=False, confidence=0.9, reason="new_claim"
    )
    fixy.record_semantic_loop(result)
    assert fixy.semantic_loop_count == 0


# ---------------------------------------------------------------------------
# 37. record_semantic_loop — loop boosts guidance confidence
# ---------------------------------------------------------------------------


def test_record_semantic_loop_boosts_confidence():
    fixy = _make_fixy()
    fixy.fixy_guidance = _make_guidance("EXAMPLE", 0.6)
    result = LoopCheckResult(
        speaker="Socrates", is_loop=True, confidence=0.75, reason="loop"
    )
    fixy.record_semantic_loop(result)
    assert fixy.fixy_guidance.confidence > 0.6


# ---------------------------------------------------------------------------
# 38. record_semantic_loop — no crash when guidance is None
# ---------------------------------------------------------------------------


def test_record_semantic_loop_no_guidance():
    fixy = _make_fixy()
    fixy.fixy_guidance = None
    result = LoopCheckResult(
        speaker="Socrates", is_loop=True, confidence=0.75, reason="loop"
    )
    fixy.record_semantic_loop(result)  # must not raise
    assert fixy.semantic_loop_count == 1


# ---------------------------------------------------------------------------
# 39. evaluate_reply — no guidance → neutral validation result
# ---------------------------------------------------------------------------


def test_evaluate_reply_no_guidance():
    ctrl = FixySemanticController(llm=_RaiseLLM(), model="stub")
    val_result, loop_result = ctrl.evaluate_reply(
        "Socrates", "Some reply text.", fixy_guidance=None, recent_texts=[]
    )
    assert val_result.compliant is True
    assert val_result.reason == "no_guidance_active"
    assert loop_result.is_loop is False
    assert loop_result.reason == "loop_check_not_triggered"


# ---------------------------------------------------------------------------
# 40. evaluate_reply — loop check skipped when no trigger conditions
# ---------------------------------------------------------------------------


def test_evaluate_reply_loop_not_triggered():
    guidance = _make_guidance("EXAMPLE", 0.8)
    llm = _ReturnLLM(
        {"compliant": True, "partial": False, "confidence": 0.8, "reason": "ok"}
    )
    ctrl = FixySemanticController(llm=llm, model="stub")
    _, loop_result = ctrl.evaluate_reply(
        "Socrates",
        "For example, when I was a student...",
        fixy_guidance=guidance,
        recent_texts=["Earlier turn."],
        stagnation=0.0,
        repeated_moves=False,
        ignored_recently=False,
        unresolved_rising=False,
    )
    assert loop_result.reason == "loop_check_not_triggered"


# ---------------------------------------------------------------------------
# 41-43. evaluate_reply — loop check runs when trigger conditions are met
# ---------------------------------------------------------------------------


def test_evaluate_reply_loop_triggered_by_stagnation():
    guidance = _make_guidance("EXAMPLE", 0.8)
    llm = _ReturnLLM(
        {
            "compliant": True,
            "partial": False,
            "confidence": 0.8,
            "reason": "ok",
            "is_loop": False,
        }
    )

    # Provide two responses: one for validation, one for loop
    class _DualLLM:
        def __init__(self):
            self._calls = 0

        def generate(self, model, prompt, **kw):
            self._calls += 1
            if self._calls == 1:
                return json.dumps(
                    {
                        "compliant": True,
                        "partial": False,
                        "confidence": 0.8,
                        "reason": "ok",
                    }
                )
            return json.dumps(
                {"is_loop": False, "confidence": 0.7, "reason": "new_arg"}
            )

    ctrl = FixySemanticController(llm=_DualLLM(), model="stub")
    _, loop_result = ctrl.evaluate_reply(
        "Socrates",
        "Some new text.",
        fixy_guidance=guidance,
        recent_texts=["Previous turn."],
        stagnation=0.3,  # trigger
    )
    # Loop check ran — reason will not be "loop_check_not_triggered"
    assert loop_result.reason != "loop_check_not_triggered"


def test_evaluate_reply_loop_triggered_by_repeated_moves():
    class _DualLLM:
        def __init__(self):
            self._calls = 0

        def generate(self, model, prompt, **kw):
            self._calls += 1
            if self._calls == 1:
                return json.dumps(
                    {
                        "compliant": True,
                        "partial": False,
                        "confidence": 0.8,
                        "reason": "ok",
                    }
                )
            return json.dumps({"is_loop": True, "confidence": 0.8, "reason": "loop"})

    guidance = _make_guidance("EXAMPLE", 0.8)
    ctrl = FixySemanticController(llm=_DualLLM(), model="stub")
    _, loop_result = ctrl.evaluate_reply(
        "Athena",
        "Some text.",
        fixy_guidance=guidance,
        recent_texts=["Prev."],
        repeated_moves=True,
    )
    assert loop_result.reason != "loop_check_not_triggered"


def test_evaluate_reply_loop_triggered_by_ignored_recently():
    class _DualLLM:
        def __init__(self):
            self._calls = 0

        def generate(self, model, prompt, **kw):
            self._calls += 1
            if self._calls == 1:
                return json.dumps(
                    {
                        "compliant": True,
                        "partial": False,
                        "confidence": 0.8,
                        "reason": "ok",
                    }
                )
            return json.dumps({"is_loop": False, "confidence": 0.6, "reason": "ok"})

    guidance = _make_guidance("EXAMPLE", 0.8)
    ctrl = FixySemanticController(llm=_DualLLM(), model="stub")
    _, loop_result = ctrl.evaluate_reply(
        "Socrates",
        "Some text.",
        fixy_guidance=guidance,
        recent_texts=["Prev."],
        ignored_recently=True,
    )
    assert loop_result.reason != "loop_check_not_triggered"


def test_evaluate_reply_loop_triggered_by_unresolved_rising():
    class _DualLLM:
        def __init__(self):
            self._calls = 0

        def generate(self, model, prompt, **kw):
            self._calls += 1
            if self._calls == 1:
                return json.dumps(
                    {
                        "compliant": True,
                        "partial": False,
                        "confidence": 0.8,
                        "reason": "ok",
                    }
                )
            return json.dumps({"is_loop": False, "confidence": 0.6, "reason": "ok"})

    guidance = _make_guidance("EXAMPLE", 0.8)
    ctrl = FixySemanticController(llm=_DualLLM(), model="stub")
    _, loop_result = ctrl.evaluate_reply(
        "Athena",
        "Some text.",
        fixy_guidance=guidance,
        recent_texts=["Prev."],
        unresolved_rising=True,
    )
    assert loop_result.reason != "loop_check_not_triggered"


# ---------------------------------------------------------------------------
# 44-49. score_progress integration
# ---------------------------------------------------------------------------


def test_score_progress_semantic_loop_lowers():
    pe.clear_agent_state()
    mem = pe.get_claims_memory("Socrates")
    text = "I argue that consciousness is entirely reducible to physical states."
    history = []
    loop_r = LoopCheckResult(
        speaker="Socrates", is_loop=True, confidence=0.8, reason="loop"
    )
    score_with_loop = pe.score_progress(text, history, mem, loop_result=loop_r)
    score_without = pe.score_progress(text, history, pe.get_claims_memory("Athena"))
    # Score with loop should be lower
    assert score_with_loop <= score_without


def test_score_progress_full_compliance_boosts():
    pe.clear_agent_state()
    mem = pe.get_claims_memory("Socrates")
    text = "I claim freedom is impossible without social structure."
    history = []
    val_r = ValidationResult(
        speaker="Socrates",
        expected_move="EXAMPLE",
        compliant=True,
        partial=False,
        confidence=0.9,
        reason="concrete_case",
    )
    score_with = pe.score_progress(text, history, mem, validation_result=val_r)
    mem2 = pe.get_claims_memory("Athena")
    score_without = pe.score_progress(text, history, mem2)
    assert score_with >= score_without


def test_score_progress_non_compliance_lowers():
    pe.clear_agent_state()
    mem = pe.get_claims_memory("Socrates")
    text = "I claim freedom is impossible without social structure."
    history = []
    val_r = ValidationResult(
        speaker="Socrates",
        expected_move="EXAMPLE",
        compliant=False,
        partial=False,
        confidence=0.9,
        reason="no_example",
    )
    score_with = pe.score_progress(text, history, mem, validation_result=val_r)
    mem2 = pe.get_claims_memory("Athena")
    score_without = pe.score_progress(text, history, mem2)
    assert score_with <= score_without


def test_score_progress_backward_compat_no_validation():
    pe.clear_agent_state()
    mem = pe.get_claims_memory("Socrates")
    text = "Consciousness is not reducible to physical processes alone."
    history = []
    score = pe.score_progress(text, history, mem)
    assert 0.0 <= score <= 1.0


def test_score_progress_backward_compat_no_loop():
    pe.clear_agent_state()
    mem = pe.get_claims_memory("Socrates")
    text = "Consciousness is not reducible to physical processes alone."
    history = []
    score = pe.score_progress(text, history, mem, loop_result=None)
    assert 0.0 <= score <= 1.0


def test_score_progress_never_below_zero_after_loop():
    pe.clear_agent_state()
    mem = pe.get_claims_memory("Socrates")
    # Low-scoring text (filler) with a strong loop
    text = "Great question! Interesting perspective."
    history = [text, text]
    loop_r = LoopCheckResult(
        speaker="Socrates", is_loop=True, confidence=0.95, reason="definite_loop"
    )
    score = pe.score_progress(text, history, mem, loop_result=loop_r)
    assert score >= 0.0


# ---------------------------------------------------------------------------
# VALIDATED_MOVE_TYPES and LOOP_BREAKING_MOVES sanity checks
# ---------------------------------------------------------------------------


def test_validated_move_types_content():
    assert "EXAMPLE" in VALIDATED_MOVE_TYPES
    assert "TEST" in VALIDATED_MOVE_TYPES
    assert "CONCESSION" in VALIDATED_MOVE_TYPES
    # Not in v1 scope
    assert "NEW_CLAIM" not in VALIDATED_MOVE_TYPES


def test_loop_breaking_moves_content():
    for move in ("EXAMPLE", "TEST", "CONCESSION", "NEW_FRAME"):
        assert move in LOOP_BREAKING_MOVES

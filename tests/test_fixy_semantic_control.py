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

  semantic_repeat follows loop result
  53. semantic_repeat=True after loop detected
  54. semantic_repeat=False after no-loop result
  55. semantic_repeat follows latest result (alternating True/False)

  Loop-breaking guidance bias
  56. Guidance preferred_move updated to loop-breaking move when non-loop-breaking
  57. Guidance preferred_move unchanged when already a loop-breaking move
  58. Guidance bias rotates through multiple loop-breaking moves

  False-positive prevention (strict validator policy)
  59. EXAMPLE — abstract philosophical reply → non-compliant
  60. EXAMPLE — metaphor only → non-compliant
  61. EXAMPLE — vague "for example" phrase without real specifics → non-compliant
  62. TEST — general skepticism → non-compliant
  63. TEST — "we need evidence" with no concrete condition → non-compliant
  64. TEST — rhetorical challenge without observable criterion → non-compliant
  65. CONCESSION — fake concession that immediately cancels → non-compliant
  66. CONCESSION — trivial concession that doesn't weaken position → non-compliant
  67. CONCESSION — attack on other side disguised as concession → non-compliant
  68. EXAMPLE positive control — concrete case → compliant
  69. TEST positive control — specific falsifiable condition → compliant
  70. CONCESSION positive control — genuine weakness acknowledged → compliant

  Confidence threshold
  71. Compliant result with confidence >= 0.70 → remains compliant
  72. Compliant result with confidence < 0.70 → becomes non-compliant with partial=True
  73. Non-compliant result with low confidence → unchanged (still non-compliant)
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
    COMPLIANCE_CONFIDENCE_THRESHOLD,
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
    assert adjusted == pytest.approx(base * 0.70, abs=1e-6)
    # Below confidence threshold — no cap at 0.50
    assert adjusted > 0.50


def test_apply_loop_high_confidence():
    result = LoopCheckResult(
        speaker="Socrates", is_loop=True, confidence=0.85, reason="definite_loop"
    )
    base = 0.8
    adjusted = apply_loop_to_progress(base, result)
    # ×0.70 then cap at 0.50
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


# ---------------------------------------------------------------------------
# semantic_repeat follows loop result
# ---------------------------------------------------------------------------


def test_semantic_repeat_true_after_loop():
    """record_semantic_loop sets semantic_repeat=True when is_loop=True."""
    fixy = _make_fixy()
    assert fixy.semantic_repeat is False  # default
    result = LoopCheckResult(
        speaker="Socrates", is_loop=True, confidence=0.8, reason="rephrasing"
    )
    fixy.record_semantic_loop(result)
    assert fixy.semantic_repeat is True


def test_semantic_repeat_false_after_no_loop():
    """record_semantic_loop sets semantic_repeat=False when is_loop=False."""
    fixy = _make_fixy()
    # Prime it to True first
    loop_true = LoopCheckResult(
        speaker="Socrates", is_loop=True, confidence=0.8, reason="rephrasing"
    )
    fixy.record_semantic_loop(loop_true)
    assert fixy.semantic_repeat is True

    loop_false = LoopCheckResult(
        speaker="Socrates", is_loop=False, confidence=0.8, reason="new_argument"
    )
    fixy.record_semantic_loop(loop_false)
    assert fixy.semantic_repeat is False


def test_semantic_repeat_follows_latest_result():
    """semantic_repeat always reflects the most recent LoopCheckResult."""
    fixy = _make_fixy()
    results = [True, False, True, False]
    for is_loop in results:
        r = LoopCheckResult(
            speaker="Athena", is_loop=is_loop, confidence=0.7, reason="check"
        )
        fixy.record_semantic_loop(r)
        assert fixy.semantic_repeat is is_loop


# ---------------------------------------------------------------------------
# Loop-breaking guidance bias
# ---------------------------------------------------------------------------


def test_guidance_biased_toward_loop_breaking_when_non_loop_move():
    """When loop detected and preferred_move is not a loop-breaker, it should be updated."""
    from entelgia.fixy_interactive import _SEMANTIC_LOOP_BIAS_MOVES

    fixy = _make_fixy()
    # NEW_CLAIM is not a loop-breaking move
    fixy.fixy_guidance = _make_guidance(preferred_move="NEW_CLAIM", confidence=0.5)
    result = LoopCheckResult(
        speaker="Socrates", is_loop=True, confidence=0.8, reason="rephrasing"
    )
    fixy.record_semantic_loop(result)
    # The preferred_move should now be a loop-breaking move
    assert fixy.fixy_guidance.preferred_move in _SEMANTIC_LOOP_BIAS_MOVES


def test_guidance_not_biased_when_already_loop_breaking():
    """When preferred_move is already a loop-breaker, it should stay unchanged."""
    fixy = _make_fixy()
    fixy.fixy_guidance = _make_guidance(preferred_move="EXAMPLE", confidence=0.5)
    result = LoopCheckResult(
        speaker="Socrates", is_loop=True, confidence=0.8, reason="rephrasing"
    )
    fixy.record_semantic_loop(result)
    # EXAMPLE is already a loop-breaking move — should remain unchanged
    assert fixy.fixy_guidance.preferred_move == "EXAMPLE"


def test_guidance_bias_rotates_across_multiple_loops():
    """Repeated loop detections cycle through different loop-breaking moves."""
    from entelgia.fixy_interactive import _SEMANTIC_LOOP_BIAS_MOVES

    fixy = _make_fixy()
    seen_moves = []
    for _ in range(len(_SEMANTIC_LOOP_BIAS_MOVES) + 1):
        # Reset guidance to a non-loop-breaking move each iteration
        fixy.fixy_guidance = _make_guidance(preferred_move="NEW_CLAIM", confidence=0.5)
        r = LoopCheckResult(
            speaker="Socrates", is_loop=True, confidence=0.8, reason="rephrasing"
        )
        fixy.record_semantic_loop(r)
        seen_moves.append(fixy.fixy_guidance.preferred_move)
    # Should have used more than one distinct loop-breaking move
    assert len(set(seen_moves)) > 1


# ---------------------------------------------------------------------------
# False-positive prevention — EXAMPLE
# ---------------------------------------------------------------------------


def test_example_false_positive_abstract_philosophical():
    """Abstract philosophical reasoning must not be marked as a concrete example."""
    llm = _ReturnLLM(
        {
            "compliant": False,
            "partial": False,
            "confidence": 0.88,
            "reason": "abstract_reasoning_no_specific_scenario",
        }
    )
    ctrl = FixySemanticController(llm=llm, model="stub")
    result = ctrl.validate_guidance_compliance(
        "Socrates",
        "Freedom is the condition of self-determination. Where there is no autonomy, there is no genuine agency.",
        "EXAMPLE",
    )
    assert result.compliant is False


def test_example_false_positive_metaphor_only():
    """A metaphor without a concrete scenario must not count as an example."""
    llm = _ReturnLLM(
        {
            "compliant": False,
            "partial": False,
            "confidence": 0.82,
            "reason": "metaphor_only_no_real_scenario",
        }
    )
    ctrl = FixySemanticController(llm=llm, model="stub")
    result = ctrl.validate_guidance_compliance(
        "Athena",
        "It is like a river that knows no boundaries — it flows wherever the landscape allows.",
        "EXAMPLE",
    )
    assert result.compliant is False


def test_example_false_positive_vague_phrase():
    """A vague 'for example' phrase without real specifics must not be compliant."""
    llm = _ReturnLLM(
        {
            "compliant": False,
            "partial": True,
            "confidence": 0.76,
            "reason": "example_phrase_without_real_specifics",
        }
    )
    ctrl = FixySemanticController(llm=llm, model="stub")
    result = ctrl.validate_guidance_compliance(
        "Socrates",
        "For example, one can imagine a situation where this principle applies broadly.",
        "EXAMPLE",
    )
    assert result.compliant is False


# ---------------------------------------------------------------------------
# False-positive prevention — TEST
# ---------------------------------------------------------------------------


def test_test_false_positive_general_skepticism():
    """General skepticism without a testable condition must not be compliant."""
    llm = _ReturnLLM(
        {
            "compliant": False,
            "partial": False,
            "confidence": 0.85,
            "reason": "only_rhetorical_doubt_no_observable_condition",
        }
    )
    ctrl = FixySemanticController(llm=llm, model="stub")
    result = ctrl.validate_guidance_compliance(
        "Athena",
        "I remain sceptical. These claims have not been rigorously examined and need scrutiny.",
        "TEST",
    )
    assert result.compliant is False


def test_test_false_positive_vague_need_for_evidence():
    """'We need evidence' without defining a concrete condition must not be compliant."""
    llm = _ReturnLLM(
        {
            "compliant": False,
            "partial": False,
            "confidence": 0.83,
            "reason": "vague_demand_for_proof_no_testable_condition",
        }
    )
    ctrl = FixySemanticController(llm=llm, model="stub")
    result = ctrl.validate_guidance_compliance(
        "Socrates",
        "We need more evidence before accepting this claim. Science demands rigour.",
        "TEST",
    )
    assert result.compliant is False


def test_test_false_positive_rhetorical_challenge():
    """A rhetorical challenge without an observable criterion must not be compliant."""
    llm = _ReturnLLM(
        {
            "compliant": False,
            "partial": False,
            "confidence": 0.81,
            "reason": "rhetorical_challenge_no_falsifiable_criterion",
        }
    )
    ctrl = FixySemanticController(llm=llm, model="stub")
    result = ctrl.validate_guidance_compliance(
        "Athena",
        "Can you even prove this? What would convince you otherwise? I challenge you to try.",
        "TEST",
    )
    assert result.compliant is False


# ---------------------------------------------------------------------------
# False-positive prevention — CONCESSION
# ---------------------------------------------------------------------------


def test_concession_false_positive_fake_self_cancelling():
    """A concession that immediately cancels itself must not be fully compliant."""
    llm = _ReturnLLM(
        {
            "compliant": False,
            "partial": True,
            "confidence": 0.78,
            "reason": "fake_concession_immediately_cancelled",
        }
    )
    ctrl = FixySemanticController(llm=llm, model="stub")
    result = ctrl.validate_guidance_compliance(
        "Socrates",
        "One might argue my position has weaknesses, but in reality it handles every case perfectly.",
        "CONCESSION",
    )
    assert result.compliant is False


def test_concession_false_positive_trivial():
    """Admitting something trivial that does not weaken the speaker's position must not count."""
    llm = _ReturnLLM(
        {
            "compliant": False,
            "partial": False,
            "confidence": 0.80,
            "reason": "trivial_admission_does_not_weaken_position",
        }
    )
    ctrl = FixySemanticController(llm=llm, model="stub")
    result = ctrl.validate_guidance_compliance(
        "Athena",
        "Of course, no argument is perfectly expressed — word choice can always be improved.",
        "CONCESSION",
    )
    assert result.compliant is False


def test_concession_false_positive_attack_disguised():
    """An attack on the other side disguised as a concession must not be compliant."""
    llm = _ReturnLLM(
        {
            "compliant": False,
            "partial": False,
            "confidence": 0.84,
            "reason": "attack_on_other_side_not_own_weakness",
        }
    )
    ctrl = FixySemanticController(llm=llm, model="stub")
    result = ctrl.validate_guidance_compliance(
        "Socrates",
        "I concede that your position is popular — but popular views are often wrong, as history shows.",
        "CONCESSION",
    )
    assert result.compliant is False


# ---------------------------------------------------------------------------
# Positive controls — strict validator still allows genuine compliance
# ---------------------------------------------------------------------------


def test_example_positive_control_concrete_case():
    """A genuinely concrete, specific case must remain compliant."""
    llm = _ReturnLLM(
        {
            "compliant": True,
            "partial": False,
            "confidence": 0.92,
            "reason": "specific_event_identifiable_actors_concrete_outcome",
        }
    )
    ctrl = FixySemanticController(llm=llm, model="stub")
    result = ctrl.validate_guidance_compliance(
        "Athena",
        "In 2008, Iceland's parliament passed emergency legislation within 48 hours to nationalise its three major banks after their simultaneous collapse.",
        "EXAMPLE",
    )
    assert result.compliant is True
    assert result.partial is False


def test_test_positive_control_specific_falsifiable():
    """A genuine falsifiable condition must remain compliant."""
    llm = _ReturnLLM(
        {
            "compliant": True,
            "partial": False,
            "confidence": 0.91,
            "reason": "specific_observable_condition_clearly_stated",
        }
    )
    ctrl = FixySemanticController(llm=llm, model="stub")
    result = ctrl.validate_guidance_compliance(
        "Socrates",
        "If mindfulness training reduces cortisol, we should see a measurable drop in salivary cortisol within four weeks in a randomised controlled trial.",
        "TEST",
    )
    assert result.compliant is True
    assert result.partial is False


def test_concession_positive_control_genuine_weakness():
    """A genuine acknowledgement of a real weakness in one's own position must remain compliant."""
    llm = _ReturnLLM(
        {
            "compliant": True,
            "partial": False,
            "confidence": 0.90,
            "reason": "genuine_limitation_in_own_position_acknowledged",
        }
    )
    ctrl = FixySemanticController(llm=llm, model="stub")
    result = ctrl.validate_guidance_compliance(
        "Athena",
        "I must admit my argument relies heavily on self-reported data, which introduces a serious measurement bias that I have not adequately addressed.",
        "CONCESSION",
    )
    assert result.compliant is True
    assert result.partial is False


# ---------------------------------------------------------------------------
# Confidence threshold
# ---------------------------------------------------------------------------


def test_confidence_threshold_high_remains_compliant():
    """A compliant result with confidence >= COMPLIANCE_CONFIDENCE_THRESHOLD must remain compliant."""
    # Use a value clearly above the threshold
    high_confidence = COMPLIANCE_CONFIDENCE_THRESHOLD + 0.05
    llm = _ReturnLLM(
        {
            "compliant": True,
            "partial": False,
            "confidence": high_confidence,
            "reason": "borderline_but_acceptable",
        }
    )
    ctrl = FixySemanticController(llm=llm, model="stub")
    result = ctrl.validate_guidance_compliance("Socrates", "Some valid example text.", "EXAMPLE")
    assert result.compliant is True
    assert "low_confidence_treated_as_non_compliant" not in result.reason


def test_confidence_threshold_low_demotes_compliant():
    """A compliant result with confidence < COMPLIANCE_CONFIDENCE_THRESHOLD must be demoted.

    The original reason from the LLM should be preserved as a prefix so logs remain
    actionable — the demotion suffix is appended rather than replacing the original.
    """
    # Use a value clearly below the threshold
    low_confidence = COMPLIANCE_CONFIDENCE_THRESHOLD - 0.08
    llm = _ReturnLLM(
        {
            "compliant": True,
            "partial": False,
            "confidence": low_confidence,
            "reason": "abstract_but_possibly_relevant",
        }
    )
    ctrl = FixySemanticController(llm=llm, model="stub")
    result = ctrl.validate_guidance_compliance("Athena", "Some abstract text.", "EXAMPLE")
    assert result.compliant is False
    assert result.partial is True
    # Original reason must be preserved and demotion suffix must be appended
    assert "abstract_but_possibly_relevant" in result.reason
    assert "low_confidence_treated_as_non_compliant" in result.reason
    assert result.confidence == pytest.approx(low_confidence)


def test_confidence_threshold_non_compliant_unchanged():
    """A non-compliant result with low confidence must stay non-compliant (no unintended changes)."""
    low_confidence = COMPLIANCE_CONFIDENCE_THRESHOLD - 0.15
    llm = _ReturnLLM(
        {
            "compliant": False,
            "partial": False,
            "confidence": low_confidence,
            "reason": "no_example_found",
        }
    )
    ctrl = FixySemanticController(llm=llm, model="stub")
    result = ctrl.validate_guidance_compliance("Socrates", "Pure abstraction.", "EXAMPLE")
    assert result.compliant is False
    assert result.partial is False
    assert result.reason == "no_example_found"


# ---------------------------------------------------------------------------
# Prompt content assertions — verify strict-rejection bias text is present
# ---------------------------------------------------------------------------


class _CaptureLLM:
    """Stub LLM that records the most recently received prompt, then returns a preset JSON."""

    def __init__(self, payload: dict):
        self._payload = payload
        self.last_prompt: str = ""

    def generate(self, model, prompt, **kw):
        self.last_prompt = prompt
        return json.dumps(self._payload)


_STRICT_REJECTION_PHRASES = [
    "Be strict.",
    "compliant=false",
    "false positive",
]


def test_example_prompt_contains_strict_rejection_bias():
    """The EXAMPLE validator prompt must contain the strict-rejection bias instructions."""
    llm = _CaptureLLM({"compliant": False, "partial": False, "confidence": 0.85, "reason": "no_example"})
    ctrl = FixySemanticController(llm=llm, model="stub")
    ctrl.validate_guidance_compliance("Socrates", "Some reply.", "EXAMPLE")
    for phrase in _STRICT_REJECTION_PHRASES:
        assert phrase in llm.last_prompt, f"Expected {phrase!r} in EXAMPLE prompt"


def test_example_prompt_contains_disallowed_patterns():
    """The EXAMPLE prompt must list abstract, metaphor, and hypothetical as non-compliant patterns."""
    llm = _CaptureLLM({"compliant": False, "partial": False, "confidence": 0.85, "reason": "no_example"})
    ctrl = FixySemanticController(llm=llm, model="stub")
    ctrl.validate_guidance_compliance("Athena", "Some reply.", "EXAMPLE")
    for phrase in ("abstract", "metaphor", "hypothetical"):
        assert phrase in llm.last_prompt.lower(), f"Expected {phrase!r} in EXAMPLE prompt non-compliant list"


def test_test_prompt_contains_strict_rejection_bias():
    """The TEST validator prompt must contain the strict-rejection bias instructions."""
    llm = _CaptureLLM({"compliant": False, "partial": False, "confidence": 0.85, "reason": "no_test"})
    ctrl = FixySemanticController(llm=llm, model="stub")
    ctrl.validate_guidance_compliance("Socrates", "Some reply.", "TEST")
    for phrase in _STRICT_REJECTION_PHRASES:
        assert phrase in llm.last_prompt, f"Expected {phrase!r} in TEST prompt"


def test_test_prompt_contains_disallowed_patterns():
    """The TEST prompt must list rhetorical doubt, skepticism, and vague demands as non-compliant."""
    llm = _CaptureLLM({"compliant": False, "partial": False, "confidence": 0.85, "reason": "no_test"})
    ctrl = FixySemanticController(llm=llm, model="stub")
    ctrl.validate_guidance_compliance("Athena", "Some reply.", "TEST")
    for phrase in ("rhetorical", "skepticism", "vague"):
        assert phrase in llm.last_prompt.lower(), f"Expected {phrase!r} in TEST prompt non-compliant list"


def test_concession_prompt_contains_strict_rejection_bias():
    """The CONCESSION validator prompt must contain the strict-rejection bias instructions."""
    llm = _CaptureLLM({"compliant": False, "partial": False, "confidence": 0.85, "reason": "no_concession"})
    ctrl = FixySemanticController(llm=llm, model="stub")
    ctrl.validate_guidance_compliance("Socrates", "Some reply.", "CONCESSION")
    for phrase in _STRICT_REJECTION_PHRASES:
        assert phrase in llm.last_prompt, f"Expected {phrase!r} in CONCESSION prompt"


def test_concession_prompt_contains_disallowed_patterns():
    """The CONCESSION prompt must list fake concession, trivial, and attacks as non-compliant."""
    llm = _CaptureLLM({"compliant": False, "partial": False, "confidence": 0.85, "reason": "no_concession"})
    ctrl = FixySemanticController(llm=llm, model="stub")
    ctrl.validate_guidance_compliance("Athena", "Some reply.", "CONCESSION")
    for phrase in ("fake", "trivial", "attacks"):
        assert phrase in llm.last_prompt.lower(), f"Expected {phrase!r} in CONCESSION prompt non-compliant list"

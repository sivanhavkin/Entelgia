#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Fixy Semantic Control Layer for Entelgia.

Provides a unified semantic validation and loop-detection controller attached
to Fixy's guidance system.

Responsibilities
----------------
* Validate whether a Socrates/Athena reply is semantically compliant with the
  move type Fixy requested (e.g. EXAMPLE, TEST, CONCESSION).
* Detect whether a reply repeats the same core argument as the recent turns
  from the same speaker (semantic loop detection).
* Expose results as lightweight dataclasses that callers can use to adjust
  the progress score and update Fixy's internal state.

This layer is *soft*:
- It never rejects, regenerates, blocks, or retries a reply.
- It only detects, scores, and biases.

v1 scope
--------
- Validates only EXAMPLE, TEST, CONCESSION move types.
- Loop detection uses LLM with lightweight heuristic pre-signal.
- Safe JSON fallbacks on all LLM parse failures.
- Does NOT validate Fixy's own output.
- Does NOT use embeddings.
- Does NOT run multiple LLM checks per turn.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from typing import Any, List, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Move types eligible for semantic compliance validation in v1
# ---------------------------------------------------------------------------

#: Only these move types are semantically validated in v1.
VALIDATED_MOVE_TYPES: frozenset = frozenset({"EXAMPLE", "TEST", "CONCESSION"})

#: Move types that break semantic loops (used to bias future Fixy guidance).
LOOP_BREAKING_MOVES: List[str] = [
    "EXAMPLE",
    "TEST",
    "CONCESSION",
    "NEW_FRAME",
]

#: Minimum validator confidence required to grant compliance.
#: Results with confidence below this threshold are demoted to non-compliant
#: (partial=True) to prevent false positives from uncertain LLM judgements.
COMPLIANCE_CONFIDENCE_THRESHOLD: float = 0.70

#: Minimum loop-detection confidence required to treat a semantic loop as a
#: "strong loop".  At this level, :func:`apply_loop_to_progress` caps the
#: score at 0.50, and callers may apply an additional non-compliance penalty.
STRONG_LOOP_CONFIDENCE_THRESHOLD: float = 0.80

# ---------------------------------------------------------------------------
# Result dataclasses
# ---------------------------------------------------------------------------


@dataclass
class ValidationResult:
    """Result of a semantic guidance compliance check.

    Attributes
    ----------
    speaker:
        Name of the agent whose reply was validated (e.g. "Socrates").
    expected_move:
        The move type Fixy requested (e.g. "EXAMPLE").
    compliant:
        True when the reply fully satisfies the expected move requirement.
    partial:
        True when the reply partially satisfies (e.g. an abstract example
        rather than a concrete one).
    confidence:
        Validator's confidence in its own judgement in [0.0, 1.0].
    reason:
        Short human-readable explanation of the judgement.
    """

    speaker: str
    expected_move: str
    compliant: bool
    partial: bool
    confidence: float
    reason: str


@dataclass
class LoopCheckResult:
    """Result of a semantic loop detection check.

    Attributes
    ----------
    speaker:
        Name of the agent whose reply was checked.
    is_loop:
        True when the reply is judged to repeat the same core argument as
        recent turns from the same speaker.
    confidence:
        Detector's confidence in its own judgement in [0.0, 1.0].
    reason:
        Short human-readable explanation of the judgement.
    """

    speaker: str
    is_loop: bool
    confidence: float
    reason: str


# ---------------------------------------------------------------------------
# Lightweight pre-signal heuristics
# ---------------------------------------------------------------------------


def quick_example_hint(text: str) -> bool:
    """Return True when the text contains surface signals of a concrete example.

    This is a pre-signal only — it is never the final authority on compliance.
    """
    lowered = text.lower()
    return any(
        [
            "for example" in lowered,
            "for instance" in lowered,
            "when i" in lowered,
            "once" in lowered,
            "in a situation" in lowered,
        ]
    )


def quick_test_hint(text: str) -> bool:
    """Return True when the text contains surface signals of a falsifiable test.

    This is a pre-signal only — it is never the final authority on compliance.
    """
    lowered = text.lower()
    return bool(
        any(
            [
                ("if" in lowered and "then" in lowered),
                "would count as evidence" in lowered,
                "would prove" in lowered,
                "would show" in lowered,
                "observable" in lowered,
            ]
        )
    )


# ---------------------------------------------------------------------------
# Compliance prompt builders
# ---------------------------------------------------------------------------

_EXAMPLE_PROMPT_TEMPLATE = """\
You are validating whether a reply actually contains a concrete real-world example.

Be strict.
If the reply does not clearly satisfy the requirement, mark compliant=false.
If uncertain, prefer compliant=false rather than a false positive.
Do not reward replies that merely sound relevant.

A valid example MUST include:
- a specific situation, event, or scenario
- identifiable actors, roles, or participants
- a concrete action, decision, or consequence

A reply is NOT compliant if it is:
- abstract reasoning
- metaphor only
- general commentary
- a hypothetical without a concrete scenario
- an example-like phrase without real specifics

Speaker: {speaker}

Reply:
{text}

Return valid JSON only:
{{
  "compliant": true or false,
  "partial": true or false,
  "confidence": 0.0 to 1.0,
  "reason": "short explanation"
}}"""

_TEST_PROMPT_TEMPLATE = """\
You are validating whether a reply contains a real falsifiable or observable test.

Be strict.
If the reply does not clearly satisfy the requirement, mark compliant=false.
If uncertain, prefer compliant=false rather than a false positive.
Do not reward replies that merely sound relevant.

A valid test MUST include:
- a specific observable condition, outcome, or event
- a clear statement of what would count as supporting or weakening the claim

A reply is NOT compliant if it only includes:
- rhetorical doubt
- general skepticism
- abstract discussion of evidence
- vague demands for proof without defining a testable condition

Speaker: {speaker}

Reply:
{text}

Return valid JSON only:
{{
  "compliant": true or false,
  "partial": true or false,
  "confidence": 0.0 to 1.0,
  "reason": "short explanation"
}}"""

_CONCESSION_PROMPT_TEMPLATE = """\
You are validating whether a reply contains a real concession.

Be strict.
If the reply does not clearly satisfy the requirement, mark compliant=false.
If uncertain, prefer compliant=false rather than a false positive.
Do not reward replies that merely sound relevant.

A valid concession MUST include:
- a genuine weakness, limitation, uncertainty, blind spot, or vulnerability
- this weakness must belong to the speaker's own position

A reply is NOT compliant if it:
- attacks the other side only
- uses a fake concession that immediately cancels itself
- admits something trivial without weakening the speaker's position

Speaker: {speaker}

Reply:
{text}

Return valid JSON only:
{{
  "compliant": true or false,
  "partial": true or false,
  "confidence": 0.0 to 1.0,
  "reason": "short explanation"
}}"""

_COMPLIANCE_PROMPTS = {
    "EXAMPLE": _EXAMPLE_PROMPT_TEMPLATE,
    "TEST": _TEST_PROMPT_TEMPLATE,
    "CONCESSION": _CONCESSION_PROMPT_TEMPLATE,
}

_LOOP_PROMPT_TEMPLATE = """\
Determine whether the current reply repeats the same core argument as the recent replies from the same speaker, even if wording differs.

Speaker: {speaker}

Recent replies:
{recent_texts}

Current reply:
{text}

Rules:
- Mark is_loop=true if the current reply is mainly a rephrasing of the same underlying argument.
- Small wording changes, new metaphors, or slightly sharper phrasing do NOT count as a new argument.
- Mark is_loop=false only if the current reply adds a genuinely new distinction, example, test, concession, or framework.

Return valid JSON only:
{{
  "is_loop": true or false,
  "confidence": 0.0 to 1.0,
  "reason": "short explanation"
}}"""


# ---------------------------------------------------------------------------
# Safe JSON parsing helpers
# ---------------------------------------------------------------------------


def _safe_parse_validation(
    raw: str, speaker: str, expected_move: str
) -> ValidationResult:
    """Parse *raw* LLM output into a :class:`ValidationResult`.

    Falls back to a low-confidence partial result on any parse failure.
    """
    try:
        # Strip any markdown code fences
        cleaned = re.sub(r"^```[a-z]*\s*|\s*```$", "", raw.strip(), flags=re.MULTILINE)
        data = json.loads(cleaned)
        return ValidationResult(
            speaker=speaker,
            expected_move=expected_move,
            compliant=bool(data.get("compliant", False)),
            partial=bool(data.get("partial", False)),
            confidence=float(data.get("confidence", 0.5)),
            reason=str(data.get("reason", "unknown")),
        )
    except Exception:
        logger.debug(
            "[FIXY-VALIDATION] parse failed for speaker=%r move=%r — using fallback",
            speaker,
            expected_move,
        )
        return ValidationResult(
            speaker=speaker,
            expected_move=expected_move,
            compliant=False,
            partial=True,
            confidence=0.3,
            reason="validator_parse_failed",
        )


def _safe_parse_loop(raw: str, speaker: str) -> LoopCheckResult:
    """Parse *raw* LLM output into a :class:`LoopCheckResult`.

    Falls back to a low-confidence non-loop result on any parse failure.
    """
    try:
        cleaned = re.sub(r"^```[a-z]*\s*|\s*```$", "", raw.strip(), flags=re.MULTILINE)
        data = json.loads(cleaned)
        return LoopCheckResult(
            speaker=speaker,
            is_loop=bool(data.get("is_loop", False)),
            confidence=float(data.get("confidence", 0.5)),
            reason=str(data.get("reason", "unknown")),
        )
    except Exception:
        logger.debug(
            "[FIXY-LOOP] parse failed for speaker=%r — using fallback",
            speaker,
        )
        return LoopCheckResult(
            speaker=speaker,
            is_loop=False,
            confidence=0.3,
            reason="loop_parse_failed",
        )


# ---------------------------------------------------------------------------
# Main controller
# ---------------------------------------------------------------------------


class FixySemanticController:
    """Semantic compliance validator and loop detector for Fixy guidance.

    Validates whether Socrates/Athena replies honour Fixy's guidance move type
    and detects when a reply repeats the same core argument as recent turns.

    Parameters
    ----------
    llm:
        LLM backend with a ``generate(model, prompt, **kwargs)`` method.
    model:
        Model identifier string passed to *llm*.
    """

    def __init__(self, llm: Any, model: str) -> None:
        self.llm = llm
        self.model = model

    # ------------------------------------------------------------------
    # Guidance compliance validation
    # ------------------------------------------------------------------

    def validate_guidance_compliance(
        self,
        speaker: str,
        text: str,
        expected_move: str,
    ) -> ValidationResult:
        """Check whether *text* satisfies the *expected_move* type.

        Only EXAMPLE, TEST, and CONCESSION are validated in v1.  All other
        move types return a default compliant result.

        Parameters
        ----------
        speaker:
            Agent name (e.g. "Socrates").
        text:
            The reply text to validate.
        expected_move:
            The move type Fixy requested (e.g. "EXAMPLE").

        Returns
        -------
        :class:`ValidationResult`
        """
        if expected_move not in VALIDATED_MOVE_TYPES:
            return ValidationResult(
                speaker=speaker,
                expected_move=expected_move,
                compliant=True,
                partial=False,
                confidence=0.5,
                reason="validation_not_required_for_move_type",
            )

        prompt_template = _COMPLIANCE_PROMPTS[expected_move]
        prompt = prompt_template.format(speaker=speaker, text=text)

        try:
            raw = self.llm.generate(self.model, prompt)
        except Exception as exc:
            logger.debug(
                "[FIXY-VALIDATION] LLM error for speaker=%r move=%r: %s",
                speaker,
                expected_move,
                exc,
            )
            return ValidationResult(
                speaker=speaker,
                expected_move=expected_move,
                compliant=False,
                partial=True,
                confidence=0.3,
                reason="validator_parse_failed",
            )

        result = _safe_parse_validation(raw, speaker, expected_move)

        # Low-confidence compliance is treated as non-compliant to avoid false positives
        if result.compliant and result.confidence < COMPLIANCE_CONFIDENCE_THRESHOLD:
            result.compliant = False
            result.partial = True
            original_reason = result.reason
            if original_reason:
                result.reason = f"{original_reason}; low_confidence_treated_as_non_compliant"
            else:
                result.reason = "low_confidence_treated_as_non_compliant"

        logger.info(
            "[FIXY-VALIDATION] speaker=%s expected=%s compliant=%s partial=%s"
            " confidence=%.2f reason=%s",
            speaker,
            expected_move,
            result.compliant,
            result.partial,
            result.confidence,
            result.reason,
        )
        return result

    # ------------------------------------------------------------------
    # Semantic loop detection
    # ------------------------------------------------------------------

    def detect_semantic_loop(
        self,
        speaker: str,
        text: str,
        recent_texts: List[str],
    ) -> LoopCheckResult:
        """Check whether *text* repeats the same core argument as *recent_texts*.

        Only compares against the last 2–3 turns from the same speaker.

        Parameters
        ----------
        speaker:
            Agent name.
        text:
            The current reply text.
        recent_texts:
            Recent turns from the same speaker (most recent last).  Should be
            2–3 entries for a meaningful comparison.

        Returns
        -------
        :class:`LoopCheckResult`
        """
        if not recent_texts:
            return LoopCheckResult(
                speaker=speaker,
                is_loop=False,
                confidence=0.5,
                reason="no_recent_texts_to_compare",
            )

        # Truncate to last 3 turns for comparison
        compare_texts = recent_texts[-3:]
        formatted = "\n---\n".join(compare_texts)

        prompt = _LOOP_PROMPT_TEMPLATE.format(
            speaker=speaker,
            recent_texts=formatted,
            text=text,
        )

        try:
            raw = self.llm.generate(self.model, prompt)
        except Exception as exc:
            logger.debug(
                "[FIXY-LOOP] LLM error for speaker=%r: %s",
                speaker,
                exc,
            )
            return LoopCheckResult(
                speaker=speaker,
                is_loop=False,
                confidence=0.3,
                reason="loop_parse_failed",
            )

        result = _safe_parse_loop(raw, speaker)

        logger.info(
            "[FIXY-LOOP] speaker=%s is_loop=%s confidence=%.2f reason=%s",
            speaker,
            result.is_loop,
            result.confidence,
            result.reason,
        )
        return result

    # ------------------------------------------------------------------
    # Combined evaluation
    # ------------------------------------------------------------------

    def evaluate_reply(
        self,
        speaker: str,
        text: str,
        fixy_guidance: Optional[Any],
        recent_texts: List[str],
        *,
        stagnation: float = 0.0,
        repeated_moves: bool = False,
        ignored_recently: bool = False,
        unresolved_rising: bool = False,
    ) -> tuple:
        """Evaluate *text* against Fixy guidance and check for semantic looping.

        Runs guidance compliance validation (when guidance is active and the
        expected move is in :data:`VALIDATED_MOVE_TYPES`) and optionally runs
        loop detection when any of the trigger conditions are true.

        Parameters
        ----------
        speaker:
            Agent name ("Socrates" or "Athena").
        text:
            The reply text to evaluate.
        fixy_guidance:
            Active :class:`~entelgia.fixy_interactive.FixyGuidance` or ``None``.
        recent_texts:
            Recent turns from the same speaker (most recent last).
        stagnation:
            Current stagnation score; loop detection triggers when > 0.0.
        repeated_moves:
            True when move repetition has been detected.
        ignored_recently:
            True when Fixy guidance was ignored in recent turns.
        unresolved_rising:
            True when the count of unresolved claims is growing.

        Returns
        -------
        tuple of (:class:`ValidationResult`, :class:`LoopCheckResult`)
        """
        # --- Guidance compliance validation ---
        if fixy_guidance is not None:
            expected_move = getattr(fixy_guidance, "preferred_move", "")
            validation_result = self.validate_guidance_compliance(
                speaker, text, expected_move
            )
        else:
            # No guidance active — return a neutral default
            validation_result = ValidationResult(
                speaker=speaker,
                expected_move="",
                compliant=True,
                partial=False,
                confidence=0.5,
                reason="no_guidance_active",
            )

        # --- Semantic loop detection (gated by trigger conditions) ---
        should_check_loop = (
            stagnation > 0.0 or repeated_moves or ignored_recently or unresolved_rising
        )

        if should_check_loop and recent_texts:
            loop_result = self.detect_semantic_loop(speaker, text, recent_texts)
        else:
            loop_result = LoopCheckResult(
                speaker=speaker,
                is_loop=False,
                confidence=0.5,
                reason="loop_check_not_triggered",
            )

        return validation_result, loop_result


# ---------------------------------------------------------------------------
# Progress score adjustments (pure functions — no side effects)
# ---------------------------------------------------------------------------


def apply_validation_to_progress(
    progress_score: float,
    validation_result: ValidationResult,
    ignored_guidance_count: int = 0,
) -> float:
    """Adjust *progress_score* based on guidance compliance.

    This supplements (not replaces) the move-mismatch penalty already applied
    by :func:`~entelgia.progress_enforcer.score_progress`.

    Rules (section 12.1 of spec):

    * Full compliance  → +0.05 × confidence
    * Partial          → −0.03
    * Non-compliance   → ×0.85
    * Repeated non-compliance (ignored_guidance_count >= 3) → cap at 0.55

    Parameters
    ----------
    progress_score:
        Base progress score to adjust.
    validation_result:
        Result from :meth:`FixySemanticController.validate_guidance_compliance`.
    ignored_guidance_count:
        Current ignored-guidance streak from :class:`InteractiveFixy`.

    Returns
    -------
    float
        Adjusted progress score clamped to [0.0, 1.0].
    """
    # Skip adjustment when validation was not required / no guidance active
    if validation_result.reason in (
        "validation_not_required_for_move_type",
        "no_guidance_active",
    ):
        return progress_score

    if validation_result.compliant and not validation_result.partial:
        # Full compliance reward
        progress_score += 0.05 * validation_result.confidence
    elif validation_result.partial:
        # Partial compliance penalty
        progress_score -= 0.03
    else:
        # Non-compliance penalty
        progress_score *= 0.85

    # Repeated non-compliance cap
    if ignored_guidance_count >= 3:
        progress_score = min(progress_score, 0.55)

    return float(max(0.0, min(1.0, progress_score)))


def apply_loop_to_progress(
    progress_score: float,
    loop_result: LoopCheckResult,
) -> float:
    """Adjust *progress_score* based on semantic loop detection.

    Rules (section 12.3 of spec):

    * Semantic loop detected → ×0.70
    * Loop with confidence >= 0.80 → also cap at 0.50

    Parameters
    ----------
    progress_score:
        Current progress score to adjust.
    loop_result:
        Result from :meth:`FixySemanticController.detect_semantic_loop`.

    Returns
    -------
    float
        Adjusted progress score clamped to [0.0, 1.0].
    """
    if loop_result.is_loop:
        progress_score *= 0.70
        if loop_result.confidence >= STRONG_LOOP_CONFIDENCE_THRESHOLD:
            progress_score = min(progress_score, 0.50)

    return float(max(0.0, min(1.0, progress_score)))

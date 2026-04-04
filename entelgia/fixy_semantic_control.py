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
from typing import TYPE_CHECKING, Any, List, Optional

if TYPE_CHECKING:  # pragma: no cover
    from entelgia.integration_memory_store import IntegrationMemoryStore

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

#: Valid values for :attr:`LoopCheckResult.reasoning_delta`.
_VALID_REASONING_DELTAS: frozenset = frozenset({"none", "weak", "moderate", "strong"})

#: Valid values for :attr:`LoopCheckResult.new_move_type`.
_VALID_NEW_MOVE_TYPES: frozenset = frozenset(
    {
        "none",
        "example_only",
        "new_distinction",
        "new_variable",
        "reframe",
        "resolution_attempt",
        "counterexample",
    }
)

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
    reasoning_delta:
        Degree of new reasoning introduced, as returned by the LLM judge:
        ``"none"`` — no new reasoning at all;
        ``"weak"`` — cosmetic change only (e.g. a single illustrative example);
        ``"moderate"`` — partial new reasoning but same core structure;
        ``"strong"`` — genuine new reasoning move.
        ``None`` means the field was not evaluated (e.g. no recent texts, parse
        failure, or check not triggered) and callers must not treat it as a
        loop signal.
    new_move_type:
        Classification of the new move (if any), as returned by the LLM judge:
        ``"none"`` — nothing new;
        ``"example_only"`` — concrete example that only illustrates the prior claim;
        ``"new_distinction"`` — introduces a new conceptual distinction;
        ``"new_variable"`` — introduces a new causal variable;
        ``"reframe"`` — reframes the problem at a different level;
        ``"resolution_attempt"`` — attempts to resolve a prior contradiction;
        ``"counterexample"`` — tests the prior claim with a counterexample.
        ``None`` means not evaluated.
    """

    speaker: str
    is_loop: bool
    confidence: float
    reason: str
    reasoning_delta: Optional[str] = None
    new_move_type: Optional[str] = None


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
You are a strict reasoning judge. Evaluate whether the current reply introduces a genuinely new reasoning move, or merely restates and decorates the previous argument.

Speaker: {speaker}

Recent replies:
{recent_texts}

Current reply:
{text}

Step 1 — Semantic check:
- Does the current reply restate the same core claim as the recent replies?
- Does it preserve the same causal structure, even with different wording?

Step 2 — Reasoning delta check:
- Does the current reply introduce a new causal variable not present before?
- Does it reframe the problem (shift level: principle → test case, or test case → principle)?
- Does it produce a counterexample that challenges the prior claim?
- Does it attempt to resolve a prior contradiction?
- Does it introduce a new conceptual distinction?
- OR: does it only add a concrete example that illustrates the same prior argument?

Classification rules:
- Classify is_loop=true when: same core claim is restated AND same reasoning structure is preserved AND no new distinction, variable, reframe, counterexample, or resolution is introduced.
- Classify is_loop=false ONLY when: a new causal variable, a reframe, a counterexample, a contradiction resolution, or a meaningful level shift is present.
- A concrete example alone is NOT sufficient. If the example only illustrates the previous claim, set is_loop=true, reasoning_delta="weak", new_move_type="example_only".
- Do NOT reward surface novelty, stylistic variation, or sharper phrasing.

For reasoning_delta, choose one of: "none" | "weak" | "moderate" | "strong"
  none: nothing new at all
  weak: cosmetic change or example-only illustration of the same argument
  moderate: partial new reasoning but the same core structure persists
  strong: genuine new reasoning move (new variable, reframe, counterexample, resolution, new distinction)

For new_move_type, choose one of: "none" | "example_only" | "new_distinction" | "new_variable" | "reframe" | "resolution_attempt" | "counterexample"

Return valid JSON only:
{{
  "is_loop": true or false,
  "confidence": 0.0 to 1.0,
  "reason": "short explanation",
  "reasoning_delta": "none" | "weak" | "moderate" | "strong",
  "new_move_type": "none" | "example_only" | "new_distinction" | "new_variable" | "reframe" | "resolution_attempt" | "counterexample"
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

    On any parse failure, falls back to a low-confidence non-loop result with
    ``reasoning_delta=None`` (meaning *not evaluated*).  The fail-safe
    conservatively leaves ``is_loop=False`` so uncertain LLM output never
    triggers a false-positive loop intervention.
    """
    try:
        cleaned = re.sub(r"^```[a-z]*\s*|\s*```$", "", raw.strip(), flags=re.MULTILINE)
        data = json.loads(cleaned)
        delta_value = data.get("reasoning_delta")
        if delta_value is None:
            reasoning_delta = None
        else:
            raw_delta = str(delta_value).lower()
            reasoning_delta = raw_delta if raw_delta in _VALID_REASONING_DELTAS else "none"

        move_value = data.get("new_move_type")
        if move_value is None:
            new_move_type = None
        else:
            raw_move = str(move_value).lower()
            new_move_type = raw_move if raw_move in _VALID_NEW_MOVE_TYPES else "none"

        return LoopCheckResult(
            speaker=speaker,
            is_loop=bool(data.get("is_loop", False)),
            confidence=float(data.get("confidence", 0.5)),
            reason=str(data.get("reason", "unknown")),
            reasoning_delta=reasoning_delta,
            new_move_type=new_move_type,
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
            reasoning_delta=None,
            new_move_type=None,
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

    Memory integration
    ------------------
    An optional :class:`~entelgia.integration_memory_store.IntegrationMemoryStore`
    can be attached via :meth:`attach_memory_store`.  Once wired, every
    :class:`ValidationResult` and :class:`LoopCheckResult` produced by this
    controller is automatically persisted to the store so that
    :class:`~entelgia.integration_core.IntegrationCore` (or any other consumer)
    can retrieve historical semantic-validation context for a given agent.

    Logging tags
    ------------
    [FIXY-VALIDATION]          — guidance compliance check result
    [FIXY-LOOP]                — semantic loop detection result
    [FIXY-MEMORY-RECORD]       — entry written to attached memory store
    """

    def __init__(self, llm: Any, model: str) -> None:
        self.llm = llm
        self.model = model
        # Optional JSON-backed memory store (wired via attach_memory_store)
        self._memory_store: Optional[IntegrationMemoryStore] = None

    # ------------------------------------------------------------------
    # Memory store integration
    # ------------------------------------------------------------------

    def attach_memory_store(self, store: "Optional[IntegrationMemoryStore]") -> None:
        """Wire an :class:`~entelgia.integration_memory_store.IntegrationMemoryStore`
        so that validation and loop results are automatically persisted.

        Parameters
        ----------
        store:
            An initialised ``IntegrationMemoryStore`` instance.  Pass ``None``
            to detach an existing store.
        """
        self._memory_store = store
        logger.debug(
            "[FIXY-MEMORY] memory store %s",
            "attached" if store is not None else "detached",
        )

    def _record_validation(self, result: ValidationResult) -> None:
        """Persist *result* to the memory store (no-op when no store attached)."""
        if self._memory_store is None:
            return
        entry = {
            "agent": result.speaker,
            "entry_type": "fixy_validation",
            "active_mode": "VALIDATION",
            "decision_reason": result.reason,
            "priority_level": 0,
            "regenerate": False,
            "suppress_personality": False,
            "enforce_fixy": False,
            "stagnation": 0.0,
            "loop_count": 0,
            "unresolved": 0,
            "fatigue": 0.0,
            "energy": 100.0,
            "expected_move": result.expected_move,
            "compliant": result.compliant,
            "partial": result.partial,
            "confidence": result.confidence,
            "tags": ["fixy_validation", result.expected_move.lower()],
        }
        self._memory_store.store_entry(entry)
        logger.debug(
            "[FIXY-MEMORY-RECORD] type=validation agent=%s move=%s compliant=%s",
            result.speaker,
            result.expected_move,
            result.compliant,
        )

    def _record_loop(self, result: LoopCheckResult) -> None:
        """Persist *result* to the memory store (no-op when no store attached)."""
        if self._memory_store is None:
            return
        tags = ["semantic_loop"]
        if result.is_loop:
            tags.append("loop_detected")
        if result.reasoning_delta in ("none", "weak"):
            tags.append("weak_reasoning")
        entry = {
            "agent": result.speaker,
            "entry_type": "loop_check",
            "active_mode": "LOOP_CHECK",
            "decision_reason": result.reason,
            "priority_level": 0,
            "regenerate": False,
            "suppress_personality": False,
            "enforce_fixy": False,
            "stagnation": 0.0,
            "loop_count": 1 if result.is_loop else 0,
            "unresolved": 0,
            "fatigue": 0.0,
            "energy": 100.0,
            "is_loop": result.is_loop,
            "reasoning_delta": result.reasoning_delta,
            "new_move_type": result.new_move_type,
            "confidence": result.confidence,
            "tags": tags,
        }
        self._memory_store.store_entry(entry)
        logger.debug(
            "[FIXY-MEMORY-RECORD] type=loop_check agent=%s is_loop=%s "
            "reasoning_delta=%s",
            result.speaker,
            result.is_loop,
            result.reasoning_delta,
        )

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
                result.reason = (
                    f"{original_reason}; low_confidence_treated_as_non_compliant"
                )
            else:
                result.reason = "low_confidence_treated_as_non_compliant"

        logger.debug(
            "[FIXY-VALIDATION] speaker=%s expected=%s compliant=%s partial=%s"
            " confidence=%.2f reason=%s",
            speaker,
            expected_move,
            result.compliant,
            result.partial,
            result.confidence,
            result.reason,
        )
        self._record_validation(result)
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

        logger.debug(
            "[FIXY-LOOP] speaker=%s is_loop=%s confidence=%.2f"
            " reasoning_delta=%s new_move_type=%s reason=%s",
            speaker,
            result.is_loop,
            result.confidence,
            result.reasoning_delta,
            result.new_move_type,
            result.reason,
        )
        self._record_loop(result)
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
    * Loop with reasoning_delta ``"none"`` or ``"weak"`` → additionally cap at 0.40,
      because a concrete-example-only or zero-delta response warrants stronger
      suppression than a borderline loop.

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
        if getattr(loop_result, "reasoning_delta", None) in ("none", "weak"):
            progress_score = min(progress_score, 0.40)

    return float(max(0.0, min(1.0, progress_score)))

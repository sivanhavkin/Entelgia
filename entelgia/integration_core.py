#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
IntegrationCore (Executive Cortex) for Entelgia.

An active decision-making layer that sits above the dialogue agents and above
Fixy.  It reads signals from the current turn, integrates them through a
priority-ordered rule engine, and produces a :class:`ControlDecision` that
the main loop can use to regulate the next generation step.

This is NOT a passive logger.  It can suppress personality, enforce Fixy
authority, force concrete/resolution/attack modes, and flag responses for
regeneration.

Public API
----------
IntegrationCore.evaluate_turn(agent_name, state_dict) -> ControlDecision
IntegrationCore.build_prompt_overlay(decision)        -> str
IntegrationCore.should_regenerate(decision)           -> bool

Data classes
------------
IntegrationState  — normalised snapshot of one turn's signals
ControlDecision   — the cortex's output for the next generation step

Integration modes
-----------------
NORMAL
CONCRETE_OVERRIDE
RESOLUTION_OVERRIDE
ATTACK_OVERRIDE
LOW_COMPLEXITY
PERSONALITY_SUPPRESSION
FIXY_AUTHORITY_OVERRIDE

Priority order (highest → lowest)
----------------------------------
1. Loop / semantic repetition
2. Stagnation
3. Unresolved overload
4. Fatigue degradation
5. Pressure misalignment
6. Personality style preservation (default)

Future-ready hook
-----------------
A later ``SupervisorNet`` can score :class:`IntegrationState` before the
symbolic rule engine runs.  The hook is a no-op stub right now:
``IntegrationCore._supervisor_score(state) -> Optional[float]``

Logging tags
------------
[INTEGRATION-STATE]   — normalised input signals
[INTEGRATION-DECISION] — final ControlDecision
[INTEGRATION-MODE]    — active IntegrationMode
[INTEGRATION-OVERLAY] — generated prompt overlay text
[INTEGRATION-REGEN]   — regeneration policy triggered
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Thresholds (module-level constants for easy tuning)
# ---------------------------------------------------------------------------

_LOOP_COUNT_TRIGGER: int = 1
_STAGNATION_SUPPRESS_THRESHOLD: float = 0.25
_UNRESOLVED_RESOLUTION_TRIGGER: int = 3
_PROGRESS_RESOLUTION_TRIGGER: float = 0.5
_FATIGUE_LOW_COMPLEXITY_THRESHOLD: float = 0.6
_PRIORITY_LOOP: int = 10
_PRIORITY_STAGNATION: int = 8
_PRIORITY_UNRESOLVED: int = 6
_PRIORITY_FATIGUE: int = 4
_PRIORITY_PRESSURE: int = 2
_PRIORITY_DEFAULT: int = 0


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class IntegrationMode(str, Enum):
    """Active regulation mode selected by :class:`IntegrationCore`."""

    NORMAL = "NORMAL"
    CONCRETE_OVERRIDE = "CONCRETE_OVERRIDE"
    RESOLUTION_OVERRIDE = "RESOLUTION_OVERRIDE"
    ATTACK_OVERRIDE = "ATTACK_OVERRIDE"
    LOW_COMPLEXITY = "LOW_COMPLEXITY"
    PERSONALITY_SUPPRESSION = "PERSONALITY_SUPPRESSION"
    FIXY_AUTHORITY_OVERRIDE = "FIXY_AUTHORITY_OVERRIDE"


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class IntegrationState:
    """Normalised snapshot of signals available at the end of one turn.

    All fields map directly to signals already computed elsewhere in the
    Entelgia pipeline.  :class:`IntegrationCore` reads this struct; it does
    not write to it.

    Attributes
    ----------
    agent_name:
        Name of the agent whose response is being evaluated.
    semantic_repeat:
        True when the latest response is semantically too similar to
        recent dialogue history (see ``response_evaluator.is_semantic_repeat``).
    structural_repeat:
        True when sentence-level structural templates are repeated
        (see ``circularity_guard``).
    loop_count:
        Number of consecutive loop detections recorded by the loop guard.
    progress_after:
        Argumentative progress score of the last response (0.0–1.0).
    unresolved:
        Count of unresolved tensions currently tracked.
    pressure:
        Current DrivePressure meta-signal (0.0–10.0 scale).
    fatigue:
        Fatigue score (0.0–1.0) computed from agent energy.
    stagnation:
        Stagnation signal (0.0–1.0) as reported by the progress enforcer.
    linguistic_score:
        Linguistic quality score of the last response (0.0–1.0).
    dialogue_score:
        Dialogue movement score of the last response (0.0–1.0).
    alignment:
        Pressure-alignment label, e.g. ``"aligned"``, ``"weak_alignment"``.
    move_type:
        Argumentative move type of the last response, e.g. ``"NEW_CLAIM"``.
    compliance:
        True when the agent genuinely complied with Fixy's guidance (not
        just superficially).
    is_loop:
        True when the loop guard raised a hard loop flag this turn.
    abstraction_detected:
        True when the response was identified as excessively abstract with
        no concrete grounding.
    energy:
        Agent energy level (0.0–100.0).
    status:
        Agent status label, e.g. ``"active"``, ``"fatigued"``, ``"dreaming"``.
    """

    agent_name: str
    semantic_repeat: bool = False
    structural_repeat: bool = False
    loop_count: int = 0
    progress_after: float = 1.0
    unresolved: int = 0
    pressure: float = 0.0
    fatigue: float = 0.0
    stagnation: float = 0.0
    linguistic_score: float = 1.0
    dialogue_score: float = 1.0
    alignment: str = "aligned"
    move_type: str = "NEW_CLAIM"
    compliance: bool = True
    is_loop: bool = False
    abstraction_detected: bool = False
    energy: float = 100.0
    status: str = "active"


@dataclass
class ControlDecision:
    """Output produced by :class:`IntegrationCore` for the next generation step.

    Attributes
    ----------
    allow_response:
        When False the caller should block response emission entirely.
    regenerate:
        When True the caller must discard the current response draft and
        regenerate before proceeding.
    suppress_personality:
        When True the caller must strip or override the agent's default
        personality attractor in the next prompt.
    enforce_fixy:
        When True Fixy's directives have authority over stylistic preferences.
    force_concrete_mode:
        Next response must include at least one concrete, real-world example.
    force_resolution_mode:
        Next response must directly resolve at least one unresolved tension.
    force_attack_mode:
        Next response must structurally challenge the other side's reasoning
        (not only adjust tone).
    low_complexity_mode:
        Next response must use simplified language and shorter sentences.
    prompt_overlay:
        Short imperative text block to be injected verbatim into the next
        LLM prompt.
    decision_reason:
        Human-readable explanation of why this decision was produced.
    priority_level:
        Numeric priority of the triggered rule (higher = more critical).
    active_mode:
        The :class:`IntegrationMode` that was activated.
    """

    allow_response: bool = True
    regenerate: bool = False
    suppress_personality: bool = False
    enforce_fixy: bool = False
    force_concrete_mode: bool = False
    force_resolution_mode: bool = False
    force_attack_mode: bool = False
    low_complexity_mode: bool = False
    prompt_overlay: str = ""
    decision_reason: str = "No override required."
    priority_level: int = _PRIORITY_DEFAULT
    active_mode: IntegrationMode = IntegrationMode.NORMAL


# ---------------------------------------------------------------------------
# Overlay text templates
# ---------------------------------------------------------------------------

_OVERLAY_LOOP: str = (
    "Loop detected. Abstract repetition is forbidden in the next response. "
    "You must introduce a genuinely new reasoning structure."
)
_OVERLAY_PERSONALITY_SUPPRESSION: str = (
    "Default personality style is temporarily suppressed. "
    "Do not fall back on your typical rhetorical patterns."
)
_OVERLAY_RESOLUTION: str = (
    "You must directly resolve one unresolved tension from the previous turn. "
    "Do not defer, qualify, or restate — resolve."
)
_OVERLAY_CONCRETE: str = (
    "You must provide one concrete real-world example. "
    "Abstract reasoning alone is not acceptable in this response."
)
_OVERLAY_FATIGUE: str = (
    "Keep the response short and direct. "
    "Low-complexity mode is active — required: plain language, short sentences, one main point."
)
_OVERLAY_FIXY: str = (
    "Fixy authority has priority over stylistic consistency. "
    "Override your default attractor and follow Fixy's directive exactly."
)
_OVERLAY_ATTACK: str = (
    "You must directly challenge the structural assumption in the opposing argument. "
    "Tone adjustment alone is not sufficient — override the reasoning structure."
)


# ---------------------------------------------------------------------------
# IntegrationCore
# ---------------------------------------------------------------------------


class IntegrationCore:
    """Executive control cortex for Entelgia.

    Reads an :class:`IntegrationState` and applies a priority-ordered rule
    engine to produce a :class:`ControlDecision`.

    The class is intentionally decoupled from specific agents, memory modules,
    or LLM backends.  It operates purely on the normalised signal struct.

    Usage
    -----
    ::

        core = IntegrationCore()
        state = IntegrationState(
            agent_name="Socrates",
            semantic_repeat=True,
            loop_count=2,
            stagnation=0.3,
        )
        decision = core.evaluate_turn("Socrates", state)
        if core.should_regenerate(decision):
            # discard draft, regenerate
            ...
        overlay = core.build_prompt_overlay(decision)
        # inject overlay into next LLM prompt

    Notes
    -----
    Rule priority order:
    1. Loop / semantic repetition         (priority 10)
    2. Stagnation                         (priority 8)
    3. Unresolved overload                (priority 6)
    4. Fatigue degradation                (priority 4)
    5. Pressure misalignment              (priority 2)
    6. Default (no override)              (priority 0)

    The first rule that fires wins.  Rules are evaluated in descending
    priority order and only the highest-priority match is applied.

    TODO: Add ``_supervisor_score(state)`` neural hook — once SupervisorNet
          is available, call it here before the symbolic rule engine to
          optionally adjust rule weights or veto decisions.
    """

    def __init__(self) -> None:
        # TODO: wire SupervisorNet instance here when available
        self._supervisor: Optional[Any] = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def evaluate_turn(
        self,
        agent_name: str,
        state_dict: Dict[str, Any],
    ) -> ControlDecision:
        """Evaluate one completed turn and return a :class:`ControlDecision`.

        Parameters
        ----------
        agent_name:
            Name of the agent that just spoke.
        state_dict:
            Dictionary of signal values.  Unknown keys are silently ignored;
            missing keys fall back to the defaults defined in
            :class:`IntegrationState`.

        Returns
        -------
        ControlDecision
            The regulation decision for the *next* turn.
        """
        state = self._build_state(agent_name, state_dict)
        logger.info(
            "[INTEGRATION-STATE] agent=%s semantic_repeat=%s structural_repeat=%s "
            "loop_count=%d progress_after=%.2f unresolved=%d pressure=%.2f "
            "fatigue=%.2f stagnation=%.2f is_loop=%s compliance=%s "
            "abstraction=%s energy=%.1f status=%s",
            state.agent_name,
            state.semantic_repeat,
            state.structural_repeat,
            state.loop_count,
            state.progress_after,
            state.unresolved,
            state.pressure,
            state.fatigue,
            state.stagnation,
            state.is_loop,
            state.compliance,
            state.abstraction_detected,
            state.energy,
            state.status,
        )

        # TODO: call _supervisor_score(state) here once SupervisorNet is ready
        decision = self._apply_rules(state)

        logger.info(
            "[INTEGRATION-DECISION] agent=%s mode=%s priority=%d reason=%r "
            "regenerate=%s suppress_personality=%s enforce_fixy=%s",
            state.agent_name,
            decision.active_mode.value,
            decision.priority_level,
            decision.decision_reason,
            decision.regenerate,
            decision.suppress_personality,
            decision.enforce_fixy,
        )
        logger.info(
            "[INTEGRATION-MODE] %s", decision.active_mode.value
        )
        return decision

    def build_prompt_overlay(self, decision: ControlDecision) -> str:
        """Return the overlay text block for injection into the next LLM prompt.

        The overlay is already populated inside *decision*.  This method
        additionally logs it and returns it for convenience.

        Parameters
        ----------
        decision:
            A :class:`ControlDecision` previously returned by
            :meth:`evaluate_turn`.

        Returns
        -------
        str
            Short imperative directive block, or empty string when mode is
            NORMAL.
        """
        overlay = decision.prompt_overlay
        if overlay:
            logger.info("[INTEGRATION-OVERLAY] %r", overlay)
        return overlay

    def should_regenerate(self, decision: ControlDecision) -> bool:
        """Return True when the caller must discard the current draft and retry.

        Parameters
        ----------
        decision:
            A :class:`ControlDecision` previously returned by
            :meth:`evaluate_turn`.

        Returns
        -------
        bool
        """
        if decision.regenerate:
            logger.warning(
                "[INTEGRATION-REGEN] Regeneration required. reason=%r",
                decision.decision_reason,
            )
        return decision.regenerate

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _build_state(
        agent_name: str, state_dict: Dict[str, Any]
    ) -> IntegrationState:
        """Construct an :class:`IntegrationState` from a raw signal dict.

        Only keys that correspond to :class:`IntegrationState` fields are
        consumed; all others are silently discarded.
        """
        valid_fields = IntegrationState.__dataclass_fields__  # type: ignore[attr-defined]
        filtered = {
            k: v for k, v in state_dict.items() if k in valid_fields
        }
        return IntegrationState(agent_name=agent_name, **filtered)

    # ------------------------------------------------------------------
    # Rule engine
    # ------------------------------------------------------------------

    def _apply_rules(self, state: IntegrationState) -> ControlDecision:
        """Apply priority-ordered rules and return the first matching decision."""

        # Priority 1 — Loop / semantic repetition
        if self._rule_fixy_authority(state):
            return self._decide_fixy_authority(state)

        if self._rule_loop_concrete(state):
            return self._decide_loop_concrete(state)

        if self._rule_personality_suppression(state):
            return self._decide_personality_suppression(state)

        # Priority 2 — Stagnation → attack (only if it structurally changes reasoning)
        if self._rule_stagnation_attack(state):
            return self._decide_stagnation_attack(state)

        # Priority 3 — Unresolved overload
        if self._rule_unresolved_resolution(state):
            return self._decide_unresolved_resolution(state)

        # Priority 4 — Fatigue degradation
        if self._rule_fatigue_low_complexity(state):
            return self._decide_fatigue_low_complexity(state)

        # Priority 5 — Pressure misalignment (measurement-only, advisory)
        if self._rule_pressure_misalignment(state):
            return self._decide_pressure_misalignment(state)

        # Priority 6 — Default
        return ControlDecision(
            active_mode=IntegrationMode.NORMAL,
            decision_reason="All signals within acceptable range. No override required.",
            priority_level=_PRIORITY_DEFAULT,
        )

    # ------------------------------------------------------------------
    # Rule predicates
    # ------------------------------------------------------------------

    @staticmethod
    def _rule_fixy_authority(state: IntegrationState) -> bool:
        """Fixy flagged loop AND compliance was only superficial."""
        return state.is_loop and not state.compliance

    @staticmethod
    def _rule_loop_concrete(state: IntegrationState) -> bool:
        """Semantic repetition AND loop_count >= 1."""
        return state.semantic_repeat and state.loop_count >= _LOOP_COUNT_TRIGGER

    @staticmethod
    def _rule_personality_suppression(state: IntegrationState) -> bool:
        """Semantic repetition AND stagnation above suppression threshold."""
        return (
            state.semantic_repeat
            and state.stagnation >= _STAGNATION_SUPPRESS_THRESHOLD
        )

    @staticmethod
    def _rule_stagnation_attack(state: IntegrationState) -> bool:
        """Stagnation above suppression threshold (without semantic_repeat)."""
        return state.stagnation >= _STAGNATION_SUPPRESS_THRESHOLD

    @staticmethod
    def _rule_unresolved_resolution(state: IntegrationState) -> bool:
        """Unresolved tensions overloaded AND low argumentative progress."""
        return (
            state.unresolved >= _UNRESOLVED_RESOLUTION_TRIGGER
            and state.progress_after < _PROGRESS_RESOLUTION_TRIGGER
        )

    @staticmethod
    def _rule_fatigue_low_complexity(state: IntegrationState) -> bool:
        """Fatigue exceeds low-complexity threshold."""
        return state.fatigue >= _FATIGUE_LOW_COMPLEXITY_THRESHOLD

    @staticmethod
    def _rule_pressure_misalignment(state: IntegrationState) -> bool:
        """Pressure alignment is not 'aligned'."""
        return state.alignment not in ("aligned", "neutral")

    # ------------------------------------------------------------------
    # Decision builders
    # ------------------------------------------------------------------

    @staticmethod
    def _decide_fixy_authority(state: IntegrationState) -> ControlDecision:
        reason = (
            f"Fixy flagged loop (is_loop=True) and agent '{state.agent_name}' "
            "showed only superficial compliance (compliance=False). "
            "Fixy authority override is mandatory."
        )
        return ControlDecision(
            regenerate=True,
            suppress_personality=True,
            enforce_fixy=True,
            force_concrete_mode=True,
            prompt_overlay=_OVERLAY_FIXY,
            decision_reason=reason,
            priority_level=_PRIORITY_LOOP,
            active_mode=IntegrationMode.FIXY_AUTHORITY_OVERRIDE,
        )

    @staticmethod
    def _decide_loop_concrete(state: IntegrationState) -> ControlDecision:
        reason = (
            f"Semantic repeat detected for '{state.agent_name}' "
            f"with loop_count={state.loop_count}. "
            "Concrete override activated to break abstract repetition."
        )
        return ControlDecision(
            force_concrete_mode=True,
            prompt_overlay=_OVERLAY_LOOP + " " + _OVERLAY_CONCRETE,
            decision_reason=reason,
            priority_level=_PRIORITY_LOOP,
            active_mode=IntegrationMode.CONCRETE_OVERRIDE,
        )

    @staticmethod
    def _decide_personality_suppression(state: IntegrationState) -> ControlDecision:
        reason = (
            f"Semantic repeat with stagnation={state.stagnation:.2f} "
            f">= {_STAGNATION_SUPPRESS_THRESHOLD} for '{state.agent_name}'. "
            "Personality style suppressed to break attractor loop."
        )
        return ControlDecision(
            suppress_personality=True,
            force_concrete_mode=True,
            prompt_overlay=_OVERLAY_PERSONALITY_SUPPRESSION + " " + _OVERLAY_CONCRETE,
            decision_reason=reason,
            priority_level=_PRIORITY_LOOP,
            active_mode=IntegrationMode.PERSONALITY_SUPPRESSION,
        )

    @staticmethod
    def _decide_stagnation_attack(state: IntegrationState) -> ControlDecision:
        reason = (
            f"Stagnation={state.stagnation:.2f} detected for '{state.agent_name}'. "
            "Attack override activated to force structural reasoning change."
        )
        return ControlDecision(
            force_attack_mode=True,
            suppress_personality=True,
            prompt_overlay=_OVERLAY_ATTACK,
            decision_reason=reason,
            priority_level=_PRIORITY_STAGNATION,
            active_mode=IntegrationMode.ATTACK_OVERRIDE,
        )

    @staticmethod
    def _decide_unresolved_resolution(state: IntegrationState) -> ControlDecision:
        reason = (
            f"Unresolved tensions={state.unresolved} >= {_UNRESOLVED_RESOLUTION_TRIGGER} "
            f"and progress_after={state.progress_after:.2f} < {_PROGRESS_RESOLUTION_TRIGGER} "
            f"for '{state.agent_name}'. Resolution override required."
        )
        return ControlDecision(
            force_resolution_mode=True,
            prompt_overlay=_OVERLAY_RESOLUTION,
            decision_reason=reason,
            priority_level=_PRIORITY_UNRESOLVED,
            active_mode=IntegrationMode.RESOLUTION_OVERRIDE,
        )

    @staticmethod
    def _decide_fatigue_low_complexity(state: IntegrationState) -> ControlDecision:
        reason = (
            f"Fatigue={state.fatigue:.2f} >= {_FATIGUE_LOW_COMPLEXITY_THRESHOLD} "
            f"for '{state.agent_name}'. Low-complexity mode activated."
        )
        return ControlDecision(
            low_complexity_mode=True,
            prompt_overlay=_OVERLAY_FATIGUE,
            decision_reason=reason,
            priority_level=_PRIORITY_FATIGUE,
            active_mode=IntegrationMode.LOW_COMPLEXITY,
        )

    @staticmethod
    def _decide_pressure_misalignment(state: IntegrationState) -> ControlDecision:
        reason = (
            f"Pressure alignment='{state.alignment}' is not 'aligned'/'neutral' "
            f"for '{state.agent_name}'. Advisory overlay injected."
        )
        overlay = (
            "Internal pressure state and expressed dialogue pressure are misaligned. "
            "You must express the actual tension in this response — do not suppress it."
        )
        return ControlDecision(
            prompt_overlay=overlay,
            decision_reason=reason,
            priority_level=_PRIORITY_PRESSURE,
            active_mode=IntegrationMode.NORMAL,
        )

    # ------------------------------------------------------------------
    # Future-ready stub
    # ------------------------------------------------------------------

    def _supervisor_score(self, state: IntegrationState) -> Optional[float]:
        """Neural supervisor hook — returns None until SupervisorNet is wired.

        TODO: replace with actual SupervisorNet.score(state) call.
        The return value should be a confidence modifier in [0.0, 1.0] that
        is applied to rule thresholds before the symbolic engine runs.
        """
        # pylint: disable=unused-argument
        return None  # no-op stub


# ---------------------------------------------------------------------------
# Convenience factory
# ---------------------------------------------------------------------------


def make_integration_state(
    agent_name: str, **kwargs: Any
) -> IntegrationState:
    """Construct an :class:`IntegrationState` from keyword arguments.

    Unrecognised keywords are silently dropped.  Useful in one-liners::

        state = make_integration_state("Socrates", semantic_repeat=True, loop_count=2)
    """
    return IntegrationCore._build_state(agent_name, kwargs)

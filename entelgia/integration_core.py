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
IntegrationCore.escalate_decision(decision)           -> ControlDecision
detect_pseudo_compliance(text)                        -> bool

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

Escalation levels
-----------------
0 → NORMAL
1 → CONCRETE_OVERRIDE (soft)
2 → STRICT_CONCRETE
3 → FORMAT_ENFORCED
4 → HARD_OVERRIDE (personality suppressed)

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
[INTEGRATION-STATE]         — normalised input signals (post-generation)
[INTEGRATION-DECISION]      — final ControlDecision (post-generation)
[INTEGRATION-MODE]          — active IntegrationMode
[INTEGRATION-OVERLAY]       — generated prompt overlay text (post-generation)
[INTEGRATION-REGEN]         — regeneration policy triggered
[INTEGRATION-ESCALATION]    — escalation level assigned
[INTEGRATION-PSEUDO-COMPLIANCE] — pseudo-compliance detection result
[INTEGRATION-FORCE-REGEN]   — forced regeneration with reason
[PRE-GEN-STATE]             — normalised input signals before LLM call
[PRE-GEN-DECISION]          — ControlDecision produced before LLM call
[PRE-GEN-OVERLAY]           — overlay text injected into current prompt
[POST-GEN-VALIDATION]       — compliance check on generated output
"""

from __future__ import annotations

import hashlib
import logging
import re
from dataclasses import dataclass, field
from enum import Enum, IntEnum
from typing import Any, Dict, List, Optional, Tuple, Union

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

# Escalation engine constants
_ESCALATION_LOOP_COUNT_LEVEL1: int = 1
_ESCALATION_LOOP_COUNT_LEVEL2: int = 2
_ESCALATION_LOOP_COUNT_LEVEL3: int = 3
_ESCALATION_LOOP_COUNT_LEVEL4: int = 4
_ESCALATION_PERSONALITY_SUPPRESS_LEVEL: int = 3
_MAX_REGENERATION_ATTEMPTS: int = 3

# Structure lock: activates when escalation_level >= this threshold.
# At this point text-based instructions alone are insufficient; the response
# format is enforced structurally by validating that all required section
# headers are present in the output AND that each section contains meaningful
# concrete content.
_STRUCTURE_LOCK_LEVEL: int = 3
# Required section headers (lowercased for case-insensitive matching)
_STRUCTURE_LOCK_SECTIONS: tuple = ("[person]", "[action]", "[outcome]")

# Generic placeholder phrases that make any section body invalid.
# Each entry is a regex fragment matched with word boundaries.
_STRUCTURE_LOCK_GENERIC_PLACEHOLDERS: tuple = (
    r"someone",
    r"a\s+person",
    r"an\s+individual",
    r"something",
    r"some\s+action",
)

# Concrete observable action verbs required in the [ACTION] body.
# At least one must be present (past or present tense).
# Past-tense forms (examples are typically narrated in past tense)
_STRUCTURE_LOCK_ACTION_VERBS: tuple = (
    # Medical / clinical
    "administered", "prescribed", "diagnosed", "treated", "operated",
    # Professional / administrative
    "signed", "filed", "submitted", "registered", "issued", "approved",
    "denied", "refused", "rejected", "accepted", "announced", "declared",
    "promoted", "fired", "hired", "resigned", "dismissed", "convicted",
    "arrested", "charged", "voted", "introduced", "passed", "acquired",
    "banned", "reported", "requested",
    # Communication
    "called", "wrote", "published", "recorded",
    # Construction / technical
    "built", "installed", "removed", "replaced", "repaired", "fixed",
    "assembled", "loaded", "printed", "scanned", "tested", "measured",
    "deployed", "launched", "activated", "released", "executed", "implemented",
    # Transport / movement
    "drove", "walked", "ran", "arrived", "departed", "entered", "exited",
    "returned", "visited", "moved", "transferred",
    # Commerce / logistics
    "sold", "bought", "sent", "received", "delivered", "completed",
    # Manufacturing / production
    "produced", "created", "conducted", "performed", "applied",
    # Everyday / general observable
    "gave", "took", "put", "placed", "ate", "drank", "read", "taught",
    "edited", "deleted", "copied", "typed", "pressed", "clicked",
    "started", "stopped", "closed", "chose", "selected", "decided",
    # Present-tense forms (for responses narrated in present tense).
    # Suffix pattern in matching covers -s/-es/-ing/-ed/-d inflections so each
    # base stem here also matches third-person singular and progressive forms.
    "decide", "choose", "take", "run", "drive", "walk", "produce",
    "create", "publish", "fire", "hire", "operate", "deploy", "launch",
    "install", "remove", "close", "complete", "deliver", "sell", "buy",
    "transfer", "send", "receive", "conduct", "perform", "execute",
    "apply", "announce", "report", "approve", "give", "treat", "diagnose",
    "repair", "fix", "test", "measure", "record", "visit", "arrive",
    "enter", "exit", "return",
    # Medical base stems not covered by past-tense entries above
    "administer", "prescribe",
)

# Phrases in [OUTCOME] that signal abstract reflection rather than an
# observable consequence.  Any match causes content validation to fail.
_STRUCTURE_LOCK_OUTCOME_ABSTRACT: tuple = (
    "invites reflection",
    "raises the question",
    "challenges us to",
    "makes us think",
    "reminds us",
    "highlights the importance",
    "shows us that",
    "demonstrates that",
    "suggests that",
    "implies that",
    "serves as a reminder",
    "calls into question",
    "forces us to reconsider",
    "opens up new questions",
    "opens up new ways of thinking",
    "this is a reminder",
)

# Pseudo-compliance detection: similarity threshold for reasoning hash comparison
_REASONING_HASH_SIMILARITY_THRESHOLD: int = 2  # max allowed same hashes in history
# Number of content words used when building the reasoning skeleton hash
_REASONING_HASH_MAX_TOKENS: int = 40
# History window size: threshold + 1 unique entries + 1 buffer for the incoming hash
_REASONING_HASH_HISTORY_SIZE: int = _REASONING_HASH_SIMILARITY_THRESHOLD + 2


# ---------------------------------------------------------------------------
# Pipeline gate
# ---------------------------------------------------------------------------


def integration_pipeline_enabled(cfg) -> bool:
    """Return True only when the IntegrationCore enforce pipeline must be active.

    This is the single authoritative gate for the cortex enforce subsystem.
    Every IntegrationCore entry point (pre-generation decision,
    post-generation evaluate_turn, overlay injection, regeneration, and
    cortex-forced Fixy intervention) must be gated through this function.

    When this returns False the cortex enforce pipeline is a hard no-op: no
    force-mode overlays are applied, no regeneration is triggered by the
    cortex, and IntegrationCore returns NORMAL decisions only.
    """
    return bool(getattr(cfg, "integration_enforce_enabled", False))


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


class EscalationLevel(IntEnum):
    """Escalation levels used by the hard-control engine.

    Level 0 → NORMAL         — no escalation
    Level 1 → CONCRETE_OVERRIDE (soft) — request a concrete real-world example
    Level 2 → STRICT_CONCRETE — structured concrete example required
    Level 3 → FORMAT_ENFORCED — mandatory output format; personality suppressed
    Level 4 → HARD_OVERRIDE   — personality fully disabled; hard output cap
    """

    NORMAL = 0
    CONCRETE_OVERRIDE = 1
    STRICT_CONCRETE = 2
    FORMAT_ENFORCED = 3
    HARD_OVERRIDE = 4


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
    escalation_level: int = EscalationLevel.NORMAL


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
# Escalation-level overlay templates
# ---------------------------------------------------------------------------

_OVERLAY_ESCALATION_1: str = (
    "Provide one concrete real-world example. Avoid abstract repetition."
)

_OVERLAY_ESCALATION_2: str = (
    "You must provide a specific real-world example:\n"
    "- include a person\n"
    "- include a concrete action\n"
    "- include a situation\n"
    "Abstract reasoning is not sufficient."
)

_OVERLAY_ESCALATION_3: str = (
    "STRICT FORMAT REQUIRED:\n\n"
    "[PERSON]\n"
    "A specific real person — use a name or a concrete role (e.g. 'Dr Smith' or 'a nurse').\n"
    "Do NOT write 'a person', 'someone', or 'an individual'.\n\n"
    "[ACTION]\n"
    "One specific observable action they performed — use a concrete action verb.\n"
    "Do NOT write 'does something' or 'performs some action'.\n\n"
    "[OUTCOME]\n"
    "A concrete observable consequence — what actually happened next.\n"
    "Do NOT write abstract reflection or philosophical commentary.\n\n"
    "Failure to follow format exactly is invalid."
)

_OVERLAY_ESCALATION_4: str = (
    "HARD OVERRIDE:\n\n"
    "- Personality style is disabled\n"
    "- No philosophical questions allowed\n"
    "- Output must be 1–2 sentences maximum\n"
    "- Must describe a concrete real-world action\n\n"
    "Invalid output will be rejected."
)

# Map escalation level → overlay text
_ESCALATION_OVERLAYS: Dict[int, str] = {
    EscalationLevel.NORMAL: "",
    EscalationLevel.CONCRETE_OVERRIDE: _OVERLAY_ESCALATION_1,
    EscalationLevel.STRICT_CONCRETE: _OVERLAY_ESCALATION_2,
    EscalationLevel.FORMAT_ENFORCED: _OVERLAY_ESCALATION_3,
    EscalationLevel.HARD_OVERRIDE: _OVERLAY_ESCALATION_4,
}

# ---------------------------------------------------------------------------
# Second-pass overlay prefix (used when the first pass was ignored)
# ---------------------------------------------------------------------------

_STRONGER_OVERLAY_PREFIX: str = (
    "STRICT REGENERATION REQUIRED. "
    "The previous response ignored an active directive. "
    "This is a mandatory second attempt. You must comply with the following:\n"
)

# ---------------------------------------------------------------------------
# Failure memory injection (injected into re-generation prompts)
# ---------------------------------------------------------------------------

_FAILURE_MEMORY_PREFIX: str = (
    "Previous attempts failed to comply with constraints. "
    "Do not repeat previous reasoning.\n"
)

# ---------------------------------------------------------------------------
# Post-generation validation signal lists
# ---------------------------------------------------------------------------

# Phrases that indicate a concrete, real-world grounding
_VALIDATE_CONCRETE_SIGNALS: tuple = (
    "for example",
    "for instance",
    "such as",
    "in practice",
    "real-world",
    "real world",
    "consider the case",
    "take the case",
    "in the case of",
    "specifically",
    "a study",
    "research shows",
    "evidence shows",
    "data shows",
    "according to",
    "demonstrated by",
    "illustrated by",
    "imagine a",
    "picture a",
    "think of",
)

# Phrases that indicate resolution or conclusion
_VALIDATE_RESOLUTION_SIGNALS: tuple = (
    "therefore",
    "thus we can",
    "i conclude",
    "we can conclude",
    "the answer is",
    "this resolves",
    "this settles",
    "the tension is resolved",
    "we can agree",
    "i agree that",
    "it follows that",
    "this means",
    "this implies that",
    "in conclusion",
    "to summarise",
    "to summarize",
)

# Phrases that indicate a structural challenge or attack
_VALIDATE_ATTACK_SIGNALS: tuple = (
    "wrong",
    "incorrect",
    "this is false",
    "that is false",
    "flawed",
    "fails to",
    "overlooks",
    "mistaken",
    "does not account",
    "ignores",
    "contradicts",
    "undermines",
    "refutes",
    "i challenge",
    "i dispute",
    "i reject",
    "not the case",
    "the opposite",
    "rather than",
)

# Word-count ceiling enforced for LOW_COMPLEXITY mode responses
_LOW_COMPLEXITY_MAX_WORDS: int = 150

# ---------------------------------------------------------------------------
# Pseudo-compliance detection helpers
# ---------------------------------------------------------------------------

# Phrases that typically introduce a hypothetical or abstract placeholder
# rather than a genuine concrete example.
_PSEUDO_COMPLIANCE_TRIGGERS: tuple = (
    "for example",
    "for instance",
    "imagine",
    "picture a",
    "think of",
    "suppose",
    "let's say",
    "let us say",
    "consider",
)

# Patterns indicating the presence of a named person or a named role
_CONCRETE_PERSON_PATTERN: re.Pattern = re.compile(
    r"""
    \b(
        [A-Z][a-z]* \s [A-Z][a-z]*   # Proper full name: "John Smith", "Li Wu"
        | [A-Z][a-z]{1,}              # Capitalised first name: "Alice", "Al"
        | a \s teacher                # role article + role noun
        | a \s doctor
        | a \s student
        | a \s nurse
        | a \s manager
        | a \s soldier
        | a \s pilot
        | a \s engineer
        | a \s scientist
        | a \s worker
        | a \s parent
        | the \s teacher
        | the \s doctor
        | the \s student
        | the \s nurse
        | the \s manager
        | the \s soldier
        | the \s pilot
        | the \s engineer
        | the \s scientist
        | the \s worker
        | the \s parent
    )\b
    """,
    re.VERBOSE | re.IGNORECASE,
)

# Pattern indicating a concrete action: verb clearly tied to a scenario
_CONCRETE_ACTION_PATTERN: re.Pattern = re.compile(
    r"\b(decides?|chooses?|takes?|runs?|walks?|opens?|closes?|builds?|writes?|calls?|"
    r"applies?|submits?|fires?|hires?|signs?|pays?|buys?|sells?|sends?|reads?|"
    r"leaves?|arrives?|creates?|starts?|stops?|drives?|flies?|enters?|exits?)\b",
    re.IGNORECASE,
)

# Pattern indicating a specific situation (location / time / event anchor)
_CONCRETE_SITUATION_PATTERN: re.Pattern = re.compile(
    r"\b(in \w+ (hospital|school|factory|office|courtroom|city|town|company)|"
    r"during (the|a) \w+|at (the|a) \w+ (meeting|trial|game|event|session|interview)|"
    r"on (monday|tuesday|wednesday|thursday|friday|saturday|sunday)|"
    r"in \d{4}|last (week|month|year)|yesterday|this (morning|afternoon|evening))\b",
    re.IGNORECASE,
)


def detect_pseudo_compliance(text: str) -> bool:
    """Return ``True`` when *text* appears to comply but lacks genuine concreteness.

    Pseudo-compliance is detected when the text contains one of the typical
    hypothetical-introduction phrases (e.g. "for example", "imagine") **but**
    does **not** include all three of:

    1. A named person or a concrete role (e.g. "a teacher", "John")
    2. A concrete action verb tied to a real scenario
    3. A specific situational anchor (location, time, event)

    Parameters
    ----------
    text:
        The generated response text to inspect.

    Returns
    -------
    bool
        ``True`` when pseudo-compliance is detected.
    """
    t_lower = text.lower()
    has_trigger = any(phrase in t_lower for phrase in _PSEUDO_COMPLIANCE_TRIGGERS)
    if not has_trigger:
        return False

    has_person = bool(_CONCRETE_PERSON_PATTERN.search(text))
    has_action = bool(_CONCRETE_ACTION_PATTERN.search(text))
    has_situation = bool(_CONCRETE_SITUATION_PATTERN.search(text))

    # If trigger present but missing any concreteness indicator → pseudo-compliance
    return not (has_person and has_action and has_situation)


def _extract_section_body(text_lower: str, section_header: str) -> str:
    """Return the body text after *section_header* until the next section or end.

    The set of known section names is derived from :data:`_STRUCTURE_LOCK_SECTIONS`
    so the regex stays in sync if sections are ever renamed.

    Parameters
    ----------
    text_lower:
        The full response text already lowercased.
    section_header:
        Lowercased section tag, e.g. ``"[action]"``.

    Returns
    -------
    str
        Stripped body text, or an empty string when the header is not found.
    """
    # Build alternation from known section names (strip surrounding brackets).
    # Anchor to line start so that a section name inside a body paragraph does
    # not trigger a false split.
    section_names = "|".join(
        re.escape(s.strip("[]")) for s in _STRUCTURE_LOCK_SECTIONS
    )
    pattern = (
        r"(?m)^"
        + re.escape(section_header)
        + r"\s*\n(.*?)(?=^"
        + r"\[(?:"
        + section_names
        + r")\]|\Z)"
    )
    match = re.search(pattern, text_lower, re.DOTALL | re.MULTILINE)
    if match:
        return match.group(1).strip()
    return ""


def _validate_structure_lock_content(text: str) -> "Tuple[bool, str]":
    """Validate that each STRUCTURE_LOCK section has meaningful concrete content.

    Called **after** all required headers have been confirmed present.  Checks
    that section bodies are not filled with generic placeholders, that
    ``[ACTION]`` contains at least one concrete observable action verb, and that
    ``[OUTCOME]`` does not consist solely of abstract philosophical reflection.

    Parameters
    ----------
    text:
        The full response text (any casing).

    Returns
    -------
    (compliant, reason)
        *compliant* is ``True`` when every section passes all content rules.
        *reason* is a short human-readable explanation of the first failure
        encountered.
    """
    t = text.lower()

    # 1. Generic placeholder check — applies to all sections
    for section_header in _STRUCTURE_LOCK_SECTIONS:
        body = _extract_section_body(t, section_header)
        for placeholder_re in _STRUCTURE_LOCK_GENERIC_PLACEHOLDERS:
            if re.search(r"\b" + placeholder_re + r"\b", body):
                return (
                    False,
                    f"STRUCTURE_LOCK content violation: {section_header.upper()} "
                    f"contains generic placeholder — content must be specific and concrete.",
                )

    # 2. [ACTION] must contain at least one concrete observable action verb.
    # Matches base form, 3rd-person singular (-s/-es), past tense (-d/-ed),
    # and progressive (-ing) to avoid false failures for common inflections.
    action_body = _extract_section_body(t, "[action]")
    if not any(
        re.search(r"\b" + re.escape(verb) + r"(?:s|es|ing|ed|d)?\b", action_body)
        for verb in _STRUCTURE_LOCK_ACTION_VERBS
    ):
        return (
            False,
            "STRUCTURE_LOCK content violation: [ACTION] must contain at least "
            "one concrete observable action verb.",
        )

    # 3. [OUTCOME] must not be pure abstract reflection
    outcome_body = _extract_section_body(t, "[outcome]")
    for phrase in _STRUCTURE_LOCK_OUTCOME_ABSTRACT:
        if phrase in outcome_body:
            return (
                False,
                f"STRUCTURE_LOCK content violation: [OUTCOME] contains abstract "
                f"reflection ('{phrase}') instead of an observable consequence.",
            )

    return True, "STRUCTURE_LOCK content validated: all sections contain concrete content."


def _reasoning_hash(text: str) -> str:
    """Return a short hash of the normalised reasoning skeleton of *text*.

    Strips common filler words and punctuation to surface structural
    similarity across responses that use different surface wording.
    """
    # Normalise: lowercase, strip punctuation, collapse whitespace
    normalised = re.sub(r"[^\w\s]", "", text.lower())
    normalised = re.sub(r"\s+", " ", normalised).strip()
    # Remove extremely common stop words to surface structural similarity
    stop_words = {
        "the", "a", "an", "is", "are", "was", "were", "be", "been", "being",
        "have", "has", "had", "do", "does", "did", "will", "would", "could",
        "should", "may", "might", "shall", "can", "i", "we", "you", "they",
        "he", "she", "it", "this", "that", "these", "those", "and", "or",
        "but", "if", "in", "on", "at", "to", "for", "of", "with", "by",
        "from", "as", "so", "yet", "not",
    }
    tokens = [w for w in normalised.split() if w not in stop_words]
    skeleton = " ".join(sorted(tokens[:_REASONING_HASH_MAX_TOKENS]))
    return hashlib.md5(skeleton.encode("utf-8")).hexdigest()[:12]


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

        # Preferred: pass an IntegrationState directly
        state = IntegrationState(
            agent_name="Socrates",
            semantic_repeat=True,
            loop_count=2,
            stagnation=0.3,
        )
        decision = core.evaluate_turn("Socrates", state)

        # Alternatively: pass a plain signal dict (used by the main loop)
        decision = core.evaluate_turn("Socrates", {"semantic_repeat": True, "loop_count": 2})

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
        # Rolling history of reasoning hashes for same-reasoning detection
        self._reasoning_hash_history: List[str] = []

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def evaluate_turn(
        self,
        agent_name: str,
        state_input: "Union[IntegrationState, Dict[str, Any]]",
    ) -> ControlDecision:
        """Evaluate one completed turn and return a :class:`ControlDecision`.

        Parameters
        ----------
        agent_name:
            Name of the agent that just spoke.  Ignored when *state_input*
            is already an :class:`IntegrationState` (the name is read from
            the struct directly).
        state_input:
            Either an :class:`IntegrationState` instance (preferred, used
            when the caller has already built the struct) or a plain
            ``Dict[str, Any]`` of signal values (used by the main loop for
            convenience).  When a dict is supplied, unknown keys are silently
            ignored and missing keys fall back to the defaults defined in
            :class:`IntegrationState`.

        Returns
        -------
        ControlDecision
            The regulation decision for the *next* turn.
        """
        if isinstance(state_input, IntegrationState):
            state = state_input
        else:
            state = self._build_state(agent_name, state_input)
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

    def prepare_generation_state(
        self,
        agent_name: str,
        signals: "Dict[str, Any]",
    ) -> IntegrationState:
        """Build an :class:`IntegrationState` from pre-generation signals.

        Identical in mechanics to the internal :meth:`_build_state` helper but
        exposed as a named public entry-point to make the two-stage control
        flow explicit in calling code.

        Parameters
        ----------
        agent_name:
            Name of the agent about to generate a response.
        signals:
            Dict of signal values mirroring :class:`IntegrationState` fields.
            Unknown keys are silently ignored; missing keys fall back to
            :class:`IntegrationState` defaults.

        Returns
        -------
        IntegrationState
        """
        return self._build_state(agent_name, signals)

    def pre_generation_decision(
        self,
        agent_name: str,
        state_input: "Union[IntegrationState, Dict[str, Any]]",
    ) -> ControlDecision:
        """Evaluate pre-generation state and return a :class:`ControlDecision`.

        Must be called **before** the LLM call so that the active mode
        constrains the *current* response rather than only the next one.
        Accepts the same input formats as :meth:`evaluate_turn` and applies
        the same rule engine; the difference is the ``[PRE-GEN-*]`` log tags
        used here, which distinguish pre-generation decisions from the
        post-generation :meth:`evaluate_turn` call.

        Parameters
        ----------
        agent_name:
            Name of the agent about to speak.
        state_input:
            :class:`IntegrationState` or signal dict built from the signals
            known at the *end of the previous turn*.

        Returns
        -------
        ControlDecision
        """
        if isinstance(state_input, IntegrationState):
            state = state_input
        else:
            state = self._build_state(agent_name, state_input)

        logger.info(
            "[PRE-GEN-STATE] agent=%s semantic_repeat=%s structural_repeat=%s "
            "loop_count=%d progress_after=%.2f unresolved=%d pressure=%.2f "
            "fatigue=%.2f stagnation=%.2f is_loop=%s compliance=%s "
            "energy=%.1f status=%s",
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
            state.energy,
            state.status,
        )

        decision = self._apply_rules(state)

        logger.info(
            "[PRE-GEN-DECISION] agent=%s mode=%s priority=%d reason=%r "
            "suppress_personality=%s enforce_fixy=%s",
            state.agent_name,
            decision.active_mode.value,
            decision.priority_level,
            decision.decision_reason,
            decision.suppress_personality,
            decision.enforce_fixy,
        )
        return decision

    def build_generation_overlay(self, decision: ControlDecision) -> str:
        """Return the overlay text to inject into the **current** LLM prompt.

        Logs the overlay under ``[PRE-GEN-OVERLAY]`` so it is distinguishable
        from the post-generation :meth:`build_prompt_overlay` call.

        Parameters
        ----------
        decision:
            A :class:`ControlDecision` previously returned by
            :meth:`pre_generation_decision`.

        Returns
        -------
        str
            Short imperative directive block, or empty string when no overlay
            is active. Callers must not assume that NORMAL mode implies an
            empty overlay; advisory overlays may be present even when
            ``decision.active_mode`` is NORMAL.
        """
        overlay = decision.prompt_overlay
        if overlay:
            logger.info("[PRE-GEN-OVERLAY] %r", overlay)
        return overlay

    def validate_generated_output(
        self,
        text: str,
        decision: ControlDecision,
    ) -> "Tuple[bool, str]":
        """Check whether *text* respects the active mode in *decision*.

        Uses lightweight heuristic pattern matching — no semantic parsing.
        Only modes that impose a detectable textual obligation are validated:

        * ``CONCRETE_OVERRIDE`` / ``PERSONALITY_SUPPRESSION`` —
          response must contain at least one concrete signal phrase and must
          not be pseudo-compliant.
        * ``RESOLUTION_OVERRIDE`` — response must contain resolution language.
        * ``ATTACK_OVERRIDE`` — response must contain a structural challenge.
        * ``LOW_COMPLEXITY`` — response word count must not exceed
          :data:`_LOW_COMPLEXITY_MAX_WORDS`.
        * ``FIXY_AUTHORITY_OVERRIDE`` / ``NORMAL`` — always pass (no
          additional detectable textual obligation).

        **STRUCTURE_LOCK** (escalation_level >= :data:`_STRUCTURE_LOCK_LEVEL`):
          Applied regardless of active mode.  When engaged, (1) every required
          section header listed in :data:`_STRUCTURE_LOCK_SECTIONS` must be
          present, and (2) each section body must contain meaningful concrete
          content — no generic placeholders, ``[ACTION]`` must include at
          least one observable action verb, and ``[OUTCOME]`` must not consist
          of abstract reflection.  Only after both checks pass are mode-based
          heuristics skipped.

        Pseudo-compliance is checked for CONCRETE_OVERRIDE and
        PERSONALITY_SUPPRESSION modes: a response that contains a
        hypothetical trigger phrase but lacks a concrete person, action, and
        situation is treated as non-compliant even if it contains a concrete
        signal phrase.

        Parameters
        ----------
        text:
            The generated response text to validate.
        decision:
            The :class:`ControlDecision` produced by
            :meth:`pre_generation_decision` for this generation step.

        Returns
        -------
        (compliant, reason)
            *compliant* is ``True`` when the response satisfies the active
            mode constraint.  *reason* is a short human-readable explanation.
        """
        mode = decision.active_mode

        t = text.lower()

        # -----------------------------------------------------------------
        # STRUCTURE_LOCK — section-header + content enforcement (level >= 3)
        # Evaluated first, before the NORMAL early-return, so that any future
        # decision combining NORMAL mode with a high escalation level is still
        # caught here.  Uses line-anchored regex so that a section name
        # mentioned inside a body paragraph does not satisfy the header check.
        # -----------------------------------------------------------------
        if decision.escalation_level >= _STRUCTURE_LOCK_LEVEL:
            logger.info(
                "[STRUCTURE-LOCK] active escalation_level=%d required_sections=%s",
                decision.escalation_level,
                _STRUCTURE_LOCK_SECTIONS,
            )
            missing = [
                s for s in _STRUCTURE_LOCK_SECTIONS
                if not re.search(r"(?m)^" + re.escape(s), t)
            ]
            if missing:
                return (
                    False,
                    f"STRUCTURE_LOCK violation: required section(s) missing: "
                    f"{', '.join(s.upper() for s in missing)}. "
                    "Response must use the exact section headers.",
                )
            # All headers present — now validate section content quality.
            content_ok, content_reason = _validate_structure_lock_content(text)
            if not content_ok:
                logger.warning(
                    "[STRUCTURE-LOCK] content validation failed: %s",
                    content_reason,
                )
                return False, content_reason
            # Headers present and content concrete — skip mode-based text
            # heuristics which are superseded by structural enforcement.
            logger.info(
                "[STRUCTURE-LOCK] satisfied — skipping mode-based checks "
                "(mode=%s escalation_level=%d)",
                mode.value,
                decision.escalation_level,
            )
            return True, "STRUCTURE_LOCK satisfied: all sections present with concrete content."

        if mode == IntegrationMode.NORMAL:
            return True, "No active mode constraint."

        if mode in (
            IntegrationMode.CONCRETE_OVERRIDE,
            IntegrationMode.PERSONALITY_SUPPRESSION,
        ):
            has_signal = any(s in t for s in _VALIDATE_CONCRETE_SIGNALS)
            pseudo = detect_pseudo_compliance(text)
            logger.info(
                "[INTEGRATION-PSEUDO-COMPLIANCE] detected=%s",
                pseudo,
            )
            if has_signal and not pseudo:
                return True, f"Active mode {mode.value}: concrete example detected."
            if pseudo:
                return (
                    False,
                    f"Active mode {mode.value}: pseudo-compliance detected — "
                    "response contains hypothetical language but lacks genuine concreteness.",
                )
            return (
                False,
                f"Active mode {mode.value}: no concrete example detected in response.",
            )

        if mode == IntegrationMode.RESOLUTION_OVERRIDE:
            if any(s in t for s in _VALIDATE_RESOLUTION_SIGNALS):
                return True, f"Active mode {mode.value}: resolution language detected."
            return (
                False,
                f"Active mode {mode.value}: no resolution language detected.",
            )

        if mode == IntegrationMode.ATTACK_OVERRIDE:
            if any(s in t for s in _VALIDATE_ATTACK_SIGNALS):
                return True, f"Active mode {mode.value}: structural challenge detected."
            return (
                False,
                f"Active mode {mode.value}: no structural challenge detected.",
            )

        if mode == IntegrationMode.LOW_COMPLEXITY:
            word_count = len(text.split())
            if word_count <= _LOW_COMPLEXITY_MAX_WORDS:
                return True, f"Active mode {mode.value}: response length {word_count} words is acceptable."
            return (
                False,
                f"Active mode {mode.value}: response too long ({word_count} words > {_LOW_COMPLEXITY_MAX_WORDS}).",
            )

        # Any other mode — no textual constraint defined, treat as compliant.
        return True, f"Active mode {mode.value}: no textual constraint defined."

    def should_regenerate_after_validation(
        self,
        text: str,
        decision: ControlDecision,
    ) -> bool:
        """Return True when the generated output ignored the active mode.

        Calls :meth:`validate_generated_output` and logs the result under
        ``[POST-GEN-VALIDATION]``.  Returns ``False`` immediately when the
        active mode is ``NORMAL`` (no constraint to validate).

        Also checks for pseudo-compliance in CONCRETE_OVERRIDE and
        PERSONALITY_SUPPRESSION modes, and forces regeneration with an
        incremented escalation level when found.

        Parameters
        ----------
        text:
            The generated response text to validate.
        decision:
            The :class:`ControlDecision` produced by
            :meth:`pre_generation_decision` for this generation step.

        Returns
        -------
        bool
            ``True`` when the response must be regenerated.
        """
        if (
            decision.active_mode == IntegrationMode.NORMAL
            and decision.escalation_level < _STRUCTURE_LOCK_LEVEL
        ):
            return False

        compliant, reason = self.validate_generated_output(text, decision)
        logger.info(
            "[POST-GEN-VALIDATION] mode=%s compliant=%s reason=%r",
            decision.active_mode.value,
            compliant,
            reason,
        )

        if not compliant:
            logger.warning(
                "[INTEGRATION-FORCE-REGEN] reason=%r escalation_level=%d",
                reason,
                decision.escalation_level,
            )

        return not compliant

    def build_stronger_overlay(self, decision: ControlDecision) -> str:
        """Return a stronger overlay directive for second-pass regeneration.

        Prepends :data:`_STRONGER_OVERLAY_PREFIX` to the original overlay so
        the model receives an escalated constraint that explicitly states a
        prior attempt was insufficient.

        Parameters
        ----------
        decision:
            The :class:`ControlDecision` whose overlay should be strengthened.

        Returns
        -------
        str
            Stronger imperative directive block.
        """
        return _STRONGER_OVERLAY_PREFIX + decision.prompt_overlay

    def escalate_decision(self, decision: ControlDecision) -> ControlDecision:
        """Return a new :class:`ControlDecision` with escalation incremented by 1.

        Used during the regeneration loop when the previous response failed
        validation.  The new decision carries:

        * ``escalation_level`` incremented by 1 (capped at
          :data:`EscalationLevel.HARD_OVERRIDE`)
        * A stronger ``prompt_overlay`` drawn from the escalation overlay table,
          prefixed with :data:`_FAILURE_MEMORY_PREFIX`
        * ``suppress_personality=True`` when the new level is ≥
          :data:`_ESCALATION_PERSONALITY_SUPPRESS_LEVEL`
        * ``regenerate=True`` so the caller knows it must retry

        Parameters
        ----------
        decision:
            The previous :class:`ControlDecision` that was non-compliant.

        Returns
        -------
        ControlDecision
            New escalated decision ready to drive the next generation attempt.
        """
        new_level = min(
            decision.escalation_level + 1,
            int(EscalationLevel.HARD_OVERRIDE),
        )
        suppress = new_level >= _ESCALATION_PERSONALITY_SUPPRESS_LEVEL

        overlay = _FAILURE_MEMORY_PREFIX + _ESCALATION_OVERLAYS.get(
            new_level,
            _OVERLAY_ESCALATION_4,
        )

        logger.info(
            "[INTEGRATION-ESCALATION] level=%d suppress_personality=%s",
            new_level,
            suppress,
        )

        return ControlDecision(
            allow_response=decision.allow_response,
            regenerate=True,
            suppress_personality=suppress,
            enforce_fixy=decision.enforce_fixy,
            force_concrete_mode=True,
            force_resolution_mode=decision.force_resolution_mode,
            force_attack_mode=decision.force_attack_mode,
            low_complexity_mode=decision.low_complexity_mode,
            prompt_overlay=overlay,
            decision_reason=(
                f"Escalation triggered: previous response was non-compliant. "
                f"escalation_level={new_level}."
            ),
            priority_level=decision.priority_level,
            active_mode=decision.active_mode,
            escalation_level=new_level,
        )

    def build_escalation_overlay(self, decision: ControlDecision) -> str:
        """Return the escalation overlay text for *decision*.

        Uses :attr:`ControlDecision.escalation_level` to select the
        appropriate overlay template from :data:`_ESCALATION_OVERLAYS`.
        When the level is 0 the method returns an empty string.

        Parameters
        ----------
        decision:
            A :class:`ControlDecision` with an ``escalation_level`` field.

        Returns
        -------
        str
            Escalation overlay text, or empty string for level 0.
        """
        overlay = _ESCALATION_OVERLAYS.get(decision.escalation_level, "")
        if overlay:
            logger.info(
                "[INTEGRATION-ESCALATION] level=%d overlay=%r",
                decision.escalation_level,
                overlay,
            )
        return overlay

    def record_response_hash(self, text: str) -> bool:
        """Record the reasoning hash of *text* and return True when a repeated
        reasoning structure is detected.

        Keeps a sliding window of recent hashes (up to
        :data:`_REASONING_HASH_SIMILARITY_THRESHOLD` + 1 entries).  If the
        same hash appears more than :data:`_REASONING_HASH_SIMILARITY_THRESHOLD`
        times in the window, repetition is flagged and the caller should force
        escalation immediately.

        Parameters
        ----------
        text:
            The generated response text.

        Returns
        -------
        bool
            ``True`` when repeated reasoning structure is detected.
        """
        h = _reasoning_hash(text)
        self._reasoning_hash_history.append(h)
        # Keep a bounded window — threshold + 2 so we can count up to threshold + 1
        # occurrences of the incoming hash before evicting old entries.
        if len(self._reasoning_hash_history) > _REASONING_HASH_HISTORY_SIZE:
            self._reasoning_hash_history = self._reasoning_hash_history[-_REASONING_HASH_HISTORY_SIZE:]

        repeat_count = self._reasoning_hash_history.count(h)
        repeated = repeat_count > _REASONING_HASH_SIMILARITY_THRESHOLD
        if repeated:
            logger.warning(
                "[INTEGRATION-FORCE-REGEN] reason='same_reasoning_hash' "
                "hash=%s count=%d",
                h,
                repeat_count,
            )
        return repeated

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
            k: v
            for k, v in state_dict.items()
            if k in valid_fields and k != "agent_name"
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
        # Determine escalation level based on loop_count
        lc = state.loop_count
        if lc >= _ESCALATION_LOOP_COUNT_LEVEL4:
            esc_level = int(EscalationLevel.HARD_OVERRIDE)
        elif lc >= _ESCALATION_LOOP_COUNT_LEVEL3:
            esc_level = int(EscalationLevel.FORMAT_ENFORCED)
        elif lc >= _ESCALATION_LOOP_COUNT_LEVEL2:
            esc_level = int(EscalationLevel.STRICT_CONCRETE)
        else:
            esc_level = int(EscalationLevel.CONCRETE_OVERRIDE)

        suppress = esc_level >= _ESCALATION_PERSONALITY_SUPPRESS_LEVEL
        escalation_overlay = _ESCALATION_OVERLAYS.get(esc_level, _OVERLAY_ESCALATION_1)

        reason = (
            f"Semantic repeat detected for '{state.agent_name}' "
            f"with loop_count={state.loop_count}. "
            f"Escalation level {esc_level} activated to break abstract repetition."
        )

        logger.info(
            "[INTEGRATION-ESCALATION] level=%d suppress_personality=%s",
            esc_level,
            suppress,
        )

        return ControlDecision(
            force_concrete_mode=True,
            suppress_personality=suppress,
            prompt_overlay=_OVERLAY_LOOP + " " + escalation_overlay,
            decision_reason=reason,
            priority_level=_PRIORITY_LOOP,
            active_mode=IntegrationMode.CONCRETE_OVERRIDE,
            escalation_level=esc_level,
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

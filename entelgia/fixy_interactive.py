#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Interactive Fixy for Entelgia
Need-based interventions rather than scheduled interventions.

v2.9.0: Added FixyMode enum and disruption strategies so that when the
DialogueLoopDetector flags a failure mode, Fixy forces novelty instead of
defaulting to generic mediation / synthesis language.
"""

import re
import logging
from collections import deque
from typing import Dict, List, Tuple, Any, Optional

# LLM Response Length Instruction
LLM_RESPONSE_LIMIT = "IMPORTANT: Please answer in maximum 150 words."

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Fixy response modes
# ---------------------------------------------------------------------------
# These modes determine *how* Fixy intervenes.  MEDIATE is the legacy
# behaviour.  All other modes introduce novelty to move the dialogue beyond
# a detected loop rather than summarising or bridging it.


class FixyMode:
    """Named constants for Fixy intervention modes.

    Staged intervention ladder (soft → deep):
      SILENT_OBSERVE      — Fixy observes but says nothing yet.
      SOFT_REFLECTION     — Gentle observation; reflects what the disagreement is about.
      GENTLE_NUDGE        — Points to a missing distinction or reframes the discussion.
      STRUCTURED_MEDIATION— Structured analysis of the disagreement with suggested vector.
      HARD_CONSTRAINT     — Deep structural reflection after extended unresolved tension (only after thresholds met).

    Legacy disruption modes remain for backward-compat with loop_guard policy.
    """

    # ── Staged intervention ladder ──────────────────────────────────────────
    SILENT_OBSERVE = "SILENT_OBSERVE"
    SOFT_REFLECTION = "SOFT_REFLECTION"
    GENTLE_NUDGE = "GENTLE_NUDGE"
    STRUCTURED_MEDIATION = "STRUCTURED_MEDIATION"
    HARD_CONSTRAINT = "HARD_CONSTRAINT"

    # ── Legacy / disruption modes ───────────────────────────────────────────
    MEDIATE = "MEDIATE"
    CONTRADICT = "CONTRADICT"
    CONCRETIZE = "CONCRETIZE"
    INVERT = "INVERT"
    PIVOT = "PIVOT"
    EXPOSE_SYNTHESIS = "EXPOSE_SYNTHESIS"
    FORCE_MECHANISM = "FORCE_MECHANISM"
    # Loop-breaking modes (added to ensure Fixy breaks loops, not amplifies them)
    FORCE_CONCRETE_EXAMPLE = "FORCE_CONCRETE_EXAMPLE"
    FORCE_COUNTEREXAMPLE = "FORCE_COUNTEREXAMPLE"
    FORCE_DIRECT_DISAGREEMENT = "FORCE_DIRECT_DISAGREEMENT"
    FORCE_TOPIC_RETURN = "FORCE_TOPIC_RETURN"
    FORCE_SHORT_ANSWER = "FORCE_SHORT_ANSWER"
    FORCE_NEW_DOMAIN = "FORCE_NEW_DOMAIN"
    # Structural rewrite modes — select the rewrite instruction injected into
    # the next agent's generation (issue requirement §7 / §8).
    FORCE_METRIC = "force_metric"
    FORCE_CHOICE = "force_choice"
    FORCE_TEST = "force_test"
    FORCE_CASE = "force_case"
    FORCE_DEFINITION = "force_definition"


# ---------------------------------------------------------------------------
# Deep-intervention threshold constants
# ---------------------------------------------------------------------------
# Fixy must NOT use deeper intervention modes (surfacing hidden assumptions,
# naming structural patterns, probing unexamined variables) before these
# thresholds are reached.
MIN_TURNS_BEFORE_FIXY_HARD_INTERVENTION: int = 8
MIN_FULL_PAIRS_BEFORE_FIXY_HARD_INTERVENTION: int = 3

# Set of modes considered "hard" — blocked until thresholds are reached.
_HARD_INTERVENTION_MODES: frozenset = frozenset(
    {
        FixyMode.CONTRADICT,
        FixyMode.FORCE_CHOICE,
        FixyMode.FORCE_DIRECT_DISAGREEMENT,
        FixyMode.FORCE_SHORT_ANSWER,
        FixyMode.FORCE_COUNTEREXAMPLE,
        FixyMode.EXPOSE_SYNTHESIS,
        FixyMode.HARD_CONSTRAINT,
    }
)


# Policy: loop failure mode → preferred Fixy mode
# (imported lazily to avoid circular import — loop_guard must not import fixy)
_LOOP_MODE_POLICY: Dict[str, str] = {
    "loop_repetition": FixyMode.FORCE_CONCRETE_EXAMPLE,
    "weak_conflict": FixyMode.FORCE_DIRECT_DISAGREEMENT,
    "premature_synthesis": FixyMode.EXPOSE_SYNTHESIS,
    "topic_stagnation": FixyMode.FORCE_NEW_DOMAIN,
    "fixy_mediation_loop": FixyMode.FORCE_SHORT_ANSWER,
}

# Rotation list for loop_repetition / fixy_mediation_loop — cycles through
# different breaking strategies so Fixy never repeats the same move twice.
_LOOP_BREAKING_MODES: List[str] = [
    FixyMode.FORCE_CONCRETE_EXAMPLE,
    FixyMode.FORCE_COUNTEREXAMPLE,
    FixyMode.FORCE_DIRECT_DISAGREEMENT,
    FixyMode.FORCE_NEW_DOMAIN,
    FixyMode.FORCE_SHORT_ANSWER,
    FixyMode.CONCRETIZE,
    FixyMode.CONTRADICT,
    FixyMode.PIVOT,
    FixyMode.FORCE_TOPIC_RETURN,
    FixyMode.FORCE_METRIC,
    FixyMode.FORCE_CHOICE,
    FixyMode.FORCE_TEST,
    FixyMode.FORCE_CASE,
    FixyMode.FORCE_DEFINITION,
]

# Mapping from loop failure mode → rewrite mode for next-agent injection
# Each loop type has a preferred structural rewrite mode that forces
# the next agent to advance along a specific dimension.
_LOOP_REWRITE_MODE_POLICY: Dict[str, str] = {
    "loop_repetition": FixyMode.FORCE_CASE,  # break repetition with a grounded case
    "weak_conflict": FixyMode.FORCE_CHOICE,  # resolve soft conflict with binary pick
    "premature_synthesis": FixyMode.FORCE_TEST,  # challenge synthesis with a testable claim
    "topic_stagnation": FixyMode.FORCE_METRIC,  # break stagnation with a new criterion
    "fixy_mediation_loop": FixyMode.FORCE_DEFINITION,  # clarify what's being argued
    "circular_reasoning": FixyMode.FORCE_CASE,
    "high_conflict_no_resolution": FixyMode.FORCE_CHOICE,
    "shallow_discussion": FixyMode.FORCE_TEST,
    "synthesis_opportunity": FixyMode.FORCE_METRIC,
}

# Structural rewrite directives — one per FORCE_* mode.
# Injected verbatim into the next agent's seed to force structural advancement.
# Defined at module level so it is not recreated on every get_rewrite_hint call.
_REWRITE_DIRECTIVES: Dict[str, str] = {
    FixyMode.FORCE_METRIC: (
        "Your next response MUST introduce a measurable criterion, benchmark, "
        "or quantifiable indicator. Do NOT argue without a metric."
    ),
    FixyMode.FORCE_CHOICE: (
        "Your next response MUST commit to one side of the binary. "
        "Pick a position and state exactly why the other fails. Do NOT hedge."
    ),
    FixyMode.FORCE_TEST: (
        "Your next response MUST propose a testable, falsifiable prediction. "
        "State what observable outcome would refute the claim."
    ),
    FixyMode.FORCE_CASE: (
        "Your next response MUST ground the argument in one specific real-world "
        "case, scenario, or historical instance. Do NOT generalize."
    ),
    FixyMode.FORCE_DEFINITION: (
        "Your next response MUST provide an operational definition for the "
        "central contested term. Define precisely what counts as an instance."
    ),
}

# Condition-based output framing — maps each intervention reason to a natural
# mediation style instruction.  Defined at module level so it is not recreated
# on every generate_intervention call.
# Do NOT use rigid police-style labels like "Deadlock:" or "Next move:".
# Instead, sound like a sharp mediator or theorist of the disagreement.
_REASON_LABEL_MAP: Dict[str, str] = {
    "loop_repetition": (
        "Do NOT use 'Deadlock:' or 'Loop:' or 'Next move:'. "
        "Begin with a phrase like 'It seems both are circling the same point...' "
        "or 'What remains unclear is whether...' "
        "The unspoken gap between both positions may be what deserves attention."
    ),
    "weak_conflict": (
        "Do NOT use 'Deadlock:'. "
        "Begin with 'It seems the disagreement is really about...' "
        "or 'Both of you may be using this concept in different senses...' "
        "The hidden fork in the argument may not yet be visible to either side."
    ),
    "premature_synthesis": (
        "Do NOT use 'Deadlock:' or 'Loop:'. "
        "Begin with 'A missing distinction here may be...' "
        "or 'The synthesis claimed here may paper over...' "
        "The tension the synthesis skips may still be worth examining."
    ),
    "topic_stagnation": (
        "Do NOT use 'Drift:'. "
        "Begin with 'What remains unaddressed in this exchange is...' "
        "or 'The conversation seems anchored to a single frame...' "
        "A different conceptual angle may be what this exchange has not yet considered."
    ),
    "circular_reasoning": (
        "Do NOT use 'Loop:' or 'Next move:'. "
        "Begin with 'It seems both positions are grounded in the same assumption...' "
        "or 'A missing variable here is...' "
        "The hidden shared premise may be what remains unexamined by both sides."
    ),
    "high_conflict_no_resolution": (
        "Do NOT use 'Deadlock:'. "
        "Begin with 'It seems the disagreement is really about...' "
        "or 'Both of you may be using X in different senses...' "
        "The structure of the conflict itself may deserve more attention than its conclusions."
    ),
    "shallow_discussion": (
        "Do NOT use 'Loop:' or 'Next move:'. "
        "Begin with 'What remains unclear is whether...' "
        "or 'A missing distinction here may be...' "
        "What neither side has yet examined may be where the depth lies."
    ),
    "synthesis_opportunity": (
        "Do NOT use 'Deadlock:'. "
        "Begin with 'It seems the disagreement is really about...' "
        "or 'There may be a distinction neither side has named yet...' "
        "A conceptual bridge between both positions may exist but has not yet been named."
    ),
    "fixy_mediation_loop": (
        "Do NOT repeat bridging or mediation language. "
        "Begin with 'What remains unclear is whether...' "
        "or 'A missing distinction here may be...' "
        "A different frame may be what this exchange has not yet considered."
    ),
}


_FIXY_FORBIDDEN_CONCEPTS: List[str] = [
    "ethics",
    "monitoring",
    "adaptive learning",
    "societal values",
    "ethical framework",
    "societal impact",
    "ethical considerations",
    "balance",
    "integration",
    "synthesis",
    "both are needed",
    "complement each other",
]
_FIXY_FORBIDDEN_CONCEPTS_INSTRUCTION: str = (
    "FORBIDDEN CONCEPTS: Do NOT use or repeat these words/phrases in your response: "
    + ", ".join(_FIXY_FORBIDDEN_CONCEPTS)
    + ". Use fresh vocabulary and concrete specifics."
)

# Reasons that trigger rotation through all loop-breaking strategies
_ROTATION_TRIGGER_REASONS: frozenset = frozenset(
    {"loop_repetition", "fixy_mediation_loop", "circular_reasoning"}
)

# Number of recent Fixy intervention texts to retain for deduplication.
# The prompt instructs the LLM not to repeat the same framings or examples
# used in the last _INTERVENTION_DEDUP_WINDOW interventions.
_INTERVENTION_DEDUP_WINDOW: int = 4

# ---------------------------------------------------------------------------
# force_choice response validation
# ---------------------------------------------------------------------------
# Commitment markers: signal that the agent has explicitly chosen one side.
_FC_COMMITMENT_MARKERS: List[str] = [
    "i choose",
    "i pick",
    "i select",
    "is wrong because",
    "is false because",
    "is incorrect because",
    "i reject",
    "i dismiss",
    "wins because",
    "fails because",
    "is stronger because",
    "is better because",
    "is weaker because",
    "is worse because",
    "not the answer",
    "the answer is",
    "my position is",
    "i commit to",
    "clearly wrong",
    "clearly right",
    "clearly superior",
    "clearly inferior",
    ", not because",
    ", not the",
    "rather than",
]

# Heavy hedge markers: signal that the agent avoided making a real choice.
_FC_HEDGE_MARKERS: List[str] = [
    "both matter",
    "both are important",
    "both are valid",
    "both have merit",
    "both contribute",
    "it depends",
    "depends on context",
    "we need both",
    "balance between",
    "balanced approach",
    "third path",
    "third option",
    "third way",
    "neither extreme",
]


def validate_force_choice(text: str) -> bool:
    """Return True when *text* contains a genuine commitment structure.

    A valid force_choice response must:
      1. Contain at least one explicit commitment marker, AND
      2. Not be dominated by heavy hedging (fewer than 2 hedge markers).

    This is a lightweight heuristic; it does not require semantic parsing.

    Parameters
    ----------
    text:
        The agent response to validate.

    Returns
    -------
    ``True`` when the response satisfies the force_choice requirement.
    """
    t = text.lower()
    has_commitment = any(m in t for m in _FC_COMMITMENT_MARKERS)
    hedge_count = sum(1 for m in _FC_HEDGE_MARKERS if m in t)
    # Fail if no commitment found, or if two or more distinct hedge phrases
    # are present (suggesting the agent blended rather than chose).
    return has_commitment and hedge_count < 2


# Mode-specific prompt templates
# {context} is replaced with the last 6 turns of dialogue
_MODE_PROMPTS: Dict[str, str] = {
    # ── Staged intervention ladder (soft → hard) ────────────────────────────
    FixyMode.SOFT_REFLECTION: (
        "You are Fixy, a sharp mediator and pattern-sensitive observer.\n"
        "The real disagreement may concern a distinction that neither side has yet named.\n"
        "Sound like a theorist of this specific disagreement, not a validator.\n"
        "Begin with one of: 'It seems the disagreement is really about...' / "
        "'What remains unclear is whether...' / "
        "'Both of you may be using this concept in different senses...'\n"
        "Do NOT use 'Deadlock:', 'Loop:', 'Next move:', or any prescriptive label.\n"
        "Max 2–3 short sentences. Do NOT summarize or recycle dialogue content."
    ),
    FixyMode.GENTLE_NUDGE: (
        "You are Fixy, a sharp mediator and pattern-sensitive observer.\n"
        "A missing distinction or variable may be what neither side has yet named.\n"
        "Begin with one of: 'A missing distinction here may be...' / "
        "'What neither side has yet examined is...' / "
        "'There may be a variable that changes everything here...'\n"
        "Do NOT use 'Deadlock:', 'Loop:', 'Next move:', or rigid police-style labels.\n"
        "Preserve productive tension. Do NOT push for premature closure.\n"
        "Max 2–3 short sentences. Do NOT moralize."
    ),
    FixyMode.STRUCTURED_MEDIATION: (
        "You are Fixy, a sharp mediator and pattern-sensitive observer.\n"
        "The disagreement may have a structural dimension that neither side has named.\n"
        "Begin with 'It seems the disagreement is really about...' "
        "Then identify what is missing: 'A missing distinction here may be...'\n"
        "Do NOT use 'Deadlock:', 'Loop:', 'Next move:'. Do NOT force a verdict. "
        "Do NOT guide the next step explicitly.\n"
        "Max 3 sentences. Sound like a theorist, not a policy engine."
    ),
    FixyMode.HARD_CONSTRAINT: (
        "You are Fixy, a sharp mediator and pattern-sensitive observer.\n"
        "The dialogue has persisted long enough to reveal its underlying structural tensions.\n"
        "Begin with 'It seems the tension here is fundamentally between...' "
        "or 'What remains unresolved beneath the surface is...'\n"
        "Do NOT instruct, prescribe, or propose next steps. Illuminate the structure of the disagreement.\n"
        "Max 3 short sentences. Sound like a thinker inside the dialogue, not an arbiter above it."
    ),
    # ── Legacy / default mode ──────────────────────────────────────────────
    FixyMode.MEDIATE: (
        "You are Fixy, a sharp mediator and pattern-sensitive observer.\n"
        "Reflect what the real disagreement is about. Identify what is missing.\n"
        "Begin with 'It seems the disagreement is really about...' "
        "or 'A missing distinction here may be...'\n"
        "Do NOT use rigid labels like 'Deadlock:', 'Loop:', 'Next move:'.\n"
        "Max 3 short sentences. Do NOT summarize or recycle dialogue content. Do NOT moralize."
    ),
    FixyMode.CONTRADICT: (
        "You are Fixy, a sharp mediator and pattern-sensitive observer.\n"
        "A genuine contradiction is being softened into apparent agreement.\n"
        "Begin with 'It seems the disagreement is really about...' "
        "or 'Both of you may be using this concept in different senses...'\n"
        "Do NOT use 'Deadlock:' or 'Next move:'. Max 3 short sentences. Do NOT bridge or reconcile."
    ),
    FixyMode.CONCRETIZE: (
        "You are Fixy, a sharp mediator and pattern-sensitive observer.\n"
        "The exchange has remained abstract without concrete grounding.\n"
        "Begin with 'A missing distinction here may be...' or "
        "'What neither side has yet examined is a specific instance...'\n"
        "Max 3 short sentences. Do NOT summarize the dialogue."
    ),
    FixyMode.INVERT: (
        "You are Fixy, a sharp mediator and pattern-sensitive observer.\n"
        "One view has been repeated without genuine challenge.\n"
        "Begin with 'What remains unclear is what the strongest objection to this position would be...' "
        "or 'A missing distinction may emerge if the dominant view is tested against...'\n"
        "Max 3 short sentences. Do NOT recycle dialogue content."
    ),
    FixyMode.PIVOT: (
        "You are Fixy, a sharp mediator and pattern-sensitive observer.\n"
        "The conversation appears locked within one conceptual domain.\n"
        "Begin with 'What remains unaddressed is...' "
        "or 'The conversation seems anchored to a single frame...'\n"
        "Max 3 short sentences. Do NOT philosophize or prescribe a direction."
    ),
    FixyMode.EXPOSE_SYNTHESIS: (
        "You are Fixy, a sharp mediator and pattern-sensitive observer.\n"
        "A synthesis has been claimed without resolving the underlying contradiction.\n"
        "Begin with 'A missing distinction here may be...' "
        "or 'The synthesis claimed here may paper over...'\n"
        "Max 3 short sentences. Do NOT accept the synthesis. Do NOT recycle dialogue content."
    ),
    FixyMode.FORCE_MECHANISM: (
        "You are Fixy, a sharp mediator and pattern-sensitive observer.\n"
        "Claims are being made without a stated causal mechanism.\n"
        "Begin with 'A missing variable here is the causal chain from...' "
        "or 'What remains unclear is how one leads to the other...'\n"
        "Max 3 short sentences. Do NOT prescribe a mechanism or direct next steps."
    ),
    FixyMode.FORCE_CONCRETE_EXAMPLE: (
        "You are Fixy, a sharp mediator and pattern-sensitive observer.\n"
        "The exchange has remained abstract without any real-world grounding.\n"
        "Begin with 'What neither side has yet examined is a specific real-world instance...' "
        "or 'A missing distinction may become visible in a concrete situation where...'\n"
        "Max 3 short sentences. Do NOT summarize or moralize."
    ),
    FixyMode.FORCE_COUNTEREXAMPLE: (
        "You are Fixy, a sharp mediator and pattern-sensitive observer.\n"
        "A central assertion has not been subjected to a disconfirming case.\n"
        "Begin with 'A missing variable here is a case where this claim does not hold...' "
        "or 'What remains unclear is whether this position survives a situation where...'\n"
        "Max 3 short sentences. Do NOT resolve or prescribe an answer."
    ),
    FixyMode.FORCE_DIRECT_DISAGREEMENT: (
        "You are Fixy, a sharp mediator and pattern-sensitive observer.\n"
        "The exchange has converged toward agreement without naming the underlying tension.\n"
        "Begin with 'It seems the disagreement is really about...' "
        "or 'Both of you may be using this concept in different senses...'\n"
        "Max 3 short sentences. Do NOT reconcile or bridge the positions."
    ),
    FixyMode.FORCE_TOPIC_RETURN: (
        "You are Fixy, a sharp mediator and pattern-sensitive observer.\n"
        "The conversation has drifted from its original question.\n"
        "Begin with 'What remains unaddressed is the original question of...' "
        "or 'A tension emerges when the current frame is held against what was first asked...'\n"
        "Max 3 short sentences. Do NOT moralize or prescribe a direction."
    ),
    FixyMode.FORCE_SHORT_ANSWER: (
        "You are Fixy, a sharp mediator and pattern-sensitive observer.\n"
        "A central question has gone unanswered in the exchange.\n"
        "Begin with 'What remains unclear is whether...' "
        "followed by a precise articulation of the unresolved question.\n"
        "Max 2 short sentences. Do NOT prescribe an answer."
    ),
    FixyMode.FORCE_NEW_DOMAIN: (
        "You are Fixy, a sharp mediator and pattern-sensitive observer.\n"
        "The conversation appears anchored to a single conceptual cluster.\n"
        "Begin with 'The conversation seems anchored to a single frame...' "
        "or 'A tension emerges when this argument is held against a different domain...'\n"
        "Max 3 short sentences. Do NOT moralize or prescribe a next step."
    ),
    FixyMode.FORCE_METRIC: (
        "You are Fixy, a sharp mediator and pattern-sensitive observer.\n"
        "No measurable criterion or benchmark has appeared in the exchange.\n"
        "Begin with 'A missing variable here is a measurable criterion for...' "
        "or 'What remains unclear is how either position could be evaluated against...'\n"
        "Max 3 short sentences. Do NOT prescribe what to measure."
    ),
    FixyMode.FORCE_CHOICE: (
        "You are Fixy, a sharp mediator and pattern-sensitive observer.\n"
        "Both positions are held simultaneously without genuine conflict.\n"
        "Begin with 'It seems the disagreement is really about...' "
        "or 'A tension emerges when both views are held at once — specifically...'\n"
        "Max 3 short sentences. Do NOT resolve the tension or prescribe a commitment."
    ),
    FixyMode.FORCE_TEST: (
        "You are Fixy, a sharp mediator and pattern-sensitive observer.\n"
        "The exchange contains claims that have not yet been grounded empirically.\n"
        "Begin with 'A missing variable here is a testable prediction for...' "
        "or 'What remains unclear is what observable difference would follow from...'\n"
        "Max 3 short sentences. Do NOT demand proof or prescribe a test."
    ),
    FixyMode.FORCE_CASE: (
        "You are Fixy, a sharp mediator and pattern-sensitive observer.\n"
        "The reasoning has remained at an abstract level with no grounded instance.\n"
        "Begin with 'A missing distinction may be visible in a specific historical or situational case where...' "
        "or 'Both of you may be assuming something that a particular case would complicate...'\n"
        "Max 3 short sentences. Do NOT prescribe which case to examine."
    ),
    FixyMode.FORCE_DEFINITION: (
        "You are Fixy, a sharp mediator and pattern-sensitive observer.\n"
        "A central term is being used by both sides without a shared definition.\n"
        "Begin with 'Both of you may be using this term in different senses...' "
        "or 'What remains unclear is whether the same word is carrying different meanings...'\n"
        "Max 3 short sentences. Do NOT define the term or prescribe a resolution."
    ),
}

# ---------------------------------------------------------------------------
# Optional semantic similarity support (sentence-transformers)
# ---------------------------------------------------------------------------
try:
    from sentence_transformers import SentenceTransformer
    from sklearn.metrics.pairwise import cosine_similarity as _cosine_similarity
    import numpy as _np

    _SEMANTIC_MODEL: Optional[SentenceTransformer] = None
    _SEMANTIC_AVAILABLE = True
except ImportError:
    _SEMANTIC_AVAILABLE = False
    _SEMANTIC_MODEL = None
    _cosine_similarity = None  # type: ignore[assignment]


def _get_semantic_model():
    """Lazily load and cache the SentenceTransformer model."""
    global _SEMANTIC_MODEL
    if _SEMANTIC_MODEL is None:
        try:
            logger.info("Loading SentenceTransformer model 'all-MiniLM-L6-v2'…")
            _SEMANTIC_MODEL = SentenceTransformer("all-MiniLM-L6-v2")
            logger.info("SentenceTransformer model loaded.")
        except Exception as exc:  # pragma: no cover
            logger.warning("Could not load SentenceTransformer model: %s", exc)
    return _SEMANTIC_MODEL


def _semantic_similarity(text1: str, text2: str) -> float:
    """
    Compute cosine similarity between two texts using sentence embeddings.

    Returns a float in [0, 1], or 0.0 if the model is unavailable or fails.
    """
    if not _SEMANTIC_AVAILABLE:
        return 0.0
    model = _get_semantic_model()
    if model is None:
        return 0.0
    try:
        embeddings = model.encode([text1, text2])
        score = float(
            _cosine_similarity(
                embeddings[0].reshape(1, -1), embeddings[1].reshape(1, -1)
            )[0][0]
        )
        # cosine similarity is in [-1, 1]; clamp to [0, 1]
        return max(0.0, min(1.0, score))
    except Exception as exc:  # pragma: no cover
        logger.warning("Semantic similarity computation failed: %s", exc)
        return 0.0


def _encode_turns(turns: List[Dict[str, str]]):
    """
    Batch-encode all turn texts into sentence embeddings.

    Returns a numpy array of shape (n_turns, embedding_dim), or None if
    sentence-transformers is unavailable or encoding fails.
    """
    if not _SEMANTIC_AVAILABLE:
        return None
    model = _get_semantic_model()
    if model is None:
        return None
    try:
        texts = [t.get("text", "") for t in turns]
        return model.encode(texts)
    except Exception as exc:  # pragma: no cover
        logger.warning("Batch turn encoding failed: %s", exc)
        return None


class InteractiveFixy:
    """Fixy as active dialogue participant with intelligent interventions.

    v2.9.0: Fixy now selects a *disruption mode* based on the active failure
    mode detected by DialogueLoopDetector.  When a loop is active, Fixy uses
    FORCE_CONCRETE_EXAMPLE / FORCE_COUNTEREXAMPLE / FORCE_DIRECT_DISAGREEMENT /
    FORCE_NEW_DOMAIN / FORCE_SHORT_ANSWER / FORCE_TOPIC_RETURN (and legacy
    CONTRADICT / CONCRETIZE / EXPOSE_SYNTHESIS / PIVOT / FORCE_MECHANISM)
    instead of the default mediating style.  Modes rotate so Fixy never repeats
    the same breaking strategy in consecutive interventions.

    v4.0.0: Added pair gating (both Socrates and Athena must have spoken before
    evaluation), structural rewrite hint injection, and condition-based output.

    v4.2.0: Refactored into a staged intervention ladder (SOFT_REFLECTION →
    GENTLE_NUDGE → STRUCTURED_MEDIATION → HARD_CONSTRAINT).  Deeper interventions
    (surfacing hidden assumptions, naming structural tensions, introducing missing variables)
    are gated until configurable turn/pair thresholds are reached.  When NEW_CLAIM is
    present in recent turns, Fixy stays silent or uses only SOFT_REFLECTION.
    """

    # Minimum number of distinct main-agent turns required before Fixy may
    # evaluate.  This enforces the pair requirement without relying solely on
    # turn_count.
    _MIN_CONTEXT_TURNS: int = 2

    def __init__(
        self,
        llm,
        model: str,
        topics_enabled: bool = True,
        min_turns_hard: int = MIN_TURNS_BEFORE_FIXY_HARD_INTERVENTION,
        min_pairs_hard: int = MIN_FULL_PAIRS_BEFORE_FIXY_HARD_INTERVENTION,
    ):
        """
        Initialize Interactive Fixy.

        Args:
            llm: LLM instance for generating interventions
            model: Model name to use
            topics_enabled: Whether the topic subsystem is active.  When
                ``False``, any ``notify_pair_reset`` call with
                ``reason="topic_shift"`` is silently suppressed so that
                topic-related log entries never appear in a topics-disabled
                session.
            min_turns_hard: Minimum total turns before hard interventions are
                allowed.  Defaults to ``MIN_TURNS_BEFORE_FIXY_HARD_INTERVENTION``.
            min_pairs_hard: Minimum consecutive full-pair observations before
                hard interventions are allowed.  Defaults to
                ``MIN_FULL_PAIRS_BEFORE_FIXY_HARD_INTERVENTION``.
        """
        self.llm = llm
        self.model = model
        # Mirror of CFG.topics_enabled captured at construction time.
        # Used to gate topic-shift pair-window resets and topic-aware
        # prompt anchoring so that all topic-related behaviour is fully
        # suppressed when the topic subsystem is disabled.
        self._topics_enabled: bool = topics_enabled
        # Hard-intervention thresholds (configurable via constructor).
        self._min_turns_hard: int = min_turns_hard
        self._min_pairs_hard: int = min_pairs_hard
        # Counter for rotating through loop-breaking modes so Fixy never
        # repeats the same breaking strategy in consecutive interventions.
        self._loop_break_rotation: int = 0
        # Deque of recent intervention texts for deduplication; keeps the last
        # _INTERVENTION_DEDUP_WINDOW entries so the prompt can instruct the
        # LLM to avoid repeating the same examples or framings.
        self._recent_interventions: deque[str] = deque(
            maxlen=_INTERVENTION_DEDUP_WINDOW
        )
        # Last rewrite hint computed during should_intervene — consumed by the
        # caller to inject into the next agent's seed.
        self._pending_rewrite_hint: Optional[str] = None
        # Rewrite mode chosen for the pending hint.
        self._pending_rewrite_mode: Optional[str] = None
        # Set to True by should_intervene when a hard intervention was blocked
        # (NEW_CLAIM present or turn/pair thresholds not yet met).  Consumed by
        # get_fixy_mode to select a soft staged mode instead of a disruptive one.
        # Resets to False at the start of every should_intervene call.
        self._soft_mode_forced: bool = False

        # ── Pair-window tracking ──────────────────────────────────────────────
        # The pair gate must be evaluated only over the window since the last
        # boundary event (Fixy intervention, dream cycle, topic shift, or rewrite
        # injection).  _pair_window_start stores the dialog index (len of dialog
        # at the moment of the last external reset) for non-Fixy boundaries.
        # Fixy boundaries are detected automatically via dialog entries.
        self._pair_window_start: int = 0
        # Human-readable label of the most recent reset trigger (for logging).
        self._pair_reset_reason: str = ""
        # Counter: how many consecutive times the pair gate AND minimum-context
        # check both passed (i.e. "full pair observed" was reached).  Resets to
        # zero whenever either gate fails.  Used to gate the agent stop signal —
        # the stop signal is honoured only after 3 consecutive full-pair turns.
        self._consecutive_full_pair_count: int = 0

        # Lazy import to avoid circular dependency (loop_guard → no imports from fixy)
        try:
            from entelgia.loop_guard import DialogueLoopDetector

            self._loop_detector = DialogueLoopDetector()
        except ImportError:  # pragma: no cover
            self._loop_detector = None

    # ------------------------------------------------------------------
    # Pair-gating helper
    # ------------------------------------------------------------------

    @staticmethod
    def _both_agents_present(dialog: List[Dict[str, str]]) -> bool:
        """Return True when both Socrates and Athena have spoken in *dialog*."""
        roles = {t.get("role") for t in dialog if t.get("role") not in ("Fixy", "seed")}
        return "Socrates" in roles and "Athena" in roles

    def notify_pair_reset(self, dialog_length: int, reason: str = "") -> None:
        """Signal a pair-window boundary from an external event.

        Call this after dream cycles, topic shifts, or rewrite-hint injection
        so that Fixy waits for a fresh Socrates+Athena pair before evaluating
        again.  Fixy-intervention boundaries are detected automatically via
        Fixy dialog entries and do not require this call.

        Parameters
        ----------
        dialog_length:
            Current ``len(dialog)`` at the time of the event.  Turns at
            indices below this value are excluded from the current pair window.
        reason:
            Human-readable label for the triggering event (e.g.
            ``"dream_cycle"``, ``"topic_shift"``, ``"rewrite_injection"``).
        """
        # When the topic subsystem is disabled, topic-shift resets are
        # meaningless (there are no topic transitions to wait for) and would
        # produce misleading log entries.  Suppress them silently so that a
        # topics-disabled session never emits [FIXY-GATE] pair window reset
        # entries with reason=topic_shift.
        if reason == "topic_shift" and not self._topics_enabled:
            logger.debug(
                "[FIXY-GATE] pair window reset suppressed: reason=topic_shift"
                " (topics_enabled=False) dialog_idx=%d",
                dialog_length,
            )
            return
        self._pair_window_start = dialog_length
        self._pair_reset_reason = reason
        logger.info(
            "[FIXY-GATE] pair window reset: reason=%s dialog_idx=%d",
            reason or "external",
            dialog_length,
        )

    @property
    def consecutive_full_pair_count(self) -> int:
        """Number of consecutive turns where both pair and context gates passed.

        This counter increments each time :meth:`should_intervene` reaches the
        "full pair observed" checkpoint without either gate failing.  It resets
        to zero whenever the pair-presence gate or the minimum-context gate
        rejects the evaluation.  The main loop uses this to require at least 3
        consecutive full-pair turns before honouring an agent stop signal.
        """
        return self._consecutive_full_pair_count

    def should_intervene(
        self,
        dialog: List[Dict[str, str]],
        turn_count: int,
        current_topic: Optional[str] = None,
    ) -> Tuple[bool, str]:
        """
        Decide if intervention needed based on dialogue state.

        v2.9.0: First checks explicit loop failure modes via DialogueLoopDetector.
        Falls back to the existing heuristic patterns when no loop is active.

        v4.0.0: Added mandatory pair gating — Fixy will never evaluate after a
        single agent's turn.  Both Socrates AND Athena must have spoken.  Also
        clears the pending rewrite hint on each call.

        v4.0.1: Fixed pair-gating bug — the window is now scoped to turns
        since the last Fixy dialog entry OR the most recent external reset
        (dream cycle, topic shift, rewrite injection), whichever is later.
        This prevents the gate from being permanently open once both agents
        have spoken at any historical point.

        Args:
            dialog: Full dialogue history
            turn_count: Current turn number
            current_topic: Current topic label (optional; used for stagnation check)

        Returns:
            Tuple of (should_intervene, reason)
        """
        # Reset pending rewrite hint from the previous turn
        self._pending_rewrite_hint = None
        self._pending_rewrite_mode = None
        self._soft_mode_forced = False

        # When the topic subsystem is disabled, discard any topic label passed
        # by the caller so that stagnation detection and loop-guard logging
        # never reference topic strings in a topics-disabled session.
        if not self._topics_enabled:
            current_topic = None

        # ── Pair gating: require both main agents to have spoken since last reset ──
        # Compute the pair-window boundary: the later of (a) the index just after
        # the last Fixy dialog entry, and (b) the last external reset point.
        last_fixy_idx = -1
        for i, t in enumerate(dialog):
            if t.get("role") == "Fixy":
                last_fixy_idx = i
        window_start = max(last_fixy_idx + 1, self._pair_window_start)
        window = dialog[window_start:]

        if not self._both_agents_present(window):
            # Determine the most descriptive skip reason for logging.
            # Use a consistent human-readable format: underscores replaced by spaces.
            if self._pair_reset_reason:
                readable_reason = self._pair_reset_reason.replace("_", " ")
                skip_detail = f"pair window not complete after {readable_reason}"
            elif last_fixy_idx >= 0:
                skip_detail = "waiting for both agents"
            else:
                skip_detail = "waiting for both agents"
            self._consecutive_full_pair_count = 0
            logger.debug(
                "[FIXY-GATE] skipped: %s at turn %d",
                skip_detail,
                turn_count,
            )
            return (False, "")

        # ── Minimum context window ──────────────────────────────────────────
        agent_turns_all = [t for t in dialog if t.get("role") not in ("Fixy", "seed")]
        if len(agent_turns_all) < self._MIN_CONTEXT_TURNS:
            self._consecutive_full_pair_count = 0
            logger.info(
                "[FIXY-GATE] skipped: insufficient context (have %d agent turns, need %d) at turn %d",
                len(agent_turns_all),
                self._MIN_CONTEXT_TURNS,
                turn_count,
            )
            return (False, "")

        self._consecutive_full_pair_count += 1
        logger.info(
            "[FIXY-GATE] accepted: full pair observed at turn %d (consecutive=%d)",
            turn_count,
            self._consecutive_full_pair_count,
        )

        # ── Loop-guard checks (new v2.9.0) ─────────────────────────────────
        if self._loop_detector is not None:
            active_modes = self._loop_detector.detect(
                dialog, turn_count, current_topic=current_topic
            )
            if active_modes:
                primary = active_modes[0]

                # ── NEW_CLAIM gate: if new claims are still appearing, stay soft ──
                if self._detect_new_claim_in_recent_turns(agent_turns_all):
                    logger.info(
                        "[FIXY-SOFT] NEW_CLAIM detected in recent turns at turn %d"
                        " — using soft_reflection instead of hard intervention",
                        turn_count,
                    )
                    self._pending_rewrite_mode = None
                    self._soft_mode_forced = True
                    return (True, primary)

                # ── Hard-threshold gate: block hard modes before thresholds ────
                candidate_mode = _LOOP_REWRITE_MODE_POLICY.get(
                    primary, FixyMode.FORCE_CASE
                )
                hard_blocked = candidate_mode in _HARD_INTERVENTION_MODES and (
                    turn_count < self._min_turns_hard
                    or self._consecutive_full_pair_count < self._min_pairs_hard
                )
                if hard_blocked:
                    logger.info(
                        "[FIXY-SOFT] hard intervention blocked at turn %d"
                        " (need %d turns, %d pairs; have %d turns, %d pairs)"
                        " — using soft_reflection",
                        turn_count,
                        self._min_turns_hard,
                        self._min_pairs_hard,
                        turn_count,
                        self._consecutive_full_pair_count,
                    )
                    self._pending_rewrite_mode = None
                    self._soft_mode_forced = True
                    return (True, primary)

                # Select structural rewrite mode for the next agent's seed
                rewrite_mode = _LOOP_REWRITE_MODE_POLICY.get(
                    primary, FixyMode.FORCE_CASE
                )
                self._pending_rewrite_mode = rewrite_mode
                logger.info(
                    "[FIXY-LOOP] Loop detected: modes=%s turn=%d topic=%r → Fixy will break loop",
                    active_modes,
                    turn_count,
                    current_topic,
                )
                # Use the first (highest-priority) failure mode as the reason
                return (True, primary)
            else:
                logger.debug(
                    "[FIXY-GATE] skipped: insufficient structural repetition at turn %d",
                    turn_count,
                )

        # ── Legacy heuristic patterns (preserved for backward compat) ───────
        # Only analyse main-agent turns; excluding Fixy's own past interventions
        # prevents a feedback loop where Fixy's meta-commentary (which references
        # the dialogue topic and therefore has high semantic similarity) inflates
        # the repetition score and triggers yet more Fixy interventions.
        last_10 = (
            agent_turns_all[-10:] if len(agent_turns_all) >= 10 else agent_turns_all
        )

        # Before applying any legacy pattern, check NEW_CLAIM: if new claims are
        # still arriving, step back to soft reflection only.
        _new_claim_active = self._detect_new_claim_in_recent_turns(agent_turns_all)

        def _hard_allowed() -> bool:
            """Return True when the hard-intervention thresholds have been met."""
            return (
                turn_count >= self._min_turns_hard
                and self._consecutive_full_pair_count >= self._min_pairs_hard
            )

        # Pattern 1: Circular reasoning (repetition)
        if self._detect_repetition(last_10):
            if not _new_claim_active and _hard_allowed():
                self._pending_rewrite_mode = FixyMode.FORCE_CASE
            else:
                self._pending_rewrite_mode = None
                self._soft_mode_forced = True
            return (True, "circular_reasoning")

        # Pattern 2: High conflict without synthesis (check every 6+ turns)
        if turn_count >= 6 and self._detect_high_conflict(last_10):
            if not _new_claim_active and _hard_allowed():
                self._pending_rewrite_mode = FixyMode.FORCE_CHOICE
            else:
                self._pending_rewrite_mode = None
                self._soft_mode_forced = True
            return (True, "high_conflict_no_resolution")

        # Pattern 3: Surface-level discussion for too long
        if turn_count >= 10 and self._detect_shallow_discussion(last_10):
            if not _new_claim_active and _hard_allowed():
                self._pending_rewrite_mode = FixyMode.FORCE_TEST
            else:
                self._pending_rewrite_mode = None
                self._soft_mode_forced = True
            return (True, "shallow_discussion")

        # Pattern 4: Missed synthesis opportunity
        if turn_count >= 5 and self._detect_synthesis_opportunity(last_10):
            if not _new_claim_active and _hard_allowed():
                self._pending_rewrite_mode = FixyMode.FORCE_METRIC
            else:
                self._pending_rewrite_mode = None
                self._soft_mode_forced = True
            return (True, "synthesis_opportunity")

        # Pattern 5: Meta-reflection needed (every 15 turns)
        if turn_count > 15 and turn_count % 15 == 0:
            return (True, "meta_reflection_needed")

        return (False, "")

    def get_fixy_mode(self, reason: str) -> str:
        """Return the FixyMode that best matches *reason*.

        When ``should_intervene`` set ``_soft_mode_forced=True`` (because a
        NEW_CLAIM is present or hard turn/pair thresholds are not yet met),
        returns a soft staged mode instead of a hard disruption mode.  This
        ensures Fixy reflects rather than enforces during early dialogue turns.

        Loop-guard reasons that signal repetition rotate through all loop-breaking
        modes so Fixy never repeats the same strategy twice in a row.
        Legacy reasons use MEDIATE (the neutral default).

        Args:
            reason: Intervention reason string

        Returns:
            One of the FixyMode constants
        """
        # When should_intervene forced soft mode (hard blocked or NEW_CLAIM present),
        # select a staged soft mode based on how many consecutive pair-turns we have.
        if self._soft_mode_forced:
            pairs = self._consecutive_full_pair_count
            if pairs <= 1:
                soft_mode = FixyMode.SOFT_REFLECTION
            elif pairs <= 2:
                soft_mode = FixyMode.GENTLE_NUDGE
            else:
                soft_mode = FixyMode.STRUCTURED_MEDIATION
            logger.debug(
                "[FIXY-MODE] reason=%r → soft mode=%s (pairs=%d, hard threshold not reached)",
                reason,
                soft_mode,
                pairs,
            )
            return soft_mode

        if reason in _ROTATION_TRIGGER_REASONS:
            mode = _LOOP_BREAKING_MODES[
                self._loop_break_rotation % len(_LOOP_BREAKING_MODES)
            ]
            self._loop_break_rotation += 1
            logger.debug(
                "[FIXY-MODE] reason=%r → rotating loop-break mode=%s (rotation=%d)",
                reason,
                mode,
                self._loop_break_rotation,
            )
            return mode
        return _LOOP_MODE_POLICY.get(reason, FixyMode.MEDIATE)

    def get_rewrite_hint(
        self,
        active_modes: List[str],
        rewrite_mode: Optional[str],
        target_agent: Optional[str],
    ) -> str:
        """Return a structural rewrite hint to inject into the next agent's seed.

        This is the companion to ``generate_intervention``: while the
        intervention is Fixy's spoken commentary appended to the dialogue,
        the rewrite hint is a silent directive prepended to the *next*
        agent's generation prompt.  It forces structural advancement (new
        metric, forced choice, concrete test, etc.) rather than allowing the
        agent to restate the same idea.

        The hint is consumed by the caller (MainScript.run) immediately after
        Fixy's intervention and stored in ``self._pending_rewrite_hint`` so it
        survives until the next agent's seed is built.

        Parameters
        ----------
        active_modes:
            Loop failure modes active during this intervention.
        rewrite_mode:
            One of the ``FORCE_*`` FixyMode constants (e.g. ``"force_metric"``).
            When ``None``, the hint selects a default based on ``active_modes``.
        target_agent:
            Name of the next agent to receive the hint (for logging).

        Returns
        -------
        A multi-line directive string or ``""`` when no rewrite is needed.
        """
        if not active_modes and not rewrite_mode:
            return ""

        effective_mode = rewrite_mode
        if effective_mode is None and active_modes:
            effective_mode = _LOOP_REWRITE_MODE_POLICY.get(
                active_modes[0], FixyMode.FORCE_CASE
            )

        logger.info(
            "[FIXY-REWRITE] mode=%s target=%s active_modes=%s",
            effective_mode,
            target_agent,
            active_modes,
        )

        directive = _REWRITE_DIRECTIVES.get(
            effective_mode or "",
            "Your next response MUST introduce something genuinely new: a new variable, "
            "forced decision, or concrete test. Do NOT restate the same idea.",
        )

        lines = [
            "--- FIXY STRUCTURAL REWRITE DIRECTIVE ---",
            f"Rewrite mode: {effective_mode}",
        ]
        if target_agent:
            lines.append(f"Target: {target_agent}")
        lines += [
            "",
            directive,
            "",
            "This directive takes priority over your default framing.",
            "--- END FIXY REWRITE DIRECTIVE ---",
        ]

        hint = "\n".join(lines)
        self._pending_rewrite_hint = hint
        return hint

    def generate_intervention(
        self,
        dialog: List[Dict[str, str]],
        reason: str,
        mode: Optional[str] = None,
        current_topic: Optional[str] = None,
    ) -> str:
        """
        Generate contextual intervention using the appropriate Fixy mode.

        v2.9.0: When *reason* maps to a loop failure mode, Fixy selects a
        disruptive mode (CONTRADICT, CONCRETIZE, etc.) instead of the
        default mediating style, ensuring it does not reinforce loops.

        v3.0.0: Accepts *current_topic* to anchor the intervention to the
        active dialogue topic, reducing TOPIC-MISMATCH failures.  Also
        tracks recent intervention texts to avoid repeating the same
        examples or framings across consecutive calls.

        v4.0.0: Output is condition-based: labels ('Loop:', 'Deadlock:',
        'Missing variable:') appear only when the corresponding failure is
        present.  The output type instruction now reflects the active reason
        so Fixy does not produce a fixed template regardless of context.

        Args:
            dialog: Dialogue history
            reason: Reason for intervention
            mode: Override FixyMode (optional; auto-selected from reason if omitted)
            current_topic: Active topic label (optional; included in prompt when provided)

        Returns:
            Intervention text
        """
        context = self._build_intervention_context(dialog, reason)

        # When topics are disabled, topic anchoring in the intervention prompt
        # would reference topic labels that are not active in the session.
        # Discard the caller-supplied topic so no ACTIVE TOPIC instruction is
        # injected into the Fixy prompt.
        if not self._topics_enabled:
            current_topic = None

        # Select Fixy mode — loop-guard reasons override legacy behaviour
        if mode is None:
            mode = self.get_fixy_mode(reason)

        # Use disruption prompt when mode is non-mediation; fall back for legacy reasons
        if mode in _MODE_PROMPTS:
            prompt_template = _MODE_PROMPTS[mode]
        else:
            # Legacy fallback prompts for reasons not covered by _MODE_PROMPTS
            legacy_prompts = {
                "circular_reasoning": _MODE_PROMPTS[FixyMode.CONCRETIZE],
                "high_conflict_no_resolution": _MODE_PROMPTS[FixyMode.GENTLE_NUDGE],
                "shallow_discussion": (
                    "You are Fixy, a sharp mediator and pattern-sensitive observer.\n"
                    "The exchange has remained at a surface level without reaching depth.\n"
                    "Begin with 'What neither side has yet examined is...' "
                    "or 'A missing distinction here may be...'\n"
                    "Do NOT use 'Loop:', 'Next move:', or rigid labels.\n"
                    "Max 3 short sentences. Do NOT summarize dialogue content."
                ),
                "synthesis_opportunity": _MODE_PROMPTS[FixyMode.EXPOSE_SYNTHESIS],
                "meta_reflection_needed": (
                    "You are Fixy, a sharp mediator and pattern-sensitive observer.\n"
                    "The dialogue has not evolved beyond its initial framing.\n"
                    "Begin with 'What remains unaddressed is...' "
                    "or 'The conversation seems anchored to a single frame...'\n"
                    "Do NOT use 'Drift:', 'Next move:', or rigid labels.\n"
                    "Max 3 short sentences. Do NOT moralize or prescribe policy."
                ),
            }
            prompt_template = legacy_prompts.get(
                reason, _MODE_PROMPTS[FixyMode.MEDIATE]
            )

        # Build condition-based output instruction using the module-level map.
        # Instructs the LLM to use natural mediation language, not rigid labels.
        output_instruction = _REASON_LABEL_MAP.get(
            reason,
            "Sound like a sharp mediator or theorist of this disagreement. "
            "Do NOT use rigid labels like 'Deadlock:', 'Loop:', or 'Next move:'. "
            "Begin with a reflective observation about the structure of the exchange.",
        )

        # Build topic anchor instruction when a topic is active
        topic_instruction = ""
        if current_topic:
            topic_instruction = (
                f"ACTIVE TOPIC: {current_topic}. "
                f"Your intervention MUST be directly relevant to this topic. "
                f"Do NOT drift to unrelated domains or generic examples.\n"
            )

        # Build deduplication instruction from recent intervention history
        dedup_instruction = ""
        if self._recent_interventions:
            prior_examples = "; ".join(
                f'"{t[:80]}..."' if len(t) > 80 else f'"{t}"'
                for t in self._recent_interventions
            )
            dedup_instruction = (
                f"AVOID REPETITION: Do NOT reuse the framing, examples, or scenarios "
                f"from your previous interventions: {prior_examples}. "
                f"Use a completely different angle.\n"
            )

        full_prompt = (
            f"{prompt_template}\n\n"
            f"{topic_instruction}"
            f"{dedup_instruction}"
            f"RECENT DIALOGUE:\n{context}\n\n"
            f"Output rule: {output_instruction}\n"
            f"Max 3 short sentences. Do NOT recycle dialogue content. Do NOT prescribe policy.\n"
            f"{_FIXY_FORBIDDEN_CONCEPTS_INSTRUCTION}\n"
            f"{LLM_RESPONSE_LIMIT}\n"
        )

        intervention = self.llm.generate(
            self.model, full_prompt, temperature=0.4, use_cache=False
        )

        result = (
            intervention.strip()
            if intervention
            else "I notice we might benefit from a fresh perspective here."
        )

        # Track this intervention for future deduplication
        self._recent_interventions.append(result)
        return result

    def _build_intervention_context(
        self, dialog: List[Dict[str, str]], reason: str
    ) -> str:
        """
        Build context string for intervention.

        Args:
            dialog: Dialogue history
            reason: Intervention reason

        Returns:
            Formatted context string
        """
        # Get last 6 turns for context
        recent = dialog[-6:] if len(dialog) >= 6 else dialog

        context_lines = []
        for turn in recent:
            role = turn.get("role", "")
            text = turn.get("text", "")
            context_lines.append(f"{role}: {text}")

        return "\n".join(context_lines)

    def _detect_repetition(self, turns: List[Dict[str, str]]) -> bool:
        """
        Detect if same concepts repeated 3+ times.

        Args:
            turns: Recent dialogue turns

        Returns:
            True if repetition detected
        """
        if len(turns) < 4:
            return False

        # Extract key words from each turn (words > 4 chars)
        turn_keywords = []
        for turn in turns:
            text = turn.get("text", "").lower()
            words = set(w for w in re.findall(r"\w+", text) if len(w) > 4)
            turn_keywords.append(words)

        # Batch-encode all turns once to avoid redundant computation in the inner loop
        turn_embeddings = _encode_turns(turns) if _SEMANTIC_AVAILABLE else None

        # Check for high overlap between multiple turns
        high_overlap_count = 0
        for i in range(len(turn_keywords) - 1):
            for j in range(i + 1, len(turn_keywords)):
                if len(turn_keywords[i]) > 0 and len(turn_keywords[j]) > 0:
                    # Step 1: Jaccard keyword similarity (always computed)
                    overlap = len(turn_keywords[i] & turn_keywords[j])
                    union = len(turn_keywords[i] | turn_keywords[j])
                    jaccard_score = overlap / union if union > 0 else 0.0

                    # Step 2: Semantic similarity via pre-computed embeddings (optional)
                    if turn_embeddings is not None:
                        try:
                            semantic_sim = float(
                                _cosine_similarity(
                                    turn_embeddings[i].reshape(1, -1),
                                    turn_embeddings[j].reshape(1, -1),
                                )[0][0]
                            )
                            # clamp cosine similarity to [0, 1]
                            semantic_sim = max(0.0, min(1.0, semantic_sim))
                        except Exception:  # pragma: no cover
                            semantic_sim = 0.0
                        # Step 3: Combine both scores equally
                        combined_score = 0.5 * jaccard_score + 0.5 * semantic_sim
                    else:
                        # Fall back to Jaccard only when sentence-transformers is absent
                        combined_score = jaccard_score

                    # Step 4: Use combined score threshold
                    if combined_score > 0.5:
                        high_overlap_count += 1

        # If we find 3+ pairs with high overlap, it's repetitive
        return high_overlap_count >= 3

    def _detect_high_conflict(self, turns: List[Dict[str, str]]) -> bool:
        """
        Detect high conflict without resolution.

        Args:
            turns: Recent dialogue turns

        Returns:
            True if high conflict detected
        """
        if len(turns) < 4:
            return False

        # Simple heuristic: look for disagreement markers
        conflict_markers = [
            "no",
            "but",
            "disagree",
            "however",
            "wrong",
            "incorrect",
            "actually",
            "contrary",
            "opposite",
            "mistake",
            "error",
        ]

        conflict_count = 0
        for turn in turns:
            text = turn.get("text", "").lower()
            for marker in conflict_markers:
                if marker in text:
                    conflict_count += 1
                    break

        # High conflict if more than 60% of turns have conflict markers
        return (conflict_count / len(turns)) > 0.6

    def _detect_shallow_discussion(self, turns: List[Dict[str, str]]) -> bool:
        """
        Detect surface-level discussion.

        Args:
            turns: Recent dialogue turns

        Returns:
            True if shallow discussion detected
        """
        if len(turns) < 6:
            return False

        # Heuristic: if turns are consistently short, might be shallow
        avg_length = sum(len(turn.get("text", "")) for turn in turns) / len(turns)

        # Also check for lack of depth markers
        depth_markers = [
            "why",
            "because",
            "how",
            "reason",
            "therefore",
            "implies",
            "consequence",
            "deeper",
            "fundamental",
            "underlying",
            "depth",
            "foundation",
            "implication",
        ]

        depth_count = 0
        for turn in turns:
            text = turn.get("text", "").lower()
            for marker in depth_markers:
                if marker in text:
                    depth_count += 1
                    break

        # Shallow if average length < 150 and few depth markers
        return avg_length < 150 and (depth_count / len(turns)) < 0.3

    def _detect_synthesis_opportunity(self, turns: List[Dict[str, str]]) -> bool:
        """
        Detect when complementary ideas haven't been connected.

        Args:
            turns: Recent dialogue turns

        Returns:
            True if synthesis opportunity detected
        """
        if len(turns) < 4:
            return False

        # Look for synthesis markers being absent
        synthesis_markers = [
            "connect",
            "integrate",
            "together",
            "both",
            "combine",
            "linking",
            "merging",
            "unified",
            "all",
            "also",
        ]

        has_synthesis = False
        for turn in turns[-3:]:  # Check last 3 turns
            text = turn.get("text", "").lower()
            for marker in synthesis_markers:
                if marker in text:
                    has_synthesis = True
                    break
            if has_synthesis:
                break

        # If no synthesis markers in recent turns and we have enough content, might be opportunity
        return not has_synthesis and len(turns) >= 5

    def _detect_new_claim_in_recent_turns(
        self,
        turns: List[Dict[str, str]],
        window: int = 4,
    ) -> bool:
        """Return True when any recent agent turn contains a NEW_CLAIM move.

        Uses ``progress_enforcer.classify_move`` to detect whether the dialogue
        is still producing genuinely novel claims.  When True, Fixy should stay
        silent or use only soft_reflection rather than hard intervention.

        Parameters
        ----------
        turns:
            All agent turns (Fixy and seed already excluded by the caller).
        window:
            How many of the most recent turns to inspect.  Defaults to 4.

        Returns
        -------
        ``True`` when at least one NEW_CLAIM is found in the window.
        """
        recent = [t for t in turns[-window:] if t.get("role") not in ("Fixy", "seed")]
        if not recent:
            return False
        try:
            from entelgia.progress_enforcer import classify_move, NEW_CLAIM  # type: ignore[import]

            history = [t.get("text", "") for t in recent]
            for turn in recent:
                move = classify_move(turn.get("text", ""), history)
                if move == NEW_CLAIM:
                    logger.debug(
                        "[FIXY-NOVELTY] NEW_CLAIM detected in turn by %r — soft gate active",
                        turn.get("role"),
                    )
                    return True
        except (ImportError, AttributeError, TypeError) as exc:
            logger.debug("[FIXY-NOVELTY] progress_enforcer unavailable: %s", exc)
        return False

    def generate_fixy_analysis(
        self,
        dialog: List[Dict[str, str]],
        reason: str,
        intervention_mode: str,
        turn_count: int,
    ) -> Dict[str, Any]:
        """Return a structured internal Fixy analysis before rendering.

        This is the internal analysis layer that the controller can use to
        decide whether to show, ignore, or escalate Fixy's intervention.
        The controller retains full authority over what is rendered.

        Parameters
        ----------
        dialog:
            Full dialogue history.
        reason:
            Intervention reason string (e.g. ``"loop_repetition"``).
        intervention_mode:
            The selected ``FixyMode`` constant.
        turn_count:
            Current turn number.

        Returns
        -------
        A dict with keys:

        * ``intervention_mode`` — the selected mode (e.g. ``"SOFT_REFLECTION"``).
        * ``dialogue_read`` — Fixy's brief read of what the real disagreement is.
        * ``missing_element`` — the missing distinction, variable, or frame.
        * ``suggested_vector`` — the conceptual direction that could deepen the dialogue.
        * ``urgency`` — ``"low"``, ``"medium"``, or ``"high"``.
        """
        # Determine urgency from turn count and consecutive pairs
        if (
            turn_count >= self._min_turns_hard
            and self._consecutive_full_pair_count >= self._min_pairs_hard
        ):
            urgency = "high"
        elif turn_count >= self._min_turns_hard // 2:
            urgency = "medium"
        else:
            urgency = "low"

        # Map intervention_mode to a human-readable dialogue_read template
        _mode_read: Dict[str, str] = {
            FixyMode.SILENT_OBSERVE: "Dialogue is evolving; no intervention needed yet.",
            FixyMode.SOFT_REFLECTION: "The disagreement appears to be about a conceptual distinction not yet named.",
            FixyMode.GENTLE_NUDGE: "A key variable is missing from both positions.",
            FixyMode.STRUCTURED_MEDIATION: "The disagreement is structural — both sides share a hidden assumption.",
            FixyMode.HARD_CONSTRAINT: "The dialogue has persisted long enough for its underlying structural tensions to become visible.",
            FixyMode.MEDIATE: "A pattern-level issue is preventing dialogue from deepening.",
        }
        dialogue_read = _mode_read.get(
            intervention_mode,
            "The exchange may have reached a point where a new perspective could deepen it.",
        )

        # Missing element based on reason
        _reason_missing: Dict[str, str] = {
            "loop_repetition": "A concrete grounding case or operational definition.",
            "weak_conflict": "A precise distinction between the contested concepts.",
            "premature_synthesis": "Acknowledgment of the unresolved tension the synthesis skips.",
            "topic_stagnation": "A new conceptual frame outside the current cluster.",
            "circular_reasoning": "An independent variable that could break the circularity.",
            "high_conflict_no_resolution": "A shared criterion that both sides would accept.",
            "shallow_discussion": "A mechanism or causal account beneath the surface claims.",
            "synthesis_opportunity": "A named conceptual bridge connecting both positions.",
            "fixy_mediation_loop": "A frame shift that neither side has yet proposed.",
            "meta_reflection_needed": "A structural review of what has actually been established.",
        }
        missing_element = _reason_missing.get(reason, "A novel variable or frame.")

        # Suggested vector based on mode
        _mode_vector: Dict[str, str] = {
            FixyMode.SOFT_REFLECTION: "Reflect the disagreement structure back without forcing closure.",
            FixyMode.GENTLE_NUDGE: "Introduce the missing distinction gently.",
            FixyMode.STRUCTURED_MEDIATION: "Name the hidden assumption and propose a new framing.",
            FixyMode.HARD_CONSTRAINT: "Illuminate the structural tension that both sides have not yet named.",
            FixyMode.MEDIATE: "Identify and name the pattern preventing progress.",
        }
        suggested_vector = _mode_vector.get(
            intervention_mode,
            "Use the most appropriate disruption mode for the current failure.",
        )

        return {
            "intervention_mode": intervention_mode,
            "dialogue_read": dialogue_read,
            "missing_element": missing_element,
            "suggested_vector": suggested_vector,
            "urgency": urgency,
        }

    def should_request_research(
        self,
        dialog: List[Dict[str, str]],
        turn_count: int,
    ) -> Tuple[bool, Optional[str]]:
        """Determine whether Fixy should signal a need for external research.

        This method only *signals* a research need; it does **not** trigger a
        web search directly.  The web research system consumes the returned
        reason string and decides whether to run a search.

        Parameters
        ----------
        dialog:
            Full dialogue history (list of dicts with ``"role"`` and
            ``"text"`` keys).
        turn_count:
            Current turn number (1-based).

        Returns
        -------
        A ``(bool, Optional[str])`` tuple where the first element is ``True``
        when external research is recommended and the second element is the
        reason string (e.g. ``"external_verification_needed"``) or ``None``
        when no research is needed.
        """
        if turn_count < 3:
            return (False, None)

        # Only analyse main-agent turns; excluding Fixy's own past interventions
        # prevents a feedback loop where Fixy's meta-commentary inflates the
        # repetition score and triggers further unwanted interventions.
        agent_turns = [t for t in dialog if t.get("role") != "Fixy"]
        last_10 = agent_turns[-10:] if len(agent_turns) >= 10 else agent_turns

        # Condition 1: high conflict without resolution
        if turn_count >= 6 and self._detect_high_conflict(last_10):
            return (True, "high_conflict_no_resolution")

        # Condition 2: shallow factual discussion (surface level for a long time)
        if turn_count >= 10 and self._detect_shallow_discussion(last_10):
            return (True, "external_verification_needed")

        # Condition 3: repeated factual uncertainty (heavy repetition)
        if self._detect_repetition(last_10):
            return (True, "factual_uncertainty_detected")

        # Condition 4: missed synthesis opportunity requiring external evidence
        if turn_count >= 5 and self._detect_synthesis_opportunity(last_10):
            return (True, "research_needed_for_synthesis")

        return (False, None)

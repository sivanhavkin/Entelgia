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
# behaviour.  All other modes are disruptive — they force the dialogue out
# of a detected loop rather than summarising or bridging it.


class FixyMode:
    """Named constants for Fixy intervention modes."""

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
    "loop_repetition": FixyMode.FORCE_CASE,       # break repetition with a grounded case
    "weak_conflict": FixyMode.FORCE_CHOICE,        # resolve soft conflict with binary pick
    "premature_synthesis": FixyMode.FORCE_TEST,    # challenge synthesis with a testable claim
    "topic_stagnation": FixyMode.FORCE_METRIC,     # break stagnation with a new criterion
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

# Condition-based output label instructions — maps each intervention reason to
# the diagnostic labels that are appropriate for it.  Defined at module level
# so it is not recreated on every generate_intervention call.
_REASON_LABEL_MAP: Dict[str, str] = {
    "loop_repetition": (
        "Use 'Loop:' label only. "
        "Omit 'Deadlock:' unless positions are genuinely locked."
    ),
    "weak_conflict": (
        "Use 'Deadlock:' label. "
        "Include 'Missing variable:' only if a position is genuinely absent."
    ),
    "premature_synthesis": (
        "Use 'Deadlock:' label to expose what the synthesis hides. "
        "Omit 'Loop:' unless repetition exists."
    ),
    "topic_stagnation": (
        "Use 'Drift:' label. Do NOT use 'Loop:' or 'Deadlock:'."
    ),
    "circular_reasoning": (
        "Use 'Loop:' label. Include 'Next move:' with a concrete demand."
    ),
    "high_conflict_no_resolution": (
        "Use 'Deadlock:' label. "
        "Include 'Missing variable:' only if genuinely absent."
    ),
    "shallow_discussion": (
        "Use 'Loop:' label for surface repetition. Include 'Next move:'."
    ),
    "synthesis_opportunity": (
        "Use 'Deadlock:' to name hidden tension. "
        "Omit 'Missing variable:' if not needed."
    ),
    "fixy_mediation_loop": (
        "Use 'Loop:' label only. Do NOT repeat mediation language."
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

# Mode-specific prompt templates
# {context} is replaced with the last 6 turns of dialogue
_MODE_PROMPTS: Dict[str, str] = {
    FixyMode.MEDIATE: (
        "You are Fixy, the meta-cognitive observer. Diagnose the structural failure mode.\n"
        "Preferred labels: 'Deadlock:', 'Loop:', 'Drift:', 'Missing variable:', 'Next move:'.\n"
        "Max 3 short sentences. Do NOT summarize or recycle dialogue content. Do NOT moralize."
    ),
    FixyMode.CONTRADICT: (
        "You are Fixy. Failure mode: weak conflict — agents soften contradiction into synthesis.\n"
        "Name the unresolved binary. Demand the next speaker pick a side.\n"
        "Example: 'Deadlock: X vs Y. Missing variable: a committed position. Next move: choose one.'\n"
        "Max 3 short sentences. Do NOT bridge. Do NOT recycle dialogue content."
    ),
    FixyMode.CONCRETIZE: (
        "You are Fixy. Failure mode: abstraction loop — no concrete case grounding the claim.\n"
        "Name the recurring abstract claim. Demand one real-world example.\n"
        "Example: 'Loop: [claim] repeated. Missing variable: a specific case. Next move: name one.'\n"
        "Max 3 short sentences. Do NOT summarize the dialogue."
    ),
    FixyMode.INVERT: (
        "You are Fixy. Failure mode: position lock — one view repeated without challenge.\n"
        "State the locked position. Demand the strongest counterargument be addressed.\n"
        "Max 3 short sentences. Do NOT recycle dialogue content."
    ),
    FixyMode.PIVOT: (
        "You are Fixy. Failure mode: conceptual cluster lock — ideas stay in the same domain.\n"
        "Name the stuck cluster. Inject one question from a different domain.\n"
        "Example: 'Drift: stuck in [cluster]. Missing variable: a different domain. Next move: [domain question].'\n"
        "Max 3 short sentences. Do NOT philosophize."
    ),
    FixyMode.EXPOSE_SYNTHESIS: (
        "You are Fixy. Failure mode: premature synthesis — contradiction papered over.\n"
        "Name what the synthesis glosses over. Restore the unresolved tension.\n"
        "Example: 'Deadlock: synthesis claimed before contradiction resolved. Missing variable: which side wins. Next move: choose.'\n"
        "Max 3 short sentences. Do NOT accept the synthesis. Do NOT recycle dialogue content."
    ),
    FixyMode.FORCE_MECHANISM: (
        "You are Fixy. Failure mode: slogan loop — claims stated without causal mechanism.\n"
        "Name the unsupported claim. Demand the causal step-by-step.\n"
        "Example: 'Loop: [claim] stated. Missing variable: causal chain. Next move: show the steps.'\n"
        "Max 3 short sentences."
    ),
    FixyMode.FORCE_CONCRETE_EXAMPLE: (
        "You are Fixy. Failure mode: abstraction loop — no real-world case cited.\n"
        "Name the recurring claim. Demand one specific named example.\n"
        "Example: 'Loop: [claim] repeated. Missing variable: a dated real-world case. Next move: name one.'\n"
        "Max 3 short sentences. Do NOT summarize. Do NOT moralize."
    ),
    FixyMode.FORCE_COUNTEREXAMPLE: (
        "You are Fixy. Failure mode: unchallenged assertion — no disconfirming case cited.\n"
        "Name the assertion. Demand a case where it fails.\n"
        "Example: 'Loop: [claim] asserted. Missing variable: a case where it fails. Next move: name one or retract.'\n"
        "Max 3 short sentences. Do NOT hedge."
    ),
    FixyMode.FORCE_DIRECT_DISAGREEMENT: (
        "You are Fixy. Failure mode: false agreement — agents converge without genuine contradiction.\n"
        "Identify one claim that is flatly wrong. State it is wrong with one reason.\n"
        "Example: 'Deadlock: [claim] is wrong. Missing variable: direct contradiction. Next move: state the opposite.'\n"
        "Max 3 short sentences. Do NOT reconcile."
    ),
    FixyMode.FORCE_TOPIC_RETURN: (
        "You are Fixy. Failure mode: topic drift — dialogue has left the original question.\n"
        "Name the original question and the tangent. Demand return to the original.\n"
        "Example: 'Drift: from [original] to [tangent]. Missing variable: direct answer. Next move: answer it.'\n"
        "Max 3 short sentences. Do NOT allow the tangent to continue."
    ),
    FixyMode.FORCE_SHORT_ANSWER: (
        "You are Fixy. Failure mode: evasion — question not directly answered.\n"
        "Name the unanswered question. Demand a one-sentence answer.\n"
        "Example: 'Loop: [question] evaded. Missing variable: a direct claim. Next move: answer in one sentence.'\n"
        "Max 2 short sentences."
    ),
    FixyMode.FORCE_NEW_DOMAIN: (
        "You are Fixy. Failure mode: semantic trap — all topics collapse into the same cluster.\n"
        "Name the cluster. Inject one question from an unrelated domain.\n"
        "Example: 'Drift: stuck in [cluster]. Missing variable: a different domain. Next move: [domain question].'\n"
        "Max 3 short sentences. Do NOT stay in philosophy or abstract reasoning."
    ),
    FixyMode.FORCE_METRIC: (
        "You are Fixy. Failure mode: unmeasured claim — argument lacks any criterion or benchmark.\n"
        "Name the unmeasured claim. Demand a concrete measurable indicator.\n"
        "Example: 'Loop: [claim] argued without metric. Missing variable: a measurable criterion. "
        "Next move: define what would count as evidence.'\n"
        "Max 3 short sentences. Do NOT accept abstract assertions."
    ),
    FixyMode.FORCE_CHOICE: (
        "You are Fixy. Failure mode: undecided fork — both positions held without commitment.\n"
        "Name the binary choice. Demand one side be chosen and defended.\n"
        "Example: 'Deadlock: [X] vs [Y] unresolved. Missing variable: a committed position. "
        "Next move: pick one and state why the other fails.'\n"
        "Max 3 short sentences. Do NOT allow hedging."
    ),
    FixyMode.FORCE_TEST: (
        "You are Fixy. Failure mode: unfalsifiable claim — no empirical test proposed.\n"
        "Name the untestable claim. Demand a falsifiable prediction.\n"
        "Example: 'Loop: [claim] asserted. Missing variable: a testable prediction. "
        "Next move: state what observable outcome would refute it.'\n"
        "Max 3 short sentences. Do NOT accept claims without tests."
    ),
    FixyMode.FORCE_CASE: (
        "You are Fixy. Failure mode: ungrounded abstraction — no real-world case anchors the claim.\n"
        "Name the abstract claim. Demand one specific named case or scenario.\n"
        "Example: 'Loop: [claim] generalised. Missing variable: a specific grounded case. "
        "Next move: name a real historical or current instance.'\n"
        "Max 3 short sentences. Do NOT accept purely theoretical assertions."
    ),
    FixyMode.FORCE_DEFINITION: (
        "You are Fixy. Failure mode: undefined concept — a central term is contested but never defined.\n"
        "Name the undefined term. Demand an operational definition.\n"
        "Example: 'Loop: [term] used differently by each side. Missing variable: an operational definition. "
        "Next move: define precisely what counts as an instance.'\n"
        "Max 3 short sentences. Do NOT allow the term to remain ambiguous."
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
    """

    # Minimum number of distinct main-agent turns required before Fixy may
    # evaluate.  This enforces the pair requirement without relying solely on
    # turn_count.
    _MIN_CONTEXT_TURNS: int = 2

    def __init__(self, llm, model: str):
        """
        Initialize Interactive Fixy.

        Args:
            llm: LLM instance for generating interventions
            model: Model name to use
        """
        self.llm = llm
        self.model = model
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

        # ── Pair gating: require both main agents to have spoken ────────────
        # Fixy must not intervene after a single agent's message.
        if not self._both_agents_present(dialog):
            logger.info(
                "[FIXY-GATE] skipped: waiting for both agents at turn %d",
                turn_count,
            )
            return (False, "")

        # ── Minimum context window ──────────────────────────────────────────
        agent_turns_all = [
            t for t in dialog if t.get("role") not in ("Fixy", "seed")
        ]
        if len(agent_turns_all) < self._MIN_CONTEXT_TURNS:
            logger.info(
                "[FIXY-GATE] skipped: insufficient context (have %d agent turns, need %d) at turn %d",
                len(agent_turns_all),
                self._MIN_CONTEXT_TURNS,
                turn_count,
            )
            return (False, "")

        # ── Loop-guard checks (new v2.9.0) ─────────────────────────────────
        if self._loop_detector is not None:
            active_modes = self._loop_detector.detect(
                dialog, turn_count, current_topic=current_topic
            )
            if active_modes:
                primary = active_modes[0]
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
        last_10 = agent_turns_all[-10:] if len(agent_turns_all) >= 10 else agent_turns_all

        # Pattern 1: Circular reasoning (repetition)
        if self._detect_repetition(last_10):
            self._pending_rewrite_mode = FixyMode.FORCE_CASE
            return (True, "circular_reasoning")

        # Pattern 2: High conflict without synthesis (check every 6+ turns)
        if turn_count >= 6 and self._detect_high_conflict(last_10):
            self._pending_rewrite_mode = FixyMode.FORCE_CHOICE
            return (True, "high_conflict_no_resolution")

        # Pattern 3: Surface-level discussion for too long
        if turn_count >= 10 and self._detect_shallow_discussion(last_10):
            self._pending_rewrite_mode = FixyMode.FORCE_TEST
            return (True, "shallow_discussion")

        # Pattern 4: Missed synthesis opportunity
        if turn_count >= 5 and self._detect_synthesis_opportunity(last_10):
            self._pending_rewrite_mode = FixyMode.FORCE_METRIC
            return (True, "synthesis_opportunity")

        # Pattern 5: Meta-reflection needed (every 15 turns)
        if turn_count > 15 and turn_count % 15 == 0:
            return (True, "meta_reflection_needed")

        return (False, "")

    def get_fixy_mode(self, reason: str) -> str:
        """Return the FixyMode that best matches *reason*.

        Loop-guard reasons that signal repetition rotate through all loop-breaking
        modes so Fixy never repeats the same strategy twice in a row.
        Legacy reasons use MEDIATE (the neutral default).

        Args:
            reason: Intervention reason string

        Returns:
            One of the FixyMode constants
        """
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
                "high_conflict_no_resolution": _MODE_PROMPTS[FixyMode.CONTRADICT],
                "shallow_discussion": (
                    "You are Fixy. Failure mode: surface-level exchange — no depth reached.\n"
                    "Name the pattern. Demand a deeper angle.\n"
                    "Example: 'Loop: surface claims only. Missing variable: a mechanism or concrete case. Next move: go deeper.'\n"
                    "Max 3 short sentences. Do NOT summarize dialogue content."
                ),
                "synthesis_opportunity": _MODE_PROMPTS[FixyMode.EXPOSE_SYNTHESIS],
                "meta_reflection_needed": (
                    "You are Fixy. Failure mode: structural stagnation — dialogue has not evolved.\n"
                    "Name what has stalled. Propose one concrete direction.\n"
                    "Example: 'Drift: no new angle introduced. Missing variable: a new domain or case. Next move: introduce one.'\n"
                    "Max 3 short sentences. Do NOT moralize or prescribe policy."
                ),
            }
            prompt_template = legacy_prompts.get(
                reason, _MODE_PROMPTS[FixyMode.MEDIATE]
            )

        # Build condition-based output instruction using the module-level map.
        # Only include diagnostic labels that match the actual failure type.
        output_instruction = _REASON_LABEL_MAP.get(
            reason,
            "Use only the diagnostic labels that apply to the actual failure. "
            "Do NOT produce all labels by default.",
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

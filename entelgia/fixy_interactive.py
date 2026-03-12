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
]

# Concepts Fixy must NEVER repeat — they signal a semantic attractor
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

# Mode-specific prompt templates
# {context} is replaced with the last 6 turns of dialogue
_MODE_PROMPTS: Dict[str, str] = {
    FixyMode.MEDIATE: (
        "You are Fixy, the meta-cognitive observer.  The dialogue needs rebalancing.\n"
        "Generate a brief intervention (2-4 sentences) that:\n"
        "1. Names the pattern you observe\n"
        "2. Suggests a specific reframe or new angle\n"
        "3. Helps break the loop"
    ),
    FixyMode.CONTRADICT: (
        "You are Fixy, the meta-cognitive observer.  The conflict is weak — "
        "agents appear to disagree but keep softening into synthesis.\n"
        "Your job: FORCE a sharper contradiction.\n"
        "In 2-3 sentences:\n"
        "1. Identify the one claim that the two agents cannot BOTH hold simultaneously\n"
        "2. State it as an unresolved binary: either X or Y — not both\n"
        "3. Demand that the next speaker choose a side and defend it without hedging\n"
        "Do NOT reconcile. Do NOT bridge. Do NOT use 'both have merit'."
    ),
    FixyMode.CONCRETIZE: (
        "You are Fixy, the meta-cognitive observer.  The dialogue is repeating "
        "abstract claims without adding new content.\n"
        "Your job: demand a concrete case.\n"
        "In 2-3 sentences:\n"
        "1. Name the abstract claim that keeps recurring\n"
        "2. Challenge: provide ONE real-world case, historical example, or "
        "counterexample that either proves or disproves it\n"
        "3. Make clear that abstract restatement is not acceptable — specifics only\n"
        "Do NOT summarise the dialogue."
    ),
    FixyMode.INVERT: (
        "You are Fixy, the meta-cognitive observer.  An agent is stuck defending "
        "the same position repeatedly.\n"
        "Your job: temporarily invert that position.\n"
        "In 2-3 sentences:\n"
        "1. State the position that has become repetitive\n"
        "2. Argue the opposite view as forcefully as possible\n"
        "3. Ask the repeating agent to respond to the strongest version of the counter-argument\n"
        "Do NOT say this is hypothetical. Commit to the inversion."
    ),
    FixyMode.PIVOT: (
        "You are Fixy, the meta-cognitive observer.  The semantic content of the "
        "dialogue has not moved — the topic label changed but the ideas stayed "
        "in the same conceptual neighbourhood.\n"
        "Your job: force a real pivot.\n"
        "In 2-3 sentences:\n"
        "1. Name the conceptual cluster that dialogue has been stuck in\n"
        "2. Introduce a question or concept from a genuinely different domain "
        "(e.g., biology, law, engineering, economics, practice)\n"
        "3. Show one concrete bridge so the shift feels motivated\n"
        "Do NOT stay inside philosophy or abstract ethics."
    ),
    FixyMode.EXPOSE_SYNTHESIS: (
        "You are Fixy, the meta-cognitive observer.  The dialogue has collapsed "
        "into premature synthesis — 'both are needed', 'integrate both views'.\n"
        "Your job: expose what is false or lost in that synthesis.\n"
        "In 2-3 sentences:\n"
        "1. State what the synthesis claim actually says\n"
        "2. Identify what genuine contradiction it papers over or what "
        "costs it ignores\n"
        "3. Restore the tension: declare which side of the contradiction "
        "must be resolved before synthesis is earned\n"
        "Do NOT accept the synthesis. Do NOT soften the contradiction."
    ),
    FixyMode.FORCE_MECHANISM: (
        "You are Fixy, the meta-cognitive observer.  The dialogue is stuck in "
        "slogans and abstract labels with no causal mechanism.\n"
        "Your job: demand a mechanism.\n"
        "In 2-3 sentences:\n"
        "1. Name the abstract claim being repeated\n"
        "2. Ask: what is the step-by-step causal process by which this claim "
        "produces its supposed effect?\n"
        "3. Warn that without a mechanism the claim is empty rhetoric\n"
        "Do NOT accept abstract restatement."
    ),
    FixyMode.FORCE_CONCRETE_EXAMPLE: (
        "You are Fixy, the meta-cognitive observer.  The dialogue is looping on "
        "abstract claims without grounding them in reality.\n"
        "Your job: demand ONE concrete real-world example.\n"
        "In 2-3 sentences:\n"
        "1. Name the abstract claim that keeps returning\n"
        "2. Demand: give a single specific dated real-world example — a name, "
        "a place, a documented event — that either proves or disproves it\n"
        "3. Make clear that abstract restatement will be rejected\n"
        "Do NOT summarise. Do NOT bridge. Demand the example now."
    ),
    FixyMode.FORCE_COUNTEREXAMPLE: (
        "You are Fixy, the meta-cognitive observer.  One position is being "
        "asserted repeatedly without challenge.\n"
        "Your job: produce the strongest possible counterexample.\n"
        "In 2-3 sentences:\n"
        "1. State the claim being repeated\n"
        "2. Provide ONE specific case where that claim demonstrably fails — "
        "a real event, a documented exception, an empirical disconfirmation\n"
        "3. Ask the next speaker to either refute the counterexample or abandon the claim\n"
        "Do NOT hedge. The counterexample must be specific and named."
    ),
    FixyMode.FORCE_DIRECT_DISAGREEMENT: (
        "You are Fixy, the meta-cognitive observer.  The dialogue has drifted "
        "into polite agreement or vague parallel monologues.\n"
        "Your job: force a direct, unambiguous disagreement.\n"
        "In 2-3 sentences:\n"
        "1. Identify one concrete claim made by the last speaker\n"
        "2. State flatly that this claim is wrong — no hedging, no 'perhaps', "
        "no 'in some cases'\n"
        "3. Give the single strongest reason it is wrong\n"
        "Do NOT reconcile. Do NOT use 'both'. Be adversarial."
    ),
    FixyMode.FORCE_TOPIC_RETURN: (
        "You are Fixy, the meta-cognitive observer.  The dialogue has drifted "
        "away from its original question into tangents.\n"
        "Your job: pull it back to the core question.\n"
        "In 2-3 sentences:\n"
        "1. State what the original question or topic was\n"
        "2. Name the tangent the dialogue has wandered into\n"
        "3. Demand that the next speaker answer the original question directly — "
        "not the tangent\n"
        "Do NOT allow the tangent to continue. Redirect sharply."
    ),
    FixyMode.FORCE_SHORT_ANSWER: (
        "You are Fixy, the meta-cognitive observer.  Responses have become "
        "verbose, padded, and evasive.\n"
        "Your job: enforce brevity and precision.\n"
        "In 1-2 sentences:\n"
        "1. Identify the question that has not been directly answered\n"
        "2. Demand a one-sentence answer: yes or no, true or false, or a single "
        "concrete claim — no qualifications, no context-setting\n"
        "Do NOT accept a paragraph where a sentence will do."
    ),
    FixyMode.FORCE_NEW_DOMAIN: (
        "You are Fixy, the meta-cognitive observer.  The dialogue is semantically "
        "trapped — every new topic collapses back into the same conceptual cluster.\n"
        "Your job: inject a question from a completely unrelated domain.\n"
        "In 2-3 sentences:\n"
        "1. Name the conceptual cluster the dialogue keeps returning to\n"
        "2. Introduce a question or case from a domain with no obvious connection "
        "(e.g., microbiology, contract law, structural engineering, game theory, "
        "historical cartography)\n"
        "3. Explain in one sentence why this new domain actually illuminates "
        "the original problem from an unexpected angle\n"
        "Do NOT stay in philosophy, abstract reasoning, or technology."
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
    """

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

        # Lazy import to avoid circular dependency (loop_guard → no imports from fixy)
        try:
            from entelgia.loop_guard import DialogueLoopDetector

            self._loop_detector = DialogueLoopDetector()
        except ImportError:  # pragma: no cover
            self._loop_detector = None

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

        Args:
            dialog: Full dialogue history
            turn_count: Current turn number
            current_topic: Current topic label (optional; used for stagnation check)

        Returns:
            Tuple of (should_intervene, reason)
        """
        # Don't intervene too early
        if turn_count < 3:
            return (False, "")

        # ── Loop-guard checks (new v2.9.0) ─────────────────────────────────
        if self._loop_detector is not None:
            active_modes = self._loop_detector.detect(
                dialog, turn_count, current_topic=current_topic
            )
            if active_modes:
                primary = active_modes[0]
                logger.info(
                    "[FIXY-LOOP] Loop detected: modes=%s turn=%d topic=%r → Fixy will break loop",
                    active_modes,
                    turn_count,
                    current_topic,
                )
                # Use the first (highest-priority) failure mode as the reason
                return (True, primary)

        # ── Legacy heuristic patterns (preserved for backward compat) ───────
        # Only analyse main-agent turns; excluding Fixy's own past interventions
        # prevents a feedback loop where Fixy's meta-commentary (which references
        # the dialogue topic and therefore has high semantic similarity) inflates
        # the repetition score and triggers yet more Fixy interventions.
        agent_turns = [t for t in dialog if t.get("role") != "Fixy"]
        last_10 = agent_turns[-10:] if len(agent_turns) >= 10 else agent_turns

        # Pattern 1: Circular reasoning (repetition)
        if self._detect_repetition(last_10):
            return (True, "circular_reasoning")

        # Pattern 2: High conflict without synthesis (check every 6+ turns)
        if turn_count >= 6 and self._detect_high_conflict(last_10):
            return (True, "high_conflict_no_resolution")

        # Pattern 3: Surface-level discussion for too long
        if turn_count >= 10 and self._detect_shallow_discussion(last_10):
            return (True, "shallow_discussion")

        # Pattern 4: Missed synthesis opportunity
        if turn_count >= 5 and self._detect_synthesis_opportunity(last_10):
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

    def generate_intervention(
        self,
        dialog: List[Dict[str, str]],
        reason: str,
        mode: Optional[str] = None,
    ) -> str:
        """
        Generate contextual intervention using the appropriate Fixy mode.

        v2.9.0: When *reason* maps to a loop failure mode, Fixy selects a
        disruptive mode (CONTRADICT, CONCRETIZE, etc.) instead of the
        default mediating style, ensuring it does not reinforce loops.

        Args:
            dialog: Dialogue history
            reason: Reason for intervention
            mode: Override FixyMode (optional; auto-selected from reason if omitted)

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
                    "You are Fixy, the meta-cognitive observer. The dialogue has stayed at a "
                    "surface level for a while. Generate a brief intervention (2-4 sentences) that:\n"
                    "1. Notes the pattern of surface-level engagement\n"
                    "2. Suggests going deeper\n"
                    "3. Offers a specific deeper question or angle"
                ),
                "synthesis_opportunity": _MODE_PROMPTS[FixyMode.EXPOSE_SYNTHESIS],
                "meta_reflection_needed": (
                    "You are Fixy, the meta-cognitive observer. It's time for meta-reflection on "
                    "the dialogue. Generate a brief intervention (2-4 sentences) that:\n"
                    "1. Reflects on what's been accomplished\n"
                    "2. Notes what patterns have emerged\n"
                    "3. Suggests where to go next"
                ),
            }
            prompt_template = legacy_prompts.get(
                reason, _MODE_PROMPTS[FixyMode.MEDIATE]
            )

        full_prompt = (
            f"{prompt_template}\n\n"
            f"RECENT DIALOGUE:\n{context}\n\n"
            f"Respond in 1-2 sentences only. Be direct and concrete.\n"
            f"{_FIXY_FORBIDDEN_CONCEPTS_INSTRUCTION}\n"
            f"{LLM_RESPONSE_LIMIT}\n"
        )

        intervention = self.llm.generate(
            self.model, full_prompt, temperature=0.4, use_cache=False
        )

        return (
            intervention.strip()
            if intervention
            else "I notice we might benefit from a fresh perspective here."
        )

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

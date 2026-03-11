#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Interactive Fixy for Entelgia
Need-based interventions rather than scheduled interventions.
"""

import re
import logging
from typing import Dict, List, Tuple, Any, Optional

# LLM Response Length Instruction
LLM_RESPONSE_LIMIT = "IMPORTANT: Please answer in maximum 150 words."

logger = logging.getLogger(__name__)

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
    """Fixy as active dialogue participant with intelligent interventions."""

    def __init__(self, llm, model: str):
        """
        Initialize Interactive Fixy.

        Args:
            llm: LLM instance for generating interventions
            model: Model name to use
        """
        self.llm = llm
        self.model = model

    def should_intervene(
        self, dialog: List[Dict[str, str]], turn_count: int
    ) -> Tuple[bool, str]:
        """
        Decide if intervention needed based on dialogue state.

        Args:
            dialog: Full dialogue history
            turn_count: Current turn number

        Returns:
            Tuple of (should_intervene, reason)
        """
        # Don't intervene too early
        if turn_count < 3:
            return (False, "")

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

    def generate_intervention(self, dialog: List[Dict[str, str]], reason: str) -> str:
        """
        Generate contextual intervention.

        Args:
            dialog: Dialogue history
            reason: Reason for intervention

        Returns:
            Intervention text
        """
        context = self._build_intervention_context(dialog, reason)

        # Create intervention prompt based on reason
        prompts = {
            "circular_reasoning": "You are Fixy, the meta-cognitive observer. The dialogue has circled back to the same points multiple times. Generate a brief intervention (2-4 sentences) that:\n1. Names the circular pattern you observe\n2. Suggests a specific reframe or new angle\n3. Helps break the loop",
            "high_conflict_no_resolution": "You are Fixy, the meta-cognitive observer. The dialogue has high conflict without moving toward synthesis. Generate a brief intervention (2-4 sentences) that:\n1. Acknowledges the tension\n2. Points out the complementary aspects being missed\n3. Suggests a bridging perspective",
            "shallow_discussion": "You are Fixy, the meta-cognitive observer. The dialogue has stayed at a surface level for a while. Generate a brief intervention (2-4 sentences) that:\n1. Notes the pattern of surface-level engagement\n2. Suggests going deeper\n3. Offers a specific deeper question or angle",
            "synthesis_opportunity": "You are Fixy, the meta-cognitive observer. There's an obvious synthesis opportunity being missed. Generate a brief intervention (2-4 sentences) that:\n1. Points out the complementary ideas\n2. Suggests how they might connect\n3. Encourages integration",
            "meta_reflection_needed": "You are Fixy, the meta-cognitive observer. It's time for meta-reflection on the dialogue. Generate a brief intervention (2-4 sentences) that:\n1. Reflects on what's been accomplished\n2. Notes what patterns have emerged\n3. Suggests where to go next",
        }

        prompt_template = prompts.get(reason, prompts["circular_reasoning"])

        full_prompt = f"""{prompt_template}

RECENT DIALOGUE:
{context}

Respond in 1-2 sentences only. Be direct and concrete.
{LLM_RESPONSE_LIMIT}
"""

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

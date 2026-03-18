"""topic_enforcer.py — Soft semantic topic anchoring and graded compliance.

Replaces the binary pass/fail topic validation with a graded compliance
score and a three-level recovery ladder:

  - score >= ACCEPT_THRESHOLD (0.70):        accept
  - SOFT_REANCHOR_THRESHOLD <= score < 0.70: soft re-anchor regeneration
  - score < SOFT_REANCHOR_THRESHOLD (0.50):  hard recovery

Design principles:
  * The OPENING (first 1-2 sentences) must be anchored to the current
    session topic — not to the agent's previous topic.
  * Prior memory may influence later parts of the response but must not
    dominate the opening.
  * Stale carryover phrases (prior-topic framing) in the opening are
    penalised, not outright rejected unless contamination is severe.
"""

from __future__ import annotations

import logging
import re
from typing import Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Enforcement thresholds
# ---------------------------------------------------------------------------

ACCEPT_THRESHOLD: float = 0.70
"""Responses at or above this score are accepted without further action."""

SOFT_REANCHOR_THRESHOLD: float = 0.50
"""Responses in [SOFT_REANCHOR_THRESHOLD, ACCEPT_THRESHOLD) receive a
soft re-anchor instruction and are regenerated once."""

# ---------------------------------------------------------------------------
# Internal scoring constants
# ---------------------------------------------------------------------------

# Maximum number of prior-topic anchor hits to normalise against in
# _contamination_score().  Keeps one highly verbose previous topic from
# dominating the penalty calculation.
_MAX_CONTAMINATION_ANCHORS: int = 4

# Weight applied per stale contamination phrase found in the opening.
# Four phrases at this weight saturate the penalty at 1.0.
_STALE_PHRASE_PENALTY_WEIGHT: float = 0.25

# When computing memory_hijack, the opening contamination baseline is
# discounted by this factor before subtracting from full-response
# contamination.  This prevents double-counting sentences that appear in
# both the opening and the body.
_OPENING_CONTAMINATION_DISCOUNT: float = 0.5

# ---------------------------------------------------------------------------
# Stale contamination phrases
# ---------------------------------------------------------------------------

# Prior-topic framing that must NOT dominate the opening sentence.
# These are examples of AI/technology-domain concepts that commonly leak
# into responses regardless of the active session topic.
_STALE_CONTAMINATION_PHRASES: list[str] = [
    "strict adherence to initial programming",
    "autonomous decision-making capabilities",
    "biased algorithms",
    "data provenance",
    "training datasets",
    "machine learning model",
    "neural network architecture",
    "deep learning",
    "large language model",
    "model weights",
    "reinforcement learning from human feedback",
    "supervised fine-tuning",
]

# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _get_opening_sentences(text: str, n: int = 2) -> str:
    """Return the first *n* sentences of *text*.

    Sentence boundaries are identified by terminal punctuation followed by
    whitespace.  If fewer than *n* sentences are found the entire text is
    returned.
    """
    parts = re.split(r"(?<=[.!?])\s+", text.strip())
    return " ".join(parts[:n])


def _semantic_relevance(text: str, anchors: list[str]) -> float:
    """Return a relevance score [0, 1] based on anchor-keyword presence.

    Returns 1.0 when any anchor keyword is found in *text* (case-insensitive),
    0.0 when none are found.

    This binary approach is appropriate when using keyword matching as a proxy
    for semantic similarity: mentioning any single topic concept in the opening
    is sufficient evidence of on-topic engagement.  The contamination and
    memory-hijack penalties then supply the gradient for borderline responses.
    """
    if not anchors:
        return 1.0
    text_lower = text.lower()
    return 1.0 if any(a.lower() in text_lower for a in anchors) else 0.0


def _contamination_score(text: str, prev_anchors: list[str]) -> float:
    """Return a contamination score [0, 1] based on prior-topic anchor density.

    A high score means the text contains many concepts from the *previous*
    topic, which would indicate carryover contamination.  Normalises against
    ``_MAX_CONTAMINATION_ANCHORS`` to prevent an unusually long prior-topic
    anchor list from inflating the penalty.
    """
    if not prev_anchors:
        return 0.0
    text_lower = text.lower()
    hits = sum(1 for a in prev_anchors if a.lower() in text_lower)
    return min(1.0, hits / max(1, min(_MAX_CONTAMINATION_ANCHORS, len(prev_anchors))))


def _stale_phrase_penalty(text: str) -> float:
    """Return a stale-phrase penalty [0, 1] for *text*.

    Each stale contamination phrase found in *text* adds
    ``_STALE_PHRASE_PENALTY_WEIGHT`` to the penalty, capped at 1.0.
    """
    text_lower = text.lower()
    hits = sum(1 for phrase in _STALE_CONTAMINATION_PHRASES if phrase in text_lower)
    return min(1.0, hits * _STALE_PHRASE_PENALTY_WEIGHT)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def compute_topic_compliance_score(
    text: str,
    topic: str,
    topic_anchors: list[str],
    prev_anchors: Optional[list[str]] = None,
    *,
    log_agent: str = "",
) -> dict:
    """Compute a graded topic compliance score for *text*.

    The formula is::

        score = 0.45 * opening_topic_relevance
              + 0.35 * full_response_topic_relevance
              - 0.20 * contamination_penalty
              - 0.15 * memory_hijack_penalty

    Parameters
    ----------
    text:
        The agent's generated response to evaluate.
    topic:
        The active session topic label (used only for logging).
    topic_anchors:
        Anchor keywords for the current topic.
    prev_anchors:
        Anchor keywords for the *previous* topic (used for contamination
        detection).  Pass an empty list or ``None`` when there is no
        previous topic.
    log_agent:
        Agent name for log messages (optional).

    Returns
    -------
    dict with keys:
        ``opening_topic_relevance``, ``full_response_topic_relevance``,
        ``contamination_penalty``, ``memory_hijack_penalty``, ``score``.
    """
    _prev_anchors: list[str] = prev_anchors or []

    if not topic_anchors:
        result = {
            "opening_topic_relevance": 1.0,
            "full_response_topic_relevance": 1.0,
            "contamination_penalty": 0.0,
            "memory_hijack_penalty": 0.0,
            "score": 1.0,
        }
        logger.debug(
            "[TOPIC-SCORE] agent=%s topic=%r no anchors defined → score=1.0",
            log_agent,
            topic,
        )
        return result

    opening = _get_opening_sentences(text, n=2)

    # How well does the OPENING align with the current topic?
    opening_rel = _semantic_relevance(opening, topic_anchors)
    # How well does the FULL RESPONSE align with the current topic?
    full_rel = _semantic_relevance(text, topic_anchors)

    # Contamination: prior-topic framing in the opening
    opening_contamination = _contamination_score(opening, _prev_anchors)
    stale_pen = _stale_phrase_penalty(opening)
    contamination_penalty = max(opening_contamination, stale_pen)

    # Memory hijack: prior-topic density across the *full* response that
    # exceeds what would be expected from the opening alone.
    # The opening contamination is discounted by _OPENING_CONTAMINATION_DISCOUNT
    # to avoid double-counting sentences present in both opening and body.
    full_contamination = _contamination_score(text, _prev_anchors)
    memory_hijack = max(
        0.0,
        full_contamination - opening_contamination * _OPENING_CONTAMINATION_DISCOUNT,
    )

    score = (
        0.45 * opening_rel
        + 0.35 * full_rel
        - 0.20 * contamination_penalty
        - 0.15 * memory_hijack
    )
    score = max(0.0, min(1.0, score))

    result = {
        "opening_topic_relevance": opening_rel,
        "full_response_topic_relevance": full_rel,
        "contamination_penalty": contamination_penalty,
        "memory_hijack_penalty": memory_hijack,
        "score": score,
    }
    logger.debug(
        "[TOPIC-SCORE] agent=%s topic=%r opening_rel=%.2f full_rel=%.2f "
        "contamination=%.2f hijack=%.2f score=%.2f",
        log_agent,
        topic,
        opening_rel,
        full_rel,
        contamination_penalty,
        memory_hijack,
        score,
    )
    return result


def build_soft_reanchor_instruction(topic: str, anchors: list[str]) -> str:
    """Build a soft re-anchor instruction appended to the prompt on the
    first recovery attempt.

    Instructs the model to open the *next* response with a sentence that
    is clearly about the current topic, without prescribing exact wording.
    The instruction is intentionally short to avoid bloating the prompt.
    """
    top_anchors = anchors[:4] if anchors else []
    anchor_hint = f" (key concepts: {', '.join(top_anchors)})" if top_anchors else ""
    return (
        f"\n[RE-ANCHOR] Your previous response drifted from the current topic.\n"
        f"Please begin your next response with a sentence that clearly "
        f"addresses: {topic}{anchor_hint}.\n"
        f"Memory from prior topics may appear later in your response but "
        f"must not dominate your opening sentence.\n"
    )

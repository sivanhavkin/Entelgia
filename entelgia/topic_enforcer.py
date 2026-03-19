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
  * Fixy (meta-observer) uses a role-aware rubric: meta-analytic framing
    is allowed as long as it names the current topic or a core concept.
"""

from __future__ import annotations

import logging
import re
from typing import List, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Enforcement thresholds
# ---------------------------------------------------------------------------

ACCEPT_THRESHOLD: float = 0.60
"""Responses at or above this score are accepted without further action."""

SOFT_REANCHOR_THRESHOLD: float = 0.40
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
    cluster_anchors: Optional[list[str]] = None,
) -> dict:
    """Compute a graded topic compliance score for *text*.

    The formula is::

        score = 0.45 * opening_topic_relevance
              + 0.35 * full_response_topic_relevance
              - 0.20 * contamination_penalty
              - 0.15 * memory_hijack_penalty

    Additionally computes detail sub-scores:
        - ``topic_exactness``: how precisely the text matches the specific topic keywords
        - ``cluster_only_match``: text matches cluster keywords but not topic-exact keywords
        - ``contamination``: prior-topic content density
        - ``hijack``: full-body prior-topic density beyond opening

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
    cluster_anchors:
        Generic keywords for the cluster (e.g. "economics" cluster terms).
        When provided, used to compute ``cluster_only_match`` sub-score so
        that same-cluster-but-off-topic drift can be penalised more clearly.

    Returns
    -------
    dict with keys:
        ``opening_topic_relevance``, ``full_response_topic_relevance``,
        ``contamination_penalty``, ``memory_hijack_penalty``, ``score``,
        ``topic_exactness``, ``cluster_only_match``.
    """
    _prev_anchors: list[str] = prev_anchors or []
    _cluster_anchors: list[str] = cluster_anchors or []

    if not topic_anchors:
        result = {
            "opening_topic_relevance": 1.0,
            "full_response_topic_relevance": 1.0,
            "contamination_penalty": 0.0,
            "memory_hijack_penalty": 0.0,
            "score": 1.0,
            "topic_exactness": 1.0,
            "cluster_only_match": 0.0,
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

    # --- Detail sub-scores ---
    # topic_exactness: count of distinct topic anchors matched vs total anchors
    text_lower = text.lower()
    topic_hits = sum(1 for a in topic_anchors if a.lower() in text_lower)
    topic_exactness = min(1.0, topic_hits / max(1, len(topic_anchors)))

    # cluster_only_match: text matches cluster-generic terms but not topic-exact
    # A high cluster_only_match with low topic_exactness = wallpaper drift
    cluster_only_match = 0.0
    if _cluster_anchors:
        cluster_hits = sum(1 for a in _cluster_anchors if a.lower() in text_lower)
        cluster_only_match = min(1.0, cluster_hits / max(1, len(_cluster_anchors)))
        # Penalise cluster-only drift: lower the score when topic is imprecise
        # but cluster terms are present (wallpaper effect).
        # Thresholds:
        #   0.3 = cluster_only_match minimum to trigger (avoid false positives)
        #   0.2 = topic_exactness ceiling below which drift is flagged
        #   0.10 = max wallpaper penalty multiplier (keeps total penalty modest)
        _WALLPAPER_CLUSTER_MIN = 0.30
        _WALLPAPER_TOPIC_MAX = 0.20
        _WALLPAPER_PENALTY_MULTIPLIER = 0.10
        if (
            cluster_only_match > _WALLPAPER_CLUSTER_MIN
            and topic_exactness < _WALLPAPER_TOPIC_MAX
        ):
            wallpaper_penalty = _WALLPAPER_PENALTY_MULTIPLIER * cluster_only_match
            score = max(0.0, score - wallpaper_penalty)

    result = {
        "opening_topic_relevance": opening_rel,
        "full_response_topic_relevance": full_rel,
        "contamination_penalty": contamination_penalty,
        "memory_hijack_penalty": memory_hijack,
        "score": score,
        "topic_exactness": topic_exactness,
        "cluster_only_match": cluster_only_match,
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
    logger.debug(
        "[TOPIC-COMPLIANCE-DETAIL] agent=%s topic=%r topic_exactness=%.2f "
        "cluster_only_match=%.2f contamination=%.2f hijack=%.2f score=%.2f",
        log_agent,
        topic,
        topic_exactness,
        cluster_only_match,
        contamination_penalty,
        memory_hijack,
        score,
    )
    return result


# ---------------------------------------------------------------------------
# Cluster-generic vocabulary (wallpaper terms per cluster)
# ---------------------------------------------------------------------------

# These are generic terms that agents tend to repeat when they remain in
# a cluster but drift from the specific topic ("wallpaper" vocabulary).
CLUSTER_WALLPAPER_TERMS: dict[str, list[str]] = {
    "economics": [
        "allocation",
        "incentives",
        "tradeoffs",
        "opportunity cost",
        "policy",
        "markets",
        "efficiency",
        "equilibrium",
        "supply",
        "demand",
    ],
    "philosophy": [
        "truth",
        "knowledge",
        "reality",
        "existence",
        "reasoning",
        "morality",
        "ethics",
        "perspective",
        "concept",
        "notion",
    ],
    "psychology": [
        "behavior",
        "cognition",
        "perception",
        "emotion",
        "response",
        "pattern",
        "motivation",
        "awareness",
        "feelings",
        "mind",
    ],
    "biology": [
        "evolution",
        "adaptation",
        "organism",
        "survival",
        "genetic",
        "neural",
        "biological",
        "system",
        "mechanism",
        "process",
    ],
    "society": [
        "social",
        "structure",
        "norms",
        "community",
        "power",
        "institutions",
        "collective",
        "culture",
        "society",
        "values",
    ],
    "technology": [
        "system",
        "algorithm",
        "data",
        "digital",
        "network",
        "process",
        "model",
        "technology",
        "automated",
        "interface",
    ],
    "practical_dilemmas": [
        "balance",
        "tension",
        "compromise",
        "choice",
        "value",
        "conflict",
        "decision",
        "priority",
        "trade-off",
        "consideration",
    ],
}

# Topic-distinct vocabulary: terms that are highly specific to a given topic
# and should be preferred over generic cluster vocabulary.
TOPIC_DISTINCT_LEXICON: dict[str, list[str]] = {
    "Risk and decision making": [
        "uncertainty",
        "expected utility",
        "probability weighting",
        "loss aversion",
        "signal",
        "variance",
        "risk premium",
        "gamble",
        "expected value",
    ],
    "Scarcity and human behavior": [
        "deprivation",
        "prioritization",
        "scarcity mindset",
        "rationing",
        "adaptation",
        "delayed gratification",
        "bandwidth",
        "tunneling",
    ],
    "Cognitive bias": [
        "heuristic",
        "anchoring",
        "availability",
        "representativeness",
        "confirmation bias",
        "framing effect",
        "sunk cost",
    ],
    "Memory and identity": [
        "episodic memory",
        "narrative self",
        "autobiographical",
        "recall",
        "recognition",
        "encoding",
        "retrieval",
        "continuity of self",
    ],
    "AI alignment": [
        "corrigibility",
        "reward hacking",
        "value alignment",
        "mesa-optimizer",
        "goal misgeneralization",
        "outer alignment",
        "inner alignment",
    ],
    "Free will vs determinism": [
        "compatibilism",
        "libertarian free will",
        "causal chain",
        "agency",
        "moral responsibility",
        "deterministic universe",
        "randomness",
    ],
}


def get_cluster_wallpaper_terms(cluster: str) -> list[str]:
    """Return cluster-generic wallpaper terms for the given cluster."""
    return CLUSTER_WALLPAPER_TERMS.get(cluster, [])


def get_topic_distinct_lexicon(topic: str) -> list[str]:
    """Return topic-distinct preferred vocabulary for the given topic."""
    return TOPIC_DISTINCT_LEXICON.get(topic, [])


# ---------------------------------------------------------------------------
# Fixy role-aware compliance scoring
# ---------------------------------------------------------------------------


def compute_fixy_compliance_score(
    text: str,
    topic: str,
    topic_anchors: list[str],
    prev_anchors: Optional[list[str]] = None,
    *,
    new_domain_penalty: float = 0.20,
    must_name_topic_or_concept: bool = True,
) -> dict:
    """Compute topic compliance for Fixy using a role-aware rubric.

    Fixy is a meta-observer/intervener, not a content speaker.  Its
    compliance is judged differently:

    - Meta-analytic framing is allowed (e.g. "The dialogue is looping on X").
    - Must name the current topic or at least one core concept from it.
    - Must not introduce a new unrelated domain without tying it back.
    - Scored more on "useful intervention inside this topic" than on
      matching the same rhetorical style as Socrates/Athena.

    Parameters
    ----------
    text:
        Fixy's generated intervention text.
    topic:
        The active session topic label.
    topic_anchors:
        Anchor keywords for the current topic.
    prev_anchors:
        Anchor keywords for the *previous* topic (contamination detection).
    new_domain_penalty:
        Score penalty applied when Fixy introduces a new unrelated domain.
    must_name_topic_or_concept:
        When True, Fixy must explicitly mention the topic name or at least
        one anchor concept, or the score is capped at 0.60.

    Returns
    -------
    dict with keys: ``score``, ``names_topic``, ``new_domain_drift``,
        ``contamination_penalty``, ``fixy_mode``.
    """
    _prev_anchors: list[str] = prev_anchors or []
    text_lower = text.lower()
    topic_lower = topic.lower() if topic else ""

    # 1. Does Fixy name the topic or a core concept?
    names_topic = bool(topic_lower and topic_lower in text_lower)
    names_concept = bool(
        topic_anchors and any(a.lower() in text_lower for a in topic_anchors)
    )
    has_topic_anchor = names_topic or names_concept

    # 2. Contamination from previous topic
    opening = _get_opening_sentences(text, n=2)
    opening_contamination = _contamination_score(opening, _prev_anchors)
    stale_pen = _stale_phrase_penalty(opening)
    contamination_penalty = max(opening_contamination, stale_pen)

    # 3. New-domain drift: text has no anchor keywords at all but has
    #    prior-topic content → possible domain hijack
    full_contamination = _contamination_score(text, _prev_anchors)
    new_domain_drift = full_contamination > 0.4 and not has_topic_anchor

    # 4. Base score: Fixy is given more credit for meta-framing even when
    #    rhetorical style doesn't match the speaker agents.
    base_score = 0.80 if has_topic_anchor else 0.55

    # Cap score when topic/concept is absent and must_name is required
    if must_name_topic_or_concept and not has_topic_anchor:
        base_score = min(base_score, 0.60)

    # Apply penalties
    score = base_score - 0.20 * contamination_penalty
    if new_domain_drift:
        score -= new_domain_penalty
        logger.info(
            "[FIXY-DOMAIN-DRIFT] agent=Fixy topic=%r new_domain_drift=True "
            "full_contamination=%.2f penalty=%.2f",
            topic,
            full_contamination,
            new_domain_penalty,
        )

    score = max(0.0, min(1.0, score))

    result = {
        "score": score,
        "names_topic": names_topic,
        "names_concept": names_concept,
        "new_domain_drift": new_domain_drift,
        "contamination_penalty": contamination_penalty,
        "fixy_mode": True,
    }
    logger.info(
        "[TOPIC-COMPLIANCE-FIXY] agent=Fixy topic=%r names_topic=%s "
        "names_concept=%s new_domain_drift=%s contamination=%.2f score=%.2f",
        topic,
        names_topic,
        names_concept,
        new_domain_drift,
        contamination_penalty,
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

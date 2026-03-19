#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Circularity Guard for Entelgia — pre-generation circularity detection.

Detects four circular dialogue failure modes before a response is accepted:

  1. Semantic repetition     — delta-based score measuring how much the new
                               response exceeds the agent's recent baseline
                               similarity (cosine / Jaccard).
  2. Structural templates    — repeated *rhetorical* frames only; technical
                               vocabulary is tracked separately and does not
                               strongly affect the structural score.
  3. Cross-topic contamination — banned carryover phrases from previous topics.
  4. Composite circularity score — weighted combination of the three signals
                               against an adaptive threshold that grows with
                               history size.

Public API
----------
detect_semantic_repetition(text, previous_texts) -> (bool, float)
detect_structural_templates(text)                -> (bool, int)
detect_cross_topic_contamination(text, topic)    -> (bool, List[str])
compute_circularity_score(text, agent_name, topic, threshold,
                          first_turn_after_topic_change)  -> CircularityResult
get_dynamic_threshold(history_size)              -> float

History management
------------------
add_to_history(agent_name, text)   — call after accepting a response
get_agent_history(agent_name)      — read-only deque of last N responses
clear_history(agent_name=None)     — reset one or all agents

Instruction injection
---------------------
get_new_angle_instruction()        — rotating prompt fragment that forces a new angle
"""

from __future__ import annotations

import logging
import re
from collections import deque
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Optional semantic-similarity dependencies (sentence-transformers + sklearn)
# ---------------------------------------------------------------------------
try:
    from sentence_transformers import SentenceTransformer
    from sklearn.metrics.pairwise import cosine_similarity as _cosine_similarity
    import numpy as np  # noqa: F401

    _ST_MODEL: Optional[SentenceTransformer] = None
    _SEMANTIC_AVAILABLE = True
except ImportError:
    _SEMANTIC_AVAILABLE = False
    _ST_MODEL = None
    _cosine_similarity = None  # type: ignore[assignment]

# ---------------------------------------------------------------------------
# Configuration constants
# ---------------------------------------------------------------------------

#: Number of recent responses stored per agent.
HISTORY_SIZE: int = 10

#: Minimum number of previous responses required before semantic repetition detection
#: can fire.  Fewer prior responses are insufficient to establish a repetition pattern.
MIN_HISTORY_FOR_DETECTION: int = 3

#: Threshold for the delta-based cosine repetition score.
#: The delta score is typically in [0, ~0.75], so this is lower than a raw cosine threshold.
SEMANTIC_REPETITION_THRESHOLD: float = 0.45

#: Threshold for the delta-based Jaccard repetition score.
JACCARD_REPETITION_THRESHOLD: float = 0.40

#: Number of *rhetorical* pattern matches needed to flag structural repetition.
TEMPLATE_COUNT_THRESHOLD: int = 2

#: Number of contamination phrases needed to flag cross-topic leakage.
CONTAMINATION_THRESHOLD: int = 1

#: Default composite circularity score threshold (used as a fallback constant).
#: In practice ``compute_circularity_score`` uses ``get_dynamic_threshold()``.
CIRCULARITY_SCORE_THRESHOLD: float = 0.5

#: Score multiplier applied on the first response turn after a topic change,
#: providing leniency because framing language naturally overlaps on topic transitions.
FIRST_TURN_SCORE_FACTOR: float = 0.7

#: Sentence-transformers model name used for semantic similarity.
_SEMANTIC_MODEL_NAME: str = "all-MiniLM-L6-v2"

# ---------------------------------------------------------------------------
# Module-level state: per-agent rolling history
# ---------------------------------------------------------------------------

_agent_history: Dict[str, deque] = {}

# ---------------------------------------------------------------------------
# Rhetorical template patterns — ONLY these affect the structural score.
# Technical vocabulary (tradeoff, optimization, …) is catalogued separately
# and intentionally excluded from circularity scoring.
# ---------------------------------------------------------------------------

_RHETORICAL_PATTERNS: List[re.Pattern] = [
    # "let us examine / define / scrutinize / explore / consider / investigate"
    re.compile(
        r"\blet us\b.{0,30}\b(examine|explore|consider|investigate|define|scrutinize)\b",
        re.I,
    ),
    # "I identify/note/observe/see a critical …"
    re.compile(r"\bi (identify|note|observe|see) a critical\b", re.I),
    # "on one hand / on the other hand / on the one hand"
    re.compile(r"\b(on one hand|on the other hand|on the one hand)\b", re.I),
    # "at its/the core"
    re.compile(r"\b(at its core|at the core)\b", re.I),
    # "the fundamental tension / question / issue / problem"
    re.compile(r"\bthe fundamental (question|tension|issue|problem)\b", re.I),
    # "we must balance / weigh / consider"
    re.compile(r"\bwe must (balance|weigh|consider)\b", re.I),
    # "in our scrutiny"
    re.compile(r"\bin our scrutiny\b", re.I),
    # "there is/are two / a fundamental / a tension between"
    re.compile(r"\bthere (is|are) (two|2|a tension between|a fundamental)\b", re.I),
    # Duplicated speaker prefix — e.g. "Fixy: Fixy:"
    re.compile(r"(\b\w+)\s*:\s*\1\s*:", re.I),
]

# ---------------------------------------------------------------------------
# Technical vocabulary — tracked but NOT counted toward structural score.
# Present here for documentation and potential future analysis only.
# ---------------------------------------------------------------------------

_TECHNICAL_VOCABULARY: List[re.Pattern] = [
    re.compile(r"\btradeoff[s]?\b|\btrade-off[s]?\b|\btrade off[s]?\b", re.I),
    re.compile(r"\barchitecture\b", re.I),
    re.compile(r"\boptimization\b", re.I),
    re.compile(r"\bsystem constraint[s]?\b", re.I),
    re.compile(r"\bfailure mode[s]?\b", re.I),
]

# ---------------------------------------------------------------------------
# Cross-topic carryover phrase sets
# ---------------------------------------------------------------------------

#: Topic-specific carryover phrases that should not bleed into the named topic.
_CARRYOVER_PHRASES_BY_TOPIC: Dict[str, List[str]] = {
    "ethics & responsibility": [
        "system constraint",
        "optimization function",
        "alignment objective",
    ],
    "AI alignment": [
        "moral duty",
        "categorical imperative",
        "deontological",
    ],
    "free will & determinism": [
        "resource allocation",
        "computational cost",
        "system optimization",
    ],
    "consciousness & self-models": [
        "resource constraint",
        "cost-benefit",
        "optimization",
    ],
    "truth & epistemology": [
        "option a",
        "option b",
        "tradeoff",
    ],
    "emotion and rationality": [
        "system architecture",
        "computational",
    ],
}

#: Generic carryover phrases that apply to every topic.
_GENERIC_CARRYOVER_PHRASES: List[str] = [
    "option a",
    "option b",
    "scenario a",
    "scenario b",
    "as discussed previously",
    "in the previous topic",
    "as we established",
    "as i mentioned",
    "building on what was said",
    "to summarize our findings",
]

#: Leaked rhetorical template phrases that signal template bleed-over
#: regardless of topic.
_LEAKED_TEMPLATE_PHRASES: List[str] = [
    "forgiveness",
    "peace and harmony",
    "our community",
    "practical dilemma",
]

# ---------------------------------------------------------------------------
# New-angle instructions (rotate to avoid repeating the same nudge)
# ---------------------------------------------------------------------------

_NEW_ANGLE_INSTRUCTIONS: List[str] = [
    "Shift your analytical frame entirely. Do not reuse your previous reasoning structure.",
    "Approach this from a completely different conceptual direction.",
    "Use a concrete example or analogy you have not mentioned before.",
    "Introduce a new distinction or concept that has not appeared yet.",
    "Challenge an assumption that has been treated as fixed so far.",
    "Ground your response in a specific historical or empirical case.",
]

_new_angle_index: int = 0


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _get_semantic_model() -> Optional["SentenceTransformer"]:
    """Lazily load and cache the SentenceTransformer model."""
    global _ST_MODEL
    if _ST_MODEL is None:
        try:
            logger.info(
                "CircularityGuard: loading SentenceTransformer '%s'…",
                _SEMANTIC_MODEL_NAME,
            )
            _ST_MODEL = SentenceTransformer(_SEMANTIC_MODEL_NAME)  # type: ignore[name-defined]
            logger.info("CircularityGuard: model loaded.")
        except Exception as exc:  # pragma: no cover
            logger.warning("CircularityGuard: could not load model: %s", exc)
    return _ST_MODEL


def _jaccard(a: str, b: str) -> float:
    """Token-level Jaccard similarity between two texts."""
    sa = set(re.findall(r"\w+", a.lower()))
    sb = set(re.findall(r"\w+", b.lower()))
    union = sa | sb
    if not union:
        return 0.0
    return len(sa & sb) / len(union)


def _delta_score(similarities: List[float]) -> float:
    """Compute the delta-based repetition score from a list of similarity values.

    Formula: ``max(0.0, max_sim - avg_last_3 * 0.5)``

    The average of the three most-recent similarity values acts as a
    topic-consistency baseline.  Subtracting half that baseline from the
    maximum prevents same-topic responses from being over-penalised while
    still catching genuine circular repetition.
    """
    if not similarities:
        return 0.0
    max_sim = max(similarities)
    last_3 = similarities[-3:]
    avg_last_3 = sum(last_3) / len(last_3)
    return max(0.0, max_sim - avg_last_3 * 0.5)


# ---------------------------------------------------------------------------
# History management
# ---------------------------------------------------------------------------


def get_agent_history(agent_name: str) -> deque:
    """Return (creating if necessary) the rolling response history for *agent_name*."""
    if agent_name not in _agent_history:
        _agent_history[agent_name] = deque(maxlen=HISTORY_SIZE)
    return _agent_history[agent_name]


def add_to_history(agent_name: str, text: str) -> None:
    """Append *text* to *agent_name*'s rolling history."""
    get_agent_history(agent_name).append(text)


def clear_history(agent_name: Optional[str] = None) -> None:
    """Clear history for *agent_name*, or all agents when *agent_name* is ``None``."""
    if agent_name is None:
        _agent_history.clear()
    elif agent_name in _agent_history:
        _agent_history[agent_name].clear()


# ---------------------------------------------------------------------------
# Adaptive threshold
# ---------------------------------------------------------------------------


def get_dynamic_threshold(history_size: int) -> float:
    """Return an adaptive circularity threshold based on *history_size*.

    As the agent builds up more history the guard can afford to be stricter
    because it has more evidence.  The threshold grows linearly from 0.55 at
    zero turns, capping at 0.70 once history is large.

    Formula: ``min(0.70, 0.55 + 0.01 * history_size)``
    """
    return min(0.70, 0.55 + 0.01 * history_size)


# ---------------------------------------------------------------------------
# 1. Semantic repetition detection
# ---------------------------------------------------------------------------


def detect_semantic_repetition(
    text: str,
    previous_texts: List[str],
    threshold: float = SEMANTIC_REPETITION_THRESHOLD,
    min_history: int = MIN_HISTORY_FOR_DETECTION,
) -> Tuple[bool, float]:
    """Detect whether *text* is semantically too similar to the agent's recent history.

    Uses a **delta-based** score to reduce false positives on same-topic
    responses:

    .. code-block:: text

        score = max(0.0, max_similarity - avg_similarity_last_3 * 0.5)

    When sentence-transformers is available the similarities are cosine
    distances from ``all-MiniLM-L6-v2`` embeddings.  Falls back to
    token-level Jaccard similarity when the library is absent or model
    loading fails.

    Returns ``(detected, delta_score)``.

    Parameters
    ----------
    text:
        The candidate response to check.
    previous_texts:
        The agent's recent responses (up to the last ``HISTORY_SIZE``).
    threshold:
        Delta score above which repetition is flagged.  Applied to both the
        cosine path (default ``SEMANTIC_REPETITION_THRESHOLD``) and the
        Jaccard fallback (which additionally checks against
        ``JACCARD_REPETITION_THRESHOLD``).
    min_history:
        Minimum number of entries in *previous_texts* required before
        detection can fire.  Defaults to ``MIN_HISTORY_FOR_DETECTION`` (3).
    """
    if len(previous_texts) < min_history:
        return False, 0.0

    if _SEMANTIC_AVAILABLE:
        model = _get_semantic_model()
        if model is not None:
            try:
                all_texts = list(previous_texts) + [text]
                embeddings = model.encode(all_texts)
                query_emb = embeddings[-1].reshape(1, -1)
                prev_embs = embeddings[:-1]
                raw_sims = _cosine_similarity(query_emb, prev_embs)[0]
                sims = [float(s) for s in raw_sims]
                delta = _delta_score(sims)
                logger.debug(
                    "[CircularityGuard] semantic: max_sim=%.3f avg_last3=%.3f delta=%.3f",
                    max(sims),
                    sum(sims[-3:]) / len(sims[-3:]),
                    delta,
                )
                return delta >= threshold, delta
            except Exception as exc:  # pragma: no cover
                logger.warning("CircularityGuard: semantic encoding failed: %s", exc)

    # Jaccard fallback
    jaccards = [_jaccard(text, prev) for prev in previous_texts]
    delta_j = _delta_score(jaccards)
    logger.debug(
        "[CircularityGuard] jaccard: max=%.3f avg_last3=%.3f delta=%.3f",
        max(jaccards),
        sum(jaccards[-3:]) / len(jaccards[-3:]),
        delta_j,
    )
    return delta_j >= JACCARD_REPETITION_THRESHOLD, delta_j


# ---------------------------------------------------------------------------
# 2. Structural template detection (rhetorical patterns only)
# ---------------------------------------------------------------------------


def detect_structural_templates(text: str) -> Tuple[bool, int]:
    """Detect repeated *rhetorical* structural templates in *text*.

    Only patterns in ``_RHETORICAL_PATTERNS`` are counted.  Technical
    vocabulary (``_TECHNICAL_VOCABULARY``) is intentionally excluded so that
    normal on-topic language does not raise false positives.

    Returns ``(detected, rhetorical_match_count)`` where *detected* is
    ``True`` when *rhetorical_match_count* reaches ``TEMPLATE_COUNT_THRESHOLD``.
    """
    matched: List[str] = []
    for pat in _RHETORICAL_PATTERNS:
        if pat.search(text):
            matched.append(pat.pattern)
    count = len(matched)
    if count > 0:
        logger.debug("[CircularityGuard] rhetorical patterns matched: %s", matched)
    return count >= TEMPLATE_COUNT_THRESHOLD, count


# ---------------------------------------------------------------------------
# 3. Cross-topic contamination detection
# ---------------------------------------------------------------------------


def detect_cross_topic_contamination(
    text: str,
    topic: str,
    contamination_threshold: int = CONTAMINATION_THRESHOLD,
) -> Tuple[bool, List[str]]:
    """Detect banned carryover phrases and leaked templates in *text*.

    Checks three phrase sets in order:
    1. Generic cross-topic carryover phrases (``_GENERIC_CARRYOVER_PHRASES``).
    2. Leaked rhetorical template phrases (``_LEAKED_TEMPLATE_PHRASES``).
    3. Topic-specific banned phrases (``_CARRYOVER_PHRASES_BY_TOPIC[topic]``).

    Returns ``(detected, list_of_found_phrases)``.
    """
    text_lower = text.lower()
    found: List[str] = []

    for phrase in _GENERIC_CARRYOVER_PHRASES:
        if phrase.lower() in text_lower:
            found.append(phrase)

    for phrase in _LEAKED_TEMPLATE_PHRASES:
        p_lower = phrase.lower()
        if p_lower in text_lower and phrase not in found:
            found.append(phrase)

    topic_phrases = _CARRYOVER_PHRASES_BY_TOPIC.get(topic, [])
    for phrase in topic_phrases:
        p_lower = phrase.lower()
        if p_lower in text_lower and phrase not in found:
            found.append(phrase)

    if found:
        logger.debug("[CircularityGuard] contamination phrases found: %s", found)

    return len(found) >= contamination_threshold, found


# ---------------------------------------------------------------------------
# 4. Composite circularity score
# ---------------------------------------------------------------------------


@dataclass
class CircularityResult:
    """Full circularity check result returned by :func:`compute_circularity_score`."""

    is_circular: bool
    """Whether the composite score exceeds the detection threshold."""

    score: float
    """Composite circularity score in ``[0, 1]``."""

    semantic_score: float
    """Delta-based semantic repetition score (cosine or Jaccard delta)."""

    template_count: int
    """Number of rhetorical template patterns matched."""

    contamination_phrases: List[str]
    """Carryover / leaked-template phrases detected in the text."""

    threshold: float
    """The detection threshold used for this check (dynamic or explicit)."""

    reasons: List[str] = field(default_factory=list)
    """Human-readable list of triggered detection signals."""


def compute_circularity_score(
    text: str,
    agent_name: str,
    topic: str = "",
    threshold: Optional[float] = None,
    first_turn_after_topic_change: bool = False,
) -> CircularityResult:
    """Compute a composite circularity score for *text* against *agent_name*'s history.

    The composite score is a weighted average of three signals:

    * **Semantic repetition** (weight 0.5) — delta-based cosine / Jaccard
      score against the agent's recent responses.
    * **Structural templates** (weight 0.3) — presence of repeated *rhetorical*
      frames, capped at 5 matches → 1.0.
    * **Cross-topic contamination** (weight 0.2) — carryover phrase count,
      capped at 5 → 1.0.

    The detection threshold is adaptive by default: it increases with history
    size via :func:`get_dynamic_threshold`.  Pass an explicit *threshold* to
    override (e.g. ``threshold=0.0`` in tests).

    When *first_turn_after_topic_change* is ``True`` the raw score is
    multiplied by ``FIRST_TURN_SCORE_FACTOR`` to provide leniency on the
    first turn of a new topic.

    Returns a :class:`CircularityResult`; call :func:`add_to_history`
    **after** the response has been accepted to keep the history current.
    """
    history = list(get_agent_history(agent_name))
    effective_threshold = (
        threshold if threshold is not None else get_dynamic_threshold(len(history))
    )

    sem_detected, sem_score = detect_semantic_repetition(text, history)
    sem_component = sem_score

    tpl_detected, tpl_count = detect_structural_templates(text)
    tpl_component = min(tpl_count / 5.0, 1.0)

    ct_detected, ct_phrases = detect_cross_topic_contamination(text, topic)
    ct_component = min(len(ct_phrases) / 5.0, 1.0)

    raw_score = 0.5 * sem_component + 0.3 * tpl_component + 0.2 * ct_component

    # Apply leniency factor on the first turn after a topic change
    score = (
        raw_score * FIRST_TURN_SCORE_FACTOR
        if first_turn_after_topic_change
        else raw_score
    )

    reasons: List[str] = []
    if sem_detected:
        reasons.append(f"semantic_repetition(score={sem_score:.2f})")
    if tpl_detected:
        reasons.append(f"structural_templates(count={tpl_count})")
    if ct_detected:
        reasons.append(f"cross_topic_contamination(phrases={ct_phrases})")

    is_circular = score >= effective_threshold

    logger.debug(
        "[CircularityGuard] agent=%s topic=%r "
        "sem=%.3f tpl=%.3f ct=%.3f raw=%.3f score=%.3f threshold=%.3f "
        "first_turn=%s circular=%s",
        agent_name,
        topic,
        sem_component,
        tpl_component,
        ct_component,
        raw_score,
        score,
        effective_threshold,
        first_turn_after_topic_change,
        is_circular,
    )

    if is_circular:
        logger.info(
            "[CircularityGuard] agent=%s topic=%r circular score=%.2f "
            "threshold=%.2f reasons=%s",
            agent_name,
            topic,
            score,
            effective_threshold,
            reasons,
        )

    return CircularityResult(
        is_circular=is_circular,
        score=score,
        semantic_score=sem_score,
        template_count=tpl_count,
        contamination_phrases=ct_phrases,
        threshold=effective_threshold,
        reasons=reasons,
    )


# ---------------------------------------------------------------------------
# Instruction injection
# ---------------------------------------------------------------------------


def get_new_angle_instruction() -> str:
    """Return the next new-angle prompt instruction (rotates through the list)."""
    global _new_angle_index
    instruction = _NEW_ANGLE_INSTRUCTIONS[
        _new_angle_index % len(_NEW_ANGLE_INSTRUCTIONS)
    ]
    _new_angle_index += 1
    return instruction

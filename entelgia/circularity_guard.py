#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Circularity Guard for Entelgia — pre-generation circularity detection.

Detects four circular dialogue failure modes before a response is accepted:

  1. Semantic repetition     — the generated text is too similar to the
                               agent's recent responses (cosine / Jaccard).
  2. Structural templates    — repeated rhetorical frames and openings.
  3. Cross-topic contamination — banned carryover phrases from previous topics.
  4. Composite circularity score — weighted combination of the three signals.

Public API
----------
detect_semantic_repetition(text, previous_texts) -> (bool, float)
detect_structural_templates(text)                -> (bool, int)
detect_cross_topic_contamination(text, topic)    -> (bool, List[str])
compute_circularity_score(text, agent_name, topic, threshold) -> CircularityResult

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
    import numpy as _np  # noqa: F401 — imported so we can type-check

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

#: Cosine-similarity threshold above which semantic repetition is flagged.
SEMANTIC_REPETITION_THRESHOLD: float = 0.75

#: Jaccard similarity threshold (used when sentence-transformers is absent).
JACCARD_REPETITION_THRESHOLD: float = 0.55

#: Number of structural template matches needed to flag a response.
TEMPLATE_COUNT_THRESHOLD: int = 2

#: Number of contamination phrases needed to flag a response.
CONTAMINATION_THRESHOLD: int = 1

#: Composite circularity score at or above which a response is considered circular.
CIRCULARITY_SCORE_THRESHOLD: float = 0.5

# ---------------------------------------------------------------------------
# Module-level state: per-agent rolling history
# ---------------------------------------------------------------------------

_agent_history: Dict[str, deque] = {}

# ---------------------------------------------------------------------------
# Structural rhetorical template patterns
# ---------------------------------------------------------------------------

_RHETORICAL_TEMPLATES: List[re.Pattern] = [
    re.compile(r"\blet us\b.{0,30}\b(examine|explore|consider|investigate)\b", re.I),
    re.compile(r"\bi (identify|note|observe|see) a critical\b", re.I),
    re.compile(r"\bsystem constraint[s]?\b", re.I),
    re.compile(r"\btradeoff[s]?\b|\btrade-off[s]?\b|\btrade off[s]?\b", re.I),
    re.compile(r"\boption [ab]\b.{0,60}\boption [ab]\b", re.I | re.S),
    re.compile(r"\b(on one hand|on the other hand)\b", re.I),
    re.compile(r"\b(at its core|at the core)\b", re.I),
    re.compile(r"\bthe fundamental (question|tension|issue|problem)\b", re.I),
    re.compile(r"\bwe must (balance|weigh|consider)\b", re.I),
    re.compile(r"\bthere (is|are) (two|2|a tension between|a fundamental)\b", re.I),
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
    "as discussed previously",
    "as we established",
    "as i mentioned",
    "building on what was said",
    "to summarize our findings",
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
            logger.info("CircularityGuard: loading SentenceTransformer 'all-MiniLM-L6-v2'…")
            _ST_MODEL = SentenceTransformer("all-MiniLM-L6-v2")  # type: ignore[name-defined]
            logger.info("CircularityGuard: model loaded.")
        except Exception as exc:  # pragma: no cover
            logger.warning("CircularityGuard: could not load model: %s", exc)
    return _ST_MODEL


def _jaccard(a: str, b: str) -> float:
    """Token-level Jaccard similarity between two texts."""
    sa = set(re.findall(r"\w+", a.lower()))
    sb = set(re.findall(r"\w+", b.lower()))
    if not sa and not sb:
        return 0.0
    union = sa | sb
    if not union:
        return 0.0
    return len(sa & sb) / len(union)


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
# 1. Semantic repetition detection
# ---------------------------------------------------------------------------


def detect_semantic_repetition(
    text: str,
    previous_texts: List[str],
    threshold: float = SEMANTIC_REPETITION_THRESHOLD,
    min_history: int = MIN_HISTORY_FOR_DETECTION,
) -> Tuple[bool, float]:
    """Detect whether *text* is semantically too similar to any of *previous_texts*.

    Returns ``(detected, max_similarity_score)``.

    When sentence-transformers is available, uses cosine similarity on
    ``all-MiniLM-L6-v2`` embeddings.  Falls back to token-level Jaccard
    similarity when the library is absent or model loading fails.

    Parameters
    ----------
    text:
        The candidate response to check.
    previous_texts:
        The agent's recent responses (up to the last ``HISTORY_SIZE``).
    threshold:
        Similarity threshold above which repetition is flagged.  Applied to
        cosine similarity when sentence-transformers is available.  When the
        Jaccard fallback is used instead, ``JACCARD_REPETITION_THRESHOLD`` is
        applied unconditionally — the *threshold* parameter does not affect the
        Jaccard path, because Jaccard and cosine similarity operate on different
        scales.  Callers that need to adjust Jaccard sensitivity should modify
        ``JACCARD_REPETITION_THRESHOLD`` directly.
    min_history:
        Minimum number of entries in *previous_texts* required before detection
        can fire.  Defaults to ``MIN_HISTORY_FOR_DETECTION`` (3).  Callers may
        lower this for testing purposes.
    """
    if len(previous_texts) < min_history:
        return False, 0.0

    max_score = 0.0

    if _SEMANTIC_AVAILABLE:
        model = _get_semantic_model()
        if model is not None:
            try:
                all_texts = list(previous_texts) + [text]
                embeddings = model.encode(all_texts)
                query_emb = embeddings[-1].reshape(1, -1)
                prev_embs = embeddings[:-1]
                sims = _cosine_similarity(query_emb, prev_embs)[0]
                max_score = float(max(sims))
                return max_score >= threshold, max_score
            except Exception as exc:  # pragma: no cover
                logger.warning("CircularityGuard: semantic encoding failed: %s", exc)

    # Jaccard fallback
    for prev in previous_texts:
        score = _jaccard(text, prev)
        if score > max_score:
            max_score = score
    return max_score >= JACCARD_REPETITION_THRESHOLD, max_score


# ---------------------------------------------------------------------------
# 2. Structural template detection
# ---------------------------------------------------------------------------


def detect_structural_templates(text: str) -> Tuple[bool, int]:
    """Detect repeated rhetorical structural templates in *text*.

    Returns ``(detected, match_count)`` where *detected* is ``True`` when
    *match_count* reaches ``TEMPLATE_COUNT_THRESHOLD``.
    """
    count = sum(1 for pat in _RHETORICAL_TEMPLATES if pat.search(text))
    return count >= TEMPLATE_COUNT_THRESHOLD, count


# ---------------------------------------------------------------------------
# 3. Cross-topic contamination detection
# ---------------------------------------------------------------------------


def detect_cross_topic_contamination(
    text: str,
    topic: str,
    contamination_threshold: int = CONTAMINATION_THRESHOLD,
) -> Tuple[bool, List[str]]:
    """Detect banned carryover phrases from other topics leaking into *text*.

    Checks both the generic carryover list and the topic-specific list for
    *topic*.

    Returns ``(detected, list_of_found_phrases)``.
    """
    text_lower = text.lower()
    found: List[str] = []

    for phrase in _GENERIC_CARRYOVER_PHRASES:
        if phrase.lower() in text_lower:
            found.append(phrase)

    topic_phrases = _CARRYOVER_PHRASES_BY_TOPIC.get(topic, [])
    for phrase in topic_phrases:
        p_lower = phrase.lower()
        if p_lower in text_lower and phrase not in found:
            found.append(phrase)

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
    """Raw semantic similarity score (cosine or Jaccard)."""

    template_count: int
    """Number of rhetorical template patterns matched."""

    contamination_phrases: List[str]
    """Carryover phrases detected in the text."""

    reasons: List[str] = field(default_factory=list)
    """Human-readable list of triggered detection signals."""


def compute_circularity_score(
    text: str,
    agent_name: str,
    topic: str = "",
    threshold: float = CIRCULARITY_SCORE_THRESHOLD,
) -> CircularityResult:
    """Compute a composite circularity score for *text* against *agent_name*'s history.

    The composite score is a weighted average of three signals:

    * **Semantic repetition** (weight 0.5) — cosine / Jaccard similarity to
      the agent's recent responses.
    * **Structural templates** (weight 0.3) — presence of repeated rhetorical
      frames, capped at 5 matches → 1.0.
    * **Cross-topic contamination** (weight 0.2) — carryover phrase count,
      capped at 5 → 1.0.

    Returns a :class:`CircularityResult` with ``is_circular=True`` when the
    composite score is at or above *threshold*.

    .. note::
       Call :func:`add_to_history` **after** the response has been accepted to
       keep the history current.
    """
    history = list(get_agent_history(agent_name))

    sem_detected, sem_score = detect_semantic_repetition(text, history)
    sem_component = sem_score

    tpl_detected, tpl_count = detect_structural_templates(text)
    tpl_component = min(tpl_count / 5.0, 1.0)

    ct_detected, ct_phrases = detect_cross_topic_contamination(text, topic)
    ct_component = min(len(ct_phrases) / 5.0, 1.0)

    score = 0.5 * sem_component + 0.3 * tpl_component + 0.2 * ct_component

    reasons: List[str] = []
    if sem_detected:
        reasons.append(f"semantic_repetition(score={sem_score:.2f})")
    if tpl_detected:
        reasons.append(f"structural_templates(count={tpl_count})")
    if ct_detected:
        reasons.append(f"cross_topic_contamination(phrases={ct_phrases})")

    is_circular = score >= threshold
    if is_circular:
        logger.info(
            "[CircularityGuard] agent=%s topic=%r circular score=%.2f reasons=%s",
            agent_name,
            topic,
            score,
            reasons,
        )

    return CircularityResult(
        is_circular=is_circular,
        score=score,
        semantic_score=sem_score,
        template_count=tpl_count,
        contamination_phrases=ct_phrases,
        reasons=reasons,
    )


# ---------------------------------------------------------------------------
# Instruction injection
# ---------------------------------------------------------------------------


def get_new_angle_instruction() -> str:
    """Return the next new-angle prompt instruction (rotates through the list)."""
    global _new_angle_index
    instruction = _NEW_ANGLE_INSTRUCTIONS[_new_angle_index % len(_NEW_ANGLE_INSTRUCTIONS)]
    _new_angle_index += 1
    return instruction

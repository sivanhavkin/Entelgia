#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Response Evaluator for Entelgia — quality measurement layer.

Provides an independent evaluation score for each generated response.
This score is **measurement-only** and does not influence any engine
behaviour, thresholds, or Fixy logic.

The ``evaluate_response`` score is designed to be complementary to the
progress-enforcer ``engine_score``: while ``engine_score`` measures
*argumentative progress* (move-type analysis), ``evaluate_response``
measures *linguistic quality* of the response text.

Scoring components (all additive, result clamped to [0.0, 1.0])
----------------------------------------------------------------
+0.25  lexical diversity   — type-token ratio of content words
+0.20  specificity         — concrete nouns, numbers, named concepts
+0.20  sentence complexity — average tokens per sentence (moderate is best)
+0.20  depth               — word-count in the productive range (50–300)
−0.10  per-hedge cluster   — vague/filler phrases (up to −0.30)

Public API
----------
evaluate_response(response, context) -> float
"""

from __future__ import annotations

import re
from typing import List, Sequence

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Hedge / filler phrases that reduce perceived quality
_HEDGE_PHRASES: List[str] = [
    r"\bperhaps\b",
    r"\bmaybe\b",
    r"\bsomewhat\b",
    r"\bin a sense\b",
    r"\bto some extent\b",
    r"\bit could be argued\b",
    r"\bsome might say\b",
    r"\bone could argue\b",
    r"\binteresting(ly)?\b",
    r"\bcertainly\b",
    r"\bobviously\b",
    r"\bof course\b",
    r"\bneedless to say\b",
    r"\bkind of\b",
    r"\bsort of\b",
]

# Common English stop-words — excluded from lexical diversity calculation
_STOP_WORDS: frozenset = frozenset(
    {
        "a", "an", "the", "and", "or", "but", "if", "in", "on", "at", "to",
        "for", "of", "with", "by", "from", "is", "are", "was", "were", "be",
        "been", "being", "have", "has", "had", "do", "does", "did", "will",
        "would", "could", "should", "may", "might", "shall", "can", "need",
        "that", "this", "these", "those", "it", "its", "they", "them", "their",
        "we", "our", "you", "your", "he", "his", "she", "her", "i", "my",
        "not", "no", "so", "as", "up", "out", "about", "into", "than", "then",
        "there", "here", "which", "who", "what", "when", "where", "how",
        "also", "just", "more", "very", "all", "each", "both", "few", "most",
        "other", "such", "even", "well", "still", "yet", "nor", "any",
    }
)

# Targets for sentence-length complexity scoring.
# Research on readability and philosophical discourse suggests that
# 10–25 tokens per sentence strikes the balance between depth and clarity.
_IDEAL_AVG_TOKENS_LOW = 10
_IDEAL_AVG_TOKENS_HIGH = 25

# Word-count range for the depth score
_DEPTH_LOW = 50
_DEPTH_HIGH = 300

# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _tokenize(text: str) -> List[str]:
    """Return a list of lowercase word tokens, stripped of punctuation."""
    return re.findall(r"[a-z]+", text.lower())


def _split_sentences(text: str) -> List[str]:
    """Split text into sentences using punctuation boundaries."""
    parts = re.split(r"[.!?]+", text)
    return [p.strip() for p in parts if p.strip()]


def _lexical_diversity(tokens: List[str]) -> float:
    """Type-token ratio of content words (stop-words excluded)."""
    content = [t for t in tokens if t not in _STOP_WORDS]
    if not content:
        return 0.0
    return min(len(set(content)) / len(content), 1.0)


def _specificity_score(text: str) -> float:
    """Estimate concreteness via numbers, proper nouns, and named concepts."""
    score = 0.0
    # Numeric values signal concrete claims
    numeric_matches = re.findall(r"\b\d+(?:[.,]\d+)?\b", text)
    score += min(len(numeric_matches) * 0.05, 0.15)
    # Uppercase mid-sentence tokens suggest named entities / proper nouns.
    # The negative lookbehinds filter out sentence-initial capitals
    # (characters preceded by a sentence-ending punctuation mark and space).
    mid_sentence_caps = re.findall(r"(?<![.!?]\s)(?<![.!?])\b[A-Z][a-z]{2,}\b", text)
    score += min(len(mid_sentence_caps) * 0.03, 0.15)
    # Quoted material or technical-looking tokens
    quoted = re.findall(r'"[^"]{3,}"', text)
    score += min(len(quoted) * 0.05, 0.10)
    return min(score, 1.0)


def _complexity_score(sentences: List[str], tokens: List[str]) -> float:
    """Score based on average tokens per sentence (moderate length is best)."""
    if not sentences:
        return 0.0
    avg = len(tokens) / len(sentences)
    if _IDEAL_AVG_TOKENS_LOW <= avg <= _IDEAL_AVG_TOKENS_HIGH:
        return 1.0
    if avg < _IDEAL_AVG_TOKENS_LOW:
        return avg / _IDEAL_AVG_TOKENS_LOW
    # Penalise very long sentences linearly; 25.0 represents the range from
    # _IDEAL_AVG_TOKENS_HIGH (25) to the maximum-penalty point at 50 tokens/sent.
    return max(0.0, 1.0 - (avg - _IDEAL_AVG_TOKENS_HIGH) / 25.0)


def _depth_score(word_count: int) -> float:
    """Score word-count depth: best between _DEPTH_LOW and _DEPTH_HIGH."""
    if word_count < 1:
        return 0.0
    if word_count < _DEPTH_LOW:
        return word_count / _DEPTH_LOW
    if word_count <= _DEPTH_HIGH:
        return 1.0
    # Gradual penalty for very long responses; 300.0 means zero depth credit
    # is reached at _DEPTH_HIGH + 300 words (600 words total).
    return max(0.0, 1.0 - (word_count - _DEPTH_HIGH) / 300.0)


def _hedge_penalty(text: str) -> float:
    """Return total penalty for hedge/filler phrases (capped at 0.30)."""
    count = 0
    for pattern in _HEDGE_PHRASES:
        count += len(re.findall(pattern, text, re.IGNORECASE))
    return min(count * 0.10, 0.30)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def evaluate_response(response: str, context: Sequence[str]) -> float:
    """Evaluate the linguistic quality of *response*.

    Parameters
    ----------
    response:
        The generated agent response text.
    context:
        Recent dialogue history (list of plain-text turns).  Reserved for
        future use; currently not used in scoring to keep this step
        measurement-only.

    Returns
    -------
    float
        Quality score in [0.0, 1.0].  Higher is better.
    """
    if not response or not response.strip():
        return 0.0

    tokens = _tokenize(response)
    sentences = _split_sentences(response)
    word_count = len(tokens)

    diversity = _lexical_diversity(tokens)
    specificity = _specificity_score(response)
    complexity = _complexity_score(sentences, tokens)
    depth = _depth_score(word_count)
    hedge_pen = _hedge_penalty(response)

    raw = (
        0.25 * diversity
        + 0.20 * specificity
        + 0.20 * complexity
        + 0.20 * depth
        - hedge_pen
    )

    return max(0.0, min(1.0, raw))

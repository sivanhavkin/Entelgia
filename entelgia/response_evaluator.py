#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Response Evaluator for Entelgia — quality and dialogue-movement measurement.

Provides two independent, measurement-only scores for each generated response.
Neither score influences engine behaviour, thresholds, or Fixy logic.

Step 1 — Linguistic quality (``evaluate_response``)
----------------------------------------------------
Measures writing quality independently of dialogue position.

Scoring components (all additive, result clamped to [0.0, 1.0])
+0.25  lexical diversity   — type-token ratio of content words
+0.20  specificity         — concrete nouns, numbers, named concepts
+0.20  sentence complexity — average tokens per sentence (moderate is best)
+0.20  depth               — word-count in the productive range (50–300)
−0.10  per-hedge cluster   — vague/filler phrases (up to −0.30)

Step 2 — Dialogue movement (``evaluate_dialogue_movement``)
-----------------------------------------------------------
Measures whether the response moved the conversation forward.

Scoring components
+0.15  new claim          — response is not too similar to the last turn
+0.15  pressure           — response creates tension or sharpens disagreement
+0.25  resolution         — response narrows, decides, concedes, or collapses
−0.20  semantic repeat    — response is too similar to recent dialogue history
Base score: 0.40

Public API
----------
evaluate_response(response, context) -> float
evaluate_dialogue_movement(response, context) -> float
evaluate_dialogue_movement_with_signals(response, context) -> DialogueSignals
is_new_claim(response, context) -> bool
is_semantic_repeat(response, context) -> bool
creates_pressure(response) -> bool
shows_resolution(response) -> bool

Step 3 — Pressure synchronisation (``compute_pressure_alignment``)
-------------------------------------------------------------------
Measurement-only comparison layer between the agent's internal
DrivePressure (meta signal) and the dialogue-pressure flag (text signal).
Does not influence engine behaviour, scores, or Fixy logic.

compute_pressure_alignment(meta_pressure, dialogue_pressure) -> str
"""

from __future__ import annotations

import re
from typing import List, Sequence, TypedDict

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
# Dialogue-movement constants
# ---------------------------------------------------------------------------

# Similarity threshold above which a response is not considered a new claim
_NEW_CLAIM_SIMILARITY_THRESHOLD = 0.75

# Similarity threshold above which a response is considered a semantic repeat
_SEMANTIC_REPEAT_THRESHOLD = 0.82

# How many recent context turns to consider for semantic-repeat detection
_RECENT_TURNS_WINDOW = 5

# Keywords that signal argumentative pressure / contradiction.
# Intentionally kept as simple substrings for the measurement-only heuristic —
# some false positives are acceptable at this stage.
_PRESSURE_KEYWORDS: List[str] = [
    "but",
    "however",
    "fails",
    "cannot",
    "contradiction",
    "inconsistent",
    "yet",
    "nevertheless",
    "counter",
    "refute",
    "undermines",
    "incompatible",
]

# Phrase fragments that signal assumption-challenging or structural instability.
# These extend _PRESSURE_KEYWORDS with patterns that challenge hidden premises
# or expose framing incompatibilities without using explicit contradiction words.
_PRESSURE_PHRASES: List[str] = [
    "you assume",
    "why assume",
    "what if",
    "how do you know",
    "are you not just",
    "doesn't that",
    "does that not",
    "why overlook",
    "tilted long before",
    "already stacked",
    "cannot hold",
    "pull in opposite directions",
    "hidden premise",
    "that presupposes",
    "you're assuming",
    "you are assuming",
    "is that not just",
    # structural challenge phrases
    "quietly assumes",
    "risks sneaking in",
    "just swaps one anchor for another",
    "what happens if",
]

# Assertion-based challenge phrases that expose hidden assumptions, challenge
# framing, or destabilise claims through declarative critique — no question
# mark required.  These complement _PRESSURE_PHRASES with patterns that are
# specifically associated with reframing, assumption exposure, or implicit
# critique of the other agent's position.
_ASSERTION_PHRASES: List[str] = [
    "misses that",
    "ignores that",
    "assumes that",
    "you seem to",
    "there's no guarantee",
    "there is no guarantee",
    "fails to consider",
    "overlooks",
]

# Compiled regex patterns for structural pressure signals.
# Catches rhetorical question forms that challenge framing or stability.
# All [^.!?] character classes are bounded to 200 characters to prevent
# catastrophic backtracking on pathological inputs.
_PRESSURE_PATTERNS: List[re.Pattern[str]] = [
    # Negation-contracted rhetorical question, e.g. "Doesn't this collapse?"
    # The optional apostrophe (') also handles informal spellings like "doesnt".
    re.compile(
        r"\b(?:doesn'?t|isn'?t|aren'?t|wasn'?t|weren'?t|can'?t|won'?t"
        r"|wouldn'?t|shouldn'?t|couldn'?t)\b[^.!?]{0,200}\?",
        re.IGNORECASE,
    ),
    # Structural challenge: "treats X as if" exposes a hidden assumption.
    re.compile(r"\btreats?\b[^.!?]{0,200}\bas\s+if\b", re.IGNORECASE),
    # Conditional challenge: "if …, does that mean" — probes consequences.
    re.compile(r"\bif\b[^.!?]{0,200}\bdoes that mean\b", re.IGNORECASE),
    # Conditional challenge: "if … what happens" — probes instability.
    re.compile(r"\bif\b[^.!?]{0,200}\bwhat happens\b", re.IGNORECASE),
    # Conditional challenge: "if …, then" — exposes entailed consequence.
    re.compile(r"\bif\b[^.!?]{0,200},\s*then\b", re.IGNORECASE),
]

# Markers that, when combined with the presence of '?' in a response, signal
# a challenging rhetorical question.  Covers assumption challenges, epistemic
# challenges, contradiction framing, and reframing prompts.  Used exclusively
# in the structural Layer-4 check of creates_pressure().
# NOTE: All entries here are substring prefixes — they only produce a pressure
# signal when the response also contains '?', so short prefixes like "assum"
# or "justif" do not fire on declarative statements.
_RHETORICAL_QUESTION_MARKERS: List[str] = [
    # assumption challenges — word-family prefix catches assume/assumes/assumed/
    # assuming/assumption/assumptions without an NLP library.
    "assum",
    "you assume",
    "why assume",
    # justification challenges — justif* catches justify/justified/justification
    "justif",
    # definition challenges — defin* catches define/defines/definition/defining
    "defin",
    # agreement challenges — agre* catches agree/agrees/agreed/agreement
    "agre",
    # epistemic challenges — specific interrogative forms to avoid false positives
    # from mid-sentence uses of "why" (e.g. "that's why it matters?")
    "how do you know",
    "what if",
    "why do",
    "why does",
    "why is",
    "why are",
    "why would",
    "why should",
    # contradiction framing
    "doesn't that",
    "isn't that",
    "aren't you",
    # reframing / collective challenge prompts
    "are you not just",
    "are we just",
    "does this not",
]

# Keywords that signal resolution, narrowing, or collapse
_RESOLUTION_KEYWORDS: List[str] = [
    "i was wrong",
    "we must reject",
    "this fails",
    "cannot both",
    "we conclude",
    "therefore we must",
    "it follows that",
    "we can conclude",
    "this settles",
    "must be abandoned",
    "forces us to accept",
    "the answer is",
    # Mutual exclusion
    "one must yield",
    "one excludes the other",
    "one force always has to yield",
    "cannot operate simultaneously",
    # Tradeoff forcing
    "you cannot have both",
    "for one to happen, the other must",
    # Collapse / narrowing
    "the loop closes",
    "the drive fades",
    "one side has to give",
    "this narrows the issue to",
    "cannot coexist",
    "must give way",
    "one has to give",
    "forced to choose",
]

# Compiled regex patterns for structural resolution signals.
# Catches exclusion and tradeoff constructs not covered by plain keywords.
_RESOLUTION_PATTERNS: List[re.Pattern[str]] = [
    # "either X or Y" exclusion structure
    re.compile(r"\beither\b[^.!?]+\bor\b[^.!?]*[.!?]", re.IGNORECASE),
    # "if X holds / is true, Y cannot" tradeoff structure
    re.compile(
        r"\bif\b[^.!?]+\bcannot\b[^.!?]*\b(?:hold|stand|work|coexist|both)\b",
        re.IGNORECASE,
    ),
    # "one (side|force|…) (must|always|has to) (yield|give|collapse)" collapse structure
    re.compile(
        r"\bone (?:of them|side|force)(?: (?:always|must|has to|always has to))?"
        r" ?(?:yield|give|collapse)\b",
        re.IGNORECASE,
    ),
]

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
    """Evaluate the linguistic quality of *response* (Step 1 score).

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
        Linguistic quality score in [0.0, 1.0].  Higher is better.
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


# ---------------------------------------------------------------------------
# Step 2 — Dialogue-movement helpers
# ---------------------------------------------------------------------------


def _word_overlap(text_a: str, text_b: str) -> float:
    """Jaccard-like word overlap between two texts (content words only)."""
    set_a = {t for t in _tokenize(text_a) if t not in _STOP_WORDS}
    set_b = {t for t in _tokenize(text_b) if t not in _STOP_WORDS}
    if not set_a and not set_b:
        return 1.0
    if not set_a or not set_b:
        return 0.0
    return len(set_a & set_b) / len(set_a | set_b)


def _similarity_to_last(response: str, context: Sequence[str]) -> float:
    """Return word-overlap similarity between *response* and the last context turn."""
    if not context:
        return 0.0
    return _word_overlap(response, context[-1])


def _similarity_to_recent(response: str, context: Sequence[str]) -> float:
    """Return the maximum word-overlap similarity between *response* and
    the most recent *_RECENT_TURNS_WINDOW* context turns."""
    if not context:
        return 0.0
    window = context[-_RECENT_TURNS_WINDOW:]
    return max(_word_overlap(response, turn) for turn in window)


def is_new_claim(response: str, context: Sequence[str]) -> bool:
    """Return True if *response* differs enough from the last turn to count
    as a new claim (similarity below *_NEW_CLAIM_SIMILARITY_THRESHOLD*)."""
    return _similarity_to_last(response, context) < _NEW_CLAIM_SIMILARITY_THRESHOLD


def is_semantic_repeat(response: str, context: Sequence[str]) -> bool:
    """Return True if *response* is too similar to recent turns even if the
    exact wording changed (similarity above *_SEMANTIC_REPEAT_THRESHOLD*)."""
    return _similarity_to_recent(response, context) > _SEMANTIC_REPEAT_THRESHOLD


def creates_pressure(response: str) -> bool:
    """Return True if *response* contains words or structural patterns that
    signal argumentative pressure, tension, contradiction, or sharpened
    disagreement.

    Detection uses five layers:
    1. ``_PRESSURE_KEYWORDS`` — explicit contradiction / tension vocabulary.
    2. ``_PRESSURE_PHRASES`` — phrase fragments that challenge assumptions or
       expose framing instability, including structural phrases such as
       "quietly assumes", "risks sneaking in", "what happens if", and
       "just swaps one anchor for another".
    3. ``_PRESSURE_PATTERNS`` — structural regex patterns including
       negation-contracted rhetorical questions, "treats X as if" constructs,
       and conditional challenge forms ("if …, then", "if … does that mean",
       "if … what happens").
    4. Rhetorical-question rule — if the response contains a ``?`` *and* any
       marker from ``_RHETORICAL_QUESTION_MARKERS`` (assumption/justification/
       definition/agreement word-family prefixes, epistemic interrogative forms,
       contradiction framing, or reframing prompts), the response is treated as
       argumentative pressure.
    5. ``_ASSERTION_PHRASES`` — declarative assertion patterns that expose
       hidden assumptions, challenge framing, or destabilise claims without
       requiring a question mark ("misses that", "ignores that", "assumes that",
       "you seem to", "there's no guarantee", "fails to consider", "overlooks").
    """
    lower = response.lower()
    if any(k in lower for k in _PRESSURE_KEYWORDS):
        return True
    if any(phrase in lower for phrase in _PRESSURE_PHRASES):
        return True
    if any(p.search(response) for p in _PRESSURE_PATTERNS):
        return True
    if "?" in response and any(marker in lower for marker in _RHETORICAL_QUESTION_MARKERS):
        return True
    if any(phrase in lower for phrase in _ASSERTION_PHRASES):
        return True
    return False


def shows_resolution(response: str) -> bool:
    """Return True if *response* signals resolution, narrowing, concession,
    rejection, or collapse of a position.

    Detection uses two layers:
    1. ``_RESOLUTION_KEYWORDS`` — explicit conclusion / exclusion vocabulary
       and phrase fragments.
    2. ``_RESOLUTION_PATTERNS`` — structural regex patterns (e.g. either/or
       exclusion, conditional tradeoff, collapse phrasing).
    """
    lower = response.lower()
    if any(k in lower for k in _RESOLUTION_KEYWORDS):
        return True
    if any(p.search(response) for p in _RESOLUTION_PATTERNS):
        return True
    return False


def evaluate_dialogue_movement(response: str, context: Sequence[str]) -> float:
    """Evaluate how much *response* moved the dialogue forward (Step 2 score).

    This is a **measurement-only** heuristic — it does not influence engine
    behaviour, thresholds, or Fixy logic.

    Parameters
    ----------
    response:
        The generated agent response text.
    context:
        Recent dialogue history (list of plain-text turns), most recent last.

    Returns
    -------
    float
        Dialogue-movement score in [0.0, 1.0].  Higher means more movement.
    """
    if not response or not response.strip():
        return 0.0

    score = 0.40  # base

    if is_new_claim(response, context):
        score += 0.15

    if creates_pressure(response):
        score += 0.15

    if shows_resolution(response):
        score += 0.25

    if is_semantic_repeat(response, context):
        score -= 0.20

    return max(0.0, min(1.0, score))


# ---------------------------------------------------------------------------
# Step 2 — Dialogue-movement signals (debug / measurement)
# ---------------------------------------------------------------------------


class DialogueSignals(TypedDict):
    """Raw component signals used to produce the dialogue-movement score.

    All fields are **measurement-only** — they do not influence engine
    behaviour, thresholds, or Fixy logic.
    """

    score: float
    new_claim: bool
    pressure: bool
    resolution: bool
    semantic_repeat: bool


def evaluate_dialogue_movement_with_signals(
    response: str, context: Sequence[str]
) -> DialogueSignals:
    """Return the dialogue-movement score together with its component signals.

    This is a **measurement-only** helper that exposes the individual boolean
    flags used internally by :func:`evaluate_dialogue_movement` so that the
    score can be validated and debugged in real sessions.

    Parameters
    ----------
    response:
        The generated agent response text.
    context:
        Recent dialogue history (list of plain-text turns), most recent last.

    Returns
    -------
    DialogueSignals
        A dict with keys ``score``, ``new_claim``, ``pressure``,
        ``resolution``, and ``semantic_repeat``.
    """
    if not response or not response.strip():
        return DialogueSignals(
            score=0.0,
            new_claim=False,
            pressure=False,
            resolution=False,
            semantic_repeat=False,
        )

    _new_claim = is_new_claim(response, context)
    _pressure = creates_pressure(response)
    _resolution = shows_resolution(response)
    _semantic_repeat = is_semantic_repeat(response, context)

    raw = 0.40  # base
    if _new_claim:
        raw += 0.15
    if _pressure:
        raw += 0.15
    if _resolution:
        raw += 0.25
    if _semantic_repeat:
        raw -= 0.20

    return DialogueSignals(
        score=max(0.0, min(1.0, raw)),
        new_claim=_new_claim,
        pressure=_pressure,
        resolution=_resolution,
        semantic_repeat=_semantic_repeat,
    )


# ---------------------------------------------------------------------------
# Step 3 — Pressure synchronisation (measurement only)
# ---------------------------------------------------------------------------

# DrivePressure threshold above which meta pressure is considered "high".
# Range is 0.0–10.0; meta pressure is high when strictly greater than 5.0
# (the midpoint), so the flag only activates for genuinely elevated pressure.
_META_PRESSURE_HIGH_THRESHOLD: float = 5.0


def compute_pressure_alignment(
    meta_pressure: float,
    dialogue_pressure: bool,
) -> str:
    """Compare meta (internal) pressure with dialogue (text) pressure.

    This is a **measurement-only** function.  It does not influence engine
    behaviour, score weights, or Fixy logic.

    Parameters
    ----------
    meta_pressure:
        The agent's current DrivePressure scalar (0.0–10.0).
    dialogue_pressure:
        The ``pressure`` flag from :func:`evaluate_dialogue_movement_with_signals`,
        indicating whether the generated text contains argumentative pressure.

    Returns
    -------
    str
        One of:

        * ``"aligned"`` — meta pressure is high **and** dialogue pressure is True.
        * ``"internal_not_expressed"`` — meta pressure is high but the
          text shows no pressure (internal state not expressed).
        * ``"text_more_pressured_than_state"`` — meta pressure is low
          but the text signals pressure (text exceeds internal state).
        * ``"neutral"`` — meta pressure is low and dialogue pressure is False.
    """
    meta_high = meta_pressure > _META_PRESSURE_HIGH_THRESHOLD
    if meta_high and dialogue_pressure:
        return "aligned"
    if meta_high and not dialogue_pressure:
        return "internal_not_expressed"
    if not meta_high and dialogue_pressure:
        return "text_more_pressured_than_state"
    return "neutral"

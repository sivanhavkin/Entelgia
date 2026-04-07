#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Progress Enforcer for Entelgia — argumentative-progress detection layer.

Ensures that each generated response *advances* the argument rather than
merely paraphrasing or balancing existing points.

Core idea
---------
Relevance is required but NOT sufficient.  A response must change the
argumentative state of the dialogue by introducing at least one "progress
move": a new claim, a direct attack/defense, a forced choice, a reframe,
a resolution attempt, or an escalation.

Public API
----------
extract_claims(text)                          -> list[str]
classify_move(text, history)                  -> str   (move-type constant)
score_progress(text, history, claims_memory, *, fixy_guidance=None, ignored_guidance_count=0)  -> float (0.0 – 1.0)
detect_stagnation(recent_turns, scores)       -> bool
get_intervention_policy(stagnation_reason)    -> str
get_regeneration_instruction()                -> str

Per-agent state helpers
-----------------------
get_claims_memory(agent_name)  -> ClaimsMemory
update_claims_memory(agent_name, text, move_type)
add_progress_score(agent_name, score)
get_recent_scores(agent_name)  -> list[float]
get_recent_move_types(agent_name) -> list[str]
clear_agent_state(agent_name=None)

Move-type constants
-------------------
NEW_CLAIM, DIRECT_ATTACK, DIRECT_DEFENSE, FORCED_CHOICE,
REFRAME, RESOLUTION_ATTEMPT, ESCALATION,
PARAPHRASE, BALANCED_RESTATEMENT, FILLER, SOFT_NUANCE
"""

from __future__ import annotations

import logging
import re
from collections import deque
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Move-type constants
# ---------------------------------------------------------------------------

#: High-value progress moves — acceptable responses must contain at least one.
NEW_CLAIM = "NEW_CLAIM"
DIRECT_ATTACK = "DIRECT_ATTACK"
DIRECT_DEFENSE = "DIRECT_DEFENSE"
FORCED_CHOICE = "FORCED_CHOICE"
REFRAME = "REFRAME"
RESOLUTION_ATTEMPT = "RESOLUTION_ATTEMPT"
ESCALATION = "ESCALATION"

#: Low-value / invalid moves that signal semantic recycling.
PARAPHRASE = "PARAPHRASE"
BALANCED_RESTATEMENT = "BALANCED_RESTATEMENT"
FILLER = "FILLER"
SOFT_NUANCE = "SOFT_NUANCE"

#: The ordered set of high-value move types.
HIGH_VALUE_MOVES: List[str] = [
    NEW_CLAIM,
    DIRECT_ATTACK,
    DIRECT_DEFENSE,
    FORCED_CHOICE,
    REFRAME,
    RESOLUTION_ATTEMPT,
    ESCALATION,
]

#: Low-value move types (penalised).
LOW_VALUE_MOVES: List[str] = [
    PARAPHRASE,
    BALANCED_RESTATEMENT,
    FILLER,
    SOFT_NUANCE,
]

# ---------------------------------------------------------------------------
# Configuration constants
# ---------------------------------------------------------------------------

#: Minimum progress score to accept a response without regeneration.
PROGRESS_SCORE_THRESHOLD: float = 0.35

#: Number of recent turns with low progress that triggers stagnation.
STAGNATION_TURN_COUNT: int = 3

#: Low-progress threshold used when counting stagnant turns.
STAGNATION_LOW_SCORE: float = 0.30

#: Number of repeated move types (consecutive) that triggers stagnation.
STAGNATION_REPEATED_MOVES: int = 3

#: Number of recent progress scores to store per agent.
SCORE_HISTORY_SIZE: int = 8

#: Number of recent move types to store per agent.
MOVE_TYPE_HISTORY_SIZE: int = 8

#: Maximum number of claims to extract per response.
MAX_CLAIMS: int = 3

#: Minimum sentence length (chars) to be treated as a potential claim.
MIN_CLAIM_LEN: int = 20

# ---------------------------------------------------------------------------
# Claim status constants
# ---------------------------------------------------------------------------

STATUS_UNRESOLVED = "unresolved"
STATUS_CHALLENGED = "challenged"
STATUS_DEFENDED = "defended"
STATUS_RESOLVED = "resolved"

# ---------------------------------------------------------------------------
# Linguistic pattern compilations
# ---------------------------------------------------------------------------

# Patterns that strongly suggest a DIRECT_ATTACK move
_ATTACK_PATTERNS: List[re.Pattern] = [
    re.compile(
        r"\b(wrong|incorrect|false|mistaken|flawed|error|fails to|ignores?|overlooks?|misses?|contradicts?)\b",
        re.I,
    ),
    re.compile(
        r"\b(but (this|that) (is|ignores?|fails?|misses?|contradicts?))\b", re.I
    ),
    re.compile(
        r"\b(counter(argument|example|claim|point|evidence)|refut(e|es|ing|ation))\b",
        re.I,
    ),
    re.compile(r"\b(not the case|no[,.]?\s+(?:actually|in fact|rather))\b", re.I),
    re.compile(r"\b(disagree|reject[s]?|deny|denies|oppose[s]?)\b", re.I),
]

# Patterns that suggest a DIRECT_DEFENSE move
_DEFENSE_PATTERNS: List[re.Pattern] = [
    re.compile(
        r"\b(precisely because|exactly right|correct(ly)?|exactly (so|this))\b", re.I
    ),
    re.compile(
        r"\b(this (confirms?|supports?|validates?|shows?|demonstrates?))\b", re.I
    ),
    re.compile(r"\b(in (support|defense|favour|favor) of)\b", re.I),
    re.compile(r"\b(holds?\s+(true|up|firm)|stands?\s+(correct|firm))\b", re.I),
    re.compile(r"\b(strengthens?|reinforce[s]?|corroborates?)\b", re.I),
]

# Patterns that suggest a FORCED_CHOICE move
_FORCED_CHOICE_PATTERNS: List[re.Pattern] = [
    re.compile(r"\b(either\s+.{3,60}\s+or\s+.{3,60})\b", re.I),
    re.compile(r"\b(choose\s+between|must\s+(choose|decide|pick|commit))\b", re.I),
    re.compile(
        r"\b(there\s+(are|is)\s+(only\s+)?(two|2)\s+(options?|choices?|paths?|positions?))\b",
        re.I,
    ),
    re.compile(r"\b(a\s+or\s+b\b|option\s+[ab]\b)", re.I),
    re.compile(r"\b(which\s+(is\s+it|do\s+you\s+choose|will\s+you\s+accept))\b", re.I),
]

# Patterns that suggest a REFRAME move
_REFRAME_PATTERNS: List[re.Pattern] = [
    re.compile(r"\b(the\s+real\s+(question|issue|problem|distinction|point))\b", re.I),
    re.compile(r"\b(mis(framed?|framing|understood|characteriz(ed|ing)))\b", re.I),
    re.compile(r"\b(better\s+(framed?|understood|described|conceived)\s+as)\b", re.I),
    re.compile(r"\b(actually\s+(about|a\s+question\s+of|depends?\s+on))\b", re.I),
    re.compile(
        r"\b(the\s+distinction\s+is|what\s+matters?\s+(here|is)|what\s+is\s+at\s+stake)\b",
        re.I,
    ),
    re.compile(
        r"\b(not\s+(about|a\s+matter\s+of)\s+.{3,40},?\s+but\s+(about|rather))\b", re.I
    ),
]

# Patterns that suggest a RESOLUTION_ATTEMPT move
_RESOLUTION_PATTERNS: List[re.Pattern] = [
    re.compile(
        r"\b(resolv(e|es|ing|ed)|resolution|settle[s]?|reconcil(e|es|ing|iation))\b",
        re.I,
    ),
    re.compile(
        r"\b(common\s+ground|both\s+(sides?|positions?)\s+(can|agree|accept))\b", re.I
    ),
    re.compile(r"\b(synthesis|synthesiz(e|es|ing))\b", re.I),
    re.compile(r"\b(the\s+answer\s+is|the\s+solution\s+(is|lies))\b", re.I),
    re.compile(
        r"\b(therefore[,:]?\s+we\s+(can|should|must)|this\s+means\s+that\s+we)\b", re.I
    ),
]

# Patterns that suggest an ESCALATION move
_ESCALATION_PATTERNS: List[re.Pattern] = [
    re.compile(
        r"\b(sharper|stricter|stronger|harder|more\s+(demanding|precise|rigorous|exacting))\b",
        re.I,
    ),
    re.compile(
        r"\b(prove\s+it|demonstrate\s+it|show\s+me|give\s+(an?\s+)?(example|counterexample|instance|evidence))\b",
        re.I,
    ),
    re.compile(
        r"\b(the\s+(real|harder|deeper|further|ultimate)\s+(test|challenge|question|constraint))\b",
        re.I,
    ),
    re.compile(
        r"\b(even\s+if\s+.{3,50},?\s+it\s+(still|does\s+not|cannot|fails?))\b", re.I
    ),
    re.compile(r"\b(what\s+if\s+.{3,60}\?)\b", re.I),
    re.compile(r"\b(push\s+further|go\s+further|take\s+it\s+further)\b", re.I),
]

# Patterns that suggest a PARAPHRASE / recycling move
_PARAPHRASE_PATTERNS: List[re.Pattern] = [
    re.compile(
        r"\b(as\s+(i|you|we)\s+(said|mentioned|noted|argued|stated|pointed\s+out))\b",
        re.I,
    ),
    re.compile(r"\b(in\s+other\s+words|to\s+put\s+it\s+(another|differently))\b", re.I),
    re.compile(r"\b(essentially|fundamentally|at\s+(bottom|its\s+core))\b", re.I),
    re.compile(r"\b(simply\s+(put|stated|said)|to\s+repeat\b)\b", re.I),
    re.compile(r"\b(once\s+again|again[,:]?|restating|restat(e|ed))\b", re.I),
]

# Patterns that suggest a BALANCED_RESTATEMENT move
_BALANCED_PATTERNS: List[re.Pattern] = [
    re.compile(
        r"\b(on\s+(one|the\s+one)\s+hand.{1,80}on\s+the\s+other\s+hand)\b", re.I
    ),
    re.compile(
        r"\b(both\s+.{3,50}\s+and\s+.{3,50}\s+(are\s+valid|matter|have\s+merit))\b",
        re.I,
    ),
    re.compile(r"\b(it\s+depends|that\s+depends|depends\s+on\s+the)\b", re.I),
    re.compile(
        r"\b(each\s+(side|position|view)\s+has\s+(a\s+)?(point|merit|validity))\b", re.I
    ),
    re.compile(r"\b(trade.?off|balance\s+between|weigh\s+(the|both|all))\b", re.I),
]

# Patterns that suggest FILLER
_FILLER_PATTERNS: List[re.Pattern] = [
    re.compile(
        r"\b(great\s+(question|point)|interesting\s+(question|point|perspective))\b",
        re.I,
    ),
    re.compile(
        r"\b(you\s+(raise|make)\s+a\s+(good|valid|fair|interesting|important)\s+point)\b",
        re.I,
    ),
    re.compile(
        r"\b(thank\s+you\s+for|thanks?\s+for\s+(raising|bringing|sharing))\b", re.I
    ),
    re.compile(
        r"\b(i\s+(appreciate|acknowledge|recognize|understand)\s+(your|that|this)\s+(concern|point|perspective))\b",
        re.I,
    ),
    re.compile(
        r"\b(as\s+i\s+reflect|upon\s+reflection|reflecting\s+on\s+this)\b", re.I
    ),
]

# Phrases that strongly signal commitment (raises progress score)
_COMMITMENT_PHRASES: List[re.Pattern] = [
    re.compile(
        r"\b(i\s+(claim|assert|argue|maintain|insist|hold|believe)\s+that)\b", re.I
    ),
    re.compile(r"\b(my\s+(claim|position|thesis|argument|view)\s+is)\b", re.I),
    re.compile(r"\b(specifically[,:]|concretely[,:]|definitively[,:])\b", re.I),
    re.compile(
        r"\b(must\s+(be|accept|reject|choose|commit)|cannot\s+(be|avoid|escape|deny))\b",
        re.I,
    ),
    re.compile(r"\b(the\s+answer\s+is\s+(yes|no|clear|simple))\b", re.I),
]

# Hedging / soft-nuance markers that lower the score
_HEDGE_PHRASES: List[re.Pattern] = [
    re.compile(r"\b(perhaps|maybe|might|could\s+be|possibly|conceivably)\b", re.I),
    re.compile(r"\b(in\s+some\s+(sense|way|respects?|cases?))\b", re.I),
    re.compile(r"\b(to\s+some\s+extent|partially|nuanced|nuance)\b", re.I),
    re.compile(r"\b(it\s+is\s+not\s+entirely|not\s+so\s+simple|complicated)\b", re.I),
    re.compile(r"\b(one\s+might\s+(say|argue|think|suggest))\b", re.I),
]

# ---------------------------------------------------------------------------
# Claim-extraction sentence splitter helpers
# ---------------------------------------------------------------------------

_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+")

# Strong declarative structures that suggest a claim sentence
_CLAIM_INDICATORS: List[re.Pattern] = [
    re.compile(
        r"\b(is|are|must|cannot|will|does|shows?|proves?|implies?|entails?)\b", re.I
    ),
    re.compile(r"\b(i\s+(claim|argue|hold|maintain|assert|believe)\s+that)\b", re.I),
    re.compile(r"\b(therefore|thus|hence|consequently|it\s+follows\s+that)\b", re.I),
    re.compile(
        r"\b(the\s+(key|main|core|central|fundamental)\s+(claim|point|assertion|fact|truth)\s+is)\b",
        re.I,
    ),
]

# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass
class Claim:
    """A single argumentative claim with its status."""

    text: str
    status: str = STATUS_UNRESOLVED  # one of the STATUS_* constants
    move_type: str = NEW_CLAIM  # move that introduced / last touched this claim


@dataclass
class ClaimsMemory:
    """Per-agent store of recent claims and their current argumentative state."""

    claims: List[Claim] = field(default_factory=list)
    max_claims: int = 20  # rolling window of retained claims

    def add(self, text: str, move_type: str = NEW_CLAIM) -> None:
        """Add a new claim (de-duplicated by approximate string matching)."""
        text = text.strip()
        if not text:
            return
        # De-duplicate against existing claims
        for c in self.claims:
            if _jaccard_similarity(text, c.text) > 0.6:
                return  # already present (close enough)
        self.claims.append(Claim(text=text, move_type=move_type))
        # Trim to rolling window
        if len(self.claims) > self.max_claims:
            self.claims = self.claims[-self.max_claims :]

    def update_status(self, text: str, new_status: str, move_type: str) -> bool:
        """Update the status of the claim most similar to *text*.  Returns True if updated."""
        best_idx = -1
        best_sim = 0.0
        for i, c in enumerate(self.claims):
            sim = _jaccard_similarity(text, c.text)
            if sim > best_sim:
                best_sim = sim
                best_idx = i
        if best_idx >= 0 and best_sim > 0.3:
            self.claims[best_idx].status = new_status
            self.claims[best_idx].move_type = move_type
            return True
        return False

    def has_unresolved(self) -> bool:
        return any(c.status == STATUS_UNRESOLVED for c in self.claims)

    def unresolved_claims(self) -> List[Claim]:
        return [c for c in self.claims if c.status == STATUS_UNRESOLVED]

    def state_changed_by(self, new_claims: List[str], move_type: str) -> bool:
        """Return True if any of *new_claims* modifies existing claim state or adds a genuinely new claim."""
        for nc in new_claims:
            # Check if it updates an existing claim
            if self.update_status(nc, _status_from_move(move_type), move_type):
                return True
            # Check if it is genuinely new (no close match in memory)
            if not any(_jaccard_similarity(nc, c.text) > 0.5 for c in self.claims):
                return True
        return False

    def summary(self) -> str:
        lines = []
        for c in self.claims[-5:]:
            lines.append(f"[{c.status}] {c.text[:80]}")
        return "\n".join(lines) if lines else "(empty)"


# ---------------------------------------------------------------------------
# Module-level per-agent state
# ---------------------------------------------------------------------------

_agent_claims_memory: Dict[str, ClaimsMemory] = {}
_agent_progress_scores: Dict[str, deque] = {}
_agent_move_types: Dict[str, deque] = {}


def get_claims_memory(agent_name: str) -> ClaimsMemory:
    """Return (or create) the ClaimsMemory for *agent_name*."""
    if agent_name not in _agent_claims_memory:
        _agent_claims_memory[agent_name] = ClaimsMemory()
    return _agent_claims_memory[agent_name]


def add_progress_score(agent_name: str, score: float) -> None:
    """Record a progress score for the agent."""
    if agent_name not in _agent_progress_scores:
        _agent_progress_scores[agent_name] = deque(maxlen=SCORE_HISTORY_SIZE)
    _agent_progress_scores[agent_name].append(score)


def replace_last_progress_score(agent_name: str, score: float) -> None:
    """Replace the most recently recorded progress score for *agent_name*.

    Used to apply post-generation penalties (e.g. semantic non-compliance or
    loop detection) so that stagnation tracking reflects the adjusted score.
    No-op when no score has been recorded yet.
    """
    history = _agent_progress_scores.get(agent_name)
    if history:
        history[-1] = score


def get_recent_scores(agent_name: str) -> List[float]:
    """Return recent progress scores for *agent_name*."""
    return list(_agent_progress_scores.get(agent_name, []))


def add_move_type(agent_name: str, move_type: str) -> None:
    """Record the move type used by *agent_name*."""
    if agent_name not in _agent_move_types:
        _agent_move_types[agent_name] = deque(maxlen=MOVE_TYPE_HISTORY_SIZE)
    _agent_move_types[agent_name].append(move_type)


def get_recent_move_types(agent_name: str) -> List[str]:
    """Return recent move types for *agent_name*."""
    return list(_agent_move_types.get(agent_name, []))


def clear_agent_state(agent_name: Optional[str] = None) -> None:
    """Clear per-agent state for *agent_name*, or all agents if None."""
    global _agent_claims_memory, _agent_progress_scores, _agent_move_types
    if agent_name is None:
        _agent_claims_memory.clear()
        _agent_progress_scores.clear()
        _agent_move_types.clear()
    else:
        _agent_claims_memory.pop(agent_name, None)
        _agent_progress_scores.pop(agent_name, None)
        _agent_move_types.pop(agent_name, None)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _tokenize(text: str) -> set:
    """Return a lowercase set of word tokens (stop-words excluded)."""
    _STOP = {
        "a",
        "an",
        "the",
        "is",
        "are",
        "was",
        "were",
        "be",
        "been",
        "being",
        "have",
        "has",
        "had",
        "do",
        "does",
        "did",
        "will",
        "would",
        "shall",
        "should",
        "may",
        "might",
        "must",
        "can",
        "could",
        "to",
        "of",
        "in",
        "on",
        "at",
        "by",
        "for",
        "with",
        "about",
        "that",
        "this",
        "these",
        "those",
        "it",
        "its",
        "i",
        "you",
        "we",
        "they",
        "he",
        "she",
        "or",
        "and",
        "but",
        "not",
        "no",
        "so",
        "if",
        "as",
        "than",
        "then",
        "when",
    }
    tokens = re.findall(r"\b[a-zA-Z]{3,}\b", text.lower())
    return {t for t in tokens if t not in _STOP}


def _jaccard_similarity(a: str, b: str) -> float:
    """Jaccard similarity between the token sets of *a* and *b*."""
    ta, tb = _tokenize(a), _tokenize(b)
    if not ta and not tb:
        return 1.0
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)


def _max_similarity_to_history(text: str, history: List[str]) -> float:
    """Return the maximum Jaccard similarity between *text* and any item in *history*."""
    if not history:
        return 0.0
    return max(_jaccard_similarity(text, h) for h in history)


def _count_pattern_matches(text: str, patterns: List[re.Pattern]) -> int:
    """Return the total number of pattern matches across all *patterns*."""
    return sum(1 for p in patterns if p.search(text))


def _status_from_move(move_type: str) -> str:
    if move_type == DIRECT_ATTACK:
        return STATUS_CHALLENGED
    if move_type == DIRECT_DEFENSE:
        return STATUS_DEFENDED
    if move_type == RESOLUTION_ATTEMPT:
        return STATUS_RESOLVED
    return STATUS_UNRESOLVED


def _contradiction_strength(text: str) -> float:
    """Return a normalized contradiction strength in [0.0, 1.0].

    Counts the number of distinct attack-pattern families matched in *text*
    and normalizes by the total number of families.  A score above 0.7
    indicates a strongly adversarial / contradictory move.
    """
    hits = _count_pattern_matches(text, _ATTACK_PATTERNS)
    return min(hits / max(len(_ATTACK_PATTERNS), 1), 1.0)


def _detect_domain_shift(text: str, history: List[str]) -> bool:
    """Return True if *text* introduces a substantially new vocabulary domain.

    A domain shift is detected when more than 40 % of the meaningful tokens
    in *text* are absent from all recent history turns.  An empty history is
    not considered a domain shift (there is nothing to shift *from*).
    """
    if not history:
        return False
    current_tokens = _tokenize(text)
    if not current_tokens:
        return False
    history_tokens: set = set()
    for h in history:
        history_tokens |= _tokenize(h)
    new_tokens = current_tokens - history_tokens
    return len(new_tokens) / len(current_tokens) > 0.40


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def extract_claims(text: str) -> List[str]:
    """Extract 1–3 core declarative claims from *text*.

    Uses sentence splitting and simple heuristics (declarative structure,
    presence of a verb, absence of question marks) to rank candidate sentences.
    Returns up to MAX_CLAIMS claims.
    """
    sentences = _SENTENCE_SPLIT_RE.split(text.strip())
    scored: List[Tuple[float, str]] = []
    for sent in sentences:
        sent = sent.strip()
        if len(sent) < MIN_CLAIM_LEN:
            continue
        if sent.endswith("?"):
            continue  # questions are not claims
        score = 0.0
        # Bonus for declarative markers
        score += _count_pattern_matches(sent, _CLAIM_INDICATORS) * 0.3
        # Bonus for commitment phrases
        score += _count_pattern_matches(sent, _COMMITMENT_PHRASES) * 0.4
        # Penalty for hedging
        score -= _count_pattern_matches(sent, _HEDGE_PHRASES) * 0.2
        # Moderate bonus for sentence length (dense sentences carry more)
        score += min(len(sent) / 200.0, 0.3)
        scored.append((score, sent))
    # Sort descending by score, take the top MAX_CLAIMS
    scored.sort(key=lambda x: x[0], reverse=True)
    return [s for _, s in scored[:MAX_CLAIMS]]


def classify_move(text: str, history: List[str]) -> str:
    """Classify the dominant argumentative move in *text*.

    Uses pattern matching and history similarity to assign one of the
    move-type constants.  Returns the first matching high-value move, or
    the most prominent low-value move if no high-value match is found.
    """
    # --- high-value moves (ordered by specificity) ---
    attack_hits = _count_pattern_matches(text, _ATTACK_PATTERNS)
    defense_hits = _count_pattern_matches(text, _DEFENSE_PATTERNS)
    choice_hits = _count_pattern_matches(text, _FORCED_CHOICE_PATTERNS)
    reframe_hits = _count_pattern_matches(text, _REFRAME_PATTERNS)
    resolution_hits = _count_pattern_matches(text, _RESOLUTION_PATTERNS)
    escalation_hits = _count_pattern_matches(text, _ESCALATION_PATTERNS)

    # Aggregate score for new-claim detection: low similarity to history + commitment
    similarity = _max_similarity_to_history(text, history) if history else 0.0
    commitment_hits = _count_pattern_matches(text, _COMMITMENT_PHRASES)

    # --- low-value moves ---
    filler_hits = _count_pattern_matches(text, _FILLER_PATTERNS)
    balanced_hits = _count_pattern_matches(text, _BALANCED_PATTERNS)
    paraphrase_hits = _count_pattern_matches(text, _PARAPHRASE_PATTERNS)
    hedge_hits = _count_pattern_matches(text, _HEDGE_PHRASES)

    # Decision tree (most distinctive signals first)
    # Low-value signals checked at >= 1 when they are strong enough to dominate.
    if filler_hits >= 1:
        return FILLER
    if balanced_hits >= 2 and attack_hits == 0 and defense_hits == 0:
        return BALANCED_RESTATEMENT
    if paraphrase_hits >= 2 and similarity > 0.55:
        return PARAPHRASE
    if choice_hits >= 1:
        return FORCED_CHOICE
    if attack_hits >= 2:
        return DIRECT_ATTACK
    if defense_hits >= 2:
        return DIRECT_DEFENSE
    if escalation_hits >= 2:
        return ESCALATION
    if reframe_hits >= 2:
        return REFRAME
    if resolution_hits >= 2:
        return RESOLUTION_ATTEMPT
    if attack_hits >= 1:
        return DIRECT_ATTACK
    if defense_hits >= 1:
        return DIRECT_DEFENSE
    if escalation_hits >= 1:
        return ESCALATION
    if reframe_hits >= 1:
        return REFRAME
    if resolution_hits >= 1:
        return RESOLUTION_ATTEMPT
    # Soft-nuance / balanced detection before new-claim fallback so that
    # heavily-hedged or balanced text is not mislabelled as NEW_CLAIM.
    if hedge_hits >= 3 and commitment_hits == 0:
        return SOFT_NUANCE
    if balanced_hits >= 1 and attack_hits == 0 and defense_hits == 0:
        return BALANCED_RESTATEMENT
    if paraphrase_hits >= 1 and similarity > 0.45:
        return PARAPHRASE
    # New claim: low history similarity AND some declarative commitment signal
    # but NOT dominated by hedging or balance signals.
    if (
        similarity < 0.40
        and (commitment_hits >= 1 or len(extract_claims(text)) >= 1)
        and hedge_hits < 3
        and balanced_hits == 0
    ):
        return NEW_CLAIM
    # Remaining hedge-heavy responses → SOFT_NUANCE
    if hedge_hits >= 2 and commitment_hits == 0:
        return SOFT_NUANCE
    # Default: treat as NEW_CLAIM if no repetition signal
    if similarity < 0.50:
        return NEW_CLAIM
    return SOFT_NUANCE


def score_progress(
    text: str,
    history: List[str],
    claims_memory: ClaimsMemory,
    *,
    fixy_guidance: "Optional[Any]" = None,
    ignored_guidance_count: int = 0,
    validation_result: "Optional[Any]" = None,
    loop_result: "Optional[Any]" = None,
) -> float:
    """Heuristic progress score in [0.0, 1.0].

    Higher is better (more argumentative progress).

    Base move-type scoring
    ----------------------
    + 0.40  new claim that isn't in claims_memory
    + 0.30  direct attack or defense
    + 0.25  forced choice, reframe, escalation
    + 0.20  resolution attempt
    + 0.15  any commitment phrase
    − 0.05  soft nuance / mild hedge
    − 0.15  paraphrase, balanced restatement, or filler
    − 0.15  moderate similarity to recent turns (0.40 – 0.60)
    − 0.30  high similarity to recent turns (> 0.60)
    − 0.20  no existing claim state changed and move is low-value
    − 0.10  per hedge phrase (up to −0.30)

    Dynamic progress bonuses (state-changing dynamics)
    ---------------------------------------------------
    + 0.20  argumentative state actually changed (new or updated claim)
    + 0.20  strong contradiction detected (contradiction_strength > 0.7)
    + 0.20  significant domain / vocabulary shift vs. recent history
    + 0.30  resolution attempt (additional bonus on top of base +0.20)

    Soft Fixy guidance adjustments (v5.2.0)
    ----------------------------------------
    ×0.85   ignored_guidance_count >= 2 (soft penalty for repeated ignore)
    ×0.75   ignored_guidance_count >= 3 (stronger penalty); also caps at 0.55
    −0.05×c  actual move differs from preferred_move (mismatch penalty)
    +0.05×c  actual move matches preferred_move (compliance reward)

    Semantic validation adjustments (v5.3.0)
    -----------------------------------------
    Applies :func:`~entelgia.fixy_semantic_control.apply_validation_to_progress`
    and :func:`~entelgia.fixy_semantic_control.apply_loop_to_progress` when
    *validation_result* or *loop_result* are provided.  These adjustments are
    soft and never reduce the score to zero.

    Parameters
    ----------
    text:
        The agent response to score.
    history:
        Recent dialogue history as plain-text strings.
    claims_memory:
        Per-agent claims state tracker.
    fixy_guidance:
        Optional :class:`~entelgia.fixy_interactive.FixyGuidance` issued by
        Fixy before this turn.  When provided, *preferred_move* and
        *confidence* are used to compute a mismatch penalty or compliance
        reward.
    ignored_guidance_count:
        Number of consecutive turns where the agent did not follow Fixy
        guidance.  Used to apply a soft multiplier penalty.
    validation_result:
        Optional :class:`~entelgia.fixy_semantic_control.ValidationResult`
        from the semantic compliance check.  When provided, guidance
        compliance coupling (section 12.1) is applied.
    loop_result:
        Optional :class:`~entelgia.fixy_semantic_control.LoopCheckResult`
        from the semantic loop detector.  When provided, loop coupling
        (section 12.3) is applied.
    """
    move = classify_move(text, history)
    new_claims = extract_claims(text)
    similarity = _max_similarity_to_history(text, history) if history else 0.0
    commitment_hits = _count_pattern_matches(text, _COMMITMENT_PHRASES)
    hedge_hits = _count_pattern_matches(text, _HEDGE_PHRASES)

    score = 0.0

    # Move-type bonus
    if move in (NEW_CLAIM,):
        score += 0.40
    elif move in (DIRECT_ATTACK, DIRECT_DEFENSE):
        score += 0.30
    elif move in (FORCED_CHOICE, REFRAME, ESCALATION):
        score += 0.25
    elif move in (RESOLUTION_ATTEMPT,):
        score += 0.20
    elif move in (PARAPHRASE, BALANCED_RESTATEMENT, FILLER):
        score -= 0.15
    elif move in (SOFT_NUANCE,):
        score -= 0.05

    # Commitment bonus
    score += min(commitment_hits * 0.15, 0.15)

    # Similarity penalty
    if similarity > 0.60:
        score -= 0.30
    elif similarity > 0.40:
        score -= 0.15

    # Claims-memory state bonus / penalty — consolidated into one branch so
    # the net effect of state_changed is clear: +0.20 when the argumentative
    # state genuinely changed, −0.20 when nothing changed and the move was
    # already low-value.
    state_changed = claims_memory.state_changed_by(new_claims, move)
    if state_changed:
        score += 0.20
    elif move not in HIGH_VALUE_MOVES:
        score -= 0.20  # nothing changed argumentatively

    # Hedge penalty
    score -= min(hedge_hits * 0.10, 0.30)

    # ------------------------------------------------------------------
    # Dynamic progress bonuses — enable scores > 0.40 for genuinely
    # state-changing turns (regardless of base move-type label).
    # ------------------------------------------------------------------
    contradiction_strength = _contradiction_strength(text)
    domain_shift = _detect_domain_shift(text, history)
    # Additional bonus for resolution on top of the base +0.20 move-type score
    resolution_bonus = move == RESOLUTION_ATTEMPT

    if contradiction_strength > 0.70:
        score += 0.20
    if domain_shift:
        score += 0.20
    if resolution_bonus:
        score += 0.30

    # ------------------------------------------------------------------
    # Soft Fixy guidance adjustments (v5.2.0)
    # ------------------------------------------------------------------
    # 1. Penalty for repeatedly ignoring Fixy guidance — multiplicative so
    #    it degrades gracefully; never zeroes the score.
    if ignored_guidance_count >= 3:
        score *= 0.75
        score = min(score, 0.55)
    elif ignored_guidance_count >= 2:
        score *= 0.85

    # 2. Mismatch / compliance adjustment based on the preferred move type.
    if fixy_guidance is not None:
        c = fixy_guidance.confidence
        if move == fixy_guidance.preferred_move:
            score += 0.05 * c
            logger.debug(
                "[PROGRESS-GUIDANCE] compliance bonus +%.3f (move=%r confidence=%.2f)",
                0.05 * c,
                move,
                c,
            )
        else:
            mismatch_penalty = 0.05 * c
            score = max(0.0, score - mismatch_penalty)
            logger.debug(
                "[PROGRESS-GUIDANCE] mismatch penalty -%.3f"
                " (actual=%r preferred=%r confidence=%.2f)",
                mismatch_penalty,
                move,
                fixy_guidance.preferred_move,
                c,
            )

    # ------------------------------------------------------------------
    # Semantic validation and loop adjustments (v5.3.0)
    # ------------------------------------------------------------------
    # 3. Guidance compliance coupling from FixySemanticController
    if validation_result is not None:
        try:
            from entelgia.fixy_semantic_control import apply_validation_to_progress

            score = apply_validation_to_progress(
                score, validation_result, ignored_guidance_count
            )
        except Exception:
            pass  # Never crash the dialogue engine

    # 4. Semantic loop coupling from FixySemanticController
    if loop_result is not None:
        try:
            from entelgia.fixy_semantic_control import apply_loop_to_progress

            score = apply_loop_to_progress(score, loop_result)
        except Exception:
            pass  # Never crash the dialogue engine

    # Clamp to [0.0, 1.0]
    return float(max(0.0, min(1.0, score)))


def detect_stagnation(
    recent_scores: List[float],
    recent_move_types: List[str],
) -> Tuple[bool, str]:
    """Detect whether the dialogue is stagnating.

    Returns a (bool, reason_string) tuple.  reason_string is one of:
      "low_scores"        — too many consecutive low-progress turns
      "repeated_moves"    — the same move type repeats too many times
      "no_state_change"   — same move type + low score every turn
      ""                  — no stagnation detected
    """
    if len(recent_scores) < STAGNATION_TURN_COUNT:
        return False, ""

    # Reason 1: persistent low-progress scores
    tail_scores = recent_scores[-STAGNATION_TURN_COUNT:]
    if all(s <= STAGNATION_LOW_SCORE for s in tail_scores):
        return True, "low_scores"

    # Reason 2: repeated move types
    if len(recent_move_types) >= STAGNATION_REPEATED_MOVES:
        tail_moves = recent_move_types[-STAGNATION_REPEATED_MOVES:]
        if len(set(tail_moves)) == 1:
            return True, "repeated_moves"

    # Reason 3: combined — low-value repeated moves
    if len(recent_move_types) >= STAGNATION_TURN_COUNT:
        tail_moves = recent_move_types[-STAGNATION_TURN_COUNT:]
        all_low = all(m in LOW_VALUE_MOVES for m in tail_moves)
        if all_low:
            return True, "no_state_change"

    return False, ""


def get_intervention_policy(
    stagnation_reason: str, in_recovery: bool = False
) -> str:
    """Return an intervention policy constant for the given stagnation reason.

    Possible return values:
      "REQUIRE_COMMITMENT"   — force the agent to choose A or B
      "REQUIRE_ATTACK"       — force the agent to directly challenge a prior claim
      "REQUIRE_EVIDENCE"     — force the agent to provide an example or counterexample

    When *in_recovery* is True (post-dream recovery mode), REQUIRE_ATTACK is
    suppressed in favour of REQUIRE_EVIDENCE so that aggressive adversarial
    forcing is not applied to a recovering agent.
    """
    if stagnation_reason == "low_scores":
        return "REQUIRE_COMMITMENT"
    if stagnation_reason == "repeated_moves":
        if in_recovery:
            return "REQUIRE_EVIDENCE"
        return "REQUIRE_ATTACK"
    if stagnation_reason == "no_state_change":
        return "REQUIRE_EVIDENCE"
    return "REQUIRE_COMMITMENT"


def get_regeneration_instruction() -> str:
    """Return the prompt instruction to inject when a response is low-progress."""
    return (
        "Advance the argument: add a new claim, attack an existing one, or force a choice. "
        "Avoid paraphrase, balance, and vague nuance. "
        "Take a clear position and commit to it."
    )


def build_intervention_instruction(policy: str, claims_memory: ClaimsMemory) -> str:
    """Build a specific prompt instruction for an intervention policy.

    Optionally references unresolved claims from *claims_memory* to make
    the intervention more targeted.
    """
    unresolved = claims_memory.unresolved_claims()
    claim_hint = ""
    if unresolved:
        claim_hint = f' Specifically, address this unresolved claim: "{unresolved[-1].text[:120]}"'

    if policy == "REQUIRE_COMMITMENT":
        return (
            "INTERVENTION — REQUIRE COMMITMENT: "
            "You must choose one position explicitly. "
            "Do not balance or hedge. State which side you take and why." + claim_hint
        )
    if policy == "REQUIRE_ATTACK":
        return (
            "INTERVENTION — REQUIRE ATTACK: "
            "You must directly challenge a claim made earlier. "
            "Name the claim, explain why it is wrong or incomplete, and offer a better alternative."
            + claim_hint
        )
    if policy == "REQUIRE_EVIDENCE":
        return (
            "INTERVENTION — REQUIRE EVIDENCE: "
            "You must support or refute a claim with a concrete example or counterexample. "
            "Generalities are not acceptable — give a specific case." + claim_hint
        )
    return get_regeneration_instruction()


def update_claims_memory(
    agent_name: str,
    text: str,
    move_type: str,
) -> List[str]:
    """Extract claims from *text*, update the agent's ClaimsMemory, and return new claim texts."""
    mem = get_claims_memory(agent_name)
    new_claims = extract_claims(text)
    for claim_text in new_claims:
        if move_type in (DIRECT_ATTACK,):
            mem.update_status(claim_text, STATUS_CHALLENGED, move_type)
        elif move_type in (DIRECT_DEFENSE,):
            mem.update_status(claim_text, STATUS_DEFENDED, move_type)
        elif move_type in (RESOLUTION_ATTEMPT,):
            mem.update_status(claim_text, STATUS_RESOLVED, move_type)
        else:
            mem.add(claim_text, move_type)
    return new_claims

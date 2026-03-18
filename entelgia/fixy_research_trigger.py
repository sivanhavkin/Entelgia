#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Fixy Research Trigger for Entelgia

Determines whether Fixy (the meta-observer agent) should initiate a web
research cycle for a given user message, recent dialogue turns, or a
Fixy meta-reasoning signal.

A search is triggered when the seed text, recent dialogue, or Fixy's
reasoning signal contains indicators that up-to-date external knowledge
is needed.
"""

from __future__ import annotations

import logging
import re
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Cooldown state
# ---------------------------------------------------------------------------

# Number of turns a trigger must be absent before it can fire again
_COOLDOWN_TURNS: int = 5

# Global search cooldown – prevents any search for _GLOBAL_SEARCH_COOLDOWN_TURNS
# turns after the last successful search, regardless of query or trigger keyword.
_GLOBAL_SEARCH_COOLDOWN_TURNS: int = 5
_last_global_search_turn: Optional[int] = None

# Monotonically increasing call counter – incremented on every
# fixy_should_search() invocation.
_trigger_turn_counter: int = 0

# Maps trigger word/phrase → turn number on which it last triggered a search
_recent_triggers: Dict[str, int] = {}

# Maps full query string → turn number on which it last triggered a search.
# Prevents the same query from firing again within the cooldown window even
# when different trigger keywords are present.
_recent_queries: Dict[str, int] = {}

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# High-signal triggers for external web research
# Phrases are checked before single keywords

_TRIGGER_PHRASES: frozenset = frozenset(
    {
        # recency / updates
        "latest research",
        "recent research",
        "current research",
        "recent study",
        "recent studies",
        "recent paper",
        "new research",
        "new paper",
        "latest findings",
        "latest results",
        "current evidence",
        "recent evidence",
        "recent developments",
        # academic sources
        "peer reviewed",
        "peer reviewed paper",
        "research paper",
        "academic paper",
        "journal article",
        "systematic review",
        "meta analysis",
        "scientific report",
        # verification / sourcing
        "primary source",
        "reliable source",
        "academic source",
        "supporting evidence",
        "published research",
        "empirical study",
        # explicit research actions
        "find paper",
        "find study",
        "find research",
        "look up research",
        "search for evidence",
    }
)

_TRIGGER_KEYWORDS: frozenset = frozenset(
    {
        # recency / freshness
        "latest",
        "recent",
        "current",
        "today",
        "update",
        "updated",
        "trend",
        "trends",
        # user intent / action
        "web",
        # academic / research signals
        "research",
        "study",
        "studies",
        "paper",
        "journal",
        "arxiv",
        # sourcing / verification
        "evidence",
        "source",
        "sources",
        "reference",
        "references",
        "citation",
        "citations",
        "verify",
        "verification",
        "fact",
        "report",
        "published",
        # concept-bearing epistemic terms
        "credibility",
        "bias",
        "epistemology",
        "truth",
        "reasoning",
    }
)

# ---------------------------------------------------------------------------
# Scoring constants
# ---------------------------------------------------------------------------

# Multi-word phrases score higher than single keywords
_PHRASE_SCORE: int = 3
_KEYWORD_SCORE: int = 1

# Academic and concept-bearing keywords that carry extra weight (+1) when found
_HIGH_VALUE_KEYWORDS: frozenset = frozenset(
    {
        "research",
        "study",
        "paper",
        "arxiv",
        "journal",
        "credibility",
        "bias",
        "epistemology",
        "truth",
        "reasoning",
    }
)

# Fixy meta-reason values that indicate a research need
_FIXY_RESEARCH_REASONS: frozenset = frozenset(
    {
        "external_verification_needed",
        "research_needed_for_synthesis",
        "factual_uncertainty_detected",
        "high_conflict_no_resolution",
    }
)

# Number of recent dialogue turns to inspect
_DIALOG_TAIL_WINDOW: int = 4

# ---------------------------------------------------------------------------
# Weak trigger word blacklist
# ---------------------------------------------------------------------------

# Functional/non-conceptual words that should not alone trigger a web search.
# These words are too common and non-specific to justify external research.
# "truth" and "reasoning" are fundamental philosophical vocabulary used in
# almost every dialogue turn; they must not fire a search in isolation.
_WEAK_TRIGGER_WORDS: frozenset = frozenset(
    {
        "current",
        "recent",
        "today",
        "web",
        "internet",
        "update",
        "latest",
        "truth",
        "reasoning",
        "bias",  # too generic alone — "cognitive bias study" is fine, "I notice bias" is not
    }
)

# Effective keyword set after removing weak/non-conceptual entries.
# Computed once at module load to avoid repeated set-difference at call time.
_STRONG_TRIGGER_KEYWORDS: frozenset = _TRIGGER_KEYWORDS - _WEAK_TRIGGER_WORDS

# ---------------------------------------------------------------------------
# Multi-signal detection helpers
# ---------------------------------------------------------------------------

# Words that signal explicit factual uncertainty or a request for evidence
_UNCERTAINTY_SIGNAL_WORDS: frozenset = frozenset(
    {
        "uncertain", "uncertainty", "unclear", "unsure", "unknown",
        "not sure", "don't know", "do we know", "question",
        "verify", "verification", "check", "confirm",
        "evidence", "proof", "support", "demonstrate", "show",
        "source", "sources", "reference", "references",
        "data", "findings", "results", "outcome",
    }
)

# Minimum number of distinct strong trigger hits for multi-signal mode
_MIN_MULTI_SIGNAL_CONCEPTS: int = 2


def _count_strong_trigger_hits(text: str) -> int:
    """Count distinct strong trigger keyword/phrase hits in *text*."""
    text_lower = text.lower()
    hits = 0
    seen: set = set()
    for phrase in _TRIGGER_PHRASES:
        if phrase in text_lower and phrase not in seen:
            hits += 1
            seen.add(phrase)
    for m in re.finditer(r"\b[a-zA-Z\-]+\b", text_lower):
        word = m.group()
        if word in _STRONG_TRIGGER_KEYWORDS and word not in seen:
            hits += 1
            seen.add(word)
    return hits


def _has_uncertainty_or_evidence_signal(text: str) -> bool:
    """Return True if *text* contains an uncertainty or evidence signal."""
    text_lower = text.lower()
    return any(w in text_lower for w in _UNCERTAINTY_SIGNAL_WORDS)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def find_trigger(text: str) -> Optional[str]:
    """
    Return the strongest trigger phrase or keyword found in text.

    Selection rules:
    1. Prefer multi-word phrases over single keywords (higher score).
    2. When scores are equal, prefer the trigger that appears earliest in text.
    3. Case-insensitive matching.
    """

    if not text:
        return None

    text_lower = text.lower()
    # Each candidate: (score, position, trigger)
    candidates = []

    # --- phrase detection ---
    for phrase in _TRIGGER_PHRASES:
        idx = text_lower.find(phrase)
        if idx != -1:
            candidates.append((_PHRASE_SCORE, idx, phrase))

    # --- keyword detection (whole-word, case-insensitive) ---
    for m in re.finditer(r"\b[a-zA-Z\-]+\b", text_lower):
        word = m.group()
        if word in _STRONG_TRIGGER_KEYWORDS:
            score = _KEYWORD_SCORE + (1 if word in _HIGH_VALUE_KEYWORDS else 0)
            candidates.append((score, m.start(), word))

    if not candidates:
        return None

    # Sort: higher score first; for equal scores, earlier position first.
    candidates.sort(key=lambda c: (-c[0], c[1]))
    return candidates[0][2]


def _text_has_trigger(text: str) -> bool:
    """Return True if *text* contains a trigger keyword (whole-word) or phrase."""
    return find_trigger(text) is not None


def clear_trigger_cooldown() -> None:
    """Reset the trigger cooldown state.

    Intended for use in tests to avoid cross-test cooldown interference.
    """
    global _trigger_turn_counter, _last_global_search_turn
    _trigger_turn_counter = 0
    _last_global_search_turn = None
    _recent_triggers.clear()
    _recent_queries.clear()


def _is_trigger_cooled_down(trigger: str, current_turn: int) -> bool:
    """Return ``True`` if *trigger* has not yet cooled down and must not fire again.

    The trigger is considered hot (still cooling) when the gap between
    *current_turn* and the turn on which it last fired is within the
    ``_COOLDOWN_TURNS`` window.
    """
    last_turn = _recent_triggers.get(trigger)
    if last_turn is None:
        return False
    return (current_turn - last_turn) <= _COOLDOWN_TURNS


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def fixy_should_search(
    seed_text: str,
    dialog_tail: Optional[List[Dict[str, str]]] = None,
    fixy_reason: Optional[str] = None,
    query_cooldown_key: Optional[str] = None,
    *,
    require_multi_signal: bool = True,
    min_concepts: int = 2,
    require_uncertainty_or_evidence: bool = True,
) -> bool:
    """Decide whether Fixy should trigger a web research cycle.

    Returns ``True`` when any of the following conditions hold:

    1. A trigger phrase (multi-word) is present in *seed_text* and not cooled down.
    2. Multiple trigger signals are present across seed text and recent dialogue,
       and the multi-signal gate (``require_multi_signal``) is satisfied.
    3. *fixy_reason* matches one of the known research-signal values.

    Multi-signal mode (``require_multi_signal=True``, default):
        A single generic keyword is no longer sufficient.  At least
        ``min_concepts`` distinct strong triggers must be found across the
        combined text window, OR at least one trigger must co-occur with
        an explicit uncertainty/evidence signal word.

    A per-trigger cooldown (``_COOLDOWN_TURNS``) prevents repeated searches
    for the same keyword in rapid succession.

    Parameters
    ----------
    seed_text:
        The initial seed / user input string.
    dialog_tail:
        Optional list of recent dialogue turns, each a dict with at least
        a ``"text"`` key.  Only the last ``_DIALOG_TAIL_WINDOW`` turns are
        inspected.
    fixy_reason:
        Optional meta-reasoning signal emitted by Fixy.
    query_cooldown_key:
        Optional pre-built sanitized search query string.  When provided,
        this key is used for ``_recent_queries`` tracking instead of
        ``seed_text``.
    require_multi_signal:
        When True (default), a single generic keyword cannot fire the trigger
        alone — at least ``min_concepts`` distinct signals are required, or an
        uncertainty/evidence signal must co-occur.
    min_concepts:
        Minimum number of distinct strong trigger hits required in multi-signal
        mode.
    require_uncertainty_or_evidence:
        When True, also accepts a single strong trigger if an
        uncertainty/evidence word co-occurs in the same window.

    Returns
    -------
    ``True`` if a web search should be performed, ``False`` otherwise.
    """
    global _trigger_turn_counter, _last_global_search_turn
    _trigger_turn_counter += 1
    current_turn = _trigger_turn_counter

    # Global cooldown: block any search for _GLOBAL_SEARCH_COOLDOWN_TURNS turns
    # after the last successful search, regardless of query or trigger keyword.
    if _last_global_search_turn is not None:
        if current_turn - _last_global_search_turn < _GLOBAL_SEARCH_COOLDOWN_TURNS:
            logger.info(
                "global cooldown active: skipping web search "
                "(last search turn %d, current %d)",
                _last_global_search_turn,
                current_turn,
            )
            return False

    # Determine the key used for per-query cooldown tracking.
    _cooldown_key = query_cooldown_key if query_cooldown_key is not None else seed_text

    # 0. Per-query cooldown
    if _cooldown_key in _recent_queries:
        if (current_turn - _recent_queries[_cooldown_key]) <= _COOLDOWN_TURNS:
            logger.info(
                "per-query cooldown active: query %r skipped "
                "(last fired on turn %d, current %d)",
                _cooldown_key[:160],
                _recent_queries[_cooldown_key],
                current_turn,
            )
            return False

    # --- Build combined text window for multi-signal analysis ---
    combined_texts = [seed_text]
    if dialog_tail:
        turns_to_scan = dialog_tail[1:]
        recent_turns = turns_to_scan[-_DIALOG_TAIL_WINDOW:]
        for turn in recent_turns:
            turn_text = turn.get("text", "") if isinstance(turn, dict) else ""
            if turn_text:
                combined_texts.append(turn_text)
    combined_window = " ".join(combined_texts)

    logger.debug(
        "[WEB-TRIGGER-CHECK] combined_window_preview=%r require_multi_signal=%s min_concepts=%d",
        combined_window[:200],
        require_multi_signal,
        min_concepts,
    )

    # 1. High-priority: explicit trigger phrase in seed text (multi-word → bypass single-signal gate)
    logger.debug(
        "[branch=seed] source_type=seed_text text_preview=%r",
        seed_text[:160],
    )
    seed_trigger = find_trigger(seed_text)
    logger.debug("[branch=seed] detected_trigger=%r", seed_trigger)
    if seed_trigger and seed_trigger in _TRIGGER_PHRASES:
        # Multi-word phrase: high confidence, skip multi-signal gate
        if not _is_trigger_cooled_down(seed_trigger, current_turn):
            _recent_triggers[seed_trigger] = current_turn
            _recent_queries[_cooldown_key] = current_turn
            _last_global_search_turn = current_turn
            logger.info(
                "[WEB-TRIGGER-FIRE] trigger=%r type=phrase concepts=1", seed_trigger
            )
            return True

    # Emit per-turn dialogue debug logs (for observability regardless of mode)
    if dialog_tail:
        turns_to_scan = dialog_tail[1:]
        recent_turns = turns_to_scan[-_DIALOG_TAIL_WINDOW:]
        for turn in recent_turns:
            turn_text = turn.get("text", "") if isinstance(turn, dict) else ""
            turn_role = turn.get("role", "") if isinstance(turn, dict) else ""
            logger.debug(
                "[branch=dialogue] source_type=dialogue_text turn_role=%r text_preview=%r",
                turn_role,
                turn_text[:160],
            )
            turn_trigger = find_trigger(turn_text)
            logger.debug("[branch=dialogue] detected_trigger=%r", turn_trigger)

    # 2. Multi-signal gate across combined window
    if require_multi_signal:
        concept_count = _count_strong_trigger_hits(combined_window)
        has_uncertainty = _has_uncertainty_or_evidence_signal(combined_window)

        logger.debug(
            "[WEB-TRIGGER-CHECK] concept_count=%d has_uncertainty=%s min_concepts=%d",
            concept_count,
            has_uncertainty,
            min_concepts,
        )

        # Fire if enough distinct concepts, or one strong concept + uncertainty
        multi_ok = concept_count >= min_concepts
        uncertainty_ok = require_uncertainty_or_evidence and has_uncertainty and concept_count >= 1

        if not (multi_ok or uncertainty_ok):
            trigger = find_trigger(combined_window)
            logger.info(
                "[WEB-TRIGGER-SKIP] reason=%s trigger=%r concept_count=%d "
                "has_uncertainty=%s",
                "single_keyword" if concept_count == 1 else "insufficient_concepts",
                trigger,
                concept_count,
                has_uncertainty,
            )
            # Still check Fixy reason below before returning False
        else:
            # Gate passed — find the best trigger from combined window
            trigger = find_trigger(combined_window)
            if trigger and not _is_trigger_cooled_down(trigger, current_turn):
                _recent_triggers[trigger] = current_turn
                _recent_queries[_cooldown_key] = current_turn
                _last_global_search_turn = current_turn
                logger.info(
                    "[WEB-TRIGGER-FIRE] trigger=%r concepts=%d uncertainty=%s",
                    trigger,
                    concept_count,
                    has_uncertainty,
                )
                return True
    else:
        # Legacy single-signal mode
        # 1a. Check seed text trigger (single-signal)
        if seed_trigger and not _is_trigger_cooled_down(seed_trigger, current_turn):
            _recent_triggers[seed_trigger] = current_turn
            _recent_queries[_cooldown_key] = current_turn
            _last_global_search_turn = current_turn
            logger.info("[WEB-TRIGGER-FIRE] trigger=%r type=single", seed_trigger)
            return True

        # 1b. Check recent dialogue turns (single-signal)
        if dialog_tail:
            turns_to_scan = dialog_tail[1:]
            recent_turns = turns_to_scan[-_DIALOG_TAIL_WINDOW:]
            for turn in recent_turns:
                turn_text = turn.get("text", "") if isinstance(turn, dict) else ""
                turn_trigger = find_trigger(turn_text)
                if turn_trigger and not _is_trigger_cooled_down(turn_trigger, current_turn):
                    _recent_triggers[turn_trigger] = current_turn
                    _recent_queries[_cooldown_key] = current_turn
                    _last_global_search_turn = current_turn
                    logger.info("[WEB-TRIGGER-FIRE] trigger=%r type=dialogue", turn_trigger)
                    return True

    # 3. Check Fixy meta-reason signal (always checked regardless of multi-signal setting)
    logger.debug(
        "[branch=fixy_reason] source_type=fixy_reason text_preview=%r",
        (fixy_reason or "")[:160],
    )
    if fixy_reason and fixy_reason in _FIXY_RESEARCH_REASONS:
        _recent_queries[_cooldown_key] = current_turn
        _last_global_search_turn = current_turn
        logger.info("web search triggered by fixy_reason: %r", fixy_reason)
        return True

    return False

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
_COOLDOWN_TURNS: int = 8

# Monotonically increasing call counter – incremented on every
# fixy_should_search() invocation.
_trigger_turn_counter: int = 0

# Maps trigger word/phrase → turn number on which it last triggered a search
_recent_triggers: Dict[str, int] = {}

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_TRIGGER_KEYWORDS: frozenset = frozenset(
    {
        "latest",
        "recent",
        "current",
        "today",
        "news",
        "research",
        "paper",
        "study",
        "article",
        "source",
        "sources",
        "evidence",
        "published",
        "updated",
        "report",
        "find",
        "search",
        "web",
        "verify",
        "verification",
        "fact",
        "citation",
        "citations",
        "external",
        "reference",
        "references",
        "peer",
        "reviewed",
        "journal",
        "arxiv",
        "trend",
        "new",
    }
)

# Phrases that signal a need for external research (simple substring matching)
_TRIGGER_PHRASES: tuple[str, ...] = (
    "latest research",
    "recent paper",
    "find sources",
    "external evidence",
    "current research",
    "peer reviewed",
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
# Internal helpers
# ---------------------------------------------------------------------------


def find_trigger(text: str) -> Optional[str]:
    """Return the first trigger phrase or keyword found in *text*, or ``None``.

    Multi-word phrases are checked before single keywords so that the more
    specific match is always preferred.

    Parameters
    ----------
    text:
        Arbitrary text to scan for trigger signals.

    Returns
    -------
    The matched phrase or keyword string, or ``None`` when no trigger is found.
    """
    if not text or not text.strip():
        return None
    text_lower = text.lower()
    # Phrase check first (multi-word match takes priority over single words)
    for phrase in _TRIGGER_PHRASES:
        if phrase in text_lower:
            return phrase
    # Whole-word keyword check
    words = re.findall(r"[a-z]+", text_lower)
    return next((word for word in words if word in _TRIGGER_KEYWORDS), None)


def _text_has_trigger(text: str) -> bool:
    """Return True if *text* contains a trigger keyword (whole-word) or phrase."""
    return find_trigger(text) is not None


def clear_trigger_cooldown() -> None:
    """Reset the trigger cooldown state.

    Intended for use in tests to avoid cross-test cooldown interference.
    """
    global _trigger_turn_counter
    _trigger_turn_counter = 0
    _recent_triggers.clear()


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
) -> bool:
    """Decide whether Fixy should trigger a web research cycle.

    Returns ``True`` when any of the following conditions hold:

    1. A trigger keyword or phrase is present in *seed_text* and has not
       fired within the last ``_COOLDOWN_TURNS`` turns.
    2. A trigger keyword or phrase appears in the last
       ``_DIALOG_TAIL_WINDOW`` turns of *dialog_tail* and has not fired
       within the cooldown window.
    3. *fixy_reason* matches one of the known research-signal values.

    A per-trigger cooldown (``_COOLDOWN_TURNS = 8``) prevents repeated
    searches for the same keyword in rapid succession.

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

    Returns
    -------
    ``True`` if a web search should be performed, ``False`` otherwise.
    """
    global _trigger_turn_counter
    _trigger_turn_counter += 1
    current_turn = _trigger_turn_counter

    # 1. Check seed text
    trigger = find_trigger(seed_text)
    if trigger:
        if _is_trigger_cooled_down(trigger, current_turn):
            logger.debug(
                "trigger %r is in cooldown (last fired on turn %d, current %d), skipping",
                trigger,
                _recent_triggers[trigger],
                current_turn,
            )
        else:
            _recent_triggers[trigger] = current_turn
            logger.info("web search triggered by keyword: %r", trigger)
            return True

    # 2. Check recent dialogue turns (skip index 0 – the seed topic)
    # Scanning starts from index 1 to prevent the seed topic from
    # activating web search on every turn.
    if dialog_tail:
        turns_to_scan = dialog_tail[1:]
        recent_turns = turns_to_scan[-_DIALOG_TAIL_WINDOW:]
        for turn in recent_turns:
            turn_text = turn.get("text", "") if isinstance(turn, dict) else ""
            trigger = find_trigger(turn_text)
            if trigger:
                if _is_trigger_cooled_down(trigger, current_turn):
                    logger.debug(
                        "trigger %r is in cooldown (last fired on turn %d, current %d), skipping",
                        trigger,
                        _recent_triggers[trigger],
                        current_turn,
                    )
                    continue
                _recent_triggers[trigger] = current_turn
                logger.info("web search triggered by keyword: %r", trigger)
                return True

    # 3. Check Fixy meta-reason signal
    if fixy_reason and fixy_reason in _FIXY_RESEARCH_REASONS:
        logger.info("web search triggered by fixy_reason: %r", fixy_reason)
        return True

    return False

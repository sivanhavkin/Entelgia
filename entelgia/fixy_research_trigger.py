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

    1. A trigger keyword or phrase is present in *seed_text*.
    2. A trigger keyword or phrase appears in the last
       ``_DIALOG_TAIL_WINDOW`` turns of *dialog_tail*.
    3. *fixy_reason* matches one of the known research-signal values.

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
    # 1. Check seed text
    trigger = find_trigger(seed_text)
    if trigger:
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
                logger.info("web search triggered by keyword: %r", trigger)
                return True

    # 3. Check Fixy meta-reason signal
    if fixy_reason and fixy_reason in _FIXY_RESEARCH_REASONS:
        logger.info("web search triggered by fixy_reason: %r", fixy_reason)
        return True

    return False

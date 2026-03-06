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


def _text_has_trigger(text: str) -> bool:
    """Return True if *text* contains a trigger keyword (whole-word) or phrase."""
    if not text or not text.strip():
        return False
    text_lower = text.lower()
    # Phrase check (substring)
    for phrase in _TRIGGER_PHRASES:
        if phrase in text_lower:
            return True
    # Whole-word keyword check
    words = frozenset(re.findall(r"[a-z]+", text_lower))
    return bool(words & _TRIGGER_KEYWORDS)


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
    if _text_has_trigger(seed_text):
        logger.debug("fixy_should_search: trigger found in seed_text")
        return True

    # 2. Check recent dialogue turns
    if dialog_tail:
        recent_turns = dialog_tail[-_DIALOG_TAIL_WINDOW:]
        for turn in recent_turns:
            turn_text = turn.get("text", "") if isinstance(turn, dict) else ""
            if _text_has_trigger(turn_text):
                logger.debug("fixy_should_search: trigger found in dialogue turn")
                return True

    # 3. Check Fixy meta-reason signal
    if fixy_reason and fixy_reason in _FIXY_RESEARCH_REASONS:
        logger.debug("fixy_should_search: trigger from fixy_reason=%r", fixy_reason)
        return True

    return False

#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Fixy Research Trigger for Entelgia

Determines whether Fixy (the meta-observer agent) should initiate a web
research cycle for a given user message.

A search is triggered when the message contains one or more keywords that
signal a need for up-to-date external knowledge.
"""

from __future__ import annotations

import re

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_TRIGGER_KEYWORDS: frozenset = frozenset(
    {
        "latest",
        "recent",
        "research",
        "news",
        "current",
        "today",
        "web",
        "find",
        "search",
        "paper",
        "study",
        "article",
        "published",
        "updated",
        "new",
        "trend",
        "report",
        "source",
    }
)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def fixy_should_search(user_message: str) -> bool:
    """Decide whether Fixy should trigger a web research cycle.

    Returns ``True`` when the user message contains at least one keyword
    that indicates a need for external, up-to-date information.

    Parameters
    ----------
    user_message:
        The raw user input string.

    Returns
    -------
    ``True`` if a web search should be performed, ``False`` otherwise.
    """
    if not user_message or not user_message.strip():
        return False

    message_lower = user_message.lower()
    # Extract whole words for accurate matching
    words = frozenset(re.findall(r"[a-z]+", message_lower))
    return bool(words & _TRIGGER_KEYWORDS)

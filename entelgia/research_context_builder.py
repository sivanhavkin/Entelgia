#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Research Context Builder for Entelgia

Converts a structured research bundle (produced by web_tool.search_and_fetch)
into a formatted text block suitable for injection into agent prompts.

At most MAX_SOURCES sources are included in the output, ordered by the
credibility score already attached to each source.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

MAX_SOURCES: int = 3
# Character limit per source summary (≈ 200 tokens for typical English text).
# This is an approximate guideline; actual token count varies by content type.
_SUMMARY_TEXT_LIMIT: int = 800  # characters per source in the prompt section
_MAX_SENTENCES: int = 3
# Minimum ratio of the char limit at which a word boundary is accepted when
# truncating: only break at a word boundary if it falls in the last 20 % of
# the allowed length (avoids very short summaries when the first space is near
# the beginning).
_WORD_BOUNDARY_THRESHOLD: float = 0.8


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _summarize_text(text: str) -> str:
    """Return a concise summary limited to ``_MAX_SENTENCES`` sentences or
    ``_SUMMARY_TEXT_LIMIT`` characters (≈ 200 tokens), whichever is shorter.

    The result is appended with ``"..."`` when the original text was truncated.
    """
    if not text or not text.strip():
        return ""

    # Split into sentences on any sentence-ending punctuation followed by whitespace
    sentences = re.split(r"(?<=[.!?])\s+", text.strip())

    # Keep at most _MAX_SENTENCES sentences
    selected = " ".join(sentences[:_MAX_SENTENCES])

    # Also enforce the character limit
    if len(selected) > _SUMMARY_TEXT_LIMIT:
        selected = selected[:_SUMMARY_TEXT_LIMIT].rstrip()
        # Break at the last word boundary to avoid a mid-word cut
        last_space = selected.rfind(" ")
        if last_space > _SUMMARY_TEXT_LIMIT * _WORD_BOUNDARY_THRESHOLD:
            selected = selected[:last_space]
        return selected + "..."

    # Append ellipsis if the original text was longer than what we kept
    if len(text.strip()) > len(selected):
        selected += "..."

    return selected


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def build_research_context(
    bundle: Dict[str, Any],
    scored_sources: List[Dict[str, Any]],
    max_sources: int = MAX_SOURCES,
    active_topic: str = "",
) -> str:
    """Format a research bundle as an LLM-ready context block.

    Parameters
    ----------
    bundle:
        The output of ``web_tool.search_and_fetch``, containing a ``query``
        string and a ``sources`` list.
    scored_sources:
        Output of ``source_evaluator.evaluate_sources`` – list of dicts with
        ``url`` and ``credibility_score``, sorted descending by score.
    max_sources:
        Maximum number of sources to include (default 3).
    active_topic:
        Optional current dialogue topic string.  When provided, the context
        block is prefixed with a framing sentence that reminds the LLM to use
        the external information only when it directly supports the topic.

    Returns
    -------
    A formatted multi-line string ready to embed in an LLM prompt, or an
    empty string when there are no sources.
    """
    sources: List[Dict[str, Any]] = bundle.get("sources", [])
    if not sources:
        return ""

    # Build a lookup from URL to credibility score
    score_map: Dict[str, float] = {
        s["url"]: s["credibility_score"] for s in scored_sources
    }

    # Sort sources by descending credibility score
    ranked = sorted(
        sources, key=lambda s: score_map.get(s.get("url", ""), 0.0), reverse=True
    )

    lines: List[str] = ["External Research:\n"]

    for idx, src in enumerate(ranked[:max_sources], start=1):
        url = src.get("url", "")
        title = src.get("title", "") or src.get("snippet", "")[:80]
        credibility = score_map.get(url, 0.0)
        text = src.get("text", "") or src.get("snippet", "")
        summary = _summarize_text(text)

        lines.append(f"Source {idx}:")
        lines.append(f"  Title: {title}")
        lines.append(f"  URL: {url}")
        lines.append(f"  Credibility: {credibility:.2f}")
        lines.append(f"  Summary Text: {summary}")
        lines.append("")

    context = "\n".join(lines).rstrip()
    if active_topic and context:
        context = (
            f"External information related to topic '{active_topic}'. "
            "Use only if it helps address the topic directly.\n\n" + context
        )
    return context

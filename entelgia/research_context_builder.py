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

from typing import Any, Dict, List

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

MAX_SOURCES: int = 3
_SUMMARY_TEXT_LIMIT: int = 500  # characters per source in the prompt section


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def build_research_context(
    bundle: Dict[str, Any],
    scored_sources: List[Dict[str, Any]],
    max_sources: int = MAX_SOURCES,
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
    ranked = sorted(sources, key=lambda s: score_map.get(s.get("url", ""), 0.0), reverse=True)

    lines: List[str] = ["External Research:\n"]

    for idx, src in enumerate(ranked[:max_sources], start=1):
        url = src.get("url", "")
        title = src.get("title", "") or src.get("snippet", "")[:80]
        credibility = score_map.get(url, 0.0)
        text = src.get("text", "") or src.get("snippet", "")
        summary = text[:_SUMMARY_TEXT_LIMIT].strip()
        if len(text) > _SUMMARY_TEXT_LIMIT:
            summary += "..."

        lines.append(f"Source {idx}:")
        lines.append(f"  Title: {title}")
        lines.append(f"  URL: {url}")
        lines.append(f"  Credibility: {credibility:.2f}")
        lines.append(f"  Summary Text: {summary}")
        lines.append("")

    return "\n".join(lines).rstrip()

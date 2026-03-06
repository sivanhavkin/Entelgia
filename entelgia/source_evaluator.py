#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Source Evaluator for Entelgia Web Research

Implements simple heuristic credibility scoring for web sources.

Scoring rules (all additive):
  +0.3   domain is .edu or .gov
  +0.2   domain belongs to a known research/reference site
  +0.2   extracted text is long and coherent (>= 500 chars)
  +0.1   extracted text is moderately long (>= 200 chars)
  -0.2   content is very short (< 50 chars) – likely ads/boilerplate

Scores are clamped to [0.0, 1.0].
"""

from __future__ import annotations

import re
from typing import Dict, List, Any
from urllib.parse import urlparse

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_TRUSTED_DOMAINS = frozenset(
    {
        "wikipedia.org",
        "scholar.google.com",
        "pubmed.ncbi.nlm.nih.gov",
        "arxiv.org",
        "nature.com",
        "science.org",
        "scientificamerican.com",
        "bbc.com",
        "reuters.com",
        "apnews.com",
        "who.int",
        "cdc.gov",
        "nih.gov",
    }
)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def evaluate_source(source: Dict[str, Any]) -> Dict[str, Any]:
    """Score a single source for credibility.

    Parameters
    ----------
    source:
        Dict containing at least ``url`` and ``text`` (page body).

    Returns
    -------
    Dict with keys ``url`` and ``credibility_score`` (float in [0.0, 1.0]).
    """
    url: str = source.get("url", "")
    text: str = source.get("text", "")
    score: float = 0.0

    # Parse domain
    try:
        parsed = urlparse(url if url.startswith("http") else "https://" + url)
        domain = parsed.netloc.lower()
    except Exception:
        domain = ""

    # Strip "www." prefix for matching
    if domain.startswith("www."):
        domain = domain[4:]

    # Domain-based scoring
    if domain.endswith(".edu") or domain.endswith(".gov"):
        score += 0.3
    if any(domain == td or domain.endswith("." + td) for td in _TRUSTED_DOMAINS):
        score += 0.2

    # Text length scoring
    text_len = len(text.strip())
    if text_len >= 500:
        score += 0.2
    elif text_len >= 200:
        score += 0.1

    # Penalise very short / boilerplate content
    if text_len < 50:
        score -= 0.2

    # Clamp to valid range
    score = max(0.0, min(1.0, score))

    return {"url": url, "credibility_score": round(score, 4)}


def evaluate_sources(sources: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Score and rank a list of sources by credibility.

    Parameters
    ----------
    sources:
        List of source dicts (each with ``url`` and ``text``).

    Returns
    -------
    List of dicts ``{"url": ..., "credibility_score": ...}`` sorted
    descending by ``credibility_score``.
    """
    scored = [evaluate_source(s) for s in sources]
    scored.sort(key=lambda x: x["credibility_score"], reverse=True)
    return scored

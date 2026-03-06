#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Web Research Integration for Entelgia

Provides the high-level ``maybe_add_web_context`` function that ties together
the web search, credibility evaluation, and context-building pipeline.

When Fixy detects that a search is needed the pipeline runs as follows:

1. ``fixy_research_trigger.fixy_should_search`` decides whether to search,
   evaluating the seed text, recent dialogue turns, and Fixy's reasoning signal.
2. ``build_research_query`` selects the best query from available context.
3. ``web_tool.search_and_fetch`` retrieves pages.
4. ``source_evaluator.evaluate_sources`` scores each source.
5. Sources are sorted by credibility score (descending).
6. ``research_context_builder.build_research_context`` formats the block.
7. Optionally, high-credibility sources (score > HIGH_CREDIBILITY_THRESHOLD)
   are stored in the Entelgia long-term memory database.

The function always fails gracefully; any exception returns an empty string
so that the main dialogue pipeline is never disrupted.
"""

from __future__ import annotations

import datetime
import logging
import sqlite3
import uuid
from typing import Any, Dict, List, Optional

from entelgia.fixy_research_trigger import fixy_should_search
from entelgia.research_context_builder import build_research_context
from entelgia.source_evaluator import evaluate_sources
from entelgia.web_tool import search_and_fetch

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

HIGH_CREDIBILITY_THRESHOLD: float = 0.8

# ---------------------------------------------------------------------------
# Memory persistence (optional)
# ---------------------------------------------------------------------------


def _store_external_knowledge(
    db_path: str,
    query: str,
    url: str,
    summary: str,
    credibility_score: float,
) -> None:
    """Persist a high-credibility source to the ``external_knowledge`` table.

    Creates the table on first use.  Silently skips on any database error so
    the main pipeline is never disrupted.

    Schema
    ------
    id               TEXT PRIMARY KEY
    timestamp        TEXT    ISO-8601 timestamp
    query            TEXT    original search query
    url              TEXT    source URL
    summary          TEXT    extracted text excerpt
    credibility_score  REAL  score in [0, 1]
    """
    try:
        with sqlite3.connect(db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS external_knowledge (
                    id               TEXT PRIMARY KEY,
                    timestamp        TEXT NOT NULL,
                    query            TEXT,
                    url              TEXT,
                    summary          TEXT,
                    credibility_score REAL
                )
                """)
            conn.execute(
                """
                INSERT INTO external_knowledge
                    (id, timestamp, query, url, summary, credibility_score)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    str(uuid.uuid4()),
                    datetime.datetime.now(datetime.timezone.utc).isoformat(),
                    query,
                    url,
                    summary[:1000],
                    credibility_score,
                ),
            )
            conn.commit()
        logger.debug(
            "Stored external knowledge from %r (score=%.2f)", url, credibility_score
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("Failed to store external knowledge: %s", exc)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

_MAX_QUERY_LENGTH: int = 200


def build_research_query(
    seed_text: str,
    dialog_tail: Optional[List[Dict[str, Any]]],
    fixy_reason: Optional[str],
) -> str:
    """Build the best search query from available context.

    Priority order:

    1. An explicit question detected in the last few dialogue turns.
    2. The most informative (longest) recent agent dialogue turn.
    3. Fallback to *seed_text*.

    The returned query is limited to ``_MAX_QUERY_LENGTH`` characters and has
    excessive whitespace collapsed.

    Parameters
    ----------
    seed_text:
        Initial seed / user input string.
    dialog_tail:
        Recent dialogue turns (each a dict with at least a ``"text"`` key).
    fixy_reason:
        Fixy meta-reasoning signal (not currently used to modify the query
        but reserved for future use).

    Returns
    -------
    A compact query string suitable for a web search.
    """
    candidate: str = ""

    if dialog_tail:
        recent = dialog_tail[-4:]

        # Priority 1: explicit question in recent turns
        for turn in reversed(recent):
            text = (turn.get("text", "") if isinstance(turn, dict) else "").strip()
            if "?" in text:
                candidate = text
                break

        # Priority 2: most informative (longest) turn
        if not candidate:
            best = max(
                recent,
                key=lambda t: len(t.get("text", "") if isinstance(t, dict) else ""),
                default=None,
            )
            if best:
                candidate = (
                    best.get("text", "") if isinstance(best, dict) else ""
                ).strip()

    # Priority 3: fall back to seed_text
    if not candidate:
        candidate = (seed_text or "").strip()

    # Normalise whitespace and truncate
    query = " ".join(candidate.split())
    query = query[:_MAX_QUERY_LENGTH]
    logger.debug("build_research_query: query=%r", query)
    return query


def maybe_add_web_context(
    seed_text: str,
    dialog_tail: Optional[List[Dict[str, Any]]] = None,
    fixy_reason: Optional[str] = None,
    db_path: Optional[str] = None,
    max_results: int = 5,
) -> str:
    """Return a formatted external knowledge context block, or empty string.

    Parameters
    ----------
    seed_text:
        Initial seed / user input; evaluated by Fixy to decide if a search
        is needed.
    dialog_tail:
        Optional recent dialogue turns (each a dict with a ``"text"`` key).
        Also inspected when deciding whether to trigger a search.
    fixy_reason:
        Optional Fixy meta-reasoning signal (e.g.
        ``"external_verification_needed"``).  When this matches a known
        research-signal value, a search is triggered regardless of keywords.
    db_path:
        Path to the SQLite database for long-term memory persistence.
        When ``None`` memory storage is skipped.
    max_results:
        Maximum number of web search results to retrieve.

    Returns
    -------
    A formatted string ready to embed in an LLM prompt, or ``""`` when no
    search is performed or an error occurs.
    """
    try:
        if not fixy_should_search(seed_text, dialog_tail, fixy_reason):
            logger.debug("maybe_add_web_context: Fixy decided no search needed.")
            return ""

        query = build_research_query(seed_text, dialog_tail, fixy_reason)
        logger.info("maybe_add_web_context: search triggered, query=%r", query)

        bundle: Dict[str, Any] = search_and_fetch(query, max_results=max_results)
        sources: List[Dict[str, Any]] = bundle.get("sources", [])
        logger.debug("maybe_add_web_context: %d source(s) retrieved", len(sources))

        if not sources:
            logger.debug("maybe_add_web_context: no sources returned.")
            return ""

        scored: List[Dict[str, Any]] = evaluate_sources(sources)

        # Optionally store high-credibility sources in long-term memory
        stored_count = 0
        if db_path:
            for item in scored:
                if item["credibility_score"] >= HIGH_CREDIBILITY_THRESHOLD:
                    url = item["url"]
                    src = next((s for s in sources if s.get("url") == url), {})
                    summary = src.get("text", "") or src.get("snippet", "")
                    _store_external_knowledge(
                        db_path=db_path,
                        query=query,
                        url=url,
                        summary=summary,
                        credibility_score=item["credibility_score"],
                    )
                    stored_count += 1
            logger.debug(
                "maybe_add_web_context: %d source(s) stored to memory",
                stored_count,
            )

        context = build_research_context(bundle, scored)
        return context

    except Exception as exc:  # noqa: BLE001
        logger.warning("maybe_add_web_context: unexpected error: %s", exc)
        return ""

#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Web Research Integration for Entelgia

Provides the high-level ``maybe_add_web_context`` function that ties together
the web search, credibility evaluation, and context-building pipeline.

When Fixy detects that a user message requires external knowledge the
pipeline runs as follows:

1. ``fixy_research_trigger.fixy_should_search`` decides whether to search.
2. ``web_tool.search_and_fetch`` retrieves pages.
3. ``source_evaluator.evaluate_sources`` scores each source.
4. Sources are sorted by credibility score (descending).
5. ``research_context_builder.build_research_context`` formats the block.
6. Optionally, high-credibility sources (score > HIGH_CREDIBILITY_THRESHOLD)
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
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS external_knowledge (
                    id               TEXT PRIMARY KEY,
                    timestamp        TEXT NOT NULL,
                    query            TEXT,
                    url              TEXT,
                    summary          TEXT,
                    credibility_score REAL
                )
                """
            )
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
        logger.debug("Stored external knowledge from %r (score=%.2f)", url, credibility_score)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Failed to store external knowledge: %s", exc)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def maybe_add_web_context(
    user_message: str,
    db_path: Optional[str] = None,
    max_results: int = 5,
) -> str:
    """Return a formatted external knowledge context block, or empty string.

    Parameters
    ----------
    user_message:
        Raw user input; Fixy inspects this to decide if a search is needed.
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
        if not fixy_should_search(user_message):
            logger.debug("maybe_add_web_context: Fixy decided no search needed.")
            return ""

        logger.info("maybe_add_web_context: Fixy triggered search for %r", user_message)

        bundle: Dict[str, Any] = search_and_fetch(user_message, max_results=max_results)
        sources: List[Dict[str, Any]] = bundle.get("sources", [])

        if not sources:
            logger.debug("maybe_add_web_context: no sources returned.")
            return ""

        scored: List[Dict[str, Any]] = evaluate_sources(sources)

        # Optionally store high-credibility sources in long-term memory
        if db_path:
            for item in scored:
                if item["credibility_score"] >= HIGH_CREDIBILITY_THRESHOLD:
                    # Find matching source text
                    url = item["url"]
                    src = next((s for s in sources if s.get("url") == url), {})
                    summary = src.get("text", "") or src.get("snippet", "")
                    _store_external_knowledge(
                        db_path=db_path,
                        query=bundle.get("query", user_message),
                        url=url,
                        summary=summary,
                        credibility_score=item["credibility_score"],
                    )

        context = build_research_context(bundle, scored)
        return context

    except Exception as exc:  # noqa: BLE001
        logger.warning("maybe_add_web_context: unexpected error: %s", exc)
        return ""

#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Web Research Tool for Entelgia

Provides functions to search the internet via DuckDuckGo HTML search,
fetch and extract readable text from web pages, and combine results
into structured research bundles for injection into agent dialogue.

All network operations apply a configurable timeout and fail gracefully
so that a network error never crashes the main Entelgia system.
"""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional

import requests

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_DEFAULT_MAX_RESULTS: int = 5
_DEFAULT_TEXT_LIMIT: int = 6000
_REQUEST_TIMEOUT: int = 10  # seconds

_DUCKDUCKGO_URL = "https://html.duckduckgo.com/html/"

_UNWANTED_TAGS = {"script", "style", "nav", "footer", "header", "aside", "noscript"}


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _get_soup(html: str) -> Any:
    """Parse *html* with BeautifulSoup; returns None when bs4 is unavailable."""
    try:
        from bs4 import BeautifulSoup  # type: ignore[import-untyped]

        return BeautifulSoup(html, "html.parser")
    except ImportError:  # pragma: no cover
        logger.warning(
            "beautifulsoup4 is not installed; page text extraction disabled."
        )
        return None


def _clean_text(text: str) -> str:
    """Collapse multiple blank lines and strip leading/trailing whitespace."""
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def web_search(
    query: str, max_results: int = _DEFAULT_MAX_RESULTS
) -> List[Dict[str, str]]:
    """Search DuckDuckGo HTML interface and return structured results.

    Parameters
    ----------
    query:
        The search query string.
    max_results:
        Maximum number of results to return (default 5).

    Returns
    -------
    List of dicts with keys ``title``, ``url``, ``snippet``.
    Returns an empty list on any network or parsing error.
    """
    results: List[Dict[str, str]] = []
    try:
        response = requests.post(
            _DUCKDUCKGO_URL,
            data={"q": query, "b": "", "kl": ""},
            headers={"User-Agent": "Mozilla/5.0 (compatible; Entelgia/1.0)"},
            timeout=_REQUEST_TIMEOUT,
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        logger.warning("web_search: network error for query %r: %s", query, exc)
        return results

    soup = _get_soup(response.text)
    if soup is None:
        return results

    for result_div in soup.select(".result")[:max_results]:
        title_tag = result_div.select_one(".result__title a")
        snippet_tag = result_div.select_one(".result__snippet")
        url_tag = result_div.select_one(".result__url")

        title = title_tag.get_text(strip=True) if title_tag else ""
        snippet = snippet_tag.get_text(strip=True) if snippet_tag else ""

        # Prefer the href on the title link; fall back to text of .result__url
        url = ""
        if title_tag:
            href = title_tag.get("href", "")
            # DuckDuckGo wraps redirect URLs; extract the real URL via `uddg=`
            uddg_match = re.search(r"uddg=([^&]+)", href)
            if uddg_match:
                from urllib.parse import unquote

                url = unquote(uddg_match.group(1))
            elif href.startswith("http"):
                url = href
        if not url and url_tag:
            raw = url_tag.get_text(strip=True)
            if not raw.startswith("http"):
                raw = "https://" + raw
            url = raw

        if title or url:
            results.append({"title": title, "url": url, "snippet": snippet})

    logger.debug("web_search: %d results for %r", len(results), query)
    return results


def fetch_page_text(url: str, text_limit: int = _DEFAULT_TEXT_LIMIT) -> Dict[str, str]:
    """Download *url* and extract its readable text.

    Removes ``<script>``, ``<style>``, ``<nav>``, ``<footer>``, and other
    chrome-heavy tags.  The extracted text is truncated to *text_limit*
    characters (default 6 000) to keep context concise.

    Parameters
    ----------
    url:
        The URL to fetch.
    text_limit:
        Maximum characters of extracted text to return.

    Returns
    -------
    Dict with keys ``url``, ``title``, ``text``.
    On error ``title`` and ``text`` will be empty strings.
    """
    result: Dict[str, str] = {"url": url, "title": "", "text": ""}
    try:
        response = requests.get(
            url,
            headers={"User-Agent": "Mozilla/5.0 (compatible; Entelgia/1.0)"},
            timeout=_REQUEST_TIMEOUT,
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        logger.warning("fetch_page_text: failed to fetch %r: %s", url, exc)
        return result

    soup = _get_soup(response.text)
    if soup is None:
        return result

    # Extract title
    title_tag = soup.find("title")
    if title_tag:
        result["title"] = title_tag.get_text(strip=True)

    # Remove unwanted elements in-place
    for tag in soup.find_all(_UNWANTED_TAGS):
        tag.decompose()

    # Extract visible text
    raw_text = soup.get_text(separator="\n")
    cleaned = _clean_text(raw_text)
    result["text"] = cleaned[:text_limit]

    logger.debug(
        "fetch_page_text: extracted %d chars from %r", len(result["text"]), url
    )
    return result


def search_and_fetch(
    query: str,
    max_results: int = _DEFAULT_MAX_RESULTS,
    text_limit: int = _DEFAULT_TEXT_LIMIT,
) -> Dict[str, Any]:
    """Perform a web search then fetch full text for each result.

    Parameters
    ----------
    query:
        The search query string.
    max_results:
        Maximum number of search results to retrieve.
    text_limit:
        Maximum characters of page text per source.

    Returns
    -------
    Dict with keys:

    * ``query`` – the original query string
    * ``sources`` – list of dicts, each with ``title``, ``url``,
      ``snippet``, and ``text``
    """
    search_results = web_search(query, max_results=max_results)

    sources: List[Dict[str, str]] = []
    for item in search_results:
        url = item.get("url", "")
        page = fetch_page_text(url, text_limit=text_limit) if url else {}
        sources.append(
            {
                "title": page.get("title") or item.get("title", ""),
                "url": url,
                "snippet": item.get("snippet", ""),
                "text": page.get("text", ""),
            }
        )

    return {"query": query, "sources": sources}

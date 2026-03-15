# tests/test_web_tool.py
"""
Tests for entelgia/web_tool.py

Covers:
- clear_failed_urls — resets the failed-URL blacklist
- _clean_text — collapses multiple blank lines
- fetch_page_text — skips blacklisted URLs; adds 403/404 to blacklist
- web_search — returns list of result dicts; handles network errors gracefully
- search_and_fetch — integrates web_search + fetch_page_text
"""

from __future__ import annotations

import sys
import os
from unittest.mock import MagicMock, patch

import pytest
import requests

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from entelgia.web_tool import (
    _clean_text,
    clear_failed_urls,
    fetch_page_text,
    search_and_fetch,
    web_search,
    _failed_urls,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _mock_response(text: str = "", status_code: int = 200) -> MagicMock:
    """Build a minimal mock requests.Response."""
    mock = MagicMock()
    mock.text = text
    mock.status_code = status_code
    mock.raise_for_status = MagicMock()
    return mock


def _mock_http_error(status_code: int) -> requests.HTTPError:
    """Build a minimal HTTPError with a mock response."""
    resp = MagicMock()
    resp.status_code = status_code
    err = requests.HTTPError(response=resp)
    return err


# ---------------------------------------------------------------------------
# clear_failed_urls
# ---------------------------------------------------------------------------


class TestClearFailedUrls:
    """clear_failed_urls must reset the module-level _failed_urls set."""

    def test_clears_populated_set(self):
        _failed_urls.add("https://example.com/blocked")
        clear_failed_urls()
        assert len(_failed_urls) == 0

    def test_idempotent_on_empty_set(self):
        clear_failed_urls()
        clear_failed_urls()
        assert len(_failed_urls) == 0


# ---------------------------------------------------------------------------
# _clean_text
# ---------------------------------------------------------------------------


class TestCleanText:
    """_clean_text must collapse excessive blank lines and strip whitespace."""

    def test_collapses_three_blank_lines(self):
        result = _clean_text("first\n\n\n\nsecond")
        assert "\n\n\n" not in result
        assert "first" in result
        assert "second" in result

    def test_strips_leading_trailing_whitespace(self):
        result = _clean_text("   hello world   ")
        assert result == "hello world"

    def test_preserves_two_blank_lines(self):
        text = "para1\n\npara2"
        result = _clean_text(text)
        assert "para1" in result
        assert "para2" in result

    def test_handles_empty_string(self):
        assert _clean_text("") == ""


# ---------------------------------------------------------------------------
# fetch_page_text
# ---------------------------------------------------------------------------


class TestFetchPageText:
    """fetch_page_text must handle blacklisted URLs, 403/404 errors, and
    successful fetches."""

    def setup_method(self):
        clear_failed_urls()

    def test_skips_blacklisted_url(self):
        url = "https://example.com/forbidden"
        _failed_urls.add(url)
        result = fetch_page_text(url)
        assert result["url"] == url
        assert result["title"] == ""
        assert result["text"] == ""

    def test_403_adds_to_blacklist(self):
        url = "https://example.com/denied"
        with patch("entelgia.web_tool.requests.get") as mock_get:
            mock_get.return_value = _mock_response(status_code=403)
            mock_get.return_value.raise_for_status.side_effect = _mock_http_error(403)
            result = fetch_page_text(url)
        assert url in _failed_urls
        assert result["text"] == ""

    def test_404_adds_to_blacklist(self):
        url = "https://example.com/notfound"
        with patch("entelgia.web_tool.requests.get") as mock_get:
            mock_get.return_value = _mock_response(status_code=404)
            mock_get.return_value.raise_for_status.side_effect = _mock_http_error(404)
            result = fetch_page_text(url)
        assert url in _failed_urls
        assert result["text"] == ""

    def test_returns_dict_with_expected_keys(self):
        url = "https://example.com/page"
        html = "<html><head><title>Test Page</title></head><body><p>Hello World</p></body></html>"
        with patch("entelgia.web_tool.requests.get") as mock_get:
            mock_get.return_value = _mock_response(text=html)
            result = fetch_page_text(url)
        assert "url" in result
        assert "title" in result
        assert "text" in result
        assert result["url"] == url

    def test_network_error_returns_empty_result(self):
        url = "https://example.com/timeout"
        with patch("entelgia.web_tool.requests.get") as mock_get:
            mock_get.side_effect = requests.RequestException("timeout")
            result = fetch_page_text(url)
        assert result["text"] == ""
        assert result["title"] == ""

    def test_text_limit_is_respected(self):
        url = "https://example.com/long"
        long_text = "A" * 10000
        html = f"<html><body><p>{long_text}</p></body></html>"
        with patch("entelgia.web_tool.requests.get") as mock_get:
            mock_get.return_value = _mock_response(text=html)
            result = fetch_page_text(url, text_limit=100)
        assert len(result["text"]) <= 100


# ---------------------------------------------------------------------------
# web_search
# ---------------------------------------------------------------------------


class TestWebSearch:
    """web_search must return structured results and handle network errors."""

    def test_returns_list_on_network_error(self):
        with patch("entelgia.web_tool.requests.post") as mock_post:
            mock_post.side_effect = requests.RequestException("network error")
            result = web_search("consciousness philosophy")
        assert result == []

    def test_returns_list_on_http_error(self):
        with patch("entelgia.web_tool.requests.post") as mock_post:
            mock = _mock_response(status_code=500)
            mock.raise_for_status.side_effect = requests.HTTPError(response=mock)
            mock_post.return_value = mock
            result = web_search("test query")
        assert isinstance(result, list)

    def test_max_results_respected(self):
        # Build HTML with 10 fake result divs
        divs = "".join(
            f'<div class="result">'
            f'<a class="result__title" href="http://example.com/{i}">Title {i}</a>'
            f'<span class="result__snippet">Snippet {i}</span>'
            f"</div>"
            for i in range(10)
        )
        html = f"<html><body>{divs}</body></html>"
        with patch("entelgia.web_tool.requests.post") as mock_post:
            mock_post.return_value = _mock_response(text=html)
            result = web_search("test", max_results=3)
        assert len(result) <= 3


# ---------------------------------------------------------------------------
# search_and_fetch
# ---------------------------------------------------------------------------


class TestSearchAndFetch:
    """search_and_fetch must combine search and fetch into a bundle."""

    def test_returns_dict_with_query_and_sources(self):
        with patch("entelgia.web_tool.web_search") as mock_search:
            mock_search.return_value = []
            result = search_and_fetch("free will")
        assert "query" in result
        assert "sources" in result
        assert result["query"] == "free will"

    def test_empty_search_results_gives_empty_sources(self):
        with patch("entelgia.web_tool.web_search") as mock_search:
            mock_search.return_value = []
            result = search_and_fetch("nonexistent topic xyz")
        assert result["sources"] == []

    def test_sources_have_expected_keys(self):
        with (
            patch("entelgia.web_tool.web_search") as mock_search,
            patch("entelgia.web_tool.fetch_page_text") as mock_fetch,
        ):
            mock_search.return_value = [
                {"title": "Test", "url": "https://example.com", "snippet": "A test."}
            ]
            mock_fetch.return_value = {
                "url": "https://example.com",
                "title": "Test",
                "text": "Some text.",
            }
            result = search_and_fetch("test query")
        assert len(result["sources"]) == 1
        source = result["sources"][0]
        assert "title" in source
        assert "url" in source
        assert "snippet" in source
        assert "text" in source


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])

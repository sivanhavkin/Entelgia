# tests/test_web_research.py
"""
Tests for the Web Research Module (v2.8.0).

Covers:
- fixy_research_trigger.fixy_should_search
- source_evaluator.evaluate_source / evaluate_sources
- research_context_builder.build_research_context
- web_research.maybe_add_web_context (mocked network)
- web_research._store_external_knowledge (in-memory SQLite)
- context_manager.ContextManager.build_enriched_context with web_context
"""

from __future__ import annotations

import os
import sqlite3
import sys
import tempfile
from typing import Any, Dict, List
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from entelgia.fixy_research_trigger import fixy_should_search
from entelgia.research_context_builder import build_research_context
from entelgia.source_evaluator import evaluate_source, evaluate_sources

# ---------------------------------------------------------------------------
# fixy_research_trigger
# ---------------------------------------------------------------------------


class TestFixyResearchTrigger:
    """Tests for fixy_should_search."""

    def test_trigger_on_latest(self):
        assert fixy_should_search("latest AI research") is True

    def test_trigger_on_research(self):
        assert fixy_should_search("Tell me about recent research on climate") is True

    def test_trigger_on_news(self):
        assert fixy_should_search("What is the current news?") is True

    def test_trigger_on_find(self):
        assert fixy_should_search("Find papers on quantum computing") is True

    def test_trigger_on_search(self):
        assert fixy_should_search("search for new studies") is True

    def test_trigger_on_today(self):
        assert fixy_should_search("What happened today in AI?") is True

    def test_trigger_on_paper(self):
        assert fixy_should_search("Find me a paper on memory") is True

    def test_no_trigger_ordinary_message(self):
        assert fixy_should_search("Hello, how are you?") is False

    def test_no_trigger_empty_string(self):
        assert fixy_should_search("") is False

    def test_no_trigger_whitespace_only(self):
        assert fixy_should_search("   ") is False

    def test_no_trigger_unrelated_words(self):
        assert fixy_should_search("cats and dogs love play time") is False

    def test_case_insensitive(self):
        assert fixy_should_search("LATEST developments in robotics") is True

    def test_word_boundary_matching(self):
        # "searches" contains "search" as a substring but as a different word form
        # The function uses whole-word extraction via re.findall([a-z]+)
        assert fixy_should_search("web searches for truth") is True

    def test_trigger_on_trend(self):
        assert fixy_should_search("What is the current trend?") is True

    # ------------------------------------------------------------------
    # New tests: dialogue-tail trigger
    # ------------------------------------------------------------------

    def test_trigger_from_dialogue_turn(self):
        dialog = [
            {"role": "Socrates", "text": "Tell me your thoughts."},
            {"role": "Athena", "text": "We need current evidence to settle this."},
        ]
        assert fixy_should_search("Let us discuss", dialog_tail=dialog) is True

    def test_trigger_from_dialogue_keyword_external(self):
        # Seed topic (index 0) is neutral; trigger keyword is at index 1
        dialog = [
            {"role": "system", "text": "Let us begin the discussion."},
            {"role": "Socrates", "text": "Find recent external sources on this topic."},
        ]
        assert fixy_should_search("Discuss.", dialog_tail=dialog) is True

    def test_seed_topic_at_index_0_does_not_trigger(self):
        # Keyword only in the seed topic at index 0 – must NOT trigger
        dialog = [
            {"role": "system", "text": "Find recent external sources on this topic."},
        ]
        assert fixy_should_search("Discuss.", dialog_tail=dialog) is False

    def test_no_trigger_from_empty_dialogue(self):
        assert fixy_should_search("Hello.", dialog_tail=[]) is False

    def test_no_trigger_dialog_tail_none(self):
        assert fixy_should_search("Hello.", dialog_tail=None) is False

    def test_dialogue_only_last_4_turns_inspected(self):
        # Keyword only in old turns beyond the window – must NOT trigger
        old_turn = {
            "role": "Socrates",
            "text": "latest research was mentioned long ago",
        }
        neutral_turns = [
            {"role": "Athena", "text": "I agree."},
            {"role": "Socrates", "text": "Indeed."},
            {"role": "Athena", "text": "Certainly."},
            {"role": "Socrates", "text": "Quite so."},
        ]
        dialog = [old_turn] + neutral_turns
        assert fixy_should_search("Hello.", dialog_tail=dialog) is False

    def test_trigger_phrase_in_dialogue(self):
        # Seed topic (index 0) is neutral; trigger phrase is at index 1
        dialog = [
            {"role": "system", "text": "Welcome to the debate."},
            {"role": "Athena", "text": "We should find sources to verify this."},
        ]
        assert fixy_should_search("Interesting.", dialog_tail=dialog) is True

    # ------------------------------------------------------------------
    # New tests: fixy_reason trigger
    # ------------------------------------------------------------------

    def test_trigger_from_fixy_reason_external_verification(self):
        assert (
            fixy_should_search(
                "Hello.",
                fixy_reason="external_verification_needed",
            )
            is True
        )

    def test_trigger_from_fixy_reason_research_needed(self):
        assert (
            fixy_should_search(
                "Hello.",
                fixy_reason="research_needed_for_synthesis",
            )
            is True
        )

    def test_trigger_from_fixy_reason_factual_uncertainty(self):
        assert (
            fixy_should_search(
                "Hello.",
                fixy_reason="factual_uncertainty_detected",
            )
            is True
        )

    def test_no_trigger_unknown_fixy_reason(self):
        assert fixy_should_search("Hello.", fixy_reason="some_other_signal") is False

    def test_no_trigger_fixy_reason_none(self):
        assert fixy_should_search("Hello.", fixy_reason=None) is False


# ---------------------------------------------------------------------------
# source_evaluator
# ---------------------------------------------------------------------------


class TestEvaluateSource:
    """Tests for evaluate_source."""

    def _source(self, url: str, text: str = "") -> Dict[str, Any]:
        return {"url": url, "text": text}

    def test_edu_domain_scores_higher(self):
        result = evaluate_source(self._source("https://mit.edu/paper", "x" * 600))
        assert result["credibility_score"] >= 0.3

    def test_gov_domain_scores_higher(self):
        result = evaluate_source(self._source("https://cdc.gov/topic", "x" * 600))
        assert result["credibility_score"] >= 0.3

    def test_trusted_domain_wikipedia(self):
        result = evaluate_source(
            self._source("https://en.wikipedia.org/wiki/AI", "x" * 600)
        )
        assert result["credibility_score"] >= 0.2

    def test_long_text_boosts_score(self):
        base = evaluate_source(self._source("https://example.com", "x" * 100))
        long = evaluate_source(self._source("https://example.com", "x" * 600))
        assert long["credibility_score"] > base["credibility_score"]

    def test_very_short_text_penalised(self):
        result = evaluate_source(self._source("https://example.com", "hi"))
        assert result["credibility_score"] == 0.0

    def test_score_clamped_to_one(self):
        result = evaluate_source(self._source("https://nih.gov/research", "x" * 800))
        assert result["credibility_score"] <= 1.0

    def test_score_clamped_to_zero(self):
        result = evaluate_source(self._source("https://spammy-ads.example.com", "ad"))
        assert result["credibility_score"] >= 0.0

    def test_returns_url(self):
        url = "https://example.org/page"
        result = evaluate_source(self._source(url, "sample text " * 50))
        assert result["url"] == url

    def test_score_is_float(self):
        result = evaluate_source(self._source("https://example.com", "content " * 100))
        assert isinstance(result["credibility_score"], float)


class TestEvaluateSources:
    """Tests for evaluate_sources."""

    def test_returns_sorted_descending(self):
        sources = [
            {"url": "https://spammy.example.com", "text": "short"},
            {"url": "https://nih.gov/study", "text": "detailed content " * 50},
            {"url": "https://example.com", "text": "medium content " * 30},
        ]
        ranked = evaluate_sources(sources)
        scores = [s["credibility_score"] for s in ranked]
        assert scores == sorted(scores, reverse=True)

    def test_empty_input(self):
        assert evaluate_sources([]) == []

    def test_all_items_returned(self):
        sources = [
            {"url": "https://a.edu", "text": "text"},
            {"url": "https://b.com", "text": "text"},
        ]
        ranked = evaluate_sources(sources)
        assert len(ranked) == 2


# ---------------------------------------------------------------------------
# research_context_builder
# ---------------------------------------------------------------------------


class TestBuildResearchContext:
    """Tests for build_research_context."""

    def _bundle(self, n: int = 2) -> Dict[str, Any]:
        sources = [
            {
                "url": f"https://source{i}.edu/page",
                "title": f"Title {i}",
                "snippet": f"Snippet {i}",
                "text": f"Body text content number {i}. " * 30,
            }
            for i in range(1, n + 1)
        ]
        return {"query": "test query", "sources": sources}

    def _scored(self, bundle: Dict[str, Any]) -> List[Dict[str, Any]]:
        return evaluate_sources(bundle["sources"])

    def test_returns_string(self):
        bundle = self._bundle(2)
        result = build_research_context(bundle, self._scored(bundle))
        assert isinstance(result, str)

    def test_contains_external_research_header(self):
        bundle = self._bundle(2)
        result = build_research_context(bundle, self._scored(bundle))
        assert "External Research:" in result

    def test_contains_source_entries(self):
        bundle = self._bundle(2)
        result = build_research_context(bundle, self._scored(bundle))
        assert "Source 1:" in result

    def test_respects_max_sources(self):
        bundle = self._bundle(5)
        result = build_research_context(bundle, self._scored(bundle), max_sources=2)
        assert "Source 1:" in result
        assert "Source 2:" in result
        assert "Source 3:" not in result

    def test_empty_sources_returns_empty_string(self):
        bundle = {"query": "q", "sources": []}
        result = build_research_context(bundle, [])
        assert result == ""

    def test_contains_credibility_field(self):
        bundle = self._bundle(1)
        result = build_research_context(bundle, self._scored(bundle))
        assert "Credibility:" in result

    def test_contains_url_field(self):
        bundle = self._bundle(1)
        result = build_research_context(bundle, self._scored(bundle))
        assert "URL:" in result


# ---------------------------------------------------------------------------
# web_research.maybe_add_web_context
# ---------------------------------------------------------------------------


class TestMaybeAddWebContext:
    """Tests for maybe_add_web_context with mocked network calls."""

    def _mock_bundle(self) -> Dict[str, Any]:
        return {
            "query": "latest AI research",
            "sources": [
                {
                    "url": "https://arxiv.org/abs/2401.00001",
                    "title": "AI Paper 2026",
                    "snippet": "A great study on AI.",
                    "text": "Detailed text about AI research " * 40,
                }
            ],
        }

    def test_returns_empty_string_when_no_trigger(self):
        from entelgia.web_research import maybe_add_web_context

        result = maybe_add_web_context("Hello, how are you?")
        assert result == ""

    def test_returns_context_string_when_triggered(self):
        from entelgia.web_research import maybe_add_web_context

        with patch(
            "entelgia.web_research.search_and_fetch", return_value=self._mock_bundle()
        ):
            result = maybe_add_web_context("latest AI research")
        assert isinstance(result, str)
        assert "External Research:" in result

    def test_returns_empty_on_network_error(self):
        from entelgia.web_research import maybe_add_web_context

        with patch(
            "entelgia.web_research.search_and_fetch",
            side_effect=Exception("network error"),
        ):
            result = maybe_add_web_context("latest AI research")
        assert result == ""

    def test_returns_empty_when_no_sources(self):
        from entelgia.web_research import maybe_add_web_context

        empty_bundle = {"query": "latest AI", "sources": []}
        with patch("entelgia.web_research.search_and_fetch", return_value=empty_bundle):
            result = maybe_add_web_context("latest AI research")
        assert result == ""

    def test_triggered_by_dialogue_turn(self):
        from entelgia.web_research import maybe_add_web_context

        # Seed topic at index 0 is neutral; trigger is at index 1
        dialog = [
            {"role": "system", "text": "Let us begin."},
            {"role": "Athena", "text": "We need to find recent papers on this."},
        ]
        with patch(
            "entelgia.web_research.search_and_fetch", return_value=self._mock_bundle()
        ):
            result = maybe_add_web_context("Discuss the matter.", dialog_tail=dialog)
        assert isinstance(result, str)
        assert "External Research:" in result

    def test_triggered_by_fixy_reason(self):
        from entelgia.web_research import maybe_add_web_context

        with patch(
            "entelgia.web_research.search_and_fetch", return_value=self._mock_bundle()
        ):
            result = maybe_add_web_context(
                "Hello.",
                fixy_reason="external_verification_needed",
            )
        assert isinstance(result, str)
        assert "External Research:" in result

    def test_skipped_when_no_trigger_with_dialog(self):
        from entelgia.web_research import maybe_add_web_context

        dialog = [{"role": "Athena", "text": "I agree completely."}]
        result = maybe_add_web_context("Let us talk.", dialog_tail=dialog)
        assert result == ""

    def test_graceful_failure_on_network_error_with_dialogue(self):
        from entelgia.web_research import maybe_add_web_context

        # Seed topic at index 0 is neutral; trigger is at index 1
        dialog = [
            {"role": "system", "text": "Welcome."},
            {"role": "Athena", "text": "We need current evidence."},
        ]
        with patch(
            "entelgia.web_research.search_and_fetch",
            side_effect=Exception("timeout"),
        ):
            result = maybe_add_web_context("Hello.", dialog_tail=dialog)
        assert result == ""


# ---------------------------------------------------------------------------
# web_research.build_research_query
# ---------------------------------------------------------------------------


class TestBuildResearchQuery:
    """Tests for build_research_query."""

    def test_fallback_to_seed_when_no_dialog(self):
        from entelgia.web_research import build_research_query

        result = build_research_query("tell me about AI", None, None)
        assert result == "tell me about AI"

    def test_uses_question_from_dialogue(self):
        from entelgia.web_research import build_research_query

        dialog = [
            {"role": "Socrates", "text": "This is interesting."},
            {
                "role": "Athena",
                "text": "What recent research exists on consciousness?",
            },
        ]
        result = build_research_query("Seed text.", dialog, None)
        assert "consciousness" in result

    def test_falls_back_to_longest_turn_without_question(self):
        from entelgia.web_research import build_research_query

        dialog = [
            {"role": "Socrates", "text": "Short."},
            {
                "role": "Athena",
                "text": "A much longer statement about cognitive architecture.",
            },
        ]
        result = build_research_query("Seed.", dialog, None)
        assert "cognitive architecture" in result

    def test_query_within_max_length(self):
        from entelgia.web_research import build_research_query

        long_text = "word " * 300
        dialog = [{"role": "Athena", "text": long_text}]
        result = build_research_query("seed", dialog, None)
        assert len(result) <= 200

    def test_empty_dialog_falls_back_to_seed(self):
        from entelgia.web_research import build_research_query

        result = build_research_query("my seed query", [], None)
        assert result == "my seed query"

    def test_whitespace_normalised(self):
        from entelgia.web_research import build_research_query

        result = build_research_query("  hello   world  ", None, None)
        assert result == "hello world"


class TestStoreExternalKnowledge:
    """Tests for _store_external_knowledge using a temporary SQLite database."""

    def test_creates_table_and_stores_row(self):
        from entelgia.web_research import _store_external_knowledge

        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name
        try:
            _store_external_knowledge(
                db_path=db_path,
                query="AI research",
                url="https://arxiv.org/abs/test",
                summary="This is a test summary.",
                credibility_score=0.9,
            )
            with sqlite3.connect(db_path) as conn:
                rows = conn.execute("SELECT * FROM external_knowledge").fetchall()
            assert len(rows) == 1
            row = rows[0]
            assert row[2] == "AI research"  # query
            assert row[3] == "https://arxiv.org/abs/test"  # url
            assert row[5] == 0.9  # credibility_score
        finally:
            if os.path.exists(db_path):
                os.remove(db_path)

    def test_does_not_raise_on_invalid_db_path(self):
        from entelgia.web_research import _store_external_knowledge

        # Should silently swallow the error
        _store_external_knowledge(
            db_path="/nonexistent_dir/cannot_create.db",
            query="q",
            url="https://example.com",
            summary="s",
            credibility_score=0.9,
        )

    def test_summary_truncated_to_1000_chars(self):
        from entelgia.web_research import _store_external_knowledge

        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name
        try:
            long_summary = "x" * 5000
            _store_external_knowledge(
                db_path=db_path,
                query="q",
                url="https://example.com",
                summary=long_summary,
                credibility_score=0.85,
            )
            with sqlite3.connect(db_path) as conn:
                row = conn.execute("SELECT summary FROM external_knowledge").fetchone()
            assert len(row[0]) <= 1000
        finally:
            if os.path.exists(db_path):
                os.remove(db_path)


# ---------------------------------------------------------------------------
# ContextManager integration
# ---------------------------------------------------------------------------


class TestContextManagerWebContext:
    """Tests for ContextManager.build_enriched_context with web_context."""

    def _make_context_manager(self):
        from entelgia.context_manager import ContextManager

        return ContextManager()

    def _base_args(self) -> Dict[str, Any]:
        return dict(
            agent_name="Socrates",
            agent_lang="en",
            persona="I am a philosopher.",
            drives={
                "id_strength": 5.0,
                "ego_strength": 5.0,
                "superego_strength": 5.0,
                "self_awareness": 0.5,
            },
            user_seed="TOPIC: Test\nThink carefully.",
            dialog_tail=[{"role": "Athena", "text": "What do you think?"}],
            stm=[],
            ltm=[],
            debate_profile={"style": "analytical"},
            show_pronoun=False,
            agent_pronoun=None,
        )

    def test_prompt_without_web_context(self):
        cm = self._make_context_manager()
        prompt = cm.build_enriched_context(**self._base_args())
        assert "External Knowledge Context" not in prompt

    def test_prompt_with_web_context_contains_section(self):
        cm = self._make_context_manager()
        args = self._base_args()
        args["web_context"] = (
            "External Research:\n\nSource 1:\n  Title: Test\n  URL: https://example.com\n  Credibility: 0.85\n  Summary Text: Sample content."
        )
        prompt = cm.build_enriched_context(**args)
        assert "External Knowledge Context:" in prompt
        assert "External Research:" in prompt

    def test_prompt_with_web_context_includes_agent_instructions(self):
        cm = self._make_context_manager()
        args = self._base_args()
        args["web_context"] = (
            "External Research:\n\nSource 1:\n  Title: T\n  URL: u\n  Credibility: 0.9\n  Summary Text: text."
        )
        prompt = cm.build_enriched_context(**args)
        assert "Superego must verify credibility" in prompt
        assert "Ego must integrate sources" in prompt

    def test_prompt_with_empty_web_context_no_section(self):
        cm = self._make_context_manager()
        args = self._base_args()
        args["web_context"] = ""
        prompt = cm.build_enriched_context(**args)
        assert "External Knowledge Context" not in prompt

    def test_prompt_ends_with_respond_now(self):
        cm = self._make_context_manager()
        args = self._base_args()
        args["web_context"] = (
            "External Research:\n\nSource 1:\n  Title: T\n  URL: u\n  Credibility: 0.9\n  Summary Text: text."
        )
        prompt = cm.build_enriched_context(**args)
        assert "Respond now:" in prompt

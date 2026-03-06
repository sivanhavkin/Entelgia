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

from entelgia.fixy_research_trigger import find_trigger, fixy_should_search
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
        assert fixy_should_search("Find paper on quantum computing") is True

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

    def test_logs_trigger_keyword_on_seed_match(self, caplog):
        import logging

        with caplog.at_level(logging.INFO, logger="entelgia.fixy_research_trigger"):
            fixy_should_search("Find the latest AI news")
        assert any("web search triggered by keyword:" in m for m in caplog.messages)

    def test_logs_trigger_keyword_on_dialogue_match(self, caplog):
        import logging

        dialog = [
            {"role": "system", "text": "Let us begin."},
            {"role": "Athena", "text": "We need current evidence for this claim."},
        ]
        with caplog.at_level(logging.INFO, logger="entelgia.fixy_research_trigger"):
            fixy_should_search("Neutral seed.", dialog_tail=dialog)
        assert any("web search triggered by keyword:" in m for m in caplog.messages)


# ---------------------------------------------------------------------------
# fixy_research_trigger.find_trigger
# ---------------------------------------------------------------------------


class TestFindTrigger:
    """Tests for the find_trigger helper."""

    def test_returns_none_on_empty_string(self):
        assert find_trigger("") is None

    def test_returns_none_on_whitespace_only(self):
        assert find_trigger("   ") is None

    def test_returns_none_when_no_trigger(self):
        assert find_trigger("cats and dogs love play time") is None

    def test_returns_matched_keyword(self):
        result = find_trigger("latest AI research")
        assert result == "latest"

    def test_returns_first_keyword_in_sentence(self):
        # "recent" appears at position 0, before "sources" at position 7;
        # position wins over alphabetical order ("sources" > "recent" alphabetically).
        result = find_trigger("recent sources on some topic")
        assert result == "recent"

    def test_phrase_takes_priority_over_single_keyword(self):
        # "latest research" is a phrase; "latest" is also a standalone keyword
        result = find_trigger("latest research on climate")
        assert result == "latest research"

    def test_case_insensitive_keyword(self):
        result = find_trigger("LATEST developments in robotics")
        assert result == "latest"

    def test_returns_keyword_from_dialogue_prose(self):
        # "latest" appears before "sources" in the text, so "latest" is returned.
        result = find_trigger(
            "Athena, I think we need to check the latest sources on this."
        )
        assert result == "latest"

    def test_returns_none_for_agent_name_alone(self):
        # Agent names like "Athena" must not be trigger words
        assert find_trigger("Athena says hello.") is None

    def test_returns_none_for_socrates_alone(self):
        assert find_trigger("Socrates poses the question.") is None


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

        # Use a seed without trigger keywords so fixy_reason is the sole trigger.
        # "Tell me about AI" produces a query that overlaps with the mock
        # AI-research bundle and therefore passes the quality gate.
        with patch(
            "entelgia.web_research.search_and_fetch", return_value=self._mock_bundle()
        ):
            result = maybe_add_web_context(
                "Tell me about AI",
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

    def test_agent_name_excluded_when_trigger_found_in_question(self):
        # Agent name "Athena" in prose must not appear in the query when a
        # trigger keyword anchors the fragment extraction.
        from entelgia.web_research import build_research_query

        dialog = [
            {"role": "Socrates", "text": "Let us think carefully."},
            {
                "role": "Socrates",
                "text": (
                    "Athena, I think we need to find the latest research "
                    "on consciousness?"
                ),
            },
        ]
        result = build_research_query("Seed.", dialog, None)
        assert "Athena" not in result
        assert "consciousness" in result

    def test_query_starts_at_trigger_keyword(self):
        # When dialogue contains an agent name before the trigger, the returned
        # query must NOT include the agent name; the fragment starts at the
        # trigger keyword or phrase instead.
        from entelgia.web_research import build_research_query

        dialog = [
            {"role": "system", "text": "Welcome."},
            {
                "role": "Fixy",
                "text": "Socrates, please search for recent papers on ethics.",
            },
        ]
        result = build_research_query("Intro.", dialog, None)
        # The query must exclude the agent name preamble
        assert "Socrates" not in result
        # The query should contain the substantive topic
        assert "ethics" in result

    def test_trigger_fragment_respects_max_words(self):
        # The fragment must not exceed _TRIGGER_FRAGMENT_MAX_WORDS words even
        # when the source text is very long.
        from entelgia.web_research import _extract_trigger_fragment

        long_text = "find " + " ".join(["word"] * 50)
        result = _extract_trigger_fragment(long_text, "find")
        assert len(result.split()) <= 15

    def test_extract_trigger_fragment_fallback_on_missing_trigger(self):
        # When the trigger is not found literally in the text, a safe
        # truncation is returned instead of raising an error.
        from entelgia.web_research import _extract_trigger_fragment

        result = _extract_trigger_fragment("Some text without the keyword.", "missing")
        assert isinstance(result, str)
        assert len(result) > 0

    def test_fragment_begins_at_trigger_when_trigger_appears_later(self):
        # When the trigger word appears mid-sentence, the fragment must start
        # at the trigger position — not at the beginning of the sentence.
        from entelgia.web_research import _extract_trigger_fragment

        text = "Reflecting on the nature of truth and our understanding today is key."
        result = _extract_trigger_fragment(text, "today")
        # The result must begin with the trigger word (after sanitization)
        assert result.lower().startswith("today")

    def test_query_does_not_start_from_sentence_beginning(self):
        # Conversational filler before the trigger must be excluded from the query.
        from entelgia.web_research import build_research_query

        dialog = [
            {
                "role": "Athena",
                "text": (
                    "Reflecting on the nature of truth and our understanding "
                    "today is what research shows?"
                ),
            }
        ]
        result = build_research_query("seed", dialog, None)
        # The conversational preamble before "today" must not appear in the query
        assert "Reflecting" not in result
        assert "nature" not in result
        # The trigger and content after it must drive the query
        assert "today" in result

    def test_sanitize_and_compress_run_after_fragment_extraction(self):
        # _extract_trigger_fragment must apply _sanitize_text then
        # _compress_to_keywords so that agent names and stopwords are removed
        # from the extracted fragment.
        from entelgia.web_research import _extract_trigger_fragment

        # "Athena" is an agent name that should be stripped by _sanitize_text;
        # "the" is a stopword that should be removed by _compress_to_keywords.
        text = "today Athena explains the philosophy of mind"
        result = _extract_trigger_fragment(text, "today")
        assert "Athena" not in result
        # Use split() to check for the standalone stopword token, not a substring
        assert "the" not in result.split()
        # Core content keywords must be retained
        assert "today" in result
        assert "philosophy" in result


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


# ---------------------------------------------------------------------------
# _sanitize_text
# ---------------------------------------------------------------------------


class TestSanitizeText:
    """Tests for the _sanitize_text helper."""

    def test_removes_possessive_s(self):
        from entelgia.web_research import _sanitize_text

        assert _sanitize_text("history's patterns") == "history patterns"

    def test_removes_period(self):
        from entelgia.web_research import _sanitize_text

        assert _sanitize_text("hello.") == "hello"

    def test_removes_question_mark(self):
        from entelgia.web_research import _sanitize_text

        assert _sanitize_text("what is this?") == "what is this"

    def test_removes_comma(self):
        from entelgia.web_research import _sanitize_text

        assert _sanitize_text("one, two") == "one two"

    def test_removes_agent_name_athena(self):
        from entelgia.web_research import _sanitize_text

        result = _sanitize_text("Athena history patterns")
        assert "Athena" not in result
        assert "history" in result

    def test_removes_agent_name_socrates(self):
        from entelgia.web_research import _sanitize_text

        result = _sanitize_text("Socrates contemplates truth")
        assert "Socrates" not in result
        assert "truth" in result

    def test_removes_agent_name_fixy(self):
        from entelgia.web_research import _sanitize_text

        result = _sanitize_text("Fixy verifies the claim")
        assert "Fixy" not in result

    def test_removes_agent_name_observer(self):
        from entelgia.web_research import _sanitize_text

        result = _sanitize_text("Observer notes the pattern")
        assert "Observer" not in result

    def test_removes_agent_name_case_insensitive(self):
        from entelgia.web_research import _sanitize_text

        result = _sanitize_text("ATHENA says hello")
        assert "ATHENA" not in result
        assert "says" in result

    def test_removes_balanced_integration_mode(self):
        from entelgia.web_research import _sanitize_text

        result = _sanitize_text("in balanced integration mode I contemplate history")
        assert "balanced integration mode" not in result
        assert "history" in result

    def test_removes_reflective_mode(self):
        from entelgia.web_research import _sanitize_text

        result = _sanitize_text("reflective mode engaged for thought")
        assert "reflective mode" not in result

    def test_removes_observer_mode(self):
        from entelgia.web_research import _sanitize_text

        result = _sanitize_text("observer mode analysis complete")
        assert "observer mode" not in result

    def test_normalises_whitespace(self):
        from entelgia.web_research import _sanitize_text

        result = _sanitize_text("  hello   world  ")
        assert result == "hello world"

    def test_preserves_content_words(self):
        from entelgia.web_research import _sanitize_text

        result = _sanitize_text("history patterns civilizations")
        assert result == "history patterns civilizations"


# ---------------------------------------------------------------------------
# _compress_to_keywords
# ---------------------------------------------------------------------------


class TestCompressToKeywords:
    """Tests for the _compress_to_keywords helper."""

    def test_removes_stopword_the(self):
        from entelgia.web_research import _compress_to_keywords

        result = _compress_to_keywords("the history of nations")
        assert "the" not in result.split()
        assert "history" in result

    def test_removes_stopword_a(self):
        from entelgia.web_research import _compress_to_keywords

        result = _compress_to_keywords("a memory identity formation")
        assert "a" not in result.split()

    def test_removes_stopword_of(self):
        from entelgia.web_research import _compress_to_keywords

        result = _compress_to_keywords("formation of civilizations")
        assert "of" not in result.split()
        assert "formation" in result
        assert "civilizations" in result

    def test_removes_stopword_and(self):
        from entelgia.web_research import _compress_to_keywords

        result = _compress_to_keywords("memory and identity")
        assert "and" not in result.split()

    def test_removes_stopword_in(self):
        from entelgia.web_research import _compress_to_keywords

        result = _compress_to_keywords("history in civilizations")
        assert "in" not in result.split()

    def test_removes_stopword_within(self):
        from entelgia.web_research import _compress_to_keywords

        result = _compress_to_keywords("patterns within identity formation")
        assert "within" not in result.split()
        assert "patterns" in result

    def test_removes_stopword_across(self):
        from entelgia.web_research import _compress_to_keywords

        result = _compress_to_keywords("history across civilizations")
        assert "across" not in result.split()

    def test_limits_to_six_words(self):
        from entelgia.web_research import _compress_to_keywords

        text = "history identity memory truth knowledge philosophy ethics virtue"
        result = _compress_to_keywords(text)
        assert len(result.split()) <= 6

    def test_converts_sentence_to_keywords(self):
        from entelgia.web_research import _compress_to_keywords

        # Per spec example: "history patterns resonate within identity formation
        # across civilizations" → "history identity formation civilizations"
        result = _compress_to_keywords(
            "history patterns resonate within identity formation across civilizations"
        )
        assert "within" not in result.split()
        assert "across" not in result.split()
        assert "history" in result
        assert "identity" in result

    def test_stopword_check_is_case_insensitive(self):
        from entelgia.web_research import _compress_to_keywords

        result = _compress_to_keywords("The history OF nations")
        assert "The" not in result.split()
        assert "OF" not in result.split()
        assert "history" in result


# ---------------------------------------------------------------------------
# Trigger cooldown
# ---------------------------------------------------------------------------


class TestTriggerCooldown:
    """Tests for the per-trigger cooldown in fixy_should_search."""

    def test_first_occurrence_triggers_search(self):
        assert fixy_should_search("latest AI news") is True

    def test_same_trigger_within_cooldown_window_does_not_trigger(self):
        # First call fires the trigger
        assert fixy_should_search("latest news") is True
        # Subsequent calls within the cooldown window are suppressed
        for _ in range(5):
            assert fixy_should_search("latest news") is False

    def test_trigger_allowed_after_cooldown_expires(self):
        from entelgia import fixy_research_trigger as frt

        assert fixy_should_search("latest news") is True
        # Simulate cooldown expiry by winding the turn counter forward
        frt._trigger_turn_counter += frt._COOLDOWN_TURNS
        assert fixy_should_search("latest news") is True

    def test_different_triggers_are_independent(self):
        # "latest" fires, then "recent" fires independently (no cross-keyword cooldown)
        assert fixy_should_search("latest news") is True
        assert fixy_should_search("recent study") is True

    def test_cooldown_applies_to_dialogue_triggers(self):
        # Fire "current" from dialogue
        dialog = [
            {"role": "system", "text": "Start."},
            {"role": "Athena", "text": "We need current evidence."},
        ]
        assert fixy_should_search("Neutral seed.", dialog_tail=dialog) is True
        # Same trigger in the next call – cooldown applies
        assert fixy_should_search("Neutral seed.", dialog_tail=dialog) is False

    def test_clear_cooldown_resets_state(self):
        from entelgia.fixy_research_trigger import clear_trigger_cooldown

        assert fixy_should_search("latest news") is True
        assert fixy_should_search("latest news") is False
        clear_trigger_cooldown()
        assert fixy_should_search("latest news") is True


# ---------------------------------------------------------------------------
# Search result cache
# ---------------------------------------------------------------------------


class TestQueryCache:
    """Tests for the search result cache in maybe_add_web_context."""

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

    def test_cache_hit_avoids_second_network_call(self):
        """When the same query is repeated, search_and_fetch is called only once."""
        from entelgia.web_research import maybe_add_web_context

        with patch(
            "entelgia.web_research.search_and_fetch", return_value=self._mock_bundle()
        ) as mock_fetch:
            maybe_add_web_context("latest AI research")
            # Reset cooldown so the second call is allowed
            from entelgia.fixy_research_trigger import clear_trigger_cooldown

            clear_trigger_cooldown()
            maybe_add_web_context("latest AI research")
        # search_and_fetch must only be called once due to the cache
        assert mock_fetch.call_count == 1

    def test_cache_returns_valid_context_on_second_call(self):
        """Context returned on cache hit is identical to the first call."""
        from entelgia.web_research import maybe_add_web_context

        with patch(
            "entelgia.web_research.search_and_fetch", return_value=self._mock_bundle()
        ):
            first = maybe_add_web_context("latest AI research")
        # Reset cooldown only
        from entelgia.fixy_research_trigger import clear_trigger_cooldown

        clear_trigger_cooldown()
        with patch(
            "entelgia.web_research.search_and_fetch", return_value=self._mock_bundle()
        ) as mock_fetch:
            second = maybe_add_web_context("latest AI research")
        # Should not have called search_and_fetch again (cache hit)
        assert mock_fetch.call_count == 0
        assert first == second


# ---------------------------------------------------------------------------
# Topic research cache
# ---------------------------------------------------------------------------


class TestTopicResearchCache:
    """Tests for the topic research cache in maybe_add_web_context."""

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

    def test_topic_not_repeated_within_session(self):
        """When a topic has already been researched, subsequent calls return ""."""
        from entelgia.web_research import maybe_add_web_context

        with patch(
            "entelgia.web_research.search_and_fetch", return_value=self._mock_bundle()
        ):
            first = maybe_add_web_context(
                "latest AI research", topic="AI & machine learning"
            )

        # Reset trigger cooldown so the second call is not blocked by cooldown
        from entelgia.fixy_research_trigger import clear_trigger_cooldown

        clear_trigger_cooldown()

        with patch(
            "entelgia.web_research.search_and_fetch", return_value=self._mock_bundle()
        ) as mock_fetch:
            second = maybe_add_web_context(
                "latest AI research", topic="AI & machine learning"
            )

        assert "External Research:" in first
        assert second == ""
        # The second call must not reach the network
        assert mock_fetch.call_count == 0

    def test_different_topics_are_independent(self):
        """Two different topics both get researched."""
        from entelgia.web_research import maybe_add_web_context

        with patch(
            "entelgia.web_research.search_and_fetch", return_value=self._mock_bundle()
        ):
            r1 = maybe_add_web_context("latest AI research", topic="machine learning")

        from entelgia.fixy_research_trigger import clear_trigger_cooldown

        clear_trigger_cooldown()

        with patch(
            "entelgia.web_research.search_and_fetch", return_value=self._mock_bundle()
        ):
            r2 = maybe_add_web_context("latest AI research", topic="consciousness")

        assert "External Research:" in r1
        assert "External Research:" in r2


# ---------------------------------------------------------------------------
# Search quality gate
# ---------------------------------------------------------------------------


class TestQualityGate:
    """Tests for the search quality gate in maybe_add_web_context."""

    def test_skips_injection_when_no_pages_fetched(self):
        """When all sources have empty text, context must not be injected."""
        from entelgia.web_research import maybe_add_web_context

        empty_text_bundle = {
            "query": "latest AI",
            "sources": [
                {
                    "url": "https://example.com",
                    "title": "AI",
                    "snippet": "",
                    "text": "",
                },
            ],
        }
        with patch(
            "entelgia.web_research.search_and_fetch", return_value=empty_text_bundle
        ):
            result = maybe_add_web_context("latest AI research")
        assert result == ""

    def test_skips_injection_when_topic_overlap_too_low(self):
        """When query words do not appear in results, context is not injected."""
        from entelgia.web_research import maybe_add_web_context

        # Query keywords like "latest", "ai", "research" won't overlap with
        # purely unrelated source text.
        irrelevant_bundle = {
            "query": "latest AI research",
            "sources": [
                {
                    "url": "https://example.com",
                    "title": "Cooking tips",
                    "snippet": "Best recipes for dinner.",
                    "text": "Great cooking tips for every meal. " * 50,
                }
            ],
        }
        with patch(
            "entelgia.web_research.search_and_fetch", return_value=irrelevant_bundle
        ):
            result = maybe_add_web_context("latest AI research")
        assert result == ""

    def test_injects_context_when_quality_gate_passes(self):
        """Relevant sources with fetched text pass the quality gate."""
        from entelgia.web_research import maybe_add_web_context

        relevant_bundle = {
            "query": "latest AI research",
            "sources": [
                {
                    "url": "https://arxiv.org/abs/2401.00001",
                    "title": "AI Research Paper",
                    "snippet": "A study on latest AI research trends.",
                    "text": "Detailed information about the latest AI research trends. "
                    * 20,
                }
            ],
        }
        with patch(
            "entelgia.web_research.search_and_fetch", return_value=relevant_bundle
        ):
            result = maybe_add_web_context("latest AI research")
        assert "External Research:" in result


# ---------------------------------------------------------------------------
# Structured logging
# ---------------------------------------------------------------------------


class TestStructuredLogging:
    """Tests for structured log output in maybe_add_web_context."""

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

    def test_logs_sanitized_query(self, caplog):
        from entelgia.web_research import maybe_add_web_context
        import logging

        with caplog.at_level(logging.INFO, logger="entelgia.web_research"):
            with patch(
                "entelgia.web_research.search_and_fetch",
                return_value=self._mock_bundle(),
            ):
                maybe_add_web_context("latest AI research")

        assert any("sanitized query" in m for m in caplog.messages)

    def test_logs_search_results_count(self, caplog):
        from entelgia.web_research import maybe_add_web_context
        import logging

        with caplog.at_level(logging.INFO, logger="entelgia.web_research"):
            with patch(
                "entelgia.web_research.search_and_fetch",
                return_value=self._mock_bundle(),
            ):
                maybe_add_web_context("latest AI research")

        assert any("search results" in m for m in caplog.messages)

    def test_logs_pages_fetched(self, caplog):
        from entelgia.web_research import maybe_add_web_context
        import logging

        with caplog.at_level(logging.INFO, logger="entelgia.web_research"):
            with patch(
                "entelgia.web_research.search_and_fetch",
                return_value=self._mock_bundle(),
            ):
                maybe_add_web_context("latest AI research")

        assert any("pages fetched" in m for m in caplog.messages)

    def test_logs_context_injected_status(self, caplog):
        from entelgia.web_research import maybe_add_web_context
        import logging

        with caplog.at_level(logging.INFO, logger="entelgia.web_research"):
            with patch(
                "entelgia.web_research.search_and_fetch",
                return_value=self._mock_bundle(),
            ):
                maybe_add_web_context("latest AI research")

        assert any("context injected" in m for m in caplog.messages)

    def test_logs_topic_when_provided(self, caplog):
        from entelgia.web_research import maybe_add_web_context
        import logging

        with caplog.at_level(logging.INFO, logger="entelgia.web_research"):
            with patch(
                "entelgia.web_research.search_and_fetch",
                return_value=self._mock_bundle(),
            ):
                maybe_add_web_context(
                    "latest AI research", topic="AI & machine learning"
                )

        assert any("AI & machine learning" in m for m in caplog.messages)

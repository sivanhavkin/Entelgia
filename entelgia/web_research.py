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
import re
import sqlite3
import time
import uuid
from typing import Any, Dict, FrozenSet, List, Optional, Set, Tuple

from entelgia.fixy_research_trigger import find_trigger, fixy_should_search
from entelgia.research_context_builder import build_research_context
from entelgia.source_evaluator import evaluate_sources
from entelgia.web_tool import search_and_fetch

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

HIGH_CREDIBILITY_THRESHOLD: float = 0.6

# Agent names that must be stripped from search queries
_AGENT_NAMES: FrozenSet[str] = frozenset({"athena", "socrates", "fixy", "observer"})

# Mode label phrases to remove (checked before word removal)
_MODE_LABELS: Tuple[str, ...] = (
    "balanced integration mode",
    "reflective mode",
    "observer mode",
)

# Stopwords for keyword compression (per spec §6)
_STOPWORDS: FrozenSet[str] = frozenset(
    {
        "the",
        "a",
        "an",
        "of",
        "and",
        "in",
        "within",
        "across",
        "that",
        "this",
        "these",
        "those",
        "how",
        "what",
        "which",
        "our",
        "your",
        "their",
        "its",
    }
)

# Directive/instruction words to strip from seed text during sanitization
_INSTRUCTION_WORDS: FrozenSet[str] = frozenset(
    {
        "question",
        "reflect",
        "build",
        "explore",
        "disagree",
        "consider",
        "examine",
    }
)

# Filler, functional, and light-semantic words removed during query rewriting.
# These extend _STOPWORDS with pronouns, common verbs, modals, conjunctions,
# prepositions, and discourse markers that carry no concept value for search.
_REWRITE_FILLER_WORDS: FrozenSet[str] = frozenset(
    {
        # Personal pronouns
        "i",
        "we",
        "you",
        "he",
        "she",
        "they",
        "it",
        "me",
        "us",
        "him",
        "her",
        "them",
        # Demonstratives / locatives
        "this",
        "that",
        "these",
        "those",
        "here",
        "there",
        # Auxiliary / modal verbs
        "is",
        "are",
        "was",
        "were",
        "be",
        "been",
        "being",
        "have",
        "has",
        "had",
        "do",
        "does",
        "did",
        "can",
        "could",
        "will",
        "would",
        "shall",
        "should",
        "may",
        "might",
        "must",
        # Light / copula verbs
        "hold",
        "holds",
        "held",
        "seem",
        "seems",
        "seemed",
        "appear",
        "appears",
        "appeared",
        "become",
        "becomes",
        "became",
        "feel",
        "feels",
        "felt",
        "keep",
        "keeps",
        "kept",
        "get",
        "gets",
        "got",
        "make",
        "makes",
        "made",
        "go",
        "goes",
        "went",
        "come",
        "comes",
        "came",
        "take",
        "takes",
        "took",
        "give",
        "gives",
        "gave",
        "see",
        "sees",
        "saw",
        "look",
        "looks",
        "looked",
        "say",
        "says",
        "said",
        "tell",
        "tells",
        "told",
        "mean",
        "means",
        "meant",
        "find",
        "finds",
        "found",
        "know",
        "knows",
        "knew",
        "think",
        "thinks",
        "thought",
        "believe",
        "believes",
        "believed",
        "suggest",
        "suggests",
        "suggested",
        "understand",
        "understands",
        "understood",
        # Conjunctions / subordinators
        "and",
        "but",
        "or",
        "nor",
        "so",
        "yet",
        "for",
        "if",
        "because",
        "since",
        "as",
        "when",
        "while",
        "although",
        "though",
        "whether",
        # Prepositions not already in _STOPWORDS
        "with",
        "at",
        "from",
        "by",
        "to",
        "into",
        "onto",
        "upon",
        "about",
        "before",
        "after",
        "during",
        "through",
        "between",
        "among",
        "under",
        "over",
        "above",
        "near",
        "around",
        "against",
        "on",
        "off",
        # Adverbs / discourse markers
        "not",
        "no",
        "just",
        "only",
        "also",
        "very",
        "quite",
        "rather",
        "often",
        "always",
        "never",
        "sometimes",
        "still",
        "even",
        "now",
        "then",
        "today",
        "already",
        "well",
        "perhaps",
        "maybe",
        "certainly",
        "indeed",
        "however",
        "therefore",
        "thus",
        "hence",
        "moreover",
        "furthermore",
        "nevertheless",
        # Interrogatives
        "where",
        "when",
        "why",
        "who",
        "whom",
        # Already in _STOPWORDS — included here so the set is self-contained
        "the",
        "a",
        "an",
        "of",
        "in",
        "within",
        "across",
        "how",
        "what",
        "which",
        "our",
        "your",
        "their",
        "its",
        # Generic nouns / adjectives that add no search value
        "place",
        "central",
        "way",
        "thing",
        "things",
        "part",
        "fact",
        "matter",
        "kind",
        "sort",
        "type",
        # Discourse / sentence-opening gerunds (prose style markers)
        "reflecting",
        "considering",
        "exploring",
        "examining",
        "thinking",
        "noting",
        "observing",
        "recognizing",
        "acknowledging",
        "believing",
        "knowing",
        "wondering",
        "questioning",
        "suggesting",
        "arguing",
        "discussing",
        "analyzing",
        "reviewing",
        "looking",
        "seeing",
        "finding",
        "getting",
        "making",
        "taking",
        "giving",
        "coming",
        "going",
        "saying",
        "telling",
        "meaning",
        "holding",
        # Common filler adjectives / participles
        "given",
        "certain",
        "clear",
        "true",
        "false",
        "various",
        "different",
        "similar",
        "important",
        "possible",
        "likely",
        "general",
        "specific",
        "genuine",
        "authentic",
        "real",
        # Verb forms that carry no concept value in search
        "shows",
        "show",
        "shown",
        "demonstrate",
        "demonstrates",
        "demonstrated",
        "indicates",
        "indicate",
        "indicated",
        "implies",
        "imply",
        "implied",
        "follows",
        "follow",
        "need",
        "needs",
        "needed",
        "want",
        "wants",
        "wanted",
        "use",
        "uses",
        "used",
        "allow",
        "allows",
        "allowed",
        "work",
        "works",
        "worked",
        "put",
        "puts",
        # Action / discourse verbs explicitly banned from search queries
        "err",
        "errs",
        "erring",
        "erred",
        "dismiss",
        "dismisses",
        "dismissed",
        "dismissing",
        "overlook",
        "overlooks",
        "overlooked",
        "overlooking",
        "try",
        "tries",
        "tried",
        "trying",
        "seek",
        "seeks",
        "sought",
        "seeking",
        "limit",
        "limits",
        "limited",
        "limiting",
        # Adverbial connectives with no concept value
        "thereby",
        # Comparatives, quantifiers, and determiners with no search value
        "more",
        "less",
        "most",
        "least",
        "many",
        "much",
        "few",
        "some",
        "any",
        "all",
        "both",
        "each",
        "every",
        "other",
        "another",
        "such",
        # Light verbs: lead / leave / bring not already covered
        "lead",
        "leads",
        "leading",
        "led",
        "leave",
        "leaves",
        "leaving",
        "left",
        "bring",
        "brings",
        "bringing",
        "brought",
    }
)

# Weak nouns that look substantive but carry little search value.
# These are removed after filler-word filtering as a final cleanup pass.
_WEAK_CONCEPT_WORDS: FrozenSet[str] = frozenset(
    {
        "form",
        "forms",
        "thing",
        "things",
        "way",
        "ways",
        "aspect",
        "aspects",
        "element",
        "elements",
        "part",
        "parts",
        "case",
        "cases",
        "instance",
        "instances",
        "area",
        "areas",
        "nature",
        "point",
        "points",
        "basis",
        "level",
        "levels",
        "sense",
        "senses",
        "role",
        "roles",
        "result",
        "results",
        "effect",
        "effects",
    }
)

# Suffixes associated with strong concept nouns (high-priority in ranking).
_CONCEPT_NOUN_SUFFIXES: Tuple[str, ...] = (
    "ity",
    "ism",
    "ness",
    "tion",
    "sion",
    "ment",
    "hood",
    "ology",
    "ence",
    "ance",
)

# Suffixes associated with verb-derived forms (low-priority in ranking).
# These are kept only when no better concept terms are available.
_VERB_LIKE_SUFFIXES: Tuple[str, ...] = ("ing", "ed")

# Maximum number of words in a compressed search query
_MAX_QUERY_WORDS: int = 6

# Minimum overlap fraction between query keywords and result content
_TOPIC_OVERLAP_THRESHOLD: float = 0.2

# Query result cache TTL in seconds (10 minutes)
_QUERY_CACHE_TTL: float = 600.0

# ---------------------------------------------------------------------------
# Module-level caches
# ---------------------------------------------------------------------------

# query → (bundle, monotonic_timestamp)
_query_cache: Dict[str, Tuple[Dict[str, Any], float]] = {}

# Topics for which web research has already been performed in this session
_topic_research_cache: Set[str] = set()

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
_TRIGGER_FRAGMENT_MAX_WORDS: int = 15


def _sanitize_text(text: str) -> str:
    """Remove agent names, mode labels, HTML entities, instruction words, and punctuation.

    Processing order:

    1. Strip multi-word mode labels (case-insensitive).
    2. Remove agent names as whole words (case-insensitive).
    3. Replace common HTML entities (``&amp;``, ``&lt;``, ``&gt;``, etc.) with a space.
    4. Remove instruction/directive words as whole words (case-insensitive).
    5. Remove possessive ``'s`` and common punctuation characters.
    6. Collapse multiple spaces into one.

    The original capitalisation of retained words is preserved so that
    the output can be used directly as a search query without further
    transformation.

    Parameters
    ----------
    text:
        Raw text fragment (typically from ``_extract_trigger_fragment``).

    Returns
    -------
    Cleaned string with agent names, mode labels, HTML entities, instruction
    words, and punctuation removed.
    """
    # 1. Remove mode labels (case-insensitive, multi-word)
    for label in _MODE_LABELS:
        text = re.sub(re.escape(label), " ", text, flags=re.IGNORECASE)
    # 2. Remove agent names (whole-word, case-insensitive)
    for name in _AGENT_NAMES:
        text = re.sub(r"\b" + re.escape(name) + r"\b", " ", text, flags=re.IGNORECASE)
    # 3. Replace common HTML entities with a space
    text = re.sub(r"&amp;", " ", text)
    text = re.sub(r"&lt;", " ", text)
    text = re.sub(r"&gt;", " ", text)
    text = re.sub(r"&quot;", " ", text)
    text = re.sub(r"&apos;", " ", text)
    text = re.sub(r"&#[0-9]+;", " ", text)
    # 4. Remove instruction words (whole-word, case-insensitive)
    for word in _INSTRUCTION_WORDS:
        text = re.sub(r"\b" + re.escape(word) + r"\b", " ", text, flags=re.IGNORECASE)
    # 5. Remove possessive 's and punctuation: . , ? ! : ; " '
    text = re.sub(r"'s\b", " ", text)
    text = re.sub(r"[.,?!:;\"']", " ", text)
    # 6. Normalize whitespace
    return " ".join(text.split())


def _compress_to_keywords(text: str) -> str:
    """Convert *text* into a compact keyword-style search query.

    Splits *text* into words, removes stopwords (case-insensitively),
    and keeps at most ``_MAX_QUERY_WORDS`` words.

    Parameters
    ----------
    text:
        Pre-sanitized text to compress.

    Returns
    -------
    A short, keyword-style string with at most ``_MAX_QUERY_WORDS`` words.
    """
    words = text.split()
    keywords = [w for w in words if w and w.lower() not in _STOPWORDS]
    return " ".join(keywords[:_MAX_QUERY_WORDS])


def _compute_topic_overlap(query: str, sources: List[Dict[str, Any]]) -> float:
    """Return the fraction of query keywords found anywhere in *sources*.

    Parameters
    ----------
    query:
        The search query string.
    sources:
        List of source dicts with ``text``, ``snippet``, and ``title`` keys.

    Returns
    -------
    A float in ``[0.0, 1.0]``.
    """
    query_words = set(query.lower().split())
    if not query_words:
        return 0.0
    combined = " ".join(
        f"{s.get('text', '')} {s.get('snippet', '')} {s.get('title', '')}".lower()
        for s in sources
    )
    matching = sum(1 for w in query_words if w in combined)
    return matching / len(query_words)


def _get_cached_bundle(query: str) -> Optional[Dict[str, Any]]:
    """Return a cached search bundle for *query*, or ``None`` if expired/absent."""
    entry = _query_cache.get(query)
    if entry is not None:
        bundle, ts = entry
        if time.monotonic() - ts < _QUERY_CACHE_TTL:
            logger.debug("_get_cached_bundle: cache hit for query %r", query)
            return bundle
        del _query_cache[query]
    return None


def _cache_bundle(query: str, bundle: Dict[str, Any]) -> None:
    """Store *bundle* in the search result cache under *query*."""
    _query_cache[query] = (bundle, time.monotonic())


def clear_research_caches() -> None:
    """Reset the search result cache and topic research cache.

    Intended for use in tests to ensure a clean state between test runs.
    """
    _query_cache.clear()
    _topic_research_cache.clear()


def _extract_trigger_fragment(text: str, trigger: str) -> str:
    """Return a sanitized, keyword-compressed query fragment starting from the trigger.

    Finds the first occurrence of *trigger* in *text*, discards everything
    before it, then passes the resulting fragment through :func:`_sanitize_text`
    and :func:`_compress_to_keywords` so the return value is ready to use
    directly as a web search query.

    Parameters
    ----------
    text:
        The full dialogue turn or seed text.
    trigger:
        The trigger keyword or phrase already identified in *text*.

    Returns
    -------
    A sanitized, keyword-compressed string derived from the portion of *text*
    that starts at *trigger*.  Falls back to a sanitized truncation of the
    full text when the trigger is not found literally.
    """
    text_lower = text.lower()
    trigger_pos = text_lower.find(trigger.lower())
    if trigger_pos == -1:
        # Trigger not found literally — unexpected since find_trigger() should
        # have confirmed its presence; log a warning and return a safe truncation.
        logger.warning(
            "_extract_trigger_fragment: trigger %r not found in text; "
            "returning truncated text",
            trigger,
        )
        fragment = " ".join(text.split()[:_TRIGGER_FRAGMENT_MAX_WORDS])
    else:
        fragment = text[trigger_pos:]
    return _compress_to_keywords(_sanitize_text(fragment))


def _score_concept_token(word: str) -> int:
    """Return a concept-quality score for a single token.

    Higher scores indicate stronger concept nouns suitable for search queries.

    Scoring tiers
    -------------
    2 — word ends with a strong concept-noun suffix (-ity, -ism, -ness, etc.)
    1 — neutral / regular nouns and adjectives
    0 — verb-derived forms ending in -ing or -ed (de-prioritised)

    Parameters
    ----------
    word:
        A single token (may be mixed-case).

    Returns
    -------
    Integer score: 2, 1, or 0.
    """
    lower = word.lower()
    for suffix in _CONCEPT_NOUN_SUFFIXES:
        # Require the word to be meaningfully longer than just the suffix
        # (e.g., reject trivial matches like "ed" → "-ed").
        if lower.endswith(suffix) and len(lower) > len(suffix) + 2:
            return 2
    for suffix in _VERB_LIKE_SUFFIXES:
        if lower.endswith(suffix) and len(lower) > len(suffix) + 2:
            return 0
    return 1


def _select_concept_terms(
    concepts: List[str],
    trigger: str,
    max_terms: int = _MAX_QUERY_WORDS,
) -> str:
    """Rank *concepts* by quality and return the best terms as a query string.

    The pipeline is:

    1. Remove ``_WEAK_CONCEPT_WORDS`` (generic nouns like *form*, *aspect*, etc.).
    2. Score each remaining token with :func:`_score_concept_token`.
    3. Select the top *max_terms* tokens by score (stable sort keeps insertion
       order for equal-scoring tokens, which preserves sentence adjacency).
    4. Restore the original sentence order of selected tokens (so adjacent
       concept pairs like "subjective experience" stay together).
    5. Append the *trigger* at the end if it adds specificity — i.e., when it
       is not already represented in the selected tokens.

    Parameters
    ----------
    concepts:
        Pre-filtered list of tokens (filler words already removed), in their
        original sentence order.
    trigger:
        The trigger keyword or phrase.
    max_terms:
        Maximum number of terms to include (default: ``_MAX_QUERY_WORDS``).

    Returns
    -------
    A compact, concept-based query string of at most *max_terms* words.
    """
    # Step 1 — remove weak concept words.
    strong = [w for w in concepts if w.lower() not in _WEAK_CONCEPT_WORDS]

    # Fall back to the full concept list if all tokens were removed.
    if not strong:
        strong = concepts

    # Step 2 — score.
    scored = [(w, _score_concept_token(w)) for w in strong]

    # Step 3 — prefer high-quality (score ≥ 1) terms; only fall back to
    # verb-derived (score = 0) tokens when there aren't enough better options.
    _MIN_CONCEPT_TERMS = 3
    high_quality = [(w, s) for w, s in scored if s >= 1]
    candidates = high_quality if len(high_quality) >= _MIN_CONCEPT_TERMS else scored

    # Take top candidates (stable sort preserves sentence order for equal scores).
    candidates_sorted = sorted(candidates, key=lambda x: x[1], reverse=True)
    top_words_set = {w for w, _ in candidates_sorted[:max_terms]}

    # Step 4 — restore original sentence order (preserves adjacency of concept pairs).
    ordered = [w for w in strong if w in top_words_set]

    # Step 5 — optionally append trigger for specificity.
    # Include trigger if none of its words are already represented in the result
    # and the trigger itself is not a pure filler term.
    trigger_lower = trigger.lower()
    trigger_tokens = trigger_lower.split()
    already_covered = any(
        t in " ".join(ordered).lower() for t in trigger_tokens
    )
    trigger_is_filler = all(
        t in _REWRITE_FILLER_WORDS or len(t) <= 2 for t in trigger_tokens
    )
    if not already_covered and not trigger_is_filler:
        # Reserve a slot for the trigger by taking one fewer concept term,
        # then append each trigger word that isn't already in the result.
        trigger_extra = [
            t for t in trigger_tokens
            if t not in " ".join(ordered).lower() and t not in _REWRITE_FILLER_WORDS
        ]
        if trigger_extra:
            slots_for_concepts = max(max_terms - len(trigger_extra), 1)
            ordered = ordered[:slots_for_concepts]
            ordered.extend(trigger_extra)

    return " ".join(ordered[:max_terms])


def rewrite_search_query(text: str, trigger: str) -> str:
    """Rewrite a trigger-containing sentence into a concept-based search query.

    Finds the sentence in *text* that contains *trigger*, then aggressively
    strips pronouns, auxiliary verbs, conjunctions, prepositions, and other
    non-concept words so only meaningful noun/concept terms remain (at most
    ``_MAX_QUERY_WORDS`` words).

    This produces search-oriented output instead of the raw prose fragment
    that results from simple keyword compression.  For example::

        "Truth holds a central place in our understanding of knowledge"
        → "truth understanding knowledge"

        "I question whether memory can distort our perception of reality"
        → "memory perception reality distort"

    Parameters
    ----------
    text:
        The full dialogue turn or seed text containing the trigger.
    trigger:
        The trigger keyword or phrase already identified in *text*.

    Returns
    -------
    A compact, concept-based query string of at most ``_MAX_QUERY_WORDS``
    meaningful terms.  When the trigger is not located in *text*, concept words
    are extracted from the full text using the same aggressive filler-word filter.
    """
    # 0. Short-circuit: if the trigger is already a specific multi-word concept
    #    phrase (≥ 3 non-filler words), return it directly as a ready-made query.
    #    Two-word phrases are kept for contextualization with nearby concepts.
    trigger_words = trigger.lower().split()
    if len(trigger_words) >= 3 and all(
        w not in _REWRITE_FILLER_WORDS and len(w) > 2 for w in trigger_words
    ):
        logger.debug(
            "rewrite_search_query: specific multi-word trigger %r returned as-is",
            trigger,
        )
        return trigger.lower()

    # 1. Find the sentence that contains the trigger.
    trigger_lower = trigger.lower()
    sentences = re.split(r"(?<=[.!?])\s+", text)
    target_sentence = None
    for sentence in sentences:
        if trigger_lower in sentence.lower():
            target_sentence = sentence
            break
    if target_sentence is None:
        # Trigger not found in any sentence — extract concept words from the
        # full text using the same aggressive filler-word filter so the result
        # is concept-based rather than a raw prose fragment.
        logger.warning(
            "rewrite_search_query: trigger %r not found in any sentence; "
            "extracting concepts from full text",
            trigger,
        )
        clean = _sanitize_text(text)
        words = clean.split()
        concepts = [
            w for w in words if w.lower() not in _REWRITE_FILLER_WORDS and len(w) > 2
        ]
        return _select_concept_terms(concepts, trigger)

    # 2. Sanitize the sentence (strips agent names, HTML entities, mode labels,
    #    instruction words, possessives, and punctuation).
    clean = _sanitize_text(target_sentence)

    # 3. Remove filler/functional words (much more aggressive than _compress_to_keywords).
    words = clean.split()
    concepts = [
        w for w in words if w.lower() not in _REWRITE_FILLER_WORDS and len(w) > 2
    ]

    # 4. Rank by concept quality, restore sentence order, and return.
    return _select_concept_terms(concepts, trigger)


def _extract_topic_line(text: str) -> str:
    """Return the content after the first ``TOPIC:`` label, or the full text.

    When *text* contains a line that begins with ``TOPIC:`` (case-insensitive),
    only the content on that line after the colon is returned.  This lets the
    seed-fallback branch focus on the topical noun phrase rather than on the
    full seed template with its instruction words and questions.

    Parameters
    ----------
    text:
        Raw seed text, potentially containing a ``TOPIC:`` header line.

    Returns
    -------
    The topic content string, or *text* unchanged when no ``TOPIC:`` line is
    found.
    """
    for line in text.splitlines():
        stripped = line.strip()
        m = re.match(r"TOPIC:\s*(.*)", stripped, re.IGNORECASE)
        if m:
            return m.group(1).strip()
    return text


def build_research_query(
    seed_text: str,
    dialog_tail: Optional[List[Dict[str, Any]]],
    fixy_reason: Optional[str],
) -> str:
    """Build the best search query from available context.

    Priority order:

    1. An explicit question detected in the last few dialogue turns.
       When a trigger keyword is identified in the question, only the
       fragment starting at the trigger is used to avoid including
       agent names or conversational filler in the query.
    2. The most informative (longest) recent agent dialogue turn,
       similarly trimmed to start at the trigger keyword when one is
       present.
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
    query: str = ""

    if dialog_tail:
        recent = dialog_tail[-4:]

        # Priority 1: explicit question in recent turns
        for turn in reversed(recent):
            text = (turn.get("text", "") if isinstance(turn, dict) else "").strip()
            if "?" in text:
                logger.debug(
                    "[branch=dialogue_question] source_type=dialogue_text text_preview=%r",
                    text[:160],
                )
                trigger = find_trigger(text)
                logger.debug("[branch=dialogue_question] detected_trigger=%r", trigger)
                if trigger:
                    # rewrite_search_query extracts concepts from the full sentence
                    query = rewrite_search_query(text, trigger)
                    logger.debug("[branch=dialogue_question] query=%r", query)
                    break

        # Priority 2: most informative (longest) turn
        if not query:
            best = max(
                recent,
                key=lambda t: len(t.get("text", "") if isinstance(t, dict) else ""),
                default=None,
            )
            if best:
                text = (best.get("text", "") if isinstance(best, dict) else "").strip()
                logger.debug(
                    "[branch=dialogue_longest] source_type=dialogue_text text_preview=%r",
                    text[:160],
                )
                trigger = find_trigger(text)
                logger.debug("[branch=dialogue_longest] detected_trigger=%r", trigger)
                if trigger:
                    # rewrite_search_query extracts concepts from the full sentence
                    query = rewrite_search_query(text, trigger)
                    logger.debug("[branch=dialogue_longest] query=%r", query)

    # Priority 3: fall back to seed_text, still applying trigger-based extraction
    if not query:
        seed = (seed_text or "").strip()
        logger.debug(
            "[branch=seed_fallback] source_type=seed_text text_preview=%r",
            seed[:160],
        )
        # Prefer the TOPIC line when the seed follows the structured seed template
        topic_seed = _extract_topic_line(seed)
        trigger = find_trigger(topic_seed)
        logger.debug("[branch=seed_fallback] detected_trigger=%r", trigger)
        if trigger:
            # rewrite_search_query extracts concepts from the full sentence
            query = rewrite_search_query(topic_seed, trigger)
        else:
            query = _compress_to_keywords(_sanitize_text(topic_seed))
        logger.debug("[branch=seed_fallback] query=%r", query)

    logger.debug("build_research_query: query=%r", query)
    return query


def maybe_add_web_context(
    seed_text: str,
    dialog_tail: Optional[List[Dict[str, Any]]] = None,
    fixy_reason: Optional[str] = None,
    db_path: Optional[str] = None,
    max_results: int = 5,
    topic: Optional[str] = None,
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
    topic:
        Optional current dialogue topic string.  When provided, topics that
        have already been researched in this session are skipped, and the
        topic is logged and stored in the topic research cache on success.

    Returns
    -------
    A formatted string ready to embed in an LLM prompt, or ``""`` when no
    search is performed or an error occurs.
    """
    try:
        if topic:
            logger.info("Topic: %s", topic)
            if topic in _topic_research_cache:
                logger.debug(
                    "maybe_add_web_context: topic %r already researched, skipping.",
                    topic,
                )
                return ""

        if not fixy_should_search(seed_text, dialog_tail, fixy_reason):
            logger.debug("maybe_add_web_context: Fixy decided no search needed.")
            return ""

        query = build_research_query(seed_text, dialog_tail, fixy_reason)
        logger.info("sanitized query: %r", query)

        # Use cached bundle when available
        bundle: Optional[Dict[str, Any]] = _get_cached_bundle(query)
        if bundle is None:
            bundle = search_and_fetch(query, max_results=max_results)
            _cache_bundle(query, bundle)

        sources: List[Dict[str, Any]] = bundle.get("sources", [])
        logger.info("search results: %d", len(sources))

        if not sources:
            logger.debug("maybe_add_web_context: no sources returned.")
            logger.info("context injected: False")
            return ""

        # Count pages that were successfully fetched (non-empty text)
        successful_pages = sum(1 for s in sources if s.get("text", "").strip())
        logger.info("pages fetched: %d", successful_pages)

        # Quality gate: require at least one fetched page and sufficient
        # overlap between query keywords and result content
        topic_overlap = _compute_topic_overlap(query, sources)
        if successful_pages < 1 or topic_overlap < _TOPIC_OVERLAP_THRESHOLD:
            logger.info(
                "maybe_add_web_context: quality gate failed "
                "(successful_pages=%d, topic_overlap=%.2f); skipping injection.",
                successful_pages,
                topic_overlap,
            )
            logger.info("context injected: False")
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

        if topic and context:
            _topic_research_cache.add(topic)

        logger.info("context injected: %s", bool(context))
        return context

    except Exception as exc:  # noqa: BLE001
        logger.warning("maybe_add_web_context: unexpected error: %s", exc)
        return ""

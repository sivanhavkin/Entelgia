#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Entelgia Web Research Demo
===========================

Demonstrates the full Web Research pipeline integrated into the Entelgia
cognitive architecture:

  1. User asks a question that needs current information
  2. Fixy (meta-observer) detects the need for external knowledge
  3. Web Research Module fetches and evaluates sources
  4. Credibility scores are computed and sources are ranked
  5. Context is injected into the internal agent dialogue
  6. High-credibility sources are optionally stored in long-term memory

This script uses mocked agent dialogue so it runs without a live Ollama
instance.  Replace the ``_mock_agent_speak`` calls with real agent.speak()
calls to run the full system.

Usage
-----
    python entelgia_research_demo.py [query]

Examples
--------
    python entelgia_research_demo.py "latest research on quantum computing"
    python entelgia_research_demo.py "current news on AI regulation"
"""

from __future__ import annotations

import sys
import tempfile
import textwrap

# ---------------------------------------------------------------------------
# Entelgia web research imports
# ---------------------------------------------------------------------------
from entelgia.fixy_research_trigger import fixy_should_search
from entelgia.research_context_builder import build_research_context
from entelgia.source_evaluator import evaluate_sources
from entelgia.web_research import maybe_add_web_context

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _separator(char: str = "─", width: int = 70) -> None:
    print(char * width)


def _header(title: str) -> None:
    _separator()
    print(f"  {title}")
    _separator()


def _mock_agent_speak(agent_name: str, web_context: str, topic: str) -> str:
    """Produce a deterministic mock response for demo purposes."""
    agent_lines = {
        "Id": (
            f"I feel a strong pull toward this topic — '{topic}' stirs my curiosity. "
            "The sources are interesting but I want to explore more freely!"
        ),
        "Ego": (
            f"Looking at the external sources about '{topic}', I integrate the credible "
            "information with our existing understanding. We should weigh evidence carefully."
        ),
        "Superego": (
            f"I must verify the credibility of these web sources before accepting them. "
            f"The topic '{topic}' deserves rigorous scrutiny. Only high-credibility sources "
            "should influence our conclusions."
        ),
        "Fixy": (
            "I have detected a need for external knowledge and triggered a web search. "
            "Sources have been evaluated and ranked by credibility. "
            "Reasoning loop is healthy — no circular patterns detected."
        ),
    }
    base = agent_lines.get(agent_name, f"[{agent_name}]: Reflecting on the research...")
    if web_context:
        note = " (I have access to external research context.)"
    else:
        note = ""
    return base + note


# ---------------------------------------------------------------------------
# Main demo
# ---------------------------------------------------------------------------


def run_demo(user_query: str) -> None:
    """Run the full Entelgia web research demo for *user_query*."""

    print()
    _header("Entelgia Web Research Demo")
    print()
    print(f"  User query: {user_query!r}")
    print()

    # ── Step 1: Fixy decides whether to search ────────────────────────────
    _header("Step 1 — Fixy: should I search the web?")
    should_search = fixy_should_search(user_query)
    print(f"  fixy_should_search({user_query!r}) → {should_search}")
    print()

    if not should_search:
        print("  Fixy decided no external search is needed.")
        print("  Proceeding with internal agent dialogue only.")
        print()
        web_context = ""
    else:
        print("  Fixy triggered web research pipeline.")
        print()

        # ── Step 2: Retrieve web sources ─────────────────────────────────
        _header("Step 2 — Web Research Module: fetching sources")
        print("  (Using real DuckDuckGo HTML search + BeautifulSoup page extraction)")
        print()

        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
            db_path = tmp.name

        web_context = maybe_add_web_context(
            seed_text=query,
            dialog_tail=None,
            fixy_reason=None,
            db_path=db_path,
            max_results=5,
        )

        if web_context:
            # ── Step 3: Show ranked sources ──────────────────────────────
            _header("Step 3 — Source Evaluation & Ranking")
            print(web_context)
            print()
        else:
            print("  No sources could be retrieved (network may be unavailable).")
            print("  Continuing demo with empty web context.")
            print()

    # ── Step 4: Internal agent dialogue ───────────────────────────────────
    _header("Step 4 — Internal Agent Dialogue")
    print("  Injecting external knowledge context into agent prompts...")
    print()

    agents = ["Fixy", "Ego", "Superego", "Id"]
    dialog: list[dict[str, str]] = []

    for agent_name in agents:
        response = _mock_agent_speak(agent_name, web_context, user_query)
        dialog.append({"role": agent_name, "text": response})

        colour_codes = {
            "Fixy": "\033[33m",  # yellow
            "Ego": "\033[36m",  # cyan
            "Superego": "\033[35m",  # magenta
            "Id": "\033[31m",  # red
        }
        reset = "\033[0m"
        colour = colour_codes.get(agent_name, "")
        print(f"  {colour}{agent_name}:{reset}")
        wrapped = textwrap.fill(
            response, width=65, initial_indent="    ", subsequent_indent="    "
        )
        print(wrapped)
        print()

    # ── Step 5: Final synthesised answer ──────────────────────────────────
    _header("Step 5 — Final Answer (synthesised by Ego)")
    final = (
        f"Based on our internal dialogue and the external research "
        f"about '{user_query}', Entelgia synthesises the following:\n\n"
        "  The available sources have been credibility-ranked by Superego. "
        "Ego integrates the most reliable findings, while Id ensures the "
        "response remains engaged and curious. Fixy confirms there are no "
        "circular reasoning patterns in this session."
    )
    print(textwrap.fill(final, width=68, initial_indent="  ", subsequent_indent="  "))
    print()
    _separator("═")
    print("  Demo complete.")
    _separator("═")
    print()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    query = (
        " ".join(sys.argv[1:])
        if len(sys.argv) > 1
        else "latest research on artificial intelligence"
    )
    run_demo(query)

#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Test script for enhanced dialogue features
Tests dynamic speaker selection, seed variety, context enrichment, and Fixy interventions.
"""

import sys
import os

# Add parent directory to path so we can import from entelgia package
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from entelgia import (
    DialogueEngine,
    ContextManager,
    InteractiveFixy,
    get_persona,
    format_persona_for_prompt,
)

# ---------------------------------------------------------------------------
# Terminal display helpers – tables and ASCII bar charts
# ---------------------------------------------------------------------------


def _print_table(headers, rows, title=None):
    """Print a neatly formatted ASCII table to stdout."""
    if title:
        print(f"\n  ╔{'═' * (len(title) + 4)}╗")
        print(f"  ║  {title}  ║")
        print(f"  ╚{'═' * (len(title) + 4)}╝")
    col_widths = [len(str(h)) for h in headers]
    for row in rows:
        for i, cell in enumerate(row):
            col_widths[i] = max(col_widths[i], len(str(cell)))
    sep = "─┼─".join("─" * w for w in col_widths)
    header_line = " │ ".join(str(h).ljust(col_widths[i]) for i, h in enumerate(headers))
    print(f"  {header_line}")
    print(f"  {sep}")
    for row in rows:
        print(
            "  "
            + " │ ".join(str(cell).ljust(col_widths[i]) for i, cell in enumerate(row))
        )
    print()


def _print_bar_chart(data_pairs, title=None, max_width=36):
    """Print a horizontal ASCII bar chart.  *data_pairs* is [(label, value), ...]."""
    if title:
        print(f"\n  📊 {title}")
        print(f"  {'─' * 52}")
    if not data_pairs:
        return
    max_val = max(v for _, v in data_pairs) or 1.0
    for label, value in data_pairs:
        bar_len = max(1, int(round((value / max_val) * max_width)))
        bar = "█" * bar_len
        print(f"  {str(label):>10} │ {bar:<{max_width}} {value:.4f}")
    print()


def test_dynamic_speaker_selection():
    """Test that speakers are selected dynamically."""

    engine = DialogueEngine()

    # Create mock agents
    class MockAgent:
        def __init__(self, name):
            self.name = name

        def conflict_index(self):
            return 5.0

    socrates = MockAgent("Socrates")
    athena = MockAgent("Athena")
    fixy = MockAgent("Fixy")

    # Simulate 20 turns
    dialog = []
    speakers = []

    for i in range(20):
        if i == 0:
            speaker = socrates
        else:
            agents = [socrates, athena]
            speaker = engine.select_next_speaker(
                current_speaker=speakers[-1] if speakers else socrates,
                dialog_history=dialog,
                agents=agents,
                allow_fixy=False,
                fixy_probability=0.0,
            )

        speakers.append(speaker)
        dialog.append({"role": speaker.name, "text": f"Turn {i+1}"})

    # Check no 3+ consecutive turns
    consecutive = 1
    max_consecutive = 1
    for i in range(1, len(speakers)):
        if speakers[i].name == speakers[i - 1].name:
            consecutive += 1
            max_consecutive = max(max_consecutive, consecutive)
        else:
            consecutive = 1

    socrates_count = sum(1 for s in speakers if s.name == "Socrates")
    athena_count = sum(1 for s in speakers if s.name == "Athena")
    _print_table(
        ["check_name", "result", "pass?"],
        [
            [
                "Max consecutive turns",
                str(max_consecutive),
                "✓" if max_consecutive < 3 else "✗",
            ]
        ],
        title="test_dynamic_speaker_selection",
    )
    _print_bar_chart(
        [("Socrates", float(socrates_count)), ("Athena", float(athena_count))],
        title="Speaker distribution (20 turns)",
    )
    assert (
        max_consecutive < 3
    ), f"Expected no agent to speak 3+ consecutive turns, got max_consecutive={max_consecutive}"


def test_seed_variety():
    """Test that seeds vary across different strategies."""

    engine = DialogueEngine()

    class MockAgent:
        def __init__(self, name):
            self.name = name

        def conflict_index(self):
            return 5.0

    socrates = MockAgent("Socrates")

    # Generate seeds for different turn counts
    seeds = []
    for turn in range(1, 21):
        dialog = [{"role": "Socrates", "text": "test", "emotion": "neutral"}] * min(
            turn, 5
        )
        seed = engine.generate_seed(
            topic="Philosophy of Mind",
            dialog_history=dialog,
            speaker=socrates,
            turn_count=turn,
        )
        seeds.append(seed)

    # Extract strategies from seeds
    strategies_found = set()
    for seed in seeds:
        if "BUILD" in seed:
            strategies_found.add("agree_and_expand")
        elif "QUESTION" in seed:
            strategies_found.add("question_assumption")
        elif "INTEGRATE" in seed:
            strategies_found.add("synthesize")
        elif "DISAGREE" in seed:
            strategies_found.add("constructive_disagree")
        elif "EXPLORE" in seed:
            strategies_found.add("explore_implication")
        elif "CONNECT" in seed:
            strategies_found.add("introduce_analogy")
        elif "REFLECT" in seed:
            strategies_found.add("meta_reflect")

    all_strategies = [
        "agree_and_expand",
        "question_assumption",
        "synthesize",
        "constructive_disagree",
        "explore_implication",
        "introduce_analogy",
        "meta_reflect",
    ]
    _print_table(
        ["strategy", "found?"],
        [[s, "✓" if s in strategies_found else "✗"] for s in all_strategies],
        title="test_seed_variety",
    )
    _print_bar_chart(
        [("found", float(len(strategies_found))), ("threshold", 4.0)],
        title="Strategies found vs threshold",
    )
    assert (
        len(strategies_found) >= 4
    ), f"Expected at least 4 distinct strategies, found {len(strategies_found)}: {strategies_found}"


def test_context_enrichment():
    """Test that context includes enhanced elements."""

    mgr = ContextManager()

    # Create mock data
    drives = {
        "id_strength": 6.0,
        "ego_strength": 5.5,
        "superego_strength": 5.0,
        "self_awareness": 0.6,
    }
    debate_profile = {"style": "integrative, Socratic", "dissent_level": 4.5}

    dialog_tail = [
        {"role": "Socrates", "text": f"This is turn {i}. " * 50} for i in range(10)
    ]

    stm = [{"text": f"Thought {i}. " * 20, "emotion": "curious"} for i in range(10)]

    ltm = [
        {"content": f"Memory {i}. " * 30, "importance": 0.5 + i * 0.05}
        for i in range(10)
    ]

    # Test 1: Default (no pronoun)
    prompt_no_pronoun = mgr.build_enriched_context(
        agent_name="Socrates",
        agent_lang="he",
        persona="Test persona",
        drives=drives,
        user_seed="TOPIC: Test\nQUESTION assumptions",
        dialog_tail=dialog_tail,
        stm=stm,
        ltm=ltm,
        debate_profile=debate_profile,
        show_pronoun=False,
    )

    # Test 2: With pronoun
    prompt_with_pronoun = mgr.build_enriched_context(
        agent_name="Socrates",
        agent_lang="he",
        persona="Test persona",
        drives=drives,
        user_seed="TOPIC: Test\nQUESTION assumptions",
        dialog_tail=dialog_tail,
        stm=stm,
        ltm=ltm,
        debate_profile=debate_profile,
        show_pronoun=True,
        agent_pronoun="he",
    )

    # Check for key elements
    checks = {
        "Full speaker names": "Socrates:" in prompt_no_pronoun,
        "8 dialogue turns": prompt_no_pronoun.count("This is turn") >= 8,
        "6 recent thoughts": prompt_no_pronoun.count("Thought") >= 6,
        "5 memories": prompt_no_pronoun.count("Memory") >= 5,
        "Drive information": "id=" in prompt_no_pronoun and "ego=" in prompt_no_pronoun,
        "Smart truncation": "..."
        in prompt_no_pronoun,  # Should have truncation markers
        "No gender pronouns (default)": "(he)" not in prompt_no_pronoun
        and "(she)" not in prompt_no_pronoun,
        "Gender pronoun shown when enabled": "Socrates (he):" in prompt_with_pronoun,
        "150-word limit instruction": "150 words" in prompt_no_pronoun
        and "150 words" in prompt_with_pronoun,
    }

    _print_table(
        ["check_name", "pass?"],
        [[name, "✓" if ok else "✗"] for name, ok in checks.items()],
        title="test_context_enrichment",
    )
    failed_checks = [name for name, ok in checks.items() if not ok]
    assert not failed_checks, f"Failed context enrichment checks: {failed_checks}"


def test_fixy_interventions():
    """Test that Fixy intervenes based on need, not schedule."""

    class MockLLM:
        def generate(self, model, prompt, temperature=0.7, use_cache=True):
            return "I notice we're circling. Let's try a different approach."

    fixy = InteractiveFixy(MockLLM(), "phi3:latest")

    # Test 1: Early turns - should not intervene
    dialog_early = [{"role": "Socrates", "text": "Hello"}]
    should1, reason1 = fixy.should_intervene(dialog_early, turn_count=2)
    early_pass = not should1

    # Test 2: Repetitive dialogue - should intervene
    dialog_repetitive = [
        {"role": "Socrates", "text": "Freedom means liberty autonomy independence"},
        {"role": "Athena", "text": "Liberty and freedom are autonomy related"},
        {"role": "Socrates", "text": "Independence connects to freedom and liberty"},
        {"role": "Athena", "text": "Autonomy is similar to freedom and liberty"},
        {"role": "Socrates", "text": "Freedom liberty autonomy are interconnected"},
    ]
    should2, reason2 = fixy.should_intervene(dialog_repetitive, turn_count=5)
    repetitive_pass = should2 and reason2 == "circular_reasoning"

    # Test 3: Normal dialogue - should not intervene
    dialog_normal = [
        {"role": "Socrates", "text": "What is knowledge?"},
        {"role": "Athena", "text": "Knowledge combines understanding and experience."},
        {"role": "Socrates", "text": "But can we truly know anything?"},
        {"role": "Athena", "text": "Perhaps certainty exists on a spectrum."},
    ]
    should3, reason3 = fixy.should_intervene(dialog_normal, turn_count=4)
    normal_pass = not should3

    _print_table(
        ["scenario", "should_intervene", "reason", "expected", "pass?"],
        [
            [
                "early (turn 2)",
                str(should1),
                str(reason1),
                "False",
                "✓" if early_pass else "✗",
            ],
            [
                "repetitive (turn 5)",
                str(should2),
                str(reason2),
                "True/circular_reasoning",
                "✓" if repetitive_pass else "✗",
            ],
            [
                "normal (turn 4)",
                str(should3),
                str(reason3),
                "False",
                "✓" if normal_pass else "✗",
            ],
        ],
        title="test_fixy_interventions",
    )

    assert (
        early_pass
    ), f"Early turns (turn 2): Fixy should NOT intervene, got should_intervene={should1}, reason={reason1}"
    assert repetitive_pass, (
        f"Repetitive dialogue (turn 5): Fixy SHOULD intervene with reason='circular_reasoning', "
        f"got should_intervene={should2}, reason={reason2}"
    )
    assert (
        normal_pass
    ), f"Normal dialogue (turn 4): Fixy should NOT intervene, got should_intervene={should3}, reason={reason3}"


def test_persona_formatting():
    """Test that personas are rich and distinctive."""

    socrates = get_persona("Socrates")
    athena = get_persona("Athena")
    fixy = get_persona("Fixy")

    # Check that personas have rich content
    checks = {
        "Socrates has core traits": len(socrates.get("core_traits", [])) >= 3,
        "Athena has speech patterns": len(athena.get("speech_patterns", [])) >= 3,
        "Fixy has intervention triggers": len(fixy.get("intervention_triggers", []))
        >= 3,
        "Personas are distinctive": (
            socrates.get("thinking_style") != athena.get("thinking_style")
        ),
    }

    # Test formatting with drives
    drives = {"id_strength": 7.0, "ego_strength": 5.0, "superego_strength": 4.0}
    formatted = format_persona_for_prompt(socrates, drives)
    _print_table(
        ["check_name", "pass?"],
        [[name, "✓" if ok else "✗"] for name, ok in checks.items()]
        + [["formatted_len > 100", "✓" if len(formatted) > 100 else "✗"]],
        title="test_persona_formatting",
    )
    print(f"\n  Formatted Socrates persona (snippet):\n  {formatted[:200]}...")
    failed_checks = [name for name, ok in checks.items() if not ok]
    assert not failed_checks, f"Failed persona formatting checks: {failed_checks}"
    assert (
        len(formatted) > 100
    ), f"Expected formatted persona length > 100, got {len(formatted)}"


def test_persona_pronouns():
    """Test that persona data includes correct pronouns."""

    from entelgia import SOCRATES_PERSONA, ATHENA_PERSONA, FIXY_PERSONA

    checks = {
        "Socrates has 'he' pronoun": SOCRATES_PERSONA.get("pronoun") == "he",
        "Athena has 'she' pronoun": ATHENA_PERSONA.get("pronoun") == "she",
        "Fixy has 'he' pronoun": FIXY_PERSONA.get("pronoun") == "he",
    }

    _print_table(
        ["agent", "pronoun", "expected", "match?"],
        [
            [
                "Socrates",
                str(SOCRATES_PERSONA.get("pronoun")),
                "he",
                "✓" if SOCRATES_PERSONA.get("pronoun") == "he" else "✗",
            ],
            [
                "Athena",
                str(ATHENA_PERSONA.get("pronoun")),
                "she",
                "✓" if ATHENA_PERSONA.get("pronoun") == "she" else "✗",
            ],
            [
                "Fixy",
                str(FIXY_PERSONA.get("pronoun")),
                "he",
                "✓" if FIXY_PERSONA.get("pronoun") == "he" else "✗",
            ],
        ],
        title="test_persona_pronouns",
    )
    failed_checks = [name for name, ok in checks.items() if not ok]
    assert not failed_checks, f"Failed pronoun checks: {failed_checks}"


if __name__ == "__main__":
    import pytest

    pytest.main([__file__, "-v", "-s"])

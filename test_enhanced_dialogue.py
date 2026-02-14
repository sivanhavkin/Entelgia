#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Test script for enhanced dialogue features
Tests dynamic speaker selection, seed variety, context enrichment, and Fixy interventions.
"""

import sys

sys.path.insert(0, ".")

from entelgia import (
    DialogueEngine,
    ContextManager,
    InteractiveFixy,
    get_persona,
    format_persona_for_prompt,
)


def test_dynamic_speaker_selection():
    """Test that speakers are selected dynamically."""
    print("\n=== Test 1: Dynamic Speaker Selection ===")

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

    print(f"Speaker sequence: {[s.name[:3] for s in speakers]}")
    print(f"Max consecutive turns: {max_consecutive}")

    if max_consecutive >= 3:
        print("✗ FAIL: Same speaker spoke 3+ times in a row")
        return False
    else:
        print("✓ PASS: No speaker spoke 3+ times consecutively")
        return True


def test_seed_variety():
    """Test that seeds vary across different strategies."""
    print("\n=== Test 2: Seed Variety ===")

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

    print(f"Strategies found: {strategies_found}")
    print(f"Number of unique strategies: {len(strategies_found)}")

    if len(strategies_found) >= 4:
        print(f"✓ PASS: Found {len(strategies_found)} different seed strategies")
        return True
    else:
        print(f"✗ FAIL: Only {len(strategies_found)} strategies found (expected 4+)")
        return False


def test_context_enrichment():
    """Test that context includes enhanced elements."""
    print("\n=== Test 3: Context Enrichment ===")

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

    print("Context checks:")
    for check, passed in checks.items():
        status = "✓" if passed else "✗"
        print(f"  {status} {check}")

    all_passed = all(checks.values())
    if all_passed:
        print("✓ PASS: All context enrichment checks passed")
    else:
        print("✗ FAIL: Some context enrichment checks failed")

    return all_passed


def test_fixy_interventions():
    """Test that Fixy intervenes based on need, not schedule."""
    print("\n=== Test 4: Fixy Interventions ===")

    class MockLLM:
        def generate(self, model, prompt, temperature=0.7, use_cache=True):
            return "I notice we're circling. Let's try a different approach."

    fixy = InteractiveFixy(MockLLM(), "phi3:latest")

    # Test 1: Early turns - should not intervene
    dialog_early = [{"role": "Socrates", "text": "Hello"}]
    should, reason = fixy.should_intervene(dialog_early, turn_count=2)

    print(f"Early turns (turn 2): should_intervene={should}")
    if not should:
        print("  ✓ Correctly does not intervene early")
        early_pass = True
    else:
        print("  ✗ Incorrectly wants to intervene early")
        early_pass = False

    # Test 2: Repetitive dialogue - should intervene
    dialog_repetitive = [
        {"role": "Socrates", "text": "Freedom means liberty autonomy independence"},
        {"role": "Athena", "text": "Liberty and freedom are autonomy related"},
        {"role": "Socrates", "text": "Independence connects to freedom and liberty"},
        {"role": "Athena", "text": "Autonomy is similar to freedom and liberty"},
        {"role": "Socrates", "text": "Freedom liberty autonomy are interconnected"},
    ]
    should, reason = fixy.should_intervene(dialog_repetitive, turn_count=5)

    print(f"Repetitive dialogue (turn 5): should_intervene={should}, reason={reason}")
    if should and reason == "circular_reasoning":
        print("  ✓ Correctly detects circular reasoning")
        repetitive_pass = True
    else:
        print(
            f"  ✗ Failed to detect circular reasoning (should={should}, reason={reason})"
        )
        repetitive_pass = False

    # Test 3: Normal dialogue - should not intervene
    dialog_normal = [
        {"role": "Socrates", "text": "What is knowledge?"},
        {"role": "Athena", "text": "Knowledge combines understanding and experience."},
        {"role": "Socrates", "text": "But can we truly know anything?"},
        {"role": "Athena", "text": "Perhaps certainty exists on a spectrum."},
    ]
    should, reason = fixy.should_intervene(dialog_normal, turn_count=4)

    print(f"Normal dialogue (turn 4): should_intervene={should}")
    if not should:
        print("  ✓ Correctly does not intervene in normal dialogue")
        normal_pass = True
    else:
        print(f"  ✗ Incorrectly wants to intervene (reason={reason})")
        normal_pass = False

    all_passed = early_pass and repetitive_pass and normal_pass
    if all_passed:
        print("✓ PASS: Fixy intervention logic works correctly")
    else:
        print("✗ FAIL: Some Fixy intervention checks failed")

    return all_passed


def test_persona_formatting():
    """Test that personas are rich and distinctive."""
    print("\n=== Test 5: Persona Formatting ===")

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

    print("Persona checks:")
    for check, passed in checks.items():
        status = "✓" if passed else "✗"
        print(f"  {status} {check}")

    # Test formatting with drives
    drives = {"id_strength": 7.0, "ego_strength": 5.0, "superego_strength": 4.0}
    formatted = format_persona_for_prompt(socrates, drives)

    print(f"\nFormatted Socrates persona (snippet):\n{formatted[:200]}...")

    all_passed = all(checks.values()) and len(formatted) > 100
    if all_passed:
        print("\n✓ PASS: Personas are rich and well-formatted")
    else:
        print("\n✗ FAIL: Some persona checks failed")

    return all_passed


def test_persona_pronouns():
    """Test that persona data includes correct pronouns."""
    print("\n=== Test 6: Persona Pronouns ===")

    from entelgia import SOCRATES_PERSONA, ATHENA_PERSONA, FIXY_PERSONA

    checks = {
        "Socrates has 'he' pronoun": SOCRATES_PERSONA.get("pronoun") == "he",
        "Athena has 'she' pronoun": ATHENA_PERSONA.get("pronoun") == "she",
        "Fixy has 'he' pronoun": FIXY_PERSONA.get("pronoun") == "he",
    }

    print("Pronoun checks:")
    for check, passed in checks.items():
        status = "✓" if passed else "✗"
        print(f"  {status} {check}")

    all_passed = all(checks.values())
    if all_passed:
        print("✓ PASS: All pronoun checks passed")
    else:
        print("✗ FAIL: Some pronoun checks failed")

    return all_passed


def main():
    """Run all tests."""
    print("=" * 70)
    print("ENHANCED DIALOGUE FEATURES TEST SUITE")
    print("=" * 70)

    tests = [
        test_dynamic_speaker_selection,
        test_seed_variety,
        test_context_enrichment,
        test_fixy_interventions,
        test_persona_formatting,
        test_persona_pronouns,
    ]

    results = []
    for test in tests:
        try:
            result = test()
            results.append(result)
        except Exception as e:
            print(f"\n✗ TEST FAILED WITH EXCEPTION: {e}")
            import traceback

            traceback.print_exc()
            results.append(False)

    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    passed = sum(results)
    total = len(results)
    print(f"Tests passed: {passed}/{total}")

    if all(results):
        print("\n✓ ALL TESTS PASSED!")
        return 0
    else:
        print("\n✗ SOME TESTS FAILED")
        return 1


if __name__ == "__main__":
    sys.exit(main())

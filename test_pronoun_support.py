#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Test script for pronoun support feature
Validates that show_pronouns configuration works correctly.
"""

import sys

sys.path.insert(0, ".")

from Entelgia_production_meta import (
    Config,
    get_display_name,
    Agent,
    LLM,
    MemoryCore,
    EmotionCore,
    BehaviorCore,
    LanguageCore,
    ConsciousCore
)
import Entelgia_production_meta


def test_get_display_name_function():
    """Test the get_display_name helper function."""
    print("\n=== Test 1: get_display_name() Helper Function ===")
    
    # Test without CFG (should return name only)
    Entelgia_production_meta.CFG = None
    result = get_display_name("Socrates", "he")
    assert result == "Socrates", f"Expected 'Socrates', got '{result}'"
    print("✓ Without CFG: Returns name only")
    
    # Test with show_pronouns=False
    cfg_disabled = Config(show_pronouns=False)
    Entelgia_production_meta.CFG = cfg_disabled
    result = get_display_name("Socrates", "he")
    assert result == "Socrates", f"Expected 'Socrates', got '{result}'"
    print("✓ With show_pronouns=False: Returns name only")
    
    # Test with show_pronouns=True
    cfg_enabled = Config(show_pronouns=True)
    Entelgia_production_meta.CFG = cfg_enabled
    result = get_display_name("Socrates", "he")
    assert result == "Socrates (he)", f"Expected 'Socrates (he)', got '{result}'"
    print("✓ With show_pronouns=True: Returns name with pronoun")
    
    # Test with None pronoun
    result = get_display_name("Socrates", None)
    assert result == "Socrates", f"Expected 'Socrates', got '{result}'"
    print("✓ With None pronoun: Returns name only")
    
    # Test all characters
    result_athena = get_display_name("Athena", "she")
    assert result_athena == "Athena (she)", f"Expected 'Athena (she)', got '{result_athena}'"
    print("✓ Athena displays correctly: 'Athena (she)'")
    
    result_fixy = get_display_name("Fixy", "he")
    assert result_fixy == "Fixy (he)", f"Expected 'Fixy (he)', got '{result_fixy}'"
    print("✓ Fixy displays correctly: 'Fixy (he)'")
    
    return True


def test_agent_display_name():
    """Test that Agent display name property and method work correctly."""
    print("\n=== Test 2: Agent Display Name (Property & Method) ===")
    
    # Initialize minimal agent
    cfg = Config(show_pronouns=False)
    Entelgia_production_meta.CFG = cfg
    
    memory = MemoryCore(":memory:")  # In-memory SQLite for testing
    llm = LLM(cfg, None)
    emotion = EmotionCore(llm)
    behavior = BehaviorCore(llm)
    language = LanguageCore()
    conscious = ConsciousCore()
    
    # Create agent with pronoun
    agent_socrates = Agent(
        name="Socrates",
        model="phi3:latest",
        color="",
        llm=llm,
        memory=memory,
        emotion=emotion,
        behavior=behavior,
        language=language,
        conscious=conscious,
        persona="Test",
        use_enhanced=False,
        pronoun="he"
    )
    
    # Test property with show_pronouns=False
    result = agent_socrates.display_name
    assert result == "Socrates", f"Expected 'Socrates', got '{result}'"
    print("✓ Agent property with show_pronouns=False: Returns name only")
    
    # Test deprecated method with show_pronouns=False
    result = agent_socrates.get_display_name()
    assert result == "Socrates", f"Expected 'Socrates', got '{result}'"
    print("✓ Agent method (deprecated) with show_pronouns=False: Returns name only")
    
    # Test property with show_pronouns=True
    cfg_enabled = Config(show_pronouns=True)
    Entelgia_production_meta.CFG = cfg_enabled
    result = agent_socrates.display_name
    assert result == "Socrates (he)", f"Expected 'Socrates (he)', got '{result}'"
    print("✓ Agent property with show_pronouns=True: Returns name with pronoun")
    
    # Test deprecated method with show_pronouns=True
    result = agent_socrates.get_display_name()
    assert result == "Socrates (he)", f"Expected 'Socrates (he)', got '{result}'"
    print("✓ Agent method (deprecated) with show_pronouns=True: Returns name with pronoun")
    
    # Create agent without pronoun
    agent_no_pronoun = Agent(
        name="Test",
        model="phi3:latest",
        color="",
        llm=llm,
        memory=memory,
        emotion=emotion,
        behavior=behavior,
        language=language,
        conscious=conscious,
        persona="Test",
        use_enhanced=False,
        pronoun=None
    )
    
    result = agent_no_pronoun.display_name
    assert result == "Test", f"Expected 'Test', got '{result}'"
    print("✓ Agent property without pronoun: Returns name only")
    
    return True


def test_backward_compatibility():
    """Test backward compatibility - default behavior unchanged."""
    print("\n=== Test 3: Backward Compatibility ===")
    
    # Default config should have show_pronouns=False
    cfg = Config()
    assert cfg.show_pronouns is False, "Default show_pronouns should be False"
    print("✓ Default Config has show_pronouns=False")
    
    Entelgia_production_meta.CFG = cfg
    
    # Test that default behavior matches old behavior (no pronouns)
    result = get_display_name("Socrates", "he")
    assert result == "Socrates", f"Expected 'Socrates', got '{result}'"
    print("✓ Default behavior: No pronouns shown (backward compatible)")
    
    return True


def test_prompt_length_instruction():
    """Test that length instruction is present in prompts."""
    print("\n=== Test 4: LLM Prompt Length Instruction ===")
    
    cfg = Config(show_pronouns=False)
    Entelgia_production_meta.CFG = cfg
    
    memory = MemoryCore(":memory:")
    llm = LLM(cfg, None)
    emotion = EmotionCore(llm)
    behavior = BehaviorCore(llm)
    language = LanguageCore()
    conscious = ConsciousCore()
    
    agent = Agent(
        name="Socrates",
        model="phi3:latest",
        color="",
        llm=llm,
        memory=memory,
        emotion=emotion,
        behavior=behavior,
        language=language,
        conscious=conscious,
        persona="Test persona",
        use_enhanced=False,
        pronoun="he"
    )
    
    # Build a test prompt
    dialog_tail = [
        {"role": "Socrates", "text": "First message"},
        {"role": "Athena", "text": "Second message"}
    ]
    prompt = agent._build_compact_prompt("Test topic", dialog_tail)
    
    # Check for length instruction
    length_instruction = "Please answer in no more than 150 words. End your response at the nearest sentence."
    assert length_instruction in prompt, f"Length instruction not found in prompt"
    print("✓ Legacy prompt contains length instruction")
    print(f"  Instruction: '{length_instruction}'")
    
    return True


def main():
    """Run all tests."""
    print("=" * 70)
    print("PRONOUN SUPPORT TEST SUITE")
    print("=" * 70)
    
    tests = [
        test_get_display_name_function,
        test_agent_display_name,
        test_backward_compatibility,
        test_prompt_length_instruction,
    ]
    
    passed = 0
    failed = 0
    
    for test in tests:
        try:
            if test():
                passed += 1
        except Exception as e:
            print(f"✗ FAIL: {e}")
            failed += 1
            import traceback
            traceback.print_exc()
    
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(f"Tests passed: {passed}/{len(tests)}")
    
    if failed == 0:
        print("\n✓ ALL TESTS PASSED!")
        return 0
    else:
        print(f"\n✗ {failed} TEST(S) FAILED")
        return 1


if __name__ == "__main__":
    sys.exit(main())

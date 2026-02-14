#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Demo script showing pronoun support feature
Demonstrates both disabled (default) and enabled pronoun display modes.
"""

import sys
sys.path.insert(0, ".")

from Entelgia_production_meta import Config, get_display_name
import Entelgia_production_meta
from colorama import Fore, Style, init as colorama_init

def demo_pronoun_support():
    """Demonstrate pronoun support feature."""
    colorama_init(autoreset=True)
    
    print("=" * 70)
    print("PRONOUN SUPPORT FEATURE DEMONSTRATION")
    print("=" * 70)
    
    # Demo 1: Default behavior (show_pronouns=False)
    print("\n" + Fore.CYAN + "=== Mode 1: Gender-Neutral (default) ===" + Style.RESET_ALL)
    print("Config: show_pronouns=False (backward compatible)")
    print()
    
    cfg_disabled = Config(show_pronouns=False)
    Entelgia_production_meta.CFG = cfg_disabled
    
    print(Fore.CYAN + get_display_name("Socrates", "he") + Style.RESET_ALL + ": Why do we believe what we believe?")
    print(Fore.MAGENTA + get_display_name("Athena", "she") + Style.RESET_ALL + ": Let me synthesize multiple perspectives on this question.")
    print(Fore.YELLOW + get_display_name("Fixy", "he") + Style.RESET_ALL + ": I notice the dialogue is getting circular.")
    
    print("\n" + Fore.GREEN + "✓ Clean, inclusive display without gender markers" + Style.RESET_ALL)
    print("  Perfect for gender-neutral conversations and diverse audiences")
    
    # Demo 2: Pronouns enabled
    print("\n" + Fore.CYAN + "=== Mode 2: With Pronouns ===" + Style.RESET_ALL)
    print("Config: show_pronouns=True")
    print()
    
    cfg_enabled = Config(show_pronouns=True)
    Entelgia_production_meta.CFG = cfg_enabled
    
    print(Fore.CYAN + get_display_name("Socrates", "he") + Style.RESET_ALL + ": Why do we believe what we believe?")
    print(Fore.MAGENTA + get_display_name("Athena", "she") + Style.RESET_ALL + ": Let me synthesize multiple perspectives on this question.")
    print(Fore.YELLOW + get_display_name("Fixy", "he") + Style.RESET_ALL + ": I notice the dialogue is getting circular.")
    
    print("\n" + Fore.GREEN + "✓ Explicit character identity with pronoun markers" + Style.RESET_ALL)
    print("  Helps LLM understand character relationships and identities")
    print("  LLM may produce more naturally gendered references in responses")
    
    # Demo 3: Character overview
    print("\n" + Fore.CYAN + "=== Character Pronouns ===" + Style.RESET_ALL)
    print()
    
    characters = [
        ("Socrates", "he", "Socratic philosopher who questions assumptions"),
        ("Athena", "she", "Strategic thinker who builds frameworks"),
        ("Fixy", "he", "Observer who detects circular reasoning"),
    ]
    
    # Pre-compute display names for both modes to avoid state toggling
    for name, pronoun, description in characters:
        # Compute both display formats
        Entelgia_production_meta.CFG = cfg_disabled
        display_disabled = get_display_name(name, pronoun)
        Entelgia_production_meta.CFG = cfg_enabled
        display_enabled = get_display_name(name, pronoun)
        
        # Display information
        print(f"  • {name}")
        print(f"    Pronoun: {pronoun}")
        print(f"    Role: {description}")
        print(f"    Display (disabled): {display_disabled}")
        print(f"    Display (enabled): {display_enabled}")
        print()
    
    # Reset to default
    Entelgia_production_meta.CFG = cfg_disabled
    
    # Demo 4: Configuration examples
    print(Fore.CYAN + "=== Configuration Examples ===" + Style.RESET_ALL)
    print()
    print("# Example 1: Default (gender-neutral)")
    print("cfg = Config()")
    print("# show_pronouns defaults to False")
    print()
    print("# Example 2: Enable pronouns")
    print("cfg = Config(show_pronouns=True)")
    print()
    print("# Example 3: Runtime toggle")
    print("CFG.show_pronouns = True   # Enable")
    print("CFG.show_pronouns = False  # Disable")
    print()
    
    # Demo 5: Impact on LLM behavior
    print(Fore.CYAN + "=== Impact on LLM Behavior ===" + Style.RESET_ALL)
    print()
    print("When show_pronouns=False (default):")
    print("  • LLM sees: 'Socrates:', 'Athena:', 'Fixy:'")
    print("  • LLM tends to use character names rather than gendered pronouns")
    print("  • More gender-neutral language in responses")
    print()
    print("When show_pronouns=True:")
    print("  • LLM sees: 'Socrates (he):', 'Athena (she):', 'Fixy (he):'")
    print("  • LLM understands character gender explicitly")
    print("  • May produce more naturally gendered references (he/she)")
    print()
    
    print("=" * 70)
    print(Fore.GREEN + "✓ DEMONSTRATION COMPLETE" + Style.RESET_ALL)
    print("=" * 70)
    print()
    print("Both modes maintain full character personality and dialogue quality.")
    print("The choice depends on preference for inclusivity vs. explicit identity.")


if __name__ == "__main__":
    demo_pronoun_support()

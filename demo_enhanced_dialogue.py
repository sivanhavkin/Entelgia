#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Quick demonstration of enhanced dialogue features
Shows 10 turns of dialogue with the new system.
"""

import sys
import os

# Suppress warnings for demo
os.environ['MEMORY_SECRET_KEY'] = 'demo-key-not-for-production-use-only'

sys.path.insert(0, '.')

from Entelgia_production_meta import MainScript, Config
from colorama import Fore, Style, init as colorama_init

def demo_enhanced_dialogue():
    """Run a short demonstration dialogue."""
    colorama_init(autoreset=True)
    
    print(Fore.GREEN + "=" * 70)
    print(Fore.GREEN + "ENTELGIA ENHANCED DIALOGUE DEMONSTRATION")
    print(Fore.GREEN + "Showing: Dynamic speakers, varied seeds, rich context")
    print(Fore.GREEN + "=" * 70 + Style.RESET_ALL)
    print()
    
    # Create short config for demo (10 turns, 2 minute timeout)
    cfg = Config(
        max_turns=10,
        timeout_minutes=2,
        seed_topic="The nature of consciousness and artificial intelligence"
    )
    
    print(Fore.YELLOW + "Configuration:")
    print(f"  Max turns: {cfg.max_turns}")
    print(f"  Timeout: {cfg.timeout_minutes} minutes")
    print(f"  Seed topic: {cfg.seed_topic}")
    print(f"  Enhanced mode: {cfg.__dict__.get('use_enhanced', 'auto-detect')}")
    print(Style.RESET_ALL)
    
    try:
        # Initialize and run
        app = MainScript(cfg)
        
        # Override max turns for demo
        original_timeout = cfg.timeout_minutes
        cfg.timeout_minutes = 2  # 2 minutes for demo
        
        print(Fore.GREEN + "\nStarting enhanced dialogue...\n" + Style.RESET_ALL)
        
        # Run dialogue (will stop at 10 turns due to max_turns or 2 min timeout)
        app.run()
        
        print(Fore.GREEN + "\n" + "=" * 70)
        print(Fore.GREEN + "DEMONSTRATION COMPLETE")
        print(Fore.GREEN + "=" * 70 + Style.RESET_ALL)
        
        # Show statistics
        print(Fore.YELLOW + "\nDialogue Statistics:")
        print(f"  Total turns: {app.turn_index}")
        print(f"  Unique speakers: {len(set(t.get('role') for t in app.dialog if t.get('role') != 'seed'))}")
        
        # Count speaker turns
        speaker_counts = {}
        for turn in app.dialog:
            role = turn.get('role')
            if role and role != 'seed':
                speaker_counts[role] = speaker_counts.get(role, 0) + 1
        
        print(f"  Speaker distribution:")
        for speaker, count in speaker_counts.items():
            print(f"    - {speaker}: {count} turns")
        
        # Check for Fixy interventions
        fixy_turns = speaker_counts.get('Fixy', 0)
        if fixy_turns > 0:
            print(f"\n  ✓ Fixy intervened {fixy_turns} time(s) (need-based)")
        else:
            print(f"\n  ℹ Fixy did not need to intervene")
        
        print(Style.RESET_ALL)
        
        return 0
        
    except KeyboardInterrupt:
        print(Fore.YELLOW + "\n\nDialogue interrupted by user." + Style.RESET_ALL)
        return 0
    except Exception as e:
        print(Fore.RED + f"\n\nError: {e}" + Style.RESET_ALL)
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(demo_enhanced_dialogue())

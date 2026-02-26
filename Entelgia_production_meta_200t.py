#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Entelgia Unified – 200-Turn No-Timeout Edition - By Sivan Havkin
=================================================================

A variant of Entelgia_production_meta configured for:
  - 200 turns total (hard stop after 200 turns)
  - No time limit (runs until all 200 turns are complete)

Usage:
  python Entelgia_production_meta_200t.py
"""

import json
import sys
import os
from dataclasses import asdict
from colorama import Fore, Style

# Ensure the directory containing the base module is on the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from Entelgia_production_meta import Config, MainScript  # noqa: E402


def main():
    """Run 200-turn, no-timeout dialogue."""
    cfg = Config(max_turns=200, timeout_minutes=0, show_meta=True)

    print(Fore.GREEN + "=" * 80 + Style.RESET_ALL)
    print(
        Fore.GREEN
        + "Entelgia Unified – 200-Turn No-Timeout Edition By Sivan Havkin"
        + Style.RESET_ALL
    )
    print(Fore.GREEN + "=" * 80 + Style.RESET_ALL)
    print("\nConfiguration:")
    config_dict = asdict(cfg)
    config_display = {k: v for k, v in config_dict.items() if not k.startswith("_")}
    print(json.dumps(config_display, ensure_ascii=False, indent=2))
    print()

    try:
        app_script = MainScript(cfg)
        app_script.run()
        print(Fore.GREEN + "\nSession completed successfully!" + Style.RESET_ALL)
    except KeyboardInterrupt:
        print(
            Fore.YELLOW + "\n[INTERRUPTED] Session cancelled by user" + Style.RESET_ALL
        )
        sys.exit(0)
    except Exception as e:
        print(Fore.RED + f"[FATAL ERROR] {e}" + Style.RESET_ALL)
        sys.exit(1)


if __name__ == "__main__":
    main()

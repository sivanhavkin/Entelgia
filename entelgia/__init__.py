#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Entelgia Enhanced Dialogue Package
Provides improved dialogue quality through dynamic speaker selection, rich personas, and intelligent context management.

Version Note: Pronoun support feature added for v2.2.0
Latest official release: v2.2.0
"""

from .dialogue_engine import DialogueEngine, SeedGenerator
from .enhanced_personas import (
    SOCRATES_PERSONA,
    ATHENA_PERSONA,
    FIXY_PERSONA,
    format_persona_for_prompt,
    get_persona,
    get_typical_opening,
    is_global_show_pronouns,
)
from .context_manager import ContextManager, EnhancedMemoryIntegration
from .fixy_interactive import InteractiveFixy

__all__ = [
    "DialogueEngine",
    "SeedGenerator",
    "SOCRATES_PERSONA",
    "ATHENA_PERSONA",
    "FIXY_PERSONA",
    "format_persona_for_prompt",
    "get_persona",
    "get_typical_opening",
    "ContextManager",
    "EnhancedMemoryIntegration",
    "InteractiveFixy",
    "is_global_show_pronouns",
]

__version__ = "2.2.0"  # Latest official: 2.2.0

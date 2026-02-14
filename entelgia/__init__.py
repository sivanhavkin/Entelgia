#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Entelgia Enhanced Dialogue Package
Provides improved dialogue quality through dynamic speaker selection, rich personas, and intelligent context management.
"""

from .dialogue_engine import DialogueEngine, SeedGenerator
from .enhanced_personas import (
    SOCRATES_PERSONA,
    ATHENA_PERSONA,
    FIXY_PERSONA,
    format_persona_for_prompt,
    get_persona,
    get_typical_opening,
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
]

__version__ = "2.1.1"

#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Shared constants for Entelgia
"""

# LLM Response Length Instruction
# Added to all prompts to guide LLM to produce bounded responses
LLM_LENGTH_INSTRUCTION = (
    "Please answer in no more than 150 words. "
    "End your response at a natural sentence boundary."
)

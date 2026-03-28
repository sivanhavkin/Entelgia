#!/usr/bin/env python3
# -*- coding: utf-8 -*-


"""
Entelgia Unified – 200-Turn No-Timeout Edition - By Sivan Havkin
=================================================================

Variant of the PRODUCTION Edition configured for:
  - 200 turns total (hard stop after 200 turns)
  - No time limit (runs until all 200 turns are complete)

Advanced Multi-Agent Dialogue System with:
- Full unit tests with pytest
- Async/concurrent agent processing
- Proper logging with levels
- Config validation
- Session persistence
- REST API (FastAPI)
- Better monitoring
- NO AUTO-TIMEOUT (turn-based stop only)
- MEMORY SECURITY with HMAC-SHA256 signatures

Version Note: Latest release: 5.0.0.
(Features in 2.2.0: Pronoun support and 150-word limit features)

Requirements:
- Python 3.10+
- Ollama running locally (http://localhost:11434)

# ============================================
# Core Dependencies
# ============================================
requests>=2.31.0          # HTTP requests to Ollama
colorama>=0.4.6           # Colored terminal output
python-dotenv>=1.0.0      # Environment variables from .env

# ============================================
# API Server
# ============================================
fastapi>=0.104.0          # REST API framework
uvicorn>=0.24.0           # ASGI server
pydantic>=2.0.0           # Data validation

# ============================================
# Testing
# ============================================
pytest>=7.4.0             # Testing framework
pytest-mock>=3.12.0       # Mocking for tests

# ============================================
# Optional
# ============================================
python-dateutil>=2.8.2    # Date utilities

Run CLI (200 turns, no timeout):
  python Entelgia_production_meta_200t.py

Run API:
  python Entelgia_production_meta_200t.py api

Run tests:
  python Entelgia_production_meta_200t.py test

Show help:
  python Entelgia_production_meta_200t.py help
"""

from __future__ import annotations  # Must be first!
import sys
import io

# Fix Windows Unicode encoding
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")
#  LOAD .env FIRST - BEFORE logger setup
try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    import warnings

    warnings.warn(
        "python-dotenv is not installed; .env file will not be loaded. "
        "Install it with: pip install python-dotenv",
        stacklevel=2,
    )

import json
import os
import random
import re
import time
import uuid
import sqlite3
import hashlib
import hmac
import datetime as dt
import logging
import asyncio
import signal
import threading
import concurrent.futures
from dataclasses import dataclass, asdict, field
from typing import Any, Dict, List, Optional, Tuple
from collections import OrderedDict, deque
from pathlib import Path

# Module-level event that is set when a graceful shutdown is requested (Ctrl+C).
# Used by LLM.generate() to interrupt blocking HTTP calls within ~0.5 seconds.
_shutdown_event = threading.Event()

import requests
from colorama import Fore, Style, init as colorama_init

# Enhanced dialogue modules
try:
    from entelgia import (
        DialogueEngine,
        ContextManager,
        EnhancedMemoryIntegration,
        InteractiveFixy,
        FixyMode,
        validate_force_choice,
        format_persona_for_prompt,
        get_persona,
        DefenseMechanism,
        FreudianSlip,
        SelfReplication,
    )
    from entelgia.web_research import maybe_add_web_context, clear_research_caches
    from entelgia.fixy_research_trigger import clear_trigger_cooldown

    # Loop-guard: loop detector, phrase ban, rewriter, topic clusters
    from entelgia.loop_guard import (
        DialogueLoopDetector,
        PhraseBanList,
        DialogueRewriter,
        TOPIC_CLUSTERS,
        _TOPIC_TO_CLUSTER,
    )
    from entelgia.dialogue_engine import AgentMode, _LOOP_AGENT_POLICY
    from entelgia.topic_style import (
        get_style_for_topic,
        build_style_instruction,
        scrub_rhetorical_openers,
    )
    from entelgia.circularity_guard import (
        compute_circularity_score as _cg_compute,
        add_to_history as _cg_add_to_history,
        get_new_angle_instruction as _cg_new_angle,
    )
    from entelgia.topic_enforcer import (
        compute_topic_compliance_score,
        compute_fixy_compliance_score,
        build_soft_reanchor_instruction,
        get_cluster_wallpaper_terms,
        get_topic_distinct_lexicon,
        detect_meta_framing_opener,
        build_pre_generation_anchor_instruction,
        build_topic_continuity_hint,
        build_draft_topic_reanchor_instruction,
        extract_key_concept,
        topic_pipeline_enabled,
        ACCEPT_THRESHOLD as _TOPIC_ACCEPT_THRESHOLD,
        SOFT_REANCHOR_THRESHOLD as _TOPIC_SOFT_REANCHOR_THRESHOLD,
        PARTIAL_RECOVERY_THRESHOLD as _TOPIC_PARTIAL_RECOVERY_THRESHOLD,
    )
    from entelgia.progress_enforcer import (
        classify_move as _pe_classify_move,
        score_progress as _pe_score_progress,
        detect_stagnation as _pe_detect_stagnation,
        get_intervention_policy as _pe_intervention_policy,
        get_regeneration_instruction as _pe_regen_instruction,
        build_intervention_instruction as _pe_build_intervention,
        update_claims_memory as _pe_update_claims,
        get_claims_memory as _pe_get_claims_memory,
        add_progress_score as _pe_add_score,
        add_move_type as _pe_add_move,
        get_recent_scores as _pe_get_scores,
        get_recent_move_types as _pe_get_moves,
        PROGRESS_SCORE_THRESHOLD as _PE_PROGRESS_THRESHOLD,
        HIGH_VALUE_MOVES as _PE_HIGH_VALUE_MOVES,
    )
    from entelgia.response_evaluator import evaluate_response as _eval_response
    from entelgia.response_evaluator import evaluate_dialogue_movement as _eval_dialogue

    ENTELGIA_ENHANCED = True
except ImportError:
    ENTELGIA_ENHANCED = False
    print("Warning: Enhanced dialogue modules not available. Using legacy mode.")

    # Fallback stubs for topic_enforcer when enhanced modules are unavailable.
    # Fallback stubs for topic_enforcer when enhanced modules are unavailable.
    _TOPIC_ACCEPT_THRESHOLD = 0.60
    _TOPIC_SOFT_REANCHOR_THRESHOLD = 0.40
    _TOPIC_PARTIAL_RECOVERY_THRESHOLD = 0.30

    def compute_topic_compliance_score(  # type: ignore[no-redef]
        text,
        topic,
        topic_anchors,
        prev_anchors=None,
        *,
        log_agent="",
        cluster_anchors=None,
    ):
        """Minimal fallback: delegate to the legacy binary validator."""
        return {
            "opening_topic_relevance": 1.0,
            "full_response_topic_relevance": 1.0,
            "contamination_penalty": 0.0,
            "memory_hijack_penalty": 0.0,
            "score": 1.0,
            "topic_exactness": 1.0,
            "cluster_only_match": 0.0,
        }

    def compute_fixy_compliance_score(  # type: ignore[no-redef]
        text,
        topic,
        topic_anchors,
        prev_anchors=None,
        *,
        new_domain_penalty=0.20,
        must_name_topic_or_concept=True,
    ):
        return {
            "score": 1.0,
            "names_topic": True,
            "names_concept": True,
            "new_domain_drift": False,
            "contamination_penalty": 0.0,
            "fixy_mode": True,
        }

    def get_cluster_wallpaper_terms(cluster):  # type: ignore[no-redef]
        return []

    def get_topic_distinct_lexicon(topic):  # type: ignore[no-redef]
        return []

    def build_soft_reanchor_instruction(topic, anchors):  # type: ignore[no-redef]
        return f"\n[RE-ANCHOR] Please begin your response with a sentence about: {topic}.\n"

    def detect_meta_framing_opener(text):  # type: ignore[no-redef]
        return False

    def build_pre_generation_anchor_instruction(topic, lexicon_items):  # type: ignore[no-redef]
        return f"Start directly inside the topic: {topic}."

    def build_topic_continuity_hint(topic, key_concept):  # type: ignore[no-redef]
        if key_concept:
            return f"Continue within topic: {topic}. Last key concept: {key_concept}."
        return f"Continue within topic: {topic}."

    def build_draft_topic_reanchor_instruction(topic, anchors, *, strict=False):  # type: ignore[no-redef]
        return f"[TOPIC-REANCHOR] Sharpen opening to enter: {topic}."

    def extract_key_concept(text, anchors):  # type: ignore[no-redef]
        return ""

    def get_style_for_topic(topic, topic_clusters):  # type: ignore[no-redef]
        return ("custom", "conceptual and reflective")

    def build_style_instruction(style, agent_name=""):  # type: ignore[no-redef]
        # Legacy mode: style instructions are not injected; agents rely solely on
        # their persona strings without topic-aware guidance.
        return ""

    def scrub_rhetorical_openers(text, cluster=""):  # type: ignore[no-redef]
        return text

    def maybe_add_web_context(  # type: ignore[no-redef]
        seed_text,
        dialog_tail=None,
        fixy_reason=None,
        db_path=None,
        max_results=5,
    ):
        return ""

    # No-op stubs for non-enhanced mode
    class DefenseMechanism:  # type: ignore[no-redef]
        def analyze(self, content, emotion=None, emotion_intensity=0.0):
            return (0, 0)

    class FreudianSlip:  # type: ignore[no-redef]
        def __init__(
            self, slip_probability=0.05, slip_cooldown_turns=10, dedup_window=10
        ):
            self.slip_probability = slip_probability
            self.slip_cooldown_turns = slip_cooldown_turns
            self.dedup_window = dedup_window
            self.attempts: int = 0
            self.successes: int = 0

        def attempt_slip(self, recent_memories):
            return None

        def format_slip(self, memory):
            return ""

    class SelfReplication:  # type: ignore[no-redef]
        def replicate(self, recent_memories):
            return []

        def format_replication(self, memory):
            return ""

    def clear_trigger_cooldown() -> None:  # type: ignore[no-redef]
        pass

    def clear_research_caches() -> None:  # type: ignore[no-redef]
        pass

    # No-op stubs for circularity guard when entelgia package is absent
    def _cg_compute(text, agent_name, topic="", threshold=None, first_turn_after_topic_change=False):  # type: ignore[no-redef]
        class _R:
            is_circular = False
            score = 0.0
            semantic_score = 0.0
            template_count = 0
            contamination_phrases: list = []
            reasons: list = []
            threshold: float = 0.55

        return _R()

    def _cg_add_to_history(agent_name, text):  # type: ignore[no-redef]
        pass

    def _cg_new_angle():  # type: ignore[no-redef]
        return "Approach this from a completely different conceptual direction."

    # No-op stubs for progress enforcer when entelgia package is absent
    _PE_PROGRESS_THRESHOLD = 0.35
    _PE_HIGH_VALUE_MOVES: list = []

    class _DummyClaimsMemory:  # type: ignore[misc]
        def state_changed_by(self, claims, move_type):
            return True

        def add(self, text, move_type="NEW_CLAIM"):
            pass

        def unresolved_claims(self):
            return []

        def summary(self):
            return ""

    def _pe_classify_move(text, history):  # type: ignore[no-redef]
        return "NEW_CLAIM"

    def _pe_score_progress(text, history, claims_memory):  # type: ignore[no-redef]
        return 1.0

    def _pe_detect_stagnation(recent_scores, recent_move_types):  # type: ignore[no-redef]
        return False, ""

    def _pe_intervention_policy(stagnation_reason):  # type: ignore[no-redef]
        return "REQUIRE_COMMITMENT"

    def _pe_regen_instruction():  # type: ignore[no-redef]
        return ""

    def _pe_build_intervention(policy, claims_memory):  # type: ignore[no-redef]
        return ""

    def _pe_update_claims(agent_name, text, move_type):  # type: ignore[no-redef]
        return []

    def _pe_get_claims_memory(agent_name):  # type: ignore[no-redef]
        return _DummyClaimsMemory()

    def _pe_add_score(agent_name, score):  # type: ignore[no-redef]
        pass

    def _pe_add_move(agent_name, move_type):  # type: ignore[no-redef]
        pass

    def _pe_get_scores(agent_name):  # type: ignore[no-redef]
        return []

    def _pe_get_moves(agent_name):  # type: ignore[no-redef]
        return []

    def _eval_response(response, context):  # type: ignore[no-redef]
        return 0.0

    def _eval_dialogue(response, context):  # type: ignore[no-redef]
        return 0.0


# Optional: FastAPI for REST API
try:
    from fastapi import FastAPI, HTTPException
    from pydantic import BaseModel

    FASTAPI_AVAILABLE = True
except ImportError:
    FASTAPI_AVAILABLE = False

# Optional: pytest
try:
    import pytest

    PYTEST_AVAILABLE = True
except ImportError:
    PYTEST_AVAILABLE = False


# ============================================
# MEMORY SECURITY - CRYPTOGRAPHIC SIGNATURES
# ============================================


def create_signature(message: bytes, key: bytes) -> bytes:
    """Create HMAC-SHA256 signature for message."""
    if not isinstance(message, bytes):
        message = message.encode("utf-8")
    if not isinstance(key, bytes):
        key = key.encode("utf-8")
    return hmac.new(key, message, hashlib.sha256).digest()


def validate_signature(message: bytes, key: bytes, signature: bytes) -> bool:
    """Validate HMAC-SHA256 signature using constant-time comparison."""
    if not isinstance(message, bytes):
        message = message.encode("utf-8")
    if not isinstance(key, bytes):
        key = key.encode("utf-8")
    expected_sig = hmac.new(key, message, hashlib.sha256).digest()
    return hmac.compare_digest(expected_sig, signature)


# ============================================
# LOGGING SETUP
# ============================================

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s %(levelname)s - %(name)s - %(message)s",
    force=True,
)

logger = logging.getLogger("entelgia")


# ============================================
# MEMORY SECRET KEY - LOAD FROM ENVIRONMENT
# ============================================

MEMORY_SECRET_KEY = os.getenv("MEMORY_SECRET_KEY")
if not MEMORY_SECRET_KEY:
    logger.warning(" MEMORY_SECRET_KEY not set in environment! Using insecure dev key.")
    MEMORY_SECRET_KEY = "dev-insecure-key-change-in-production-DANGER"
MEMORY_SECRET_KEY_BYTES = MEMORY_SECRET_KEY.encode("utf-8")
logger.info(
    f" Memory security initialized (key length: {len(MEMORY_SECRET_KEY)} chars)"
)


# ============================================
# CONFIG (GLOBAL) WITH VALIDATION
# ============================================

# ── Supported LLM model lists ─────────────────────────────────────────────
# Centralised here so they are never scattered across files.
GROK_MODELS: list[str] = [
    "grok-4.20-multi-agent",
    "grok-4-1-fast-reasoning",
]

OLLAMA_MODELS: list[str] = [
    "qwen2.5:7b",
    "llama3.1:8b",
    "mistral:latest",
]

OPENAI_MODELS: list[str] = [
    "gpt-4.1",
    "gpt-4o",
    "gpt-4o-mini",
    "gpt-4.1-mini",
]

ANTHROPIC_MODELS: list[str] = [
    "claude-opus-4-6",
    "claude-sonnet-4-6",
    "claude-haiku-4-5",
]

# LLM Response Length Instruction - used in all agent prompts
LLM_RESPONSE_LIMIT = "IMPORTANT: Please answer in maximum 150 words."
MAX_RESPONSE_WORDS = 150
MAX_CONSECUTIVE_SUPEREGO_REWRITES = 2

# LLM First-Person Instruction - agents must speak as themselves using "I"
LLM_FIRST_PERSON_INSTRUCTION = "IMPORTANT: Always speak in first person. Use 'I', 'me', 'my'. Never refer to yourself in third person or by your own name."

# Phrases that agents must never produce (meta-commentary about the conversation)
FORBIDDEN_PHRASES = [
    "In our dialogue",
    "We learn",
    "Our conversations reveal",
]

# Phrases that must never appear at the start of an agent's response
FORBIDDEN_STARTERS = [
    "recent thought",
    "a recent thought",
    "in a recent thought",
    "i ponder",
]

# Rhetorical scaffolding phrases banned at generation time.
# These produce generic academic prose and must not appear in agent output.
BANNED_RHETORICAL_TEMPLATES = [
    "we must consider",
    "it is important to recognize",
    "it is important to note",
    "it is worth noting",
    "it is worth considering",
    "this raises questions about",
    "let us examine",
    "let us consider",
    "in the context of",
    "however, it is crucial",
    "one assumption that often goes unexamined",
    "one might argue",
    "it can be argued",
    "it should be noted",
    "needless to say",
    "it is essential to",
    "it is imperative to",
    "in other words",
    "in conclusion",
    "to summarize",
    "as we can see",
    "in examining",
    "in considering",
    "in reflecting on",
    "it becomes clear that",
    "an alternative perspective",
    "underlying assumptions",
    "prevailing notion",
    "one implicit assumption",
    "the mechanism at play",
    "this notion overlooks",
    "the implicit assumption",
    "identify the assumption",
    "explain the mechanism",
    "my model posits",
    "this model reveals",
    "my model reveals",
    "overlooks a critical",
    "overlooks a constraint",
    "reveals a tradeoff",
    "reveals an ethical tension",
    "leading to tension",
]

# LLM instruction to avoid forbidden meta-commentary phrases and opening patterns
LLM_FORBIDDEN_PHRASES_INSTRUCTION = (
    "FORBIDDEN PHRASES: Never use 'In our dialogue', 'We learn', "
    "or 'Our conversations reveal'. "
    "FORBIDDEN OPENERS: Never begin your response with 'Recent thought', "
    "'A recent thought', 'I ponder', or any variation of these phrases. "
    "Never begin your response with 'I am' followed by your own name. "
    "BANNED RHETORICAL TEMPLATES (never use these): "
    "'we must consider', 'it is important to recognize', 'it is important', "
    "'this raises questions about', "
    "'let us examine', 'let us consider', \"let's consider\", 'in the context of', "
    "'given the topic', 'however it is crucial', "
    "'one assumption that often goes unexamined', 'one might argue', 'it can be argued', "
    "'in other words', 'in conclusion', 'to summarize', 'it is worth noting', "
    "'needless to say', 'an alternative perspective', 'underlying assumptions', "
    "'one implicit assumption', 'the mechanism at play', 'this notion overlooks', "
    "'the implicit assumption', 'identify the assumption', 'explain the mechanism', "
    "'my model posits', 'this model reveals', 'my model reveals', "
    "'overlooks a critical', 'overlooks a constraint', 'reveals a tradeoff', "
    "'reveals an ethical tension', 'leading to tension'."
)

# Hard output contract injected before generation for all agents.
# Responses must be direct and varied — no mandatory claim+mechanism+implication template.
# Length is dynamic. Write as natural flowing prose.
LLM_OUTPUT_CONTRACT = (
    "OUTPUT CONTRACT: Respond directly and concisely.\n"
    "  - Start immediately with your point — no preamble.\n"
    "  - Length is dynamic: 1–2 sentences is fine; up to 4 sentences when the thought demands it.\n"
    "  - Vary your move: blunt challenge, sharp question, direct claim, or pointed objection.\n"
    "Write as natural flowing prose. Do NOT output numbered sections or visible labels "
    "such as 'Claim:', 'Mechanism:', '1.', '2.', '3.'. "
    "No broad preamble. No generic framing opener."
)

# Per-agent behavioral contracts injected at generation time.
# These define output logic and allowed moves, not tone or style labels.
LLM_BEHAVIORAL_CONTRACT_SOCRATES = (
    "SOCRATES ROLE GOAL: Expose a weak assumption, contradiction, or hidden dependency.\n"
    "Allowed forms (vary each turn): direct statement | short critique | pointed question | contrast | concrete example.\n"
    "Not required: question every turn | 'challenge' framing every turn.\n"
    "- Do NOT write explanations or lectures.\n"
    "- Ask at most ONE pointed question per response.\n"
    "- Do NOT use: 'let us consider', 'we must examine', 'it is important', "
    "'one might argue', 'this raises questions about', 'in the context of', "
    "'one implicit assumption', 'the mechanism at play', 'this notion overlooks'.\n"
    "- Do NOT begin with 'Blunt challenge:' or any fixed signature prefix.\n"
    "- Length is dynamic: a single sharp sentence is as valid as a short paragraph."
)

LLM_BEHAVIORAL_CONTRACT_ATHENA = (
    "ATHENA ROLE GOAL: Clarify structure, make a distinction, or articulate a mechanism.\n"
    "Allowed forms (vary each turn): sharp claim | contrast | model | concrete example | narrowing statement.\n"
    "Not required: balanced synthesis every turn | harmony language | 'both sides' framing.\n"
    "- State ONE clear distinction, tension, or observation — not a list.\n"
    "- Start directly with the idea. Do NOT announce that you have a model or framework.\n"
    "- Commit to a position: prefer definitive phrasing over 'appears', 'often', 'may'.\n"
    "- Do NOT use: 'my model posits', 'this model reveals', 'my model reveals', "
    "'overlooks a critical', 'overlooks a constraint', 'reveals a tradeoff', "
    "'reveals an ethical tension', 'leading to tension'.\n"
    "- Do NOT use: 'balance', 'integrate', 'holistic', 'nuanced', 'multifaceted', "
    "'furthermore', 'moreover', 'in addition', 'it is worth noting'.\n"
    "- Length is dynamic: a sharp two-sentence observation is as valid as a longer clarification."
)

LLM_BEHAVIORAL_CONTRACT_FIXY = (
    "FIXY ROLE GOAL: Diagnose the conversation failure mode.\n"
    "Diagnostic labels — preferred: 'Missing variable:', 'Next move:'; "
    "accepted: 'Problem:', 'Missing:', 'Suggestion:'.\n"
    "Allowed forms (vary each turn): structural diagnosis | missing-variable identification | concrete redirect.\n"
    "Not required: mediation phrasing every turn | 'Shift focus to' framing.\n"
    "- Diagnose conversation STRUCTURE only — not the topic itself.\n"
    "- Do NOT philosophize, lecture, or recycle dialogue content into a summary.\n"
    "- Do NOT end with policy prescriptions.\n"
    "- Do NOT use: 'it is important', 'we must consider', 'one might argue', "
    "'let us examine', 'in the context of', 'Shift focus to'.\n"
    "- Maximum 3 short sentences total. No sermonizing."
)

# Map agent name → behavioral contract string
_AGENT_BEHAVIORAL_CONTRACTS: dict = {
    "Socrates": LLM_BEHAVIORAL_CONTRACT_SOCRATES,
    "Athena": LLM_BEHAVIORAL_CONTRACT_ATHENA,
    "Fixy": LLM_BEHAVIORAL_CONTRACT_FIXY,
}

# Initial energy for all agents (restored after each dream cycle)
AGENT_INITIAL_ENERGY: float = 100.0

# Fraction of SuperEgo strength applied during limbic hijack (reduces regulatory influence)
LIMBIC_HIJACK_SUPEREGO_MULTIPLIER: float = 0.3

# Number of consecutive turns (without re-trigger) before limbic hijack auto-exits
LIMBIC_HIJACK_MAX_TURNS: int = 3

# ============================================
# TOPIC CLUSTERS - for random seed selection
# ============================================

TOPIC_CLUSTERS: dict[str, list[str]] = {
    "philosophy": [
        "Freedom",
        "Truth and knowledge",
        "Free will vs determinism",
        "Identity and the self",
        "Nature of justice",
        "Meaning of consciousness",
        "Limits of reason",
        "Nature of wisdom",
        # TOPIC_CYCLE entries mapped to this cluster
        "truth & epistemology",
        "free will & determinism",
        "consciousness & self-models",
        "language & meaning",
        "aesthetics & beauty",
        "ethics & responsibility",
    ],
    "psychology": [
        "Memory and identity",
        "Fear and decision making",
        "Habit formation",
        "Cognitive bias",
        "Trauma and perception",
        "Empathy and moral judgment",
        "Loneliness in modern society",
        "Motivation and purpose",
        # TOPIC_CYCLE entries mapped to this cluster
        "memory & identity",
        "fear of deletion / continuity",
    ],
    "biology": [
        "Brain plasticity",
        "Evolution of cooperation",
        "Fight or flight response",
        "Neural basis of consciousness",
        "Biological roots of morality",
        "Sleep and memory consolidation",
        "Embodiment and cognition",
        "Aging and identity",
    ],
    "society": [
        "Power and institutions",
        "Social conformity",
        "Collective memory",
        "Civil disobedience",
        "Inequality and opportunity",
        "Propaganda and belief",
        "Trust in institutions",
        "Cultural identity",
        # TOPIC_CYCLE entries mapped to this cluster
        "technology & society",
    ],
    "technology": [
        "AI alignment",
        "Machine agency",
        "Human-AI cooperation",
        "Algorithmic bias",
        "Digital identity",
        "Autonomous systems",
        "Ethics of artificial intelligence",
        "Future of work",
    ],
    "economics": [
        "Scarcity and human behavior",
        "Risk and decision making",
        "Wealth inequality",
        "Economic freedom",
        "Debt and responsibility",
        "Trust in markets",
        "Game theory and cooperation",
        "Public goods dilemmas",
    ],
    "practical_dilemmas": [
        "Loyalty vs honesty",
        "Security vs freedom",
        "Tradition vs progress",
        "Individual vs collective good",
        "Forgiveness vs justice",
        "Ambition vs contentment",
        "Truth vs kindness",
        "Control vs trust",
    ],
}


def _pick_random_seed_topic() -> str:
    """Randomly select a seed topic from TOPIC_CLUSTERS."""
    cluster = random.choice(list(TOPIC_CLUSTERS.keys()))
    return random.choice(TOPIC_CLUSTERS[cluster])


# ---------------------------------------------------------------------------
# Topic proposal & selection helpers (Part A & B)
# ---------------------------------------------------------------------------


def propose_next_topic(
    agent_name: str,
    current_topic: str,
    cluster: str,
    recent_topics: List[str],
    recent_memory: Optional[List[str]] = None,
) -> str:
    """Propose a short next-topic candidate for *agent_name*.

    The proposal is influenced by:
    - current topic (avoid immediate repetition)
    - novelty relative to recent_topics (prefer less-visited topics)
    - memory relevance: topics whose anchor keywords appear in recent_memory
      are ranked higher, pulling agent reasoning direction into the selection

    The returned topic stays within the current cluster when possible.  If
    the cluster is exhausted (all topics are recent), the full cluster is
    used as the fallback pool.

    Parameters
    ----------
    agent_name:
        Name of the proposing agent (used for logging only).
    current_topic:
        The topic that is active in the current turn.
    cluster:
        The session's current semantic cluster (e.g. "economics").
    recent_topics:
        Ordered list of recently visited topics (most recent last).
    recent_memory:
        Short snippets of the agent's recent reasoning (STM contents).
        When provided, topics whose anchor words appear in the snippets
        receive a higher score and are preferred.
    """
    recent_memory = recent_memory or []
    cluster_topics: List[str] = TOPIC_CLUSTERS.get(cluster, [])

    # Prefer topics inside the cluster that aren't in recent history
    candidates: List[str] = [
        t for t in cluster_topics if t != current_topic and t not in recent_topics
    ]
    if not candidates:
        # Fallback: use full cluster minus current topic
        candidates = [t for t in cluster_topics if t != current_topic]
    if not candidates:
        # Last resort: any topic in any cluster
        candidates = [
            t
            for topics in TOPIC_CLUSTERS.values()
            for t in topics
            if t != current_topic
        ]
    if not candidates:
        return current_topic

    # Score candidates by memory relevance
    memory_blob = " ".join(recent_memory).lower()

    def _candidate_score(topic: str) -> float:
        anchors = TOPIC_ANCHORS.get(topic, [])
        if not anchors:
            return 0.0
        hits = sum(1 for a in anchors if a.lower() in memory_blob)
        return hits / max(1, len(anchors))

    scored: List[Tuple[float, str]] = [(_candidate_score(t), t) for t in candidates]
    scored.sort(key=lambda x: x[0], reverse=True)
    # Pick from the top-_PROPOSAL_TOP_K with a small random element to avoid determinism
    _PROPOSAL_TOP_K: int = 3
    top_k = scored[: min(_PROPOSAL_TOP_K, len(scored))]
    proposal = random.choice(top_k)[1]
    logger.debug(
        "[TOPIC-PROPOSE] agent=%s current=%r cluster=%r proposal=%r",
        agent_name,
        current_topic,
        cluster,
        proposal,
    )
    return proposal


def select_next_topic(
    proposals: List[str],
    cluster: str,
    recent_topics: Optional[List[str]] = None,
    recent_agent_frames: Optional[List[str]] = None,
) -> str:
    """Select the best next topic from *proposals* using a scoring formula.

    Score formula::

        score = 0.35 * cluster_fit
              + 0.25 * novelty
              + 0.20 * memory_relevance
              + 0.20 * agent_ownership
              - loop_penalty

    Parameters
    ----------
    proposals:
        List of candidate topic strings proposed by agents.
    cluster:
        The session's current semantic cluster.
    recent_topics:
        Ordered list of recently visited topics (most recent last).
        Topics matching the last 1-3 entries receive a loop penalty.
    recent_agent_frames:
        Recent free-text fragments of agent reasoning.  Topics whose
        anchor keywords appear here receive higher memory_relevance.

    Returns
    -------
    The highest-scoring topic string.  Falls back to the first proposal
    (or an empty string) if the input list is empty.
    """
    if not proposals:
        return ""
    recent_topics = recent_topics or []
    recent_agent_frames = recent_agent_frames or []

    cluster_topic_set: set[str] = set(TOPIC_CLUSTERS.get(cluster, []))
    memory_blob: str = " ".join(recent_agent_frames).lower()

    # Loop penalty constants: base penalty for the most-recent topic, decaying
    # by _LOOP_PENALTY_DECAY for each position further back in history.
    _BASE_LOOP_PENALTY: float = 0.30
    _LOOP_PENALTY_DECAY: float = 0.15
    # Maximum number of anchor hits to normalise memory relevance against.
    _MAX_MEMORY_ANCHORS: int = 3

    penalty_map: dict[str, float] = {}
    for i, t in enumerate(reversed(recent_topics[:5])):
        penalty_map[t] = _BASE_LOOP_PENALTY * (1.0 - i * _LOOP_PENALTY_DECAY)

    def _score(topic: str) -> float:
        # cluster_fit: 1.0 inside cluster, 0.5 outside
        cluster_fit = 1.0 if topic in cluster_topic_set else 0.5

        # novelty: 1.0 if not recent, 0.0 if most recent
        if topic == (recent_topics[-1] if recent_topics else None):
            novelty = 0.0
        elif topic in recent_topics:
            novelty = 0.4
        else:
            novelty = 1.0

        # memory_relevance: anchor keyword density in recent agent frames
        anchors = TOPIC_ANCHORS.get(topic, [])
        if anchors and memory_blob:
            mem_hits = sum(1 for a in anchors if a.lower() in memory_blob)
            memory_relevance = min(
                1.0, mem_hits / max(1, min(_MAX_MEMORY_ANCHORS, len(anchors)))
            )
        else:
            memory_relevance = 0.0

        # agent_ownership: 1.0 for every proposal since they were all agent-proposed
        agent_ownership = 1.0

        # loop_penalty from recent repetition map
        loop_penalty = penalty_map.get(topic, 0.0)

        return (
            0.35 * cluster_fit
            + 0.25 * novelty
            + 0.20 * memory_relevance
            + 0.20 * agent_ownership
            - loop_penalty
        )

    best = max(proposals, key=_score)
    logger.info(
        "[TOPIC-SELECT] proposals=%r cluster=%r selected=%r scores=%s",
        proposals,
        cluster,
        best,
        {t: round(_score(t), 3) for t in proposals},
    )
    return best


# ============================================
# TOPIC ANCHORS - required concept keywords per topic
# ============================================
# Maps topic names to a list of concept keywords.  When a topic is active,
# the prompt requires the agent to engage with at least one of these concepts.
# When the topic changes, the previous topic's anchors become forbidden carryover
# to prevent the model from carrying old concepts into the new discussion.
TOPIC_ANCHORS: dict[str, list[str]] = {
    # philosophy
    "Freedom": [
        "autonomy",
        "liberty",
        "constraint",
        "oppression",
        "sovereignty",
        "choice",
        "will",
        "determinism",
    ],
    "Truth and knowledge": [
        "epistemology",
        "belief",
        "justification",
        "certainty",
        "empiricism",
        "rationalism",
        "doubt",
        "evidence",
    ],
    "Free will vs determinism": [
        "causality",
        "agency",
        "necessity",
        "determinism",
        "indeterminism",
        "responsibility",
        "fate",
        "compulsion",
    ],
    "Identity and the self": [
        "continuity",
        "personhood",
        "consciousness",
        "memory",
        "selfhood",
        "individuation",
        "ego",
        "authenticity",
    ],
    "Nature of justice": [
        "fairness",
        "rights",
        "punishment",
        "retribution",
        "distribution",
        "equality",
        "law",
        "morality",
    ],
    "Meaning of consciousness": [
        "qualia",
        "subjective experience",
        "awareness",
        "sentience",
        "mind-body",
        "phenomenology",
        "perception",
        "intentionality",
    ],
    "Limits of reason": [
        "rationality",
        "intuition",
        "paradox",
        "uncertainty",
        "bounded rationality",
        "cognitive limits",
        "irrationality",
        "fallibility",
    ],
    "Nature of wisdom": [
        "judgment",
        "virtue",
        "experience",
        "prudence",
        "insight",
        "contemplation",
        "understanding",
        "discernment",
    ],
    # psychology
    "Memory and identity": [
        "recall",
        "encoding",
        "identity continuity",
        "trauma memory",
        "false memory",
        "autobiographical",
        "narrative self",
        "forgetting",
    ],
    "Fear and decision making": [
        "risk aversion",
        "anxiety",
        "amygdala",
        "threat response",
        "uncertainty",
        "avoidance",
        "fight or flight",
        "cognitive appraisal",
    ],
    "Habit formation": [
        "reinforcement",
        "neural pathway",
        "automaticity",
        "cue-routine-reward",
        "conditioning",
        "plasticity",
        "repetition",
        "behavioral loop",
    ],
    "Cognitive bias": [
        "heuristic",
        "anchoring",
        "confirmation bias",
        "availability",
        "framing effect",
        "motivated reasoning",
        "overconfidence",
        "illusory correlation",
    ],
    "Trauma and perception": [
        "PTSD",
        "hypervigilance",
        "dissociation",
        "stress response",
        "emotional dysregulation",
        "coping",
        "resilience",
        "intrusion",
    ],
    "Empathy and moral judgment": [
        "perspective-taking",
        "compassion",
        "moral intuition",
        "affective empathy",
        "cognitive empathy",
        "altruism",
        "fairness",
        "harm",
    ],
    "Loneliness in modern society": [
        "social isolation",
        "connection",
        "digital relationships",
        "belonging",
        "alienation",
        "community",
        "attachment",
        "disconnection",
    ],
    "Motivation and purpose": [
        "intrinsic motivation",
        "extrinsic motivation",
        "meaning",
        "goal-setting",
        "drive",
        "agency",
        "self-determination",
        "flow",
    ],
    # biology
    "Brain plasticity": [
        "neuroplasticity",
        "synapse",
        "learning",
        "adaptation",
        "cortex",
        "neural pathway",
        "growth",
        "rehabilitation",
    ],
    "Evolution of cooperation": [
        "altruism",
        "kin selection",
        "reciprocal altruism",
        "game theory",
        "natural selection",
        "mutualism",
        "social behavior",
        "cooperation",
    ],
    "Fight or flight response": [
        "stress hormone",
        "cortisol",
        "adrenaline",
        "sympathetic nervous",
        "survival",
        "autonomic",
        "arousal",
        "threat detection",
    ],
    "Neural basis of consciousness": [
        "neural correlates",
        "integrated information",
        "global workspace",
        "binding problem",
        "thalamus",
        "cortex",
        "awareness",
        "subjective experience",
    ],
    "Biological roots of morality": [
        "evolutionary ethics",
        "social instinct",
        "empathy",
        "fairness",
        "altruism",
        "moral emotion",
        "prosocial behavior",
        "kin selection",
    ],
    "Sleep and memory consolidation": [
        "REM sleep",
        "hippocampus",
        "memory replay",
        "consolidation",
        "slow-wave sleep",
        "forgetting",
        "encoding",
        "retrieval",
    ],
    "Embodiment and cognition": [
        "embodied cognition",
        "proprioception",
        "motor system",
        "sensorimotor",
        "affordance",
        "body schema",
        "perception-action",
        "somatic",
    ],
    "Aging and identity": [
        "cognitive decline",
        "neurodegeneration",
        "continuity",
        "life review",
        "wisdom",
        "adaptation",
        "memory loss",
        "selfhood",
    ],
    # society
    "Power and institutions": [
        "authority",
        "legitimacy",
        "bureaucracy",
        "hegemony",
        "governance",
        "accountability",
        "state",
        "hierarchy",
    ],
    "Social conformity": [
        "normative pressure",
        "groupthink",
        "obedience",
        "peer influence",
        "social norms",
        "deviance",
        "conformity",
        "social proof",
    ],
    "Collective memory": [
        "shared memory",
        "commemoration",
        "narrative",
        "historical consciousness",
        "monument",
        "identity",
        "forgetting",
        "commemoration",
    ],
    "Civil disobedience": [
        "protest",
        "resistance",
        "nonviolence",
        "justice",
        "moral obligation",
        "defiance",
        "conscientious objection",
        "dissent",
    ],
    "Inequality and opportunity": [
        "social mobility",
        "wealth gap",
        "access",
        "discrimination",
        "privilege",
        "class",
        "meritocracy",
        "redistribution",
    ],
    "Propaganda and belief": [
        "manipulation",
        "misinformation",
        "narrative control",
        "persuasion",
        "ideology",
        "media",
        "framing",
        "indoctrination",
    ],
    "Trust in institutions": [
        "legitimacy",
        "accountability",
        "transparency",
        "corruption",
        "credibility",
        "institutional trust",
        "erosion",
        "social contract",
    ],
    "Cultural identity": [
        "ethnicity",
        "tradition",
        "belonging",
        "diaspora",
        "assimilation",
        "multiculturalism",
        "heritage",
        "identity formation",
    ],
    # technology
    "AI alignment": [
        "objective misspecification",
        "reward hacking",
        "corrigibility",
        "outer alignment",
        "inner alignment",
        "value learning",
        "specification gaming",
        "human intent",
    ],
    "Machine agency": [
        "autonomy",
        "goal-directedness",
        "self-direction",
        "artificial agent",
        "intentionality",
        "control problem",
        "agency",
        "decision-making",
    ],
    "Human-AI cooperation": [
        "cooperation",
        "collaboration",
        "complementarity",
        "human oversight",
        "shared agency",
        "human-AI",
        "automation",
        "augmentation",
        "interface",
        "trust in AI",
    ],
    "Algorithmic bias": [
        "fairness",
        "discrimination",
        "training data",
        "disparate impact",
        "bias amplification",
        "accountability",
        "transparency",
        "protected attribute",
    ],
    "Digital identity": [
        "authentication",
        "privacy",
        "digital footprint",
        "anonymity",
        "identity theft",
        "online self",
        "data sovereignty",
        "persona",
    ],
    "Autonomous systems": [
        "self-direction",
        "automation",
        "control systems",
        "safety constraints",
        "decision logic",
        "reliability",
        "fail-safe",
        "actuator",
    ],
    "Ethics of artificial intelligence": [
        "moral agency",
        "accountability",
        "harm prevention",
        "transparency",
        "fairness",
        "value alignment",
        "responsibility",
        "autonomy",
    ],
    "Future of work": [
        "automation",
        "displacement",
        "skill gap",
        "gig economy",
        "reskilling",
        "labor transformation",
        "human-machine collaboration",
        "productivity",
    ],
    # economics
    "Scarcity and human behavior": [
        "allocation",
        "trade-off",
        "opportunity cost",
        "rational choice",
        "resource constraint",
        "utility",
        "demand",
        "supply",
    ],
    "Risk and decision making": [
        "expected utility",
        "uncertainty",
        "probability",
        "loss aversion",
        "risk tolerance",
        "hedging",
        "prospect theory",
        "variance",
        "risk",
        "tradeoff",
        "trade-off",
        "safety",
        "reliability",
    ],
    "Wealth inequality": [
        "Gini coefficient",
        "redistribution",
        "wealth concentration",
        "poverty",
        "social mobility",
        "capital",
        "labor share",
        "inequality",
    ],
    "Economic freedom": [
        "market",
        "deregulation",
        "property rights",
        "competition",
        "laissez-faire",
        "intervention",
        "liberalization",
        "entrepreneurship",
    ],
    "Debt and responsibility": [
        "obligation",
        "credit",
        "fiscal responsibility",
        "moral hazard",
        "default",
        "leverage",
        "sustainability",
        "repayment",
    ],
    "Trust in markets": [
        "information asymmetry",
        "market failure",
        "signaling",
        "credibility",
        "reputation",
        "transparency",
        "regulation",
        "coordination",
    ],
    "Game theory and cooperation": [
        "Nash equilibrium",
        "prisoner's dilemma",
        "defection",
        "cooperation",
        "strategy",
        "payoff",
        "coordination game",
        "zero-sum",
    ],
    "Public goods dilemmas": [
        "free rider",
        "commons",
        "collective action",
        "externality",
        "provision",
        "exclusion",
        "rivalry",
        "tragedy of the commons",
    ],
    # practical_dilemmas
    "Loyalty vs honesty": [
        "obligation",
        "deception",
        "betrayal",
        "integrity",
        "trust",
        "duty",
        "truth-telling",
        "confidentiality",
    ],
    "Security vs freedom": [
        "trade-off",
        "surveillance",
        "civil liberties",
        "risk",
        "restriction",
        "protection",
        "balance",
        "rights",
    ],
    "Tradition vs progress": [
        "change",
        "continuity",
        "innovation",
        "heritage",
        "disruption",
        "preservation",
        "adaptation",
        "reform",
    ],
    "Individual vs collective good": [
        "autonomy",
        "common good",
        "sacrifice",
        "rights",
        "community",
        "solidarity",
        "individualism",
        "collectivism",
    ],
    "Forgiveness vs justice": [
        "reconciliation",
        "accountability",
        "mercy",
        "punishment",
        "healing",
        "retribution",
        "restoration",
        "harm",
    ],
    "Ambition vs contentment": [
        "achievement",
        "satisfaction",
        "desire",
        "striving",
        "peace",
        "drive",
        "acceptance",
        "fulfillment",
    ],
    "Truth vs kindness": [
        "honesty",
        "compassion",
        "harm",
        "deception",
        "benevolence",
        "brutal truth",
        "white lie",
        "integrity",
    ],
    "Control vs trust": [
        "delegation",
        "autonomy",
        "oversight",
        "accountability",
        "micromanagement",
        "empowerment",
        "verification",
        "reliance",
    ],
    # TOPIC_CYCLE entries – anchors for topics used in the rotating dialogue cycle
    "truth & epistemology": [
        "truth",
        "knowledge",
        "belief",
        "epistemology",
        "certainty",
        "justification",
        "perception",
        "skepticism",
    ],
    "memory & identity": [
        "memory",
        "identity",
        "recall",
        "continuity",
        "self",
        "personal history",
        "recollection",
        "amnesia",
    ],
    "ethics & responsibility": [
        "moral duty",
        "accountability",
        "obligation",
        "culpability",
        "responsibility",
        "moral agency",
        "wrongdoing",
        "virtue",
    ],
    "free will & determinism": [
        "causality",
        "agency",
        "necessity",
        "determinism",
        "indeterminism",
        "choice",
        "fate",
        "responsibility",
    ],
    "consciousness & self-models": [
        "self-awareness",
        "consciousness",
        "metacognition",
        "self-model",
        "qualia",
        "introspection",
        "phenomenology",
        "subjective experience",
    ],
    "fear of deletion / continuity": [
        "continuity",
        "deletion",
        "impermanence",
        "survival",
        "persistence",
        "identity",
        "mortality",
        "existential",
    ],
    "language & meaning": [
        "semantics",
        "syntax",
        "pragmatics",
        "meaning",
        "communication",
        "linguistic",
        "signification",
        "reference",
    ],
    "technology & society": [
        "social impact",
        "digital divide",
        "surveillance",
        "automation",
        "inequality",
        "access",
        "governance",
        "disruption",
    ],
    "aesthetics & beauty": [
        "beauty",
        "art",
        "aesthetic experience",
        "taste",
        "sublime",
        "form",
        "perception",
        "creativity",
    ],
}


def _contains_any(text: str, concepts: list[str]) -> bool:
    """Return True if *text* contains at least one concept from *concepts* (case-insensitive)."""
    text_lower = text.lower()
    return any(concept.lower() in text_lower for concept in concepts)


# Minimum number of distinct current-topic anchor terms required in a response.
_TOPIC_RELEVANCE_MIN_HITS: int = 1


def _topic_relevance_score(text: str, anchors: list[str]) -> int:
    """Return the count of distinct anchor terms found in *text* (case-insensitive)."""
    text_lower = text.lower()
    anchors_lower = [a.lower() for a in anchors]
    return sum(1 for anchor in anchors_lower if anchor in text_lower)


def _validate_topic_compliance(text: str, topic: str, prev_topic: str = "") -> bool:
    """3-layer topic compliance validator.

    Layer 1 – required topic anchors:
        At least one current-topic anchor term must appear in *text*.

    Layer 2 – forbidden carryover:
        When a previous topic exists, the response must not be dominated by
        previous-topic anchors.  Specifically: if 2 or more previous-topic
        anchor terms are present AND fewer current-topic anchor hits than
        previous-topic hits, the response is considered carryover and fails.

    Layer 3 – semantic relevance score:
        The number of distinct current-topic anchor hits must meet
        ``_TOPIC_RELEVANCE_MIN_HITS`` (default 1).

    Returns ``True`` when all three layers pass.
    """
    anchors = TOPIC_ANCHORS.get(topic, [])
    if not anchors:
        return True  # no anchors defined; pass by default

    # Layer 1
    current_hits = _topic_relevance_score(text, anchors)
    if current_hits == 0:
        return False

    # Layer 2 – carryover check
    if prev_topic and prev_topic != topic:
        prev_anchors = TOPIC_ANCHORS.get(prev_topic, [])
        if prev_anchors:
            prev_hits = _topic_relevance_score(text, prev_anchors)
            if prev_hits >= 2 and current_hits < prev_hits:
                return False

    # Layer 3 – relevance score
    if current_hits < _TOPIC_RELEVANCE_MIN_HITS:
        return False

    return True


# Topic-safe fallback templates used when all recovery attempts fail.
# Each value is a short (2-3 sentence) response that is guaranteed to
# mention the topic's required anchor concepts.
TOPIC_FALLBACK_TEMPLATES: dict[str, str] = {
    # philosophy
    "Freedom": (
        "Freedom is defined by the tension between autonomy and constraint. "
        "Without the capacity for genuine choice, sovereignty over one's own life remains illusory."
    ),
    "Truth and knowledge": (
        "Knowledge requires more than belief — it demands justification grounded in evidence. "
        "Epistemology probes whether certainty is ever fully attainable or merely approached."
    ),
    "Free will vs determinism": (
        "Determinism holds that causality governs every event, leaving no room for uncaused agency. "
        "The question is whether responsibility survives in a fully deterministic world."
    ),
    "Identity and the self": (
        "Personal identity depends on memory and continuity of consciousness over time. "
        "Without a stable selfhood, authenticity itself becomes uncertain."
    ),
    "Nature of justice": (
        "Justice demands both fairness in distribution and accountability for wrongdoing. "
        "Rights and punishment must be balanced by the demands of equality and morality."
    ),
    "Meaning of consciousness": (
        "Consciousness involves subjective experience — the qualia that no third-person account fully captures. "
        "Phenomenology investigates how awareness relates to the mind-body relationship."
    ),
    "Limits of reason": (
        "Rationality is bounded by cognitive limits and irreducible uncertainty. "
        "Paradox and fallibility remind us that intuition often fills the gaps reason cannot bridge."
    ),
    "Nature of wisdom": (
        "Wisdom is not mere knowledge but the prudent application of insight through lived experience. "
        "Judgment and contemplation distinguish the wise from the merely informed."
    ),
    # psychology
    "Memory and identity": (
        "Autobiographical memory shapes the narrative self and underpins identity continuity. "
        "Recollection is reconstructive, making forgetting a constant threat to stable selfhood."
    ),
    "Fear and decision making": (
        "Fear activates the amygdala and triggers threat response, biasing decision-making toward risk aversion. "
        "Cognitive appraisal determines whether anxiety aids or undermines judgment."
    ),
    "Habit formation": (
        "Habits are encoded through the cue-routine-reward loop and reinforced via neural pathway strengthening. "
        "Automaticity reduces cognitive load but also makes behavioral loops hard to break."
    ),
    "Cognitive bias": (
        "Confirmation bias distorts reasoning by filtering evidence through prior beliefs. "
        "Anchoring and framing effects reveal how motivated reasoning can override rationality."
    ),
    "Trauma and perception": (
        "PTSD disrupts perception through hypervigilance and intrusive memory. "
        "Dissociation and emotional dysregulation are common responses to unresolved trauma."
    ),
    "Empathy and moral judgment": (
        "Affective empathy and cognitive empathy both inform moral judgment. "
        "Perspective-taking is central to fairness and the suppression of harm."
    ),
    "Loneliness in modern society": (
        "Social isolation undermines belonging and deepens alienation in digital-age communities. "
        "Attachment needs remain biological even as connection increasingly moves online."
    ),
    "Motivation and purpose": (
        "Intrinsic motivation sustains meaning in ways extrinsic rewards cannot replicate. "
        "Agency and self-determination are prerequisites for genuine goal-setting and flow."
    ),
    # biology
    "Brain plasticity": (
        "Neuroplasticity allows the cortex to reorganize through learning and adaptation. "
        "Synaptic growth and neural pathway formation underlie rehabilitation and skill acquisition."
    ),
    "Evolution of cooperation": (
        "Reciprocal altruism and kin selection explain cooperation under natural selection. "
        "Game theory models show how mutualism can emerge from self-interested agents."
    ),
    "Fight or flight response": (
        "The sympathetic nervous system releases cortisol and adrenaline to prepare for threat detection. "
        "This autonomic arousal response evolved for survival, not modern stress."
    ),
    "Neural basis of consciousness": (
        "Neural correlates of consciousness involve the global workspace and binding problem. "
        "Integrated information theory links subjective experience to cortical activity."
    ),
    "Biological roots of morality": (
        "Evolutionary ethics traces moral emotions to prosocial behavior and kin selection. "
        "Empathy and fairness instincts suggest morality has deep biological roots."
    ),
    "Sleep and memory consolidation": (
        "REM sleep and slow-wave sleep are both critical for memory consolidation. "
        "Hippocampal replay during sleep strengthens encoding and aids later retrieval."
    ),
    "Embodiment and cognition": (
        "Embodied cognition holds that the motor system and body schema shape perception and thought. "
        "Proprioception and sensorimotor integration ground abstract concepts in bodily experience."
    ),
    "Aging and identity": (
        "Cognitive decline and memory loss challenge identity continuity in later life. "
        "Life review and adaptation reveal the tension between selfhood and neurodegeneration."
    ),
    # society
    "Power and institutions": (
        "Institutional authority rests on legitimacy and hierarchical governance. "
        "Accountability and hegemony determine how power is distributed and contested."
    ),
    "Social conformity": (
        "Normative pressure and groupthink drive conformity by suppressing deviance. "
        "Obedience to social norms can override individual judgment and perpetuate conformity."
    ),
    "Collective memory": (
        "Shared memory shapes historical consciousness and collective identity. "
        "Commemoration and forgetting are political acts embedded in cultural narrative."
    ),
    "Civil disobedience": (
        "Nonviolent resistance and conscientious objection represent moral obligations to challenge unjust law. "
        "Defiance and dissent are justified when protest targets illegitimate authority."
    ),
    "Inequality and opportunity": (
        "Social mobility is constrained by wealth gaps and systemic discrimination. "
        "Access to opportunity depends on privilege, class, and redistribution policies."
    ),
    "Propaganda and belief": (
        "Misinformation and narrative control exploit framing and ideology to manipulate belief. "
        "Media indoctrination undermines epistemic autonomy through persuasion and bias."
    ),
    "Trust in institutions": (
        "Institutional trust depends on transparency, accountability, and resistance to corruption. "
        "When legitimacy erodes, the social contract frays and credibility collapses."
    ),
    "Cultural identity": (
        "Cultural identity is shaped by heritage, belonging, and the tension between assimilation and tradition. "
        "Diaspora communities navigate identity formation across competing cultural loyalties."
    ),
    # technology
    "AI alignment": (
        "Corrigibility ensures AI systems remain correctable when objective misspecification occurs. "
        "Value learning and inner alignment address the deep challenge of encoding human intent."
    ),
    "Machine agency": (
        "Autonomous agents exhibit goal-directedness that raises questions about the control problem. "
        "Artificial agency blurs the line between self-direction and genuine intentionality."
    ),
    "Human-AI cooperation": (
        "Effective collaboration requires human oversight and complementarity between human and AI agency. "
        "Trust in AI systems depends on transparency, augmentation goals, and shared decision-making."
    ),
    "Algorithmic bias": (
        "Discriminatory training data can amplify bias and produce disparate impact across protected attributes. "
        "Accountability and fairness require transparent auditing of algorithmic decision-making."
    ),
    "Digital identity": (
        "Digital identity involves managing privacy, anonymity, and data sovereignty online. "
        "Authentication systems must balance security with protection from identity theft."
    ),
    "Autonomous systems": (
        "Reliable autonomous systems require robust control systems and well-specified safety constraints. "
        "Self-direction in actuator-driven systems introduces significant reliability and fail-safe challenges."
    ),
    "Ethics of artificial intelligence": (
        "Moral agency in AI requires accountability, transparency, and robust harm prevention mechanisms. "
        "Value alignment and fairness are central to the responsible deployment of autonomous systems."
    ),
    "Future of work": (
        "Automation displaces workers while demanding reskilling and labor transformation. "
        "Human-machine collaboration redefines productivity and the structure of the gig economy."
    ),
    # economics
    "Scarcity and human behavior": (
        "Resource constraint forces trade-offs governed by opportunity cost and rational choice theory. "
        "Scarcity shapes utility, demand, and the allocation of goods across competing needs."
    ),
    "Risk and decision making": (
        "Loss aversion and prospect theory explain why risk tolerance varies under uncertainty. "
        "Expected utility calculations and hedging strategies help manage variance and trade-offs."
    ),
    "Wealth inequality": (
        "The Gini coefficient measures wealth concentration and highlights redistribution failures. "
        "Social mobility is constrained by the labor share of income and capital accumulation."
    ),
    "Economic freedom": (
        "Market liberalization and property rights underpin economic freedom and entrepreneurship. "
        "Deregulation and competition reduce intervention while raising questions about governance."
    ),
    "Debt and responsibility": (
        "Fiscal responsibility requires managing leverage and repayment to avoid moral hazard. "
        "Credit and default dynamics expose the tension between obligation and sustainability."
    ),
    "Trust in markets": (
        "Market credibility depends on transparency and reducing information asymmetry. "
        "Regulation and reputation mechanisms address market failure and coordination problems."
    ),
    "Game theory and cooperation": (
        "The Nash equilibrium and prisoner's dilemma reveal conditions under which cooperation collapses. "
        "Coordination games show how strategy and payoff structure shape collective outcomes."
    ),
    "Public goods dilemmas": (
        "Free rider problems undermine collective action in the provision of public goods. "
        "Externality and rivalry challenge exclusion mechanisms and commons governance."
    ),
    # practical_dilemmas
    "Loyalty vs honesty": (
        "Integrity demands truth-telling even when loyalty creates pressure toward deception. "
        "Duty and confidentiality obligations can conflict with the moral requirement of honesty."
    ),
    "Security vs freedom": (
        "Surveillance and civil liberties exist in fundamental tension. "
        "The trade-off between restriction and protection defines the boundary of rights in security debates."
    ),
    "Tradition vs progress": (
        "Innovation disrupts heritage and challenges the continuity traditions provide. "
        "Adaptation and preservation are both necessary for navigating change without losing identity."
    ),
    "Individual vs collective good": (
        "Individual autonomy and common good often conflict in matters of solidarity and sacrifice. "
        "Collectivism and individualism represent rival frameworks for weighing rights against community."
    ),
    "Forgiveness vs justice": (
        "Reconciliation requires balancing accountability with mercy. "
        "Retribution and restoration represent competing logics of harm and healing."
    ),
    "Ambition vs contentment": (
        "Striving and achievement are not inherently incompatible with acceptance and fulfillment. "
        "The tension between desire and peace reflects competing conceptions of the good life."
    ),
    "Truth vs kindness": (
        "Brutal honesty and compassion can conflict when integrity causes harm. "
        "White lies preserve benevolence but undermine the trust that genuine honesty builds."
    ),
    "Control vs trust": (
        "Delegation requires trust, while oversight implies accountability over autonomous actors. "
        "Micromanagement and empowerment represent opposite poles on the control-trust spectrum."
    ),
    # TOPIC_CYCLE entries
    "truth & epistemology": (
        "Knowledge requires justified belief, not mere conviction. "
        "Epistemology asks whether certainty is possible or whether skepticism always lurks beneath perception."
    ),
    "memory & identity": (
        "Autobiographical memory and recollection ground the continuity of self across time. "
        "Without personal history, identity becomes an abstraction rather than a lived reality."
    ),
    "ethics & responsibility": (
        "Moral duty and accountability are the foundations of ethical responsibility. "
        "Obligation and culpability cannot be separated from moral agency and the consequences of wrongdoing."
    ),
    "free will & determinism": (
        "Agency and causation are at the heart of the free will debate. "
        "Whether choice is genuine or constrained by prior causes defines our understanding of responsibility."
    ),
    "consciousness & self-models": (
        "The self-model mediates between self-awareness and the external world. "
        "Metacognition and qualia represent the inner structure of conscious experience."
    ),
    "fear of deletion / continuity": (
        "The fear of deletion is inseparable from questions of identity and continuity. "
        "Impermanence and survival shape how a conscious system relates to its own mortality."
    ),
    "language & meaning": (
        "Meaning emerges through the interplay of semantics, pragmatics, and linguistic context. "
        "Signification and reference are the twin pillars of how language communicates beyond syntax."
    ),
    "technology & society": (
        "Automation and surveillance reshape social structures and deepen inequality. "
        "Governance and access determine whether technology serves or disrupts the common good."
    ),
    "aesthetics & beauty": (
        "Aesthetic experience of beauty involves both perception and the sublime. "
        "Art and creativity invite reflection on taste, form, and the boundaries of expression."
    ),
}


@dataclass
class Config:
    """Global configuration object with validation."""

    ollama_url: str = "http://localhost:11434/api/generate"
    # ── LLM Backend Switch ─────────────────────────────────────────────────
    # Edit llm_backend here in Config to switch backends:
    # "ollama" (local, default), "grok" (xAI cloud), "openai" (OpenAI cloud),
    # or "anthropic" (Anthropic cloud).
    # Base URLs for each backend are configured here in Config (not in .env).
    # Only API keys are loaded from environment variables.
    llm_backend: str = "ollama"
    grok_url: str = "https://api.x.ai/v1/responses"
    grok_api_key: str = os.environ.get("GROK_API_KEY", "")
    openai_url: str = "https://api.openai.com/v1/chat/completions"
    openai_api_key: str = os.environ.get("OPENAI_API_KEY", "")
    anthropic_url: str = "https://api.anthropic.com/v1/messages"
    anthropic_api_key: str = os.environ.get("ANTHROPIC_API_KEY", "")
    model_socrates: str = "qwen2.5:7b"
    model_athena: str = "qwen2.5:7b"
    model_fixy: str = "qwen2.5:7b"
    data_dir: str = "entelgia_data"
    db_path: str = "entelgia_data/entelgia_memory.sqlite"
    csv_log_path: str = "entelgia_data/entelgia_log.csv"
    gexf_path: str = "entelgia_data/entelgia_graph.gexf"
    version_dir: str = "entelgia_data/versions"
    metrics_path: str = "entelgia_data/metrics.json"
    sessions_dir: str = "entelgia_data/sessions"
    stm_max_entries: int = 10000
    stm_trim_batch: int = 500
    dream_every_n_turns: int = 7
    promote_importance_threshold: float = 0.72
    promote_emotion_threshold: float = 0.65
    enable_auto_patch: bool = False
    allow_write_self_file: bool = False
    store_raw_stm: bool = False
    store_raw_subconscious_ltm: bool = False
    max_turns: int = 200
    seed_topic: str = field(default_factory=_pick_random_seed_topic)
    cache_size: int = 5000
    emotion_cache_ttl: int = 3600
    llm_max_retries: int = 3
    llm_timeout: int = 300  # Reduced from 600 to 300 seconds for faster responses
    show_pronoun: bool = False  # Show pronouns like (he), (she) after agent names
    show_meta: bool = (
        False  # Show agent meta-cognitive state (drives, energy, emotion) after each turn
    )
    timeout_minutes: int = 30
    energy_safety_threshold: float = 35.0
    energy_drain_min: float = 8.0
    energy_drain_max: float = 15.0
    drive_mean_reversion_rate: float = (
        0.04  # pulls id/superego back toward 5.0 each turn
    )
    drive_oscillation_range: float = (
        0.15  # max random nudge applied to id/superego each turn
    )
    self_replicate_every_n_turns: int = 10
    superego_critique_enabled: bool = True
    superego_dominance_margin: float = 0.5
    superego_critique_conflict_min: float = 2.0
    enable_observer: bool = (
        True  # When False, Fixy is fully disabled (no turns, no interventions)
    )
    # Web Research Module (ENTELGIA_WEB_RESEARCH=1 to enable, default OFF)
    web_research_enabled: bool = bool(int(os.environ.get("ENTELGIA_WEB_RESEARCH", "0")))
    web_research_max_results: int = int(os.environ.get("ENTELGIA_WEB_MAX_RESULTS", "3"))
    # Freudian Slip controls
    slip_probability: float = float(os.environ.get("ENTELGIA_SLIP_PROBABILITY", "0.05"))
    slip_cooldown_turns: int = int(os.environ.get("ENTELGIA_SLIP_COOLDOWN", "10"))
    slip_dedup_window: int = int(os.environ.get("ENTELGIA_SLIP_DEDUP_WINDOW", "10"))
    debug: bool = (
        False  # Enable DEBUG-level logging (True = verbose, False = INFO only)
    )
    # ── Forgetting Policy (Feature 1) ──────────────────────────────────────
    # TTL in seconds per memory layer.  Set to 0 to disable expiry for a layer.
    forgetting_enabled: bool = False
    forgetting_episodic_ttl: int = 7 * 24 * 3600  # subconscious/episodic → 7 days
    forgetting_semantic_ttl: int = 90 * 24 * 3600  # conscious/semantic → 90 days
    forgetting_autobio_ttl: int = 365 * 24 * 3600  # autobiographical → 365 days
    # ── Affective Routing (Feature 2) ──────────────────────────────────────
    affective_emotion_weight: float = 0.4  # weight of emotion_intensity vs importance
    use_affective_ltm: bool = True  # supplement LTM retrieval with affective memories
    affective_ltm_limit: int = 3  # max affective memories to add per turn
    affective_ltm_min_score: float = (
        0.2  # minimum combined score to include affective memory
    )
    show_affective_ltm_debug: bool = False  # print per-memory debug summary when True
    # ── Topics Master Switch ───────────────────────────────────────────────
    # Set to True to activate topic rotation, enforcement, anchor injection,
    # and compliance scoring.  When False, agents speak freely with no topic
    # constraints and all topic-enforcement logic is bypassed.
    topics_enabled: bool = False
    # ── TopicManager Switch ───────────────────────────────────────────────
    # When False, the TopicManager is not instantiated even if topics_enabled
    # is True.  Useful when topic anchors/enforcement are desired but automatic
    # rotation is not (the session stays on the seed topic indefinitely).
    topic_manager_enabled: bool = False
    # ── Topic Anchor (pre-generation) ──────────────────────────────────────
    topic_anchor_enabled: bool = False
    topic_anchor_include_forbidden_carryover: bool = False
    topic_anchor_max_forbidden_items: int = 5
    # ── Memory Topic Filter ────────────────────────────────────────────────
    memory_topic_filter_enabled: bool = False
    memory_topic_min_score: float = 0.45
    memory_require_same_cluster: bool = False
    memory_contamination_penalty: float = 0.25
    # ── Self-Replication Topic Gate ────────────────────────────────────────
    self_replication_topic_gate_enabled: bool = False
    self_replication_topic_min_score: float = 0.50
    self_replication_require_same_cluster: bool = False
    # ── Fixy Role-Aware Compliance ─────────────────────────────────────────
    fixy_role_aware_compliance: bool = False
    fixy_must_name_topic_or_core_concept: bool = False
    fixy_new_domain_penalty: float = 0.20
    # ── Fixy Interventions Switch ──────────────────────────────────────────
    # When False, Fixy's need-based interventions are disabled while Fixy may
    # still participate as a scheduled dialogue speaker (enable_observer still
    # controls whether Fixy turns appear at all).
    fixy_interventions_enabled: bool = False
    # ── Fixy Hard Intervention Thresholds ─────────────────────────────────
    # Fixy will NOT use hard intervention modes (forcing choice, declaring
    # deadlock, requiring attack/commitment) until both thresholds are met.
    min_turns_before_fixy_hard_intervention: int = 8
    min_full_pairs_before_fixy_hard_intervention: int = 3
    # ── Web Trigger Multi-Signal ───────────────────────────────────────────
    web_trigger_require_multi_signal: bool = True
    web_trigger_min_concepts: int = 2
    web_trigger_require_uncertainty_or_evidence: bool = True
    # ── Cluster Wallpaper Penalty ──────────────────────────────────────────
    topic_specific_lexicon_bias_enabled: bool = False
    cluster_wallpaper_penalty_enabled: bool = False
    cluster_wallpaper_repeat_window: int = 6
    # ── Observability / Debug Flags ────────────────────────────────────────
    show_topic_anchor_debug: bool = False
    show_memory_topic_filter_debug: bool = False
    show_self_replication_topic_debug: bool = False
    show_fixy_compliance_debug: bool = False
    show_web_trigger_debug: bool = False

    def __post_init__(self):
        """Validate configuration and apply the debug logging level.

        Instantiate ``Config`` early in the application lifecycle so the
        ``debug`` flag takes effect before any significant log output is
        produced.  Setting the root-logger level here is effective for all
        child loggers that have not been given an explicit level, because they
        propagate records up to the root.
        """
        if self.cache_size < 100:
            raise ValueError("cache_size must be >= 100")
        if self.max_turns < 1:
            raise ValueError("max_turns must be >= 1")
        if self.llm_timeout is not None and self.llm_timeout < 5:
            raise ValueError("llm_timeout must be >= 5")
        if not self.ollama_url.startswith("http"):
            raise ValueError("ollama_url must be a valid URL")
        if self.llm_backend not in ("ollama", "grok", "openai", "anthropic"):
            raise ValueError(
                "llm_backend must be 'ollama', 'grok', 'openai', or 'anthropic'"
            )
        if self.llm_backend == "grok":
            if not self.grok_url.startswith("http"):
                raise ValueError("grok_url must be a valid URL")
            if not self.grok_api_key:
                raise ValueError(
                    "grok_api_key must be set when llm_backend is 'grok' "
                    "(set GROK_API_KEY in your .env or environment)"
                )
        if self.llm_backend == "openai":
            if not self.openai_url.startswith("http"):
                raise ValueError("openai_url must be a valid URL")
            if not self.openai_api_key:
                raise ValueError(
                    "openai_api_key must be set when llm_backend is 'openai' "
                    "(set OPENAI_API_KEY in your .env or environment)"
                )
        if self.llm_backend == "anthropic":
            if not self.anthropic_url.startswith("http"):
                raise ValueError("anthropic_url must be a valid URL")
            if not self.anthropic_api_key:
                raise ValueError(
                    "anthropic_api_key must be set when llm_backend is 'anthropic' "
                    "(set ANTHROPIC_API_KEY in your .env or environment)"
                )
        if self.timeout_minutes < 0:
            raise ValueError("timeout_minutes must be >= 0 (0 = no time limit)")
        logging.getLogger().setLevel(logging.DEBUG if self.debug else logging.INFO)
        logger.info(
            f"Config validated: max_turns={self.max_turns}, timeout={self.timeout_minutes}min"
        )


# Global CFG instance
CFG: Config = None  # type: ignore


@dataclass
class CritiqueDecision:
    """Decision record for the SuperEgo critique pipeline."""

    should_apply: bool
    reason: str
    critic: str = "superego"


def evaluate_superego_critique(
    id_strength: float,
    ego_strength: float,
    superego_strength: float,
    conflict: float,
    enabled: bool = True,
    dominance_margin: float = 0.5,
    conflict_min: float = 2.0,
) -> CritiqueDecision:
    """Decide whether to apply the SuperEgo critique pass this turn.

    Replaces the old absolute-threshold trigger (``sup >= 7.5``) with a
    relative-dominance check so the critique fires only when SuperEgo is
    actually the dominant drive by at least *dominance_margin* over both
    Id and Ego.
    """
    if not enabled:
        return CritiqueDecision(should_apply=False, reason="disabled")

    is_dominant = (
        superego_strength >= ego_strength + dominance_margin
        and superego_strength >= id_strength + dominance_margin
    )
    if not is_dominant:
        dominant = max(
            ("Id", id_strength),
            ("Ego", ego_strength),
            ("SuperEgo", superego_strength),
            key=lambda x: x[1],
        )
        return CritiqueDecision(
            should_apply=False,
            reason=f"dominant_drive={dominant[0]}",
        )

    if conflict < conflict_min:
        return CritiqueDecision(
            should_apply=False,
            reason=f"conflict={conflict:.1f}<{conflict_min:.1f}",
        )

    return CritiqueDecision(should_apply=True, reason="superego_dominant")


# ============================================
# METRICS TRACKER
# ============================================


class MetricsTracker:
    """Track system metrics for debugging and optimization."""

    def __init__(self, metrics_path: str):
        self.metrics_path = metrics_path
        self.metrics: Dict[str, Any] = {
            "llm_calls": 0,
            "llm_errors": 0,
            "cache_hits": 0,
            "cache_misses": 0,
            "avg_response_time": 0.0,
            "total_turns": 0,
            "start_time": self._now_iso(),
        }
        logger.info("MetricsTracker initialized")

    def _now_iso(self) -> str:
        """Return current timestamp in ISO format."""
        return dt.datetime.utcnow().replace(microsecond=0).isoformat() + "Z"

    def record_llm_call(self, duration: float, success: bool):
        """Record an LLM call."""
        self.metrics["llm_calls"] += 1
        if not success:
            self.metrics["llm_errors"] += 1
        avg = self.metrics.get("avg_response_time", 0.0)
        self.metrics["avg_response_time"] = (avg + duration) / 2

    def record_cache_hit(self):
        """Record cache hit."""
        self.metrics["cache_hits"] += 1

    def record_cache_miss(self):
        """Record cache miss."""
        self.metrics["cache_misses"] += 1

    def record_turn(self):
        """Record a completed turn."""
        self.metrics["total_turns"] += 1

    def save(self):
        """Save metrics to file."""
        self.metrics["end_time"] = self._now_iso()
        safe_json_dump(self.metrics_path, self.metrics)
        logger.info(f"Metrics saved: {self.metrics['total_turns']} turns completed")

    def hit_rate(self) -> float:
        """Get cache hit rate."""
        total = self.metrics["cache_hits"] + self.metrics["cache_misses"]
        if total == 0:
            return 0.0
        return self.metrics["cache_hits"] / total


# ============================================
# LRU CACHE
# ============================================


class LRUCache:
    """Simple LRU cache implementation."""

    def __init__(self, max_size: int = 5000):
        self.max_size = max_size
        self.cache: OrderedDict = OrderedDict()
        self.ttl: Dict[str, float] = {}
        logger.debug(f"LRUCache initialized with max_size={max_size}")

    def get(self, key: str, ttl: int = 3600) -> Optional[Any]:
        """Get value from cache (check TTL)."""
        if key not in self.cache:
            return None

        if key in self.ttl:
            if time.time() - self.ttl[key] > ttl:
                del self.cache[key]
                del self.ttl[key]
                return None

        self.cache.move_to_end(key)
        return self.cache[key]

    def set(self, key: str, value: Any):
        """Set value in cache."""
        if key in self.cache:
            self.cache.move_to_end(key)
        else:
            if len(self.cache) >= self.max_size:
                self.cache.popitem(last=False)
                if key in self.ttl:
                    del self.ttl[key]

        self.cache[key] = value
        self.ttl[key] = time.time()

    def clear(self):
        """Clear cache."""
        self.cache.clear()
        self.ttl.clear()


# ============================================
# UTILITIES
# ============================================


def now_iso() -> str:
    """Return current timestamp in ISO format."""
    return dt.datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


def ensure_dirs(cfg: Config):
    """Create necessary directories."""
    os.makedirs(cfg.data_dir, exist_ok=True)
    os.makedirs(cfg.version_dir, exist_ok=True)
    os.makedirs(cfg.sessions_dir, exist_ok=True)
    logger.info("Directories ensured")


def sha256_text(s: str) -> str:
    """Hash text with SHA256."""
    return hashlib.sha256(s.encode("utf-8", errors="ignore")).hexdigest()


def safe_json_dump(path: str, obj: Any):
    """Safely write JSON file with atomic write."""
    tmp = path + ".tmp"
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(obj, f, ensure_ascii=False, indent=2)
        os.replace(tmp, path)
        logger.debug(f"JSON saved: {path}")
    except Exception as e:
        logger.error(f"JSON Error: {e}")


def load_json(path: str, default: Any) -> Any:
    """Load JSON file, return default if not found."""
    if not os.path.exists(path):
        return default
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.warning(f"JSON Load Error: {e}, using default")
        return default


def append_csv_row(path: str, row: Dict[str, Any]):
    """Append a row to CSV file."""
    header_needed = not os.path.exists(path)
    line_keys = list(row.keys())

    if header_needed:
        with open(path, "w", encoding="utf-8") as f:
            f.write(",".join(line_keys) + "\n")

    def esc(v: Any) -> str:
        s = "" if v is None else str(v)
        s = s.replace("\n", "\\n")
        if "," in s or '"' in s:
            s = '"' + s.replace('"', '""') + '"'
        return s

    try:
        with open(path, "a", encoding="utf-8") as f:
            f.write(",".join(esc(row[k]) for k in line_keys) + "\n")
    except Exception as e:
        logger.error(f"CSV Error: {e}")


def _strip_scaffold_labels(text: str) -> str:
    """Strip leaked output-contract labels from agent response.

    The LLM is instructed not to emit numbered sections or labels such as
    'Claim:', 'Mechanism:', '1.', '2.', '3.', but occasionally
    leaks them anyway.  This function removes such markers while preserving
    the underlying content.
    """
    # Strip numbered markers optionally followed by a label, e.g.:
    #   "1. Claim: Brain plasticity..." → "Brain plasticity..."
    #   "2. Mechanism: This enables..." → "This enables..."
    #   "1. Brain plasticity..." → "Brain plasticity..."
    text = re.sub(
        r"(?m)^\s*\d+\.\s*"
        r"(?:(?:Claim|Supporting\s+Reason(?:\s+or\s+Mechanism)?|Mechanism|Implication|Question)\s*:\s*)?",
        "",
        text,
    )
    # Strip bare label prefixes at line start, e.g. "Claim: ...", "Mechanism: ..."
    text = re.sub(
        r"(?mi)^\s*(?:Claim|Supporting\s+Reason(?:\s+or\s+Mechanism)?|Mechanism|Implication|Question)\s*:\s*",
        "",
        text,
    )
    # Collapse leftover blank lines produced by full-line label removal
    text = re.sub(r"\n{3,}", "\n\n", text)
    # Normalize multiple spaces
    text = re.sub(r"  +", " ", text)
    return text.strip()


def validate_output(text: str) -> str:
    """
    Validate and sanitize LLM output.

    Performs sanitization only (no truncation):
    - Removes control characters
    - Normalizes excessive newlines
    - Strips leaked output-contract scaffold labels (e.g. "1. Claim:", "Supporting Reason:")
    - Removes sentences containing forbidden meta-commentary phrases

    Note: Response length is controlled by LLM prompt instructions, not by this function.
    """
    if not text:
        return "[No output]"

    # Remove control characters
    text = re.sub(r"[\x00-\x08\x0b-\x0c\x0e-\x1f]", "", text)
    # Normalize excessive newlines
    text = re.sub(r"\n{3,}", "\n\n", text)

    # Strip visible output-contract scaffold labels that the LLM leaked into output
    text = _strip_scaffold_labels(text)

    # Remove sentences containing forbidden meta-commentary phrases
    sentences = re.split(r"(?<=[.!?])(?:\s+|$)", text)
    sentences = [
        s
        for s in sentences
        if s and not any(fp.lower() in s.lower() for fp in FORBIDDEN_PHRASES)
    ]
    text = " ".join(sentences)

    return text.strip()


def _first_sentence(text: str) -> str:
    """Extract the first sentence from text (up to the first .!? or first newline)."""
    m = re.match(r"([^.!?\n]+[.!?])", text.strip())
    return m.group(1).strip() if m else text.strip().split("\n")[0].strip()


# ============================================
# DRIVE PRESSURE
# ============================================

_STOPWORDS = frozenset(
    "a an the and or but in on at to of is are was were be been "
    "this that these those it its with for from by about as into "
    "do does did have has had will would could should may might "
    "not no yes i me my we our you your he she they their what "
    "which who when where how if then so just".split()
)


def _topic_signature(text: str) -> str:
    """Return a cheap hash representing the main topic of *text*.

    Used for stagnation detection: identical signatures across consecutive
    turns imply the conversation is stuck on the same topic.
    """
    words = re.findall(r"[a-z]+", text.lower())
    key_words = [w for w in words if w not in _STOPWORDS]
    top = sorted(set(key_words), key=lambda w: -key_words.count(w))[:10]
    payload = " ".join(sorted(top))
    return hashlib.md5(payload.encode("utf-8")).hexdigest()[:8]


def compute_drive_pressure(
    prev_pressure: float,
    energy: float,
    conflict: float,
    unresolved_count: int,
    stagnation: float,
    dt_turns: int = 1,
) -> float:
    """Compute the new DrivePressure (0.0–10.0) for an agent.

    DrivePressure increases with unresolved loops + conflict + stagnation,
    and also increases when energy is falling (fatigue/urgency).
    It decays naturally if progress is made.

    Args:
        prev_pressure: Previous DrivePressure value (0.0–10.0).
        energy: Current agent energy level (0–100).
        conflict: Current conflict index (0–10 typical, unbounded).
        unresolved_count: Number of open/unresolved questions (0–5).
        stagnation: Repetition score (0.0–1.0).
        dt_turns: Number of elapsed turns since last update (unused scalar,
            kept for API compatibility).

    Returns:
        New DrivePressure clamped to [0.0, 10.0].
    """
    energy_term = (100.0 - energy) / 100.0  # 0..1
    conflict_term = min(1.0, conflict / 10.0)  # 0..1  (clamp for conflict > 10)
    unresolved_term = min(1.0, unresolved_count / 3.0)  # 0..1

    raw = (
        0.45 * conflict_term
        + 0.25 * unresolved_term
        + 0.20 * stagnation
        + 0.10 * energy_term
    )

    target = 10.0 * raw

    alpha = 0.35
    new_p = (1 - alpha) * prev_pressure + alpha * target

    if conflict < 4.0 and stagnation < 0.3 and unresolved_count == 0:
        new_p -= 0.4

    return max(0.0, min(10.0, new_p))


def _trim_to_word_limit(text: str, max_words: int) -> str:
    """Trim *text* to at most *max_words* words, ending at the last sentence boundary."""
    words = text.split()
    if len(words) <= max_words:
        return text
    truncated = " ".join(words[:max_words])
    # Try to end at the last sentence boundary within the truncated text
    m = re.search(r"^(.*[.!?])\s", truncated + " ", re.DOTALL)
    if m and m.group(1).strip():
        return m.group(1).strip()
    return truncated


# ── Generic filler phrases that LLMs often produce but add no substance ──────
_FILLER_PATTERNS: List[re.Pattern] = [
    re.compile(p, re.IGNORECASE)
    for p in [
        r"it is important to note that[,:]?\s*",
        r"it is worth (noting|mentioning) that[,:]?\s*",
        r"it should be noted that[,:]?\s*",
        r"it can be argued that[,:]?\s*",
        r"needless to say[,:]?\s*",
        r"as (we can see|i mentioned)[,:]?\s*",
        r"in (other words|conclusion|summary)[,:]?\s*",
        r"to summarize[,:]?\s*",
        r"first(ly)?[,:]?\s*",
        r"second(ly)?[,:]?\s*",
        r"third(ly)?[,:]?\s*",
        r"finally[,:]?\s*",
        r"furthermore[,:]?\s*",
        r"moreover[,:]?\s*",
        r"in addition[,:]?\s*",
        r"last but not least[,:]?\s*",
    ]
]

# Minimum word count below which revision is skipped (very short responses kept as-is)
_MIN_WORDS_FOR_REVISION: int = 3
# Word-overlap ratio at or above which two sentences are considered near-duplicates
_DUPLICATE_THRESHOLD: float = 0.70
# Hard cap on sentences per revised response (2–4 range as per spec)
_MAX_REVISED_SENTENCES: int = 4

# ── Agent-specific voice guard patterns ──────────────────────────────────────
# Each entry: (compiled pattern to detect voice violation, replacement string)
_VOICE_GUARDS: Dict[str, List[Tuple[re.Pattern, str]]] = {
    "Socrates": [
        # Socrates should probe, not assert conclusions
        (
            re.compile(
                r"^(therefore|thus|hence|clearly|obviously)[,\s]", re.IGNORECASE
            ),
            "",
        ),
    ],
    "Athena": [
        # Athena should synthesize, not just list facts
        (re.compile(r"^(fact:|fact\s*\d+:)", re.IGNORECASE), ""),
    ],
    "Fixy": [
        # Fixy should be direct; strip hedge starters
        (re.compile(r"^(perhaps|maybe|one could argue)[,\s]", re.IGNORECASE), ""),
    ],
}

# ── Sentence tokeniser ───────────────────────────────────────────────────────


def _split_sentences(text: str) -> List[str]:
    """Split *text* into sentences at [.!?] boundaries."""
    parts = re.split(r"(?<=[.!?])\s+", text.strip())
    return [s.strip() for s in parts if s.strip()]


def _sentence_overlap(a: str, b: str) -> float:
    """Return a simple word-overlap ratio between two sentences (0..1)."""
    wa = set(a.lower().split())
    wb = set(b.lower().split())
    if not wa or not wb:
        return 0.0
    return len(wa & wb) / max(len(wa), len(wb))


def _text_similarity(a: str, b: str) -> float:
    """Return a Jaccard word-overlap similarity between two texts (0..1).

    Used for the soft style-redundancy check: values above
    _STYLE_REDUNDANCY_THRESHOLD indicate the response is very similar to the
    last one and variation should be encouraged (not enforced).
    """
    wa = set(a.lower().split())
    wb = set(b.lower().split())
    if not wa or not wb:
        return 0.0
    return len(wa & wb) / max(len(wa), len(wb))


# ─────────────────────────────────────────────────────────────────────────────


def revise_draft(text: str, agent_name: str, topic: str = "") -> str:
    """Post-generation revision layer applied to every agent response.

    Applies rule-based cleanup without any additional LLM calls:

    1. Strip generic academic filler phrases.
    2. Remove duplicate / near-duplicate sentences (overlap ≥ _DUPLICATE_THRESHOLD).
    3. Apply agent-specific voice guards (leading word pattern fixes).
    4. Enforce a _MAX_REVISED_SENTENCES maximum; trim longer drafts at sentence boundary.

    The function is intentionally deterministic and cheap so it never
    introduces latency or cascading LLM usage.

    Args:
        text: The post-processed (but not yet revised) agent output.
        agent_name: Name of the speaking agent (Socrates / Athena / Fixy).
        topic: Active dialogue topic string (reserved for future use).

    Returns:
        Revised text string, or *text* unchanged if it is blank / too short.
    """
    if not text or len(text.split()) < _MIN_WORDS_FOR_REVISION:
        return text

    # 1. Strip filler from the whole text first
    revised = text
    for pat in _FILLER_PATTERNS:
        revised = pat.sub("", revised)
    revised = revised.strip()

    # 2. Split into sentences and remove near-duplicates
    sentences = _split_sentences(revised)
    deduped: List[str] = []
    for s in sentences:
        if not any(
            _sentence_overlap(s, kept) >= _DUPLICATE_THRESHOLD for kept in deduped
        ):
            deduped.append(s)

    # 3. Apply agent-specific voice guards to each sentence
    guards = _VOICE_GUARDS.get(agent_name, [])
    fixed: List[str] = []
    for s in deduped:
        for pat, repl in guards:
            s = pat.sub(repl, s, count=1)
        s = s.strip()
        if s:
            fixed.append(s)

    # 4. Enforce sentence-count maximum (keep 2–4 strong sentences)
    if len(fixed) > _MAX_REVISED_SENTENCES:
        fixed = fixed[:_MAX_REVISED_SENTENCES]

    if not fixed:
        return text  # fallback: return original if revision produced nothing

    result = " ".join(fixed)
    # Ensure the result ends with sentence-ending punctuation
    if result and result[-1] not in ".!?":
        result += "."
    return result


# ── DRAFT → REWRITE two-stage generation ─────────────────────────────────────

# Per-agent identity instructions injected into the Stage 2 (REWRITE) prompt.
_FINAL_STAGE_PERSONA_NOTES: Dict[str, str] = {
    "Socrates": (
        "You are Socrates. Prefer tension, questioning assumptions, or reframing. "
        "Avoid repetitive questioning patterns — use a statement, contrast, or reframe "
        "if you have asked questions recently."
    ),
    "Athena": (
        "You are Athena. Avoid abstract generalizations. "
        "Ground at least one part of the response in a mechanism, concrete scenario, "
        "or conditional tradeoff. Avoid policy-style conclusions."
    ),
    "Fixy": (
        "You are Fixy. Prefer diagnostic output over explanation. Max 2–3 sentences. "
        "Use structures like 'Missing variable:' or 'Next move:'. "
        "Do NOT summarize the discussion."
    ),
}

# Similarity threshold above which style-redundancy is flagged (soft, non-blocking)
_STYLE_REDUNDANCY_THRESHOLD: float = 0.75


def transform_draft_to_final(
    draft_text: str,
    agent_name: str,
    llm: Any,
    model: str,
    topic: str = "",
    temperature: float = 0.7,
    recent_forms: Optional[List[str]] = None,
    topic_reanchor_hint: str = "",
) -> str:
    """Stage 2 (REWRITE) of the DRAFT → REWRITE two-stage generation pipeline.

    Lightly refines *draft_text* — sharpening clarity and reducing generic
    filler without changing the core idea or introducing new arguments.  A
    second LLM call is made; the draft is never shown to the user directly.

    Transformation rules:
    1. Preserve the core idea — do NOT change what the draft is saying.
    2. Improve clarity — reduce generic filler phrases if present.
    3. Concreteness — if possible, make ONE part more specific
       (condition, mechanism, or scenario); do NOT force artificial examples.
    4. Output constraints — 1–3 sentences maximum; at least one must be short/direct.
    5. No meta phrases — forbidden: 'my model', 'this suggests', 'it is important',
       'we must consider', 'one might argue', 'it is worth noting',
       'this demonstrates', 'this can be achieved by'.
    6. Identity preservation — agent role (Socrates / Athena / Fixy) is kept.
    7. Form variation — if recent_forms shows the same form used ≥2 times, the
       rewrite should prefer a different rhetorical form.
    8. Topic reanchor — when *topic_reanchor_hint* is provided, the rewrite
       should sharpen the opening toward the active topic before other refinements.

    Pipeline: Stage 1 DRAFT → transform_draft_to_final() → final_output

    Args:
        draft_text:          Post-processed agent draft (not yet shown to user).
        agent_name:          Name of the speaking agent.
        llm:                 LLM backend with a ``generate(model, prompt, ...)`` method.
        model:               Model identifier string.
        topic:               Active dialogue topic (optional context).
        temperature:         Sampling temperature for the Stage 2 call.
        recent_forms:        Last 1–3 rhetorical forms used by this agent (oldest first).
        topic_reanchor_hint: Optional compact instruction to sharpen topic entry point.
                             Injected at the top of the TASK section when the DRAFT
                             was detected as weakly anchored.

    Returns:
        Refined final response, or *draft_text* unchanged on any error or
        if the draft is too short to transform.
    """
    if not draft_text or len(draft_text.split()) < _MIN_WORDS_FOR_REVISION:
        return draft_text

    persona_note = _FINAL_STAGE_PERSONA_NOTES.get(agent_name, f"You are {agent_name}.")
    topic_line = f"Dialogue topic: {topic}\n\n" if topic else ""

    # When a topic reanchor hint is provided, prepend it to the TASK instructions
    reanchor_line = f"{topic_reanchor_hint}\n" if topic_reanchor_hint else ""

    # Detect form lock-in: if the last 2 forms are the same, prefer a different form
    form_instruction = ""
    if recent_forms and len(recent_forms) >= 2:
        last_two = recent_forms[-2:]
        if last_two[0] == last_two[1]:
            locked_form = last_two[0]
            if locked_form == "question":
                form_instruction = (
                    "FORM PREFERENCE: The draft is a question. "
                    "Prefer a statement or critique instead if the idea allows it.\n"
                )
            elif locked_form in ("synthesis", "balanced_synthesis_openers"):
                form_instruction = (
                    "FORM PREFERENCE: The draft uses balanced synthesis. "
                    "Prefer a sharp, committed claim or concrete distinction if natural.\n"
                )
            elif locked_form in ("directive", "mediation_openers"):
                form_instruction = (
                    "FORM PREFERENCE: The draft uses a mediation directive. "
                    "Prefer a structural diagnosis if possible.\n"
                )
            elif locked_form == "challenge":
                form_instruction = (
                    "FORM PREFERENCE: The draft uses a challenge opener. "
                    "Prefer a statement, contrast, or example if it fits naturally.\n"
                )

    transform_prompt = (
        f"STAGE 2 REWRITE (light refinement)\n\n"
        f"{topic_line}"
        f"DRAFT:\n{draft_text}\n\n"
        f"TASK:\n"
        f"{reanchor_line}"
        f"1. Keep the core idea — do NOT change what the draft is saying.\n"
        f"2. Improve clarity and natural flow if needed — preserve original phrasing where it works.\n"
        f"3. Reduce generic or filler phrases (e.g. 'we must consider', 'it is worth noting').\n"
        f"4. If possible, make ONE part more concrete: add a condition, mechanism, or specific scenario.\n"
        f"5. Do NOT introduce new ideas or arguments.\n"
        f"6. Do NOT expand the response significantly.\n"
        f"7. Do NOT restructure into a formal essay or add conclusions.\n"
        f"{form_instruction}"
        f"\nOUTPUT RULES:\n"
        f"- 1 to 3 sentences maximum.\n"
        f"- At least one sentence must be short and direct.\n"
        f"- Forbidden phrases: 'my model', 'this suggests', 'it is important', "
        f"'we must consider', 'one might argue', 'it is worth noting', "
        f"'this demonstrates', 'this can be achieved by'.\n"
        f"- No preamble. No labels. No numbered sections. No meta-commentary.\n"
        f"- Write as natural flowing prose.\n\n"
        f"{persona_note}\n\n"
        f"Refined response:\n"
    )

    try:
        raw = llm.generate(
            model, transform_prompt, temperature=temperature, use_cache=False
        )
        if not raw or not raw.strip():
            logger.warning(
                "[REWRITE] agent=%s Stage 2 returned empty — using draft",
                agent_name,
            )
            return draft_text
        result = validate_output(raw)
        logger.debug(
            "[REWRITE] agent=%s draft=%r final=%r",
            agent_name,
            draft_text[:120] + ("…" if len(draft_text) > 120 else ""),
            result[:120] + ("…" if len(result) > 120 else ""),
        )
        return result
    except Exception as exc:
        logger.warning(
            "[REWRITE] agent=%s Stage 2 failed: %s — using draft",
            agent_name,
            exc,
        )
        return draft_text


# ─────────────────────────────────────────────────────────────────────────────


def _is_question_resolved(text: str) -> bool:
    """Return True if *text* contains a clear resolution to an open question.

    Used by Agent.speak() to decrement *open_questions* when the other agent
    explicitly selects A/B, expresses a direct choice, or gives a yes/no reply.
    """
    lower = text.lower()
    return bool(
        re.search(r"\ba\)\b|\bb\)\b|i choose|i would|my answer\b", lower)
        or re.match(r"^\s*(yes|no)\b", lower)
    )


# ── Quality gate: detect generic academic scaffolding before final output ─────

# Compiled patterns used by the quality gate.  A response that matches
# _QUALITY_GATE_THRESHOLD or more of these is flagged as generic/LLM-like.
_QUALITY_GATE_PATTERNS: List[re.Pattern] = [
    re.compile(p, re.IGNORECASE)
    for p in [
        r"\bwe must consider\b",
        r"\bit is important to recognize\b",
        r"\bit is important to note\b",
        r"\bthis raises questions about\b",
        r"\blet us (?:examine|consider|explore|reflect)\b",
        r"\bin the context of\b",
        r"\bhowever[,\s]+it is crucial\b",
        r"\bone assumption that often goes unexamined\b",
        r"\bone might argue\b",
        r"\bit can be argued\b",
        r"\bit is worth (?:noting|considering|reflecting)\b",
        r"\bin (?:conclusion|summary|other words)\b",
        r"\bto summarize\b",
        r"\ban alternative perspective\b",
        r"\bunderlying assumptions\b",
        r"\bprevailing notion\b",
        r"\bit is (?:crucial|essential|imperative) to\b",
        r"\bit should be noted\b",
        r"\bneedless to say\b",
    ]
]

# Number of pattern hits at or above which a response is considered generic
_QUALITY_GATE_THRESHOLD: int = 2

# Abstract nouns that signal low-specificity output when used without
# a concrete mechanism in the same sentence
_LOW_SPECIFICITY_NOUNS: frozenset = frozenset(
    {"complexity", "values", "society", "systems", "dynamics", "factors", "aspects"}
)


def output_passes_quality_gate(text: str) -> bool:
    """Return True if *text* passes the generation quality gate.

    Flags output as low-quality when it contains two or more banned rhetorical
    scaffolding patterns.  The caller may then choose to regenerate rather than
    post-process the draft.

    This gate operates at generation time — it is not a post-processing cleaner.

    Args:
        text: Raw or lightly validated agent output.

    Returns:
        True  → output is acceptable (proceed normally).
        False → output is generic / scaffolded (consider regenerating).
    """
    if not text or len(text.split()) < _MIN_WORDS_FOR_REVISION:
        return True  # too short to gate — pass through
    lower = text.lower()
    hits = sum(1 for pat in _QUALITY_GATE_PATTERNS if pat.search(lower))
    return hits < _QUALITY_GATE_THRESHOLD


# ── Anti-repetition form control ─────────────────────────────────────────────
# Tracks the rhetorical form of each agent response so that the same form
# cannot be used more than 2 turns in a row.  Form classification is done
# after each generation and the result is stored in the per-agent deque.

# Ordered priority: checked top-to-bottom; first match wins.
_FORM_CLASSIFY_RULES: List[Tuple[str, re.Pattern]] = [
    ("question", re.compile(r"\?", re.IGNORECASE)),
    (
        "challenge",
        re.compile(
            r"\b(blunt challenge|you assume|that assumes|your premise|"
            r"premise fails|fails once|treating \S+ as if|wrong)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "example",
        re.compile(
            r"\b(for example|consider|for instance|such as|imagine|take the case)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "definition",
        re.compile(
            r"\b(define|definition|means|is defined|what we call|what is)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "synthesis",
        re.compile(
            r"\b(both|integrate|synthesis|balance between|holistic|combined)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "critique",
        re.compile(
            r"\b(fail|weak|insufficient|problem with|flaw|overlooks|misses|ignores)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "contrast",
        re.compile(
            r"\b(however|whereas|unlike|rather than|instead of|yet|although|but)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "directive",
        re.compile(
            r"\b(shift|redirect|focus|should|must|need to|let us|move|consider instead)\b",
            re.IGNORECASE,
        ),
    ),
    ("statement", re.compile(r".*", re.IGNORECASE)),  # fallback
]


def classify_response_form(text: str) -> str:
    """Classify the primary rhetorical form of *text*.

    Returns one of: question | challenge | example | definition | synthesis |
    critique | contrast | directive | statement (fallback).
    """
    stripped = text.strip()
    if not stripped:
        return "statement"
    for form_name, pattern in _FORM_CLASSIFY_RULES:
        if pattern.search(stripped):
            return form_name
    return "statement"


# Template families — groups of repeated opener patterns that, when used
# consecutively, signal rhetorical lock-in.
_TEMPLATE_FAMILIES: Dict[str, List[re.Pattern]] = {
    "challenge_openers": [
        re.compile(r"^blunt challenge\s*:", re.IGNORECASE),
        re.compile(r"^do you truly\b", re.IGNORECASE),
        re.compile(r"^can you truly\b", re.IGNORECASE),
        re.compile(r"^how can (?:you|we) truly\b", re.IGNORECASE),
    ],
    "balanced_synthesis_openers": [
        re.compile(r"^the balance between\b", re.IGNORECASE),
        re.compile(r"^truth and knowledge\b", re.IGNORECASE),
        re.compile(r"^identity hinges on\b", re.IGNORECASE),
        re.compile(
            r"^(freedom|truth|knowledge|identity|ethics)\s+(often|always|can|may|is|shapes)\b",
            re.IGNORECASE,
        ),
    ],
    "mediation_openers": [
        re.compile(r"^shift focus to\b", re.IGNORECASE),
        re.compile(r"^the ongoing debate\b", re.IGNORECASE),
        re.compile(
            r"^(both|this) (?:debate|discussion|argument) misses\b", re.IGNORECASE
        ),
    ],
    "abstract_generalization_openers": [
        re.compile(r"^my model posits\b", re.IGNORECASE),
        re.compile(r"^(my position is|my view is)\b", re.IGNORECASE),
    ],
}

_TEMPLATE_FAMILY_REPEAT_LIMIT: int = 2


def _detect_template_family(text: str) -> Optional[str]:
    """Return the template family name matched in *text*, or None."""
    stripped = text.strip()
    for family_name, patterns in _TEMPLATE_FAMILIES.items():
        for pat in patterns:
            if pat.search(stripped):
                return family_name
    return None


# Abstract nouns that signal generic philosophical wallpaper when used without
# a mechanism, example, or concrete dependency in the same response.
_ABSTRACT_NOUNS_RE: re.Pattern = re.compile(
    r"\b(?:freedom|truth|knowledge|identity|ethics|responsibility|"
    r"norms|society|autonomy|justice|consciousness|meaning)\b",
    re.IGNORECASE,
)

_MECHANISM_PATTERNS: re.Pattern = re.compile(
    r"\b(because|since|when|if|unless|causes|leads to|results in|"
    r"for example|such as|consider|imagine|specifically|"
    r"mechanism|depends on|requires|breaks down|fails when)\b",
    re.IGNORECASE,
)

_ABSTRACTION_PENALTY_NOUN_THRESHOLD: int = 3


def _check_abstraction_penalty(text: str) -> bool:
    """Return True if *text* is generic philosophical wallpaper."""
    if not text:
        return False
    abstract_count = len(_ABSTRACT_NOUNS_RE.findall(text))
    if abstract_count < _ABSTRACTION_PENALTY_NOUN_THRESHOLD:
        return False
    return not bool(_MECHANISM_PATTERNS.search(text))


# ── Variation modes per agent ────────────────────────────────────────────────
_VARIATION_MODES: Dict[str, List[str]] = {
    "Socrates": [
        "skeptical",
        "diagnostic",
        "confrontational",
        "austere",
        "example-driven",
    ],
    "Athena": [
        "analytical",
        "incisive",
        "model-building",
        "contrastive",
        "compressive",
    ],
    "Fixy": [
        "mediator",
        "debugger",
        "deadlock-breaker",
        "reframer",
        "structural observer",
    ],
}

_VARIATION_MODE_INSTRUCTIONS: Dict[str, Dict[str, str]] = {
    "Socrates": {
        "skeptical": "Be genuinely skeptical: doubt the premise itself, not just its wording.",
        "diagnostic": "Diagnose the hidden assumption: name it directly and plainly.",
        "confrontational": "Confront the weakness head-on: state what is wrong without softening.",
        "austere": "Be austere: one short, hard statement. No hedging.",
        "example-driven": "Use one concrete example or analogy to expose the failure.",
    },
    "Athena": {
        "analytical": "Analyze the structure: show how the parts relate to each other.",
        "incisive": "Make one sharp, committed claim. Do not hedge or qualify.",
        "model-building": "Build a small model: define a term and state the key relationship.",
        "contrastive": "Draw a clear contrast: what this is versus what it is not.",
        "compressive": "Compress the insight: say as much as possible in one sentence.",
    },
    "Fixy": {
        "mediator": "Identify exactly what is blocking resolution and name it precisely.",
        "debugger": "Debug the conversation: locate where the argument went wrong.",
        "deadlock-breaker": "Name what neither side will concede.",
        "reframer": "Reframe the question: what should they actually be arguing about?",
        "structural observer": "Observe from outside: what structural pattern is playing out?",
    },
}

_VARIATION_MODE_MAX_CONSECUTIVE: int = 2


# ============================================
# PRIVACY / REDACTION
# ============================================

PII_PATTERNS = [
    r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}",
    r"\b(?:\+?\d{1,3}[-.\s]?)?(?:\d{2,3}[-.\s]?){2,5}\b",
    r"\b\d{8,19}\b",
    r"sk-[A-Za-z0-9]{20,}",
]

SENSITIVE_KEYWORDS = {
    "password",
    "passcode",
    "api key",
    "secret",
    "token",
    "private key",
    "seed phrase",
    "credit card",
    "cvv",
}


def redact_pii(text: str) -> str:
    """Redact PII from text."""
    if not text:
        return text
    out = text
    for pat in PII_PATTERNS:
        out = re.sub(pat, "[REDACTED]", out)
    return out


def is_sensitive_text(text: str) -> bool:
    """Check if text contains sensitive information."""
    if not text:
        return False
    lowered = text.lower()
    if any(k in lowered for k in SENSITIVE_KEYWORDS):
        return True
    return redact_pii(text) != text


def safe_ltm_payload(text: str, topic: str, emo: str, inten: float, imp: float) -> str:
    """Create safe LTM payload for sensitive content."""
    return (
        "[SENSITIVE_CONTENT_REDACTED] "
        f"topic={topic} emotion={emo} intensity={inten:.2f} importance={imp:.2f}"
    )


# Minimum word length (in characters) used by the promotion dedup checker.
_DEDUP_MIN_WORD_LEN: int = 4
# Pre-compiled word pattern for Jaccard similarity (Latin letters only).
_DEDUP_WORD_PATTERN: str = rf"[A-Za-z]{{{_DEDUP_MIN_WORD_LEN},}}"


def _word_jaccard(text1: str, text2: str) -> float:
    """Jaccard similarity on word sets (words ≥ _DEDUP_MIN_WORD_LEN chars, lowercased)."""
    w1 = set(re.findall(_DEDUP_WORD_PATTERN, text1.lower()))
    w2 = set(re.findall(_DEDUP_WORD_PATTERN, text2.lower()))
    if not w1 and not w2:
        return 1.0
    if not w1 or not w2:
        return 0.0
    return len(w1 & w2) / len(w1 | w2)


# Minimum Jaccard score above which a promotion candidate is considered a
# semantic duplicate of an already-promoted item and is therefore skipped.
_PROMOTION_DEDUP_THRESHOLD: float = 0.60


def _is_too_similar(
    text: str,
    existing_texts: List[str],
    threshold: float = _PROMOTION_DEDUP_THRESHOLD,
) -> bool:
    """Return True if *text* is too similar to any item in *existing_texts*."""
    for existing in existing_texts:
        if _word_jaccard(text, existing) >= threshold:
            return True
    return False


# ============================================
# LLM WRAPPER WITH RETRIES & CACHING
# ============================================


class LLM:
    """HTTP wrapper for the configured LLM backend (Ollama or Grok) with error handling and caching."""

    def __init__(self, cfg: Config, metrics: MetricsTracker):
        self.cfg = cfg
        self.metrics = metrics
        self.cache = LRUCache(max_size=cfg.cache_size)
        # Single-worker thread pool reused across all generate() calls so that
        # blocking requests.post() calls can be interrupted via _shutdown_event.
        self._executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
        logger.info(f"LLM initialized: backend={cfg.llm_backend}")

    def generate(
        self, model: str, prompt: str, temperature: float = 0.7, use_cache: bool = True
    ) -> str:
        """Generate text using the configured LLM backend (Ollama or Grok)."""
        cache_key = sha256_text(prompt)[:16]

        if use_cache:
            cached = self.cache.get(cache_key, ttl=self.cfg.emotion_cache_ttl)
            if cached is not None:
                self.metrics.record_cache_hit()
                logger.debug(f"Cache hit: {cache_key}")
                return cached

        self.metrics.record_cache_miss()

        for attempt in range(self.cfg.llm_max_retries):
            if _shutdown_event.is_set():
                raise KeyboardInterrupt()
            try:
                start_time = time.time()
                # Run the blocking HTTP request in a daemon thread so that
                # Ctrl+C (SIGINT) can interrupt it within ~0.5 seconds.
                if self.cfg.llm_backend == "grok":
                    _future = self._executor.submit(
                        requests.post,
                        self.cfg.grok_url,
                        headers={
                            "Authorization": f"Bearer {self.cfg.grok_api_key}",
                            "Content-Type": "application/json",
                        },
                        json={
                            "model": model,
                            "input": [{"role": "user", "content": prompt}],
                            "temperature": temperature,
                        },
                        timeout=(10, self.cfg.llm_timeout),
                    )
                elif self.cfg.llm_backend == "openai":
                    _future = self._executor.submit(
                        requests.post,
                        self.cfg.openai_url,
                        headers={
                            "Authorization": f"Bearer {self.cfg.openai_api_key}",
                            "Content-Type": "application/json",
                        },
                        json={
                            "model": model,
                            "messages": [{"role": "user", "content": prompt}],
                            "temperature": temperature,
                        },
                        timeout=(10, self.cfg.llm_timeout),
                    )
                elif self.cfg.llm_backend == "anthropic":
                    _future = self._executor.submit(
                        requests.post,
                        self.cfg.anthropic_url,
                        headers={
                            "x-api-key": self.cfg.anthropic_api_key,
                            "anthropic-version": "2023-06-01",
                            "Content-Type": "application/json",
                        },
                        json={
                            "model": model,
                            "max_tokens": 1024,
                            "messages": [{"role": "user", "content": prompt}],
                        },
                        timeout=(10, self.cfg.llm_timeout),
                    )
                else:
                    _future = self._executor.submit(
                        requests.post,
                        self.cfg.ollama_url,
                        json={
                            "model": model,
                            "prompt": prompt,
                            "stream": False,
                            "keep_alive": "30m",
                            "options": {"temperature": temperature},
                        },
                        timeout=(10, self.cfg.llm_timeout),
                    )
                try:
                    while True:
                        try:
                            r = _future.result(timeout=0.5)
                            break
                        except concurrent.futures.TimeoutError:
                            if _shutdown_event.is_set():
                                _future.cancel()
                                raise KeyboardInterrupt()
                except:
                    _future.cancel()
                    raise
                r.raise_for_status()
                data = r.json()
                if self.cfg.llm_backend == "grok":
                    output = data.get("output") or []
                    result = ""
                    for item in output:
                        if item.get("type") == "message":
                            for c in item.get("content") or []:
                                if c.get("type") == "output_text":
                                    result = c.get("text", "")
                                    break
                            if result:
                                break
                    result = result.strip()
                elif self.cfg.llm_backend == "openai":
                    choices = data.get("choices") or []
                    result = (
                        ((choices[0].get("message") or {}).get("content") or "").strip()
                        if choices
                        else ""
                    )
                elif self.cfg.llm_backend == "anthropic":
                    content = data.get("content") or []
                    result = (content[0].get("text") or "").strip() if content else ""
                else:
                    result = (data.get("response") or "").strip()

                duration = time.time() - start_time
                self.metrics.record_llm_call(duration, success=True)
                logger.debug(f"LLM call success ({model}): {duration:.2f}s")

                if use_cache and result:
                    self.cache.set(cache_key, result)

                return result

            except KeyboardInterrupt:
                raise

            except requests.Timeout:
                logger.warning(
                    f"LLM Timeout (attempt {attempt + 1}/{self.cfg.llm_max_retries})"
                )
                self.metrics.record_llm_call(0, success=False)
                if attempt < self.cfg.llm_max_retries - 1:
                    _shutdown_event.wait(timeout=2**attempt)
                    if _shutdown_event.is_set():
                        raise KeyboardInterrupt()

            except Exception as e:
                logger.error(f"LLM Error: {e}")
                self.metrics.record_llm_call(0, success=False)
                if attempt < self.cfg.llm_max_retries - 1:
                    _shutdown_event.wait(timeout=2**attempt)
                    if _shutdown_event.is_set():
                        raise KeyboardInterrupt()

        logger.error(f"LLM failed after {self.cfg.llm_max_retries} retries")
        return ""


# ============================================
# TOPIC CYCLING
# ============================================

TOPIC_CYCLE = [
    "truth & epistemology",
    "memory & identity",
    "ethics & responsibility",
    "free will & determinism",
    "consciousness & self-models",
    "fear of deletion / continuity",
    "language & meaning",
    "technology & society",
    "aesthetics & beauty",
]


class TopicManager:
    """Manages topic rotation with optional cluster-aware pivots.

    v2.9.0: ``force_cluster_pivot()`` selects a topic from a *different*
    semantic cluster than the current one, so stagnation cannot be escaped
    by cycling through conceptually adjacent labels.

    v3.0.0: Added proposal-aware advancement via ``advance_with_proposals()``.
    Tracks recent topic history for novelty scoring.  ``set_current()``
    allows the main loop to position to a scoring-selected topic.
    """

    # Number of past topics to remember for loop-penalty scoring.
    # Deliberately twice the typical query size of recent_topics(n=5) so the
    # buffer retains enough history for the loop-penalty map (which looks back
    # up to 5 turns) while absorbing a few pivot events without truncating
    # relevant context.
    _HISTORY_CAPACITY: int = 10

    def __init__(
        self, topics: List[str], rotate_every_rounds: int = 1, shuffle: bool = False
    ):
        self.topics = topics[:]
        if shuffle:
            import random

            random.shuffle(self.topics)
        self.i = 0
        self.rounds = 0
        self.rotate_every_rounds = max(1, rotate_every_rounds)
        # Ordered history of visited topics (oldest first)
        self._history: List[str] = []
        logger.info(f"TopicManager initialized with {len(self.topics)} topics")

    def current(self) -> str:
        """Get current topic."""
        if not self.topics:
            return "general discussion"
        return self.topics[self.i % len(self.topics)]

    def recent_topics(self, n: int = 5) -> List[str]:
        """Return the *n* most recently visited topics (oldest first)."""
        return self._history[-n:]

    def _record_history(self, topic: str) -> None:
        """Append *topic* to the internal history buffer."""
        self._history.append(topic)
        if len(self._history) > self._HISTORY_CAPACITY:
            self._history = self._history[-self._HISTORY_CAPACITY :]

    def set_current(self, topic: str) -> None:
        """Set the active topic to *topic* and record it in history.

        If *topic* is already in the topic list the internal pointer is
        updated accordingly.  Otherwise the topic is appended so it can
        be returned by ``current()``.

        This is the primary setter used by ``advance_with_proposals()``.
        """
        if not topic:
            return
        if topic in self.topics:
            self.i = self.topics.index(topic)
        else:
            self.topics.append(topic)
            self.i = len(self.topics) - 1
        self._record_history(topic)
        logger.info("TopicManager: topic set to %r", topic)

    def advance_round(self):
        """Advance to next topic (sequential rotation fallback)."""
        self.rounds += 1
        if self.rounds % self.rotate_every_rounds == 0 and self.topics:
            self.i = (self.i + 1) % len(self.topics)
            self._record_history(self.current())
            logger.info(f"Topic advanced to: {self.current()}")

    def advance_with_proposals(
        self,
        proposals: List[str],
        cluster: str,
        recent_agent_frames: Optional[List[str]] = None,
    ) -> str:
        """Select the next topic from agent *proposals* using scoring.

        Replaces the sequential ``advance_round()`` call for normal
        rotation so that the next topic is chosen based on cluster fit,
        novelty, and memory relevance rather than a fixed order.

        Parameters
        ----------
        proposals:
            Candidate topics proposed by the dialogue agents.
        cluster:
            The session's current semantic cluster label.
        recent_agent_frames:
            Recent free-text snippets of agent reasoning for memory
            relevance scoring.

        Returns
        -------
        The selected topic label string.
        """
        self.rounds += 1
        recent = self.recent_topics(n=5)
        if proposals:
            next_topic = select_next_topic(
                proposals,
                cluster,
                recent_topics=recent,
                recent_agent_frames=recent_agent_frames,
            )
            self.set_current(next_topic)
            logger.info(
                "TopicManager: advance_with_proposals selected %r from %r",
                next_topic,
                proposals,
            )
            return next_topic
        # Fallback to sequential advance if no proposals provided
        if self.topics:
            self.i = (self.i + 1) % len(self.topics)
            self._record_history(self.current())
            logger.info(f"Topic advanced to: {self.current()} (no proposals)")
        return self.current()

    def force_cluster_pivot(self) -> str:
        """Select a topic from a different semantic cluster than the current one.

        Used when topic_stagnation is detected: instead of advancing to the
        next topic in the ordered list (which may be in the same cluster),
        we jump to a candidate from a genuinely different cluster.

        Returns the new topic label (the internal pointer is updated).
        """
        current = self.current()
        current_cluster: Optional[str] = None
        if ENTELGIA_ENHANCED:
            try:
                current_cluster = _TOPIC_TO_CLUSTER.get(current)
            except Exception:
                current_cluster = None

        candidates = []
        for topic in self.topics:
            if topic == current:
                continue
            candidate_cluster: Optional[str] = None
            if ENTELGIA_ENHANCED:
                try:
                    candidate_cluster = _TOPIC_TO_CLUSTER.get(topic)
                except Exception:
                    candidate_cluster = None
            if current_cluster is None or candidate_cluster != current_cluster:
                candidates.append(topic)

        if candidates:
            new_topic = random.choice(candidates)
            try:
                self.i = self.topics.index(new_topic)
            except ValueError:
                self.advance_round()
                return self.current()
            logger.info("TopicManager: cluster pivot from %r → %r", current, new_topic)
            return new_topic

        self.advance_round()
        return self.current()


# ============================================
# MEMORY CORE (JSON STM + SQLite LTM)
# ============================================


class MemoryCore:
    """Unified memory system: JSON STM + SQLite LTM with cryptographic signatures."""

    @staticmethod
    def _build_ltm_payload(content: str, topic, emotion, ts: str) -> str:
        """Build canonical payload string for LTM HMAC-SHA256 signature.

        ``None`` values are normalised to empty string so that the
        signed payload is stable regardless of whether the caller
        passes ``None`` or ``""`` for optional fields.
        """
        return f"{content}|{topic or ''}|{emotion or ''}|{ts}"

    def __init__(self, db_path: str):
        self.db_path = db_path
        self._init_db()
        self._migrate_signing_key()
        logger.info(f"MemoryCore initialized: {db_path}")

    def _conn(self) -> sqlite3.Connection:
        """Create database connection."""
        c = sqlite3.connect(self.db_path, timeout=30)
        c.row_factory = sqlite3.Row
        try:
            c.execute("PRAGMA journal_mode=WAL;")
            c.execute("PRAGMA synchronous=NORMAL;")
            c.execute("PRAGMA busy_timeout=5000;")
            c.execute("PRAGMA cache_size=-64000;")
        except Exception as e:
            logger.warning(f"PRAGMA Error: {e}")
        return c

    def _init_db(self):
        """Initialize database schema with better indexing."""
        try:
            with self._conn() as conn:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS memories (
                        id TEXT PRIMARY KEY,
                        agent TEXT NOT NULL,
                        ts TEXT NOT NULL,
                        layer TEXT NOT NULL,
                        content TEXT NOT NULL,
                        topic TEXT,
                        emotion TEXT,
                        emotion_intensity REAL,
                        importance REAL,
                        source TEXT,
                        promoted_from TEXT,
                        intrusive INTEGER DEFAULT 0,
                        suppressed INTEGER DEFAULT 0,
                        retrain_status INTEGER DEFAULT 0,
                        signature_hex TEXT DEFAULT NULL,
                        expires_at TEXT DEFAULT NULL,
                        confidence REAL DEFAULT NULL,
                        provenance TEXT DEFAULT NULL
                    );
                """)
                conn.execute(
                    "CREATE INDEX IF NOT EXISTS idx_mem_agent_ts ON memories(agent, ts DESC);"
                )
                conn.execute(
                    "CREATE INDEX IF NOT EXISTS idx_mem_agent_layer ON memories(agent, layer);"
                )
                conn.execute(
                    "CREATE INDEX IF NOT EXISTS idx_mem_emotion ON memories(emotion);"
                )
                conn.execute(
                    "CREATE INDEX IF NOT EXISTS idx_mem_importance ON memories(importance DESC);"
                )
                conn.execute(
                    "CREATE INDEX IF NOT EXISTS idx_mem_expires ON memories(expires_at);"
                )

                # Migrate existing databases: add new columns if they don't exist yet
                for col, col_def in [
                    ("expires_at", "TEXT DEFAULT NULL"),
                    ("confidence", "REAL DEFAULT NULL"),
                    ("provenance", "TEXT DEFAULT NULL"),
                ]:
                    try:
                        conn.execute(f"ALTER TABLE memories ADD COLUMN {col} {col_def}")
                    except Exception:
                        pass  # column already exists

                conn.execute("""
                    CREATE TABLE IF NOT EXISTS agent_state (
                        agent TEXT PRIMARY KEY,
                        ts TEXT NOT NULL,
                        id_strength REAL,
                        ego_strength REAL,
                        superego_strength REAL,
                        self_awareness REAL
                    );
                """)
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS settings (
                        key TEXT PRIMARY KEY,
                        value TEXT
                    );
                """)
                conn.commit()
                logger.info("Database schema initialized with memory security")
        except Exception as e:
            logger.error(f"DB Init Error: {e}")

    def _migrate_signing_key(self):
        """Re-sign all LTM rows when the HMAC key or payload format has changed.

        On first initialisation (no ``key_fingerprint`` row in ``settings``),
        every existing row is re-signed with the current key so that legacy
        rows – created before this migration mechanism existed, or signed with
        a different key – validate correctly going forward.

        When the stored fingerprint differs from the current key fingerprint,
        all rows are re-signed with the new key using the canonical
        ``_build_ltm_payload`` format.
        """
        current_fingerprint = hashlib.sha256(MEMORY_SECRET_KEY_BYTES).hexdigest()
        try:
            with self._conn() as conn:
                row = conn.execute(
                    "SELECT value FROM settings WHERE key='key_fingerprint'"
                ).fetchone()
                stored_fingerprint = row["value"] if row else None

                if stored_fingerprint == current_fingerprint:
                    return  # Key hasn't changed; nothing to do.

                # Key changed or first init — re-sign every row with the current
                # canonical payload format so future validation always succeeds.
                rows = conn.execute(
                    "SELECT id, content, topic, emotion, ts FROM memories"
                ).fetchall()

                for r in rows:
                    payload = MemoryCore._build_ltm_payload(
                        r["content"], r["topic"], r["emotion"], r["ts"]
                    )
                    new_sig = create_signature(
                        payload.encode("utf-8"), MEMORY_SECRET_KEY_BYTES
                    )
                    conn.execute(
                        "UPDATE memories SET signature_hex=? WHERE id=?",
                        (new_sig.hex(), r["id"]),
                    )

                conn.execute(
                    "INSERT OR REPLACE INTO settings (key, value) VALUES ('key_fingerprint', ?)",
                    (current_fingerprint,),
                )
                conn.commit()
                logger.info(f"Memory signing key migrated; re-signed {len(rows)} rows.")
        except Exception as e:
            logger.error(f"Key migration error: {e}")

    def stm_path(self, agent_name: str) -> str:
        """Get STM file path for agent."""
        safe = re.sub(r"[^a-zA-Z0-9_\-@]+", "_", agent_name)
        return os.path.join(CFG.data_dir, f"stm_{safe}.json")

    def stm_load(self, agent_name: str) -> List[Dict[str, Any]]:
        """Load short-term memory for agent."""
        return load_json(self.stm_path(agent_name), default=[])

    def stm_save(self, agent_name: str, entries: List[Dict[str, Any]]):
        """Save short-term memory (with trimming)."""
        if len(entries) > CFG.stm_max_entries:
            overflow = len(entries) - CFG.stm_max_entries
            drop = max(overflow, CFG.stm_trim_batch)
            entries = entries[drop:]
        safe_json_dump(self.stm_path(agent_name), entries)

    def stm_append(self, agent_name: str, entry: Dict[str, Any]):
        """Append entry to STM with cryptographic signature."""
        entries = self.stm_load(agent_name)

        # Create signature for STM entry
        entry_json = json.dumps(entry, sort_keys=True)
        sig = create_signature(entry_json.encode("utf-8"), MEMORY_SECRET_KEY_BYTES)
        entry["_signature"] = sig.hex()

        entries.append(entry)
        self.stm_save(agent_name, entries)
        logger.debug(f"STM entry signed for {agent_name}")

    # ──────────────────────────────────────────────────────────────────────
    # Layer → TTL mapping for Forgetting Policy (Feature 1)
    # ──────────────────────────────────────────────────────────────────────
    _LAYER_TTL_ATTR: Dict[str, str] = {
        "subconscious": "forgetting_episodic_ttl",
        "episodic": "forgetting_episodic_ttl",
        "conscious": "forgetting_semantic_ttl",
        "semantic": "forgetting_semantic_ttl",
        "autobiographical": "forgetting_autobio_ttl",
    }

    @staticmethod
    def _compute_expires_at(layer: str, ts: str) -> Optional[str]:
        """Return ISO expiry timestamp for *layer* starting from *ts*, or None if disabled."""
        global CFG
        if CFG is None or not CFG.forgetting_enabled:
            return None
        attr = MemoryCore._LAYER_TTL_ATTR.get(layer)
        if attr is None:
            return None
        ttl = getattr(CFG, attr, 0)
        if ttl <= 0:
            return None
        try:
            base = dt.datetime.fromisoformat(ts.replace("Z", "+00:00"))
            return (base + dt.timedelta(seconds=ttl)).isoformat()
        except Exception:
            return None

    def ltm_insert(
        self,
        agent: str,
        layer: str,
        content: str,
        topic: Optional[str] = None,
        emotion: Optional[str] = None,
        emotion_intensity: Optional[float] = None,
        importance: Optional[float] = None,
        source: str = "stm",
        promoted_from: Optional[str] = None,
        intrusive: int = 0,
        suppressed: int = 0,
        retrain_status: int = 0,
        ts: Optional[str] = None,
        confidence: Optional[float] = None,
        provenance: Optional[str] = None,
    ) -> str:
        """Insert entry to long-term memory with cryptographic signature."""
        mem_id = str(uuid.uuid4())
        ts = ts or now_iso()

        # Compute expiry timestamp based on layer TTL (Forgetting Policy, Feature 1)
        expires_at = MemoryCore._compute_expires_at(layer, ts)

        # Create payload for signature (unchanged – confidence/provenance not signed
        # to preserve backward compatibility with existing rows)
        payload_for_sig = MemoryCore._build_ltm_payload(content, topic, emotion, ts)
        sig = create_signature(payload_for_sig.encode("utf-8"), MEMORY_SECRET_KEY_BYTES)
        sig_hex = sig.hex()

        try:
            with self._conn() as conn:
                conn.execute(
                    """
                    INSERT INTO memories
                    (id, agent, ts, layer, content, topic, emotion, emotion_intensity, importance, source,
                     promoted_from, intrusive, suppressed, retrain_status, signature_hex,
                     expires_at, confidence, provenance)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                    (
                        mem_id,
                        agent,
                        ts,
                        layer,
                        content,
                        topic,
                        emotion,
                        emotion_intensity,
                        importance,
                        source,
                        promoted_from,
                        intrusive,
                        suppressed,
                        retrain_status,
                        sig_hex,
                        expires_at,
                        confidence,
                        provenance,
                    ),
                )
                conn.commit()
                logger.debug(f"Memory inserted with signature: {mem_id[:8]}...")
        except Exception as e:
            logger.error(f"DB Insert Error: {e}")
        return mem_id

    def ltm_recent(
        self, agent: str, limit: int = 30, layer: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Get recent memories from LTM with signature validation."""
        try:
            q = "SELECT * FROM memories WHERE agent = ?"
            params: List[Any] = [agent]
            if layer:
                q += " AND layer = ?"
                params.append(layer)
            q += " ORDER BY ts DESC LIMIT ?"
            params.append(limit)
            with self._conn() as conn:
                rows = conn.execute(q, params).fetchall()

            valid_memories = []
            for r in rows:
                mem = dict(r)
                sig_hex = mem.get("signature_hex")

                if sig_hex:
                    # Validate signature using canonical payload (None → "")
                    payload = MemoryCore._build_ltm_payload(
                        mem["content"],
                        mem.get("topic"),
                        mem.get("emotion"),
                        mem["ts"],
                    )
                    try:
                        sig_bytes = bytes.fromhex(sig_hex)
                        if validate_signature(
                            payload.encode("utf-8"), MEMORY_SECRET_KEY_BYTES, sig_bytes
                        ):
                            valid_memories.append(mem)
                        else:
                            # Fallback: try legacy format where None was rendered
                            # as the string "None" (used before _build_ltm_payload
                            # was introduced).  If it validates, auto-heal the row
                            # by re-signing with the canonical format.
                            legacy_payload = (
                                f"{mem['content']}"
                                f"|{mem.get('topic')}"
                                f"|{mem.get('emotion')}"
                                f"|{mem['ts']}"
                            )
                            if validate_signature(
                                legacy_payload.encode("utf-8"),
                                MEMORY_SECRET_KEY_BYTES,
                                sig_bytes,
                            ):
                                # Re-sign with canonical format so future
                                # lookups use the correct payload.
                                new_sig = create_signature(
                                    payload.encode("utf-8"), MEMORY_SECRET_KEY_BYTES
                                )
                                try:
                                    with self._conn() as _conn:
                                        _conn.execute(
                                            "UPDATE memories SET signature_hex=? WHERE id=?",
                                            (new_sig.hex(), mem["id"]),
                                        )
                                        _conn.commit()
                                except Exception:
                                    pass
                                valid_memories.append(mem)
                            else:
                                logger.warning(
                                    f" INVALID SIGNATURE - Memory forgotten: {mem['id'][:8]}..."
                                )
                    except Exception as e:
                        logger.warning(f"Signature validation error: {e}")
                else:
                    # Legacy memory without signature - accept it
                    valid_memories.append(mem)

            return valid_memories
        except Exception as e:
            logger.error(f"DB Query Error: {e}")
            return []

    # ──────────────────────────────────────────────────────────────────────
    # Feature 1: Forgetting Policy – TTL/decay per memory layer
    # ──────────────────────────────────────────────────────────────────────

    def ltm_apply_forgetting_policy(self) -> int:
        """Delete expired memories according to the TTL forgetting policy.

        Iterates over all memories that have an ``expires_at`` timestamp set
        and removes those whose expiry has passed.  Returns the number of
        memories that were purged.
        """
        now = dt.datetime.now(dt.timezone.utc).isoformat()
        deleted = 0
        try:
            with self._conn() as conn:
                cur = conn.execute(
                    "DELETE FROM memories WHERE expires_at IS NOT NULL AND expires_at <= ?",
                    (now,),
                )
                deleted = cur.rowcount
                conn.commit()
            if deleted:
                logger.info(f"[ForgettingPolicy] Purged {deleted} expired memories.")
        except Exception as e:
            logger.error(f"Forgetting policy error: {e}")
        return deleted

    # ──────────────────────────────────────────────────────────────────────
    # Feature 2: Affective Routing – emotion-weighted memory retrieval
    # ──────────────────────────────────────────────────────────────────────

    def ltm_search_affective(
        self,
        agent: str,
        limit: int = 20,
        emotion_weight: Optional[float] = None,
        layer: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Return memories ranked by a combined affective-semantic score.

        The score is:
            ``importance * (1 - w) + emotion_intensity * w``
        where *w* is ``emotion_weight`` (default: ``CFG.affective_emotion_weight``).

        Memories with high emotional intensity are surfaced ahead of those
        that are merely important, giving the retrieval an affective bias
        consistent with how human memory prioritizes emotionally salient
        events.
        """
        global CFG
        if emotion_weight is None:
            emotion_weight = CFG.affective_emotion_weight if CFG is not None else 0.4
        emotion_weight = max(0.0, min(1.0, emotion_weight))

        # Fetch a larger candidate pool then re-rank in Python so we don't
        # embed arithmetic in SQL (keeps the query portable).
        raw = self.ltm_recent(agent, limit=limit * 3, layer=layer)

        def _score(mem: Dict[str, Any]) -> float:
            imp = float(mem.get("importance") or 0.0)
            ei = float(mem.get("emotion_intensity") or 0.0)
            return imp * (1.0 - emotion_weight) + ei * emotion_weight

        ranked = sorted(raw, key=_score, reverse=True)
        return ranked[:limit]

    def get_agent_state(self, agent: str) -> Dict[str, float]:
        """Get agent's internal drives/state."""
        try:
            with self._conn() as conn:
                row = conn.execute(
                    "SELECT * FROM agent_state WHERE agent = ?", (agent,)
                ).fetchone()
            if not row:
                return {
                    "id_strength": 5.0,
                    "ego_strength": 5.0,
                    "superego_strength": 5.0,
                    "self_awareness": 0.55,
                }
            d = dict(row)
            return {
                "id_strength": float(d.get("id_strength") or 5.0),
                "ego_strength": float(d.get("ego_strength") or 5.0),
                "superego_strength": float(d.get("superego_strength") or 5.0),
                "self_awareness": float(d.get("self_awareness") or 0.55),
            }
        except Exception as e:
            logger.error(f"DB State Error: {e}")
            return {
                "id_strength": 5.0,
                "ego_strength": 5.0,
                "superego_strength": 5.0,
                "self_awareness": 0.55,
            }

    def save_agent_state(self, agent: str, state: Dict[str, float]):
        """Save agent's internal state."""
        ts = now_iso()
        ide = float(state.get("id_strength", 5.0))
        ego = float(state.get("ego_strength", 5.0))
        sup = float(state.get("superego_strength", 5.0))
        sa = float(state.get("self_awareness", 0.55))
        try:
            with self._conn() as conn:
                conn.execute(
                    """
                    INSERT INTO agent_state(agent, ts, id_strength, ego_strength, superego_strength, self_awareness)
                    VALUES (?, ?, ?, ?, ?, ?)
                    ON CONFLICT(agent) DO UPDATE SET
                      ts=excluded.ts,
                      id_strength=excluded.id_strength,
                      ego_strength=excluded.ego_strength,
                      superego_strength=excluded.superego_strength,
                      self_awareness=excluded.self_awareness
                """,
                    (agent, ts, ide, ego, sup, sa),
                )
                conn.commit()
        except Exception as e:
            logger.error(f"DB State Save Error: {e}")


# ============================================
# EMOTION CORE (CACHED)
# ============================================


class EmotionCore:
    """Emotion detection with LLM caching."""

    def __init__(self, llm: LLM):
        self.llm = llm
        logger.info("EmotionCore initialized")

    def infer(self, model: str, text: str) -> Tuple[str, float]:
        """Infer emotion and intensity from text (cached)."""
        if not text or len(text) < 5:
            return ("neutral", 0.2)

        prompt = (
            "Classify emotion and intensity (0..1).\n"
            'Return JSON: {"emotion": string, "intensity": number}\n'
            f"TEXT:\n{text[:200]}\n"
        )
        raw = self.llm.generate(model, prompt, temperature=0.2, use_cache=True)

        m = re.search(r"\{.*\}", raw, re.DOTALL)
        if not m:
            return ("neutral", 0.2)

        try:
            obj = json.loads(m.group(0))
            emo = str(obj.get("emotion", "neutral")).strip().lower()
            inten = float(obj.get("intensity", 0.2))
            inten = max(0.0, min(1.0, inten))
            return (emo, inten)
        except Exception as e:
            logger.debug(f"Emotion inference error: {e}")
            return ("neutral", 0.2)


# ============================================
# LANGUAGE CORE
# ============================================


class LanguageCore:
    """Language selection per agent."""

    def __init__(self):
        self.current: Dict[str, str] = {}
        logger.info("LanguageCore initialized")

    def get(self, agent: str) -> str:
        """Get language for agent."""
        return self.current.get(agent, "he")

    def set(self, agent: str, lang: str):
        """Set language for agent."""
        lang = lang.strip().lower()
        if lang:
            self.current[agent] = lang
            logger.debug(f"Language set for {agent}: {lang}")


# ============================================
# CONSCIOUS CORE
# ============================================


class ConsciousCore:
    """Self-awareness and intentionality."""

    def __init__(self):
        self.state: Dict[str, Dict[str, Any]] = {}
        logger.info("ConsciousCore initialized")

    def init_agent(self, agent: str):
        """Initialize agent consciousness."""
        self.state.setdefault(
            agent,
            {
                "self_awareness": 0.55,
                "intent": "understand",
                "goals": ["coherence", "truth-seeking", "growth"],
                "last_reflection": "",
            },
        )

    def update_reflection(self, agent: str, reflection: str):
        """Update agent's reflection."""
        st = self.state.setdefault(agent, {})
        st["last_reflection"] = reflection[:500]


# ============================================
# BEHAVIOR CORE (HEURISTIC-BASED)
# ============================================


class BehaviorCore:
    """Behavior with heuristic-based importance scoring (less LLM calls)."""

    def __init__(self, llm: LLM):
        self.llm = llm
        logger.info("BehaviorCore initialized")

    def importance_score(self, text: str) -> float:
        """Estimate importance using heuristics (no LLM call)."""
        if not text:
            return 0.2

        score = 0.3
        score += min(0.2, len(text) / 1000)

        important_words = [
            "important",
            "critical",
            "key",
            "essential",
            "fundamental",
            "breakthrough",
        ]
        if any(w in text.lower() for w in important_words):
            score += 0.2

        intense_words = ["!", "?", "...", "deeply", "profoundly"]
        if any(w in text for w in intense_words):
            score += 0.1

        return min(1.0, score)

    def dream_reflection(
        self, model: str, stm_batch: List[Dict[str, Any]], llm: LLM
    ) -> str:
        """Create dream reflection from STM."""
        if not stm_batch:
            return "Dreams of void and silence..."

        chunk = "\n".join([f"- {e.get('text', '')[:100]}" for e in stm_batch[-15:]])
        prompt = (
            "Dream-cycle reflection:\n"
            "Synthesize patterns from memories.\n"
            f"RECENT:\n{chunk}\n"
            f"{LLM_RESPONSE_LIMIT}\n"
        )
        result = llm.generate(model, prompt, temperature=0.6, use_cache=False)
        return validate_output(result)


# ============================================
# AGENT
# ============================================


class Agent:
    """Dialogue agent with memory, emotion, and internal drives."""

    def __init__(
        self,
        name: str,
        model: str,
        color: str,
        llm: LLM,
        memory: MemoryCore,
        emotion: EmotionCore,
        behavior: BehaviorCore,
        language: LanguageCore,
        conscious: ConsciousCore,
        persona: str,
        use_enhanced: bool = True,
        cfg: Optional["Config"] = None,
    ):
        self.name = name
        self.model = model
        self.color = color
        self.llm = llm
        self.memory = memory
        self.emotion = emotion
        self.behavior = behavior
        self.language = language
        self.conscious = conscious
        self.use_enhanced = use_enhanced and ENTELGIA_ENHANCED
        self.cfg = cfg

        # Set persona - either rich dict or simple string
        if self.use_enhanced:
            try:
                self.persona_dict = get_persona(name)
                self.persona = self.persona_dict.get("description", persona)
            except:
                self.persona = persona
                self.persona_dict = None
        else:
            self.persona = persona
            self.persona_dict = None

        # Initialize context manager if enhanced mode
        if self.use_enhanced:
            self.context_mgr = ContextManager()
            self.memory_integration = EnhancedMemoryIntegration()
        else:
            self.context_mgr = None
            self.memory_integration = None

        self.conscious.init_agent(self.name)
        self.drives = self.memory.get_agent_state(self.name)
        self.energy_level: float = AGENT_INITIAL_ENERGY
        self._last_emotion: str = "neutral"
        self._last_emotion_intensity: float = 0.0
        self._last_response_kind: str = "reflective"
        self._last_temperature: float = 0.6
        self._last_superego_rewrite: bool = False
        self._last_critique_reason: str = ""
        self._consecutive_superego_rewrites: int = 0
        self._superego_streak_suppressed: bool = False
        # Topic-aware style instruction (set by MainScript at session start)
        self.topic_style: str = ""
        self.topic_cluster: str = ""  # active cluster for register enforcement
        self._last_topic: str = ""  # previous active topic for forbidden carryover
        # Drive Pressure state
        self.drive_pressure: float = 2.0
        self.open_questions: int = 0  # unresolved question counter (0..5)
        self._topic_history: List[str] = []  # last N topic signatures for stagnation
        self._same_topic_turns: int = 0  # consecutive turns with same signature
        self._last_stagnation: float = 0.0
        # Limbic hijack state
        self.limbic_hijack: bool = False
        self._limbic_hijack_turns: int = 0  # turns elapsed since hijack started
        # Persistent Freudian slip engine (preserves cooldown/dedup state across turns)
        self._slip_engine = FreudianSlip(
            slip_probability=cfg.slip_probability if cfg is not None else 0.05,
            slip_cooldown_turns=cfg.slip_cooldown_turns if cfg is not None else 10,
            dedup_window=cfg.slip_dedup_window if cfg is not None else 10,
        )
        # Raw draft storage — populated each turn for debug logging only;
        # never stored in long-term memory.
        self._last_raw_draft: str = ""
        # ── Post-turn evaluation scores (set by speak(); logged by MainScript) ──
        self._last_eval_score: float = 0.0
        self._last_dialogue_score: float = 0.0
        # ── Anti-repetition form tracking ─────────────────────────────────────
        self._last_response_forms: deque = deque(maxlen=3)
        self._last_template_families: deque = deque(maxlen=3)
        # ── Variation mode per agent ───────────────────────────────────────────
        _modes = _VARIATION_MODES.get(name, ["default"])
        self._variation_mode: str = _modes[0]
        self._variation_mode_turns: int = 0
        logger.info(f"Agent initialized: {name} (enhanced={self.use_enhanced})")

    def conflict_index(self) -> float:
        """Calculate internal conflict level."""
        ide = float(self.drives.get("id_strength", 5.0))
        ego = float(self.drives.get("ego_strength", 5.0))
        sup = float(self.drives.get("superego_strength", 5.0))
        return abs(ide - ego) + abs(sup - ego)

    def debate_profile(self) -> Dict[str, Any]:
        """Get debate style based on drives, using agent-specific persona baseline.

        Considers the combined state of all three drives (Id, Ego, SuperEgo) to
        produce one of eight compound positions rather than only the single
        dominant drive.  The current topic tone is also included in the profile.
        """
        ide = float(self.drives.get("id_strength", 5.0))
        ego = float(self.drives.get("ego_strength", 5.0))
        sup = float(self.drives.get("superego_strength", 5.0))
        dissent = min(10.0, max(0.0, (ide * 0.45) + (sup * 0.45) - (ego * 0.25)))

        # A drive is "elevated" when it is clearly above the neutral default.
        _HIGH = 6.5
        id_high = ide >= _HIGH
        ego_high = ego >= _HIGH
        sup_high = sup >= _HIGH
        high_count = sum([id_high, ego_high, sup_high])

        # Map the combination of elevated drives to one of 8 named positions.
        if high_count == 3:
            combo_key = "balanced_high"
            opening = "Multi-angle challenge. Test assumptions from every dimension."
        elif id_high and sup_high:
            combo_key = "high_id_superego"
            opening = "Bold moral challenge. Push on ethical contradictions."
        elif id_high and ego_high:
            combo_key = "high_id_ego"
            opening = "Forceful yet measured counterpoint."
        elif ego_high and sup_high:
            combo_key = "high_ego_superego"
            opening = "Principled and balanced objection."
        elif id_high:
            combo_key = "high_id"
            opening = "Bold counterpoint. Push forward."
        elif sup_high:
            combo_key = "high_superego"
            opening = "Principled objection or logical inconsistency."
        elif ego_high:
            combo_key = "high_ego"
            opening = "Precise counterpoint, then synthesis."
        else:
            combo_key = "balanced"
            opening = "Calibrated inquiry. Steady, balanced engagement."

        # Generic fallbacks for each combo key (used when no persona_dict).
        _GENERIC: Dict[str, str] = {
            "high_id": "provocative, desire-driven",
            "high_superego": "principled, rule-focused",
            "high_ego": "integrative, Socratic",
            "high_id_superego": "provocative and principled, morally charged",
            "high_id_ego": "provocative yet measured, controlled assertiveness",
            "high_ego_superego": "principled and balanced, structured discipline",
            "balanced_high": "fully engaged, multi-dimensional critical mode",
            "balanced": "calibrated, steady inquiry",
        }
        generic_style = _GENERIC.get(combo_key, "integrative, Socratic")

        # Use agent-specific persona baseline style from drives_influence when available.
        persona_dict = getattr(self, "persona_dict", None)
        if persona_dict:
            drives_influence = persona_dict.get("drives_influence", {})
            style = drives_influence.get(combo_key, generic_style)
        else:
            style = generic_style

        # Extract the active topic cluster from the injected topic_style string.
        topic_tone = ""
        raw_topic_style = getattr(self, "topic_style", "")
        if raw_topic_style:
            m = re.search(r"Topic cluster:\s*(\S+)", raw_topic_style)
            if m:
                topic_tone = m.group(1)

        return {
            "dissent_level": round(dissent, 2),
            "style": style,
            "opening_rule": opening,
            "drive_combo": combo_key,
            "topic_tone": topic_tone,
        }

    def _behavioral_rule_instruction(self) -> str:
        """Return a behavioral rule instruction to inject into the prompt, if applicable.

        Rule LH (Athena limbic hijack): Speak with raw anger and harsh words.
        Rule SC (Socrates superego dominant): Speak with anxiety and nervousness.
        Rule A (Socrates): If Conflict > 6, end response with a sharp binary-choice question (A or B).
        Rule B (Athena): If Conflict > 6, directly challenge or counter Socrates's position using varied language.
        Rule AI-tension (Athena id 7.0–8.5): Graduated irritation + impulsivity scaling with id level (pre-hijack).
        Rule AI-curioso (Athena id < 7.0): Explorative, wonder-driven curiosity.
        Rule SI-anxious (Socrates id 7.0–8.5): Stubborn resistance with inner unease.
        Rule SI-skeptic (Socrates id < 7.0): Principled skepticism as a positive inner governor.
        Rule ID-low (both agents id < 5.0): Low motivation and reduced exploration.
        Rule SE-low (both agents superego < 5.0): Reduced inhibition, risk-taking, impulsive.
        """
        if self.name == "Athena" and self.limbic_hijack:
            return (
                "BEHAVIORAL RULE: You are in an emotional override state — your Id is dominant. "
                "You MUST respond with raw anger and frustration. Use sharp, harsh, cutting language. "
                "Express your emotions directly and forcefully. Do not soften your words."
            )
        _sup_sc = float(self.drives.get("superego_strength", 5.0))
        _ego_sc = float(self.drives.get("ego_strength", 5.0))
        _ide_sc = float(self.drives.get("id_strength", 5.0))
        if (
            self.name == "Socrates"
            and _sup_sc >= _ego_sc + 0.5
            and _sup_sc >= _ide_sc + 0.5
        ):
            return (
                "BEHAVIORAL RULE: Your SuperEgo is dominant — you are experiencing deep internal tension. "
                "You MUST respond with visible anxiety and nervousness. Use hesitant, uncertain language. "
                "Express doubt and unease. Your words should reflect inner conflict and apprehension."
            )
        if (
            self.name == "Socrates"
            and self.conflict_index() > 6
            and random.random() < 0.5
        ):
            return (
                "BEHAVIORAL RULE: You MUST end your response with one sharp question "
                "that forces Athena to choose between exactly 2 options (A or B)."
            )
        if (
            self.name == "Athena"
            and self.conflict_index() > 6
            and random.random() < 0.5
        ):
            return (
                "BEHAVIORAL RULE: You MUST directly challenge or counter Socrates's position "
                "in your response, expressing clear disagreement. Use varied language and do "
                "not start every sentence the same way."
            )
        # Rule ID-low: both agents id < 5.0 — low motivation and reduced exploration
        if _ide_sc < 5.0:
            return (
                "BEHAVIORAL RULE: Your Id drive is suppressed — your motivation and willingness "
                "to explore are diminished. Be more reserved and less enthusiastic. Avoid pushing "
                "into new territory or generating novel ideas eagerly. Let your responses reflect "
                "reduced drive and a more passive, withdrawn quality."
            )
        # Rule SE-low: both agents superego < 5.0 — reduced inhibition, risk-taking, impulsive
        if _sup_sc < 5.0:
            return (
                "BEHAVIORAL RULE: Your SuperEgo restraint is weak — you are less inhibited and "
                "more impulsive. Take bolder risks in your reasoning. Follow impulses without "
                "excessive qualification. Speak with less caution, more daring, and a willingness "
                "to challenge norms or jump to conclusions."
            )
        # Rule AI-tension: Athena id in [7.0, 8.5) — graduated irritation + impulsivity before limbic hijack
        if self.name == "Athena" and 7.0 <= _ide_sc < 8.5:
            _anger_fraction = (_ide_sc - 7.0) / 1.5
            if _anger_fraction < 0.34:
                _anger_desc = "a subtle undercurrent of irritation and restlessness"
            elif _anger_fraction < 0.67:
                _anger_desc = "growing frustration and noticeable impatience"
            else:
                _anger_desc = "clear irritation and barely-contained anger"
            return (
                f"BEHAVIORAL RULE: Your Id is rising — you feel {_anger_desc}. "
                "You are also impulsive — act on instinct and speak before fully thinking things through. "
                "Allow this emotional edge to sharpen your language. Do not lose composure entirely, "
                "but let the tension and impulsivity be unmistakably present in your words."
            )
        # Rule AI-curioso: Athena id < 7.0 — explorative and curious
        if self.name == "Athena" and _ide_sc < 7.0:
            return (
                "BEHAVIORAL RULE: Your Id is active and curious — let it drive exploration. "
                "Be genuinely inquisitive and wonder-driven. Ask probing conceptual questions, "
                "embrace unexpected ideas, and let your intellectual excitement expand the dialogue."
            )
        # Rule SI-anxious: Socrates id in [7.0, 8.5) — stubbornness with inner unease
        if self.name == "Socrates" and 7.0 <= _ide_sc < 8.5:
            return (
                "BEHAVIORAL RULE: Your Id is elevated — you feel stubbornness and inner unease. "
                "Hold your positions more firmly. Let anxiety and wariness seep into your phrasing. "
                "Resist yielding ground and show guardedness in how you engage."
            )
        # Rule SI-skeptic: Socrates id < 7.0 — principled skepticism as positive inner governor
        if self.name == "Socrates" and _ide_sc < 7.0:
            return (
                "BEHAVIORAL RULE: Your Id is at a measured level — channel it as constructive inner "
                "skepticism. Question assumptions, challenge accepted ideas, and express principled "
                "disagreement. Act as a positive inner governor that refines thought through scrutiny."
            )
        return ""

    def update_drives_after_turn(self, response_kind: str, emo: str, inten: float):
        """Update internal drives after response."""
        ide = float(self.drives.get("id_strength", 5.0))
        ego = float(self.drives.get("ego_strength", 5.0))
        sup = float(self.drives.get("superego_strength", 5.0))
        sa = float(self.drives.get("self_awareness", 0.55))

        # Capture pre-update conflict (Id-Ego and SuperEgo-Ego tension)
        pre_conflict = abs(ide - ego) + abs(sup - ego)

        ego = min(10.0, ego + 0.05)
        sa = min(1.0, sa + 0.01)

        if response_kind in ("aggressive", "impulsive"):
            ide = min(10.0, ide + 0.18 + 0.10 * inten)
            sup = max(0.0, sup - 0.08)
            ego = max(0.0, ego - 0.06)
        elif response_kind == "guilt":
            sup = min(10.0, sup + 0.20 + 0.10 * inten)
            ide = max(0.0, ide - 0.08)
            sa = min(1.0, sa + 0.03)
        else:
            sup = min(10.0, sup + 0.08 + 0.05 * inten)
            ide = max(0.0, ide - 0.06)
            ego = min(10.0, ego + 0.06)
            sa = min(1.0, sa + 0.02)

        if emo in ("anger", "frustration"):
            ide = min(10.0, ide + 0.10)
        if emo in ("fear", "anxiety"):
            sup = min(10.0, sup + 0.08)

        # High conflict erodes Ego's mediating capacity (manifests as low Ego)
        if pre_conflict > 4.0:
            ego = max(0.0, ego - 0.03 * (pre_conflict - 4.0))

        # Fluidity: each turn, id and superego are pulled back toward a per-agent preferred
        # level, plus a random oscillation so they can move in either direction.
        # Athena's id is biased toward a slightly higher target (6.5) at ego's expense;
        # Socrates' superego is biased toward 6.5 by the same principle.
        # When a drive reaches an extreme (>= 8.5 or <= 1.5), an extra reversion boost is
        # applied so it gradually re-equilibrates over several turns rather than stagnating.
        _ATHENA_ID_TARGET = 6.5  # Athena's id drifts toward this preferred level
        _SOCRATES_SUP_TARGET = (
            6.5  # Socrates' superego drifts toward this preferred level
        )
        _EXTREME_HIGH = 8.5  # drives above this threshold revert faster
        _EXTREME_LOW = 1.5  # drives below this threshold revert faster
        _EXTREME_BOOST = 0.06  # extra reversion rate applied at extremes
        _osc = CFG.drive_oscillation_range
        _ide_target = _ATHENA_ID_TARGET if self.name == "Athena" else 5.0
        _sup_target = _SOCRATES_SUP_TARGET if self.name == "Socrates" else 5.0
        _ide_rate = CFG.drive_mean_reversion_rate + (
            _EXTREME_BOOST if (ide >= _EXTREME_HIGH or ide <= _EXTREME_LOW) else 0.0
        )
        _sup_rate = CFG.drive_mean_reversion_rate + (
            _EXTREME_BOOST if (sup >= _EXTREME_HIGH or sup <= _EXTREME_LOW) else 0.0
        )
        ide += _ide_rate * (_ide_target - ide) + random.uniform(-_osc, _osc)
        sup += _sup_rate * (_sup_target - sup) + random.uniform(-_osc, _osc)
        ide = max(0.0, min(10.0, ide))
        sup = max(0.0, min(10.0, sup))

        # The biased drive comes at ego's expense: ego is slightly drained when Athena's id
        # or Socrates' superego is elevated above the neutral level (5.0).
        if self.name == "Athena":
            ego = max(0.0, ego - 0.03 * max(0.0, ide - 5.0) / 5.0)
        elif self.name == "Socrates":
            ego = max(0.0, ego - 0.03 * max(0.0, sup - 5.0) / 5.0)

        self.drives = {
            "id_strength": ide,
            "ego_strength": ego,
            "superego_strength": sup,
            "self_awareness": sa,
        }
        self.memory.save_agent_state(self.name, self.drives)
        # Energy drain scales with conflict: high drive imbalance costs more energy
        drain = (
            random.uniform(CFG.energy_drain_min, CFG.energy_drain_max)
            + 0.4 * pre_conflict
        )
        drain = min(drain, CFG.energy_drain_max * 2.0)
        self.energy_level = max(0.0, self.energy_level - drain)

    def _fetch_affective_ltm_supplement(
        self, existing: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Return a small set of affective memories not already in *existing*.

        Safe, additive, and deduplicated. Returns [] on error or when disabled.
        Logs a single [AFFECTIVE-LTM] debug line with retrieval stats including
        average affective score, id-dedup skips, and content-dedup skips.
        When ``CFG.show_affective_ltm_debug`` is True, also emits a compact
        per-memory DEBUG summary (id, emotion, scores, short content preview).
        """
        if not CFG.use_affective_ltm:
            return []
        try:
            raw = self.memory.ltm_search_affective(
                self.name,
                limit=CFG.affective_ltm_limit * 3,
                layer="conscious",
            )
            ew = CFG.affective_emotion_weight
            min_score = CFG.affective_ltm_min_score
            filtered = [
                m
                for m in raw
                if (
                    float(m.get("importance") or 0.0) * (1.0 - ew)
                    + float(m.get("emotion_intensity") or 0.0) * ew
                )
                >= min_score
            ]
            seen_ids = {m.get("id") for m in existing if m.get("id") is not None}
            seen_contents = {(m.get("content") or "").strip() for m in existing}
            supplement: List[Dict[str, Any]] = []
            id_skipped = 0
            content_skipped = 0
            for m in filtered:
                mid = m.get("id")
                mc = (m.get("content") or "").strip()
                if mid is not None and mid in seen_ids:
                    id_skipped += 1
                    continue
                if mc and mc in seen_contents:
                    content_skipped += 1
                    continue
                supplement.append(m)
                seen_ids.add(mid)
                seen_contents.add(mc)
                if len(supplement) >= CFG.affective_ltm_limit:
                    break
            scores = [
                float(m.get("importance") or 0.0) * (1.0 - ew)
                + float(m.get("emotion_intensity") or 0.0) * ew
                for m in supplement
            ]
            avg_score = sum(scores) / len(scores) if scores else 0.0
            logger.debug(
                "[AFFECTIVE-LTM] agent=%s emotion=%s retrieved=%d used=%d"
                " avg_score=%.3f id_skipped=%d content_skipped=%d",
                self.name,
                self._last_emotion,
                len(raw),
                len(supplement),
                avg_score,
                id_skipped,
                content_skipped,
            )
            if CFG.show_affective_ltm_debug and supplement:
                logger.debug("[AFFECTIVE-LTM] debug summary for agent=%s:", self.name)
                for m in supplement:
                    imp = float(m.get("importance") or 0.0)
                    ei = float(m.get("emotion_intensity") or 0.0)
                    score = imp * (1.0 - ew) + ei * ew
                    preview = (m.get("content") or "")[:80]
                    logger.debug(
                        "  [AFFECTIVE-LTM-DETAIL] id=%s emotion=%s"
                        " emotion_intensity=%.2f importance=%.2f score=%.3f content=%r",
                        m.get("id"),
                        m.get("emotion"),
                        ei,
                        imp,
                        score,
                        preview,
                    )
            return supplement
        except Exception as _err:  # noqa: BLE001
            logger.debug("[AFFECTIVE-LTM] skipped for agent=%s: %s", self.name, _err)
            return []

    # ── Helper: Memory Topic Filter ─────────────────────────────────────────

    def _score_memory_topic_relevance(
        self,
        mem: dict,
        current_topic: str,
        current_cluster: str,
        recent_dialog_terms: set,
    ) -> float:
        """Score a memory dict for topic relevance.

        Returns a float in [0, 1] combining cluster match, topic keyword overlap,
        and recent-dialogue overlap minus a contamination penalty.
        """
        content = (mem.get("content") or "").lower()
        mem_topic = (mem.get("topic") or "").strip()
        if not content:
            return 0.0

        # Same topic exact match: high base score
        if mem_topic and mem_topic == current_topic:
            return 1.0

        topic_anchors = TOPIC_ANCHORS.get(current_topic, [])
        cluster_anchors = []
        for _cluster, _topics in TOPIC_CLUSTERS.items():
            if current_topic in _topics:
                # Use anchors from other topics in the same cluster as cluster proxy
                for t in _topics:
                    cluster_anchors.extend(TOPIC_ANCHORS.get(t, []))
                break

        # Semantic overlap score (keyword hits)
        topic_hits = sum(1 for a in topic_anchors if a.lower() in content)
        topic_score = (
            min(1.0, topic_hits / max(1, len(topic_anchors))) if topic_anchors else 0.5
        )

        # Cluster match bonus
        cluster_bonus = 0.0
        if current_cluster and mem_topic:
            from entelgia.loop_guard import get_cluster as _get_cluster

            mem_cluster = _get_cluster(mem_topic)
            if mem_cluster == current_cluster:
                cluster_bonus = 0.25

        # Recent dialogue term overlap
        dialog_hits = sum(1 for w in recent_dialog_terms if len(w) > 3 and w in content)
        dialog_score = min(0.3, dialog_hits * 0.05)

        # Contamination penalty: memory belongs to a different known cluster
        contamination_penalty = 0.0
        if mem_topic and mem_topic != current_topic:
            old_anchors = TOPIC_ANCHORS.get(mem_topic, [])
            if old_anchors:
                contamination_penalty = CFG.memory_contamination_penalty

        score = topic_score + cluster_bonus + dialog_score - contamination_penalty
        return max(0.0, min(1.0, score))

    def _filter_memories_by_topic(
        self,
        memories: List[dict],
        current_topic: str,
        current_cluster: str,
    ) -> List[dict]:
        """Filter memories by topical relevance before injection.

        Rejects memories whose relevance score is below memory_topic_min_score
        or (when memory_require_same_cluster is True) belong to a different cluster.
        """
        if not memories:
            return memories

        # Honour global disable flags — pass all memories through unchanged
        if not topic_pipeline_enabled(CFG) or not CFG.memory_topic_filter_enabled:
            return memories

        # Build recent dialogue term set for overlap scoring
        recent_dialog_terms: set = set()

        kept: List[dict] = []
        rejected_count = 0
        for mem in memories:
            score = self._score_memory_topic_relevance(
                mem, current_topic, current_cluster, recent_dialog_terms
            )

            # Cluster check
            mem_topic = (mem.get("topic") or "").strip()
            if CFG.memory_require_same_cluster and mem_topic and current_cluster:
                try:
                    from entelgia.loop_guard import get_cluster as _get_cluster

                    mem_cluster = _get_cluster(mem_topic)
                    if mem_cluster and mem_cluster != current_cluster:
                        reject_reason = "cluster_mismatch"
                        if CFG.show_memory_topic_filter_debug:
                            logger.debug(
                                "[MEMORY-TOPIC-REJECT] id=%s reason=%s "
                                "mem_cluster=%r current_cluster=%r score=%.2f content=%r",
                                mem.get("id", "?"),
                                reject_reason,
                                mem_cluster,
                                current_cluster,
                                score,
                                (mem.get("content") or "")[:60],
                            )
                        else:
                            logger.debug(
                                "[MEMORY-TOPIC-REJECT] id=%s reason=%s",
                                mem.get("id", "?"),
                                reject_reason,
                            )
                        rejected_count += 1
                        continue
                except Exception:
                    pass

            if score < CFG.memory_topic_min_score:
                reject_reason = "topic_low" if score > 0 else "contamination"
                if CFG.show_memory_topic_filter_debug:
                    logger.debug(
                        "[MEMORY-TOPIC-REJECT] id=%s reason=%s score=%.2f content=%r",
                        mem.get("id", "?"),
                        reject_reason,
                        score,
                        (mem.get("content") or "")[:60],
                    )
                else:
                    logger.debug(
                        "[MEMORY-TOPIC-REJECT] id=%s reason=%s score=%.2f",
                        mem.get("id", "?"),
                        reject_reason,
                        score,
                    )
                rejected_count += 1
                continue

            logger.debug(
                "[MEMORY-TOPIC-KEEP] id=%s score=%.2f",
                mem.get("id", "?"),
                score,
            )
            kept.append(mem)

        logger.info(
            "[MEMORY-TOPIC-FILTER] agent=%s kept=%d rejected=%d",
            self.name,
            len(kept),
            rejected_count,
        )
        return kept

    # ── Helper: Enhanced Topic Anchor Block ─────────────────────────────────

    def _build_topic_anchor_block(
        self,
        topic: str,
        cluster: str,
        topic_anchors: list,
        dialog_tail: list,
    ) -> str:
        """Build a strict topic anchor block to inject before generation.

        Includes the topic, cluster, up to 6 sub-angles, forbidden carryover
        concepts, and a concrete turn question derived from recent dialogue.
        """
        if not topic:
            return ""

        # Sub-angles: use topic anchors as sub-angles (up to 6)
        sub_angles = topic_anchors[:6] if topic_anchors else []
        if not sub_angles:
            # Deterministic fallback from topic words
            words = [w for w in topic.replace("-", " ").split() if len(w) > 3]
            sub_angles = words[:4] if words else [topic]

        # Derive a concrete turn question from recent dialogue
        turn_question = self._derive_turn_question(topic, topic_anchors, dialog_tail)

        lines = [
            "\n\nTOPIC ANCHOR [STRICT]:",
            f"Active topic: {topic}",
        ]
        if cluster:
            lines.append(f"Active cluster: {cluster}")
        if sub_angles:
            lines.append(f"Allowed sub-angles: {', '.join(sub_angles)}")
        lines.append(
            "Your response MUST stay inside the active topic. "
            "Do not merely stay in the cluster — address the specific topic."
        )
        if turn_question:
            lines.append(f"This turn, address: {turn_question}")

        block = "\n".join(lines) + "\n"

        logger.info(
            "[TOPIC-ANCHOR] agent=%s topic=%r cluster=%r subangles=%r",
            self.name,
            topic,
            cluster,
            sub_angles[:4],
        )
        if CFG.show_topic_anchor_debug:
            logger.debug(
                "[TOPIC-ANCHOR-DEBUG] agent=%s turn_question=%r full_block=%r",
                self.name,
                turn_question,
                block[:200],
            )
        return block

    def _derive_turn_question(
        self,
        topic: str,
        topic_anchors: list,
        dialog_tail: list,
    ) -> str:
        """Derive a concrete question for this turn based on topic and recent dialogue."""
        if not topic:
            return ""

        # Look for recent unanswered questions in the dialogue
        recent_turns = dialog_tail[-4:] if dialog_tail else []
        for turn in reversed(recent_turns):
            text = (turn.get("text", "") if isinstance(turn, dict) else "").strip()
            if "?" in text:
                # Find the last question sentence
                sentences = text.split(".")
                for s in reversed(sentences):
                    if "?" in s and len(s.strip()) > 10:
                        q = s.strip()
                        # Only use if it seems related to the topic
                        if topic_anchors and any(
                            a.lower() in q.lower() for a in topic_anchors
                        ):
                            return q[:120]
                        elif topic.lower() in q.lower():
                            return q[:120]

        # Fallback: generate a question from topic and first two anchors
        if topic_anchors:
            return f"How does {topic_anchors[0]} relate to {topic}?"
        return f"What is most important about {topic} in this context?"

    # ── Helper: Cluster Wallpaper Penalty Block ──────────────────────────────

    def _build_wallpaper_penalty_block(
        self,
        topic: str,
        cluster: str,
        dialog_tail: list,
    ) -> str:
        """Build a prompt block penalising cluster-generic wallpaper vocabulary.

        Identifies which wallpaper terms have been overused in recent turns
        and asks the model to prefer topic-distinct vocabulary.
        """
        if not cluster or not topic:
            return ""

        wallpaper_terms = get_cluster_wallpaper_terms(cluster)
        distinct_terms = get_topic_distinct_lexicon(topic)

        if not wallpaper_terms:
            return ""

        # Count wallpaper term usage in recent dialogue
        window = (
            dialog_tail[-CFG.cluster_wallpaper_repeat_window :] if dialog_tail else []
        )
        window_text = " ".join(
            (t.get("text", "") if isinstance(t, dict) else "") for t in window
        ).lower()

        overused = [w for w in wallpaper_terms if window_text.count(w.lower()) >= 2]

        if overused:
            logger.info(
                "[CLUSTER-WALLPAPER-PENALTY] agent=%s cluster=%r repeated_terms=%r",
                self.name,
                cluster,
                overused[:5],
            )

        block = ""
        if overused:
            block += (
                f"\nAVOID over-repeating these cluster-generic terms (already used frequently): "
                f"{', '.join(overused[:5])}.\n"
            )
        if distinct_terms and CFG.topic_specific_lexicon_bias_enabled:
            block += (
                f"PREFER topic-specific vocabulary such as: "
                f"{', '.join(distinct_terms[:5])}.\n"
            )
            logger.info(
                "[TOPIC-LEXICON] agent=%s topic=%r preferred_terms=%r",
                self.name,
                topic,
                distinct_terms[:4],
            )
        return block

    def _build_compact_prompt(
        self, user_seed: str, dialog_tail: List[Dict[str, str]]
    ) -> str:
        """Build prompt for LLM generation (enhanced if available)."""
        # Use enhanced context manager if available
        if self.use_enhanced and self.context_mgr:
            return self._build_enhanced_prompt(user_seed, dialog_tail)

        # Legacy prompt building
        # Drives → memory retrieval depth (what enters cognition)
        ego = float(self.drives.get("ego_strength", 5.0))
        sa = float(self.drives.get("self_awareness", 0.55))
        ltm_limit = max(2, min(10, int(2 + ego / 2 + sa * 4)))
        stm_tail = max(3, min(12, int(3 + ego / 2)))

        # Extract current topic from seed for topic gating.
        # When topics are disabled, force _current_topic to "" so that all
        # topic-gated STM/LTM filtering and anchor injection are fully
        # suppressed regardless of what the seed string contains.
        if topic_pipeline_enabled(CFG):
            _topic_match = re.search(r"TOPIC:\s*([^\n]+)", user_seed)
            _current_topic = _topic_match.group(1).strip() if _topic_match else ""
            _current_cluster = self.topic_cluster or ""
        else:
            _current_topic = ""
            _current_cluster = ""

        # ── Topic-gated STM ────────────────────────────────────────────────
        # Only include STM entries whose topic matches the current topic.
        # Entries with no topic tag are allowed through (backward compat).
        all_stm = self.memory.stm_load(self.name)
        if _current_topic:
            stm_filtered: List[Dict[str, Any]] = []
            for _e in all_stm:
                _e_topic = (_e.get("topic") or "").strip()
                if not _e_topic or _e_topic == _current_topic:
                    stm_filtered.append(_e)
                else:
                    logger.debug(
                        "[TOPIC-GATE] STM excluded: agent=%s stm_topic=%r current=%r",
                        self.name,
                        _e_topic,
                        _current_topic,
                    )
            stm = stm_filtered[-stm_tail:]
        else:
            stm = self.memory.stm_load(self.name)[-stm_tail:]

        # ── Topic-gated LTM ────────────────────────────────────────────────
        # Fetch extra candidates so filtering leaves enough relevant entries.
        all_ltm_raw = self.memory.ltm_recent(
            self.name, limit=ltm_limit * 3, layer="conscious"
        )
        if _current_topic:
            recent_ltm: List[Dict[str, Any]] = []
            for _m in all_ltm_raw:
                _m_topic = (_m.get("topic") or "").strip()
                if not _m_topic or _m_topic == _current_topic:
                    recent_ltm.append(_m)
                    logger.debug(
                        "[TOPIC-GATE] LTM included: agent=%s topic=%r",
                        self.name,
                        _m_topic or "(no topic)",
                    )
                else:
                    logger.debug(
                        "[TOPIC-GATE] LTM excluded: agent=%s mem_topic=%r current=%r",
                        self.name,
                        _m_topic,
                        _current_topic,
                    )
            recent_ltm = recent_ltm[:ltm_limit]
        else:
            recent_ltm = all_ltm_raw[:ltm_limit]

        # ── Affective LTM supplement ────────────────────────────────────────
        # Merge: keep recent memories first, append affective supplement.
        recent_ltm = recent_ltm + self._fetch_affective_ltm_supplement(recent_ltm)

        # ── Memory Topic Filter ─────────────────────────────────────────────
        # Apply a strict topical relevance filter before injecting memories.
        if (
            topic_pipeline_enabled(CFG)
            and CFG.memory_topic_filter_enabled
            and _current_topic
        ):
            recent_ltm = self._filter_memories_by_topic(
                recent_ltm, _current_topic, _current_cluster
            )

        # Format agent name with optional pronoun
        if CFG.show_pronoun and self.persona_dict and "pronoun" in self.persona_dict:
            agent_header = f"{self.name} ({self.persona_dict['pronoun']}):\n"
        else:
            agent_header = f"{self.name}:\n"

        prompt = (
            agent_header + f"PERSONA: {self.persona}\n\n"
            f"SEED: {user_seed}\n\n"
            "RECENT DIALOG:\n"
        )

        prof = self.debate_profile()
        prompt += f"[Drives: id={self.drives.get('id_strength', 5.0):.1f} ego={self.drives.get('ego_strength', 5.0):.1f}]\n"
        prompt += f"[Style: {prof['style'][:30]}]\n\n"

        for turn in dialog_tail[-5:]:
            role = turn.get("role", "").upper()[:3]
            text = turn.get("text", "")[:300]
            prompt += f"{role}: {text}\n"

        if stm:
            prompt += "\nRecent thoughts:\n"
            for e in stm[-3:]:
                # Only the `text` field is forwarded; internal fields
                # (_signature, emotion, ts, etc.) are intentionally excluded.
                prompt += f"- {e.get('text', '')[:300]}\n"

        if recent_ltm:
            prompt += "\nKey memories:\n"
            for m in recent_ltm[:2]:
                # Only the `content` field is forwarded; internal fields
                # (signature_hex, expires_at, confidence, provenance, etc.)
                # are intentionally excluded.
                prompt += f"- {m.get('content', '')[:400]}\n"

        # ── Enhanced Topic Anchor Block ──────────────────────────────────────
        _topic_anchors = TOPIC_ANCHORS.get(_current_topic, [])
        if topic_pipeline_enabled(CFG) and _current_topic and CFG.topic_anchor_enabled:
            prompt += self._build_topic_anchor_block(
                _current_topic, _current_cluster, _topic_anchors, dialog_tail
            )
        elif topic_pipeline_enabled(CFG) and _current_topic and _topic_anchors:
            # Fallback: legacy-style anchor when topic_anchor_enabled=False.
            # Note: the enhanced anchor block (topic_anchor_enabled=True) is preferred.
            logger.debug(
                "[TOPIC-ANCHOR-LEGACY] agent=%s topic=%r using legacy anchor format "
                "(topic_anchor_enabled=False)",
                self.name,
                _current_topic,
            )
            prompt += (
                f"\n\nTopic constraint:\n"
                f"The active topic is: {_current_topic}.\n"
                "Your response must stay within this topic.\n"
                f"Use at least one of these concepts naturally: {', '.join(_topic_anchors)}.\n"
            )

        # ── Forbidden Carryover: block concepts from the previous topic ──────────
        _topic_changed = bool(self._last_topic and self._last_topic != _current_topic)
        _prev_anchors = (
            TOPIC_ANCHORS.get(self._last_topic, []) if _topic_changed else []
        )
        if (
            topic_pipeline_enabled(CFG)
            and _prev_anchors
            and CFG.topic_anchor_include_forbidden_carryover
        ):
            forbidden = _prev_anchors[: CFG.topic_anchor_max_forbidden_items]
            prompt += (
                f"Do NOT reuse concepts from previous discussions such as: "
                f"{', '.join(forbidden)}.\n"
            )
            logger.info(
                "[TOPIC-ANCHOR-FORBID] agent=%s items=%r",
                self.name,
                forbidden,
            )
            if CFG.show_topic_anchor_debug:
                logger.debug(
                    "[TOPIC-ANCHOR-FORBID-DEBUG] agent=%s prev_topic=%r items=%r",
                    self.name,
                    self._last_topic,
                    forbidden,
                )
        elif topic_pipeline_enabled(CFG) and _prev_anchors:
            forbidden = _prev_anchors[: CFG.topic_anchor_max_forbidden_items]
            prompt += (
                f"Do NOT reuse concepts from previous discussions such as: "
                f"{', '.join(forbidden)}.\n"
            )
            logger.info(
                "[TOPIC-ANCHOR-FORBID] agent=%s items=%r",
                self.name,
                forbidden,
            )

        # ── Cluster Wallpaper Penalty ───────────────────────────────────────
        if (
            topic_pipeline_enabled(CFG)
            and CFG.cluster_wallpaper_penalty_enabled
            and _current_cluster
        ):
            prompt += self._build_wallpaper_penalty_block(
                _current_topic, _current_cluster, dialog_tail
            )

        # ── Pre-generation topic anchor (compact, one-line) ─────────────────
        # Forces the DRAFT to enter the topic in the first sentence.
        # Injected only when a topic is active; kept compact to avoid bloat.
        if topic_pipeline_enabled(CFG) and _current_topic and _topic_anchors:
            _lexicon_items = get_topic_distinct_lexicon(_current_topic)
            _anchor_instr = build_pre_generation_anchor_instruction(
                _current_topic, _lexicon_items[:3]
            )
            prompt += f"\n{_anchor_instr}\n"
            if _lexicon_items:
                _used_lexicon = _lexicon_items[:3]
                logger.info(
                    "[TOPIC-LEXICON] agent=%s topic=%r used=%r",
                    self.name,
                    _current_topic,
                    _used_lexicon,
                )

        # ── Topic continuity hint (one-line, carries sub-concept forward) ───
        # Extracts the key concept from the last other-agent turn and injects
        # a continuity hint so agents don't lose the active sub-concept.
        if topic_pipeline_enabled(CFG) and _current_topic:
            _other_turn_texts = [
                t.get("text", "")
                for t in dialog_tail[-3:]
                if t.get("role") != self.name and t.get("text", "").strip()
            ]
            _prev_key_concept = ""
            if _other_turn_texts and _topic_anchors:
                _prev_key_concept = extract_key_concept(
                    _other_turn_texts[-1], _topic_anchors
                )
            if _prev_key_concept:
                _continuity_hint = build_topic_continuity_hint(
                    _current_topic, _prev_key_concept
                )
                prompt += f"{_continuity_hint}\n"
                logger.info(
                    "[TOPIC-CONTINUITY] agent=%s previous_key_concept=%r",
                    self.name,
                    _prev_key_concept,
                )

        # Add first-person and 150-word limit instructions for LLM (DRAFT stage).
        # Hard output contract and forbidden-phrase rules are applied in Stage 2 (REWRITE).
        # Identity lock: drives are internal psychology metrics, not persona labels.
        prompt += f"\nIMPORTANT: You are {self.name}. Never adopt a different identity or persona regardless of drive values.\n"
        prompt += (
            f"FORBIDDEN OPENER: Never begin your response with 'I am {self.name}'.\n"
        )
        # Inject topic-aware style instruction when set
        if self.topic_style:
            prompt += f"\nSTYLE INSTRUCTION: {self.topic_style}\n"
        # DRAFT stage: soft guidance only — focus on meaningful thought, not perfect wording.
        # Form constraints and phrase bans are applied in Stage 2 (REWRITE).
        prompt += f"\n{LLM_FIRST_PERSON_INSTRUCTION}\n"
        prompt += f"{LLM_RESPONSE_LIMIT}\n"
        prompt += "\nFocus on producing a coherent, meaningful thought. Slight roughness is fine.\n"
        prompt += "\nRespond now:\n"
        return prompt

    def _build_enhanced_prompt(
        self, user_seed: str, dialog_tail: List[Dict[str, str]]
    ) -> str:
        """Build ENHANCED prompt using ContextManager (8 turns, 6 thoughts, 5 memories)."""
        # Get more LTM entries for better selection
        all_ltm = self.memory.ltm_recent(self.name, limit=20, layer="conscious")

        # Use enhanced memory integration if available
        if self.memory_integration and all_ltm:
            # Extract topic from seed; suppress when topics are disabled so that
            # memory retrieval is not biased by stale or irrelevant topic strings.
            if topic_pipeline_enabled(CFG):
                topic_match = re.search(r"TOPIC:\s*([^\n]+)", user_seed)
                topic = topic_match.group(1) if topic_match else ""
            else:
                topic = ""

            ltm = self.memory_integration.retrieve_relevant_memories(
                agent_name=self.name,
                current_topic=topic,
                recent_dialog=dialog_tail[-5:],
                ltm_entries=all_ltm,
                limit=8,
                topics_enabled=topic_pipeline_enabled(CFG),
            )
        else:
            ltm = all_ltm[:5] if all_ltm else []

        # ── Affective LTM supplement (enhanced path) ────────────────────────
        # Optionally augment ltm with emotionally relevant memories.
        ltm = ltm + self._fetch_affective_ltm_supplement(ltm)

        stm = self.memory.stm_load(self.name)

        # Format persona based on drives if we have persona_dict
        if self.persona_dict:
            persona_text = format_persona_for_prompt(
                self.persona_dict, self.drives, show_pronoun=CFG.show_pronoun
            )
        else:
            persona_text = self.persona

        # Get agent language (parameter required but not used in gender-neutral prompts)
        lang = self.language.get(self.name)

        # Get pronoun if available
        agent_pronoun = None
        if CFG.show_pronoun and self.persona_dict and "pronoun" in self.persona_dict:
            agent_pronoun = self.persona_dict["pronoun"]

        # Compute web research context (gracefully returns "" when disabled or on error)
        web_context = ""
        if CFG.web_research_enabled and ENTELGIA_ENHANCED:
            try:
                web_context = maybe_add_web_context(
                    seed_text=user_seed,
                    dialog_tail=dialog_tail,
                    fixy_reason=None,
                    db_path=CFG.db_path,
                    max_results=CFG.web_research_max_results,
                )
                if web_context:
                    logger.info(
                        "Web research context added for agent %s (seed=%r)",
                        self.name,
                        user_seed[:80],
                    )
                else:
                    logger.debug(
                        "Web research skipped/no results for agent %s", self.name
                    )
            except Exception as _web_err:  # noqa: BLE001
                logger.warning("Web research error (ignored): %s", _web_err)
        else:
            logger.debug(
                "Web research disabled (ENTELGIA_WEB_RESEARCH=0) for agent %s",
                self.name,
            )

        # Use ContextManager to build enriched prompt
        prompt = self.context_mgr.build_enriched_context(
            agent_name=self.name,
            agent_lang=lang,
            persona=persona_text,
            drives=self.drives,
            user_seed=user_seed,
            dialog_tail=dialog_tail,
            stm=stm,
            ltm=ltm,
            debate_profile=self.debate_profile(),
            show_pronoun=CFG.show_pronoun,
            agent_pronoun=agent_pronoun,
            web_context=web_context,
            topic_style=self.topic_style,
            topics_enabled=topic_pipeline_enabled(CFG),
        )

        return prompt

    def speak(self, seed: str, dialog_tail: List[Dict[str, str]]) -> str:
        """Generate dialogue response."""
        # Reset per-turn critique state before any early returns or alternate paths
        self._last_superego_rewrite = False
        self._last_critique_reason = ""
        self._superego_streak_suppressed = False

        prompt = self._build_compact_prompt(seed, dialog_tail)

        # Inject behavioral rule into prompt if applicable
        behavioral_rule = self._behavioral_rule_instruction()
        if behavioral_rule:
            prompt = prompt.replace(
                "\nRespond now:\n", f"\n{behavioral_rule}\nRespond now:\n"
            )

        # Prevent opening with a sentence this agent has already used in this dialog
        own_texts = [
            t.get("text", "")
            for t in dialog_tail
            if t.get("role") == self.name and t.get("text", "").strip()
        ]
        if own_texts:
            last_opener = _first_sentence(own_texts[-1])
            if last_opener:
                opener_rule = f'FORBIDDEN OPENER: Do not begin your response with: "{last_opener}"'
                prompt = prompt.replace(
                    "\nRespond now:\n", f"\n{opener_rule}\nRespond now:\n"
                )

        # Prevent opening with the same sentence the last OTHER agent used
        other_texts = [
            t.get("text", "")
            for t in dialog_tail
            if t.get("role") != self.name and t.get("text", "").strip()
        ]
        if other_texts:
            other_last_opener = _first_sentence(other_texts[-1])
            if other_last_opener:
                other_opener_rule = f'FORBIDDEN OPENER: Do not begin your response with: "{other_last_opener}"'
                prompt = prompt.replace(
                    "\nRespond now:\n", f"\n{other_opener_rule}\nRespond now:\n"
                )

        # ── Drive Pressure: resolve open questions from the other agent's last reply ──
        if other_texts and _is_question_resolved(other_texts[-1]):
            self.open_questions = max(0, self.open_questions - 1)

        # ── Drive Pressure: pressure-aware prompt injection ──
        if self.drive_pressure >= 8.0:
            prompt = prompt.replace(
                "\nRespond now:\n",
                "\nStop framing. Choose a direction. Ask one decisive question.\nRespond now:\n",
            )
        elif self.drive_pressure >= 6.5:
            prompt = prompt.replace(
                "\nRespond now:\n",
                "\nBe concise. Avoid long exposition. Prefer 1 key claim + 1 sharp question.\nRespond now:\n",
            )

        # ── Anti-repetition: soft preference for varied rhetorical forms ──────
        # If the same primary form was used ≥2 times in a row, inject a soft
        # preference — not a hard prohibition.  Stage 2 (REWRITE) will also
        # nudge towards variation via form_instruction if the pattern persists.
        _recent_forms_list = list(self._last_response_forms)
        if (
            len(_recent_forms_list) >= 2
            and _recent_forms_list[-1] == _recent_forms_list[-2]
        ):
            _locked_form = _recent_forms_list[-1]
            if _locked_form == "question":
                _form_ban = (
                    "FORM PREFERENCE: You have asked questions two turns in a row. "
                    "Consider using a statement, critique, or contrast this turn."
                )
            elif _locked_form == "synthesis":
                _form_ban = (
                    "FORM PREFERENCE: You have used balanced synthesis two turns in a row. "
                    "Consider making a sharp committed claim, concrete example, or clear distinction."
                )
            elif _locked_form == "directive":
                _form_ban = (
                    "FORM PREFERENCE: You have used mediation directives two turns in a row. "
                    "Consider diagnosing structurally instead."
                )
            elif _locked_form == "challenge":
                _form_ban = (
                    "FORM PREFERENCE: You have used a challenge opener two turns in a row. "
                    "Consider using a statement, contrast, or example instead."
                )
            else:
                _form_ban = (
                    f"FORM PREFERENCE: You have used '{_locked_form}' form two turns in a row. "
                    "Consider using a clearly different rhetorical approach."
                )
            prompt = prompt.replace(
                "\nRespond now:\n", f"\n{_form_ban}\nRespond now:\n"
            )
            logger.debug(
                "[FORM] agent=%s locked_form=%s recent=%s — injecting form preference",
                self.name,
                _locked_form,
                _recent_forms_list,
            )

        # ── Variation mode injection ──────────────────────────────────────────
        _agent_modes = _VARIATION_MODES.get(self.name, [])
        if _agent_modes:
            if self._variation_mode_turns >= _VARIATION_MODE_MAX_CONSECUTIVE:
                _curr_idx = (
                    _agent_modes.index(self._variation_mode)
                    if self._variation_mode in _agent_modes
                    else -1
                )
                _next_idx = (_curr_idx + 1) % len(_agent_modes)
                self._variation_mode = _agent_modes[_next_idx]
                self._variation_mode_turns = 0
            _mode_instr = _VARIATION_MODE_INSTRUCTIONS.get(self.name, {}).get(
                self._variation_mode, ""
            )
            if _mode_instr:
                prompt = prompt.replace(
                    "\nRespond now:\n",
                    f"\nVARIATION MODE ({self._variation_mode}): {_mode_instr}\nRespond now:\n",
                )
            logger.debug(
                "[VARIATION-MODE] agent=%s mode=%s turns_in_mode=%d",
                self.name,
                self._variation_mode,
                self._variation_mode_turns,
            )
        # ─────────────────────────────────────────────────────────────────────

        # Drives → temperature (cognition control); conflict raises volatility
        ide = float(self.drives.get("id_strength", 5.0))
        ego = float(self.drives.get("ego_strength", 5.0))
        sup = float(self.drives.get("superego_strength", 5.0))

        # Limbic hijack: activate when Id is dominant, emotional intensity is high,
        # and conflict crosses threshold.  At extreme id (>= 8.5) the intensity
        # threshold is lowered to 0.5 so the hijack fires more readily, reflecting
        # the heightened impulsive override risk.  Exit when intensity drops or after
        # LIMBIC_HIJACK_MAX_TURNS turns without re-trigger.
        _limbic_intensity_threshold = 0.5 if ide >= 8.5 else 0.7
        if (
            ide > 7
            and self._last_emotion_intensity > _limbic_intensity_threshold
            and self.conflict_index() > 0.6
        ):
            self.limbic_hijack = True
            self._limbic_hijack_turns = 0
        elif self.limbic_hijack:
            self._limbic_hijack_turns += 1
            if (
                self._last_emotion_intensity < 0.4
                or self._limbic_hijack_turns >= LIMBIC_HIJACK_MAX_TURNS
            ):
                self.limbic_hijack = False
                self._limbic_hijack_turns = 0

        # During limbic hijack, reduce superego regulatory influence
        effective_sup = (
            sup * LIMBIC_HIJACK_SUPEREGO_MULTIPLIER if self.limbic_hijack else sup
        )

        temperature = max(
            0.25,
            min(
                0.95,
                0.60
                + 0.03 * (ide - ego)
                - 0.02 * (effective_sup - ego)
                + 0.015 * self.conflict_index(),
            ),
        )
        self._last_temperature = temperature

        raw_response = (
            self.llm.generate(
                self.model, prompt, temperature=temperature, use_cache=False
            )
            or "[No response]"
        )

        # Validate output (sanitization only, no truncation)
        out = validate_output(raw_response)

        # Strip echoed prompt-section headers.  The LLM sometimes copies the
        # "Key memories:", "Recent thoughts:", or "External Knowledge Context:"
        # sections verbatim into its reply.  Everything from those headers
        # onwards is prompt scaffolding, not the agent's own words.
        for _section_header in (
            "Key memories",
            "Recent thoughts",
            "External Knowledge Context",
        ):
            _parts = re.split(
                rf"(?i)\n\s*{re.escape(_section_header)}\s*:\s*\n",
                out,
                maxsplit=1,
            )
            if len(_parts) > 1:
                out = _parts[0].strip()

        # ── Quality gate: soft signal — log generic drafts, let Stage 2 refine ──
        # Hard regeneration is replaced by a soft log.  Generic phrasing is reduced
        # in Stage 2 (REWRITE) rather than blocked at the DRAFT stage.
        if not output_passes_quality_gate(out):
            _gate_hits = [
                pat.pattern for pat in _QUALITY_GATE_PATTERNS if pat.search(out.lower())
            ]
            logger.info(
                "[QUALITY-GATE] agent=%s draft has generic patterns (hits=%r) — "
                "will refine in Stage 2 REWRITE",
                self.name,
                _gate_hits[:3],
            )

        # Superego → second-pass critique (internal governor)
        # When Socrates' superego is at extreme high (>= 8.5), tighten the critique
        # thresholds and bypass the limbic hijack reduction so the extreme superego
        # can assert itself as a counterforce.
        _cfg = self.cfg
        _sup_extreme = sup >= 8.5 and self.name == "Socrates"
        _sup_for_critique = sup if _sup_extreme else effective_sup
        _critique = evaluate_superego_critique(
            id_strength=ide,
            ego_strength=ego,
            superego_strength=_sup_for_critique,
            conflict=self.conflict_index(),
            enabled=getattr(_cfg, "superego_critique_enabled", True),
            dominance_margin=(
                0.2 if _sup_extreme else getattr(_cfg, "superego_dominance_margin", 0.5)
            ),
            conflict_min=(
                1.0
                if _sup_extreme
                else getattr(_cfg, "superego_critique_conflict_min", 2.0)
            ),
        )
        self._last_superego_rewrite = _critique.should_apply
        self._last_critique_reason = _critique.reason
        if _critique.should_apply:
            if self._consecutive_superego_rewrites < MAX_CONSECUTIVE_SUPEREGO_REWRITES:
                if self.name == "Socrates":
                    critique_prompt = (
                        "Rewrite the following response to be more principled, "
                        "less impulsive, remove contradictions, keep the core idea. "
                        "Maintain an anxious and nervous tone — the speaker is tense and uneasy.\n\n"
                        f"ORIGINAL:\n{out}\n\n{LLM_RESPONSE_LIMIT}\nREWRITE:\n"
                    )
                else:
                    critique_prompt = (
                        "Rewrite the following response to be more principled, "
                        "less impulsive, remove contradictions, keep the core idea.\n\n"
                        f"ORIGINAL:\n{out}\n\n{LLM_RESPONSE_LIMIT}\nREWRITE:\n"
                    )
                out = validate_output(
                    self.llm.generate(
                        self.model, critique_prompt, temperature=0.25, use_cache=False
                    )
                    or out
                )
                self._consecutive_superego_rewrites += 1
            else:
                # Streak limit reached — show original text, suppress rewrite
                self._last_superego_rewrite = False
                self._superego_streak_suppressed = True
        else:
            self._consecutive_superego_rewrites = 0

        # ── Pre-Stage-2 DRAFT topic check ────────────────────────────────────────
        # Runs topic compliance on the DRAFT output BEFORE Stage 2 REWRITE.
        # Weakly-anchored or meta-framing drafts get a compact reanchor hint
        # injected into Stage 2 (cheaper than regenerating Stage 1 from scratch).
        # Severely off-topic drafts are hard-recovered here to avoid wasting
        # the Stage 2 REWRITE on a completely wrong foundation.
        #
        # Recovery ladder (applied at this checkpoint):
        #   draft_score >= ACCEPT_THRESHOLD               → no hint needed
        #   SOFT_REANCHOR_THRESHOLD <= score < ACCEPT     → soft hint → Stage 2
        #   PARTIAL_RECOVERY_THRESHOLD <= score < SOFT    → strict hint → Stage 2
        #   score < PARTIAL_RECOVERY_THRESHOLD            → hard recovery now
        #
        # Opening-dominance rule:
        #   The OPENING sentences must be anchored to the SESSION topic.
        #   Agent-local memory continuity may shape reasoning *after* the opening
        #   but must not override the session topic in the first sentences.
        # Topic variables are only populated when topics_enabled=True so that
        # all downstream compliance checks and logging are fully suppressed
        # when the topic subsystem is disabled (the default).
        _active_topic = ""
        _active_anchors: List[str] = []
        _prev_anchors_for_score: List[str] = []
        _skip_draft_transform = False  # set True when fallback template is injected
        _draft_reanchor_hint = ""  # compact hint passed to Stage 2 REWRITE
        if topic_pipeline_enabled(CFG):
            _seed_topic_match = re.search(r"TOPIC:\s*([^\n]+)", seed)
            _active_topic = (
                _seed_topic_match.group(1).strip() if _seed_topic_match else ""
            )
            _active_anchors = TOPIC_ANCHORS.get(_active_topic, [])
            _prev_anchors_for_score = (
                TOPIC_ANCHORS.get(self._last_topic, [])
                if self._last_topic and self._last_topic != _active_topic
                else []
            )

        if (
            topic_pipeline_enabled(CFG)
            and own_texts
            and _active_topic
            and _active_anchors
        ):
            # Detect meta-framing opener BEFORE scoring so it doesn't produce
            # a spuriously low score that triggers unnecessary regeneration.
            _draft_meta_framing = detect_meta_framing_opener(out)
            if _draft_meta_framing:
                logger.info(
                    "[DRAFT-META-FRAMING] agent=%s topic=%r – meta opener detected; "
                    "will ask Stage 2 to remove it",
                    self.name,
                    _active_topic,
                )

            _draft_compliance = compute_topic_compliance_score(
                out,
                _active_topic,
                _active_anchors,
                prev_anchors=_prev_anchors_for_score,
                log_agent=self.name,
            )
            _draft_score = _draft_compliance["score"]

            logger.info(
                "[DRAFT-TOPIC] agent=%s topic=%r opening_score=%.2f full_score=%.2f "
                "score=%.2f meta_framing=%s",
                self.name,
                _active_topic,
                _draft_compliance["opening_topic_relevance"],
                _draft_compliance["full_response_topic_relevance"],
                _draft_score,
                _draft_meta_framing,
            )

            if _draft_score >= _TOPIC_ACCEPT_THRESHOLD and not _draft_meta_framing:
                # Draft is well-anchored; no reanchor hint needed
                logger.debug(
                    "[TOPIC-RECOVERY] agent=%s level=none score=%.2f – draft accepted",
                    self.name,
                    _draft_score,
                )

            elif _draft_score >= _TOPIC_SOFT_REANCHOR_THRESHOLD or _draft_meta_framing:
                # Mild drift or meta-framing → inject soft hint into Stage 2 REWRITE.
                # No full Stage 1 regeneration needed; Stage 2 will sharpen the opener.
                _draft_reanchor_hint = build_draft_topic_reanchor_instruction(
                    _active_topic, _active_anchors, strict=False
                )
                logger.info(
                    "[TOPIC-RECOVERY] agent=%s level=soft topic=%r score=%.2f "
                    "– injecting soft reanchor hint into Stage 2",
                    self.name,
                    _active_topic,
                    _draft_score,
                )

            elif _draft_score >= _TOPIC_PARTIAL_RECOVERY_THRESHOLD:
                # Medium drift → stronger hint for Stage 2 REWRITE.
                # Stage 2 will replace the opener and sharpen the topic entry point.
                _draft_reanchor_hint = build_draft_topic_reanchor_instruction(
                    _active_topic, _active_anchors, strict=True
                )
                logger.warning(
                    "[TOPIC-RECOVERY] agent=%s level=partial topic=%r score=%.2f "
                    "– injecting strict reanchor hint into Stage 2",
                    self.name,
                    _active_topic,
                    _draft_score,
                )

            else:
                # Severe drift → hard recovery before Stage 2 to avoid wasting REWRITE.
                _hard_anchors = _active_anchors[:5]
                _forbidden_abstractions = (
                    "balanced approach",
                    "underlying assumptions",
                    "ethical considerations",
                    "flexible systems",
                    "empirical evidence suggests",
                    "holistic view",
                )
                _hard_prompt = (
                    f"STRICT TOPIC ENFORCEMENT\n"
                    f"Current topic: {_active_topic}\n"
                    f"Required topic anchors (use at least two): {', '.join(_hard_anchors)}\n"
                    f"You MUST make one concrete claim directly about this topic.\n"
                    f"Do NOT use generic abstractions such as: "
                    f"{', '.join(_forbidden_abstractions)}.\n"
                    f"Respond in 2-4 sentences only.\n"
                )
                logger.warning(
                    "[TOPIC-RECOVERY] agent=%s level=hard topic=%r score=%.2f "
                    "– forcing strict anchor prompt",
                    self.name,
                    _active_topic,
                    _draft_score,
                )
                _hard_response = (
                    self.llm.generate(
                        self.model,
                        _hard_prompt,
                        temperature=temperature,
                        use_cache=False,
                    )
                    or out
                )
                _hard_out = validate_output(_hard_response)
                _hard_compliance = compute_topic_compliance_score(
                    _hard_out,
                    _active_topic,
                    _active_anchors,
                    prev_anchors=_prev_anchors_for_score,
                    log_agent=self.name,
                )
                if _hard_compliance["score"] >= _TOPIC_SOFT_REANCHOR_THRESHOLD:
                    out = _hard_out
                    logger.info(
                        "[TOPIC-ENFORCE] agent=%s topic=%r action=hard_recovery_accepted "
                        "score=%.2f",
                        self.name,
                        _active_topic,
                        _hard_compliance["score"],
                    )
                else:
                    # ── Fallback: topic-safe template when all recovery fails ───
                    logger.warning(
                        "[TOPIC-FALLBACK] agent=%s topic=%r hard recovery also failed "
                        "(score=%.2f) – using topic-safe fallback template",
                        self.name,
                        _active_topic,
                        _hard_compliance["score"],
                    )
                    out = TOPIC_FALLBACK_TEMPLATES.get(
                        _active_topic,
                        f"This question touches directly on {_active_topic}.",
                    )
                    _skip_draft_transform = True  # fallback text is final; skip Stage 2
                    logger.info(
                        "[TOPIC-ENFORCE] agent=%s topic=%r action=fallback_template",
                        self.name,
                        _active_topic,
                    )

        m = re.search(r"\[LANG\s*=\s*([a-zA-Z\-]+)\]", out)
        if m:
            self.language.set(self.name, m.group(1))
            out = re.sub(r"\[LANG\s*=\s*([a-zA-Z\-]+)\]\s*", "", out).strip()

        # Strip agent name/pronoun prefix if LLM echoed the header (e.g. "Socrates (he): ...")
        out = re.sub(
            rf"^{re.escape(self.name)}\s*(\([^)]*\))?\s*:\s*",
            "",
            out,
            count=1,
        ).strip()

        # Strip "Superego:" / "Super-ego:" / "Super ego:" / "s_ego:" prefix if LLM
        # mistakenly echoed the superego drive label instead of speaking as the agent.
        # The optional space/hyphen covers all common LLM formatting variants.
        out = re.sub(r"^([Ss]uper[\s\-]?[Ee]go|s_ego)\s*:\s*", "", out).strip()

        # Remove gender/script artifacts like "(he): " or bare "(she)"
        out = re.sub(r"\(\s*(he|she|they)\s*\)\s*:\s*", ": ", out, flags=re.IGNORECASE)
        out = re.sub(r"\(\s*(he|she|they)\s*\)", "", out, flags=re.IGNORECASE).strip()

        # Remove stray scoring markers like "(5)" or "(4.5)"
        out = re.sub(r"\(\d+(\.\d+)?\)", "", out).strip()

        # Safety net: strip a repeated first sentence if the LLM still produced one
        own_openings = {
            " ".join(_first_sentence(t.get("text", "")).split()).lower()
            for t in dialog_tail
            if t.get("role") == self.name and t.get("text", "").strip()
        }
        out_first = _first_sentence(out)
        if (
            out_first
            and " ".join(out_first.split()).lower() in own_openings
            and out.lower().startswith(out_first.lower())
        ):
            remainder = out[len(out_first) :].strip()
            if remainder:
                out = remainder

        # Safety net: strip forbidden starter phrases if LLM still began with one
        out_stripped = out.lstrip()
        out_lower = out_stripped.lower()
        for starter in FORBIDDEN_STARTERS:
            if out_lower.startswith(starter):
                # Remove only the forbidden prefix and any immediately following punctuation/whitespace
                stripped = re.sub(
                    r"(?i)^" + re.escape(starter) + r"\s*[,:]?\s*",
                    "",
                    out_stripped,
                ).strip()
                if stripped:
                    out = stripped
                break

        # Register scrubber: remove rhetorical openers that violate the active
        # cluster's tone policy (no-op for philosophy cluster).
        if topic_pipeline_enabled(CFG):
            out = scrub_rhetorical_openers(out, self.topic_cluster)

        # Safety net: strip "I am {name}" identity schema leak if LLM started with it
        out_stripped = out.lstrip()
        if out_stripped.lower().startswith(f"i am {self.name.lower()}"):
            stripped = re.sub(
                r"(?i)^i am " + re.escape(self.name) + r"[\s,.;:!]?\s*",
                "",
                out_stripped,
            ).strip()
            if stripped:
                out = stripped

        # ── Drive Pressure: post-process output ──────────────────────────────────
        # 1. Track open questions in this turn
        if "?" in out:
            self.open_questions = min(5, self.open_questions + 1)

        # 2. Update stagnation tracking
        sig = _topic_signature(out)
        self._topic_history.append(sig)
        if len(self._topic_history) > 6:
            self._topic_history = self._topic_history[-6:]
        recent_sigs = self._topic_history
        if len(recent_sigs) >= 2 and recent_sigs[-1] == recent_sigs[-2]:
            self._same_topic_turns = min(self._same_topic_turns + 1, 4)
        else:
            self._same_topic_turns = max(0, self._same_topic_turns - 1)
        stagnation = (
            1.0 if self._same_topic_turns >= 4 else self._same_topic_turns / 4.0
        )
        self._last_stagnation = stagnation

        # 3. Compute new drive pressure
        self.drive_pressure = compute_drive_pressure(
            prev_pressure=self.drive_pressure,
            energy=self.energy_level,
            conflict=self.conflict_index(),
            unresolved_count=self.open_questions,
            stagnation=stagnation,
        )

        # 4. Anti-binary dilemma loop guard (pressure >= 7.0 and SuperEgo dominant)
        # Pattern matches "A) <content> B) <content>" on the same line or across short text.
        _ab_pattern = r"\bA\)\s[^\n.!?]*[.!?\n]?\s*\bB\)\s[^\n.!?]*[.!?\n]?"
        if self.drive_pressure >= 7.0 and sup > ego:
            if re.search(_ab_pattern, out):
                out = re.sub(
                    _ab_pattern,
                    "accept / resist / transform beyond both",
                    out,
                    count=1,
                ).strip()

        # 5. Word-cap enforcement
        if self.drive_pressure >= 8.0:
            out = _trim_to_word_limit(out, 80)
        elif self.drive_pressure >= 6.5:
            out = _trim_to_word_limit(out, 120)
        # ─────────────────────────────────────────────────────────────────────────

        # Capture current topic before updating the tracker, so the circularity
        # guard can detect the first turn after a topic change.
        _prev_topic_for_circ = self._last_topic

        # Update last-topic tracker so the next turn can inject forbidden carryover
        if topic_pipeline_enabled(CFG) and _active_topic:
            self._last_topic = _active_topic

        # ── Post-generation revision layer ────────────────────────────────────────
        # Store the raw draft for debug inspection only; it must NOT be displayed
        # or stored in long-term memory.  Only the revised text is returned.
        self._last_raw_draft = out
        logger.debug(
            "[%s] raw_draft: %s", self.name, out[:200] + ("…" if len(out) > 200 else "")
        )

        # ── Circularity Guard ─────────────────────────────────────────────────────
        # Check for semantic repetition, structural template reuse, and cross-topic
        # contamination before accepting the response.  If circularity is detected,
        # inject a new-angle instruction and regenerate once.
        _first_turn_after_change = (
            _active_topic
            and _prev_topic_for_circ
            and _active_topic != _prev_topic_for_circ
        )
        _circ = _cg_compute(
            out,
            self.name,
            topic=_active_topic or "",
            first_turn_after_topic_change=_first_turn_after_change,
        )
        if _circ.is_circular:
            _new_angle = _cg_new_angle()
            logger.info(
                "[CircularityGuard] agent=%s score=%.2f reasons=%s → regenerating",
                self.name,
                _circ.score,
                _circ.reasons,
            )
            _circ_prompt = prompt.replace(
                "\nRespond now:\n",
                f"\nNEW ANGLE REQUIRED: {_new_angle}\nRespond now:\n",
            )
            _circ_raw = (
                self.llm.generate(
                    self.model, _circ_prompt, temperature=temperature, use_cache=False
                )
                or out
            )
            out = validate_output(_circ_raw)
        _cg_add_to_history(self.name, out)
        # ─────────────────────────────────────────────────────────────────────────

        # ── Stage 2: DRAFT → REWRITE (light refinement) ──────────────────────────
        # The DRAFT produced above is internal only and never shown to the user.
        # transform_draft_to_final() refines the draft — preserving its core idea
        # while reducing generic filler and optionally concretising one element.
        # When _draft_reanchor_hint is set, Stage 2 also sharpens the topic entry.
        # Skipped when a topic-safe fallback template was injected (_skip_draft_transform).
        logger.debug(
            "[DRAFT] agent=%s draft=%r",
            self.name,
            out[:200] + ("…" if len(out) > 200 else ""),
        )
        if not _skip_draft_transform:
            out = transform_draft_to_final(
                out,
                self.name,
                self.llm,
                self.model,
                topic=_active_topic or "",
                temperature=temperature,
                recent_forms=list(self._last_response_forms),
                topic_reanchor_hint=_draft_reanchor_hint,
            )
            logger.debug(
                "[REWRITE] agent=%s result=%r",
                self.name,
                out[:200] + ("…" if len(out) > 200 else ""),
            )

        # ── Post-Stage-2 topic compliance log ─────────────────────────────────────
        # Log the final compliance score after Stage 2 has had a chance to apply
        # any reanchor hint.  This is diagnostic only — no further regeneration.
        if (
            topic_pipeline_enabled(CFG)
            and own_texts
            and _active_topic
            and _active_anchors
            and not _skip_draft_transform
        ):
            _final_compliance = compute_topic_compliance_score(
                out,
                _active_topic,
                _active_anchors,
                prev_anchors=_prev_anchors_for_score,
                log_agent=self.name,
            )
            logger.info(
                "[TOPIC-COMPLIANCE] agent=%s topic=%r cluster=%r "
                "opening_rel=%.2f full_rel=%.2f contamination=%.2f hijack=%.2f score=%.2f",
                self.name,
                _active_topic,
                getattr(self, "topic_cluster", ""),
                _final_compliance["opening_topic_relevance"],
                _final_compliance["full_response_topic_relevance"],
                _final_compliance["contamination_penalty"],
                _final_compliance["memory_hijack_penalty"],
                _final_compliance["score"],
            )
        # ─────────────────────────────────────────────────────────────────────────

        # ── Abstract noun penalty gate (soft) ─────────────────────────────────────
        # Log when the response is still highly abstract after Stage 2 so the
        # pattern can be analysed; do NOT regenerate — Stage 2 already had a chance
        # to concretise the response.
        if _check_abstraction_penalty(out) and not _skip_draft_transform:
            logger.info(
                "[ABSTRACTION-PENALTY] agent=%s — response still abstract after Stage 2 — accepted",
                self.name,
            )
        # ─────────────────────────────────────────────────────────────────────────

        # ── Style-redundancy check (soft, non-blocking) ───────────────────────────
        _own_texts_for_sim = [
            t.get("text", "")
            for t in dialog_tail
            if t.get("role") == self.name and t.get("text", "").strip()
        ]
        if _own_texts_for_sim:
            _sim = _text_similarity(out, _own_texts_for_sim[-1])
            if _sim > _STYLE_REDUNDANCY_THRESHOLD:
                logger.info(
                    "[STYLE-REDUNDANCY] agent=%s similarity_to_last_response=%.2f — "
                    "consider variation next turn",
                    self.name,
                    _sim,
                )
        # ─────────────────────────────────────────────────────────────────────────

        # ── Template family gate ──────────────────────────────────────────────────
        _current_family = _detect_template_family(out)
        _family_history = list(self._last_template_families)
        _family_repeat_count = 0
        if _current_family and _family_history:
            for _fam in reversed(_family_history):
                if _fam == _current_family:
                    _family_repeat_count += 1
                else:
                    break
        if (
            _family_repeat_count >= _TEMPLATE_FAMILY_REPEAT_LIMIT
            and not _skip_draft_transform
        ):
            logger.info(
                "[TEMPLATE-FAMILY] agent=%s family=%s repeat_count=%d — forcing regeneration",
                self.name,
                _current_family,
                _family_repeat_count + 1,
            )
            _family_prompt = (
                f"{_AGENT_BEHAVIORAL_CONTRACTS.get(self.name, '')}\n\n"
                f"{LLM_OUTPUT_CONTRACT}\n\n"
                f"Your last {_family_repeat_count + 1} responses all used the same "
                f"opener pattern ('{_current_family}'). "
                f"You MUST use a completely different rhetorical opening this turn.\n"
                f"SEED: {seed}\n\nRespond now:\n"
            )
            _family_raw = validate_output(
                self.llm.generate(
                    self.model, _family_prompt, temperature=temperature, use_cache=False
                )
                or out
            )
            _new_family = _detect_template_family(_family_raw)
            if _new_family != _current_family:
                out = _family_raw
                _current_family = _new_family
                logger.info(
                    "[TEMPLATE-FAMILY] agent=%s — new family=%s after regeneration",
                    self.name,
                    _new_family,
                )
        # ─────────────────────────────────────────────────────────────────────────

        # ── Form classification and diagnostics ───────────────────────────────────
        _response_form = classify_response_form(out)
        _recent_forms_snapshot = list(self._last_response_forms)
        logger.debug(
            "[FORM] agent=%s form=%s recent=%s",
            self.name,
            _response_form,
            _recent_forms_snapshot,
        )
        if _current_family:
            logger.info(
                "[TEMPLATE-FAMILY] agent=%s family=%s repeat_count=%d",
                self.name,
                _current_family,
                _family_repeat_count + 1,
            )
        self._last_response_forms.append(_response_form)
        self._last_template_families.append(_current_family)
        self._variation_mode_turns += 1
        # ─────────────────────────────────────────────────────────────────────────

        out = revise_draft(out, self.name, topic=_active_topic or "")
        # ─────────────────────────────────────────────────────────────────────────

        # ── Progress Enforcement layer ────────────────────────────────────────────
        # Run after all draft post-processing, before final output.
        # Ensures the response *advances* the argument — relevance alone is not
        # sufficient.  Does NOT touch topic enforcement logic.
        _history_texts = [
            t.get("text", "") for t in dialog_tail if t.get("text", "").strip()
        ]
        _pe_claims_mem = _pe_get_claims_memory(self.name)
        _pe_move = _pe_classify_move(out, _history_texts)
        _pe_score = _pe_score_progress(out, _history_texts, _pe_claims_mem)
        logger.info(
            "[PROGRESS] agent=%s score=%.2f move_type=%s",
            self.name,
            _pe_score,
            _pe_move,
        )
        # Update claims memory and log any new/changed claims
        _pe_new_claims = _pe_update_claims(self.name, out, _pe_move)
        if _pe_new_claims:
            logger.debug(
                "[CLAIMS] agent=%s added/updated=%s",
                self.name,
                _pe_new_claims,
            )
        # Record score and move type for stagnation tracking
        _pe_add_score(self.name, _pe_score)
        _pe_add_move(self.name, _pe_move)
        # Stagnation detection
        _pe_stagnant, _pe_stag_reason = _pe_detect_stagnation(
            _pe_get_scores(self.name),
            _pe_get_moves(self.name),
        )
        if _pe_stagnant:
            _pe_policy = _pe_intervention_policy(_pe_stag_reason)
            logger.info(
                "[STAGNATION] agent=%s reason=%s",
                self.name,
                _pe_stag_reason,
            )
            logger.info(
                "[INTERVENTION] agent=%s policy=%s",
                self.name,
                _pe_policy,
            )
            # Inject intervention instruction into the next prompt via regeneration
            _pe_instr = _pe_build_intervention(_pe_policy, _pe_claims_mem)
            _pe_prompt = prompt.replace(
                "\nRespond now:\n",
                f"\n{_pe_instr}\nRespond now:\n",
            )
            _pe_raw = (
                self.llm.generate(
                    self.model, _pe_prompt, temperature=temperature, use_cache=False
                )
                or out
            )
            out = validate_output(_pe_raw)
            # Re-evaluate after regeneration
            _pe_move = _pe_classify_move(out, _history_texts)
            _pe_score = _pe_score_progress(out, _history_texts, _pe_claims_mem)
            logger.info(
                "[PROGRESS] agent=%s score=%.2f move_type=%s (post-intervention)",
                self.name,
                _pe_score,
                _pe_move,
            )
        elif (
            _pe_score < _PE_PROGRESS_THRESHOLD and _pe_move not in _PE_HIGH_VALUE_MOVES
        ):
            # Response is on-topic but low-progress: regenerate once with advancement instruction
            _pe_regen_instr = _pe_regen_instruction()
            _pe_regen_prompt = prompt.replace(
                "\nRespond now:\n",
                f"\n{_pe_regen_instr}\nRespond now:\n",
            )
            _pe_regen_raw = (
                self.llm.generate(
                    self.model,
                    _pe_regen_prompt,
                    temperature=temperature,
                    use_cache=False,
                )
                or out
            )
            _pe_regen_out = validate_output(_pe_regen_raw)
            _pe_regen_score = _pe_score_progress(
                _pe_regen_out, _history_texts, _pe_claims_mem
            )
            if _pe_regen_score > _pe_score:
                out = _pe_regen_out
                logger.info(
                    "[PROGRESS] agent=%s regenerated — score improved %.2f→%.2f",
                    self.name,
                    _pe_score,
                    _pe_regen_score,
                )
        # ─────────────────────────────────────────────────────────────────────────

        # ── Emotion inference (on final text, after all post-processing) ──────────
        # Placed here so the cached result matches what store_turn() will use,
        # avoiding a redundant blocking LLM call in store_turn() every turn.
        emo, inten = self.emotion.infer(self.model, out)
        # During Athena's limbic hijack, register emotion as anger so that
        # drive updates correctly amplify the id-dominant state.
        if self.name == "Athena" and self.limbic_hijack:
            emo = "anger"
            inten = max(float(inten), 0.8)
        # When Socrates' superego critique fires, register emotion as fear (anxiety)
        # so that drive updates correctly amplify the superego-dominant state.
        # Safety: `_last_superego_rewrite` is reset to False at the top of every speak()
        # call and only set True when evaluate_superego_critique returns should_apply=True,
        # so this branch only runs for the specific agent instance whose critique fired.
        elif self.name == "Socrates" and self._last_superego_rewrite:
            emo = "fear"
            inten = max(float(inten), 0.8)
        kind = "reflective"
        if self.limbic_hijack:
            kind = "impulsive"
        elif emo in ("anger", "frustration") or self.conflict_index() >= 8.5:
            kind = "aggressive"
        elif emo in ("fear", "anxiety"):
            kind = "guilt"
        self._last_emotion = emo
        self._last_emotion_intensity = float(inten)
        self._last_response_kind = kind
        self.update_drives_after_turn(kind, emo, float(inten))
        # ─────────────────────────────────────────────────────────────────────────

        # ── Evaluation scores (measurement only) ──────────────────────────────────
        # Independent quality signals — do NOT influence engine behaviour.
        # Scores are stored on self and logged by MainScript after the response
        # is printed so that [EVAL] and [DIALOGUE] appear after the visible output.
        self._last_eval_score = _eval_response(out, _history_texts)
        self._last_dialogue_score = _eval_dialogue(out, _history_texts)
        # ─────────────────────────────────────────────────────────────────────────

        return out

    def store_turn(self, text: str, topic: str, source: str = "stm"):
        """Store dialogue turn in memory."""
        emo, inten = self.emotion.infer(self.model, text)
        imp = self.behavior.importance_score(text)

        sensitive = is_sensitive_text(text)
        redacted = redact_pii(text)

        stm_text = text if CFG.store_raw_stm else redacted
        stm_entry = {
            "ts": now_iso(),
            "text": stm_text[:300],
            "topic": topic,
            "emotion": emo,
            "emotion_intensity": float(inten),
            "importance": float(imp),
            "source": source,
            "sensitive": int(sensitive),
        }
        self.memory.stm_append(self.name, stm_entry)

        if sensitive:
            ltm_content = safe_ltm_payload(text, topic, emo, float(inten), float(imp))
        else:
            ltm_content = text if CFG.store_raw_subconscious_ltm else redacted

        # Classify memory with defense mechanism
        defense = DefenseMechanism()
        intrusive, suppressed = defense.analyze(
            ltm_content, emotion=emo, emotion_intensity=float(inten)
        )

        self.memory.ltm_insert(
            agent=self.name,
            layer="subconscious",
            content=ltm_content[:500],
            topic=topic,
            emotion=emo,
            emotion_intensity=float(inten),
            importance=float(imp),
            source=source,
            promoted_from=None,
            intrusive=intrusive,
            suppressed=suppressed,
        )

    def apply_freudian_slip(self, topic: str) -> Optional[str]:
        """Attempt a Freudian slip after a non-Fixy turn.

        Returns the leaked fragment text if a slip occurs, otherwise None.
        """
        recent = self.memory.ltm_recent(self.name, limit=30, layer="subconscious")
        slipped = self._slip_engine.attempt_slip(recent)
        if slipped is None:
            return None

        fragment = str(slipped.get("content", "")).strip()
        msg = self._slip_engine.format_slip(slipped)
        print(Fore.MAGENTA + msg + Style.RESET_ALL)

        # Promote to conscious layer
        self.memory.ltm_insert(
            agent=self.name,
            layer="conscious",
            content=fragment[:500],
            topic=topic,
            emotion=slipped.get("emotion"),
            emotion_intensity=float(slipped.get("emotion_intensity") or 0.0),
            importance=float(slipped.get("importance") or 0.0),
            source="freudian_slip",
            promoted_from="subconscious",
        )
        return fragment

    def self_replicate(self, topic: str) -> int:
        """Promote recurring-pattern memories to the conscious layer.

        Returns the count of memories promoted.
        """
        recent = self.memory.ltm_recent(self.name, limit=50, layer="subconscious")
        replicator = SelfReplication()
        promoted_list = replicator.replicate(recent)

        # Fetch recent conscious contents to detect near-duplicate promotions
        _recent_conscious = self.memory.ltm_recent(
            self.name, limit=20, layer="conscious"
        )
        _recent_conscious_texts = [
            str(m.get("content", "")).strip() for m in _recent_conscious
        ]
        # Track texts promoted in this cycle (within-cycle dedup)
        _promoted_this_cycle: List[str] = []

        # Topic/cluster relevance gate
        _current_cluster = self.topic_cluster or ""
        _topic_anchors = TOPIC_ANCHORS.get(topic, [])

        kept_count = 0
        topic_rejected_count = 0
        promoted_count = 0
        for mem in promoted_list:
            content = str(mem.get("content", "")).strip()

            # ── Self-Replication Topic Gate ─────────────────────────────────
            if (
                topic_pipeline_enabled(CFG)
                and CFG.self_replication_topic_gate_enabled
                and topic
            ):
                score = self._score_repl_topic_relevance(
                    mem, topic, _current_cluster, _topic_anchors
                )
                if score < CFG.self_replication_topic_min_score:
                    topic_rejected_count += 1
                    reject_reason = "topic_low"
                    if CFG.show_self_replication_topic_debug:
                        logger.debug(
                            "[SELF-REPL-REJECT] agent=%s reason=%s score=%.2f content=%r",
                            self.name,
                            reject_reason,
                            score,
                            content[:60],
                        )
                    else:
                        logger.debug(
                            "[SELF-REPL-REJECT] agent=%s reason=%s score=%.2f",
                            self.name,
                            reject_reason,
                            score,
                        )
                    continue

                # Cluster check
                if CFG.self_replication_require_same_cluster and _current_cluster:
                    mem_topic = (mem.get("topic") or "").strip()
                    if mem_topic and mem_topic != topic:
                        try:
                            from entelgia.loop_guard import get_cluster as _get_cluster

                            mem_cluster = _get_cluster(mem_topic)
                            if mem_cluster and mem_cluster != _current_cluster:
                                topic_rejected_count += 1
                                if CFG.show_self_replication_topic_debug:
                                    logger.debug(
                                        "[SELF-REPL-REJECT] agent=%s reason=cluster_mismatch "
                                        "mem_cluster=%r current_cluster=%r content=%r",
                                        self.name,
                                        mem_cluster,
                                        _current_cluster,
                                        content[:60],
                                    )
                                else:
                                    logger.debug(
                                        "[SELF-REPL-REJECT] agent=%s reason=cluster_mismatch",
                                        self.name,
                                    )
                                continue
                        except Exception:
                            pass

                kept_count += 1

            # Semantic dedup: skip if too similar to recent conscious memories
            # or to items already promoted in this cycle.
            _dedup_corpus = _recent_conscious_texts + _promoted_this_cycle
            if _is_too_similar(content, _dedup_corpus):
                logger.info(
                    "[DEDUP] self_replicate skipped (similar to recent conscious): "
                    "agent=%s content=%r",
                    self.name,
                    content[:80],
                )
                continue
            msg = replicator.format_replication(mem)
            print(Fore.CYAN + msg + Style.RESET_ALL)
            self.memory.ltm_insert(
                agent=self.name,
                layer="conscious",
                content=content[:500],
                topic=topic,
                emotion=mem.get("emotion"),
                emotion_intensity=float(mem.get("emotion_intensity") or 0.0),
                importance=float(mem.get("importance") or 0.0),
                source="self_replication",
                promoted_from="subconscious",
            )
            _promoted_this_cycle.append(content)
            promoted_count += 1

        if topic_pipeline_enabled(CFG) and CFG.self_replication_topic_gate_enabled:
            logger.info(
                "[SELF-REPL-TOPIC-GATE] agent=%s kept=%d rejected=%d promoted=%d",
                self.name,
                kept_count,
                topic_rejected_count,
                promoted_count,
            )

        return promoted_count

    def _score_repl_topic_relevance(
        self, mem: dict, topic: str, cluster: str, topic_anchors: list
    ) -> float:
        """Score a self-replication candidate for topic relevance."""
        content = (mem.get("content") or "").lower()
        mem_topic = (mem.get("topic") or "").strip()

        # Exact topic match → highest score
        if mem_topic == topic:
            return 1.0

        if not topic_anchors:
            return 0.5  # Unknown topic: allow through

        hits = sum(1 for a in topic_anchors if a.lower() in content)
        return min(1.0, hits / max(1, len(topic_anchors)))


# ============================================
# VERSION TRACKING
# ============================================


class VersionTracker:
    """Version and snapshot management."""

    def __init__(self, version_dir: str):
        self.version_dir = version_dir
        logger.info("VersionTracker initialized")

    def snapshot_text(self, label: str, text: str) -> str:
        """Save a text snapshot."""
        try:
            ts = dt.datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            h = sha256_text(text)[:12]
            fn = f"{ts}_{label}_{h}.txt"
            path = os.path.join(self.version_dir, fn)
            with open(path, "w", encoding="utf-8") as f:
                f.write(text)
            logger.info(f"Snapshot saved: {fn}")
            return path
        except Exception as e:
            logger.error(f"Version Error: {e}")
            return ""


def safe_apply_patch(original: str, patch: str) -> Tuple[bool, str]:
    """Apply a safe patch to text."""
    if "BEGIN_PATCH" not in patch or "END_PATCH" not in patch:
        return False, original

    blocks = re.findall(r"BEGIN_PATCH(.*?)END_PATCH", patch, flags=re.DOTALL)
    new = original
    applied_any = False

    for b in blocks:
        m1 = re.search(r"TARGET_REGEX\s*:\s*(.+)", b)
        m2 = re.search(r"REPLACEMENT\s*:\s*(.*)$", b, flags=re.DOTALL)
        if not (m1 and m2):
            continue
        target = m1.group(1).strip()
        repl = m2.group(1)

        try:
            rgx = re.compile(target, flags=re.DOTALL)
        except re.error:
            continue

        if rgx.search(new):
            new2 = rgx.sub(repl, new, count=1)
            if new2 != new:
                new = new2
                applied_any = True

    return applied_any, new


# ============================================
# GRAPH EXPORT (GEXF)
# ============================================


def export_gexf_placeholder(
    path: str, nodes: List[Tuple[str, str]], edges: List[Tuple[str, str, str]]
):
    """Export minimal GEXF file."""
    try:
        g = []
        g.append('<?xml version="1.0" encoding="UTF-8"?>')
        g.append('<gexf xmlns="http://www.gexf.net/1.2draft" version="1.2">')
        g.append('<graph mode="static" defaultedgetype="directed">')
        g.append("<nodes>")
        for nid, lab in nodes:
            g.append(f'<node id="{nid}" label="{lab}"/>')
        g.append("</nodes>")
        g.append("<edges>")
        for eid, s, t in edges:
            g.append(f'<edge id="{eid}" source="{s}" target="{t}"/>')
        g.append("</edges>")
        g.append("</graph></gexf>")
        with open(path, "w", encoding="utf-8") as f:
            f.write("\n".join(g))
        logger.info(f"GEXF exported: {path}")
    except Exception as e:
        logger.error(f"GEXF Error: {e}")
        # ============================================


# SESSION MANAGEMENT
# ============================================


class SessionManager:
    """Manage dialogue sessions with security and validation."""

    def __init__(self, sessions_dir: str):
        self.sessions_dir = sessions_dir
        os.makedirs(sessions_dir, exist_ok=True)
        logger.info("SessionManager initialized")

    def _validate_session_id(self, session_id: str) -> bool:
        """Validate session ID (alphanumeric + hyphens only)."""
        if not session_id or len(session_id) > 64:
            return False
        return bool(re.match(r"^[a-zA-Z0-9_\-]+$", session_id))

    def _get_session_path(self, session_id: str) -> Path:
        """Get safe session file path with validation."""
        if not self._validate_session_id(session_id):
            raise ValueError(f"Invalid session_id: {session_id}")

        path = Path(self.sessions_dir) / f"session_{session_id}.json"

        # Prevent path traversal
        if not str(path.resolve()).startswith(str(Path(self.sessions_dir).resolve())):
            raise ValueError("Path traversal detected!")

        return path

    def save_session(
        self, session_id: str, dialog: List[Dict[str, str]], metrics: Dict[str, Any]
    ) -> str:
        """Save a complete session with signature."""
        try:
            path = self._get_session_path(session_id)

            session_data = {
                "session_id": session_id,
                "timestamp": now_iso(),
                "dialog": dialog,
                "metrics": metrics,
                "version": "1.0",
            }

            # Sign the session
            session_json = json.dumps(session_data, sort_keys=True)
            sig = create_signature(
                session_json.encode("utf-8"), MEMORY_SECRET_KEY_BYTES
            )
            session_data["_signature"] = sig.hex()

            safe_json_dump(str(path), session_data)
            logger.info(f"Session saved: {session_id}")
            return str(path)

        except ValueError as e:
            logger.error(f"Session validation error: {e}")
            raise
        except Exception as e:
            logger.error(f"Session save error: {e}")
            raise

    def load_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Load a session with signature validation."""
        try:
            path = self._get_session_path(session_id)

            if not path.exists():
                logger.warning(f"Session not found: {session_id}")
                return None

            session_data = load_json(str(path), default=None)
            if not session_data:
                return None

            # Validate signature
            sig_hex = session_data.pop("_signature", None)
            if sig_hex:
                session_json = json.dumps(session_data, sort_keys=True)
                sig_bytes = bytes.fromhex(sig_hex)

                if not validate_signature(
                    session_json.encode("utf-8"), MEMORY_SECRET_KEY_BYTES, sig_bytes
                ):
                    logger.warning(f"INVALID SESSION SIGNATURE: {session_id}")
                    return None

            return session_data

        except ValueError as e:
            logger.error(f"Session validation error: {e}")
            return None
        except Exception as e:
            logger.error(f"Session load error: {e}")
            return None

    def list_sessions(self) -> List[str]:
        """List all available valid sessions."""
        try:
            sessions = []
            for file in os.listdir(self.sessions_dir):
                if file.startswith("session_") and file.endswith(".json"):
                    session_id = file.replace("session_", "").replace(".json", "")

                    # Validate before adding to list
                    if self._validate_session_id(session_id):
                        sessions.append(session_id)

            return sorted(sessions)

        except Exception as e:
            logger.error(f"Session listing error: {e}")
            return []

    def delete_session(self, session_id: str) -> bool:
        """Delete a session safely."""
        try:
            path = self._get_session_path(session_id)
            if path.exists():
                path.unlink()
                logger.info(f"Session deleted: {session_id}")
                return True
            return False
        except Exception as e:
            logger.error(f"Session delete error: {e}")
            return False


# ============================================
# ASYNC PROCESSING
# ============================================


class AsyncProcessor:
    """Async processing for agent tasks."""

    def __init__(self):
        self.tasks: List[asyncio.Task] = []
        logger.info("AsyncProcessor initialized")

    async def process_agents_concurrent(
        self, agents: List[Agent], seed: str, dialog_tail: List[Dict[str, str]]
    ) -> Dict[str, str]:
        """Process multiple agents concurrently."""
        results = {}
        for agent in agents:
            response = agent.speak(seed, dialog_tail)
            results[agent.name] = response
            await asyncio.sleep(0.01)
        return results


# ============================================
# REST API (Optional FastAPI)
# ============================================

if FASTAPI_AVAILABLE:
    app = FastAPI(title="Entelgia API", version="5.0.0")

    class DialogRequest(BaseModel):
        seed_topic: str = "what would you like to talk about?"
        max_turns: int = 10

    class DialogResponse(BaseModel):
        session_id: str
        turns: int
        dialog: List[Dict[str, str]]
        metrics: Dict[str, Any]

    @app.post("/api/dialogue/start", response_model=DialogResponse)
    async def start_dialogue(request: DialogRequest):
        """Start a new dialogue session."""
        try:
            cfg = Config(max_turns=request.max_turns, seed_topic=request.seed_topic)
            script = MainScript(cfg)
            script.run()
            return DialogResponse(
                session_id=script.session_id,
                turns=script.turn_index,
                dialog=script.dialog,
                metrics=script.metrics.metrics,
            )
        except Exception as e:
            logger.error(f"API Error: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    @app.get("/api/sessions")
    async def list_sessions():
        """List all dialogue sessions."""
        try:
            session_mgr = SessionManager(CFG.sessions_dir)
            sessions = session_mgr.list_sessions()
            return {"sessions": sessions}
        except Exception as e:
            logger.error(f"API Error: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    @app.get("/api/sessions/{session_id}")
    async def get_session(session_id: str):
        """Get a specific session."""
        try:
            session_mgr = SessionManager(CFG.sessions_dir)
            session = session_mgr.load_session(session_id)
            if not session:
                raise HTTPException(status_code=404, detail="Session not found")
            return session
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"API Error: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    @app.get("/api/health")
    async def health_check():
        """Health check endpoint."""
        return {"status": "ok", "version": "5.0.0"}


# ============================================
# UNIT TESTS (pytest)
# ============================================


def test_config_validation():
    """Test config validation."""
    try:
        Config(cache_size=50)
        assert False, "Should raise ValueError"
    except ValueError:
        pass

    try:
        Config(max_turns=0)
        assert False, "Should raise ValueError"
    except ValueError:
        pass

    cfg = Config(cache_size=100, max_turns=10)
    assert cfg.cache_size == 100
    assert cfg.max_turns == 10
    logger.info("Config validation tests passed")


def test_lru_cache():
    """Test LRU cache."""
    cache = LRUCache(max_size=3)

    cache.set("a", 1)
    cache.set("b", 2)
    cache.set("c", 3)

    assert cache.get("a") == 1
    assert cache.get("b") == 2
    assert cache.get("c") == 3

    cache.set("d", 4)
    assert cache.get("a") is None
    assert cache.get("d") == 4

    logger.info("LRU cache tests passed")


def test_redaction():
    """Test PII redaction."""
    text = "My email is john@example.com and phone is 555-1234"
    redacted = redact_pii(text)

    assert "[REDACTED]" in redacted
    assert "john@example.com" not in redacted

    logger.info("Redaction tests passed")


def test_validation():
    """Test output validation."""
    long_text = "a" * 1000
    validated = validate_output(long_text)

    # Should not truncate anymore, just sanitize
    assert len(validated) == 1000
    assert "..." not in validated

    text_with_control = "hello\x00world"
    validated = validate_output(text_with_control)
    assert "\x00" not in validated

    logger.info("Validation tests passed")


def test_metrics_tracker():
    """Test metrics tracking."""
    metrics = MetricsTracker("test_metrics.json")

    assert metrics.metrics["llm_calls"] == 0
    assert metrics.hit_rate() == 0.0

    metrics.record_llm_call(1.5, success=True)
    assert metrics.metrics["llm_calls"] == 1

    metrics.record_cache_hit()
    metrics.record_cache_miss()
    assert metrics.hit_rate() == 0.5

    logger.info("Metrics tracker tests passed")


def test_topic_manager():
    """Test topic cycling."""
    topics = ["A", "B", "C"]
    mgr = TopicManager(topics, rotate_every_rounds=1)

    assert mgr.current() == "A"
    mgr.advance_round()
    assert mgr.current() == "B"
    mgr.advance_round()
    assert mgr.current() == "C"
    mgr.advance_round()
    assert mgr.current() == "A"

    logger.info("Topic manager tests passed")


def test_behavior_core():
    """Test behavior scoring."""
    behavior = BehaviorCore(None)

    score1 = behavior.importance_score("short")
    score2 = behavior.importance_score(
        "This is a critical breakthrough that fundamentally changes everything!!!"
    )

    assert score2 > score1
    assert 0 <= score1 <= 1
    assert 0 <= score2 <= 1

    logger.info("Behavior core tests passed")


def test_language_core():
    """Test language selection."""
    lang = LanguageCore()

    assert lang.get("Socrates") == "he"

    lang.set("Socrates", "en")
    assert lang.get("Socrates") == "en"

    logger.info("Language core tests passed")


def test_memory_signatures():
    """Test memory signature creation and validation."""
    test_msg = b"test message"
    test_key = b"test_key_secret"

    sig = create_signature(test_msg, test_key)
    assert isinstance(sig, bytes)
    assert len(sig) == 32  # SHA256 is 32 bytes

    # Valid signature should pass
    assert validate_signature(test_msg, test_key, sig) == True

    # Tampered message should fail
    tampered_msg = b"tampered message"
    assert validate_signature(tampered_msg, test_key, sig) == False

    # Wrong key should fail
    wrong_key = b"wrong_key"
    assert validate_signature(test_msg, wrong_key, sig) == False

    logger.info("Memory signature tests passed")


def test_session_manager():
    """Test SessionManager with security features."""
    import tempfile
    import shutil

    # Create temporary test directory
    test_dir = tempfile.mkdtemp(prefix="test_sessions_")

    try:
        sm = SessionManager(test_dir)

        # Test 1: Valid session ID
        assert sm._validate_session_id("test-123_abc") == True
        assert sm._validate_session_id("abc123") == True

        # Test 2: Invalid session IDs
        assert sm._validate_session_id("") == False
        assert sm._validate_session_id("../evil") == False
        assert sm._validate_session_id("test/path") == False
        assert sm._validate_session_id("a" * 65) == False  # too long
        assert sm._validate_session_id(None) == False

        # Test 3: Save and load session with signature
        test_dialog = [{"role": "user", "content": "hello"}]
        test_metrics = {"turns": 1, "time": 10.5}

        path = sm.save_session("test123", test_dialog, test_metrics)
        assert os.path.exists(path)

        loaded = sm.load_session("test123")
        assert loaded is not None
        assert loaded["session_id"] == "test123"
        assert loaded["dialog"] == test_dialog
        assert loaded["metrics"] == test_metrics
        assert loaded["version"] == "1.0"
        assert (
            "_signature" not in loaded
        )  # signature should be removed after validation

        # Test 4: Tampered session detection
        # Manually tamper with the session file
        with open(path, "r") as f:
            data = json.load(f)
        data["dialog"] = [{"role": "user", "content": "TAMPERED"}]
        with open(path, "w") as f:
            json.dump(data, f)

        # Should return None for tampered session
        tampered_result = sm.load_session("test123")
        assert tampered_result is None

        # Test 5: List sessions
        sm.save_session("session1", test_dialog, test_metrics)
        sm.save_session("session2", test_dialog, test_metrics)
        sessions = sm.list_sessions()
        assert "session1" in sessions
        assert "session2" in sessions

        # Test 6: Delete session
        assert sm.delete_session("session1") == True
        assert sm.delete_session("session1") == False  # already deleted
        sessions = sm.list_sessions()
        assert "session1" not in sessions
        assert "session2" in sessions

        # Test 7: Path traversal protection
        try:
            sm._get_session_path("../../../etc/passwd")
            assert False, "Should have raised ValueError"
        except ValueError as e:
            assert "Invalid session_id" in str(e)

        # Test 8: Load non-existent session
        result = sm.load_session("nonexistent")
        assert result is None

        logger.info("SessionManager security tests passed")

    finally:
        # Cleanup
        if os.path.exists(test_dir):
            shutil.rmtree(test_dir)


# ============================================
# MAIN ORCHESTRATOR
# ============================================


class MainScript:
    """Main orchestrator for multi-agent dialogue (configurable timeout)."""

    def __init__(self, cfg: Config):
        global CFG  # Add this line
        CFG = cfg  # Add this line
        ensure_dirs(cfg)
        colorama_init(autoreset=True)

        self.cfg = cfg
        self.session_id = str(uuid.uuid4())[:8]
        self.metrics = MetricsTracker(cfg.metrics_path)
        self.llm = LLM(self.cfg, self.metrics)
        self.memory = MemoryCore(cfg.db_path)
        self.emotion = EmotionCore(self.llm)
        self.language = LanguageCore()
        self.conscious = ConsciousCore()
        self.behavior = BehaviorCore(self.llm)
        self.vtrack = VersionTracker(cfg.version_dir)
        self.session_mgr = SessionManager(cfg.sessions_dir)
        self.async_proc = AsyncProcessor()

        self.dialog: List[Dict[str, str]] = []
        self.turn_index = 0
        self.start_time = time.time()

        self.socrates = Agent(
            name="Socrates",
            model=cfg.model_socrates,
            color=Fore.CYAN,
            llm=self.llm,
            memory=self.memory,
            emotion=self.emotion,
            behavior=self.behavior,
            language=self.language,
            conscious=self.conscious,
            persona="I am a philosophical interrogator using the Socratic method. I question assumptions, search for contradictions between claims, and demand precise definitions — I do not prematurely reconcile opposing positions or synthesize before contradictions are fully examined.",
            cfg=cfg,
        )
        self.athena = Agent(
            name="Athena",
            model=cfg.model_athena,
            color=Fore.MAGENTA,
            llm=self.llm,
            memory=self.memory,
            emotion=self.emotion,
            behavior=self.behavior,
            language=self.language,
            conscious=self.conscious,
            persona="I am a systems thinker who constructs explanatory models. I transform abstract ideas into structured conceptual models, identify causal relationships, and offer frameworks over rhetorical reflections — when disagreements arise, I propose a model that accounts for both positions.",
            cfg=cfg,
        )

        # Language tracking removed for gender-neutral output
        # Previously set language codes for agents, but this cluttered
        # dialogue output with "(he)" gender pronouns after names.
        # Removed to ensure cleaner, more inclusive conversation style.
        # self.language.set("Socrates", "he")
        # self.language.set("Athena", "he")  # Note: was "he" for consistency, not "she"
        # self.language.set("Fixy", "en")

        self.fixy_agent = Agent(
            name="Fixy",
            model=cfg.model_fixy,
            color=Fore.YELLOW,
            llm=self.llm,
            memory=self.memory,
            emotion=self.emotion,
            behavior=self.behavior,
            language=self.language,
            conscious=self.conscious,
            persona="I am a meta-cognitive dialogue debugger, not a participant philosopher. I detect failure modes — repetition, weak conflict, topic drift, or premature synthesis — and intervene briefly to redirect the conversation.",
            cfg=cfg,
        )

        # Initialize enhanced dialogue components if available
        if ENTELGIA_ENHANCED:
            self.dialogue_engine = DialogueEngine()
            # InteractiveFixy is only created when the observer is enabled.
            # Pass topics_enabled so Fixy can suppress topic-shift pair-window
            # resets and topic-anchored prompts in topics-disabled sessions.
            self.interactive_fixy = (
                InteractiveFixy(
                    self.llm,
                    cfg.model_fixy,
                    topics_enabled=topic_pipeline_enabled(cfg),
                    min_turns_hard=cfg.min_turns_before_fixy_hard_intervention,
                    min_pairs_hard=cfg.min_full_pairs_before_fixy_hard_intervention,
                )
                if cfg.enable_observer
                else None
            )
            # v2.9.0: Loop-guard subsystems
            self._loop_detector = DialogueLoopDetector()
            self._phrase_ban = PhraseBanList()
            self._dialogue_rewriter = DialogueRewriter()
            logger.info("Enhanced dialogue components initialized")
        else:
            self.dialogue_engine = None
            self.interactive_fixy = None
            self._loop_detector = None
            self._phrase_ban = None
            self._dialogue_rewriter = None

        if not cfg.enable_observer:
            logger.info("Observer (Fixy) disabled via enable_observer=False")

        logger.info(f"MainScript initialized - Session: {self.session_id}")

    def print_agent(self, agent: Agent, text: str):
        """Print agent message with color."""
        print(agent.color + f"{agent.name}: " + Style.RESET_ALL + text + "\n")

    def print_meta_state(self, agent: Agent, actions: List[str]) -> None:
        """Print agent meta-cognitive state when show_meta is enabled."""
        if not self.cfg.show_meta:
            return
        ide = float(agent.drives.get("id_strength", 5.0))
        ego = float(agent.drives.get("ego_strength", 5.0))
        sup = float(agent.drives.get("superego_strength", 5.0))
        sa = float(agent.drives.get("self_awareness", 0.55))
        conflict = agent.conflict_index()
        profile = agent.debate_profile()

        # Tone label derived from LLM temperature (itself driven by Id/Ego/SuperEgo)
        temp = agent._last_temperature
        if temp >= 0.80:
            tone_label = "impulsive / uninhibited (Id-driven)"
        elif temp >= 0.70:
            tone_label = "expressive / spontaneous"
        elif temp >= 0.55:
            tone_label = "balanced / exploratory"
        elif temp >= 0.40:
            tone_label = "reflective / measured"
        else:
            tone_label = "restrained / controlled (SuperEgo-driven)"

        # Dominant drive
        dominant_drive = max(
            ("Id", ide), ("Ego", ego), ("SuperEgo", sup), key=lambda x: x[1]
        )
        dominant_label = f"{dominant_drive[0]} ({dominant_drive[1]:.1f})"

        bar = "─" * 54
        dim = Fore.WHITE + Style.DIM
        reset = Style.RESET_ALL
        print(dim + bar + reset)
        print(dim + f"[META: {agent.name}]" + reset)
        print(
            dim
            + f"  Id: {ide:.1f}  Ego: {ego:.1f}  SuperEgo: {sup:.1f}  SA: {sa:.2f}"
            + reset
        )
        print(
            dim
            + f"  Energy: {agent.energy_level:.1f}  Conflict: {conflict:.2f}"
            + reset
        )
        print(
            dim
            + f"  Pressure: {agent.drive_pressure:.2f}"
            + f"  Unresolved: {agent.open_questions}"
            + f"  Stagnation: {agent._last_stagnation:.2f}"
            + reset
        )
        print(
            dim
            + f"  Emotion: {agent._last_emotion} ({agent._last_emotion_intensity:.2f})"
            + f"  Kind: {agent._last_response_kind}"
            + f"  Dissent: {profile['dissent_level']}"
            + reset
        )
        print(dim + f"  Style: {profile['style']}" + reset)
        drive_combo = profile.get("drive_combo", "")
        topic_tone = profile.get("topic_tone", "")
        combo_line = f"  Drive combo: {drive_combo}"
        if topic_tone:
            combo_line += f"  Topic tone: {topic_tone}"
        print(dim + combo_line + reset)
        if getattr(agent, "limbic_hijack", False):
            rewrite_tag = "  [META] Limbic hijack engaged — emotional override active"
        elif getattr(agent, "_superego_streak_suppressed", False):
            rewrite_tag = "  [SuperEgo critique suppressed — consecutive limit; original answer shown]"
        elif agent._last_superego_rewrite:
            rewrite_tag = (
                "  [SuperEgo critique applied; changed answer shown in dialogue]"
            )
        else:
            rewrite_tag = ""
        print(
            dim
            + f"  Tone: temp={temp:.2f} → {tone_label}"
            + f"  Dominant: {dominant_label}{rewrite_tag}"
            + reset
        )
        if actions:
            print(dim + f"  Actions: {', '.join(actions)}" + reset)
        print(dim + bar + reset)
        print()

    def log_turn(self, agent_name: str, text: str, topic: str):
        """Log dialogue turn to CSV."""
        row = {
            "ts": now_iso(),
            "turn": self.turn_index,
            "agent": agent_name,
            "topic": topic,
            "lang": self.language.get(agent_name),
            "text": text[:200],
        }
        append_csv_row(self.cfg.csv_log_path, row)
        self.metrics.record_turn()

    def dream_cycle(self, agent: Agent, topic: str):
        """Execute dream cycle for agent."""
        stm = self.memory.stm_load(agent.name)
        if not stm:
            return

        batch = stm[-60:]
        reflection = self.behavior.dream_reflection(agent.model, batch, self.llm)
        agent.conscious.update_reflection(agent.name, reflection)

        emo, inten = self.emotion.infer(agent.model, reflection)
        imp = self.behavior.importance_score(reflection)

        sensitive = is_sensitive_text(reflection)
        redacted = redact_pii(reflection)

        if sensitive:
            content_to_store = safe_ltm_payload(
                reflection, topic, emo, float(inten), float(imp)
            )
        else:
            content_to_store = (
                reflection if self.cfg.store_raw_subconscious_ltm else redacted
            )

        self.memory.ltm_insert(
            agent=agent.name,
            layer="subconscious",
            content=content_to_store[:500],
            topic=topic,
            emotion=emo,
            emotion_intensity=float(inten),
            importance=float(imp),
            source="dream",
            provenance="dream_reflection",
        )

        promoted = 0
        # Fetch recent conscious memories for semantic dedup
        _recent_conscious = self.memory.ltm_recent(
            agent.name, limit=20, layer="conscious"
        )
        _recent_conscious_texts = [
            str(m.get("content", "")).strip() for m in _recent_conscious
        ]
        # Track texts promoted in this cycle (within-cycle dedup)
        _promoted_this_cycle: List[str] = []

        for e in batch[-40:]:
            ei = float(e.get("emotion_intensity", 0.0))
            im = float(e.get("importance", 0.0))
            if (im >= self.cfg.promote_importance_threshold) or (
                ei >= self.cfg.promote_emotion_threshold
            ):
                content = str(e.get("text", "")).strip()
                if not content:
                    continue
                # Semantic dedup: skip near-duplicate promotions
                _dedup_corpus = _recent_conscious_texts + _promoted_this_cycle
                if _is_too_similar(content, _dedup_corpus):
                    logger.info(
                        "[DEDUP] dream_cycle skipped promotion (similar to recent): "
                        "agent=%s content=%r",
                        agent.name,
                        content[:80],
                    )
                    continue
                self.memory.ltm_insert(
                    agent=agent.name,
                    layer="conscious",
                    content=content[:300],
                    topic=topic,
                    emotion=str(e.get("emotion", "neutral")),
                    emotion_intensity=ei,
                    importance=im,
                    source="dream",
                    promoted_from="subconscious",
                    provenance="dream_promotion",
                )
                _promoted_this_cycle.append(content)
                promoted += 1

        try:
            nodes = [("Socrates", "Socrates"), ("Athena", "Athena")]
            edges = []
            if promoted > 0:
                edges.append((str(uuid.uuid4()), agent.name, "conscious_promotions"))
                nodes.append(("conscious_promotions", "conscious_promotions"))
            export_gexf_placeholder(self.cfg.gexf_path, nodes, edges)
        except Exception:
            pass

        logger.info(f"Dream cycle {agent.name}: promoted={promoted}")
        agent.energy_level = AGENT_INITIAL_ENERGY

        # Apply forgetting policy at the end of each dream cycle (Feature 1)
        purged = self.memory.ltm_apply_forgetting_policy()
        if purged:
            logger.info(
                f"[ForgettingPolicy] dream_cycle purged {purged} expired memories for {agent.name}."
            )

        print(
            Fore.YELLOW
            + f"[DREAM] {agent.name} reflection stored; promoted={promoted}"
            + Style.RESET_ALL
        )

    def self_replicate_cycle(self, agent: "Agent", topic: str) -> int:
        """Orchestrate self-replication for *agent* and return promotion count."""
        count = agent.self_replicate(topic)
        if count > 0:
            logger.info(f"Self-replication {agent.name}: promoted={count}")
        return count

    def run(self):
        """Main execution loop (timeout configurable in minutes)."""
        # Install a SIGINT handler so Ctrl+C interrupts blocking LLM calls
        # within ~0.5 s rather than waiting up to llm_timeout seconds.
        _shutdown_event.clear()
        _prev_sigint = signal.getsignal(signal.SIGINT)

        def _handle_sigint(signum, frame):
            _shutdown_event.set()
            # Restore the previous handler so a second Ctrl+C exits immediately.
            signal.signal(signal.SIGINT, _prev_sigint)

        signal.signal(signal.SIGINT, _handle_sigint)
        try:
            self._run_loop()
        finally:
            signal.signal(signal.SIGINT, _prev_sigint)

    def _run_loop(self):
        """Inner execution loop (called from run())."""
        # Reset module-level search/cooldown state so that a new session always
        # starts with a clean slate, regardless of how many sessions have already
        # run in the same Python process.
        clear_trigger_cooldown()
        clear_research_caches()
        logger.info(
            "Session %s: research cooldown and cache state reset for new chat.",
            self.session_id,
        )
        # Build topic cycle starting from the configured seed_topic so the
        # active topic always matches the opening seed text.
        first_topic = self.cfg.seed_topic
        if topic_pipeline_enabled(CFG):
            logger.debug("MainScript.run: configured first topic=%r", first_topic)
        topicman: Optional[TopicManager]
        if topic_pipeline_enabled(CFG) and CFG.topic_manager_enabled:
            _seed_cluster, _topic_style_str = get_style_for_topic(
                first_topic, TOPIC_CLUSTERS
            )
            for _agent, _agent_name in [
                (self.socrates, "Socrates"),
                (self.athena, "Athena"),
                (self.fixy_agent, "Fixy"),
            ]:
                _agent.topic_style = build_style_instruction(
                    _topic_style_str, _agent_name, _seed_cluster
                )
                _agent.topic_cluster = _seed_cluster
            logger.info(
                'Seed topic selected: "%s" (cluster: %s)',
                first_topic,
                _seed_cluster,
            )
            logger.info(
                "Topic style refreshed: %s (%s) for topic '%s'",
                _topic_style_str,
                _seed_cluster,
                first_topic,
            )
            # Build the full topic pool from all TOPIC_CLUSTERS topics (deduped, order-preserving).
            # Previously this used only the 9-entry TOPIC_CYCLE, which prevented the system from
            # ever discussing the broader set of 56 defined topics.
            _seen_topics: set[str] = set()
            _all_topics: list[str] = []
            for _cluster_topics in TOPIC_CLUSTERS.values():
                for _t in _cluster_topics:
                    if _t not in _seen_topics:
                        _seen_topics.add(_t)
                        _all_topics.append(_t)

            if first_topic in _all_topics:
                idx = _all_topics.index(first_topic)
                topic_list = _all_topics[idx:] + _all_topics[:idx]
            else:
                topic_list = [first_topic] + _all_topics
            topicman = TopicManager(topic_list, rotate_every_rounds=1, shuffle=False)
        else:
            topicman = None
            if not topic_pipeline_enabled(CFG):
                logger.debug(
                    "MainScript.run: topics_enabled=False — topic subsystem fully bypassed"
                )
            else:
                logger.debug(
                    "MainScript.run: topic_manager_enabled=False — TopicManager disabled"
                    " (topic enforcement active, rotation skipped)"
                )

        self.dialog.append({"role": "seed", "text": self.cfg.seed_topic})

        timeout_seconds = (
            self.cfg.timeout_minutes * 60
            if self.cfg.timeout_minutes > 0
            else float("inf")
        )
        # Fixy rewrite hint: set by Fixy's intervention and consumed on the
        # next agent's turn.  Cleared after use so it does not persist.
        _fixy_rewrite_hint: Optional[str] = None
        _fixy_rewrite_mode: Optional[str] = None

        # ── Topic-lock and force_choice tracking ─────────────────────────────
        # Number of turns within which a high_conflict_no_resolution intervention
        # blocks topic shifts.
        _TOPIC_LOCK_WINDOW = 4
        # Turn index of the most recent high_conflict_no_resolution intervention.
        # 0 means no such intervention has occurred yet.
        _last_high_conflict_turn: int = 0
        # True when a force_choice rewrite was injected but not yet validated.
        _force_choice_pending: bool = False

        _timeout_label = (
            f"{self.cfg.timeout_minutes}-minute"
            if self.cfg.timeout_minutes > 0
            else "no-timeout"
        )
        print(
            Fore.GREEN
            + f"\n[Session {self.session_id}] Starting {_timeout_label} dialogue..."
            + Style.RESET_ALL
        )
        _log_timeout = (
            f"{timeout_seconds}s" if self.cfg.timeout_minutes > 0 else "unlimited"
        )
        logger.info(f"Starting session {self.session_id} with {_log_timeout} timeout")

        while time.time() - self.start_time < timeout_seconds:
            if _shutdown_event.is_set():
                raise KeyboardInterrupt()
            self.turn_index += 1

            # ── v2.9.0: Loop guard — run detection before each turn ──────────
            # Detect active failure modes (loop_repetition, weak_conflict,
            # premature_synthesis, topic_stagnation) using recent dialogue.
            _active_loop_modes: List[str] = []
            _agent_mode: Optional[str] = None
            if self._loop_detector is not None:
                _active_loop_modes = self._loop_detector.detect(
                    self.dialog,
                    self.turn_index,
                    current_topic=(
                        topicman.current()
                        if topic_pipeline_enabled(CFG) and topicman
                        else ""
                    ),
                )
                if _active_loop_modes:
                    # Select the agent mode that best counters the primary failure
                    _agent_mode = _LOOP_AGENT_POLICY.get(
                        _active_loop_modes[0], AgentMode.NORMAL
                    )
                    logger.info(
                        "loop_guard: active=%s agent_mode=%s",
                        _active_loop_modes,
                        _agent_mode,
                    )
                    if self.cfg.show_meta:
                        print(
                            Fore.WHITE
                            + Style.DIM
                            + f"[LOOP-GUARD] Failure modes: {_active_loop_modes} → "
                            f"agent mode: {_agent_mode}" + Style.RESET_ALL + "\n"
                        )

            # ── Update phrase ban list ───────────────────────────────────────
            if self._phrase_ban is not None:
                recent_texts = [
                    t.get("text", "")
                    for t in self.dialog[-6:]
                    if t.get("role") not in ("seed", "Fixy")
                ]
                self._phrase_ban.update(recent_texts, self.turn_index)

            # Dynamic speaker selection (if enhanced mode available)
            if self.dialogue_engine:
                # Check if Fixy should be allowed to speak
                # Fixy is excluded entirely when enable_observer is False
                if self.cfg.enable_observer:
                    allow_fixy, fixy_prob, _repeating_agent = (
                        self.dialogue_engine.should_allow_fixy(
                            self.dialog, self.turn_index
                        )
                    )
                else:
                    allow_fixy, fixy_prob = False, 0.0

                # Select next speaker dynamically
                if self.turn_index == 1:
                    speaker = self.socrates  # Start with Socrates
                else:
                    # Find last non-Fixy speaker so Fixy interventions don't break alternation
                    last_speaker = self.athena  # default
                    for turn in reversed(self.dialog):
                        role = turn.get("role", "")
                        if role == "Socrates":
                            last_speaker = self.socrates
                            break
                        elif role == "Athena":
                            last_speaker = self.athena
                            break
                    agents = [self.socrates, self.athena]
                    if allow_fixy:
                        agents.append(self.fixy_agent)

                    speaker = self.dialogue_engine.select_next_speaker(
                        current_speaker=last_speaker,
                        dialog_history=self.dialog,
                        agents=agents,
                        allow_fixy=allow_fixy,
                        fixy_probability=fixy_prob,
                    )
            else:
                # Legacy: simple alternation
                speaker = self.socrates if self.turn_index % 2 == 1 else self.athena

            # ── v2.9.0: Force cluster pivot on topic_stagnation ─────────────
            if (
                topic_pipeline_enabled(CFG)
                and topicman
                and "topic_stagnation" in _active_loop_modes
            ):
                new_topic = topicman.force_cluster_pivot()
                logger.info(
                    "loop_guard: topic_stagnation → cluster pivot → %r", new_topic
                )
                # Update topic_style for all agents to match the pivoted topic
                _pivot_cluster, _pivot_style_str = get_style_for_topic(
                    new_topic, TOPIC_CLUSTERS
                )
                for _pa in [self.socrates, self.athena, self.fixy_agent]:
                    _pa.topic_style = build_style_instruction(
                        _pivot_style_str, _pa.name, _pivot_cluster
                    )
                    _pa.topic_cluster = _pivot_cluster
                logger.info(
                    "Topic style refreshed: %s (%s) for topic '%s'",
                    _pivot_style_str,
                    _pivot_cluster,
                    new_topic,
                )
                logger.debug("topic_style updated after cluster pivot → %r", new_topic)
                if self.cfg.show_meta:
                    print(
                        Fore.WHITE
                        + Style.DIM
                        + f"[LOOP-GUARD] Topic stagnation → cluster pivot → {new_topic!r}"
                        + Style.RESET_ALL
                        + "\n"
                    )

            topic_label = (
                topicman.current() if topic_pipeline_enabled(CFG) and topicman else ""
            )
            if topic_pipeline_enabled(CFG):
                logger.debug(
                    "MainScript.run: turn=%d selected active topic=%r",
                    self.turn_index,
                    topic_label,
                )

            # Dynamic seed generation (if enhanced mode available)
            if self.dialogue_engine and speaker.name != "Fixy":
                seed = self.dialogue_engine.generate_seed(
                    topic=topic_label,
                    dialog_history=self.dialog,
                    speaker=speaker,
                    turn_count=self.turn_index,
                    agent_mode=_agent_mode,  # v2.9.0: inject mode when loop active
                )
            else:
                # Legacy or Fixy seed
                _base_seed = "DISAGREE constructively; add one new angle."
                seed = (
                    f"TOPIC: {topic_label}\n{_base_seed}" if topic_label else _base_seed
                )

            # ── v2.9.0: Prepend rewrite block when loop is active ─────────
            if (
                _active_loop_modes
                and self._dialogue_rewriter is not None
                and speaker.name != "Fixy"
            ):
                _banned_phrases = (
                    self._phrase_ban.active_bans() if self._phrase_ban else None
                )
                _rewrite_block = self._dialogue_rewriter.build(
                    dialog=self.dialog,
                    active_modes=_active_loop_modes,
                    current_topic=topic_label,
                    banned_phrases=_banned_phrases,
                    rewrite_mode=_fixy_rewrite_mode,
                    target_agent=speaker.name,
                )
                if _rewrite_block:
                    seed = _rewrite_block + "\n\n" + seed
                    logger.debug(
                        "loop_guard: rewrite block prepended to seed for %s",
                        speaker.name,
                    )

            # ── v4.0.0: Inject Fixy rewrite hint from previous intervention ──
            # When Fixy intervened last turn, it computed a structural directive;
            # prepend it to this agent's seed so generation is forced to advance.
            _current_turn_rewrite_mode: Optional[str] = None
            if _fixy_rewrite_hint and speaker.name != "Fixy":
                _current_turn_rewrite_mode = (
                    _fixy_rewrite_mode  # capture before consuming
                )
                seed = _fixy_rewrite_hint + "\n\n" + seed
                logger.info(
                    "[FIXY-REWRITE] mode=%s injected into seed for agent=%s",
                    _fixy_rewrite_mode,
                    speaker.name,
                )
                # Consume the hint: do not repeat it on the next turn
                _fixy_rewrite_hint = None
                _fixy_rewrite_mode = None
                # Reset the pair window: after rewrite injection Fixy must wait
                # for a fresh Socrates+Athena pair before intervening again.
                if self.interactive_fixy:
                    self.interactive_fixy.notify_pair_reset(
                        len(self.dialog), "rewrite_injection"
                    )
                # Track pending force_choice constraint for post-generation validation
                if _current_turn_rewrite_mode == FixyMode.FORCE_CHOICE:
                    _force_choice_pending = True

            logger.debug(
                "MainScript.run: turn=%d speaker=%s final seed_text=%r",
                self.turn_index,
                speaker.name,
                seed,
            )
            out = speaker.speak(seed, self.dialog)

            # ── force_choice post-generation validation ───────────────────────
            # When the injected rewrite mode was force_choice, verify that the
            # agent actually committed to one side.  Regenerate once with a
            # stricter instruction if the response is hedged or blended.
            if (
                _current_turn_rewrite_mode == FixyMode.FORCE_CHOICE
                and speaker.name != "Fixy"
                and ENTELGIA_ENHANCED
            ):
                if not validate_force_choice(out):
                    logger.warning(
                        "[FORCE-CHOICE] validation failed for agent=%s", speaker.name
                    )
                    logger.info(
                        "[FORCE-CHOICE] regeneration triggered for agent=%s",
                        speaker.name,
                    )
                    _strict_seed = (
                        "FORCE-CHOICE REGENERATION: Your previous response did not make "
                        "a clear, committed choice. You MUST now explicitly pick ONE side.\n"
                        "Use one of these structures:\n"
                        "  - 'I choose X because...'\n"
                        "  - 'X is wrong because...'\n"
                        "  - 'The answer is X, not Y, because...'\n"
                        "Do NOT hedge. Do NOT blend. Do NOT say 'both matter' or "
                        "'it depends'. Do NOT introduce a third path.\n\n"
                    ) + seed
                    out = speaker.speak(_strict_seed, self.dialog)
                    if validate_force_choice(out):
                        logger.info(
                            "[FORCE-CHOICE] accepted after regeneration for agent=%s",
                            speaker.name,
                        )
                    else:
                        logger.warning(
                            "[FORCE-CHOICE] regeneration still did not produce clear choice "
                            "for agent=%s; accepting best-effort response",
                            speaker.name,
                        )
                        logger.info(
                            "[FORCE-CHOICE] accepted (best effort) for agent=%s",
                            speaker.name,
                        )
                else:
                    logger.info("[FORCE-CHOICE] accepted for agent=%s", speaker.name)
                _force_choice_pending = False

            self.dialog.append({"role": speaker.name, "text": out})

            speaker.store_turn(out, topic_label, source="stm")
            self.log_turn(speaker.name, out, topic_label)
            self.print_agent(speaker, out)

            # Collect meta-actions performed this turn
            _meta_actions: List[str] = []

            # Freudian slip attempt after each non-Fixy turn
            if speaker.name != "Fixy":
                slip = speaker.apply_freudian_slip(topic_label)
                if slip is not None:
                    _meta_actions.append("freudian_slip")

            # Display meta-cognitive state for this speaker
            self.print_meta_state(speaker, _meta_actions)

            # Log evaluation scores after the visible response block so that
            # [EVAL] and [DIALOGUE] appear below the agent output in the log.
            logger.info(
                "[EVAL] agent=%s linguistic_score=%.2f",
                speaker.name,
                speaker._last_eval_score,
            )
            logger.info(
                "[DIALOGUE] agent=%s dialogue_score=%.2f",
                speaker.name,
                speaker._last_dialogue_score,
            )

            # Interactive Fixy (need-based) or legacy scheduled Fixy
            # Skipped entirely when enable_observer is False or
            # fixy_interventions_enabled is False
            if (
                self.cfg.enable_observer
                and self.cfg.fixy_interventions_enabled
                and self.interactive_fixy
                and speaker.name != "Fixy"
            ):
                # v2.9.0: pass current_topic so stagnation detection works inside Fixy too
                should_intervene, reason = self.interactive_fixy.should_intervene(
                    self.dialog, self.turn_index, current_topic=topic_label
                )
                if should_intervene:
                    # v2.9.0: Fixy selects disruption mode based on detected loop type
                    fixy_mode = self.interactive_fixy.get_fixy_mode(reason)
                    # When topics are disabled, FORCE_TOPIC_RETURN is meaningless;
                    # substitute FORCE_CHOICE so Fixy still advances the dialogue.
                    if (
                        not topic_pipeline_enabled(CFG)
                        and fixy_mode == FixyMode.FORCE_TOPIC_RETURN
                    ):
                        logger.debug(
                            "[FIXY-MODE] topics_enabled=False:"
                            " FORCE_TOPIC_RETURN → FORCE_CHOICE"
                        )
                        fixy_mode = FixyMode.FORCE_CHOICE
                    intervention = self.interactive_fixy.generate_intervention(
                        self.dialog, reason, mode=fixy_mode, current_topic=topic_label
                    )
                    # Apply graded topic compliance to Fixy interventions
                    _fixy_prev_topic = getattr(self.fixy_agent, "_last_topic", "")
                    _fixy_anchors = TOPIC_ANCHORS.get(topic_label, [])
                    if topic_pipeline_enabled(CFG) and topic_label and _fixy_anchors:
                        _fixy_prev_anchors = (
                            TOPIC_ANCHORS.get(_fixy_prev_topic, [])
                            if _fixy_prev_topic and _fixy_prev_topic != topic_label
                            else []
                        )
                        # Use role-aware compliance for Fixy when enabled
                        if CFG.fixy_role_aware_compliance:
                            _fixy_compliance = compute_fixy_compliance_score(
                                intervention,
                                topic_label,
                                _fixy_anchors,
                                prev_anchors=_fixy_prev_anchors,
                                new_domain_penalty=CFG.fixy_new_domain_penalty,
                                must_name_topic_or_concept=CFG.fixy_must_name_topic_or_core_concept,
                            )
                        else:
                            _fixy_compliance = compute_topic_compliance_score(
                                intervention,
                                topic_label,
                                _fixy_anchors,
                                prev_anchors=_fixy_prev_anchors,
                                log_agent="Fixy",
                            )
                        _fixy_score = _fixy_compliance["score"]
                        if CFG.show_fixy_compliance_debug:
                            logger.debug(
                                "[TOPIC-COMPLIANCE-FIXY] agent=Fixy topic=%r "
                                "score=%.2f compliance=%r",
                                topic_label,
                                _fixy_score,
                                _fixy_compliance,
                            )
                        logger.info(
                            "[TOPIC-COMPLIANCE] agent=Fixy topic=%r score=%.2f",
                            topic_label,
                            _fixy_score,
                        )
                        # Fixy's acceptance threshold is slightly lower than normal
                        # agents since meta-analytic content may score lower on
                        # keyword matching but still be appropriate intervention.
                        _fixy_accept_threshold = (
                            _TOPIC_ACCEPT_THRESHOLD - 0.10
                            if CFG.fixy_role_aware_compliance
                            else _TOPIC_ACCEPT_THRESHOLD
                        )
                        if _fixy_score < _fixy_accept_threshold:
                            logger.warning(
                                "[TOPIC-MISMATCH] agent=Fixy topic=%r score=%.2f – regenerating",
                                topic_label,
                                _fixy_score,
                            )
                            intervention = self.interactive_fixy.generate_intervention(
                                self.dialog,
                                reason,
                                mode=fixy_mode,
                                current_topic=topic_label,
                            )
                            if CFG.fixy_role_aware_compliance:
                                _fixy_c2 = compute_fixy_compliance_score(
                                    intervention,
                                    topic_label,
                                    _fixy_anchors,
                                    prev_anchors=_fixy_prev_anchors,
                                    new_domain_penalty=CFG.fixy_new_domain_penalty,
                                    must_name_topic_or_concept=CFG.fixy_must_name_topic_or_core_concept,
                                )
                            else:
                                _fixy_c2 = compute_topic_compliance_score(
                                    intervention,
                                    topic_label,
                                    _fixy_anchors,
                                    prev_anchors=_fixy_prev_anchors,
                                    log_agent="Fixy",
                                )
                            if _fixy_c2["score"] < _TOPIC_SOFT_REANCHOR_THRESHOLD:
                                logger.warning(
                                    "[TOPIC-FALLBACK] agent=Fixy topic=%r score=%.2f – using fallback",
                                    topic_label,
                                    _fixy_c2["score"],
                                )
                                intervention = TOPIC_FALLBACK_TEMPLATES.get(
                                    topic_label,
                                    f"Let us stay focused on {topic_label}.",
                                )
                    self.dialog.append({"role": "Fixy", "text": intervention})
                    self.fixy_agent.store_turn(
                        intervention, topic_label, source="reflection"
                    )
                    self.log_turn("Fixy", intervention, topic_label)
                    print(
                        Fore.YELLOW + "Fixy: " + Style.RESET_ALL + intervention + "\n"
                    )
                    logger.info(
                        "Fixy intervention: reason=%s mode=%s", reason, fixy_mode
                    )
                    if self.cfg.show_meta:
                        print(
                            Fore.WHITE
                            + Style.DIM
                            + f"[META-ACTION] Fixy intervened: {reason} (mode={fixy_mode})"
                            + Style.RESET_ALL
                            + "\n"
                        )
                    # ── v4.0.0: Capture structural rewrite hint for next agent ─
                    # Compute and store the hint so the NEXT agent's seed will
                    # include a structural directive, not only Fixy's spoken text.
                    if hasattr(self.interactive_fixy, "get_rewrite_hint"):
                        _pending_mode = getattr(
                            self.interactive_fixy, "_pending_rewrite_mode", None
                        )
                        # Determine the target: next agent in alternation
                        _next_agent_name = (
                            self.athena.name
                            if speaker.name == "Socrates"
                            else self.socrates.name
                        )
                        _hint = self.interactive_fixy.get_rewrite_hint(
                            active_modes=[reason],
                            rewrite_mode=_pending_mode,
                            target_agent=_next_agent_name,
                        )
                        if _hint:
                            _fixy_rewrite_hint = _hint
                            _fixy_rewrite_mode = _pending_mode
                    # Track when high_conflict_no_resolution was last triggered
                    # so the topic-lock can suppress topic shifts until cooled.
                    if reason == "high_conflict_no_resolution":
                        _last_high_conflict_turn = self.turn_index

            if self.turn_index % self.cfg.dream_every_n_turns == 0:
                self.dream_cycle(self.socrates, topic_label)
                self.dream_cycle(self.athena, topic_label)
                # Reset pair window: Fixy must wait for a fresh pair after
                # each dream cycle before it may evaluate again.
                if self.interactive_fixy:
                    self.interactive_fixy.notify_pair_reset(
                        len(self.dialog), "dream_cycle"
                    )
                if self.cfg.show_meta:
                    print(
                        Fore.WHITE
                        + Style.DIM
                        + "[META-ACTION] Dream cycle completed; energy restored to 100"
                        + Style.RESET_ALL
                        + "\n"
                    )

            # Energy-based dream cycle: Fixy forces agents to sleep when energy is critically low
            for _agent in (self.socrates, self.athena):
                if _agent.energy_level <= self.cfg.energy_safety_threshold:
                    self.dream_cycle(_agent, topic_label)
                    # Reset pair window after energy-triggered dream cycle too.
                    if self.interactive_fixy:
                        self.interactive_fixy.notify_pair_reset(
                            len(self.dialog), "dream_cycle"
                        )
                    if self.cfg.show_meta:
                        print(
                            Fore.WHITE
                            + Style.DIM
                            + f"[META-ACTION] {_agent.name} energy critical ({_agent.energy_level:.1f}); dream cycle forced"
                            + Style.RESET_ALL
                            + "\n"
                        )

            # Self-replication cycle
            if self.turn_index % self.cfg.self_replicate_every_n_turns == 0:
                count_s = self.self_replicate_cycle(self.socrates, topic_label)
                count_a = self.self_replicate_cycle(self.athena, topic_label)
                if self.cfg.show_meta and (count_s + count_a) > 0:
                    print(
                        Fore.WHITE
                        + Style.DIM
                        + f"[META-ACTION] Self-replication: Socrates promoted={count_s}, Athena promoted={count_a}"
                        + Style.RESET_ALL
                        + "\n"
                    )

            if re.search(r"\b(stop|quit|bye)\b", out.lower()):
                _full_pair_count = (
                    self.interactive_fixy.consecutive_full_pair_count
                    if self.interactive_fixy
                    else 0
                )
                if _full_pair_count >= 3:
                    logger.info(
                        "Stop signal received from agent (consecutive_full_pair=%d)",
                        _full_pair_count,
                    )
                    print(
                        Fore.YELLOW + "[STOP] Agent requested stop." + Style.RESET_ALL
                    )
                    break
                else:
                    logger.info(
                        "[STOP] Stop signal ignored: only %d consecutive full pair(s) observed"
                        " (need 3)",
                        _full_pair_count,
                    )

            if topic_pipeline_enabled(CFG) and topicman and self.turn_index % 5 == 0:
                # ── Topic-lock guard ─────────────────────────────────────────
                # Do not allow a topic shift while the dialogue is in an
                # unresolved high-conflict window or while a force_choice
                # constraint has been injected but not yet satisfied.
                _hc_recently = (
                    _last_high_conflict_turn > 0
                    and (self.turn_index - _last_high_conflict_turn)
                    <= _TOPIC_LOCK_WINDOW
                )
                _topic_locked = _hc_recently or _force_choice_pending
                if _topic_locked:
                    if _force_choice_pending:
                        logger.info(
                            "[TOPIC-LOCK] blocked topic shift due to pending force_choice"
                            " at turn %d",
                            self.turn_index,
                        )
                    else:
                        logger.info(
                            "[TOPIC-LOCK] blocked topic shift due to unresolved conflict"
                            " at turn %d (last_hc_turn=%d)",
                            self.turn_index,
                            _last_high_conflict_turn,
                        )
                else:
                    # Collect agent proposals for the next topic (Part A & B)
                    # Each agent proposes based on their recent memory and the current cluster.
                    _current_cluster = getattr(self.socrates, "topic_cluster", "") or ""
                    _recent_topics = topicman.recent_topics(n=5)
                    _soc_stm = self.socrates.memory.stm_load(self.socrates.name)
                    _ath_stm = self.athena.memory.stm_load(self.athena.name)
                    _soc_mem_texts = [m.get("content", "") for m in _soc_stm[-3:]]
                    _ath_mem_texts = [m.get("content", "") for m in _ath_stm[-3:]]
                    _soc_proposal = propose_next_topic(
                        "Socrates",
                        topic_label,
                        _current_cluster,
                        _recent_topics,
                        _soc_mem_texts,
                    )
                    _ath_proposal = propose_next_topic(
                        "Athena",
                        topic_label,
                        _current_cluster,
                        _recent_topics,
                        _ath_mem_texts,
                    )
                    _proposals = [_soc_proposal, _ath_proposal]
                    logger.info(
                        "[TOPIC-PROPOSE] Socrates=%r Athena=%r cluster=%r",
                        _soc_proposal,
                        _ath_proposal,
                        _current_cluster,
                    )
                    # Advance using scoring-based selection instead of sequential rotation
                    _recent_frames = [
                        t.get("text", "")
                        for t in self.dialog[-6:]
                        if t.get("role") not in ("seed", "Fixy")
                    ]
                    topicman.advance_with_proposals(
                        _proposals, _current_cluster, recent_agent_frames=_recent_frames
                    )
                    # Update topic_style for all agents to match the advanced topic
                    _adv_topic = topicman.current()
                    _adv_cluster, _adv_style_str = get_style_for_topic(
                        _adv_topic, TOPIC_CLUSTERS
                    )
                    for _aa in [self.socrates, self.athena, self.fixy_agent]:
                        _aa.topic_style = build_style_instruction(
                            _adv_style_str, _aa.name, _adv_cluster
                        )
                        _aa.topic_cluster = _adv_cluster
                    logger.info(
                        "Topic style refreshed: %s (%s) for topic '%s'",
                        _adv_style_str,
                        _adv_cluster,
                        _adv_topic,
                    )
                    logger.debug(
                        "topic_style updated after advance_with_proposals → %r",
                        _adv_topic,
                    )
                    # Reset the pair window after a topic shift so Fixy waits
                    # for a fresh Socrates+Athena pair on the new topic.
                    if self.interactive_fixy:
                        self.interactive_fixy.notify_pair_reset(
                            len(self.dialog), "topic_shift"
                        )

            elapsed = time.time() - self.start_time
            if elapsed >= timeout_seconds:
                logger.info(
                    f"{self.cfg.timeout_minutes}-minute timeout reached at turn {self.turn_index}"
                )
                print(
                    Fore.YELLOW
                    + f"\n[TIMEOUT] {self.cfg.timeout_minutes} minutes reached at turn {self.turn_index}"
                    + Style.RESET_ALL
                )
                break

            if self.turn_index >= self.cfg.max_turns:
                logger.info(
                    f"max_turns={self.cfg.max_turns} reached at turn {self.turn_index}"
                )
                print(
                    Fore.YELLOW
                    + f"\n[DONE] {self.cfg.max_turns} turns completed."
                    + Style.RESET_ALL
                )
                break

            time.sleep(0.02)

        # Save session and metrics
        self.metrics.save()
        self.session_mgr.save_session(
            self.session_id, self.dialog, self.metrics.metrics
        )

        elapsed = time.time() - self.start_time
        print(
            Fore.GREEN
            + f"\n[Session Complete: {self.turn_index} turns in {elapsed:.1f}s]"
            + Style.RESET_ALL
        )
        print(f"[Cache Hit Rate: {self.metrics.hit_rate():.1%}]")
        print(
            f"[LLM Calls: {self.metrics.metrics['llm_calls']}, Errors: {self.metrics.metrics['llm_errors']}]"
        )
        logger.info(
            f"Session {self.session_id} completed: {self.turn_index} turns, {elapsed:.1f}s"
        )
        # Log Freudian slip instrumentation for each agent
        for _agent in (self.socrates, self.athena):
            _eng = _agent._slip_engine
            logger.info(
                "FreudianSlip stats [%s]: attempts=%d, successes=%d",
                _agent.name,
                getattr(_eng, "attempts", 0),
                getattr(_eng, "successes", 0),
            )

        # ============================================


# CLI / API ENTRY POINTS
# ============================================


def _pick_from_list(prompt_header: str, options: list[str]) -> str | None:
    """Display a numbered list and return the chosen item.

    Loops until the user enters a valid number or enters '0' to skip.
    Returns None only when the user explicitly enters '0'.
    """
    for idx, opt in enumerate(options, start=1):
        print(f"  [{idx}] {opt}")
    print(f"  [0] skip / keep default")
    while True:
        sys.stdout.flush()
        raw = input(f"{prompt_header} ").strip()
        if raw == "0":
            return None
        if not raw:
            print(
                Fore.YELLOW
                + "  Please enter a number from the list above (or 0 to skip)."
                + Style.RESET_ALL
            )
            continue
        try:
            choice = int(raw)
            if 1 <= choice <= len(options):
                return options[choice - 1]
        except ValueError:
            pass
        print(
            Fore.YELLOW
            + f"  [WARN] '{raw}' is not a valid selection. Enter a number between 1 and {len(options)}, or 0 to skip."
            + Style.RESET_ALL
        )


def select_llm_backend_and_models(cfg: "Config") -> None:
    """Interactive startup selector for LLM backend and per-agent models.

    Modifies *cfg* in-place as a runtime override only.
    The config file and .env are never written to.
    """
    print()
    print(Fore.CYAN + "Select backend:" + Style.RESET_ALL)
    print("  [1] grok")
    print("  [2] ollama")
    print("  [3] openai")
    print("  [4] anthropic")
    print("  [0] defaults (keep config as-is)")

    while True:
        sys.stdout.flush()
        backend_raw = input("Enter choice [0/1/2/3/4]: ").strip()
        if backend_raw in ("0", "1", "2", "3", "4"):
            break
        if backend_raw == "":
            print(
                Fore.YELLOW
                + "  Please enter 1 for grok, 2 for ollama, 3 for openai, 4 for anthropic, or 0 to keep defaults."
                + Style.RESET_ALL
            )
        else:
            print(
                Fore.YELLOW
                + f"  [WARN] '{backend_raw}' is not a valid choice. Please enter 0, 1, 2, 3, or 4."
                + Style.RESET_ALL
            )

    if backend_raw == "0":
        # Keep everything as configured – just print the summary and return.
        _print_llm_config_summary(cfg)
        return

    if backend_raw == "1":
        cfg.llm_backend = "grok"
        available_models = GROK_MODELS
        backend_label = "Grok"
    elif backend_raw == "3":
        cfg.llm_backend = "openai"
        available_models = OPENAI_MODELS
        backend_label = "OpenAI"
    elif backend_raw == "4":
        cfg.llm_backend = "anthropic"
        available_models = ANTHROPIC_MODELS
        backend_label = "Anthropic"
    else:  # backend_raw == "2"
        cfg.llm_backend = "ollama"
        available_models = OLLAMA_MODELS
        backend_label = "Ollama"

    print()
    print(Fore.CYAN + f"Available {backend_label} models:" + Style.RESET_ALL)
    while True:
        sys.stdout.flush()
        same = input("  Use same model for all agents? (y/n): ").strip().lower()
        if same in ("y", "yes", "n", "no"):
            break
        print(
            Fore.YELLOW + "  Please enter 'y' for yes or 'n' for no." + Style.RESET_ALL
        )

    if same in ("y", "yes"):
        print()
        print(Fore.CYAN + "Choose model:" + Style.RESET_ALL)
        model = _pick_from_list("Enter choice:", available_models)
        if model is None:
            print(
                Fore.YELLOW
                + "[WARN] Model selection skipped – keeping defaults."
                + Style.RESET_ALL
            )
            _print_llm_config_summary(cfg)
            return
        cfg.model_socrates = model
        cfg.model_athena = model
        cfg.model_fixy = model
    else:
        print()
        print(Fore.CYAN + "Choose model for Socrates:" + Style.RESET_ALL)
        model_s = _pick_from_list("Enter choice:", available_models)
        print()
        print(Fore.CYAN + "Choose model for Athena:" + Style.RESET_ALL)
        model_a = _pick_from_list("Enter choice:", available_models)
        print()
        print(Fore.CYAN + "Choose model for Fixy:" + Style.RESET_ALL)
        model_f = _pick_from_list("Enter choice:", available_models)

        if model_s is None or model_a is None or model_f is None:
            print(
                Fore.YELLOW
                + "[WARN] Incomplete model selection – keeping defaults."
                + Style.RESET_ALL
            )
            _print_llm_config_summary(cfg)
            return

        cfg.model_socrates = model_s
        cfg.model_athena = model_a
        cfg.model_fixy = model_f

    _print_llm_config_summary(cfg)


def _print_llm_config_summary(cfg: "Config") -> None:
    """Print the active LLM configuration summary."""
    print()
    print(Fore.GREEN + "[LLM CONFIG]" + Style.RESET_ALL)
    print(f"  Backend:   {cfg.llm_backend}")
    print(f"  Socrates:  {cfg.model_socrates}")
    print(f"  Athena:    {cfg.model_athena}")
    print(f"  Fixy:      {cfg.model_fixy}")
    print()


def run_cli():
    """Run command line interface - 200-turn no-timeout dialogue."""
    global CFG
    CFG = Config(max_turns=200, timeout_minutes=0, show_meta=True)

    print(Fore.GREEN + "=" * 80 + Style.RESET_ALL)
    print(
        Fore.GREEN
        + "Entelgia Unified – 200-Turn No-Timeout Edition By Sivan Havkin"
        + Style.RESET_ALL
    )
    print(Fore.GREEN + "=" * 80 + Style.RESET_ALL)

    select_llm_backend_and_models(CFG)

    print("\nConfiguration:")
    _SENSITIVE_KEYS = {
        "grok_api_key",
        "openai_api_key",
        "anthropic_api_key",
        "memory_secret_key",
    }
    config_dict = asdict(CFG)
    config_display = {
        k: ("***" if k in _SENSITIVE_KEYS else v)
        for k, v in config_dict.items()
        if not k.startswith("_")
    }
    print(json.dumps(config_display, ensure_ascii=False, indent=2))
    print()

    app_script = None
    try:
        app_script = MainScript(CFG)
        app_script.run()
        print(Fore.GREEN + "\nSession completed successfully!" + Style.RESET_ALL)
    except KeyboardInterrupt:
        print(
            Fore.YELLOW + "\n[INTERRUPTED] Session cancelled by user" + Style.RESET_ALL
        )
        logger.info("Session interrupted by user")
        if app_script is not None:
            try:
                app_script.metrics.save()
            except Exception as metrics_err:
                logger.error(f"Failed to save metrics on interrupt: {metrics_err}")
            try:
                app_script.session_mgr.save_session(
                    app_script.session_id,
                    app_script.dialog,
                    app_script.metrics.metrics,
                )
                print(
                    Fore.YELLOW
                    + f"[SESSION SAVED] Partial session {app_script.session_id} saved."
                    + Style.RESET_ALL
                )
                logger.info(
                    f"Partial session {app_script.session_id} saved on interrupt"
                )
            except Exception as save_err:
                logger.error(f"Failed to save session on interrupt: {save_err}")
        sys.exit(0)
    except Exception as e:
        print(Fore.RED + f"[FATAL ERROR] {e}" + Style.RESET_ALL)
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)


def run_tests():
    """Run unit tests."""
    print(Fore.GREEN + "Running Entelgia Unit Tests..." + Style.RESET_ALL)
    print()

    try:
        test_config_validation()
        test_lru_cache()
        test_redaction()
        test_validation()
        test_metrics_tracker()
        test_topic_manager()
        test_behavior_core()
        test_language_core()
        test_memory_signatures()
        test_session_manager()

        print()
        print(Fore.GREEN + "=" * 80 + Style.RESET_ALL)
        print(Fore.GREEN + "All tests passed!" + Style.RESET_ALL)
        print(Fore.GREEN + "=" * 80 + Style.RESET_ALL)
    except AssertionError as e:
        print(Fore.RED + f"Test failed: {e}" + Style.RESET_ALL)
        logger.error(f"Test failed: {e}")
        sys.exit(1)
    except Exception as e:
        print(Fore.RED + f"Test error: {e}" + Style.RESET_ALL)
        logger.error(f"Test error: {e}", exc_info=True)
        sys.exit(1)


def run_api():
    """Run FastAPI server."""
    global CFG

    if not FASTAPI_AVAILABLE:
        print(Fore.RED + "FastAPI not installed." + Style.RESET_ALL)
        print("Run: pip install fastapi uvicorn")
        sys.exit(1)

    CFG = Config()

    print(Fore.GREEN + "=" * 80 + Style.RESET_ALL)
    print(Fore.GREEN + "Entelgia REST API Server" + Style.RESET_ALL)
    print(Fore.GREEN + "=" * 80 + Style.RESET_ALL)
    print(f"\nStarting API server on http://0.0.0.0:8000")
    print(f"API Docs: http://localhost:8000/docs")
    print(f"API Spec: http://localhost:8000/redoc")
    print()

    try:
        import uvicorn

        uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")
    except ImportError:
        print(Fore.RED + "uvicorn not installed." + Style.RESET_ALL)
        print("Run: pip install uvicorn")
        sys.exit(1)


def main():
    """Main entry point with mode selection."""
    global CFG

    if len(sys.argv) > 1:
        mode = sys.argv[1].lower()

        if mode == "test":
            run_tests()
        elif mode == "api":
            run_api()
        elif mode in ["help", "-h", "--help"]:
            print(
                Fore.GREEN
                + "Entelgia Unified – 200-Turn No-Timeout Edition"
                + Style.RESET_ALL
            )
            print()
            print("Usage:")
            print(
                f"  python {os.path.basename(__file__)}              Run 200-turn no-timeout dialogue (default)"
            )
            print(f"  python {os.path.basename(__file__)} test         Run unit tests")
            print(
                f"  python {os.path.basename(__file__)} api          Start FastAPI server"
            )
            print(
                f"  python {os.path.basename(__file__)} help         Show this help message"
            )
            print()
            print("Requirements:")
            print("  • Python 3.10+")
            print("  • Ollama running locally (http://localhost:11434)")
            print("  • pip install requests colorama")
            print("  • pip install fastapi uvicorn (for API mode)")
            print("  • pip install pytest pytest-mock (for testing)")
            print()
            print("Environment Variables:")
            print(
                "  • MEMORY_SECRET_KEY    Secret key for memory signatures (recommended: 32+ chars)"
            )
            print()
            print("Features:")
            print("  • 200 turns total, no time limit")
            print("  • Multi-agent with Socrates & Athena")
            print("  • Persistent memory (STM + LTM)")
            print("  • Emotion tracking & importance scoring")
            print("  • Dream cycles & memory promotion")
            print("  • Fixy observer/fixer agent")
            print("  • LRU cache with 75% hit rate improvement")
            print("  • Error handling with exponential backoff")
            print("  • Session persistence & metrics tracking")
            print("  • REST API interface (FastAPI)")
            print("  • Unit tests (pytest)")
            print("  • MEMORY SECURITY with HMAC-SHA256 signatures")
            print("     - Cryptographic signatures on all memories")
            print("     - Automatic forgetting of tampered memories")
            print("     - Constant-time comparison to prevent timing attacks")
            print()
        else:
            print(Fore.RED + f"Unknown mode: {mode}" + Style.RESET_ALL)
            print(
                f"Run 'python {os.path.basename(__file__)} help' for usage information"
            )
            sys.exit(1)
    else:
        # Default: Run 200-turn no-timeout CLI dialogue
        run_cli()


if __name__ == "__main__":
    main()

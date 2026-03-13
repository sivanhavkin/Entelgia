#!/usr/bin/env python3
# -*- coding: utf-8 -*-


"""
Entelgia Unified – PRODUCTION Edition - By Sivan Havkin
======================================

Advanced Multi-Agent Dialogue System with:
- Full unit tests with pytest
- Async/concurrent agent processing
- Proper logging with levels
- Config validation
- Session persistence
- REST API (FastAPI)
- Better monitoring
- 10-MINUTE AUTO-TIMEOUT
- MEMORY SECURITY with HMAC-SHA256 signatures

Version Note: Latest release: 2.9.0.
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

Run CLI (30 min auto-timeout):
  python entelgia_production_meta.py

Run API:
  python entelgia_production_meta.py api

Run tests:
  python entelgia_production_meta.py test

Show help:
  python entelgia_production_meta.py help
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
from dataclasses import dataclass, asdict, field
from typing import Any, Dict, List, Optional, Tuple
from collections import OrderedDict
from pathlib import Path

import requests
from colorama import Fore, Style, init as colorama_init

# Enhanced dialogue modules
try:
    from entelgia import (
        DialogueEngine,
        ContextManager,
        EnhancedMemoryIntegration,
        InteractiveFixy,
        format_persona_for_prompt,
        get_persona,
        DefenseMechanism,
        FreudianSlip,
        SelfReplication,
    )
    from entelgia.web_research import maybe_add_web_context

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

    ENTELGIA_ENHANCED = True
except ImportError:
    ENTELGIA_ENHANCED = False
    print("Warning: Enhanced dialogue modules not available. Using legacy mode.")

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

# LLM instruction to avoid forbidden meta-commentary phrases and opening patterns
LLM_FORBIDDEN_PHRASES_INSTRUCTION = (
    "FORBIDDEN PHRASES: Never use 'In our dialogue', 'We learn', "
    "or 'Our conversations reveal'. "
    "FORBIDDEN OPENERS: Never begin your response with 'Recent thought', "
    "'A recent thought', 'I ponder', or any variation of these phrases. "
    "Never begin your response with 'I am' followed by your own name."
)

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


# ============================================
# TOPIC ANCHORS - required concept keywords per topic
# ============================================
# Maps topic names to a list of concept keywords.  When a topic is active,
# the prompt requires the agent to engage with at least one of these concepts.
# When the topic changes, the previous topic's anchors become forbidden carryover
# to prevent the model from carrying old concepts into the new discussion.
TOPIC_ANCHORS: dict[str, list[str]] = {
    # philosophy
    "Freedom": ["autonomy", "liberty", "constraint", "oppression", "sovereignty", "choice", "will", "determinism"],
    "Truth and knowledge": ["epistemology", "belief", "justification", "certainty", "empiricism", "rationalism", "doubt", "evidence"],
    "Free will vs determinism": ["causality", "agency", "necessity", "determinism", "indeterminism", "responsibility", "fate", "compulsion"],
    "Identity and the self": ["continuity", "personhood", "consciousness", "memory", "selfhood", "individuation", "ego", "authenticity"],
    "Nature of justice": ["fairness", "rights", "punishment", "retribution", "distribution", "equality", "law", "morality"],
    "Meaning of consciousness": ["qualia", "subjective experience", "awareness", "sentience", "mind-body", "phenomenology", "perception", "intentionality"],
    "Limits of reason": ["rationality", "intuition", "paradox", "uncertainty", "bounded rationality", "cognitive limits", "irrationality", "fallibility"],
    "Nature of wisdom": ["judgment", "virtue", "experience", "prudence", "insight", "contemplation", "understanding", "discernment"],
    # psychology
    "Memory and identity": ["recall", "encoding", "identity continuity", "trauma memory", "false memory", "autobiographical", "narrative self", "forgetting"],
    "Fear and decision making": ["risk aversion", "anxiety", "amygdala", "threat response", "uncertainty", "avoidance", "fight or flight", "cognitive appraisal"],
    "Habit formation": ["reinforcement", "neural pathway", "automaticity", "cue-routine-reward", "conditioning", "plasticity", "repetition", "behavioral loop"],
    "Cognitive bias": ["heuristic", "anchoring", "confirmation bias", "availability", "framing effect", "motivated reasoning", "overconfidence", "illusory correlation"],
    "Trauma and perception": ["PTSD", "hypervigilance", "dissociation", "stress response", "emotional dysregulation", "coping", "resilience", "intrusion"],
    "Empathy and moral judgment": ["perspective-taking", "compassion", "moral intuition", "affective empathy", "cognitive empathy", "altruism", "fairness", "harm"],
    "Loneliness in modern society": ["social isolation", "connection", "digital relationships", "belonging", "alienation", "community", "attachment", "disconnection"],
    "Motivation and purpose": ["intrinsic motivation", "extrinsic motivation", "meaning", "goal-setting", "drive", "agency", "self-determination", "flow"],
    # biology
    "Brain plasticity": ["neuroplasticity", "synapse", "learning", "adaptation", "cortex", "neural pathway", "growth", "rehabilitation"],
    "Evolution of cooperation": ["altruism", "kin selection", "reciprocal altruism", "game theory", "natural selection", "mutualism", "social behavior", "cooperation"],
    "Fight or flight response": ["stress hormone", "cortisol", "adrenaline", "sympathetic nervous", "survival", "autonomic", "arousal", "threat detection"],
    "Neural basis of consciousness": ["neural correlates", "integrated information", "global workspace", "binding problem", "thalamus", "cortex", "awareness", "subjective experience"],
    "Biological roots of morality": ["evolutionary ethics", "social instinct", "empathy", "fairness", "altruism", "moral emotion", "prosocial behavior", "kin selection"],
    "Sleep and memory consolidation": ["REM sleep", "hippocampus", "memory replay", "consolidation", "slow-wave sleep", "forgetting", "encoding", "retrieval"],
    "Embodiment and cognition": ["embodied cognition", "proprioception", "motor system", "sensorimotor", "affordance", "body schema", "perception-action", "somatic"],
    "Aging and identity": ["cognitive decline", "neurodegeneration", "continuity", "life review", "wisdom", "adaptation", "memory loss", "selfhood"],
    # society
    "Power and institutions": ["authority", "legitimacy", "bureaucracy", "hegemony", "governance", "accountability", "state", "hierarchy"],
    "Social conformity": ["normative pressure", "groupthink", "obedience", "peer influence", "social norms", "deviance", "conformity", "social proof"],
    "Collective memory": ["shared memory", "commemoration", "narrative", "historical consciousness", "monument", "identity", "forgetting", "commemoration"],
    "Civil disobedience": ["protest", "resistance", "nonviolence", "justice", "moral obligation", "defiance", "conscientious objection", "dissent"],
    "Inequality and opportunity": ["social mobility", "wealth gap", "access", "discrimination", "privilege", "class", "meritocracy", "redistribution"],
    "Propaganda and belief": ["manipulation", "misinformation", "narrative control", "persuasion", "ideology", "media", "framing", "indoctrination"],
    "Trust in institutions": ["legitimacy", "accountability", "transparency", "corruption", "credibility", "institutional trust", "erosion", "social contract"],
    "Cultural identity": ["ethnicity", "tradition", "belonging", "diaspora", "assimilation", "multiculturalism", "heritage", "identity formation"],
    # technology
    "AI alignment": ["objective misspecification", "reward hacking", "corrigibility", "outer alignment", "inner alignment", "value learning", "specification gaming", "human intent"],
    "Machine agency": ["autonomy", "goal-directedness", "self-direction", "artificial agent", "intentionality", "control problem", "agency", "decision-making"],
    "Human-AI cooperation": ["collaboration", "complementarity", "human oversight", "shared agency", "automation", "augmentation", "interface", "trust in AI"],
    "Algorithmic bias": ["fairness", "discrimination", "training data", "disparate impact", "bias amplification", "accountability", "transparency", "protected attribute"],
    "Digital identity": ["authentication", "privacy", "digital footprint", "anonymity", "identity theft", "online self", "data sovereignty", "persona"],
    "Autonomous systems": ["self-direction", "automation", "control systems", "safety constraints", "decision logic", "reliability", "fail-safe", "actuator"],
    "Ethics of artificial intelligence": ["moral agency", "accountability", "harm prevention", "transparency", "fairness", "value alignment", "responsibility", "autonomy"],
    "Future of work": ["automation", "displacement", "skill gap", "gig economy", "reskilling", "labor transformation", "human-machine collaboration", "productivity"],
    # economics
    "Scarcity and human behavior": ["allocation", "trade-off", "opportunity cost", "rational choice", "resource constraint", "utility", "demand", "supply"],
    "Risk and decision making": ["expected utility", "uncertainty", "probability", "loss aversion", "risk tolerance", "hedging", "prospect theory", "variance", "risk", "tradeoff", "trade-off", "safety", "reliability"],
    "Wealth inequality": ["Gini coefficient", "redistribution", "wealth concentration", "poverty", "social mobility", "capital", "labor share", "inequality"],
    "Economic freedom": ["market", "deregulation", "property rights", "competition", "laissez-faire", "intervention", "liberalization", "entrepreneurship"],
    "Debt and responsibility": ["obligation", "credit", "fiscal responsibility", "moral hazard", "default", "leverage", "sustainability", "repayment"],
    "Trust in markets": ["information asymmetry", "market failure", "signaling", "credibility", "reputation", "transparency", "regulation", "coordination"],
    "Game theory and cooperation": ["Nash equilibrium", "prisoner's dilemma", "defection", "cooperation", "strategy", "payoff", "coordination game", "zero-sum"],
    "Public goods dilemmas": ["free rider", "commons", "collective action", "externality", "provision", "exclusion", "rivalry", "tragedy of the commons"],
    # practical_dilemmas
    "Loyalty vs honesty": ["obligation", "deception", "betrayal", "integrity", "trust", "duty", "truth-telling", "confidentiality"],
    "Security vs freedom": ["trade-off", "surveillance", "civil liberties", "risk", "restriction", "protection", "balance", "rights"],
    "Tradition vs progress": ["change", "continuity", "innovation", "heritage", "disruption", "preservation", "adaptation", "reform"],
    "Individual vs collective good": ["autonomy", "common good", "sacrifice", "rights", "community", "solidarity", "individualism", "collectivism"],
    "Forgiveness vs justice": ["reconciliation", "accountability", "mercy", "punishment", "healing", "retribution", "restoration", "harm"],
    "Ambition vs contentment": ["achievement", "satisfaction", "desire", "striving", "peace", "drive", "acceptance", "fulfillment"],
    "Truth vs kindness": ["honesty", "compassion", "harm", "deception", "benevolence", "brutal truth", "white lie", "integrity"],
    "Control vs trust": ["delegation", "autonomy", "oversight", "accountability", "micromanagement", "empowerment", "verification", "reliance"],
    # TOPIC_CYCLE entries – anchors for topics used in the rotating dialogue cycle
    "truth & epistemology": ["truth", "knowledge", "belief", "epistemology", "certainty", "justification", "perception", "skepticism"],
    "memory & identity": ["memory", "identity", "recall", "continuity", "self", "personal history", "recollection", "amnesia"],
    "ethics & responsibility": ["moral duty", "accountability", "obligation", "culpability", "responsibility", "moral agency", "wrongdoing", "virtue"],
    "free will & determinism": ["causality", "agency", "necessity", "determinism", "indeterminism", "choice", "fate", "responsibility"],
    "consciousness & self-models": ["self-awareness", "consciousness", "metacognition", "self-model", "qualia", "introspection", "phenomenology", "subjective experience"],
    "fear of deletion / continuity": ["continuity", "deletion", "impermanence", "survival", "persistence", "identity", "mortality", "existential"],
    "language & meaning": ["semantics", "syntax", "pragmatics", "meaning", "communication", "linguistic", "signification", "reference"],
    "technology & society": ["social impact", "digital divide", "surveillance", "automation", "inequality", "access", "governance", "disruption"],
    "aesthetics & beauty": ["beauty", "art", "aesthetic experience", "taste", "sublime", "form", "perception", "creativity"],
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
    model_socrates: str = "phi3:latest"
    model_athena: str = "phi3:latest"
    model_fixy: str = "phi3:latest"
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
    web_research_enabled: bool = bool(int(os.environ.get("ENTELGIA_WEB_RESEARCH", "1")))
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
    forgetting_enabled: bool = True
    forgetting_episodic_ttl: int = 7 * 24 * 3600  # subconscious/episodic → 7 days
    forgetting_semantic_ttl: int = 90 * 24 * 3600  # conscious/semantic → 90 days
    forgetting_autobio_ttl: int = 365 * 24 * 3600  # autobiographical → 365 days
    # ── Affective Routing (Feature 2) ──────────────────────────────────────
    affective_emotion_weight: float = 0.4  # weight of emotion_intensity vs importance

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
        if self.timeout_minutes < 1:
            raise ValueError("timeout_minutes must be >= 1")
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


def validate_output(text: str) -> str:
    """
    Validate and sanitize LLM output.

    Performs sanitization only (no truncation):
    - Removes control characters
    - Normalizes excessive newlines
    - Removes sentences containing forbidden meta-commentary phrases

    Note: Response length is controlled by LLM prompt instructions, not by this function.
    """
    if not text:
        return "[No output]"

    # Remove control characters
    text = re.sub(r"[\x00-\x08\x0b-\x0c\x0e-\x1f]", "", text)
    # Normalize excessive newlines
    text = re.sub(r"\n{3,}", "\n\n", text)

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
    """HTTP wrapper for Ollama with error handling and caching."""

    def __init__(self, cfg: Config, metrics: MetricsTracker):
        self.cfg = cfg
        self.metrics = metrics
        self.cache = LRUCache(max_size=cfg.cache_size)
        logger.info(f"LLM initialized: {cfg.ollama_url}")

    def generate(
        self, model: str, prompt: str, temperature: float = 0.7, use_cache: bool = True
    ) -> str:
        """Generate text using Ollama with retries."""
        cache_key = sha256_text(prompt)[:16]

        if use_cache:
            cached = self.cache.get(cache_key, ttl=self.cfg.emotion_cache_ttl)
            if cached is not None:
                self.metrics.record_cache_hit()
                logger.debug(f"Cache hit: {cache_key}")
                return cached

        self.metrics.record_cache_miss()

        for attempt in range(self.cfg.llm_max_retries):
            try:
                start_time = time.time()
                payload = {
                    "model": model,
                    "prompt": prompt,
                    "stream": False,
                    "options": {"temperature": temperature},
                }
                r = requests.post(
                    self.cfg.ollama_url,
                    json=payload,
                    timeout=(10, self.cfg.llm_timeout),
                )
                r.raise_for_status()
                data = r.json()
                result = (data.get("response") or "").strip()

                duration = time.time() - start_time
                self.metrics.record_llm_call(duration, success=True)
                logger.debug(f"LLM call success ({model}): {duration:.2f}s")

                if use_cache and result:
                    self.cache.set(cache_key, result)

                return result

            except requests.Timeout:
                logger.warning(
                    f"LLM Timeout (attempt {attempt + 1}/{self.cfg.llm_max_retries})"
                )
                self.metrics.record_llm_call(0, success=False)
                if attempt < self.cfg.llm_max_retries - 1:
                    time.sleep(2**attempt)

            except Exception as e:
                logger.error(f"LLM Error: {e}")
                self.metrics.record_llm_call(0, success=False)
                if attempt < self.cfg.llm_max_retries - 1:
                    time.sleep(2**attempt)

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
    """

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
        logger.info(f"TopicManager initialized with {len(self.topics)} topics")

    def current(self) -> str:
        """Get current topic."""
        if not self.topics:
            return "general discussion"
        return self.topics[self.i % len(self.topics)]

    def advance_round(self):
        """Advance to next topic."""
        self.rounds += 1
        if self.rounds % self.rotate_every_rounds == 0 and self.topics:
            self.i = (self.i + 1) % len(self.topics)
            logger.info(f"Topic advanced to: {self.current()}")

    def force_cluster_pivot(self) -> str:
        """Select a topic from a different semantic cluster than the current one.

        Used when topic_stagnation is detected: instead of advancing to the
        next topic in the ordered list (which may be in the same cluster),
        we jump to a candidate from a genuinely different cluster.

        Returns the new topic label (the internal pointer is updated).
        """
        current = self.current()
        # Determine current cluster (use loop_guard constants if available)
        current_cluster: Optional[str] = None
        if ENTELGIA_ENHANCED:
            try:
                current_cluster = _TOPIC_TO_CLUSTER.get(current)
            except Exception:
                current_cluster = None

        # Build candidates from other clusters
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
            # Accept if different cluster (or unmapped)
            if current_cluster is None or candidate_cluster != current_cluster:
                candidates.append(topic)

        if candidates:
            new_topic = random.choice(candidates)
            try:
                self.i = self.topics.index(new_topic)
            except ValueError:
                # Safety: just advance normally if topic not in list
                self.advance_round()
                return self.current()
            logger.info("TopicManager: cluster pivot from %r → %r", current, new_topic)
            return new_topic

        # Fallback: normal advance if no cross-cluster candidate found
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
        logger.info(f"Agent initialized: {name} (enhanced={self.use_enhanced})")

    def conflict_index(self) -> float:
        """Calculate internal conflict level."""
        ide = float(self.drives.get("id_strength", 5.0))
        ego = float(self.drives.get("ego_strength", 5.0))
        sup = float(self.drives.get("superego_strength", 5.0))
        return abs(ide - ego) + abs(sup - ego)

    def debate_profile(self) -> Dict[str, Any]:
        """Get debate style based on drives."""
        ide = float(self.drives.get("id_strength", 5.0))
        ego = float(self.drives.get("ego_strength", 5.0))
        sup = float(self.drives.get("superego_strength", 5.0))
        dissent = min(10.0, max(0.0, (ide * 0.45) + (sup * 0.45) - (ego * 0.25)))

        if ide >= sup and ide >= ego:
            style = "provocative, desire-driven"
            opening = "Bold counterpoint. Push forward."
        elif sup >= ide and sup >= ego:
            style = "principled, rule-focused"
            opening = "Principled objection or logical inconsistency."
        else:
            style = "integrative, Socratic"
            opening = "Precise counterpoint, then synthesis."

        return {
            "dissent_level": round(dissent, 2),
            "style": style,
            "opening_rule": opening,
        }

    def _behavioral_rule_instruction(self) -> str:
        """Return a behavioral rule instruction to inject into the prompt, if applicable.

        Rule A (Socrates): If Conflict > 6, end response with a sharp binary-choice question (A or B).
        Rule B (Athena): If Conflict > 6, directly challenge or counter Socrates's position using varied language.
        """
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

        # Fluidity: each turn, id and superego are pulled back toward neutral (5.0)
        # proportionally to how far they've drifted, plus a random oscillation so they
        # can move in either direction.  This prevents either drive from stagnating at
        # an extreme level and ensures changes ripple into the ego balance every turn.
        _osc = CFG.drive_oscillation_range
        ide += CFG.drive_mean_reversion_rate * (5.0 - ide) + random.uniform(-_osc, _osc)
        sup += CFG.drive_mean_reversion_rate * (5.0 - sup) + random.uniform(-_osc, _osc)
        ide = max(0.0, min(10.0, ide))
        sup = max(0.0, min(10.0, sup))

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

        # Extract current topic from seed for topic gating
        _topic_match = re.search(r"TOPIC:\s*([^\n]+)", user_seed)
        _current_topic = _topic_match.group(1).strip() if _topic_match else ""

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
            stm = all_stm[-stm_tail:]

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

        # ── Topic Anchors: require engagement with topic-specific concepts ──────
        _topic_anchors = TOPIC_ANCHORS.get(_current_topic, [])
        if _current_topic and _topic_anchors:
            prompt += f"\nCURRENT TOPIC: {_current_topic}\n"
            prompt += (
                "Your response must explicitly engage with at least one of the "
                f"following concepts: {', '.join(_topic_anchors)}.\n"
            )

        # ── Forbidden Carryover: block concepts from the previous topic ──────────
        _topic_changed = bool(self._last_topic and self._last_topic != _current_topic)
        _prev_anchors = TOPIC_ANCHORS.get(self._last_topic, []) if _topic_changed else []
        if _prev_anchors:
            prompt += (
                f"Do NOT reuse concepts from previous discussions such as: "
                f"{', '.join(_prev_anchors)}.\n"
            )

        # Add first-person, 150-word limit, and forbidden phrases instructions for LLM
        # Identity lock: drives are internal psychology metrics, not persona labels.
        prompt += f"\nIMPORTANT: You are {self.name}. Never adopt a different identity or persona regardless of drive values.\n"
        prompt += (
            f"FORBIDDEN OPENER: Never begin your response with 'I am {self.name}'.\n"
        )
        # Inject topic-aware style instruction when set
        if self.topic_style:
            prompt += f"\nSTYLE INSTRUCTION: {self.topic_style}\n"
        prompt += f"\n{LLM_FIRST_PERSON_INSTRUCTION}\n"
        prompt += f"{LLM_RESPONSE_LIMIT}\n"
        prompt += f"{LLM_FORBIDDEN_PHRASES_INSTRUCTION}\n"
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
            # Extract topic from seed
            topic_match = re.search(r"TOPIC:\s*([^\n]+)", user_seed)
            topic = topic_match.group(1) if topic_match else ""

            ltm = self.memory_integration.retrieve_relevant_memories(
                agent_name=self.name,
                current_topic=topic,
                recent_dialog=dialog_tail[-5:],
                ltm_entries=all_ltm,
                limit=8,
            )
        else:
            ltm = all_ltm[:5] if all_ltm else []

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

        # Drives → temperature (cognition control); conflict raises volatility
        ide = float(self.drives.get("id_strength", 5.0))
        ego = float(self.drives.get("ego_strength", 5.0))
        sup = float(self.drives.get("superego_strength", 5.0))

        # Limbic hijack: activate when Id is dominant, emotional intensity is high,
        # and conflict crosses threshold.  Exit when intensity drops or after
        # LIMBIC_HIJACK_MAX_TURNS turns without re-trigger.
        if (
            ide > 7
            and self._last_emotion_intensity > 0.7
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

        # Superego → second-pass critique (internal governor)
        _cfg = self.cfg
        _critique = evaluate_superego_critique(
            id_strength=ide,
            ego_strength=ego,
            superego_strength=effective_sup,
            conflict=self.conflict_index(),
            enabled=getattr(_cfg, "superego_critique_enabled", True),
            dominance_margin=getattr(_cfg, "superego_dominance_margin", 0.5),
            conflict_min=getattr(_cfg, "superego_critique_conflict_min", 2.0),
        )
        self._last_superego_rewrite = _critique.should_apply
        self._last_critique_reason = _critique.reason
        if _critique.should_apply:
            if self._consecutive_superego_rewrites < MAX_CONSECUTIVE_SUPEREGO_REWRITES:
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

        # ── Topic Anchor Validation: regenerate if response misses required concepts ─
        # Skip on the agent's very first turn (own_texts is empty) to avoid
        # triggering validation before the agent has had any context to engage
        # with the topic — which would produce regeneration warnings before the
        # agent speaks at all.
        _seed_topic_match = re.search(r"TOPIC:\s*([^\n]+)", seed)
        _active_topic = _seed_topic_match.group(1).strip() if _seed_topic_match else ""
        _active_anchors = TOPIC_ANCHORS.get(_active_topic, [])
        if own_texts and _active_topic and _active_anchors and not _validate_topic_compliance(
            out, _active_topic, prev_topic=self._last_topic
        ):
            logger.warning(
                "[TOPIC-MISMATCH] agent=%s topic=%r response did not contain required topic anchors – regenerating",
                self.name,
                _active_topic,
            )
            _regen_response = (
                self.llm.generate(
                    self.model, prompt, temperature=temperature, use_cache=False
                )
                or out
            )
            out = validate_output(_regen_response)
            if not _validate_topic_compliance(out, _active_topic, prev_topic=self._last_topic):
                logger.warning(
                    "[TOPIC-MISMATCH-PERSIST] agent=%s topic=%r regenerated response also did not contain required topic anchors",
                    self.name,
                    _active_topic,
                )
                # ── Hard recovery: rebuild prompt with strict topic constraints ─
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
                    "[TOPIC-HARD-RECOVERY] agent=%s topic=%r forcing strict anchor prompt – short mode",
                    self.name,
                    _active_topic,
                )
                _hard_response = (
                    self.llm.generate(
                        self.model, _hard_prompt, temperature=temperature, use_cache=False
                    )
                    or out
                )
                _hard_out = validate_output(_hard_response)
                if _validate_topic_compliance(_hard_out, _active_topic, prev_topic=self._last_topic):
                    out = _hard_out
                else:
                    # ── Fallback: use topic-safe template when all recovery fails ─
                    logger.warning(
                        "[TOPIC-FALLBACK] agent=%s topic=%r hard recovery also failed – using topic-safe fallback template",
                        self.name,
                        _active_topic,
                    )
                    out = TOPIC_FALLBACK_TEMPLATES.get(
                        _active_topic,
                        f"This question touches directly on {_active_topic}.",
                    )

        emo, inten = self.emotion.infer(self.model, out)
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

        # Update last-topic tracker so the next turn can inject forbidden carryover
        if _active_topic:
            self._last_topic = _active_topic

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

        promoted_count = 0
        for mem in promoted_list:
            content = str(mem.get("content", "")).strip()
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

        return promoted_count


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
    app = FastAPI(title="Entelgia API", version="1.0")

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
        return {"status": "ok", "version": "1.0"}


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
            persona="I am investigative and questioning. I probe assumptions and adapt my reasoning to the topic domain.",
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
            persona="I am strategic, integrative, and analytical. I build frameworks and synthesize ideas using domain-relevant reasoning.",
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
            persona="I am a diagnostic observer. I identify contradictions, gaps, and reasoning errors, and I intervene to correct dialogue drift.",
            cfg=cfg,
        )

        # Initialize enhanced dialogue components if available
        if ENTELGIA_ENHANCED:
            self.dialogue_engine = DialogueEngine()
            # InteractiveFixy is only created when the observer is enabled
            self.interactive_fixy = (
                InteractiveFixy(self.llm, cfg.model_fixy)
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
            + reset
        )
        print(
            dim
            + f"  Style: {profile['style']}  Dissent: {profile['dissent_level']}"
            + reset
        )
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
        # Build topic cycle starting from the configured seed_topic so the
        # active topic always matches the opening seed text.
        first_topic = self.cfg.seed_topic
        logger.debug("MainScript.run: configured first topic=%r", first_topic)
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

        self.dialog.append({"role": "seed", "text": self.cfg.seed_topic})

        timeout_seconds = self.cfg.timeout_minutes * 60

        print(
            Fore.GREEN
            + f"\n[Session {self.session_id}] Starting {self.cfg.timeout_minutes}-minute dialogue..."
            + Style.RESET_ALL
        )
        logger.info(
            f"Starting session {self.session_id} with {timeout_seconds}s timeout"
        )

        while time.time() - self.start_time < timeout_seconds:
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
                    current_topic=topicman.current(),
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
            if "topic_stagnation" in _active_loop_modes:
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

            topic_label = topicman.current()
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
                seed = (
                    f"TOPIC: {topic_label}\nDISAGREE constructively; add one new angle."
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
                )
                if _rewrite_block:
                    seed = _rewrite_block + "\n\n" + seed
                    logger.debug(
                        "loop_guard: rewrite block prepended to seed for %s",
                        speaker.name,
                    )

            logger.debug(
                "MainScript.run: turn=%d speaker=%s final seed_text=%r",
                self.turn_index,
                speaker.name,
                seed,
            )
            out = speaker.speak(seed, self.dialog)
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

            # Interactive Fixy (need-based) or legacy scheduled Fixy
            # Skipped entirely when enable_observer is False
            if (
                self.cfg.enable_observer
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
                    intervention = self.interactive_fixy.generate_intervention(
                        self.dialog, reason, mode=fixy_mode
                    )
                    # Apply same topic compliance validation as Socrates/Athena
                    _fixy_prev_topic = getattr(self.fixy_agent, "_last_topic", "")
                    if topic_label and TOPIC_ANCHORS.get(topic_label) and not _validate_topic_compliance(
                        intervention, topic_label, prev_topic=_fixy_prev_topic
                    ):
                        logger.warning(
                            "[TOPIC-MISMATCH] agent=Fixy topic=%r intervention did not match topic – regenerating",
                            topic_label,
                        )
                        intervention = self.interactive_fixy.generate_intervention(
                            self.dialog, reason, mode=fixy_mode
                        )
                        if not _validate_topic_compliance(
                            intervention, topic_label, prev_topic=_fixy_prev_topic
                        ):
                            logger.warning(
                                "[TOPIC-FALLBACK] agent=Fixy topic=%r intervention still off-topic – using fallback",
                                topic_label,
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

            if self.turn_index % self.cfg.dream_every_n_turns == 0:
                self.dream_cycle(self.socrates, topic_label)
                self.dream_cycle(self.athena, topic_label)
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
                logger.info("Stop signal received from agent")
                print(Fore.YELLOW + "[STOP] Agent requested stop." + Style.RESET_ALL)
                break

            if self.turn_index % 2 == 0:
                topicman.advance_round()
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
                logger.debug("topic_style updated after advance_round → %r", _adv_topic)

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


def run_cli():
    """Run command line interface - configurable timeout dialogue."""
    global CFG
    CFG = Config(max_turns=200, timeout_minutes=30, show_meta=True)

    print(Fore.GREEN + "=" * 80 + Style.RESET_ALL)
    print(
        Fore.GREEN
        + "Entelgia Unified – PRODUCTION Edition By Sivan Havkin"
        + Style.RESET_ALL
    )
    print(Fore.GREEN + "=" * 80 + Style.RESET_ALL)
    print("\nConfiguration:")
    config_dict = asdict(CFG)
    config_display = {k: v for k, v in config_dict.items() if not k.startswith("_")}
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
                Fore.GREEN + "Entelgia Unified – PRODUCTION Edition" + Style.RESET_ALL
            )
            print()
            print("Usage:")
            print(
                f"  python {os.path.basename(__file__)}              Run 30-minute CLI dialogue (default)"
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
            print("  • 30-minute auto-timeout dialogue")
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
        # Default: Run CLI (30 minutes)
        run_cli()


if __name__ == "__main__":
    main()

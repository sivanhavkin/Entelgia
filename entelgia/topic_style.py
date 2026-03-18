#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Topic Style Module for Entelgia
Maps seed topic clusters to preferred reasoning styles for agent prompts.

Prevents agents from defaulting to abstract philosophical language when the
topic domain calls for a different mode of reasoning (analytical, scientific,
pragmatic, etc.).

v2.9.0: Two-layer topic-style control system separating content domain
selection (Layer 1) from linguistic register enforcement (Layer 2).
``build_style_instruction()`` now generates a strict mandatory control block
using the ``TOPIC_TONE_POLICY`` table.  ``scrub_rhetorical_openers()``
provides a lightweight post-generation register cleanup pass.
"""

import re
from typing import Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# Layer 1 – Default topic cluster fallback
# ---------------------------------------------------------------------------

DEFAULT_TOPIC_CLUSTER: str = "technology"
"""Cluster to use when topic classification fails or yields no match."""

# ---------------------------------------------------------------------------
# Topic cluster → preferred reasoning style (legacy compatibility)
# ---------------------------------------------------------------------------

TOPIC_STYLE: Dict[str, str] = {
    "technology": "analytical, concrete, system-oriented",
    "economics": "pragmatic, causal, incentive-based",
    "biology": "scientific, explanatory, mechanism-focused",
    "psychology": "behavioral, example-driven, analytical",
    "society": "sociological, institutional, real-world",
    "ethics_social": "normative, case-based, real-world",
    "practical_dilemmas": "case-based, scenario-driven",
    "practical": "case-based, scenario-driven",
    "identity": "behavioral, example-driven, analytical",
    "biological": "scientific, explanatory, mechanism-focused",
    "philosophy": "conceptual and reflective",
}

# ---------------------------------------------------------------------------
# Layer 2 – Tone policy per cluster
# ---------------------------------------------------------------------------

TOPIC_TONE_POLICY: Dict[str, Dict] = {
    "technology": {
        "allowed_registers": ["technical", "engineering", "analytic"],
        "forbidden_registers": ["philosophical", "poetic", "dramatic", "theatrical"],
        "forbidden_phrases": [
            "my dear friend",
            "let us explore",
            "let us delve deeper",
            "quest for knowledge",
            "intricate dance",
            "fundamental aspects of our existence",
        ],
        "preferred_cues": [
            "system constraints",
            "architecture",
            "tradeoff",
            "implementation",
            "failure mode",
            "optimization",
        ],
        "response_mode": "concrete_analysis",
    },
    "biology": {
        "allowed_registers": ["scientific", "mechanistic", "evidence-based"],
        "forbidden_registers": ["philosophical", "poetic", "dramatic", "theatrical"],
        "forbidden_phrases": [
            "my dear friend",
            "intricate dance",
            "quest for knowledge",
            "fundamental aspects of our existence",
        ],
        "preferred_cues": [
            "mechanism",
            "neural pathway",
            "hippocampus",
            "reactivation",
            "evidence",
            "experimental finding",
        ],
        "response_mode": "mechanistic_explanation",
    },
    "economics": {
        "allowed_registers": ["analytic", "policy-oriented", "causal"],
        "forbidden_registers": ["poetic", "dramatic", "theatrical"],
        "forbidden_phrases": [
            "my dear friend",
            "quest for knowledge",
        ],
        "preferred_cues": [
            "incentive",
            "market effect",
            "tradeoff",
            "policy",
            "cost",
            "allocation",
        ],
        "response_mode": "tradeoff_analysis",
    },
    "psychology": {
        "allowed_registers": ["clinical", "empirical", "explanatory"],
        "forbidden_registers": ["poetic", "theatrical"],
        "forbidden_phrases": [
            "my dear friend",
            "intricate dance",
        ],
        "preferred_cues": [
            "behavior pattern",
            "cognitive process",
            "affect regulation",
            "evidence",
            "mechanism",
        ],
        "response_mode": "structured_explanation",
    },
    "society": {
        "allowed_registers": ["sociological", "practical", "analytical"],
        "forbidden_registers": ["poetic", "theatrical"],
        "forbidden_phrases": [
            "my dear friend",
            "quest for knowledge",
        ],
        "preferred_cues": [
            "institution",
            "incentive",
            "social effect",
            "policy consequence",
            "group behavior",
        ],
        "response_mode": "social_analysis",
    },
    "practical_dilemmas": {
        "allowed_registers": ["pragmatic", "decision-oriented", "clear"],
        "forbidden_registers": ["poetic", "theatrical", "overly abstract"],
        "forbidden_phrases": [
            "my dear friend",
            "let us delve deeper",
            "quest for knowledge",
        ],
        "preferred_cues": [
            "option",
            "risk",
            "benefit",
            "next step",
            "constraint",
            "decision rule",
        ],
        "response_mode": "decision_support",
    },
    "philosophy": {
        "allowed_registers": ["dialectical", "socratic", "analytical"],
        "forbidden_registers": [],
        "forbidden_phrases": [],
        "preferred_cues": [
            "assumption",
            "premise",
            "contradiction",
            "ethical tension",
            "conceptual distinction",
        ],
        "response_mode": "dialectical_reasoning",
    },
    # loop_guard.py clusters – mapped to nearest policy equivalent
    "ethics_social": {
        "allowed_registers": ["analytic", "normative", "policy-oriented"],
        "forbidden_registers": ["poetic", "theatrical"],
        "forbidden_phrases": [
            "my dear friend",
            "quest for knowledge",
        ],
        "preferred_cues": [
            "norm",
            "obligation",
            "social contract",
            "tradeoff",
            "accountability",
        ],
        "response_mode": "normative_analysis",
    },
    "practical": {
        "allowed_registers": ["pragmatic", "decision-oriented", "clear"],
        "forbidden_registers": ["poetic", "theatrical", "overly abstract"],
        "forbidden_phrases": [
            "my dear friend",
            "let us delve deeper",
            "quest for knowledge",
        ],
        "preferred_cues": [
            "option",
            "risk",
            "benefit",
            "next step",
            "constraint",
        ],
        "response_mode": "decision_support",
    },
    "identity": {
        "allowed_registers": ["behavioral", "explanatory", "analytical"],
        "forbidden_registers": ["theatrical", "overly abstract"],
        "forbidden_phrases": [
            "my dear friend",
            "quest for knowledge",
        ],
        "preferred_cues": [
            "behavior pattern",
            "self-concept",
            "social role",
            "cognitive process",
            "evidence",
        ],
        "response_mode": "structured_explanation",
    },
    "biological": {
        "allowed_registers": ["scientific", "mechanistic", "evidence-based"],
        "forbidden_registers": ["philosophical", "poetic", "dramatic", "theatrical"],
        "forbidden_phrases": [
            "my dear friend",
            "intricate dance",
            "quest for knowledge",
            "fundamental aspects of our existence",
        ],
        "preferred_cues": [
            "mechanism",
            "pathway",
            "evidence",
            "experimental finding",
            "physiology",
        ],
        "response_mode": "mechanistic_explanation",
    },
}

# ---------------------------------------------------------------------------
# Mapping from production-file TOPIC_CLUSTERS keys to TOPIC_STYLE keys.
# The production file uses different cluster names from loop_guard.py, so
# both are covered here.
# ---------------------------------------------------------------------------

_CLUSTER_ALIAS: Dict[str, str] = {
    # production_meta cluster name → TOPIC_STYLE key
    "technology": "technology",
    "economics": "economics",
    "biology": "biology",
    "psychology": "psychology",
    "society": "society",
    "practical_dilemmas": "practical_dilemmas",
    "philosophy": "philosophy",
    # loop_guard.py cluster names
    "ethics_social": "ethics_social",
    "practical": "practical",
    "identity": "identity",
    "biological": "biological",
}

# ---------------------------------------------------------------------------
# Role-specific lines for build_style_instruction()
# ---------------------------------------------------------------------------

_ROLE_LINES: Dict[str, str] = {
    "Socrates": "Use investigative, topic-focused reasoning.",
    "Athena": "Use structured synthesis and concise explanation.",
    "Fixy": "Use direct diagnostic and corrective reasoning.",
}

# ---------------------------------------------------------------------------
# Rhetorical opener patterns for the post-generation scrubber
# ---------------------------------------------------------------------------

_RHETORICAL_OPENERS: List[str] = [
    r"my dear friend\s*[,!.]?",
    r"let us delve deeper\s*[,!.]?",
    r"let us explore\s*[,!.]?",
    r"these questions demand our thoughtful consideration\s*[,!.]?",
]


def get_style_for_cluster(cluster: Optional[str]) -> str:
    """Return the preferred reasoning style for *cluster*.

    Falls back to the ``DEFAULT_TOPIC_CLUSTER`` style when the cluster is
    unknown or ``None``.
    """
    if cluster is None:
        return TOPIC_STYLE.get(
            DEFAULT_TOPIC_CLUSTER, "analytical, concrete, system-oriented"
        )
    key = _CLUSTER_ALIAS.get(cluster, cluster)
    return TOPIC_STYLE.get(
        key,
        TOPIC_STYLE.get(DEFAULT_TOPIC_CLUSTER, "analytical, concrete, system-oriented"),
    )


def get_style_for_topic(topic: str, topic_clusters: Dict[str, list]) -> Tuple[str, str]:
    """Return ``(cluster, style)`` for *topic* given a *topic_clusters* mapping.

    Searches *topic_clusters* for a cluster whose topic list contains *topic*.
    Falls back to ``DEFAULT_TOPIC_CLUSTER`` when not found so that
    ``topic_style`` is never empty.
    """
    cluster = next((c for c, topics in topic_clusters.items() if topic in topics), None)
    resolved = cluster or DEFAULT_TOPIC_CLUSTER
    style = get_style_for_cluster(resolved)
    return (resolved, style)


def build_style_instruction(style: str, role: str = "", cluster: str = "") -> str:
    """Build a **mandatory** style-control block to inject into an agent prompt.

    Layer 2 enforcement: uses ``TOPIC_TONE_POLICY`` to produce an explicit
    block that names allowed/forbidden registers, forbidden phrases, preferred
    vocabulary cues, and the expected response mode.

    Args:
        style:   Reasoning style string (e.g. ``"analytical, concrete,
                 system-oriented"``).  Included for context but the policy
                 table drives the hard constraints.
        role:    Agent name (``"Socrates"``, ``"Athena"``, or ``"Fixy"``).
        cluster: Topic cluster key (e.g. ``"biology"``).  When absent or
                 unknown the ``DEFAULT_TOPIC_CLUSTER`` policy is applied so
                 that a control block is always generated.

    Returns:
        A multi-line STYLE INSTRUCTION block suitable for embedding in a
        prompt before the persona flavour section.
    """
    resolved_cluster = (
        cluster if cluster in TOPIC_TONE_POLICY else DEFAULT_TOPIC_CLUSTER
    )
    policy = TOPIC_TONE_POLICY[resolved_cluster]

    role_line = _ROLE_LINES.get(role, "Use topic-focused reasoning.")

    allowed = ", ".join(policy["allowed_registers"]) or "topic-appropriate"
    forbidden_reg = ", ".join(policy["forbidden_registers"]) or "none"
    cues = ", ".join(policy["preferred_cues"])
    banned_lines = "\n".join(f"- {p}" for p in policy["forbidden_phrases"])

    return (
        f"STYLE INSTRUCTION (MANDATORY)\n\n"
        f"Topic cluster: {resolved_cluster}\n"
        f"Role: {role}\n\n"
        f"{role_line}\n\n"
        f"Use these registers:\n{allowed}\n\n"
        f"Do NOT use these registers:\n{forbidden_reg}\n\n"
        f"Prefer vocabulary and framing such as:\n{cues}\n\n"
        "Avoid rhetorical/philosophical filler unless the topic cluster is philosophy.\n"
        "Do not use theatrical or poetic wording for non-philosophy topics.\n\n"
        f"Forbidden phrases:\n{banned_lines if banned_lines else '- none'}\n\n"
        f"Response mode:\n{policy['response_mode']}\n\n"
        "Output rules:\n"
        "- Be concrete.\n"
        "- Use domain-appropriate vocabulary.\n"
        "- Prefer explanation over rhetorical questioning.\n"
        "- Do not use grand philosophical framing unless cluster == philosophy.\n"
    )


def scrub_rhetorical_openers(text: str, cluster: str) -> str:
    """Strip legacy rhetorical openers from *text* for non-philosophy topics.

    Performs a conservative, exact-match pass over the leading portion of
    *text*.  Only the specific phrases listed in ``_RHETORICAL_OPENERS`` are
    removed, and only when they appear at the very start of the response and
    the active cluster is **not** ``"philosophy"``.

    Args:
        text:    The generated response text.
        cluster: The active topic cluster key.

    Returns:
        The cleaned text (unchanged when ``cluster == "philosophy"`` or no
        opener is matched).
    """
    if cluster == "philosophy":
        return text

    stripped = text.lstrip()
    for pattern in _RHETORICAL_OPENERS:
        m = re.match(r"(?i)" + pattern + r"\s*", stripped)
        if m:
            remainder = stripped[m.end() :].strip()
            if remainder:
                # Capitalise the first letter of what follows.
                # str.upper() is a no-op on non-letter characters so this
                # is safe regardless of what character follows the opener.
                return remainder[0].upper() + remainder[1:]
    return text

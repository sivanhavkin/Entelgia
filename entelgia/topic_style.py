#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Topic Style Module for Entelgia
Maps seed topic clusters to preferred reasoning styles for agent prompts.

Prevents agents from defaulting to abstract philosophical language when the
topic domain calls for a different mode of reasoning (analytical, scientific,
pragmatic, etc.).
"""

from typing import Dict, Optional, Tuple

# ---------------------------------------------------------------------------
# Topic cluster → preferred reasoning style
# ---------------------------------------------------------------------------

TOPIC_STYLE: Dict[str, str] = {
    "technology": "analytical, concrete, system-oriented",
    "economics": "pragmatic, causal, incentive-based",
    "biology": "scientific, explanatory, mechanism-focused",
    "psychology": "reflective, behavioral, example-driven",
    "society": "sociological, institutional, real-world",
    "ethics_social": "normative, case-based, real-world",
    "practical_dilemmas": "case-based, scenario-driven",
    "practical": "case-based, scenario-driven",
    "identity": "reflective, behavioral, example-driven",
    "biological": "scientific, explanatory, mechanism-focused",
    "philosophy": "conceptual and reflective",
}

# ---------------------------------------------------------------------------
# Mapping from the production-file TOPIC_CLUSTERS keys to TOPIC_STYLE keys.
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
# Style instruction templates per agent role
# ---------------------------------------------------------------------------

_STYLE_PREAMBLE = (
    "Adapt your reasoning style to the topic domain. "
    "Preferred style for this topic: {style}. "
    "Anchor your response in the topic domain — discuss real mechanisms, "
    "systems, or examples before abstract reflection. "
    "Do not default to abstract philosophical language unless the topic is "
    "explicitly philosophical."
)

_AGENT_STYLE_SUFFIX: Dict[str, str] = {
    "Socrates": (
        "Ask probing, domain-aware questions. "
        "Prefer concrete examples and causal chains over metaphors."
    ),
    "Athena": (
        "Build structured frameworks relevant to the domain. "
        "Use domain vocabulary and real-world cases."
    ),
    "Fixy": (
        "Identify gaps, contradictions, or reasoning errors specific to this domain. "
        "Be diagnostic and corrective."
    ),
}


def get_style_for_cluster(cluster: Optional[str]) -> str:
    """Return the preferred reasoning style for *cluster*.

    Falls back to ``"conceptual and reflective"`` when the cluster is unknown
    or ``None``.
    """
    if cluster is None:
        return "conceptual and reflective"
    key = _CLUSTER_ALIAS.get(cluster, cluster)
    return TOPIC_STYLE.get(key, "conceptual and reflective")


def get_style_for_topic(topic: str, topic_clusters: Dict[str, list]) -> Tuple[str, str]:
    """Return ``(cluster, style)`` for *topic* given a *topic_clusters* mapping.

    Searches *topic_clusters* for a cluster whose topic list contains *topic*.
    Falls back to ``("custom", "conceptual and reflective")`` when not found.
    """
    cluster = next((c for c, topics in topic_clusters.items() if topic in topics), None)
    style = get_style_for_cluster(cluster)
    return (cluster or "custom", style)


def build_style_instruction(style: str, agent_name: str = "") -> str:
    """Build the style instruction string to inject into an agent prompt.

    Args:
        style: Reasoning style string (e.g. ``"analytical, concrete, system-oriented"``).
        agent_name: Optional agent name for role-specific suffix.

    Returns:
        A multi-sentence instruction suitable for embedding in a prompt.
    """
    instruction = _STYLE_PREAMBLE.format(style=style)
    suffix = _AGENT_STYLE_SUFFIX.get(agent_name, "")
    if suffix:
        instruction = instruction + " " + suffix
    return instruction

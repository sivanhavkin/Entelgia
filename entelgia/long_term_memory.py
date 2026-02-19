#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Long-Term Memory System for Entelgia
=====================================
Personal long-term memory divided into two layers:
  - Unconscious: ALL experiences stored raw with defense mechanism metadata
  - Conscious: Content promoted via dreams, slips of tongue, and self-replication

Transfer mechanisms from unconscious to conscious:
  1. Dreams           – high-importance/emotion memories promoted during dream cycle
  2. Freudian Slips   – defended memories surface involuntarily during speech
  3. Self-Replication – recurring patterns identified and promoted via introspection
"""

import random
import re
from typing import Any, Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# Defense Mechanism Thresholds
# ---------------------------------------------------------------------------

# Emotion intensity above this triggers repression
_REPRESSION_INTENSITY_THRESHOLD = 0.75

# Emotions that are candidates for repression
_REPRESSED_EMOTIONS = frozenset(
    {
        "anger",
        "fear",
        "shame",
        "guilt",
        "anxiety",
        "disgust",
    }
)

# Keywords in content that trigger suppression
_SUPPRESSION_TRIGGER_WORDS = frozenset(
    {
        "forbidden",
        "wrong",
        "bad",
        "evil",
        "dangerous",
        "secret",
        "hidden",
        "private",
        "shameful",
    }
)


# ============================================
# DEFENSE MECHANISMS
# ============================================


class DefenseMechanism:
    """
    Applies psychoanalytic defense mechanisms to classify how memories
    are stored in the unconscious layer.

    Every memory enters the unconscious in raw form; defense mechanisms
    determine how strongly the memory is "defended" from reaching
    consciousness through normal recall (vs. leaking via slips/dreams/replication).

    Mechanisms modelled:
      - Repression : painful high-intensity emotion -> blocked from easy recall
      - Suppression: consciously avoided content -> pushed away
    """

    def analyze(
        self,
        content: str,
        emotion: str,
        emotion_intensity: float,
        importance: float,
    ) -> Dict[str, int]:
        """
        Analyze content and return defense mechanism classification.

        Args:
            content: Raw memory content text
            emotion: Detected emotion label (e.g. "fear", "anger")
            emotion_intensity: Emotion intensity 0..1
            importance: Memory importance score 0..1

        Returns:
            Dict with integer flags:
              - repressed (1=yes): painful emotion blocked from easy recall
              - suppressed (1=yes): consciously avoided content
        """
        text_lower = (content or "").lower()
        emo_lower = (emotion or "").lower()

        # Repression: high-intensity painful emotion -> defended against recall
        repressed = int(
            emo_lower in _REPRESSED_EMOTIONS
            and emotion_intensity >= _REPRESSION_INTENSITY_THRESHOLD
        )

        # Suppression: content contains consciously avoided topics
        suppressed = int(any(w in text_lower for w in _SUPPRESSION_TRIGGER_WORDS))

        return {"repressed": repressed, "suppressed": suppressed}

    def slip_probability(self, repressed: int, suppressed: int) -> float:
        """
        Probability that a memory produces a Freudian slip.

        Defended memories (repressed/suppressed) have greater unconscious
        pressure to surface during speech.

        Args:
            repressed: Repression flag (0 or 1)
            suppressed: Suppression flag (0 or 1)

        Returns:
            Probability 0..1
        """
        base = 0.04
        if repressed:
            base += 0.14  # Repressed content has strong upward pressure
        if suppressed:
            base += 0.08
        return min(0.30, base)


# ============================================
# FREUDIAN SLIP
# ============================================


class FreudianSlip:
    """
    Mechanism by which unconscious content surfaces involuntarily during speech.

    A Freudian slip occurs when:
      1. A defended unconscious memory is selected (probability-weighted by defenses)
      2. A short fragment of that memory leaks into the agent's speaking context
      3. The slipped memory is simultaneously promoted to the conscious layer
    """

    _FRAGMENT_MAX_LEN = 80  # Maximum characters in a slip fragment

    def __init__(self, defense: DefenseMechanism):
        self.defense = defense

    def attempt(
        self, unconscious_memories: List[Dict[str, Any]]
    ) -> Optional[Dict[str, Any]]:
        """
        Attempt a Freudian slip from the unconscious memory pool.

        Args:
            unconscious_memories: Recent entries from the unconscious (subconscious) layer

        Returns:
            The memory that slipped through, or None if no slip occurred
        """
        if not unconscious_memories:
            return None

        slipped: List[Dict[str, Any]] = []
        for mem in unconscious_memories:
            # Use stored defense flags; fall back to 0
            repressed = int(mem.get("intrusive", 0) or mem.get("repressed", 0))
            suppressed = int(mem.get("suppressed", 0))
            p = self.defense.slip_probability(repressed, suppressed)
            if random.random() < p:
                slipped.append(mem)

        if not slipped:
            return None

        # Among slipped memories, prefer the most important one
        return max(slipped, key=lambda m: float(m.get("importance", 0.0)))

    def format_fragment(self, memory: Dict[str, Any]) -> str:
        """
        Format a memory as a brief, natural-sounding slip fragment.

        Args:
            memory: The memory that is slipping through

        Returns:
            Short text fragment representing the unconscious intrusion
        """
        content = (memory.get("content") or "")[: self._FRAGMENT_MAX_LEN]
        # Prefer to end at a natural sentence boundary
        for sep in (".", "!", "?", ","):
            idx = content.find(sep)
            if 8 <= idx < self._FRAGMENT_MAX_LEN - 4:
                content = content[: idx + 1]
                break
        return content.strip()


# ============================================
# SELF-REPLICATION
# ============================================


class SelfReplication:
    """
    Self-directed promotion of unconscious memories to conscious layer.

    The agent periodically scans its own unconscious for recurring keyword
    patterns and promotes memories that embody those patterns to the
    conscious layer.  This creates a reflective self-narrative from raw
    unconscious data, without requiring LLM inference.
    """

    _MIN_OCCURRENCES = 2  # A keyword must appear in >= N distinct memories
    _PROMOTE_LIMIT = 3  # Maximum promotions per self-replication cycle

    def find_patterns(self, memories: List[Dict[str, Any]]) -> List[str]:
        """
        Identify recurring keywords across unconscious memories.

        Args:
            memories: Unconscious memory entries

        Returns:
            List of recurring keyword patterns (words >= 4 chars appearing >= MIN_OCCURRENCES times)
        """
        word_freq: Dict[str, int] = {}
        for mem in memories:
            content = (mem.get("content") or "").lower()
            # Match Latin words with >= 4 characters
            words = set(re.findall(r"[a-zA-Z]{4,}", content))
            for w in words:
                word_freq[w] = word_freq.get(w, 0) + 1

        return [w for w, cnt in word_freq.items() if cnt >= self._MIN_OCCURRENCES]

    def select_for_promotion(
        self,
        memories: List[Dict[str, Any]],
        patterns: List[str],
    ) -> List[Dict[str, Any]]:
        """
        Select memories to promote based on pattern frequency and importance.

        Args:
            memories: Unconscious memory pool
            patterns: Detected recurring keyword patterns

        Returns:
            Memories chosen for conscious promotion (at most _PROMOTE_LIMIT)
        """
        if not patterns or not memories:
            return []

        scored: List[Tuple[float, Dict[str, Any]]] = []
        for mem in memories:
            content_lower = (mem.get("content") or "").lower()
            pattern_hits = sum(1 for p in patterns if p in content_lower)
            if pattern_hits == 0:
                continue
            importance = float(mem.get("importance", 0.0))
            score = pattern_hits * 0.6 + importance * 0.4
            scored.append((score, mem))

        scored.sort(reverse=True, key=lambda x: x[0])
        return [mem for _, mem in scored[: self._PROMOTE_LIMIT]]

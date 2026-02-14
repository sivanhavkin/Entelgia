#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Context Manager for Entelgia
Manages intelligent context windowing, smart truncation, and memory integration.
"""

import re
from typing import Dict, List, Any, Optional


class ContextManager:
    """Manages intelligent context windowing and summarization."""

    def __init__(self):
        pass

    def build_enriched_context(
        self,
        agent_name: str,
        agent_lang: str,
        persona: str,
        drives: Dict[str, float],
        user_seed: str,
        dialog_tail: List[Dict[str, str]],
        stm: List[Dict[str, Any]],
        ltm: List[Dict[str, Any]],
        debate_profile: Dict[str, Any],
    ) -> str:
        """
        Build rich context with smart truncation and memory integration.

        Args:
            agent_name: Name of the agent
            agent_lang: Language code for agent
            persona: Persona description
            drives: Drive levels (id, ego, superego, self_awareness)
            user_seed: Seed instruction
            dialog_tail: Recent dialogue turns
            stm: Short-term memory entries
            ltm: Long-term memory entries
            debate_profile: Debate style profile

        Returns:
            Formatted prompt string
        """
        # Take last 8 turns (up from 5)
        recent_dialog = dialog_tail[-8:] if len(dialog_tail) >= 8 else dialog_tail

        # Smart truncation for dialogue
        dialog_lines = []
        for turn in recent_dialog:
            role = turn.get("role", "")  # Full name, not abbreviated
            text = turn.get("text", "")

            # Truncate at sentence boundary if needed
            text_display = self._truncate_at_sentence(text, max_len=500)
            dialog_lines.append(f"{role}: {text_display}")

        # Take last 6 STM entries (up from 3)
        recent_thoughts = stm[-6:] if len(stm) >= 6 else stm

        # Take up to 5 LTM entries (up from 2), prioritize by importance
        important_memories = self._prioritize_memories(ltm, limit=5)

        # Build prompt
        prompt = self._format_prompt(
            agent_name=agent_name,
            agent_lang=agent_lang,
            persona=persona,
            drives=drives,
            debate_profile=debate_profile,
            user_seed=user_seed,
            dialog_lines=dialog_lines,
            recent_thoughts=recent_thoughts,
            important_memories=important_memories,
        )

        return prompt

    def _truncate_at_sentence(self, text: str, max_len: int) -> str:
        """
        Truncate at sentence boundary, not mid-sentence.

        Args:
            text: Text to truncate
            max_len: Maximum length

        Returns:
            Truncated text ending at sentence boundary
        """
        if len(text) <= max_len:
            return text

        # Find last sentence ending before max_len
        for sep in [". ", "! ", "? ", ".\n", "!\n", "?\n"]:
            pos = text[:max_len].rfind(sep)
            if pos > max_len * 0.7:  # At least 70% of target length
                return text[: pos + 1] + "..."

        # Fallback: word boundary
        words = text[:max_len].rsplit(" ", 1)
        if len(words) > 1:
            return words[0] + "..."

        return text[:max_len] + "..."

    def _prioritize_memories(
        self, ltm: List[Dict[str, Any]], limit: int
    ) -> List[Dict[str, Any]]:
        """
        Prioritize memories by importance score.

        Args:
            ltm: Long-term memory entries
            limit: Maximum number to return

        Returns:
            Sorted list of important memories
        """
        if not ltm:
            return []

        # Sort by importance (if available)
        sorted_ltm = sorted(
            ltm, key=lambda m: float(m.get("importance", 0.0)), reverse=True
        )

        return sorted_ltm[:limit]

    def _format_prompt(
        self,
        agent_name: str,
        agent_lang: str,
        persona: str,
        drives: Dict[str, float],
        debate_profile: Dict[str, Any],
        user_seed: str,
        dialog_lines: List[str],
        recent_thoughts: List[Dict[str, Any]],
        important_memories: List[Dict[str, Any]],
    ) -> str:
        """
        Format enriched prompt with all context.

        Args:
            agent_name: Agent name
            agent_lang: Language code
            persona: Persona description
            drives: Drive levels
            debate_profile: Debate style
            user_seed: Seed instruction
            dialog_lines: Formatted dialogue lines
            recent_thoughts: Recent STM entries
            important_memories: Important LTM entries

        Returns:
            Formatted prompt
        """
        prompt = f"{agent_name} ({agent_lang}):\n"
        prompt += f"PERSONA: {persona}\n\n"

        # Add drive info
        id_str = drives.get("id_strength", 5.0)
        ego_str = drives.get("ego_strength", 5.0)
        sup_str = drives.get("superego_strength", 5.0)
        prompt += (
            f"[Drives: id={id_str:.1f} ego={ego_str:.1f} superego={sup_str:.1f}]\n"
        )

        # Add debate style
        style = debate_profile.get("style", "integrative")
        prompt += f"[Style: {style}]\n\n"

        prompt += f"SEED: {user_seed}\n\n"

        # Add dialogue
        prompt += "RECENT DIALOG:\n"
        for line in dialog_lines:
            prompt += f"{line}\n"

        # Add recent thoughts if available
        if recent_thoughts:
            prompt += "\nRecent thoughts:\n"
            for thought in recent_thoughts:
                text = thought.get("text", "")
                text_display = self._truncate_at_sentence(text, max_len=400)
                prompt += f"- {text_display}\n"

        # Add important memories if available
        if important_memories:
            prompt += "\nKey memories:\n"
            for memory in important_memories:
                content = memory.get("content", "")
                importance = memory.get("importance", 0.0)
                content_display = self._truncate_at_sentence(content, max_len=600)

                # Add star marker for very important memories
                marker = "⭐ " if float(importance) > 0.7 else ""
                prompt += f"{marker}- {content_display}\n"

        prompt += "\nRespond now:\n"

        return prompt


class EnhancedMemoryIntegration:
    """Integrate memories more meaningfully into prompts."""

    def __init__(self):
        pass

    def retrieve_relevant_memories(
        self,
        agent_name: str,
        current_topic: str,
        recent_dialog: List[Dict[str, str]],
        ltm_entries: List[Dict[str, Any]],
        limit: int = 8,
    ) -> List[Dict[str, Any]]:
        """
        Retrieve memories based on relevance scoring.

        Args:
            agent_name: Agent requesting memories
            current_topic: Current topic label
            recent_dialog: Recent dialogue turns
            ltm_entries: Available LTM entries
            limit: Maximum memories to return

        Returns:
            List of relevant memories
        """
        if not ltm_entries:
            return []

        # Score each memory
        scored_memories = []
        for mem in ltm_entries:
            score = self._calculate_relevance_score(
                memory=mem, topic=current_topic, recent_dialog=recent_dialog
            )
            scored_memories.append((score, mem))

        # Sort by score and return top N
        scored_memories.sort(reverse=True, key=lambda x: x[0])
        return [mem for score, mem in scored_memories[:limit]]

    def _calculate_relevance_score(
        self, memory: Dict[str, Any], topic: str, recent_dialog: List[Dict[str, str]]
    ) -> float:
        """
        Score memory relevance.

        Score = (
            topic_similarity * 0.4 +
            importance * 0.3 +
            dialog_relevance * 0.2 +
            recency * 0.1
        )

        Args:
            memory: Memory entry
            topic: Current topic
            recent_dialog: Recent dialogue

        Returns:
            Relevance score (0.0 to 1.0)
        """
        content = memory.get("content", "").lower()

        # Topic similarity (keyword overlap)
        topic_sim = self._keyword_similarity(content, topic.lower())

        # Importance (already in memory)
        importance = float(memory.get("importance", 0.5))

        # Dialog relevance (mentions concepts from recent turns)
        dialog_text = " ".join([t.get("text", "") for t in recent_dialog[-3:]]).lower()
        dialog_rel = self._keyword_similarity(content, dialog_text)

        # Recency (simple heuristic - could use timestamp)
        recency = 0.5  # Default for now

        # Calculate weighted score
        score = topic_sim * 0.4 + importance * 0.3 + dialog_rel * 0.2 + recency * 0.1

        return min(1.0, max(0.0, score))

    def _keyword_similarity(self, text1: str, text2: str) -> float:
        """
        Calculate simple keyword-based similarity.

        Args:
            text1: First text
            text2: Second text

        Returns:
            Similarity score (0.0 to 1.0)
        """
        if not text1 or not text2:
            return 0.0

        # Extract words longer than 3 characters
        words1 = set(w for w in re.findall(r"\w+", text1.lower()) if len(w) > 3)
        words2 = set(w for w in re.findall(r"\w+", text2.lower()) if len(w) > 3)

        if not words1 or not words2:
            return 0.0

        # Jaccard similarity
        intersection = len(words1 & words2)
        union = len(words1 | words2)

        return intersection / union if union > 0 else 0.0

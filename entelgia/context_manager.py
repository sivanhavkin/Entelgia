#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Context Manager for Entelgia
Manages intelligent context windowing and memory integration.

Version Note: Pronoun support and 150-word limit features added for v2.2.0
Latest official release: v2.7.0
"""

import re
from typing import Dict, List, Any, Optional

# LLM Response Length Instruction
LLM_RESPONSE_LIMIT = "IMPORTANT: Please answer in maximum 150 words."

# LLM First-Person Instruction - agents must speak as themselves using "I"
LLM_FIRST_PERSON_INSTRUCTION = "IMPORTANT: Always speak in first person. Use 'I', 'me', 'my'. Never refer to yourself in third person or by your own name."

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

# Hard output contract — injected before generation for all agents
LLM_OUTPUT_CONTRACT = (
    "OUTPUT CONTRACT: Respond directly and concisely.\n"
    "  - Start immediately with your point — no preamble.\n"
    "  - Length is dynamic: 1–2 sentences is fine; up to 4 sentences when the thought demands it.\n"
    "  - Vary your move: blunt challenge, sharp question, direct claim, or pointed objection.\n"
    "Write as natural flowing prose. Do NOT output numbered sections or visible labels "
    "such as 'Claim:', 'Mechanism:', '1.', '2.', '3.'. "
    "No broad preamble. No generic framing opener."
)

# Per-agent behavioral contracts — define role goals and allowed move variation,
# not rigid output shapes.
_AGENT_BEHAVIORAL_CONTRACTS: Dict[str, str] = {
    "Socrates": (
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
    ),
    "Athena": (
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
    ),
    "Fixy": (
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
    ),
}

# ── Memory leakage guard ────────────────────────────────────────────────────
# These sets enumerate every LTM / STM field that is *internal* to the
# memory subsystem and must **never** be forwarded verbatim into an agent
# prompt.  Only ``content`` (LTM) and ``text`` (STM) carry human-readable
# narrative that the LLM should see.
_INTERNAL_LTM_FIELDS: frozenset = frozenset(
    {
        "id",
        "agent",
        "ts",
        "layer",
        "source",
        "promoted_from",
        "intrusive",
        "suppressed",
        "retrain_status",
        "signature_hex",  # HMAC-SHA256 cryptographic signature
        "expires_at",  # TTL expiry timestamp (Forgetting Policy)
        "confidence",  # confidence score (Confidence Metadata)
        "provenance",  # memory origin label (Confidence Metadata)
    }
)

_INTERNAL_STM_FIELDS: frozenset = frozenset(
    {
        "ts",
        "topic",
        "emotion",
        "emotion_intensity",
        "source",
        "sensitive",
        "_signature",  # HMAC-SHA256 cryptographic signature
    }
)


def _safe_ltm_content(mem: Dict[str, Any]) -> str:
    """Return only the human-readable content from an LTM record.

    All internal fields (``signature_hex``, ``expires_at``, ``confidence``,
    ``provenance``, ``id``, ``ts``, ``layer``, ``source``, etc.) are
    deliberately ignored so they can never be forwarded to the LLM.
    """
    return str(mem.get("content") or "")


def _safe_stm_text(entry: Dict[str, Any]) -> str:
    """Return only the human-readable text from an STM entry.

    Internal fields such as ``_signature``, ``topic``, ``emotion``, and
    ``ts`` are deliberately ignored so they can never be forwarded to the
    LLM.
    """
    return str(entry.get("text") or "")


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
        show_pronoun: bool = False,
        agent_pronoun: Optional[str] = None,
        web_context: str = "",
        topic_style: str = "",
        topics_enabled: bool = True,
        energy: float = 100.0,
        pressure: float = 0.0,
        emotion: str = "neutral",
        emotion_intensity: float = 0.0,
        conflict: float = 0.0,
        unresolved: int = 0,
        stagnation: float = 0.0,
        kind: str = "",
        temp: float = 0.65,
        dissent: float = 0.0,
        drive_combo: str = "",
    ) -> str:
        """
        Build rich context with smart truncation and memory integration.

        Args:
            agent_name: Name of the agent
            agent_lang: Language code for the agent (e.g., 'he', 'en') - currently unused, reserved for future use
            persona: Persona description
            drives: Drive levels (id, ego, superego, self_awareness)
            user_seed: Seed instruction
            dialog_tail: Recent dialogue turns
            stm: Short-term memory entries
            ltm: Long-term memory entries
            debate_profile: Debate style profile
            show_pronoun: Whether to display pronoun after agent name
            agent_pronoun: Pronoun to display (e.g., "he", "she") if show_pronoun is True
            web_context: Optional external knowledge context from web research
            topic_style: Optional style instruction derived from the seed topic cluster
            topics_enabled: Whether the topic subsystem is active.  When
                ``False``, ``topic_style`` is suppressed regardless of the
                value passed by the caller, ensuring no topic-related
                instructions appear in the prompt.
            energy: Current energy level of the agent (0–100).
            pressure: Current drive pressure of the agent.
            emotion: Current dominant emotion label.
            emotion_intensity: Intensity of the current emotion (0–1).
            conflict: Current drive conflict index.
            unresolved: Number of open/unresolved questions.
            stagnation: Current stagnation score (0–1).
            kind: Last response kind label (e.g., 'reflective', 'assertive').
            temp: LLM temperature used last turn.
            dissent: Dissent level from debate profile.
            drive_combo: Drive combination label from debate profile.

        Returns:
            Formatted prompt string
        """
        # When the topic subsystem is disabled, force topic_style to empty so
        # that no STYLE INSTRUCTION block is injected into the prompt.
        if not topics_enabled:
            topic_style = ""
        # Take last 8 turns (up from 5)
        recent_dialog = dialog_tail[-8:] if len(dialog_tail) >= 8 else dialog_tail

        # Smart display for dialogue - truncate long content at word boundary with "..."
        max_dialog_text = 200
        dialog_lines = []
        for turn in recent_dialog:
            role = turn.get("role", "")  # Full name, not abbreviated
            text = self._truncate_text(turn.get("text", ""), max_dialog_text)
            dialog_lines.append(f"{role}: {text}")

        # Take last 6 STM entries (up from 3)
        recent_thoughts = stm[-6:] if len(stm) >= 6 else stm

        # Take up to 5 LTM entries (up from 2), prioritize by importance
        important_memories = self._prioritize_memories(ltm, limit=5)

        # Build prompt
        prompt = self._format_prompt(
            agent_name=agent_name,
            persona=persona,
            drives=drives,
            debate_profile=debate_profile,
            user_seed=user_seed,
            dialog_lines=dialog_lines,
            recent_thoughts=recent_thoughts,
            important_memories=important_memories,
            show_pronoun=show_pronoun,
            agent_pronoun=agent_pronoun,
            web_context=web_context,
            topic_style=topic_style,
            energy=energy,
            pressure=pressure,
            emotion=emotion,
            emotion_intensity=emotion_intensity,
            conflict=conflict,
            unresolved=unresolved,
            stagnation=stagnation,
            kind=kind,
            temp=temp,
            dissent=dissent,
            drive_combo=drive_combo,
        )

        return prompt

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

    def _truncate_text(self, text: str, max_length: int) -> str:
        """
        Truncate text to max_length characters at a word boundary.

        Args:
            text: Text to truncate
            max_length: Maximum character length before truncation

        Returns:
            Text truncated at the last word boundary before max_length, with "..." appended
        """
        if len(text) <= max_length:
            return text
        # Find the last space at or before max_length to avoid cutting mid-word
        cut = text.rfind(" ", 0, max_length)
        if cut <= 0:
            cut = max_length  # No space found; fall back to hard cut
        return text[:cut] + "..."

    def _format_prompt(
        self,
        agent_name: str,
        persona: str,
        drives: Dict[str, float],
        debate_profile: Dict[str, Any],
        user_seed: str,
        dialog_lines: List[str],
        recent_thoughts: List[Dict[str, Any]],
        important_memories: List[Dict[str, Any]],
        show_pronoun: bool = False,
        agent_pronoun: Optional[str] = None,
        web_context: str = "",
        topic_style: str = "",
        energy: float = 100.0,
        pressure: float = 0.0,
        emotion: str = "neutral",
        emotion_intensity: float = 0.0,
        conflict: float = 0.0,
        unresolved: int = 0,
        stagnation: float = 0.0,
        kind: str = "",
        temp: float = 0.65,
        dissent: float = 0.0,
        drive_combo: str = "",
    ) -> str:
        """
        Format enriched prompt with all context.

        Args:
            agent_name: Agent name
            persona: Persona description
            drives: Drive levels
            debate_profile: Debate style
            user_seed: Seed instruction
            dialog_lines: Formatted dialogue lines
            recent_thoughts: Recent STM entries
            important_memories: Important LTM entries
            show_pronoun: Whether to display pronoun after agent name
            agent_pronoun: Pronoun to display (e.g., "he", "she")
            web_context: Optional external knowledge block from web research
            topic_style: Optional style instruction derived from the seed topic cluster
            energy: Current energy level of the agent (0–100).
            pressure: Current drive pressure of the agent.
            emotion: Current dominant emotion label.
            emotion_intensity: Intensity of the current emotion (0–1).
            conflict: Current drive conflict index.
            unresolved: Number of open/unresolved questions.
            stagnation: Current stagnation score (0–1).
            kind: Last response kind label.
            temp: LLM temperature used last turn.
            dissent: Dissent level from debate profile.
            drive_combo: Drive combination label from debate profile.

        Returns:
            Formatted prompt
        """
        # Format agent name with optional pronoun
        if show_pronoun and agent_pronoun:
            agent_header = f"{agent_name} ({agent_pronoun}):\n"
        else:
            agent_header = f"{agent_name}:\n"

        prompt = agent_header
        prompt += f"PERSONA: {persona}\n\n"

        # Add drive info
        id_str = drives.get("id_strength", 5.0)
        ego_str = drives.get("ego_strength", 5.0)
        sup_str = drives.get("superego_strength", 5.0)
        sa_str = drives.get("self_awareness", 0.55)
        prompt += f"[Drives: id={id_str:.1f} ego={ego_str:.1f} sup={sup_str:.1f} sa={sa_str:.2f}]\n"

        # Add runtime agent state (all key state variables)
        # Sanitize string fields to word characters and hyphens only to prevent injection
        safe_emotion = re.sub(r"[^\w\-]", "", emotion)[:32] or "neutral"
        safe_kind = re.sub(r"[^\w\-]", "", kind)[:32]
        safe_combo = re.sub(r"[^\w\-]", "", drive_combo)[:32]
        prompt += (
            f"[State: energy={energy:.1f}"
            f" pressure={pressure:.2f}"
            f" conflict={conflict:.2f}"
            f" unresolved={unresolved}"
            f" stagnation={stagnation:.2f}"
            f" emotion={safe_emotion}({emotion_intensity:.2f})"
            f" kind={safe_kind}"
            f" temp={temp:.2f}"
            f"]\n"
        )

        # Add debate style with combo and dissent
        style = debate_profile.get("style", "integrative")
        _profile_combo = safe_combo or debate_profile.get("drive_combo", "")
        _profile_dissent = dissent if dissent else debate_profile.get("dissent_level", 0.0)
        prompt += f"[Style: {style} | combo={_profile_combo} | dissent={_profile_dissent:.2f}]\n\n"

        prompt += f"SEED: {user_seed}\n\n"

        # Add dialogue
        prompt += "RECENT DIALOG:\n"
        for line in dialog_lines:
            prompt += f"{line}\n"

        # Add recent thoughts if available - truncate long entries at word boundary with "..."
        max_thought_text = 150
        if recent_thoughts:
            prompt += "\nRecent thoughts:\n"
            for thought in recent_thoughts:
                # _safe_stm_text ensures only the human-readable text field is
                # forwarded – internal fields (_signature, emotion, ts …) are
                # never included.
                text = self._truncate_text(_safe_stm_text(thought), max_thought_text)
                prompt += f"- {text}\n"

        # Add important memories if available - truncate long entries at word boundary with "..."
        max_memory_text = 200
        if important_memories:
            prompt += "\nKey memories:\n"
            for memory in important_memories:
                # _safe_ltm_content ensures only the human-readable content
                # field is forwarded – internal fields (signature_hex,
                # expires_at, confidence, provenance, id, ts, layer …) are
                # never included.
                content = self._truncate_text(
                    _safe_ltm_content(memory), max_memory_text
                )
                importance = memory.get("importance", 0.0)

                # Add star marker for very important memories
                marker = "* " if float(importance) > 0.7 else ""
                prompt += f"{marker}- {content}\n"

        # Add external knowledge context if provided
        if web_context:
            prompt += "\nExternal Knowledge Context:\n"
            prompt += web_context + "\n"
            prompt += (
                "Instructions for agents:\n"
                "- Superego must verify credibility of external sources.\n"
                "- Ego must integrate sources into the reasoning.\n"
                "- Id may resist heavy research if energy is low.\n"
                "- Fixy monitors reasoning loops and source reliability.\n"
            )

        # Inject topic-aware style instruction when provided
        if topic_style:
            prompt += f"\nSTYLE INSTRUCTION: {topic_style}\n"

        # Add first-person, 150-word limit, and forbidden phrases instructions for LLM
        # Identity lock: drives are internal psychology metrics, not persona labels.
        prompt += f"\nIMPORTANT: You are {agent_name}. Never adopt a different identity or persona regardless of drive values.\n"
        prompt += (
            f"FORBIDDEN OPENER: Never begin your response with 'I am {agent_name}'.\n"
        )
        # Inject hard output contract and agent-specific behavioral contract
        prompt += f"\n{LLM_OUTPUT_CONTRACT}\n"
        _agent_contract = _AGENT_BEHAVIORAL_CONTRACTS.get(agent_name, "")
        if _agent_contract:
            prompt += f"\n{_agent_contract}\n"
        prompt += f"{LLM_FIRST_PERSON_INSTRUCTION}\n"
        prompt += f"{LLM_RESPONSE_LIMIT}\n"
        prompt += f"{LLM_FORBIDDEN_PHRASES_INSTRUCTION}\n"
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
        topics_enabled: bool = True,
    ) -> List[Dict[str, Any]]:
        """
        Retrieve memories based on relevance scoring.

        Args:
            agent_name: Agent requesting memories
            current_topic: Current topic label
            recent_dialog: Recent dialogue turns
            ltm_entries: Available LTM entries
            limit: Maximum memories to return
            topics_enabled: Whether the topic subsystem is active.  When
                ``False``, ``current_topic`` is ignored and memories are
                ranked by importance and dialog relevance only, preventing
                topic-based filtering in topics-disabled sessions.

        Returns:
            List of relevant memories
        """
        if not ltm_entries:
            return []

        # When topics are disabled, discard the topic label so that memory
        # scoring cannot be biased by a stale or irrelevant topic string.
        effective_topic = current_topic if topics_enabled else ""

        # Score each memory
        scored_memories = []
        for mem in ltm_entries:
            score = self._calculate_relevance_score(
                memory=mem, topic=effective_topic, recent_dialog=recent_dialog
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


# ---------------------------------------------------------------------------
# Entry point — allows running directly: python entelgia/context_manager.py
# ---------------------------------------------------------------------------


if __name__ == "__main__":
    cm = ContextManager()

    sample_drives = {"id_strength": 6.2, "ego_strength": 7.5, "superego_strength": 8.0}
    sample_stm = [
        {"text": "Consciousness may arise from self-referential information loops."},
        {"text": "The hard problem resists purely functional explanations."},
        {"text": "Embodiment plays a crucial role in shaping cognition."},
    ]
    sample_ltm = [
        {
            "content": "Socrates argued that the unexamined life is not worth living.",
            "importance": 0.9,
        },
        {
            "content": "Athena synthesized Platonic idealism with empirical observation.",
            "importance": 0.75,
        },
        {
            "content": "Earlier dialogue resolved the free-will tension via compatibilism.",
            "importance": 0.6,
        },
    ]
    sample_dialog = [
        {"role": "Socrates", "text": "What is the nature of consciousness?"},
        {"role": "Athena", "text": "It emerges from complex information processing."},
        {
            "role": "Socrates",
            "text": "But does that account for subjective experience?",
        },
    ]
    sample_debate_profile = {"style": "integrative"}

    print("=" * 60)
    print("Context Manager Demo")
    print("=" * 60)

    prompt = cm.build_enriched_context(
        agent_name="Socrates",
        agent_lang="en",
        persona="Ancient Greek philosopher; pursues truth through dialectic questioning.",
        drives=sample_drives,
        user_seed="Explore the relationship between consciousness and identity.",
        dialog_tail=sample_dialog,
        stm=sample_stm,
        ltm=sample_ltm,
        debate_profile=sample_debate_profile,
        show_pronoun=True,
        agent_pronoun="he",
    )

    print(prompt)
    print("=" * 60)

    emi = EnhancedMemoryIntegration()
    relevant = emi.retrieve_relevant_memories(
        agent_name="Socrates",
        current_topic="consciousness",
        recent_dialog=sample_dialog,
        ltm_entries=sample_ltm,
        limit=3,
    )

    print("\nRelevant memories retrieved:")
    for mem in relevant:
        print(f"  [{mem.get('importance', 0.0):.2f}] {mem.get('content', '')}")

    print("\nDone.")

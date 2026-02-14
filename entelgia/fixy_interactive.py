#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Interactive Fixy for Entelgia
Need-based interventions rather than scheduled interventions.
"""

import re
from typing import Dict, List, Tuple, Any, Optional


class InteractiveFixy:
    """Fixy as active dialogue participant with intelligent interventions."""

    def __init__(self, llm, model: str):
        """
        Initialize Interactive Fixy.

        Args:
            llm: LLM instance for generating interventions
            model: Model name to use
        """
        self.llm = llm
        self.model = model

    def should_intervene(
        self, dialog: List[Dict[str, str]], turn_count: int
    ) -> Tuple[bool, str]:
        """
        Decide if intervention needed based on dialogue state.

        Args:
            dialog: Full dialogue history
            turn_count: Current turn number

        Returns:
            Tuple of (should_intervene, reason)
        """
        # Don't intervene too early
        if turn_count < 3:
            return (False, "")

        # Get last 10 turns for analysis
        last_10 = dialog[-10:] if len(dialog) >= 10 else dialog

        # Pattern 1: Circular reasoning (repetition)
        if self._detect_repetition(last_10):
            return (True, "circular_reasoning")

        # Pattern 2: High conflict without synthesis (check every 6+ turns)
        if turn_count >= 6 and self._detect_high_conflict(last_10):
            return (True, "high_conflict_no_resolution")

        # Pattern 3: Surface-level discussion for too long
        if turn_count >= 10 and self._detect_shallow_discussion(last_10):
            return (True, "shallow_discussion")

        # Pattern 4: Missed synthesis opportunity
        if turn_count >= 5 and self._detect_synthesis_opportunity(last_10):
            return (True, "synthesis_opportunity")

        # Pattern 5: Meta-reflection needed (every 15 turns)
        if turn_count > 15 and turn_count % 15 == 0:
            return (True, "meta_reflection_needed")

        return (False, "")

    def generate_intervention(self, dialog: List[Dict[str, str]], reason: str) -> str:
        """
        Generate contextual intervention.

        Args:
            dialog: Dialogue history
            reason: Reason for intervention

        Returns:
            Intervention text
        """
        context = self._build_intervention_context(dialog, reason)

        # Create intervention prompt based on reason
        prompts = {
            "circular_reasoning": "You are Fixy, the meta-cognitive observer. The dialogue has circled back to the same points multiple times. Generate a brief intervention (2-4 sentences) that:\n1. Names the circular pattern you observe\n2. Suggests a specific reframe or new angle\n3. Helps break the loop",
            "high_conflict_no_resolution": "You are Fixy, the meta-cognitive observer. The dialogue has high conflict without moving toward synthesis. Generate a brief intervention (2-4 sentences) that:\n1. Acknowledges the tension\n2. Points out the complementary aspects being missed\n3. Suggests a bridging perspective",
            "shallow_discussion": "You are Fixy, the meta-cognitive observer. The dialogue has stayed at a surface level for a while. Generate a brief intervention (2-4 sentences) that:\n1. Notes the pattern of surface-level engagement\n2. Suggests going deeper\n3. Offers a specific deeper question or angle",
            "synthesis_opportunity": "You are Fixy, the meta-cognitive observer. There's an obvious synthesis opportunity being missed. Generate a brief intervention (2-4 sentences) that:\n1. Points out the complementary ideas\n2. Suggests how they might connect\n3. Encourages integration",
            "meta_reflection_needed": "You are Fixy, the meta-cognitive observer. It's time for meta-reflection on the dialogue. Generate a brief intervention (2-4 sentences) that:\n1. Reflects on what's been accomplished\n2. Notes what patterns have emerged\n3. Suggests where to go next",
        }

        prompt_template = prompts.get(reason, prompts["circular_reasoning"])

        full_prompt = f"""{prompt_template}

RECENT DIALOGUE:
{context}

Generate your intervention (2-4 sentences, direct and concrete):"""

        intervention = self.llm.generate(
            self.model, full_prompt, temperature=0.4, use_cache=False
        )

        return (
            intervention.strip()
            if intervention
            else "I notice we might benefit from a fresh perspective here."
        )

    def _build_intervention_context(
        self, dialog: List[Dict[str, str]], reason: str
    ) -> str:
        """
        Build context string for intervention.

        Args:
            dialog: Dialogue history
            reason: Intervention reason

        Returns:
            Formatted context string
        """
        # Get last 6 turns for context
        recent = dialog[-6:] if len(dialog) >= 6 else dialog

        context_lines = []
        for turn in recent:
            role = turn.get("role", "")
            text = turn.get("text", "")
            # Truncate to 200 chars for context
            text_short = text[:200] + "..." if len(text) > 200 else text
            context_lines.append(f"{role}: {text_short}")

        return "\n".join(context_lines)

    def _detect_repetition(self, turns: List[Dict[str, str]]) -> bool:
        """
        Detect if same concepts repeated 3+ times.

        Args:
            turns: Recent dialogue turns

        Returns:
            True if repetition detected
        """
        if len(turns) < 4:
            return False

        # Extract key words from each turn (words > 4 chars)
        turn_keywords = []
        for turn in turns:
            text = turn.get("text", "").lower()
            words = set(w for w in re.findall(r"\w+", text) if len(w) > 4)
            turn_keywords.append(words)

        # Check for high overlap between multiple turns
        high_overlap_count = 0
        for i in range(len(turn_keywords) - 1):
            for j in range(i + 1, len(turn_keywords)):
                if len(turn_keywords[i]) > 0 and len(turn_keywords[j]) > 0:
                    overlap = len(turn_keywords[i] & turn_keywords[j])
                    union = len(turn_keywords[i] | turn_keywords[j])
                    similarity = overlap / union if union > 0 else 0.0

                    if similarity > 0.5:  # More than 50% similar
                        high_overlap_count += 1

        # If we find 3+ pairs with high overlap, it's repetitive
        return high_overlap_count >= 3

    def _detect_high_conflict(self, turns: List[Dict[str, str]]) -> bool:
        """
        Detect high conflict without resolution.

        Args:
            turns: Recent dialogue turns

        Returns:
            True if high conflict detected
        """
        if len(turns) < 4:
            return False

        # Simple heuristic: look for disagreement markers
        conflict_markers = [
            "לא",
            "אבל",
            "disagree",
            "however",
            "wrong",
            "incorrect",
            "actually",
            "contrary",
            "opposite",
            "טעות",
            "שגוי",
        ]

        conflict_count = 0
        for turn in turns:
            text = turn.get("text", "").lower()
            for marker in conflict_markers:
                if marker in text:
                    conflict_count += 1
                    break

        # High conflict if more than 60% of turns have conflict markers
        return (conflict_count / len(turns)) > 0.6

    def _detect_shallow_discussion(self, turns: List[Dict[str, str]]) -> bool:
        """
        Detect surface-level discussion.

        Args:
            turns: Recent dialogue turns

        Returns:
            True if shallow discussion detected
        """
        if len(turns) < 6:
            return False

        # Heuristic: if turns are consistently short, might be shallow
        avg_length = sum(len(turn.get("text", "")) for turn in turns) / len(turns)

        # Also check for lack of depth markers
        depth_markers = [
            "why",
            "because",
            "מדוע",
            "כי",
            "therefore",
            "implies",
            "consequence",
            "deeper",
            "fundamental",
            "underlying",
            "עמוק",
            "יסוד",
            "השלכה",
        ]

        depth_count = 0
        for turn in turns:
            text = turn.get("text", "").lower()
            for marker in depth_markers:
                if marker in text:
                    depth_count += 1
                    break

        # Shallow if average length < 150 and few depth markers
        return avg_length < 150 and (depth_count / len(turns)) < 0.3

    def _detect_synthesis_opportunity(self, turns: List[Dict[str, str]]) -> bool:
        """
        Detect when complementary ideas haven't been connected.

        Args:
            turns: Recent dialogue turns

        Returns:
            True if synthesis opportunity detected
        """
        if len(turns) < 4:
            return False

        # Look for synthesis markers being absent
        synthesis_markers = [
            "connect",
            "integrate",
            "together",
            "both",
            "combine",
            "מחבר",
            "משלב",
            "יחד",
            "שניהם",
            "גם",
        ]

        has_synthesis = False
        for turn in turns[-3:]:  # Check last 3 turns
            text = turn.get("text", "").lower()
            for marker in synthesis_markers:
                if marker in text:
                    has_synthesis = True
                    break
            if has_synthesis:
                break

        # If no synthesis markers in recent turns and we have enough content, might be opportunity
        return not has_synthesis and len(turns) >= 5

#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Dialogue Engine for Entelgia
Manages dynamic speaker selection and flexible seed generation for natural dialogue flow.
"""

import random
from typing import Dict, List, Any, Tuple, TYPE_CHECKING

if TYPE_CHECKING:
    from typing import Protocol
    
    class Agent(Protocol):
        """Type hint for Agent class."""
        name: str
        def conflict_index(self) -> float: ...


class SeedGenerator:
    """Generates varied, context-aware dialogue seeds."""
    
    SEED_STRATEGIES = [
        "agree_and_expand",
        "question_assumption",
        "synthesize",
        "constructive_disagree",
        "explore_implication",
        "introduce_analogy",
        "meta_reflect",
    ]
    
    SEED_TEMPLATES = {
        "agree_and_expand": "TOPIC: {topic}\nBUILD on the previous insight. Add depth or a new dimension.",
        "question_assumption": "TOPIC: {topic}\nQUESTION a hidden assumption. What are we taking for granted?",
        "synthesize": "TOPIC: {topic}\nINTEGRATE the different views. Find the connecting thread.",
        "constructive_disagree": "TOPIC: {topic}\nDISAGREE constructively. Offer an alternative perspective.",
        "explore_implication": "TOPIC: {topic}\nEXPLORE consequences. Where does this line of thinking lead?",
        "introduce_analogy": "TOPIC: {topic}\nCONNECT via analogy. How is this like something else?",
        "meta_reflect": "TOPIC: {topic}\nREFLECT on our dialogue. What are we learning? Where are we stuck?"
    }
    
    def generate_seed(
        self,
        topic: str,
        recent_turns: List[Dict[str, str]],
        speaker: Any,  # Agent type
        turn_count: int
    ) -> str:
        """
        Generate contextual seed based on dialogue state.
        
        Args:
            topic: Current topic label
            recent_turns: Recent dialogue turns
            speaker: Current speaker agent
            turn_count: Current turn number
        
        Returns:
            Formatted seed instruction
        """
        if not recent_turns:
            return self.SEED_TEMPLATES["constructive_disagree"].format(topic=topic)
        
        # Get last emotion if available
        last_turn = recent_turns[-1]
        last_emotion = last_turn.get("emotion", "neutral")
        
        # Get conflict level
        try:
            conflict_level = speaker.conflict_index()
        except:
            conflict_level = 5.0
        
        # Select strategy based on dialogue state
        strategy = self._select_strategy(turn_count, conflict_level, last_emotion)
        
        # Format and return seed
        template = self.SEED_TEMPLATES.get(strategy, self.SEED_TEMPLATES["constructive_disagree"])
        return template.format(topic=topic)
    
    def _select_strategy(self, turn_count: int, conflict_level: float, last_emotion: str) -> str:
        """
        Select seed strategy based on dialogue state.
        
        Args:
            turn_count: Current turn number
            conflict_level: Speaker's conflict index
            last_emotion: Emotion from last turn
        
        Returns:
            Strategy name
        """
        # Every 7 turns, meta-reflect
        if turn_count > 0 and turn_count % 7 == 0:
            return "meta_reflect"
        
        # High conflict → synthesize
        if conflict_level > 8.0:
            return "synthesize"
        
        # After anger/frustration → agree and expand
        if last_emotion in ["anger", "frustration"]:
            return "agree_and_expand"
        
        # Otherwise, random selection with weighted probabilities
        weights = {
            "agree_and_expand": 0.15,
            "question_assumption": 0.20,
            "synthesize": 0.10,
            "constructive_disagree": 0.25,
            "explore_implication": 0.15,
            "introduce_analogy": 0.10,
            "meta_reflect": 0.05
        }
        
        strategies = list(weights.keys())
        probabilities = list(weights.values())
        
        return random.choices(strategies, weights=probabilities)[0]


class DialogueEngine:
    """Manages dynamic, natural dialogue flow."""
    
    def __init__(self):
        self.seed_generator = SeedGenerator()
    
    def select_next_speaker(
        self,
        current_speaker: Any,  # Agent type
        dialog_history: List[Dict[str, str]],
        agents: List[Any],  # List[Agent]
        allow_fixy: bool = False,
        fixy_probability: float = 0.0
    ) -> Any:  # Returns Agent
        """
        Select next speaker based on dialogue dynamics.
        
        Args:
            current_speaker: Agent who just spoke
            dialog_history: Full dialogue history
            agents: List of available agents
            allow_fixy: Whether Fixy can speak now
            fixy_probability: Probability of Fixy speaking if allowed
        
        Returns:
            Next speaker agent
        """
        if len(agents) < 2:
            return agents[0] if agents else current_speaker
        
        # Check recent speakers (last 5 turns)
        recent_speakers = [turn.get("role", "") for turn in dialog_history[-5:]]
        
        # Don't allow same agent 3+ times in a row
        if len(recent_speakers) >= 2:
            last_two = recent_speakers[-2:]
            if all(s == current_speaker.name for s in last_two):
                # Force switch
                other_agents = [a for a in agents if a.name != current_speaker.name]
                if other_agents:
                    return self._select_by_engagement(other_agents, dialog_history)
        
        # Allow Fixy to interject if conditions met
        if allow_fixy and random.random() < fixy_probability:
            fixy = next((a for a in agents if a.name == "Fixy"), None)
            if fixy:
                return fixy
        
        # Calculate engagement scores for each agent
        candidates = [a for a in agents if a.name != current_speaker.name and a.name != "Fixy"]
        
        if not candidates:
            # No other candidates, return different agent or current
            return next((a for a in agents if a.name != current_speaker.name), current_speaker)
        
        # Select based on engagement
        return self._select_by_engagement(candidates, dialog_history)
    
    def _select_by_engagement(self, candidates: List[Any], dialog_history: List[Dict[str, str]]) -> Any:
        """
        Select speaker based on engagement metrics.
        
        Args:
            candidates: List of candidate agents
            dialog_history: Dialogue history
        
        Returns:
            Selected agent
        """
        if len(candidates) == 1:
            return candidates[0]
        
        # Count recent participation (last 10 turns)
        recent_turns = dialog_history[-10:] if len(dialog_history) >= 10 else dialog_history
        participation_count = {agent.name: 0 for agent in candidates}
        
        for turn in recent_turns:
            role = turn.get("role", "")
            if role in participation_count:
                participation_count[role] += 1
        
        # Calculate scores (prefer less recent speakers, but with some randomness)
        scores = {}
        for agent in candidates:
            # Base score: inverse of participation
            base_score = 10.0 - participation_count.get(agent.name, 0)
            
            # Add conflict index as minor factor
            try:
                conflict_bonus = agent.conflict_index() * 0.1
            except:
                conflict_bonus = 0.5
            
            # Add randomness (10-20% variation)
            random_factor = random.uniform(0.9, 1.2)
            
            scores[agent.name] = (base_score + conflict_bonus) * random_factor
        
        # Select agent with highest score
        best_agent_name = max(scores, key=scores.get)
        return next(a for a in candidates if a.name == best_agent_name)
    
    def generate_seed(
        self,
        topic: str,
        dialog_history: List[Dict[str, str]],
        speaker: Any,  # Agent
        turn_count: int
    ) -> str:
        """
        Generate contextual seed for speaker.
        
        Args:
            topic: Current topic
            dialog_history: Recent dialogue
            speaker: Current speaker
            turn_count: Turn number
        
        Returns:
            Seed instruction string
        """
        recent_turns = dialog_history[-5:] if len(dialog_history) >= 5 else dialog_history
        return self.seed_generator.generate_seed(topic, recent_turns, speaker, turn_count)
    
    def should_allow_fixy(self, dialog_history: List[Dict[str, str]], turn_count: int) -> Tuple[bool, float]:
        """
        Determine if Fixy should be allowed to speak.
        
        Args:
            dialog_history: Dialogue history
            turn_count: Current turn number
        
        Returns:
            Tuple of (allow_fixy, probability)
        """
        # Don't allow Fixy too early
        if turn_count < 4:
            return False, 0.0
        
        # Don't allow if Fixy spoke recently (within last 3 turns)
        recent_speakers = [turn.get("role", "") for turn in dialog_history[-3:]]
        if "Fixy" in recent_speakers:
            return False, 0.0
        
        # Base probability: 20% after turn 4
        probability = 0.20
        
        # Increase if dialogue seems stuck (similar patterns)
        if len(dialog_history) >= 5:
            last_5_texts = [turn.get("text", "")[:100].lower() for turn in dialog_history[-5:]]
            # Simple heuristic: check for word overlap
            if self._detect_repetition_simple(last_5_texts):
                probability = 0.35
        
        return True, probability
    
    def _detect_repetition_simple(self, texts: List[str]) -> bool:
        """
        Simple repetition detection based on keyword overlap.
        
        Args:
            texts: List of text snippets
        
        Returns:
            True if repetition detected
        """
        if len(texts) < 3:
            return False
        
        # Extract key words (>4 chars)
        all_words = []
        for text in texts:
            words = [w for w in text.split() if len(w) > 4]
            all_words.append(set(words))
        
        # Check for high overlap between texts
        overlaps = 0
        for i in range(len(all_words) - 1):
            for j in range(i + 1, len(all_words)):
                if len(all_words[i]) > 0 and len(all_words[j]) > 0:
                    overlap = len(all_words[i] & all_words[j]) / max(len(all_words[i]), len(all_words[j]))
                    if overlap > 0.6:
                        overlaps += 1
        
        return overlaps >= 2

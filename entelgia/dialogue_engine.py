#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Dialogue Engine for Entelgia
Manages dynamic speaker selection and flexible seed generation for natural dialogue flow.

v2.9.0: Added AgentMode enum and cluster-aware topic pivot support.
"""

import logging
import random
import re
from typing import Dict, List, Any, Tuple, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from entelgia.fixy_interactive import FixyGuidance

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from typing import Protocol

    class Agent(Protocol):
        """Type hint for Agent class."""

        name: str

        def conflict_index(self) -> float: ...


# ---------------------------------------------------------------------------
# Agent response modes
# ---------------------------------------------------------------------------
# These modes are injected into the seed when a loop failure mode is active,
# directing the agent to respond in a specific way rather than its default
# pattern.


class AgentMode:
    """Named constants for agent response modes."""

    NORMAL = "NORMAL"
    CONTRADICT = "CONTRADICT"
    CONCRETIZE = "CONCRETIZE"
    INVERT = "INVERT"
    MECHANIZE = "MECHANIZE"
    PIVOT = "PIVOT"


# Policy: loop failure mode → agent response mode
_LOOP_AGENT_POLICY: Dict[str, str] = {
    "loop_repetition": AgentMode.CONCRETIZE,
    "weak_conflict": AgentMode.INVERT,
    "premature_synthesis": AgentMode.CONTRADICT,
    "topic_stagnation": AgentMode.PIVOT,
    "conceptual_loop": AgentMode.MECHANIZE,
    "axis_stagnation": AgentMode.CONCRETIZE,
}

# Mode-specific instruction appended to the seed
_AGENT_MODE_INSTRUCTION: Dict[str, str] = {
    AgentMode.CONTRADICT: (
        "\nMODE: CONTRADICT — sharpen the disagreement. "
        "Identify one claim in the previous turn and argue directly against it. "
        "Do NOT synthesise or hedge."
    ),
    AgentMode.CONCRETIZE: (
        "\nMODE: CONCRETIZE — give one specific real-world example, case study, "
        "or counterexample. No abstract restatement. Facts only."
    ),
    AgentMode.INVERT: (
        "\nMODE: INVERT — temporarily defend the opposite of your usual position. "
        "Commit to the reversal; do not qualify it as hypothetical."
    ),
    AgentMode.MECHANIZE: (
        "\nMODE: MECHANIZE — explain the step-by-step causal mechanism behind "
        "your claim. No slogans. Show how it actually works."
    ),
    AgentMode.PIVOT: (
        "\nMODE: PIVOT — shift to a genuinely different conceptual domain while "
        "keeping one clear bridge to the previous idea. "
        "Do not stay inside the same philosophical cluster."
    ),
}


# Header prefix that all seed templates inject when a topic is active.
# Used to detect and strip the prefix when the topic subsystem is disabled.
_SEED_TOPIC_PREFIX = "TOPIC: \n"

# ---------------------------------------------------------------------------
# Fixy guidance bias constants
# ---------------------------------------------------------------------------
#: Additive weight increase applied to strategies that support the Fixy-
#: recommended move type.  Scaled by guidance.confidence so a strong
#: recommendation (confidence=1.0) raises the target strategy's weight by
#: this full amount, while a weak one (confidence=0.5) applies half the boost.
_GUIDANCE_BOOST: float = 0.25

#: Weight reduction applied to strategies that conflict with the recommended
#: move type (e.g. suppress "agree_and_expand" when guidance asks for attack).
_GUIDANCE_SUPPRESS: float = 0.15

#: Minimum strategy weight after suppression.  Prevents any strategy from
#: reaching exactly 0 so the selection is never fully deterministic — Fixy
#: biases the dialogue, it does not control it.
_GUIDANCE_MIN_WEIGHT: float = 0.02

# ---------------------------------------------------------------------------
# Dynamic continuation context helpers
# ---------------------------------------------------------------------------

#: Instruction injected before each continuation prompt to stop the agent
#: from restarting the topic or repeating prior arguments.
_CONTINUATION_INSTRUCTION: str = (
    "Continue the dialogue from its last meaningful state.\n"
    "Do not restart the topic.\n"
    "Do not repeat prior arguments."
)

#: Adversative conjunctions used to detect tension points in dialogue text.
_TENSION_MARKERS: tuple = (
    "but ",
    "however,",
    "yet ",
    "although ",
    "nevertheless,",
    "despite ",
)

#: Minimum character length for a sentence to qualify as a last_claim or
#: tension_point candidate.
_MIN_SENTENCE_LEN: int = 20

#: Minimum character length for a sentence to qualify as an
#: unresolved_question candidate.
_MIN_QUESTION_LEN: int = 10

#: Maximum characters taken from any extracted sentence field.
_MAX_FIELD_LEN: int = 120


def extract_continuation_context(
    recent_turns: List[Dict[str, str]],
    topic: str = "",
) -> Dict[str, str]:
    """Extract continuation context from recent dialogue turns.

    Scans *recent_turns* (most recent last) for:

    - ``dominant_topic``      — taken from *topic* when provided.
    - ``last_claim``          — the most recent declarative sentence
      (non-question, length > :data:`_MIN_SENTENCE_LEN`).
    - ``unresolved_question`` — the most recent question sentence
      (ends with ``?``, length > :data:`_MIN_QUESTION_LEN`).
    - ``tension_point``       — the most recent sentence containing an
      adversative conjunction that is longer than :data:`_MIN_SENTENCE_LEN`.

    Entries whose ``role`` is ``"seed"`` are skipped so the static opening
    seed text is never treated as conversation content.

    When *recent_turns* contains **no real speaker turns** (first session
    with no memory), ``last_claim``, ``unresolved_question``, and
    ``tension_point`` are all empty strings.  Callers should treat that
    signal as "first session — fall back to the default topic seed."

    Args:
        recent_turns: Slice of the dialogue history to scan.
        topic: Active topic label; becomes ``dominant_topic`` in the result.

    Returns:
        Dict with keys ``dominant_topic``, ``last_claim``,
        ``unresolved_question``, ``tension_point``.
    """
    dominant_topic: str = topic
    last_claim: str = ""
    unresolved_question: str = ""
    tension_point: str = ""

    # Walk from most-recent to oldest to surface the latest signals first.
    for turn in reversed(recent_turns):
        if turn.get("role") == "seed":
            continue
        text = turn.get("text", "").strip()
        if not text:
            continue

        # Split on terminal punctuation boundaries.
        sentences: List[str] = [
            s.strip()
            for s in re.split(r"(?<=[.!?])\s+", text)
            if s.strip()
        ]

        for sentence in reversed(sentences):
            lower = sentence.lower()

            if not last_claim and not sentence.endswith("?") and len(sentence) > _MIN_SENTENCE_LEN:
                last_claim = sentence[:_MAX_FIELD_LEN]

            if (
                not unresolved_question
                and sentence.endswith("?")
                and len(sentence) > _MIN_QUESTION_LEN
            ):
                unresolved_question = sentence[:_MAX_FIELD_LEN]

            if (
                not tension_point
                and any(marker in lower for marker in _TENSION_MARKERS)
                and len(sentence) > _MIN_SENTENCE_LEN
            ):
                tension_point = sentence[:_MAX_FIELD_LEN]

        # Stop scanning once all three contextual signals have been found.
        if last_claim and unresolved_question and tension_point:
            break

    return {
        "dominant_topic": dominant_topic,
        "last_claim": last_claim,
        "unresolved_question": unresolved_question,
        "tension_point": tension_point,
    }


def build_continuation_prompt(context: Dict[str, str]) -> str:
    """Build a continuation prompt from extracted context.

    Constructs a multi-line prompt of the form::

        Continue the dialogue from its last meaningful state.
        Do not restart the topic.
        Do not repeat prior arguments.

        The previous discussion focused on: <dominant_topic>.
        The last claim made was: <last_claim>.
        An unresolved question remains: <unresolved_question>.
        The tension point was: <tension_point>.

    Only lines whose values are non-empty are included.  Returns an **empty
    string** when the context carries no meaningful content (e.g. first
    session with no prior memory), so that callers can transparently fall
    back to the default topic-seed behaviour.

    Args:
        context: Dict produced by :func:`extract_continuation_context`.

    Returns:
        Formatted continuation prompt string, or ``""`` if context is empty.
    """
    context_lines: List[str] = []

    if context.get("dominant_topic"):
        context_lines.append(
            f"The previous discussion focused on: {context['dominant_topic']}."
        )
    if context.get("last_claim"):
        context_lines.append(f"The last claim made was: {context['last_claim']}.")
    if context.get("unresolved_question"):
        context_lines.append(
            f"An unresolved question remains: {context['unresolved_question']}."
        )
    if context.get("tension_point"):
        context_lines.append(f"The tension point was: {context['tension_point']}.")

    if not context_lines:
        return ""

    return _CONTINUATION_INSTRUCTION + "\n\n" + "\n".join(context_lines)


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
        "constructive_disagree": (
            "TOPIC: {topic}\n"
            "DISAGREE constructively:\n"
            "1. Identify the main claim in the previous turn.\n"
            "2. Question an assumption, definition, or implication of that claim.\n"
            "3. Offer an alternative interpretation or counter-argument.\n"
            "4. Maintain a respectful philosophical tone."
        ),
        "explore_implication": "TOPIC: {topic}\nEXPLORE consequences. Where does this line of thinking lead?",
        "introduce_analogy": "TOPIC: {topic}\nCONNECT via analogy. How is this like something else?",
        "meta_reflect": "TOPIC: {topic}\nREFLECT on our dialogue. What are we learning? Where are we stuck?",
    }

    def generate_seed(
        self,
        topic: str,
        recent_turns: List[Dict[str, str]],
        speaker: Any,  # Agent type
        turn_count: int,
        agent_mode: Optional[str] = None,
        fixy_guidance: "Optional[FixyGuidance]" = None,
    ) -> str:
        """
        Generate contextual seed based on dialogue state.

        v2.9.0: *agent_mode* (one of AgentMode constants) appends a targeted
        instruction so that the agent responds in a specific way when a loop
        failure mode is active.  When ``AgentMode.NORMAL`` or ``None``, the
        seed is generated as before.

        v5.1.0: *fixy_guidance* (optional :class:`FixyGuidance`) probabilistically
        biases strategy selection toward the Fixy-recommended move type.

        v5.2.0: Dynamic continuation context.  When *recent_turns* contains
        real speaker turns the static ``TOPIC: {topic}`` header is replaced by
        a continuation prompt built from
        :func:`extract_continuation_context` / :func:`build_continuation_prompt`.
        On the **first session with no memory** (no real speaker turns), the
        function falls back to the original ``TOPIC: {topic}`` header so the
        conversation is still anchored to the configured seed topic.

        Args:
            topic: Current topic label
            recent_turns: Recent dialogue turns
            speaker: Current speaker agent
            turn_count: Current turn number
            agent_mode: Optional AgentMode override injected when loop is active
            fixy_guidance: Optional Fixy guidance to bias strategy weights

        Returns:
            Formatted seed instruction
        """
        if not recent_turns:
            base = self.SEED_TEMPLATES["constructive_disagree"].format(topic=topic)
        else:
            # Get last emotion if available
            last_turn = recent_turns[-1]
            last_emotion = last_turn.get("emotion", "neutral")

            # Get conflict level
            try:
                conflict_level = speaker.conflict_index()
            except Exception:
                conflict_level = 5.0

            # Select strategy based on dialogue state
            strategy = self._select_strategy(
                turn_count, conflict_level, last_emotion, fixy_guidance=fixy_guidance
            )

            # Format seed
            template = self.SEED_TEMPLATES.get(
                strategy, self.SEED_TEMPLATES["constructive_disagree"]
            )
            base = template.format(topic=topic)

        # ── Dynamic continuation context ─────────────────────────────────────
        # When the dialogue contains real speaker turns, replace the static
        # "TOPIC: {topic}" header with a continuation prompt derived from
        # the actual conversation.  On the very first session (no real turns
        # yet), extract_continuation_context returns empty strings for
        # last_claim / unresolved_question / tension_point, causing
        # build_continuation_prompt to return "" — we then fall back to the
        # original TOPIC-prefix behaviour so the first turn is still anchored
        # to the configured seed topic (first-session / no-memory path).
        real_turns = [
            t for t in recent_turns
            if t.get("role") != "seed" and t.get("text", "").strip()
        ]
        if real_turns:
            ctx = extract_continuation_context(recent_turns, topic)
            continuation_prefix = build_continuation_prompt(ctx)
        else:
            continuation_prefix = ""

        if continuation_prefix:
            # Extract the strategy instruction (text after the first newline)
            # and pair it with the dynamic continuation header.
            nl_pos = base.find("\n")
            strategy_instruction = base[nl_pos + 1:] if nl_pos >= 0 else base
            base = continuation_prefix + "\n\n" + strategy_instruction
        elif not topic:
            # Legacy path: topic subsystem disabled and no continuation
            # context — strip the empty "TOPIC: \n" header.
            base = base.removeprefix(_SEED_TOPIC_PREFIX)
        # else: first session with a topic — keep the original
        # "TOPIC: {topic}\n<strategy>" base unchanged.

        # Append mode-specific instruction when a loop is active
        mode_instruction = ""
        if agent_mode and agent_mode != AgentMode.NORMAL:
            mode_instruction = _AGENT_MODE_INSTRUCTION.get(agent_mode, "")

        # Append guidance content hint when Fixy has issued guidance
        guidance_hint = ""
        if fixy_guidance is not None:
            from entelgia.fixy_interactive import build_guidance_prompt_hint

            raw_hint = build_guidance_prompt_hint(fixy_guidance)
            if raw_hint:
                guidance_hint = "\n[GUIDANCE HINT] " + raw_hint

        seed_text = base + mode_instruction + guidance_hint
        logger.debug(
            "SeedGenerator.generate_seed: topic=%r agent_mode=%r"
            " guidance_move=%r guidance_hint=%r seed_text=%r",
            topic,
            agent_mode,
            fixy_guidance.preferred_move if fixy_guidance else None,
            guidance_hint or None,
            seed_text,
        )
        return seed_text

    def _select_strategy(
        self,
        turn_count: int,
        conflict_level: float,
        last_emotion: str,
        fixy_guidance: "Optional[FixyGuidance]" = None,
    ) -> str:
        """
        Select seed strategy based on dialogue state.

        v5.1.0: *fixy_guidance* (optional :class:`FixyGuidance` from
        ``InteractiveFixy``) probabilistically biases the strategy weights
        toward the preferred move type when Fixy has detected an issue.  The
        selection is **never forced** — guidance only adjusts weights.

        Args:
            turn_count: Current turn number
            conflict_level: Speaker's conflict index
            last_emotion: Emotion from last turn
            fixy_guidance: Optional guidance from Fixy to bias strategy selection

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
            "meta_reflect": 0.05,
        }

        # ── Apply Fixy guidance bias ──────────────────────────────────────
        # When Fixy has issued guidance, shift probability mass toward
        # strategies that produce the recommended move type.  The bias
        # magnitude scales with guidance.confidence.  No strategy weight
        # is forced to zero — this is purely additive/subtractive.
        if fixy_guidance is not None:
            c = fixy_guidance.confidence
            pm = fixy_guidance.preferred_move

            # Map preferred_move → strategies to boost / suppress
            _BOOST: Dict[str, List[str]] = {
                "TEST": ["explore_implication", "question_assumption"],
                "EXAMPLE": ["introduce_analogy"],
                "CONCESSION": ["agree_and_expand", "synthesize"],
                "NEW_FRAME": ["meta_reflect", "explore_implication"],
                "NEW_CLAIM": ["constructive_disagree", "question_assumption"],
                "DIRECT_ATTACK": ["constructive_disagree"],
            }
            _SUPPRESS: Dict[str, List[str]] = {
                "TEST": ["agree_and_expand"],
                "EXAMPLE": ["agree_and_expand"],
                "CONCESSION": ["constructive_disagree"],
                "NEW_FRAME": ["agree_and_expand"],
                "NEW_CLAIM": ["agree_and_expand", "synthesize"],
                "DIRECT_ATTACK": ["agree_and_expand", "synthesize"],
            }

            for strategy in _BOOST.get(pm, []):
                if strategy in weights:
                    weights[strategy] += _GUIDANCE_BOOST * c

            for strategy in _SUPPRESS.get(pm, []):
                if strategy in weights:
                    weights[strategy] = max(
                        _GUIDANCE_MIN_WEIGHT, weights[strategy] - _GUIDANCE_SUPPRESS
                    )

            logger.debug(
                "[ENGINE-GUIDANCE] biased weights for preferred_move=%r confidence=%.2f",
                pm,
                c,
            )

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
        fixy_probability: float = 0.0,
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
                last_speaker = (
                    dialog_history[-1].get("role", "") if dialog_history else ""
                )
                if last_speaker == "Fixy":
                    # Force non-Fixy speaker to prevent two consecutive Fixy turns
                    candidates = [a for a in agents if a.name != "Fixy"]
                    return self._select_by_engagement(candidates, dialog_history)
                return fixy

        # Calculate engagement scores for each agent
        candidates = [
            a for a in agents if a.name != current_speaker.name and a.name != "Fixy"
        ]

        if not candidates:
            # No other candidates, return different agent or current
            return next(
                (a for a in agents if a.name != current_speaker.name), current_speaker
            )

        # Select based on engagement
        return self._select_by_engagement(candidates, dialog_history)

    def _select_by_engagement(
        self, candidates: List[Any], dialog_history: List[Dict[str, str]]
    ) -> Any:
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
        recent_turns = (
            dialog_history[-10:] if len(dialog_history) >= 10 else dialog_history
        )
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
        turn_count: int,
        agent_mode: Optional[str] = None,
        fixy_guidance: "Optional[FixyGuidance]" = None,
    ) -> str:
        """
        Generate contextual seed for speaker.

        v2.9.0: *agent_mode* is forwarded to ``SeedGenerator.generate_seed``
        so that loop-aware mode instructions are embedded in the seed.

        v5.1.0: *fixy_guidance* is forwarded to probabilistically bias
        strategy weights toward the Fixy-recommended move type.

        v5.2.0: Dynamic continuation context is derived from *dialog_history*
        and injected in place of the static topic header when real speaker
        turns are present.  Falls back to the default topic seed on the first
        session when no memory exists yet.

        Args:
            topic: Current topic
            dialog_history: Recent dialogue
            speaker: Current speaker
            turn_count: Turn number
            agent_mode: Optional AgentMode constant (injected when loop active)
            fixy_guidance: Optional Fixy guidance to bias strategy weights

        Returns:
            Seed instruction string
        """
        recent_turns = (
            dialog_history[-5:] if len(dialog_history) >= 5 else dialog_history
        )
        return self.seed_generator.generate_seed(
            topic,
            recent_turns,
            speaker,
            turn_count,
            agent_mode=agent_mode,
            fixy_guidance=fixy_guidance,
        )

    def should_allow_fixy(
        self, dialog_history: List[Dict[str, str]], turn_count: int
    ) -> Tuple[bool, float, Optional[str]]:
        # Don't allow Fixy too early
        if turn_count < 3:
            return False, 0.0, None

        # Base probability
        probability = 0.40

        # Increase if repetition detected
        if len(dialog_history) >= 5:
            last_5_texts = [
                turn.get("text", "")[:100].lower() for turn in dialog_history[-5:]
            ]
            if self._detect_repetition_simple(last_5_texts):
                probability = 0.80

        # Detect if a specific agent is repeating themselves
        repeating_agent = self._detect_repeating_agent(dialog_history)
        if repeating_agent:
            return True, 0.90, repeating_agent

        return True, probability, None

    def _detect_repeating_agent(
        self, dialog_history: List[Dict[str, str]]
    ) -> Optional[str]:
        """
        Detect if a specific agent is repeating the same words in their last 3 turns.

        Args:
            dialog_history: Full dialogue history

        Returns:
            Name of the repeating agent, or None if no repetition detected
        """
        if len(dialog_history) < 6:
            return None

        # Gather unique non-Fixy agent names
        agent_names = list(
            {
                turn.get("role", "")
                for turn in dialog_history
                if turn.get("role") != "Fixy"
            }
        )

        for agent_name in agent_names:
            agent_turns = [t for t in dialog_history if t.get("role") == agent_name]
            if len(agent_turns) < 3:
                continue
            last_3 = agent_turns[-3:]

            # Extract keywords (words >4 chars) from each of the last 3 turns
            turn_words = []
            for turn in last_3:
                text = turn.get("text", "").lower()
                words = set(w for w in text.split() if len(w) > 4)
                turn_words.append(words)

            # Count pairs with high word overlap
            overlaps = 0
            for i in range(len(turn_words) - 1):
                for j in range(i + 1, len(turn_words)):
                    if len(turn_words[i]) > 0 and len(turn_words[j]) > 0:
                        overlap = len(turn_words[i] & turn_words[j]) / max(
                            len(turn_words[i]), len(turn_words[j])
                        )
                        if overlap > 0.5:
                            overlaps += 1

            # At least 2 of the 3 possible pairs must overlap to flag repetition
            if overlaps >= 2:
                return agent_name

        return None

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
                    overlap = len(all_words[i] & all_words[j]) / max(
                        len(all_words[i]), len(all_words[j])
                    )
                    if overlap > 0.6:
                        overlaps += 1

        return overlaps >= 2

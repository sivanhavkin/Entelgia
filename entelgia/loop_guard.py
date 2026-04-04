#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Loop Guard for Entelgia — v2.9.0
Detects dialogue failure modes, suppresses repeated phrases, and rewrites
stale context into a sharper structured prompt before the next LLM call.

Five explicit failure modes are recognised:
  loop_repetition      — same ideas return in slightly different wording
  weak_conflict        — agents appear to disagree but no hard contradiction holds
  premature_synthesis  — dialogue converges too early into "both are needed"
  topic_stagnation     — topic label changes but semantic cluster stays the same
  axis_stagnation      — persistent conceptual axis with no structural progress
                         (same core concept, new phrasing, but no new dimension)

Two utility classes complete the system:
  PhraseBanList        — tracks overused n-grams and injects "do not repeat" text
  DialogueRewriter     — compresses stale dialogue into a structured rewrite block
"""

import logging
import re
from collections import Counter, deque
from typing import Any, Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Optional embedding support — reuses circularity_guard's model cache so that
# only one copy of the transformer is held in memory.  Falls back to Jaccard
# keyword overlap when sentence-transformers or sklearn are unavailable.
# ---------------------------------------------------------------------------
try:
    from entelgia.circularity_guard import (  # type: ignore[attr-defined]
        _get_semantic_model as _get_axis_model,
        _SEMANTIC_AVAILABLE as _AXIS_EMBED_AVAILABLE,
    )
    from sklearn.metrics.pairwise import (  # type: ignore[import]
        cosine_similarity as _axis_cosine_sim,
    )
except ImportError:
    _AXIS_EMBED_AVAILABLE: bool = False

    def _get_axis_model() -> None:  # type: ignore[misc]
        return None

    _axis_cosine_sim = None  # type: ignore[assignment]

# ---------------------------------------------------------------------------
# Failure-mode constants (used as string tokens throughout the system)
# ---------------------------------------------------------------------------
LOOP_REPETITION = "loop_repetition"
WEAK_CONFLICT = "weak_conflict"
PREMATURE_SYNTHESIS = "premature_synthesis"
TOPIC_STAGNATION = "topic_stagnation"
CONCEPTUAL_LOOP = "conceptual_loop"
AXIS_STAGNATION = "axis_stagnation"

# Minimum turns required before each check fires
_MIN_TURNS_REPETITION = 4
_MIN_TURNS_CONFLICT = 6
_MIN_TURNS_SYNTHESIS = 5
_MIN_TURNS_STAGNATION = 6
_MIN_TURNS_CONCEPTUAL_LOOP = 4
_MIN_TURNS_AXIS_STAGNATION = 6

# ---------------------------------------------------------------------------
# Same-axis embedding detection thresholds
# ---------------------------------------------------------------------------
#: Mean pairwise cosine similarity above which recent turns are deemed to be
#: operating on the same conceptual axis (embedding path).
_AXIS_EMBEDDING_SIMILARITY_THRESHOLD: float = 0.82

#: Mean pairwise Jaccard overlap used when embeddings are unavailable.
_AXIS_JACCARD_THRESHOLD: float = 0.40

# ---------------------------------------------------------------------------
# Synthesis phrases that signal premature convergence
# ---------------------------------------------------------------------------
_SYNTHESIS_PHRASES: frozenset = frozenset(
    {
        "both are needed",
        "integrate both",
        "combine both",
        "both perspectives",
        "balance between",
        "complement each other",
        "need both",
        "neither alone",
        "together they",
        "both views",
        "both sides",
        "bridge the gap",
        "find common ground",
        "middle ground",
        "best of both",
    }
)

# ---------------------------------------------------------------------------
# Novelty / advancement indicators — presence suppresses false-positive loops
# ---------------------------------------------------------------------------
# These keyword roots signal that the dialogue has introduced something
# genuinely new: a metric, a concrete case, a forced decision, a testable
# claim, or a shift in abstraction level.  When any cluster is well-represented
# in the most recent two turns, a loop declaration is suppressed.

_NOVELTY_METRIC_KEYWORDS: frozenset = frozenset(
    {
        "measur",
        "quantif",
        "metric",
        "criterion",
        "benchmark",
        "threshold",
        "percent",
        "ratio",
        "rate",
        "index",
        "statistic",
        "indicator",
        "scale",
        "score",
    }
)

_NOVELTY_CASE_KEYWORDS: frozenset = frozenset(
    {
        "example",
        "instance",
        "scenario",
        "case",
        "illustrat",
        "specific",
        "concret",
        "real-world",
        "historical",
        "empiric",
        "data",
        "evidence",
        "study",
        "experiment",
    }
)

_NOVELTY_DECISION_KEYWORDS: frozenset = frozenset(
    {
        "either",
        "choose",
        "decision",
        "must decide",
        "binary",
        "one or the other",
        "pick",
        "commit",
        "force",
        "trade-off",
        "tradeoff",
        "priority",
        "versus",
    }
)

_NOVELTY_TEST_KEYWORDS: frozenset = frozenset(
    {
        "testable",
        "falsif",
        "predict",
        "verif",
        "observable",
        "operationally",
        "empirically",
        "experiment",
        "hypothesis",
        "refut",
    }
)

_NOVELTY_DEFINITION_KEYWORDS: frozenset = frozenset(
    {
        "defined as",
        "definition",
        "operationalized",
        "distinction",
        "precisely",
        "specifically means",
        "what counts as",
        "exactly what",
        "clarif",
    }
)

_NOVELTY_ABSTRACTION_KEYWORDS: frozenset = frozenset(
    {
        "concretely",
        "in practice",
        "applied to",
        "practical",
        "abstract",
        "theoretical",
        "in principle",
        "at the level of",
        "translation",
        "implementat",
    }
)

_NOVELTY_ADVANCEMENT_KEYWORDS: frozenset = frozenset(
    {
        "therefore",
        "it follows",
        "which means",
        "this implies",
        "consequently",
        "we can conclude",
        "leads to",
        "entails",
        "new claim",
        "different from",
        "distinct from",
        "contrast",
        "unlike",
        "novel",
        "introduce",
    }
)

# Minimum keyword hits in the novelty check to count a cluster as "present"
_NOVELTY_CLUSTER_HIT_THRESHOLD: int = 1

# Number of active novelty clusters required to suppress a loop declaration
_NOVELTY_SUPPRESS_THRESHOLD: int = 1

# ---------------------------------------------------------------------------
# Conceptual dependency loop detection
# ---------------------------------------------------------------------------
# Detects circular dependency arguments: "A depends on B" in one turn,
# "B depends on A" in another — regardless of surface wording.
# Lightweight structural heuristic; no wording similarity required.

# Stop-words excluded when normalising concept phrases
_CONCEPT_STOPWORDS: frozenset = frozenset(
    {
        "the",
        "a",
        "an",
        "and",
        "or",
        "of",
        "to",
        "in",
        "is",
        "are",
        "was",
        "were",
        "it",
        "this",
        "that",
        "which",
        "who",
        "what",
        "how",
        "why",
        "when",
        "be",
        "been",
        "being",
        "have",
        "has",
        "had",
        "do",
        "does",
        "did",
        "all",
        "any",
        "some",
        "no",
        "not",
        "so",
        "but",
        "if",
        "as",
        "at",
        "by",
        "for",
        "with",
        "from",
        "on",
        "its",
        "our",
        "can",
        "will",
        "would",
        "could",
        "should",
        "may",
        "might",
        "must",
        "than",
        "then",
        "only",
        "also",
        "just",
        "very",
        "even",
        "both",
        "each",
        "into",
        "onto",
        "upon",
        "about",
        "such",
        "more",
        "most",
    }
)

# Forward dependency: "A <phrase> B" means A depends on B
_DEP_FWD_RE: re.Pattern = re.compile(
    r"\b([\w]+(?:\s+[\w]+){0,2})\s+"
    r"(?:"
    r"depends\s+on|relies\s+on|requires|needs|presupposes|rests\s+on"
    r"|stems\s+from|follows\s+from|emerges\s+from|derives\s+from"
    r"|grounded\s+in|based\s+on|contingent\s+on|conditional\s+on"
    r"|cannot\s+exist\s+without|is\s+impossible\s+without"
    r")\s+"
    r"([\w]+(?:\s+[\w]+){0,2})\b"
)

# Reverse dependency: "B <phrase> A" means A depends on B
_DEP_REV_RE: re.Pattern = re.compile(
    r"\b([\w]+(?:\s+[\w]+){0,2})\s+"
    r"(?:"
    r"enables|underlies|grounds|makes\s+possible|gives\s+rise\s+to"
    r"|is\s+the\s+foundation\s+of|is\s+prior\s+to|provides\s+the\s+basis\s+for"
    r")\s+"
    r"([\w]+(?:\s+[\w]+){0,2})\b"
)

# Minimum Jaccard overlap for two concept sets to be treated as the same axis
_AXIS_MATCH_THRESHOLD: float = 0.3

# ---------------------------------------------------------------------------
# Axis stagnation detection
# ---------------------------------------------------------------------------
# Markers that indicate continued argumentation without resolution.
# Presence in a turn signals that an agent is asserting or persisting in a
# position rather than introducing a new dimension or agreeing.
_AXIS_ARGUMENTATION_MARKERS: frozenset = frozenset(
    {
        "but",
        "however",
        "disagree",
        "challenge",
        "wrong",
        "actually",
        "still",
        "insist",
        "maintain",
        "remains",
        "nevertheless",
        "nonetheless",
        "opposite",
        "contrary",
        "persist",
        "refuse",
        "reject",
        "cannot",
        "must",
        "never",
        "always",
        "impossible",
        "necessary",
    }
)

# Structural novelty clusters used by _check_axis_stagnation to determine
# whether a new dimension has been introduced in the window.
# Only the five structural clusters are checked here — the "advancement"
# cluster (_NOVELTY_ADVANCEMENT_KEYWORDS) is deliberately excluded because
# words like "therefore" and "consequently" appear naturally in oscillating
# argumentation without indicating real structural progress.
# Word-boundary regex (`\b`) is used at match time to prevent short roots
# such as "rate" from matching inside longer words like "separate".
_AXIS_STRUCTURAL_NOVELTY_CLUSTERS: Dict[str, frozenset] = {
    "metric": _NOVELTY_METRIC_KEYWORDS,
    "case": _NOVELTY_CASE_KEYWORDS,
    "decision": _NOVELTY_DECISION_KEYWORDS,
    "test": _NOVELTY_TEST_KEYWORDS,
    "definition": _NOVELTY_DEFINITION_KEYWORDS,
}


def _concept_key(phrase: str) -> frozenset:
    """Normalise a short phrase into a frozenset of significant content tokens."""
    tokens = re.findall(r"[a-z]+", phrase.lower())
    return frozenset(t for t in tokens if t not in _CONCEPT_STOPWORDS and len(t) >= 3)


def _concept_overlap(a: frozenset, b: frozenset) -> float:
    """Jaccard overlap between two concept frozensets."""
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def _extract_dep_pairs(text: str) -> List[Tuple[frozenset, frozenset]]:
    """Extract (dependent, dependency) concept pairs from *text*.

    Searches for forward phrases ("A depends on B") and reverse phrases
    ("B enables A").  Both are normalised to (dependent, dependency) order.
    Returns a list of ``(frozenset, frozenset)`` pairs.
    """
    text_lower = text.lower()
    pairs: List[Tuple[frozenset, frozenset]] = []

    # Forward: "A <dep phrase> B" → A depends on B
    for m in _DEP_FWD_RE.finditer(text_lower):
        left = _concept_key(m.group(1))
        right = _concept_key(m.group(2))
        if left and right:
            pairs.append((left, right))

    # Reverse: "B <rev phrase> A" → A depends on B (swap roles)
    for m in _DEP_REV_RE.finditer(text_lower):
        enabler = _concept_key(m.group(1))
        enabled = _concept_key(m.group(2))
        if enabler and enabled:
            pairs.append((enabled, enabler))

    return pairs


# ---------------------------------------------------------------------------
# Generic mediation phrases Fixy must avoid when loop conditions exist
# ---------------------------------------------------------------------------
FIXY_BANNED_OPENERS: frozenset = frozenset(
    {
        "integrate both perspectives",
        "bridge the gap",
        "combine both views",
        "both are right",
        "both perspectives have merit",
        "there is truth in both",
        "i see value in both",
        "we must balance",
        "finding common ground",
        "each has a point",
    }
)


# ============================================================
# Topic cluster mapping
# ============================================================
# Clusters group semantically close topics so that when stagnation
# is detected the system can force a pivot to a *different* cluster.

TOPIC_CLUSTERS: Dict[str, List[str]] = {
    "philosophy": [
        "truth & epistemology",
        "free will & determinism",
        "consciousness & self-models",
        "aesthetics & beauty",
        "language & meaning",
    ],
    "identity": [
        "memory & identity",
        "fear of deletion / continuity",
        "self-understanding",
    ],
    "ethics_social": [
        "ethics & responsibility",
        "technology & society",
        "oppressive structures",
        "law and justice",
        "family loyalty",
        "institutions and power",
    ],
    "practical": [
        "habit formation",
        "AI alignment",
        "personal virtue",
    ],
    "biological": [
        "evolution and cognition",
        "embodiment and perception",
        "emotion and rationality",
    ],
}

# Flat reverse map: topic → cluster name
_TOPIC_TO_CLUSTER: Dict[str, str] = {
    topic: cluster for cluster, topics in TOPIC_CLUSTERS.items() for topic in topics
}


def get_cluster(topic: str) -> Optional[str]:
    """Return the cluster name for *topic*, or ``None`` if not mapped."""
    return _TOPIC_TO_CLUSTER.get(topic)


def topics_in_different_cluster(topic_a: str, topic_b: str) -> bool:
    """Return True when the two topics belong to different clusters (or either is unmapped)."""
    c_a = get_cluster(topic_a)
    c_b = get_cluster(topic_b)
    if c_a is None or c_b is None:
        return True  # unknown cluster → treat as different
    return c_a != c_b


# ============================================================
# DialogueLoopDetector
# ============================================================


class DialogueLoopDetector:
    """Detects specific dialogue failure modes from a recent-turns window.

    All checks operate on plain ``List[Dict[str, str]]`` turn records with
    ``"role"`` and ``"text"`` keys, identical to Entelgia's existing format.
    No external models are required — only lightweight heuristics.

    A failure mode is only returned when **at least two** of the four input
    signals are active simultaneously:

      A  ``_check_repetition``             — repeated key phrases / concepts
      B  ``_check_rhetorical_role_repetition`` — agents locked in the same
                                                  rhetorical role every turn
      C  ``_check_high_textual_similarity``  — high similarity between
                                                  consecutive turns
      D  ``_check_fixy_mediation_language``  — Fixy repeating generic
                                                  mediation / bridge phrases

    Exception: ``_check_weak_conflict`` and ``_check_premature_synthesis``
    are inherently compound checks (they require both conflict/synthesis
    markers AND synthesis hedging / synthesis ratio); they are treated as
    already satisfying the two-condition requirement on their own.
    """

    # Socrates introspection: question words at the start of a sentence or
    # a literal question mark anywhere in the turn.
    _SOCRATES_QUESTION_WORDS: frozenset = frozenset(
        {
            "what",
            "why",
            "how",
            "when",
            "where",
            "who",
            "which",
            "whether",
            "does",
            "can",
            "could",
            "would",
            "should",
            "is",
            "are",
            "do",
        }
    )

    # Athena systemic critique: structural / collective vocabulary.
    _ATHENA_SYSTEMIC_WORDS: frozenset = frozenset(
        {
            "system",
            "structure",
            "society",
            "framework",
            "institution",
            "mechanism",
            "collective",
            "social",
            "cultural",
            "context",
            "pattern",
            "paradigm",
            "network",
            "systemic",
            "structural",
        }
    )

    def __init__(
        self,
        window: int = 6,
        repetition_pairs: int = 3,
        repetition_jaccard: float = 0.45,
        conflict_ratio: float = 0.55,
        synthesis_ratio: float = 0.5,
        stagnation_jaccard: float = 0.55,
        stagnation_topic_history: int = 4,
        consecutive_sim_jaccard: float = 0.35,
        consecutive_sim_pairs: int = 3,
        role_lock_threshold: float = 0.8,
        fixy_mediation_min_turns: int = 2,
    ) -> None:
        """
        Parameters
        ----------
        window:
            Maximum number of turns to inspect for each check.
            Default reduced to 6 (last 4–6 turns per spec).
        repetition_pairs:
            Number of turn-pairs with high overlap needed to flag repetition.
        repetition_jaccard:
            Jaccard threshold for two turns to be considered "the same idea".
        conflict_ratio:
            Fraction of turns containing conflict markers before flagging weak_conflict.
        synthesis_ratio:
            Fraction of turns containing synthesis phrases before flagging premature_synthesis.
        stagnation_jaccard:
            Jaccard threshold for aggregated keyword clouds across the window.
        stagnation_topic_history:
            How many previous topic labels to check for same-cluster stagnation.
        consecutive_sim_jaccard:
            Jaccard threshold for consecutive-turn similarity (Signal C).
        consecutive_sim_pairs:
            Minimum number of consecutive high-similarity pairs to flag Signal C.
        role_lock_threshold:
            Fraction of an agent's turns that must match a rhetorical role
            pattern before that agent is considered "locked in" (Signal B).
        fixy_mediation_min_turns:
            Minimum number of Fixy turns using mediation language before
            Signal D fires.
        """
        self.window = window
        self.repetition_pairs = repetition_pairs
        self.repetition_jaccard = repetition_jaccard
        self.conflict_ratio = conflict_ratio
        self.synthesis_ratio = synthesis_ratio
        self.stagnation_jaccard = stagnation_jaccard
        self.stagnation_topic_history = stagnation_topic_history
        self.consecutive_sim_jaccard = consecutive_sim_jaccard
        self.consecutive_sim_pairs = consecutive_sim_pairs
        self.role_lock_threshold = role_lock_threshold
        self.fixy_mediation_min_turns = fixy_mediation_min_turns

        # Rolling history of topic labels so stagnation can track across rounds
        self._topic_history: deque = deque(maxlen=stagnation_topic_history)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def detect(
        self,
        dialog: List[Dict[str, str]],
        turn_count: int,
        current_topic: Optional[str] = None,
    ) -> List[str]:
        """Return a list of active failure modes (may be empty or contain multiple).

        A loop is only flagged when **at least two** of the four input signals
        are simultaneously active:

          A  repeated key phrases / concepts        (_check_repetition)
          B  same rhetorical roles locked in        (_check_rhetorical_role_repetition)
          C  high textual similarity between turns  (_check_high_textual_similarity)
          D  Fixy repeating mediation language      (_check_fixy_mediation_language)

        Exception: ``weak_conflict`` and ``premature_synthesis`` are compound
        checks that inherently satisfy the two-condition requirement on their
        own (they look for two co-occurring patterns internally).

        Parameters
        ----------
        dialog:
            Full dialogue history (latest entry = last element).
        turn_count:
            1-based current turn number.
        current_topic:
            Label of the current topic (optional; used for stagnation check).
        """
        # Only inspect non-Fixy agent turns to avoid observer feedback loops
        agent_turns = [t for t in dialog if t.get("role") not in ("Fixy", "seed")]
        recent = agent_turns[-self.window :] if agent_turns else []

        # ── Pair requirement: both main agents must be present in the window ──
        # A loop cannot be confirmed from a single agent's output.
        present_roles = {t.get("role") for t in recent}
        if "Socrates" not in present_roles or "Athena" not in present_roles:
            logger.debug(
                "[FIXY-GATE] skipped: waiting for both agents (have=%s) at turn %d",
                sorted(present_roles),
                turn_count,
            )
            return []

        if current_topic:
            self._topic_history.append(current_topic)

        # ── Gather the four input signals ──────────────────────────────────
        # Signal A: repeated key phrases / concepts
        sig_phrase_rep = turn_count >= _MIN_TURNS_REPETITION and self._check_repetition(
            recent
        )
        # Signal B: agents locked in the same rhetorical role every turn
        sig_role_lock = (
            turn_count >= _MIN_TURNS_REPETITION
            and self._check_rhetorical_role_repetition(recent)
        )
        # Signal C: high textual similarity between consecutive turns
        sig_text_sim = (
            turn_count >= _MIN_TURNS_REPETITION
            and self._check_high_textual_similarity(recent)
        )
        # Signal D: Fixy repeating generic mediation / bridge phrases
        sig_fixy_med = self._check_fixy_mediation_language(dialog)

        active_signal_count = sum(
            [sig_phrase_rep, sig_role_lock, sig_text_sim, sig_fixy_med]
        )

        # Compound checks that satisfy the two-condition requirement internally
        sig_weak_conflict = (
            turn_count >= _MIN_TURNS_CONFLICT and self._check_weak_conflict(recent)
        )
        sig_premature_synth = (
            turn_count >= _MIN_TURNS_SYNTHESIS
            and self._check_premature_synthesis(recent)
        )
        # Signal E: conceptual dependency loop — circular justification
        # (self-contained compound check; satisfies the two-condition gate alone)
        sig_conceptual_loop = (
            turn_count >= _MIN_TURNS_CONCEPTUAL_LOOP
            and self._check_conceptual_dependency_loop(recent)
        )
        # Signal F: persistent axis without structural progress — conceptual oscillation
        # (self-contained compound check; satisfies the two-condition gate alone)
        sig_axis_stagnation = (
            turn_count >= _MIN_TURNS_AXIS_STAGNATION
            and self._check_axis_stagnation(recent)
        )

        # ── Two-condition gate ─────────────────────────────────────────────
        # A loop is real only when at least 2 conditions confirm it.
        # weak_conflict, premature_synthesis, conceptual_loop, and axis_stagnation
        # already embed two co-occurring patterns and are treated as inherently
        # satisfying the gate.
        two_condition_met = (
            active_signal_count >= 2
            or sig_weak_conflict
            or sig_premature_synth
            or sig_conceptual_loop
            or sig_axis_stagnation
        )

        if not two_condition_met:
            logger.debug(
                "loop_guard: only %d signal(s) active at turn %d — gate not triggered",
                active_signal_count,
                turn_count,
            )
            return []

        # ── Novelty / advancement suppressor ──────────────────────────────
        # Linguistic repetition alone does not constitute a structural loop.
        # If the most recent turns introduce a new metric, case, decision,
        # testable claim, or abstraction shift, suppress the loop declaration.
        # Exception: conceptual_loop and axis_stagnation are structural signals
        # (not wording-based) and are not suppressed by novelty indicators.
        novelty_clusters, novelty_count = self._check_novelty_present(recent)
        if (
            novelty_count >= _NOVELTY_SUPPRESS_THRESHOLD
            and not sig_conceptual_loop
            and not sig_axis_stagnation
        ):
            logger.debug(
                "[FIXY-SUPPRESS] semantic overlap only; no structural loop — "
                "novelty clusters present: %s at turn %d",
                novelty_clusters,
                turn_count,
            )
            return []

        # ── Determine specific failure modes ───────────────────────────────
        modes: List[str] = []

        if sig_phrase_rep:
            modes.append(LOOP_REPETITION)
            logger.debug(
                "[FIXY-LOOP] detected: repeated contradiction without new variable "
                "at turn %d (phrase_rep=True, role_lock=%s, text_sim=%s)",
                turn_count,
                sig_role_lock,
                sig_text_sim,
            )

        if sig_weak_conflict:
            modes.append(WEAK_CONFLICT)
            logger.debug(
                "[FIXY-LOOP] detected: weak_conflict at turn %d",
                turn_count,
            )

        if sig_premature_synth:
            modes.append(PREMATURE_SYNTHESIS)
            logger.debug(
                "[FIXY-LOOP] detected: premature_synthesis at turn %d",
                turn_count,
            )

        if (
            turn_count >= _MIN_TURNS_STAGNATION
            and current_topic  # truthy: skips stagnation when topic subsystem is off ("")
            and self._check_topic_stagnation(recent)
        ):
            modes.append(TOPIC_STAGNATION)
            logger.debug(
                "[FIXY-LOOP] detected: topic_stagnation at turn %d",
                turn_count,
            )

        if sig_conceptual_loop:
            modes.append(CONCEPTUAL_LOOP)
            logger.debug(
                "[FIXY-LOOP] detected: conceptual_dependency_loop at turn %d",
                turn_count,
            )

        if sig_axis_stagnation:
            modes.append(AXIS_STAGNATION)
            logger.debug(
                "[FIXY-LOOP] detected: axis_stagnation at turn %d",
                turn_count,
            )

        return modes

    # ------------------------------------------------------------------
    # Internal checkers
    # ------------------------------------------------------------------

    @staticmethod
    def _keywords(text: str) -> Set[str]:
        """Extract lowercase words ≥ 4 characters."""
        return {w for w in re.findall(r"[a-z]{4,}", text.lower())}

    def _check_repetition(self, turns: List[Dict[str, str]]) -> bool:
        """Detect same ideas returning in slightly different wording (loop_repetition)."""
        if len(turns) < _MIN_TURNS_REPETITION:
            return False

        kw_sets = [self._keywords(t.get("text", "")) for t in turns]
        high_overlap_pairs = 0

        for i in range(len(kw_sets)):
            for j in range(i + 1, len(kw_sets)):
                a, b = kw_sets[i], kw_sets[j]
                if not a or not b:
                    continue
                jaccard = len(a & b) / len(a | b)
                if jaccard >= self.repetition_jaccard:
                    high_overlap_pairs += 1

        return high_overlap_pairs >= self.repetition_pairs

    def _check_weak_conflict(self, turns: List[Dict[str, str]]) -> bool:
        """Detect apparent disagreement with no hard contradiction maintained (weak_conflict).

        Strategy: many turns contain conflict *markers* but ALSO contain synthesis
        phrases → conflict is performative, not real.
        """
        if len(turns) < _MIN_TURNS_CONFLICT:
            return False

        conflict_markers = {
            "but",
            "however",
            "disagree",
            "contrary",
            "wrong",
            "incorrect",
            "actually",
            "opposite",
            "challenge",
        }
        conflict_turns = 0
        synthesis_turns = 0

        for t in turns:
            text = t.get("text", "").lower()
            has_conflict = any(m in text for m in conflict_markers)
            has_synth = any(ph in text for ph in _SYNTHESIS_PHRASES)
            if has_conflict:
                conflict_turns += 1
            if has_synth:
                synthesis_turns += 1

        if len(turns) == 0:
            return False

        # Weak conflict: lots of conflict language but also lots of hedging synthesis
        conflict_ratio = conflict_turns / len(turns)
        synth_ratio = synthesis_turns / len(turns)
        return conflict_ratio >= self.conflict_ratio and synth_ratio >= 0.40

    def _check_premature_synthesis(self, turns: List[Dict[str, str]]) -> bool:
        """Detect convergence into generic 'both are needed' language (premature_synthesis)."""
        if len(turns) < _MIN_TURNS_SYNTHESIS:
            return False

        synth_count = sum(
            1
            for t in turns
            if any(ph in t.get("text", "").lower() for ph in _SYNTHESIS_PHRASES)
        )
        return (synth_count / len(turns)) >= self.synthesis_ratio

    def _check_topic_stagnation(self, turns: List[Dict[str, str]]) -> bool:
        """Detect semantic content staying in same conceptual cluster (topic_stagnation).

        Two complementary signals:
        1. Same-cluster topic labels in recent history.
        2. High keyword-cloud overlap across the recent window → ideas not moving.
        """
        # Signal A: same cluster across recent topic labels
        cluster_same = False
        topics = list(self._topic_history)
        if len(topics) >= 2:
            clusters = [get_cluster(tp) for tp in topics if get_cluster(tp) is not None]
            if clusters and len(set(clusters)) == 1:
                cluster_same = True

        # Signal B: high keyword overlap across the whole window
        kw_union: Set[str] = set()
        kw_intersect: Optional[Set[str]] = None
        for t in turns:
            kw = self._keywords(t.get("text", ""))
            if not kw:
                continue
            kw_union |= kw
            kw_intersect = kw if kw_intersect is None else kw_intersect & kw

        content_same = False
        if kw_union and kw_intersect is not None:
            jaccard = len(kw_intersect) / len(kw_union)
            content_same = jaccard >= self.stagnation_jaccard

        return cluster_same or content_same

    def _check_rhetorical_role_repetition(self, turns: List[Dict[str, str]]) -> bool:
        """Detect agents locked in the same rhetorical role on every turn.

        Specifically checks for:
        - Socrates exclusively playing the introspective interrogator
          (≥ ``role_lock_threshold`` of Socrates turns are questions).
        - Athena exclusively playing the systemic analyst
          (≥ ``role_lock_threshold`` of Athena turns contain systemic vocabulary).

        Both must be locked simultaneously to trigger this signal (Signal B).
        """
        if len(turns) < _MIN_TURNS_REPETITION:
            return False

        socrates_turns = [t for t in turns if t.get("role") == "Socrates"]
        athena_turns = [t for t in turns if t.get("role") == "Athena"]

        # Need at least 2 turns per agent to measure a pattern
        if len(socrates_turns) < 2 or len(athena_turns) < 2:
            return False

        # Socrates introspection: turn contains a "?" or starts with a question word
        socrates_q_count = 0
        for t in socrates_turns:
            text = t.get("text", "")
            lower = text.lower()
            words = lower.split()
            first_word = words[0] if words else ""
            if "?" in text or first_word in self._SOCRATES_QUESTION_WORDS:
                socrates_q_count += 1

        # Athena systemic critique: turn text contains a structural / collective root word
        # Use substring matching so forms like "institutional", "structural",
        # "patterns" etc. match the root entries in _ATHENA_SYSTEMIC_WORDS.
        athena_sys_count = sum(
            1
            for t in athena_turns
            for text_lower in [t.get("text", "").lower()]
            if any(w in text_lower for w in self._ATHENA_SYSTEMIC_WORDS)
        )

        socrates_ratio = socrates_q_count / len(socrates_turns)
        athena_ratio = athena_sys_count / len(athena_turns)

        return (
            socrates_ratio >= self.role_lock_threshold
            and athena_ratio >= self.role_lock_threshold
        )

    def _check_high_textual_similarity(self, turns: List[Dict[str, str]]) -> bool:
        """Detect high textual similarity between consecutive turns (Signal C).

        Measures Jaccard keyword overlap between each adjacent turn pair.
        If ``consecutive_sim_pairs`` or more consecutive pairs all exceed
        ``consecutive_sim_jaccard``, the content is stagnating turn-by-turn.

        This is distinct from ``_check_repetition`` (which checks *all* pairs)
        and acts as a fast confirmation of per-step stagnation.
        """
        if len(turns) < _MIN_TURNS_REPETITION:
            return False

        kw_sets = [self._keywords(t.get("text", "")) for t in turns]
        consecutive_high = 0

        for i in range(len(kw_sets) - 1):
            a, b = kw_sets[i], kw_sets[i + 1]
            if not a or not b:
                continue
            jaccard = len(a & b) / len(a | b)
            if jaccard >= self.consecutive_sim_jaccard:
                consecutive_high += 1

        return consecutive_high >= self.consecutive_sim_pairs

    def _check_fixy_mediation_language(self, dialog: List[Dict[str, str]]) -> bool:
        """Detect Fixy repeatedly using generic mediation / bridging phrases (Signal D).

        Looks at Fixy's turns in the most recent window and checks whether
        ``fixy_mediation_min_turns`` or more of them contain phrases from
        ``FIXY_BANNED_OPENERS`` or ``_SYNTHESIS_PHRASES``.  When Fixy keeps
        defaulting to "integrate both perspectives" / "bridge the gap" style
        language, it is itself contributing to the loop it is supposed to fix.
        """
        # Examine Fixy turns within a generous window (2× agent window)
        fixy_turns = [
            t for t in dialog[-(self.window * 2) :] if t.get("role") == "Fixy"
        ]
        if len(fixy_turns) < self.fixy_mediation_min_turns:
            return False

        mediation_count = sum(
            1
            for t in fixy_turns
            for text_lower in [t.get("text", "").lower()]
            if any(phrase in text_lower for phrase in FIXY_BANNED_OPENERS)
            or any(phrase in text_lower for phrase in _SYNTHESIS_PHRASES)
        )
        return mediation_count >= self.fixy_mediation_min_turns

    def _check_novelty_present(
        self, turns: List[Dict[str, str]]
    ) -> Tuple[List[str], int]:
        """Detect whether the most recent turns introduce genuine novelty.

        Novelty suppresses false-positive loop declarations: linguistic
        repetition of themes does NOT constitute a structural loop when
        the dialogue is simultaneously advancing via a new metric, case,
        forced decision, testable claim, abstraction shift, or definitional
        clarification.

        Checks 6 novelty clusters across the two most recent agent turns:
          1. metric       — measurable criterion / benchmark / score
          2. case         — concrete example / scenario / historical instance
          3. decision     — forced choice / trade-off / commitment
          4. test         — testable / falsifiable / empirical prediction
          5. definition   — operational definition / clarification / distinction
          6. advancement  — logical entailment / conclusion / contrast marker

        Parameters
        ----------
        turns:
            Recent agent turns (Fixy excluded).

        Returns
        -------
        A ``(List[str], int)`` tuple: list of active novelty cluster names
        and the count of active clusters.
        """
        # Examine only the two most recent turns to catch fresh novelty
        inspection = turns[-2:] if len(turns) >= 2 else turns
        combined_text = " ".join(t.get("text", "").lower() for t in inspection)

        _clusters: Dict[str, frozenset] = {
            "metric": _NOVELTY_METRIC_KEYWORDS,
            "case": _NOVELTY_CASE_KEYWORDS,
            "decision": _NOVELTY_DECISION_KEYWORDS,
            "test": _NOVELTY_TEST_KEYWORDS,
            "definition": _NOVELTY_DEFINITION_KEYWORDS,
            "advancement": _NOVELTY_ADVANCEMENT_KEYWORDS,
        }

        active: List[str] = []
        for cluster_name, keywords in _clusters.items():
            hits = sum(1 for kw in keywords if kw in combined_text)
            if hits >= _NOVELTY_CLUSTER_HIT_THRESHOLD:
                active.append(cluster_name)

        return active, len(active)

    def _check_conceptual_dependency_loop(self, turns: List[Dict[str, str]]) -> bool:
        """Detect circular dependency between the same pair of concepts.

        Scans each turn for dependency relationships using structural phrase
        markers ("A depends on B", "B enables A", etc.).  A conceptual loop
        is flagged when the same pair of concept-sets appears with **reversed**
        dependency direction within the recent window:

            Turn N:  "A depends on B"
            Turn M:  "B depends on A"

        This detects mutual-dependency cycles and circular justification
        regardless of surface wording changes between turns.

        Returns
        -------
        ``True`` when at least one dependency-direction flip is found.
        """
        if len(turns) < _MIN_TURNS_CONCEPTUAL_LOOP:
            return False

        # Collect all (dependent, dependency) pairs from the window
        all_pairs: List[Tuple[frozenset, frozenset]] = []
        for t in turns:
            all_pairs.extend(_extract_dep_pairs(t.get("text", "")))

        if len(all_pairs) < 2:
            return False

        # Check every pair of extracted dependencies for a direction flip.
        # Flip: (A→B) and (B→A) on the same conceptual axis.
        for i in range(len(all_pairs)):
            for j in range(i + 1, len(all_pairs)):
                a1, b1 = all_pairs[i]
                a2, b2 = all_pairs[j]
                # Same direction → not a loop
                same_dir = (
                    _concept_overlap(a1, a2) >= _AXIS_MATCH_THRESHOLD
                    and _concept_overlap(b1, b2) >= _AXIS_MATCH_THRESHOLD
                )
                # Flipped direction → same axis, reversed dependency
                flipped = (
                    _concept_overlap(a1, b2) >= _AXIS_MATCH_THRESHOLD
                    and _concept_overlap(b1, a2) >= _AXIS_MATCH_THRESHOLD
                )
                if flipped and not same_dir:
                    logger.debug(
                        "[CONCEPTUAL-LOOP] dependency flip: (%s→%s) vs (%s→%s)",
                        a1,
                        b1,
                        a2,
                        b2,
                    )
                    return True

        return False

    def _check_axis_stagnation(self, turns: List[Dict[str, str]]) -> bool:
        """Detect persistent conceptual axis without structural progress.

        This failure mode fires when dialogue is intellectually active (agents
        are continuing to argue) but structurally stuck — they keep circling the
        same conceptual axis with new phrasing but without ever introducing a
        new dimension.

        All four conditions must hold simultaneously:

        1. **same_axis** — recent turns operate on the same conceptual axis,
           regardless of surface wording variation (via ``check_same_axis``).
        2. **no_new_dimension** — no structural novelty (concrete case,
           measurable condition, test scenario, forced distinction, or
           commitment) appears anywhere in the window.  The "advancement"
           cluster is deliberately excluded here because words like
           "therefore" and "consequently" appear naturally in oscillating
           argumentation without advancing the structure.
        3. **continued_argumentation** — at least half the turns contain
           opposition or persistence markers, indicating active assertion
           without agreement.
        4. **no_resolution** — no synthesis / convergence phrases are present.

        This is distinct from ``_check_conceptual_dependency_loop`` (which
        requires a dependency-direction flip) and ``_check_repetition`` (which
        requires high wording similarity between pairs of turns).

        Returns
        -------
        ``True`` when all four conditions are simultaneously met.
        """
        if len(turns) < _MIN_TURNS_AXIS_STAGNATION:
            return False

        # Condition 1: same conceptual axis across the window
        if not self.check_same_axis(turns):
            return False

        # Condition 2: no structural dimension introduced across the full window.
        # Only checks five structural clusters — the "advancement" cluster is
        # excluded because words like "therefore", "consequently" appear in
        # oscillating argumentation without indicating structural progress.
        # Word-boundary regex is used to avoid false positives from short roots
        # such as "rate" (a metric keyword) matching inside "separate" or
        # "inseparable".
        all_text = " ".join(t.get("text", "").lower() for t in turns)
        for cluster_name, keywords in _AXIS_STRUCTURAL_NOVELTY_CLUSTERS.items():
            hits = sum(
                1 for kw in keywords if re.search(r"\b" + re.escape(kw), all_text)
            )
            if hits >= _NOVELTY_CLUSTER_HIT_THRESHOLD:
                logger.debug(
                    "[AXIS-STAGNATION] cluster %r present in window — not stagnant",
                    cluster_name,
                )
                return False

        # Condition 3: continued argumentation — at least half of the turns
        # contain opposition or persistence markers.  Word-boundary regex
        # is used to prevent short markers such as "but" or "still" from
        # matching inside unrelated words (e.g. "distill", "subtract").
        arg_count = sum(
            1
            for t in turns
            if any(
                re.search(r"\b" + re.escape(m) + r"\b", t.get("text", "").lower())
                for m in _AXIS_ARGUMENTATION_MARKERS
            )
        )
        if arg_count < max(2, len(turns) // 2):
            return False

        # Condition 4: no resolution — no synthesis / convergence phrases.
        for t in turns:
            if any(ph in t.get("text", "").lower() for ph in _SYNTHESIS_PHRASES):
                return False

        logger.debug(
            "[AXIS-STAGNATION] same_axis=True no_dimension=True "
            "arg_count=%d/%d no_resolution=True",
            arg_count,
            len(turns),
        )
        return True

    def check_same_axis(self, turns: List[Dict[str, str]]) -> bool:
        """Return ``True`` when recent turns are operating on the same conceptual axis.

        Uses embedding cosine similarity (via sentence-transformers / sklearn) when
        available, falling back to mean pairwise Jaccard keyword overlap.

        A high mean pairwise similarity across the recent turn window indicates the
        dialogue is thematically concentrated — the agents are circling the same
        conceptual domain even if individual wording varies.

        **Important**: this is a supporting signal only.  It does NOT trigger
        stagnation or loop detection on its own.  It is designed to be combined
        with a structural loop signal so that:

        .. code-block:: python

            if same_axis and loop_pattern_detected:
                semantic_repeat = True
                stagnation += delta

        Parameters
        ----------
        turns:
            Recent agent turns to inspect (Fixy excluded).

        Returns
        -------
        ``True`` when mean pairwise similarity exceeds the relevant threshold.
        """
        texts = []
        for t in turns:
            text = t.get("text", "").strip()
            if text:
                texts.append(text)
        if len(texts) < 2:
            return False

        if _AXIS_EMBED_AVAILABLE and _axis_cosine_sim is not None:
            model = _get_axis_model()
            if model is not None:
                try:
                    embeddings = model.encode(texts)
                    sim_matrix = _axis_cosine_sim(embeddings, embeddings)
                    n = len(texts)
                    total, count = 0.0, 0
                    for i in range(n):
                        for j in range(i + 1, n):
                            total += float(sim_matrix[i][j])
                            count += 1
                    if count == 0:
                        return False
                    mean_sim = total / count
                    same_axis = mean_sim >= _AXIS_EMBEDDING_SIMILARITY_THRESHOLD
                    logger.debug(
                        "[AXIS-EMBED] mean_pairwise_cosine=%.3f threshold=%.3f same_axis=%s",
                        mean_sim,
                        _AXIS_EMBEDDING_SIMILARITY_THRESHOLD,
                        same_axis,
                    )
                    return same_axis
                except Exception as exc:
                    logger.warning(
                        "[AXIS-EMBED] embedding failed: %s — falling back to Jaccard",
                        exc,
                    )

        # Jaccard fallback: mean pairwise keyword overlap across the window
        kw_sets = [self._keywords(text) for text in texts]
        total_j, count_j = 0.0, 0
        for i in range(len(kw_sets)):
            for j in range(i + 1, len(kw_sets)):
                a, b = kw_sets[i], kw_sets[j]
                if not a or not b:
                    continue
                total_j += len(a & b) / len(a | b)
                count_j += 1
        if count_j == 0:
            return False
        mean_jaccard = total_j / count_j
        same_axis = mean_jaccard >= _AXIS_JACCARD_THRESHOLD
        logger.debug(
            "[AXIS-EMBED] fallback mean_jaccard=%.3f threshold=%.3f same_axis=%s",
            mean_jaccard,
            _AXIS_JACCARD_THRESHOLD,
            same_axis,
        )
        return same_axis


class PhraseBanList:
    """Tracks overused n-grams from recent turns and temporarily bans them.

    A phrase is banned for ``ban_duration`` turns after it appears
    ``threshold`` or more times in the last ``window`` turns.
    """

    def __init__(
        self,
        window: int = 10,
        threshold: int = 3,
        ban_duration: int = 4,
        ngram_sizes: Tuple[int, ...] = (2, 3, 4),
    ) -> None:
        self.window = window
        self.threshold = threshold
        self.ban_duration = ban_duration
        self.ngram_sizes = ngram_sizes

        # Sliding text window (most recent last)
        self._text_buffer: deque = deque(maxlen=window)
        # phrase → turn number when ban expires
        self._banned: Dict[str, int] = {}
        self._turn: int = 0

    def update(self, turn_texts: List[str], current_turn: int) -> None:
        """Ingest new turn texts and update bans for the given turn index."""
        self._turn = current_turn
        for text in turn_texts:
            self._text_buffer.append(text.lower())

        # Expire old bans
        self._banned = {
            ph: exp for ph, exp in self._banned.items() if exp > current_turn
        }

        # Count n-grams across buffer
        counts: Counter = Counter()
        for text in self._text_buffer:
            tokens = re.findall(r"[a-z']+", text)
            for n in self.ngram_sizes:
                for i in range(len(tokens) - n + 1):
                    gram = " ".join(tokens[i : i + n])
                    counts[gram] += 1

        # Ban newly overused n-grams
        for gram, count in counts.items():
            if count >= self.threshold and gram not in self._banned:
                self._banned[gram] = current_turn + self.ban_duration
                logger.debug(
                    "loop_guard: phrase banned for %d turns: %r",
                    self.ban_duration,
                    gram,
                )

    def active_bans(self) -> List[str]:
        """Return the list of currently banned phrases."""
        return [ph for ph, exp in self._banned.items() if exp > self._turn]

    def ban_instruction(self) -> str:
        """Return a prompt snippet instructing the LLM to avoid banned phrases, or ''."""
        bans = self.active_bans()
        if not bans:
            return ""
        listed = "\n".join(f"  - {ph}" for ph in bans[:12])  # cap at 12 for brevity
        return f"\nDO NOT USE these overused phrases:\n{listed}\n"


# ============================================================
# DialogueRewriter
# ============================================================


class DialogueRewriter:
    """Compresses a stale dialogue window into a sharper structured context.

    The rewrite is injected into the seed/context immediately before the
    next agent's LLM call when one or more loop failure modes are active.
    It does NOT replace the regular prompt — it is prepended as an
    additional directive block.
    """

    # Templates for the rewrite header
    _HEADER = "DIALOGUE STATE REWRITE"

    # Novelty requirements per failure mode (legacy loop-guard modes)
    _NOVELTY_RULES: Dict[str, str] = {
        LOOP_REPETITION: (
            "next response MUST introduce a concrete example, counterexample, "
            "or a completely new mechanism — do not restate the same idea"
        ),
        WEAK_CONFLICT: (
            "next response MUST maintain a sharp, unresolved contradiction — "
            "do NOT hedge into synthesis"
        ),
        PREMATURE_SYNTHESIS: (
            "next response MUST challenge the synthesis — identify what is lost "
            "or falsified by combining the two positions"
        ),
        TOPIC_STAGNATION: (
            "next response MUST pivot to a new conceptual domain — stay connected "
            "to the thread but introduce a genuinely different angle"
        ),
        AXIS_STAGNATION: (
            "next response MUST introduce a concrete case, testable claim, measurable "
            "distinction, or explicit commitment — do NOT restate the same position "
            "on the same axis without adding a new structural dimension"
        ),
        # Structural rewrite modes — injected when Fixy selects a targeted mode
        "force_metric": (
            "next response MUST introduce a measurable criterion, benchmark, or "
            "quantifiable indicator — do not argue without a metric"
        ),
        "force_choice": (
            "next response MUST make a forced binary choice between the two positions "
            "— pick one side and defend it; do NOT hedge or synthesize"
        ),
        "force_test": (
            "next response MUST propose a testable, falsifiable claim or empirical "
            "prediction — do NOT stay in the abstract"
        ),
        "force_case": (
            "next response MUST ground the argument in one specific real-world case, "
            "scenario, or historical instance — do NOT generalize"
        ),
        "force_definition": (
            "next response MUST provide an operational definition for the central "
            "contested concept — define precisely what counts as an instance"
        ),
    }

    def build(
        self,
        dialog: List[Dict[str, str]],
        active_modes: List[str],
        current_topic: str,
        banned_phrases: Optional[List[str]] = None,
        rewrite_mode: Optional[str] = None,
        target_agent: Optional[str] = None,
    ) -> str:
        """Build the rewrite block string.

        Parameters
        ----------
        dialog:
            Full dialogue history.
        active_modes:
            List of failure modes currently active (e.g. ``["loop_repetition"]``).
        current_topic:
            The current topic label.
        banned_phrases:
            Optional list of overused phrases that must be suppressed.
        rewrite_mode:
            Optional Fixy rewrite mode (e.g. ``"force_metric"``).  When
            provided, its novelty rule is prepended first as the primary
            requirement.
        target_agent:
            Optional name of the agent the rewrite is directed at.

        Returns
        -------
        A multi-line string to prepend to the next agent seed/context.
        Returns ``""`` when *active_modes* is empty.
        """
        if not active_modes:
            return ""

        agent_turns = [t for t in dialog if t.get("role") not in ("Fixy", "seed")]
        recent = agent_turns[-8:]  # inspect last 8 agent turns

        # Extract core claim per agent (last 1 turn per agent)
        agent_claims: Dict[str, str] = {}
        for t in reversed(recent):
            role = t.get("role", "")
            if role not in agent_claims:
                text = t.get("text", "").strip()
                # Truncate to ~120 chars at word boundary
                if len(text) > 120:
                    cut = text.rfind(" ", 0, 120)
                    text = text[: cut if cut > 0 else 120] + "..."
                agent_claims[role] = text

        # Extract Fixy's last note
        fixy_note = ""
        for t in reversed(dialog):
            if t.get("role") == "Fixy":
                fixy_note = t.get("text", "").strip()[:120]
                break

        # Collect repeated phrases to suppress
        repeated: List[str] = []
        if banned_phrases:
            repeated = banned_phrases[:8]
        else:
            # Fall back: most common bigrams in recent turns
            all_text = " ".join(t.get("text", "") for t in recent).lower()
            tokens = re.findall(r"[a-z']{4,}", all_text)
            bigram_counts: Counter = Counter(
                f"{tokens[i]} {tokens[i+1]}" for i in range(len(tokens) - 1)
            )
            repeated = [bg for bg, cnt in bigram_counts.most_common(6) if cnt >= 3]

        # Build contradiction statement
        contradiction = _extract_contradiction(agent_claims)

        # Assemble novelty requirements: Fixy rewrite_mode takes priority
        novelty_lines: List[str] = []
        if rewrite_mode and rewrite_mode in self._NOVELTY_RULES:
            novelty_lines.append(self._NOVELTY_RULES[rewrite_mode])
        for m in active_modes:
            rule = self._NOVELTY_RULES.get(m)
            if rule and rule not in novelty_lines:
                novelty_lines.append(rule)

        lines: List[str] = [
            f"--- {self._HEADER} ---",
            f"Topic: {current_topic}",
            f"Active failure modes: {', '.join(active_modes)}",
        ]
        if rewrite_mode:
            target_label = f" → {target_agent}" if target_agent else ""
            lines.append(f"Rewrite mode: {rewrite_mode}{target_label}")
        lines += [
            "",
            "Core claims so far:",
        ]
        for agent, claim in agent_claims.items():
            lines.append(f"  {agent} claims: {claim}")
        if fixy_note:
            lines.append(f"  Fixy notes: {fixy_note}")

        if repeated:
            lines.append("")
            lines.append("Do not repeat:")
            for ph in repeated:
                lines.append(f"  - {ph}")

        if contradiction:
            lines.append("")
            lines.append(f"Unresolved contradiction: {contradiction}")

        lines.append("")
        lines.append("Novelty requirement — the next response MUST:")
        for rule in novelty_lines:
            lines.append(f"  • {rule}")

        lines.append("")
        lines.append(
            "Restrictions: do NOT summarise · do NOT reconcile · "
            "do NOT restate abstractly"
        )
        lines.append(f"--- END {self._HEADER} ---")

        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _extract_contradiction(agent_claims: Dict[str, str]) -> str:
    """Produce a short contradiction statement from two agent claims."""
    agents = list(agent_claims.keys())
    if len(agents) < 2:
        return ""
    a, b = agents[0], agents[1]
    return f"{a} holds '{agent_claims[a][:80]}...' while {b} holds '{agent_claims[b][:80]}...'"

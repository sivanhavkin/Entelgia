#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Dialogue Metrics for Entelgia
Three quantitative metrics for measuring dialogue quality and intervention effectiveness.

Metrics
-------
circularity_rate      — Fraction of turn-pairs that share a recurring topic signature.
progress_rate         — Rate of forward steps: topic changes, synthesis markers,
                        and open-question resolutions per turn.
intervention_utility  — Average reduction in circularity in the window following a
                        Fixy intervention compared with the window preceding it.
"""

import re
from typing import Dict, List, Tuple

# ---------------------------------------------------------------------------
# Keyword helpers
# ---------------------------------------------------------------------------

_SYNTHESIS_MARKERS = frozenset(
    [
        "therefore",
        "integrating",
        "combining",
        "synthesis",
        "synthesize",
        "connect",
        "connecting",
        "both",
        "together",
        "unified",
        "merging",
        "bridge",
        "converge",
        "overall",
        "in sum",
        "to sum",
    ]
)

_RESOLUTION_MARKERS = frozenset(
    [
        "answer",
        "resolve",
        "resolved",
        "solution",
        "because",
        "explains",
        "explained",
        "clarifies",
        "hence",
        "thus",
        "so",
    ]
)

_QUESTION_PATTERN = re.compile(r"\?")


def _keywords(text: str) -> frozenset:
    """Return the set of meaningful words (length ≥ 4) from *text* in lower-case."""
    return frozenset(w for w in re.findall(r"\b[a-z]{4,}\b", text.lower()))


def _jaccard(a: frozenset, b: frozenset) -> float:
    """Jaccard similarity between two keyword sets."""
    union = a | b
    if not union:
        return 0.0
    return len(a & b) / len(union)


# ---------------------------------------------------------------------------
# Topic-signature extraction
# ---------------------------------------------------------------------------


def _topic_signature(turn: Dict[str, str]) -> frozenset:
    """Return the keyword fingerprint of a dialogue turn."""
    return _keywords(turn.get("text", ""))


def _circularity_in_window(
    turns: List[Dict[str, str]], threshold: float = 0.5
) -> float:
    """
    Compute the circularity rate for a list of turns.

    A turn-pair is considered *circular* when the Jaccard similarity of their
    keyword sets exceeds *threshold*.

    Returns
    -------
    float
        Fraction of turn-pairs that are circular, in [0, 1].
        Returns 0.0 when there are fewer than two turns.
    """
    if len(turns) < 2:
        return 0.0

    sigs = [_topic_signature(t) for t in turns]
    circular_pairs = 0
    total_pairs = 0

    for i in range(len(sigs)):
        for j in range(i + 1, len(sigs)):
            if sigs[i] or sigs[j]:  # skip pairs with no keywords at all
                total_pairs += 1
                if _jaccard(sigs[i], sigs[j]) >= threshold:
                    circular_pairs += 1

    return circular_pairs / total_pairs if total_pairs > 0 else 0.0


# ---------------------------------------------------------------------------
# Public metric functions
# ---------------------------------------------------------------------------


def circularity_rate(dialog: List[Dict[str, str]], threshold: float = 0.5) -> float:
    """
    Measure the Loop/Circularity Rate of a dialogue.

    Counts the fraction of turn-pairs whose topic signatures (keyword sets)
    overlap by at least *threshold* (Jaccard similarity).  A high value
    indicates the dialogue keeps revisiting the same ground.

    Parameters
    ----------
    dialog:
        Sequence of turn dicts, each with at least a ``"text"`` field.
    threshold:
        Jaccard similarity above which a pair is considered circular.
        Default is 0.5 (50 % keyword overlap).

    Returns
    -------
    float
        Circularity rate in [0, 1].
    """
    return _circularity_in_window(dialog, threshold=threshold)


def circularity_per_turn(
    dialog: List[Dict[str, str]],
    window: int = 6,
    threshold: float = 0.5,
) -> List[float]:
    """
    Return a per-turn circularity time-series.

    For each turn *t*, circularity is computed over the *window* turns
    ending at *t* (inclusive).  Useful for plotting how circularity
    evolves over the course of a dialogue.

    Parameters
    ----------
    dialog:
        Full dialogue history.
    window:
        Number of turns in the rolling window.
    threshold:
        Jaccard similarity threshold for the ``circularity_rate`` metric.

    Returns
    -------
    List[float]
        One value per turn.
    """
    series: List[float] = []
    for i in range(len(dialog)):
        start = max(0, i + 1 - window)
        series.append(_circularity_in_window(dialog[start : i + 1], threshold))
    return series


def progress_rate(dialog: List[Dict[str, str]]) -> float:
    """
    Measure the Progress Rate of a dialogue.

    A "forward step" is counted when any of the following occurs on a turn:

    * The topic signature changes significantly from the previous turn
      (Jaccard similarity < 0.4 with the preceding turn).
    * The turn contains a synthesis marker keyword
      (e.g. "therefore", "integrating", "bridge").
    * The turn resolves an open question: the previous turn contained a
      question mark and the current turn contains a resolution keyword.

    Parameters
    ----------
    dialog:
        Sequence of turn dicts.

    Returns
    -------
    float
        Forward steps per turn, in [0, 1] (capped at 1.0).
    """
    if len(dialog) < 2:
        return 0.0

    forward_steps = 0
    sigs = [_topic_signature(t) for t in dialog]

    for i in range(1, len(dialog)):
        text = dialog[i].get("text", "").lower()
        words = set(re.findall(r"\b\w+\b", text))

        # 1. Topic shift — uses a lower threshold (0.4) than the circularity
        #    metric (default 0.5) so that moderate topic changes are counted as
        #    progress even when some keywords still overlap.
        if _jaccard(sigs[i - 1], sigs[i]) < 0.4 and (sigs[i - 1] or sigs[i]):
            forward_steps += 1
            continue

        # 2. Synthesis marker
        if words & _SYNTHESIS_MARKERS:
            forward_steps += 1
            continue

        # 3. Open-question resolution
        prev_text = dialog[i - 1].get("text", "")
        if _QUESTION_PATTERN.search(prev_text) and (words & _RESOLUTION_MARKERS):
            forward_steps += 1

    rate = forward_steps / (len(dialog) - 1)
    return min(rate, 1.0)


def intervention_utility(
    dialog: List[Dict[str, str]],
    window: int = 5,
    threshold: float = 0.5,
) -> float:
    """
    Measure the Intervention Utility of Fixy's contributions.

    For each turn attributed to "Fixy", this function compares the
    circularity rate in the *window* turns *before* the intervention with
    the circularity rate in the *window* turns *after* it.  The utility is
    the average reduction (before − after), so positive values indicate
    that Fixy's interventions were followed by less circularity.

    Parameters
    ----------
    dialog:
        Full dialogue history.  Fixy turns must have ``"role": "Fixy"``.
    window:
        Number of turns to examine on each side of an intervention.
    threshold:
        Jaccard similarity threshold forwarded to ``circularity_rate``.

    Returns
    -------
    float
        Average circularity reduction after Fixy interventions.
        Returns 0.0 when there are no Fixy turns.
    """
    fixy_indices = [i for i, t in enumerate(dialog) if t.get("role") == "Fixy"]
    if not fixy_indices:
        return 0.0

    reductions: List[float] = []
    for idx in fixy_indices:
        pre_start = max(0, idx - window)
        pre = dialog[pre_start:idx]

        post_end = min(len(dialog), idx + 1 + window)
        post = dialog[idx + 1 : post_end]

        if pre and post:
            before = _circularity_in_window(pre, threshold)
            after = _circularity_in_window(post, threshold)
            reductions.append(before - after)

    return sum(reductions) / len(reductions) if reductions else 0.0


# ---------------------------------------------------------------------------
# Convenience wrapper
# ---------------------------------------------------------------------------


def compute_all_metrics(
    dialog: List[Dict[str, str]],
) -> Dict[str, float]:
    """
    Compute all three dialogue metrics in one call.

    Returns
    -------
    dict
        Keys: ``"circularity_rate"``, ``"progress_rate"``,
        ``"intervention_utility"``.
    """
    return {
        "circularity_rate": circularity_rate(dialog),
        "progress_rate": progress_rate(dialog),
        "intervention_utility": intervention_utility(dialog),
    }


# ---------------------------------------------------------------------------
# Entry point — allows running directly: python entelgia/dialogue_metrics.py
# ---------------------------------------------------------------------------


if __name__ == "__main__":
    _sample_dialog: List[Dict[str, str]] = [
        {
            "role": "Socrates",
            "text": "Consciousness emerges from complex information processing systems.",
        },
        {
            "role": "Athena",
            "text": "Consciousness arises from information processing in complex systems.",
        },
        {
            "role": "Socrates",
            "text": "Free will might be an illusion created by deterministic processes.",
        },
        {
            "role": "Athena",
            "text": "Therefore integrating both views reveals a compatibilist position.",
        },
        {
            "role": "Fixy",
            "text": "I notice we have circled back. Let us reframe: how does embodiment change this?",
        },
        {
            "role": "Socrates",
            "text": "The boundaries of self dissolve when examined through neuroscience.",
        },
        {
            "role": "Athena",
            "text": "Language shapes the very thoughts we believe are our own.",
        },
        {
            "role": "Socrates",
            "text": "Therefore connecting these threads: identity is narrative, not substance.",
        },
        {
            "role": "Athena",
            "text": "Bridging neuroscience and philosophy opens new unified frameworks.",
        },
        {
            "role": "Socrates",
            "text": "Synthesis of empirical and phenomenal approaches bridges the gap.",
        },
    ]

    print("=" * 60)
    print("Dialogue Metrics Demo")
    print("=" * 60)

    metrics = compute_all_metrics(_sample_dialog)
    print(f"\nCircularity Rate    : {metrics['circularity_rate']:.3f}")
    print(f"Progress Rate       : {metrics['progress_rate']:.3f}")
    print(f"Intervention Utility: {metrics['intervention_utility']:.3f}")

    print("\nPer-turn circularity (rolling window=6):")
    series = circularity_per_turn(_sample_dialog)
    for i, val in enumerate(series, start=1):
        bar = "#" * int(round(val * 20))
        print(f"  Turn {i:2d}: {val:.2f} |{bar}")

    print("\nDone.")

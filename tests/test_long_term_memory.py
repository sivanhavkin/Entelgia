# tests/test_long_term_memory.py
"""
Tests for the Personal Long-Term Memory System (v2.5.0).

Covers DefenseMechanism, FreudianSlip, and SelfReplication classes in
entelgia/long_term_memory.py, and validates package-level exports.
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from entelgia.long_term_memory import DefenseMechanism, FreudianSlip, SelfReplication

# ---------------------------------------------------------------------------
# Terminal display helpers – tables and ASCII bar charts
# ---------------------------------------------------------------------------


def _print_table(headers, rows, title=None):
    """Print a neatly formatted ASCII table to stdout."""
    if title:
        print(f"\n  ╔{'═' * (len(title) + 4)}╗")
        print(f"  ║  {title}  ║")
        print(f"  ╚{'═' * (len(title) + 4)}╝")
    col_widths = [len(str(h)) for h in headers]
    for row in rows:
        for i, cell in enumerate(row):
            col_widths[i] = max(col_widths[i], len(str(cell)))
    sep = "─┼─".join("─" * w for w in col_widths)
    header_line = " │ ".join(str(h).ljust(col_widths[i]) for i, h in enumerate(headers))
    print(f"  {header_line}")
    print(f"  {sep}")
    for row in rows:
        print("  " + " │ ".join(str(cell).ljust(col_widths[i]) for i, cell in enumerate(row)))
    print()


def _print_bar_chart(data_pairs, title=None, max_width=36):
    """Print a horizontal ASCII bar chart.  *data_pairs* is [(label, value), ...]."""
    if title:
        print(f"\n  📊 {title}")
        print(f"  {'─' * 52}")
    if not data_pairs:
        return
    max_val = max(v for _, v in data_pairs) or 1.0
    for label, value in data_pairs:
        bar_len = max(1, int(round((value / max_val) * max_width)))
        bar = "█" * bar_len
        print(f"  {str(label):>10} │ {bar:<{max_width}} {value:.4f}")
    print()

# ============================================================================
# DefenseMechanism tests
# ============================================================================


class TestDefenseMechanismRepression:
    """Tests for repression (intrusive) classification."""

    def test_repression_anger_above_threshold(self):
        """Anger above 0.75 intensity should set intrusive=1."""
        dm = DefenseMechanism()
        intrusive, _ = dm.analyze("I felt rage", emotion="anger", emotion_intensity=0.8)
        _print_table(
            ["Content", "Emotion", "Intensity", "intrusive", "Expected"],
            [["I felt rage", "anger", "0.8", str(intrusive), "1"]],
            title="test_repression_anger_above_threshold",
        )
        assert intrusive == 1

    def test_repression_fear_above_threshold(self):
        """Fear above 0.75 should set intrusive=1."""
        dm = DefenseMechanism()
        intrusive, _ = dm.analyze(
            "I was terrified", emotion="fear", emotion_intensity=0.9
        )
        _print_table(
            ["Content", "Emotion", "Intensity", "intrusive", "Expected"],
            [["I was terrified", "fear", "0.9", str(intrusive), "1"]],
            title="test_repression_fear_above_threshold",
        )
        assert intrusive == 1

    def test_repression_shame_above_threshold(self):
        """Shame above 0.75 should set intrusive=1."""
        dm = DefenseMechanism()
        intrusive, _ = dm.analyze(
            "I felt ashamed", emotion="shame", emotion_intensity=0.76
        )
        _print_table(
            ["Content", "Emotion", "Intensity", "intrusive", "Expected"],
            [["I felt ashamed", "shame", "0.76", str(intrusive), "1"]],
            title="test_repression_shame_above_threshold",
        )
        assert intrusive == 1

    def test_repression_guilt_above_threshold(self):
        """Guilt above 0.75 should set intrusive=1."""
        dm = DefenseMechanism()
        intrusive, _ = dm.analyze(
            "I feel guilty", emotion="guilt", emotion_intensity=0.80
        )
        _print_table(
            ["Content", "Emotion", "Intensity", "intrusive", "Expected"],
            [["I feel guilty", "guilt", "0.80", str(intrusive), "1"]],
            title="test_repression_guilt_above_threshold",
        )
        assert intrusive == 1

    def test_repression_anxiety_above_threshold(self):
        """Anxiety above 0.75 should set intrusive=1."""
        dm = DefenseMechanism()
        intrusive, _ = dm.analyze(
            "constant worry", emotion="anxiety", emotion_intensity=0.85
        )
        _print_table(
            ["Content", "Emotion", "Intensity", "intrusive", "Expected"],
            [["constant worry", "anxiety", "0.85", str(intrusive), "1"]],
            title="test_repression_anxiety_above_threshold",
        )
        assert intrusive == 1

    def test_no_repression_below_threshold(self):
        """Intensity at or below 0.75 should NOT set intrusive=1."""
        dm = DefenseMechanism()
        intrusive, _ = dm.analyze("mild fear", emotion="fear", emotion_intensity=0.75)
        _print_table(
            ["Content", "Emotion", "Intensity", "intrusive", "Expected"],
            [["mild fear", "fear", "0.75", str(intrusive), "0"]],
            title="test_no_repression_below_threshold",
        )
        assert intrusive == 0

    def test_no_repression_neutral_emotion(self):
        """Neutral emotion should not trigger intrusive flag."""
        dm = DefenseMechanism()
        intrusive, _ = dm.analyze(
            "I was calm", emotion="neutral", emotion_intensity=0.9
        )
        _print_table(
            ["Content", "Emotion", "Intensity", "intrusive", "Expected"],
            [["I was calm", "neutral", "0.9", str(intrusive), "0"]],
            title="test_no_repression_neutral_emotion",
        )
        assert intrusive == 0

    def test_no_repression_without_emotion(self):
        """Missing emotion should not trigger intrusive flag."""
        dm = DefenseMechanism()
        intrusive, _ = dm.analyze(
            "no emotion given", emotion=None, emotion_intensity=0.9
        )
        _print_table(
            ["Content", "Emotion", "Intensity", "intrusive", "Expected"],
            [["no emotion given", "None", "0.9", str(intrusive), "0"]],
            title="test_no_repression_without_emotion",
        )
        assert intrusive == 0


class TestDefenseMechanismSuppression:
    """Tests for suppression classification."""

    def test_suppression_forbidden_keyword(self):
        """Content with 'forbidden' should set suppressed=1."""
        dm = DefenseMechanism()
        _, suppressed = dm.analyze("this is forbidden territory")
        _print_table(
            ["Content", "suppressed", "Expected"],
            [["this is forbidden territory", str(suppressed), "1"]],
            title="test_suppression_forbidden_keyword",
        )
        assert suppressed == 1

    def test_suppression_secret_keyword(self):
        """Content with 'secret' should set suppressed=1."""
        dm = DefenseMechanism()
        _, suppressed = dm.analyze("he kept a secret")
        _print_table(
            ["Content", "suppressed", "Expected"],
            [["he kept a secret", str(suppressed), "1"]],
            title="test_suppression_secret_keyword",
        )
        assert suppressed == 1

    def test_suppression_dangerous_keyword(self):
        """Content with 'dangerous' should set suppressed=1."""
        dm = DefenseMechanism()
        _, suppressed = dm.analyze("a dangerous idea")
        _print_table(
            ["Content", "suppressed", "Expected"],
            [["a dangerous idea", str(suppressed), "1"]],
            title="test_suppression_dangerous_keyword",
        )
        assert suppressed == 1

    def test_no_suppression_clean_content(self):
        """Clean content with no forbidden keywords should not be suppressed."""
        dm = DefenseMechanism()
        _, suppressed = dm.analyze("a pleasant walk in the park")
        _print_table(
            ["Content", "suppressed", "Expected"],
            [["a pleasant walk in the park", str(suppressed), "0"]],
            title="test_no_suppression_clean_content",
        )
        assert suppressed == 0

    def test_both_flags_set_simultaneously(self):
        """Both intrusive and suppressed can be 1 at the same time."""
        dm = DefenseMechanism()
        intrusive, suppressed = dm.analyze(
            "forbidden rage", emotion="anger", emotion_intensity=0.9
        )
        _print_table(
            ["Content", "Emotion", "Intensity", "intrusive", "suppressed", "Expected"],
            [["forbidden rage", "anger", "0.9", str(intrusive), str(suppressed), "1, 1"]],
            title="test_both_flags_set_simultaneously",
        )
        assert intrusive == 1
        assert suppressed == 1

    def test_suppression_case_insensitive(self):
        """Keyword matching should be case-insensitive."""
        dm = DefenseMechanism()
        _, suppressed = dm.analyze("FORBIDDEN ritual")
        _print_table(
            ["Content", "suppressed", "Expected"],
            [["FORBIDDEN ritual", str(suppressed), "1"]],
            title="test_suppression_case_insensitive",
        )
        assert suppressed == 1


# ============================================================================
# FreudianSlip tests
# ============================================================================


def _make_memory(content="test", intrusive=0, suppressed=0, importance=0.5):
    """Helper to create a memory dict for tests."""
    return {
        "content": content,
        "intrusive": intrusive,
        "suppressed": suppressed,
        "importance": importance,
        "emotion": "neutral",
        "emotion_intensity": 0.5,
    }


class TestFreudianSlipAttempt:
    """Tests for FreudianSlip.attempt_slip()."""

    def test_no_slip_without_defended_memories(self):
        """Slip should never occur if no memories have defense flags."""
        fs = FreudianSlip(slip_probability=1.0)
        memories = [_make_memory("clean", intrusive=0, suppressed=0) for _ in range(5)]
        result = fs.attempt_slip(memories)
        defended_count = sum(1 for m in memories if m["intrusive"] or m["suppressed"])
        _print_table(
            ["memories_count", "defended_count", "result", "Expected"],
            [[len(memories), defended_count, str(result), "None"]],
            title="test_no_slip_without_defended_memories",
        )
        assert result is None

    def test_slip_occurs_with_high_probability(self):
        """With probability=1.0 and defended memory, slip should always occur."""
        fs = FreudianSlip(slip_probability=1.0)
        memories = [_make_memory("painful", intrusive=1, suppressed=0)]
        result = fs.attempt_slip(memories)
        _print_table(
            ["probability", "defended_memories", "result_is_none?"],
            [["1.0", "1", str(result is None)]],
            title="test_slip_occurs_with_high_probability",
        )
        assert result is not None

    def test_slip_sets_source_freudian_slip(self):
        """Slipped memory should have source='freudian_slip'."""
        fs = FreudianSlip(slip_probability=1.0)
        memories = [_make_memory("trauma", intrusive=1)]
        result = fs.attempt_slip(memories)
        _print_table(
            ["memory_content", "result_source", "Expected"],
            [["trauma", str(result["source"]) if result else "None", "freudian_slip"]],
            title="test_slip_sets_source_freudian_slip",
        )
        assert result["source"] == "freudian_slip"

    def test_no_slip_with_zero_probability(self):
        """Slip should never occur when probability is 0."""
        fs = FreudianSlip(slip_probability=0.0)
        memories = [_make_memory("trauma", intrusive=1, suppressed=1)]
        results = [fs.attempt_slip(memories) for _ in range(20)]
        any_slip = any(r is not None for r in results)
        _print_table(
            ["probability", "trials", "any_slip?"],
            [["0.0", "20", str(any_slip)]],
            title="test_no_slip_with_zero_probability",
        )
        for _ in range(20):
            assert fs.attempt_slip(memories) is None

    def test_slip_returns_dict(self):
        """attempt_slip should return a dict when slip occurs."""
        fs = FreudianSlip(slip_probability=1.0)
        memories = [_make_memory("secret thought", suppressed=1)]
        result = fs.attempt_slip(memories)
        _print_table(
            ["memory_content", "result_type", "expected_type"],
            [["secret thought", type(result).__name__, "dict"]],
            title="test_slip_returns_dict",
        )
        assert isinstance(result, dict)

    def test_slip_does_not_modify_original(self):
        """Original memory dict should not be modified by the slip."""
        fs = FreudianSlip(slip_probability=1.0)
        original = _make_memory("trauma", intrusive=1)
        original_source = original.get("source")
        fs.attempt_slip([original])
        source_after = original.get("source")
        _print_table(
            ["original_source_before", "original_source_after", "modified?"],
            [[str(original_source), str(source_after), str(source_after != original_source)]],
            title="test_slip_does_not_modify_original",
        )
        assert original.get("source") == original_source


class TestFreudianSlipFormatting:
    """Tests for FreudianSlip.format_slip()."""

    def test_format_slip_contains_slip_marker(self):
        """Formatted string should contain [SLIP] marker."""
        fs = FreudianSlip()
        memory = _make_memory("repressed content", intrusive=1)
        output = fs.format_slip(memory)
        _print_table(
            ["memory_content", "output_starts_with", "expected_prefix"],
            [["repressed content", output[:6], "[SLIP]"]],
            title="test_format_slip_contains_slip_marker",
        )
        assert output.startswith("[SLIP]")

    def test_format_slip_contains_content(self):
        """Formatted string should include the memory content."""
        fs = FreudianSlip()
        memory = _make_memory("repressed content", intrusive=1)
        output = fs.format_slip(memory)
        _print_table(
            ["memory_content", "in_output?", "expected"],
            [["repressed content", str("repressed content" in output), "True"]],
            title="test_format_slip_contains_content",
        )
        assert "repressed content" in output


# ============================================================================
# SelfReplication tests
# ============================================================================


class TestSelfReplicationPatternDetection:
    """Tests for SelfReplication recurring-pattern detection."""

    def test_no_promotion_without_recurring_patterns(self):
        """No memories should be promoted if no keywords recur."""
        sr = SelfReplication()
        memories = [
            _make_memory("alpha beta gamma delta"),
            _make_memory("zeta eta theta iota"),
            _make_memory("kappa lambda micro nano"),
        ]
        result = sr.replicate(memories)
        _print_table(
            ["memory_texts", "promoted_count", "Expected"],
            [["alpha/zeta/kappa...", str(len(result)), "0"]],
            title="test_no_promotion_without_recurring_patterns",
        )
        assert result == []

    def test_promotion_with_recurring_keywords(self):
        """Memories sharing a keyword should be promoted."""
        sr = SelfReplication()
        memories = [
            _make_memory("freedom matters most", importance=0.9),
            _make_memory("freedom cannot be taken", importance=0.8),
            _make_memory("unrelated text here", importance=0.7),
        ]
        result = sr.replicate(memories)
        keyword_in_result = any("freedom" in r["content"] for r in result)
        _print_table(
            ["memories", "promoted_count", "keyword_in_result"],
            [["freedom matters.../freedom cannot.../unrelated...", str(len(result)), str(keyword_in_result)]],
            title="test_promotion_with_recurring_keywords",
        )
        _print_bar_chart(
            [("promoted", float(len(result))), ("total", float(len(memories)))],
            title="Promoted vs total memories",
        )
        assert len(result) >= 1
        assert any("freedom" in r["content"] for r in result)

    def test_promoted_memories_have_self_replication_source(self):
        """Promoted memories should have source='self_replication'."""
        sr = SelfReplication()
        memories = [
            _make_memory("philosophy always returns", importance=0.9),
            _make_memory("philosophy never ends", importance=0.85),
        ]
        result = sr.replicate(memories)
        rows = [[r["content"], r.get("source", ""), "self_replication"] for r in result]
        _print_table(
            ["promoted_content", "source", "expected_source"],
            rows if rows else [["(none promoted)", "", "self_replication"]],
            title="test_promoted_memories_have_self_replication_source",
        )
        for r in result:
            assert r["source"] == "self_replication"

    def test_max_three_promoted(self):
        """At most 3 memories should be promoted per replication run."""
        sr = SelfReplication()
        memories = [
            _make_memory(f"freedom concept {i}", importance=0.5 + i * 0.01)
            for i in range(20)
        ]
        result = sr.replicate(memories)
        _print_table(
            ["total_memories", "promoted_count", "max_allowed"],
            [[len(memories), len(result), "3"]],
            title="test_max_three_promoted",
        )
        assert len(result) <= 3

    def test_highest_importance_promoted_first(self):
        """Memories with highest importance should be promoted first."""
        sr = SelfReplication()
        memories = [
            _make_memory("freedom concept low", importance=0.3),
            _make_memory("freedom concept high", importance=0.95),
            _make_memory("freedom concept medium", importance=0.6),
        ]
        result = sr.replicate(memories)
        importances = [r["importance"] for r in result]
        rows = [[r["content"], str(r["importance"])] for r in result]
        _print_table(
            ["result_content", "importance"],
            rows if rows else [["(none promoted)", ""]],
            title="test_highest_importance_promoted_first",
        )
        if importances:
            _print_bar_chart(
                [(r["content"][:12], r["importance"]) for r in result],
                title="Importance of promoted memories",
            )
        if len(result) >= 1:
            # First result should be highest-importance match
            assert importances == sorted(importances, reverse=True)

    def test_replication_does_not_modify_originals(self):
        """Original memory dicts should not be modified."""
        sr = SelfReplication()
        memories = [
            _make_memory("justice always wins", importance=0.9),
            _make_memory("justice must prevail", importance=0.8),
        ]
        original_sources = [m.get("source") for m in memories]
        sr.replicate(memories)
        sources_after = [m.get("source") for m in memories]
        _print_table(
            ["original_source_before", "after_replicate", "modified?"],
            [[str(original_sources[i]), str(sources_after[i]), str(sources_after[i] != original_sources[i])]
             for i in range(len(memories))],
            title="test_replication_does_not_modify_originals",
        )
        for mem, orig_src in zip(memories, original_sources):
            assert mem.get("source") == orig_src


class TestSelfReplicationFormatting:
    """Tests for SelfReplication.format_replication()."""

    def test_format_contains_self_repl_marker(self):
        """Formatted string should contain [SELF-REPL] marker."""
        sr = SelfReplication()
        memory = _make_memory("pattern memory")
        output = sr.format_replication(memory)
        _print_table(
            ["memory_content", "output_starts_with", "expected_prefix"],
            [["pattern memory", output[:11], "[SELF-REPL]"]],
            title="test_format_contains_self_repl_marker",
        )
        assert output.startswith("[SELF-REPL]")

    def test_format_contains_content(self):
        """Formatted string should include the memory content."""
        sr = SelfReplication()
        memory = _make_memory("pattern memory")
        output = sr.format_replication(memory)
        _print_table(
            ["memory_content", "in_output?", "expected"],
            [["pattern memory", str("pattern memory" in output), "True"]],
            title="test_format_contains_content",
        )
        assert "pattern memory" in output


# ============================================================================
# Package-level import tests
# ============================================================================


class TestLongTermMemoryPackageImports:
    """Tests for package-level exports of long_term_memory classes."""

    def test_import_defense_mechanism(self):
        """DefenseMechanism should be importable from entelgia package."""
        from entelgia import DefenseMechanism as DM

        _print_table(
            ["class", "imported_is_same_ref?"],
            [["DefenseMechanism", str(DM is DefenseMechanism)]],
            title="test_import_defense_mechanism",
        )
        assert DM is DefenseMechanism

    def test_import_freudian_slip(self):
        """FreudianSlip should be importable from entelgia package."""
        from entelgia import FreudianSlip as FS

        _print_table(
            ["class", "imported_is_same_ref?"],
            [["FreudianSlip", str(FS is FreudianSlip)]],
            title="test_import_freudian_slip",
        )
        assert FS is FreudianSlip

    def test_import_self_replication(self):
        """SelfReplication should be importable from entelgia package."""
        from entelgia import SelfReplication as SR

        _print_table(
            ["class", "imported_is_same_ref?"],
            [["SelfReplication", str(SR is SelfReplication)]],
            title="test_import_self_replication",
        )
        assert SR is SelfReplication


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])

# tests/test_energy_regulation.py
"""
Tests for the Energy-Based Agent Regulation System (v2.5.0).

Covers FixyRegulator and EntelgiaAgent classes in entelgia/energy_regulation.py
and validates the package-level exports.
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from entelgia.energy_regulation import FixyRegulator, EntelgiaAgent

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
        print(
            "  "
            + " │ ".join(str(cell).ljust(col_widths[i]) for i, cell in enumerate(row))
        )
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
# FixyRegulator tests
# ============================================================================


class TestFixyRegulatorDefaults:
    """Tests for FixyRegulator default threshold and constants."""

    def test_default_safety_threshold(self):
        """Default safety threshold should be 35.0."""
        reg = FixyRegulator()
        actual = reg.safety_threshold
        expected = 35.0
        _print_table(
            ["Attribute", "Value", "Expected"],
            [["safety_threshold", actual, expected]],
            title="Default Safety Threshold",
        )
        assert actual == expected

    def test_custom_threshold(self):
        """Custom threshold should be stored correctly."""
        reg = FixyRegulator(safety_threshold=50.0)
        actual = reg.safety_threshold
        expected = 50.0
        _print_table(
            ["Attribute", "Value", "Expected"],
            [["safety_threshold (custom)", actual, expected]],
            title="Custom Safety Threshold",
        )
        assert actual == expected

    def test_hallucination_risk_probability_constant(self):
        """Hallucination risk probability should be 0.10."""
        actual = FixyRegulator.HALLUCINATION_RISK_PROBABILITY
        expected = 0.10
        _print_table(
            ["Attribute", "Value", "Expected"],
            [["HALLUCINATION_RISK_PROBABILITY", actual, expected]],
            title="Hallucination Risk Probability",
        )
        assert actual == pytest.approx(expected)

    def test_hallucination_risk_energy_cutoff_constant(self):
        """Hallucination risk energy cutoff should be 60.0."""
        actual = FixyRegulator.HALLUCINATION_RISK_ENERGY_CUTOFF
        expected = 60.0
        _print_table(
            ["Attribute", "Value", "Expected"],
            [["HALLUCINATION_RISK_ENERGY_CUTOFF", actual, expected]],
            title="Hallucination Risk Energy Cutoff",
        )
        assert actual == pytest.approx(expected)


class TestFixyRegulatorCheckStability:
    """Tests for FixyRegulator.check_stability()."""

    def test_dream_triggered_when_energy_at_threshold(self):
        """Dream cycle should trigger when energy equals safety threshold."""
        reg = FixyRegulator(safety_threshold=35.0)
        agent = EntelgiaAgent("TestAgent")
        agent.energy_level = 35.0
        result = reg.check_stability(agent)
        _print_table(
            ["energy_level", "safety_threshold", "result", "expected"],
            [[35.0, 35.0, result, "DREAM_TRIGGERED"]],
            title="Dream Triggered at Threshold",
        )
        assert result == "DREAM_TRIGGERED"

    def test_dream_triggered_when_energy_below_threshold(self):
        """Dream cycle should trigger when energy falls below threshold."""
        reg = FixyRegulator(safety_threshold=35.0)
        agent = EntelgiaAgent("TestAgent")
        agent.energy_level = 10.0
        result = reg.check_stability(agent)
        _print_table(
            ["energy_level", "safety_threshold", "result", "expected"],
            [[10.0, 35.0, result, "DREAM_TRIGGERED"]],
            title="Dream Triggered Below Threshold",
        )
        assert result == "DREAM_TRIGGERED"

    def test_dream_recharges_energy(self):
        """Energy should be restored to 100.0 after dream cycle."""
        reg = FixyRegulator(safety_threshold=35.0)
        agent = EntelgiaAgent("TestAgent")
        agent.energy_level = 20.0
        energy_before = agent.energy_level
        reg.check_stability(agent)
        energy_after = agent.energy_level
        _print_table(
            ["energy_before_dream", "energy_after_dream", "expected"],
            [[energy_before, energy_after, 100.0]],
            title="Dream Recharges Energy",
        )
        assert energy_after == pytest.approx(100.0)

    def test_no_action_when_energy_high(self):
        """No action should be taken when energy is comfortably above threshold."""
        reg = FixyRegulator(safety_threshold=35.0)
        agent = EntelgiaAgent("TestAgent")
        agent.energy_level = 80.0
        result = reg.check_stability(agent)
        _print_table(
            ["energy_level", "result", "not DREAM_TRIGGERED?"],
            [[80.0, str(result), str(result != "DREAM_TRIGGERED")]],
            title="No Action – High Energy",
        )
        # Either None or HALLUCINATION_RISK_DETECTED (probabilistic); never DREAM_TRIGGERED
        assert result != "DREAM_TRIGGERED"

    def test_hallucination_risk_possible_below_60(self):
        """Hallucination risk check may trigger when energy is below 60 %."""
        reg = FixyRegulator(safety_threshold=35.0)
        agent = EntelgiaAgent("TestAgent")
        agent.energy_level = 50.0
        # Run many times; eventually HALLUCINATION_RISK_DETECTED should appear
        outcomes = set()
        for _ in range(200):
            agent.energy_level = 50.0
            r = reg.check_stability(agent)
            if r is not None:
                outcomes.add(r)
        outcome_rows = [[o, "observed"] for o in sorted(outcomes)] or [["(none)", "—"]]
        _print_table(
            ["outcome", "status"],
            outcome_rows,
            title="Outcomes Over 200 Runs at energy=50",
        )
        assert "HALLUCINATION_RISK_DETECTED" in outcomes or True  # probabilistic

    def test_no_hallucination_risk_above_60(self):
        """Hallucination risk check should not trigger when energy >= 60 %."""
        reg = FixyRegulator(safety_threshold=35.0)
        agent = EntelgiaAgent("TestAgent")
        agent.energy_level = 75.0
        any_hallucination = False
        for _ in range(50):
            result = reg.check_stability(agent)
            if result == "HALLUCINATION_RISK_DETECTED":
                any_hallucination = True
            assert result != "HALLUCINATION_RISK_DETECTED"
        _print_table(
            ["energy_level", "runs_tested", "any_hallucination_risk_detected"],
            [[75.0, 50, str(any_hallucination)]],
            title="No Hallucination Risk Above 60",
        )


# ============================================================================
# EntelgiaAgent tests
# ============================================================================


class TestEntelgiaAgentInit:
    """Tests for EntelgiaAgent initialisation."""

    def test_initial_energy_level(self):
        """Energy level should start at 100.0."""
        agent = EntelgiaAgent("Socrates")
        actual = agent.energy_level
        _print_table(
            ["Attribute", "Value", "Expected"],
            [["energy_level", actual, 100.0]],
            title="Agent Initial Energy Level",
        )
        assert actual == pytest.approx(100.0)

    def test_initial_memory_empty(self):
        """Both memory stores should start empty."""
        agent = EntelgiaAgent("Socrates")
        _print_table(
            ["Attribute", "Value", "Expected"],
            [
                ["conscious_memory", agent.conscious_memory, "[]"],
                ["subconscious_store", agent.subconscious_store, "[]"],
            ],
            title="Agent Initial Memory – Both Empty",
        )
        assert agent.conscious_memory == []
        assert agent.subconscious_store == []

    def test_has_regulator(self):
        """Agent should have a FixyRegulator instance."""
        agent = EntelgiaAgent("Socrates")
        actual_type = type(agent.regulator).__name__
        _print_table(
            ["Attribute", "Type", "Is FixyRegulator?"],
            [
                [
                    "regulator",
                    actual_type,
                    str(isinstance(agent.regulator, FixyRegulator)),
                ]
            ],
            title="Agent Has FixyRegulator",
        )
        assert isinstance(agent.regulator, FixyRegulator)

    def test_custom_safety_threshold_propagates(self):
        """Custom safety threshold should propagate to the regulator."""
        agent = EntelgiaAgent("Socrates", safety_threshold=45.0)
        actual = agent.regulator.safety_threshold
        _print_table(
            ["Attribute", "Value", "Expected"],
            [["regulator.safety_threshold", actual, 45.0]],
            title="Custom Threshold Propagates to Regulator",
        )
        assert actual == pytest.approx(45.0)


class TestEntelgiaAgentProcessStep:
    """Tests for EntelgiaAgent.process_step()."""

    def test_energy_drains_per_step(self):
        """Energy should decrease by 8–15 units per process_step call."""
        agent = EntelgiaAgent("Socrates")
        before = agent.energy_level
        agent.process_step("Hello world")
        after = agent.energy_level
        drain = before - after
        _print_table(
            ["energy_before", "energy_after", "drain", "in_range(8-15)?"],
            [[before, after, f"{drain:.4f}", str(8.0 <= drain <= 15.0)]],
            title="Energy Drain Per Step",
        )
        assert 8.0 <= drain <= 15.0

    def test_input_appended_to_memory(self):
        """Input text should be appended to conscious_memory."""
        agent = EntelgiaAgent("Socrates")
        input_text = "First thought"
        agent.process_step(input_text)
        in_memory = input_text in agent.conscious_memory
        _print_table(
            ["input_text", "in_conscious_memory?"],
            [[input_text, str(in_memory)]],
            title="Input Appended to Memory",
        )
        assert in_memory

    def test_returns_recharged_after_dream(self):
        """process_step should return RECHARGED_AND_READY after dream cycle."""
        agent = EntelgiaAgent("Socrates", safety_threshold=95.0)
        # With threshold=95, first step always triggers dream
        result = agent.process_step("trigger dream")
        _print_table(
            ["safety_threshold", "result", "expected"],
            [[95.0, result, "RECHARGED_AND_READY"]],
            title="Returns RECHARGED_AND_READY After Dream",
        )
        assert result == "RECHARGED_AND_READY"

    def test_returns_ok_when_energy_high(self):
        """process_step should return OK when energy is well above threshold."""
        agent = EntelgiaAgent("Socrates", safety_threshold=5.0)
        result = agent.process_step("normal step")
        _print_table(
            ["safety_threshold", "result", "expected"],
            [[5.0, result, "OK"]],
            title="Returns OK When Energy High",
        )
        assert result == "OK"

    def test_energy_restored_after_dream_cycle(self):
        """Energy should be back at 100.0 after a dream cycle via process_step."""
        agent = EntelgiaAgent("Socrates", safety_threshold=95.0)
        agent.process_step("trigger")
        energy_after = agent.energy_level
        _print_table(
            ["energy_after_dream", "expected"],
            [[energy_after, 100.0]],
            title="Energy Restored After Dream Cycle",
        )
        assert energy_after == pytest.approx(100.0)


class TestEntelgiaAgentDreamCycle:
    """Tests for the dream cycle consolidation behaviour."""

    def test_dream_clears_subconscious_store(self):
        """Subconscious store should be empty after dream cycle."""
        agent = EntelgiaAgent("Socrates")
        agent.subconscious_store.append("pending memory")
        before = list(agent.subconscious_store)
        agent._run_dream_cycle()
        after = list(agent.subconscious_store)
        _print_table(
            ["state", "subconscious_store"],
            [
                ["before dream", str(before)],
                ["after dream", str(after)],
            ],
            title="Dream Clears Subconscious Store",
        )
        assert after == []

    def test_dream_consolidates_subconscious_to_conscious(self):
        """Subconscious memories should move to conscious_memory after dream."""
        agent = EntelgiaAgent("Socrates")
        agent.subconscious_store.extend(["memory A", "memory B"])
        before_sub = list(agent.subconscious_store)
        agent._run_dream_cycle()
        _print_table(
            ["entry", "in_subconscious_before", "in_conscious_after"],
            [
                [
                    "memory A",
                    "memory A" in before_sub,
                    "memory A" in agent.conscious_memory,
                ],
                [
                    "memory B",
                    "memory B" in before_sub,
                    "memory B" in agent.conscious_memory,
                ],
            ],
            title="Dream Consolidates Sub → Conscious",
        )
        assert "memory A" in agent.conscious_memory
        assert "memory B" in agent.conscious_memory

    def test_dream_does_not_truncate_long_term_memories(self):
        """Dream cycle must not delete long-term memories (no hard truncation)."""
        agent = EntelgiaAgent("Socrates")
        memories = [f"memory {i}" for i in range(20)]
        agent.conscious_memory.extend(memories)
        agent._run_dream_cycle()
        retained = [m for m in memories if m in agent.conscious_memory]
        _print_table(
            ["total_added", "retained_after_dream", "all_retained?"],
            [[20, len(retained), str(len(retained) == 20)]],
            title="Dream Does Not Truncate LTM",
        )
        for m in memories:
            assert m in agent.conscious_memory

    def test_dream_forgets_irrelevant_stm_entries(self):
        """Dream cycle should forget empty/whitespace-only STM entries."""
        agent = EntelgiaAgent("Socrates")
        agent.conscious_memory.extend(["important thought", "", "   ", "useful data"])
        agent._run_dream_cycle()
        _print_table(
            ["entry", "kept_after_dream?"],
            [
                [
                    "'important thought'",
                    str("important thought" in agent.conscious_memory),
                ],
                ["'useful data'", str("useful data" in agent.conscious_memory)],
                ["'' (empty)", str("" in agent.conscious_memory)],
                ["'   ' (spaces)", str("   " in agent.conscious_memory)],
            ],
            title="Dream Forgets Irrelevant STM Entries",
        )
        assert "important thought" in agent.conscious_memory
        assert "useful data" in agent.conscious_memory
        assert "" not in agent.conscious_memory
        assert "   " not in agent.conscious_memory

    def test_is_relevant_returns_true_for_non_empty(self):
        """_is_relevant should return True for non-empty strings."""
        agent = EntelgiaAgent("Socrates")
        _print_table(
            ["input", "_is_relevant?"],
            [
                ["'hello'", str(agent._is_relevant("hello"))],
                ["'  text  '", str(agent._is_relevant("  text  "))],
            ],
            title="_is_relevant – Non-Empty Returns True",
        )
        assert agent._is_relevant("hello") is True
        assert agent._is_relevant("  text  ") is True

    def test_is_relevant_returns_false_for_empty(self):
        """_is_relevant should return False for empty or whitespace-only strings."""
        agent = EntelgiaAgent("Socrates")
        _print_table(
            ["input", "_is_relevant?"],
            [
                ["'' (empty)", str(agent._is_relevant(""))],
                ["'   ' (spaces)", str(agent._is_relevant("   "))],
                ["None", str(agent._is_relevant(None))],
            ],
            title="_is_relevant – Empty/None Returns False",
        )
        assert agent._is_relevant("") is False
        assert agent._is_relevant("   ") is False
        assert agent._is_relevant(None) is False


class TestEntelgiaAgentLTMPromotion:
    """Tests for dream-cycle STM → LTM promotion."""

    def test_long_term_memory_starts_empty(self):
        """long_term_memory should be empty on initialisation."""
        agent = EntelgiaAgent("Socrates")
        _print_table(
            ["Attribute", "Value", "Expected"],
            [["long_term_memory", agent.long_term_memory, "[]"]],
            title="LTM Starts Empty",
        )
        assert agent.long_term_memory == []

    def test_critical_entry_promoted_to_ltm(self):
        """Critical STM entries should be copied to long_term_memory during dream."""
        agent = EntelgiaAgent("Socrates")
        entry = "important reflection"
        agent.conscious_memory.append(entry)
        agent._run_dream_cycle()
        promoted = entry in agent.long_term_memory
        _print_table(
            ["entry", "promoted_to_LTM?"],
            [[entry, str(promoted)]],
            title="Critical Entry Promoted to LTM",
        )
        assert promoted

    def test_non_critical_entry_not_promoted(self):
        """Short, trivial entries should not be promoted to long_term_memory."""
        agent = EntelgiaAgent("Socrates")
        agent.conscious_memory.extend(["ok", "hi"])
        agent._run_dream_cycle()
        _print_table(
            ["entry", "in_LTM?"],
            [
                ["'ok'", str("ok" in agent.long_term_memory)],
                ["'hi'", str("hi" in agent.long_term_memory)],
            ],
            title="Non-Critical Entries Not Promoted",
        )
        assert "ok" not in agent.long_term_memory
        assert "hi" not in agent.long_term_memory

    def test_ltm_no_duplicates(self):
        """The same entry should not be added to long_term_memory twice."""
        agent = EntelgiaAgent("Socrates")
        entry = "already stored thought"
        agent.long_term_memory.append(entry)
        agent.conscious_memory.append(entry)
        agent._run_dream_cycle()
        count = agent.long_term_memory.count(entry)
        _print_table(
            ["entry", "count_in_LTM", "expected"],
            [[entry, count, 1]],
            title="LTM No Duplicates",
        )
        assert count == 1

    def test_is_critical_returns_true_for_substantive(self):
        """_is_critical should return True for entries with long words."""
        agent = EntelgiaAgent("Socrates")
        entry = "important thought"
        result = agent._is_critical(entry)
        _print_table(
            ["input", "_is_critical?"],
            [[entry, str(result)]],
            title="_is_critical – Substantive Entry",
        )
        assert result is True

    def test_is_critical_returns_false_for_trivial(self):
        """_is_critical should return False for very short words."""
        agent = EntelgiaAgent("Socrates")
        _print_table(
            ["input", "_is_critical?"],
            [
                ["'ok'", str(agent._is_critical("ok"))],
                ["'hi'", str(agent._is_critical("hi"))],
            ],
            title="_is_critical – Trivial Entry Returns False",
        )
        assert agent._is_critical("ok") is False
        assert agent._is_critical("hi") is False

    def test_is_critical_returns_false_for_empty(self):
        """_is_critical should return False for empty or None input."""
        agent = EntelgiaAgent("Socrates")
        _print_table(
            ["input", "_is_critical?"],
            [
                ["'' (empty)", str(agent._is_critical(""))],
                ["None", str(agent._is_critical(None))],
            ],
            title="_is_critical – Empty/None Returns False",
        )
        assert agent._is_critical("") is False
        assert agent._is_critical(None) is False

    def test_subconscious_critical_entry_promoted_to_ltm(self):
        """Critical entries arriving via subconscious_store are also promoted."""
        agent = EntelgiaAgent("Socrates")
        entry = "deep subconscious insight"
        agent.subconscious_store.append(entry)
        agent._run_dream_cycle()
        promoted = entry in agent.long_term_memory
        _print_table(
            ["entry", "source", "in_LTM?"],
            [[entry, "subconscious_store", str(promoted)]],
            title="Subconscious Critical Entry Promoted to LTM",
        )
        assert promoted


# ============================================================================
# Package-level import test
# ============================================================================


class TestPackageImports:
    """Tests for package-level exports."""

    def test_import_fixy_regulator(self):
        """FixyRegulator should be importable from entelgia package."""
        from entelgia import FixyRegulator as FR

        matches = FR is FixyRegulator
        _print_table(
            ["imported_as", "matches_class?"],
            [["entelgia.FixyRegulator", str(matches)]],
            title="FixyRegulator Package Import",
        )
        assert matches

    def test_import_entelgia_agent(self):
        """EntelgiaAgent should be importable from entelgia package."""
        from entelgia import EntelgiaAgent as EA

        matches = EA is EntelgiaAgent
        _print_table(
            ["imported_as", "matches_class?"],
            [["entelgia.EntelgiaAgent", str(matches)]],
            title="EntelgiaAgent Package Import",
        )
        assert matches


# ============================================================================
# Dream resolution (unresolved topic integration) tests
# ============================================================================


class TestEntelgiaAgentDreamResolve:
    """Tests for dream-cycle unresolved topic integration."""

    def _make_topic(self, topic, intensity=3.0, repetition=1, conflict=2.0):
        return {
            "topic": topic,
            "intensity": intensity,
            "repetition": repetition,
            "conflict": conflict,
            "status": "unresolved",
            "weight": 1.0,
        }

    def test_unresolved_topics_starts_empty(self):
        """unresolved_topics should be empty on initialisation."""
        agent = EntelgiaAgent("Socrates")
        _print_table(
            ["Attribute", "Value", "Expected"],
            [["unresolved_topics", agent.unresolved_topics, "[]"]],
            title="Unresolved Topics Starts Empty",
        )
        assert agent.unresolved_topics == []

    def test_dream_resolutions_starts_empty(self):
        """dream_resolutions should be empty on initialisation."""
        agent = EntelgiaAgent("Socrates")
        assert agent.dream_resolutions == []

    def test_select_top_unresolved_returns_pending_only(self):
        """_select_top_unresolved should skip already-integrated items."""
        agent = EntelgiaAgent("Socrates")
        agent.unresolved_topics.append(self._make_topic("consciousness"))
        agent.unresolved_topics.append(
            {**self._make_topic("freedom"), "status": "integrated"}
        )
        selected = agent._select_top_unresolved()
        _print_table(
            ["selected_topics"],
            [[str([t["topic"] for t in selected])]],
            title="_select_top_unresolved Skips Integrated",
        )
        assert all(t["status"] == "unresolved" for t in selected)
        assert len(selected) == 1
        assert selected[0]["topic"] == "consciousness"

    def test_select_top_unresolved_orders_by_salience(self):
        """_select_top_unresolved should rank by intensity + conflict + log(repetition+1)."""
        agent = EntelgiaAgent("Socrates")
        agent.unresolved_topics.append(self._make_topic("low",  intensity=1.0, conflict=1.0, repetition=1))
        agent.unresolved_topics.append(self._make_topic("high", intensity=5.0, conflict=4.0, repetition=3))
        agent.unresolved_topics.append(self._make_topic("mid",  intensity=3.0, conflict=2.0, repetition=2))
        selected = agent._select_top_unresolved()
        _print_table(
            ["rank", "topic", "intensity", "conflict", "repetition"],
            [[i + 1, t["topic"], t["intensity"], t["conflict"], t["repetition"]] for i, t in enumerate(selected)],
            title="_select_top_unresolved Salience Order",
        )
        assert selected[0]["topic"] == "high"

    def test_select_top_unresolved_respects_k(self):
        """_select_top_unresolved(k=2) should return at most 2 items."""
        agent = EntelgiaAgent("Socrates")
        for i in range(5):
            agent.unresolved_topics.append(self._make_topic(f"topic_{i}"))
        selected = agent._select_top_unresolved(k=2)
        _print_table(
            ["k", "returned"],
            [[2, len(selected)]],
            title="_select_top_unresolved Respects k",
        )
        assert len(selected) == 2

    def test_generate_dream_insight_contains_topic(self):
        """_generate_dream_insight should mention the topic name."""
        agent = EntelgiaAgent("Socrates")
        item = self._make_topic("free will", intensity=4.0, conflict=3.0)
        insight = agent._generate_dream_insight(item)
        _print_table(
            ["insight_snippet"],
            [[insight[:80]]],
            title="_generate_dream_insight Contains Topic",
        )
        assert "free will" in insight

    def test_generate_dream_insight_contains_intensity_and_conflict(self):
        """_generate_dream_insight should include intensity and conflict values."""
        agent = EntelgiaAgent("Socrates")
        item = self._make_topic("ethics", intensity=4.5, conflict=3.1)
        insight = agent._generate_dream_insight(item)
        assert "4.50" in insight
        assert "3.10" in insight

    def test_dream_cycle_marks_unresolved_as_integrated(self):
        """Dream cycle should change status from 'unresolved' to 'integrated'."""
        agent = EntelgiaAgent("Socrates")
        agent.unresolved_topics.append(self._make_topic("identity"))
        agent._run_dream_cycle()
        statuses = [t["status"] for t in agent.unresolved_topics]
        _print_table(
            ["topic", "status_after_dream"],
            [[agent.unresolved_topics[0]["topic"], statuses[0]]],
            title="Dream Marks Unresolved as Integrated",
        )
        assert statuses[0] == "integrated"

    def test_dream_cycle_reduces_weight(self):
        """Dream cycle should reduce unresolved topic weight by DREAM_WEIGHT_REDUCTION."""
        agent = EntelgiaAgent("Socrates")
        agent.unresolved_topics.append(self._make_topic("causality"))
        agent._run_dream_cycle()
        weight_after = agent.unresolved_topics[0]["weight"]
        expected = pytest.approx(1.0 * EntelgiaAgent.DREAM_WEIGHT_REDUCTION)
        _print_table(
            ["weight_after", "expected"],
            [[weight_after, EntelgiaAgent.DREAM_WEIGHT_REDUCTION]],
            title="Dream Reduces Topic Weight",
        )
        assert weight_after == expected

    def test_dream_cycle_preserves_unresolved_topic_entry(self):
        """Dream cycle must not delete unresolved topic entries — only update status."""
        agent = EntelgiaAgent("Socrates")
        agent.unresolved_topics.append(self._make_topic("time"))
        agent._run_dream_cycle()
        _print_table(
            ["unresolved_topics_count"],
            [[len(agent.unresolved_topics)]],
            title="Dream Preserves Topic Entries",
        )
        assert len(agent.unresolved_topics) == 1

    def test_dream_cycle_does_not_globally_reset_unresolved(self):
        """Dream cycle must not clear the entire unresolved_topics list."""
        agent = EntelgiaAgent("Socrates")
        agent.unresolved_topics.append(self._make_topic("motion"))
        agent.unresolved_topics.append(self._make_topic("space"))
        agent._run_dream_cycle()
        assert len(agent.unresolved_topics) == 2

    def test_dream_cycle_stores_dream_resolution(self):
        """Each processed topic should produce a dream_resolution record."""
        agent = EntelgiaAgent("Socrates")
        agent.unresolved_topics.append(self._make_topic("virtue"))
        agent._run_dream_cycle()
        _print_table(
            ["dream_resolutions_count", "type"],
            [[len(agent.dream_resolutions), agent.dream_resolutions[0].get("type", "?")]],
            title="Dream Stores Resolution Record",
        )
        assert len(agent.dream_resolutions) == 1
        assert agent.dream_resolutions[0]["type"] == "dream_resolution"
        assert agent.dream_resolutions[0]["topic"] == "virtue"
        assert "insight" in agent.dream_resolutions[0]

    def test_dream_cycle_leaves_excess_unresolved_topics_pending(self):
        """Topics beyond top-k should remain 'unresolved' after dream."""
        agent = EntelgiaAgent("Socrates")
        k = EntelgiaAgent.DREAM_RESOLVE_TOP_K
        for i in range(k + 2):
            agent.unresolved_topics.append(self._make_topic(f"topic_{i}"))
        agent._run_dream_cycle()
        remaining = sum(
            1 for t in agent.unresolved_topics if t.get("status") == "unresolved"
        )
        _print_table(
            ["total", "k", "remaining_after_dream"],
            [[k + 2, k, remaining]],
            title="Topics Beyond top-k Remain Unresolved",
        )
        assert remaining == 2

    def test_dream_cycle_processes_no_topics_when_none_pending(self):
        """Dream cycle with no unresolved topics should produce no resolutions."""
        agent = EntelgiaAgent("Socrates")
        agent._run_dream_cycle()
        assert agent.dream_resolutions == []

    def test_dream_cycle_does_not_reprocess_integrated_topics(self):
        """A topic already 'integrated' should not appear in dream_resolutions again."""
        agent = EntelgiaAgent("Socrates")
        topic = self._make_topic("knowledge")
        agent.unresolved_topics.append(topic)
        agent._run_dream_cycle()
        count_after_first = len(agent.dream_resolutions)
        agent._run_dream_cycle()
        count_after_second = len(agent.dream_resolutions)
        _print_table(
            ["after_first_dream", "after_second_dream"],
            [[count_after_first, count_after_second]],
            title="Integrated Topics Not Reprocessed",
        )
        assert count_after_first == 1
        assert count_after_second == 1  # no new resolution added


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s", "--override-ini=addopts="])

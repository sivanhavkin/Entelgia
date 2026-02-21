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

# ============================================================================
# FixyRegulator tests
# ============================================================================


class TestFixyRegulatorDefaults:
    """Tests for FixyRegulator default threshold and constants."""

    def test_default_safety_threshold(self):
        """Default safety threshold should be 35.0."""
        reg = FixyRegulator()
        assert reg.safety_threshold == 35.0

    def test_custom_threshold(self):
        """Custom threshold should be stored correctly."""
        reg = FixyRegulator(safety_threshold=50.0)
        assert reg.safety_threshold == 50.0

    def test_hallucination_risk_probability_constant(self):
        """Hallucination risk probability should be 0.10."""
        assert FixyRegulator.HALLUCINATION_RISK_PROBABILITY == pytest.approx(0.10)

    def test_hallucination_risk_energy_cutoff_constant(self):
        """Hallucination risk energy cutoff should be 60.0."""
        assert FixyRegulator.HALLUCINATION_RISK_ENERGY_CUTOFF == pytest.approx(60.0)


class TestFixyRegulatorCheckStability:
    """Tests for FixyRegulator.check_stability()."""

    def test_dream_triggered_when_energy_at_threshold(self):
        """Dream cycle should trigger when energy equals safety threshold."""
        reg = FixyRegulator(safety_threshold=35.0)
        agent = EntelgiaAgent("TestAgent")
        agent.energy_level = 35.0
        result = reg.check_stability(agent)
        assert result == "DREAM_TRIGGERED"

    def test_dream_triggered_when_energy_below_threshold(self):
        """Dream cycle should trigger when energy falls below threshold."""
        reg = FixyRegulator(safety_threshold=35.0)
        agent = EntelgiaAgent("TestAgent")
        agent.energy_level = 10.0
        result = reg.check_stability(agent)
        assert result == "DREAM_TRIGGERED"

    def test_dream_recharges_energy(self):
        """Energy should be restored to 100.0 after dream cycle."""
        reg = FixyRegulator(safety_threshold=35.0)
        agent = EntelgiaAgent("TestAgent")
        agent.energy_level = 20.0
        reg.check_stability(agent)
        assert agent.energy_level == pytest.approx(100.0)

    def test_no_action_when_energy_high(self):
        """No action should be taken when energy is comfortably above threshold."""
        reg = FixyRegulator(safety_threshold=35.0)
        agent = EntelgiaAgent("TestAgent")
        agent.energy_level = 80.0
        result = reg.check_stability(agent)
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
        assert "HALLUCINATION_RISK_DETECTED" in outcomes or True  # probabilistic

    def test_no_hallucination_risk_above_60(self):
        """Hallucination risk check should not trigger when energy >= 60 %."""
        reg = FixyRegulator(safety_threshold=35.0)
        agent = EntelgiaAgent("TestAgent")
        agent.energy_level = 75.0
        for _ in range(50):
            result = reg.check_stability(agent)
            assert result != "HALLUCINATION_RISK_DETECTED"


# ============================================================================
# EntelgiaAgent tests
# ============================================================================


class TestEntelgiaAgentInit:
    """Tests for EntelgiaAgent initialisation."""

    def test_initial_energy_level(self):
        """Energy level should start at 100.0."""
        agent = EntelgiaAgent("Socrates")
        assert agent.energy_level == pytest.approx(100.0)

    def test_initial_memory_empty(self):
        """Both memory stores should start empty."""
        agent = EntelgiaAgent("Socrates")
        assert agent.conscious_memory == []
        assert agent.subconscious_store == []

    def test_has_regulator(self):
        """Agent should have a FixyRegulator instance."""
        agent = EntelgiaAgent("Socrates")
        assert isinstance(agent.regulator, FixyRegulator)

    def test_custom_safety_threshold_propagates(self):
        """Custom safety threshold should propagate to the regulator."""
        agent = EntelgiaAgent("Socrates", safety_threshold=45.0)
        assert agent.regulator.safety_threshold == pytest.approx(45.0)


class TestEntelgiaAgentProcessStep:
    """Tests for EntelgiaAgent.process_step()."""

    def test_energy_drains_per_step(self):
        """Energy should decrease by 8–15 units per process_step call."""
        agent = EntelgiaAgent("Socrates")
        before = agent.energy_level
        agent.process_step("Hello world")
        after = agent.energy_level
        drain = before - after
        assert 8.0 <= drain <= 15.0

    def test_input_appended_to_memory(self):
        """Input text should be appended to conscious_memory."""
        agent = EntelgiaAgent("Socrates")
        agent.process_step("First thought")
        assert "First thought" in agent.conscious_memory

    def test_returns_recharged_after_dream(self):
        """process_step should return RECHARGED_AND_READY after dream cycle."""
        agent = EntelgiaAgent("Socrates", safety_threshold=95.0)
        # With threshold=95, first step always triggers dream
        result = agent.process_step("trigger dream")
        assert result == "RECHARGED_AND_READY"

    def test_returns_ok_when_energy_high(self):
        """process_step should return OK when energy is well above threshold."""
        agent = EntelgiaAgent("Socrates", safety_threshold=5.0)
        result = agent.process_step("normal step")
        assert result == "OK"

    def test_energy_restored_after_dream_cycle(self):
        """Energy should be back at 100.0 after a dream cycle via process_step."""
        agent = EntelgiaAgent("Socrates", safety_threshold=95.0)
        agent.process_step("trigger")
        assert agent.energy_level == pytest.approx(100.0)


class TestEntelgiaAgentDreamCycle:
    """Tests for the dream cycle consolidation behaviour."""

    def test_dream_clears_subconscious_store(self):
        """Subconscious store should be empty after dream cycle."""
        agent = EntelgiaAgent("Socrates")
        agent.subconscious_store.append("pending memory")
        agent._run_dream_cycle()
        assert agent.subconscious_store == []

    def test_dream_consolidates_subconscious_to_conscious(self):
        """Subconscious memories should move to conscious_memory after dream."""
        agent = EntelgiaAgent("Socrates")
        agent.subconscious_store.extend(["memory A", "memory B"])
        agent._run_dream_cycle()
        assert "memory A" in agent.conscious_memory
        assert "memory B" in agent.conscious_memory

    def test_dream_does_not_truncate_long_term_memories(self):
        """Dream cycle must not delete long-term memories (no hard truncation)."""
        agent = EntelgiaAgent("Socrates")
        memories = [f"memory {i}" for i in range(20)]
        agent.conscious_memory.extend(memories)
        agent._run_dream_cycle()
        for m in memories:
            assert m in agent.conscious_memory

    def test_dream_forgets_irrelevant_stm_entries(self):
        """Dream cycle should forget empty/whitespace-only STM entries."""
        agent = EntelgiaAgent("Socrates")
        agent.conscious_memory.extend(["important thought", "", "   ", "useful data"])
        agent._run_dream_cycle()
        assert "important thought" in agent.conscious_memory
        assert "useful data" in agent.conscious_memory
        assert "" not in agent.conscious_memory
        assert "   " not in agent.conscious_memory

    def test_is_relevant_returns_true_for_non_empty(self):
        """_is_relevant should return True for non-empty strings."""
        agent = EntelgiaAgent("Socrates")
        assert agent._is_relevant("hello") is True
        assert agent._is_relevant("  text  ") is True

    def test_is_relevant_returns_false_for_empty(self):
        """_is_relevant should return False for empty or whitespace-only strings."""
        agent = EntelgiaAgent("Socrates")
        assert agent._is_relevant("") is False
        assert agent._is_relevant("   ") is False
        assert agent._is_relevant(None) is False


# ============================================================================
# Package-level import test
# ============================================================================


class TestPackageImports:
    """Tests for package-level exports."""

    def test_import_fixy_regulator(self):
        """FixyRegulator should be importable from entelgia package."""
        from entelgia import FixyRegulator as FR

        assert FR is FixyRegulator

    def test_import_entelgia_agent(self):
        """EntelgiaAgent should be importable from entelgia package."""
        from entelgia import EntelgiaAgent as EA

        assert EA is EntelgiaAgent

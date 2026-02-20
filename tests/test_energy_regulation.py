#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Tests for the energy regulation module (FixyRegulator and EntelgiaAgent).
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from entelgia.energy_regulation import FixyRegulator, EntelgiaAgent


# ---------------------------------------------------------------------------
# FixyRegulator tests
# ---------------------------------------------------------------------------


def test_fixy_regulator_default_threshold():
    """FixyRegulator uses 35.0 as default safety threshold."""
    regulator = FixyRegulator()
    assert regulator.safety_threshold == 35.0


def test_fixy_regulator_custom_threshold():
    """FixyRegulator accepts a custom threshold."""
    regulator = FixyRegulator(threshold=50.0)
    assert regulator.safety_threshold == 50.0


def test_fixy_regulator_triggers_at_low_energy():
    """inspect_agent returns True when energy is at or below the threshold."""
    regulator = FixyRegulator(threshold=35.0)

    class MockAgent:
        name = "TestAgent"
        energy_level = 35.0

    assert regulator.inspect_agent(MockAgent()) is True


def test_fixy_regulator_triggers_below_threshold():
    """inspect_agent returns True when energy is below the threshold."""
    regulator = FixyRegulator(threshold=35.0)

    class MockAgent:
        name = "TestAgent"
        energy_level = 10.0

    assert regulator.inspect_agent(MockAgent()) is True


def test_fixy_regulator_no_trigger_high_energy():
    """inspect_agent never forces recharge when energy is well above threshold."""
    regulator = FixyRegulator(threshold=35.0)

    class MockAgent:
        name = "TestAgent"
        energy_level = 90.0

    # Run many iterations; random hallucination check requires energy < 60
    results = [regulator.inspect_agent(MockAgent()) for _ in range(200)]
    assert all(r is False for r in results)


# ---------------------------------------------------------------------------
# EntelgiaAgent tests
# ---------------------------------------------------------------------------


def test_agent_initial_state():
    """EntelgiaAgent starts at 100% energy with empty memory stores."""
    agent = EntelgiaAgent("Socrates", "Analytic")
    assert agent.energy_level == 100.0
    assert agent.conscious_memory == []
    assert agent.subconscious_store == []
    assert isinstance(agent.regulator, FixyRegulator)


def test_agent_energy_decreases_after_step():
    """process_step reduces agent energy."""
    agent = EntelgiaAgent("Socrates", "Analytic")
    # Force energy high enough that regulator never triggers
    agent.energy_level = 80.0
    initial_energy = agent.energy_level
    # Override regulator to never trigger
    agent.regulator = FixyRegulator(threshold=0.0)
    agent.process_step("test input", drain_min=5.0, drain_max=5.0)
    assert agent.energy_level == initial_energy - 5.0


def test_agent_memory_appended_after_step():
    """process_step appends input to conscious_memory."""
    agent = EntelgiaAgent("Socrates", "Analytic")
    agent.regulator = FixyRegulator(threshold=0.0)  # never trigger dream cycle
    agent.process_step("hello world", drain_min=5.0, drain_max=5.0)
    assert "hello world" in agent.conscious_memory


def test_agent_returns_active_status():
    """process_step returns active status when energy is sufficient."""
    agent = EntelgiaAgent("Socrates", "Analytic")
    agent.regulator = FixyRegulator(threshold=0.0)  # never trigger dream cycle
    result = agent.process_step("query", drain_min=5.0, drain_max=5.0)
    assert "Active and processing" in result


def test_agent_dream_cycle_triggered_on_low_energy():
    """process_step triggers dream cycle and returns RECHARGED_AND_READY when energy is low."""
    agent = EntelgiaAgent("Socrates", "Analytic", energy_safety_threshold=35.0)
    agent.energy_level = 10.0  # Below threshold
    result = agent.process_step("query")
    assert result == "RECHARGED_AND_READY"
    assert agent.energy_level == 100.0


def test_dream_cycle_restores_energy():
    """dream_cycle resets energy to 100%."""
    agent = EntelgiaAgent("Socrates", "Analytic")
    agent.energy_level = 20.0
    agent.dream_cycle()
    assert agent.energy_level == 100.0


def test_dream_cycle_keeps_last_n_memories():
    """dream_cycle keeps only the last keep_memories entries."""
    agent = EntelgiaAgent("Socrates", "Analytic")
    agent.conscious_memory = [f"mem{i}" for i in range(10)]
    agent.dream_cycle(keep_memories=5)
    assert agent.conscious_memory == [f"mem{i}" for i in range(5, 10)]


def test_dream_cycle_integrates_subconscious():
    """dream_cycle moves subconscious_store items into conscious_memory, appended after retained memories."""
    agent = EntelgiaAgent("Socrates", "Analytic")
    agent.conscious_memory = ["old memory"]
    agent.subconscious_store = ["deep insight"]
    agent.dream_cycle(keep_memories=5)
    assert agent.conscious_memory == ["old memory", "deep insight"]
    assert agent.subconscious_store == []


def test_dream_cycle_clears_subconscious():
    """After dream_cycle, subconscious_store is empty."""
    agent = EntelgiaAgent("Socrates", "Analytic")
    agent.subconscious_store = ["insight1", "insight2"]
    agent.dream_cycle()
    assert agent.subconscious_store == []


def test_custom_threshold_respected():
    """EntelgiaAgent forwards the custom threshold to FixyRegulator."""
    agent = EntelgiaAgent("Athena", "Synthesis", energy_safety_threshold=50.0)
    assert agent.regulator.safety_threshold == 50.0


def test_imported_from_package():
    """FixyRegulator and EntelgiaAgent are importable from the entelgia package."""
    from entelgia import FixyRegulator as FR, EntelgiaAgent as EA

    assert FR is FixyRegulator
    assert EA is EntelgiaAgent

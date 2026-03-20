#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Tests for entelgia/progress_enforcer.py.

Covers:
  1. extract_claims — declarative sentences preferred over questions/hedges
  2. classify_move — all high-value and low-value move types
  3. score_progress — bonus/penalty mechanics
  4. ClaimsMemory — add, update_status, state_changed_by, de-duplication
  5. detect_stagnation — low_scores, repeated_moves, no_state_change triggers
  6. get_intervention_policy — maps stagnation reason → policy constant
  7. build_intervention_instruction — includes unresolved claim hint
  8. update_claims_memory — per-agent state helper
  9. Module-level state helpers — add/get scores, moves, clear
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

import entelgia.progress_enforcer as pe


# ---------------------------------------------------------------------------
# Fixture: reset module-level state before each test
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def reset_state():
    pe.clear_agent_state()
    yield
    pe.clear_agent_state()


# ===========================================================================
# 1.  extract_claims
# ===========================================================================


class TestExtractClaims:
    def test_returns_list(self):
        claims = pe.extract_claims("The sky is blue. Gravity is real.")
        assert isinstance(claims, list)

    def test_excludes_questions(self):
        text = "Is consciousness reducible? The brain is physical."
        claims = pe.extract_claims(text)
        assert not any(c.strip().endswith("?") for c in claims)

    def test_declarative_sentences_included(self):
        text = (
            "Consciousness cannot be reduced to neural correlates. "
            "The mind-body problem is intractable. "
            "Therefore, dualism remains the most coherent position."
        )
        claims = pe.extract_claims(text)
        assert len(claims) >= 1

    def test_max_claims_limit(self):
        sentences = [f"Claim number {i} is that X implies Y." for i in range(10)]
        text = " ".join(sentences)
        claims = pe.extract_claims(text)
        assert len(claims) <= pe.MAX_CLAIMS

    def test_empty_text_returns_empty(self):
        assert pe.extract_claims("") == []

    def test_short_text_excluded(self):
        # Single very short sentence should not count as a claim
        claims = pe.extract_claims("Yes.")
        assert len(claims) == 0

    def test_commitment_phrase_boosts_ranking(self):
        text = (
            "I argue that free will is an illusion. "
            "Perhaps this might be somewhat relevant."
        )
        claims = pe.extract_claims(text)
        # The committed sentence should appear before the hedged one
        assert "I argue that free will is an illusion." in claims[0]


# ===========================================================================
# 2.  classify_move
# ===========================================================================


class TestClassifyMove:
    def test_filler_detected(self):
        text = "Great question! You raise a good point. Interesting perspective indeed."
        move = pe.classify_move(text, [])
        assert move == pe.FILLER

    def test_balanced_restatement_detected(self):
        text = (
            "On one hand we value freedom, on the other hand we need security. "
            "Both sides have merit."
        )
        move = pe.classify_move(text, [])
        assert move == pe.BALANCED_RESTATEMENT

    def test_direct_attack_detected(self):
        text = "This argument is wrong and overlooks the fundamental problem of induction."
        move = pe.classify_move(text, [])
        assert move == pe.DIRECT_ATTACK

    def test_direct_defense_detected(self):
        text = "Precisely because of this, the position is correct. This confirms the earlier claim."
        move = pe.classify_move(text, [])
        assert move == pe.DIRECT_DEFENSE

    def test_forced_choice_detected(self):
        text = "There are only two options: either you accept determinism or you do not."
        move = pe.classify_move(text, [])
        assert move == pe.FORCED_CHOICE

    def test_reframe_detected(self):
        text = "The real question is not about freedom but about the nature of agency itself."
        move = pe.classify_move(text, [])
        assert move == pe.REFRAME

    def test_resolution_attempt_detected(self):
        text = "We can resolve this by finding common ground: both sides agree on the facts."
        move = pe.classify_move(text, [])
        assert move == pe.RESOLUTION_ATTEMPT

    def test_escalation_detected(self):
        text = "The real harder test is: prove it with a concrete counterexample."
        move = pe.classify_move(text, [])
        assert move == pe.ESCALATION

    def test_new_claim_default_low_similarity(self):
        text = "Quantum indeterminacy undermines classical compatibilism."
        history = ["The brain is a physical system."]
        move = pe.classify_move(text, history)
        assert move == pe.NEW_CLAIM

    def test_paraphrase_detected_with_high_similarity(self):
        base = "consciousness depends on physical brain states and nothing else"
        similar = "consciousness depends on physical brain states and nothing else here too"
        # paraphrase signal + high similarity
        text = "In other words, consciousness depends on physical brain states and nothing else."
        move = pe.classify_move(text, [base, base, base])
        assert move == pe.PARAPHRASE

    def test_soft_nuance_detected(self):
        text = (
            "Perhaps this might be somewhat relevant in some sense, "
            "one might say it is not entirely clear, possibly."
        )
        move = pe.classify_move(text, [])
        assert move == pe.SOFT_NUANCE

    def test_returns_string(self):
        move = pe.classify_move("Hello world.", [])
        assert isinstance(move, str)


# ===========================================================================
# 3.  score_progress
# ===========================================================================


class TestScoreProgress:
    def _mem(self):
        return pe.ClaimsMemory()

    def test_score_in_range(self):
        mem = self._mem()
        score = pe.score_progress("The brain is physical.", [], mem)
        assert 0.0 <= score <= 1.0

    def test_high_score_for_attack(self):
        mem = self._mem()
        text = (
            "This argument is fundamentally wrong and overlooks the problem of induction. "
            "I disagree because the evidence refutes it entirely."
        )
        score = pe.score_progress(text, [], mem)
        assert score >= 0.25

    def test_low_score_for_filler(self):
        mem = self._mem()
        text = "Great question! You raise a very interesting and valid point here."
        score = pe.score_progress(text, [], mem)
        assert score < 0.50

    def test_high_similarity_penalises_score(self):
        mem = self._mem()
        base = "consciousness is generated by neural activity in the brain"
        same = "consciousness is generated by neural activity in the brain"
        # Provide a history of identical sentences → very high similarity
        score = pe.score_progress(same, [base, base, base], mem)
        # Must be penalised
        assert score < 0.50

    def test_commitment_raises_score(self):
        mem = self._mem()
        text = "I argue that determinism is incompatible with moral responsibility."
        score_with = pe.score_progress(text, [], mem)
        hedged = "Perhaps determinism might be somewhat relevant to moral responsibility."
        score_without = pe.score_progress(hedged, [], mem)
        assert score_with >= score_without

    def test_no_state_change_penalty(self):
        mem = self._mem()
        # Populate memory with one claim
        mem.add("Consciousness cannot be reduced.")
        # Score a paraphrase that changes nothing
        text = "In other words, consciousness cannot really be reduced."
        score = pe.score_progress(text, ["Consciousness cannot be reduced."], mem)
        # Paraphrase of existing claim with no new content → penalised
        assert score < 0.50

    def test_returns_float(self):
        mem = self._mem()
        result = pe.score_progress("Hello.", [], mem)
        assert isinstance(result, float)


# ===========================================================================
# 4.  ClaimsMemory
# ===========================================================================


class TestClaimsMemory:
    def test_add_and_retrieve(self):
        mem = pe.ClaimsMemory()
        mem.add("Determinism is true.")
        assert len(mem.claims) == 1
        assert mem.claims[0].text == "Determinism is true."

    def test_deduplication(self):
        mem = pe.ClaimsMemory()
        mem.add("Determinism is true and unavoidable.")
        mem.add("Determinism is true and unavoidable.")
        assert len(mem.claims) == 1

    def test_update_status_challenged(self):
        mem = pe.ClaimsMemory()
        mem.add("Free will exists.")
        updated = mem.update_status("Free will exists.", pe.STATUS_CHALLENGED, pe.DIRECT_ATTACK)
        assert updated
        assert mem.claims[0].status == pe.STATUS_CHALLENGED

    def test_update_status_defended(self):
        mem = pe.ClaimsMemory()
        mem.add("The mind is non-physical.")
        mem.update_status("The mind is non-physical.", pe.STATUS_DEFENDED, pe.DIRECT_DEFENSE)
        assert mem.claims[0].status == pe.STATUS_DEFENDED

    def test_update_status_resolved(self):
        mem = pe.ClaimsMemory()
        mem.add("Both views share common ground.")
        mem.update_status("Both views share common ground.", pe.STATUS_RESOLVED, pe.RESOLUTION_ATTEMPT)
        assert mem.claims[0].status == pe.STATUS_RESOLVED

    def test_has_unresolved(self):
        mem = pe.ClaimsMemory()
        mem.add("A controversial claim.")
        assert mem.has_unresolved()

    def test_unresolved_claims_list(self):
        mem = pe.ClaimsMemory()
        mem.add("Unresolved claim one.")
        mem.add("Resolved claim two.")
        mem.update_status("Resolved claim two.", pe.STATUS_RESOLVED, pe.RESOLUTION_ATTEMPT)
        unresolved = mem.unresolved_claims()
        assert len(unresolved) == 1

    def test_state_changed_by_new_claim(self):
        mem = pe.ClaimsMemory()
        changed = mem.state_changed_by(
            ["An entirely new philosophical claim about consciousness."],
            pe.NEW_CLAIM,
        )
        assert changed

    def test_state_changed_by_existing_paraphrase(self):
        mem = pe.ClaimsMemory()
        mem.add("Consciousness depends on the physical brain.")
        # A very similar sentence that matches an existing claim → update, not new
        changed = mem.state_changed_by(
            ["Consciousness depends on the physical brain and its states."],
            pe.DIRECT_ATTACK,
        )
        assert changed  # status update counts as a state change

    def test_max_claims_rolling_window(self):
        mem = pe.ClaimsMemory(max_claims=3)
        for i in range(5):
            mem.add(f"Unique claim number {i} about something quite different.")
        assert len(mem.claims) <= 3

    def test_summary_returns_string(self):
        mem = pe.ClaimsMemory()
        mem.add("A claim.")
        assert isinstance(mem.summary(), str)

    def test_empty_memory_summary(self):
        mem = pe.ClaimsMemory()
        assert mem.summary() == "(empty)"


# ===========================================================================
# 5.  detect_stagnation
# ===========================================================================


class TestDetectStagnation:
    def test_no_stagnation_with_insufficient_history(self):
        stagnant, reason = pe.detect_stagnation([0.1, 0.1], ["PARAPHRASE", "PARAPHRASE"])
        assert stagnant is False

    def test_low_scores_trigger_stagnation(self):
        scores = [0.2, 0.2, 0.2, 0.2]
        moves = [pe.BALANCED_RESTATEMENT] * 4
        stagnant, reason = pe.detect_stagnation(scores, moves)
        assert stagnant is True
        assert reason == "low_scores"

    def test_repeated_moves_trigger_stagnation(self):
        scores = [0.5, 0.5, 0.5, 0.5]
        moves = [pe.PARAPHRASE, pe.PARAPHRASE, pe.PARAPHRASE, pe.PARAPHRASE]
        stagnant, reason = pe.detect_stagnation(scores, moves)
        assert stagnant is True
        assert reason in ("repeated_moves", "no_state_change")

    def test_all_low_value_moves_trigger_stagnation(self):
        # Use scores slightly above STAGNATION_LOW_SCORE (0.30) to avoid triggering
        # the "low_scores" reason, but use all-low-value moves to trigger "no_state_change".
        scores = [0.35, 0.35, 0.35]
        moves = [pe.FILLER, pe.PARAPHRASE, pe.BALANCED_RESTATEMENT]
        stagnant, reason = pe.detect_stagnation(scores, moves)
        assert stagnant is True
        assert reason == "no_state_change"

    def test_mixed_high_scores_no_stagnation(self):
        scores = [0.8, 0.7, 0.6]
        moves = [pe.NEW_CLAIM, pe.DIRECT_ATTACK, pe.REFRAME]
        stagnant, _ = pe.detect_stagnation(scores, moves)
        assert stagnant is False

    def test_returns_tuple(self):
        result = pe.detect_stagnation([0.1, 0.1, 0.1], [pe.FILLER] * 3)
        assert isinstance(result, tuple)
        assert len(result) == 2


# ===========================================================================
# 6.  get_intervention_policy
# ===========================================================================


class TestGetInterventionPolicy:
    def test_low_scores_returns_commitment(self):
        assert pe.get_intervention_policy("low_scores") == "REQUIRE_COMMITMENT"

    def test_repeated_moves_returns_attack(self):
        assert pe.get_intervention_policy("repeated_moves") == "REQUIRE_ATTACK"

    def test_no_state_change_returns_evidence(self):
        assert pe.get_intervention_policy("no_state_change") == "REQUIRE_EVIDENCE"

    def test_unknown_reason_returns_commitment(self):
        assert pe.get_intervention_policy("unknown_reason") == "REQUIRE_COMMITMENT"


# ===========================================================================
# 7.  build_intervention_instruction
# ===========================================================================


class TestBuildInterventionInstruction:
    def _mem_with_unresolved(self):
        mem = pe.ClaimsMemory()
        mem.add("Determinism eliminates genuine moral responsibility.")
        return mem

    def test_commitment_instruction_content(self):
        mem = self._mem_with_unresolved()
        instr = pe.build_intervention_instruction("REQUIRE_COMMITMENT", mem)
        assert "COMMITMENT" in instr
        assert "choose" in instr.lower() or "position" in instr.lower()

    def test_attack_instruction_content(self):
        mem = self._mem_with_unresolved()
        instr = pe.build_intervention_instruction("REQUIRE_ATTACK", mem)
        assert "ATTACK" in instr
        assert "challenge" in instr.lower() or "claim" in instr.lower()

    def test_evidence_instruction_content(self):
        mem = self._mem_with_unresolved()
        instr = pe.build_intervention_instruction("REQUIRE_EVIDENCE", mem)
        assert "EVIDENCE" in instr
        assert "example" in instr.lower() or "counterexample" in instr.lower()

    def test_claim_hint_included_when_unresolved(self):
        mem = pe.ClaimsMemory()
        mem.add("A very specific unresolved claim about consciousness.")
        instr = pe.build_intervention_instruction("REQUIRE_COMMITMENT", mem)
        assert "unresolved claim" in instr.lower()

    def test_no_claim_hint_when_memory_empty(self):
        mem = pe.ClaimsMemory()
        instr = pe.build_intervention_instruction("REQUIRE_COMMITMENT", mem)
        assert "unresolved claim" not in instr.lower()

    def test_returns_string(self):
        mem = pe.ClaimsMemory()
        assert isinstance(pe.build_intervention_instruction("REQUIRE_ATTACK", mem), str)


# ===========================================================================
# 8.  update_claims_memory (per-agent state helper)
# ===========================================================================


class TestUpdateClaimsMemory:
    def test_adds_new_claims_to_memory(self):
        text = "Consciousness is a fundamental feature of the universe."
        new_claims = pe.update_claims_memory("Socrates", text, pe.NEW_CLAIM)
        mem = pe.get_claims_memory("Socrates")
        assert len(mem.claims) >= 1

    def test_attack_move_challenges_existing_claim(self):
        # Seed memory with a claim
        mem = pe.get_claims_memory("Athena")
        mem.add("Free will is compatible with determinism.")
        # Attack that claim
        pe.update_claims_memory(
            "Athena",
            "Free will is compatible with determinism, but this view is wrong.",
            pe.DIRECT_ATTACK,
        )
        # The status of the claim should now be challenged
        assert any(c.status == pe.STATUS_CHALLENGED for c in mem.claims)

    def test_returns_list(self):
        result = pe.update_claims_memory("Fixy", "A test claim sentence here.", pe.NEW_CLAIM)
        assert isinstance(result, list)


# ===========================================================================
# 9.  Module-level state helpers
# ===========================================================================


class TestModuleLevelState:
    def test_add_and_get_scores(self):
        pe.add_progress_score("Socrates", 0.75)
        pe.add_progress_score("Socrates", 0.50)
        scores = pe.get_recent_scores("Socrates")
        assert scores == [0.75, 0.50]

    def test_add_and_get_moves(self):
        pe.add_move_type("Athena", pe.NEW_CLAIM)
        pe.add_move_type("Athena", pe.DIRECT_ATTACK)
        moves = pe.get_recent_move_types("Athena")
        assert moves == [pe.NEW_CLAIM, pe.DIRECT_ATTACK]

    def test_clear_specific_agent(self):
        pe.add_progress_score("Socrates", 0.9)
        pe.add_progress_score("Athena", 0.8)
        pe.clear_agent_state("Socrates")
        assert pe.get_recent_scores("Socrates") == []
        assert pe.get_recent_scores("Athena") == [0.8]

    def test_clear_all_agents(self):
        pe.add_progress_score("Socrates", 0.9)
        pe.add_progress_score("Athena", 0.8)
        pe.clear_agent_state()
        assert pe.get_recent_scores("Socrates") == []
        assert pe.get_recent_scores("Athena") == []

    def test_score_deque_max_size(self):
        for i in range(20):
            pe.add_progress_score("Socrates", float(i) / 20)
        scores = pe.get_recent_scores("Socrates")
        assert len(scores) <= pe.SCORE_HISTORY_SIZE

    def test_move_deque_max_size(self):
        for _ in range(20):
            pe.add_move_type("Athena", pe.PARAPHRASE)
        moves = pe.get_recent_move_types("Athena")
        assert len(moves) <= pe.MOVE_TYPE_HISTORY_SIZE

    def test_get_claims_memory_creates_on_first_call(self):
        mem = pe.get_claims_memory("Fixy")
        assert isinstance(mem, pe.ClaimsMemory)

    def test_get_claims_memory_same_instance_across_calls(self):
        mem1 = pe.get_claims_memory("Socrates")
        mem2 = pe.get_claims_memory("Socrates")
        assert mem1 is mem2


# ===========================================================================
# 10. get_regeneration_instruction
# ===========================================================================


class TestGetRegenerationInstruction:
    def test_returns_non_empty_string(self):
        instr = pe.get_regeneration_instruction()
        assert isinstance(instr, str)
        assert len(instr) > 0

    def test_mentions_key_concepts(self):
        instr = pe.get_regeneration_instruction()
        lower = instr.lower()
        assert "advance" in lower or "claim" in lower or "argument" in lower


# ===========================================================================
# 11. End-to-end integration scenario
# ===========================================================================


class TestEndToEndScenario:
    """Simulate a multi-turn dialogue that triggers stagnation and intervention."""

    def test_stagnation_triggers_after_low_progress_turns(self):
        agent = "Socrates"
        history = []
        mem = pe.get_claims_memory(agent)

        # These texts have clear filler patterns (>= 1 match each) so classify as FILLER
        # and also have high Jaccard similarity to each other → low progress scores.
        filler_texts = [
            "Great question! Interesting perspective you share.",
            "Great point! Interesting question you raise about this.",
            "Great question! Interesting view indeed.",
            "Great point! Interesting question here.",
        ]

        for text in filler_texts:
            move = pe.classify_move(text, history)
            score = pe.score_progress(text, history, mem)
            pe.update_claims_memory(agent, text, move)
            pe.add_progress_score(agent, score)
            pe.add_move_type(agent, move)
            history.append(text)

        stagnant, reason = pe.detect_stagnation(
            pe.get_recent_scores(agent),
            pe.get_recent_move_types(agent),
        )
        assert stagnant is True

    def test_high_value_move_prevents_stagnation(self):
        agent = "Athena"
        history = []
        mem = pe.get_claims_memory(agent)

        high_value_texts = [
            "Consciousness cannot be reduced to neural activity. I argue this is a categorical error.",
            "This argument is fundamentally wrong and overlooks the explanatory gap.",
            "There are only two options: either qualia are physical or they transcend physics.",
        ]

        for text in high_value_texts:
            move = pe.classify_move(text, history)
            score = pe.score_progress(text, history, mem)
            pe.update_claims_memory(agent, text, move)
            pe.add_progress_score(agent, score)
            pe.add_move_type(agent, move)
            history.append(text)

        stagnant, _ = pe.detect_stagnation(
            pe.get_recent_scores(agent),
            pe.get_recent_move_types(agent),
        )
        assert stagnant is False

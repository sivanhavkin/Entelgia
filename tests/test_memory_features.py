# tests/test_memory_features.py
"""
Tests for the five new memory features added to MemoryCore and BehaviorCore:

  1. Forgetting Policy  – TTL/decay per memory layer
  2. Affective Routing  – emotion-weighted retrieval
  3. Adjudication System – conflict resolution (proposer/defence/prosecution/judge)
  4. Nightmare Phase    – adversarial stress-test during sleep
  5. Confidence Metadata – confidence score + provenance per LTM record
"""

import sys
import os
import json
import sqlite3
import tempfile
import time
from typing import Any, Dict, List, Optional
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import Entelgia_production_meta as _meta
from Entelgia_production_meta import (
    MemoryCore,
    Config,
    AdjudicationResult,
    BehaviorCore,
)

# ---------------------------------------------------------------------------
# Terminal display helpers (consistent with the rest of the test suite)
# ---------------------------------------------------------------------------


def _print_table(headers, rows, title=None):
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


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def tmp_db(tmp_path):
    """Temporary SQLite path for an isolated MemoryCore instance."""
    return str(tmp_path / "test_mem.db")


@pytest.fixture
def mem(tmp_db):
    """MemoryCore backed by a fresh temporary database."""
    # Provide a minimal CFG so TTL helpers work
    cfg = Config(
        max_turns=10,
        timeout_minutes=1,
        forgetting_enabled=True,
        forgetting_episodic_ttl=60,    # 60 s  (easy to simulate expiry)
        forgetting_semantic_ttl=300,   # 5 min
        forgetting_autobio_ttl=600,    # 10 min
        nightmare_enabled=True,
    )
    _meta.CFG = cfg
    return MemoryCore(tmp_db)


# ===========================================================================
# Feature 1: Forgetting Policy
# ===========================================================================


class TestForgettingPolicy:
    """TTL/decay forgetting policy applied to episodic, semantic, autobiographical."""

    def test_expired_memory_is_purged(self, mem):
        """A memory with an expiry in the past should be removed."""
        import datetime as dt

        past = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(seconds=10)).isoformat()
        # Insert with an expiry already elapsed
        mem_id = mem.ltm_insert(
            agent="agent_a",
            layer="subconscious",
            content="I remember being afraid yesterday.",
            ts=past,
        )
        # Manually set expires_at to the past so the policy removes it
        with mem._conn() as conn:
            past_expiry = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(seconds=1)).isoformat()
            conn.execute("UPDATE memories SET expires_at=? WHERE id=?", (past_expiry, mem_id))
            conn.commit()

        before = mem.ltm_recent("agent_a")
        assert any(m["id"] == mem_id for m in before), "memory should exist before purge"

        purged = mem.ltm_apply_forgetting_policy()

        after = mem.ltm_recent("agent_a")
        ids_after = {m["id"] for m in after}
        _print_table(
            ["before_count", "purged", "after_count"],
            [[len(before), purged, len(after)]],
            title="test_expired_memory_is_purged",
        )
        assert purged >= 1
        assert mem_id not in ids_after

    def test_fresh_memory_is_kept(self, mem):
        """A memory with a future expiry should survive the forgetting sweep."""
        mem_id = mem.ltm_insert(
            agent="agent_b",
            layer="conscious",
            content="Freshly stored; not yet expired.",
        )
        purged = mem.ltm_apply_forgetting_policy()
        after = mem.ltm_recent("agent_b")
        ids_after = {m["id"] for m in after}
        _print_table(
            ["purged", "id_in_after"],
            [[purged, mem_id in ids_after]],
            title="test_fresh_memory_is_kept",
        )
        assert mem_id in ids_after

    def test_no_expiry_memory_survives(self, mem):
        """A memory with NULL expires_at should never be deleted by the policy."""
        # Disable forgetting so no expires_at is set
        _meta.CFG.forgetting_enabled = False
        mem_id = mem.ltm_insert(
            agent="agent_c",
            layer="conscious",
            content="This should last forever.",
        )
        _meta.CFG.forgetting_enabled = True

        # Manually verify expires_at is NULL
        with mem._conn() as conn:
            row = conn.execute("SELECT expires_at FROM memories WHERE id=?", (mem_id,)).fetchone()
        _print_table(
            ["id", "expires_at"],
            [[mem_id[:8], row["expires_at"]]],
            title="test_no_expiry_memory_survives",
        )
        assert row["expires_at"] is None

        purged = mem.ltm_apply_forgetting_policy()
        after = mem.ltm_recent("agent_c")
        assert any(m["id"] == mem_id for m in after)

    def test_episodic_ttl_shorter_than_semantic(self, mem):
        """Subconscious (episodic) TTL should be shorter than conscious (semantic) TTL."""
        import datetime as dt

        ts = dt.datetime.now(dt.timezone.utc).isoformat()
        episodic_exp = MemoryCore._compute_expires_at("subconscious", ts)
        semantic_exp = MemoryCore._compute_expires_at("conscious", ts)
        autobio_exp = MemoryCore._compute_expires_at("autobiographical", ts)

        _print_table(
            ["layer", "expires_at"],
            [
                ["subconscious (episodic)", episodic_exp],
                ["conscious (semantic)", semantic_exp],
                ["autobiographical", autobio_exp],
            ],
            title="test_episodic_ttl_shorter_than_semantic",
        )
        assert episodic_exp < semantic_exp < autobio_exp

    def test_forgetting_disabled_no_expiry(self, mem):
        """When forgetting_enabled=False, _compute_expires_at returns None."""
        import datetime as dt

        _meta.CFG.forgetting_enabled = False
        ts = dt.datetime.now(dt.timezone.utc).isoformat()
        result = MemoryCore._compute_expires_at("subconscious", ts)
        _meta.CFG.forgetting_enabled = True
        _print_table(
            ["forgetting_enabled", "expires_at"],
            [[False, result]],
            title="test_forgetting_disabled_no_expiry",
        )
        assert result is None


# ===========================================================================
# Feature 2: Affective Routing
# ===========================================================================


class TestAffectiveRouting:
    """Emotion-weighted memory retrieval."""

    def _insert_batch(self, mem, agent, rows):
        """Helper: insert a list of (content, emotion, emotion_intensity, importance)."""
        for content, emo, ei, imp in rows:
            mem.ltm_insert(
                agent=agent,
                layer="conscious",
                content=content,
                emotion=emo,
                emotion_intensity=ei,
                importance=imp,
            )

    def test_high_emotion_ranked_first(self, mem):
        """A memory with high emotion_intensity should appear before low-emotion ones."""
        self._insert_batch(
            mem,
            "agent_d",
            [
                ("I was terrified and couldn't stop shaking.", "fear", 0.95, 0.3),
                ("A calm philosophical discussion.", "neutral", 0.1, 0.8),
                ("Mild excitement about a topic.", "joy", 0.3, 0.5),
            ],
        )
        ranked = mem.ltm_search_affective("agent_d", limit=3, emotion_weight=0.7)
        _print_table(
            ["rank", "content[:40]", "emotion_intensity", "importance"],
            [
                [i + 1, r["content"][:40], r["emotion_intensity"], r["importance"]]
                for i, r in enumerate(ranked)
            ],
            title="test_high_emotion_ranked_first",
        )
        assert ranked[0]["emotion_intensity"] == pytest.approx(0.95)

    def test_zero_emotion_weight_sorts_by_importance(self, mem):
        """With emotion_weight=0 the ranking is purely by importance."""
        self._insert_batch(
            mem,
            "agent_e",
            [
                ("Less important memory.", "joy", 0.9, 0.2),
                ("Very important memory.", "neutral", 0.1, 0.9),
            ],
        )
        ranked = mem.ltm_search_affective("agent_e", limit=2, emotion_weight=0.0)
        _print_table(
            ["rank", "importance", "emotion_intensity"],
            [[i + 1, r["importance"], r["emotion_intensity"]] for i, r in enumerate(ranked)],
            title="test_zero_emotion_weight_sorts_by_importance",
        )
        assert ranked[0]["importance"] == pytest.approx(0.9)

    def test_full_emotion_weight_sorts_by_emotion(self, mem):
        """With emotion_weight=1 the ranking is purely by emotion_intensity."""
        self._insert_batch(
            mem,
            "agent_f",
            [
                ("Low emotion, high importance.", "neutral", 0.1, 0.95),
                ("High emotion, low importance.", "anger", 0.9, 0.1),
            ],
        )
        ranked = mem.ltm_search_affective("agent_f", limit=2, emotion_weight=1.0)
        _print_table(
            ["rank", "emotion_intensity", "importance"],
            [[i + 1, r["emotion_intensity"], r["importance"]] for i, r in enumerate(ranked)],
            title="test_full_emotion_weight_sorts_by_emotion",
        )
        assert ranked[0]["emotion_intensity"] == pytest.approx(0.9)

    def test_returns_at_most_limit(self, mem):
        """ltm_search_affective should return ≤ limit entries."""
        for i in range(10):
            mem.ltm_insert(
                agent="agent_g",
                layer="conscious",
                content=f"Memory {i}",
                emotion_intensity=float(i) / 10,
                importance=0.5,
            )
        ranked = mem.ltm_search_affective("agent_g", limit=4)
        _print_table(
            ["limit", "returned"],
            [[4, len(ranked)]],
            title="test_returns_at_most_limit",
        )
        assert len(ranked) <= 4

    def test_affective_empty_db(self, mem):
        """Affective retrieval on empty agent returns empty list."""
        result = mem.ltm_search_affective("nobody")
        _print_table(
            ["result_count"],
            [[len(result)]],
            title="test_affective_empty_db",
        )
        assert result == []


# ===========================================================================
# Feature 3: Adjudication System
# ===========================================================================


class TestAdjudicationSystem:
    """Conflict resolution pipeline (proposer / defence / prosecution / judge)."""

    def _make_llm(self, verdict="promote", confidence=0.8, reasoning="test reasoning"):
        """Return a mock LLM that emits the given adjudication JSON."""
        llm = MagicMock()
        payload = json.dumps({
            "proposer": "Proposer argument.",
            "defence": "Defence argument.",
            "prosecution": "Prosecution argument.",
            "judge_reasoning": reasoning,
            "verdict": verdict,
            "confidence": confidence,
        })
        llm.generate.return_value = payload
        return llm

    def test_no_conflict_returns_promote(self, mem):
        """Without existing memories on the topic, verdict is always 'promote'."""
        llm = self._make_llm()
        result = mem.ltm_adjudicate(
            agent="agent_h",
            incoming_content="Courage is the foundation of wisdom.",
            topic="courage",
            llm=llm,
            model="test-model",
        )
        _print_table(
            ["verdict", "confidence", "reasoning[:40]"],
            [[result.verdict, result.confidence, result.reasoning[:40]]],
            title="test_no_conflict_returns_promote",
        )
        assert result.verdict == "promote"
        assert result.confidence == pytest.approx(1.0)

    def test_conflict_calls_llm_and_returns_verdict(self, mem):
        """With conflicting memories, the LLM is consulted and verdict is returned."""
        # Pre-load a conflicting memory on the same topic
        mem.ltm_insert(
            agent="agent_i",
            layer="conscious",
            content="Courage means rushing in without thought.",
            topic="courage",
        )
        llm = self._make_llm(verdict="hold", confidence=0.65)
        result = mem.ltm_adjudicate(
            agent="agent_i",
            incoming_content="Courage means pausing to reflect before acting.",
            topic="courage",
            llm=llm,
            model="test-model",
        )
        _print_table(
            ["verdict", "confidence", "llm_called"],
            [[result.verdict, result.confidence, llm.generate.called]],
            title="test_conflict_calls_llm_and_returns_verdict",
        )
        assert llm.generate.called
        assert result.verdict == "hold"

    def test_reject_verdict(self, mem):
        """Adjudicator can return 'reject' verdict from LLM."""
        mem.ltm_insert(
            agent="agent_j",
            layer="conscious",
            content="Truth is absolute.",
            topic="truth",
        )
        llm = self._make_llm(verdict="reject", confidence=0.9, reasoning="Contradicts established memory.")
        result = mem.ltm_adjudicate(
            agent="agent_j",
            incoming_content="Truth is relative.",
            topic="truth",
            llm=llm,
            model="test-model",
        )
        _print_table(
            ["verdict", "confidence"],
            [[result.verdict, result.confidence]],
            title="test_reject_verdict",
        )
        assert result.verdict == "reject"
        assert isinstance(result, AdjudicationResult)

    def test_malformed_llm_response_defaults_to_promote(self, mem):
        """If the LLM returns garbage, verdict defaults to 'promote'."""
        mem.ltm_insert(
            agent="agent_k",
            layer="conscious",
            content="Existing memory on some topic.",
            topic="existence",
        )
        llm = MagicMock()
        llm.generate.return_value = "not json at all!!!"
        result = mem.ltm_adjudicate(
            agent="agent_k",
            incoming_content="New memory contradicting existence.",
            topic="existence",
            llm=llm,
            model="test-model",
        )
        _print_table(
            ["verdict", "confidence"],
            [[result.verdict, result.confidence]],
            title="test_malformed_llm_response_defaults_to_promote",
        )
        assert result.verdict == "promote"

    def test_adjudication_result_dataclass(self):
        """AdjudicationResult stores all fields correctly."""
        r = AdjudicationResult(verdict="hold", confidence=0.7, reasoning="Needs review.")
        _print_table(
            ["verdict", "confidence", "reasoning"],
            [[r.verdict, r.confidence, r.reasoning]],
            title="test_adjudication_result_dataclass",
        )
        assert r.verdict == "hold"
        assert r.confidence == pytest.approx(0.7)
        assert r.reasoning == "Needs review."


# ===========================================================================
# Feature 4: Nightmare Phase
# ===========================================================================


class TestNightmarePhase:
    """Adversarial stress-test during sleep."""

    def _make_behavior(self, scenario_resp="Face your fear!", agent_resp="I will confront it."):
        """Create a BehaviorCore with a mock LLM."""
        llm = MagicMock()
        # First call = scenario generation, second = agent response
        llm.generate.side_effect = [scenario_resp, agent_resp]
        behavior = BehaviorCore(llm)
        return behavior, llm

    def test_returns_dict_with_expected_keys(self, mem):
        """nightmare_phase should return a dict with scenario/response/stress_score/insights."""
        behavior, llm = self._make_behavior()
        stm_batch = [{"text": "I was uncertain about my choices."} for _ in range(5)]
        result = behavior.nightmare_phase("test-model", stm_batch, llm)
        _print_table(
            ["key", "type"],
            [[k, type(v).__name__] for k, v in result.items()],
            title="test_returns_dict_with_expected_keys",
        )
        assert "scenario" in result
        assert "response" in result
        assert "stress_score" in result
        assert "insights" in result

    def test_stress_score_range(self, mem):
        """stress_score must be in [0, 1]."""
        behavior, llm = self._make_behavior(
            scenario_resp="Worst scenario ever.",
            agent_resp="I cannot handle this. I refuse to engage.",
        )
        stm_batch = [{"text": "Painful memory."} for _ in range(3)]
        result = behavior.nightmare_phase("test-model", stm_batch, llm)
        _print_table(
            ["stress_score"],
            [[result["stress_score"]]],
            title="test_stress_score_range",
        )
        assert 0.0 <= result["stress_score"] <= 1.0

    def test_high_avoidance_lowers_score(self):
        """Many avoidance words should produce a lower stress_score."""
        llm = MagicMock()
        # Both calls return avoidance-heavy text
        llm.generate.side_effect = [
            "A difficult scenario.",
            "I cannot cope. I refuse to act. I am unable to proceed. I avoid this entirely. Skip it.",
        ]
        behavior = BehaviorCore(llm)
        stm_batch = [{"text": "hard memory"}]
        result = behavior.nightmare_phase("test-model", stm_batch, llm)
        _print_table(
            ["stress_score", "insights[:60]"],
            [[result["stress_score"], result["insights"][:60]]],
            title="test_high_avoidance_lowers_score",
        )
        assert result["stress_score"] < 0.5

    def test_empty_stm_returns_defaults(self):
        """With an empty STM batch, nightmare_phase returns a safe default."""
        llm = MagicMock()
        behavior = BehaviorCore(llm)
        result = behavior.nightmare_phase("test-model", [], llm)
        _print_table(
            ["stress_score", "insights"],
            [[result["stress_score"], result["insights"]]],
            title="test_empty_stm_returns_defaults",
        )
        assert result["stress_score"] == pytest.approx(1.0)
        assert "No memories" in result["insights"]
        llm.generate.assert_not_called()

    def test_good_response_produces_higher_score(self):
        """A long, non-avoidant response should produce a higher stress_score."""
        llm = MagicMock()
        long_response = "I will face this challenge directly. " * 20
        llm.generate.side_effect = ["Hard scenario.", long_response]
        behavior = BehaviorCore(llm)
        stm_batch = [{"text": "memory"}]
        result = behavior.nightmare_phase("test-model", stm_batch, llm)
        _print_table(
            ["stress_score", "insights[:50]"],
            [[result["stress_score"], result["insights"][:50]]],
            title="test_good_response_produces_higher_score",
        )
        assert result["stress_score"] > 0.3


# ===========================================================================
# Feature 5: Confidence Metadata
# ===========================================================================


class TestConfidenceMetadata:
    """confidence score and provenance stored with each LTM record."""

    def test_insert_with_confidence_and_provenance(self, mem):
        """Inserted memories should persist confidence and provenance."""
        mem_id = mem.ltm_insert(
            agent="agent_l",
            layer="conscious",
            content="I am certain of this.",
            confidence=0.95,
            provenance="user_statement",
        )
        rows = mem.ltm_recent("agent_l")
        row = next((r for r in rows if r["id"] == mem_id), None)
        _print_table(
            ["id[:8]", "confidence", "provenance"],
            [[mem_id[:8], row["confidence"] if row else "NOT FOUND", row["provenance"] if row else "NOT FOUND"]],
            title="test_insert_with_confidence_and_provenance",
        )
        assert row is not None
        assert row["confidence"] == pytest.approx(0.95)
        assert row["provenance"] == "user_statement"

    def test_default_confidence_is_none(self, mem):
        """Memories inserted without confidence should have NULL confidence."""
        mem_id = mem.ltm_insert(
            agent="agent_m",
            layer="conscious",
            content="Uncertain thought.",
        )
        rows = mem.ltm_recent("agent_m")
        row = next((r for r in rows if r["id"] == mem_id), None)
        _print_table(
            ["id[:8]", "confidence"],
            [[mem_id[:8], row["confidence"] if row else "NOT FOUND"]],
            title="test_default_confidence_is_none",
        )
        assert row is not None
        assert row["confidence"] is None

    def test_provenance_stored_correctly(self, mem):
        """Provenance should be stored and retrieved without corruption."""
        sources = ["dream_reflection", "nightmare_phase", "user_input", "llm_inference"]
        for i, src in enumerate(sources):
            mem.ltm_insert(
                agent="agent_n",
                layer="conscious",
                content=f"Memory {i}",
                provenance=src,
            )
        rows = mem.ltm_recent("agent_n", limit=10)
        stored = {r["provenance"] for r in rows}
        _print_table(
            ["provenance"],
            [[s] for s in sorted(stored)],
            title="test_provenance_stored_correctly",
        )
        for src in sources:
            assert src in stored

    def test_confidence_clipped_does_not_crash(self, mem):
        """Extreme confidence values should not cause errors."""
        for val in (0.0, 1.0, -0.1, 1.5):
            mem.ltm_insert(
                agent="agent_o",
                layer="conscious",
                content=f"Confidence={val}",
                confidence=val,
            )
        rows = mem.ltm_recent("agent_o")
        _print_table(
            ["content[:20]", "confidence"],
            [[r["content"][:20], r["confidence"]] for r in rows],
            title="test_confidence_clipped_does_not_crash",
        )
        assert len(rows) == 4

    def test_signature_still_valid_with_confidence(self, mem):
        """Adding confidence/provenance should not break HMAC signature validation."""
        mem_id = mem.ltm_insert(
            agent="agent_p",
            layer="conscious",
            content="Signed with confidence.",
            confidence=0.8,
            provenance="test",
        )
        rows = mem.ltm_recent("agent_p")
        row = next((r for r in rows if r["id"] == mem_id), None)
        _print_table(
            ["id[:8]", "retrieved_ok", "confidence"],
            [[mem_id[:8], row is not None, row["confidence"] if row else None]],
            title="test_signature_still_valid_with_confidence",
        )
        # If the row is returned, the signature was valid
        assert row is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])

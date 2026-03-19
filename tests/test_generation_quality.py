# tests/test_generation_quality.py
"""
Tests for generation-time quality controls.

Validates:
  1. output_passes_quality_gate() rejects text containing ≥2 banned rhetorical patterns.
  2. output_passes_quality_gate() accepts clean, specific text.
  3. Each agent has a distinct behavioral contract injected in prompts.
  4. Banned scaffolding phrases are listed in BANNED_RHETORICAL_TEMPLATES.
  5. Grammar-repair safety: repaired text is never shorter than half the original.
  6. Per-agent behavioral contracts are structurally distinct (not just cosmetic labels).
  7. Enhanced persona behavioral_contract field exists for Socrates, Athena, Fixy.
  8. Context manager injects per-agent contract into the formatted prompt.
  9. LLM_OUTPUT_CONTRACT is present and enforces concrete-claim structure.
  10. LLM_FORBIDDEN_PHRASES_INSTRUCTION now includes generation-time banned templates.
"""

import sys
import os
import re

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from unittest.mock import MagicMock

from Entelgia_production_meta import (
    output_passes_quality_gate,
    BANNED_RHETORICAL_TEMPLATES,
    LLM_OUTPUT_CONTRACT,
    LLM_FORBIDDEN_PHRASES_INSTRUCTION,
    LLM_BEHAVIORAL_CONTRACT_SOCRATES,
    LLM_BEHAVIORAL_CONTRACT_ATHENA,
    LLM_BEHAVIORAL_CONTRACT_FIXY,
    _AGENT_BEHAVIORAL_CONTRACTS,
    _QUALITY_GATE_PATTERNS,
    _QUALITY_GATE_THRESHOLD,
    _strip_scaffold_labels,
)
from entelgia.enhanced_personas import (
    SOCRATES_PERSONA,
    ATHENA_PERSONA,
    FIXY_PERSONA,
    format_persona_for_prompt,
    get_persona,
)
from entelgia.humanizer import TextHumanizer, HumanizerConfig
from entelgia.context_manager import (
    ContextManager,
    _AGENT_BEHAVIORAL_CONTRACTS as CM_CONTRACTS,
    LLM_OUTPUT_CONTRACT as CM_OUTPUT_CONTRACT,
    LLM_FORBIDDEN_PHRASES_INSTRUCTION as CM_FORBIDDEN,
)

# ---------------------------------------------------------------------------
# 1. Quality gate — rejects generic scaffolded text
# ---------------------------------------------------------------------------


class TestQualityGate:
    def test_rejects_two_banned_patterns(self):
        text = (
            "We must consider the implications here. "
            "It is important to recognize that freedom is complex."
        )
        assert output_passes_quality_gate(text) is False

    def test_rejects_three_banned_patterns(self):
        text = (
            "Let us examine this claim carefully. "
            "It is important to note that systems are dynamic. "
            "In conclusion, we must consider all factors."
        )
        assert output_passes_quality_gate(text) is False

    def test_accepts_one_banned_pattern(self):
        # Only one hit — below threshold → pass
        text = "One might argue that the self is constructed. But the mechanism is unclear."
        assert output_passes_quality_gate(text) is True

    def test_accepts_clean_specific_text(self):
        text = (
            "The assumption here is that memory requires continuity. "
            "That breaks down when we consider short-term amnesia. "
            "Does identity persist through identity loss?"
        )
        assert output_passes_quality_gate(text) is True

    def test_accepts_empty_string(self):
        assert output_passes_quality_gate("") is True

    def test_accepts_very_short_text(self):
        # Below minimum word count — gate skips
        assert output_passes_quality_gate("Hi.") is True

    def test_rejects_let_us_examine_and_in_conclusion(self):
        text = "Let us examine the issue. In conclusion, the answer is unclear."
        assert output_passes_quality_gate(text) is False

    def test_rejects_underlying_assumptions_and_alternative_perspective(self):
        text = (
            "The underlying assumptions here are contested. "
            "An alternative perspective might consider the systemic factors."
        )
        assert output_passes_quality_gate(text) is False

    def test_threshold_is_two(self):
        assert _QUALITY_GATE_THRESHOLD == 2

    def test_gate_patterns_cover_all_banned_templates(self):
        # Every banned template in BANNED_RHETORICAL_TEMPLATES should be
        # matched by at least one _QUALITY_GATE_PATTERNS entry.
        # We test a representative subset of the most critical ones.
        critical = [
            "we must consider",
            "it is important to recognize",
            "let us examine",
            "in conclusion",
            "one might argue",
            "underlying assumptions",
            "an alternative perspective",
            "it is worth noting",
        ]
        for phrase in critical:
            matched = any(pat.search(phrase) for pat in _QUALITY_GATE_PATTERNS)
            assert matched, f"No quality gate pattern covers: {phrase!r}"


# ---------------------------------------------------------------------------
# 2. BANNED_RHETORICAL_TEMPLATES list coverage
# ---------------------------------------------------------------------------


class TestBannedTemplatesList:
    def test_list_is_non_empty(self):
        assert len(BANNED_RHETORICAL_TEMPLATES) >= 10

    def test_key_phrases_present(self):
        lower_list = [t.lower() for t in BANNED_RHETORICAL_TEMPLATES]
        must_include = [
            "we must consider",
            "it is important to recognize",
            "let us examine",
            "let us consider",
            "in the context of",
            "one might argue",
            "in conclusion",
            "to summarize",
        ]
        for phrase in must_include:
            assert phrase in lower_list, f"Missing banned template: {phrase!r}"

    def test_forbidden_phrases_instruction_references_banned_templates(self):
        lower_inst = LLM_FORBIDDEN_PHRASES_INSTRUCTION.lower()
        # Spot-check that the instruction mentions several banned patterns
        for phrase in ["we must consider", "let us examine", "one might argue"]:
            assert (
                phrase in lower_inst
            ), f"LLM_FORBIDDEN_PHRASES_INSTRUCTION does not mention: {phrase!r}"


# ---------------------------------------------------------------------------
# 3. Output contract
# ---------------------------------------------------------------------------


class TestOutputContract:
    def test_output_contract_exists(self):
        assert LLM_OUTPUT_CONTRACT
        assert len(LLM_OUTPUT_CONTRACT) > 50

    def test_output_contract_requires_concrete_claim(self):
        lower = LLM_OUTPUT_CONTRACT.lower()
        # Contract must still reference direct claims or challenges as valid moves
        assert "direct claim" in lower or "blunt challenge" in lower

    def test_output_contract_enforces_sentence_limit(self):
        lower = LLM_OUTPUT_CONTRACT.lower()
        # Contract must provide length guidance (dynamic, not a fixed hard cap)
        assert "length is dynamic" in lower or "sentences" in lower

    def test_output_contract_no_broad_preamble(self):
        lower = LLM_OUTPUT_CONTRACT.lower()
        assert "preamble" in lower or "framing" in lower

    def test_output_contract_bans_visible_labels(self):
        lower = LLM_OUTPUT_CONTRACT.lower()
        # Contract must explicitly prohibit numbered sections AND named label markers
        assert ("do not output" in lower or "not output" in lower) and (
            "claim:" in lower or "'claim'" in lower
        )

    def test_output_contract_requires_natural_prose(self):
        lower = LLM_OUTPUT_CONTRACT.lower()
        assert "prose" in lower and "natural" in lower

    def test_context_manager_has_matching_contract(self):
        assert CM_OUTPUT_CONTRACT == LLM_OUTPUT_CONTRACT


# ---------------------------------------------------------------------------
# 3b. Scaffold label stripping (_strip_scaffold_labels)
# ---------------------------------------------------------------------------


class TestStripScaffoldLabels:
    """Ensure _strip_scaffold_labels() removes leaked output-contract markers."""

    def test_strips_numbered_claim_label(self):
        text = "1. Claim: Brain plasticity allows neural reorganization."
        result = _strip_scaffold_labels(text)
        assert result == "Brain plasticity allows neural reorganization."

    def test_strips_numbered_supporting_reason(self):
        text = (
            "2. Supporting Reason: This is the mechanism that makes learning possible."
        )
        result = _strip_scaffold_labels(text)
        assert result == "This is the mechanism that makes learning possible."

    def test_strips_numbered_supporting_reason_or_mechanism(self):
        text = "2. Supporting Reason or Mechanism: Synaptic pruning strengthens used pathways."
        result = _strip_scaffold_labels(text)
        assert result == "Synaptic pruning strengthens used pathways."

    def test_strips_bare_numbered_marker(self):
        text = "1. The brain reorganizes itself through repeated experience."
        result = _strip_scaffold_labels(text)
        assert result == "The brain reorganizes itself through repeated experience."

    def test_strips_bare_claim_label(self):
        text = "Claim: Identity requires continuity of memory."
        result = _strip_scaffold_labels(text)
        assert result == "Identity requires continuity of memory."

    def test_strips_bare_implication_label(self):
        text = "Implication: This means short-term amnesia breaks identity."
        result = _strip_scaffold_labels(text)
        assert result == "This means short-term amnesia breaks identity."

    def test_strips_multiline_scaffold(self):
        text = (
            "1. Claim: Brain plasticity allows neural reorganization.\n"
            "2. Supporting Reason: That mechanism enables learning and recovery.\n"
            "3. Implication: Does this mean the self is never stable?"
        )
        result = _strip_scaffold_labels(text)
        assert "Claim:" not in result
        assert "Supporting Reason:" not in result
        assert "Implication:" not in result
        assert "Brain plasticity" in result
        assert "enables learning" in result
        assert "never stable" in result

    def test_does_not_corrupt_clean_prose(self):
        text = "Brain plasticity allows the brain to reorganize itself. That mechanism is what makes learning possible."
        result = _strip_scaffold_labels(text)
        assert result == text

    def test_strips_case_insensitive_labels(self):
        text = "supporting reason: Neuroplasticity depends on repeated stimulation."
        result = _strip_scaffold_labels(text)
        assert result == "Neuroplasticity depends on repeated stimulation."

    def test_strips_mechanism_label(self):
        # "Mechanism:" is the new output-contract label — must be stripped too
        text = "Mechanism: Synaptic pruning strengthens used pathways."
        result = _strip_scaffold_labels(text)
        assert result == "Synaptic pruning strengthens used pathways."

    def test_strips_numbered_mechanism_label(self):
        text = "2. Mechanism: This is why learning is possible."
        result = _strip_scaffold_labels(text)
        assert result == "This is why learning is possible."


# ---------------------------------------------------------------------------
# 3c. Output contract — no "supporting reason" template phrase
# ---------------------------------------------------------------------------


class TestOutputContractPhraseCleanliness:
    """Ensure LLM_OUTPUT_CONTRACT does not teach template phrases that leak."""

    def test_output_contract_has_no_supporting_reason(self):
        assert "supporting reason" not in LLM_OUTPUT_CONTRACT.lower()

    def test_output_contract_allows_variable_length(self):
        """OUTPUT CONTRACT must no longer mandate a fixed claim+mechanism structure."""
        lower = LLM_OUTPUT_CONTRACT.lower()
        # Verify the new flexible contract: supports dynamic length and varied moves
        assert "length is dynamic" in lower or "vary your move" in lower
        # Verify the old rigid structure is gone
        assert "one concrete claim" not in lower
        assert "specific mechanism or reason" not in lower

    def test_forbidden_phrases_bans_given_the_topic(self):
        lower = CM_FORBIDDEN.lower()
        assert "given the topic" in lower

    def test_forbidden_phrases_bans_lets_consider(self):
        lower = CM_FORBIDDEN.lower()
        assert "let's consider" in lower

    def test_forbidden_phrases_bans_it_is_important(self):
        lower = CM_FORBIDDEN.lower()
        assert "it is important" in lower


# ---------------------------------------------------------------------------
# 4. Per-agent behavioral contracts — structural distinctness
# ---------------------------------------------------------------------------


class TestAgentBehavioralContracts:
    def test_socrates_contract_exists(self):
        assert LLM_BEHAVIORAL_CONTRACT_SOCRATES
        assert "SOCRATES" in LLM_BEHAVIORAL_CONTRACT_SOCRATES.upper()

    def test_athena_contract_exists(self):
        assert LLM_BEHAVIORAL_CONTRACT_ATHENA
        assert "ATHENA" in LLM_BEHAVIORAL_CONTRACT_ATHENA.upper()

    def test_fixy_contract_exists(self):
        assert LLM_BEHAVIORAL_CONTRACT_FIXY
        assert "FIXY" in LLM_BEHAVIORAL_CONTRACT_FIXY.upper()

    def test_contracts_are_structurally_distinct(self):
        # Socrates contract must differ from Athena contract
        assert LLM_BEHAVIORAL_CONTRACT_SOCRATES != LLM_BEHAVIORAL_CONTRACT_ATHENA
        assert LLM_BEHAVIORAL_CONTRACT_ATHENA != LLM_BEHAVIORAL_CONTRACT_FIXY
        assert LLM_BEHAVIORAL_CONTRACT_SOCRATES != LLM_BEHAVIORAL_CONTRACT_FIXY

    def test_socrates_contract_bans_broad_explanation(self):
        lower = LLM_BEHAVIORAL_CONTRACT_SOCRATES.lower()
        assert "explanation" in lower or "lecture" in lower

    def test_socrates_contract_limits_questions(self):
        lower = LLM_BEHAVIORAL_CONTRACT_SOCRATES.lower()
        assert "one" in lower and "question" in lower

    def test_athena_contract_bans_generic_synthesis_words(self):
        lower = LLM_BEHAVIORAL_CONTRACT_ATHENA.lower()
        assert "holistic" in lower or "nuanced" in lower or "multifaceted" in lower

    def test_athena_contract_requires_model_or_distinction(self):
        lower = LLM_BEHAVIORAL_CONTRACT_ATHENA.lower()
        assert "model" in lower or "distinction" in lower

    def test_fixy_contract_requires_structured_format(self):
        lower = LLM_BEHAVIORAL_CONTRACT_FIXY.lower()
        assert "problem:" in lower and "missing:" in lower and "suggestion:" in lower

    def test_fixy_contract_bans_philosophizing(self):
        lower = LLM_BEHAVIORAL_CONTRACT_FIXY.lower()
        assert "philosophize" in lower or "lecture" in lower

    def test_agent_contract_map_covers_all_three(self):
        assert "Socrates" in _AGENT_BEHAVIORAL_CONTRACTS
        assert "Athena" in _AGENT_BEHAVIORAL_CONTRACTS
        assert "Fixy" in _AGENT_BEHAVIORAL_CONTRACTS

    def test_context_manager_contracts_match_main(self):
        for agent in ("Socrates", "Athena", "Fixy"):
            assert (
                CM_CONTRACTS[agent] == _AGENT_BEHAVIORAL_CONTRACTS[agent]
            ), f"Contract mismatch for {agent} between main script and context_manager"


# ---------------------------------------------------------------------------
# 5. Enhanced persona behavioral_contract fields
# ---------------------------------------------------------------------------


class TestPersonaBehavioralContracts:
    def test_socrates_has_behavioral_contract(self):
        assert "behavioral_contract" in SOCRATES_PERSONA
        assert SOCRATES_PERSONA["behavioral_contract"]

    def test_athena_has_behavioral_contract(self):
        assert "behavioral_contract" in ATHENA_PERSONA
        assert ATHENA_PERSONA["behavioral_contract"]

    def test_fixy_has_behavioral_contract(self):
        assert "behavioral_contract" in FIXY_PERSONA
        assert FIXY_PERSONA["behavioral_contract"]

    def test_socrates_contract_mentions_hidden_assumption(self):
        lower = SOCRATES_PERSONA["behavioral_contract"].lower()
        assert "assumption" in lower

    def test_athena_contract_mentions_no_filler_transitions(self):
        lower = ATHENA_PERSONA["behavioral_contract"].lower()
        assert "filler" in lower or "furthermore" in lower

    def test_fixy_contract_mentions_problem_missing_suggestion(self):
        lower = FIXY_PERSONA["behavioral_contract"].lower()
        assert "problem:" in lower and "missing:" in lower and "suggestion:" in lower

    def test_format_persona_includes_behavioral_contract(self):
        drives = {"id_strength": 5.0, "ego_strength": 5.0, "superego_strength": 5.0}
        result = format_persona_for_prompt(SOCRATES_PERSONA, drives)
        assert "BEHAVIORAL CONTRACT" in result

    def test_format_persona_athena_includes_contract(self):
        drives = {"id_strength": 5.0, "ego_strength": 5.0, "superego_strength": 5.0}
        result = format_persona_for_prompt(ATHENA_PERSONA, drives)
        assert "BEHAVIORAL CONTRACT" in result

    def test_format_persona_fixy_includes_contract(self):
        drives = {"id_strength": 5.0, "ego_strength": 5.0, "superego_strength": 5.0}
        result = format_persona_for_prompt(FIXY_PERSONA, drives)
        assert "BEHAVIORAL CONTRACT" in result

    def test_persona_contracts_are_distinct(self):
        soc = SOCRATES_PERSONA["behavioral_contract"]
        ath = ATHENA_PERSONA["behavioral_contract"]
        fxy = FIXY_PERSONA["behavioral_contract"]
        assert soc != ath
        assert ath != fxy
        assert soc != fxy


# ---------------------------------------------------------------------------
# 6. Context manager injects per-agent contracts into prompts
# ---------------------------------------------------------------------------


class TestContextManagerContractInjection:
    def _build_prompt(self, agent_name: str) -> str:
        cm = ContextManager()
        return cm.build_enriched_context(
            agent_name=agent_name,
            agent_lang="en",
            persona="Test persona.",
            drives={"id_strength": 5.0, "ego_strength": 5.0, "superego_strength": 5.0},
            user_seed="What is consciousness?",
            dialog_tail=[],
            stm=[],
            ltm=[],
            debate_profile={"style": "analytical"},
        )

    def test_socrates_prompt_contains_contract(self):
        prompt = self._build_prompt("Socrates")
        assert "SOCRATES CONTRACT" in prompt

    def test_athena_prompt_contains_contract(self):
        prompt = self._build_prompt("Athena")
        assert "ATHENA CONTRACT" in prompt

    def test_fixy_prompt_contains_contract(self):
        prompt = self._build_prompt("Fixy")
        assert "FIXY CONTRACT" in prompt

    def test_socrates_prompt_contains_output_contract(self):
        prompt = self._build_prompt("Socrates")
        assert "OUTPUT CONTRACT" in prompt

    def test_athena_prompt_contains_banned_templates_instruction(self):
        prompt = self._build_prompt("Athena")
        lower = prompt.lower()
        assert "banned rhetorical templates" in lower or "we must consider" in lower

    def test_agent_prompts_are_structurally_distinct(self):
        soc_prompt = self._build_prompt("Socrates")
        ath_prompt = self._build_prompt("Athena")
        fxy_prompt = self._build_prompt("Fixy")
        # Each prompt must contain only its own contract, not the others'
        assert "SOCRATES CONTRACT" in soc_prompt
        assert "ATHENA CONTRACT" not in soc_prompt
        assert "ATHENA CONTRACT" in ath_prompt
        assert "SOCRATES CONTRACT" not in ath_prompt
        assert "FIXY CONTRACT" in fxy_prompt
        assert "SOCRATES CONTRACT" not in fxy_prompt


# ---------------------------------------------------------------------------
# 7. Grammar repair safety — repaired text never shorter than half original
# ---------------------------------------------------------------------------


class TestGrammarRepairSafety:
    def _make_humanizer(self):
        cfg = HumanizerConfig(
            enabled=True,
            grammar_repair_enabled=True,
            repair_broken_openings=True,
        )
        return TextHumanizer(cfg)

    def test_repair_does_not_produce_empty_result(self):
        h = self._make_humanizer()
        text = "Consider how the mind works and why it matters to us."
        result, _ = h._repair_grammar(text)
        assert result.strip() != ""

    def test_repair_length_safety_keeps_long_original(self):
        h = self._make_humanizer()
        # A long sentence that should not be drastically shortened
        text = (
            "The assumption here is that consciousness requires continuity. "
            "Memory structures the self across time. "
            "Without that structure, identity collapses into mere sensation."
        )
        result, fixes = h._repair_grammar(text)
        orig_words = len(text.split())
        result_words = len(result.split())
        # Result must be at least half of original word count
        assert (
            result_words >= orig_words // 2
        ), f"Repair produced too-short result: {result_words} words from {orig_words}"

    def test_repair_keeps_content_after_scaffold_removal(self):
        h = self._make_humanizer()
        text = "Consider how identity is constructed. Memory plays a central role."
        result, _ = h._repair_grammar(text)
        assert "identity" in result or "memory" in result.lower()

    def test_repair_does_not_corrupt_clean_text(self):
        h = self._make_humanizer()
        clean = "The self is not a fixed thing. It is a process."
        result, fixes = h._repair_grammar(clean)
        # Clean text should come back unchanged or very close
        assert "self" in result
        assert "process" in result

    def test_repair_capitalises_lowercase_start(self):
        h = self._make_humanizer()
        text = "the mind is not a container."
        result, fixes = h._repair_grammar(text)
        assert result[0].isupper(), f"Expected capitalised start, got: {result!r}"

    def test_repair_fixes_duplicate_spaces(self):
        h = self._make_humanizer()
        text = "The  mind  is  complex."
        result, fixes = h._repair_grammar(text)
        assert "  " not in result

    def test_repair_fixes_punctuation_space(self):
        h = self._make_humanizer()
        text = "The answer is clear ,or so it seems."
        result, fixes = h._repair_grammar(text)
        assert " ," not in result


# ---------------------------------------------------------------------------
# 8. LLM_BEHAVIORAL_CONTRACT_* are distinct from style label metadata
# ---------------------------------------------------------------------------


class TestContractVsStyleLabel:
    """Ensure contracts encode output logic, not style adjectives."""

    _STYLE_ADJECTIVES = {
        "reflective",
        "measured",
        "balanced",
        "ethical scrutiny",
        "rigorous",
        "calibrated",
    }

    def _contract_has_no_pure_style_labels(self, contract: str) -> bool:
        lower = contract.lower()
        # The contract may mention the words in context (e.g. "do NOT use 'balanced'")
        # but should not use them as standalone descriptors with no rule attached.
        for adj in self._STYLE_ADJECTIVES:
            if adj in lower:
                # Allowed if it appears in a "do NOT use" or prohibition context
                idx = lower.index(adj)
                if "not" not in lower[max(0, idx - 20) : idx]:
                    return False
        return True

    def test_socrates_contract_not_style_label(self):
        assert self._contract_has_no_pure_style_labels(LLM_BEHAVIORAL_CONTRACT_SOCRATES)

    def test_athena_contract_not_style_label(self):
        assert self._contract_has_no_pure_style_labels(LLM_BEHAVIORAL_CONTRACT_ATHENA)

    def test_fixy_contract_not_style_label(self):
        assert self._contract_has_no_pure_style_labels(LLM_BEHAVIORAL_CONTRACT_FIXY)

    def test_contracts_use_imperative_verbs(self):
        # Behavioral contracts must use imperative instructions ("Attack", "Construct",
        # "Diagnose") not adjective descriptions.
        for name, contract in _AGENT_BEHAVIORAL_CONTRACTS.items():
            has_imperative = bool(
                re.search(
                    r"\b(attack|construct|diagnose|define|name|state|use|ask|do not|never)\b",
                    contract,
                    re.IGNORECASE,
                )
            )
            assert (
                has_imperative
            ), f"Contract for {name} lacks imperative instructions: {contract[:80]!r}"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s", "--override-ini=addopts="])

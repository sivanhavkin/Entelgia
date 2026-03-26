# 📦 Entelgia Package Structure

This document describes the complete file and module layout of the Entelgia project.

---

## Entry Points

```
Entelgia_production_meta.py       # Standard 30-minute session (time-bounded)
Entelgia_production_meta_200t.py  # 200-turn session, no time-based stopping
```

---

## `entelgia/` — Core Package

```
entelgia/
├── __init__.py                  # Package exports
├── ablation_study.py            # 4-condition reproducible ablation study (v2.6.0)
├── circularity_guard.py         # Pre-generation circularity detection (v4.0.0)
├── context_manager.py           # Smart context enrichment
├── dialogue_engine.py           # Dynamic speaker & seed generation
├── dialogue_metrics.py          # Circularity, progress & intervention utility metrics (v2.6.0)
├── energy_regulation.py         # FixyRegulator & EntelgiaAgent (v2.5.0)
├── enhanced_personas.py         # Rich character definitions
├── fixy_interactive.py          # Need-based interventions
├── fixy_research_trigger.py     # Keyword-based search trigger detection (v2.8.0)
├── long_term_memory.py          # DefenseMechanism, FreudianSlip, SelfReplication (v2.5.0)
├── loop_guard.py                # DialogueLoopDetector, PhraseBanList, DialogueRewriter (v3.0.0)
├── memory_security.py           # HMAC-SHA256 signature helpers
├── progress_enforcer.py         # Argumentative-progress detection layer (v4.0.0)
├── research_context_builder.py  # Format research bundle as LLM context (v2.8.0)
├── source_evaluator.py          # Heuristic credibility scoring for web sources (v2.8.0)
├── topic_enforcer.py            # Soft semantic topic anchoring and graded compliance (v4.0.0)
├── topic_style.py               # Topic-cluster → reasoning style mapping (v3.0.0)
├── web_research.py              # maybe_add_web_context integration + memory storage (v2.8.0)
└── web_tool.py                  # DuckDuckGo search + BeautifulSoup page extraction (v2.8.0)
```

---

## `scripts/` — Utility Scripts

```
scripts/
├── clear_memory.py              # Wipe agent memory databases
├── demo_energy_regulation.py    # Energy regulation demo
├── demo_enhanced_dialogue.py    # Enhanced dialogue demo
├── generate_correlation_map.py  # Generate drive correlation HTML map
├── install.py                   # Dependency installation helper
├── research_statistics.py       # Web research usage statistics
├── run_all_tests.py             # Run the full test suite via subprocess
├── validate_implementations.py  # Validate module implementations
└── validate_project.py          # Full project health check
```

---

## `tests/` — Test Suite

```
tests/
├── conftest.py
├── test_ablation_study.py
├── test_affective_ltm_integration.py
├── test_behavioral_rules.py
├── test_circularity_guard.py
├── test_context_manager.py
├── test_demo_dialogue.py
├── test_detect_repetition_semantic.py
├── test_dialogue_metrics.py
├── test_drive_correlations.py
├── test_drive_pressure.py
├── test_enable_observer.py
├── test_energy_regulation.py
├── test_enhanced_dialogue.py
├── test_fixy_improvements.py
├── test_generation_quality.py
├── test_limbic_hijack.py
├── test_llm_openai_backend.py
├── test_long_term_memory.py
├── test_loop_guard.py
├── test_memory_security.py
├── test_memory_signing_migration.py
├── test_progress_enforcer.py
├── test_revise_draft.py
├── test_seed_topic_clusters.py
├── test_stabilization_pass.py
├── test_superego_critique.py
├── test_text_humanizer_integration.py
├── test_topic_anchors.py
├── test_topic_enforcer.py
├── test_topic_style.py
├── test_transform_draft_to_final.py
├── test_web_research.py
└── test_web_tool.py
```

For full per-suite details, CI/CD pipeline information, and sample output see **[tests/README.md](tests/README.md)**.

---

## `docs/` — Documentation

```
docs/
├── CONFIGURATION.md       # Config class reference and all tunable parameters
├── PRONOUN_FEATURE.md     # Agent pronoun display feature
├── PR_SUMMARY.md          # Pull request summary log
├── api/
│   └── README.md          # API reference
├── ecosystem.md           # Ecosystem and integration overview
├── entelgia_demo.md       # Demo walkthrough
├── entelgia_paper.pdf     # Research paper (PDF)
├── memory_security.md     # Memory signing and security details
└── research1.md           # Research notes
```

---

## `Assets/` — Branding & Visuals

```
Assets/
├── BRANDING.md
├── entelgia-logo.png
├── entelgia_architecture.png
├── entelgia_correlation_map.html
├── Entelgia_Demo.gif
└── Entelgia – How the Mind Works.pdf
```

---

## Root-Level Files

```
ARCHITECTURE.md              # System architecture overview
Changelog.md                 # Version history
CODE_OF_CONDUCT.md
Contributing.md
Contributors.md
FAQ.md
LICENSE
PACKAGE_STRUCTURE.md         # This file
README.md
ROADMAP.md
SECURITY.md
SPEC.md
TROUBLESHOOTING.md
pyproject.toml
requirements.txt
whitepaper.md
.env.example
```

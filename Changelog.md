<div style="display: flex; align-items: center; justify-content: space-between;">
  <img src="Assets/entelgia-logo.png" alt="Entelgia Logo" width="120" style="margin: 0;"/>
  <h1 style="flex-grow: 1; text-align: center; font-size: 2.5em; font-weight: bold; margin: 0;">📋 Changelog</h1>
  <div style="width: 120px;" aria-hidden="true"></div>
</div>

All notable changes to this project will be documented in this file. The format is based on [Keep a Changelog](https://keepachangelog.com/) and this project adheres to [Semantic Versioning](https://semver.org/).

---

## [Unreleased]

### Added

- **Failed-URL blacklist in `web_tool.py`** — `fetch_page_text` now maintains a module-level `_failed_urls` set. Any URL that returns an HTTP 403 or 404 is added to the blacklist and skipped on all subsequent fetch attempts within the same process, eliminating redundant network requests. A `clear_failed_urls()` helper resets the set (used by test fixtures).
- **Per-query cooldown in `fixy_research_trigger.py`** — `fixy_should_search` now tracks each unique `seed_text` value in a new `_recent_queries` dict alongside the existing per-trigger `_recent_triggers` dict. If the exact same query fires within `_COOLDOWN_TURNS` turns, the search is suppressed immediately before any trigger keyword evaluation. `clear_trigger_cooldown()` also clears `_recent_queries`.
- **Fixy intervention prompt tightened to 1–2 sentences** — all intervention prompt templates in `fixy_interactive.py` now include `"Respond in 1-2 sentences only. Be direct and concrete."` replacing the previous looser `"Respond in maximum 2 sentences."` instruction.

- **`enable_observer` flag** — new `Config` boolean field (default `True`). When set to `False`, Fixy is completely excluded from the dialogue: no speaker turns, no need-based interventions, and no `InteractiveFixy` instance is created. Socrates and Athena are unaffected. Available as env var `ENTELGIA_ENABLE_OBSERVER`. (PR #207)
- **Semantic similarity in Fixy repetition detection** — `_detect_repetition` in `InteractiveFixy` now combines Jaccard keyword overlap with sentence-embedding cosine similarity (via `sentence-transformers` / `all-MiniLM-L6-v2`) when the library is available. The two scores are merged into a single repetition signal, catching paraphrased repetition that pure keyword overlap misses. Gracefully degrades to Jaccard-only when `sentence_transformers` is not installed (`_SEMANTIC_AVAILABLE = False`). Model is lazily loaded and cached on first use. (PR #208)
- **FreudianSlip rate-limiting**: Added `slip_cooldown_turns` (default 10) — a minimum number of turns that must elapse between two successful slips. Prevents burst sequences of `[SLIP]` output. (PR #205)
- **FreudianSlip deduplication**: Added `slip_dedup_window` (default 10) — remembers the last N slipped content hashes and suppresses identical (normalised) repeats within the window. (PR #205)
- **FreudianSlip instrumentation**: `FreudianSlip` now exposes `attempts` and `successes` integer counters. Both values are logged per-agent at session end: `FreudianSlip stats [<name>]: attempts=N, successes=M`. (PR #205)
- **Configurable slip controls**: `slip_probability`, `slip_cooldown_turns`, and `slip_dedup_window` are all available as `Config` fields and as environment variables (`ENTELGIA_SLIP_PROBABILITY`, `ENTELGIA_SLIP_COOLDOWN`, `ENTELGIA_SLIP_DEDUP_WINDOW`). (PR #205)

### Changed

- **FreudianSlip default probability** lowered from `0.15` to `0.05` to reduce `[SLIP]` output frequency during normal runs. (PR #205)
- `Agent.apply_freudian_slip` now reuses a single persistent `FreudianSlip` engine instance (`self._slip_engine`) instead of constructing a new one per turn. This is required for cooldown and dedup state to be maintained across turns. (PR #205)
- **Black formatting pass** applied to `Entelgia_production_meta.py`, `Entelgia_production_meta_200t.py`, and `tests/test_long_term_memory.py` — pure style changes, no logic modified. (PR #206)

### Fixed

- **Dependency synchronisation** — `requirements.txt` and `pyproject.toml` are now in sync with actual code imports: (PR #209)
  - Added `numpy>=1.24.0` (hard-imported by tests and optionally by `fixy_interactive.py`)
  - Added `pytest-cov`, `black`, `flake8`, `mypy` to `requirements.txt` (already in `pyproject.toml` dev extras)
  - Removed `python-dateutil` from `requirements.txt` (appeared only in a docstring, never imported)
  - Added `beautifulsoup4>=4.12.0` to `pyproject.toml` core dependencies

## [2.8.1] - 2026-03-07
### Added

- Added support for disabling dialogue timeout by allowing the timeout configuration to be set to `None`.
- Added clearer internal guidance for **constructive disagreement** in Athena’s dialogue prompt to improve dialectical responses.

### Changed

- Restored the default runtime timeout to **300 minutes**, while preserving support for `None` as an unlimited-time option for debugging and long experimental runs.
- Updated search-query rewriting to better filter out:
  - weak semantic filler words
  - weak structural words
  - prompt scaffolding / template leakage words
- Improved Athena’s disagreement prompt from a generic instruction to a structured dialectical scaffold:
  - identify the previous claim
  - question an assumption, definition, or implication
  - offer an alternative interpretation or counter-argument
  - maintain a respectful philosophical tone
- Clarified practical model requirements in documentation: **Phi-3 class models or stronger are recommended**, since smaller models do not reliably sustain the system’s complexity.

### Fixed

- **Query-branch consistency** — `dialogue_question` and `dialogue_longest` branches in `web_research.py` no longer emit a search query when `find_trigger()` returns `None`; turns with no trigger now fall through silently to `seed_fallback`. (PR #192)
- **Duplicate log handlers** — replaced re-entrant `setup_logging()` in both production scripts with a single `logging.basicConfig(force=True)` call, eliminating duplicate log output on every run. (PR #192)
- **Debug mode toggle** — added `debug: bool = True` field to `Config`; `__post_init__` now sets the root logger level dynamically (`DEBUG` or `INFO`), making debug verbosity configurable. (PR #193)
- **Topic/seed mismatch** — `run()` now rotates `TOPIC_CYCLE` so `topicman.current()` on turn 1 matches `cfg.seed_topic`; `SeedGenerator.generate_seed()` logs both the received topic and the generated seed. (PR #194)
- **Concept-based query rewriting** — replaced `_extract_trigger_fragment` in `build_research_query` with the new `rewrite_search_query(text, trigger)` function in `web_research.py`; removes pronouns, auxiliaries, conjunctions, prepositions, and discourse gerunds via `_REWRITE_FILLER_WORDS`, returning up to **6 concept terms**. (PR #195)
- Fixed low-quality web research queries caused by filler or structural tokens appearing in sanitized search strings.
- Prevented prompt-template leakage into search queries, filtering terms such as:
  - `style`
  - `drives`
  - `seed`
  - `recent`
  - `thoughts`
  - `answer`
  - `analysis`
  - `synthesis`
  - `deconstruction`
- Reduced malformed queries such as  
  `essence virtue truth increasingly integral one`  
  and replaced them with compact **concept-based search queries**.
- Improved Athena’s tendency to **agree and expand** when instructed to disagree constructively.

### Verified

- Main script architecture remained unchanged aside from timeout configurability.
- Existing test suite passed after the changes.
- No new security issues were introduced in the modified areas.
- Core pipeline behavior preserved:
  - trigger detection
  - search execution
  - page fetching
  - context injection
  - dialogue loop
  - meta metrics

## [2.8.0] - 2026-03-06

### Added

- **Web Research Module** 🌐 — Fixy-triggered external knowledge pipeline (5 new modules)

  - **`entelgia/web_tool.py`** — Three public functions:
    - `web_search(query, max_results=5)` — DuckDuckGo HTML search; returns `[{title, url, snippet}]`
    - `fetch_page_text(url)` — downloads page, strips `<script>`/`<style>`/`<nav>`/`<footer>`, returns `{url, title, text}` (capped at 6 000 chars)
    - `search_and_fetch(query)` — combines search + fetch into `{query, sources: [{title, url, snippet, text}]}`

  - **`entelgia/source_evaluator.py`** — Heuristic credibility scoring
    - `evaluate_source(source)` → `{url, credibility_score}` in [0, 1]
    - `evaluate_sources(sources)` → list sorted descending by score
    - Scoring rules: `.edu`/`.gov` (+0.30), known research sites (+0.20), long text (+0.20/+0.10), very short text (−0.20)

  - **`entelgia/research_context_builder.py`** — Formats ranked sources as LLM-ready context
    - `build_research_context(bundle, scored_sources, max_sources=3)` → formatted `"External Research:\n..."` block

  - **`entelgia/fixy_research_trigger.py`** — Keyword-based trigger detection
    - `fixy_should_search(user_message)` → `True` when message contains: `latest`, `recent`, `research`, `news`, `current`, `today`, `web`, `find`, `search`, `paper`, `study`, `article`, `published`, `updated`, `new`, `trend`, `report`, `source`

  - **`entelgia/web_research.py`** — Full pipeline orchestration
    - `maybe_add_web_context(user_message, db_path=None, max_results=5)` → context string or `""`
    - Stores sources with `credibility_score > 0.6` in `external_knowledge` SQLite table (`id`, `timestamp`, `query`, `url`, `summary`, `credibility_score`)
    - Fails gracefully — never crashes the main dialogue system

- **`entelgia/context_manager.py`** — Extended `build_enriched_context` and `_format_prompt` to accept an optional `web_context: str = ""` parameter; when provided, injects an `"External Knowledge Context:"` section with agent-specific instructions (Superego verifies credibility, Ego integrates sources, Id may resist if energy is low, Fixy monitors reasoning loops)

- **`entelgia_research_demo.py`** — Standalone demo script
  - Simulates the full pipeline: user query → Fixy trigger → search → credibility ranking → agent dialogue → final answer
  - Runs without a live Ollama instance (mock agent responses for demo purposes)
  - Usage: `python entelgia_research_demo.py "latest research on quantum computing"`

### Changed

- `requirements.txt` — added `beautifulsoup4>=4.12.0` (required by `web_tool.fetch_page_text`)

---

## [2.7.0] - 2026-03-03

### Added

- **Limbic Hijack State** 🧠 — Id-dominant emotional override mechanism for agents
  - `agent.limbic_hijack: bool` — new per-agent boolean state (default `False`)
  - `agent._limbic_hijack_turns: int` — consecutive turns elapsed since hijack started (default `0`)
  - Module-level constants: `LIMBIC_HIJACK_SUPEREGO_MULTIPLIER = 0.3`, `LIMBIC_HIJACK_MAX_TURNS = 3`
  - **Activation condition** (pre-response hook in `speak()`): fires when `id_strength > 7`, `_last_emotion_intensity > 0.7`, and `conflict_index() > 0.6` simultaneously
  - **Behavioral effects during hijack**: SuperEgo influence reduced to 30% (`effective_sup = sup × 0.3`); response kind forced to `"impulsive"`; LLM temperature elevated; SuperEgo critique effectively suppressed
  - **Exit condition**: deactivates immediately when `emotion_intensity < 0.4`, or automatically after `LIMBIC_HIJACK_MAX_TURNS = 3` turns without re-trigger
  - Applied identically to both `Entelgia_production_meta.py` and `Entelgia_production_meta_200t.py`

- **Meta Output Refinement** — eliminated per-turn "SuperEgo critic skipped" log spam
  - `print_meta_state()` now uses a priority-ordered tag system:
    1. Limbic hijack active → `[META] Limbic hijack engaged — emotional override active`
    2. SuperEgo critique applied → `[SuperEgo critique applied; original shown in dialogue]`
    3. Otherwise → silent (no message)

- **`tests/test_limbic_hijack.py`** 🧪 — 15 unit tests covering all hijack scenarios
  - `TestLimbicHijackInitialState` — initial attribute defaults
  - `TestLimbicHijackActivation` — all-conditions-met vs. each threshold below boundary
  - `TestLimbicHijackExit` — intensity-drop exit, turn-cap exit, counter increment
  - `TestLimbicHijackResponseKind` — impulsive kind enforcement during hijack
  - `TestMetaOutputLogic` — all three meta output branches + priority ordering + no skipped-message spam

---

### Changed

- `Agent.speak()` in both production files: drives → temperature block now computes `effective_sup` before passing to temperature formula and `evaluate_superego_critique`, enabling hijack suppression without changing the public API or `drives` dict
- `print_meta_state()` in both production files: removed unconditional "skipped" branch; limbic hijack message takes priority over SuperEgo messages

---

## [2.6.0] - 2026-02-26

### Added

- **`entelgia/dialogue_metrics.py`** 📊 — Three quantitative dialogue-quality metrics (PR #111)
  - `circularity_rate` — fraction of turn-pairs with topic-signature Jaccard similarity ≥ threshold; measures how much the dialogue loops
  - `progress_rate` — forward steps per turn: topic shifts + synthesis markers + open-question resolutions
  - `intervention_utility` — mean circularity reduction in the post-Fixy window vs. pre-Fixy window
  - `circularity_per_turn()` — rolling time-series for graphing
  - `compute_all_metrics()` — runs all three metrics in one call
  - `if __name__ == "__main__"` demo block: prints all three metrics plus a per-turn ASCII circularity bar chart (PR #117)

- **`entelgia/ablation_study.py`** 🔬 — Reproducible 4-condition ablation study (PR #111)
  - `BASELINE` — fixed A-B round-robin with repetitive content
  - `DIALOGUE_ENGINE` — adds dynamic speaker selection and varied seeds
  - `FIXY` — adds need-based Fixy interventions every 6 turns
  - `DREAM` — adds dream-cycle energy consolidation
  - `run_ablation(turns, seed)` — fully reproducible across conditions
  - `print_results_table()` — formatted metrics table output
  - `plot_circularity()` — matplotlib line chart with ASCII fallback
  - `if __name__ == "__main__"` block for direct script execution (PR #115)

- **`entelgia/__init__.py`** updated exports: `run_ablation`, `print_results_table`, `plot_circularity`, and all metrics functions (PR #111)

- **`entelgia/context_manager.py`** — `if __name__ == "__main__"` demo block added; prints enriched prompt and relevant memories when run directly (PR #117)

- **`tests/test_dialogue_metrics.py`** 🧪 — 45 unit tests covering metrics correctness, edge cases, reproducibility, and inter-condition ordering guarantees (PR #111)
  - `TestDialogueMetricsDemo` class added: pins exact demo output values as regression tests (PR #121)
    - Exact metric values: Circularity Rate `0.022`, Progress Rate `0.889`, Intervention Utility `0.167`
    - Validates the full 10-value per-turn circularity series
    - Subprocess smoke-tests confirm script stdout output

- **`tests/test_demo_dialogue.py`** 🎭 — Live dialogue demo test (PR #127)
  - Canonical 10-turn Socrates / Athena / Fixy conversation on consciousness, free will, and identity
  - `test_full_dialogue_demo()` validates circularity, progress, and intervention utility metrics
  - Shows per-test metric summary with expected thresholds and ✓/✗ results (PR #138)

- **`tests/conftest.py`** — pytest session hooks (PR #127)

- **All test files** — `if __name__ == "__main__": pytest.main([__file__, "-v", "-s"])` entry point added for direct execution (PR #128)
  - `test_behavioral_rules.py`, `test_drive_correlations.py`, `test_drive_pressure.py`, `test_energy_regulation.py`, `test_long_term_memory.py`, `test_memory_security.py`, `test_memory_signing_migration.py`

- **All test files** — Unique per-test ASCII tables and bar charts (PR #139)
  - `_print_table(headers, rows, title)` — auto-sized bordered ASCII table per test
  - `_print_bar_chart(data_pairs, title)` — horizontal `█`-bar chart per test
  - Every test prints its own specific computed data (inputs, outputs, thresholds, pass/fail) with `-s`

- **Fluid drive dynamics** — `Config.drive_mean_reversion_rate` and `Config.drive_oscillation_range` (PR #102)
  - `drive_mean_reversion_rate: float = 0.04` — pulls Id/Superego back toward 5.0 each turn
  - `drive_oscillation_range: float = 0.15` — max random nudge applied to Id/Superego each turn
  - Prevents monotonic drift to extremes; `Agent.update_drives_after_turn` fluidity block applied after ego-erosion step

- **`DrivePressure`** 📈 — Per-agent urgency/tension scalar 0.0–10.0 (PR #107)
  - `compute_drive_pressure()` — weighted formula: conflict (45%) + unresolved questions (25%) + stagnation (20%) + energy depletion (10%) with α=0.35 smoothing
  - `_topic_signature(text)` — MD5-based stagnation detection
  - `_trim_to_word_limit(text, max_words)` — trims to last sentence boundary within limit
  - `_is_question_resolved(text)` — detects A)/B)/yes/no resolution patterns
  - `Agent` fields: `drive_pressure=2.0`, `open_questions`, `_topic_history`, `_same_topic_turns`
  - `speak()` injects directives at pressure ≥6.5 (concise) and ≥8.0 (decisive); word caps 120/80
  - `print_meta_state()` prints `Pressure:` line after Energy/Conflict
  - **`tests/test_drive_pressure.py`** 🧪 — 4 acceptance test classes (pressure rise, word caps, decay, determinism)

- **Forbidden opener phrases** — Agents no longer open with `"Recent thought"`, `"A recent thought"`, or `"I ponder"` (PR #104)
  - Extended `LLM_FORBIDDEN_PHRASES_INSTRUCTION` in both `context_manager.py` and `Entelgia_production_meta.py`
  - `FORBIDDEN_STARTERS` runtime list with post-processing strip in `speak()`
  - Cross-agent opener deduplication: injects `FORBIDDEN OPENER` for last other-agent's opening sentence

- **`Entelgia_production_meta_200t.py`** — CLI mode dispatch aligned with `Entelgia_production_meta.py` (PR #105)
  - `main()` entry point with `test` / `api` / `help` / default (`run_cli_long()`) modes
  - Module docstring updated to document all run modes

- **`scripts/validate_project.py`** v3.0 — `MarkdownConsistencyChecker` added (PR #106)
  - `check_classes_in_markdown()`, `check_config_attrs_in_markdown()`, `check_module_files_in_markdown()`, `check_stale_md_references()` via AST introspection
  - Validates all public classes, all `Config` fields, all `entelgia/*.py` modules, and stale symbol references
  - Overall project score improved: 88.3% → 90.8%

- **`scripts/validate_implementations.py`** 🔍 — Data-driven code vs. documentation cross-checker (PR #109)
  - `MarkdownExtractor` — scans README, ARCHITECTURE, SPEC, whitepaper; extracts backtick symbols and `.py` references
  - `CodeInspector` — AST-parses all Python sources; extracts classes, `Config` fields, module filenames, public functions
  - `ImplementationComparator` — reports discrepancies in both directions across 4 categories
  - Usage: `python scripts/validate_implementations.py`; exits `0` on full sync, `1` on discrepancies

- **`scripts/run_all_tests.py`** 🏃 — Single script to discover and run the full test suite (PR #123)
  - Delegates to `pytest` as a subprocess; extra arguments forwarded verbatim
  - Auto-installs `requirements.txt` and `.[dev]` extras before running (PR #124)
  - Detects and replaces incompatible `pyreadline` with `pyreadline3` on Windows (PR #125)

- **`scripts/research_statistics.py`** 📊 — Comprehensive measurable-factors table across all 4 ablation conditions (PR #136)
  - Reports 16 statistics: core dialogue metrics, dialogue characteristics (vocab diversity, TTR, etc.), energy-system metrics (avg energy, dream cycles, LTM size)
  - Usage: `python scripts/research_statistics.py`

- **`research.md`** 📄 — Reformatted as a proper structured scientific paper (PR #132)
  - Standard repo logo/title header; article metadata (Author, Affiliation, Date, Status, Keywords)
  - `##`/`###` headings; aligned markdown tables; Discussion as numbered subsections
  - Figures moved into corresponding subsections; References section with internal doc links
  - `README.md`: Added `🔬 Research Paper (research.md)` entry to Documentation section
  - `xychart-beta` Mermaid charts with vivid color palette for Figures 1–5 (PR #133, #134)
  - Expanded abstract (3 paragraphs), in-text numeric citations, and 12-entry peer-reviewed bibliography (PR #135)

### Fixed

- `tests/test_dialogue_metrics.py` produced no output when executed directly from the command line; added `if __name__ == "__main__": pytest.main([__file__, "-v"])` guard (PR #112)
- `entelgia/ablation_study.py` raised `ModuleNotFoundError` when imported as `entelgia.ablation_study`; `dialogue_metrics` was missing the `.py` extension (PR #113)
- `entelgia/ablation_study.py` raised `ImportError: attempted relative import with no known parent package` when executed directly; added try/except import fallback (relative imports first, then absolute via `sys.path`) and a `__main__` entry point (PR #115)

- **Agents echoing Superego voice** — Superego identity bleed fixed in three layers (PR #98)
  - `entelgia/enhanced_personas.py`: `format_persona_for_prompt` now uses `Current mode (as {name}):` to anchor agent identity
  - `entelgia/context_manager.py`: Drive label renamed `superego=` → `s_ego=` → `val=` to prevent LLM persona-switch
  - `Entelgia_production_meta.py` `speak()`: Safety-net `re.sub` strips `Superego:` / `Super-ego:` / `s_ego:` prefixes

- **Superego persona bleed and repeated first sentence** — PR #98 regression fixes (PR #101)
  - `val=` drive label (further renamed from `s_ego=`); identity-lock instruction added to both prompt paths: `"IMPORTANT: You are {agent_name}. Never adopt a different identity..."`
  - `_first_sentence()` helper; `FORBIDDEN OPENER` injection prevents agent from repeating its own or other agent's opening sentences

- **Fixy agent silently disabled when package installed** — `pyproject.toml` was missing `packages = ["entelgia"]`, causing `InteractiveFixy` import to fail silently (PR #103)

- **`python-dotenv` hard crash converted to soft warning** — `Entelgia_production_meta.py` no longer raises `ImportError` at module level when dotenv is absent; emits `warnings.warn()` instead, allowing all 217 tests to collect and run without the package (PR #129)

- **pytest INTERNALERROR on test collection** — `sys.exit(1)` in `Entelgia_production_meta.py` replaced with `raise ImportError(...)` (PR #126); `--continue-on-collection-errors` added to `pyproject.toml` addopts so 188+ tests still run when 2 files have missing-dependency errors

- **pytest crash on Windows Python 3.10+** — `pyreadline` (unmaintained, uses removed `collections.Callable`) replaced with `pyreadline3` (maintained fork); `requirements.txt` and `pyproject.toml` updated with `pyreadline3>=3.4.1; sys_platform == "win32"` (PR #125)

- **Noisy demo dialogue in test output** — `conftest.py` `pytest_terminal_summary` hook removed; `test_demo_dialogue.py` replaced `capsys.disabled()` full transcript with targeted per-test metric result printing (PR #138)

### Changed

- **`entelgia/context_manager.py`** and **`README.md`** — Docs corrected for accuracy (PR #106)
  - `config.max_output_words` removed (it is a module-level constant, not a `Config` field)
  - `llm_timeout` default corrected: `60` → `300` s
  - `memory_security.py` and undocumented `Config` fields added to README
  - `ARCHITECTURE.md`: class names added to Core Components; Session & API table added
  - `SPEC.md`: 5 missing output-path fields and new drive-fluidity fields added

- **Black formatting** applied across Python codebase (PR #100, #108, #110, #122, #137)
  - `Entelgia_production_meta.py`, `entelgia/context_manager.py`, `tests/test_drive_correlations.py`, `tests/test_drive_pressure.py`, `entelgia/__init__.py`, `entelgia/ablation_study.py`, `entelgia/dialogue_metrics.py`, `scripts/validate_implementations.py`, `scripts/research_statistics.py`

---

## [2.5.0] - 2026-02-21

## 🚀 Highlights

- **Energy-Based Agent Regulation System** — cognitive energy as a first-class resource
- **Personal Long-Term Memory System** — psychoanalytically-inspired memory regulation
- **Drive-aware cognition** — dynamic LLM temperature, ego-driven memory depth, superego second-pass critique
- **Coherent Freudian drive correlations** — high conflict now directly erodes ego, raises temperature, and amplifies energy drain (PR #92)
- **`Entelgia_production_meta_200t.py`** — guaranteed 200-turn dialogue without time-based stopping
- **Dialogue bug fixes** — third body calling to first body, double turn (agent answering twice in one turn), and pronoun issue all resolved
- **Super ego persona fix** — dialogue now displays the agent's original authentic voice; the superego rewrite is applied only for internal state updates (PR #95)
- **Output quality rules** — forbidden meta-commentary phrases removed at sentence level, dissent marker capped to exactly one sentence, hard word truncation removed (PR #96)
- New module exports, comprehensive tests, and a working demo
- Version bump from 2.4.0 → 2.5.0 across all documents and code

## 📝 Changes

### Added

- **`Entelgia_production_meta_200t.py`** 🔁 — 200-turn companion script
  - `MainScriptLong(MainScript)` — subclass that overrides only `run()`, replacing the
    time-based `while time < timeout` condition with a turn-count gate `while turn_index < max_turns`
  - `_NO_TIMEOUT_MINUTES = 9999` sentinel disables time-based stopping entirely
  - `run_cli_long()` entry point: `Config(max_turns=200, timeout_minutes=9999)`
  - All other behaviour (memory, emotions, Fixy interventions, dream cycles, session
    persistence) inherited from `MainScript` unchanged
  - Run via: `python Entelgia_production_meta_200t.py`
  - EntelgiaAgent.long_term_memory — persistent list that accumulates critical memories promoted from short-term memory during every dream cycle.
  - EntelgiaAgent._is_critical(memory) — relevance gate that determines whether a STM entry is substantive enough (contains at least one word ≥ 4 characters) to be promoted to long-term memory; designed to be overridden in subclasses for richer emotional / importance-based scoring.
  - Dream cycle STM → LTM promotion — _run_dream_cycle() now iterates conscious memory and copies every critical, relevant entry to long_term_memory (no duplicates). Existing integration and relevance-filtering  behavior is unchanged.
  - Eight new unit tests in tests/test_energy_regulation.py (TestEntelgiaAgentLTMPromotion) covering: initial LTM state, critical-entry promotion, trivial-entry exclusion, duplicate prevention, _is_critical edge cases, and subconscious-path promotion.
- **`entelgia/energy_regulation.py`** ⚡ — Energy-Based Agent Regulation System
  - **`FixyRegulator`** — Meta-level energy supervisor
    - `safety_threshold` (default: 35.0) — minimum energy threshold for safe operation
    - `check_stability(agent)` method: evaluates agent energy and applies regulation
      - Triggers a dream cycle (`DREAM_TRIGGERED`) when energy ≤ safety threshold
      - Stochastic hallucination-risk check (p=0.10) when energy drops below 60 %
        returns `HALLUCINATION_RISK_DETECTED`
      - Returns `None` when the agent is healthy
    - Class constants: `DEFAULT_SAFETY_THRESHOLD = 35.0`,
      `HALLUCINATION_RISK_PROBABILITY = 0.10`,
      `HALLUCINATION_RISK_ENERGY_CUTOFF = 60.0`
  - **`EntelgiaAgent`** — Agent with energy tracking and dream-cycle consolidation
    - `energy_level` starts at 100.0 and decreases 8–15 units per `process_step` call
    - `conscious_memory` (active inputs) and `subconscious_store` (pending consolidation)
    - Every agent is supervised by an embedded `FixyRegulator`
    - `process_step(text)` — appends input to memory, drains energy, triggers dream cycle
      when needed; returns `"RECHARGED_AND_READY"` or `"OK"`
    - `_run_dream_cycle()` — consolidates `subconscious_store` into `conscious_memory`,
      keeps only the last 5 entries, and restores `energy_level` to 100.0

- **`entelgia/long_term_memory.py`** 🧠 — Personal Long-Term Memory System
  - **`DefenseMechanism`** — classifies every memory write as repressed or suppressed
    - Repression: painful emotion (anger, fear, shame, guilt, anxiety) above 0.75 intensity
      or forbidden-keyword match → sets `intrusive = 1`
    - Suppression: mildly negative or low-intensity content → sets `suppressed = 1`
  - **`FreudianSlip`** — surfaces defended memories probabilistically
    - Samples up to 30 candidate memories; returns one at random (p per-call)
    - Skips memories that are not intrusive or suppressed
  - **`SelfReplication`** — promotes recurring-pattern memories to consciousness
    - Detects keywords (≥ 4 chars) appearing ≥ 2 times across candidate pool
    - Promotes up to 3 matching memories per call

- **`entelgia/__init__.py`** package exports updated
  - `FixyRegulator`, `EntelgiaAgent` exported from `energy_regulation`
  - `DefenseMechanism`, `FreudianSlip`, `SelfReplication` exported from `long_term_memory`

- **`tests/test_energy_regulation.py`** 🧪 — 18 unit tests
  - `TestFixyRegulatorDefaults` — threshold and constant validation
  - `TestFixyRegulatorCheckStability` — dream trigger, recharge, hallucination risk
  - `TestEntelgiaAgentInit` — initial state, regulator propagation
  - `TestEntelgiaAgentProcessStep` — energy drain, memory append, return values
  - `TestEntelgiaAgentDreamCycle` — consolidation and subconscious clearing
  - `TestPackageImports` — package-level import checks

- **`tests/test_long_term_memory.py`** 🧪 — comprehensive tests for all three classes
  - `TestDefenseMechanismRepression` / `TestDefenseMechanismSuppression`
  - `TestFreudianSlip` — slip surface and empty-pool edge cases
  - `TestSelfReplication` — keyword promotion and threshold logic
  - `TestPackageImports` — package-level import checks

- **`examples/demo_energy_regulation.py`** 📖 — 8-turn Socrates demo
  - Shows energy depletion and automatic dream-cycle recovery
  - Prints turn-by-turn energy level and status

- **ROADMAP.md** 🗺️ — project roadmap added to repository
- Project logo added to all markdown files

- **`tests/test_drive_correlations.py`** 🧪 — 18 unit tests across 4 classes (PR #92)
  - `TestConflictIndex` — boundary value tests for `conflict_index()`
  - `TestEgoErosion` — magnitude and monotonicity of ego erosion under conflict
  - `TestTemperatureConflictCorrelation` — temperature rises with conflict index
  - `TestEnergyDrainScaling` — conflict-scaled drain and cap behavior

## 🔄 Changed

- **`Entelgia_production_meta.py`** — Drive-aware cognition (PR #75)
  - **Dynamic LLM temperature** derived from Freudian drive values:
    ```
    temperature = max(0.25, min(0.95, 0.60 + 0.03 * (id - ego) - 0.02 * (superego - ego)))
    ```
    Higher `id_strength` → more creative/exploratory; higher `superego_strength` → more constrained.
  - **Superego second-pass critique**: when `superego_strength ≥ 7.5`, the initial response is
    fed back to the LLM at `temperature=0.25` with a principled rewrite prompt acting as an
    internal governor.
  - **Ego-driven memory retrieval depth** replaces fixed `limit=4` / `[-6:]`:
    ```
    ltm_limit = max(2, min(10, int(2 + ego / 2 + sa * 4)))   # long-term
    stm_tail  = max(3, min(12, int(3 + ego / 2)))             # short-term
    ```
    Agents with stronger ego / self-awareness pull more context and stabilise faster after reset.
  - **Output artifact cleanup + word limit enforcement** after all validate/critique passes:
    - Strips agent name/pronoun prefix echoed by LLM (e.g. `"Socrates (he): "`)
    - Removes gender script tags: `(he):`, `(she)`, `(they)`
    - Removes stray scoring markers: `(5)`, `(4.5)`, etc.
    - Truncates to `MAX_RESPONSE_WORDS = 150`

- **`Entelgia_production_meta.py`** — Coherent Freudian drive correlations (PR #92)
  - **Conflict → Ego erosion** (`update_drives_after_turn`): captures `pre_conflict = |ide - ego| + |sup - ego|` before updating drives; when it exceeds 4.0, Ego is eroded proportionally:
    ```python
    if pre_conflict > 4.0:
        ego = max(0.0, ego - 0.03 * (pre_conflict - 4.0))
    ```
  - **Conflict → Temperature/Tone** (`speak`): adds a conflict component to the LLM temperature formula so high drive imbalance produces a more volatile, impulsive tone:
    ```python
    temperature = 0.60 + 0.03*(ide-ego) - 0.02*(sup-ego) + 0.015*self.conflict_index()
    ```
  - **Conflict → Energy drain** (`update_drives_after_turn`): replaces flat random drain with conflict-scaled drain, capped at `2 × energy_drain_max`:
    ```python
    drain = random.uniform(CFG.energy_drain_min, CFG.energy_drain_max) + 0.4 * pre_conflict
    drain = min(drain, CFG.energy_drain_max * 2.0)
    ```

- **`Entelgia_production_meta.py` / `entelgia/context_manager.py`** — Output quality rules (PR #96)
  - **Dissent marker capped to exactly one sentence** — `_behavioral_rule_instruction` (Athena, `dissent_level ≥ 3.0`) changed from `"at least one sentence"` to `"exactly one sentence"`.
  - **Forbidden meta-commentary phrases** — Added `FORBIDDEN_PHRASES` (`"In our dialogue"`, `"We learn"`, `"Our conversations reveal"`) and `LLM_FORBIDDEN_PHRASES_INSTRUCTION` to both `Entelgia_production_meta.py` and `entelgia/context_manager.py`.
    - `validate_output()` now performs sentence-level removal of any sentence containing a forbidden phrase (regex split on `.!?`).
    - `LLM_FORBIDDEN_PHRASES_INSTRUCTION` is injected into both prompt-building paths (`_build_compact_prompt` / `_format_prompt`) to prevent generation up-front.
  - **Hard word truncation removed from `speak()`** — the post-processing `# Enforce 150-word limit` block (word-split + `…` append) is removed; response length is already governed by `LLM_RESPONSE_LIMIT` in the prompt.

- Package `__version__` bumped to **2.5.0**
- `pyproject.toml` version bumped to **2.5.0**
- All documentation version references updated to **v2.5.0**
- `entelgia/energy_regulation.py` and `entelgia/long_term_memory.py` added as
  first-class modules in the `entelgia` package
- Applied **Black** code formatting across the entire Python codebase (PR #69)

## 🐛 Fixed

- **`Entelgia_production_meta.py`** — Super ego character role fix (PR #95)
  - **Super ego persona removed from critique prompt** — `"You are the agent's Superego."` was inadvertently assigning a dialogue character role to the rewrite call, causing agents with high `superego_strength` to speak as the super ego character instead of themselves. Replaced with a plain rewrite instruction: `"Rewrite the following response to be more principled…"`.
  - **Original agent response preserved in dialogue** — `speak()` now saves `original_out` before the superego critique pass. The rewrite is still executed and used for internal state updates (emotion inference + drive recalibration), but `out` is restored to `original_out` before returning, so the dialogue always displays what the agent originally said.
  - **Meta display tag updated** — `[SuperEgo rewrite applied]` → `[SuperEgo critique applied; original shown in dialogue]` to reflect the actual behaviour.

- **`Entelgia_production_meta.py`** — Dialogue engine bug fixes (PR #74)
  - **Third body calling to first body** (broken speaker alternation after Fixy intervention):
    after Fixy (the third agent) intervened, `last_speaker` was mistakenly resolved as the
    first body (Socrates), causing Socrates to speak twice in a row. Fixed by scanning
    `dialog` backwards for the last *non-Fixy* turn when determining the next speaker.
  - **Double turn — agent answering 2 times in 1 turn** (duplicate Fixy output): the legacy
    scheduled `fixy_check` (every N turns) fired *in addition to* the `InteractiveFixy`
    handler, producing two Fixy responses in a single turn. The legacy scheduled path has since
    been fully removed (PR #87); Fixy now intervenes exclusively via `InteractiveFixy`.
  - **Pronoun issue** (pronoun leakage from LLM response): `speak()` now strips the agent
    header prefix that the LLM echoes from its own prompt (e.g. `"Socrates (he): …"`), so
    pronouns never appear in output when `show_pronoun=False`.
  - **Smart text truncation** in `_format_prompt`: dialog turns capped at 200 chars,
    thoughts at 150 chars, memories at 200 chars — all cut at the last word boundary
    (no mid-word splits).

## 🧹 Clean Config & Need-Based Fixy (PR #87)

### Removed
- **Dead `Config` fields** — `fixy_every_n_turns`, `max_prompt_tokens`, `log_level`, and
  `dream_keep_memories` were defined but never read anywhere in the codebase; all removed.
- **`ObserverCore` / `FixyReport`** — legacy observer classes and the `fixy_check()` method
  are removed; Fixy now intervenes exclusively via `InteractiveFixy.should_intervene()`.
- **Legacy scheduled Fixy path** — the `elif not self.interactive_fixy and turn % fixy_every_n_turns == 0`
  block has been deleted from both `Entelgia_production_meta.py` and `Entelgia_production_meta_200t.py`.

### Changed
- **`Config.energy_safety_threshold`** — was defined but silently ignored; now actively
  forces a dream cycle for each agent whose `energy_level` drops to or below the threshold
  on every turn.
- **`ARCHITECTURE.md`** — `energy_safety_threshold` description updated to reflect the
  direct dream-cycle trigger instead of the old "passed to `FixyRegulator`" wording.
- **`TROUBLESHOOTING.md`** — circular-reasoning section rewritten: removed the
  `fixy_every_n_turns` tuning step; Fixy is now described as need-based.
- **`SPEC.md` appendix** — removed `fixy_every_n_turns` and `dream_keep_memories` entries.
- **`whitepaper.md`** — removed `fixy_every_n_turns` entry from Agent Behavior config table.
- **`README.md`** — removed `fixy_every_n_turns` example from the configuration snippet.
- **`scripts/validate_project.py`** — updated class-name patterns from `ObserverCore` to
  `InteractiveFixy`; removed `fixy_every_n_turns` config check; reduced `total_checks` from 5 to 4.

## 🛑 Breaking Changes
*None* — all changes are backward compatible

---

## [2.4.0] - 2026-02-18

# Entelgia v2.4.0 Release Notes

## 🚀 Highlights

- Major refactor and documentation improvements
- Project structure update
- Memory management tool improvements
- Expanded FAQ & troubleshooting
- Updated whitepaper and architecture overview
- English documentation standard

## 📝 Changes

- clear_memory.py utility
- modular project reorganization
- FAQ updates
- demo and example updates
- whitepaper, architecture docs enriched

## 🛑 Breaking Changes
*None* (All changes are backwards compatible)

## 💡 Upgrade Instructions
- See ARCHITECTURE.md
- Use updated clear_memory.py

## 📋 Contributors
- @sivanhavkin

### Added
- **Memory Management Utility** 🗑️
  - New `clear_memory.py` script for deleting stored memories
  - Interactive menu with three deletion options:
    - Delete short-term memory (JSON files)
    - Delete long-term memory (SQLite database)
    - Delete all memories (both types)
  - Safety features:
    - Confirmation prompt before deletion
    - Shows count of files/entries before deletion
    - Cannot be undone warning
  - Use cases: reset experiments, privacy concerns, testing, storage management
  - Documentation added to README.md with usage examples

### Changed
- Reorganized project structure into modular subdirectories
- Moved core files from repository root into dedicated folders
- Improved repository layout for clarity and future scalability
- Rewrite and rename demo examples to Entelgia_demo
  
### Documentation
- Removed all foreign language content to standardize the repository to English only.
- Added comprehensive troubleshooting documentation.
- Added FAQ - 513-line FAQ covering common questions.
- Added Memory Management section to README.md
- Added detailed ARCHITECTURE.md describing Entelgia's system architecture.
- whitepaper updated to reflect all recent changes.
---

## [2.3.0] - 2026-02-16

### Installation & Documentation Improvements
- Added a new `install.py` script for automated setup: installs all Python dependencies, creates the `.env` file, prompts for API key, and checks/installs Ollama (where supported).
- Refactored README: unified all installation steps into a single "Quick Install" section, including a direct link to `install.py`.
- Removed duplicate/manual install instructions and clarified the process for installing Ollama, with consistent formatting and messaging.
### Changed
- Removed all Unicode icons (such as ✔, ✓, 🚨, etc.) from logger messages in all main execution files and test/demo scripts.
  - This improves compatibility with Windows consoles and environments that do not support extended Unicode in standard output.
- Logger outputs are now ASCII-only for maximum readability on all platforms.
- No changes made to documentation, README, or markdown files – decorative icons remain.

### Fixed
- UnicodeEncodeError warnings no longer appear when running on Windows terminal.

---


## [2.2.0] - 2026-02-14

### ➕ Added

- **Pronoun Support** 🏷️
  - Official support for gender pronouns (he/she) for agents
  - `show_pronoun` flag in Config (default: False for backwards compatibility)
  - `is_global_show_pronouns` global control variable in enhanced_personas module
  - Pronoun data added to personas: Socrates (he), Athena (she), Fixy (he)
  - Uniform display control in user and LLM prompts
  - When enabled, pronouns appear as "AgentName (pronoun):" in prompts
  - Gender-neutral by default to maintain inclusive conversation style

- **Response Handling Without Truncation** ✨
  - All truncation/cutting limits on agent responses removed
  - Explicit LLM instruction added to prompts: "Please answer in maximum 150 words"
  - All responses displayed in full without any cutting or truncation
  - Role-playing maintains 150-word request for conciseness without enforced truncation
  - `validate_output()` function performs sanitization only (removes control chars, normalizes newlines)
  - LLM naturally controls response length based on prompt guidance
  - Ensures complete, coherent responses without mid-sentence cuts

 - **Enhanced Dialogue Module** 🎭
   - `entelgia/` package with modular dialogue components
   - `dialogue_engine.py` - Dynamic speaker selection & seed generation
   - ` enhanced_personas.py` - Rich character definitions (Socrates, Athena, Fixy)
   - `context_manager.py` - Smart context enrichment with sentence boundaries
   - `fixy_interactive.py` - Need-based interventions (vs scheduled)
   - `__init__.py` - Clean package API
  
- **Dialogue Features** 💬
  - Dynamic speaker selection (prevents 3+ consecutive turns)
  - 6 seed generation strategies:
    - `introduce_analogy` - Metaphorical thinking
    - `constructive_disagree` - Respectful challenge
    - `explore_implication` - Consequence analysis
    - `question_assumption` - Foundational inquiry
    - `meta_reflect` - Self-awareness
    - `agree_and_expand` - Collaborative building
  - Rich context with 8 dialogue turns, 6 recent thoughts, 5 memories
  - Context enrichment with intelligent text management
  - Fixy interventions based on need (circular reasoning, repetition, confusion)

- **Testing & Demo** 🧪
  - `test_enhanced_dialogue.py` - 5 comprehensive tests for dialogue system
  - `demo_enhanced_dialogue.py` - 10-turn demonstration script
  - All tests passing (5 dialogue + 19 security = 24 total)

- **Response Length Control** ⚡
  - Explicit 150-word limit instruction added to all LLM prompts
  - `validate_output()` function for sanitization (no truncation)
  - New Config options:
    - `max_output_words` (default: 150) - Used in LLM prompt instruction
  - Responses displayed in full without truncation
  - LLM controls response length naturally based on prompt guidance

### 🐛 Fixed

- Fixed `CFG` global initialization in `MainScript.__init__`
- Resolves `'NoneType' has no attribute 'data_dir'` error
- Demo scripts now work without `run_cli()` wrapper
- Added `global CFG` declaration to ensure proper initialization

### 🔄 Changed

- **Architecture** 🏗️
  - Migrated from monolithic to modular dialogue system
  - Legacy ping-pong alternation preserved as fallback
  - Enhanced mode auto-detected when `entelgia` package available
  
- **Personas** 🎭
  - Expanded from short strings to rich dataclass definitions
  - Added traits, speech patterns, intervention triggers
  - Socrates: Deconstructive, dialectic method
  - Athena: Integrative, wisdom-seeking
  - Fixy: Pattern-matching, meta-cognitive

- **Performance** ⚡
  - Reduced predictability in dialogue flow
  - Smarter context management (fewer token waste)
  - Fixy only speaks when needed (not every N turns)

- **Timeouts & Performance** ⚡ (v2.2.0-unreleased)
  - Reduced `llm_timeout` from 600 seconds (10 minutes) to 60 seconds (1 minute)
  - Shorter maximum wait times for LLM responses
  - Faster failure detection when LLM is unresponsive
  - Better user experience with more predictable response times

- **Gender-Neutral Output** 🌐 
  - Removed gender language tracking initialization
  - Cleaner dialogue output without gender pronouns
  - More inclusive and neutral conversation style

### 📝 Documentation

- Added version notes to all modified files indicating unreleased features
- Added comprehensive comments explaining pronoun feature
---

## [2.1.1] - 2026-02-13

### Fixed
- Fixed pyproject.toml configuration issues
- Applied Black code formatting across all files
- Resolved CI/CD pipeline failures

### Infrastructure
- All tests passing on 6 platforms
- Code quality checks now green
- Build verification successful
- Latest official release marked as v2.1.1 throughout codebase

---

## [2.1.0] – 2026-02-13 – **Testing & Community Infrastructure - Superseded**

This release adds a comprehensive testing infrastructure, build system configuration, and community contribution tools without changing core functionality.

### Added

- **Testing Suite** 🧪
  - Complete pytest configuration in pyproject.toml
  - tests/__init__.py package initialization
  - conftest.py with reusable fixtures
  - test_memory_security.py with 18+ unit tests
  - Test coverage for HMAC-SHA256 signature validation

- **Build System** ⚙️
  - pyproject.toml with full project metadata
  - Dependency management (runtime and dev dependencies)
  - pytest, black, flake8, mypy configurations
  - Project URLs and classifiers

- **GitHub Templates** 🤝
  - Bug report template (.github/ISSUE_TEMPLATE/bug_report.md)
  - Feature request template (.github/ISSUE_TEMPLATE/feature_request.md)
  - Pull request template (.github/ISSUE_TEMPLATE/PULL_REQUEST_TEMPLATE.md)

- **API Documentation** 📚
  - Comprehensive API docs (docs/api/README.md)
  - Quick start guide with examples
  - Python and cURL usage examples
  - Error handling documentation

### Fixed

- Fixed file naming conventions (README.md, requirements.txt lowercase)
- Refactored memory security tests into organized classes

### Notes

This is a quality-of-life release focused on developer experience and project infrastructure. All core v2.0.1 functionality is preserved.

---

## [2.0.1] – 2026‑02‑13 – **Production Final - Superseded**

This version finalises the 2.x production rewrite with additional **memory security measures** and licence updates. It retains all features from the 2.0.0 release and adds cryptographic protection for stored memories.

### ➕ Added
- ✅ **HMAC‑SHA256 signatures** on all memory entries, enabling tamper detection and validation.
- ✅ **Automatic forgetting** of memory entries when signature validation fails, ensuring corrupted or tampered memories are not retained.
- ✅ **Secret key management** via environment variables, allowing secure configuration of cryptographic keys without hard‑coding secrets.
- ✅ **Unit tests** to validate signature creation and verification logic.
- ✅ **Windows Unicode encoding fix** to improve emoji and character support.
- ✅ **Standard MIT License** replacing the custom Entelgia ethical licence.

### 🔄 Changed
- Updated the README licence section to reflect the adoption of the **MIT License**.

### 📝 Notes
> This version is considered the **final release** of the 2.x line at the time of publication.

### ⚠️ Known Limitations
- Requires **8 GB or more of RAM** and a powerful CPU; may experience Ollama HTTP timeouts on low‑resource machines.

---

## [2.0.0] – 2026‑02‑11 – **Production V2.0 - Superseded**

Version 2.0.0 represents a **breaking change** and a complete rewrite of the project with a modular, production‑ready architecture. It introduces a multitude of new capabilities, improved performance, and a robust foundation for future development.

### ⚠️ Breaking Changes
- The entire architecture has been rewritten. Existing integrations and extensions targeting the 1.x line will need to be updated.

### ➕ Added
- 🤖 **Multi‑agent dialogue system** with three agents: **Socrates**, **Athena**, and an observer/fixer agent (**Fixy**). Agents interact and reason with each other to produce more nuanced responses.
- 💾 **Persistent memory** comprising short‑term memory (JSON, FIFO trimming) and long‑term memory (SQLite) unified for conscious and subconscious storage.
- 🧠 **Psychological drives** inspired by Freud (id, ego and superego dynamics) influence decision making and responses.
- 😊 **Emotion tracking** and importance scoring, including intensity metrics for experiences.
- 🌙 **Dream cycles** that periodically promote memories from short‑term to long‑term storage, consolidating context over time.
- ⚡ **Least Recently Used (LRU) cache** yielding approximately **75% cache hit rates** and reducing repeated LLM calls.
- 🌐 **REST API** built with FastAPI, exposing endpoints for agent interaction and memory management.
- ✅ **Unit tests** (pytest) covering core functionality (nine tests in total).
- ⏱️ **10‑minute auto‑timeout** to prevent runaway conversation loops.
- 🔒 **PII redaction** and privacy protection integrated into memory storage and logs.
- 🔁 **Error handling with exponential backoff**, improving resilience against network or model failures.
- 📊 **Structured logging** to console and file for easier debugging and observability.

### ⚡ Performance
- 📉 **50% reduction in LLM calls** thanks to caching of repeated queries.
- 📉 **70% reduction in token usage** by compressing prompts and responses.
- ⚡ **2‑3× faster response times** through parallel agent execution and caching.

### 🏗️ Architecture
- Approximately **1,860 lines of production code** with **25+ classes** and **50+ documented functions**, all with full type hints.
- **Modular core system** composed of Memory, Emotion, Language, Conscious, Behavior, and Observer modules, promoting separation of concerns and extensibility.

### ⚠️ Known Limitations
- Requires **8 GB or more of RAM** and a powerful CPU; may experience Ollama HTTP timeouts on low‑resource machines.

### 📝 Notes
> This release lays the foundation for all future 2.x versions and is the **first production‑ready version** of Entelgia. All subsequent changes are expected to be backward compatible within the 2.x series.

---

## [1.5.1] – 2026‑02‑08 – **V1.5 Hotfix** 🔧

This hotfix addresses a critical model update without introducing new features. It builds on top of version 1.5.0.

### 🐛 Fixed
- Updated Ollama models to **phi3:latest**, improving generation quality and stability.

### 📝 Notes
> Users should update to this version if they rely on the Ollama backend.

---

## [1.5.0] – 2026‑02‑07 – **V1.5**

Version 1.5.0 introduced the first iteration of the multi‑agent system and began the transition toward the architecture that would later be refined in 2.0.0.

### ➕ Added
- 🤖 **Multi‑agent conversation loop** featuring Socrates and Athena.
- 👁️ **Observer/fixer agent (Fixy)** to monitor conversations and offer perspective shifts or terminate loops when necessary.
- 🔌 **Ollama integration** with separate per‑agent models for Socrates and Athena.
- 💾 **Per‑agent short‑term memory** stored as JSON with FIFO trimming.
- 💾 **Unified long‑term memory** in SQLite for conscious and subconscious storage.
- 😊 **Emotion tracking** including intensity metrics for each agent.
- 🌍 **Agent‑controlled language selection**, allowing agents to choose the appropriate language for responses.
- 🌙 **Dream cycle functionality** to promote memories from short‑term to long‑term storage every N turns.
- 📊 **CSV logging** of conversation data with an optional GEXF knowledge graph export.
- 🔄 **Safe auto‑patching** of the codebase and version‑tracking snapshots to monitor changes between runs.
- 🚀 Added run script **entelgia_pitch1.5.py** for launching the system.

### 📋 Requirements
- Python 3.10 or higher.
- Ollama running locally at `http://localhost:11434`.
- Installation of the `requests` and `colorama` Python packages.

### 📝 Notes
> This version marked a significant step toward a more interactive and modular system but was still research‑oriented and lacked many of the production enhancements introduced in 2.0.0.

---

## [1.0.0] – 2026‑02‑06 – **Initial Public Core** 🎯

The first public release of the Entelgia core. Although not yet production‑ready, it provided a proof‑of‑concept for moral reasoning and conflict‑based self‑regulation.

### ➕ Added
- 📄 **Single‑file architecture** (`entelgia_unified.py`) encapsulating the entire system.
- 🤖 **Two persistent agents** (Socrates and Athena) with evolving internal states.
- 🧠 **Freud‑inspired internal conflict dynamics** guiding agent behaviour.
- 💾 **Long‑term memory** implemented with SQLite.
- 👁️ **Observer agent (Fixy)** to detect loops and prompt perspective shifts.
- 🔌 **Optional local LLM integration** via Ollama, with fallback to a deterministic mock mode if Ollama is unavailable.

### 📝 Notes
> This release was a research‑grade prototype focusing on moral reasoning and internal conflict rather than rule‑based safety filters.

> The code supporting this version was merged into the main branch on **2026‑01‑23**. The version tag v1.0.0 was later published on **2026‑02‑06**.

### 📋 Requirements
- Python 3.10 or higher.
- Ollama running locally (default `http://localhost:11434`).
- Installation of the `requests` and `colorama` Python packages.

---

## [0.4.0‑experimental] – 2026‑02‑07 – **Experimental Preview** ⚗️

This pre‑release demonstrated the full multi‑agent architecture running end‑to‑end. It was intentionally resource‑intensive and is **not suitable for production use**.

### ➕ Added
- 🤖 **Full multi‑agent architecture** with Socrates, Athena and Fixy.
- 🧪 **Experimental self‑modelling** and cognitive depth features, which may surface meta‑instructions or internal rules during execution.

### ⚠️ Known Limitations
- Requires **16 GB or more of RAM** and a powerful CPU; may experience Ollama HTTP timeouts on low‑resource machines.
- **Not production‑ready**; intended for researchers, system thinkers, experimental AI developers and anyone interested in cognitive depth.

### 📝 Notes
> Although tagged as version 0.4.0‑experimental, this release was published on the same day as v1.5.0 and should be considered a separate research preview rather than part of the stable release series.

---

**Legend:**
- 🎉 Major milestone
- 🚀 Production release
- ➕ Added feature
- 🔄 Changed feature
- 🐛 Bug fix
- ⚠️ Breaking change or warning
- 📝 Notes
- 🔧 Hotfix
- ⚗️ Experimental

---

## 📊 Quick Reference

- ✅ **Latest stable:** v2.8.1
- 🚧 **Next release:** TBD
- 📅 **Release schedule:** Bi-weekly minor, as-needed patches
- 📖 **Versioning:** [Semantic Versioning 2.0](https://semver.org/)

---

## 📊 Version History Summary

| Version | Release Date | Type | Status | Description |
|---------|--------------|------|--------|-------------|
| **v2.8.1** | 2026-03-07 | Patch | ✅ **Current** | Version bump across all documentation |
| **v2.8.0** | 2026-03-06 | Minor | ⚠️ Superseded | Web Research Module — Fixy-triggered external knowledge pipeline |
| **v2.7.0** | 2026-03-03 | Minor | ✅ **Stable** | Limbic hijack state, meta output refinement |
| **v2.6.0** | 2026-02-26 | Minor | ✅ **Stable** | Dialogue metrics, ablation study, drive pressure & research tools |
| **v2.5.0** | 2026-02-21 | Minor | ✅ **Stable** | Energy regulation, long-term memory & coherent drive correlations |
| **v2.4.0** | 2026-02-18 | Minor | ⚠️ Superseded | Documentation & structure improvements |
| **v2.3.0** | 2026-02-16 | Minor | ⚠️ Superseded | Installation improvements |
| **v2.2.0** | 2026-02-14 | Minor | ⚠️ Superseded | Enhanced dialogue system |
| **v2.1.1** | 2026-02-13 | Patch | ⚠️ Superseded | Bug fixes + formatting |
| v2.1.0 | 2026-02-13 | Minor | ⚠️ Superseded | Testing infrastructure |
| v2.0.01 | 2026-02-13 | Major | ⚠️ Superseded | Production rewrite |
| v1.5 | 2026-01-31 | Minor | 📦 Legacy | Multi-agent v1.5 |
| v1.5-HOTFIX | 2026-01-31 | Patch | 📦 Legacy | Model update |
| v1.0.0 | 2026-01-23 | Major | 📦 Legacy | Initial public release |
| v0.4.0-exp | 2026-02-06 | Experimental | 🧪 Archive | Research only |

### Status Legend
- 🚧 **Coming Soon** - In development
- ✅ **Current** - Latest stable release, recommended
- ⚠️ **Superseded** - Working but upgrade recommended
- 📦 **Legacy** - Old architecture, no longer maintained
- 🧪 **Archive** - Experimental, not for production

---

## 🔄 Versioning Guidelines

This project follows [Semantic Versioning 2.0.0](https://semver.org/):


























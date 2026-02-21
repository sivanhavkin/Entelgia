<div style="display: flex; align-items: center; justify-content: space-between;">
  <img src="Assets/entelgia-logo.png" alt="Entelgia Logo" width="120" style="margin: 0;"/>
  <h1 style="flex-grow: 1; text-align: center; font-size: 2.5em; font-weight: bold; margin: 0;">📋 Changelog</h1>
  <div style="width: 120px;" aria-hidden="true"></div>
</div>

All notable changes to this project will be documented in this file. The format is based on [Keep a Changelog](https://keepachangelog.com/) and this project adheres to [Semantic Versioning](https://semver.org/).

---

## [2.5.0] - 2026-02-21

## 🚀 Highlights

- **Energy-Based Agent Regulation System** — cognitive energy as a first-class resource
- **Personal Long-Term Memory System** — psychoanalytically-inspired memory regulation
- **Drive-aware cognition** — dynamic LLM temperature, ego-driven memory depth, superego second-pass critique
- **Coherent Freudian drive correlations** — high conflict now directly erodes ego, raises temperature, and amplifies energy drain (PR #92)
- **`entelgia_production_long.py`** — guaranteed 200-turn dialogue without time-based stopping
- **Dialogue bug fixes** — third body calling to first body, double turn (agent answering twice in one turn), and pronoun issue all resolved
- New module exports, comprehensive tests, and a working demo
- Version bump from 2.4.0 → 2.5.0 across all documents and code

## 📝 Changes

### Added

- **`entelgia_production_long.py`** 🔁 — 200-turn companion script
  - `MainScriptLong(MainScript)` — subclass that overrides only `run()`, replacing the
    time-based `while time < timeout` condition with a turn-count gate `while turn_index < max_turns`
  - `_NO_TIMEOUT_MINUTES = 9999` sentinel disables time-based stopping entirely
  - `run_cli_long()` entry point: `Config(max_turns=200, timeout_minutes=9999)`
  - All other behaviour (memory, emotions, Fixy interventions, dream cycles, session
    persistence) inherited from `MainScript` unchanged
  - Run via: `python entelgia_production_long.py`
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

- Package `__version__` bumped to **2.5.0**
- `pyproject.toml` version bumped to **2.5.0**
- All documentation version references updated to **v2.5.0**
- `entelgia/energy_regulation.py` and `entelgia/long_term_memory.py` added as
  first-class modules in the `entelgia` package
- Applied **Black** code formatting across the entire Python codebase (PR #69)

## 🐛 Fixed

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
  block has been deleted from both `Entelgia_production_meta.py` and `entelgia_production_long.py`.

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

- ✅ **Latest stable:** v2.5.0
- 🚧 **Next release:** TBD
- 📅 **Release schedule:** Bi-weekly minor, as-needed patches
- 📖 **Versioning:** [Semantic Versioning 2.0](https://semver.org/)

---

## 📊 Version History Summary

| Version | Release Date | Type | Status | Description |
|---------|--------------|------|--------|-------------|
| **v2.5.0** | 2026-02-21 | Minor | ✅ **Current** | Energy regulation, long-term memory & coherent drive correlations |
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


























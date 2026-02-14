# 📋 Changelog

All notable changes to this project will be documented in this file. The format is based on [Keep a Changelog](https://keepachangelog.com/) and this project adheres to [Semantic Versioning](https://semver.org/).

---

## [Unreleased] - v2.2.0

These are changes that have been committed to the repository but have not yet been packaged as a new release. When a new version is tagged, the contents of this section should be moved under the appropriate version heading below.

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
- ✅ **Windows Unicode encoding fix** to improve emoji and Hebrew character support.
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

- ✅ **Latest stable:** v2.1.1
- 🚧 **Next release:** v2.2.0 (Enhanced Dialogue - coming soon)
- 📅 **Release schedule:** Bi-weekly minor, as-needed patches
- 📖 **Versioning:** [Semantic Versioning 2.0](https://semver.org/)

---

## 📊 Version History Summary

| Version | Release Date | Type | Status | Description |
|---------|--------------|------|--------|-------------|
| **v2.2.0** | TBD | Minor | 🚧 **Coming Soon** | Enhanced dialogue system |
| **v2.1.1** | 2026-02-13 | Patch | ✅ **Current** | Bug fixes + formatting |
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







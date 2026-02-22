<div style="display: flex; align-items: center; justify-content: space-between;">
  <img src="Assets/entelgia-logo.png" alt="Entelgia Logo" width="120" style="margin: 0;"/>
  <h1 style="flex-grow: 1; text-align: center; font-size: 2.5em; font-weight: bold; margin: 0;">🧠 Entelgia</h1>
  <div style="width: 120px;" aria-hidden="true"></div>
</div>

[![Python](https://img.shields.io/badge/Python-3.10+-blue)](https://docs.python.org/3.10/)
[![Status](https://img.shields.io/badge/Status-Research%20Hybrid-purple)](#-project-status)
[![Tests](https://img.shields.io/badge/tests-209%20passed-brightgreen)](https://github.com/sivanhavkin/Entelgia/actions)
[![License](https://img.shields.io/badge/license-MIT-green)](LICENSE)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://black.readthedocs.io/en/stable/)
[![Build Status](https://github.com/sivanhavkin/Entelgia/actions/workflows/ci.yml/badge.svg)](https://github.com/sivanhavkin/Entelgia/actions)
[![Flake8](https://img.shields.io/badge/lint-flake8-green)](https://flake8.pycqa.org/)  
[![Last Commit](https://img.shields.io/github/last-commit/sivanhavkin/Entelgia)](https://github.com/sivanhavkin/Entelgia/commits/main)
[![Maintenance](https://img.shields.io/maintenance/yes/2026)](https://github.com/sivanhavkin/Entelgia)
[![Docs](https://img.shields.io/badge/docs-online-blue.svg)](https://github.com/sivanhavkin/Entelgia/tree/main/docs)

---

## Entelgia — A Dialogue-Governed Multi-Agent AI Architecture

**Entelgia** is an experimental multi-agent AI architecture designed to explore persistent identity, internal conflict dynamics, and emergent behavioral regulation through shared long-term memory and structured dialogue.

  Unlike stateless chatbot systems, Entelgia maintains an evolving internal state across sessions, enabling continuity of identity, memory persistence, and more coherent reflective behavior over time.


---

## 📚 Documentation

* 📘 **[Full Whitepaper](whitepaper.md)** - Complete architectural and theoretical foundation
* 📄 **[System Specification (SPEC.md)](./SPEC.md)** - Detailed architecture specification
* 🏗 **[Architecture Overview (ARCHITECTURE.md)](ARCHITECTURE.md)** - High-level and component design
* 🗺️ **[Roadmap (ROADMAP.md)](ROADMAP.md)** - Project development roadmap and future plans
* 📖  [Entelgia Demo(entelgia_demo.py)](https://github.com/sivanhavkin/Entelgia/blob/main/entelgia_demo.md) - See the system in action
* ❓ **[FAQ](FAQ.md)** - Frequently asked questions and answers
* 🔧 **[Troubleshooting Guide](TROUBLESHOOTING.md)** - Common issues and solutions

---

## 🚀 **AUTOMATIC INSTALL** (Recommended)

> **⚡ Get started fast with our automated installer!**

```bash
# Clone the repository
git clone https://github.com/sivanhavkin/Entelgia.git
cd Entelgia

# Run the automated installer
python scripts/install.py
```

📄 **View installer source:** [`scripts/install.py`](https://github.com/sivanhavkin/Entelgia/blob/main/scripts/install.py)

### What the installer does:

1. ✅ **Detects and installs Ollama** (macOS via Homebrew; provides instructions for Linux/Windows)
2. ✅ **Pulls the `phi3` model** automatically (or lets you skip)
3. ✅ **Creates `.env` configuration** from template
4. ✅ **Generates secure `MEMORY_SECRET_KEY`** (48-char cryptographic key)
5. ✅ **Installs Python dependencies** from `requirements.txt`

### After installation:

```bash
# Start Ollama service
ollama serve

# Run the demo (10 turns, ~2 minutes)
python examples/demo_enhanced_dialogue.py

# Or run the full system (30 minutes, stops when time limit is reached)
python Entelgia_production_meta.py

# Or run 200 turns with no time-based stopping (guaranteed to complete all turns)
python entelgia_production_long.py
```

> 💡 **Having issues?** Check the [Troubleshooting Guide](TROUBLESHOOTING.md) for common problems and solutions.

---

## 📋 Requirements

* Python **3.10+**
* **Ollama** (local LLM runtime)
* At least one supported model (`phi3`, `mistral`, etc.)
* **8GB+ RAM** recommended (16GB+ for larger models)

For the complete dependency list, see [`requirements.txt`](requirements.txt).

---

## 🔧 Manual Installation

If automatic installation isn't possible, follow these steps:

### 1️⃣ Install Ollama

Entelgia requires **Ollama** for local LLM execution.

**macOS:**
```bash
brew install ollama
```

**Linux:**
```bash
curl -fsSL https://ollama.com/install.sh | sh
```

**Windows:**
- Download installer from [ollama.com/download/windows](https://ollama.com/download/windows)
- Or use WSL2 with the Linux installation method

👉 More info: [ollama.com](https://ollama.com)

### 2️⃣ Pull an LLM Model

```bash
ollama pull phi3
```

Recommended models (8GB+ RAM recommended):
* **phi3 (3.8B)** – Fast & lightweight [recommended for 8GB systems]
* **mistral (7B)** – Balanced reasoning
* **neural-chat (7B)** – Strong conversational coherence

### 3️⃣ Install Dependencies

```bash
pip install -r requirements.txt
```

### 4️⃣ Configure Environment

```bash
# Copy environment template
cp .env.example .env

# Generate secure key (or add your own)
python -c "import secrets; print(secrets.token_hex(32))"

# Add the key to .env file:
# MEMORY_SECRET_KEY=<generated-key>
```

### 5️⃣ Run Entelgia

```bash
# Start Ollama (if not already running)
ollama serve

# Run the enhanced dialogue demo (10 turns, ~2 minutes)
python examples/demo_enhanced_dialogue.py

# Or run the full system (30 minutes)
python Entelgia_production_meta.py
```

---

## 📦 Installation from GitHub

For development or integration purposes:

```bash
# Install from GitHub (recommended)
pip install git+https://github.com/sivanhavkin/Entelgia.git

# Or clone and install in editable mode
git clone https://github.com/sivanhavkin/Entelgia.git
cd Entelgia
pip install -e .
```

### 🔄 Upgrading

```bash
pip install --upgrade git+https://github.com/sivanhavkin/Entelgia.git@main
```

---

## ✨ Core Features

* **Multi-agent dialogue system** (Socrates · Athena · Fixy)
* **Persistent memory**
  * Short-term memory (JSON)
  * Long-term memory (SQLite)
  * 🔐 HMAC-SHA256 cryptographic integrity protection
* **🆕 Enhanced Dialogue Engine** (v2.2.0+)
  * **Dynamic speaker selection** - Intelligent turn-taking (no 3+ consecutive turns)
  * **Varied seed generation** - 6+ strategy types (analogy, disagree, reflect, etc.)
  * **Rich context enrichment** - Full dialogue history + thoughts + memories
  * **Smart Fixy interventions** - Need-based (not scheduled) meta-cognitive monitoring
  * **Enhanced personas** - Deep character traits and speech patterns
  * **🐛 Dialogue bug fixes** (v2.5.0):
    * **Third body calling to first body** — after Fixy (3rd agent) intervened, the turn was incorrectly assigned back to Socrates (1st agent); fixed by tracking the last non-Fixy speaker
    * **Double turn** (agent answering twice in one turn) — duplicate Fixy response per turn caused by legacy scheduled check firing alongside `InteractiveFixy`; fully resolved in PR #87 by removing the legacy scheduled path entirely
    * **Pronoun issue** — LLM echoed its own prompt header (e.g. `"Socrates (he):"`) into the response; now stripped automatically when `show_pronoun=False`
* **⚡ Energy-Based Regulation** (v2.5.0)
  * **FixyRegulator** — Meta-level energy supervisor with configurable safety threshold
  * **Dream cycle consolidation** — automatic recharge when energy falls below threshold; critical STM entries are promoted to long-term memory
  * **Hallucination-risk detection** — stochastic check when energy is below 60 %
* **🧠 Personal Long-Term Memory System** (v2.5.0)
  * **DefenseMechanism** — classifies memories as repressed or suppressed on write
  * **FreudianSlip** — probabilistically surfaces defended memory fragments
  * **SelfReplication** — promotes recurring-pattern memories to consciousness
* **🎛️ Drive-Aware Cognition** (v2.5.0)
  * **Dynamic LLM temperature** — derived from id/ego/superego drive balance
  * **Superego second-pass critique** — response is internally rewritten by a principled governor when `superego_strength ≥ 7.5`; the rewrite is used only for emotion/drive state updates — the **agent's original voice is always displayed in dialogue** (PR #95)
  * **Ego-driven memory depth** — long-term and short-term retrieval limits scale with ego/self-awareness
  * **Output artifact cleanup** — strips echoed name/pronoun headers, gender tags, scoring markers
  * **Coherent drive correlations** (PR #92) — conflict now directly erodes ego capacity, raises LLM temperature, and scales energy drain
* **🗣️ Output Quality Rules** (v2.5.0, PR #96)
  * **Forbidden meta-commentary phrases** — `validate_output()` removes any sentence containing `"In our dialogue"`, `"We learn"`, or `"Our conversations reveal"`; the same instruction is injected into LLM prompts to prevent generation up-front
  * **Dissent marker capped to exactly one sentence** — Athena's behavioral rule now requires *exactly* one dissent opener (e.g. `"However,"`, `"Yet,"`) rather than *at least* one
  * **Hard word truncation removed** — the post-processing 150-word cut is removed; response length is governed solely by the LLM prompt instruction, preventing mid-sentence clips
* **Psychological drive modeling**
  * Id / Ego / Superego dynamics
* **Emotion tracking & importance scoring**
* **Dream cycles & memory promotion**
* **Observer-based meta-cognition**
* **Memory poisoning protection**
* **PII redaction & privacy safeguards**
* **Resilient error handling (exponential backoff)**
* **Structured logging**

---

## ⚙️ Configuration

Entelgia can be customized through the `Config` class in `Entelgia_production_meta.py`. Key configuration options:

### Response Quality Settings (v2.2.0+)

> **Note:** Response length is controlled by the module-level constant `MAX_RESPONSE_WORDS = 150`
> in `Entelgia_production_meta.py` (not a `Config` field). The LLM prompt instructs the model
> to answer in maximum 150 words; responses are never truncated by the runtime.

```python
config = Config()

# LLM request timeout (seconds to wait per request)
config.llm_timeout = 300            # Default: 300 s (reduced from 600 s)
```

**Response Length Control** (v2.2.0+):
- ✅ **No truncation/cutting** - All agent responses are displayed in full
- 📝 **LLM guidance** - Explicit instruction added to LLM prompts: "Please answer in maximum 150 words"
- 🎭 **Role-playing maintained** - Agents receive the 150-word request but responses are never truncated
- 🔍 **Sanitization only** - `validate_output()` removes control characters and normalizes newlines, without any length limits
- 🎯 **Natural responses** - LLM decides the response length naturally within the 150-word guidance

This approach ensures:
- Agent responses are complete and coherent (no mid-sentence cuts)
- LLM maintains focus and conciseness through prompt instructions
- Role-playing dynamic remains authentic with requested brevity
- Users see full responses without artificial truncation

**Reduced Timeout** improves responsiveness:
- LLM request timeout reduced from 600 s to 300 s (`config.llm_timeout`) for faster failure detection
- Better user experience with more predictable behavior
- Most responses complete much faster than the timeout limit

### Other Key Settings

```python
config.max_turns = 200              # Maximum dialogue turns (default: 200)
config.timeout_minutes = 30         # Session timeout in minutes (set to 9999 to disable)
config.dream_every_n_turns = 7      # Dream cycle frequency (default: 7)
config.llm_max_retries = 3          # LLM request retry count (default: 3)
config.show_pronoun = False         # Show agent pronouns in output (default: False)
config.show_meta = False            # Show meta-state after each turn (default: False)
config.stm_max_entries = 10000      # Short-term memory capacity (default: 10000)
config.stm_trim_batch = 500         # Entries pruned per trim pass (default: 500)
config.promote_importance_threshold = 0.72  # Min importance to promote to LTM (default: 0.72)
config.promote_emotion_threshold = 0.65     # Min emotion score to promote to LTM (default: 0.65)
config.store_raw_stm = False        # Store un-redacted text in STM (default: False)
config.store_raw_subconscious_ltm = False   # Store un-redacted text in LTM (default: False)
```

### ⚡ Energy & Dream Cycle Settings (v2.5.0)

```python
config.energy_safety_threshold = 35.0  # Energy level that triggers a dream cycle (default: 35.0)
config.energy_drain_min = 8.0           # Minimum energy drained per step (default: 8.0)
config.energy_drain_max = 15.0          # Maximum energy drained per step (default: 15.0)
config.self_replicate_every_n_turns = 10  # Turns between self-replication scans (default: 10)
```

### Drive-Aware Cognition Settings (v2.5.0)

These `Config` fields control how Freudian drives evolve and influence LLM behaviour at runtime:

```python
config.drive_mean_reversion_rate = 0.04   # Rate drives revert toward 5.0 each turn (default: 0.04)
config.drive_oscillation_range = 0.15     # ±random noise added to drives per turn (default: 0.15)

# LLM temperature is computed automatically from drive values:
# temperature = max(0.25, min(0.95, 0.60 + 0.03*(id - ego) - 0.02*(superego - ego)))

# Superego critique (second-pass rewrite) fires when superego_strength >= 7.5
# Memory depth scales automatically:
#   ltm_limit = max(2, min(10, int(2 + ego/2 + self_awareness*4)))
#   stm_tail  = max(3, min(12, int(3 + ego/2)))
```

For the complete list of configuration options, see the `Config` class definition in `Entelgia_production_meta.py`.

---

### 🔥 DrivePressure — Urgency/Tension (v2.6.0)

**DrivePressure** is an invisible scalar (`0.0–10.0`) per agent that represents internal urgency to act now.
It is **not** a character or a voice — it is an urgency modulator.

**Why it exists:**
- Prevents "stable attractor" stagnation (endless SuperEgo-dominant framing loops)
- Reduces long moralized monologues when urgency is high
- Increases initiative: sharper questions, topic shifts, resolution attempts

**How it works:**

| Input | Effect on Pressure |
|---|---|
| High conflict (`conflict >= 4.0`) | Increases pressure |
| Open/unresolved questions | Increases pressure |
| Topic stagnation (same topic ≥ 4 turns) | Increases pressure |
| Low energy | Slightly increases pressure |
| Progress (resolved questions, new topic) | Pressure decays naturally |

**Behavior thresholds:**

| Pressure | Effect |
|---|---|
| `< 6.5` | Normal behavior |
| `>= 6.5` | Output capped at 120 words; prompt: *"Be concise. Prefer 1 key claim + 1 sharp question."* |
| `>= 7.0` + SuperEgo > Ego | A/B binary dilemmas rewritten as "accept / resist / transform beyond both" |
| `>= 8.0` | Output capped at 80 words; prompt: *"Stop framing. Choose a direction. Ask one decisive question."* |

**META block output** (when `show_meta=True`):
```
Pressure: 6.42  Unresolved: 2  Stagnation: 0.75
```

**Sample log showing pressure rising then output shortening:**
```
[META: Socrates]
  Id: 5.8  Ego: 5.1  SuperEgo: 6.4  SA: 0.57
  Energy: 72.0  Conflict: 1.50
  Pressure: 2.12  Unresolved: 0  Stagnation: 0.00    ← turn 1, baseline
...
[META: Socrates]
  Pressure: 5.71  Unresolved: 2  Stagnation: 0.75    ← turn 5, rising
...
[META: Socrates]
  Pressure: 8.03  Unresolved: 3  Stagnation: 1.00    ← turn 8, high pressure
  → output trimmed to 80 words, decisive question forced
```

---

## 🗑️ Memory Management

Entelgia provides a utility to clear stored memories when needed. The `clear_memory.py` script allows you to delete:

- **Short-term memory** (JSON files in `entelgia_data/stm_*.json`)
- **Long-term memory** (SQLite database in `entelgia_data/entelgia_memory.sqlite`)
- **All memories** (both short-term and long-term)

### Usage

```bash
python scripts/clear_memory.py
```

The script will prompt you with an interactive menu:

```
============================================================
Entelgia Memory Deletion Utility
============================================================

What would you like to delete?

1. Short-term memory (JSON files)
2. Long-term memory (SQLite database)
3. All memories (both short-term and long-term)
4. Exit
```

**Safety features:**
- ⚠️ Confirmation required before deletion
- 📊 Shows count of files/entries before deletion
- 🔒 Cannot be undone - use with caution

### When to Use

- **Reset experiments** - Start fresh with new dialogue sessions
- **Privacy concerns** - Remove stored conversation data
- **Testing** - Clear state between test runs
- **Storage management** - Free up disk space

**Note:** Deleting memories will remove all dialogue history and context. The system will start fresh on the next run.

---

## 🏗 Architecture Overview

Entelgia is built as a modular CoreMind system:

* `Conscious` — reflective narrative construction
* `Memory` — persistent identity continuity
* `Emotion` — affective weighting & regulation
* `Language` — dialogue-driven cognition
* `Behavior` — goal-oriented response shaping
* `Observer` — meta-level monitoring & correction
* `EnergyRegulator` — cognitive energy supervision & dream cycles (v2.5.0)

### 🆕 Enhanced Dialogue Module (v2.2.0+)

The new `entelgia/` package provides modular components:

```
entelgia/
├── __init__.py              # Package exports (v2.5.0)
├── dialogue_engine.py       # Dynamic speaker & seed generation
├── enhanced_personas.py     # Rich character definitions
├── context_manager.py       # Smart context enrichment
├── fixy_interactive.py      # Need-based interventions
├── energy_regulation.py     # FixyRegulator & EntelgiaAgent (v2.5.0)
├── long_term_memory.py      # DefenseMechanism, FreudianSlip, SelfReplication (v2.5.0)
├── memory_security.py       # HMAC-SHA256 signature helpers
├── dialogue_metrics.py      # Circularity, progress & intervention utility metrics (PR #111)
└── ablation_study.py        # 4-condition reproducible ablation study (PR #111)
```

**Key improvements:**
- 📊 **6 seed strategies** vs 1 simple template
- 🎯 **Dynamic speaker selection** vs ping-pong alternation
- 🧠 **Context-aware** with 8 turns + 6 thoughts + 5 memories
- 🔍 **Intelligent Fixy** detects circular reasoning, not just scheduled checks
- ⚡ **Energy regulation** with dream-cycle recovery and hallucination-risk detection
- 🧠 **Defense mechanisms** classifying memories as repressed or suppressed on every write

The system runs via two executable entry points:

```
Entelgia_production_meta.py   # Standard 30-minute session (time-bounded)
entelgia_production_long.py   # 200-turn session, no time-based stopping
```

---

## 🧪 Test Suite

Entelgia ships with comprehensive test coverage across **209 tests** in 9 suites:

### Enhanced Dialogue Tests (6 tests)

```bash
python tests/test_enhanced_dialogue.py
```

Tests verify:
- ✅ **Dynamic speaker selection** - No agent speaks 3+ times consecutively
- ✅ **Seed variety** - 6 different generation strategies
- ✅ **Context enrichment** - 8 turns, 6 thoughts, 5 memories
- ✅ **Fixy interventions** - Need-based (circular reasoning, repetition)
- ✅ **Persona formatting** - Rich traits and speech patterns

---

### ⚡ Energy Regulation Tests (35 tests)

```bash
pytest tests/test_energy_regulation.py -v
```

Tests verify:
- ✅ **FixyRegulator defaults** — threshold and constant values
- ✅ **Dream trigger** — fires when energy ≤ safety threshold
- ✅ **Energy recharge** — restored to 100.0 after dream cycle
- ✅ **Hallucination-risk probe** — stochastic detection below 60 %
- ✅ **EntelgiaAgent init** — initial state, regulator propagation
- ✅ **process_step** — energy drain, memory append, return values
- ✅ **Dream cycle** — subconscious consolidation and memory pruning
- ✅ **LTM promotion** — critical STM entries promoted to long-term memory during dream cycle

---

### 🧠 Long-Term Memory Tests (33 tests)

```bash
pytest tests/test_long_term_memory.py -v
```

Tests verify `DefenseMechanism`, `FreudianSlip`, and `SelfReplication` classes:
- ✅ **Repression classification** — painful emotions above threshold
- ✅ **Suppression classification** — mildly negative content
- ✅ **Freudian slip surfacing** — probabilistic recall of defended memories
- ✅ **Self-replication promotion** — recurring keyword detection

---

### 🔐 Memory Security Tests (19 tests)

```bash
pytest tests/test_memory_security.py -v
```

Entelgia ships with a comprehensive pytest test suite to ensure the reliability and security of its memory-protection subsystem. The current suite contains **19 tests** divided into three categories:

#### Signature Creation
Tests verify that creating an HMAC-SHA256 signature:
- Returns a 64-character hex string
- Behaves deterministically for the same message and key
- Yields different signatures for different messages
- Properly raises a `ValueError` when supplied with empty or `None` keys/messages

#### Signature Validation
Checks that:
- Valid signatures are accepted
- Wrong keys, tampered messages/signatures, or `None`/empty values correctly cause validation to fail

#### Security Properties
Tests assert that:
- Signatures are unique across multiple inputs and keys
- The implementation supports Unicode messages (mixed-language, Arabic, and emojis)

---

### 🔗 Drive Correlation Tests (17 tests)

```bash
pytest tests/test_drive_correlations.py -v
```

Tests verify the coherent Freudian drive correlations added in PR #92:
- ✅ **conflict_index boundaries** — zero conflict at balance, maximum at extremes
- ✅ **Ego erosion magnitude** — proportional reduction above the 4.0 threshold
- ✅ **Ego erosion monotonicity** — higher conflict → greater erosion
- ✅ **Temperature–conflict correlation** — temperature rises with conflict index
- ✅ **Energy drain scaling** — conflict adds to base drain
- ✅ **Energy drain cap** — drain never exceeds `2 × energy_drain_max`

---

### 🔥 Drive Pressure Tests (23 tests)

```bash
pytest tests/test_drive_pressure.py -v
```

Tests verify the DrivePressure urgency/tension system:
- ✅ **Pressure clamped to 0–10 range** — output always within bounds
- ✅ **High conflict raises pressure** — proportional increase
- ✅ **Stagnation raises pressure** — same topic ≥ 4 turns
- ✅ **Natural decay** — pressure decreases after progress/resolution
- ✅ **Forced brevity thresholds** — output trimmed at pressure ≥ 6.5 and ≥ 8.0
- ✅ **Unresolved question tracking** — count increments and decrements correctly

---

### 🛡️ Behavioral Rules Tests (16 tests)

```bash
pytest tests/test_behavioral_rules.py -v
```

Tests verify drive-triggered behavioral rules for Socrates and Athena:
- ✅ **Socrates conflict rule** — fires at and above conflict threshold 5.0
- ✅ **Athena dissent rule** — fires at and above dissent threshold 3.0
- ✅ **Rule content** — correct keywords injected (`binary choice`, `However`, `Yet`)
- ✅ **Prompt injection** — rule text inserted before "Respond now" in agent prompt

---

### 📊 Dialogue Metrics Tests (45 tests)

```bash
pytest tests/test_dialogue_metrics.py -v
```

Tests verify the three dialogue-quality metrics and the ablation study (PR #111):
- ✅ **circularity_rate** — Jaccard-based looping fraction
- ✅ **progress_rate** — forward topic shifts and synthesis markers
- ✅ **intervention_utility** — Fixy-window circularity reduction
- ✅ **circularity_per_turn** — rolling time-series correctness
- ✅ **AblationCondition enum** — all four conditions defined
- ✅ **run_ablation reproducibility** — same seed → identical results
- ✅ **Inter-condition ordering** — BASELINE circularity > DIALOGUE_ENGINE
- ✅ **print_results_table** — formatted output without crash
- ✅ **plot_circularity ASCII fallback** — works without matplotlib

---

### 🔏 Memory Signing Migration Tests (5 tests)

```bash
pytest tests/test_memory_signing_migration.py -v
```

Tests verify the key-rotation and legacy-format migration logic in `MemoryCore`:
- ✅ **Fingerprint stored on first init** — `settings` table populated
- ✅ **No re-sign when fingerprint matches** — existing rows untouched
- ✅ **Re-sign on fingerprint mismatch** — all rows updated on key rotation
- ✅ **Legacy format recovery** — `None`→`"None"` format auto-healed after migration
- ✅ **Settings table existence** — created during `_init_db`

---

### 📋 Latest Test Run Results

```
============================= test session starts ==============================
platform linux -- Python 3.12.3, pytest-9.0.2, pluggy-1.6.0 -- /usr/bin/python
cachedir: .pytest_cache
rootdir: /home/runner/work/Entelgia/Entelgia
configfile: pyproject.toml
plugins: cov-7.0.0
collecting ... collected 209 items

tests/test_behavioral_rules.py::TestRuleASocrates::test_returns_nonempty_rule_at_exactly_5 PASSED [  0%]
tests/test_behavioral_rules.py::TestRuleASocrates::test_returns_nonempty_rule_above_5 PASSED [  0%]
tests/test_behavioral_rules.py::TestRuleASocrates::test_returns_empty_below_5 PASSED [  1%]
tests/test_behavioral_rules.py::TestRuleASocrates::test_rule_mentions_binary_choice PASSED [  1%]
tests/test_behavioral_rules.py::TestRuleASocrates::test_rule_mentions_end_response PASSED [  2%]
tests/test_behavioral_rules.py::TestRuleASocrates::test_non_socrates_not_triggered_even_with_high_conflict PASSED [  2%]
tests/test_behavioral_rules.py::TestRuleBAnthena::test_returns_nonempty_rule_at_exactly_3 PASSED [  3%]
tests/test_behavioral_rules.py::TestRuleBAnthena::test_returns_nonempty_rule_above_3 PASSED [  3%]
tests/test_behavioral_rules.py::TestRuleBAnthena::test_returns_empty_below_3 PASSED [  4%]
tests/test_behavioral_rules.py::TestRuleBAnthena::test_rule_mentions_however PASSED [  4%]
tests/test_behavioral_rules.py::TestRuleBAnthena::test_rule_mentions_yet PASSED [  5%]
tests/test_behavioral_rules.py::TestRuleBAnthena::test_rule_mentions_this_assumes PASSED [  5%]
tests/test_behavioral_rules.py::TestRuleBAnthena::test_non_athena_not_triggered_even_with_high_dissent PASSED [  6%]
tests/test_behavioral_rules.py::TestPromptInjection::test_rule_a_injected_before_respond_now PASSED [  6%]
tests/test_behavioral_rules.py::TestPromptInjection::test_rule_b_injected_before_respond_now PASSED [  7%]
tests/test_behavioral_rules.py::TestPromptInjection::test_no_rule_leaves_prompt_unchanged PASSED [  7%]
tests/test_dialogue_metrics.py::TestKeywords::test_only_long_words PASSED [  8%]
tests/test_dialogue_metrics.py::TestKeywords::test_lowercases PASSED     [  8%]
tests/test_dialogue_metrics.py::TestJaccard::test_identical_sets PASSED  [  9%]
tests/test_dialogue_metrics.py::TestJaccard::test_disjoint_sets PASSED   [  9%]
tests/test_dialogue_metrics.py::TestJaccard::test_partial_overlap PASSED [ 10%]
tests/test_dialogue_metrics.py::TestJaccard::test_empty_sets PASSED      [ 10%]
tests/test_dialogue_metrics.py::TestCircularityRate::test_empty_dialog PASSED [ 11%]
tests/test_dialogue_metrics.py::TestCircularityRate::test_single_turn PASSED [ 11%]
tests/test_dialogue_metrics.py::TestCircularityRate::test_identical_turns_high_circularity PASSED [ 11%]
tests/test_dialogue_metrics.py::TestCircularityRate::test_completely_distinct_turns_low_circularity PASSED [ 12%]
tests/test_dialogue_metrics.py::TestCircularityRate::test_custom_threshold PASSED [ 12%]
tests/test_dialogue_metrics.py::TestCircularityRate::test_result_in_range PASSED [ 13%]
tests/test_dialogue_metrics.py::TestCircularityPerTurn::test_series_length_equals_dialog_length PASSED [ 13%]
tests/test_dialogue_metrics.py::TestCircularityPerTurn::test_empty_dialog PASSED [ 14%]
tests/test_dialogue_metrics.py::TestCircularityPerTurn::test_first_turn_is_zero PASSED [ 14%]
tests/test_dialogue_metrics.py::TestCircularityPerTurn::test_values_in_range PASSED [ 15%]
tests/test_dialogue_metrics.py::TestProgressRate::test_empty_or_single_turn PASSED [ 15%]
tests/test_dialogue_metrics.py::TestProgressRate::test_synthesis_marker_increases_progress PASSED [ 16%]
tests/test_dialogue_metrics.py::TestProgressRate::test_topic_shift_counts_as_progress PASSED [ 16%]
tests/test_dialogue_metrics.py::TestProgressRate::test_question_resolution PASSED [ 17%]
tests/test_dialogue_metrics.py::TestProgressRate::test_repetitive_dialog_low_progress PASSED [ 17%]
tests/test_dialogue_metrics.py::TestProgressRate::test_result_in_range PASSED [ 18%]
tests/test_dialogue_metrics.py::TestInterventionUtility::test_no_fixy_turns PASSED [ 18%]
tests/test_dialogue_metrics.py::TestInterventionUtility::test_fixy_reduces_circularity PASSED [ 19%]
tests/test_dialogue_metrics.py::TestInterventionUtility::test_multiple_fixy_turns PASSED [ 19%]
tests/test_dialogue_metrics.py::TestInterventionUtility::test_result_is_float PASSED [ 20%]
tests/test_dialogue_metrics.py::TestComputeAllMetrics::test_keys_present PASSED [ 20%]
tests/test_dialogue_metrics.py::TestComputeAllMetrics::test_values_are_floats_in_range PASSED [ 21%]
tests/test_dialogue_metrics.py::TestAblationCondition::test_all_four_conditions_defined PASSED [ 21%]
tests/test_dialogue_metrics.py::TestAblationCondition::test_enum_has_four_members PASSED [ 22%]
tests/test_dialogue_metrics.py::TestRunCondition::test_returns_correct_number_of_turns[AblationCondition.BASELINE] PASSED [ 22%]
tests/test_dialogue_metrics.py::TestRunCondition::test_returns_correct_number_of_turns[AblationCondition.DIALOGUE_ENGINE] PASSED [ 22%]
tests/test_dialogue_metrics.py::TestRunCondition::test_returns_correct_number_of_turns[AblationCondition.FIXY] PASSED [ 23%]
tests/test_dialogue_metrics.py::TestRunCondition::test_returns_correct_number_of_turns[AblationCondition.DREAM] PASSED [ 23%]
tests/test_dialogue_metrics.py::TestRunCondition::test_turns_have_role_and_text[AblationCondition.BASELINE] PASSED [ 24%]
tests/test_dialogue_metrics.py::TestRunCondition::test_turns_have_role_and_text[AblationCondition.DIALOGUE_ENGINE] PASSED [ 24%]
tests/test_dialogue_metrics.py::TestRunCondition::test_turns_have_role_and_text[AblationCondition.FIXY] PASSED [ 25%]
tests/test_dialogue_metrics.py::TestRunCondition::test_turns_have_role_and_text[AblationCondition.DREAM] PASSED [ 25%]
tests/test_dialogue_metrics.py::TestRunCondition::test_reproducible_with_same_seed PASSED [ 26%]
tests/test_dialogue_metrics.py::TestRunCondition::test_different_seeds_differ PASSED [ 26%]
tests/test_dialogue_metrics.py::TestRunCondition::test_fixy_condition_contains_fixy_role PASSED [ 27%]
tests/test_dialogue_metrics.py::TestRunCondition::test_baseline_no_fixy_role PASSED [ 27%]
tests/test_dialogue_metrics.py::TestRunAblation::test_returns_all_four_conditions PASSED [ 28%]
tests/test_dialogue_metrics.py::TestRunAblation::test_each_condition_has_metrics_and_series PASSED [ 28%]
tests/test_dialogue_metrics.py::TestRunAblation::test_circularity_series_length PASSED [ 29%]
tests/test_dialogue_metrics.py::TestRunAblation::test_reproducible PASSED [ 29%]
tests/test_dialogue_metrics.py::TestRunAblation::test_baseline_higher_circularity_than_dialogue_engine PASSED [ 30%]
tests/test_dialogue_metrics.py::TestPrintResultsTable::test_smoke_no_crash PASSED [ 30%]
tests/test_dialogue_metrics.py::TestPrintResultsTable::test_all_conditions_in_output PASSED [ 31%]
tests/test_dialogue_metrics.py::TestPlotCircularity::test_ascii_fallback_smoke PASSED [ 31%]
tests/test_dialogue_metrics.py::TestPlotCircularity::test_plot_circularity_uses_ascii_when_matplotlib_absent PASSED [ 32%]
tests/test_drive_correlations.py::TestConflictIndex::test_balanced_drives_zero_conflict PASSED [ 32%]
tests/test_drive_correlations.py::TestConflictIndex::test_conflict_with_high_id_only PASSED [ 33%]
tests/test_drive_correlations.py::TestConflictIndex::test_conflict_with_high_superego_only PASSED [ 33%]
tests/test_drive_correlations.py::TestConflictIndex::test_symmetric_high_conflict PASSED [ 33%]
tests/test_drive_correlations.py::TestConflictIndex::test_maximum_conflict PASSED [ 34%]
tests/test_drive_correlations.py::TestConflictIndex::test_conflict_parametrized[2.9-8.8-8.7-expected0] PASSED [ 34%]
tests/test_drive_correlations.py::TestConflictIndex::test_conflict_parametrized[5.0-5.0-5.0-expected1] PASSED [ 35%]
tests/test_drive_correlations.py::TestConflictIndex::test_conflict_parametrized[10.0-5.0-0.0-expected2] PASSED [ 35%]
tests/test_drive_correlations.py::TestEgoErosionUnderConflict::test_high_conflict_reduces_ego PASSED [ 36%]
tests/test_drive_correlations.py::TestEgoErosionUnderConflict::test_low_conflict_does_not_erode_ego PASSED [ 36%]
tests/test_drive_correlations.py::TestEgoErosionUnderConflict::test_erosion_proportional_to_conflict PASSED [ 37%]
tests/test_drive_correlations.py::TestEgoErosionUnderConflict::test_ego_never_negative PASSED [ 37%]
tests/test_drive_correlations.py::TestTemperatureConflictCorrelation::test_zero_conflict_baseline_temperature PASSED [ 38%]
tests/test_drive_correlations.py::TestTemperatureConflictCorrelation::test_higher_conflict_raises_temperature PASSED [ 38%]
tests/test_drive_correlations.py::TestTemperatureConflictCorrelation::test_temperature_stays_within_bounds[0.0-10.0-0.0] PASSED [ 39%]
tests/test_drive_correlations.py::TestTemperatureConflictCorrelation::test_temperature_stays_within_bounds[10.0-0.0-10.0] PASSED [ 39%]
tests/test_drive_correlations.py::TestTemperatureConflictCorrelation::test_temperature_stays_within_bounds[5.0-5.0-5.0] PASSED [ 40%]
tests/test_drive_correlations.py::TestTemperatureConflictCorrelation::test_conflict_component_is_positive PASSED [ 40%]
tests/test_drive_correlations.py::TestEnergyDrainConflictCorrelation::test_high_conflict_drains_more_energy PASSED [ 41%]
tests/test_drive_correlations.py::TestEnergyDrainConflictCorrelation::test_energy_never_negative PASSED [ 41%]
tests/test_drive_correlations.py::TestEnergyDrainConflictCorrelation::test_energy_drain_capped_at_twice_max PASSED [ 42%]
tests/test_drive_pressure.py::TestComputeDrivePressure::test_default_initial_value PASSED [ 42%]
tests/test_drive_pressure.py::TestComputeDrivePressure::test_output_clamped_to_range PASSED [ 43%]
tests/test_drive_pressure.py::TestComputeDrivePressure::test_high_conflict_raises_pressure PASSED [ 43%]
tests/test_drive_pressure.py::TestComputeDrivePressure::test_stagnation_raises_pressure PASSED [ 44%]
tests/test_drive_pressure.py::TestComputeDrivePressure::test_decay_when_calm PASSED [ 44%]
tests/test_drive_pressure.py::TestComputeDrivePressure::test_unresolved_raises_pressure PASSED [ 44%]
tests/test_drive_pressure.py::TestComputeDrivePressure::test_smoothing_inertia PASSED [ 45%]
tests/test_drive_pressure.py::TestPressureRisesDuringStagnation::test_pressure_rises_over_8_stagnant_turns PASSED [ 45%]
tests/test_drive_pressure.py::TestPressureRisesDuringStagnation::test_pressure_at_turn_6_is_higher_than_baseline PASSED [ 46%]
tests/test_drive_pressure.py::TestPressureForcedBrevity::test_trim_to_80_words PASSED [ 46%]
tests/test_drive_pressure.py::TestPressureForcedBrevity::test_trim_to_120_words PASSED [ 47%]
tests/test_drive_pressure.py::TestPressureForcedBrevity::test_short_text_unchanged PASSED [ 47%]
tests/test_drive_pressure.py::TestPressureForcedBrevity::test_trim_preserves_sentence_boundary PASSED [ 48%]
tests/test_drive_pressure.py::TestPressureForcedBrevity::test_high_pressure_produces_short_output PASSED [ 48%]
tests/test_drive_pressure.py::TestPressureDecaysAfterProgress::test_pressure_decreases_after_resolution PASSED [ 49%]
tests/test_drive_pressure.py::TestPressureDecaysAfterProgress::test_unresolved_count_decrements_on_answer PASSED [ 49%]
tests/test_drive_pressure.py::TestPressureDecaysAfterProgress::test_unresolved_count_no_decrement_without_answer PASSED [ 50%]
tests/test_drive_pressure.py::TestNoBreakingChanges::test_constants_present PASSED [ 50%]
tests/test_drive_pressure.py::TestNoBreakingChanges::test_new_functions_importable PASSED [ 51%]
tests/test_drive_pressure.py::TestNoBreakingChanges::test_topic_signature_returns_string PASSED [ 51%]
tests/test_drive_pressure.py::TestNoBreakingChanges::test_topic_signature_same_for_similar_text PASSED [ 52%]
tests/test_drive_pressure.py::TestNoBreakingChanges::test_topic_signature_different_for_different_topics PASSED [ 52%]
tests/test_drive_pressure.py::TestNoBreakingChanges::test_compute_drive_pressure_is_deterministic PASSED [ 53%]
tests/test_energy_regulation.py::TestFixyRegulatorDefaults::test_default_safety_threshold PASSED [ 53%]
tests/test_energy_regulation.py::TestFixyRegulatorDefaults::test_custom_threshold PASSED [ 54%]
tests/test_energy_regulation.py::TestFixyRegulatorDefaults::test_hallucination_risk_probability_constant PASSED [ 54%]
tests/test_energy_regulation.py::TestFixyRegulatorDefaults::test_hallucination_risk_energy_cutoff_constant PASSED [ 55%]
tests/test_energy_regulation.py::TestFixyRegulatorCheckStability::test_dream_triggered_when_energy_at_threshold PASSED [ 55%]
tests/test_energy_regulation.py::TestFixyRegulatorCheckStability::test_dream_triggered_when_energy_below_threshold PASSED [ 55%]
tests/test_energy_regulation.py::TestFixyRegulatorCheckStability::test_dream_recharges_energy PASSED [ 56%]
tests/test_energy_regulation.py::TestFixyRegulatorCheckStability::test_no_action_when_energy_high PASSED [ 56%]
tests/test_energy_regulation.py::TestFixyRegulatorCheckStability::test_hallucination_risk_possible_below_60 PASSED [ 57%]
tests/test_energy_regulation.py::TestFixyRegulatorCheckStability::test_no_hallucination_risk_above_60 PASSED [ 57%]
tests/test_energy_regulation.py::TestEntelgiaAgentInit::test_initial_energy_level PASSED [ 58%]
tests/test_energy_regulation.py::TestEntelgiaAgentInit::test_initial_memory_empty PASSED [ 58%]
tests/test_energy_regulation.py::TestEntelgiaAgentInit::test_has_regulator PASSED [ 59%]
tests/test_energy_regulation.py::TestEntelgiaAgentInit::test_custom_safety_threshold_propagates PASSED [ 59%]
tests/test_energy_regulation.py::TestEntelgiaAgentProcessStep::test_energy_drains_per_step PASSED [ 60%]
tests/test_energy_regulation.py::TestEntelgiaAgentProcessStep::test_input_appended_to_memory PASSED [ 60%]
tests/test_energy_regulation.py::TestEntelgiaAgentProcessStep::test_returns_recharged_after_dream PASSED [ 61%]
tests/test_energy_regulation.py::TestEntelgiaAgentProcessStep::test_returns_ok_when_energy_high PASSED [ 61%]
tests/test_energy_regulation.py::TestEntelgiaAgentProcessStep::test_energy_restored_after_dream_cycle PASSED [ 62%]
tests/test_energy_regulation.py::TestEntelgiaAgentDreamCycle::test_dream_clears_subconscious_store PASSED [ 62%]
tests/test_energy_regulation.py::TestEntelgiaAgentDreamCycle::test_dream_consolidates_subconscious_to_conscious PASSED [ 63%]
tests/test_energy_regulation.py::TestEntelgiaAgentDreamCycle::test_dream_does_not_truncate_long_term_memories PASSED [ 63%]
tests/test_energy_regulation.py::TestEntelgiaAgentDreamCycle::test_dream_forgets_irrelevant_stm_entries PASSED [ 64%]
tests/test_energy_regulation.py::TestEntelgiaAgentDreamCycle::test_is_relevant_returns_true_for_non_empty PASSED [ 64%]
tests/test_energy_regulation.py::TestEntelgiaAgentDreamCycle::test_is_relevant_returns_false_for_empty PASSED [ 65%]
tests/test_energy_regulation.py::TestEntelgiaAgentLTMPromotion::test_long_term_memory_starts_empty PASSED [ 65%]
tests/test_energy_regulation.py::TestEntelgiaAgentLTMPromotion::test_critical_entry_promoted_to_ltm PASSED [ 66%]
tests/test_energy_regulation.py::TestEntelgiaAgentLTMPromotion::test_non_critical_entry_not_promoted PASSED [ 66%]
tests/test_energy_regulation.py::TestEntelgiaAgentLTMPromotion::test_ltm_no_duplicates PASSED [ 66%]
tests/test_energy_regulation.py::TestEntelgiaAgentLTMPromotion::test_is_critical_returns_true_for_substantive PASSED [ 67%]
tests/test_energy_regulation.py::TestEntelgiaAgentLTMPromotion::test_is_critical_returns_false_for_trivial PASSED [ 67%]
tests/test_energy_regulation.py::TestEntelgiaAgentLTMPromotion::test_is_critical_returns_false_for_empty PASSED [ 68%]
tests/test_energy_regulation.py::TestEntelgiaAgentLTMPromotion::test_subconscious_critical_entry_promoted_to_ltm PASSED [ 68%]
tests/test_energy_regulation.py::TestPackageImports::test_import_fixy_regulator PASSED [ 69%]
tests/test_energy_regulation.py::TestPackageImports::test_import_entelgia_agent PASSED [ 69%]
tests/test_enhanced_dialogue.py::test_dynamic_speaker_selection PASSED   [ 70%]
tests/test_enhanced_dialogue.py::test_seed_variety PASSED                [ 70%]
tests/test_enhanced_dialogue.py::test_context_enrichment PASSED          [ 71%]
tests/test_enhanced_dialogue.py::test_fixy_interventions PASSED          [ 71%]
tests/test_enhanced_dialogue.py::test_persona_formatting PASSED          [ 72%]
tests/test_enhanced_dialogue.py::test_persona_pronouns PASSED            [ 72%]
tests/test_long_term_memory.py::TestDefenseMechanismRepression::test_repression_anger_above_threshold PASSED [ 73%]
tests/test_long_term_memory.py::TestDefenseMechanismRepression::test_repression_fear_above_threshold PASSED [ 73%]
tests/test_long_term_memory.py::TestDefenseMechanismRepression::test_repression_shame_above_threshold PASSED [ 74%]
tests/test_long_term_memory.py::TestDefenseMechanismRepression::test_repression_guilt_above_threshold PASSED [ 74%]
tests/test_long_term_memory.py::TestDefenseMechanismRepression::test_repression_anxiety_above_threshold PASSED [ 75%]
tests/test_long_term_memory.py::TestDefenseMechanismRepression::test_no_repression_below_threshold PASSED [ 75%]
tests/test_long_term_memory.py::TestDefenseMechanismRepression::test_no_repression_neutral_emotion PASSED [ 76%]
tests/test_long_term_memory.py::TestDefenseMechanismRepression::test_no_repression_without_emotion PASSED [ 76%]
tests/test_long_term_memory.py::TestDefenseMechanismSuppression::test_suppression_forbidden_keyword PASSED [ 77%]
tests/test_long_term_memory.py::TestDefenseMechanismSuppression::test_suppression_secret_keyword PASSED [ 77%]
tests/test_long_term_memory.py::TestDefenseMechanismSuppression::test_suppression_dangerous_keyword PASSED [ 77%]
tests/test_long_term_memory.py::TestDefenseMechanismSuppression::test_no_suppression_clean_content PASSED [ 78%]
tests/test_long_term_memory.py::TestDefenseMechanismSuppression::test_both_flags_set_simultaneously PASSED [ 78%]
tests/test_long_term_memory.py::TestDefenseMechanismSuppression::test_suppression_case_insensitive PASSED [ 79%]
tests/test_long_term_memory.py::TestFreudianSlipAttempt::test_no_slip_without_defended_memories PASSED [ 79%]
tests/test_long_term_memory.py::TestFreudianSlipAttempt::test_slip_occurs_with_high_probability PASSED [ 80%]
tests/test_long_term_memory.py::TestFreudianSlipAttempt::test_slip_sets_source_freudian_slip PASSED [ 80%]
tests/test_long_term_memory.py::TestFreudianSlipAttempt::test_no_slip_with_zero_probability PASSED [ 81%]
tests/test_long_term_memory.py::TestFreudianSlipAttempt::test_slip_returns_dict PASSED [ 81%]
tests/test_long_term_memory.py::TestFreudianSlipAttempt::test_slip_does_not_modify_original PASSED [ 82%]
tests/test_long_term_memory.py::TestFreudianSlipFormatting::test_format_slip_contains_slip_marker PASSED [ 82%]
tests/test_long_term_memory.py::TestFreudianSlipFormatting::test_format_slip_contains_content PASSED [ 83%]
tests/test_long_term_memory.py::TestSelfReplicationPatternDetection::test_no_promotion_without_recurring_patterns PASSED [ 83%]
tests/test_long_term_memory.py::TestSelfReplicationPatternDetection::test_promotion_with_recurring_keywords PASSED [ 84%]
tests/test_long_term_memory.py::TestSelfReplicationPatternDetection::test_promoted_memories_have_self_replication_source PASSED [ 84%]
tests/test_long_term_memory.py::TestSelfReplicationPatternDetection::test_max_three_promoted PASSED [ 85%]
tests/test_long_term_memory.py::TestSelfReplicationPatternDetection::test_highest_importance_promoted_first PASSED [ 85%]
tests/test_long_term_memory.py::TestSelfReplicationPatternDetection::test_replication_does_not_modify_originals PASSED [ 86%]
tests/test_long_term_memory.py::TestSelfReplicationFormatting::test_format_contains_self_repl_marker PASSED [ 86%]
tests/test_long_term_memory.py::TestSelfReplicationFormatting::test_format_contains_content PASSED [ 87%]
tests/test_long_term_memory.py::TestLongTermMemoryPackageImports::test_import_defense_mechanism PASSED [ 87%]
tests/test_long_term_memory.py::TestLongTermMemoryPackageImports::test_import_freudian_slip PASSED [ 88%]
tests/test_long_term_memory.py::TestLongTermMemoryPackageImports::test_import_self_replication PASSED [ 88%]
tests/test_memory_security.py::TestSignatureCreation::test_create_signature_success PASSED [ 88%]
tests/test_memory_security.py::TestSignatureCreation::test_create_signature_deterministic PASSED [ 89%]
tests/test_memory_security.py::TestSignatureCreation::test_create_signature_different_messages PASSED [ 89%]
tests/test_memory_security.py::TestSignatureCreation::test_create_signature_empty_message PASSED [ 90%]
tests/test_memory_security.py::TestSignatureCreation::test_create_signature_empty_key PASSED [ 90%]
tests/test_memory_security.py::TestSignatureCreation::test_create_signature_none_message PASSED [ 91%]
tests/test_memory_security.py::TestSignatureCreation::test_create_signature_none_key PASSED [ 91%]
tests/test_memory_security.py::TestSignatureValidation::test_validate_signature_success PASSED [ 92%]
tests/test_memory_security.py::TestSignatureValidation::test_validate_signature_wrong_key PASSED [ 92%]
tests/test_memory_security.py::TestSignatureValidation::test_validate_signature_tampered_message PASSED [ 93%]
tests/test_memory_security.py::TestSignatureValidation::test_validate_signature_tampered_signature PASSED [ 93%]
tests/test_memory_security.py::TestSignatureValidation::test_validate_signature_none_message PASSED [ 94%]
tests/test_memory_security.py::TestSignatureValidation::test_validate_signature_none_key PASSED [ 94%]
tests/test_memory_security.py::TestSignatureValidation::test_validate_signature_none_signature PASSED [ 95%]
tests/test_memory_security.py::TestSignatureValidation::test_validate_signature_empty_values PASSED [ 95%]
tests/test_memory_security.py::TestSignatureValidation::test_validate_signature_invalid_hex PASSED [ 96%]
tests/test_memory_security.py::TestSecurityProperties::test_signature_uniqueness PASSED [ 96%]
tests/test_memory_security.py::TestSecurityProperties::test_key_sensitivity PASSED [ 97%]
tests/test_memory_security.py::TestSecurityProperties::test_unicode_support PASSED [ 97%]
tests/test_memory_signing_migration.py::TestMigrateSigningKey::test_fingerprint_stored_on_first_init PASSED [ 98%]
tests/test_memory_signing_migration.py::TestMigrateSigningKey::test_no_re_sign_when_fingerprint_matches PASSED [ 98%]
tests/test_memory_signing_migration.py::TestMigrateSigningKey::test_re_sign_on_fingerprint_mismatch PASSED [ 99%]
tests/test_memory_signing_migration.py::TestMigrateSigningKey::test_legacy_format_memory_recovered_after_migration PASSED [ 99%]
tests/test_memory_signing_migration.py::TestMigrateSigningKey::test_settings_table_exists PASSED [100%]

=============================== warnings summary ===============================
tests/test_enhanced_dialogue.py::test_dynamic_speaker_selection
  PytestReturnNotNoneWarning: Test functions should return None, but
  test_dynamic_speaker_selection returned <class 'bool'>.
tests/test_enhanced_dialogue.py::test_seed_variety
  PytestReturnNotNoneWarning: Test functions should return None, but
  test_seed_variety returned <class 'bool'>.
tests/test_enhanced_dialogue.py::test_context_enrichment
  PytestReturnNotNoneWarning: Test functions should return None, but
  test_context_enrichment returned <class 'bool'>.
tests/test_enhanced_dialogue.py::test_fixy_interventions
  PytestReturnNotNoneWarning: Test functions should return None, but
  test_fixy_interventions returned <class 'bool'>.
tests/test_enhanced_dialogue.py::test_persona_formatting
  PytestReturnNotNoneWarning: Test functions should return None, but
  test_persona_formatting returned <class 'bool'>.
tests/test_enhanced_dialogue.py::test_persona_pronouns
  PytestReturnNotNoneWarning: Test functions should return None, but
  test_persona_pronouns returned <class 'bool'>.
tests/test_memory_signing_migration.py
  DeprecationWarning: datetime.datetime.utcnow() is deprecated and scheduled
  for removal in a future version. Use timezone-aware objects to represent
  datetimes in UTC: datetime.datetime.now(datetime.UTC).

================================ tests coverage ================================
Name                                     Stmts   Miss  Cover
------------------------------------------------------------
Entelgia_production_meta.py               1522   1190    22%
entelgia/__init__.py                        10      0   100%
entelgia/ablation_study.py                 151     24    84%
entelgia/context_manager.py                118     47    60%
entelgia/dialogue_engine.py                 99     55    44%
entelgia/dialogue_metrics.py                86     17    80%
entelgia/energy_regulation.py               56      0   100%
entelgia/enhanced_personas.py               31      6    81%
entelgia/fixy_interactive.py                94     54    43%
entelgia/long_term_memory.py                72      1    99%
entelgia/memory_security.py                 17      2    88%
entelgia_production_long.py                165    165     0%
tests/__init__.py                            0      0   100%
tests/conftest.py                           23      2    91%
tests/test_behavioral_rules.py             113      0   100%
tests/test_dialogue_metrics.py             251      1    99%
tests/test_drive_correlations.py           147      4    97%
tests/test_drive_pressure.py               114      0   100%
tests/test_energy_regulation.py            177      0   100%
tests/test_enhanced_dialogue.py            189     44    77%
tests/test_long_term_memory.py             167      0   100%
tests/test_memory_security.py               78      0   100%
tests/test_memory_signing_migration.py      72      0   100%
------------------------------------------------------------
TOTAL                                     3752   1612    57%
Coverage HTML written to dir htmlcov
======================= 209 passed, 9 warnings in 4.50s ========================
```

> ✅ **All 209 tests currently pass** (16 behavioral rules + 45 dialogue metrics + 17 drive correlations + 23 drive pressure + 35 energy regulation + 6 dialogue + 33 long-term memory + 19 security + 5 signing migration), providing confidence that all subsystems perform as expected.

---

### 🔄 CI/CD Pipeline

In addition to the unit tests, the continuous-integration (CI/CD) pipeline automatically runs a suite of quality and security checks:

| Category | Tools | Purpose |
|----------|-------|---------|
| **Unit Tests** | `pytest` | Runs 209 total tests (6 dialogue + 35 energy + 33 LTM + 19 security + 17 drive correlations + 23 drive pressure + 16 behavioral rules + 45 dialogue metrics + 5 signing migration) |
| **Code Quality** | `black`, `flake8`, `mypy` | Code formatting, linting, and static type checking |
| **Security Scans** | `safety`, `bandit` | Dependency and code-security vulnerability detection |
| **Scheduled Audits** | `pip-audit` | Weekly dependency security audit |
| **Build Verification** | Package build tools | Ensures valid package creation |
| **Documentation** | Doc integrity checks | Validates documentation consistency |

> 🛡️ Together these jobs ensure that **every commit** adheres to style guidelines, passes vulnerability scans and produces a valid package and documentation.

---

---

## 📦 Version Information

| Version | Status | Notes |
|---------|--------|-------|
| **v2.5.0** | ✅ **Stable** | latest |
| **v2.4.0** | ⚠️ Superseded | Use v2.5.0 instead |
| **v2.3.0** | ⚠️ Superseded | Use v2.5.0 instead |
| **v2.2.0** | ⚠️ Superseded | Use v2.5.0 instead |
| **v2.1.1** | ⚠️ Superseded | Use v2.5.0 instead |
| v2.1.0 | ⚠️ Superseded | Use v2.5.0 instead |
| v2.0.01 | ⚠️ Superseded | Use v2.5.0 instead |
| v1.5 | 📦 Legacy | Production v2.0+ recommended |

💡 **Note:** Starting from v2.1.1, we follow a controlled release schedule. Not every commit results in a new version.

---

---

## 📋 Release Policy

We follow [Semantic Versioning](https://semver.org/):

- **Major** (v3.0.0): Breaking changes
- **Minor** (v2.5.0): New features, backward compatible  
- **Patch** (v2.1.2): Bug fixes only

### Release Schedule

- 🗓️ **Minor releases**: Every 2 weeks (feature batches)
- 🐛 **Patch releases**: As needed for critical bugs
- 🚨 **Hotfixes**: Within 24h for security issues

📖 See [Changelog.md](Changelog.md) for detailed version history.

---

---

## 🧪 Research Scope

Entelgia is an architectural experiment exploring:

* Persistent identity in LLM systems
* Internal tension as computational driver
* Memory-based regulation
* Dialogue-driven ethical modeling

It does **not** claim biological consciousness or sentience.

---

---

## 📰 News & Recognition

**January 2026** — Entelgia was featured by **Yutori AI Agents Research & Frameworks Scout** in their article *"New agent SDKs and skills with secure execution"*.

The article tracked six notable releases focused on plug-and-play enterprise integration, covering platform SDKs, multi-agent prototypes, API skill generation, secure execution, and batteries-included frameworks.

### 🌟 What They Said

> **"Entelgia was highlighted as a psychologically inspired multi-agent architecture – a research prototype designed for persistent identity and moral self-regulation through agent dialogue."**

The scout explained that such capabilities make Entelgia a **promising foundation for long-term customer service and personal-assistant contexts**.

---

### 🔬 Research Positioning

Entelgia was positioned alongside:
- **GitHub's Copilot SDK**
- **openapi-to-skills**
- **Bouvet**
- **antigravity-skills**
- **Deep Agents**

Together, these projects advance three operational levers:

| Lever | Description |
|-------|-------------|
| ⚡ **Faster Integration** | Seamless connection with existing applications |
| 🛡️ **Safer Execution** | Autonomous operation with security guarantees |
| 🎁 **Out-of-the-box Capabilities** | Pre-built functionality packs |

**Entelgia specifically represents the research path for stable, ethically consistent agents.**

---

### 📖 Read More

📢 **Full Article:** [New agent SDKs and skills with secure execution](https://scouts.yutori.com)

---

---

## 📄 License

Entelgia is released under the **MIT License**.

This ensures the project remains open, permissive, and compatible with the broader open‑source ecosystem, encouraging research, experimentation, and collaboration.

For the complete legal terms, see the `LICENSE` file included in this repository.

---

### Ethical Position

While the MIT License permits broad use, Entelgia was created as a **research‑oriented, human‑centered system** exploring reflective dialogue, moral self‑regulation, and internal cognitive structure.

The original creator, **Sivan Havkin**, does not endorse and is not responsible for applications that:

* Intentionally cause harm to human beings or other living creatures
* Enable coercion, manipulation, or exploitation
* Promote violence, hatred, or dehumanization
* Contradict the philosophical intent of the project

This statement expresses the ethical stance of the author but does not modify the legal permissions granted by the MIT License.

---

## 👤 Author

Conceived and developed by **Sivan Havkin**.

---

## 📊 Project Status

* **Status:** Research / Production Hybrid
* **Version:** 2.5.0 
* **Last Updated:** 18 February 2026

### What is "Research Hybrid"?

The "Research Hybrid" status signals that Entelgia is both a forward-looking research project and a robust, production-grade system.  
It sits at the intersection between academic experimentation and real-world application, blending innovative multi-agent algorithms and theoretical ideas with practical engineering, reliability and developer-friendly workflows. 

**This means:**
- Some modules (e.g. the dialogue engine, memory security, or agent persona modeling) feature experimental, cutting-edge methods that may evolve rapidly.
- At the same time, the system is designed to be stable, usable out-of-the-box, and robust enough for integration in real settings.
- Breaking changes and new features are introduced in a controlled way to balance innovation with stability.
- The project actively solicits both contributors interested in AI/agent research and users who need a dependable foundation for projects that require persistent, moral, and reflective AI agents.

This "hybrid" approach allows Entelgia to bridge the gap between the rapid pace of AI research and the needs of production-grade software.

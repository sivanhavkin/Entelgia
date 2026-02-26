<div style="display: flex; align-items: center; justify-content: space-between;">
  <img src="Assets/entelgia-logo.png" alt="Entelgia Logo" width="120" style="margin: 0;"/>
  <h1 style="flex-grow: 1; text-align: center; font-size: 2.5em; font-weight: bold; margin: 0;">🧠 Entelgia</h1>
  <div style="width: 120px;" aria-hidden="true"></div>
</div>

[![Python](https://img.shields.io/badge/Python-3.10+-blue)](https://docs.python.org/3.10/)
[![Status](https://img.shields.io/badge/Status-Research%20Hybrid-purple)](#-project-status)
[![Tests](https://img.shields.io/badge/tests-235%20passed-brightgreen)](https://github.com/sivanhavkin/Entelgia/actions)
[![License](https://img.shields.io/badge/license-MIT-green)](LICENSE)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://black.readthedocs.io/en/stable/)
[![Build Status](https://github.com/sivanhavkin/Entelgia/actions/workflows/ci.yml/badge.svg)](https://github.com/sivanhavkin/Entelgia/actions)
[![Flake8](https://img.shields.io/badge/lint-flake8-green)](https://flake8.pycqa.org/)  
[![Last Commit](https://img.shields.io/github/last-commit/sivanhavkin/Entelgia)](https://github.com/sivanhavkin/Entelgia/commits/main)
[![Maintenance](https://img.shields.io/maintenance/yes/2026)](https://github.com/sivanhavkin/Entelgia)
[![Docs](https://img.shields.io/badge/docs-online-blue.svg)](https://github.com/sivanhavkin/Entelgia/tree/main/docs)
[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.18752028.svg)](https://doi.org/10.5281/zenodo.18754895)
[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.18774720.svg)](https://doi.org/10.5281/zenodo.18774720)

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
* 🧪 **[Test Suite (tests/README.md)](tests/README.md)** - Full test documentation and CI/CD details

---

## 📄 Research Papers

**1. Internal Structural Mechanisms and Dialogue Stability in Multi-Agent Language Systems: An Ablation Study**

Sivan Havkin (2026)  
Independent Researcher, Entelgia Labs

DOI:
https://doi.org/10.5281/zenodo.18754895

This paper presents an ablation study examining how internal structural mechanisms influence dialogue stability and progression in multi-agent language systems.

**2. The Entelgia architecture is documented in the following research preprint:**

DOI: https://doi.org/10.5281/zenodo.18774720

This publication describes the cognitive-agent framework, META behavioral metrics,
and the reproducibility methodology behind the project.

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
python Entelgia_production_meta_200t.py
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
* **Enhanced Dialogue Engine**
  * Dynamic speaker selection — intelligent turn-taking (no 3+ consecutive turns)
  * Varied seed generation — 6+ strategy types (analogy, disagree, reflect, etc.)
  * Rich context enrichment — full dialogue history + thoughts + memories
  * Smart Fixy interventions — need-based meta-cognitive monitoring
  * Enhanced personas — deep character traits and speech patterns
  * 🐛 Dialogue bug fixes:
    * **Third body calling to first body** — fixed by tracking the last non-Fixy speaker
    * **Double turn** — duplicate Fixy response resolved by removing the legacy scheduled path
    * **Pronoun issue** — LLM-echoed prompt headers now stripped automatically when `show_pronoun=False`
* **⚡ Energy-Based Regulation**
  * FixyRegulator — meta-level energy supervisor with configurable safety threshold
  * Dream cycle consolidation — automatic recharge when energy falls below threshold; critical STM entries promoted to long-term memory
  * Hallucination-risk detection — stochastic check when energy is below 60 %
* **🧠 Personal Long-Term Memory System**
  * DefenseMechanism — classifies memories as repressed or suppressed on write
  * FreudianSlip — probabilistically surfaces defended memory fragments
  * SelfReplication — promotes recurring-pattern memories to consciousness
* **🎛️ Drive-Aware Cognition**
  * Dynamic LLM temperature — derived from id/ego/superego drive balance
  * Superego second-pass critique — response internally rewritten by a principled governor when `superego_strength ≥ 7.5`; the agent's original voice is always displayed in dialogue
  * Ego-driven memory depth — retrieval limits scale with ego/self-awareness
  * Output artifact cleanup — strips echoed name/pronoun headers, gender tags, scoring markers
  * Coherent drive correlations — conflict directly erodes ego capacity, raises LLM temperature, and scales energy drain
* **🗣️ Output Quality Rules**
  * Forbidden meta-commentary phrases — `validate_output()` removes sentences containing `"In our dialogue"`, `"We learn"`, or `"Our conversations reveal"`
  * Dissent marker capped to exactly one sentence — Athena's behavioral rule requires *exactly* one dissent opener (e.g. `"However,"`, `"Yet,"`)
  * Hard word truncation removed — response length governed solely by the LLM prompt instruction
* **📊 Dialogue Quality Metrics** (v2.6.0)
  * `circularity_rate` — fraction of turn-pairs with high topic-signature similarity; measures dialogue looping
  * `progress_rate` — forward steps per turn: topic shifts + synthesis markers + open-question resolutions
  * `intervention_utility` — mean circularity reduction in the post-Fixy window vs. pre-Fixy window
  * `compute_all_metrics()` — runs all three metrics in one call
* **🔬 Ablation Study** (v2.6.0)
  * 4-condition reproducible study: `BASELINE`, `DIALOGUE_ENGINE`, `FIXY`, `DREAM`
  * `run_ablation(turns, seed)` — fully reproducible across conditions; `print_results_table()` — formatted output
* **🔥 Drive Pressure** (v2.6.0)
  * Per-agent urgency/tension scalar `0.0–10.0` injecting conciseness directives at pressure ≥ 6.5 and decisive prompts at ≥ 8.0
  * Fluid drive dynamics: mean reversion and oscillation prevent monotonic drift
* **🚫 Forbidden Opener Phrases** (v2.6.0)
  * Agents no longer open with `"Recent thought"`, `"A recent thought"`, or `"I ponder"`
  * Cross-agent opener deduplication prevents repeated opening sentences
* **Psychological drive modeling** — id / ego / superego dynamics
* **Emotion tracking & importance scoring**
* **Dream cycles & memory promotion**
* **Observer-based meta-cognition**
* **Memory poisoning protection**
* **PII redaction & privacy safeguards**
* **Resilient error handling** (exponential backoff)
* **Structured logging**

---

## ⚙️ Configuration

Entelgia can be customized through the `Config` class in `Entelgia_production_meta.py`. Key configuration options:

### Core Session Settings

```python
config = Config()

config.max_turns = 200              # Maximum dialogue turns (default: 200)
config.timeout_minutes = 30         # Session timeout in minutes (set to 9999 to disable)
config.dream_every_n_turns = 7      # Dream cycle frequency (default: 7)
config.llm_max_retries = 3          # LLM request retry count (default: 3)
config.llm_timeout = 300            # LLM request timeout in seconds (default: 300)
config.show_pronoun = False         # Show agent pronouns in output (default: False)
config.show_meta = False            # Show meta-state after each turn (default: False)
config.stm_max_entries = 10000      # Short-term memory capacity (default: 10000)
config.stm_trim_batch = 500         # Entries pruned per trim pass (default: 500)
config.promote_importance_threshold = 0.72  # Min importance to promote to LTM (default: 0.72)
config.promote_emotion_threshold = 0.65     # Min emotion score to promote to LTM (default: 0.65)
config.store_raw_stm = False        # Store un-redacted text in STM (default: False)
config.store_raw_subconscious_ltm = False   # Store un-redacted text in LTM (default: False)
```

### Response Quality Settings

> **Note:** Response length is controlled by the module-level constant `MAX_RESPONSE_WORDS = 150`
> in `Entelgia_production_meta.py` (not a `Config` field). The LLM prompt instructs the model
> to answer in maximum 150 words; responses are never truncated by the runtime.

**Response Length Control:**
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

**Timeout Settings:**
- LLM request timeout is set to 300 s (`config.llm_timeout`) for faster failure detection
- Better user experience with more predictable behavior
- Most responses complete much faster than the timeout limit

### ⚡ Energy & Dream Cycle Settings

```python
config.energy_safety_threshold = 35.0  # Energy level that triggers a dream cycle (default: 35.0)
config.energy_drain_min = 8.0           # Minimum energy drained per step (default: 8.0)
config.energy_drain_max = 15.0          # Maximum energy drained per step (default: 15.0)
config.self_replicate_every_n_turns = 10  # Turns between self-replication scans (default: 10)
```

### Drive-Aware Cognition Settings

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
├── __init__.py              # Package exports (v2.6.0)
├── dialogue_engine.py       # Dynamic speaker & seed generation
├── enhanced_personas.py     # Rich character definitions
├── context_manager.py       # Smart context enrichment
├── fixy_interactive.py      # Need-based interventions
├── energy_regulation.py     # FixyRegulator & EntelgiaAgent (v2.5.0)
├── long_term_memory.py      # DefenseMechanism, FreudianSlip, SelfReplication (v2.5.0)
├── memory_security.py       # HMAC-SHA256 signature helpers
├── dialogue_metrics.py      # Circularity, progress & intervention utility metrics (v2.6.0)
└── ablation_study.py        # 4-condition reproducible ablation study (v2.6.0)
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
Entelgia_production_meta_200t.py  # 200-turn session, no time-based stopping
```

---

## 🧪 Test Suite

Entelgia ships with comprehensive test coverage across **235 tests** in 11 suites.

For full test documentation, per-suite details, CI/CD pipeline information, and sample output, see the **[Test Suite README (tests/README.md)](tests/README.md)**.

To run all tests:

```bash
pytest tests/ -v
```

---

---

## 📦 Version Information

| Version | Status | Notes |
|---------|--------|-------|
| **v2.6.0** | ✅ **Latest** | current |
| **v2.5.0** | ✅ **Stable** | previous stable release |
| **v2.4.0** | ⚠️ Superseded | Use v2.6.0 instead |
| **v2.3.0** | ⚠️ Superseded | Use v2.6.0 instead |
| **v2.2.0** | ⚠️ Superseded | Use v2.6.0 instead |
| **v2.1.1** | ⚠️ Superseded | Use v2.6.0 instead |
| v2.1.0 | ⚠️ Superseded | Use v2.6.0 instead |
| v2.0.01 | ⚠️ Superseded | Use v2.6.0 instead |
| v1.5 | 📦 Legacy | Production v2.0+ recommended |

💡 **Note:** Starting from v2.1.1, we follow a controlled release schedule. Not every commit results in a new version.

---

---

## 📋 Release Policy

We follow [Semantic Versioning](https://semver.org/):

- **Major** (v3.0.0): Breaking changes
- **Minor** (v2.6.0): New features, backward compatible  
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
* **Version:** 2.6.0 
* **Last Updated:** 26 February 2026
---

## 📚 Citation

If you use or reference this work, please cite:

```bibtex
@misc{havkin2026entelgia,
  author = {Havkin, Sivan},
  title = {Internal Structural Mechanisms and Dialogue Stability in Multi-Agent Language Systems: An Ablation Study},
  year = {2026},
  publisher = {Zenodo},
  doi = {10.5281/zenodo.18752028},
  url = {https://doi.org/10.5281/zenodo.18752028}
}
```
### What is "Research Hybrid"?

The "Research Hybrid" status signals that Entelgia is both a forward-looking research project and a robust, production-grade system.  
It sits at the intersection between academic experimentation and real-world application, blending innovative multi-agent algorithms and theoretical ideas with practical engineering, reliability and developer-friendly workflows. 

**This means:**
- Some modules (e.g. the dialogue engine, memory security, or agent persona modeling) feature experimental, cutting-edge methods that may evolve rapidly.
- At the same time, the system is designed to be stable, usable out-of-the-box, and robust enough for integration in real settings.
- Breaking changes and new features are introduced in a controlled way to balance innovation with stability.
- The project actively solicits both contributors interested in AI/agent research and users who need a dependable foundation for projects that require persistent, moral, and reflective AI agents.

This "hybrid" approach allows Entelgia to bridge the gap between the rapid pace of AI research and the needs of production-grade software.

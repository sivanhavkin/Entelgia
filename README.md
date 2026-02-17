# 🧠 Entelgia

[![Python](https://img.shields.io/badge/Python-3.10+-blue)](https://docs.python.org/3.10/)
[![Status](https://img.shields.io/badge/Status-Research%20Hybrid-purple)](#-project-status)
[![Tests](https://img.shields.io/badge/tests-24%20passed-brightgreen)](https://github.com/sivanhavkin/Entelgia/actions)
[![License](https://img.shields.io/badge/license-MIT-green)](LICENSE)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://black.readthedocs.io/en/stable/)
[![Build Status](https://github.com/sivanhavkin/Entelgia/actions/workflows/ci.yml/badge.svg)](https://github.com/sivanhavkin/Entelgia/actions)
[![Flake8](https://img.shields.io/badge/lint-flake8-green)](https://flake8.pycqa.org/)  
[![Last Commit](https://img.shields.io/github/last-commit/sivanhavkin/Entelgia)](https://github.com/sivanhavkin/Entelgia/commits/main)
[![Maintenance](https://img.shields.io/maintenance/yes/2026)](https://github.com/sivanhavkin/Entelgia)
[![Docs](https://img.shields.io/badge/docs-online-blue.svg)](https://github.com/sivanhavkin/Entelgia/tree/main/docs)


[![ See a conscious awareness demo](https://github.com/sivanhavkin/Entelgia/blob/main/DEMO_CONSCIOUS_DIALOGUE.md)

---

## Entelgia — A Dialogue-Governed Multi-Agent AI Architecture

**Entelgia** is an experimental multi-agent AI architecture designed to explore persistent identity, internal conflict dynamics, and emergent behavioral regulation through shared long-term memory and structured dialogue.

  Unlike stateless chatbot systems, Entelgia maintains an evolving internal state across sessions, enabling continuity of identity, memory persistence, and more coherent reflective behavior over time.


---

## 🚀 **AUTOMATIC INSTALL** (Recommended)

> **⚡ Get started fast with our automated installer!**

```bash
# Clone the repository
git clone https://github.com/sivanhavkin/Entelgia.git
cd Entelgia

# Run the automated installer
python install.py
```

📄 **View installer source:** [`install.py`](https://github.com/sivanhavkin/Entelgia/blob/main/install.py)

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
python demo_enhanced_dialogue.py

# Or run the full system (30 minutes)
python Entelgia_production_meta.py
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
python demo_enhanced_dialogue.py

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

```python
config = Config()

# Response length control (via LLM prompt instruction)
config.max_output_words = 150       # LLM prompt asks for maximum 150 words (default: 150)

# LLM timeout
config.llm_timeout = 60             # Seconds to wait for LLM response (default: 60, reduced from 600)
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
- Maximum timeout reduced from 10 minutes to 60 seconds
- Faster failure detection when LLM is unresponsive
- Better user experience with more predictable behavior
- Most responses complete much faster than the timeout limit

### Other Key Settings

```python
config.max_turns = 200              # Maximum dialogue turns
config.timeout_minutes = 30         # Session timeout in minutes
config.fixy_every_n_turns = 3      # Fixy observation frequency (legacy mode)
config.dream_every_n_turns = 7     # Dream cycle frequency
```

For the complete list of configuration options, see the `Config` class definition in `Entelgia_production_meta.py`.

---

## 🏗 Architecture Overview

Entelgia is built as a modular CoreMind system:

* `Conscious` — reflective narrative construction
* `Memory` — persistent identity continuity
* `Emotion` — affective weighting & regulation
* `Language` — dialogue-driven cognition
* `Behavior` — goal-oriented response shaping
* `Observer` — meta-level monitoring & correction

### 🆕 Enhanced Dialogue Module (v2.2.0+)

The new `entelgia/` package provides modular components:

```
entelgia/
├── __init__.py              # Package exports
├── dialogue_engine.py       # Dynamic speaker & seed generation
├── enhanced_personas.py     # Rich character definitions
├── context_manager.py       # Smart context enrichment
└── fixy_interactive.py      # Need-based interventions
```

**Key improvements:**
- 📊 **6 seed strategies** vs 1 simple template
- 🎯 **Dynamic speaker selection** vs ping-pong alternation
- 🧠 **Context-aware** with 8 turns + 6 thoughts + 5 memories
- 🔍 **Intelligent Fixy** detects circular reasoning, not just scheduled checks

The entire system runs as a unified executable Python file:

```
Entelgia_production_meta.py
```

---

## 📚 Documentation

* 📘 **[Full Whitepaper](whitepaper.md)** - Complete architectural and theoretical foundation
* 📄 **[System Specification (SPEC.md)](./SPEC.md)** - Detailed architecture specification
* 📖 **[Conscious Awareness Demo](./DEMO_CONSCIOUS_DIALOGUE.md)** - See the system in action
* ❓ **[Q&A / FAQ](Q&A.md)** - Frequently asked questions and answers
* 🔧 **[Troubleshooting Guide](TROUBLESHOOTING.md)** - Common issues and solutions

---

## 🧪 Test Suite

Entelgia ships with comprehensive test coverage:

### 🆕 Enhanced Dialogue Tests (5 tests)

```bash
python test_enhanced_dialogue.py
```

Tests verify:
- ✅ **Dynamic speaker selection** - No agent speaks 3+ times consecutively
- ✅ **Seed variety** - 6 different generation strategies
- ✅ **Context enrichment** - 8 turns, 6 thoughts, 5 memories
- ✅ **Fixy interventions** - Need-based (circular reasoning, repetition)
- ✅ **Persona formatting** - Rich traits and speech patterns

**Sample output:**
```
=== Test 1: Dynamic Speaker Selection ===
✓ PASS: No speaker spoke 3+ times consecutively

=== Test 2: Seed Variety ===
✓ PASS: Found 6 different seed strategies

=== Test 3: Context Enrichment ===
✓ PASS: All context enrichment checks passed

=== Test 4: Fixy Interventions ===
✓ PASS: Fixy intervention logic works correctly

=== Test 5: Persona Formatting ===
✓ PASS: Personas are rich and well-formatted

✅ ALL TESTS PASSED!
```

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

> ✅ **All 24 tests currently pass** (5 dialogue + 19 security), providing confidence that both the enhanced dialogue system and cryptographic memory-security mechanisms perform as expected.

---

### 🔄 CI/CD Pipeline

In addition to the unit tests, the continuous-integration (CI/CD) pipeline automatically runs a suite of quality and security checks:

| Category | Tools | Purpose |
|----------|-------|---------|
| **Unit Tests** | `pytest` | Runs 24 total tests (19 security + 5 dialogue) |
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
| **v2.3.0** | ✅ **Stable** | Latest release |
| **v2.2.0** | ⚠️ Superseded | Use v2.3.0 instead |
| **v2.1.1** | ⚠️ Superseded | Use v2.3.0 instead |
| v2.1.0 | ⚠️ Superseded | Use v2.3.0 instead |
| v2.0.01 | ⚠️ Superseded | Use v2.3.0 instead |
| v1.5 | 📦 Legacy | Production v2.0+ recommended |

💡 **Note:** Starting from v2.1.1, we follow a controlled release schedule. Not every commit results in a new version.

---

---

## 📋 Release Policy

We follow [Semantic Versioning](https://semver.org/):

- **Major** (v3.0.0): Breaking changes
- **Minor** (v2.3.0): New features, backward compatible  
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
* **Version:** 2.3.0 
* **Last Updated:** 16 February 2026

### What is "Research Hybrid"?

The "Research Hybrid" status signals that Entelgia is both a forward-looking research project and a robust, production-grade system.  
It sits at the intersection between academic experimentation and real-world application, blending innovative multi-agent algorithms and theoretical ideas with practical engineering, reliability and developer-friendly workflows. 

**This means:**
- Some modules (e.g. the dialogue engine, memory security, or agent persona modeling) feature experimental, cutting-edge methods that may evolve rapidly.
- At the same time, the system is designed to be stable, usable out-of-the-box, and robust enough for integration in real settings.
- Breaking changes and new features are introduced in a controlled way to balance innovation with stability.
- The project actively solicits both contributors interested in AI/agent research and users who need a dependable foundation for projects that require persistent, moral, and reflective AI agents.

This "hybrid" approach allows Entelgia to bridge the gap between the rapid pace of AI research and the needs of production-grade software.

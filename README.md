# 🧠 Entelgia

![Python](https://img.shields.io/badge/Python-3.10+-blue)
![Status](https://img.shields.io/badge/Status-Research%20Hybrid-purple)
[![Tests](https://img.shields.io/badge/tests-19%20passed-brightgreen)](...)
[![License](https://img.shields.io/badge/license-MIT-green)](LICENSE)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

<!-- שאר ה-README שלך -->
## A Consciousness-Inspired Multi-Agent AI Architecture

**Entelgia** is a multi-agent AI architecture that models persistent identity, internal conflict, and emergent moral regulation through shared long-term memory and structured dialogue.

Unlike stateless chatbot systems, Entelgia maintains evolving internal state across sessions — enabling identity continuity, emotional persistence, and reflective behavioral coherence.

---

## 📖 Whitepaper

For the full architectural and theoretical foundation:

📘 [whitepaper.md](whitepaper.md)

---

## ✨ Core Features

* **Multi-agent dialogue system** (Socrates · Athena · Fixy)
* **Persistent memory**

  * Short-term memory (JSON)
  * Long-term memory (SQLite)
  * 🔐 HMAC-SHA256 cryptographic integrity protection
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

## ⚡ Performance

* **Up to 50% fewer LLM calls** via LRU caching
* **Up to 70% lower token usage** through compression
* **Up to 2–3× faster** response times

---

## 🏗 Architecture Overview

Entelgia is built as a modular CoreMind system:

* `Conscious` — reflective narrative construction
* `Memory` — persistent identity continuity
* `Emotion` — affective weighting & regulation
* `Language` — dialogue-driven cognition
* `Behavior` — goal-oriented response shaping
* `Observer` — meta-level monitoring & correction

The entire system runs as a unified executable Python file:

```
Entelgia_production_meta.py
```

---

## 📋 Requirements

For the complete dependency list, see `requirements.txt`.

* Python **3.10+**
* **Ollama** (local LLM runtime)
* At least one supported model (`phi3`, `mistral`, etc.)
* **8GB+ RAM** recommended (16GB+ for larger models)

Install dependencies:

```bash
pip install -r requirements.txt
```
## 🚀 Installation

### Recommended Version

**Use v2.1.1** - This is the current stable release.

```bash
# Install from GitHub (recommended)
pip install git+https://github.com/sivanhavkin/Entelgia.git@v2.1.1

# Or clone and install
git clone https://github.com/sivanhavkin/Entelgia.git
cd Entelgia
pip install -e .
```

### 📦 Release Information

| Version | Status | Notes |
|---------|--------|-------|
| **v2.1.1** | ✅ **Stable** | Current recommended version |
| v2.1.0 | ⚠️ Superseded | Use v2.1.1 instead |
| v2.0.01 | ⚠️ Superseded | Use v2.1.1 instead |
| v1.5 | 📦 Legacy | Production v2.0+ recommended |

💡 **Note:** Starting from v2.1.1, we follow a controlled release schedule. Not every commit results in a new version.

### 🔄 Upgrading

If you're using an older version:

```bash
# Upgrade to latest
pip install --upgrade git+https://github.com/sivanhavkin/Entelgia.git@v2.1.1
```

---

## 📋 Release Policy

We follow [Semantic Versioning](https://semver.org/):

- **Major** (v3.0.0): Breaking changes
- **Minor** (v2.2.0): New features, backward compatible  
- **Patch** (v2.1.2): Bug fixes only

### Release Schedule

- 🗓️ **Minor releases**: Every 2 weeks (feature batches)
- 🐛 **Patch releases**: As needed for critical bugs
- 🚨 **Hotfixes**: Within 24h for security issues

+ 📖 See [Changelog.md](Changelog.md) for detailed version history.

---

## 🔧 Installing Ollama

Entelgia runs entirely on a **local LLM** for privacy, reproducibility, and execution control.

### 1️⃣ Download Ollama

👉 [https://ollama.com](https://ollama.com)

Supported:

* macOS
* Linux
* Windows (WSL recommended)

---

### 2️⃣ Pull a Model

```bash
ollama pull phi3
```

If you encounter `OLLAMA_HTTP_ERROR` or `EOF`, ensure Ollama is running.

Recommended models:

* **phi3 (3.8B)** – Fast & lightweight
* **mistral (7B)** – Balanced reasoning
* **neural-chat (7B)** – Strong conversational coherence
* **openchat (7B)** – Fast dialogue

> On 8GB RAM systems, prefer `phi3`.

---

### 3️⃣ Verify Installation

```bash
ollama run phi3 "hello"
```

If a response appears, Ollama is operational.

---

## 🚀 Quick Start

```bash
git clone https://github.com/sivanhavkin/Entelgia.git
cd Entelgia

pip install -r requirements.txt
ollama pull phi3

# Only if Ollama is not already running:
# ollama serve

python Entelgia_production_meta.py
```

Upon launch, memory initializes automatically and the agents begin structured dialogue.

---

## 🔐 Memory Security

Entelgia supports cryptographic integrity protection for memory entries.

To enable memory signing:

```bash
export MEMORY_SECRET_KEY="your-generated-key"
```

Generate a secure key:

```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

Security includes:

* HMAC-SHA256 signatures
* Tampering detection & rejection
* Constant-time comparison
* Environment-based key management
* Backward compatibility

Full documentation:

`docs/memory_security.md`

---

## 🧪 Research Scope

Entelgia is an architectural experiment exploring:

* Persistent identity in LLM systems
* Internal tension as computational driver
* Memory-based regulation
* Dialogue-driven ethical modeling

It does **not** claim biological consciousness or sentience.

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
* **Version:** v2.1.1
* **Last Updated:** 13 February 2026

# 🧠 Entelgia

![Python](https://img.shields.io/badge/Python-3.10+-blue)
![License](https://img.shields.io/badge/License-Entelgia%20Ethical%20MIT-green)
![Status](https://img.shields.io/badge/Status-Research%20Hybrid-purple)

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

Released under the **Entelgia License (Ethical MIT Variant with Attribution Clause)**.

The original creator does not endorse or take responsibility for uses that contradict the ethical intent of the system or cause harm to living beings.

---

## 👤 Author

Conceived and developed by **Sivan Havkin**.

---

## 📊 Project Status

* **Status:** Research / Production Hybrid
* **Version:** v1.0
* **Last Updated:** February 2026

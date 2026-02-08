# 🧠 Entelgia

## A Consciousness-Inspired Multi-Agent AI Architecture

**Entelgia** is a psychologically-inspired, multi-agent AI architecture designed to explore **persistent identity**, **emotional regulation**, **internal conflict**, and **moral self-regulation** through dialogue.

This repository presents Entelgia **not as a chatbot**, but as a **consciousness-inspired system** — one that **remembers**, **reflects**, **struggles**, and **evolves over time**.

Two primary agents engage in continuous, persistent dialogue driven by a **shared memory database**, allowing **emergent internal tension and moral reasoning** to arise naturally — rather than executing pre-defined rules.

---

## 🚨 Breaking Change

**Complete rewrite with a production-ready architecture**

This version represents a full architectural overhaul focused on robustness, performance, and long-term extensibility.

---

## ✨ Features

* **Multi-agent dialogue system** (Socrates · Athena · Fixy)
* **Persistent memory**

  * Short-term memory (JSON)
  * Long-term memory (SQLite)
* **Psychological drives**

  * Id / Ego / Superego dynamics
* **Emotion tracking & importance scoring**
* **Dream cycles & memory promotion**
* **LRU caching** (≈ 75% hit-rate improvement)
* **REST API** interface (FastAPI)
* **Unit testing** (9 tests, pytest)
* **10-minute auto-timeout**
* **PII redaction & privacy protection**
* **Resilient error handling** with exponential backoff
* **Full structured logging**

---

## ⚡ Performance

* **~50% reduction** in LLM calls via caching
* **~70% reduction** in token usage via compression
* **2–3× faster** response times

---

## 🏗 Architecture Overview

* ~**1,860 lines** of production-ready code
* **25+ classes** with full type hints
* **50+ documented functions**
* Modular core system:

  * `Memory`
  * `Emotion`
  * `Language`
  * `Conscious`
  * `Behavior`
  * `Observer`

---

## 💾 Memory Management

### Local Memory Storage

Entelgia stores memory locally on your machine using **SQLite** and **JSON** files.

### Memory Structure

```
entelgia_data/
├── entelgia_memory.sqlite    # Unified long-term memory database
├── stm_*.json                # Per-agent short-term memory
├── entelgia_log.csv          # Session logs and interaction history
├── entelgia_graph.gexf       # Memory graph exports (optional)
└── versions/                 # Version history
```

### Manual Memory Wipe (Reset)

To delete all stored memory and reset the system:

1. Stop the program
2. Delete the SQLite database:

   ```bash
   rm entelgia_data/entelgia_memory.sqlite
   ```
3. Delete per-agent short-term memory files:

   ```bash
   rm entelgia_data/stm_*.json
   ```
4. (Optional) Clear logs and graphs:

   ```bash
   rm entelgia_data/entelgia_log.csv
   rm entelgia_data/entelgia_graph.gexf
   rm -rf entelgia_data/versions/
   ```
5. Run the system again — files will be recreated automatically.

---

## 📝 Metaphor Disclaimer

Entelgia uses terms such as *consciousness*, *emotion*, *conflict*, and *self-regulation* as **architectural metaphors**, not claims of biological or phenomenological consciousness.

These concepts describe internal system dynamics such as:

* Memory prioritization and revisitation
* Competing objectives within dialogue
* Observer-based correction loops (meta-cognitive feedback)

The goal is not to simulate a mind, but to explore how **complex internal structure and moral tension** can emerge in autonomous AI systems through design.

---

## 🎯 Overview

### Core Capabilities

* ✅ Unified AI core implemented as a single runnable Python file (`Entelgia_production_meta.py`)
* ✅ Persistent agents with evolving internal state
* ✅ Emotion- and conflict-driven dialogue (not prompt-only)
* ✅ Dialogue continuity across sessions via shared memory
* ✅ Meta-cognitive monitoring and corrective feedback loops

---

## 🤖 The Agents

### Socrates — The Questioner

Reflective, questioning, and internally conflicted. Drives inquiry through doubt and self-examination. Serves as the primary agent for exploration and dialectical reasoning.

### Athena — The Synthesizer

Integrative and adaptive. Synthesizes emotion, memory, and reasoning, providing coherence and emotional context to Socrates’ inquiry.

### Fixy — The Observer (Meta-Cognitive Layer)

An architectural role designed to detect loops, errors, and blind spots, injecting corrective perspective shifts to prevent stagnation or logical fallacies.

---

## 📚 What This Is / What This Is NOT

### ✅ What This Is

* A research-oriented architecture inspired by psychology, philosophy, and cognitive science
* A system modeling **identity continuity**, not stateless interaction
* A platform for experimenting with:

  * Emotional regulation
  * Moral conflict and resolution
  * Self-reflection and meta-cognition
  * Meaning construction over time

### ❌ What This Is NOT

* Not a chatbot toy
* Not prompt-only roleplay
* Not safety-through-censorship
* Not a replacement for human judgment or ethics review

---

## 🧠 Core Philosophy

**Central Premise:** True regulation emerges from **internal conflict and reflection**, not external constraints.

Instead of relying on hard-coded safety barriers, Entelgia emphasizes:

* Moral reasoning through dialogue
* Emotional consequence tracking
* Responsibility and repair mechanisms
* Learning through error rather than suppression

**Consciousness as Process:** Consciousness is treated as a *process*, not a binary state. The system explores how reflective dialogue, memory continuity, and internal tension create emergent cognitive properties.

---

## 🏗️ Architecture — CoreMind

Entelgia is organized around six interacting cores:

1. **Conscious Core** — self-awareness, reflection, narrative construction
2. **Memory Core** — unified persistent SQLite memory with STM/LTM stratification
3. **Emotion Core** — dominant emotion detection, intensity, and regulation
4. **Language Core** — dialogue-driven cognition and adaptive phrasing
5. **Behavior Core** — goal-oriented intentional responses and consequence tracking
6. **Observer Core (Fixy)** — meta-level monitoring and corrective intervention

---

## 🗣️ Example: What Happens When You Run It

```text
[Session Start - Memory Loaded]

SOCRATES: "Athena, we revisited our discussion about intention yesterday.
          I notice I'm still uncertain: does responsibility require
          the ability to have chosen otherwise?"

ATHENA:   "Your uncertainty is not a flaw, Socrates. But remember—we also
          explored how emotional commitment shapes choice. Perhaps the
          question isn't about abstract possibility, but about what we
          genuinely care about."

[Emotion tracking: Socrates = Contemplative (0.7), Athena = Integrative (0.8)]
[Memory update: "responsibility-intention-link" promoted to long-term]

SOCRATES: "That's different from what I concluded before. Let me reconsider..."
```

---

## 💡 Ethics Model

Entelgia explores ethical behavior through **dialogue-based internal tension**, not enforced safety constraints.

* Ethical dynamics emerge implicitly through agent interaction
* Conflicting moral frameworks are expressed through dialogue
* Errors and contradictions trigger reflection and memory promotion

---

## 👥 Who This Is For

* Researchers exploring consciousness-inspired AI architectures
* Developers interested in persistent multi-agent dialogue systems
* Philosophers & psychologists studying computational models of self
* Contributors curious about AI systems that do more than respond

---

## 📋 Requirements

* Python **3.10+**
* **Ollama** (local LLM runtime)
* **8GB+ RAM** recommended (16GB+ for larger models)

---

## 🔧 Installing Ollama (Required)

Entelgia runs **entirely on a local LLM** for privacy, control, and reproducibility. You must install **Ollama** before running the system.

### Step 1: Download Ollama

Download Ollama for your operating system:

👉 [https://ollama.com](https://ollama.com)

Supported platforms:

* macOS
* Linux
* Windows (WSL recommended)

### Step 2: Install a Model

After installing Ollama, pull at least one supported model:

```bash
ollama pull phi3
```

Recommended models:

* **phi3 (3.8B)** – Fast, low memory, ideal for testing
* **mistral (7B)** – Balanced reasoning and performance
* **neural-chat (7B)** – Strong conversational coherence
* **openchat (7B)** – Fast and stable dialogue

> 💡 On systems with **8GB RAM**, prefer `phi3`. Larger models may be slow or unstable.

### Step 3: Verify Ollama Is Running

Run a quick test:

```bash
ollama run phi3 "hello"
```

If you see a response, Ollama is installed and working correctly.

---
**Requirements-**
* Python **3.10+**
* **Ollama** with a local LLM (e.g., `phi3`, `mistral`, `neural-chat`)
* **8GB+ RAM** recommended (16GB+ for larger models)
* **pip install** requests colorama fastapi uvicorn pytest networkx
* **Entelgia** will automatically attempt to install missing Python dependencies at runtime for convenience.

---

## 🚀 Quick Start

```bash
git clone https://github.com/sivanhavkin/Entelgia.git
cd Entelgia
ollama serve
python Entelgia_production_meta.py
```

---

## 📄 License

Released under the **Entelgia License (Ethical MIT Variant with Attribution Clause)**.

The original creator does not endorse or take responsibility for uses that contradict the ethical intent of the system or cause harm to living beings.

---

## 👤 Authorship

Conceived and developed by **Sivan Havkin**.

---

## 🤝 Contributing

Contributions are welcome. Please open an issue or discussion before submitting major changes.

---

## 📊 Project Status

* **Status:** Production / Research Hybrid
* **Version:** v1.0
* **Last Updated:** February 7, 2026

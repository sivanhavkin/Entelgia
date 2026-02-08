# Entelgia
## A Consciousness-Inspired Multi-Agent AI Architecture

# 🧠 Entelgia

**Entelgia** is a psychologically-inspired, multi-agent AI architecture designed to explore **persistent identity**, **emotional regulation**, **internal conflict**, and **moral self-regulation** through dialogue.

This repository presents Entelgia **not as a chatbot**, but as a **consciousness-inspired system** — one that **remembers**, **reflects**, **struggles**, and **evolves over time**.

Two primary agents engage in continuous, persistent dialogue driven by a **shared memory database**, allowing **emergent internal tension and moral reasoning** to arise naturally — rather than executing pre-defined rules.

---

## 🚨 Breaking Change

> **Complete rewrite with a production-ready architecture**

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
Entelgia stores memory locally on your machine using SQLite and JSON files.

**Memory Structure:**
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

1. **Stop the program**
2. **Delete the SQLite database:**
   ```bash
   rm entelgia_data/entelgia_memory.sqlite
   ```
3. **Delete per-agent short-term memory files:**
   ```bash
   rm entelgia_data/stm_*.json
   ```
4. **(Optional) Clear logs and graphs:**
   ```bash
   rm entelgia_data/entelgia_log.csv
   rm entelgia_data/entelgia_graph.gexf
   rm -rf entelgia_data/versions/
   ```
5. **Run the system again** — it will recreate the files automatically.

---

## 📝 Metaphor Disclaimer

Entelgia uses terms such as **consciousness**, **emotion**, **conflict**, and **self-regulation** as **architectural metaphors**, not as claims of biological or phenomenological consciousness.

These concepts describe internal system dynamics:
- **Memory prioritization** (what gets retained and revisited)
- **Competing objectives** (conflicting goals within dialogue)
- **Observer-based correction loops** (meta-cognitive feedback)

**The goal is not to simulate a mind, but to explore how complex internal structure and moral tension can emerge in autonomous AI systems through design.**

---

## 🎯 Overview

**Core Features:**
- ✅ Unified AI core implemented as a single runnable Python file (`entelgia_production_meta.py`)
- ✅ Persistent agents with evolving internal state
- ✅ Emotion- and conflict-driven dialogue, not prompt-only responses
- ✅ Dialogue continuity across sessions via shared persistent memory
- ✅ Meta-cognitive monitoring and corrective feedback loops


---

## 🤖 The Agents

### **Socrates** – The Questioner
Reflective, questioning, and internally conflicted; drives inquiry through doubt and self-examination. Serves as the primary agent for exploration and dialectical reasoning.

### **Athena** – The Synthesizer
Integrative and adaptive; synthesizes emotion, memory, and reasoning. Provides coherent frameworks and emotional context to Socrates' questions.

### **Fixy** – The Observer (Meta-Cognitive Layer)
A planned architectural role that detects loops, errors, and blind spots, injecting corrective perspective shifts to prevent stagnation or logical fallacies.

---

## 📚 What This Is / What This Is NOT

### ✅ What This Is
- A research-oriented architecture inspired by psychology, philosophy, and cognitive science
- A system modeling **identity continuity** rather than stateless interaction
- A platform for experimenting with:
  - Emotional regulation
  - Moral conflict and resolution
  - Self-reflection and meta-cognition
  - Meaning construction over time

### ❌ What This Is NOT
- Not a chatbot toy
- Not prompt-only roleplay
- Not safety-through-censorship
- Not a replacement for human judgment or ethics review

---

## 🧠 Core Philosophy

**Central Premise:** True regulation emerges from **internal conflict and reflection**, not from external constraints.

Instead of relying on hard-coded safety barriers, Entelgia emphasizes:
- **Moral reasoning** through dialogue
- **Emotional consequence** tracking
- **Responsibility and repair** mechanisms
- **Learning through error** rather than suppression

**Consciousness as Process:** Consciousness is treated as a **process**, not a binary state. The system explores how reflective dialogue, memory continuity, and internal tension create emergent cognitive properties.

---

## 🏗️ Architecture – CoreMind

Entelgia is organized around **six interacting cores**:

### **1. Conscious Core**
- Self-awareness and internal narrative construction
- Reflection on actions and responses
- Active sense-making and meaning integration

### **2. Memory Core**
- Single shared persistent SQLite database
- Memory continuity across agent turns and sessions
- Short-term and long-term memory stratification
- Memory promotion through error, emotion, and reflection
- Prepared for future distributed memory architectures

### **3. Emotion Core**
- Dominant emotion detection and tracking
- Emotional intensity and valence measurement
- Limbic reaction vs. regulatory modulation
- Emotion-driven memory prioritization

### **4. Language Core**
- Dialogue-driven cognition and reasoning
- Adaptive phrasing based on emotional and moral state
- Context-sensitive response generation

### **5. Behavior Core**
- Goal-oriented response selection
- Intentionality rather than reflex-based reactions
- Action commitment and consequence tracking

### **6. Observer Core (Fixy)**
- Defined as an architectural role (currently in planning phase)
- Meta-level monitoring of agent behavior
- Detection of loops, contradictions, and instability
- Corrective intervention and perspective injection

---

## 🗣️ Example: What Happens When You Run It

When you run `entelgia_unified_meta.py`, the system initiates an ongoing dialogue:

```
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

The agents:
- Maintain continuity across turns via unified memory store
- Revisit previously introduced concepts and themes
- Exhibit emerging internal tension through dialogue (not hard-coded rules)
- Track emotional states and allow them to influence reasoning
- Build on prior conversations naturally

---

## 💡 Ethics Model

Entelgia explores **ethical behavior through dialogue-based internal tension**, not enforced safety constraints.

**Current Approach:**
- Ethical dynamics emerge **implicitly** through agent interaction
- Conflicts between agents represent different moral frameworks
- Resolution attempts create reflective, growth-oriented dialogue
- Errors and contradictions trigger memory promotion and re-examination

**Future Direction:**
- Explicit ethical frameworks as dialogue agents
- Consequence tracking for moral decisions
- Integration of virtue ethics and consequentialist reasoning

---

## 👥 Who This Is For

- **Researchers** exploring early-stage consciousness-inspired AI architectures
- **Developers** interested in persistent multi-agent dialogue systems
- **Philosophers & Psychologists** examining computational models of self and conflict
- **Contributors** who want to help evolve experimental AI systems
- **Anyone curious** about AI systems that do more than respond

---

## 📋 Requirements

- **Python 3.10+**
- **Ollama** with a local LLM (e.g., `phi3:latest`, `mistral`, `neural-chat`)
- **8GB+ RAM recommended** (16GB+ for larger models)

### Prerequisites – Ollama

This project requires a local LLM runtime for privacy and control.

**Installation:**
1. Download Ollama from: https://ollama.com
2. After installation, pull a model:
   ```bash
   ollama pull phi3
   ```
3. Verify Ollama is running:
   ```bash
   ollama run phi3 "hi"
   ```

**Model Recommendations:**
- **phi3** (3.8B) – Fast, good for testing, limited depth
- **mistral** (7B) – Balanced performance and reasoning
- **neural-chat** (7B) – Good dialogue quality
- **openchat** (7B) – Fast and coherent

**Memory Note:** On systems with 8GB RAM, large models may be very slow. Consider using a smaller model like `phi3` or exploring API-based mode.

---

## 🚀 Quick Start

### 1. Clone the Repository
```bash
git clone https://github.com/sivanhavkin/Entelgia.git
cd Entelgia
```

### 2. Ensure Ollama is Running
```bash
ollama serve
```
(In a separate terminal window)

### 3. Run Entelgia
```bash
python entelgia_production_meta.py
```

### Expected Output
```
[Entelgia System Initialized]
[Loading persistent memory...]
[Memory state: 427 long-term entries, 12 active agent concepts]

[Session #47 - 2026-02-07]
SOCRATES: (from memory) "We were discussing..."
ATHENA: "Yes, and I've been reflecting on..."
```

### Exploring the Memory
- **View session logs:** `cat entelgia_data/entelgia_log.csv`
- **View memory graph:** Open `entelgia_data/entelgia_graph.gexf` in Gephi or similar
- **Inspect dialogue history:** Check `entelgia_data/stm_*.json` files

---

## 🗺️ Roadmap & Future Directions

### Current Phase (Research Prototype)
- [x] Unified core with persistent memory
- [x] Two-agent dialogue system (Socrates & Athena)
- [x] Emotion tracking and state evolution
- [x] Memory continuity across sessions
- [ ] Comprehensive testing and validation

### Near Term (Q1-Q2 2026)
- [ ] Implement Fixy (Observer) as active architectural layer
- [ ] Add explicit ethical framework agents
- [ ] Enhanced conflict resolution mechanisms
- [ ] Consequence tracking for actions and decisions
- [ ] Improved memory retrieval and prioritization

### Medium Term (Q3-Q4 2026)
- [ ] Distributed memory architecture
- [ ] Dynamic agent creation (emergence of new perspective agents)
- [ ] Integration with external knowledge bases
- [ ] Advanced meta-cognitive feedback loops
- [ ] Emotional learning and regulation refinement

### Long Term (2027+)
- [ ] Multi-session consciousness continuity experiments
- [ ] Integration with embodied systems
- [ ] Cross-instance memory and identity persistence
- [ ] Formal philosophical validation studies
- [ ] Open research collaboration framework

---
## Tests & Validation

Entelgia includes an integrated test suite focused on system stability, safety, and behavioral integrity, rather than narrow function-level correctness.

The tests are designed to validate that the system remains coherent, responsible, and resilient under evolving conditions.

### What the Tests Cover

Configuration Validation  
Ensures configuration values are within safe and meaningful ranges and prevents the system from starting with invalid or unsafe settings.

Short-Term Memory (LRU) Behavior  
Verifies that short-term memory behaves as a bounded LRU structure, ensuring older entries are discarded predictably without memory leaks or corruption.

Privacy & Redaction  
Confirms that sensitive information (such as emails, phone numbers, or identifiers) is properly redacted. Validates that raw sensitive content is not stored when privacy flags are disabled and prevents accidental exposure of private data in logs or memory.

System-Wide Validation  
Performs sanity checks across core components to ensure internal consistency and detect broken or partially initialized system states.

Metrics Tracking  
Ensures internal metrics such as turns, counters, and timestamps update reliably to support reproducibility and research-oriented analysis.

Topic Management  
Verifies correct topic cycling and rotation, preventing conversational stagnation or infinite agreement loops.

Behavior Core  
Validates importance scoring and basic behavioral responses while ensuring graceful handling of unexpected or malformed model outputs.

Language Core  
Confirms correct language state initialization and switching, preventing undefined or stuck language modes.

Observer (Fixy) Integrity  
Verifies that the Observer layer can detect issues and generate structured reports while ensuring corrective intervention remains proportional and non-intrusive.

### How Tests Are Run

Tests are executed via a built-in test runner:

python entelgia_production_meta.py test

No external testing framework is required at this stage. Core safety and behavior checks run automatically and are intended to evolve alongside the system.

### Design Philosophy

These tests are not intended to assert deterministic outputs from probabilistic models. Instead, they validate continuity over time, responsible memory handling, ethical boundary enforcement, and system coherence under uncertainty.

This reflects Entelgia’s core philosophy: regulation through internal structure and reflection, not external censorship.

---
## 📊 Project Status

Entelgia is an **actively evolving research prototype**.

**Last Updated:** February 7, 2026  
**Current Version:** Production v1.0 
**Stability:** Production

---

## 📄 License

This project is released under the **Entelgia License (Ethical MIT Variant with Attribution Clause)**.

It is open for study, experimentation, and ethical derivative work.

**The original creator does not endorse or take responsibility for uses that contradict the ethical intent of the system or cause harm to living beings.**

---

## 👤 Authorship

**Entelgia** was conceived and developed by **Sivan Havkin**.

The architecture and core ideas are original and evolve through ongoing research and experimentation.

---

## 🤝 Contributing

Contributions are welcome! Areas of particular interest:

- **Architecture improvements** – Refactoring and optimization
- **Memory research** – Novel persistence and retrieval mechanisms
- **Emotional modeling** – Expanding the emotion core
- **Ethical frameworks** – Adding structured moral reasoning
- **Testing & validation** – Dialogue quality and consistency testing
- **Documentation** – Clarifying the system for new researchers

Please open an issue or discussion before submitting significant changes.

---

## 📞 Contact & Discussion

- **Issues & Bug Reports:** GitHub Issues
- **Research Discussion:** GitHub Discussions
- **Direct Contact:** See repository profile

---

**Remember:** This is research code. Be curious, critical, and ethical in your exploration.

**Note: This release includes an updated runtime file uploaded as a release asset.**
**The main branch reflects the same version as of this release.**

---

# Entelgia
## A Consciousness-Inspired Multi-Agent AI Architecture

**Entelgia** is a psychologically-inspired, multi-agent AI architecture designed to explore **persistent identity**, **emotional regulation**, **internal conflict**, and **moral self-regulation through dialogue**.

This repository presents Entelgia not as a chatbot, but as a **consciousness-inspired system** — one that remembers, reflects, struggles, and evolves over time. Two primary agents engage in ongoing, persistent dialogue driven by a shared memory database, creating emergent internal tension and moral reasoning rather than executing pre-defined rules.

---

## 🔒 Security & Liability Notice

**This is an experimental research system.**

Users are responsible for:
- Reviewing and testing code before production deployment
- Implementing their own security measures
- Understanding the ethical implications of their use
- Complying with applicable laws and regulations

**Not recommended for:**
- Production systems without extensive security review
- Direct internet exposure
- Handling sensitive personal data
- Autonomous decision-making without human oversight

---

## ⚠️ Legal Disclaimer

Entelgia is provided **"as is"** without any warranty or liability.

The original creator is **NOT responsible** for:
- Misuse or abuse of the system
- Damages caused by use of this software
- Security breaches or vulnerabilities
- Use that contradicts the ethical intent of the system

**Use of this code is entirely at your own risk.**

---

## 🔬 Research Branch Notice

**Status:** Active Research Prototype

**Security & Safety:** This version includes additional security hardening and usage safeguards to reduce the risk of misuse and unintended behavior. These measures are experimental and part of ongoing research, not a claim of complete protection.

---

## 💾 Memory Management

### Local Memory Storage
Entelgia stores memory locally on your machine using SQLite and JSON files.

**Memory Structure:**
```bash
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
- ✅ Unified AI core implemented as a single runnable Python file (`entelgia_pitch1.5.py`)
- ✅ Persistent agents with evolving internal state
- ✅ Emotion- and conflict-driven dialogue, not prompt-only responses
- ✅ Dialogue continuity across sessions via shared persistent memory
- ✅ Meta-cognitive monitoring and corrective feedback loops

**At this stage**, the system functions as a research prototype focused on persistent dialogue and internal coherence, rather than a fully autonomous cognitive simulation.

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

### The Six Cores

**1. Conscious Core**
- Self-awareness and internal narrative construction
- Reflection on actions and responses
- Active sense-making and meaning integration

**2. Memory Core**
- Single shared persistent SQLite database
- Memory continuity across agent turns and sessions
- Short-term and long-term memory stratification
- Memory promotion through error, emotion, and reflection
- Prepared for future distributed memory architectures

**3. Emotion Core**
- Dominant emotion detection and tracking
- Emotional intensity and valence measurement
- Limbic reaction vs. regulatory modulation
- Emotion-driven memory prioritization

**4. Language Core**
- Dialogue-driven cognition and reasoning
- Adaptive phrasing based on emotional and moral state
- Context-sensitive response generation

**5. Behavior Core**
- Goal-oriented response selection
- Intentionality rather than reflex-based reactions
- Action commitment and consequence tracking

**6. Observer Core (Fixy)**
- Defined as an architectural role (currently in planning phase)
- Meta-level monitoring of agent behavior
- Detection of loops, contradictions, and instability
- Corrective intervention and perspective injection

### Memory Core Data Layout

```bash
entelgia_data/
├── entelgia_memory.sqlite    # Unified long-term memory
├── stm_*.json                # Per-agent short-term memory
├── entelgia_log.csv          # Session logs
└── entelgia_graph.gexf       # Memory graph exports
```

---

## 🗣️ Example: What Happens When You Run It

When you run `entelgia_pitch1.5.py`, the system initiates an ongoing dialogue:

```bash
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

| Model | Size | Speed | Reasoning | Best For |
|-------|------|-------|-----------|----------|
| **phi3** | 3.8B | Very Fast | Limited | Testing, low-resource systems |
| **mistral** | 7B | Fast | Good | Balanced performance |
| **neural-chat** | 7B | Fast | Good | Dialogue quality |
| **openchat** | 7B | Very Fast | Good | Fast inference |

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
python entelgia_pitch1.5.py
```

### Expected Output
```bash
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

## 📊 Project Status

Entelgia is an **actively evolving research prototype**.

**Last Updated:** February 7, 2026 04:58:42 UTC  
**Current Version:** Alpha (Persistent Dialogue)  
**Stability:** Experimental – Breaking changes may occur

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
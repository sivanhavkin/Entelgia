# 🧠 Entelgia: A Multi-Agent AI Architecture with Persistent Identity and Moral Self-Regulation Through Dialogue

**GitHub:** https://github.com/sivanhavkin/Entelgia  
**License:** MIT  
**Status:** Research/Production Hybrid (v2.3.0)

---

## TL;DR

I've been working on **Entelgia**, an experimental multi-agent AI architecture that explores how persistent identity, internal conflict, and moral reasoning can emerge from structured dialogue and shared long-term memory. Unlike stateless LLM systems, Entelgia maintains evolving internal state across sessions, enabling continuity of identity and reflective behavioral coherence.

**Core idea:** True regulation emerges from internal conflict and reflection, not external censorship.

---

## Motivation

Most contemporary AI systems are:  
- **Stateless** - No memory between sessions  
- **Prompt-reactive** - Only respond to immediate input  
- **Externally regulated** - Safety through hard-coded rules  
- **Session-bound** - Reset after each conversation

I wanted to explore whether **persistent identity, emotional continuity, and internal tension** could produce more coherent long-term behavior than purely reactive systems.

---

## Architecture Overview

### Three Primary Agents

1. **Socrates** — The Questioner (reflective, dialectical inquiry)  
2. **Athena** — The Synthesizer (integrative, emotional coherence)  
3. **Fixy** — The Observer (meta-cognitive monitoring, intervention when needed)

All agents share a **persistent memory system** with cryptographic integrity protection (HMAC-SHA256).

### Memory Stratification

**Short-Term Memory (STM):**  
- JSON-based, session-local  
- High-frequency updates  
- Volatile

**Long-Term Memory (LTM):**  
- SQLite-based, persistent across sessions  
- Indexed and structured  
- Cryptographically signed to prevent memory poisoning

### Internal Conflict Model

Entelgia integrates psychological metaphors structurally:  
- **Id** (impulse)  
- **Ego** (regulation)  
- **Superego** (moral constraint)

Internal tension arises when:  
- Emotional state conflicts with logical inference  
- Long-term memory contradicts present reasoning  
- Agents disagree in dialogue

This conflict triggers:  
- Reflective reconsideration  
- Memory promotion (STM → LTM)  
- Emotional recalibration

---

## Key Features

- **Enhanced Dialogue Engine** with dynamic speaker selection (no agent speaks 3+ times consecutively)  
- **6 seed generation strategies** (analogy, disagree, reflect, question, synthesize, challenge)  
- **Dream cycles** for memory consolidation  
- **Emotion tracking & importance scoring**  
- **PII redaction** for privacy  
- **Observer-based meta-cognition** (Fixy detects circular reasoning, repetition, logical inconsistencies)  
- **Memory poisoning protection** via cryptographic signatures  
- **100% local execution** (uses Ollama, no cloud dependencies)

---

## Technical Implementation

**Stack:**  
- Python 3.10+  
- Ollama (local LLM runtime)  
- SQLite (persistent memory)  
- FastAPI (REST API)  
- HMAC-SHA256 (memory integrity)

**Tested with:**  
- phi3 (3.8B) - Fast & lightweight  
- mistral (7B) - Balanced reasoning  
- neural-chat (7B) - Strong conversational coherence

**Quality Assurance:**  
- 24 passing tests (19 security + 5 dialogue)  
- CI/CD pipeline (black, flake8, mypy, safety, bandit)  
- Weekly dependency audits (pip-audit)

---

## Installation

### Automatic (Recommended)
```bash
git clone https://github.com/sivanhavkin/Entelgia.git
cd Entelgia
python install.py
```

The installer:  
1. Detects/installs Ollama  
2. Pulls the phi3 model  
3. Creates `.env` configuration  
4. Generates secure `MEMORY_SECRET_KEY`  
5. Installs dependencies

### Running
```bash
ollama serve
python demo_enhanced_dialogue.py  # Quick demo (~2 min)
python Entelgia_production_meta.py  # Full system (~30 min)
```

---

## Example: Conscious Awareness Demo

Here's what a typical dialogue looks like (shortened for brevity):

```
[Socrates]: "What does it mean to be aware of being aware?"

[Athena]: "Perhaps awareness layering creates recursive depth -  
each level reflecting on the one below, like mirrors facing mirrors."

[Fixy]: "I observe both agents circling the same conceptual territory.  
Let me inject: Can awareness exist without an observer to validate it?"

[Socrates]: "Ah, the validation paradox! Does the tree fall silently  
if no mind hears it?"
```

Full demo: [DEMO_CONSCIOUS_DIALOGUE.md](https://github.com/sivanhavkin/Entelgia/blob/main/DEMO_CONSCIOUS_DIALOGUE.md)

---

## Research Questions I'm Exploring

1. **Persistent Identity:** Can an AI system maintain coherent identity across sessions through memory continuity?  
2. **Internal Conflict as Driver:** Does modeling competing drives (Id/Ego/Superego) produce emergent regulation?  
3. **Dialogue-Driven Ethics:** Can moral reasoning emerge from structured multi-agent dialogue rather than hard-coded rules?  
4. **Memory-Based Regulation:** Does long-term memory of consequences shape future behavior?

**Important disclaimer:** Entelgia does **not** claim biological consciousness or sentience. It's an architectural experiment exploring how structured internal dynamics might give rise to emergent regulatory properties.

---

## What Makes This Different?

| Traditional LLMs | Entelgia |
|-----------------|----------|
| Stateless (no memory) | Persistent identity across sessions |
| Single response generation | Internal dialogue & conflict |
| External safety rules | Emergent moral self-regulation |
| Prompt → Response | Reflection → Tension → Resolution |
| Session-bound | Memory continuity (days/weeks) |

---

## Recognition

**January 2026** — Featured by **Yutori AI Agents Research & Frameworks Scout** in their article *"New agent SDKs and skills with secure execution"*.

> "Entelgia was highlighted as a psychologically inspired multi-agent architecture – a research prototype designed for persistent identity and moral self-regulation through agent dialogue."

Positioned as a **promising foundation for long-term customer service and personal-assistant contexts**.

---

## Current Limitations & Future Work

**Limitations:**  
- Requires 8GB+ RAM (16GB recommended for larger models)  
- Dialogue can become verbose (working on compression techniques)  
- Memory promotion logic is heuristic-based (exploring ML-based approaches)  
- Single-user focused (multi-user support planned)

**Future Directions:**  
- Multi-user memory isolation  
- Reinforcement learning for memory promotion  
- External tool integration (web search, calculators, etc.)  
- Cross-session learning experiments  
- Emotion evolution models

---

## Documentation

- **Whitepaper:** [whitepaper.md](https://github.com/sivanhavkin/Entelgia/blob/main/whitepaper.md)  
- **System Spec:** [SPEC.md](https://github.com/sivanhavkin/Entelgia/blob/main/SPEC.md)  
- **API Docs:** [docs/api/README.md](https://github.com/sivanhavkin/Entelgia/blob/main/docs/api/README.md)  
- **Troubleshooting:** [TROUBLESHOOTING.md](https://github.com/sivanhavkin/Entelgia/blob/main/TROUBLESHOOTING.md)

---

## Contributing

This is an active research project! I welcome:  
- Theoretical feedback on the architecture  
- Empirical observations from running experiments  
- Bug reports and code contributions  
- Ideas for new memory/emotion/conflict models

See: [Contributing.md](https://github.com/sivanhavkin/Entelgia/blob/main/Contributing.md)

---

## Questions for the Community

1. **Memory Consolidation:** What heuristics do you think work best for promoting short-term → long-term memory?  
2. **Conflict Resolution:** How should agents resolve disagreements? Voting? Weighted importance?  
3. **Emotion Modeling:** What's a good balance between emotional influence and logical consistency?  
4. **Evaluation Metrics:** How do we measure "coherent identity" across sessions?

---

## Links

- **GitHub:** https://github.com/sivanhavkin/Entelgia  
- **Quick Demo:** Try `demo_enhanced_dialogue.py` (2 minutes, 10 turns)  
- **Author:** Sivan Havkin  
- **License:** MIT

---

Looking forward to your thoughts, critiques, and ideas!  

AMA about the architecture, implementation choices, or philosophical motivations.

---

**Tags:** #MachineLearning #AI #MultiAgent #LLM #Ollama #LocalAI #Consciousness #EthicalAI #Research
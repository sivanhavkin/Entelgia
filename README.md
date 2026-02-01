**Note: This release includes an updated runtime file uploaded as a release asset.**
**The main branch reflects the same version as of this release.**


# Entelgia

**Entelgia** is a psychologically-inspired, multi-agent AI architecture designed to explore persistent identity, emotional regulation, internal conflict, and moral self-regulation through dialogue.

This repository presents Entelgia not as a chatbot, but as a *consciousness-inspired system* — one that remembers, reflects, struggles, and evolves over time.

---

## Overview

* **Unified AI core** implemented as a single runnable Python file (`entelgia_unified.py`)
* **Persistent agents** with evolving internal state
* **Emotion- and conflict-driven dialogue**, not prompt-only responses


---

## What Happens When You Run It

When you run the system, two primary agents engage in an ongoing dialogue driven by a **shared persistent memory database**.

They:

* Maintain continuity across turns via a unified memory store
* Revisit previously introduced concepts and themes
* Exhibit emerging internal tension through dialogue (not hard-coded rules)

At this stage, the system functions as a **research prototype** focused on persistent dialogue and internal coherence, rather than a fully autonomous cognitive simulation.

---

## The Agents

* **Socrates** – reflective, questioning, and internally conflicted; drives inquiry through doubt and self-examination
* **Athena** – integrative and adaptive; synthesizes emotion, memory, and reasoning
* **Fixy (Observer)** – meta-cognitive layer that detects loops, errors, and blind spots, and injects corrective perspective shifts

---

## What This Is

* A research-oriented architecture inspired by psychology, philosophy, and cognitive science
* A system modeling *identity continuity* rather than stateless interaction
* A platform for experimenting with:

  * Emotional regulation
  * Moral conflict
  * Self-reflection
  * Meaning construction over time

## What This Is NOT

* ❌ Not a chatbot toy
* ❌ Not prompt-only roleplay
* ❌ Not safety-through-censorship

---

## Core Philosophy

Entelgia is built on a central premise:

> **True regulation emerges from internal conflict and reflection, not from external constraints.**

Instead of relying on hard-coded safety barriers, the system emphasizes:

* Moral reasoning
* Emotional consequence
* Responsibility and repair
* Learning through error rather than suppression

Consciousness is treated as a *process*, not a binary state.

---

## Architecture – CoreMind

Entelgia is organized around six interacting cores:

### Conscious Core

* Self-awareness and internal narrative
* Reflection on actions and responses

### Memory Core

* **Single shared persistent database** 

* Memory continuity across agent turns

* Architecture prepared for future memory stratification

* Short-term and long-term memory

* Unified conscious and unconscious storage

* Memory promotion through error, emotion, and reflection

### Emotion Core

* Dominant emotion detection
* Emotional intensity tracking
* Limbic reaction vs. regulatory modulation

### Language Core

* Dialogue-driven cognition
* Adaptive phrasing based on emotional and moral state

### Behavior Core

* Goal-oriented response selection
* Intentionality rather than reflex

### Observer Core (Fixy)

* Defined as an architectural role

* Planned to act as a meta-cognitive monitor in future versions

* Meta-level monitoring

* Detection of loops and instability

* Corrective intervention

---

## Ethics Model

Entelgia explores ethical behavior through **dialogue-based internal tension**, not enforced safety constraints.

At present:

* Ethical dynamics emerge implicitly through agent interaction


---

## Who This Is For

* Researchers exploring early-stage consciousness-inspired AI architectures

* Developers interested in persistent multi-agent dialogue systems

* Philosophers and psychologists examining computational models of self and conflict

* Contributors who want to help evolve experimental AI systems

* Anyone curious about AI systems that do more than respond

---

## Requirements

* Python **3.10+**
* [Ollama](https://ollama.com) with a local LLM (e.g. `phi3:latest`)

---
**Prerequisites – Ollama**

This project requires a local LLM runtime.

Install Ollama
Download from: https://ollama.com

After installation, pull a model (example):

ollama pull phi3

Verify Ollama is running:

ollama run phi3 "hi"


  **Memory note:**
On systems with 8GB RAM, large models may be very slow.
Consider using a smaller model or API-based mode.


## Run

```bash

python entelgia_pitch1.5.py
```

---

## Project Status

Entelgia is an **actively evolving research prototype**.

---

## License

This project is released under the **Entelgia License (Ethical MIT Variant with Attribution Clause)**.

It is open for study, experimentation, and ethical derivative work.

The original creator does not endorse or take responsibility for uses that contradict the ethical intent of the system or cause harm to living beings.

---

## Authorship

Entelgia was conceived and developed by **Sivan Havkin**.
The architecture and core ideas are original and evolve through ongoing research and experimentation.

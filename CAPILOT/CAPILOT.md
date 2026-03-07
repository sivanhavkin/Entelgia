# Entelgia – Copilot Context

This file provides architectural context for AI coding assistants (GitHub Copilot, etc.).
Use it to understand the system structure before generating or modifying code.

---

# Project Overview

Entelgia is an experimental AI dialogue architecture exploring how internal
structure (memory, emotion, reflection, and observer feedback) shapes agent behavior.

The system runs multi-agent philosophical dialogue where agents evolve state
across turns.

The architecture focuses on:

- interpretability
- internal state
- behavioral stability
- self-regulation through observer feedback

---

# Core Agents

Three primary agents participate in dialogue.

## Socrates
Role:
- philosophical inquiry
- question generation
- conceptual probing

Typical behavior:
- Socratic questioning
- reflective reasoning
- epistemic exploration

## Athena
Role:
- synthesis and explanation
- integration of concepts
- structured reasoning

Typical behavior:
- expanding ideas
- connecting historical/philosophical context
- summarizing arguments

## Fixy
Role:
- observer / regulator

Responsibilities:
- detect conflicts
- detect loops
- detect unresolved tension
- intervene when necessary

Fixy may:
- redirect the dialogue
- synthesize positions
- correct errors

---

# Core Modules

## MemoryCore

Handles all memory layers.

Layers include:

1. Short-Term Memory (session context)
2. Long-Term Conscious Memory
3. Long-Term Subconscious Memory

Features:

- promotion rules
- emotional importance signals
- traceable storage
- persistence via SQLite

Important principle:

Not all stored information is consciously accessible.

---

## EmotionCore

Tracks emotional signals associated with dialogue turns.

Used as:

- an importance signal
- a routing signal
- a memory promotion trigger

Emotions influence:

- storage decisions
- behavioral responses
- dialogue tone

---

## BehaviorCore

Controls constraints and behavioral rules.

Includes:

- ethical constraints
- dialogue balance
- rule enforcement

BehaviorCore prevents:

- uncontrolled drift
- inconsistent reasoning
- rule violations

---

## LanguageCore

Handles language formatting and dialogue structure.

Responsibilities:

- message formatting
- system prompts
- context shaping
- language adaptation

---

## ConsciousCore

Tracks internal awareness signals.

Includes variables like:

- self-awareness
- ego / superego balance
- internal pressure
- unresolved tension

These signals affect dialogue direction.

---

# Dialogue Flow

Typical execution loop:

1. Select next agent
2. Build prompt context
3. Include memory signals
4. Include emotional state
5. Call LLM
6. Post-process response
7. Update internal state
8. Store memory
9. Observer (Fixy) evaluates dialogue

This cycle repeats for multiple turns.

---

# Observer Loop

Fixy monitors the dialogue.

Triggers may include:

- high conflict
- unresolved disagreement
- stagnation
- repetitive patterns

Possible actions:

- synthesis
- redirection
- clarification

---

# Web Research Module

Optional module enabling external information retrieval.

Pipeline:

1. detect research trigger
2. rewrite query
3. perform search
4. fetch pages
5. summarize results
6. inject research context

Safeguards include:

- cooldown between searches
- query sanitization
- context size limits

---

# Logging and Traceability

The system generates:

- dialogue logs
- CSV traces
- GEXF graph data
- session metadata

These outputs allow:

- reproducibility
- behavioral analysis
- visualization

---

# Design Principles

Important constraints for code generation:

1. Maintain modular architecture
2. Avoid tight coupling between cores
3. Preserve agent independence
4. Keep observer logic separate from dialogue generation
5. Prefer small, testable functions
6. Avoid hidden side effects

---

# When Modifying Code

AI assistants should:

- preserve existing architecture
- avoid rewriting unrelated modules
- prefer minimal patches
- keep interfaces stable

When unsure:

Explain the data flow before proposing changes.

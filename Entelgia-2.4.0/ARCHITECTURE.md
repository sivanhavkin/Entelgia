# Entelgia Architecture Overview

## Introduction

Entelgia is an experimental multi-agent AI architecture that explores how
persistent internal state, shared memory, and structured dialogue can govern
behavior beyond stateless prompt-response systems.

Instead of treating each interaction as isolated, Entelgia models continuity
through evolving agent state and dialogue-driven dynamics.

This document provides a high-level overview of the system structure and how
its components interact.

---

## High-Level Concept

Traditional chatbot systems operate as:

User Input → Prompt → Model → Response

Entelgia introduces an internal governance layer:

Topic → Dialogue → Internal State → Observation → Next Action

Behavior emerges from interaction between agents, memory, and an observer
mechanism rather than from a single prompt.

---

## Core Components

### Agents
Primary conversational entities with persistent identity.

Examples:
- **Socrates** — inquiry-driven reasoning
- **Athena** — synthesis and reflection

Agents maintain evolving internal variables such as drives, coherence,
and interaction history.

---

### DialogueEngine
Responsible for managing conversation dynamics.

Functions:
- speaker selection
- seed strategy selection
- dialogue pacing
- prevention of mechanical alternation

The engine enables adaptive turn-taking rather than fixed sequencing.

---

### ContextManager
Builds structured prompts for each interaction cycle.

Combines:
- agent persona
- recent dialogue history
- selected memory fragments
- internal state snapshot
- dialogue strategy seed

Its goal is contextual coherence under token constraints.

---

### Memory System

#### Short-Term Memory (STM)
- recent interaction buffer
- bounded size
- supports conversational continuity

#### Long-Term Memory (LTM)
- persistent storage across sessions
- relevance-based retrieval
- enables identity continuity

Memory influences behavior without requiring explicit recall in every turn.

---

### Observer Layer (Fixy)

Fixy acts as a meta-cognitive observer.

Responsibilities:
- detect dialogue loops
- identify instability or escalation
- suggest corrective interventions
- preserve dialogue quality

Fixy does not dominate conversation but regulates interaction when needed.

---

## System Flow

Below is a high-level flow depicting how the system processes a conversational turn:

1. **Topic/Prompt Initiation**  
   The system receives a new conversation topic or user prompt.

2. **DialogueEngine Selects Next Actor and Seed**  
   The DialogueEngine decides which agent speaks next and selects a dialogue strategy or "seed" for generating the next turn.

3. **ContextManager Assembles Interaction Context**  
   ContextManager gathers relevant context: 
   - the current agent's persona
   - dialogue history from Short-Term Memory
   - relevant fragments from Long-Term Memory
   - internal agent state  
   This context is used to build a structured prompt for the language model.

4. **Agent Produces Response**  
   The designated agent generates a response, updating its own internal state as appropriate.

5. **Memory Update**  
   The new interaction is appended to Short-Term Memory and, as needed, summarized or committed to Long-Term Memory.

6. **Observer Layer Engaged**  
   Fixy monitors for repetitive patterns, instability, or undesired conversational dynamics.
   If intervention is required, Fixy may suggest a new topic, adjust agent priorities, or flag anomalies.

7. **Cycle Repeats**  
   The loop resumes with the DialogueEngine evaluating the new state and planning the next conversational turn.

---

## Component Interaction Diagram

```
User/Topic
   |
   v
DialogueEngine
   |
   v
ContextManager
   |
   v
Agent ↔ Memory (STM/LTM)
   |
   v
Observer (Fixy)
   └─› feedback ─────────┘
```

---

## Summary

Entelgia moves beyond linear chatbot paradigms by employing a collective of agents with persistent state, adaptive dialogue governance, and meta-cognitive monitoring. Its architecture is designed for research into emergent conversational dynamics, self-correction, and long-term coherence.

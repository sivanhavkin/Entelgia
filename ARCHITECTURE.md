<div style="display: flex; align-items: center; justify-content: space-between;">
  <img src="Assets/entelgia-logo.png" alt="Entelgia Logo" width="120" style="margin: 0;"/>
  <h1 style="flex-grow: 1; text-align: center; font-size: 2.5em; font-weight: bold; margin: 0;">Entelgia Architecture Overview</h1>
  <div style="width: 120px;" aria-hidden="true"></div>
</div>

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

### Agents (`Agent` base class — `Socrates`, `Athena`, `Fixy`)
Primary conversational entities with persistent identity.

Examples:
- **Socrates** — inquiry-driven reasoning
- **Athena** — synthesis and reflection

Agents maintain evolving internal variables such as drives, coherence,
and interaction history. Each agent delegates cognitive sub-tasks to
core components (`ConsciousCore`, `EmotionCore`, `LanguageCore`, `BehaviorCore`).

---

### Core Mind Modules

| Class | Role |
|---|---|
| `ConsciousCore` | Reflective narrative construction; tracks the agent's self-model |
| `EmotionCore` | Affective state inference; weights memories and responses by emotion |
| `LanguageCore` | Pronoun and language preference management per agent |
| `BehaviorCore` | Goal-oriented response shaping; importance scoring and dream reflection |

---

### DialogueEngine (`SeedGenerator`, `DialogueEngine`)
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

### Memory System (`MemoryCore`)

#### Short-Term Memory (STM)
- recent interaction buffer
- bounded size
- supports conversational continuity

#### Long-Term Memory (LTM)
- persistent storage across sessions
- relevance-based retrieval (time-ordered via `ltm_recent`, emotion-weighted via `ltm_search_affective`)
- enables identity continuity
- records carry: content, topic, emotion, emotion_intensity, importance, source, promoted_from, intrusive, suppressed, signature_hex, **expires_at**, **confidence**, **provenance**

**Memory subsystems:**
- **Forgetting Policy** — per-layer TTL expiry; `ltm_apply_forgetting_policy()` purges stale rows each dream cycle.
- **Affective Routing** — `ltm_search_affective()` ranks by `importance × (1−w) + emotion_intensity × w`.
- **Confidence Metadata** — optional `confidence` and `provenance` columns on every LTM row.

Memory influences behavior without requiring explicit recall in every turn.

---

### Session & API Support

| Class | Role |
|---|---|
| `SessionManager` | Persist and restore dialogue sessions across restarts |
| `AsyncProcessor` | Concurrent agent processing via `asyncio` |
| `DialogRequest` | Pydantic model for REST API dialogue requests |
| `DialogResponse` | Pydantic model for REST API dialogue responses |

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
   |        |
   |        └─ DefenseMechanism → intrusive/suppressed flags
   |        └─ FreudianSlip     → surface defended memories
   |        └─ SelfReplication  → promote recurring patterns
   |
   v
FixyRegulator (energy supervision)
   └─ dream cycle ──────────────┘
   |
   v
Observer (Fixy)
   └─› feedback ─────────┘
```

---

## Summary

Entelgia moves beyond linear chatbot paradigms by employing a collective of agents with persistent state, adaptive dialogue governance, and meta-cognitive monitoring. Its architecture is designed for research into emergent conversational dynamics, self-correction, and long-term coherence.

---

### DrivePressure — Urgency/Tension 

**DrivePressure** is an invisible scalar (`0.0–10.0`) per agent that represents internal urgency to act now.
It is **not** a character or a voice — it is an urgency modulator.

**Why it exists:**
- Prevents "stable attractor" stagnation (endless SuperEgo-dominant framing loops)
- Reduces long moralized monologues when urgency is high
- Increases initiative: sharper questions, topic shifts, resolution attempts

**How it works:**

| Input | Effect on Pressure |
|---|---|
| High conflict (`conflict >= 4.0`) | Increases pressure |
| Open/unresolved questions | Increases pressure |
| Topic stagnation (same topic ≥ 4 turns) | Increases pressure |
| Low energy | Slightly increases pressure |
| Progress (resolved questions, new topic) | Pressure decays naturally |

**Behaviour thresholds:**

| Pressure | Effect |
|---|---|
| `< 6.5` | Normal behavior |
| `>= 6.5` | Output capped at 120 words; prompt: *"Be concise. Prefer 1 key claim + 1 sharp question."* |
| `>= 7.0` + SuperEgo > Ego | A/B binary dilemmas rewritten as "accept / resist / transform beyond both" |
| `>= 8.0` | Output capped at 80 words; prompt: *"Stop framing. Choose a direction. Ask one decisive question."* |

## Energy Regulation & Dream Cycles

### Overview

The Energy-Based Regulation System (v2.5.0) introduces cognitive energy as a first-class resource. Each agent carries an `energy_level` that depletes with every processing step and is restored only through a *dream cycle* — a consolidation pass that integrates pending memories.

### Components

| Component | Role |
|---|---|
| `FixyRegulator` | Meta-level supervisor; monitors energy against a safety threshold |
| `EntelgiaAgent` | Agent wrapper with dual memory stores and dream-cycle consolidation |

### Flow

```
process_step(input)
      |
      v
  _drain_energy()       ← 8–15 units per step
      |
      v
  append to conscious_memory
      |
      v
  FixyRegulator.check_stability()
      |
      ├─ energy <= threshold (35.0) → _run_dream_cycle() → RECHARGED_AND_READY
      ├─ energy < 60 %  → p=0.10 → HALLUCINATION_RISK_DETECTED
      └─ otherwise      → None (OK)
```

### Dream Cycle Phases

1. **Integration** — subconscious memories are merged into conscious memory; nothing is hard-deleted from long-term memory. Tagged with `provenance="dream_reflection"`.
2. **Relevance filtering** — short-term memory entries that are not emotionally or operationally relevant (empty / whitespace-only) are forgotten.
3. **Promotion** — high-salience STM entries are promoted to conscious LTM. Tagged with `provenance="dream_promotion"`.
4. **Forgetting sweep** — `ltm_apply_forgetting_policy()` deletes any LTM records whose `expires_at` has passed.
5. **Recharge** — `energy_level` is restored to 100.0.

### Integration Points

- `Config.energy_safety_threshold` (default `35.0`) — when an agent's energy drops to or below this value, Fixy forces a dream cycle (sleep/recharge).
- `Config.energy_drain_min` / `energy_drain_max` (default `8.0` / `15.0`) — per-step drain range.
- `entelgia/energy_regulation.py` — standalone module; importable without a live LLM.

---

## Drive-Aware Cognition

### Dynamic Temperature

Each `CoreMind` agent computes its LLM temperature from its current Freudian drive values on every turn:

```
temperature = max(0.25, min(0.95, 0.60 + 0.03*(id − ego) − 0.02*(effective_sup − ego)))
```

Higher `id_strength` → more creative; higher `superego_strength` → more constrained.
During limbic hijack, `effective_sup = superego × 0.3`, elevating temperature and uninhibiting responses.

### Limbic Hijack

**Limbic hijack** is an Id-dominant emotional override state (`agent.limbic_hijack: bool`). It models the psychoanalytic concept of the limbic system overpowering rational, regulatory control.

**Activation** (checked at the start of every `speak()` call):

```python
if ide > 7 and emotion_intensity > 0.7 and conflict_index() > 0.6:
    agent.limbic_hijack = True
```

**Behavioral effects while active:**

| Effect | Detail |
|---|---|
| Reduced SuperEgo influence | `effective_sup = sup × LIMBIC_HIJACK_SUPEREGO_MULTIPLIER` (0.3) |
| Elevated temperature | Computed using `effective_sup` — less restraint |
| SuperEgo critique suppressed | `effective_sup` passed to `evaluate_superego_critique`; rarely dominant |
| Impulsive response kind | `response_kind = "impulsive"` fed into drive update loop |

**Exit conditions:**

- Immediate: `emotion_intensity < 0.4`
- Automatic: after `LIMBIC_HIJACK_MAX_TURNS = 3` consecutive turns without re-trigger

**Meta output** (when `show_meta=True`):

```
[META] Limbic hijack engaged — emotional override active
```

### Superego Second-Pass Critique

When `superego_strength ≥ 7.5` (and no limbic hijack is active), the initial response is rewritten by the LLM at `temperature=0.25` with a principled internal-governor prompt. This models the ego-superego tension: id produces a raw response; superego revises it.

### Ego-Driven Memory Retrieval Depth

| Limit | Formula | Range |
|---|---|---|
| `ltm_limit` | `int(2 + ego/2 + self_awareness×4)` | 2 – 10 |
| `stm_tail` | `int(3 + ego/2)` | 3 – 12 |

Agents with stronger ego / higher self-awareness pull deeper context and stabilise faster after reset.

### Output Artifact Cleanup

`speak()` performs a final cleanup pass after all validate/critique steps:
1. Strips the LLM-echoed agent name/pronoun prefix (e.g. `"Socrates (he): "`)
2. Removes gender script tags: `(he):`, `(she)`, `(they)`
3. Removes stray scoring markers: `(5)`, `(4.5)`
4. Truncates to `MAX_RESPONSE_WORDS = 150` at a word boundary

---

## Long-Duration Dialogue

`Entelgia_production_meta_200t.py` provides a turn-count-gated variant of the main runner:

```python
class MainScriptLong(MainScript):
    def run(self):
        while self.turn_index < self.cfg.max_turns:
            ...  # no timeout check
```

- Uses `Config(max_turns=200, timeout_minutes=9999)` to disable time-based stopping.
- All other behaviour (memory, emotions, Fixy, dream cycles, logging) is inherited unchanged.
- Run via: `python Entelgia_production_meta_200t.py`

---



## Web Research Pipeline (v2.8.0)

Entelgia can retrieve current information from the web and inject it into the
internal agent dialogue.  The pipeline is entirely optional and modular — it
runs only when Fixy detects that the user message requires external knowledge.

### Pipeline Overview

```
User Input
↓
fixy_research_trigger.fixy_should_search()   ← keyword detection
↓ (if True)
web_tool.search_and_fetch()                  ← DuckDuckGo + BeautifulSoup
↓
source_evaluator.evaluate_sources()          ← heuristic credibility scoring
↓
research_context_builder.build_research_context()  ← LLM-ready context block
↓
Injected into ContextManager.build_enriched_context() as web_context
↓
Agents discuss with "External Knowledge Context" section in their prompts
↓
High-credibility sources (score > 0.6) stored in external_knowledge SQLite table
```

### Modules

| Module | Purpose |
|--------|---------|
| `entelgia/web_tool.py` | `web_search` (DuckDuckGo HTML), `fetch_page_text` (BeautifulSoup), `search_and_fetch` |
| `entelgia/source_evaluator.py` | Domain-based + text-length credibility scoring |
| `entelgia/research_context_builder.py` | Formats top-3 sources as structured LLM prompt section |
| `entelgia/fixy_research_trigger.py` | Keyword set trigger: `latest`, `research`, `news`, `current`, `today`, `web`, `find`, `search`, `paper`, … |
| `entelgia/web_research.py` | `maybe_add_web_context` — full orchestration + optional LTM persistence |

### Agent Instructions Injected with Web Context

```
Instructions for agents:
- Superego must verify credibility of external sources.
- Ego must integrate sources into the reasoning.
- Id may resist heavy research if energy is low.
- Fixy monitors reasoning loops and source reliability.
```

### Safety Constraints

- Request timeout: 10 seconds per network call
- Results limited to 5 sources by default
- Text extracted from pages capped at 6 000 characters
- All errors are caught and logged; the main pipeline always continues
- Memory storage only for sources with `credibility_score > 0.6`

---

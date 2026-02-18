 **Entelgia** — System Specification (Research Prototype)

 **Entelgia is a dialogue-governed cognitive simulation:** behavior emerges from **internal state + meta-observation**, not from prompts alone.

   This document defines the **“laws of physics”** of Entelgia: the runtime loop, state model, dialogue policy, observer policy (Fixy), and the signals we can measure.



## 0) Scope & Non-goals

### Scope
- Multi-agent dialogue where **speaker selection** and **seed strategy** can be **dynamic**
- Internal state that shapes output: **persona, drives, memory, reflection**
- A meta-observer (**Fixy**) that intervenes **only when needed**

### Non-goals (for now)
- Production stability / SLA
- Safety guarantees beyond basic guardrails
- A polished “agent framework” API

---

## 1) Core Entities

### Agents
- **Socrates** — inquiry / structure / meaning-making
- **Athena** — creativity / synthesis / perspective shifts
- **Fixy** — observer/fixer layer; meta-cognitive intervention policy

Each agent has:
- `name`, `model`
- `persona` (string or rich dict)
- `drives` (internal state vector)
- access to memory (STM/LTM)
- a prompt builder (legacy or enhanced)

### Dialogue History
- `dialog_history`: ordered list of turns `{ role, text, metadata? }`
- used for speaker selection, seed generation, context building, and observer signals

### Dialogue Engine (Enhanced Mode)
Responsible for:
- dynamic **speaker selection**
- dynamic **seed generation** (strategy rotation)
- allowing Fixy as speaker with a probability when appropriate

### Context Manager (Enhanced Mode)
Responsible for building an **enriched prompt** with controlled token usage:
- `dialog_tail` (e.g., last 8 turns)
- `thoughts` (internal reflections if available)
- `memories` (selected LTM + recent STM)
- persona formatted by drives (if rich persona available)

### Enhanced Memory Integration (Enhanced Mode)
Retrieves **relevant** memories rather than “most recent only”:
- topic-aware selection
- dialog-aware relevance scoring
- returns a bounded set (e.g., up to 8 items)

### Interactive Fixy (Enhanced Mode)
Need-based intervention:
- analyzes dialog patterns
- decides *if* and *why* to intervene
- generates a short actionable intervention message



## 2) Runtime Loop (“Physics Loop”)

### High-level loop
1. **Select next speaker**
2. **Select topic**
3. **Generate seed** (instruction + strategy)
4. **Build prompt** (enhanced or legacy)
5. **LLM generates response**
6. **Log + print**
7. **Update memory + drives**
8. **Fixy intervention** (need-based or scheduled)
9. **Dream/Reflection cycle** (if enabled)

### Pseudocode
```python
while session_active:
    turn += 1
    
    topic = TopicManager.current()

    speaker = select_speaker(dialog_history, turn)  # dynamic or alternation
    
    seed = generate_seed(topic, dialog_history, speaker, turn)  # dynamic or default

    prompt = speaker.build_prompt(seed, dialog_history)  # enhanced or legacy

    out = LLM.generate(model=speaker.model, prompt=prompt)

    dialog_history.append({"role": speaker.name, "text": out})
    log_turn(speaker.name, out, topic)

    speaker.store_turn(out, topic)               # memory write
    speaker.update_drives_after_turn(...)        # state update

    maybe_fixy_intervene(dialog_history, turn)

    maybe_dream_cycle(turn)
```

## 3) Modes: Enhanced vs Legacy

### Enhanced Mode

Enabled when enhanced modules are importable and `use_enhanced=True`.

* `DialogueEngine` selects speaker + seeds
* `ContextManager` builds enriched context
* `EnhancedMemoryIntegration` selects relevant LTM
* `InteractiveFixy` intervenes on patterns, not on a timer

### Legacy Mode

Fallback when enhanced modules are missing or disabled.

* Speaker selection: simple alternation (Socrates ↔ Athena)
* Seed: static default instruction
* Prompt: compact legacy prompt
* Fixy: scheduled every N turns

**Guarantee:** System remains runnable even without enhanced modules.

---

## 4) State Model

### 4.1 Short-Term Memory (STM)

* recent turns / working memory buffer
* bounded by `stm_max_entries`
* trimmed in batches (`stm_trim_batch`)

### 4.2 Long-Term Memory (LTM)

* persistent store (e.g., SQLite)
* may contain layers (e.g., `conscious`, `subconscious`) depending on build
* accessed either “recent” (legacy) or “relevant” (enhanced)

### 4.3 Drives / Internal Variables

A compact agent state vector (examples):

* emotional_state / arousal / coherence
* conflict index
* self-awareness level
* other agent-specific parameters

These are updated after each turn via:

* response kind (e.g., disagreement / reflection / analogy)
* detected emotion + intensity (if enabled)
* intervention events

### 4.4 Persona

Two representations:

* **Simple**: string description embedded in prompt
* **Rich**: dict with structured traits + a function that formats a persona text based on current drives

---

## 5) Speaker Selection Policy

### Goal

Create dialogue that is:

* less mechanical than strict alternation
* sensitive to context + momentum
* optionally includes Fixy when needed

### Policy (Enhanced)

* Turn 1: start with Socrates (default)
* After that:

  * compute eligibility of Fixy (allow + probability)
  * select next speaker based on:

    * last speaker
    * dialog dynamics (stagnation, conflict, drift)
    * strategy needs (balance between inquiry vs synthesis)

### Policy (Legacy)

* `Socrates` on odd turns, `Athena` on even turns

---

## 6) Seed Strategy Policy

### Goal

Avoid repetitive dialogue loops by rotating cognitive strategies.

Example seed strategies (illustrative):

* analogy
* disagreement
* reflection
* assumption-check
* synthesis
* question-generation

### Policy

* DialogueEngine chooses a seed strategy based on:

  * last K turns
  * detected stagnation / looping
  * topic drift
  * agent role (Socrates vs Athena)
* Fixy (if speaking) uses a short corrective/meta seed or intervention prompt.

---

## 7) Prompt Construction Policy

### Enhanced Prompt (ContextManager)

Target composition (example):

* Persona (formatted)
* Drives snapshot
* Debate profile (agent style)
* Recent dialog tail (e.g., 8 turns)
* STM (selected summary)
* LTM (relevant memories, bounded)
* Seed / instruction

Token control:

* truncation rules prioritize: persona → dialog_tail → relevant LTM → STM

### Legacy Prompt

Compact prompt with:

* minimal persona
* minimal recent LTM
* last few STM turns
* seed

---

## 8) Observer Policy (Fixy)

### Fixy’s role

Fixy is a **meta-cognitive guardian**, not a participant competing for answers.

Fixy should:

* detect patterns that degrade dialogue quality
* point out contradictions / loops / escalating conflict
* propose a small corrective action
* teach (optional) via short structured hints

Fixy must NOT:

* dominate the conversation
* produce long philosophical essays
* override the agents’ autonomy every turn
* inject unrelated topics

### Intervention triggers (examples)

* **Looping / circular debate**
* **Escalation** (conflict index rising)
* **Shallow agreement** (no new angles for N turns)
* **Topic drift**
* **Persona collapse**

### Intervention style

* brief
* concrete
* actionable
* optionally: 1 question + 1 suggestion

---

## 9) Evaluation Signals (What We Measure)

### Minimal signals

* **Loop Rate**: repetition patterns per 100 turns
* **Fixy Frequency**: interventions per 50 turns
* **Topic Drift**: loss of topic continuity
* **Novelty Ratio**: new concepts introduced per N turns
* **Conflict Index**: internal conflict trend (if implemented)

### Interpretation

* High loop rate + high Fixy frequency → seed policy needs tuning
* High drift + low novelty → context too thin
* Low Fixy frequency + rising conflict → intervention threshold too high

---

## 10) Reproducibility & Debugging

### Run determinism

* Not guaranteed (LLM stochasticity)
* For experiments: fix temperature and seed ordering

### Logging (recommended)

* turn index, speaker, topic
* seed strategy used
* enhanced/legacy mode flag
* Fixy intervention reason

---

## 11) Quick Mental Model Diagram

```text
Topic ───────────────► SeedStrategy ───────────► Prompt
   │                      ▲                        │
   │                      │                        ▼
   └──► DialogueEngine ───┴─► SpeakerSelect ───► LLM Generate
              │                                      │
              ├──► allow_fixy? / fixy_prob           ▼
              │                                 Turn Output
              ▼                                      │
   InteractiveFixy ◄──────── dialog_history ─────────┘
              │
              ▼
        Intervention (optional)

Memory:
STM/LTM ──► EnhancedMemoryIntegration ─► ContextManager prompt enrichment
```

---

## 12) What Counts as Working in Entelgia

A session is considered working when:

* dialogue does not collapse into mechanical alternation (enhanced)
* strategies rotate and create new angles
* Fixy remains sparse but meaningful
* memory surfaces relevant prior context
* agents maintain distinct voices over time

---

## Appendix: Config Expectations (Example)

* `fixy_every_n_turns`
* `dream_every_n_turns`
* `promote_importance_threshold`
* `promote_emotion_threshold`
* `enable_auto_patch`
* `allow_write_self_file`

---

**Status:** Experimental / research-oriented.
PRs should preserve: internal-state governance, meta-observer policy, and reproducible evaluation signals.


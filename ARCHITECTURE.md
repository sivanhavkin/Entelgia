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
- **Socrates** — investigative, domain-aware inquiry; probes assumptions with domain-relevant questioning
- **Athena** — synthesis and framework building; structures explanations in the vocabulary of the active topic domain
- **Fixy** — diagnostic observer; detects contradictions and reasoning gaps specific to the domain

Agents maintain evolving internal variables such as drives, coherence,
and interaction history. Each agent delegates cognitive sub-tasks to
core components (`ConsciousCore`, `EmotionCore`, `LanguageCore`, `BehaviorCore`).

At session start, each agent receives a **topic-aware style instruction** derived from the
seed topic cluster (via `entelgia/topic_style.py`) so that reasoning adapts to the domain
rather than defaulting to abstract philosophical language.

---

### Topic-Aware Style System (`entelgia/topic_style.py`)

Two cooperating layers control the linguistic register agents use:

**Layer 1 — Cluster-to-Style Mapping** (`TOPIC_STYLE` dict)
`get_style_for_topic(topic, topic_clusters)` returns a `(cluster, style)` tuple.
`build_style_instruction(style, role, cluster)` generates a per-role style instruction injected into every prompt.

**Layer 2 — Mandatory Register Control** (`TOPIC_TONE_POLICY` dict)
Each cluster entry specifies:
- `allowed_registers` — e.g., `technical`, `scientific`, `mechanistic`
- `forbidden_registers` — e.g., `philosophical`, `theatrical`, `poetic`
- `forbidden_phrases` — specific strings to suppress (e.g., `"my dear friend"`, `"intricate dance"`)
- `preferred_cues` — vocabulary nudges (e.g., `"architecture"`, `"mechanism"`, `"evidence"`)
- `response_mode` — expected output type (e.g., `concrete_analysis`, `tradeoff_analysis`)

**`scrub_rhetorical_openers(text, cluster)`** — post-generation cleanup pass that strips legacy theatrical openers for non-philosophy topics via `_RHETORICAL_OPENERS` regex patterns.

**`DEFAULT_TOPIC_CLUSTER = "technology"`** — fallback when classification fails.

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

**`AgentMode` constants** shape the generated seed on a per-turn basis when Fixy's loop-guard signals demand it:

| Mode | Behaviour |
|---|---|
| `NORMAL` | Default; no additional directive |
| `CONTRADICT` | Force a sharper contradiction; demand a binary choice |
| `CONCRETIZE` | Demand a real-world case or counter-example (no abstract restatement) |
| `INVERT` | Temporarily defend the opposite position |
| `MECHANIZE` | Demand a step-by-step causal process |
| `PIVOT` | Force a genuine domain shift away from the current cluster |

`_LOOP_AGENT_POLICY` maps each `DialogueLoopDetector` failure mode to the appropriate `AgentMode`.

---

### ContextManager
Builds structured prompts for each interaction cycle.

Combines:
- agent persona
- recent dialogue history
- selected memory fragments
- internal state snapshot
- dialogue strategy seed
- **topic-aware style instruction** (injected from `topic_style.py` based on the seed topic cluster)

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

Fixy acts as a **meta-cognitive observer** — not a supervisor. As of v5.5.0, `IntegrationCore` (the executive cortex) is the sole supervisory authority; Fixy's last message is read by the controller as a **soft signal source** only. The mapping from Fixy hints to intervention modes is controller-owned, never Fixy-owned.

Fixy responsibilities:
- detect dialogue loops via `DialogueLoopDetector` (4 failure modes)
- identify instability or escalation
- reflect the structure of disagreement back without imposing a resolution path
- preserve dialogue quality via a staged intervention ladder

Fixy does **not**:
- block or force-regenerate agent responses
- act as a gatekeeper for post-generation validation
- fire `FIXY_AUTHORITY_OVERRIDE` (removed in v5.5.0)

**Staged intervention ladder:**

| Level | Mode | When activated |
|---|---|---|
| 0 | `SILENT_OBSERVE` | Pair threshold not met |
| 1 | `SOFT_REFLECTION` | First eligible pair |
| 2 | `GENTLE_NUDGE` | Second eligible pair |
| 3 | `STRUCTURED_MEDIATION` | Third+ eligible pair |
| 4 | `HARD_CONSTRAINT` | ≥ 8 turns **and** ≥ 3 full pairs, no `NEW_CLAIM` moves in recent turns |

Hard modes are additionally blocked when `NEW_CLAIM` moves (detected via `progress_enforcer.classify_move`) are still arriving, preventing premature deadlock declarations.

**`generate_fixy_analysis()`** — returns a typed dict `{intervention_mode, dialogue_read, missing_element, suggested_vector, urgency}` before rendering, giving the controller full authority to show, suppress, or escalate.

**`topic_pipeline_enabled(cfg)`** — single authoritative predicate (exported from `entelgia/topic_enforcer.py`) replacing all ad-hoc `CFG.topics_enabled` checks. When `False`, the entire topic pipeline is a strict no-op with zero topic-related log output.

**Semantic repetition detection** — `InteractiveFixy._detect_repetition` combines Jaccard keyword overlap with sentence-embedding cosine similarity (via `sentence-transformers/all-MiniLM-L6-v2`, now a core dependency). Degrades gracefully to Jaccard-only when the library is absent (`_SEMANTIC_AVAILABLE = False`).

**Observer toggle** — set `Config.enable_observer = False` (env: `ENTELGIA_ENABLE_OBSERVER`) to completely exclude Fixy from the dialogue. Set `Config.fixy_interventions_enabled = False` to suppress need-based interventions while keeping Fixy as a scheduled speaker.

Fixy does not dominate conversation but regulates interaction when needed.

---

### Dialogue Loop Guard (`entelgia/loop_guard.py`)

Three cooperating classes that detect and break dialogue failure modes:

**`DialogueLoopDetector`** — inspects the last `window` turns (default 6) and flags up to four simultaneous failure modes:

| Failure Mode | Detection Signal |
|---|---|
| `loop_repetition` | ≥ 3 turn-pairs with Jaccard similarity ≥ 0.45 |
| `weak_conflict` | ≥ 55 % of turns contain conflict markers but no resolution |
| `premature_synthesis` | ≥ 50 % of turns contain synthesis-closure phrases |
| `topic_stagnation` | keyword cloud Jaccard ≥ 0.55 across last 4 topic signatures |

Also detects **role-lock** (one agent stuck in a single rhetorical role ≥ 80 % of turns) and **consecutive similarity** (two adjacent turns with Jaccard ≥ 0.35).

**`PhraseBanList`** — tracks overused n-grams across the session and injects a "do not repeat: …" reminder into subsequent prompts for a configurable number of turns.

**`DialogueRewriter`** — compresses a stale dialogue window into a structured rewrite block; used by Fixy to reclaim token budget when the conversation has been looping.

**`TOPIC_CLUSTERS`** — dict grouping semantically related topics into named clusters (`philosophy`, `identity`, `ethics_social`, `practical`, `biological`). `get_cluster(topic)` returns the cluster name; `topics_in_different_cluster(a, b)` returns `True` when a genuine domain shift is possible.

---

## System Flow

Below is a high-level flow depicting how the system processes a conversational turn:

1. **Topic/Prompt Initiation**  
   The system receives a new conversation topic or user prompt.

2. **Topic Style Detection**  
   `get_style_for_topic()` maps the seed topic to a cluster (e.g., `technology`, `economics`, `biology`).
   A per-agent style instruction is built and assigned to each agent.
   Session start logs: `INFO — Topic style selected: <style> (<cluster>)`.

3. **DialogueEngine Selects Next Actor and Seed**  
   The DialogueEngine decides which agent speaks next and selects a dialogue strategy or "seed" for generating the next turn. From turn 2 onward, a **continuation context** (`extract_continuation_context`) is injected into the seed — capturing dominant topic, last claim, open question, and tension point — so agents advance the conversation rather than replay it.

4. **IntegrationCore Pre-Generation** *(executive cortex)*  
   `IntegrationCore._apply_rules()` evaluates all per-turn signals (stagnation, loops, unresolved items, fatigue, pressure) and selects an `IntegrationMode`. A constraint overlay is built and injected into the prompt.

5. **ContextManager Assembles Interaction Context**  
   ContextManager gathers relevant context: 
   - the current agent's persona
   - dialogue history from Short-Term Memory
   - relevant fragments from Long-Term Memory (now scored with transformer embeddings via `EnhancedMemoryIntegration`)
   - internal agent state
   - **topic-aware style instruction** (from `topic_style.py`)
   - **IntegrationCore overlay** (pre-generation constraint, if any)  
   This context is used to build a structured prompt for the language model.

6. **Agent Produces Response**  
   The designated agent generates a response, updating its own internal state as appropriate.

7. **IntegrationCore Post-Generation Validation**  
   `IntegrationCore.validate_generated_output()` checks the response against the active mode's output contract (structural fields, signal sets, rhetorical-escape patterns, quality gate). Non-compliant responses trigger regeneration. Semantic loops are hard-rejected via `check_loop_rejection()` before the response is accepted.

8. **Memory Update**  
   The new interaction is appended to Short-Term Memory and, as needed, summarized or committed to Long-Term Memory.

9. **Observer Layer Engaged**  
   Fixy reads the dialogue and emits soft signals. IntegrationCore reads Fixy's last message as a hint for the next turn's mode selection.

10. **Cycle Repeats**  
   The loop resumes with the DialogueEngine evaluating the new state and planning the next conversational turn.

---

## Component Interaction Diagram

```
User/Topic
   |
   v
TopicStyleDetector (topic_style.py)
   └─ style instruction ──────────────┐
   |                                  |
   v                                  v
DialogueEngine                     Agents (Socrates / Athena / Fixy)
   | (continuation context seed)      |
   v                                  |
ContextManager ◄───────────────────┘
   |
   ├─ IntegrationCore (pre-gen: mode + overlay)
   v
Agent ↔ Memory (STM/LTM via EnhancedMemoryIntegration)
   |        |
   |        └─ DefenseMechanism → intrusive/suppressed flags
   |        └─ FreudianSlip     → surface defended memories
   |        └─ SelfReplication  → promote recurring patterns
   |
   ├─ IntegrationCore (post-gen: validate / reject / regen)
   |
   v
FixyRegulator (energy supervision)
   └─ dream cycle ──────────────┘
   |
   v
Observer (Fixy) ──► soft signal ──► IntegrationCore (next turn)
   └─› IntegrationMemoryStore (persistent decision history)
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

1. **Unresolved topic integration** — top-*k* pending unresolved topics (ranked by `intensity + conflict + log(repetition + 1)`) are reframed into dream insights, marked `"integrated"`, and their weight is reduced to `weight × 0.3`. Entries are **never deleted** — structure is preserved. Each resolved item is stored in LTM with `provenance="dream_resolution"`. Logged as `[DREAM-RESOLVE] agent=<name> resolved=<n> integrated=<m> remaining=<k>`.
2. **Integration** — subconscious memories are merged into conscious memory; nothing is hard-deleted from long-term memory. Tagged with `provenance="dream_reflection"`.
3. **Relevance filtering** — short-term memory entries that are not emotionally or operationally relevant (empty / whitespace-only) are forgotten.
4. **Promotion** — high-salience STM entries are promoted to conscious LTM. Tagged with `provenance="dream_promotion"`.
5. **Forgetting sweep** — `ltm_apply_forgetting_policy()` deletes any LTM records whose `expires_at` has passed.
6. **Recharge** — `energy_level` is restored to 100.0.

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
| `entelgia/web_tool.py` | `web_search` (DuckDuckGo HTML), `fetch_page_text` (BeautifulSoup + failed-URL blacklist), `search_and_fetch` |
| `entelgia/source_evaluator.py` | Domain-based + text-length credibility scoring |
| `entelgia/research_context_builder.py` | Formats top-3 sources as structured LLM prompt section |
| `entelgia/fixy_research_trigger.py` | Keyword set trigger with per-trigger **and** per-query cooldown (`_COOLDOWN_TURNS = 5`) |
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
- **Failed-URL blacklist**: URLs returning 403 or 404 are permanently skipped for the process lifetime, preventing redundant retries
- **Per-query cooldown**: the same `seed_text` cannot trigger a search more than once per `_COOLDOWN_TURNS` turns, in addition to the existing per-trigger-keyword cooldown
- **Multi-signal gate**: when `Config.web_trigger_require_multi_signal` is `True`, a search requires ≥ `Config.web_trigger_min_concepts` strong concept hits AND an uncertainty/evidence signal

---

## Output Quality Pipeline

Entelgia applies a multi-layer output quality pipeline inside `speak()` to ensure responses are concrete, topic-relevant, and free of LLM scaffolding artefacts.

### Output Contract

`LLM_OUTPUT_CONTRACT` is injected before generation for every agent turn. It requires:
- One concrete claim (specific, not abstract)
- One supporting reason or mechanism (not a feeling or vague statement)
- Optionally one implication or pointed question
- Maximum 2–3 sentences total; no broad preamble; no generic framing opener
- Natural prose — no visible section labels or numbers

Per-agent behavioral contracts (`LLM_BEHAVIORAL_CONTRACT_SOCRATES`, `LLM_BEHAVIORAL_CONTRACT_ATHENA`, `LLM_BEHAVIORAL_CONTRACT_FIXY`) define allowed output moves independently of tone instructions.

### Quality Gate

`output_passes_quality_gate(text)` scans the LLM output against `_QUALITY_GATE_PATTERNS` (compiled regex for banned rhetorical templates). If ≥ `_QUALITY_GATE_THRESHOLD` (2) patterns are found, the draft fails. One regeneration attempt is made with a stricter prompt that names the specific failing patterns. If the second draft also fails, the output proceeds to avoid an infinite loop.

### Scaffold Label Stripper

`_strip_scaffold_labels(text)` is applied after all validation and critique steps. It removes numbered scaffold labels (e.g. `"1. Claim:"`, `"2. Supporting reason:"`, `"Implication:"`) that occasionally leak into LLM output, ensuring final responses read as natural prose.

### Memory Topic Filter

`Agent._score_memory_topic_relevance()` scores each retrieved LTM entry against the current topic using:
1. Exact topic label match (score = 1.0)
2. Cluster match + topic keyword overlap
3. Recent-dialogue term overlap
4. Minus a contamination penalty for off-topic content

Entries below `Config.memory_topic_min_score` (default 0.45) are excluded. `Config.memory_require_same_cluster` (default True) enforces cluster alignment.

### Fixy Role-Aware Compliance

`compute_fixy_compliance_score()` in `entelgia/topic_enforcer.py` applies stricter compliance rules to Fixy's output: must explicitly name the current topic or a core concept, and receives a penalty for introducing new-domain content. Controlled by `Config.fixy_role_aware_compliance`, `Config.fixy_must_name_topic_or_core_concept`, and `Config.fixy_new_domain_penalty`.

### Cluster Wallpaper Penalty

Generic cluster-level vocabulary that appears repeatedly within a `Config.cluster_wallpaper_repeat_window` (default 6) turn window is penalised, biasing generation toward topic-distinct terms. `get_cluster_wallpaper_terms(cluster)` and `get_topic_distinct_lexicon(topic)` in `entelgia/topic_enforcer.py` supply the word lists. Controlled by `Config.cluster_wallpaper_penalty_enabled` and `Config.topic_specific_lexicon_bias_enabled`.

### Web Trigger Multi-Signal Gate

`fixy_research_trigger.py` adds a multi-signal gate before any web search is triggered:
- `_count_strong_trigger_hits(text)` counts concept-bearing trigger keywords (excluding rhetorical framing words)
- `_has_uncertainty_or_evidence_signal(text)` checks for epistemic uncertainty or evidence-seeking language
- When `Config.web_trigger_require_multi_signal` is `True`, both ≥ `Config.web_trigger_min_concepts` (default 2) concept hits AND an uncertainty/evidence signal are required for a search to proceed

`_HIGH_VALUE_KEYWORDS` (e.g. `"studies"`, `"research"`, `"data"`) qualify as strong concept hits regardless of the rhetorical-framing filter.

---

## LLM Backend Architecture

Entelgia supports four interchangeable LLM backends, all selected interactively at startup through `select_llm_backend_and_models()`. The backend choice is a runtime-only override — the `.env` file and disk config are never modified by the selector.

### Supported Backends

| Backend | Provider | Auth | Endpoint |
|---------|----------|------|----------|
| `ollama` | Local (default) | None | `http://localhost:11434/api/generate` |
| `grok` | xAI cloud | `GROK_API_KEY` | `https://api.x.ai/v1/responses` |
| `openai` | OpenAI cloud | `OPENAI_API_KEY` | `https://api.openai.com/v1/chat/completions` |
| `anthropic` | Anthropic cloud | `ANTHROPIC_API_KEY` | `https://api.anthropic.com/v1/messages` |

### Startup Backend Selector

The startup menu offers three modes:

```
[0] Keep defaults
[1] Same backend for all agents
[2] Mix backends — choose per agent
```

Mode `[2]` prompts backend and model for each agent independently via `_pick_agent_backend_and_model()`. A `_BACKEND_MODELS` dict is the single source of truth for model lists per backend.

After choosing a backend, the user selects per-agent or uniform model names. All overrides apply to the in-memory `Config` object for that run only. A config summary is printed:

```
[LLM CONFIG]
  Global backend:  ollama
  Socrates:  [anthropic]  claude-sonnet-4-6
  Athena:    [openai]     gpt-4.1
  Fixy:      [ollama]     qwen2.5:7b
```

### Available Models per Backend

| Backend | Models |
|---------|--------|
| Ollama | `qwen2.5:7b`, `llama3.1:8b`, `mistral:latest` (any 7B+ Ollama model) |
| Grok | `grok-4.20-multi-agent`, `grok-4-1-fast-reasoning` |
| OpenAI | `gpt-4.1`, `gpt-4o`, `gpt-4o-mini`, `gpt-4.1-mini` |
| Anthropic | `claude-opus-4-6`, `claude-sonnet-4-6`, `claude-haiku-4-5` |

### LLM.generate() Dispatch

`LLM.generate()` branches on `cfg.llm_backend`:

- **Ollama**: `POST /api/generate` with `prompt` field; response extracted from `data["response"]`.
- **Grok**: `POST /v1/responses` with `input` field and `Authorization: Bearer` header; response extracted from `output[].content[].text`.
- **OpenAI**: `POST /v1/chat/completions` with `messages` field and `Authorization: Bearer` header; response extracted from `choices[0].message.content`.
- **Anthropic**: `POST /v1/messages` with `messages` field, `x-api-key` header, and `anthropic-version: 2023-06-01`; response extracted from `content[0].text`.

All backends share the same timeout, retry, and caching infrastructure. HTTP requests run in a daemon thread to allow Ctrl+C interruption within ~0.5 seconds.

### Config Fields

| Field | Default | Description |
|-------|---------|-------------|
| `llm_backend` | `"ollama"` | Active global backend (`"ollama"`, `"grok"`, `"openai"`, `"anthropic"`) |
| `backend_socrates` | `""` | Per-agent override for Socrates (empty = inherit global) |
| `backend_athena` | `""` | Per-agent override for Athena (empty = inherit global) |
| `backend_fixy` | `""` | Per-agent override for Fixy (empty = inherit global) |
| `grok_api_key` | `$GROK_API_KEY` | API key for Grok backend |
| `grok_url` | `https://api.x.ai/v1/responses` | Grok endpoint URL |
| `openai_api_key` | `$OPENAI_API_KEY` | API key for OpenAI backend |
| `openai_url` | `https://api.openai.com/v1/chat/completions` | OpenAI endpoint URL |
| `anthropic_api_key` | `$ANTHROPIC_API_KEY` | API key for Anthropic backend |
| `anthropic_url` | `https://api.anthropic.com/v1/messages` | Anthropic endpoint URL |

All API keys are read from environment variables (`.env` file) and never hard-coded.

---

## 23) Fixy Semantic Control Layer (`entelgia/fixy_semantic_control.py`, v5.3.0)

### Purpose

A unified semantic validation and loop-detection controller attached to Fixy's guidance system.  It addresses a systematic weakness where Fixy asks for concrete examples, falsifiable tests, or concessions but debate agents produce abstractions while still receiving relatively high progress scores.

### Role Separation

| Role | Component |
|---|---|
| Guidance source / spokesperson | `InteractiveFixy` (existing) |
| Semantic compliance judge | `FixySemanticController.validate_guidance_compliance()` |
| Semantic repetition judge | `FixySemanticController.detect_semantic_loop()` |
| Validated targets | Socrates, Athena (Fixy is **not** validated in v1) |

### Core Classes

#### `ValidationResult`

```python
@dataclass
class ValidationResult:
    speaker: str
    expected_move: str   # move type Fixy requested
    compliant: bool
    partial: bool
    confidence: float    # [0.0, 1.0]
    reason: str
```

#### `LoopCheckResult`

```python
@dataclass
class LoopCheckResult:
    speaker: str
    is_loop: bool
    confidence: float    # [0.0, 1.0]
    reason: str
```

#### `FixySemanticController`

```python
class FixySemanticController:
    def __init__(self, llm, model): ...
    def validate_guidance_compliance(speaker, text, expected_move) -> ValidationResult: ...
    def detect_semantic_loop(speaker, text, recent_texts) -> LoopCheckResult: ...
    def evaluate_reply(speaker, text, fixy_guidance, recent_texts, *, stagnation, repeated_moves, ignored_recently, unresolved_rising) -> tuple[ValidationResult, LoopCheckResult]: ...
```

### Validated Move Types (v1 scope)

Only `EXAMPLE`, `TEST`, and `CONCESSION` are validated in v1.  All other move types return a default compliant result with `confidence=0.5` and `reason="validation_not_required_for_move_type"`.

### Lightweight Pre-Signal Heuristics

`quick_example_hint(text)` and `quick_test_hint(text)` provide a cheap pre-signal based on surface keywords.  They are **never the final authority** — they enrich debug info and help decide whether LLM validation is strongly needed.

### Loop Detection Trigger Gate

`detect_semantic_loop` is gated in `evaluate_reply` — it only runs when at least one trigger condition is true:

* `stagnation > 0.0`
* `repeated_moves` (move-type repetition detected)
* `ignored_recently` (Fixy guidance was ignored in recent turns)
* `unresolved_rising` (count of unresolved claims is growing)

### Safe JSON Parsing

All LLM responses are parsed via `_safe_parse_validation` and `_safe_parse_loop`.  On any parse failure or LLM exception, a low-confidence fallback result is returned.  **The dialogue engine never crashes** because the validator fails.

### Fixy State Integration

Two new methods on `InteractiveFixy`:

| Method | Effect |
|---|---|
| `record_guidance_compliance(result)` | Full compliance → resets `ignored_guidance_count`; partial → no change; non-compliance → increments counter, boosts confidence after ≥ 2 ignores |
| `record_semantic_loop(result)` | Loop detected → increments `semantic_loop_count`, boosts `fixy_guidance.confidence` by 0.1 |

New attribute `semantic_loop_count: int` tracks cumulative loops across the session.

### Progress Score Coupling

`score_progress()` in `entelgia/progress_enforcer.py` accepts two new optional keyword parameters `validation_result` and `loop_result` and applies soft adjustments via two pure-function helpers:

**`apply_validation_to_progress(score, result, ignored_guidance_count)`**

| Condition | Effect |
|---|---|
| Full compliance | `+0.05 × confidence` |
| Partial compliance | `−0.03` |
| Non-compliance | `×0.85` |
| Repeated non-compliance (`ignored_guidance_count ≥ 3`) | cap at `0.55` |
| `validation_not_required_for_move_type` / `no_guidance_active` | no change |

**`apply_loop_to_progress(score, result)`**

| Condition | Effect |
|---|---|
| `is_loop=True` | `×0.75` |
| `is_loop=True` and `confidence ≥ 0.75` | also cap at `0.50` |
| `is_loop=False` | no change |

All adjustments are **soft** — scores never drop to zero, responses are never rejected.

### Loop-Breaking Moves

When a semantic loop is detected, future Fixy guidance is biased toward loop-breaking move types:

```python
LOOP_BREAKING_MOVES = ["EXAMPLE", "TEST", "CONCESSION", "NEW_FRAME"]
```

### Logging

| Tag | Emitted when |
|---|---|
| `[FIXY-VALIDATION]` | After every LLM compliance check |
| `[FIXY-LOOP]` | After every LLM loop check, and when state updates occur |

Example log lines:
```
[FIXY-VALIDATION] speaker=Athena expected=EXAMPLE compliant=False partial=True confidence=0.61 reason=abstract_not_concrete
[FIXY-LOOP] speaker=Socrates is_loop=True confidence=0.83 reason=rephrases_same_conditioning_argument
```

### Scope Boundaries (v1)

This version does **not**:
- validate Fixy's own output
- validate move types beyond EXAMPLE, TEST, CONCESSION
- compare against full conversation history
- use embeddings
- run multiple LLM checks per turn
- apply hard constraints

---

## 24) IntegrationCore — Executive Cortex (`entelgia/integration_core.py`, v5.5.0)

`IntegrationCore` is the sole supervisory authority above dialogue agents and Fixy. It runs twice per turn: once to decide pre-generation constraints and once to validate the generated output.

### IntegrationMode Taxonomy

Eight modes replace the prior `REQUIRE_ATTACK`-for-everything default:

| Mode | Purpose |
|---|---|
| `NORMAL` | Default; no additional directive |
| `REQUIRE_TEST` | Repeated abstraction with no falsifier |
| `REQUIRE_NEW_VARIABLE` | Same claim restated with only rhetorical variation |
| `REQUIRE_CONCRETE_CASE` | Discussion too abstract for too long |
| `REQUIRE_BRANCH_CLOSURE` | Unresolved count grows without closure |
| `REQUIRE_COUNTEREXAMPLE` | Needs a real-world disconfirming case |
| `REQUIRE_FORCED_CHOICE` | Fence-sitting, no committed position |
| `REQUIRE_STRUCTURAL_CHALLENGE` | Actual adversarial pressure deficit |
| `DREAM_RECOVERY` | Post-dream recovery mode |

### Rule Priority Order

`_apply_rules()` fires rules in explicit priority:

1. Dream / critical fatigue → `DREAM_RECOVERY` / `LOW_COMPLEXITY`
2. Loop break (semantic loop hard-rejection)
3. Personality suppression
4. Stagnation dispatch (`_decide_stagnation_intervention`)
5. Force-outcome rule
6. Unresolved overload → `REQUIRE_BRANCH_CLOSURE`
7. Pressure misalignment (advisory)
8. Default (`NORMAL`)

### Output Contracts

`validate_generated_output()` enforces mode-specific contracts:

| Mode | Contract |
|---|---|
| `REQUIRE_TEST` | `all()` over 5 fields: hypothesis / test / expected outcome / if true / if false |
| `REQUIRE_FORCED_CHOICE` | Commitment signal + justification signal + change-condition signal |
| `REQUIRE_BRANCH_CLOSURE` | Closure phrase + explicit state marker (resolved / testable / discarded) |
| `REQUIRE_COUNTEREXAMPLE` | Mechanism, evidence, or causal language |
| `REQUIRE_CONCRETE_CASE` | Concrete signal + pseudo-compliance check |

Non-compliant responses return `[STATE-TRANSITION-FAIL]` and trigger regeneration.

### Rhetorical Escape Detection

`_RHETORICAL_ESCAPE_PATTERNS` (show me / consider this|that / imagine if / to use your / as you said/noted/argued / according to your) are checked in all non-NORMAL intervention modes **before** mode-specific validation. Match → `[STATE-TRANSITION-FAIL] reason="rhetorical escape"`.

### Semantic Loop Hard-Rejection

`check_loop_rejection(is_loop, reasoning_delta)` returns `(True, "SEMANTIC LOOP: no new reasoning")` when `is_loop=True AND reasoning_delta in ("none","weak")`. Up to `MAX_LOOP_BREAK_ATTEMPTS = 2` retries with escalating overlays. On exhaustion: final escalation with `_OVERLAY_LOOP_ESCALATION_STRATEGY` → if still looping → `get_loop_reset_fallback()` system message. Looping responses are **never published**.

### Force-Outcome Rule

`_rule_force_outcome` fires when `turn_count > 15 AND stagnation ≥ 0.5` OR `unresolved ≥ 5`. Selects `REQUIRE_BRANCH_CLOSURE` when `unresolved > 0` (any unresolved items), else `REQUIRE_FORCED_CHOICE`. Logs `[OUTCOME-ENFORCED]`.

### Soft Fixy Signal Reading

`_read_fixy_soft_signal(fixy_last_message)` maps Fixy hint keywords to intervention modes. Priority order: `REQUIRE_TEST > REQUIRE_BRANCH_CLOSURE > REQUIRE_CONCRETE_CASE > REQUIRE_NEW_VARIABLE`. Fixy messages older than `FIXY_SOFT_SIGNAL_MAX_TURNS = 12` turns are suppressed.

### IntegrationMemoryStore

`IntegrationMemoryStore` persists decision records across turns (max entries bounded, round-trip JSON). `IntegrationCore.attach_memory_store()` / `record_decision()` / `get_memory_context()` hooks provide decision history for downstream use. `FixySemanticController` auto-records `ValidationResult` and `LoopCheckResult` when a store is attached.

### Post-Dream Recovery

`post_dream_recovery_turns` on each `Agent` tracks active recovery. When `> 0`, adversarial modes (`ATTACK_OVERRIDE`, `REQUIRE_STRUCTURAL_CHALLENGE`) are downgraded to `REQUIRE_CONCRETE_CASE` by `_decide_from_mode()` as a defence-in-depth guard.

---

## 25) Session Turn Selector

At session start, an interactive numbered menu is shown before backend selection:

```
Select session length:
  [1]  5 turns
  [2] 15 turns  (default)
  [3] 25 turns
  [4] 50 turns
  [5] 75 turns
  [6] 100 turns
```

Enter selects `Config(max_turns=<selection>, timeout_minutes=0)` — no wall-clock limit. `timeout_minutes=0` sets `timeout_seconds = float("inf")`.

---

## 26) Continuation Context Seed (`entelgia/dialogue_engine.py`)

From turn 2 onward, `generate_seed()` injects a continuation prompt built from the last few real speaker turns:

- `dominant_topic` — most recent explicit topic reference
- `last_claim` — last substantive claim made
- `unresolved_question` — latest open question
- `tension_point` — most recent statement of tension

`role="seed"` entries are skipped so the static opening text is never treated as conversation content. When `has_prior_memory=False` (first turn of a fresh session), the original `TOPIC: {topic}` header is used.

---

## 27) Semantic Memory Retrieval (`entelgia/context_manager.py`)

`EnhancedMemoryIntegration` now uses transformer embeddings for memory ranking:

- `_get_ctx_semantic_model()` — lazy-loads and caches `all-MiniLM-L6-v2`
- `_batch_semantic_scores(topic, dialog_text, memories)` — single `model.encode()` call; empty query strings skip encoding; returns `(None, None)` on failure
- `_calculate_relevance_score` — uses semantic scores when available; falls back to Jaccard when not

`sentence-transformers`, `scikit-learn`, and `numpy` are core dependencies (not optional extras).

---

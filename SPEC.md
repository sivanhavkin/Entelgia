<div style="display: flex; align-items: center; justify-content: space-between;">
  <img src="Assets/entelgia-logo.png" alt="Entelgia Logo" width="120" style="margin: 0;"/>
  <h1 style="flex-grow: 1; text-align: center; font-size: 2.5em; font-weight: bold; margin: 0;">Entelgia — System Specification (Research Prototype)</h1>
  <div style="width: 120px;" aria-hidden="true"></div>
</div>

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

### Web Research Module (v2.8.0)
External knowledge pipeline triggered by Fixy:
- `fixy_research_trigger` — detects research-intent keywords in user messages
- `web_tool` — DuckDuckGo HTML search + BeautifulSoup page extraction
- `source_evaluator` — heuristic credibility scoring (domain, text length)
- `research_context_builder` — formats top-3 sources as LLM-ready context
- `web_research.maybe_add_web_context` — full pipeline orchestration + LTM persistence



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
* accessed either “recent” (legacy) or “relevant” (enhanced), or emotion-weighted via `ltm_search_affective`

**LTM record columns:** `id`, `agent`, `ts`, `layer`, `content`, `topic`, `emotion`, `emotion_intensity`, `importance`, `source`, `promoted_from`, `intrusive`, `suppressed`, `retrain_status`, `signature_hex`, `expires_at`, `confidence`, `provenance`

| Column | Type | Description |
|---|---|---|
| `expires_at` | TEXT (ISO) | TTL expiry timestamp; row deleted by `ltm_apply_forgetting_policy()` when this passes |
| `confidence` | REAL (0–1) | How certain the system is about this memory |
| `provenance` | TEXT | Memory origin label (e.g. `"dream_reflection"`, `"dream_promotion"`, `"user_input"`) |

### 4.3 Drives / Internal Variables

A compact agent state vector (examples):

* emotional_state / arousal / coherence
* conflict index
* self-awareness level
* `drive_pressure: float` — urgency/tension scalar 0.0–10.0 (default `2.0`; see §15)
* `limbic_hijack: bool` — Id-dominant emotional override active flag (default `False`; see §16)
* `_limbic_hijack_turns: int` — consecutive turns elapsed since hijack start (default `0`)
* other agent-specific parameters

These are updated after each turn via:

* response kind (e.g., `"disagreement"` / `"reflective"` / `"impulsive"`)
* detected emotion + intensity (if enabled)
* intervention events

**Limbic hijack** is an Id-dominant emotional override that suppresses SuperEgo influence and forces `response_kind` to `"impulsive"` under high-arousal, high-conflict conditions. See §16 for activation conditions, behavioral effects, and exit logic.

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
* External Knowledge Context (optional, injected by Web Research Module when Fixy triggers a search)

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

All fields are defined in the `@dataclass Config` in `Entelgia_production_meta.py`.

### LLM / Session

* `ollama_url` — Ollama API endpoint (default: `http://localhost:11434/api/generate`)
* `model_socrates` / `model_athena` / `model_fixy` — Per-agent model names (default: `phi3:latest`)
* `max_turns` — Maximum dialogue turns (default: `200`)
* `timeout_minutes` — Session wall-clock timeout in minutes (default: `30`)
* `llm_timeout` — Per-request LLM timeout in seconds (default: `300`)
* `llm_max_retries` — Retry attempts on LLM failure (default: `3`)
* `seed_topic` — Opening topic when none is provided (default: `"what would you like to talk about?"`)
* `cache_size` — LRU response cache capacity (default: `5000`)
* `emotion_cache_ttl` — Emotion cache time-to-live in seconds (default: `3600`)
* `show_pronoun` — Include agent pronouns in output (default: `False`)
* `show_meta` — Print meta-state after each turn (default: `False`)

### Memory

* `data_dir` — Base directory for all persisted data (default: `entelgia_data`)
* `db_path` — SQLite database path (default: `entelgia_data/entelgia_memory.sqlite`)
* `csv_log_path` — CSV dialogue log path (default: `entelgia_data/entelgia_log.csv`)
* `gexf_path` — GEXF graph export path (default: `entelgia_data/entelgia_graph.gexf`)
* `metrics_path` — JSON metrics output path (default: `entelgia_data/metrics.json`)
* `sessions_dir` — Directory for persisted session files (default: `entelgia_data/sessions`)
* `version_dir` — Directory for version snapshots (default: `entelgia_data/versions`)
* `stm_max_entries` — Short-term memory capacity (default: `10000`)
* `stm_trim_batch` — Entries pruned per trim pass (default: `500`)
* `dream_every_n_turns` — Turns between dream-cycle consolidation passes (default: `7`)
* `promote_importance_threshold` — Min importance score to promote to LTM (default: `0.72`)
* `promote_emotion_threshold` — Min emotion score to promote to LTM (default: `0.65`)
* `store_raw_stm` — Store un-redacted text in STM (default: `False`)
* `store_raw_subconscious_ltm` — Store un-redacted text in subconscious LTM (default: `False`)
* `enable_auto_patch` — Enable automatic self-patching (default: `False`)
* `allow_write_self_file` — Allow the agent to write to its own source file (default: `False`)

### Forgetting Policy

* `forgetting_enabled` — Master switch; `False` disables all TTL expiry (default: `True`)
* `forgetting_episodic_ttl` — Subconscious/episodic layer TTL in seconds (default: `604800` — 7 days)
* `forgetting_semantic_ttl` — Conscious/semantic layer TTL in seconds (default: `7776000` — 90 days)
* `forgetting_autobio_ttl` — Autobiographical layer TTL in seconds (default: `31536000` — 365 days)

### Affective Routing

* `affective_emotion_weight` — Weight of `emotion_intensity` vs `importance` in `ltm_search_affective` score (default: `0.4`)

### Energy & Drive (v2.5.0+)

* `energy_safety_threshold` — Energy floor that triggers a dream cycle (default: `35.0`)
* `energy_drain_min` / `energy_drain_max` — Per-step energy drain range (default: `8.0` / `15.0`)
* `self_replicate_every_n_turns` — Turns between self-replication keyword scans (default: `10`)
* `drive_mean_reversion_rate` — Rate at which drives revert toward 5.0 each turn (default: `0.04`)
* `drive_oscillation_range` — ±random noise added to drive values per turn (default: `0.15`)

**Limbic hijack constants** (module-level, not `Config` fields):

* `LIMBIC_HIJACK_SUPEREGO_MULTIPLIER = 0.3` — fraction of SuperEgo strength applied during hijack
* `LIMBIC_HIJACK_MAX_TURNS = 3` — auto-exit after this many consecutive non-re-triggered turns

---

## 13) Energy & Dream Cycles (v2.5.0)

### Overview

Cognitive energy is a first-class agent resource. Every `process_step()` call drains 8–15 energy units. When energy falls to or below the safety threshold (default 35.0), a *dream cycle* fires automatically.

### Components

#### FixyRegulator

Monitors `energy_level` against `safety_threshold`.

| Condition | Action |
|---|---|
| `energy_level <= safety_threshold` | Trigger dream cycle; return `DREAM_TRIGGERED` |
| `energy_level < 60.0` | Roll p=0.10; may return `HALLUCINATION_RISK_DETECTED` |
| Otherwise | Return `None` |

#### EntelgiaAgent

| Attribute | Description |
|---|---|
| `energy_level` | Starts at 100.0; decreases per step |
| `conscious_memory` | Active inputs accumulated during processing |
| `subconscious_store` | Pending memories awaiting dream integration |
| `regulator` | Attached `FixyRegulator` instance |

### Dream Cycle Phases

1. **Integration** — `subconscious_store` entries appended to `conscious_memory`; no long-term memories are deleted.
2. **Relevance filtering** — STM entries that are not emotionally or operationally relevant (empty/whitespace) are forgotten.
3. **Recharge** — `energy_level` reset to 100.0.

### Future Integration Notes

- Energy drain rates will be tied to dialogue complexity in v3.x.
- Cross-agent energy sharing is a planned research feature.

---

## 14) Personal Long-Term Memory System (v2.5.0)

### DefenseMechanism

Classifies every subconscious write into two binary flags stored in the `memories` table:

| Flag | Condition |
|---|---|
| `intrusive=1` | Painful emotion (`anger`, `fear`, `shame`, `guilt`, `anxiety`) with intensity > 0.75 |
| `suppressed=1` | Content contains `forbidden`, `secret`, or `dangerous` |

### FreudianSlip

After each non-Fixy agent turn, rolls `slip_probability` (default 0.05) against the 30 most-recent unconscious memories that carry at least one defense flag. A selected fragment is simultaneously:
- Printed to console as `[SLIP] <content>` (magenta).
- Promoted to the `conscious` LTM layer with `source="freudian_slip"`.

**Rate-limiting controls** (configurable via `Config` or environment variables):

| Parameter | Default | Env var | Description |
|---|---|---|---|
| `slip_probability` | `0.05` | `ENTELGIA_SLIP_PROBABILITY` | Per-turn probability a slip fires |
| `slip_cooldown_turns` | `10` | `ENTELGIA_SLIP_COOLDOWN` | Minimum turns between two successful slips |
| `slip_dedup_window` | `10` | `ENTELGIA_SLIP_DEDUP_WINDOW` | Number of recent slip hashes remembered to block repeats |

**Instrumentation**: The `FreudianSlip` engine exposes `attempts` and `successes` counters. These are logged per-agent at the end of each session (`FreudianSlip stats [<agent>]: attempts=N, successes=M`).

### SelfReplication

Every `self_replicate_every_n_turns` turns (default 10), scans the 50 most-recent unconscious memories for recurring keywords (≥ 4 Latin chars, appearing in ≥ 2 entries). Up to 3 highest-importance matching memories are promoted to `conscious` with `source="self_replication"` and printed as `[SELF-REPL] <content>` (cyan).

### Future Integration Notes

- Defense flags will influence retrieval priority in future releases.
- Freudian slip probability will be modulated by agent stress level.

---

## 15) DrivePressure (v2.6.0)

### Overview

**DrivePressure** is a per-agent urgency/tension scalar (`0.0–10.0`) that represents the internal pressure to act, resolve, or shift topic. It is not a character trait — it is a real-time urgency modulator. High pressure causes the agent to speak more concisely and decisively, breaking stagnation loops before they degrade dialogue quality.

### Agent Fields

| Field | Type | Default | Description |
|---|---|---|---|
| `drive_pressure` | `float` | `2.0` | Current urgency scalar (0.0–10.0) |
| `open_questions` | `list[str]` | `[]` | Tracked unresolved questions |
| `_topic_history` | `list[str]` | `[]` | MD5 topic signatures for stagnation detection |
| `_same_topic_turns` | `int` | `0` | Consecutive turns on the same topic signature |

### Computation

`compute_drive_pressure()` blends four inputs with exponential smoothing (α = 0.35):

| Input | Weight | Description |
|---|---|---|
| Conflict | 45% | `conflict_index / 10.0`, clamped to 1.0 |
| Unresolved questions | 25% | `unresolved_count / 3.0`, clamped to 1.0 |
| Stagnation | 20% | Topic-repetition score (0.0–1.0) |
| Energy depletion | 10% | `(100 − energy) / 100.0` |

Stagnation is measured by `_topic_signature(text)` (MD5-based content fingerprint). When all inputs are calm (conflict < 4.0, stagnation < 0.3, no open questions) pressure decays an additional −0.4 per turn.

### Behavioral Thresholds

| Pressure | Effect |
|---|---|
| `< 6.5` | Normal behavior |
| `≥ 6.5` | Concise directive injected; response capped at 120 words |
| `≥ 8.0` | Decisive directive injected; response capped at 80 words |

### Runtime Integration

`drive_pressure` is recomputed at the start of each `speak()` call using the current energy, conflict, unresolved-question count, and stagnation score. `print_meta_state()` displays the current value as the `Pressure:` line (between Energy and Conflict). The helper functions `_topic_signature()` and `_is_question_resolved()` are exposed as module-level utilities.

### Related Config Fields (v2.6.0)

`Config.drive_mean_reversion_rate` (`0.04`) and `Config.drive_oscillation_range` (`0.15`) govern fluid drive dynamics introduced alongside DrivePressure. Each turn, `id_strength` and `superego_strength` are pulled back toward 5.0 at the reversion rate plus a bounded random oscillation — preventing monotonic drift to extremes.

---

## 16) Limbic Hijack State (v2.7.0)

### Overview

**Limbic hijack** models the psychoanalytic concept of the limbic system overpowering cortical, regulatory control when Id-driven emotional arousal becomes dominant. While active, the SuperEgo's moderating role is drastically curtailed and the agent's response kind is forced to `"impulsive"`, producing rawer, less-mediated output.

### State Fields

| Field | Type | Default | Description |
|---|---|---|---|
| `limbic_hijack` | `bool` | `False` | Emotional override active flag |
| `_limbic_hijack_turns` | `int` | `0` | Consecutive turns elapsed since activation |

### Module-Level Constants

| Constant | Value | Description |
|---|---|---|
| `LIMBIC_HIJACK_SUPEREGO_MULTIPLIER` | `0.3` | Fraction of SuperEgo strength applied during hijack |
| `LIMBIC_HIJACK_MAX_TURNS` | `3` | Auto-exit after this many consecutive non-re-triggered turns |

### Activation Conditions

Evaluated as a pre-response hook inside `speak()`. Fires when **all three** conditions hold simultaneously:

```python
if id_strength > 7 and emotion_intensity > 0.7 and conflict_index() > 0.6:
    agent.limbic_hijack = True
```

### Behavioral Effects While Active

| Effect | Detail |
|---|---|
| Reduced SuperEgo influence | `effective_sup = sup × LIMBIC_HIJACK_SUPEREGO_MULTIPLIER` (0.3) |
| Elevated temperature | Computed using `effective_sup` — less restraint yields higher temperature |
| SuperEgo critique suppressed | `effective_sup` passed to `evaluate_superego_critique`; rarely dominant |
| Impulsive response kind | `response_kind = "impulsive"` fed into the drive update loop |

### Exit Conditions

The hijack state deactivates when **either** condition is met:

* `emotion_intensity < 0.4` — arousal has dropped below the calm threshold (immediate exit).
* `_limbic_hijack_turns ≥ LIMBIC_HIJACK_MAX_TURNS` — the state has persisted for 3 consecutive turns without being re-triggered (auto-exit).

### Meta Output (Priority-Ordered Tags)

When `show_meta=True`, `print_meta_state()` uses a priority-ordered single-line tag to avoid per-turn log spam:

| Priority | Condition | Output |
|---|---|---|
| 1 | `limbic_hijack` is `True` | `[META] Limbic hijack engaged — emotional override active` |
| 2 | SuperEgo critique was applied | `[SuperEgo critique applied; original shown in dialogue]` |
| 3 | Neither | *(silent — no output)* |

This replaces the prior unconditional "SuperEgo critic skipped" message that appeared on almost every turn.

---

**Status:** Experimental / research-oriented.
PRs should preserve: internal-state governance, meta-observer policy, and reproducible evaluation signals.


---

## 16) Web Research Module (v2.8.0)

### Overview

Optional external knowledge pipeline activated by Fixy when the user message
contains research-intent keywords.

### Trigger Condition

`fixy_should_search(user_message)` returns `True` when the lowercased message
contains any word from the trigger set:

```
latest, recent, research, news, current, today, web, find, search,
paper, study, article, published, updated, new, trend, report, source,
credibility, bias, epistemology, truth, reasoning
```

Triggers are ranked by semantic weight: multi-word phrases score 3, concept-bearing
terms (`credibility`, `bias`, `epistemology`, `truth`, `reasoning`, `research`,
`study`, `paper`, `arxiv`, `journal`) score 2, and all other single keywords score 1.
When multiple triggers appear in the same fragment the highest-scoring one is chosen;
ties are broken by earliest position.

### Cooldown Mechanism

Two independent cooldown layers prevent excessive searching:

1. **Per-trigger cooldown** (`_recent_triggers`) — a specific trigger keyword cannot
   fire again within `_COOLDOWN_TURNS` (5) turns after it last triggered a search.
2. **Per-query cooldown** (`_recent_queries`) — the exact `seed_text` passed to
   `fixy_should_search` is also tracked; if the same string is seen again within
   `_COOLDOWN_TURNS` turns the search is suppressed immediately, before any trigger
   keyword evaluation.

Both cooldown dicts are reset by `clear_trigger_cooldown()`.

### Pipeline Steps

1. `web_tool.web_search(query, max_results=5)` — DuckDuckGo HTML search
2. `web_tool.fetch_page_text(url)` — download + extract text (limit 6 000 chars); skips blacklisted URLs
3. `source_evaluator.evaluate_sources(sources)` — score each source
4. Sort by `credibility_score` descending
5. `research_context_builder.build_research_context(bundle, scored)` — format top-3
6. Return context string for injection into `build_enriched_context(web_context=...)`

### Failed-URL Blacklist

`web_tool.fetch_page_text` maintains a module-level `_failed_urls` set.  When a
fetch returns HTTP **403** or **404** the URL is added to the set and all future
calls for that URL within the same process return an empty result immediately,
without making a network request.  `clear_failed_urls()` resets the set.

### Query Rewriting

Before a query is sent to the search engine it passes through processing in
`web_research.py`:

1. **`_sanitize_text`** — strips agent names and mode-label phrases.
2. **`rewrite_search_query(text, trigger)`** — finds the sentence containing the trigger, sanitizes it, then filters `_REWRITE_FILLER_WORDS`, returning at most 6 concept terms. Falls back to `_extract_trigger_fragment` when the trigger is not found within any sentence boundary.

`_REWRITE_FILLER_WORDS` is a comprehensive frozenset covering:

| Category | Examples |
|----------|---------|
| Personal pronouns | `i`, `we`, `you`, `he`, `she`, `they`, `me`, `us` |
| Auxiliary / modal verbs | `is`, `are`, `was`, `were`, `can`, `could`, `should`, `may` |
| Light / copula verbs | `hold`, `seem`, `become`, `feel`, `think`, `believe`, `find` |
| Conjunctions / subordinators | `and`, `but`, `or`, `if`, `because`, `since`, `when`, `while` |
| Prepositions | `with`, `at`, `from`, `by`, `to`, `into`, `about`, `before` |
| Adverbs / discourse markers | `not`, `just`, `only`, `very`, `however`, `therefore`, `thus` |
| Interrogatives | `where`, `when`, `why`, `who`, `whom` |
| Generic nouns / adjectives | `place`, `thing`, `way`, `part`, `fact`, `kind`, `sort`, `type` |
| Discourse gerunds | `reflecting`, `considering`, `exploring`, `examining`, `discussing` |

### Credibility Scoring Rules

| Signal | Score |
|--------|-------|
| `.edu` or `.gov` domain | +0.30 |
| Known research/reference site | +0.20 |
| Text length ≥ 500 chars | +0.20 |
| Text length ≥ 200 chars | +0.10 |
| Text length < 50 chars | −0.20 |

Score clamped to [0.0, 1.0].

### Memory Persistence

When `credibility_score > 0.6`, the source summary is stored in the
`external_knowledge` table (SQLite):

```
id, timestamp, query, url, summary, credibility_score
```

### Safety Constraints

- Timeout: 10 s per HTTP request
- Max results: 5 (configurable)
- Text cap: 6 000 chars per page
- All exceptions caught; returns `""` on any failure

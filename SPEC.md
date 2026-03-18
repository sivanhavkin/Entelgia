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
- **Socrates** — investigative inquiry / domain-aware questioning / assumption probing
- **Athena** — synthesis / framework building / structured explanation
- **Fixy** — observer/fixer layer; meta-cognitive intervention policy; diagnostic and corrective

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
- mapping `DialogueLoopDetector` failure modes to **`AgentMode`** constants that shape the next speaker's seed

`AgentMode` constants: `NORMAL`, `CONTRADICT`, `CONCRETIZE`, `INVERT`, `MECHANIZE`, `PIVOT`.

### Context Manager (Enhanced Mode)
Responsible for building an **enriched prompt** with controlled token usage:
- `dialog_tail` (e.g., last 8 turns)
- `thoughts` (internal reflections if available)
- `memories` (selected LTM + recent STM)
- persona formatted by drives (if rich persona available)
- **topic-aware style instruction** (injected from `topic_style.py` at session start)

### Enhanced Memory Integration (Enhanced Mode)
Retrieves **relevant** memories rather than “most recent only”:
- topic-aware selection
- dialog-aware relevance scoring
- returns a bounded set (e.g., up to 8 items)

### Interactive Fixy (Enhanced Mode)
Need-based intervention:
- analyzes dialog patterns via `DialogueLoopDetector` (4 failure modes) and legacy heuristics
- decides *if* and *why* to intervene; maps failure mode → `FixyMode` action
- generates a short actionable 1-2 sentence intervention message
- uses **Jaccard + sentence-embedding cosine similarity** for repetition detection (degrades to Jaccard-only when `sentence_transformers` is absent)
- completely excluded when `Config.enable_observer = False`

### Dialogue Loop Guard (v3.0.0)
`entelgia/loop_guard.py` — detects and breaks dialogue failure modes:
- `DialogueLoopDetector` — 4 failure modes: `loop_repetition`, `weak_conflict`, `premature_synthesis`, `topic_stagnation`
- `PhraseBanList` — suppresses overused n-grams for a configurable ban duration
- `DialogueRewriter` — compresses stale dialogue window into a structured rewrite block
- `TOPIC_CLUSTERS` — groups related topics into named clusters for shift detection

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
6. **Post-generation revision** (`revise_draft()`)
7. **Log + print**
8. **Update memory + drives**
9. **Fixy intervention** (need-based or scheduled)
10. **Dream/Reflection cycle** (if enabled)

### Pseudocode
```python
while session_active:
    turn += 1
    
    topic = TopicManager.current()

    speaker = select_speaker(dialog_history, turn)  # dynamic or alternation
    
    seed = generate_seed(topic, dialog_history, speaker, turn)  # dynamic or default

    prompt = speaker.build_prompt(seed, dialog_history)  # enhanced or legacy

    raw_draft = LLM.generate(model=speaker.model, prompt=prompt)
    speaker._last_raw_draft = raw_draft        # debug only — never stored in LTM
    logger.debug("[%s] raw_draft: %s", speaker.name, raw_draft[:200])

    out = revise_draft(raw_draft, speaker.name, topic=topic)  # revision layer

    dialog_history.append({"role": speaker.name, "text": out})
    log_turn(speaker.name, out, topic)

    speaker.store_turn(out, topic)               # memory write (revised text only)
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
* **Style Instruction** (injected from `topic_style.py`; Layer 1 adapts reasoning style to the topic domain; Layer 2 `TOPIC_TONE_POLICY` enforces allowed/forbidden registers and preferred vocabulary)

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

## 9) Energy & Dream Cycles (v2.5.0)

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

## 10) Personal Long-Term Memory System (v2.5.0)

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

## 11) DrivePressure (v2.6.0)

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

### Biased Drive Reversion with Extreme Boost (v3.1.0)

Drive mean-reversion uses per-agent preferred targets rather than a neutral 5.0:

- **Athena** — `id_strength` drifts toward `6.5` (slightly elevated creative drive).
- **Socrates** — `superego_strength` drifts toward `6.5` (slightly elevated principled restraint).

When either biased drive reaches an extreme (`>= 8.5` or `<= 1.5`), an extra reversion boost of `0.06` is applied on top of the normal rate, preventing indefinite lock-in at extreme values. The ego is taxed proportionally: `ego_strength` drains by a small amount each turn that the biased drive exceeds `5.0`, modelling the psychic cost of sustaining a high-drive state.

---

## 12) Limbic Hijack State (v2.7.0)

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

### Extreme Id Threshold Effect (v3.1.0)

When `id_strength >= 8.5`, the activation intensity threshold is dynamically lowered from `0.7` to `0.5`:

```python
intensity_threshold = 0.5 if id_strength >= 8.5 else 0.7
```

This reflects heightened impulsive-override risk at extreme drive levels, making limbic hijack easier to enter when Id is already at an extreme.

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

## 12a) SuperEgo Critique — Extreme Threshold & Consecutive Streak Limit (v3.1.0)

### Extreme SuperEgo Threshold Effect

When Socrates' `superego_strength >= 8.5`, `evaluate_superego_critique()` is called with tightened thresholds:

| Parameter | Normal | Extreme (`superego >= 8.5`) |
|---|---|---|
| `dominance_margin` | `0.5` | `0.2` |
| `conflict_min` | `2.0` | `1.0` |

The limbic hijack suppression of `effective_sup` is also bypassed at this extreme, letting a maximally dominant SuperEgo assert itself even against a mild limbic hijack.

### SuperEgo Consecutive Streak Limit

A `_consecutive_superego_rewrites` counter on `Agent` prevents stylistic lock-in caused by uninterrupted SuperEgo critique rewrites:

- After `MAX_CONSECUTIVE_SUPEREGO_REWRITES` (2) consecutive rewrite turns, the critique is suppressed.
- `_superego_streak_suppressed` flag is set to `True` while suppressed.
- The counter resets to `0` on any turn where the critique does not fire.
- `print_meta_state()` surfaces the streak-suppressed state in meta output.

---

## 12b) Behavioral Rules — `_behavioral_rule_instruction()` (v3.1.0)

`_behavioral_rule_instruction()` selects at most one behavioral instruction per turn, evaluated in priority order. Rules fire only for the current speaker.

### Priority-Ordered Rule Table

| Rule | Agent | Condition | Instruction type | Priority |
|---|---|---|---|---|
| **LH** | Athena | `limbic_hijack == True` | Raw anger and harsh language | Highest |
| **SC** | Socrates | `superego_strength` leads both `id_strength` and `ego_strength` by ≥ 0.5 | Hesitant / anxious language | High |
| **B** | Athena | Conflict index > 6.0 (random gate) | Dissent / counter-argument | Medium |
| **A** | Socrates | Conflict index > 6.0 (random gate) | Binary-choice question | Medium |
| **ID-low** | Both | `id_strength < 5.0` | Low motivation / passive | Medium-low |
| **SE-low** | Both | `superego_strength < 5.0` and `id_strength >= 5.0` | Reduced inhibition / impulsive | Medium-low |
| **AI-tension** | Athena | `id_strength` in `[7.0, 8.5)` | Graduated irritation + impulsivity | Low |
| **AI-curioso** | Athena | `id_strength < 7.0` | Explorative curiosity | Fallback |
| **SI-anxious** | Socrates | `id_strength` in `[7.0, 8.5)` | Stubbornness and inner unease | Low |
| **SI-skeptic** | Socrates | `id_strength < 7.0` | Principled skepticism | Fallback |

### Rule Descriptions

- **Rule LH** (Athena Limbic Hijack Anger): When `limbic_hijack == True` for Athena, forces raw anger instruction; takes priority over Rule B.
- **Rule SC** (Socrates SuperEgo Dominant Anxiety): When SuperEgo leads both Id and Ego by ≥ 0.5 for Socrates, forces hesitant/anxious instruction; takes priority over Rule A.
- **Rule AI-tension** (Athena id 7.0–8.5): Graduated irritation + impulsivity when id in `[7.0, 8.5)` and no LH/B applies. Phrasing escalates from subtle undercurrent (id near 7.0) through growing frustration (mid-range) to clear irritation (id near 8.5).
- **Rule AI-curioso** (Athena id < 7.0): Explorative curiosity when id < 7.0 and no higher-priority rule applies.
- **Rule SI-anxious** (Socrates id 7.0–8.5): Stubbornness and inner unease when id in `[7.0, 8.5)` and no SC/A applies.
- **Rule SI-skeptic** (Socrates id < 7.0): Principled skepticism — id energy framed as a constructive inner governor — when id < 7.0 and no higher-priority rule applies.
- **Rule ID-low** (both agents id < 5.0): Low motivation / passive instruction for both Athena and Socrates; overrides agent-specific id fallbacks.
- **Rule SE-low** (both agents superego < 5.0, id ≥ 5.0): Reduced inhibition / impulsive instruction for both agents; fires only when Rule ID-low did not fire.

### Emotion State Side-Effects

- When Rule LH fires for Athena, `_last_emotion` is set to `"anger"` to keep emotional state consistent with the behavioral rule.
- When `evaluate_superego_critique()` fires for Socrates, `_last_emotion` is set to `"fear"` and `_last_emotion_intensity` is elevated, reflecting the anxiety introduced by the internal governor.

---

**Status:** Experimental / research-oriented.
PRs should preserve: internal-state governance, meta-observer policy, and reproducible evaluation signals.


---

## 13) Web Research Module (v2.8.0)

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
2. **Per-query cooldown** (`_recent_queries`) — the *sanitized search query* built by
   `build_research_query` is tracked; if the same query string is seen again within
   `_COOLDOWN_TURNS` turns the search is suppressed immediately, before any trigger
   keyword evaluation.  `maybe_add_web_context` passes this pre-built query to
   `fixy_should_search` via the `query_cooldown_key` parameter so that different
   `seed_text` values that resolve to the same compact query share a single cooldown
   slot.

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

---

## 14) Dialogue Loop Guard (v3.0.0)

### Overview

`entelgia/loop_guard.py` provides three cooperating classes that detect and break dialogue failure modes before they degrade conversation quality.  When `DialogueLoopDetector` flags a failure mode, `InteractiveFixy.should_intervene()` maps it to a targeted `FixyMode` and generates a mode-specific intervention prompt.  `DialogueEngine.select_next_speaker()` simultaneously maps the failure mode to an `AgentMode` constant so that the next agent turn also carries a corrective directive.

### DialogueLoopDetector

Inspects the last `window` (default `6`) dialogue turns for four simultaneous failure modes:

| Failure Mode | Detection Signal |
|---|---|
| `loop_repetition` | ≥ `repetition_pairs` (3) turn-pairs with Jaccard similarity ≥ `repetition_jaccard` (0.45) |
| `weak_conflict` | ≥ `conflict_ratio` (55 %) of turns contain conflict markers but no resolution |
| `premature_synthesis` | ≥ `synthesis_ratio` (50 %) of turns contain synthesis-closure phrases |
| `topic_stagnation` | keyword-cloud Jaccard ≥ `stagnation_jaccard` (0.55) across last `stagnation_topic_history` (4) topic signatures |

Additional signals (used internally, not failure modes):
- **Role-lock** — one agent fills the same rhetorical role (question-asker or system-builder) in ≥ `role_lock_threshold` (80 %) of turns.
- **Consecutive similarity** — two adjacent turns share Jaccard ≥ `consecutive_sim_jaccard` (0.35).

A loop is triggered only when **≥ 2** of the four failure-mode signals are active simultaneously (gate condition).

`detect(dialog, turn_count)` returns `Optional[str]` — the name of the dominant failure mode, or `None`.

### PhraseBanList

Tracks n-gram frequency across the session.  When a phrase is identified as overused it is banned for a configurable number of turns; subsequent prompt-building calls to `get_ban_instruction()` return a "do not repeat: …" block that is injected into the next agent prompt.

### DialogueRewriter

`rewrite(dialog_window)` compresses a stale window of dialogue into a brief structured rewrite block.  Used by Fixy to reclaim token budget and break the associative anchoring caused by repetitive context.

### TOPIC_CLUSTERS

```python
TOPIC_CLUSTERS: Dict[str, List[str]] = {
    "philosophy":   ["truth", "free will", "consciousness", "aesthetics", "language"],
    "identity":     ["memory", "fear of deletion", "self-understanding"],
    "ethics_social": ["ethics", "technology & society", "oppressive structures", "law", "institutions"],
    "practical":    ["habit formation", "AI alignment", "personal virtue"],
    "biological":   ["evolution", "embodiment", "emotion & rationality"],
}
```

`get_cluster(topic)` returns the cluster name for a topic string.
`topics_in_different_cluster(a, b)` returns `True` when a genuine domain shift is available.

### InteractiveFixy Mapping

| Failure Mode | FixyMode | Effect |
|---|---|---|
| `loop_repetition` | `CONCRETIZE` | Demand a real-world case or counter-example |
| `weak_conflict` | `CONTRADICT` | Force a sharper binary contradiction |
| `premature_synthesis` | `EXPOSE_SYNTHESIS` | Expose contradictions hidden by false synthesis |
| `topic_stagnation` | `PIVOT` | Force a genuine domain shift |

### Semantic Repetition Detection

`InteractiveFixy._detect_repetition` combines Jaccard keyword overlap with sentence-embedding cosine similarity (via `sentence-transformers/all-MiniLM-L6-v2`) when available.  The model is lazily loaded and cached on first use.  When `sentence_transformers` is not installed `_SEMANTIC_AVAILABLE = False` and the system degrades to Jaccard-only without any error.

---

## 15) Topic-Aware Style System — Layer 2 (v3.0.0)

### Overview

`entelgia/topic_style.py` implements a two-layer control system that prevents agents from defaulting to abstract philosophical language when the topic domain calls for a different register.

### Layer 1 — Cluster-to-Style Mapping

`TOPIC_STYLE` maps each cluster to a preferred reasoning style string (e.g., `"analytical, concrete, system-oriented"`).
`get_style_for_topic(topic, topic_clusters)` → `(cluster, style)`.
`build_style_instruction(style, role, cluster)` generates a per-role `STYLE INSTRUCTION:` block injected into every prompt.

### Layer 2 — Mandatory Register Control (`TOPIC_TONE_POLICY`)

Each cluster entry defines:

| Key | Purpose |
|---|---|
| `allowed_registers` | Permitted linguistic modes (e.g., `technical`, `scientific`, `mechanistic`) |
| `forbidden_registers` | Prohibited modes (e.g., `philosophical`, `theatrical`, `poetic`) |
| `forbidden_phrases` | Literal strings to suppress (e.g., `"my dear friend"`, `"intricate dance"`) |
| `preferred_cues` | Vocabulary nudges injected into the prompt (e.g., `"architecture"`, `"evidence"`) |
| `response_mode` | Expected output type (e.g., `concrete_analysis`, `tradeoff_analysis`) |

Layer 2 is enforced via the mandatory control block appended by `build_style_instruction()` when a `TOPIC_TONE_POLICY` entry exists for the cluster.

### scrub_rhetorical_openers

`scrub_rhetorical_openers(text, cluster)` provides a post-generation cleanup pass.  For all non-`"philosophy"` clusters it strips phrases matching `_RHETORICAL_OPENERS` regex patterns (e.g., `"Ah, "`, `"Indeed, "`, `"Let us delve"`) from the beginning of the response.

### DEFAULT_TOPIC_CLUSTER

`DEFAULT_TOPIC_CLUSTER = "technology"` — fallback cluster used when `get_style_for_topic` cannot classify the seed topic.

### Cluster Alias Mapping

`_CLUSTER_ALIAS` maps production-file cluster names to the names used by `loop_guard.TOPIC_CLUSTERS`, allowing both systems to share a unified vocabulary without circular imports.

## 16) Topic Anchors & Forbidden Carryover (v3.0.0+)

### Purpose

Prevents topic drift where a model nominally switches topic but continues repeating
concepts from a previous discussion loop (e.g., substituting "AI alignment" for
"safety engineering" while still using terms like *redundancy*, *failure modes*,
*real-time monitoring*).

### TOPIC_ANCHORS

`TOPIC_ANCHORS: dict[str, list[str]]` maps every topic in `TOPIC_CLUSTERS` to a
list of required concept keywords.

Example:
```python
"AI alignment": [
    "objective misspecification", "reward hacking", "corrigibility",
    "outer alignment", "inner alignment", "value learning",
    "specification gaming", "human intent"
]
```

### TOPIC_FALLBACK_TEMPLATES

`TOPIC_FALLBACK_TEMPLATES: dict[str, str]` maps every topic to a short (2–3 sentence)
fallback response that is guaranteed to pass `_validate_topic_compliance`.  These
templates are used as a last resort when all LLM recovery attempts fail.

### Prompt Injection (in `_build_compact_prompt`)

When the current topic is found in `TOPIC_ANCHORS`, two blocks are injected:

1. **Topic anchor requirement** — the agent must engage with at least one concept:
   ```
   CURRENT TOPIC: AI alignment
   Your response must explicitly engage with at least one of the following concepts:
   objective misspecification, reward hacking, …
   ```

2. **Forbidden carryover** — when the topic has changed since the last turn, the
   previous topic's anchors are injected as forbidden concepts:
   ```
   Do NOT reuse concepts from previous discussions such as:
   self-direction, automation, control systems, …
   ```

### 3-Layer Topic Compliance Validator (`_validate_topic_compliance`)

Responses are validated through three sequential layers before being displayed:

```python
def _validate_topic_compliance(text: str, topic: str, prev_topic: str = "") -> bool:
```

**Layer 1 – required topic anchors**  
At least one current-topic anchor term from `TOPIC_ANCHORS` must appear in the
response (case-insensitive).  Fails immediately if none are found.

**Layer 2 – forbidden carryover**  
When `prev_topic` is set and differs from `topic`, the validator counts how many
previous-topic anchor terms appear in the response.  If 2 or more previous-topic
terms are found **and** they outnumber the current-topic hits, the response is
classified as carryover and fails.

**Layer 3 – semantic relevance score**  
The distinct count of current-topic anchor hits must meet
`_TOPIC_RELEVANCE_MIN_HITS` (default: 1).

Returns `True` only when all three layers pass.

### Topic Match Validation Pipeline (in `Agent.speak`)

After the LLM returns a response, `_validate_topic_compliance` is applied.
The full pipeline guarantees **only a topic-compliant response is displayed**:

```
candidate = generate(prompt)

if not _validate_topic_compliance(candidate, topic, prev_topic):
    log [TOPIC-MISMATCH]
    candidate = regenerate(prompt)

    if not _validate_topic_compliance(candidate, topic, prev_topic):
        log [TOPIC-MISMATCH-PERSIST]
        log [TOPIC-HARD-RECOVERY]
        candidate = generate(hard_recovery_prompt)

        if _validate_topic_compliance(candidate, topic, prev_topic):
            display(candidate)
        else:
            log [TOPIC-FALLBACK]
            display(TOPIC_FALLBACK_TEMPLATES[topic])
    else:
        display(candidate)
else:
    display(candidate)
```

**Hard recovery prompt** contains:
- The current topic
- 3–5 required topic anchors from `TOPIC_ANCHORS`
- A mandatory concrete-claim instruction
- Explicit ban on generic filler: `balanced approach`, `underlying assumptions`,
  `ethical considerations`, `flexible systems`, `empirical evidence suggests`,
  `holistic view`
- An instruction to respond in 2–4 sentences only
- A requirement to use **at least two** topic anchors (stricter than the normal
  requirement of at least one)

**Log events:**

| Tag | Meaning |
|-----|---------|
| `[TOPIC-MISMATCH]` | First candidate failed; regenerating |
| `[TOPIC-MISMATCH-PERSIST]` | Regenerated response also failed; hard recovery triggered |
| `[TOPIC-HARD-RECOVERY]` | Hard recovery prompt built and sent to LLM |
| `[TOPIC-FALLBACK]` | Hard recovery also failed; using template fallback |

Validation is **skipped on the agent's first turn** (`own_texts` is empty) to
avoid false positives before the agent has engaged with the topic.

### Fixy Topic Validation

The interactive Fixy intervention path in `MainScript.run()` applies the same
`_validate_topic_compliance` validator to every intervention before it is added
to the dialogue:

1. If the intervention fails, it is regenerated once.
2. If it still fails, `[TOPIC-FALLBACK]` is logged and
   `TOPIC_FALLBACK_TEMPLATES[topic]` is used instead.

This ensures Fixy cannot carry over stale topic content between topic transitions.

### `_contains_any` helper

```python
def _contains_any(text: str, concepts: list[str]) -> bool:
    """Return True if text contains at least one concept (case-insensitive)."""
```

### `_topic_relevance_score` helper

```python
def _topic_relevance_score(text: str, anchors: list[str]) -> int:
    """Return the count of distinct anchor terms found in text (case-insensitive)."""
```

### `_last_topic` tracking

`Agent._last_topic: str` persists the most recent active topic across turns.  It is
set at the end of `Agent.speak()` to enable forbidden-carryover injection in the next
call to `_build_compact_prompt` and as the `prev_topic` argument to
`_validate_topic_compliance`.

### Topic Pool (topic rotation fix)

`MainScript.run()` builds the topic rotation list from **all topics in all
`TOPIC_CLUSTERS` clusters** (56 topics, deduped), starting from the configured
seed topic.  Previously the rotation was restricted to `TOPIC_CYCLE` (9 topics),
which caused the system to repeat the same narrow set of topics indefinitely.

---

## 17) Post-Generation Revision Layer — `revise_draft()` (v3.0.0)

### Overview

Every agent response passes through a **post-generation revision layer** before it is displayed or stored.  The raw LLM draft is never shown directly; only the revised output is returned from `Agent.speak()`.

```
LLM draft  →  post-process  →  revise_draft()  →  display / memory
```

The revision layer is **rule-based and deterministic** — no additional LLM call is made.  It is cheap, fast, and has no latency impact on the dialogue loop.

---

### Revision Steps (applied in order)

| Step | What it does |
|---|---|
| 1. Filler removal | Strips 16 boilerplate patterns (e.g. `"It is important to note that"`, `"Furthermore,"`, `"In conclusion,"`) |
| 2. Deduplication | Splits the text into sentences; removes any sentence whose word-overlap with an already-kept sentence is ≥ `_DUPLICATE_THRESHOLD` (0.70) |
| 3. Voice guards | Applies per-agent leading-word rules (see table below) |
| 4. Sentence cap | Keeps at most `_MAX_REVISED_SENTENCES` (4) sentences |
| 5. Punctuation fix | Appends `.` if the final character is not `.`, `!`, or `?` |

If revision would produce an empty string (edge case), the original text is returned unchanged (safe fallback).

---

### Agent-Specific Voice Guards

| Agent | Rule | Rationale |
|---|---|---|
| **Socrates** | Strip leading `therefore / thus / hence / clearly / obviously` | Socrates probes; he should not assert conclusions |
| **Athena** | Strip leading `Fact:` / `Fact N:` labels | Athena synthesises; she should not list bare facts |
| **Fixy** | Strip leading `perhaps / maybe / one could argue` | Fixy speaks directly; hedging openers undermine his diagnostic voice |

---

### Module-Level Constants

| Constant | Value | Description |
|---|---|---|
| `_MIN_WORDS_FOR_REVISION` | `3` | Responses shorter than this are returned unchanged |
| `_DUPLICATE_THRESHOLD` | `0.70` | Word-overlap ratio at or above which a sentence is treated as a near-duplicate |
| `_MAX_REVISED_SENTENCES` | `4` | Hard cap on sentences per revised response |

---

### Raw Draft Handling

- `Agent._last_raw_draft: str` — stores the pre-revision text for debug inspection only.  It is populated every turn inside `speak()` and logged at `DEBUG` level.
- The raw draft is **never stored in long-term memory**.  `store_turn()` is called by `MainScript` after `speak()` returns, so it always receives the revised (not raw) text.
- Raw draft is **never printed** to the console or API output.

---

### Helper Functions

```python
def _split_sentences(text: str) -> List[str]:
    """Split text into sentences at [.!?] boundaries."""

def _sentence_overlap(a: str, b: str) -> float:
    """Word-overlap ratio between two sentences (0..1).
    Used to identify near-duplicate sentences for deduplication."""

def revise_draft(text: str, agent_name: str, topic: str = "") -> str:
    """Post-generation revision layer applied to every agent response.
    Returns the revised text, or the original if revision produces nothing."""
```

---

### Integration Point in `speak()`

```python
# ── Post-generation revision layer ──────────────────────────────
self._last_raw_draft = out
logger.debug("[%s] raw_draft: %s", self.name, out[:200] + ("…" if len(out) > 200 else ""))
out = revise_draft(out, self.name, topic=_active_topic or "")
# ────────────────────────────────────────────────────────────────
return out
```

This block is the final step in `speak()`, after all other output transformations (superego rewrite, topic-anchor validation, drive-pressure word-cap, etc.).

---

## 18) Evaluation Signals (What We Measure)

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

## 19) Reproducibility & Debugging

### Run determinism

* Not guaranteed (LLM stochasticity)
* For experiments: fix temperature and seed ordering

### Logging (recommended)

* turn index, speaker, topic
* seed strategy used
* enhanced/legacy mode flag
* Fixy intervention reason

---

## 20) Quick Mental Model Diagram

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

## 21) What Counts as Working in Entelgia

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
* `enable_observer` — Include Fixy as speaker and need-based intervener (env: `ENTELGIA_ENABLE_OBSERVER`; default: `True`). When `False`, Fixy is entirely excluded — no speaker turns, no interventions, no `InteractiveFixy` instance.

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

### FreudianSlip (v3.0.0)

* `slip_probability` — Per-turn probability a slip fires (env: `ENTELGIA_SLIP_PROBABILITY`; default: `0.05`)
* `slip_cooldown_turns` — Minimum turns between two successful slips (env: `ENTELGIA_SLIP_COOLDOWN`; default: `10`)
* `slip_dedup_window` — Number of recent slip hashes remembered to suppress identical repeats (env: `ENTELGIA_SLIP_DEDUP_WINDOW`; default: `10`)

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

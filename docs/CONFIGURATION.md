# ⚙️ Entelgia Configuration

Entelgia can be customized through the `Config` class in `Entelgia_production_meta.py`. Key configuration options:

## Core Session Settings

```python
config = Config()

config.max_turns = 200              # Maximum dialogue turns (default: 200)
config.timeout_minutes = 30         # Session timeout in minutes (set to 9999 to disable)
config.dream_every_n_turns = 7      # Dream cycle frequency (default: 7)
config.llm_max_retries = 3          # LLM request retry count (default: 3)
config.llm_timeout = 300            # LLM request timeout in seconds (default: 300)
config.show_pronoun = False         # Show agent pronouns in output (default: False)
config.show_meta = False            # Show meta-state after each turn (default: False)
config.debug = True                 # Enable DEBUG-level logging (default: True)
config.stm_max_entries = 10000      # Short-term memory capacity (default: 10000)
config.stm_trim_batch = 500         # Entries pruned per trim pass (default: 500)
config.promote_importance_threshold = 0.72  # Min importance to promote to LTM (default: 0.72)
config.promote_emotion_threshold = 0.65     # Min emotion score to promote to LTM (default: 0.65)
config.store_raw_stm = False        # Store un-redacted text in STM (default: False)
config.store_raw_subconscious_ltm = False   # Store un-redacted text in LTM (default: False)
config.enable_observer = True       # Include Fixy in dialogue (env: ENTELGIA_ENABLE_OBSERVER; default: True)
```

## 🔁 FreudianSlip Settings

```python
config.slip_probability = 0.05        # Per-turn probability a slip fires (env: ENTELGIA_SLIP_PROBABILITY)
config.slip_cooldown_turns = 10       # Min turns between two successful slips (env: ENTELGIA_SLIP_COOLDOWN)
config.slip_dedup_window = 10         # Recent slip hashes remembered to block repeats (env: ENTELGIA_SLIP_DEDUP_WINDOW)
```

## Response Quality Settings

> **Note:** Response length is controlled by the module-level constant `MAX_RESPONSE_WORDS = 150`
> in `Entelgia_production_meta.py` (not a `Config` field). The LLM prompt instructs the model
> to answer in maximum 150 words; responses are never truncated by the runtime.
> `validate_output()` removes control characters and normalizes newlines, without any length limits.

## ⚡ Energy & Dream Cycle Settings

```python
config.energy_safety_threshold = 35.0  # Energy level that triggers a dream cycle (default: 35.0)
config.energy_drain_min = 8.0           # Minimum energy drained per step (default: 8.0)
config.energy_drain_max = 15.0          # Maximum energy drained per step (default: 15.0)
config.self_replicate_every_n_turns = 10  # Turns between self-replication scans (default: 10)
```

## Drive-Aware Cognition Settings

These `Config` fields control how Freudian drives evolve and influence LLM behaviour at runtime:

```python
config.drive_mean_reversion_rate = 0.04   # Rate drives revert toward 5.0 each turn (default: 0.04)
config.drive_oscillation_range = 0.15     # ±random noise added to drives per turn (default: 0.15)

# LLM temperature is computed automatically from drive values:
# temperature = max(0.25, min(0.95, 0.60 + 0.03*(id - ego) - 0.02*(effective_sup - ego)))
# During limbic hijack, effective_sup = superego * LIMBIC_HIJACK_SUPEREGO_MULTIPLIER (0.3)

# Superego critique (second-pass rewrite) fires when superego_strength >= 7.5
# During limbic hijack, effective_sup is reduced to 30% — suppressing the critique.
# Memory depth scales automatically:
#   ltm_limit = max(2, min(10, int(2 + ego/2 + self_awareness*4)))
#   stm_tail  = max(3, min(12, int(3 + ego/2)))
```


**META block output** (when `show_meta=True`):
```
Pressure: 6.42  Unresolved: 2  Stagnation: 0.75
```

**Sample log showing pressure rising, then output shortening:**
```
[META: Socrates]
  Id: 5.8  Ego: 5.1  SuperEgo: 6.4  SA: 0.57
  Energy: 72.0  Conflict: 1.50
  Pressure: 2.12  Unresolved: 0  Stagnation: 0.00    ← turn 1, baseline
...
[META: Socrates]
  Pressure: 5.71  Unresolved: 2  Stagnation: 0.75    ← turn 5, rising
...
[META: Socrates]
  Pressure: 8.03  Unresolved: 3  Stagnation: 1.00    ← turn 8, high pressure
  → output trimmed to 80 words, decisive question forced
```

For the complete list of configuration options, see the `Config` class definition in `Entelgia_production_meta.py`.

## 🗂️ Forgetting Policy Settings

```python
config.forgetting_enabled = False             # Master switch; False disables all TTL expiry (default: False)
config.forgetting_episodic_ttl = 604800       # Subconscious / episodic layer TTL in seconds (default: 7 days)
config.forgetting_semantic_ttl = 7776000      # Conscious / semantic layer TTL in seconds (default: 90 days)
config.forgetting_autobio_ttl = 31536000      # Autobiographical layer TTL in seconds (default: 365 days)
```

`MemoryCore.ltm_apply_forgetting_policy()` is called automatically at the end of every `dream_cycle()`.
Set a TTL to `0` to disable expiry for a specific layer without disabling the feature globally.

## 💡 Affective Routing Settings

```python
config.affective_emotion_weight = 0.4   # Weight of emotion_intensity vs importance (default: 0.4)
                                         # Score = importance*(1-w) + emotion_intensity*w
```

Use `memory.ltm_search_affective(agent, emotion_weight=0.7)` for more emotion-biased retrieval.

## 🗂️ Topics Feature Switch

```python
config.topics_enabled = False   # Master switch for the topics feature (default: False)
                                 # False → agents speak freely; all topic enforcement is bypassed.
                                 # True  → topic rotation, anchor injection, compliance scoring,
                                 #         and Fixy topic-compliance checks are all active.
```

When `topics_enabled = False` (the default), the following subsystems are **fully bypassed**:

* **TopicManager** — not initialised; `topicman` is `None` for the entire session (no topic rotation, no proposals, no selection)
* Topic anchor injection into prompts (`topic_anchor_enabled`, legacy anchor fallback)
* Forbidden carryover terms from the previous topic
* Cluster wallpaper penalty block
* Pre-generation anchor instruction and topic continuity hint
* DRAFT-stage topic compliance scoring (`TOPIC-RECOVERY` levels: none / soft / partial / hard)
* Post-Stage-2 `TOPIC-COMPLIANCE` diagnostic log
* Fixy intervention topic compliance scoring (`TOPIC-COMPLIANCE-FIXY`)

To re-enable full topic enforcement:

```python
config.topics_enabled = True
```

This is equivalent to the pre-4.1.0 default behaviour where topics were always enforced.

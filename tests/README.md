<div style="display: flex; align-items: center; justify-content: space-between;">
  <img src="../Assets/entelgia-logo.png" alt="Entelgia Logo" width="120" style="margin: 0;"/>
  <h1 style="flex-grow: 1; text-align: center; font-size: 2.5em; font-weight: bold; margin: 0;">🧪 Entelgia Test Suite</h1>
  <div style="width: 120px;" aria-hidden="true"></div>
</div>

Entelgia ships with comprehensive test coverage across **235 tests** in 11 suites:

### Enhanced Dialogue Tests (6 tests)

```bash
pytest tests/test_enhanced_dialogue.py -v
```

Tests verify:
- ✅ **Dynamic speaker selection** - No agent speaks 3+ times consecutively
- ✅ **Seed variety** - 6 different generation strategies
- ✅ **Context enrichment** - 8 turns, 6 thoughts, 5 memories
- ✅ **Fixy interventions** - Need-based (circular reasoning, repetition)
- ✅ **Persona formatting** - Rich traits and speech patterns

---

### ⚡ Energy Regulation Tests (35 tests)

```bash
pytest tests/test_energy_regulation.py -v
```

Tests verify:
- ✅ **FixyRegulator defaults** — threshold and constant values
- ✅ **Dream trigger** — fires when energy ≤ safety threshold
- ✅ **Energy recharge** — restored to 100.0 after dream cycle
- ✅ **Hallucination-risk probe** — stochastic detection below 60 %
- ✅ **EntelgiaAgent init** — initial state, regulator propagation
- ✅ **process_step** — energy drain, memory append, return values
- ✅ **Dream cycle** — subconscious consolidation and memory pruning
- ✅ **LTM promotion** — critical STM entries promoted to long-term memory during dream cycle

---

### 🧠 Long-Term Memory Tests (33 tests)

```bash
pytest tests/test_long_term_memory.py -v
```

Tests verify `DefenseMechanism`, `FreudianSlip`, and `SelfReplication` classes:
- ✅ **Repression classification** — painful emotions above threshold
- ✅ **Suppression classification** — mildly negative content
- ✅ **Freudian slip surfacing** — probabilistic recall of defended memories
- ✅ **Self-replication promotion** — recurring keyword detection

---

### 🔐 Memory Security Tests (19 tests)

```bash
pytest tests/test_memory_security.py -v
```

Entelgia ships with a comprehensive pytest test suite to ensure the reliability and security of its memory-protection subsystem. The current suite contains **19 tests** divided into three categories:

#### Signature Creation
Tests verify that creating an HMAC-SHA256 signature:
- Returns a 64-character hex string
- Behaves deterministically for the same message and key
- Yields different signatures for different messages
- Properly raises a `ValueError` when supplied with empty or `None` keys/messages

#### Signature Validation
Checks that:
- Valid signatures are accepted
- Wrong keys, tampered messages/signatures, or `None`/empty values correctly cause validation to fail

#### Security Properties
Tests assert that:
- Signatures are unique across multiple inputs and keys
- The implementation supports Unicode messages (mixed-language, Arabic, and emojis)

---

### 🔗 Drive Correlation Tests (21 tests)

```bash
pytest tests/test_drive_correlations.py -v
```

Tests verify the coherent Freudian drive correlations added in PR #92:
- ✅ **conflict_index boundaries** — zero conflict at balance, maximum at extremes
- ✅ **conflict_index parametrized** — spot-check against three known Id/Ego/SuperEgo scenarios
- ✅ **Ego erosion magnitude** — proportional reduction above the 4.0 threshold
- ✅ **Ego erosion monotonicity** — higher conflict → greater erosion
- ✅ **Temperature–conflict correlation** — temperature rises with conflict index
- ✅ **Temperature conflict component** — conflict component always positive
- ✅ **Energy drain scaling** — conflict adds to base drain
- ✅ **Energy drain cap** — drain never exceeds `2 × energy_drain_max`

---

### 🔥 Drive Pressure Tests (23 tests)

```bash
pytest tests/test_drive_pressure.py -v
```

Tests verify the DrivePressure urgency/tension system:
- ✅ **Pressure clamped to 0–10 range** — output always within bounds
- ✅ **High conflict raises pressure** — proportional increase
- ✅ **Stagnation raises pressure** — same topic ≥ 4 turns
- ✅ **Natural decay** — pressure decreases after progress/resolution
- ✅ **Forced brevity thresholds** — output trimmed at pressure ≥ 6.5 and ≥ 8.0
- ✅ **Unresolved question tracking** — count increments and decrements correctly

---

### 🛡️ Behavioral Rules Tests (16 tests)

```bash
pytest tests/test_behavioral_rules.py -v
```

Tests verify drive-triggered behavioral rules for Socrates and Athena:
- ✅ **Socrates conflict rule** — fires at and above conflict threshold 5.0
- ✅ **Athena dissent rule** — fires at and above dissent threshold 3.0
- ✅ **Rule content** — correct keywords injected (`binary choice`, `However`, `Yet`)
- ✅ **Prompt injection** — rule text inserted before "Respond now" in agent prompt

---

### 📊 Dialogue Metrics Tests (58 tests)

```bash
pytest tests/test_dialogue_metrics.py -v
```

Tests verify the three dialogue-quality metrics and the ablation study (PR #111):
- ✅ **circularity_rate** — Jaccard-based looping fraction
- ✅ **progress_rate** — forward topic shifts and synthesis markers
- ✅ **intervention_utility** — Fixy-window circularity reduction
- ✅ **circularity_per_turn** — rolling time-series correctness
- ✅ **AblationCondition enum** — all four conditions defined
- ✅ **run_ablation reproducibility** — same seed → identical results
- ✅ **Inter-condition ordering** — BASELINE circularity > DIALOGUE_ENGINE
- ✅ **print_results_table** — formatted output without crash
- ✅ **plot_circularity ASCII fallback** — works without matplotlib
- ✅ **Demo metric values** — exact circularity (0.022), progress (0.889), and intervention utility (0.167) match the demo dialogue

---

### 🔏 Memory Signing Migration Tests (5 tests)

```bash
pytest tests/test_memory_signing_migration.py -v
```

Tests verify the key-rotation and legacy-format migration logic in `MemoryCore`:
- ✅ **Fingerprint stored on first init** — `settings` table populated
- ✅ **No re-sign when fingerprint matches** — existing rows untouched
- ✅ **Re-sign on fingerprint mismatch** — all rows updated on key rotation
- ✅ **Legacy format recovery** — `None`→`"None"` format auto-healed after migration
- ✅ **Settings table existence** — created during `_init_db`

---

### 🎭 Demo Dialogue Tests (1 test)

```bash
pytest tests/test_demo_dialogue.py -v
```

Tests verify the structural and metric properties of the canonical 10-turn demo dialogue (Socrates / Athena / Fixy):
- ✅ **Turn count** — exactly 10 turns in the demo dialogue
- ✅ **All three roles present** — Socrates, Athena, and Fixy must each appear
- ✅ **Turn structure** — every turn has non-empty `role` and `text` fields
- ✅ **Low circularity** — `circularity_rate` below 0.1 for a well-structured demo
- ✅ **High progress** — `progress_rate` above 0.5, confirming forward movement
- ✅ **Non-negative intervention utility** — Fixy's contributions are tracked
- ✅ **Per-turn series length** — rolling circularity series matches dialogue length

---

### 🧬 SuperEgo Critique Tests (18 tests)

```bash
pytest tests/test_superego_critique.py -v
```

Tests verify the `evaluate_superego_critique()` function and the `Agent.speak()` state-reset behaviour:
- ✅ **Ego-dominant → no critique** — repro test: critique must NOT fire when Ego leads
- ✅ **SuperEgo-dominant → critique fires** — positive test with known drive values
- ✅ **Dominance margin boundary** — gap below margin skips; gap at/above margin applies
- ✅ **Conflict minimum** — SuperEgo-dominant but `conflict < conflict_min` → skip with conflict reason
- ✅ **Disabled flag** — `critique_enabled=False` always returns `should_apply=False`
- ✅ **CritiqueDecision dataclass** — fields (`should_apply`, `reason`, `critic`) correct
- ✅ **Stale-state regression** — `_last_superego_rewrite` and `_last_critique_reason` are reset each turn

---

### 🧠 Limbic Hijack Tests (15 tests)

```bash
pytest tests/test_limbic_hijack.py -v
```

Tests verify the limbic hijack mechanism introduced in v2.7.0:
- ✅ **Initial state** — `limbic_hijack=False` and `_limbic_hijack_turns=0` on agent creation
- ✅ **Activation (all conditions met)** — `id > 7`, `emotion_intensity > 0.7`, `conflict > 0.6` → hijack fires
- ✅ **No activation (id too low)** — `id ≤ 7` → hijack stays off
- ✅ **No activation (intensity too low)** — `emotion_intensity ≤ 0.7` → hijack stays off
- ✅ **No activation (conflict too low)** — `conflict_index() ≤ 0.6` → hijack stays off
- ✅ **Intensity-drop exit** — `emotion_intensity < 0.4` → hijack deactivates
- ✅ **Turn-cap exit** — reaches `LIMBIC_HIJACK_MAX_TURNS` → hijack deactivates
- ✅ **Counter increments while active** — `_limbic_hijack_turns` increases each non-exit turn
- ✅ **Impulsive response kind** — `_last_response_kind == "impulsive"` during hijack
- ✅ **Meta: limbic hijack message** — shown when `limbic_hijack=True`
- ✅ **Meta: superego message** — shown when `_last_superego_rewrite=True` and no hijack
- ✅ **Meta: no message when neither active** — silent when both flags are off
- ✅ **Meta: no "skipped" spam** — skipped message never appears
- ✅ **Meta: hijack has priority over superego** — hijack message wins when both are True

---

### 📋 New Tests — `dialogue_metrics.py` & `ablation_study.py` (PR #111)

#### `dialogue_metrics.py` Demo Output

```
============================================================
Dialogue Metrics Demo
============================================================

Circularity Rate    : 0.022
Progress Rate       : 0.889
Intervention Utility: 0.167

Per-turn circularity (rolling window=6):
  Turn  1: 0.00 |
  Turn  2: 1.00 |####################
  Turn  3: 0.33 |#######
  Turn  4: 0.17 |###
  Turn  5: 0.10 |##
  Turn  6: 0.07 |#
  Turn  7: 0.00 |
  Turn  8: 0.00 |
  Turn  9: 0.00 |
  Turn 10: 0.00 |

Done.
```

#### `ablation_study.py` Output

```
+----------------------------+----------------------------+----------------------------+----------------------------+
| Condition                  | Circularity Rate           | Progress Rate              | Intervention Utility       |
+----------------------------+----------------------------+----------------------------+----------------------------+
| Baseline                   | 0.630                      | 0.414                      | 0.000                      |
| DialogueEngine/Seed        | 0.097                      | 1.000                      | 0.000                      |
| Fixy Interventions         | 0.409                      | 0.517                      | 0.333                      |
| Dream/Energy               | 0.421                      | 0.517                      | 0.000                      |
+----------------------------+----------------------------+----------------------------+----------------------------+

Circularity Rate Over Turns (ASCII chart)
  1.0 |
  1.0 | #####*        *            +
  0.9 |
  0.8 |
  0.7 |     +##*    *##*         ##*+
  0.6 |
  0.4 |      + #***##++##**+***+#+ #
  0.3 |
  0.2 |       + ###    ++#+#+###    #
  0.1 |        +++       +# #
  0.0 |#ooooooooooooooooooooooooooooo
       -------------------------------
       Turn →
  * = Baseline
  o = DialogueEngine/Seed
  + = Fixy Interventions
  # = Dream/Energy
```

---

### 📋 New Tests — `context_manager.py` (PR #117)

```
$ python -m pytest tests/test_enhanced_dialogue.py::test_context_enrichment -v

tests/test_enhanced_dialogue.py::test_context_enrichment PASSED                                                  [100%]

============================================= 1 passed, 1 warning in 0.02s =============================================
```

> ✅ **1 context_manager test passes** — verifies `ContextManager.build_enriched_context()` returns a non-empty prompt with 8 recent turns, 6 thoughts, and 5 memories (PR #117).

In addition to the unit tests, the continuous-integration (CI/CD) pipeline automatically runs a suite of quality and security checks:

| Category | Tools | Purpose |
|----------|-------|---------|
| **Unit Tests** | `pytest` | Runs 250 total tests (6 dialogue + 35 energy + 33 LTM + 19 security + 21 drive correlations + 23 drive pressure + 16 behavioral rules + 58 dialogue metrics + 5 signing migration + 1 demo dialogue + 18 superego critique + 15 limbic hijack) |
| **Code Quality** | `black`, `flake8`, `mypy` | Code formatting, linting, and static type checking |
| **Security Scans** | `safety`, `bandit` | Dependency and code-security vulnerability detection |
| **Scheduled Audits** | `pip-audit` | Weekly dependency security audit |
| **Build Verification** | Package build tools | Ensures valid package creation |
| **Documentation** | Doc integrity checks | Validates documentation consistency |

> 🛡️ Together these jobs ensure that **every commit** adheres to style guidelines, passes vulnerability scans and produces a valid package and documentation.

---

### 🌐 Web Research Module Tests

The web research modules include unit tests for all components:

```bash
pytest tests/test_web_research.py -v
```

Tests cover:

- ✅ **`fixy_should_search`** — trigger keyword detection, edge cases (empty string, no keywords)
- ✅ **`evaluate_source` / `evaluate_sources`** — credibility scoring rules, clamping, ranking
- ✅ **`build_research_context`** — formatting with and without sources, max_sources limit
- ✅ **`maybe_add_web_context`** — graceful failure on network error, no-trigger path
- ✅ **`_store_external_knowledge`** — SQLite table creation and row insertion
- ✅ **`ContextManager.build_enriched_context`** — `web_context` parameter injection into prompt

All network calls in tests are mocked — no real HTTP requests are made.

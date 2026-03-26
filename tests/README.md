<div style="display: flex; align-items: center; justify-content: space-between;">
  <img src="../Assets/entelgia-logo.png" alt="Entelgia Logo" width="120" style="margin: 0;"/>
  <h1 style="flex-grow: 1; text-align: center; font-size: 2.5em; font-weight: bold; margin: 0;">🧪 Entelgia Test Suite</h1>
  <div style="width: 120px;" aria-hidden="true"></div>
</div>

Entelgia ships with comprehensive test coverage across **1274 tests** (1274 collected) in 33 suites:

### Enhanced Dialogue Tests (11 tests)

```bash
pytest tests/test_enhanced_dialogue.py -v
```

Tests verify:
- ✅ **Dynamic speaker selection** - No agent speaks 3+ times consecutively
- ✅ **Seed variety** - 6 different generation strategies
- ✅ **Context enrichment** - 8 turns, 6 thoughts, 5 memories
- ✅ **Fixy interventions** - Need-based (circular reasoning, repetition)
- ✅ **Persona formatting** - Rich traits and speech patterns
- ✅ **Persona pronouns** - Pronoun injection into persona context
- ✅ **Seed topic consistency** - Seed topic preserved across consecutive turns
- ✅ **Safe LTM content** — internal fields excluded from LTM memory content
- ✅ **Safe STM text** — internal fields excluded from STM text
- ✅ **No internal field leakage** — internal memory fields never surface in prompts
- ✅ **Internal field constants** — all internal field constants are complete and consistent

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

### 🧠 Long-Term Memory Tests (43 tests)

```bash
pytest tests/test_long_term_memory.py -v
```

Tests verify `DefenseMechanism`, `FreudianSlip`, and `SelfReplication` classes:
- ✅ **Repression classification** — painful emotions above threshold
- ✅ **Suppression classification** — mildly negative content
- ✅ **Freudian slip surfacing** — probabilistic recall of defended memories
- ✅ **Self-replication promotion** — recurring keyword detection
- ✅ **FreudianSlip rate-limiting** — `slip_cooldown_turns` blocks burst sequences
- ✅ **FreudianSlip deduplication** — `slip_dedup_window` suppresses identical repeats
- ✅ **FreudianSlip counters** — `attempts` and `successes` increment correctly

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

### 🔗 Drive Correlation Tests (28 tests)

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
- ✅ **Athena id drifts above neutral** — Athena's `id_strength` gravitates toward 6.5 over multiple turns
- ✅ **Socrates superego drifts above neutral** — Socrates' `superego_strength` gravitates toward 6.5 over multiple turns
- ✅ **Generic agent stays near neutral** — agents without a bias target revert toward 5.0
- ✅ **Athena id bias drains ego** — elevated Athena Id above 5.0 reduces `ego_strength`
- ✅ **Socrates superego bias drains ego** — elevated Socrates SuperEgo above 5.0 reduces `ego_strength`
- ✅ **Athena id extreme high reverts faster** — id ≥ 8.5 triggers extra reversion boost
- ✅ **Socrates superego extreme low reverts faster** — superego ≤ 1.5 triggers extra reversion boost

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

### 🛡️ Behavioral Rules Tests (71 tests)

```bash
pytest tests/test_behavioral_rules.py -v
```

Tests verify drive-triggered behavioral rules for Socrates and Athena:
- ✅ **Socrates conflict rule** — fires above conflict threshold 6.0 when random gate passes
- ✅ **Athena dissent rule** — fires above conflict threshold 6.0 when random gate passes
- ✅ **Random gate suppression** — rule suppressed when random gate does not fire, even above threshold
- ✅ **Non-speaker exemption** — rule never fires for an agent that does not own the rule
- ✅ **Rule content** — correct keywords injected (`binary choice`, challenge/counter phrasing)
- ✅ **Prompt injection** — rule text inserted before "Respond now" in agent prompt
- ✅ **Rule LH — Athena limbic hijack anger** — fires when Athena is in active limbic hijack state
- ✅ **Rule LH content** — mentions harsh language and emotional override
- ✅ **Rule LH takes priority over Rule B** — anger rule wins even when conflict > 6
- ✅ **Rule LH absent when hijack off** — no anger rule when `limbic_hijack=False`
- ✅ **Socrates hijack does not trigger Rule LH** — anger rule is Athena-only
- ✅ **Rule SC — Socrates anxiety** — fires when Socrates' SuperEgo is dominant over Id and Ego by ≥ 0.5
- ✅ **Rule SC content** — mentions nervousness and hesitant language
- ✅ **Rule SC fires without random gate** — unconditional when condition met
- ✅ **Rule SC absent when SuperEgo not dominant** — silent below threshold
- ✅ **Rule SC takes priority over Rule A** — anxiety rule wins over binary-choice question rule
- ✅ **Athena SuperEgo-dominant does not trigger Rule SC** — anxiety rule is Socrates-only

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

### 🧬 SuperEgo Critique Tests (28 tests)

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
- ✅ **Consecutive-streak limit** — rewrite suppressed after 2 consecutive critique turns; counter resets after a non-critique turn
- ✅ **Tight margin fires at extreme SuperEgo** — `dominance_margin=0.2` allows barely-dominant extreme SuperEgo to fire
- ✅ **Normal margin suppresses barely-dominant SuperEgo** — default `dominance_margin=0.5` prevents barely-dominant case
- ✅ **Low conflict fires with extreme conflict_min** — `conflict_min=1.0` allows low-conflict extreme SuperEgo critique
- ✅ **Normal conflict_min suppresses low conflict** — default `conflict_min=2.0` blocks low-conflict critique
- ✅ **Socrates last emotion is fear when critique fires** — `_last_emotion` set to `"fear"` during critique
- ✅ **Socrates emotion not fear when critique does not fire** — emotion unchanged when critique skipped
- ✅ **Critique prompt for Socrates mentions anxious tone** — rewrite instruction explicitly requests anxious, nervous tone

---

### 🧠 Limbic Hijack Tests (20 tests)

```bash
pytest tests/test_limbic_hijack.py -v
```

Tests verify the limbic hijack mechanism introduced in v2.7.0:
- ✅ **Initial state** — `limbic_hijack=False` and `_limbic_hijack_turns=0` on agent creation
- ✅ **Activation (all conditions met)** — `id > 7`, `emotion_intensity > 0.7`, `conflict > 0.6` → hijack fires
- ✅ **No activation (id too low)** — `id ≤ 7` → hijack stays off
- ✅ **No activation (intensity too low)** — `emotion_intensity ≤ 0.7` → hijack stays off
- ✅ **No activation (conflict too low)** — `conflict_index() ≤ 0.6` → hijack stays off
- ✅ **Extreme id lowers intensity threshold** — at `id_strength >= 8.5`, intensity threshold drops from 0.7 to 0.5
- ✅ **No activation at normal id with moderate intensity** — moderate intensity only triggers hijack when id is extreme
- ✅ **Intensity-drop exit** — `emotion_intensity < 0.4` → hijack deactivates
- ✅ **Turn-cap exit** — reaches `LIMBIC_HIJACK_MAX_TURNS` → hijack deactivates
- ✅ **Counter increments while active** — `_limbic_hijack_turns` increases each non-exit turn
- ✅ **Impulsive response kind** — `_last_response_kind == "impulsive"` during hijack
- ✅ **Athena last emotion is anger** — `_last_emotion` set to `"anger"` during Athena's limbic hijack
- ✅ **Athena behavioral rule contains anger instruction** — injected rule text references raw anger
- ✅ **Non-Athena agent does not get anger rule** — Rule LH is Athena-only
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
| **Unit Tests** | `pytest` | Runs 1274 total tests across 33 suites (web research, circularity guard, fixy improvements, progress enforcer, behavioral rules, generation quality, topic anchors, dialogue metrics, stabilization pass, LTM, topic enforcer, topic style, energy, revise draft, context manager, loop guard, transform draft, superego critique, ablation study, web tool, affective LTM, drive correlations, drive pressure, limbic hijack, memory security, semantic repetition, seed topic clusters, enhanced dialogue, enable observer, signing migration, demo dialogue, openai backend) |
| **Code Quality** | `black`, `flake8`, `mypy` | Code formatting, linting, and static type checking |
| **Security Scans** | `safety`, `bandit` | Dependency and code-security vulnerability detection |
| **Scheduled Audits** | `pip-audit` | Weekly dependency security audit |
| **Build Verification** | Package build tools | Ensures valid package creation |
| **Documentation** | Doc integrity checks | Validates documentation consistency |

> 🛡️ Together these jobs ensure that **every commit** adheres to style guidelines, passes vulnerability scans and produces a valid package and documentation.

---

### 👁️ Enable Observer Tests (10 tests)

```bash
pytest tests/test_enable_observer.py -v
```

Tests verify the `enable_observer` configuration flag introduced in v3.0.0 (PR #207):

- ✅ **Default is True** — `Config.enable_observer` defaults to `True`
- ✅ **False accepted** — `Config.enable_observer=False` passes validation without error
- ✅ **Observer disabled → no InteractiveFixy** — `MainScript.__init__` skips creating `interactive_fixy` when `enable_observer=False`
- ✅ **Observer enabled → InteractiveFixy created** — `interactive_fixy` is created in enhanced mode with default config
- ✅ **Fixy excluded from speakers** — `allow_fixy` forced to `False` / `0.0` when observer is disabled
- ✅ **No intervention calls** — `should_intervene` is never called when observer is off
- ✅ **Speaker selection bypass** — Fixy is never added to the speaker pool when `enable_observer=False`
- ✅ **Env var respected** — `ENTELGIA_ENABLE_OBSERVER=false` disables the observer via environment
- ✅ **Non-enhanced mode unaffected** — disabling observer in non-enhanced mode does not crash
- ✅ **Both modes consistent** — `enable_observer` behaviour is uniform across enhanced and standard modes

---

### 🔁 Loop Guard Tests (30 tests)

```bash
pytest tests/test_loop_guard.py -v
```

Tests verify `DialogueLoopDetector`, `PhraseBanList`, `DialogueRewriter`, `TopicManager.force_cluster_pivot`, and `FixyMode`/`AgentMode` integration in `entelgia/loop_guard.py`:

- ✅ **LOOP_REPETITION detection** — identical turns above threshold flagged as repetition loop
- ✅ **WEAK_CONFLICT detection** — dialogue with insufficient conflict markers flagged
- ✅ **PREMATURE_SYNTHESIS detection** — synthesis-like closing before adequate depth reached
- ✅ **TOPIC_STAGNATION detection** — topic unchanged across too many consecutive turns
- ✅ **PhraseBanList blocking** — banned phrases are detected and blocked
- ✅ **PhraseBanList allow** — non-banned phrases pass through
- ✅ **DialogueRewriter rewrite** — stagnating turns rewritten with injected alternatives
- ✅ **TopicManager cluster pivot** — forced pivot moves to a different topic cluster
- ✅ **TOPIC_CLUSTERS structure** — all clusters non-empty and contain unique topics
- ✅ **_TOPIC_TO_CLUSTER mapping** — every topic maps to a valid cluster
- ✅ **get_cluster** — returns correct cluster for known topics
- ✅ **topics_in_different_cluster** — cross-cluster pairs detected correctly
- ✅ **FixyMode loop policy** — Fixy mode escalates correctly on detected loop type
- ✅ **AgentMode loop policy** — agent mode adapts to loop type
- ✅ **No false positive — clean dialogue** — healthy dialogue produces no loop flags
- ✅ **Boundary conditions** — exact threshold values handled correctly
- ✅ **Empty dialogue** — no crash on zero turns
- ✅ **Single turn** — no false loop on single-turn dialogue
- ✅ **Two turns** — minimum context handled gracefully
- ✅ **Mixed loops** — multiple loop types in same dialogue all detected
- ✅ **Reset state** — detector state resets correctly between checks
- ✅ **Unknown topic** — graceful handling of topic not in any cluster

---

### 🔁 Semantic Repetition Detection Tests (13 tests, 1 skipped)

```bash
pytest tests/test_detect_repetition_semantic.py -v
```

Tests verify the semantic similarity layer added to `InteractiveFixy._detect_repetition` in `entelgia/fixy_interactive.py`:

- ✅ **Jaccard-only fallback** — `_semantic_similarity` returns `0.0` when `sentence-transformers` is not installed
- ✅ **Model-None fallback** — `_semantic_similarity` returns `0.0` when the model fails to load
- ⏭️ **Float range guard** — `_semantic_similarity` always returns a value in `[0, 1]` *(skipped if `sentence-transformers` not installed)*
- ✅ **`_encode_turns` unavailable** — returns `None` when `_SEMANTIC_AVAILABLE` is `False`
- ✅ **`_encode_turns` model-None** — returns `None` when model is `None`
- ✅ **Short-turn early exit** — fewer than 4 turns returns `False` without encoding
- ✅ **Jaccard repetition detected** — 5 identical turns flagged under Jaccard-only path
- ✅ **Jaccard no repetition** — 4 fully distinct turns not flagged
- ✅ **High semantic boosts detection** — high cosine similarity pushes combined score above threshold
- ✅ **Low combined score** — low Jaccard + low semantic keeps combined ≤ 0.5 → not repetitive
- ✅ **Boundary exactly 0.5** — `combined_score == 0.5` is NOT repetitive (strict `>` threshold)
- ✅ **Encode-None falls back to Jaccard** — when `_encode_turns` returns `None` at runtime, Jaccard-only path takes over

> `sentence-transformers` and `scikit-learn` are optional (`pip install "entelgia[semantic]"`). All tests that require the library are automatically skipped when it is not installed.

---

### 🌐 Web Research Module Tests (202 tests)

The web research modules include unit tests for all components:

```bash
pytest tests/test_web_research.py -v
```

Tests cover:

- ✅ **`fixy_should_search`** — trigger keyword detection, edge cases (empty string, no keywords), dialogue-history scanning, Fixy-reason mapping, cooldown logging
- ✅ **`find_trigger`** — phrase-over-keyword priority, position tie-breaking, concept-term scoring
- ✅ **Concept terms beat generic triggers** — `credibility`, `bias`, `epistemology` each outscore `source`
- ✅ **Filler-word removal** — `that`, `this`, `how`, `what` stripped from compressed queries
- ✅ **`evaluate_source` / `evaluate_sources`** — credibility scoring rules, clamping, ranking
- ✅ **`build_research_context`** — formatting with and without sources, max_sources limit
- ✅ **`maybe_add_web_context`** — graceful failure on network error, no-trigger path, dialogue and Fixy-reason triggers
- ✅ **`build_research_query`** — trigger-fragment extraction, filler/instruction-word removal, topic-line parsing, HTML-entity stripping, whitespace normalisation
- ✅ **`_rewrite_search_query`** — concept extraction, agent-name stripping, gerund removal, fallback on missing trigger
- ✅ **Rewrite quality** — avoids broken fragments, prefers concept terms, excludes weak nouns and verb-like forms
- ✅ **`_store_external_knowledge`** — SQLite table creation and row insertion, 1,000-char summary truncation
- ✅ **`ContextManager.build_enriched_context`** — `web_context` parameter injection into prompt
- ✅ **`_sanitize_text`** — possessive stripping, punctuation removal, agent-name removal, mode-string removal, whitespace normalisation
- ✅ **`_compress_to_keywords`** — stopword removal, 6-word limit
- ✅ **Trigger cooldown** — same keyword blocked within window; different keywords independent; `clear_cooldown` resets state
- ✅ **Per-query cooldown** — same `seed_text` suppressed within cooldown window; different queries independent; cooldown expires after `_COOLDOWN_TURNS`; `clear_trigger_cooldown` resets per-query state
- ✅ **Failed-URL blacklist** — URLs returning 403/404 are blacklisted and skipped on retry; non-403/404 errors do not blacklist; `clear_failed_urls` resets the set; blacklisted URLs make no network request
- ✅ **Query cache** — second call with same query skips network; returns valid context
- ✅ **Topic research cache** — same topic not repeated within session; different topics independent
- ✅ **Quality gate** — skips injection when no pages fetched or topic overlap too low; injects when gate passes
- ✅ **Structured logging** — query, result count, pages fetched, injection status, topic all logged
- ✅ **Branch-level debug logging** — seed/dialogue/Fixy-reason branches each log source type, trigger, and preview; query-build branch logs correctly

All network calls in tests are mocked — no real HTTP requests are made.

---

### 🌐 Web Tool Tests (26 tests)

```bash
pytest tests/test_web_tool.py -v
```

Tests verify `entelgia/web_tool.py` — the DuckDuckGo search and page-fetch layer:

- ✅ **`clear_failed_urls`** — resets the module-level failed-URL blacklist
- ✅ **`_clean_text`** — collapses multiple blank lines; strips leading/trailing whitespace
- ✅ **`fetch_page_text` — blacklist skip** — URLs in `_failed_urls` return empty result without a network call
- ✅ **`fetch_page_text` — 403 blacklisting** — HTTP 403 response adds URL to blacklist
- ✅ **`fetch_page_text` — 404 blacklisting** — HTTP 404 response adds URL to blacklist
- ✅ **`fetch_page_text` — result keys** — returned dict always contains `url`, `title`, `text`
- ✅ **`fetch_page_text` — network error** — `RequestException` returns empty result without crash
- ✅ **`fetch_page_text` — text_limit respected** — extracted text truncated to requested limit
- ✅ **`web_search` — network error** — returns empty list on `RequestException`
- ✅ **`web_search` — HTTP error** — returns list (possibly empty) on HTTP error
- ✅ **`web_search` — max_results** — never returns more entries than requested
- ✅ **`search_and_fetch` — result structure** — returns dict with `query` and `sources`
- ✅ **`search_and_fetch` — empty search** — empty search results yield empty sources list
- ✅ **`search_and_fetch` — source keys** — each source has `title`, `url`, `snippet`, `text`

---

### 🧰 Context Manager Tests (30 tests)

```bash
pytest tests/test_context_manager.py -v
```

Tests verify `entelgia/context_manager.py` — the prompt-assembly and memory-integration layer:

- ✅ **`_safe_ltm_content`** — returns only the `content` field; all internal fields stripped
- ✅ **`_safe_stm_text`** — returns only the `text` field; all internal STM fields stripped
- ✅ **`build_enriched_context` — non-empty output** — always returns a non-empty string
- ✅ **`build_enriched_context` — agent name** — agent name appears in prompt
- ✅ **`build_enriched_context` — seed** — user seed topic injected into prompt
- ✅ **`build_enriched_context` — persona** — persona string appears in prompt
- ✅ **`build_enriched_context` — LTM content** — LTM memory content appears in prompt
- ✅ **`build_enriched_context` — STM text** — STM text appears in prompt
- ✅ **`build_enriched_context` — internal LTM fields hidden** — `signature_hex`, `expires_at`, etc. never appear
- ✅ **`build_enriched_context` — web_context injection** — research context injected when provided
- ✅ **`build_enriched_context` — topic_style injection** — `STYLE INSTRUCTION` block present when style is set
- ✅ **`build_enriched_context` — empty lists** — works correctly with empty STM and LTM
- ✅ **`_prioritize_memories` — higher importance ranked first** — most important memory leads
- ✅ **`_prioritize_memories` — limit respected** — never returns more than requested
- ✅ **`EnhancedMemoryIntegration.retrieve_relevant_memories`** — relevant memories surface; limit respected; empty input returns empty list

---

### 🔬 Ablation Study Tests (28 tests)

```bash
pytest tests/test_ablation_study.py -v
```

Tests verify `entelgia/ablation_study.py` — the four-condition ablation framework:

- ✅ **`AblationCondition` enum** — all four conditions (`BASELINE`, `DIALOGUE_ENGINE`, `FIXY`, `DREAM`) defined with correct labels
- ✅ **`run_condition` — returns list** — each condition produces a list of `{"role", "text"}` dicts
- ✅ **`run_condition` — turns count** — exact number of turns simulated matches the `turns` parameter
- ✅ **`run_condition` — deterministic** — same seed always produces identical dialogue
- ✅ **`run_condition` — seed variation** — different seeds produce different dialogues
- ✅ **`run_ablation` — all conditions present** — result dict contains an entry for every condition
- ✅ **`run_ablation` — metrics structure** — each entry contains `metrics` (dict) and `circularity_series` (list)
- ✅ **`run_ablation` — metric keys** — `circularity_rate` and `progress_rate` present in every metrics dict
- ✅ **`run_ablation` — numeric values** — all metric values are `int` or `float`
- ✅ **`run_ablation` — deterministic** — same seed yields identical results across calls
- ✅ **`print_results_table` — no exception** — runs without error on valid results
- ✅ **`print_results_table` — non-empty output** — produces visible tabular text
- ✅ **`print_results_table` — condition names** — `Baseline` and `Fixy` appear in the output

---

### 🎨 Topic Style Tests (39 tests)

```bash
pytest tests/test_topic_style.py -v
```

Tests verify `entelgia/topic_style.py` — the topic-aware style selection system introduced in v3.0.0:

- ✅ **`TOPIC_STYLE` dict** — all seven production clusters mapped to a style
- ✅ **`get_style_for_cluster`** — returns correct style for each cluster
- ✅ **`get_style_for_topic`** — maps individual topics to their cluster style
- ✅ **`build_style_instruction`** — generates per-role style instructions (Socrates, Athena, Fixy)
- ✅ **Unknown cluster/topic fallback** — returns default style without error

---

### ⚓ Topic Anchors Tests (60 tests)

```bash
pytest tests/test_topic_anchors.py -v
```

Tests verify the `TOPIC_ANCHORS` dict and `_contains_any` / `_validate_topic_compliance` helpers:

- ✅ **All 56 topics have anchor lists** — no topic in `TOPIC_CLUSTERS` missing from `TOPIC_ANCHORS`
- ✅ **Non-empty anchor lists** — every anchor list contains at least one keyword
- ✅ **String keywords** — all anchor keywords are non-empty strings
- ✅ **AI alignment anchors** — required concept terms present
- ✅ **Risk and decision-making anchors** — broad vocabulary included to prevent false-positive topic mismatch
- ✅ **`_contains_any` case-insensitive** — matching works regardless of case
- ✅ **`_validate_topic_compliance`** — correctly classifies compliant and non-compliant responses

---

### ✍️ Revise Draft Tests (32 tests)

```bash
pytest tests/test_revise_draft.py -v
```

Tests verify `revise_draft`, `_split_sentences`, and `_sentence_overlap` in `Entelgia_production_meta.py`:

- ✅ **`_split_sentences`** — correctly splits on `.`, `!`, `?` boundaries
- ✅ **`_sentence_overlap`** — Jaccard word overlap between sentence pairs
- ✅ **`revise_draft` — no revision needed** — unique sentences returned unchanged
- ✅ **`revise_draft` — repeated sentence removed** — duplicate removed from draft
- ✅ **`revise_draft` — empty input** — handles empty string without crash

---

### 🌱 Seed Topic Clusters Tests (12 tests)

```bash
pytest tests/test_seed_topic_clusters.py -v
```

Tests verify `TOPIC_CLUSTERS` structure and `SeedGenerator` behaviour:

- ✅ **Cluster structure** — all clusters non-empty and contain unique topic strings
- ✅ **`SeedGenerator.generate_seed`** — returns non-empty string for every known topic
- ✅ **Unknown topic fallback** — graceful handling of topic not in any cluster

---

### 🧬 Affective LTM Integration Tests (24 tests)

```bash
pytest tests/test_affective_ltm_integration.py -v
```

Tests verify affective long-term memory retrieval integration:

- ✅ **Debug toggle** — `show_affective_ltm_debug` flag controls debug output
- ✅ **Min-score threshold** — memories below threshold are excluded
- ✅ **Supplement injection** — affective memories injected into prompt context
- ✅ **Empty supplement when disabled** — no injection when feature is off
- ✅ **Per-agent emotion weighting** — `affective_emotion_weight` applied correctly per agent

---

### 🎯 Generation Quality Tests (75 tests)

```bash
pytest tests/test_generation_quality.py -v
```

Tests verify output quality pipeline components:

- ✅ **`output_passes_quality_gate`** — returns False when ≥ 2 banned rhetorical patterns are found
- ✅ **`_strip_scaffold_labels`** — removes numbered scaffold labels (e.g. `"1. Claim:"`, `"Implication:"`)
- ✅ **`LLM_OUTPUT_CONTRACT` phrase cleanliness** — contract text is free of banned phrases
- ✅ **`LLM_FORBIDDEN_PHRASES_INSTRUCTION`** — includes new banned phrases (`'it is important'`, `"let's consider"`, `'given the topic'`)
- ✅ **Per-agent behavioral contracts** — Socrates, Athena, and Fixy contracts present and distinct
- ✅ **Output contract prose requirements** — 2–3 sentence limit and no-visible-labels requirement enforced

---

### 🔩 Stabilization Pass Tests (55 tests)

```bash
pytest tests/test_stabilization_pass.py -v
```

Tests verify stabilization pass features:

- ✅ **Memory topic filter** — `_score_memory_topic_relevance` scoring, min-score threshold, cluster requirement
- ✅ **Cluster wallpaper penalty** — repeated cluster-generic terms penalised within repeat window
- ✅ **Fixy role-aware compliance** — `compute_fixy_compliance_score` stricter rules applied to Fixy
- ✅ **Web trigger multi-signal gate** — `_count_strong_trigger_hits`, `_has_uncertainty_or_evidence_signal` gating
- ✅ **Topic anchor configurable fields** — `topic_anchor_enabled`, `topic_anchor_max_forbidden_items` respected
- ✅ **Self-replication topic gate** — pattern matching gated by topic-relevance scoring
- ✅ **Debug flag forwarding** — all `show_*_debug` flags control output correctly

---

### 🔍 Topic Enforcer Tests (41 tests)

```bash
pytest tests/test_topic_enforcer.py -v
```

Tests verify `entelgia/topic_enforcer.py` compliance scoring and vocabulary functions:

- ✅ **`compute_topic_compliance_score`** — correct scoring for compliant and non-compliant responses
- ✅ **`compute_fixy_compliance_score`** — Fixy-specific stricter rules applied correctly
- ✅ **`get_cluster_wallpaper_terms`** — returns cluster-generic vocabulary list
- ✅ **`get_topic_distinct_lexicon`** — returns topic-distinct vocabulary list
- ✅ **`build_soft_reanchor_instruction`** — generates correct reanchor instruction text
- ✅ **`ACCEPT_THRESHOLD`** — constant value correct
- ✅ **`SOFT_REANCHOR_THRESHOLD`** — constant value correct

---

### 🔄 Circularity Guard Tests (92 tests)

```bash
pytest tests/test_circularity_guard.py -v
```

Tests verify `entelgia/circularity_guard.py` pre-generation circularity detection:

- ✅ **`detect_semantic_repetition` (Jaccard path)** — empty history returns false, below-min-history returns false, identical texts flagged, diverse texts not flagged, delta score uses max over history, delta reduces score for consistently similar history
- ✅ **`detect_semantic_repetition` (embeddings path)** — high similarity flagged, low similarity not flagged, model failure falls back to Jaccard, threshold boundary respected
- ✅ **`detect_structural_templates`** — no templates not flagged, single template not flagged, two rhetorical patterns flagged, tradeoff variants not counted as rhetorical alone, system constraint not rhetorical, duplicated speaker prefix detected, case-insensitive matching
- ✅ **`detect_cross_topic_contamination`** — clean text not flagged, generic carryover phrases (Option A/B, "in the previous topic") flagged, leaked template phrases ("forgiveness", "peace and harmony") flagged, topic-specific carryover flagged, multiple carryover phrases detected, case-insensitive matching
- ✅ **`compute_circularity_score`** — empty history gives low score, all result fields present, score in valid range, high semantic repetition raises score, contamination raises score, `is_circular` flag matches threshold, `reasons` populated when circular
- ✅ **Adaptive threshold** — zero-history threshold, threshold grows with history size, threshold capped at 0.70, higher threshold means fewer false positives, dynamic threshold used in compute
- ✅ **First-turn-after-topic-change leniency** — first turn score reduced, first turn less likely to be flagged, no leniency when flag is false
- ✅ **`CircularityResult` fields** — `threshold` field present and matches explicit value, `semantic_score` is delta not raw max, all fields have correct types, score in valid range, `is_circular` consistent with score and threshold

---

### 🔧 Fixy Improvements Tests (68 tests)

```bash
pytest tests/test_fixy_improvements.py -v
```

Tests verify improved Fixy intervention logic in `entelgia/loop_guard.py` and `entelgia/fixy_interactive.py`:

- ✅ **Pair gating (`DialogueLoopDetector`)** — loop not declared when only Socrates turns present, loop not declared when only Athena turns present, pair required for loop detection, single turns never trigger
- ✅ **Pair gating (`InteractiveFixy`)** — no intervention after single Socrates or Athena turn, no intervention when only one agent appears many times, intervention allowed after both agents have spoken, `pending_rewrite_mode` set on intervention and cleared on no-intervention
- ✅ **Novelty suppression** — loop not declared when new metric, concrete case, forced choice, testable claim, or operational definition is present; structural loop fires without novelty; novelty check returns clusters; no novelty in pure repetition
- ✅ **Rewrite mode selection** — loop repetition → `force_case`, weak conflict → `force_choice`, premature synthesis → `force_test`, topic stagnation → `force_metric`, shallow discussion → `force_test`; all rewrite modes have prompts; rewrite mode constants have correct values
- ✅ **Rewrite hint generation** — hint contains rewrite header, rewrite mode, and target agent; hint is structural for each mode (`force_metric`, `force_choice`, `force_test`, `force_case`, `force_definition`); hint sets `pending_rewrite_hint`; empty hint when no modes; hint infers mode from active modes
- ✅ **`DialogueRewriter` structural mode** — rewrite includes mode label and target agent; rewrite-mode rule takes priority; no rewrite mode still works
- ✅ **False positive reduction** — advancing dialogue suppressed, stagnant dialogue still detected, advancement keywords regression
- ✅ **Both-agents-present check** — true with both, false when only one, correct for Fixy combinations
- ✅ **`validate_force_choice`** — commitment phrases accepted (`"I choose"`, `"is wrong because"`, `"not X but Y"`, `"wins because"`), hedge phrases rejected (`"both matter"`, `"it depends"`, `"balance"`, `"third path"`, `"reframing without choice"`), commitment overrides single hedge
- ✅ **Pair gating window scope** — gate closed after Fixy intervention, opens after Fixy when both present, resets after topic shift, resets after dream cycle, resets after each Fixy turn, accepted log emitted when gate passes

---

### ✍️ Transform Draft to Final Tests (28 tests)

```bash
pytest tests/test_transform_draft_to_final.py -v
```

Tests verify the `transform_draft_to_final()` Stage 2 generation function:

- ✅ **Short / empty input passthrough** — empty string, single-word, and two-word texts returned unchanged without calling the LLM
- ✅ **Normal LLM call** — LLM output is returned, `generate()` called exactly once, draft text included in prompt, topic included in prompt when provided, no topic line when topic is empty, correct model and temperature passed
- ✅ **Fallback behaviour** — empty LLM response returns draft, `None` response returns draft, LLM exception returns draft
- ✅ **Persona notes** — Socrates, Athena, and Fixy personas present in prompt; all three agents have notes in `_FINAL_STAGE_PERSONA_NOTES`; unknown agent uses generic persona
- ✅ **Prompt contract** — max 3 sentences enforced, banned phrases blocked (`"my model"`, `"this suggests"`, `"it is important"`, `"one might argue"`), no preamble, natural prose required
- ✅ **`Agent.speak()` integration** — `speak()` calls `transform_draft_to_final()` as Stage 2, passes draft to transform, uses transform output (not draft) as final response

---

### 🤖 LLM OpenAI Backend Tests (10 tests)

```bash
pytest tests/test_llm_openai_backend.py -v
```

Tests verify `LLM.generate()` with the OpenAI backend:

- ✅ **Normal response** — `choices[0].message.content` is returned and whitespace-stripped
- ✅ **`None` content** — tool-call response with `None` content returns empty string without crashing
- ✅ **Edge cases** — empty `choices` list, missing `choices` key, missing `message` key all return empty string safely
- ✅ **Empty content string** — empty string in content returns empty string
- ✅ **Correct endpoint** — Chat Completions URL is used (`/v1/chat/completions`), not the Responses API
- ✅ **Request body format** — `messages` field used (not `input`), `Authorization: Bearer` header uses `openai_api_key`

---

### 📈 Progress Enforcer Tests (69 tests)

```bash
pytest tests/test_progress_enforcer.py -v
```

Tests verify `entelgia/progress_enforcer.py` dialogue progress tracking:

- ✅ **`extract_claims`** — returns list, excludes questions, declarative sentences included, max-claims limit respected, empty text returns empty, short text excluded, commitment phrase boosts ranking
- ✅ **`classify_move`** — all move types detected: filler, balanced restatement, direct attack, direct defense, forced choice, reframe, resolution attempt, escalation, new claim (low similarity), paraphrase (high similarity), soft nuance
- ✅ **`score_progress`** — returns string, score in range, high score for attack move, low score for filler, high similarity penalises score, commitment raises score, no state change penalty
- ✅ **`ClaimsMemory`** — add and retrieve claims, deduplication, `update_status` challenged and defended, `state_changed_by` detection
- ✅ **`detect_stagnation`** — low scores trigger commitment intervention, repeated moves trigger attack intervention, no state change triggers evidence intervention, unknown reason returns commitment
- ✅ **`get_intervention_policy`** — all reason → policy mappings correct
- ✅ **`build_intervention_instruction`** — commitment, attack, and evidence instruction content; unresolved claim hint included; no hint when memory empty; returns string
- ✅ **`update_claims_memory`** — adds new claims, attack move challenges existing claim, returns list
- ✅ **Module-level state** — add/get scores and moves, clear specific agent, clear all agents, deque max size enforced
- ✅ **`get_regeneration_instruction`** — returns non-empty string, mentions key concepts
- ✅ **End-to-end scenario** — stagnation triggers after multiple low-progress turns, high-value move prevents stagnation

```bash
# Run the full suite
pytest tests/ -v

# Run with coverage report
pytest tests/ --cov=. --cov-report=term

# Run a single suite
pytest tests/test_long_term_memory.py -v
```

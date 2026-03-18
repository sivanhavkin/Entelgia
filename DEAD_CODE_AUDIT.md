# 🔍 Entelgia Dead Code Audit Report

**Scope:** All Python files in the Entelgia repository  
**Method:** Full file reading, cross-file grep for every symbol, test cross-reference  
**Policy:** Read-only audit — no code was changed, deleted, or patched.

---

## Summary

| Category | Count |
|---|---|
| High-confidence dead symbols | 8 |
| Medium-confidence dead symbols | 9 |
| Low-confidence / indirectly used | 7 |
| Unused imports (confirmed) | 2 |
| Unused imports (typing/minor) | 4 |
| Draft/dead file (entire) | 1 |

---

## Section 1 — HIGH CONFIDENCE: Likely Dead Code

### 1.1 `is_global_show_pronouns` — `entelgia/enhanced_personas.py` line 18

```python
is_global_show_pronouns: bool = False
```

- **Direct callers:** None. Zero calls anywhere in the codebase.
- **Indirect use:** Exported via `__init__.py` (`__all__`) but never read in production files or any test.
- **In tests:** No.
- **Dynamic use:** Unlikely — simple boolean flag.
- **Context:** The production files use `Config.show_pronoun` (line ~1688 in `Entelgia_production_meta.py`) which fully replaces this module-level flag. This appears to be a remnant from an earlier design.
- **Confidence:** HIGH
- **Recommendation:** LIKELY DEAD

---

### 1.2 `get_typical_opening()` — `entelgia/enhanced_personas.py` line 219

```python
def get_typical_opening(agent_name: str) -> str:
```

- **Direct callers:** Not called in any production file or script.
- **Indirect use:** Exported via `__init__.py`; appears in `scripts/validate_implementations.py` KEY_FUNCTIONS list (existence check only, not a call).
- **In tests:** No.
- **Confidence:** HIGH
- **Recommendation:** LIKELY DEAD — exported as public API but never consumed.

---

### 1.3 `InteractiveFixy.should_request_research()` — `entelgia/fixy_interactive.py` line ~775

```python
def should_request_research(
    self, dialog: List[Dict[str, str]], current_turn: int
) -> Tuple[bool, str]:
```

- **Direct callers:** Zero — never called from `Entelgia_production_meta.py`, tests, or scripts.
- **Indirect use:** No dispatch table or callback references found.
- **In tests:** No.
- **Context:** Research trigger decisions are made via `fixy_should_search()` in `web_research.py`. This method was never wired up.
- **Confidence:** HIGH
- **Recommendation:** LIKELY DEAD

---

### 1.4 `import numpy as _np` — `entelgia/fixy_interactive.py` line ~256

```python
import numpy as _np
```

- **Status:** Inside an optional `try` block for sentence-transformers. `_np` is never referenced anywhere after this import line.
- **Direct use:** Zero occurrences of `_np` in the file body.
- **Confidence:** HIGH
- **Recommendation:** LIKELY DEAD — genuine unused import.

---

### 1.5 `safe_apply_patch()` — `Entelgia_production_meta.py` and `Entelgia_production_meta_200t.py` line ~4660 / ~4638

```python
def safe_apply_patch(original: str, patch: str) -> Tuple[bool, str]:
```

- **Direct callers:** Zero. Appears in `scripts/validate_implementations.py` KEY_FUNCTIONS list — an existence check only.
- **Indirect use:** Not in any dispatch table; not called via `getattr`.
- **In tests:** No test calls `safe_apply_patch`.
- **Confidence:** HIGH
- **Recommendation:** MANUAL REVIEW — appears to be a future integration point for a self-patching mechanism. Currently dead at runtime.

---

### 1.6 `VersionTracker.snapshot_text()` — `Entelgia_production_meta.py` and `Entelgia_production_meta_200t.py` line ~4644 / ~4622

```python
def snapshot_text(self, label: str, text: str) -> str:
```

- **Direct callers:** `VersionTracker` is instantiated as `self.vtrack = VersionTracker(cfg.version_dir)` in `MainScript.__init__` but `vtrack.snapshot_text()` is **never called** anywhere in the codebase.
- **In tests:** Tests mock out `VersionTracker` entirely; no test exercises `snapshot_text`.
- **Confidence:** HIGH
- **Recommendation:** LIKELY DEAD — the class instance is created but its only method is never invoked.

---

### 1.7 `AsyncProcessor` class — `Entelgia_production_meta.py` and `Entelgia_production_meta_200t.py` line ~4857 / ~4835

```python
class AsyncProcessor:
    def process_agents_concurrent(self, agents, seed, dialog_tail) -> Dict[str, str]:
```

- **Direct callers:** `AsyncProcessor()` is instantiated as `self.async_proc` in `MainScript.__init__` (line ~5207). The method `process_agents_concurrent` is **never called** anywhere. `self.async_proc` is never accessed after construction.
- **In tests:** Mocked out entirely; no test exercises `process_agents_concurrent`.
- **Confidence:** HIGH
- **Recommendation:** LIKELY DEAD — stub for concurrent agent processing. `MainScript.run()` processes agents sequentially. The async infrastructure is constructed but never activated.

---

### 1.8 `MemoryCore.ltm_search_affective()` — `Entelgia_production_meta.py` and `Entelgia_production_meta_200t.py` line ~3070 / ~3069

```python
def ltm_search_affective(
    self,
    agent: str,
    emotion_filter: Optional[str],
    ...
) -> List[Dict[str, Any]]:
```

- **Direct callers:** Zero in both production files and all tests.
- **In tests:** No test exercises this method.
- **Confidence:** HIGH
- **Recommendation:** LIKELY DEAD — emotion-filtered LTM retrieval is implemented but never called. `ltm_recent()` is used instead for memory retrieval in the `Agent.speak()` pipeline.

---

## Section 2 — MEDIUM CONFIDENCE: Manual Review Recommended

### 2.1 `scripts/draft.py` — Entire File

- **Status:** Explicitly labeled prototype ("Draft: Energy-Based Agent Regulation for Entelgia"). Defines `FixyRegulator` and `EntelgiaAgent` classes that closely duplicate content in `entelgia/energy_regulation.py`.
- **Imports:** This file is **never imported** anywhere in the codebase.
- **Code Duplication Risk:** Because `scripts/draft.py` and `entelgia/energy_regulation.py` define equivalent classes with no shared base, any logic change in production must be manually mirrored or the draft will diverge silently. This is a maintainability hazard regardless of whether the file is eventually integrated or discarded.
- **Confidence:** MEDIUM — intentionally kept as draft, but all code paths are dead.
- **Recommendation:** MANUAL REVIEW — either archive to a `/drafts` folder (or remove entirely) to eliminate the duplication risk, or formalize the integration it describes and remove the duplicate from production.

---

### 2.2 `_encode_turns()` — `entelgia/fixy_interactive.py` line ~304

```python
def _encode_turns(turns: List[Dict[str, str]]):
```

- **Direct callers:** Zero — never called from within `fixy_interactive.py` or any other file.
- **In tests:** `test_detect_repetition_semantic.py` patches `_get_semantic_model` but never calls `_encode_turns`.
- **Context:** `InteractiveFixy._detect_repetition()` computes per-turn keywords via inline Jaccard sets rather than this encoder.
- **Confidence:** MEDIUM
- **Recommendation:** MANUAL REVIEW — likely dead; was part of a refactored code path.

---

### 2.3 `import numpy as np` — `entelgia/circularity_guard.py` line ~56

```python
import numpy as np  # noqa: F401
```

- **Status:** Developer intentionally suppressed the lint warning (`# noqa: F401`). However, `np` is never referenced in `circularity_guard.py`. The file uses sentence-transformers via `_cosine_similarity` and `_ST_MODEL`.
- **Confidence:** MEDIUM — the `noqa` comment suggests this may be intentional (numpy type compatibility or future use).
- **Recommendation:** MANUAL REVIEW — ask whether this was kept for a specific reason.

---

### 2.4 `MemoryCore.stm_path()` — `Entelgia_production_meta.py` line ~2832

```python
def stm_path(self, agent_name: str) -> str:
```

- **Status:** Called internally by `stm_load()` and `stm_save()` — alive. However, it is a public method when private visibility (`_stm_path`) would be more appropriate.
- **Confidence:** MEDIUM — alive but unnecessarily public.
- **Recommendation:** KEEP — but consider renaming to `_stm_path` for clarity.

---

### 2.5 Embedded `test_*` functions — `Entelgia_production_meta.py` and `Entelgia_production_meta_200t.py` lines ~4947–5197

Ten `test_*` functions are embedded inside the production files:
`test_config_validation`, `test_lru_cache`, `test_redaction`, `test_validation`, `test_metrics_tracker`, `test_topic_manager`, `test_behavior_core`, `test_language_core`, `test_memory_signatures`, `test_session_manager`

- **Direct callers:** Only called from the `if __name__ == "__main__"` block. pytest also discovers them.
- **Context:** Intentional self-tests embedded in the production module. Listed in `scripts/validate_implementations.py` KEY_FUNCTIONS.
- **Confidence:** MEDIUM — intentional, but the pattern of embedding tests in production code is unusual.
- **Recommendation:** MANUAL REVIEW — consider migrating to the `tests/` directory for cleaner separation of concerns.

---

### 2.6 `export_gexf_placeholder()` — `Entelgia_production_meta.py` line ~4696

```python
def export_gexf_placeholder(path: str, nodes: ..., edges: ...):
```

- **Direct callers:** Called in `MainScript` conditionally when `gexf_path` is configured and a non-empty node/edge list is produced. The call site may rarely execute depending on config.
- **Confidence:** MEDIUM — the function IS reachable but may be exercised infrequently.
- **Recommendation:** KEEP — but add documentation clarifying when `gexf_path` triggers it.

---

### 2.7 `SeedGenerator._select_strategy()` — `entelgia/dialogue_engine.py` line ~174

```python
def _select_strategy(
    self, turn_count: int, conflict_level: float, last_emotion: str
) -> str:
```

- **Direct callers:** Called internally within `SeedGenerator.generate_seed()` at line ~152. Alive.
- **In tests:** Exercised indirectly via `generate_seed()` tests only.
- **Confidence:** LOW — alive; noted only because no independent test exists.
- **Recommendation:** KEEP

---

### 2.8 `DialogueEngine._detect_repeating_agent()` — `entelgia/dialogue_engine.py` line ~390

```python
def _detect_repeating_agent(self, dialog_history: List[Dict[str, str]]) -> Optional[str]:
```

- **Direct callers:** Called from `DialogueEngine.select_next_speaker()` at line ~384. Alive.
- **In tests:** No direct test; exercised only if `select_next_speaker()` reaches that branch.
- **Confidence:** LOW — alive but branches may be rarely hit.
- **Recommendation:** KEEP — worth adding a direct unit test.

---

### 2.9 `Agent._extract_topic_from_seed()` — `Entelgia_production_meta.py` line ~3681

```python
@staticmethod
def _extract_topic_from_seed(seed: str) -> str:
```

- **Direct callers:** Called in `Agent._build_compact_prompt()` (line ~3702) and `Agent._build_enhanced_prompt()` (line ~3832). Alive.
- **In tests:** No direct test.
- **Confidence:** LOW — alive; worth a dedicated unit test given its role in topic routing.
- **Recommendation:** KEEP

---

## Section 3 — Confirmed Alive (Indirect Use)

These symbols were investigated and confirmed alive through indirect use, optional code paths, or explicit test coverage:

| Symbol | File | Reason Alive |
|---|---|---|
| `_simulate_baseline`, `_simulate_fixy`, `_simulate_dream`, `_simulate_dialogue_engine` | `entelgia/ablation_study.py` | Used in dispatch table at lines ~324–327 |
| `_ascii_circularity_chart` | `entelgia/ablation_study.py` | Called by `plot_circularity()` at line ~447; tested in `test_ablation_study.py` |
| `_extract_contradiction` | `entelgia/loop_guard.py` | Called by `DialogueRewriter.build()` at line ~774 |
| `_get_semantic_model` | `circularity_guard.py`, `fixy_interactive.py` | Used internally; patched in tests |
| `_contains_any`, `_topic_relevance_score`, `_validate_topic_compliance` | `Entelgia_production_meta.py` | Called internally; tested in `test_topic_anchors.py` |
| `evaluate_superego_critique` | `Entelgia_production_meta.py` | Called in `Agent.speak()` at line ~4044; tested in `test_superego_critique.py` |
| `DialogueRewriter.build()` | `entelgia/loop_guard.py` | Called via `self._dialogue_rewriter.build()` in main loop |

---

## Section 4 — Unused Import Statements

### Confirmed Genuinely Unused

| File | Line | Import | Severity |
|---|---|---|---|
| `entelgia/fixy_interactive.py` | ~256 | `import numpy as _np` (inside try block) | HIGH — `_np` never referenced |
| `entelgia/circularity_guard.py` | ~56 | `import numpy as np  # noqa: F401` | MEDIUM — `np` never referenced; developer suppressed lint |

### Minor Typing Import Cleanup (Low Priority — Still Legitimate Cleanup)

These may reflect Python version compatibility choices, but unused imports can confuse developers reading the module about which types are actually in use, and they may trigger linter warnings in CI/CD pipelines. They should be cleaned up even if not urgently:

| File | Unused Import |
|---|---|
| `entelgia/dialogue_metrics.py` | `Tuple` (not used in annotations) |
| `entelgia/enhanced_personas.py` | `List` (not used in public API) |
| `entelgia/fixy_interactive.py` | `Any` (not used in annotations) |
| `entelgia/loop_guard.py` | `Any` (not used) |

### `from __future__ import annotations` — Present in ~10 Files

Present in: `fixy_research_trigger.py`, `source_evaluator.py`, `web_research.py`, `web_tool.py`, `topic_enforcer.py`, `long_term_memory.py`, `circularity_guard.py`, `ablation_study.py`, `energy_regulation.py`, `research_context_builder.py`.

- **Status:** Backwards-compatibility imports for Python 3.7–3.9 (PEP 563 postponed evaluation). If the project targets Python 3.10+ exclusively, these are unnecessary but harmless.
- **Recommendation:** KEEP unless Python 3.10+ is the guaranteed minimum.

---

## Section 5 — Constants Defined But Potentially Unused

### 5.1 `TOPIC_STYLE` — `entelgia/topic_style.py` line ~33

```python
TOPIC_STYLE: Dict[str, str] = { ... }
```

- **Status:** Used internally within `get_style_for_cluster()`. Exported via `__init__.py` but never imported directly in production files.
- **Recommendation:** KEEP — used indirectly. Consider removing from `__all__` if not intended as external public API.

### 5.2 `ACCEPT_THRESHOLD` / `SOFT_REANCHOR_THRESHOLD` — `entelgia/topic_enforcer.py` lines ~76–81

- **Status:** ALIVE. Imported in `Entelgia_production_meta.py` as `_TOPIC_ACCEPT_THRESHOLD` / `_TOPIC_SOFT_REANCHOR_THRESHOLD`; tested directly.
- **Recommendation:** KEEP.

---

## Section 6 — Unused Parameters

### 6.1 `_first_turn_after_topic_change` in `Agent.speak()`

- **Status:** Set and passed to `_cg_compute()`, but the parameter is only fully utilized when `ENTELGIA_ENHANCED` is True. When the enhanced package is unavailable, the fallback stub ignores it. Not truly dead — conditional path.
- **Recommendation:** KEEP — document the conditional behavior explicitly.

---

## Section 7 — Disconnected Helper Functions

### 7.1 `entelgia/context_manager.py` — module-level `__main__` demo block (line ~442+)

- **Status:** Standard `__main__` demo block. Runs only if the module is executed directly. Not dead — developer convenience tool.
- **Recommendation:** KEEP — consider adding `# pragma: no cover` to exclude from coverage reports.

### 7.2 `entelgia_research_demo.py` — `_separator()`, `_header()`, `_mock_agent_speak()` (lines ~51–91)

- **Status:** Used within `run_demo()`, which is called from `__main__`. Alive.
- **Recommendation:** KEEP.

---

## Section 8 — Complete File Assessment

| File | Status | Notes |
|---|---|---|
| `scripts/draft.py` | ⚠️ DEAD FILE | Never imported; explicitly a draft. Duplicates `entelgia/energy_regulation.py`. |
| `scripts/demo_energy_regulation.py` | ✅ Standalone script | `if __name__ == "__main__"` entry point |
| `scripts/demo_enhanced_dialogue.py` | ✅ Standalone script | Proper entry point |
| `scripts/generate_correlation_map.py` | ✅ Standalone script | Calls `entelgia.dialogue_metrics` |
| `scripts/research_statistics.py` | ✅ Standalone script | Own simulation functions, not imported elsewhere |
| `scripts/clear_memory.py` | ✅ Standalone utility | Menu-driven memory cleaner |
| `scripts/install.py` | ✅ Standalone installer | |
| `scripts/run_all_tests.py` | ✅ Test runner | |
| `scripts/validate_implementations.py` | ✅ Validation tool | |
| `scripts/validate_project.py` | ✅ Validation tool | |
| `entelgia_research_demo.py` | ✅ Demo script | `if __name__ == "__main__"` entry point |

---

## Prioritized Action Summary

### 🔴 High Priority — Remove (High Confidence, Safe Cleanup)

1. **`entelgia/fixy_interactive.py` line ~256** — Remove `import numpy as _np` (unused import inside try block; `_np` never referenced)

### 🟠 Medium Priority — Manual Review (Functional Dead Code)

2. **`Entelgia_production_meta.py` — `AsyncProcessor` class** — Instantiated in `MainScript.__init__` but `process_agents_concurrent()` is never called. Placeholder for future async.
3. **`Entelgia_production_meta.py` — `VersionTracker.snapshot_text()`** — `self.vtrack` is created but its method is never invoked anywhere.
4. **`Entelgia_production_meta.py` — `safe_apply_patch()`** — Never called at runtime; listed only in the implementation-existence validator.
5. **`Entelgia_production_meta.py` — `MemoryCore.ltm_search_affective()`** — Never called anywhere; `ltm_recent()` is used instead.
6. **`entelgia/fixy_interactive.py` — `InteractiveFixy.should_request_research()`** — Defined but never wired up to any call site.
7. **`entelgia/fixy_interactive.py` — `_encode_turns()`** — Defined but never called; appears to be an orphaned refactoring artifact.
8. **`entelgia/enhanced_personas.py` — `is_global_show_pronouns`** — Module-level flag exported but never read; superseded by `Config.show_pronoun`.
9. **`entelgia/enhanced_personas.py` — `get_typical_opening()`** — Exported as public API but never consumed.

### 🟡 Low Priority — Consider Archiving

10. **`scripts/draft.py`** — Entire file is a prototype, never imported, duplicates production module content.

### 🟢 Keep (Low Risk)

11. Embedded `test_*` functions in production meta — intentional self-test pattern; consider migrating to `tests/` directory.
12. `from __future__ import annotations` imports — harmless compatibility shims.
13. Minor unused `typing` imports (`Tuple`, `List`, `Any`) — legitimate cleanup items; low priority but worth addressing to reduce developer confusion and avoid CI lint warnings.
14. `import numpy as np  # noqa: F401` in `circularity_guard.py` — developer intentionally suppressed; verify before removing.

---

*This report is read-only. No code was changed, deleted, or patched during this audit.*

<div style="display: flex; align-items: center; justify-content: space-between;">
  <img src="Assets/entelgia-logo.png" alt="Entelgia Logo" width="120" style="margin: 0;"/>
  <h1 style="flex-grow: 1; text-align: center; font-size: 2.5em; font-weight: bold; margin: 0;">📋 Changelog</h1>
  <div style="width: 120px;" aria-hidden="true"></div>
</div>

All notable changes to this project will be documented in this file. The format is based on [Keep a Changelog](https://keepachangelog.com/) and this project adheres to [Semantic Versioning](https://semver.org/).

---

## [4.0.0] - 2026-03-20

### Added

- **DRAFT → FINAL two-stage generation pipeline** — `Agent.speak()` now implements a two-stage generation flow. Stage 1 calls the LLM normally and stores the result as `_last_raw_draft` (never shown to the user). Stage 2 calls `transform_draft_to_final()`, which makes a second LLM call to extract 1–2 core ideas from the draft and regenerate a completely new response — discarding original phrasing, sentence structure, and rhetorical connectors. Final output is 1–3 sentences maximum, with at least one short direct sentence, and without meta phrases (`"my model"`, `"this suggests"`, `"it is important"`, etc.). Agent identity (Socrates / Athena / Fixy) is preserved. Stage 2 is skipped when a topic-safe fallback template is injected.
- **`transform_draft_to_final(draft_text, agent_name, llm, model, topic, temperature)`** — new module-level function implementing Stage 2. Uses per-agent persona notes (`_FINAL_STAGE_PERSONA_NOTES`) to maintain agent identity in the transformation prompt. Falls back to `draft_text` on LLM error or empty response.
- **`_FINAL_STAGE_PERSONA_NOTES`** — new module-level dict mapping `"Socrates"`, `"Athena"`, and `"Fixy"` to per-agent identity instructions used in the Stage 2 transformation prompt. Updated in the DRAFT → REWRITE refactor: Fixy uses diagnostic labels, Socrates prefers tension/reframing, Athena grounds at least one part in mechanism/scenario/tradeoff.
- **`_skip_draft_transform` flag in `speak()`** — local variable set to `True` when a topic-safe fallback template is injected (hard recovery failure). When `True`, Stage 2 transform is skipped to preserve the carefully crafted fallback text.
- **Behavior-driven generation policy** — new module-level constants injected at generation time: `LLM_OUTPUT_CONTRACT` (one concrete claim + one supporting reason/mechanism, max 2–3 sentences, no visible labels), `LLM_BEHAVIORAL_CONTRACT_SOCRATES`, `LLM_BEHAVIORAL_CONTRACT_ATHENA`, and `LLM_BEHAVIORAL_CONTRACT_FIXY`. Per-agent behavioral contracts define output logic and allowed moves, not tone labels. Contracts later replaced with flexible role-goal + allowed-variation lists (see PR #284).
- **`BANNED_RHETORICAL_TEMPLATES`** — module-level list of banned rhetorical scaffolding phrases (`"we must consider"`, `"it is important to recognize"`, etc.) used to build both the forbidden-phrase instruction and the quality gate. Extended with `"one implicit assumption"`, `"the mechanism at play"`, `"this notion overlooks"`, `"the implicit assumption"`, `"identify the assumption"`, `"explain the mechanism"`, `"my model posits"`, `"this model reveals"`, `"my model reveals"`, `"overlooks a critical"`, `"overlooks a constraint"` and further with `"this demonstrates"`, `"this can be achieved by"`.
- **Output quality gate** — `output_passes_quality_gate(text)` returns `False` when ≥ 2 `_QUALITY_GATE_PATTERNS` hits are found in a draft. When the gate fails, quality-gate result is logged (`[QUALITY-GATE] will refine in Stage 2 REWRITE`) and Stage 2 REWRITE applies a focused refinement pass.
- **`_strip_scaffold_labels(text)`** — post-processing function applied at the end of `speak()` after all other transformations. Strips numbered scaffold labels (e.g. `"1. Claim:"`, `"2. Supporting reason:"`, `"Implication:"`) that LLMs occasionally leak into their output, ensuring responses read as natural prose.
- **Fixy role-aware compliance** — `compute_fixy_compliance_score()` in `entelgia/topic_enforcer.py` scores Fixy's output against topic/concept requirements using a stricter rule set: must name the current topic or a core concept, penalises new-domain drift. Controlled by `Config` fields `fixy_role_aware_compliance` (default `True`), `fixy_must_name_topic_or_core_concept` (default `True`), and `fixy_new_domain_penalty` (default `0.20`).
- **Cluster wallpaper penalty** — `get_cluster_wallpaper_terms(cluster)` and `get_topic_distinct_lexicon(topic)` added to `entelgia/topic_enforcer.py`. When `cluster_wallpaper_penalty_enabled` is `True`, topic-generic cluster words that repeat within a `cluster_wallpaper_repeat_window` (default 6) turn window are penalised, encouraging use of topic-distinct vocabulary. Controlled by `Config` fields `topic_specific_lexicon_bias_enabled` (default `True`), `cluster_wallpaper_penalty_enabled` (default `True`), `cluster_wallpaper_repeat_window` (default `6`).
- **Memory topic filter** — `Agent._score_memory_topic_relevance()` scores retrieved LTM entries against the current topic using cluster match, topic keyword overlap, and recent-dialogue overlap, minus a contamination penalty for off-topic content. Memories below `memory_topic_min_score` (default `0.45`) are filtered out. Controlled by `Config` fields `memory_topic_filter_enabled` (default `True`), `memory_topic_min_score` (default `0.45`), `memory_require_same_cluster` (default `True`), `memory_contamination_penalty` (default `0.25`).
- **Topic anchor pre-generation gate** — topic anchor injection and forbidden-carryover logic in `_build_compact_prompt` made fully configurable: `topic_anchor_enabled` (default `True`), `topic_anchor_include_forbidden_carryover` (default `True`), `topic_anchor_max_forbidden_items` (default `5`). Debug output controlled by `show_topic_anchor_debug` (default `False`).
- **Self-replication topic gate** — `SelfReplication` pattern matching gated by topic-relevance scoring. New `Config` fields: `self_replication_topic_gate_enabled` (default `True`), `self_replication_topic_min_score` (default `0.50`), `self_replication_require_same_cluster` (default `True`).
- **Web trigger multi-signal gate** — `fixy_research_trigger.py` adds `_count_strong_trigger_hits(text)` and `_has_uncertainty_or_evidence_signal(text)`. When `web_trigger_require_multi_signal` is `True`, a search is only triggered when ≥ `web_trigger_min_concepts` (default `2`) strong concept hits AND either an uncertainty or evidence signal are present. Controlled by `Config` fields `web_trigger_require_multi_signal` (default `True`), `web_trigger_min_concepts` (default `2`), `web_trigger_require_uncertainty_or_evidence` (default `True`). Debug output controlled by `show_web_trigger_debug` (default `False`).
- **Forbidden phrase list expanded** — `LLM_FORBIDDEN_PHRASES_INSTRUCTION` now also bans `'it is important'`, `"let's consider"`, and `'given the topic'` — common LLM scaffolding phrases that were not caught by the previous list.
- **High-value web trigger keywords** — `_HIGH_VALUE_KEYWORDS` set in `fixy_research_trigger.py` for terms like `"studies"`, `"research"`, `"data"` that qualify as strong trigger concepts regardless of rhetorical-framing filtering.
- **Rule LH — Athena Limbic Hijack Anger Behaviour** — new behavioral rule in `_behavioral_rule_instruction()`. When Athena is in an active limbic hijack state (`self.limbic_hijack == True`), the injected instruction forces raw anger and harsh language, replacing the generic conflict dissent rule. This rule takes priority over the standard conflict-triggered Rule B so that the emotional override state is always reflected in Athena's output.
- **Rule SC — Socrates SuperEgo Dominant Anxiety Behaviour** — new behavioral rule in `_behavioral_rule_instruction()`. When Socrates' `superego_strength` leads both `ego_strength` and `id_strength` by at least 0.5 points, the injected instruction forces hesitant, anxious language that reflects the agent's internal tension and apprehension. Rule SC takes priority over the random-gated Rule A.
- **Socrates anxiety emotion during SuperEgo critique** — when `evaluate_superego_critique()` fires for Socrates, `_last_emotion` is set to `"fear"` and `_last_emotion_intensity` is elevated, ensuring emotional state reflects the anxiety introduced by the SuperEgo's internal governor. Non-Socrates agents are unaffected.
- **Athena anger emotion during limbic hijack** — when Athena's limbic hijack is active, `_last_emotion` is set to `"anger"`, keeping the emotional state consistent with the raw-anger behavioral rule (Rule LH).
- **Limbic hijack at extreme Id** — activation intensity threshold is dynamically lowered from `0.7` to `0.5` when `id_strength >= 8.5`, reflecting the heightened impulsive-override risk at extreme drive levels. This makes it easier to enter hijack when Id is already at an extreme.
- **SuperEgo critique at extreme SuperEgo** — when Socrates' `superego_strength >= 8.5`, `evaluate_superego_critique()` is called with tightened thresholds: `dominance_margin=0.2` (down from `0.5`) and `conflict_min=1.0` (down from `2.0`), and the limbic hijack suppression of `effective_sup` is bypassed. This lets an extreme SuperEgo assert itself as a counterforce even against a mild limbic hijack.
- **Biased drive reversion with extreme boost** — drive mean-reversion now uses per-agent preferred targets: Athena's `id_strength` drifts toward `6.5`; Socrates' `superego_strength` drifts toward `6.5`. When either drive reaches an extreme (`>= 8.5` or `<= 1.5`), an extra reversion boost of `0.06` is applied, preventing indefinite stagnation at extreme values. Elevated bias is paid from `ego_strength`, which drains proportionally when the biased drive is above `5.0`.
- **Rule AI-tension — Athena graduated irritation + impulsivity (id 7.0–8.5)** — new fallback behavioral rule. When Athena's `id_strength` is in `[7.0, 8.5)` and no higher-priority rule (LH, B) applies, a graduated irritation + impulsivity instruction is injected. The phrasing escalates from *"subtle undercurrent of irritation"* (id near 7.0) through *"growing frustration"* (mid range) to *"clear irritation and barely-contained anger"* (id near 8.5), and always includes an impulsive-instinct directive. This rule fires only when limbic hijack is inactive and conflict-based Rule B does not trigger.
- **Rule AI-curioso — Athena explorative curiosity (id < 7.0)** — new fallback behavioral rule. When Athena's `id_strength` is below `7.0` and no higher-priority rule applies, an explorative/wonder-driven instruction is injected, directing Athena to be genuinely inquisitive, ask probing conceptual questions, and embrace unexpected ideas. Higher id within this range naturally produces more energised curiosity through the drive dynamics.
- **Rule SI-anxious — Socrates stubbornness and inner unease (id 7.0–8.5)** — new fallback behavioral rule. When Socrates' `id_strength` is in `[7.0, 8.5)` and no higher-priority rule (SC, A) applies, an instruction is injected that directs Socrates to hold positions more firmly, show guarded anxiety, and resist yielding ground.
- **Rule SI-skeptic — Socrates principled skepticism (id < 7.0)** — new fallback behavioral rule. When Socrates' `id_strength` is below `7.0` and no higher-priority rule applies, an instruction is injected framing the Id energy as a *constructive inner governor*: question assumptions, challenge accepted ideas, and express principled disagreement as a positive force that refines thought through scrutiny.
- **Rule ID-low — both agents low motivation (id < 5.0)** — new behavioral rule inserted before the agent-specific id fallbacks. When either agent's `id_strength` is strictly below `5.0`, a low-motivation/passive instruction is injected for both Athena and Socrates: be more reserved, avoid pushing into new territory, and reflect reduced drive. This overrides the agent-specific curious/skeptic fallbacks when id is truly suppressed.
- **Rule SE-low — both agents impulsive/risk-taking (superego < 5.0)** — new behavioral rule inserted after Rule ID-low. When either agent's `superego_strength` is strictly below `5.0` and id >= 5.0 (ID-low did not fire), a reduced-inhibition/impulsive instruction is injected for both Athena and Socrates: take bolder risks, follow impulses without excessive qualification, and speak with less caution and more daring.
- **Anti-repetition form tracker** — `classify_response_form(text) -> str` classifies each agent output as one of: `question | challenge | synthesis | critique | contrast | directive | example | definition | statement`. Each agent carries `_last_response_forms: deque(maxlen=3)`; when the same form appears ≥ 2 consecutive turns, a `FORM PREFERENCE: Consider using <alternative>` soft instruction is injected into the Stage 2 REWRITE prompt. The `[FORM]` diagnostic log is emitted at `DEBUG` level (not `INFO`).
- **Template family gate** — `_TEMPLATE_FAMILIES` dict and `_detect_template_family()` detect opener families: `challenge_openers`, `balanced_synthesis_openers`, `mediation_openers`, `abstract_generalization_openers`. When a family repeats ≥ 2 turns, forced regeneration uses an explicit family-ban prompt.
- **Abstract noun penalty** — `_check_abstraction_penalty()` uses `\b`-bounded regex to count abstract nouns (`freedom`, `truth`, `identity`, etc.); ≥ 3 hits without any mechanism indicator logs `[ABSTRACTION-PENALTY] accepted` and Stage 2 REWRITE applies concreteness pressure.
- **Rotating variation modes per agent** — 5 named modes per agent injected as pre-generation soft instructions, rotating every 2 turns: Socrates (`skeptical | diagnostic | confrontational | austere | example-driven`), Athena (`analytical | incisive | model-building | contrastive | compressive`), Fixy (`mediator | debugger | deadlock-breaker | reframer | structural observer`).
- **Grok (xAI) LLM backend** — `Config` gains three new fields: `llm_backend: str` (default `"ollama"`), `grok_url: str` (default `"https://api.x.ai/v1/responses"`), `grok_api_key: str` (from `GROK_API_KEY` env var). `__post_init__` validates: unknown backend raises `ValueError`; `"grok"` backend without `GROK_API_KEY` raises `ValueError`. `LLM.generate()` branches on `llm_backend`: Ollama uses existing `POST /api/generate`; Grok uses `POST /v1/responses` with `Authorization: Bearer` header, `input` field payload, and `output[].content[].text` response extraction.
- **Interactive startup LLM backend/model selector** — `select_llm_backend_and_models(cfg)` presents a numbered menu at startup to choose the backend (Grok / Ollama / defaults) and then per-agent or uniform model overrides. Overrides are applied to the `cfg` object at runtime only — `.env` and disk config are never modified. `_pick_from_list(prompt_header, options)` is a reusable numbered-list picker; `_print_llm_config_summary(cfg)` prints the `[LLM CONFIG]` block on every path including defaults. `run_cli()` calls `select_llm_backend_and_models(CFG)` immediately after `Config` initialisation.
- **`GROK_MODELS` / `OLLAMA_MODELS` module-level constants** — centralised lists driving the interactive model-selection menu. Current Grok models: `grok-4.20-multi-agent`, `grok-4-1-fast-reasoning`. Ollama defaults: `qwen2.5:7b`, `llama3.1:8b`, `mistral:latest`.
- **Startup config display** — `_SENSITIVE_KEYS = {"grok_api_key", "memory_secret_key"}` masks those fields with `"***"` in the JSON config printout at startup, preventing private keys from appearing in logs or terminals.
- **Ctrl+C interrupt within ~0.5 s** — `LLM` now holds a `ThreadPoolExecutor(max_workers=1)`. `generate()` submits `requests.post()` to the executor and polls `future.result(timeout=0.5)` in a loop, checking `_shutdown_event` between polls. `MainScript.run()` installs a SIGINT handler that sets `_shutdown_event` and restores the previous handler (second Ctrl+C exits immediately). Retry sleeps use `_shutdown_event.wait(timeout=...)` so they wake immediately on shutdown. New module-level additions: `import signal`, `import threading`, `import concurrent.futures`, `_shutdown_event = threading.Event()`.
- **Observability logs for DRAFT / REWRITE pipeline** — `[DRAFT] agent=...` logged before Stage 2, `[REWRITE] agent=...` logged after Stage 2, `[STYLE-REDUNDANCY] agent=... similarity=...` emitted when Jaccard word-overlap vs the last response exceeds `0.75`.
- **`☁️ Using the Grok Backend (xAI)` section in README.md** — covers API key acquisition, `.env` configuration, runtime backend/model selection at startup, and a model reference table for available Grok models.

### Changed

- **`Config.web_research_enabled` default changed to `False`** — web research is now OFF by default. Set env var `ENTELGIA_WEB_RESEARCH=1` or `Config(web_research_enabled=True)` to enable.
- **`LLM_OUTPUT_CONTRACT` tightened** — response limit reduced from "3–4 sentences" to "2–3 sentences"; added "no visible section labels or numbers" requirement.
- **Emotion inference moved to end of `speak()`** — `emotion.infer()` is now called after LLM generation and all post-processing steps rather than before. This eliminates a redundant LLM call that was stalling `speak()` when web research was disabled (the previous code path triggered inference twice in that scenario).
- **SuperEgo consecutive streak limit** — a new `_consecutive_superego_rewrites` counter on `Agent` prevents stylistic lock-in caused by uninterrupted SuperEgo critique rewrites. After `MAX_CONSECUTIVE_SUPEREGO_REWRITES` (2) consecutive rewrite turns, the critique is suppressed and `_superego_streak_suppressed` flag is set to `True`; the counter resets on any turn where the critique does not fire. `print_meta_state()` surfaces the streak-suppressed state in meta output.
- **Socrates behavioral contract** — mandatory three-step formula (attack assumption → objection → question) replaced with "Choose ONE move: blunt challenge, sharp question, or direct claim — do not blend all three". Length is now dynamic (1–4 sentences) instead of hard-capped at 3–4.
- **Athena behavioral contract** — mandatory "Construct ONE clear model… State the design tradeoff" replaced with "State ONE clear distinction, tension, or observation — start directly with the idea, do NOT announce you have a model". Typical openings changed from `"Let me construct a model that accounts for..."` to `"That premise breaks down once you consider..."` / `"The distinction that matters here is..."`.
- **Fixy behavioral contract and `_MODE_PROMPTS`** — all 13 `_MODE_PROMPTS` in `entelgia/fixy_interactive.py` rewritten: replaced `"Your job:"` / `"In 2-3 sentences: 1. … 2. … 3. …"` with direct failure-mode declarations and inline diagnostic label examples (e.g. `"Deadlock: X vs Y. Missing variable: a committed position. Next move: choose one."`). `LLM_BEHAVIORAL_CONTRACT_FIXY` and `_AGENT_BEHAVIORAL_CONTRACTS["Fixy"]` updated to list three permitted labels only.
- **Role-goal contracts replace output-shape contracts** — rigid per-agent output-shape contracts replaced with role goals + allowed-variation lists in both main scripts and `entelgia/context_manager.py`. Form instructions changed from hard `FORM RULE: MUST use ...` to soft `FORM PREFERENCE: Consider using ...`.
- **DRAFT prompt soft constraints** — `LLM_OUTPUT_CONTRACT`, `LLM_FORBIDDEN_PHRASES_INSTRUCTION`, and `_AGENT_BEHAVIORAL_CONTRACTS` removed from the Stage 1 DRAFT prompt; a single soft guidance line added: *"Focus on producing a coherent, meaningful thought. Slight roughness is fine."* Hard constraints remain in Stage 2 REWRITE only.
- **`Config.forgetting_enabled` default changed to `False`** — LTM forgetting (TTL expiry) is now OFF by default. Memory is retained indefinitely unless explicitly opted in via `config.forgetting_enabled = True`.
- **Default model changed from `phi3:latest` to `qwen2.5:7b`** — `Config.model_socrates`, `Config.model_athena`, and `Config.model_fixy` now default to `qwen2.5:7b`. `phi3` (3.8B) does not reliably sustain the architecture's reflective, memory-heavy, multi-layer reasoning demands; `qwen2.5:7b` is the new recommended minimum. `.env.example` updated accordingly.
- **`[AFFECTIVE-LTM]` log demoted from INFO to DEBUG** — the per-turn affective LTM retrieval stats log is now only visible when the `DEBUG` log level is active, reducing noise in normal output.
- **`[FORM]` log demoted from INFO to DEBUG** — the per-turn form classification diagnostic log `[FORM] agent=X form=Y recent=[...]` is now at `DEBUG` level, consistent with the companion `[FORM] ... injecting form preference` log.
- **`grok_api_key` stays env-driven; `llm_backend` and `grok_url` are Config defaults** — after the env-cleanup pass, `LLM_BACKEND`, `GROK_URL`, `MODEL_SOCRATES`, `MODEL_ATHENA`, and `MODEL_FIXY` are no longer read from the environment. `Config` is the single source of truth for those values; only `GROK_API_KEY` (a secret) remains env-driven.
- **`.env.example` simplified** — `LLM_BACKEND`, `GROK_URL`, `OLLAMA_URL`, `MODEL_SOCRATES`, `MODEL_ATHENA`, `MODEL_FIXY`, `TIMEOUT_MINUTES`, and `CACHE_SIZE` removed; only `MEMORY_SECRET_KEY` and `GROK_API_KEY` remain. Comments clarify that backend and model selection happen interactively at startup.
- **`scripts/install.py` updated** — `configure_grok_api_key()` and `update_grok_api_key_in_env()` added; collects `GROK_API_KEY` securely via `getpass` and writes only that key to `.env`. Model list in the installer updated to `grok-4.20-multi-agent` / `grok-4-1-fast-reasoning` to match `GROK_MODELS`. Removed `select_llm_backend()` / `update_env_backend()` (they wrote `LLM_BACKEND` which `Config` no longer reads). `print_next_steps()` now states that backend/model selection happens interactively at startup.
- **xAI Grok endpoint corrected to `/v1/responses`** — default `GROK_URL` changed from `/v1/chat/completions` to `https://api.x.ai/v1/responses`; request body changed from `messages` to `input` field; response parsing changed from `choices[0].message.content` to walking `output[i].content[j]` for the first `output_text` block.

### Removed

- **`TextHumanizer` post-processing pipeline** — removed entirely from both production scripts and all supporting files. `entelgia/humanizer.py` is preserved as a module but is no longer imported or invoked. Removed from `Config`: all `humanizer_*` and `show_humanizer_debug` fields. Removed globals: `HUMANIZER`, `should_humanize()`, `_build_humanizer_instance()`. The `TextHumanizer` post-processing block is removed from `Agent.speak()`.
- **`humanizer.py` from tests and docs** — `test_text_humanizer_integration.py` replaced with an empty placeholder; `TestHumanizerGrammarRepair` removed from `test_stabilization_pass.py`; `TestGrammarRepairSafety` removed from `test_generation_quality.py`. Grammar Repair section removed from `ARCHITECTURE.md`; `humanizer_grammar_repair_enabled` / `humanizer_repair_broken_openings` entries removed from `SPEC.md`.

### Fixed

- **Ctrl+C now interrupts within ~0.5 s** — previously `requests.post()` blocked in C-level socket I/O for up to 300 s, swallowing `KeyboardInterrupt` due to Python's PEP 475 EINTR retry. Now uses `ThreadPoolExecutor` + 0.5-second polling loop so interrupts are acted upon within half a second.
- **xAI Grok 422 errors** — Grok backend was sending a chat-completions-style body to the `/v1/responses` endpoint (incompatible schema). Fixed by switching to the correct `input` field and response path.
- **`grok_api_key` plaintext in startup logs** — `asdict(CFG)` → `json.dumps` printed the private API key to the console. Fixed with `_SENSITIVE_KEYS` masking (`"***"`) applied before display.
- **Stale Grok model list in installer** — `scripts/install.py` advertised grok-3 series models that no longer match the runtime `GROK_MODELS` list. Updated to `grok-4.20-multi-agent` / `grok-4-1-fast-reasoning`.

### Tests

- **`tests/test_transform_draft_to_final.py`** — new suite with **28 tests** covering `transform_draft_to_final()`: short/empty passthrough, normal LLM call, fallback on empty/None/exception, persona notes for all agents, prompt contract requirements (max 3 sentences, forbidden phrases, no preamble, natural prose), and integration tests verifying that `Agent.speak()` calls Stage 2 and uses its output.
- **`tests/test_affective_ltm_integration.py`** — suite with **24 tests** covering affective LTM retrieval integration: debug toggle, min-score threshold, supplement injection into prompt context, empty supplement when disabled, per-agent emotion weighting. Tests updated to `caplog.at_level(logging.DEBUG)` to match the demoted `[AFFECTIVE-LTM]` log level.
- **`tests/test_generation_quality.py`** — suite with **68 tests** (down from initial 75 after humanizer-related `TestGrammarRepairSafety` class was removed) covering `output_passes_quality_gate`, `_strip_scaffold_labels`, `LLM_OUTPUT_CONTRACT` phrase cleanliness, `LLM_FORBIDDEN_PHRASES_INSTRUCTION`, per-agent behavioral contracts, and output contract prose requirements.
- **`tests/test_stabilization_pass.py`** — suite with **50 tests** (down from initial 55 after `TestHumanizerGrammarRepair` was removed) covering memory topic filter, cluster wallpaper penalty, Fixy role-aware compliance, web trigger multi-signal gate, topic anchor configurable fields, self-replication topic gate, and debug flag forwarding.
- **`tests/test_topic_enforcer.py`** — suite with **41 tests** covering `compute_topic_compliance_score`, `compute_fixy_compliance_score`, `get_cluster_wallpaper_terms`, `get_topic_distinct_lexicon`, `build_soft_reanchor_instruction`, `ACCEPT_THRESHOLD`, and `SOFT_REANCHOR_THRESHOLD`.
- **`tests/test_web_research.py`** — **202 tests** covering `_count_strong_trigger_hits`, `_has_uncertainty_or_evidence_signal`, multi-signal gate gating logic, `_HIGH_VALUE_KEYWORDS` qualification, and rhetorical framing word exclusion from concept scoring.
- **`tests/test_web_tool.py`** — **26 tests** covering retry-on-transient-error, response text extraction, and additional blacklist edge cases.
- **`tests/test_topic_anchors.py`** — **60 tests** including test for configurable `topic_anchor_max_forbidden_items`.
- **`tests/test_behavioral_rules.py`** — **71 tests** covering all behavioral rules including Rule LH, SC, AI-tension, AI-curioso, SI-anxious, SI-skeptic, ID-low, and SE-low.
- **`tests/test_superego_critique.py`** — **28 tests** covering consecutive streak limit, extreme-SuperEgo tightened thresholds, and Socrates anxiety emotion during critique.
- **`tests/test_limbic_hijack.py`** — **20 tests** covering extreme-Id threshold lowering and Athena anger emotion during hijack.
- **`tests/test_drive_correlations.py`** — **28 tests** covering biased drive reversion with extreme boost.
- **`tests/test_ablation_study.py`** — **28 tests**.
- **`tests/test_text_humanizer_integration.py`** — replaced with an empty placeholder (humanizer feature removed).
- **Total test count**: **1127 tests** (1127 collected) across **30 suites**.

---

## [3.0.0] - 2026-03-12

### Added

- **Topic-Aware Style Selection** — agents no longer default to abstract philosophical language. A new `entelgia/topic_style.py` module maps seed topic clusters to preferred reasoning styles (`TOPIC_STYLE` dict). At session start, `MainScript.run()` calls `get_style_for_topic()` to determine the cluster and style, then calls `build_style_instruction()` to build a per-role style instruction (Socrates: investigative/domain-aware, Athena: synthesis/structured, Fixy: diagnostic/corrective) and sets it on each agent via `agent.topic_style`. The instruction is injected into every prompt (both legacy compact and enhanced ContextManager paths) as a `STYLE INSTRUCTION:` block. Session start logs: `INFO - entelgia - Topic style selected: <style> (<cluster>)`.
- **`entelgia/topic_style.py`** — new module exporting `TOPIC_STYLE`, `get_style_for_cluster()`, `get_style_for_topic()`, and `build_style_instruction()`. Covers all seven production topic clusters (technology, economics, biology, psychology, society, practical_dilemmas, philosophy) plus loop-guard clusters (ethics_social, practical, identity, biological). Exported from `entelgia/__init__.py`.
- **`ContextManager.build_enriched_context` and `_format_prompt`** — new optional `topic_style: str` parameter. When non-empty, a `STYLE INSTRUCTION:` block is appended to the enriched prompt before the response-limit instructions.
- **`Agent.topic_style`** — new instance attribute (default `""`). When set by `MainScript.run()`, both `_build_compact_prompt` and `_build_enhanced_prompt` inject the style instruction into the generated prompt.

### Changed

- **Agent persona strings updated** — `Socrates`, `Athena`, and `Fixy` fallback persona strings (used in legacy / non-enhanced mode) now describe domain-adaptive reasoning rather than a fixed philosophical stance.
- **`enhanced_personas.py` Socrates `speech_patterns`** — removed `"Speaks with philosophical terminology"`, replaced with `"Adapts vocabulary to the topic domain"`. Description updated from `"I speak with philosophical depth"` to `"adapting my reasoning style to the topic domain"`.
- **`enhanced_personas.py` Athena description** — updated from `"I speak with creative insight"` to `"I adapt my reasoning to the topic domain"`.
- **Black formatting pass** applied to `entelgia/topic_style.py`, `entelgia/enhanced_personas.py`, `entelgia/context_manager.py`, `Entelgia_production_meta.py`, and `Entelgia_production_meta_200t.py`.

- **Forgetting Policy** — per-layer TTL expiry for Long-Term Memory. New `Config` fields: `forgetting_enabled` (default `True`), `forgetting_episodic_ttl` (7 days), `forgetting_semantic_ttl` (90 days), `forgetting_autobio_ttl` (365 days). `MemoryCore.ltm_apply_forgetting_policy()` deletes expired rows; called automatically at the end of every `dream_cycle()`. `MemoryCore._compute_expires_at(layer, ts)` stamps each inserted row with its expiry timestamp. New `expires_at` column added to `memories` table with `idx_mem_expires` index; existing databases auto-migrated via `ALTER TABLE`.
- **Affective Routing** — emotion-weighted LTM retrieval. New `Config` field: `affective_emotion_weight` (default `0.4`). `MemoryCore.ltm_search_affective(agent, limit, emotion_weight, layer)` ranks memories by `importance × (1 − w) + emotion_intensity × w`, surfacing emotionally salient memories ahead of merely important ones.
- **Confidence Metadata** — provenance tracking for every LTM row. `MemoryCore.ltm_insert()` gains two new optional keyword arguments: `confidence: float` (0–1) and `provenance: str` (e.g. `"dream_reflection"`, `"dream_promotion"`, `"user_input"`). Two new nullable columns added to `memories` table (`confidence REAL`, `provenance TEXT`); existing HMAC-SHA256 signatures unchanged (new fields excluded from signed payload for backward compatibility). Databases auto-migrated via `ALTER TABLE`. `dream_cycle()` now tags its insertions with `provenance="dream_reflection"` and `provenance="dream_promotion"` respectively.
- **Failed-URL blacklist in `web_tool.py`** — `fetch_page_text` now maintains a module-level `_failed_urls` set. Any URL that returns an HTTP 403 or 404 is added to the blacklist and skipped on all subsequent fetch attempts within the same process, eliminating redundant network requests. A `clear_failed_urls()` helper resets the set (used by test fixtures).
- **Per-query cooldown in `fixy_research_trigger.py`** — `fixy_should_search` now tracks each unique `seed_text` value in a new `_recent_queries` dict alongside the existing per-trigger `_recent_triggers` dict. If the exact same query fires within `_COOLDOWN_TURNS` turns, the search is suppressed immediately before any trigger keyword evaluation. `clear_trigger_cooldown()` also clears `_recent_queries`.
- **Fixy intervention prompt tightened to 1–2 sentences** — all intervention prompt templates in `fixy_interactive.py` now include `"Respond in 1-2 sentences only. Be direct and concrete."` replacing the previous looser `"Respond in maximum 2 sentences."` instruction.

- **`enable_observer` flag** — new `Config` boolean field (default `True`). When set to `False`, Fixy is completely excluded from the dialogue: no speaker turns, no need-based interventions, and no `InteractiveFixy` instance is created. Socrates and Athena are unaffected. Available as env var `ENTELGIA_ENABLE_OBSERVER`. (PR #207)
- **Semantic similarity in Fixy repetition detection** — `_detect_repetition` in `InteractiveFixy` now combines Jaccard keyword overlap with sentence-embedding cosine similarity (via `sentence-transformers` / `all-MiniLM-L6-v2`) when the library is available. The two scores are merged into a single repetition signal, catching paraphrased repetition that pure keyword overlap misses. Gracefully degrades to Jaccard-only when `sentence_transformers` is not installed (`_SEMANTIC_AVAILABLE = False`). Model is lazily loaded and cached on first use. (PR #208)
- **FreudianSlip rate-limiting**: Added `slip_cooldown_turns` (default 10) — a minimum number of turns that must elapse between two successful slips. Prevents burst sequences of `[SLIP]` output. (PR #205)
- **FreudianSlip deduplication**: Added `slip_dedup_window` (default 10) — remembers the last N slipped content hashes and suppresses identical (normalised) repeats within the window. (PR #205)
- **FreudianSlip instrumentation**: `FreudianSlip` now exposes `attempts` and `successes` integer counters. Both values are logged per-agent at session end: `FreudianSlip stats [<name>]: attempts=N, successes=M`. (PR #205)
- **Configurable slip controls**: `slip_probability`, `slip_cooldown_turns`, and `slip_dedup_window` are all available as `Config` fields and as environment variables (`ENTELGIA_SLIP_PROBABILITY`, `ENTELGIA_SLIP_COOLDOWN`, `ENTELGIA_SLIP_DEDUP_WINDOW`). (PR #205)

- **FreudianSlip default probability** lowered from `0.15` to `0.05` to reduce `[SLIP]` output frequency during normal runs. (PR #205)
- `Agent.apply_freudian_slip` now reuses a single persistent `FreudianSlip` engine instance (`self._slip_engine`) instead of constructing a new one per turn. This is required for cooldown and dedup state to be maintained across turns. (PR #205)
- **Black formatting pass** applied to `Entelgia_production_meta.py`, `Entelgia_production_meta_200t.py`, and `tests/test_long_term_memory.py` — pure style changes, no logic modified. (PR #206)

### Fixed

- **Dependency synchronisation** — `requirements.txt` and `pyproject.toml` are now in sync with actual code imports: (PR #209)
  - Added `numpy>=1.24.0` (hard-imported by tests and optionally by `fixy_interactive.py`)
  - Added `pytest-cov`, `black`, `flake8`, `mypy` to `requirements.txt` (already in `pyproject.toml` dev extras)
  - Removed `python-dateutil` from `requirements.txt` (appeared only in a docstring, never imported)
  - Added `beautifulsoup4>=4.12.0` to `pyproject.toml` core dependencies

### Tests

- **New `tests/test_context_manager.py`** (30 tests) — dedicated test suite for `entelgia/context_manager.py`. Covers `_safe_ltm_content`, `_safe_stm_text`, `ContextManager.build_enriched_context` (seed, persona, LTM/STM injection, internal-field suppression, `web_context` and `topic_style` injection), `_prioritize_memories`, and `EnhancedMemoryIntegration.retrieve_relevant_memories`.
- **New `tests/test_ablation_study.py`** (27 tests) — dedicated test suite for `entelgia/ablation_study.py`. Covers `AblationCondition` enum, `run_condition` (all four conditions, turn count, determinism), `run_ablation` (all conditions, metrics structure, numeric values, determinism), and `print_results_table` (no exception, non-empty output).
- **New `tests/test_web_tool.py`** (18 tests) — dedicated test suite for `entelgia/web_tool.py`. Covers `clear_failed_urls`, `_clean_text`, `fetch_page_text` (blacklist skip, 403/404 blacklisting, network error handling, text-limit truncation), `web_search` (network error, max_results), and `search_and_fetch` (result structure, source keys).
- **Black formatting pass** applied to `tests/test_revise_draft.py`, `tests/test_topic_anchors.py`, `tests/test_context_manager.py`, `tests/test_ablation_study.py`, `tests/test_web_tool.py`, `Entelgia_production_meta.py`, and `Entelgia_production_meta_200t.py` — pure style changes, no logic modified.
- **`tests/README.md` updated** — test count corrected to **721 tests** (720 passed, 1 skipped) across 23 suites. Added sections for `test_context_manager.py`, `test_ablation_study.py`, `test_web_tool.py`, `test_topic_style.py`, `test_topic_anchors.py`, `test_seed_topic_clusters.py`, and `test_revise_draft.py`. Updated test counts for `test_loop_guard.py` (30), `test_detect_repetition_semantic.py` (13), and `test_web_research.py` (181). Added a "Running All Tests" section.
- **`README.md` Tests section updated** — badge updated to 720 passed; test suite table now lists all 23 suites with individual test counts.

## [2.8.1] - 2026-03-07
### Added

- Added support for disabling dialogue timeout by allowing the timeout configuration to be set to `None`.
- Added clearer internal guidance for **constructive disagreement** in Athena’s dialogue prompt to improve dialectical responses.

### Changed

- Restored the default runtime timeout to **300 minutes**, while preserving support for `None` as an unlimited-time option for debugging and long experimental runs.
- Updated search-query rewriting to better filter out:
  - weak semantic filler words
  - weak structural words
  - prompt scaffolding / template leakage words
- Improved Athena’s disagreement prompt from a generic instruction to a structured dialectical scaffold:
  - identify the previous claim
  - question an assumption, definition, or implication
  - offer an alternative interpretation or counter-argument
  - maintain a respectful philosophical tone
- Clarified practical model requirements in documentation: **Phi-3 class models or stronger are recommended**, since smaller models do not reliably sustain the system’s complexity.

### Fixed

- **Query-branch consistency** — `dialogue_question` and `dialogue_longest` branches in `web_research.py` no longer emit a search query when `find_trigger()` returns `None`; turns with no trigger now fall through silently to `seed_fallback`. (PR #192)
- **Duplicate log handlers** — replaced re-entrant `setup_logging()` in both production scripts with a single `logging.basicConfig(force=True)` call, eliminating duplicate log output on every run. (PR #192)
- **Debug mode toggle** — added `debug: bool = True` field to `Config`; `__post_init__` now sets the root logger level dynamically (`DEBUG` or `INFO`), making debug verbosity configurable. (PR #193)
- **Topic/seed mismatch** — `run()` now rotates `TOPIC_CYCLE` so `topicman.current()` on turn 1 matches `cfg.seed_topic`; `SeedGenerator.generate_seed()` logs both the received topic and the generated seed. (PR #194)
- **Concept-based query rewriting** — replaced `_extract_trigger_fragment` in `build_research_query` with the new `rewrite_search_query(text, trigger)` function in `web_research.py`; removes pronouns, auxiliaries, conjunctions, prepositions, and discourse gerunds via `_REWRITE_FILLER_WORDS`, returning up to **6 concept terms**. (PR #195)
- Fixed low-quality web research queries caused by filler or structural tokens appearing in sanitized search strings.
- Prevented prompt-template leakage into search queries, filtering terms such as:
  - `style`
  - `drives`
  - `seed`
  - `recent`
  - `thoughts`
  - `answer`
  - `analysis`
  - `synthesis`
  - `deconstruction`
- Reduced malformed queries such as  
  `essence virtue truth increasingly integral one`  
  and replaced them with compact **concept-based search queries**.
- Improved Athena’s tendency to **agree and expand** when instructed to disagree constructively.

### Verified

- Main script architecture remained unchanged aside from timeout configurability.
- Existing test suite passed after the changes.
- No new security issues were introduced in the modified areas.
- Core pipeline behavior preserved:
  - trigger detection
  - search execution
  - page fetching
  - context injection
  - dialogue loop
  - meta metrics

## [2.8.0] - 2026-03-06

### Added

- **Web Research Module** 🌐 — Fixy-triggered external knowledge pipeline (5 new modules)

  - **`entelgia/web_tool.py`** — Three public functions:
    - `web_search(query, max_results=5)` — DuckDuckGo HTML search; returns `[{title, url, snippet}]`
    - `fetch_page_text(url)` — downloads page, strips `<script>`/`<style>`/`<nav>`/`<footer>`, returns `{url, title, text}` (capped at 6 000 chars)
    - `search_and_fetch(query)` — combines search + fetch into `{query, sources: [{title, url, snippet, text}]}`

  - **`entelgia/source_evaluator.py`** — Heuristic credibility scoring
    - `evaluate_source(source)` → `{url, credibility_score}` in [0, 1]
    - `evaluate_sources(sources)` → list sorted descending by score
    - Scoring rules: `.edu`/`.gov` (+0.30), known research sites (+0.20), long text (+0.20/+0.10), very short text (−0.20)

  - **`entelgia/research_context_builder.py`** — Formats ranked sources as LLM-ready context
    - `build_research_context(bundle, scored_sources, max_sources=3)` → formatted `"External Research:\n..."` block

  - **`entelgia/fixy_research_trigger.py`** — Keyword-based trigger detection
    - `fixy_should_search(user_message)` → `True` when message contains: `latest`, `recent`, `research`, `news`, `current`, `today`, `web`, `find`, `search`, `paper`, `study`, `article`, `published`, `updated`, `new`, `trend`, `report`, `source`

  - **`entelgia/web_research.py`** — Full pipeline orchestration
    - `maybe_add_web_context(user_message, db_path=None, max_results=5)` → context string or `""`
    - Stores sources with `credibility_score > 0.6` in `external_knowledge` SQLite table (`id`, `timestamp`, `query`, `url`, `summary`, `credibility_score`)
    - Fails gracefully — never crashes the main dialogue system

- **`entelgia/context_manager.py`** — Extended `build_enriched_context` and `_format_prompt` to accept an optional `web_context: str = ""` parameter; when provided, injects an `"External Knowledge Context:"` section with agent-specific instructions (Superego verifies credibility, Ego integrates sources, Id may resist if energy is low, Fixy monitors reasoning loops)

- **`entelgia_research_demo.py`** — Standalone demo script
  - Simulates the full pipeline: user query → Fixy trigger → search → credibility ranking → agent dialogue → final answer
  - Runs without a live Ollama instance (mock agent responses for demo purposes)
  - Usage: `python entelgia_research_demo.py "latest research on quantum computing"`

### Changed

- `requirements.txt` — added `beautifulsoup4>=4.12.0` (required by `web_tool.fetch_page_text`)

---

## [2.7.0] - 2026-03-03

### Added

- **Limbic Hijack State** 🧠 — Id-dominant emotional override mechanism for agents
  - `agent.limbic_hijack: bool` — new per-agent boolean state (default `False`)
  - `agent._limbic_hijack_turns: int` — consecutive turns elapsed since hijack started (default `0`)
  - Module-level constants: `LIMBIC_HIJACK_SUPEREGO_MULTIPLIER = 0.3`, `LIMBIC_HIJACK_MAX_TURNS = 3`
  - **Activation condition** (pre-response hook in `speak()`): fires when `id_strength > 7`, `_last_emotion_intensity > 0.7`, and `conflict_index() > 0.6` simultaneously
  - **Behavioral effects during hijack**: SuperEgo influence reduced to 30% (`effective_sup = sup × 0.3`); response kind forced to `"impulsive"`; LLM temperature elevated; SuperEgo critique effectively suppressed
  - **Exit condition**: deactivates immediately when `emotion_intensity < 0.4`, or automatically after `LIMBIC_HIJACK_MAX_TURNS = 3` turns without re-trigger
  - Applied identically to both `Entelgia_production_meta.py` and `Entelgia_production_meta_200t.py`

- **Meta Output Refinement** — eliminated per-turn "SuperEgo critic skipped" log spam
  - `print_meta_state()` now uses a priority-ordered tag system:
    1. Limbic hijack active → `[META] Limbic hijack engaged — emotional override active`
    2. SuperEgo critique applied → `[SuperEgo critique applied; original shown in dialogue]`
    3. Otherwise → silent (no message)

- **`tests/test_limbic_hijack.py`** 🧪 — 15 unit tests covering all hijack scenarios
  - `TestLimbicHijackInitialState` — initial attribute defaults
  - `TestLimbicHijackActivation` — all-conditions-met vs. each threshold below boundary
  - `TestLimbicHijackExit` — intensity-drop exit, turn-cap exit, counter increment
  - `TestLimbicHijackResponseKind` — impulsive kind enforcement during hijack
  - `TestMetaOutputLogic` — all three meta output branches + priority ordering + no skipped-message spam

---

### Changed

- `Agent.speak()` in both production files: drives → temperature block now computes `effective_sup` before passing to temperature formula and `evaluate_superego_critique`, enabling hijack suppression without changing the public API or `drives` dict
- `print_meta_state()` in both production files: removed unconditional "skipped" branch; limbic hijack message takes priority over SuperEgo messages

---

## [2.6.0] - 2026-02-26

### Added

- **`entelgia/dialogue_metrics.py`** 📊 — Three quantitative dialogue-quality metrics (PR #111)
  - `circularity_rate` — fraction of turn-pairs with topic-signature Jaccard similarity ≥ threshold; measures how much the dialogue loops
  - `progress_rate` — forward steps per turn: topic shifts + synthesis markers + open-question resolutions
  - `intervention_utility` — mean circularity reduction in the post-Fixy window vs. pre-Fixy window
  - `circularity_per_turn()` — rolling time-series for graphing
  - `compute_all_metrics()` — runs all three metrics in one call
  - `if __name__ == "__main__"` demo block: prints all three metrics plus a per-turn ASCII circularity bar chart (PR #117)

- **`entelgia/ablation_study.py`** 🔬 — Reproducible 4-condition ablation study (PR #111)
  - `BASELINE` — fixed A-B round-robin with repetitive content
  - `DIALOGUE_ENGINE` — adds dynamic speaker selection and varied seeds
  - `FIXY` — adds need-based Fixy interventions every 6 turns
  - `DREAM` — adds dream-cycle energy consolidation
  - `run_ablation(turns, seed)` — fully reproducible across conditions
  - `print_results_table()` — formatted metrics table output
  - `plot_circularity()` — matplotlib line chart with ASCII fallback
  - `if __name__ == "__main__"` block for direct script execution (PR #115)

- **`entelgia/__init__.py`** updated exports: `run_ablation`, `print_results_table`, `plot_circularity`, and all metrics functions (PR #111)

- **`entelgia/context_manager.py`** — `if __name__ == "__main__"` demo block added; prints enriched prompt and relevant memories when run directly (PR #117)

- **`tests/test_dialogue_metrics.py`** 🧪 — 45 unit tests covering metrics correctness, edge cases, reproducibility, and inter-condition ordering guarantees (PR #111)
  - `TestDialogueMetricsDemo` class added: pins exact demo output values as regression tests (PR #121)
    - Exact metric values: Circularity Rate `0.022`, Progress Rate `0.889`, Intervention Utility `0.167`
    - Validates the full 10-value per-turn circularity series
    - Subprocess smoke-tests confirm script stdout output

- **`tests/test_demo_dialogue.py`** 🎭 — Live dialogue demo test (PR #127)
  - Canonical 10-turn Socrates / Athena / Fixy conversation on consciousness, free will, and identity
  - `test_full_dialogue_demo()` validates circularity, progress, and intervention utility metrics
  - Shows per-test metric summary with expected thresholds and ✓/✗ results (PR #138)

- **`tests/conftest.py`** — pytest session hooks (PR #127)

- **All test files** — `if __name__ == "__main__": pytest.main([__file__, "-v", "-s"])` entry point added for direct execution (PR #128)
  - `test_behavioral_rules.py`, `test_drive_correlations.py`, `test_drive_pressure.py`, `test_energy_regulation.py`, `test_long_term_memory.py`, `test_memory_security.py`, `test_memory_signing_migration.py`

- **All test files** — Unique per-test ASCII tables and bar charts (PR #139)
  - `_print_table(headers, rows, title)` — auto-sized bordered ASCII table per test
  - `_print_bar_chart(data_pairs, title)` — horizontal `█`-bar chart per test
  - Every test prints its own specific computed data (inputs, outputs, thresholds, pass/fail) with `-s`

- **Fluid drive dynamics** — `Config.drive_mean_reversion_rate` and `Config.drive_oscillation_range` (PR #102)
  - `drive_mean_reversion_rate: float = 0.04` — pulls Id/Superego back toward 5.0 each turn
  - `drive_oscillation_range: float = 0.15` — max random nudge applied to Id/Superego each turn
  - Prevents monotonic drift to extremes; `Agent.update_drives_after_turn` fluidity block applied after ego-erosion step

- **`DrivePressure`** 📈 — Per-agent urgency/tension scalar 0.0–10.0 (PR #107)
  - `compute_drive_pressure()` — weighted formula: conflict (45%) + unresolved questions (25%) + stagnation (20%) + energy depletion (10%) with α=0.35 smoothing
  - `_topic_signature(text)` — MD5-based stagnation detection
  - `_trim_to_word_limit(text, max_words)` — trims to last sentence boundary within limit
  - `_is_question_resolved(text)` — detects A)/B)/yes/no resolution patterns
  - `Agent` fields: `drive_pressure=2.0`, `open_questions`, `_topic_history`, `_same_topic_turns`
  - `speak()` injects directives at pressure ≥6.5 (concise) and ≥8.0 (decisive); word caps 120/80
  - `print_meta_state()` prints `Pressure:` line after Energy/Conflict
  - **`tests/test_drive_pressure.py`** 🧪 — 4 acceptance test classes (pressure rise, word caps, decay, determinism)

- **Forbidden opener phrases** — Agents no longer open with `"Recent thought"`, `"A recent thought"`, or `"I ponder"` (PR #104)
  - Extended `LLM_FORBIDDEN_PHRASES_INSTRUCTION` in both `context_manager.py` and `Entelgia_production_meta.py`
  - `FORBIDDEN_STARTERS` runtime list with post-processing strip in `speak()`
  - Cross-agent opener deduplication: injects `FORBIDDEN OPENER` for last other-agent's opening sentence

- **`Entelgia_production_meta_200t.py`** — CLI mode dispatch aligned with `Entelgia_production_meta.py` (PR #105)
  - `main()` entry point with `test` / `api` / `help` / default (`run_cli_long()`) modes
  - Module docstring updated to document all run modes

- **`scripts/validate_project.py`** v3.0 — `MarkdownConsistencyChecker` added (PR #106)
  - `check_classes_in_markdown()`, `check_config_attrs_in_markdown()`, `check_module_files_in_markdown()`, `check_stale_md_references()` via AST introspection
  - Validates all public classes, all `Config` fields, all `entelgia/*.py` modules, and stale symbol references
  - Overall project score improved: 88.3% → 90.8%

- **`scripts/validate_implementations.py`** 🔍 — Data-driven code vs. documentation cross-checker (PR #109)
  - `MarkdownExtractor` — scans README, ARCHITECTURE, SPEC, whitepaper; extracts backtick symbols and `.py` references
  - `CodeInspector` — AST-parses all Python sources; extracts classes, `Config` fields, module filenames, public functions
  - `ImplementationComparator` — reports discrepancies in both directions across 4 categories
  - Usage: `python scripts/validate_implementations.py`; exits `0` on full sync, `1` on discrepancies

- **`scripts/run_all_tests.py`** 🏃 — Single script to discover and run the full test suite (PR #123)
  - Delegates to `pytest` as a subprocess; extra arguments forwarded verbatim
  - Auto-installs `requirements.txt` and `.[dev]` extras before running (PR #124)
  - Detects and replaces incompatible `pyreadline` with `pyreadline3` on Windows (PR #125)

- **`scripts/research_statistics.py`** 📊 — Comprehensive measurable-factors table across all 4 ablation conditions (PR #136)
  - Reports 16 statistics: core dialogue metrics, dialogue characteristics (vocab diversity, TTR, etc.), energy-system metrics (avg energy, dream cycles, LTM size)
  - Usage: `python scripts/research_statistics.py`

- **`research.md`** 📄 — Reformatted as a proper structured scientific paper (PR #132)
  - Standard repo logo/title header; article metadata (Author, Affiliation, Date, Status, Keywords)
  - `##`/`###` headings; aligned markdown tables; Discussion as numbered subsections
  - Figures moved into corresponding subsections; References section with internal doc links
  - `README.md`: Added `🔬 Research Paper (research.md)` entry to Documentation section
  - `xychart-beta` Mermaid charts with vivid color palette for Figures 1–5 (PR #133, #134)
  - Expanded abstract (3 paragraphs), in-text numeric citations, and 12-entry peer-reviewed bibliography (PR #135)

### Fixed

- `tests/test_dialogue_metrics.py` produced no output when executed directly from the command line; added `if __name__ == "__main__": pytest.main([__file__, "-v"])` guard (PR #112)
- `entelgia/ablation_study.py` raised `ModuleNotFoundError` when imported as `entelgia.ablation_study`; `dialogue_metrics` was missing the `.py` extension (PR #113)
- `entelgia/ablation_study.py` raised `ImportError: attempted relative import with no known parent package` when executed directly; added try/except import fallback (relative imports first, then absolute via `sys.path`) and a `__main__` entry point (PR #115)

- **Agents echoing Superego voice** — Superego identity bleed fixed in three layers (PR #98)
  - `entelgia/enhanced_personas.py`: `format_persona_for_prompt` now uses `Current mode (as {name}):` to anchor agent identity
  - `entelgia/context_manager.py`: Drive label renamed `superego=` → `s_ego=` → `val=` to prevent LLM persona-switch
  - `Entelgia_production_meta.py` `speak()`: Safety-net `re.sub` strips `Superego:` / `Super-ego:` / `s_ego:` prefixes

- **Superego persona bleed and repeated first sentence** — PR #98 regression fixes (PR #101)
  - `val=` drive label (further renamed from `s_ego=`); identity-lock instruction added to both prompt paths: `"IMPORTANT: You are {agent_name}. Never adopt a different identity..."`
  - `_first_sentence()` helper; `FORBIDDEN OPENER` injection prevents agent from repeating its own or other agent's opening sentences

- **Fixy agent silently disabled when package installed** — `pyproject.toml` was missing `packages = ["entelgia"]`, causing `InteractiveFixy` import to fail silently (PR #103)

- **`python-dotenv` hard crash converted to soft warning** — `Entelgia_production_meta.py` no longer raises `ImportError` at module level when dotenv is absent; emits `warnings.warn()` instead, allowing all 217 tests to collect and run without the package (PR #129)

- **pytest INTERNALERROR on test collection** — `sys.exit(1)` in `Entelgia_production_meta.py` replaced with `raise ImportError(...)` (PR #126); `--continue-on-collection-errors` added to `pyproject.toml` addopts so 188+ tests still run when 2 files have missing-dependency errors

- **pytest crash on Windows Python 3.10+** — `pyreadline` (unmaintained, uses removed `collections.Callable`) replaced with `pyreadline3` (maintained fork); `requirements.txt` and `pyproject.toml` updated with `pyreadline3>=3.4.1; sys_platform == "win32"` (PR #125)

- **Noisy demo dialogue in test output** — `conftest.py` `pytest_terminal_summary` hook removed; `test_demo_dialogue.py` replaced `capsys.disabled()` full transcript with targeted per-test metric result printing (PR #138)

### Changed

- **`entelgia/context_manager.py`** and **`README.md`** — Docs corrected for accuracy (PR #106)
  - `config.max_output_words` removed (it is a module-level constant, not a `Config` field)
  - `llm_timeout` default corrected: `60` → `300` s
  - `memory_security.py` and undocumented `Config` fields added to README
  - `ARCHITECTURE.md`: class names added to Core Components; Session & API table added
  - `SPEC.md`: 5 missing output-path fields and new drive-fluidity fields added

- **Black formatting** applied across Python codebase (PR #100, #108, #110, #122, #137)
  - `Entelgia_production_meta.py`, `entelgia/context_manager.py`, `tests/test_drive_correlations.py`, `tests/test_drive_pressure.py`, `entelgia/__init__.py`, `entelgia/ablation_study.py`, `entelgia/dialogue_metrics.py`, `scripts/validate_implementations.py`, `scripts/research_statistics.py`

---

## [2.5.0] - 2026-02-21

## 🚀 Highlights

- **Energy-Based Agent Regulation System** — cognitive energy as a first-class resource
- **Personal Long-Term Memory System** — psychoanalytically-inspired memory regulation
- **Drive-aware cognition** — dynamic LLM temperature, ego-driven memory depth, superego second-pass critique
- **Coherent Freudian drive correlations** — high conflict now directly erodes ego, raises temperature, and amplifies energy drain (PR #92)
- **`Entelgia_production_meta_200t.py`** — guaranteed 200-turn dialogue without time-based stopping
- **Dialogue bug fixes** — third body calling to first body, double turn (agent answering twice in one turn), and pronoun issue all resolved
- **Super ego persona fix** — dialogue now displays the agent's original authentic voice; the superego rewrite is applied only for internal state updates (PR #95)
- **Output quality rules** — forbidden meta-commentary phrases removed at sentence level, dissent marker capped to exactly one sentence, hard word truncation removed (PR #96)
- New module exports, comprehensive tests, and a working demo
- Version bump from 2.4.0 → 2.5.0 across all documents and code

## 📝 Changes

### Added

- **`Entelgia_production_meta_200t.py`** 🔁 — 200-turn companion script
  - `MainScriptLong(MainScript)` — subclass that overrides only `run()`, replacing the
    time-based `while time < timeout` condition with a turn-count gate `while turn_index < max_turns`
  - `_NO_TIMEOUT_MINUTES = 9999` sentinel disables time-based stopping entirely
  - `run_cli_long()` entry point: `Config(max_turns=200, timeout_minutes=9999)`
  - All other behaviour (memory, emotions, Fixy interventions, dream cycles, session
    persistence) inherited from `MainScript` unchanged
  - Run via: `python Entelgia_production_meta_200t.py`
  - EntelgiaAgent.long_term_memory — persistent list that accumulates critical memories promoted from short-term memory during every dream cycle.
  - EntelgiaAgent._is_critical(memory) — relevance gate that determines whether a STM entry is substantive enough (contains at least one word ≥ 4 characters) to be promoted to long-term memory; designed to be overridden in subclasses for richer emotional / importance-based scoring.
  - Dream cycle STM → LTM promotion — _run_dream_cycle() now iterates conscious memory and copies every critical, relevant entry to long_term_memory (no duplicates). Existing integration and relevance-filtering  behavior is unchanged.
  - Eight new unit tests in tests/test_energy_regulation.py (TestEntelgiaAgentLTMPromotion) covering: initial LTM state, critical-entry promotion, trivial-entry exclusion, duplicate prevention, _is_critical edge cases, and subconscious-path promotion.
- **`entelgia/energy_regulation.py`** ⚡ — Energy-Based Agent Regulation System
  - **`FixyRegulator`** — Meta-level energy supervisor
    - `safety_threshold` (default: 35.0) — minimum energy threshold for safe operation
    - `check_stability(agent)` method: evaluates agent energy and applies regulation
      - Triggers a dream cycle (`DREAM_TRIGGERED`) when energy ≤ safety threshold
      - Stochastic hallucination-risk check (p=0.10) when energy drops below 60 %
        returns `HALLUCINATION_RISK_DETECTED`
      - Returns `None` when the agent is healthy
    - Class constants: `DEFAULT_SAFETY_THRESHOLD = 35.0`,
      `HALLUCINATION_RISK_PROBABILITY = 0.10`,
      `HALLUCINATION_RISK_ENERGY_CUTOFF = 60.0`
  - **`EntelgiaAgent`** — Agent with energy tracking and dream-cycle consolidation
    - `energy_level` starts at 100.0 and decreases 8–15 units per `process_step` call
    - `conscious_memory` (active inputs) and `subconscious_store` (pending consolidation)
    - Every agent is supervised by an embedded `FixyRegulator`
    - `process_step(text)` — appends input to memory, drains energy, triggers dream cycle
      when needed; returns `"RECHARGED_AND_READY"` or `"OK"`
    - `_run_dream_cycle()` — consolidates `subconscious_store` into `conscious_memory`,
      keeps only the last 5 entries, and restores `energy_level` to 100.0

- **`entelgia/long_term_memory.py`** 🧠 — Personal Long-Term Memory System
  - **`DefenseMechanism`** — classifies every memory write as repressed or suppressed
    - Repression: painful emotion (anger, fear, shame, guilt, anxiety) above 0.75 intensity
      or forbidden-keyword match → sets `intrusive = 1`
    - Suppression: mildly negative or low-intensity content → sets `suppressed = 1`
  - **`FreudianSlip`** — surfaces defended memories probabilistically
    - Samples up to 30 candidate memories; returns one at random (p per-call)
    - Skips memories that are not intrusive or suppressed
  - **`SelfReplication`** — promotes recurring-pattern memories to consciousness
    - Detects keywords (≥ 4 chars) appearing ≥ 2 times across candidate pool
    - Promotes up to 3 matching memories per call

- **`entelgia/__init__.py`** package exports updated
  - `FixyRegulator`, `EntelgiaAgent` exported from `energy_regulation`
  - `DefenseMechanism`, `FreudianSlip`, `SelfReplication` exported from `long_term_memory`

- **`tests/test_energy_regulation.py`** 🧪 — 18 unit tests
  - `TestFixyRegulatorDefaults` — threshold and constant validation
  - `TestFixyRegulatorCheckStability` — dream trigger, recharge, hallucination risk
  - `TestEntelgiaAgentInit` — initial state, regulator propagation
  - `TestEntelgiaAgentProcessStep` — energy drain, memory append, return values
  - `TestEntelgiaAgentDreamCycle` — consolidation and subconscious clearing
  - `TestPackageImports` — package-level import checks

- **`tests/test_long_term_memory.py`** 🧪 — comprehensive tests for all three classes
  - `TestDefenseMechanismRepression` / `TestDefenseMechanismSuppression`
  - `TestFreudianSlip` — slip surface and empty-pool edge cases
  - `TestSelfReplication` — keyword promotion and threshold logic
  - `TestPackageImports` — package-level import checks

- **`examples/demo_energy_regulation.py`** 📖 — 8-turn Socrates demo
  - Shows energy depletion and automatic dream-cycle recovery
  - Prints turn-by-turn energy level and status

- **ROADMAP.md** 🗺️ — project roadmap added to repository
- Project logo added to all markdown files

- **`tests/test_drive_correlations.py`** 🧪 — 18 unit tests across 4 classes (PR #92)
  - `TestConflictIndex` — boundary value tests for `conflict_index()`
  - `TestEgoErosion` — magnitude and monotonicity of ego erosion under conflict
  - `TestTemperatureConflictCorrelation` — temperature rises with conflict index
  - `TestEnergyDrainScaling` — conflict-scaled drain and cap behavior

## 🔄 Changed

- **`Entelgia_production_meta.py`** — Drive-aware cognition (PR #75)
  - **Dynamic LLM temperature** derived from Freudian drive values:
    ```
    temperature = max(0.25, min(0.95, 0.60 + 0.03 * (id - ego) - 0.02 * (superego - ego)))
    ```
    Higher `id_strength` → more creative/exploratory; higher `superego_strength` → more constrained.
  - **Superego second-pass critique**: when `superego_strength ≥ 7.5`, the initial response is
    fed back to the LLM at `temperature=0.25` with a principled rewrite prompt acting as an
    internal governor.
  - **Ego-driven memory retrieval depth** replaces fixed `limit=4` / `[-6:]`:
    ```
    ltm_limit = max(2, min(10, int(2 + ego / 2 + sa * 4)))   # long-term
    stm_tail  = max(3, min(12, int(3 + ego / 2)))             # short-term
    ```
    Agents with stronger ego / self-awareness pull more context and stabilise faster after reset.
  - **Output artifact cleanup + word limit enforcement** after all validate/critique passes:
    - Strips agent name/pronoun prefix echoed by LLM (e.g. `"Socrates (he): "`)
    - Removes gender script tags: `(he):`, `(she)`, `(they)`
    - Removes stray scoring markers: `(5)`, `(4.5)`, etc.
    - Truncates to `MAX_RESPONSE_WORDS = 150`

- **`Entelgia_production_meta.py`** — Coherent Freudian drive correlations (PR #92)
  - **Conflict → Ego erosion** (`update_drives_after_turn`): captures `pre_conflict = |ide - ego| + |sup - ego|` before updating drives; when it exceeds 4.0, Ego is eroded proportionally:
    ```python
    if pre_conflict > 4.0:
        ego = max(0.0, ego - 0.03 * (pre_conflict - 4.0))
    ```
  - **Conflict → Temperature/Tone** (`speak`): adds a conflict component to the LLM temperature formula so high drive imbalance produces a more volatile, impulsive tone:
    ```python
    temperature = 0.60 + 0.03*(ide-ego) - 0.02*(sup-ego) + 0.015*self.conflict_index()
    ```
  - **Conflict → Energy drain** (`update_drives_after_turn`): replaces flat random drain with conflict-scaled drain, capped at `2 × energy_drain_max`:
    ```python
    drain = random.uniform(CFG.energy_drain_min, CFG.energy_drain_max) + 0.4 * pre_conflict
    drain = min(drain, CFG.energy_drain_max * 2.0)
    ```

- **`Entelgia_production_meta.py` / `entelgia/context_manager.py`** — Output quality rules (PR #96)
  - **Dissent marker capped to exactly one sentence** — `_behavioral_rule_instruction` (Athena, `dissent_level ≥ 3.0`) changed from `"at least one sentence"` to `"exactly one sentence"`.
  - **Forbidden meta-commentary phrases** — Added `FORBIDDEN_PHRASES` (`"In our dialogue"`, `"We learn"`, `"Our conversations reveal"`) and `LLM_FORBIDDEN_PHRASES_INSTRUCTION` to both `Entelgia_production_meta.py` and `entelgia/context_manager.py`.
    - `validate_output()` now performs sentence-level removal of any sentence containing a forbidden phrase (regex split on `.!?`).
    - `LLM_FORBIDDEN_PHRASES_INSTRUCTION` is injected into both prompt-building paths (`_build_compact_prompt` / `_format_prompt`) to prevent generation up-front.
  - **Hard word truncation removed from `speak()`** — the post-processing `# Enforce 150-word limit` block (word-split + `…` append) is removed; response length is already governed by `LLM_RESPONSE_LIMIT` in the prompt.

- Package `__version__` bumped to **2.5.0**
- `pyproject.toml` version bumped to **2.5.0**
- All documentation version references updated to **v2.5.0**
- `entelgia/energy_regulation.py` and `entelgia/long_term_memory.py` added as
  first-class modules in the `entelgia` package
- Applied **Black** code formatting across the entire Python codebase (PR #69)

## 🐛 Fixed

- **`Entelgia_production_meta.py`** — Super ego character role fix (PR #95)
  - **Super ego persona removed from critique prompt** — `"You are the agent's Superego."` was inadvertently assigning a dialogue character role to the rewrite call, causing agents with high `superego_strength` to speak as the super ego character instead of themselves. Replaced with a plain rewrite instruction: `"Rewrite the following response to be more principled…"`.
  - **Original agent response preserved in dialogue** — `speak()` now saves `original_out` before the superego critique pass. The rewrite is still executed and used for internal state updates (emotion inference + drive recalibration), but `out` is restored to `original_out` before returning, so the dialogue always displays what the agent originally said.
  - **Meta display tag updated** — `[SuperEgo rewrite applied]` → `[SuperEgo critique applied; original shown in dialogue]` to reflect the actual behaviour.

- **`Entelgia_production_meta.py`** — Dialogue engine bug fixes (PR #74)
  - **Third body calling to first body** (broken speaker alternation after Fixy intervention):
    after Fixy (the third agent) intervened, `last_speaker` was mistakenly resolved as the
    first body (Socrates), causing Socrates to speak twice in a row. Fixed by scanning
    `dialog` backwards for the last *non-Fixy* turn when determining the next speaker.
  - **Double turn — agent answering 2 times in 1 turn** (duplicate Fixy output): the legacy
    scheduled `fixy_check` (every N turns) fired *in addition to* the `InteractiveFixy`
    handler, producing two Fixy responses in a single turn. The legacy scheduled path has since
    been fully removed (PR #87); Fixy now intervenes exclusively via `InteractiveFixy`.
  - **Pronoun issue** (pronoun leakage from LLM response): `speak()` now strips the agent
    header prefix that the LLM echoes from its own prompt (e.g. `"Socrates (he): …"`), so
    pronouns never appear in output when `show_pronoun=False`.
  - **Smart text truncation** in `_format_prompt`: dialog turns capped at 200 chars,
    thoughts at 150 chars, memories at 200 chars — all cut at the last word boundary
    (no mid-word splits).

## 🧹 Clean Config & Need-Based Fixy (PR #87)

### Removed
- **Dead `Config` fields** — `fixy_every_n_turns`, `max_prompt_tokens`, `log_level`, and
  `dream_keep_memories` were defined but never read anywhere in the codebase; all removed.
- **`ObserverCore` / `FixyReport`** — legacy observer classes and the `fixy_check()` method
  are removed; Fixy now intervenes exclusively via `InteractiveFixy.should_intervene()`.
- **Legacy scheduled Fixy path** — the `elif not self.interactive_fixy and turn % fixy_every_n_turns == 0`
  block has been deleted from both `Entelgia_production_meta.py` and `Entelgia_production_meta_200t.py`.

### Changed
- **`Config.energy_safety_threshold`** — was defined but silently ignored; now actively
  forces a dream cycle for each agent whose `energy_level` drops to or below the threshold
  on every turn.
- **`ARCHITECTURE.md`** — `energy_safety_threshold` description updated to reflect the
  direct dream-cycle trigger instead of the old "passed to `FixyRegulator`" wording.
- **`TROUBLESHOOTING.md`** — circular-reasoning section rewritten: removed the
  `fixy_every_n_turns` tuning step; Fixy is now described as need-based.
- **`SPEC.md` appendix** — removed `fixy_every_n_turns` and `dream_keep_memories` entries.
- **`whitepaper.md`** — removed `fixy_every_n_turns` entry from Agent Behavior config table.
- **`README.md`** — removed `fixy_every_n_turns` example from the configuration snippet.
- **`scripts/validate_project.py`** — updated class-name patterns from `ObserverCore` to
  `InteractiveFixy`; removed `fixy_every_n_turns` config check; reduced `total_checks` from 5 to 4.

## 🛑 Breaking Changes
*None* — all changes are backward compatible

---

## [2.4.0] - 2026-02-18

# Entelgia v2.4.0 Release Notes

## 🚀 Highlights

- Major refactor and documentation improvements
- Project structure update
- Memory management tool improvements
- Expanded FAQ & troubleshooting
- Updated whitepaper and architecture overview
- English documentation standard

## 📝 Changes

- clear_memory.py utility
- modular project reorganization
- FAQ updates
- demo and example updates
- whitepaper, architecture docs enriched

## 🛑 Breaking Changes
*None* (All changes are backwards compatible)

## 💡 Upgrade Instructions
- See ARCHITECTURE.md
- Use updated clear_memory.py

## 📋 Contributors
- @sivanhavkin

### Added
- **Memory Management Utility** 🗑️
  - New `clear_memory.py` script for deleting stored memories
  - Interactive menu with three deletion options:
    - Delete short-term memory (JSON files)
    - Delete long-term memory (SQLite database)
    - Delete all memories (both types)
  - Safety features:
    - Confirmation prompt before deletion
    - Shows count of files/entries before deletion
    - Cannot be undone warning
  - Use cases: reset experiments, privacy concerns, testing, storage management
  - Documentation added to README.md with usage examples

### Changed
- Reorganized project structure into modular subdirectories
- Moved core files from repository root into dedicated folders
- Improved repository layout for clarity and future scalability
- Rewrite and rename demo examples to Entelgia_demo
  
### Documentation
- Removed all foreign language content to standardize the repository to English only.
- Added comprehensive troubleshooting documentation.
- Added FAQ - 513-line FAQ covering common questions.
- Added Memory Management section to README.md
- Added detailed ARCHITECTURE.md describing Entelgia's system architecture.
- whitepaper updated to reflect all recent changes.
---

## [2.3.0] - 2026-02-16

### Installation & Documentation Improvements
- Added a new `install.py` script for automated setup: installs all Python dependencies, creates the `.env` file, prompts for API key, and checks/installs Ollama (where supported).
- Refactored README: unified all installation steps into a single "Quick Install" section, including a direct link to `install.py`.
- Removed duplicate/manual install instructions and clarified the process for installing Ollama, with consistent formatting and messaging.
### Changed
- Removed all Unicode icons (such as ✔, ✓, 🚨, etc.) from logger messages in all main execution files and test/demo scripts.
  - This improves compatibility with Windows consoles and environments that do not support extended Unicode in standard output.
- Logger outputs are now ASCII-only for maximum readability on all platforms.
- No changes made to documentation, README, or markdown files – decorative icons remain.

### Fixed
- UnicodeEncodeError warnings no longer appear when running on Windows terminal.

---


## [2.2.0] - 2026-02-14

### ➕ Added

- **Pronoun Support** 🏷️
  - Official support for gender pronouns (he/she) for agents
  - `show_pronoun` flag in Config (default: False for backwards compatibility)
  - `is_global_show_pronouns` global control variable in enhanced_personas module
  - Pronoun data added to personas: Socrates (he), Athena (she), Fixy (he)
  - Uniform display control in user and LLM prompts
  - When enabled, pronouns appear as "AgentName (pronoun):" in prompts
  - Gender-neutral by default to maintain inclusive conversation style

- **Response Handling Without Truncation** ✨
  - All truncation/cutting limits on agent responses removed
  - Explicit LLM instruction added to prompts: "Please answer in maximum 150 words"
  - All responses displayed in full without any cutting or truncation
  - Role-playing maintains 150-word request for conciseness without enforced truncation
  - `validate_output()` function performs sanitization only (removes control chars, normalizes newlines)
  - LLM naturally controls response length based on prompt guidance
  - Ensures complete, coherent responses without mid-sentence cuts

 - **Enhanced Dialogue Module** 🎭
   - `entelgia/` package with modular dialogue components
   - `dialogue_engine.py` - Dynamic speaker selection & seed generation
   - ` enhanced_personas.py` - Rich character definitions (Socrates, Athena, Fixy)
   - `context_manager.py` - Smart context enrichment with sentence boundaries
   - `fixy_interactive.py` - Need-based interventions (vs scheduled)
   - `__init__.py` - Clean package API
  
- **Dialogue Features** 💬
  - Dynamic speaker selection (prevents 3+ consecutive turns)
  - 6 seed generation strategies:
    - `introduce_analogy` - Metaphorical thinking
    - `constructive_disagree` - Respectful challenge
    - `explore_implication` - Consequence analysis
    - `question_assumption` - Foundational inquiry
    - `meta_reflect` - Self-awareness
    - `agree_and_expand` - Collaborative building
  - Rich context with 8 dialogue turns, 6 recent thoughts, 5 memories
  - Context enrichment with intelligent text management
  - Fixy interventions based on need (circular reasoning, repetition, confusion)

- **Testing & Demo** 🧪
  - `test_enhanced_dialogue.py` - 5 comprehensive tests for dialogue system
  - `demo_enhanced_dialogue.py` - 10-turn demonstration script
  - All tests passing (5 dialogue + 19 security = 24 total)

- **Response Length Control** ⚡
  - Explicit 150-word limit instruction added to all LLM prompts
  - `validate_output()` function for sanitization (no truncation)
  - New Config options:
    - `max_output_words` (default: 150) - Used in LLM prompt instruction
  - Responses displayed in full without truncation
  - LLM controls response length naturally based on prompt guidance

### 🐛 Fixed

- Fixed `CFG` global initialization in `MainScript.__init__`
- Resolves `'NoneType' has no attribute 'data_dir'` error
- Demo scripts now work without `run_cli()` wrapper
- Added `global CFG` declaration to ensure proper initialization

### 🔄 Changed

- **Architecture** 🏗️
  - Migrated from monolithic to modular dialogue system
  - Legacy ping-pong alternation preserved as fallback
  - Enhanced mode auto-detected when `entelgia` package available
  
- **Personas** 🎭
  - Expanded from short strings to rich dataclass definitions
  - Added traits, speech patterns, intervention triggers
  - Socrates: Deconstructive, dialectic method
  - Athena: Integrative, wisdom-seeking
  - Fixy: Pattern-matching, meta-cognitive

- **Performance** ⚡
  - Reduced predictability in dialogue flow
  - Smarter context management (fewer token waste)
  - Fixy only speaks when needed (not every N turns)

- **Timeouts & Performance** ⚡ (v2.2.0-unreleased)
  - Reduced `llm_timeout` from 600 seconds (10 minutes) to 60 seconds (1 minute)
  - Shorter maximum wait times for LLM responses
  - Faster failure detection when LLM is unresponsive
  - Better user experience with more predictable response times

- **Gender-Neutral Output** 🌐 
  - Removed gender language tracking initialization
  - Cleaner dialogue output without gender pronouns
  - More inclusive and neutral conversation style

### 📝 Documentation

- Added version notes to all modified files indicating unreleased features
- Added comprehensive comments explaining pronoun feature
---

## [2.1.1] - 2026-02-13

### Fixed
- Fixed pyproject.toml configuration issues
- Applied Black code formatting across all files
- Resolved CI/CD pipeline failures

### Infrastructure
- All tests passing on 6 platforms
- Code quality checks now green
- Build verification successful
- Latest official release marked as v2.1.1 throughout codebase

---

## [2.1.0] – 2026-02-13 – **Testing & Community Infrastructure - Superseded**

This release adds a comprehensive testing infrastructure, build system configuration, and community contribution tools without changing core functionality.

### Added

- **Testing Suite** 🧪
  - Complete pytest configuration in pyproject.toml
  - tests/__init__.py package initialization
  - conftest.py with reusable fixtures
  - test_memory_security.py with 18+ unit tests
  - Test coverage for HMAC-SHA256 signature validation

- **Build System** ⚙️
  - pyproject.toml with full project metadata
  - Dependency management (runtime and dev dependencies)
  - pytest, black, flake8, mypy configurations
  - Project URLs and classifiers

- **GitHub Templates** 🤝
  - Bug report template (.github/ISSUE_TEMPLATE/bug_report.md)
  - Feature request template (.github/ISSUE_TEMPLATE/feature_request.md)
  - Pull request template (.github/ISSUE_TEMPLATE/PULL_REQUEST_TEMPLATE.md)

- **API Documentation** 📚
  - Comprehensive API docs (docs/api/README.md)
  - Quick start guide with examples
  - Python and cURL usage examples
  - Error handling documentation

### Fixed

- Fixed file naming conventions (README.md, requirements.txt lowercase)
- Refactored memory security tests into organized classes

### Notes

This is a quality-of-life release focused on developer experience and project infrastructure. All core v2.0.1 functionality is preserved.

---

## [2.0.1] – 2026‑02‑13 – **Production Final - Superseded**

This version finalises the 2.x production rewrite with additional **memory security measures** and licence updates. It retains all features from the 2.0.0 release and adds cryptographic protection for stored memories.

### ➕ Added
- ✅ **HMAC‑SHA256 signatures** on all memory entries, enabling tamper detection and validation.
- ✅ **Automatic forgetting** of memory entries when signature validation fails, ensuring corrupted or tampered memories are not retained.
- ✅ **Secret key management** via environment variables, allowing secure configuration of cryptographic keys without hard‑coding secrets.
- ✅ **Unit tests** to validate signature creation and verification logic.
- ✅ **Windows Unicode encoding fix** to improve emoji and character support.
- ✅ **Standard MIT License** replacing the custom Entelgia ethical licence.

### 🔄 Changed
- Updated the README licence section to reflect the adoption of the **MIT License**.

### 📝 Notes
> This version is considered the **final release** of the 2.x line at the time of publication.

### ⚠️ Known Limitations
- Requires **8 GB or more of RAM** and a powerful CPU; may experience Ollama HTTP timeouts on low‑resource machines.

---

## [2.0.0] – 2026‑02‑11 – **Production V2.0 - Superseded**

Version 2.0.0 represents a **breaking change** and a complete rewrite of the project with a modular, production‑ready architecture. It introduces a multitude of new capabilities, improved performance, and a robust foundation for future development.

### ⚠️ Breaking Changes
- The entire architecture has been rewritten. Existing integrations and extensions targeting the 1.x line will need to be updated.

### ➕ Added
- 🤖 **Multi‑agent dialogue system** with three agents: **Socrates**, **Athena**, and an observer/fixer agent (**Fixy**). Agents interact and reason with each other to produce more nuanced responses.
- 💾 **Persistent memory** comprising short‑term memory (JSON, FIFO trimming) and long‑term memory (SQLite) unified for conscious and subconscious storage.
- 🧠 **Psychological drives** inspired by Freud (id, ego and superego dynamics) influence decision making and responses.
- 😊 **Emotion tracking** and importance scoring, including intensity metrics for experiences.
- 🌙 **Dream cycles** that periodically promote memories from short‑term to long‑term storage, consolidating context over time.
- ⚡ **Least Recently Used (LRU) cache** yielding approximately **75% cache hit rates** and reducing repeated LLM calls.
- 🌐 **REST API** built with FastAPI, exposing endpoints for agent interaction and memory management.
- ✅ **Unit tests** (pytest) covering core functionality (nine tests in total).
- ⏱️ **10‑minute auto‑timeout** to prevent runaway conversation loops.
- 🔒 **PII redaction** and privacy protection integrated into memory storage and logs.
- 🔁 **Error handling with exponential backoff**, improving resilience against network or model failures.
- 📊 **Structured logging** to console and file for easier debugging and observability.

### ⚡ Performance
- 📉 **50% reduction in LLM calls** thanks to caching of repeated queries.
- 📉 **70% reduction in token usage** by compressing prompts and responses.
- ⚡ **2‑3× faster response times** through parallel agent execution and caching.

### 🏗️ Architecture
- Approximately **1,860 lines of production code** with **25+ classes** and **50+ documented functions**, all with full type hints.
- **Modular core system** composed of Memory, Emotion, Language, Conscious, Behavior, and Observer modules, promoting separation of concerns and extensibility.

### ⚠️ Known Limitations
- Requires **8 GB or more of RAM** and a powerful CPU; may experience Ollama HTTP timeouts on low‑resource machines.

### 📝 Notes
> This release lays the foundation for all future 2.x versions and is the **first production‑ready version** of Entelgia. All subsequent changes are expected to be backward compatible within the 2.x series.

---

## [1.5.1] – 2026‑02‑08 – **V1.5 Hotfix** 🔧

This hotfix addresses a critical model update without introducing new features. It builds on top of version 1.5.0.

### 🐛 Fixed
- Updated Ollama models to **phi3:latest**, improving generation quality and stability.

### 📝 Notes
> Users should update to this version if they rely on the Ollama backend.

---

## [1.5.0] – 2026‑02‑07 – **V1.5**

Version 1.5.0 introduced the first iteration of the multi‑agent system and began the transition toward the architecture that would later be refined in 2.0.0.

### ➕ Added
- 🤖 **Multi‑agent conversation loop** featuring Socrates and Athena.
- 👁️ **Observer/fixer agent (Fixy)** to monitor conversations and offer perspective shifts or terminate loops when necessary.
- 🔌 **Ollama integration** with separate per‑agent models for Socrates and Athena.
- 💾 **Per‑agent short‑term memory** stored as JSON with FIFO trimming.
- 💾 **Unified long‑term memory** in SQLite for conscious and subconscious storage.
- 😊 **Emotion tracking** including intensity metrics for each agent.
- 🌍 **Agent‑controlled language selection**, allowing agents to choose the appropriate language for responses.
- 🌙 **Dream cycle functionality** to promote memories from short‑term to long‑term storage every N turns.
- 📊 **CSV logging** of conversation data with an optional GEXF knowledge graph export.
- 🔄 **Safe auto‑patching** of the codebase and version‑tracking snapshots to monitor changes between runs.
- 🚀 Added run script **entelgia_pitch1.5.py** for launching the system.

### 📋 Requirements
- Python 3.10 or higher.
- Ollama running locally at `http://localhost:11434`.
- Installation of the `requests` and `colorama` Python packages.

### 📝 Notes
> This version marked a significant step toward a more interactive and modular system but was still research‑oriented and lacked many of the production enhancements introduced in 2.0.0.

---

## [1.0.0] – 2026‑02‑06 – **Initial Public Core** 🎯

The first public release of the Entelgia core. Although not yet production‑ready, it provided a proof‑of‑concept for moral reasoning and conflict‑based self‑regulation.

### ➕ Added
- 📄 **Single‑file architecture** (`entelgia_unified.py`) encapsulating the entire system.
- 🤖 **Two persistent agents** (Socrates and Athena) with evolving internal states.
- 🧠 **Freud‑inspired internal conflict dynamics** guiding agent behaviour.
- 💾 **Long‑term memory** implemented with SQLite.
- 👁️ **Observer agent (Fixy)** to detect loops and prompt perspective shifts.
- 🔌 **Optional local LLM integration** via Ollama, with fallback to a deterministic mock mode if Ollama is unavailable.

### 📝 Notes
> This release was a research‑grade prototype focusing on moral reasoning and internal conflict rather than rule‑based safety filters.

> The code supporting this version was merged into the main branch on **2026‑01‑23**. The version tag v1.0.0 was later published on **2026‑02‑06**.

### 📋 Requirements
- Python 3.10 or higher.
- Ollama running locally (default `http://localhost:11434`).
- Installation of the `requests` and `colorama` Python packages.

---

## [0.4.0‑experimental] – 2026‑02‑07 – **Experimental Preview** ⚗️

This pre‑release demonstrated the full multi‑agent architecture running end‑to‑end. It was intentionally resource‑intensive and is **not suitable for production use**.

### ➕ Added
- 🤖 **Full multi‑agent architecture** with Socrates, Athena and Fixy.
- 🧪 **Experimental self‑modelling** and cognitive depth features, which may surface meta‑instructions or internal rules during execution.

### ⚠️ Known Limitations
- Requires **16 GB or more of RAM** and a powerful CPU; may experience Ollama HTTP timeouts on low‑resource machines.
- **Not production‑ready**; intended for researchers, system thinkers, experimental AI developers and anyone interested in cognitive depth.

### 📝 Notes
> Although tagged as version 0.4.0‑experimental, this release was published on the same day as v1.5.0 and should be considered a separate research preview rather than part of the stable release series.

---

**Legend:**
- 🎉 Major milestone
- 🚀 Production release
- ➕ Added feature
- 🔄 Changed feature
- 🐛 Bug fix
- ⚠️ Breaking change or warning
- 📝 Notes
- 🔧 Hotfix
- ⚗️ Experimental

---

## 📊 Quick Reference

- ✅ **Latest stable:** v4.0.0
- 🚧 **Next release:** TBD
- 📅 **Release schedule:** Bi-weekly minor, as-needed patches
- 📖 **Versioning:** [Semantic Versioning 2.0](https://semver.org/)

---

## 📊 Version History Summary

| Version | Release Date | Type | Status | Description |
|---------|--------------|------|--------|-------------|
| **v4.0.0** | 2026-03-20 | Major | ✅ **Current** | Version bump to 4.0.0; two-stage DRAFT→FINAL pipeline, proposal-aware topic selection, query rewriting improvements |
| **v3.0.0** | 2026-03-12 | Minor | ⚠️ Superseded | Topic-aware style selection, forgetting policy, affective routing, confidence metadata, loop guard, enable_observer flag, semantic repetition detection, FreudianSlip rate-limiting |
| **v2.8.1** | 2026-03-07 | Patch | ✅ **Stable** | Version bump across all documentation |
| **v2.8.0** | 2026-03-06 | Minor | ⚠️ Superseded | Web Research Module — Fixy-triggered external knowledge pipeline |
| **v2.7.0** | 2026-03-03 | Minor | ✅ **Stable** | Limbic hijack state, meta output refinement |
| **v2.6.0** | 2026-02-26 | Minor | ✅ **Stable** | Dialogue metrics, ablation study, drive pressure & research tools |
| **v2.5.0** | 2026-02-21 | Minor | ✅ **Stable** | Energy regulation, long-term memory & coherent drive correlations |
| **v2.4.0** | 2026-02-18 | Minor | ⚠️ Superseded | Documentation & structure improvements |
| **v2.3.0** | 2026-02-16 | Minor | ⚠️ Superseded | Installation improvements |
| **v2.2.0** | 2026-02-14 | Minor | ⚠️ Superseded | Enhanced dialogue system |
| **v2.1.1** | 2026-02-13 | Patch | ⚠️ Superseded | Bug fixes + formatting |
| v2.1.0 | 2026-02-13 | Minor | ⚠️ Superseded | Testing infrastructure |
| v2.0.01 | 2026-02-13 | Major | ⚠️ Superseded | Production rewrite |
| v1.5 | 2026-01-31 | Minor | 📦 Legacy | Multi-agent v1.5 |
| v1.5-HOTFIX | 2026-01-31 | Patch | 📦 Legacy | Model update |
| v1.0.0 | 2026-01-23 | Major | 📦 Legacy | Initial public release |
| v0.4.0-exp | 2026-02-06 | Experimental | 🧪 Archive | Research only |

### Status Legend
- 🚧 **Coming Soon** - In development
- ✅ **Current** - Latest stable release, recommended
- ⚠️ **Superseded** - Working but upgrade recommended
- 📦 **Legacy** - Old architecture, no longer maintained
- 🧪 **Archive** - Experimental, not for production

---

## 🔄 Versioning Guidelines

This project follows [Semantic Versioning 2.0.0](https://semver.org/):


























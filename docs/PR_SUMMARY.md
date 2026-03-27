<div style="display: flex; align-items: center; justify-content: space-between;">
  <img src="../Assets/entelgia-logo.png" alt="Entelgia Logo" width="120" style="margin: 0;"/>
  <h1 style="flex-grow: 1; text-align: center; font-size: 2.5em; font-weight: bold; margin: 0;">PR Summary: Pronoun Support and 150-Word Limit Features</h1>
  <div style="width: 120px;" aria-hidden="true"></div>
</div>


### Overview
This PR implements official support for gender pronouns in agent prompts and adds explicit 150-word limit instructions to all LLM prompts, as requested in the original issue.

### Key Features

#### 1. Pronoun Support 🏷️
- **Agents with pronouns:**
  - Socrates: he
  - Athena: she  
  - Fixy: he
- **Configuration:** `show_pronoun` flag in Config (default: False)
- **Global control:** `is_global_show_pronouns` variable
- **Display format:** "AgentName (pronoun):" when enabled
- **Backward compatible:** Gender-neutral by default

#### 2. 150-Word Limit Instruction ⚡
- Explicit instruction added to all LLM prompts
- Works with existing smart_truncate_response() fallback
- Ensures concise, focused responses

### Implementation Details

**Files Modified:**
- `entelgia/enhanced_personas.py` - Added pronoun data to personas
- `entelgia/context_manager.py` - Updated prompt formatting
- `entelgia/__init__.py` - Exported global control variable
- `Entelgia_production_meta.py` - Added Config flag, updated prompts
- `test_enhanced_dialogue.py` - Added pronoun tests
- `Changelog.md` - Documented changes

**Files Added:**
- `docs/PRONOUN_FEATURE.md` - Comprehensive documentation

### Testing Results
```
Tests passed: 6/6
✓ ALL TESTS PASSED!

Test Coverage:
- Dynamic Speaker Selection
- Seed Variety  
- Context Enrichment (with/without pronouns)
- Fixy Interventions
- Persona Formatting
- Persona Pronouns
```

### Security
- CodeQL scan: 0 alerts
- Code review: All comments addressed
- No security vulnerabilities introduced

### Version Information
- Feature version: v2.2.0 
- Latest official release: v5.0.0
- All version markers updated throughout codebase

---

## Usage Examples

### Default Mode (No Pronouns)
```python
from Entelgia_production_meta import Config, MainScript

cfg = Config()  # show_pronoun=False by default
script = MainScript(cfg)
# Output: "Socrates: What is knowledge?"
```

### With Pronouns Enabled
```python
from Entelgia_production_meta import Config, MainScript

cfg = Config(show_pronoun=True)
script = MainScript(cfg)
# Output: "Socrates (he): What is knowledge?"
```

---

## Migration Notes

### For Existing Users
- **No action required** - Feature is disabled by default

### To Enable Pronouns
```python
cfg = Config(show_pronoun=True)
```

---

## Documentation

Full documentation available in:
- `docs/PRONOUN_FEATURE.md` - Complete feature guide
- `Changelog.md` - Version history and changes

---

## Next Steps

This PR is ready for:
1. ✅ Code review (completed, all issues addressed)
2. ✅ Security scan (completed, 0 alerts)
3. ✅ Testing (completed, 6/6 tests passing)
4. 🔄 Merge to main branch
5. 📦 Release as v2.2.0

---

## PR: Web Research Module (v2.8.0)

### Overview
This PR implements the Web Research capability for Entelgia — 5 new modules plus
demo script and full documentation.

### Key Features

#### 1. Fixy Research Trigger 🔍
- `fixy_should_search(user_message)` — keyword detection
- Trigger words: `latest`, `research`, `news`, `current`, `today`, `web`, `find`, `search`, `paper`, and more

#### 2. Web Tool 🌐
- `web_search(query, max_results=5)` — DuckDuckGo HTML search (no API key)
- `fetch_page_text(url)` — BeautifulSoup extraction, 6 000-char cap
- `search_and_fetch(query)` — combined pipeline

#### 3. Source Evaluator 📊
- Heuristic credibility scoring: `.edu`/`.gov` domains, trusted research sites, text length
- Score in [0.0, 1.0], sorted descending

#### 4. Research Context Builder 📝
- Formats top-3 sources as `External Research:` block for LLM prompts

#### 5. Integration 🔗
- `maybe_add_web_context(user_message)` — full pipeline
- `ContextManager.build_enriched_context(web_context=...)` — prompt injection
- High-credibility sources (> 0.6) stored in `external_knowledge` SQLite table

### Files Changed
- `entelgia/web_tool.py` (new)
- `entelgia/source_evaluator.py` (new)
- `entelgia/research_context_builder.py` (new)
- `entelgia/fixy_research_trigger.py` (new)
- `entelgia/web_research.py` (new)
- `entelgia/context_manager.py` (modified — `web_context` parameter added)
- `entelgia_research_demo.py` (new)
- `requirements.txt` (modified — added `beautifulsoup4>=4.12.0`)
- All documentation markdown files updated

---

## PR: Web Research Hardening — Failed-URL Blacklist, Per-Query Cooldown, Fixy 1–2 Sentence Prompt

### Overview
Three targeted fixes that improve the reliability and efficiency of the Web Research
Module and Fixy's intervention quality.

### Fix 1 — Failed-URL Blacklist (`web_tool.py`) 🚫

- `fetch_page_text` now maintains a module-level `_failed_urls: set` of URLs that
  returned HTTP **403** or **404**.
- Before any network request, the URL is checked against the set; blacklisted URLs
  return `{"url": url, "title": "", "text": ""}` immediately.
- On a 403 or 404 response the URL is added to the set so all future calls skip it.
- A `clear_failed_urls()` helper resets the set (called automatically by test fixtures).

### Fix 2 — Per-Query Cooldown (`fixy_research_trigger.py`) ⏱️

- Added `_recent_queries: Dict[str, int]` alongside the existing `_recent_triggers` dict.
- At the start of `fixy_should_search`, if the same sanitized query was already searched within
  `_COOLDOWN_TURNS` turns, the function returns `False` immediately.
- `fixy_should_search` accepts an optional `query_cooldown_key` parameter; when provided,
  this pre-built sanitized query string is used as the `_recent_queries` key instead of
  `seed_text`.  `maybe_add_web_context` builds the query early and passes it as
  `query_cooldown_key` so that different `seed_text` values resolving to the same compact
  query share a single cooldown slot (fixes repeated searches despite cooldown).
- When a search is suppressed by per-query cooldown, an INFO-level log message shows the
  sanitized query key and the relevant turn numbers for easier debugging.
- `clear_trigger_cooldown()` also clears `_recent_queries`.

### Fix 3 — Fixy 1–2 Sentence Prompt (`fixy_interactive.py`) 🎯

- All intervention prompt templates now end with:
  `"Respond in 1-2 sentences only. Be direct and concrete."`
- Replaces the previous looser instruction `"Respond in maximum 2 sentences."`.
- Enforces concise, actionable Fixy interventions across all five intervention types:
  `circular_reasoning`, `high_conflict_no_resolution`, `shallow_discussion`,
  `synthesis_opportunity`, `meta_reflection_needed`.

### Files Changed
- `entelgia/web_tool.py` (modified — `_failed_urls` blacklist + `clear_failed_urls`)
- `entelgia/fixy_research_trigger.py` (modified — `_recent_queries` per-query cooldown)
- `entelgia/fixy_interactive.py` (modified — 1–2 sentence prompt)
- `tests/conftest.py` (modified — `clear_failed_urls` in autouse fixture)
- `tests/test_web_research.py` (modified — `TestQueryCooldown` + `TestFailedUrlBlacklist`)
- All documentation markdown files updated

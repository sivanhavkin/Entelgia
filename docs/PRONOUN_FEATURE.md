<div style="display: flex; align-items: center; justify-content: space-between;">
  <img src="../Assets/entelgia-logo.png" alt="Entelgia Logo" width="120" style="margin: 0;"/>
  <h1 style="flex-grow: 1; text-align: center; font-size: 2.5em; font-weight: bold; margin: 0;">Pronoun Support Feature</h1>
  <div style="width: 120px;" aria-hidden="true"></div>
</div>

## Overview

The pronoun support feature allows displaying gender pronouns (he/she) after agent names in prompts and dialogue. This feature is disabled by default to maintain gender-neutral output.

---

## Configuration

### Global Control

```python
from entelgia import is_global_show_pronouns
# Default: False - pronouns are hidden
```

### Config Flag

```python
from Entelgia_production_meta import Config

cfg = Config(
    show_pronoun=True  # Enable pronoun display
)
```

---

## Agent Pronouns

| Agent | Pronoun | Description |
|-------|---------|-------------|
| Socrates | he | Philosophical questioner |
| Athena | she | Strategic synthesizer |
| Fixy | he | Meta-cognitive observer |

---

## Usage Examples

### Example 1: Default (No Pronouns)

```python
from Entelgia_production_meta import MainScript, Config

cfg = Config()  # show_pronoun defaults to False
script = MainScript(cfg)
# Output: "Socrates: What is knowledge?"
```

### Example 2: With Pronouns

```python
from Entelgia_production_meta import MainScript, Config

cfg = Config(show_pronoun=True)
script = MainScript(cfg)
# Output: "Socrates (he): What is knowledge?"
```

---

## Implementation Details

### Persona Data Structure

Each persona now includes a `pronoun` field:

```python
SOCRATES_PERSONA = {
    "name": "Socrates",
    "pronoun": "he",  # Gender pronoun for display
    "core_traits": [...],
    ...
}
```

### Prompt Formatting

When `show_pronoun=True`, prompts are formatted as:
- `"AgentName (pronoun):"`

When `show_pronoun=False` (default):
- `"AgentName:"`

---

## Benefits

### Backward Compatibility
- Feature is disabled by default, maintaining existing gender-neutral behavior

### Flexibility
- Users can choose to display pronouns when desired for clarity or preference

### Consistent Control
- Single flag controls display across all prompts (user-facing and LLM)

---

## Version Information

- **Feature Version:** v2.2.0 
- **Latest Official Release:** v2.5.0
- **Status:** Stable

---

## Related Features

### 150-Word Limit Instruction

This release also includes explicit 150-word limit instructions in LLM prompts:

```
IMPORTANT: Keep your response concise (under 150 words).
```

This works in conjunction with the existing `smart_truncate_response()` fallback mechanism.

---

## Testing

Run the test suite to verify pronoun functionality:

```bash
python tests/test_enhanced_dialogue.py
```

Expected output includes:
- ✓ Test 6: Persona Pronouns - All pronoun checks passed
- ✓ Test 3: Context Enrichment - Verifies default (no pronouns) and enabled (with pronouns) modes

---

## Technical Notes

1. **Pronoun Data:** Stored in persona dictionaries in `entelgia/enhanced_personas.py`
2. **Control Points:** 
   - Global: `is_global_show_pronouns` variable
   - Config: `show_pronoun` flag in Config class
3. **Prompt Builders:** Updated in both enhanced and legacy prompt building methods
4. **Fallback:** If pronoun data is missing, gracefully falls back to name-only display

---

## Future Enhancements

- [ ] Support for additional pronoun options (they/them, etc.)
- [ ] Per-agent pronoun override
- [ ] Localized pronoun display based on language
- [ ] Dynamic pronoun selection in runtime

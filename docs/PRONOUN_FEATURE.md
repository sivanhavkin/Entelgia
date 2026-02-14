# Pronoun Support Feature

## Overview / סקירה כללית

**English:** The pronoun support feature allows displaying gender pronouns (he/she) after agent names in prompts and dialogue. This feature is disabled by default to maintain gender-neutral output.

**עברית:** תכונת תמיכת הכינויים מאפשרת הצגת כינויי גוף (he/she) אחרי שמות הסוכנים בפרומפטים ובדיאלוג. תכונה זו מושבתת כברירת מחדל כדי לשמור על פלט ניטרלי מגדרית.

---

## Configuration / הגדרות

### Global Control / שליטה גלובלית

```python
from entelgia import is_global_show_pronouns
# Default: False - pronouns are hidden
# ברירת מחדל: False - כינויים מוסתרים
```

### Config Flag / דגל בהגדרות

```python
from Entelgia_production_meta import Config

cfg = Config(
    show_pronoun=True  # Enable pronoun display / הפעל הצגת כינויים
)
```

---

## Agent Pronouns / כינויי הסוכנים

| Agent / סוכן | Pronoun / כינוי | Description / תיאור |
|--------------|----------------|---------------------|
| Socrates | he | Philosophical questioner / שואל פילוסופי |
| Athena | she | Strategic synthesizer / מסכמת אסטרטגית |
| Fixy | he | Meta-cognitive observer / משקיף מטה-קוגניטיבי |

---

## Usage Examples / דוגמאות שימוש

### Example 1: Default (No Pronouns) / דוגמה 1: ברירת מחדל (ללא כינויים)

```python
from Entelgia_production_meta import MainScript, Config

cfg = Config()  # show_pronoun defaults to False
script = MainScript(cfg)
# Output: "Socrates: What is knowledge?"
# פלט: "Socrates: מהי ידיעה?"
```

### Example 2: With Pronouns / דוגמה 2: עם כינויים

```python
from Entelgia_production_meta import MainScript, Config

cfg = Config(show_pronoun=True)
script = MainScript(cfg)
# Output: "Socrates (he): What is knowledge?"
# פלט: "Socrates (he): מהי ידיעה?"
```

---

## Implementation Details / פרטי יישום

### Persona Data Structure / מבנה נתוני פרסונה

Each persona now includes a `pronoun` field:

```python
SOCRATES_PERSONA = {
    "name": "Socrates",
    "pronoun": "he",  # Gender pronoun for display
    "core_traits": [...],
    ...
}
```

### Prompt Formatting / עיצוב פרומפטים

When `show_pronoun=True`, prompts are formatted as:
- `"AgentName (pronoun):"`

When `show_pronoun=False` (default):
- `"AgentName:"`

---

## Benefits / יתרונות

### Backward Compatibility / תאימות לאחור
- **English:** Feature is disabled by default, maintaining existing gender-neutral behavior
- **עברית:** התכונה מושבתת כברירת מחדל, שומרת על ההתנהגות הניטרלית הקיימת

### Flexibility / גמישות
- **English:** Users can choose to display pronouns when desired for clarity or preference
- **עברית:** משתמשים יכולים לבחור להציג כינויים כאשר רצוי לבהירות או העדפה

### Consistent Control / שליטה עקבית
- **English:** Single flag controls display across all prompts (user-facing and LLM)
- **עברית:** דגל אחד שולט בתצוגה בכל הפרומפטים (למשתמש ול-LLM)

---

## Version Information / מידע גרסה

- **Feature Version:** v2.2.0 
- **Latest Official Release:** v2.2.0
- **Status:** In development / בפיתוח

---

## Related Features / תכונות קשורות

### 150-Word Limit Instruction / הוראת מגבלת 150 מילים

This release also includes explicit 150-word limit instructions in LLM prompts:

```
IMPORTANT: Keep your response concise (under 150 words).
```

This works in conjunction with the existing `smart_truncate_response()` fallback mechanism.

**עברית:** מהדורה זו כוללת גם הוראות מפורשות למגבלת 150 מילים בפרומפטי ה-LLM, הפועלות ביחד עם מנגנון הגיבוי smart_truncate_response() הקיים.

---

## Testing / בדיקות

Run the test suite to verify pronoun functionality:

```bash
python test_enhanced_dialogue.py
```

Expected output includes:
- ✓ Test 6: Persona Pronouns - All pronoun checks passed
- ✓ Test 3: Context Enrichment - Verifies default (no pronouns) and enabled (with pronouns) modes

---

## Technical Notes / הערות טכניות

1. **Pronoun Data:** Stored in persona dictionaries in `entelgia/enhanced_personas.py`
2. **Control Points:** 
   - Global: `is_global_show_pronouns` variable
   - Config: `show_pronoun` flag in Config class
3. **Prompt Builders:** Updated in both enhanced and legacy prompt building methods
4. **Fallback:** If pronoun data is missing, gracefully falls back to name-only display

---

## Future Enhancements / שיפורים עתידיים

- [ ] Support for additional pronoun options (they/them, etc.)
- [ ] Per-agent pronoun override
- [ ] Localized pronoun display based on language
- [ ] Dynamic pronoun selection in runtime


# Bug Report - MyTelegramBot Project

## Executive Summary

After a thorough code review of the entire project, I identified **5 bugs** (2 critical, 2 medium, 1 minor) and several code quality issues. The most critical issues are in the `set_language` logic and the `reminders_off` handler.

---

## Critical Bugs

### BUG #1: `pick_lang` behaves inconsistently for unknown languages

**Location:** `bot.py` line 621-622

```python
def pick_lang(lang: str, uk: str, en: str) -> str:
    return en if lang == "en" else uk
```

**Problem:** When `lang` is any value other than `"en"` (including invalid/unknown values like `"unknown"`, `None`, `""`), the function returns `uk` (Ukrainian). This is inconsistent with the test expectation in `test_set_language.py` (Test #8) which expects English as fallback.

**Impact:** If `get_user_language()` ever returns an unexpected value (e.g., due to database corruption or migration issues), all UI text will unexpectedly be in Ukrainian instead of English.

**Test Evidence:**

```
✅ Тест 8: pick_lang для неизвестного языка
   ❌ Ожидается 'Hello', получено 'Привіт'
```

**Fix:**

```python
def pick_lang(lang: str, uk: str, en: str) -> str:
    return uk if lang == "uk" else en  # Default to English
```

---

### BUG #2: `reminders_off` incorrectly inserts `reminders_enabled=1` before setting to 0

**Location:** `bot.py` lines 2259-2271

```python
@dp.callback_query(lambda c: c.data == "reminders_off")
async def reminders_off(callback: CallbackQuery):
    # ...
    cur.execute(
        """
        INSERT INTO users (user_id, reminders_enabled)
        VALUES (?, 1)
        ON CONFLICT(user_id) DO NOTHING
        """,
        (uid,)
    )
    cur.execute(
        "UPDATE users SET reminders_enabled=0 WHERE user_id=?",
        (uid,)
    )
```

**Problem:** The INSERT statement inserts `reminders_enabled=1` (enabled) before updating it to 0. While the final result is correct due to the UPDATE, this is logically wrong and confusing. More importantly, if there's a race condition or the UPDATE fails, the user would have reminders enabled instead of disabled.

**Comparison with `reminders_on`:** The `reminders_on` handler (lines 2223-2235) has the same pattern but inserts `1` which matches the intended behavior.

**Fix:**

```python
cur.execute(
    """
    INSERT INTO users (user_id, reminders_enabled)
    VALUES (?, 0)
    ON CONFLICT(user_id) DO NOTHING
    """,
    (uid,)
)
```

---

## Medium Severity Bugs

### BUG #3: Duplicate `PROFILE_FIELDS` definition

**Location:** `bot.py` lines 183-189 and `profile_visibility.py` lines 9-15

```python
# In bot.py (line 183-189):
PROFILE_FIELDS = (
    ("height", "Зріст", "Height"),
    ("gender", "Стать", "Gender"),
    ("age", "Вік", "Age"),
    ("weight", "Вага", "Weight"),
    ("goal", "Мета", "Goal"),
)

# In profile_visibility.py (line 9-15):
PROFILE_FIELDS = (
    ("height", "Зріст", "Height"),
    ("gender", "Стать", "Gender"),
    ("age", "Вік", "Age"),
    ("weight", "Вага", "Weight"),
    ("goal", "Мета", "Goal"),
)
```

**Problem:** `PROFILE_FIELDS` is defined in both files with identical content. The `bot.py` imports `PROFILE_FIELDS` from `profile_visibility` (line 26), but then redefines it locally (line 183). This creates confusion and potential for inconsistency if one is updated but not the other.

**Impact:** Maintenance burden and risk of inconsistency.

**Fix:** Remove the duplicate definition from `bot.py` (lines 183-189) and use only the imported one from `profile_visibility`.

---

### BUG #4: Potential SQL injection in `profile_visibility.py`

**Location:** `profile_visibility.py` lines 76-81 and 104-111

```python
def set_field_visibility(user_id: int, field: str, visible: bool) -> bool:
    # ...
    column = f"show_{field}"
    value = 1 if visible else 0

    # Using f-string for column name (potential SQL injection)
    query = f"UPDATE users SET {column}=? WHERE user_id=?"
    execute_query(query, (value, user_id))
```

**Problem:** While the `field` parameter is validated against `PROFILE_FIELDS` before use (line 71-72), the column name is constructed using an f-string. If the validation is bypassed or the function is called directly without validation, this could allow SQL injection through the column name.

**Current Validation (line 71-72):**

```python
if field not in {name for name, _, _ in PROFILE_FIELDS}:
    return False
```

**Risk Level:** LOW - The validation is in place, but the pattern is still risky.

**Better Fix:** Use a whitelist approach with a mapping dictionary:

```python
VALID_COLUMNS = {
    "height": "show_height",
    "gender": "show_gender",
    "age": "show_age",
    "weight": "show_weight",
    "goal": "show_goal",
}

def set_field_visibility(user_id: int, field: str, visible: bool) -> bool:
    if field not in VALID_COLUMNS:
        return False

    column = VALID_COLUMNS[field]
    # ...
```

---

## Minor Issues

### BUG #5: Inconsistent database connection handling

**Location:** Multiple files (`bot.py`, `db_improved.py`)

**Problem:** The codebase uses two different database modules:

- `db.py` - Simple synchronous module with a single connection
- `db_improved.py` - More robust module with thread-safe global connection

Both are present and `bot.py` imports from `db_improved`, but `db.py` is still in the project. This creates confusion about which one to use.

**Impact:** Confusion for maintainers, potential for using the wrong module.

**Fix:** Remove `db.py` if `db_improved.py` is the intended module, or consolidate them.

---

## Code Quality Issues (Not Bugs)

### Issue #1: Duplicate calories calculation logic

The `calc_calories` and `calc_calories_async` functions in `bot.py` (lines 1491-1573) duplicate the same logic. The `services/calories.py` module also has similar functions. Consider consolidating.

### Issue #2: Duplicate `parse_activity_and_duration` function

The function exists in both `bot.py` (lines 1453-1488) and `services/calories.py` (lines 22-57) with identical logic.

### Issue #3: Unused imports in `bot.py`

Line 20-23 imports several functions from `db_improved`:

```python
from db_improved import (
    get_db, execute_query, fetch_one, fetch_all, execute_transaction,
    clear_user_all_data, verify_user_exists, get_user_data_safe, init_connection, get_db_context
)
```

Some of these (`init_connection`, `get_db_context`) don't appear to be used in `bot.py`.

### Issue #4: `set_language_command` doesn't require user to exist first

**Location:** `bot.py` lines 1644-1654

```python
@dp.message(Command("set_language"))
async def set_language_command(message: Message):
    uid = message.from_user.id

    # Требование: любой вызов /set_language должен переключать UA <-> EN
    lang = toggle_user_language(uid)
    # ...
```

The `toggle_user_language` function calls `get_user_language` which uses `fetch_one`. If the user doesn't exist, it returns `"uk"` (default), then `set_user_language` uses `INSERT ... ON CONFLICT DO UPDATE`. This works correctly, but it's worth noting that the user record is created implicitly.

---

## Set_Language Logic Analysis

The `set_language` functionality is implemented correctly overall:

1. **`get_user_language(user_id)`** - Returns user's language or defaults to `"uk"`
2. **`set_user_language(user_id, lang)`** - Sets language using INSERT ... ON CONFLICT
3. **`toggle_user_language(user_id)`** - Switches between `"uk"` and `"en"`
4. **`/set_language` command** - Toggles language and confirms change

**Verified Working:**

- ✅ Default language is Ukrainian
- ✅ Toggle switches correctly between uk ↔ en
- ✅ Language persists in database
- ✅ SQL injection protection via parameterized queries

**Issue Found:**

- ❌ `pick_lang` defaults to Ukrainian for unknown languages (should be English)

---

## Profile_Visibility Logic Analysis

The `profile_visibility` functionality is well-implemented:

1. **`ensure_user_exists(user_id)`** - Creates user if not exists
2. **`get_profile_visibility(user_id)`** - Returns dict of all field visibilities
3. **`set_field_visibility(user_id, field, visible)`** - Sets specific field visibility
4. **`toggle_field_visibility(user_id, field)`** - Toggles field visibility
5. **`get_visible_fields(user_id)`** - Returns list of visible fields
6. **`is_field_visible(user_id, field)`** - Checks if field is visible

**Verified Working:**

- ✅ All CRUD operations work correctly
- ✅ Default visibility is True for all fields
- ✅ Toggle correctly switches between visible/hidden
- ✅ Unknown fields raise ValueError
- ✅ set_all_visible and hide_all_fields work correctly

**Issues Found:**

- ⚠️ Potential SQL injection via column name (low risk due to validation)
- ⚠️ Duplicate PROFILE_FIELDS definition in bot.py

---

## Recommendations

1. **Fix Bug #1** - Change `pick_lang` to default to English for unknown languages
2. **Fix Bug #2** - Correct the INSERT value in `reminders_off` handler
3. **Fix Bug #3** - Remove duplicate `PROFILE_FIELDS` from `bot.py`
4. **Fix Bug #4** - Use a whitelist mapping for column names in `profile_visibility.py`
5. **Fix Bug #5** - Remove or consolidate `db.py`

---

## Test Results Summary

| Test                     | Status                                     |
| ------------------------ | ------------------------------------------ |
| set_language tests       | 9/10 passed (1 expected behavior mismatch) |
| profile_visibility tests | All passed                                 |

The test failure in Test #8 (`pick_lang` for unknown language) is actually a valid bug - the test expects English fallback but the code returns Ukrainian.

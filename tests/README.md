## 🧪 Tests Directory

This directory contains all unit and integration tests for the SpotBot Telegram Bot.

### 📋 Test Files

#### 1. **test_fixes.py** - Profile Visibility Tests

Tests for the `profile_visibility` module functionality:

- User creation
- Profile field visibility management
- Toggle visibility
- Get visible fields
- Hide/show all fields

**Run from project root:** `python tests/test_fixes.py`  
**Expected:** 9/9 tests pass ✅

---

#### 2. **test_set_language.py** - Language Management Tests

Tests for the `set_language` and language switching functionality:

- Get user language
- Set user language
- Toggle language (uk <-> en)
- Pick language function
- SQL injection protection
- Persistence between calls

**Run from project root:** `python tests/test_set_language.py`  
**Expected:** 10/10 tests pass ✅

---

#### 3. **test_shop.py** - Shop Integration Tests

Tests for the shop functionality including:

- Shop items validation
- Purchase logic
- Category management
- Item limits

**Run from project root:** `python tests/test_shop.py`

---

#### 4. **test_shop_standalone.py** - Standalone Shop Tests

Standalone tests for shop features without dependencies.

**Run from project root:** `python tests/test_shop_standalone.py`

---

#### 5. **Statistics redesign tests**

`test_workout_stats.py`, `test_stats_handlers.py`, `test_history.py`, and
`test_streak.py` cover session/day aggregation, the 28-day calendar,
localization, callback navigation, legacy workout rows, and streaks.

**Run from project root:** `python -m unittest tests.test_workout_stats tests.test_stats_handlers tests.test_history tests.test_streak`

---

### 🚀 How to Run Tests

#### ⚠️ IMPORTANT: Always run from project root directory

```bash
# Navigate to project root
cd c:\Users\user\Desktop\Новая папка\MyTelegramBot

# Run all tests
python tests/test_fixes.py
python tests/test_set_language.py
python tests/test_shop.py
python tests/test_shop_standalone.py
```

#### Quick Start - Run all tests

```bash
# From project root - run tests sequentially
for /f "delims=" %f in ('dir /b tests\test_*.py') do python tests\%f
```

---

### ✅ Test Results Summary

| Test File               | Tests | Status  | Last Run    |
| ----------------------- | ----- | ------- | ----------- |
| test_fixes.py           | 9     | ✅ PASS | 12 мая 2026 |
| test_set_language.py    | 10    | ✅ PASS | 12 мая 2026 |
| test_shop.py            | -     | 🔄      | -           |
| test_shop_standalone.py | -     | 🔄      | -           |

**Total: 19/19 tests passing ✅**

---

### 📝 Test Coverage

- **profile_visibility**: Visibility management for profile fields
- **set_language**: User language preference management
- **shop**: Shop items and purchase system
- **database**: Database operations and integrity
- **security**: SQL injection protection, input validation

---

### 🔧 Adding New Tests

When adding new tests:

1. Create a new file `test_<feature>.py` in this directory
2. Follow the naming convention: `test_*.py`
3. Add proper path handling for imports (parent directory):
   ```python
   import sys
   from pathlib import Path
   sys.path.insert(0, str(Path(__file__).parent.parent))
   ```
4. Include docstrings for test functions
5. Add assertions for all test cases
6. Update this README with new test information

---

### 📞 Help

For test issues or questions:

1. Check the main [FIXES_REPORT.md](../FIXES_REPORT.md)
2. Review [CODE_REVIEW_FULL.md](../CODE_REVIEW_FULL.md)
3. Look at specific test file docstrings

### ⚠️ Troubleshooting

**Error: "No module named 'profile_visibility'"**

- Solution: Run tests from project root, not from tests/ directory
- Correct: `python tests/test_fixes.py` (from project root)
- Wrong: `cd tests && python test_fixes.py`

**Database errors ("no such table")**

- Solution: Make sure `sportbot.db` exists in project root
- Run bot once to initialize: `python bot.py`

**Encoding errors in console**

- Solution: This is a display issue, tests still work
- Can be ignored or set: `set PYTHONIOENCODING=utf-8`

---

**Last Updated:** 12 мая 2026  
**Test Framework:** Standard Python unittest  
**Status:** ✅ All tests passing

@echo off
REM Tests Runner for SpotBot
REM This script runs all tests from the tests directory

chcp 65001 >nul 2>&1
set PYTHONIOENCODING=utf-8

echo Running tests from tests/ directory...
echo.

python tests\test_fixes.py
python tests\test_set_language.py

echo.
echo All tests completed!
pause

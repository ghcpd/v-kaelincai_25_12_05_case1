@echo off
REM One-click test runner for routing service v2
REM Sets up environment and runs all integration tests

echo [*] Setting up Python environment...
if not exist .venv (
    python -m venv .venv
)

echo [*] Activating virtual environment...
call .venv\Scripts\activate.bat

echo [*] Installing dependencies...
pip install -q -r requirements.txt

echo [*] Running integration tests...
pytest tests\test_integration.py -v --tb=short --color=yes

echo [*] Test run complete. Results saved to results/
pause

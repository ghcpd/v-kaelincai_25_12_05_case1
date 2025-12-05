#!/bin/bash
# One-click test runner for routing service v2 (Linux/Mac)

set -e

echo "[*] Setting up Python environment..."
if [ ! -d ".venv" ]; then
    python3 -m venv .venv
fi

echo "[*] Activating virtual environment..."
source .venv/bin/activate

echo "[*] Installing dependencies..."
pip install -q -r requirements.txt

echo "[*] Running integration tests..."
pytest tests/test_integration.py -v --tb=short --color=yes

echo "[*] Test run complete. Results saved to results/"

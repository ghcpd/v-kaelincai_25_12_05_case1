#!/usr/bin/env bash
set -euo pipefail
ROOT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
cd "$ROOT_DIR"
echo "Installing deps (if virtualenv active, ensure packages are installed)..."
python -m pip install -r requirements.txt >/dev/null || true
echo "Running pytest..."
pytest -q tests -q --maxfail=1

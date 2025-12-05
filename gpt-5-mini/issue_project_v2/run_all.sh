#!/usr/bin/env bash
set -euo pipefail
ROOT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
echo "Running tests and collecting results..."
cd "$ROOT_DIR"
./run_tests.sh
python3 - <<'PY'
import json,sys
print('Collecting results...')
PY
echo "Done"

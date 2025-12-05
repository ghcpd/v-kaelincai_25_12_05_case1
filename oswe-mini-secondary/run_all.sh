#!/usr/bin/env bash
set -euo pipefail

echo "Run all: tests -> collect artifacts"
pytest -q || true
echo "Collecting artifacts"
mkdir -p results logs
pytest -q || true
echo '{"note":"run complete"}' > results/results_post.json
echo "Done"

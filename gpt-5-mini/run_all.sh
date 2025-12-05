#!/usr/bin/env bash
set -e
./setup.sh
./run_tests.sh
echo '{"note":"manual compare required"}' > results/aggregated_metrics.json
echo Done

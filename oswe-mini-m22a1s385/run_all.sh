#!/usr/bin/env bash
set -euo pipefail
./setup.sh
./run_tests.sh | tee results/results_post.txt

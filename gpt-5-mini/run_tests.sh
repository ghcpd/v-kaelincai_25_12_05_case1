#!/usr/bin/env bash
# Run pytest and write results to results/results_post.json
mkdir -p results logs
pytest -q --maxfail=1 --junitxml=results/junit_post.xml

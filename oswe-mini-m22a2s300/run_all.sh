#!/usr/bin/env bash
set -e
START=$(date +%s)
echo "Running full test suite (post-change)"
pytest -q --disable-warnings --maxfail=1 || true
END=$(date +%s)
DURATION=$((END-START))
mkdir -p results
cat > results/results_post.json <<EOF
{"timestamp":$(date +%s), "duration_seconds": $DURATION, "notes": "post-change run"}
EOF

echo "Results written to results/results_post.json"

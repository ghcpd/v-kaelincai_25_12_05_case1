# Compare Report (pre vs post)

This document summarizes correctness and performance deltas between legacy (pre) and new (post) implementations.

Metrics:
- p50_latency_post: TBD
- p95_latency_post: TBD
- success_rate_post: TBD
- retries, idempotency violations, compensation counts: TBD

Rollout guidance:
- Start with shadow traffic at 1% for 24h, validate no idempotency anomalies and success_rate > 99%.
- Expand to 10% if metrics stable, then to 50%.
- For rollback: switch shadow off and expire any in-flight outbox entries before reverting.
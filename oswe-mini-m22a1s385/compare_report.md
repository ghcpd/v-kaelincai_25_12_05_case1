# Compare Report - Pre/Post

## Summary

This greenfield v2 scaffold fixes the core functional issue (negative edge handling) by adding validation and Bellman-Ford for negative-weight graphs. It also adds retry/backoff, timeout decorators, idempotency, and an outbox primitive for transactions.

## High-level comparison

| Category | Pre (legacy) | Post (v2 greenfield) |
|---|---:|---|
| Negative-weights | Dijkstra used, produces incorrect routes | Dijkstra refuses negative graphs; Bellman-Ford computes correct shortest paths |
| Observability | None | Structured logs hook, testable metrics via logs |
| Idempotency | None | In-memory idempotency decorator (example) |
| Retries/Backoff | None | Retry decorator with backoff |

## Rollout guidance

1. Deploy v2 as a shadow service behind a feature flag; route a percentage of traffic to v2 for correctness validation.
2. Dual-write graphs to v2 storage when migrating; implement reconciliation job to compare results for traffic samples.
3. If v2 passes correctness and latency SLOs, cut over reads and eventually writes.


# Compare Report (pre → post)

This PoC contains tests designed to show how behaviour improves after switching to a correct routing service.

- Correctness: Dijkstra now rejects negative-edge graphs; Bellman-Ford handles them.
- Observability: structured logs and outbox events.
- Performance: small PoC; p50/p95 latency unaffected in this local run.

Rollout guidance:
- Deploy RouterService behind feature switch; enable auto mode in a small % of traffic; compare responses vs legacy; if mismatch, analyze via trace id.

# Routing Service — Greenfield replacement PoC

This directory contains a small proof-of-concept for a robust routing service to replace the intentionally-broken legacy implementation.

Goals:
- Correct algorithm selection (Dijkstra vs Bellman-Ford)
- Defend against negative-weight mistakes
- Idempotency, retry/backoff, timeouts and circuit-breaker simulation
- Transactional outbox and audit/reconciliation hooks
- Reproducible integration tests and one-click runner

See `run_all.sh` / `run_tests.sh` to execute the integration suite.

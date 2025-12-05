# Legacy System Analysis - issue_project

## Summary findings
- Root functional bug: `dijkstra_shortest_path` marks nodes as visited on discovery and does not validate negative weights, causing incorrect shortest paths on graphs that contain negative edges (see `KNOWN_ISSUE.md`).
- Tests expect either refusal to run Dijkstra on negative graphs or use of Bellman-Ford to compute correct results.
- Observability, retries, idempotency and structured logging are absent; code is single-process library rather than a service.

## Missing data & assumptions

### Missing data (requested)
- Production logs and stack traces for failed routes.
- Usage/traffic patterns (appointment volume, peak QPS/latency targets).
- DB snapshots (if persisted graphs or events exist) and schema.
- Monitoring (metrics, alerts) and SLA/SLO targets.
- Any integration contracts: HTTP API schemas, message topics, or 3rd-party dependencies.

### Assumptions
- This repo is a library used by a routing or logistics service; no external DB is present in the codebase.
- Legacy system lacks retries and idempotency across distributed calls — these will be required for replacement.
- We will design a stateless routing service with persistent graph storage (pluggable) and event-driven reconciliation.

## Collection checklist (what to gather next)
- Code: full service source, third-party adapters, infra-as-code
- Traffic & load: 7/30/90th percentile request volumes, rate limits, peak concurrency
- Logs: recent 30 days of logs, error logs, stack traces with request IDs
- DB snapshots: production graph/state snapshots and transaction logs
- Monitoring: metrics, dashboards, alert rules
- Deployment setup: container images, K8s manifests or similar

Next: scaffold greenfield project implementing correct algorithms, observability, retry/idempotency, and integration tests.

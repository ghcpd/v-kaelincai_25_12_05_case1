1. Clarifications & Missing Data / Assumptions

- Missing data / assumptions:
  - Full API surface of legacy system (endpoints, auth, contracts) is not available.
  - DB schema and data volume (RPS, peak concurrency, size) not provided.
  - SLAs/SLOs not surfaced — assume 99.9% availability and 95th-percentile latency targets.
  - Logs, tracing, monitoring dashboards are partial or unavailable.
  - Transactional boundaries unclear: appointment creation interacts with external calendar and notifications.

- Collection checklist (minimum):
  - Code: repository, critical modules, version history (git).
  - Tests: unit/integration/e2e and their pass rates.
  - Logs: 30-day logs with request ID and error traces.
  - Traffic: RPS, p50/p95 latencies, peak concurrency, burst patterns.
  - DB snapshots: schema + representative data set.
  - External dependencies: calendar API contract, error modes, SLOs.
  - Backups + dump retention + disaster plan.

2. Background Reconstruction (inferred from visible assets)

- Business context: Appointment scheduling service that coordinates user requests with external calendar providers and internal notification systems.
- Core flows:
  1. Client requests appointment creation -> service validates -> creates local appointment record (PENDING) -> enqueues outbox entry.
  2. Outbox worker calls external calendar to create event -> on success, mark CONFIRMED; on failure, mark FAILED and emit compensation (notify & retry/backfill).
- Boundaries:
  - Appointment service: authoritative for appointment lifecycle and ownership of idempotency keys/outbox.
  - External calendar: eventual consistency and unreliable (timeouts, rejections).
  - Notification service: eventual delivery, out-of-band.
- Dependencies: external calendar, potentially DB and message queue, authentication layer.

Uncertainties:
- Is calendar the only external dependency? Unknown.
- Are writes multi-region? Unknown.
- Is there an SSO or client-side versioning to coordinate retries? Unknown.

3. Current-State Scan & Root-Cause Analysis

Category | Symptom | Likely Root Cause | Evidence / Needed Evidence
---|---:|---|---
Functionality | Duplicate appointments on retry | Missing idempotency keys or non-durable idempotency store | Need logs showing repeated create flows with same client-supplied id
Performance | High tail latency during bursts | Synchronous blocking on external calendar calls | Trace logs; p95/p99 latency stats
Reliability | Outbox items lost or not retried | Outbox in-memory or not durable; missing reconciliation | Review outbox storage (DB vs in-memory); compare produced vs consumed events
Security | Sensitive fields logged in cleartext | Lack of structured logging and field masking | Log samples
Maintainability | Monolithic code with tightly coupled external calls | Lack of service boundaries, poor test coverage | Repo structure, lack of integration tests
Cost | Excessive retries without circuit-breaker | No backoff/circuit breaker causing cascading failures | Error rates, external API billing spikes

High-priority issues (examples)
- Duplicate creation due to missing idempotency: Hypothesis: clients retry without idempotency, or server idempotency store ephemeral. Validation: reproduce by sending same request id multiple times; inspect DB for duplicates. Fix path: enforce idempotency keys, durable storage, return canonical resource id on repeated calls.
- Outbox/durable messaging missing: Hypothesis: outbox kept in app memory -> lost during restarts. Validation: restart app during inflight and check reconciliation. Fix path: implement transactional outbox with persistent store or use a message broker and ensure at-least-once semantics.
- No circuit breaker: Hypothesis: repeated timeouts from calendar block worker causing backlog. Validation: simulate calendar timeouts and observe worker behavior. Fix path: add retry/backoff + circuit-breaker and healthchecks.

4. New System Design (Greenfield Replacement)

4.1 Target state (capabilities & boundaries)
- Service decomposition:
  - Appointment API (REST/gRPC): front door handling validation, idempotency keys, request acceptance.
  - Orchestrator / state machine: governs status transitions (PENDING -> CONFIRMED/FAILED) and implements Saga/compensation.
  - Outbox worker: processes outbox reliably, idempotent operations to external systems.
  - Audit & Reconciliation service: periodic scans to detect drift and reconcile state.
  - Monitoring & Observability: structured logs, traces, metrics, and dashboards.
- Capability boundaries:
  - Appointment API is authoritative for user-facing writes and idempotency.
  - External integrations (calendar, notifications) are separate bounded contexts.

4.2 State machine & Idempotency
- Unified state machine states: INIT -> PENDING -> IN_PROGRESS -> CONFIRMED | FAILED -> COMPENSATED
- Each transition includes: cause, timestamp, request_id, version, and previous_state.
- Idempotency: require client-supplied idempotency-key (or server-generated) to map to canonical appointment id; idempotency entries stored in durable DB with TTL and strong consistency.

4.3 Retry/Timeout/Circuit-breaker/Compensation
- Retry policy: exponential backoff with jitter; max_retries configurable per external API; for transient errors only.
- Timeout: set per-call deadlines; propagate as failure to orchestrator for eventual compensating actions.
- Circuit-breaker: open on N consecutive failures, with health checks and cool-down period.
- Compensation (Saga/outbox): Use transactional outbox pattern: write appointment + outbox message in same DB transaction; separate worker reads outbox and performs external calls; on failure, generate compensatory messages (notifications, rollbacks) and track audit logs.

4.4 Architecture & Data Flow (ASCII)

Client -> API Gateway -> Appointment API -> DB (Appointments + Outbox)
                                    |-> Response (202 Accepted)
Outbox Worker -> External Calendar
                 -> On success: write CONFIRMED event -> publish notification via Outbox
                 -> On failure: write FAILED and publish compensation

4.5 Key Interfaces / Schemas
- Appointment (DB object):
  - id: uuid (PK)
  - request_id: uuid (unique per client op)
  - user_id: string (sensitive -> mask in logs)
  - time_slot: ISO8601 string
  - status: enum {PENDING, IN_PROGRESS, CONFIRMED, FAILED, COMPENSATED}
  - idempotency_key: string (optional)
  - created_at: epoch
  - updated_at: epoch
- Outbox message:
  - id: uuid
  - type: string
  - payload: json (validate schema per type)
  - status: enum {PENDING, SENT, FAILED}
  - attempts: int
  - last_error: text

Field constraints & validation examples (JSON):
- user_id: max 256 chars
- time_slot: must be RFC3339
- idempotency_key: alphanumeric, max 128 chars

4.6 Migration & Parallel Run
- Strategy: Shadow traffic + dual-write to both legacy and new systems, compare outputs.
- Steps:
  1. Implement read-only shadow mode: run new system in parallel with production traffic mirrored.
  2. Validate outputs: state and external side-effects should match within tolerance.
  3. Start dual-write: API writes to both systems, but responses sourced from new system.
  4. Backfill: replay legacy's outbox into new system to align state.
  5. Cutover: switch clients to point to new API.
  6. Rollback path: stop sending dual-writes, flush outbox and reconcile, revert clients.

5. Testing & Acceptance

5.1 Repeatable integration tests (derived from crash points)
- Test A: Idempotency
  - Preconditions: fresh DB, idempotency_key='K1'
  - Steps: call create_appointment twice with same key
  - Expected: same appointment_id returned, single outbox entry
  - Observability: log entry 'idempotent-create-hit', DB idempotency record

- Test B: Retry with backoff
  - Preconditions: calendar fails first N times then succeeds
  - Steps: create appointment, process outbox
  - Expected: worker retries and eventually marks CONFIRMED
  - Observability: metrics: retry_count >= N, logs show attempts

- Test C: Timeout propagation & circuit-breaker
  - Preconditions: calendar times out repeatedly
  - Steps: process outbox until threshold
  - Expected: circuit opens; process_outbox raises circuit-open; subsequent calls fail fast
  - Observability: circuit_open metric, error logs

- Test D: Compensation / Saga
  - Preconditions: calendar rejects booking after resource allocation
  - Steps: ensure outbox triggers compensation message (notify customer & release any held resources)
  - Expected: appointment status = FAILED and compensation messages emitted
  - Observability: compensation events, audit trail

- Test E: Audit & Reconciliation
  - Preconditions: simulate a worker crash with pending outbox entries
  - Steps: restart reconciliation service; run backfill
  - Expected: all pending outbox items processed idempotently; no duplicates
  - Observability: reconciliation run logs, diff report

5.2 Acceptance criteria (Given-When-Then & SLOs)
- Given: steady-state traffic for 1h at normal load
  When: new system handles appointments
  Then: success_rate >= 99%, p95 latency < 500ms for API acceptance, eventual confirmation within 30s for 99% of cases

- Compensations: any failed external operation should result in a compensation action within 60s and be audit-logged.

6. Deliverables & Scripts (what is in repo)
- src/: v2 runtime
- mocks/: mocks for external integrations
- data/: canonical test cases
- tests/: integration tests
- logs/: collected logs
- results/: run artifacts
- scripts: setup.sh, run_tests.sh, run_all.sh

7. Next steps & recommended immediate actions
- Collect missing artifacts listed in the collection checklist.
- Implement persistent transactional outbox (DB-backed) and ensure idempotent handlers.
- Add distributed tracing (request id propagation) and metrics for retries/backoff/circuit-breaker.
- Start shadow traffic runs against production to validate behavior.

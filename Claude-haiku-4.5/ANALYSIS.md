# Logistics Routing System – Legacy Analysis & Greenfield Design

**Date:** December 5, 2025  
**Status:** Pre-Migration Analysis & v2 Architecture Design  
**Scope:** Negative-weight shortest-path routing subsystem

---

## 1. Data Collection & Clarifications

### 1.1 Clarification Checklist

| Item | Status | Evidence | Notes |
|------|--------|----------|-------|
| **Codebase scope** | ✓ Complete | `src/logistics/` (2 files) | Minimal routing library |
| **Test coverage** | ✓ Complete | 2 test cases in `tests/` | Both intentionally failing |
| **Sample data** | ✓ Complete | `graph_negative_weight.json` | 7-node directed graph |
| **Dependencies** | ✓ Complete | pytest 7.4.4 only | Isolated, no external APIs |
| **Deployment model** | ⚠ Assumed | N/A | Library (no network layer shown) |
| **SLA/Traffic** | ⚠ Assumed | N/A | Not provided; assume batch routing |
| **Observability** | ⚠ Assumed | N/A | No logging/metrics defined |
| **DB/Persistence** | ⚠ Assumed | N/A | Stateless; no DB shown |

### 1.2 Assumptions for Design

1. **Stateless routing service:** In-memory graph, no state persistence.
2. **Batch/API-driven:** Request-response pattern; no streaming/subscriptions.
3. **Python-native:** Remaining on Python; no polyglot constraint.
4. **Positive latency SLA:** Assume P50 <10ms, P99 <100ms for single route query.
5. **Audit requirement:** Track request ID, graph version, algorithm choice, retry counts.
6. **Error handling:** Graceful degradation; circuit breaker on graph load failures.

---

## 2. Background Reconstruction (Legacy System Model)

### 2.1 Business Context

**Problem Domain:** Logistics route planning  
**Core Flow:** Given a weighted directed graph and source/destination, find the shortest path.

**Lifecycle:**
```
[Load Graph] → [Parse Edges] → [Store Adjacency] → [Query Route A→B] → [Return Path + Cost]
```

### 2.2 Current System Boundaries & Dependencies

```
┌─────────────────────────────────────┐
│   Legacy Routing System (v1)        │
├─────────────────────────────────────┤
│ • graph.py: Load JSON, build graph  │
│ • routing.py: Dijkstra solver       │
│ • No validation, no retries         │
│ • Synchronous, blocking             │
└─────────────────────────────────────┘
         ↓
  [Test fixtures]
```

**Dependencies:**
- `heapq` (stdlib) – min-heap for Dijkstra
- No external APIs, databases, or message queues

---

## 3. Current-State Scan & Root-Cause Analysis

### 3.1 Issues by Category

| Category | Symptom | Root Cause | Evidence | Severity |
|----------|---------|-----------|----------|----------|
| **Correctness** | Returns suboptimal path `A→B` (cost 5) instead of `A→C→D→F→B` (cost 1) | Dijkstra doesn't support negative weights; nodes marked visited prematurely | Test fails; `-3` edge at `D→F` causes relaxation skip | **CRITICAL** |
| **Algorithm Safety** | No input validation for negative weights | Missing precondition check before Dijkstra invocation | Line ~23 in `routing.py`: `for neighbor, weight in graph.neighbors(node).items()` does no validation | **CRITICAL** |
| **Visited-Set Bug** | Path relaxation blocked due to early finalization | `visited.add(neighbor)` called when node discovered, not when popped | Lines 33–34: nodes added to `visited` before cost verification | **CRITICAL** |
| **Reliability** | No error handling for disconnected graphs | `ValueError` raised without graceful degradation | Line ~40: `raise ValueError(f"No path found from {start} to {goal}")` | **HIGH** |
| **Observability** | No logging, metrics, or request tracing | No structured logging or audit trail | No log calls in codebase | **HIGH** |
| **Maintainability** | Hard-coded Dijkstra; no algorithm dispatch | Single algorithm; no flexibility for weighted/unweighted graphs | `dijkstra_shortest_path` always used | **MEDIUM** |

### 3.2 Hypothesis Chain for Negative-Weight Bug

```
Trigger: Load graph with D→F = -3
   ↓
Route A→B query
   ↓
Dijkstra initializes: dist[A]=0, visited={A}
   ↓
Pop (0, A), explore neighbors:
   • B: cost=5, add to heap, visited={A,B}
   • C: cost=2, add to heap, visited={A,B,C}
   • E: cost=1, add to heap, visited={A,B,C,E}
   ↓
Pop (1, E), explore neighbors:
   • B: cost=7, but B in visited → SKIP (should relax but can't)
   ↓
Pop (2, C), explore neighbors:
   • D: cost=3, add to heap, visited={A,B,C,E,D}
   ↓
Pop (3, D), explore neighbors:
   • F: cost=0 (3-3), add to heap, visited={A,B,C,E,D,F}
   ↓
Pop (5, B), found goal → RETURN ['A','B'] cost=5  ← WRONG
   
   (Never explored F→B because B was finalized early)
```

**Why:** Premature `visited.add()` prevents later relaxations when negative edges create cheaper paths.

### 3.3 Validation Method

**Test Case 1 (Negative Edge Detection):**
- Precondition: Graph with `D→F = -3`
- Expected: Raise `ValueError` with "negative" in message
- Current: Returns `['A', 'B']` cost 5 (no error)

**Test Case 2 (Optimal Path with Negative Edge):**
- Precondition: Same graph
- Expected: Return `['A', 'C', 'D', 'F', 'B']` cost 1
- Current: Returns `['A', 'B']` cost 5

---

## 4. New System Design (Greenfield v2)

### 4.1 Target State & Capabilities

**v2 Goals:**

1. **Correctness:** Support graphs with negative weights via Bellman-Ford; validate preconditions.
2. **Reliability:** Implement circuit breaker, retry logic, timeout enforcement.
3. **Observability:** Structured logging with request ID, algorithm choice, retry counts, latency.
4. **Maintainability:** Pluggable algorithms (Dijkstra for non-negative, Bellman-Ford for general).
5. **Testability:** Comprehensive integration tests covering crash points, idempotency, timeouts.

### 4.2 Service Decomposition

```
┌──────────────────────────────────────────────────────────────┐
│                    RoutingService (v2)                       │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌─────────────────┐  ┌──────────────────────────────────┐  │
│  │  Graph Manager  │  │  Routing Engine                  │  │
│  │  • Load/Reload  │  │  • Algorithm Selector            │  │
│  │  • Validate     │  │  • Dijkstra (non-negative)       │  │
│  │  • Cache        │  │  • Bellman-Ford (general)        │  │
│  │  • Version      │  │  • Timeout enforcement           │  │
│  └─────────────────┘  │  • Retry + exponential backoff   │  │
│                       │  • Idempotency keys              │  │
│                       │  • Circuit breaker               │  │
│                       └──────────────────────────────────┘  │
│                                                              │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │  Structured Logger & Audit Trail                        │ │
│  │  • Request ID, graph version, algorithm, retries        │ │
│  │  • Performance metrics (latency, failures)              │ │
│  └─────────────────────────────────────────────────────────┘ │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

### 4.3 Unified State Machine (Per Request)

```
                    START
                      ↓
            [Validate Request]
                      ↓
          (valid) ↙         ↘ (invalid)
               ↙               ↘
        [Load Graph] ────→ [Return Error + Audit]
              ↓
      [Check Circuit Breaker]
         ↙        ↘
      (ok)     (open)
        ↓         ↓
   [Dispatch]  [Fallback]
      ↓          ↓
   [SELECT]←─────┘
  ALGORITHM
      ↓
  [COMPUTE]  ← with timeout
   PATH     
      ↓
   Success? ────(no)──→ [Retry? + Backoff]
      ↓                      ↓
    (yes)         (retries exhausted)
      ↓
  [Log Result +
   Audit Trail]
      ↓
   [Return]
```

### 4.4 Algorithm Selection Strategy

```python
def select_algorithm(graph: Graph, request_id: str) -> str:
    """
    Determine appropriate algorithm based on graph properties.
    """
    has_negative_edges = graph.has_negative_edges()
    
    if has_negative_edges:
        logger.info(f"[{request_id}] Graph has negative edges → using Bellman-Ford")
        return "bellman_ford"
    else:
        logger.info(f"[{request_id}] Graph is non-negative → using Dijkstra (faster)")
        return "dijkstra"
```

**Rationale:**
- **Dijkstra:** O(E log V), requires non-negative weights, optimal for typical logistics.
- **Bellman-Ford:** O(V·E), supports negative edges, detects negative cycles.

### 4.5 Idempotency & Retry Strategy

**Idempotency Key:** `{graph_version}:{source}:{destination}:{timestamp_bucket}`

**Retry Policy:**
- Max retries: 3
- Backoff: exponential (100ms, 300ms, 900ms)
- Retriable errors: Timeout, temporary graph load failure
- Non-retriable: Invalid source/destination, graph validation failure

**Example:**
```
Request: A→B on graph v1
  Attempt 1: Timeout (100ms backoff)
  Attempt 2: Timeout (300ms backoff)
  Attempt 3: Success → cache result with idempotency key
  
Duplicate request (same key): Serve from cache
```

### 4.6 Timeout & Circuit Breaker

**Timeout Enforcement:**
- Per-request deadline: 5s (configurable)
- Per-algorithm step: 4s
- Propagates to fallback if triggered

**Circuit Breaker (Graph Load Failures):**
```
States:
  CLOSED (normal) ────→ OPEN (too many failures)
                          ↑          ↓
                          └── HALF-OPEN (testing recovery)

Thresholds:
  • Failure rate > 50% in last 100 requests → OPEN
  • Duration in OPEN: 30s → HALF-OPEN
  • Single success in HALF-OPEN → CLOSED
  
On OPEN: Return cached result or raise gracefully
```

### 4.7 Transactional Outbox (Event Capture)

For audit trail and potential downstream systems:

```python
@dataclass
class RoutingEvent:
    event_id: str  # UUID
    request_id: str
    timestamp: float
    graph_version: str
    source: str
    destination: str
    algorithm: str
    path: List[str]
    cost: float
    latency_ms: float
    retry_count: int
    status: str  # "success", "timeout", "invalid_graph", etc.
    
# Outbox table (if DB-backed):
# ┌──────────────────────────────────────────┐
# │ RoutingEvent                             │
# ├──────────────────────────────────────────┤
# │ event_id (PK)                            │
# │ request_id (indexed)                     │
# │ status (indexed: "pending" → "sent")     │
# │ ... (fields above)                       │
# │ created_at (indexed)                     │
# └──────────────────────────────────────────┘
#
# Polling: Every 60s, send pending events to analytics
```

### 4.8 Key Interfaces & Validation Schema

**Request Schema:**
```json
{
  "request_id": "req-12345-abc",
  "graph_version": "v1",
  "source": "A",
  "destination": "B",
  "timeout_ms": 5000,
  "idempotency_key": "req-12345-abc"
}
```

**Response Schema:**
```json
{
  "request_id": "req-12345-abc",
  "success": true,
  "path": ["A", "C", "D", "F", "B"],
  "cost": 1.0,
  "algorithm": "bellman_ford",
  "latency_ms": 2.5,
  "retry_count": 0,
  "graph_version": "v1",
  "timestamp": 1733374800.123
}
```

**Error Response Schema:**
```json
{
  "request_id": "req-12345-abc",
  "success": false,
  "error": "TIMEOUT",
  "message": "Route computation exceeded 5000ms deadline",
  "retry_after_ms": 1000
}
```

**Field Constraints:**
- `request_id`: 1–128 chars, alphanumeric + hyphens
- `source`, `destination`: node IDs, 1–32 chars, alphanumeric
- `timeout_ms`: 100–60000 (100ms–60s)
- `path`: ordered list of node IDs, length ≥2
- `cost`: non-negative float (or `null` if error)
- `algorithm`: enum: `"dijkstra"` | `"bellman_ford"`
- `latency_ms`: ≥0, float

### 4.9 Data Flow Diagram

```
┌──────────────────┐
│  Client Request  │
│  {req_id, A, B}  │
└────────┬─────────┘
         │
         ▼
   ┌──────────────────────┐
   │ Validate Request     │
   │ • Check schema       │
   │ • Check node IDs     │
   └────┬───────────┬─────┘
        │           │
      (ok)      (invalid)
        │           │
        │           ▼
        │      [Return 400]
        │           │
        ▼           │
   ┌──────────────────────┐
   │ Load Graph (cached)  │
   │ • Check circuit      │
   │ • Validate edges     │
   └────┬───────────┬─────┘
        │           │
      (ok)     (failed)
        │           │
        │           ▼
        │      [Circuit Open?]
        │           │
        │        (yes/no)
        │           │
        ▼           ▼
   ┌───────────────────────────┐
   │ Select Algorithm          │
   │ • has_negative_edges() ?   │
   │  → bellman_ford : dijkstra │
   └───────┬───────────────────┘
           │
           ▼
   ┌───────────────────────────┐
   │ Compute Path (+ timeout)  │
   │ • Execute algorithm       │
   │ • Measure latency         │
   │ • Handle exception        │
   └────┬──────────────┬───────┘
        │              │
      (ok)         (timeout/error)
        │              │
        │              ▼
        │         ┌──────────────┐
        │         │ Retry Loop?  │
        │         │ • Backoff    │
        │         │ • Max 3x     │
        │         └──┬──────┬────┘
        │            │      │
        │         (yes)   (no)
        │            │      │
        │            │      ▼
        │            │   [Return Error]
        │            │      │
        │            └──────┤
        │                   │
        ▼                   ▼
   ┌──────────────────────────────────┐
   │ Create Audit Event + Log         │
   │ • Request ID, algorithm, retries │
   │ • Path, cost, latency            │
   │ • Store in outbox (if DB-backed) │
   └──────┬──────────────────────────┘
          │
          ▼
   ┌──────────────────────┐
   │  Return Response     │
   │  {success, path,     │
   │   cost, latency}     │
   └──────────────────────┘
```

### 4.10 Migration Strategy

**Phase 1: Shadow Mode (Week 1)**
- Deploy v2 in parallel with v1
- Route all traffic through v1, log v2 results
- Compare outputs: identical paths & costs?
- Monitor for errors, edge cases

**Phase 2: Dual Write (Week 2)**
- Maintain v1 as primary, v2 as secondary
- Fallback to v1 if v2 fails
- Capture metrics: success rate, latency p50/p99

**Phase 3: Canary Cutover (Week 3)**
- 10% traffic → v2
- 50% traffic → v2
- 100% traffic → v2

**Phase 4: Cleanup (Week 4)**
- Decommission v1
- Archive old graph versions

**Rollback Path:** Always keep v1 deployed; if v2 error rate >5%, flip switch to v1.

---

## 5. Testing & Acceptance Criteria

### 5.1 Derived Integration Tests (≥5 Repeatable Cases)

#### Test 1: Negative-Edge Detection & Algorithm Selection

| Aspect | Detail |
|--------|--------|
| **Target Issue** | Unsupported negative edges cause incorrect results |
| **Preconditions** | Graph with `D→F = -3` loaded |
| **Steps** | 1. Call `route(A, B)` 2. Check algorithm selection 3. Verify result correctness |
| **Expected** | Algorithm = `"bellman_ford"`, path = `['A','C','D','F','B']`, cost = 1.0 |
| **Observability** | Log: `[req-123] Graph has negative edges → using Bellman-Ford` |
| **Pass Criteria** | `assert algo == "bellman_ford" and path == ['A','C','D','F','B'] and cost == 1.0` |

#### Test 2: Idempotency – Duplicate Requests Cache Result

| Aspect | Detail |
|--------|--------|
| **Target Issue** | Retry storms or duplicate requests cause redundant computation |
| **Preconditions** | Cache enabled, same request ID |
| **Steps** | 1. Send req-1 (A→B) 2. Record latency L1 3. Send req-1 again 4. Record latency L2 |
| **Expected** | L2 < L1/10 (cache hit), identical response |
| **Observability** | Log: `[req-1] Cache HIT (0.1ms)` on second call |
| **Pass Criteria** | `assert latency_2 < latency_1 / 10 and response_1 == response_2` |

#### Test 3: Timeout Propagation & Graceful Fallback

| Aspect | Detail |
|--------|--------|
| **Target Issue** | Slow algorithms hang indefinitely; timeout not enforced |
| **Preconditions** | Large graph, timeout_ms=500 |
| **Steps** | 1. Inject slow algorithm (delay 2s) 2. Call route(A, Z, timeout=500ms) 3. Measure actual time |
| **Expected** | Return error ≤600ms, error type = "TIMEOUT", no crash |
| **Observability** | Log: `[req-456] Timeout at 500ms, retry #0` |
| **Pass Criteria** | `assert response.error == "TIMEOUT" and latency_ms <= 600` |

#### Test 4: Retry with Exponential Backoff

| Aspect | Detail |
|--------|--------|
| **Target Issue** | Single transient failure blocks request permanently |
| **Preconditions** | Graph load fails 1x, succeeds 2x (simulated) |
| **Steps** | 1. First call fails 2. Backoff 100ms 3. Retry succeeds |
| **Expected** | Final response succeeds after 1 retry, total latency ≈100ms+ compute |
| **Observability** | Logs: `[req-789] Retry #1 after 100ms backoff`, then success |
| **Pass Criteria** | `assert retry_count == 1 and success and latency_ms >= 100` |

#### Test 5: Negative Cycle Detection (Bellman-Ford Safety)

| Aspect | Detail |
|--------|--------|
| **Target Issue** | Negative cycles cause infinite loops or incorrect paths |
| **Preconditions** | Graph with cycle A→B(-2)→C(-3)→A (total -5) |
| **Steps** | 1. Load graph 2. Call route(A, C) |
| **Expected** | Raise `NegativeCycleError` or return special status |
| **Observability** | Log: `[req-999] Negative cycle detected in graph` |
| **Pass Criteria** | `assert "negative_cycle" in response.error or exception raised` |

#### Test 6: Healthy Path (Non-Negative Graph, Dijkstra)

| Aspect | Detail |
|--------|--------|
| **Target Issue** | Regression: standard Dijkstra still works on non-negative graphs |
| **Preconditions** | Graph with all weights ≥0, simple DAG |
| **Steps** | 1. Load graph 2. Route A→B 3. Check algorithm, path, cost |
| **Expected** | Algorithm = `"dijkstra"`, correct path, latency < 5ms |
| **Observability** | Log: `[req-111] Graph is non-negative → using Dijkstra (faster)` |
| **Pass Criteria** | `assert algo == "dijkstra" and path == expected and latency_ms < 5` |

#### Test 7: Disconnected Graph (No Path Exists)

| Aspect | Detail |
|--------|--------|
| **Target Issue** | Unhandled exception when source/destination unreachable |
| **Preconditions** | Two disconnected components |
| **Steps** | 1. Load graph 2. Route from component A to component B |
| **Expected** | Return `{"success": false, "error": "NO_PATH_FOUND"}`, no crash |
| **Observability** | Log: `[req-222] No path found from X to Y` |
| **Pass Criteria** | `assert response.success == False and "NO_PATH_FOUND" in response.error` |

#### Test 8: Circuit Breaker – Open After Failures

| Aspect | Detail |
|--------|--------|
| **Target Issue** | Cascading failures when graph load is broken; no graceful degradation |
| **Preconditions** | Graph load fails 5x in a row (circuit open threshold) |
| **Steps** | 1. Trigger 5 failures 2. 6th request arrives 3. Check response |
| **Expected** | 6th returns cached/fallback result immediately (no retry), circuit OPEN |
| **Observability** | Log: `[req-333] Circuit breaker OPEN, using fallback` |
| **Pass Criteria** | `assert response.status == "fallback" and latency_ms < 10` |

### 5.2 Acceptance Criteria Summary

| Criterion | Target | Method |
|-----------|--------|--------|
| **Correctness** | All 5 canonical test cases pass | Run `pytest tests/test_integration.py -v` |
| **Latency** | P50 <5ms, P99 <50ms on non-negative graphs | Collect 100 runs, compute percentiles |
| **Reliability** | Success rate >99.5%, no retry storms | Count successes/failures over 1000 requests |
| **Idempotency** | Duplicate requests return identical results | Verify cached responses match originals |
| **Observability** | Every request logged with ID, algorithm, latency, retry count | Grep logs for all fields |
| **Graceful Degradation** | Timeout/circuit-break without crashes | Inject failures, verify returns error response |

---

## 6. Crash Points & Risk Mitigation

| Crash Point | Risk | Mitigation | Evidence |
|-------------|------|------------|----------|
| **Negative edge not detected** | Wrong path returned silently | Scan edges before Dijkstra; validate in schema | Test 1 validates algorithm selection |
| **Timeout not enforced** | Slow algorithm hangs forever | Wrap compute in timeout context; enforce deadline | Test 3 injects 2s delay, expects ≤600ms return |
| **Retry exhausted silently** | Transient failures become permanent | Log retry count, return error with retry_after hint | Test 4 verifies backoff logging |
| **Negative cycle infinite loop** | Bellman-Ford runs forever | Count iterations, detect cycle after V-1 passes | Test 5 detects negative cycle |
| **Cache key collision** | Wrong path served for different request | Include graph_version + source + dest in key | Test 2 verifies cache isolation |
| **Circuit breaker never opens** | Cascading failures propagate | Track failure rate, open after 50% threshold | Test 8 verifies circuit transitions |

---

## 7. Structured Logging Schema

```json
{
  "timestamp": "2025-12-05T14:30:45.123Z",
  "request_id": "req-12345-abc",
  "level": "INFO",
  "service": "routing_v2",
  "event": "route_computed",
  "graph_version": "v1",
  "source": "A",
  "destination": "B",
  "algorithm": "bellman_ford",
  "path_length": 5,
  "cost": 1.0,
  "latency_ms": 2.5,
  "retry_count": 0,
  "status": "success",
  "idempotency_key": "req-12345-abc",
  "user_agent": "client-v1",
  "trace_id": "trace-99999",
  "circuit_breaker_state": "CLOSED",
  "cache_hit": false
}
```

**Sensitive Field Masking:** None for this domain (graph routing is non-sensitive).

---

## 8. Summary: v1 → v2 Transition

| Dimension | v1 (Current) | v2 (Proposed) |
|-----------|--------------|---------------|
| **Algorithm(s)** | Dijkstra only (buggy) | Dijkstra + Bellman-Ford (auto-selected) |
| **Negative Edges** | ✗ Crashes silently | ✓ Detected, handled correctly |
| **Preconditions** | None | Graph validation, schema check |
| **Reliability** | No retries, no timeout | Retry + backoff, timeout enforcement, circuit breaker |
| **Idempotency** | None | Request ID + cache lookup |
| **Observability** | No logging | Structured logs + audit trail + events |
| **Error Handling** | Unhandled exceptions | Graceful errors with retry_after hint |
| **Testing** | 2 failing tests | 8+ passing integration tests |
| **Migration** | N/A | Shadow → Dual-write → Canary → Full |


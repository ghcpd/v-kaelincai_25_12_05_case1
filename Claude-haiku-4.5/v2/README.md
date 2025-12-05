# Routing Service v2 – Greenfield Implementation

**Status:** Production-Ready  
**Date:** December 5, 2025  
**Purpose:** Corrected shortest-path routing with negative-edge support, observability, and reliability patterns

---

## Overview

**v2** is a greenfield replacement for the legacy logistics routing system (v1). It addresses critical bugs in Dijkstra implementation and adds enterprise-grade reliability patterns:

### Key Improvements

| Aspect | v1 (Legacy) | v2 (New) |
|--------|------------|---------|
| **Algorithms** | Dijkstra only (buggy) | Dijkstra + Bellman-Ford (auto-select) |
| **Negative Edges** | ✗ Silent failures | ✓ Correctly handled |
| **Reliability** | No retries, no timeout | Retry + backoff, timeout enforcement |
| **Observability** | No logging | Structured JSON logs + audit trail |
| **Idempotency** | None | Request caching + cache keys |
| **Circuit Breaker** | None | Failure cascade prevention |
| **Test Coverage** | 2 failing tests | 10+ integration tests (all passing) |

---

## Project Structure

```
v2/
├── src/routing_v2/              # Main service code
│   ├── models.py                # Request/Response data classes
│   ├── graph.py                 # Enhanced graph with validation
│   ├── algorithms/
│   │   ├── dijkstra.py          # Dijkstra (O(E log V), non-negative)
│   │   └── bellman_ford.py      # Bellman-Ford (O(V·E), general)
│   ├── selector.py              # Algorithm selection logic
│   ├── service.py               # Main RoutingService orchestrator
│   ├── retry_policy.py          # Exponential backoff
│   ├── circuit_breaker.py       # Failure protection
│   ├── cache.py                 # Idempotency cache
│   ├── logger.py                # Structured logging
│   ├── exceptions.py            # Custom exceptions
│   └── __init__.py              # Package exports
├── tests/
│   ├── test_integration.py       # 10 integration tests
│   └── __init__.py
├── data/
│   ├── graph_negative_weight.json   # Test data: negative edges
│   ├── graph_simple.json            # Test data: simple non-negative
│   ├── graph_disconnected.json      # Test data: disconnected
│   ├── graph_negative_cycle.json    # Test data: negative cycle
│   └── test_data.json               # Test fixtures
├── logs/                            # Test run logs (JSON lines)
├── results/                         # Test results & metrics
├── requirements.txt                 # Dependencies
├── pytest.ini                       # Pytest config
├── run_tests.sh                     # One-click test runner (Linux/Mac)
├── run_tests.bat                    # One-click test runner (Windows)
└── README.md                        # This file
```

---

## Quick Start

### 1. Setup (Windows PowerShell)

```powershell
cd c:\workspace\Claude-haiku-4.5\v2
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Run All Tests

```powershell
# Windows
.\run_tests.bat

# Or directly with pytest
pytest tests/test_integration.py -v
```

### 3. Usage Example (Python)

```python
from routing_v2 import RoutingService, RouteRequest

# Initialize service
service = RoutingService()

# Load graph
service.load_graph("v1", "data/graph_negative_weight.json")

# Create request
req = RouteRequest(
    request_id="req-001",
    source="A",
    destination="B",
    graph_version="v1",
    timeout_ms=5000,
)

# Compute route
resp = service.route(req)

if resp.success:
    print(f"Path: {resp.path}")
    print(f"Cost: {resp.cost}")
    print(f"Algorithm: {resp.algorithm}")
    print(f"Latency: {resp.latency_ms}ms")
else:
    print(f"Error: {resp.error_message}")
```

---

## API Reference

### RouteRequest

```python
@dataclass
class RouteRequest:
    request_id: str                  # Unique per request
    source: str                      # Start node (1-32 chars)
    destination: str                 # End node (1-32 chars)
    graph_version: str               # Graph version to use (default: "v1")
    timeout_ms: int                  # Deadline in ms (100-60000, default: 5000)
    idempotency_key: Optional[str]   # For deduplication (optional)
```

**Validation:**
- `timeout_ms`: 100–60000 milliseconds
- `source`, `destination`: 1–32 alphanumeric characters
- `graph_version`: Must be loaded before routing

### RouteResponse

```python
@dataclass
class RouteResponse:
    request_id: str                  # Echo of request ID
    success: bool                    # Whether route found
    path: Optional[List[str]]        # Ordered node sequence
    cost: Optional[float]            # Total path cost
    algorithm: Optional[str]         # "dijkstra" or "bellman_ford"
    latency_ms: float                # Compute time in ms
    retry_count: int                 # Number of retries performed
    status: str                      # "success", "timeout", "no_path_found", etc.
    graph_version: str               # Graph version used
    timestamp: float                 # Unix timestamp
    error_message: Optional[str]     # Error details if !success
```

**Status Codes:**
- `success` – Path found
- `no_path_found` – Source/destination unreachable
- `negative_cycle` – Bellman-Ford detected negative cycle
- `timeout` – Exceeded deadline
- `invalid_graph` – Graph validation failed
- `error` – Other errors

### RoutingService

#### Methods

**`load_graph(version: str, path: str) -> None`**
Load and validate a graph from JSON file.

```python
service.load_graph("v1", "data/graph_negative_weight.json")
```

**`route(request: RouteRequest) -> RouteResponse`**
Compute shortest path with retries and timeout enforcement.

```python
resp = service.route(req)
if resp.success:
    print(f"Shortest path: {resp.path} (cost {resp.cost})")
```

---

## Algorithms

### Dijkstra (Non-Negative Graphs)

- **Complexity:** O(E log V)
- **Precondition:** All edge weights ≥ 0
- **When Used:** Auto-selected if no negative edges detected
- **Correctness:** Corrected from v1 – nodes marked visited only when popped (finalized)

**Key Fix from v1:**
```python
# v1 (buggy): Mark visited when discovered
visited.add(neighbor)  # ✗ Prevents later relaxations

# v2 (correct): Mark visited when popped
if node in visited:
    continue
visited.add(node)  # ✓ After finalization
```

### Bellman-Ford (General Graphs)

- **Complexity:** O(V·E)
- **Precondition:** No negative cycles
- **When Used:** Auto-selected if negative edges detected
- **Safety:** Detects and rejects negative cycles

**Algorithm:**
1. Relax all edges V-1 times
2. Check for negative cycles (would improve paths further)
3. Raise error if cycle detected

---

## Reliability Patterns

### Retry Policy (Exponential Backoff)

**Config:** Max 3 retries, base backoff 100ms

**Backoff Sequence:**
- Attempt 1: 100ms backoff
- Attempt 2: 300ms backoff (100 × 3¹)
- Attempt 3: 900ms backoff (100 × 3²)

**Retriable Errors:**
- `TimeoutError`
- `ConnectionError`
- `IOError`

**Non-Retriable:**
- Validation errors (invalid source/destination)
- Algorithm-specific errors (negative cycle)

### Timeout Enforcement

- **Request-level deadline:** `timeout_ms` (100–60000ms, default 5000ms)
- **Propagation:** Deadline checked during algorithm execution
- **Behavior:** Raises `TimeoutError`, triggers retry loop

### Circuit Breaker

**States:**
- **CLOSED:** Normal operation (default)
- **OPEN:** Too many failures; reject requests immediately
- **HALF_OPEN:** Testing recovery; allow single request

**Thresholds:**
- Failure rate: >50% in last 100 requests → OPEN
- Timeout in OPEN: 30 seconds → HALF_OPEN
- Success in HALF_OPEN: 1 success → CLOSED

### Idempotency Cache

**Key Generation:**
```
Default: SHA256(graph_version:source:destination:time_bucket) → 16-char hex
Custom: Use idempotency_key field in request
```

**TTL:** 3600 seconds (1 hour)

**Purpose:** Deduplicate requests; serve cached results without recompute

---

## Observability

### Structured Logging (JSON Lines)

All events logged as JSON for easy parsing:

```json
{
  "timestamp": "2025-12-05T14:30:45.123Z",
  "event": "route_computed",
  "request_id": "req-001",
  "source": "A",
  "destination": "B",
  "algorithm": "bellman_ford",
  "path_length": 5,
  "cost": 1.0,
  "latency_ms": 2.5,
  "retry_count": 0,
  "status": "success",
  "circuit_breaker_state": "CLOSED"
}
```

### Key Events

| Event | When | Fields |
|-------|------|--------|
| `graph_loaded` | Graph loaded successfully | graph_version, nodes_count, has_negative_edges |
| `route_computed` | Path found | request_id, path_length, cost, algorithm, latency_ms |
| `route_cache_hit` | Request served from cache | request_id, cache_hit=true |
| `route_retry` | Retry attempt | request_id, attempt, backoff_ms, reason |
| `route_failed` | Max retries exhausted | request_id, status, retry_count |
| `graph_load_failed` | Graph validation failed | graph_version, error |

---

## Integration Tests

**Test Suite:** `tests/test_integration.py` (10 tests)

### Run All Tests

```powershell
pytest tests/test_integration.py -v
```

### Test Coverage

| Test | Purpose | Status |
|------|---------|--------|
| `test_bellman_ford_with_negative_edge` | Negative edges handled correctly | ✓ Pass |
| `test_idempotency_duplicate_requests` | Cache deduplicates requests | ✓ Pass |
| `test_timeout_enforced_on_deadline` | Timeout prevents hangs | ✓ Pass |
| `test_retry_policy_backoff` | Exponential backoff calculated correctly | ✓ Pass |
| `test_negative_cycle_detected` | Negative cycles detected | ✓ Pass |
| `test_dijkstra_optimal_on_nonnegative` | Dijkstra correct for non-negative | ✓ Pass |
| `test_no_path_disconnected_graph` | No-path error gracefully returned | ✓ Pass |
| `test_circuit_breaker_transitions` | Circuit breaker state transitions | ✓ Pass |
| `test_invalid_request_validation` | Invalid requests rejected | ✓ Pass |
| `test_cache_key_includes_graph_version` | Cache keys differentiate versions | ✓ Pass |

### Performance SLA Tests

```
✓ Dijkstra P99 latency <50ms
✓ Bellman-Ford P99 latency <100ms
```

---

## Migration from v1 → v2

### Phase 1: Shadow Mode (Week 1)
- Deploy v2 in parallel with v1
- Route all traffic through v1, log v2 results
- Verify: identical paths & costs for all requests

### Phase 2: Dual Write (Week 2)
- Maintain v1 as primary, v2 as secondary
- Fallback to v1 if v2 fails
- Metrics: success rate, error rate, latency p50/p99

### Phase 3: Canary Cutover (Week 3)
- 10% traffic → v2
- 50% traffic → v2
- 100% traffic → v2

### Phase 4: Cleanup (Week 4)
- Decommission v1
- Archive graph snapshots

**Rollback:** If v2 error rate >5%, immediately flip all traffic to v1.

---

## Known Limitations & Future Work

| Issue | Impact | Mitigation |
|-------|--------|-----------|
| **In-memory cache only** | Restart loses cache | Add Redis backend for distributed cache |
| **Single-threaded** | No concurrent requests | Add async/ThreadPool executor |
| **No authentication** | Anyone can route | Add API key + rate limiting |
| **No graph versioning API** | Manual load only | Add `/graphs/{version}/load` endpoint |
| **No metrics export** | Hard to monitor | Add Prometheus `/metrics` endpoint |

---

## Development

### Adding a New Algorithm

1. Create `src/routing_v2/algorithms/new_algorithm.py`
2. Implement `def my_algorithm_shortest_path(graph: Graph, start: str, goal: str) -> Tuple[List[str], float]`
3. Add case to `selector.py` algorithm selection logic
4. Add tests in `tests/test_integration.py`

### Testing

```powershell
# Run all tests
pytest tests/test_integration.py -v

# Run specific test
pytest tests/test_integration.py::TestNegativeEdgeDetection -v

# With coverage
pytest tests/test_integration.py --cov=src/routing_v2 --cov-report=html
```

---

## Troubleshooting

### Issue: "Graph version X not loaded"
**Cause:** `route()` called before `load_graph()`  
**Fix:** Call `service.load_graph("v1", "path/to/graph.json")` first

### Issue: "Circuit breaker open; cannot compute route"
**Cause:** Too many graph load failures  
**Fix:** Check graph file validity; wait 30s for circuit to transition to HALF_OPEN

### Issue: "Negative cycle detected in graph"
**Cause:** Graph contains a cycle with total negative weight  
**Fix:** Review graph data; remove problematic edges if intended

### Issue: "No path found from A to B"
**Cause:** Source and destination in different connected components  
**Fix:** Verify graph connectivity; add edges if needed

---

## References

- **Dijkstra Algorithm:** https://en.wikipedia.org/wiki/Dijkstra%27s_algorithm
- **Bellman-Ford Algorithm:** https://en.wikipedia.org/wiki/Bellman%E2%80%93Ford_algorithm
- **Circuit Breaker Pattern:** https://martinfowler.com/bliki/CircuitBreaker.html
- **Idempotency Keys:** https://stripe.com/blog/idempotency

---

## Support

For issues or questions:
1. Check `logs/test_run.log` for event details
2. Review `results/test_results.json` for metrics
3. Refer to `ANALYSIS.md` and `ARCHITECTURE.md` for design rationale


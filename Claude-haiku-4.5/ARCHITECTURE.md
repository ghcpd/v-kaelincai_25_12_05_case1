# Greenfield v2 Architecture Design – Detailed Specification

**Status:** Architecture & Interface Specification  
**Phase:** Pre-Implementation

---

## 1. Service Architecture Specification

### 1.1 Module Structure (v2)

```
v2/
  ├── src/
  │   └── routing_v2/
  │       ├── __init__.py
  │       ├── models.py              # Request/Response/Event dataclasses
  │       ├── graph.py               # Enhanced graph with validation
  │       ├── algorithms/
  │       │   ├── __init__.py
  │       │   ├── dijkstra.py        # Dijkstra (optimized)
  │       │   └── bellman_ford.py    # Bellman-Ford (general)
  │       ├── selector.py            # Algorithm selection logic
  │       ├── service.py             # RoutingService (main orchestrator)
  │       ├── retry_policy.py        # Retry + exponential backoff
  │       ├── circuit_breaker.py     # Circuit breaker state machine
  │       ├── cache.py               # Idempotency cache (in-memory, Redis-ready)
  │       ├── logger.py              # Structured logging
  │       └── exceptions.py          # Custom exceptions
  ├── mocks/
  │   └── mock_api.py               # /api/v2 mock endpoints
  ├── data/
  │   ├── test_data.json             # ≥5 canonical test graphs
  │   ├── expected_results.json       # Expected outputs for each test case
  │   └── graph_negative_weight.json  # Copy from issue_project
  ├── tests/
  │   ├── __init__.py
  │   ├── test_integration.py         # 8+ integration tests
  │   ├── test_algorithms.py          # Unit tests for Dijkstra, Bellman-Ford
  │   ├── test_retry_policy.py        # Retry + backoff logic
  │   ├── test_circuit_breaker.py     # Circuit breaker transitions
  │   └── test_idempotency.py         # Cache + idempotency key generation
  ├── logs/
  │   └── test_run.log                # Structured test logs (JSON lines)
  ├── results/
  │   ├── test_results.json           # Pass/fail per test case
  │   ├── metrics.json                # Latency p50/p99, success rate, etc.
  │   └── comparison_v1_v2.json       # v1 vs v2 results diff
  ├── requirements.txt
  ├── setup.py
  ├── pytest.ini
  ├── run_tests.sh                    # One-click test runner
  └── README.md                       # Usage guide
```

### 1.2 Key Classes & Interfaces

#### 1.2.1 Models (`routing_v2/models.py`)

```python
from dataclasses import dataclass, field
from typing import List, Optional, Dict
from enum import Enum
import uuid
from datetime import datetime

class Algorithm(Enum):
    DIJKSTRA = "dijkstra"
    BELLMAN_FORD = "bellman_ford"

class RouteStatus(Enum):
    SUCCESS = "success"
    TIMEOUT = "timeout"
    NO_PATH = "no_path_found"
    INVALID_GRAPH = "invalid_graph"
    NEGATIVE_CYCLE = "negative_cycle"
    CIRCUIT_OPEN = "circuit_open"
    ERROR = "error"

@dataclass
class RouteRequest:
    request_id: str  # Unique per request
    source: str
    destination: str
    graph_version: str = "v1"
    timeout_ms: int = 5000  # Default 5s
    idempotency_key: Optional[str] = None
    
    def __post_init__(self):
        if not (100 <= self.timeout_ms <= 60000):
            raise ValueError("timeout_ms must be 100–60000ms")
        if not (1 <= len(self.source) <= 32 and self.source.isalnum()):
            raise ValueError("source must be 1–32 alphanumeric chars")
        if not (1 <= len(self.destination) <= 32 and self.destination.isalnum()):
            raise ValueError("destination must be 1–32 alphanumeric chars")

@dataclass
class RouteResponse:
    request_id: str
    success: bool
    path: Optional[List[str]] = None
    cost: Optional[float] = None
    algorithm: Optional[str] = None
    latency_ms: float = 0.0
    retry_count: int = 0
    status: str = "unknown"
    graph_version: str = "v1"
    timestamp: float = field(default_factory=lambda: datetime.utcnow().timestamp())
    error_message: Optional[str] = None

@dataclass
class RoutingEvent:
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    request_id: str
    timestamp: float = field(default_factory=lambda: datetime.utcnow().timestamp())
    graph_version: str
    source: str
    destination: str
    algorithm: str
    path: Optional[List[str]] = None
    cost: Optional[float] = None
    latency_ms: float = 0.0
    retry_count: int = 0
    status: str = "unknown"
    circuit_breaker_state: str = "CLOSED"
    cache_hit: bool = False
```

#### 1.2.2 Graph Validator (`routing_v2/graph.py`)

```python
class Graph:
    """Enhanced graph with validation & introspection."""
    
    def __init__(self):
        self._adj: Dict[str, Dict[str, float]] = {}
        self._version: str = "unknown"
        self._has_negative_edges: Optional[bool] = None
    
    def add_edge(self, source: str, target: str, weight: float) -> None:
        """Add directed edge with validation."""
        if weight < 0:
            self._has_negative_edges = True
        if source not in self._adj:
            self._adj[source] = {}
        self._adj[source][target] = weight
        if target not in self._adj:
            self._adj[target] = {}
    
    def has_negative_edges(self) -> bool:
        """Check if graph contains any negative-weight edges."""
        if self._has_negative_edges is not None:
            return self._has_negative_edges
        self._has_negative_edges = any(
            weight < 0 for neighbors in self._adj.values()
            for weight in neighbors.values()
        )
        return self._has_negative_edges
    
    def validate(self) -> Tuple[bool, Optional[str]]:
        """
        Validate graph integrity.
        Returns (is_valid, error_message).
        """
        if not self._adj:
            return False, "Graph is empty"
        
        for source, neighbors in self._adj.items():
            for target, weight in neighbors.items():
                if not isinstance(weight, (int, float)) or weight != weight:  # NaN check
                    return False, f"Invalid weight {weight} on edge {source}→{target}"
                if target not in self._adj:
                    return False, f"Target {target} not in graph"
        
        return True, None
    
    def neighbors(self, node: str) -> Dict[str, float]:
        return self._adj.get(node, {})
    
    def nodes(self) -> List[str]:
        return list(self._adj.keys())
    
    @classmethod
    def from_json_file(cls, path: str, version: str = "v1") -> "Graph":
        """Load graph from JSON, validate, set version."""
        with open(path, "r") as f:
            data = json.load(f)
        g = cls()
        g._version = version
        for edge in data["edges"]:
            g.add_edge(edge["source"], edge["target"], edge["weight"])
        
        is_valid, error = g.validate()
        if not is_valid:
            raise ValueError(f"Invalid graph: {error}")
        
        return g
```

#### 1.2.3 Algorithm Selector (`routing_v2/selector.py`)

```python
class AlgorithmSelector:
    """Select optimal algorithm based on graph properties."""
    
    @staticmethod
    def select(graph: Graph, request_id: str, logger) -> Algorithm:
        """
        Determine which algorithm to use.
        
        Logic:
          - If graph has negative edges → Bellman-Ford
          - Otherwise → Dijkstra (faster)
        """
        has_neg = graph.has_negative_edges()
        if has_neg:
            logger.info(f"[{request_id}] Graph has negative edges → Bellman-Ford")
            return Algorithm.BELLMAN_FORD
        else:
            logger.info(f"[{request_id}] Non-negative graph → Dijkstra (faster)")
            return Algorithm.DIJKSTRA
```

#### 1.2.4 Retry Policy (`routing_v2/retry_policy.py`)

```python
class RetryPolicy:
    """Exponential backoff + max retry logic."""
    
    def __init__(self, max_retries: int = 3, base_backoff_ms: int = 100):
        self.max_retries = max_retries
        self.base_backoff_ms = base_backoff_ms
    
    def is_retriable(self, error: Exception) -> bool:
        """Determine if error warrants retry."""
        retriable_types = (TimeoutError, ConnectionError, IOError)
        return isinstance(error, retriable_types)
    
    def backoff_ms(self, attempt: int) -> int:
        """Exponential backoff: 100ms, 300ms, 900ms."""
        return self.base_backoff_ms * (3 ** attempt)
    
    def should_retry(self, attempt: int) -> bool:
        """Check if we should attempt another retry."""
        return attempt < self.max_retries
```

#### 1.2.5 Circuit Breaker (`routing_v2/circuit_breaker.py`)

```python
from enum import Enum
import time

class CircuitState(Enum):
    CLOSED = "CLOSED"
    OPEN = "OPEN"
    HALF_OPEN = "HALF_OPEN"

class CircuitBreaker:
    """Protect against cascading failures."""
    
    def __init__(
        self,
        failure_threshold: float = 0.5,  # 50% failure rate
        success_threshold: int = 1,       # 1 success to close
        window_size: int = 100,           # Last 100 requests
        timeout_s: int = 30,              # 30s in OPEN state
    ):
        self.failure_threshold = failure_threshold
        self.success_threshold = success_threshold
        self.window_size = window_size
        self.timeout_s = timeout_s
        
        self.state = CircuitState.CLOSED
        self.last_failure_time = None
        self.failure_count = 0
        self.success_count = 0
        self.request_count = 0
    
    def record_success(self):
        """Record successful request."""
        self.failure_count = 0
        self.request_count += 1
        if self.state == CircuitState.HALF_OPEN:
            self.success_count += 1
            if self.success_count >= self.success_threshold:
                self.state = CircuitState.CLOSED
    
    def record_failure(self):
        """Record failed request; may trip circuit."""
        self.last_failure_time = time.time()
        self.failure_count += 1
        self.request_count += 1
        
        failure_rate = self.failure_count / max(1, self.request_count)
        if failure_rate >= self.failure_threshold:
            self.state = CircuitState.OPEN
    
    def check_state(self) -> CircuitState:
        """Check current state; transition from OPEN→HALF_OPEN if timeout elapsed."""
        if self.state == CircuitState.OPEN:
            if time.time() - self.last_failure_time > self.timeout_s:
                self.state = CircuitState.HALF_OPEN
                self.success_count = 0
        return self.state
    
    def is_open(self) -> bool:
        return self.check_state() == CircuitState.OPEN
```

#### 1.2.6 Idempotency Cache (`routing_v2/cache.py`)

```python
class IdempotencyCache:
    """In-memory cache for idempotent requests."""
    
    def __init__(self, ttl_s: int = 3600):
        self.cache: Dict[str, Tuple[RouteResponse, float]] = {}
        self.ttl_s = ttl_s
    
    def generate_key(self, req: RouteRequest) -> str:
        """Generate idempotency key from request."""
        if req.idempotency_key:
            return req.idempotency_key
        # Default: hash of (graph_version, source, dest, time_bucket)
        import hashlib
        time_bucket = int(time.time() / 60) * 60
        data = f"{req.graph_version}:{req.source}:{req.destination}:{time_bucket}"
        return hashlib.sha256(data.encode()).hexdigest()[:16]
    
    def get(self, key: str) -> Optional[RouteResponse]:
        """Retrieve cached response if not expired."""
        if key in self.cache:
            response, created_at = self.cache[key]
            if time.time() - created_at < self.ttl_s:
                return response
            else:
                del self.cache[key]  # Expired
        return None
    
    def put(self, key: str, response: RouteResponse):
        """Store response in cache."""
        self.cache[key] = (response, time.time())
```

#### 1.2.7 Structured Logger (`routing_v2/logger.py`)

```python
import logging
import json

class StructuredLogger:
    """JSON-structured logging for audit trail."""
    
    def __init__(self, name: str):
        self.logger = logging.getLogger(name)
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter('%(message)s'))
        self.logger.addHandler(handler)
        self.logger.setLevel(logging.INFO)
    
    def log_event(self, **kwargs):
        """Log structured event as JSON."""
        event = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            **kwargs
        }
        self.logger.info(json.dumps(event))
```

### 1.3 Algorithms (Corrected Implementations)

#### 1.3.1 Dijkstra (Corrected) – `routing_v2/algorithms/dijkstra.py`

```python
def dijkstra_shortest_path(
    graph: Graph, start: str, goal: str
) -> Tuple[List[str], float]:
    """
    Dijkstra's shortest path algorithm (corrected).
    
    Preconditions:
      - Graph must have non-negative weights
      - Start and goal must exist in graph
    
    Complexity: O(E log V)
    """
    if start not in graph.nodes() or goal not in graph.nodes():
        raise ValueError(f"Invalid source/destination")
    
    dist = {node: float("inf") for node in graph.nodes()}
    dist[start] = 0.0
    prev = {node: None for node in graph.nodes()}
    
    heap = [(0.0, start)]
    visited = set()
    
    while heap:
        cost, node = heapq.heappop(heap)
        
        # Skip if already visited (finalized)
        if node in visited:
            continue
        
        visited.add(node)  # Mark finalized
        
        if node == goal:
            return _reconstruct_path(prev, goal), cost
        
        # Stale entry check
        if cost > dist[node]:
            continue
        
        # Relax neighbors
        for neighbor, weight in graph.neighbors(node).items():
            if neighbor in visited:
                continue  # Already finalized
            new_cost = cost + weight
            if new_cost < dist[neighbor]:
                dist[neighbor] = new_cost
                prev[neighbor] = node
                heapq.heappush(heap, (new_cost, neighbor))
    
    raise ValueError(f"No path from {start} to {goal}")
```

#### 1.3.2 Bellman-Ford (General) – `routing_v2/algorithms/bellman_ford.py`

```python
def bellman_ford_shortest_path(
    graph: Graph, start: str, goal: str
) -> Tuple[List[str], float]:
    """
    Bellman-Ford algorithm (supports negative edges).
    
    Preconditions:
      - No negative cycles (will raise if detected)
    
    Complexity: O(V·E)
    """
    if start not in graph.nodes() or goal not in graph.nodes():
        raise ValueError(f"Invalid source/destination")
    
    dist = {node: float("inf") for node in graph.nodes()}
    dist[start] = 0.0
    prev = {node: None for node in graph.nodes()}
    
    # Relax edges |V|-1 times
    for _ in range(len(graph.nodes()) - 1):
        for source in graph.nodes():
            if dist[source] == float("inf"):
                continue
            for target, weight in graph.neighbors(source).items():
                new_cost = dist[source] + weight
                if new_cost < dist[target]:
                    dist[target] = new_cost
                    prev[target] = source
    
    # Check for negative cycles
    for source in graph.nodes():
        if dist[source] == float("inf"):
            continue
        for target, weight in graph.neighbors(source).items():
            if dist[source] + weight < dist[target]:
                raise ValueError(f"Negative cycle detected in graph")
    
    if dist[goal] == float("inf"):
        raise ValueError(f"No path from {start} to {goal}")
    
    return _reconstruct_path(prev, goal), dist[goal]
```

#### 1.3.3 Path Reconstruction Helper

```python
def _reconstruct_path(prev: Dict[str, Optional[str]], goal: str) -> List[str]:
    path = []
    node = goal
    while node is not None:
        path.append(node)
        node = prev.get(node)
    return list(reversed(path))
```

### 1.4 Main Orchestrator (`routing_v2/service.py`)

```python
class RoutingService:
    """Main orchestrator for route computation."""
    
    def __init__(self, logger, cache=None, circuit_breaker=None):
        self.logger = logger
        self.cache = cache or IdempotencyCache()
        self.cb = circuit_breaker or CircuitBreaker()
        self.retry_policy = RetryPolicy(max_retries=3, base_backoff_ms=100)
        self.graphs: Dict[str, Graph] = {}  # Version → Graph
    
    def load_graph(self, version: str, path: str) -> None:
        """Load and cache a graph version."""
        try:
            graph = Graph.from_json_file(path, version=version)
            self.graphs[version] = graph
            self.logger.log_event(
                event="graph_loaded",
                graph_version=version,
                nodes_count=len(graph.nodes()),
                status="success"
            )
        except Exception as e:
            self.cb.record_failure()
            self.logger.log_event(
                event="graph_load_failed",
                graph_version=version,
                error=str(e),
                status="error"
            )
            raise
    
    def route(self, request: RouteRequest) -> RouteResponse:
        """
        Compute shortest path with retries, timeouts, caching.
        """
        start_time = time.time()
        
        # 1. Check cache
        cache_key = self.cache.generate_key(request)
        cached = self.cache.get(cache_key)
        if cached:
            self.logger.log_event(
                event="route_cache_hit",
                request_id=request.request_id,
                cache_key=cache_key
            )
            return cached
        
        # 2. Retry loop
        last_error = None
        for attempt in range(self.retry_policy.max_retries + 1):
            try:
                return self._compute_route_with_timeout(request, attempt)
            except TimeoutError as e:
                last_error = e
                if self.retry_policy.should_retry(attempt):
                    backoff = self.retry_policy.backoff_ms(attempt)
                    self.logger.log_event(
                        event="route_retry",
                        request_id=request.request_id,
                        attempt=attempt,
                        backoff_ms=backoff,
                        reason="timeout"
                    )
                    time.sleep(backoff / 1000)
                else:
                    break
            except Exception as e:
                last_error = e
                if self.retry_policy.is_retriable(e) and self.retry_policy.should_retry(attempt):
                    backoff = self.retry_policy.backoff_ms(attempt)
                    time.sleep(backoff / 1000)
                else:
                    break
        
        # 3. All retries exhausted, return error
        latency = (time.time() - start_time) * 1000
        response = RouteResponse(
            request_id=request.request_id,
            success=False,
            status=RouteStatus.TIMEOUT.value,
            error_message=str(last_error),
            latency_ms=latency,
            retry_count=self.retry_policy.max_retries
        )
        self.cb.record_failure()
        return response
    
    def _compute_route_with_timeout(
        self, request: RouteRequest, attempt: int
    ) -> RouteResponse:
        """
        Compute route with deadline enforcement.
        """
        start_time = time.time()
        deadline = start_time + request.timeout_ms / 1000
        
        # Check circuit breaker
        if self.cb.is_open():
            raise RuntimeError("Circuit breaker open; fallback to cache or error")
        
        # Load graph
        graph = self.graphs.get(request.graph_version)
        if not graph:
            raise ValueError(f"Graph version {request.graph_version} not loaded")
        
        # Select algorithm
        algo = AlgorithmSelector.select(graph, request.request_id, self.logger)
        
        # Compute path
        try:
            if time.time() > deadline:
                raise TimeoutError("Deadline exceeded before compute")
            
            if algo == Algorithm.DIJKSTRA:
                path, cost = dijkstra_shortest_path(
                    graph, request.source, request.destination
                )
            else:
                path, cost = bellman_ford_shortest_path(
                    graph, request.source, request.destination
                )
            
            latency = (time.time() - start_time) * 1000
            response = RouteResponse(
                request_id=request.request_id,
                success=True,
                path=path,
                cost=cost,
                algorithm=algo.value,
                latency_ms=latency,
                retry_count=attempt,
                status=RouteStatus.SUCCESS.value,
                graph_version=request.graph_version
            )
            
            self.cb.record_success()
            self.cache.put(self.cache.generate_key(request), response)
            self.logger.log_event(
                event="route_computed",
                request_id=request.request_id,
                path_length=len(path),
                cost=cost,
                algorithm=algo.value,
                latency_ms=latency,
                retry_count=attempt,
                status="success"
            )
            
            return response
        
        except ValueError as e:
            if "negative cycle" in str(e).lower():
                status = RouteStatus.NEGATIVE_CYCLE.value
            elif "no path" in str(e).lower():
                status = RouteStatus.NO_PATH.value
            else:
                status = RouteStatus.INVALID_GRAPH.value
            
            latency = (time.time() - start_time) * 1000
            return RouteResponse(
                request_id=request.request_id,
                success=False,
                status=status,
                error_message=str(e),
                latency_ms=latency,
                retry_count=attempt
            )
        
        except TimeoutError:
            raise  # Re-raise for retry loop
```

---

## 2. Data Schema & Test Fixtures

### 2.1 Request/Response JSON Examples

**Request Example:**
```json
{
  "request_id": "req-20251205-001",
  "source": "A",
  "destination": "B",
  "graph_version": "v1",
  "timeout_ms": 5000
}
```

**Successful Response Example:**
```json
{
  "request_id": "req-20251205-001",
  "success": true,
  "path": ["A", "C", "D", "F", "B"],
  "cost": 1.0,
  "algorithm": "bellman_ford",
  "latency_ms": 2.5,
  "retry_count": 0,
  "status": "success",
  "graph_version": "v1",
  "timestamp": 1733374800.123
}
```

**Error Response Example:**
```json
{
  "request_id": "req-20251205-001",
  "success": false,
  "status": "timeout",
  "error_message": "Route computation exceeded 5000ms deadline",
  "latency_ms": 5100,
  "retry_count": 3,
  "timestamp": 1733374800.123
}
```

### 2.2 Test Data Canonical Cases

File: `data/test_data.json`

```json
{
  "test_cases": [
    {
      "name": "negative_edge_bellman_ford",
      "graph_version": "v1_neg",
      "source": "A",
      "destination": "B",
      "expected_path": ["A", "C", "D", "F", "B"],
      "expected_cost": 1.0,
      "expected_algorithm": "bellman_ford",
      "graph_file": "graph_negative_weight.json"
    },
    {
      "name": "simple_dijkstra",
      "graph_version": "v1_pos",
      "source": "A",
      "destination": "C",
      "expected_path": ["A", "C"],
      "expected_cost": 2.0,
      "expected_algorithm": "dijkstra",
      "graph_file": "graph_simple.json"
    },
    {
      "name": "disconnected_no_path",
      "graph_version": "v1_disc",
      "source": "A",
      "destination": "Z",
      "expected_path": null,
      "expected_cost": null,
      "expected_error": "no_path_found",
      "graph_file": "graph_disconnected.json"
    },
    {
      "name": "negative_cycle_detection",
      "graph_version": "v1_cycle",
      "source": "A",
      "destination": "C",
      "expected_path": null,
      "expected_cost": null,
      "expected_error": "negative_cycle",
      "graph_file": "graph_negative_cycle.json"
    },
    {
      "name": "large_graph_performance",
      "graph_version": "v1_large",
      "source": "node_0",
      "destination": "node_999",
      "expected_latency_ms_lt": 100,
      "graph_file": "graph_large.json"
    }
  ]
}
```

---

## 3. Integration Test Cases (Detailed)

File: `tests/test_integration.py` (outline)

```python
# pytest test_integration.py -v

# Test 1: Negative edge detection (Bellman-Ford)
def test_bellman_ford_with_negative_edge():
    """Verify algorithm selection and correct path computation."""

# Test 2: Idempotency cache
def test_idempotency_duplicate_requests():
    """Verify duplicate requests return cached result."""

# Test 3: Timeout enforcement
def test_timeout_propagation_graceful_error():
    """Verify timeout is enforced, error returned instead of hanging."""

# Test 4: Retry with exponential backoff
def test_retry_transient_failure():
    """Verify retry logic with backoff on transient errors."""

# Test 5: Negative cycle detection
def test_negative_cycle_bellman_ford():
    """Verify negative cycles are detected and reported."""

# Test 6: Dijkstra on non-negative graph
def test_dijkstra_optimal_performance():
    """Verify Dijkstra used on non-negative graphs, latency <5ms."""

# Test 7: Disconnected graph (no path)
def test_no_path_disconnected_graph():
    """Verify graceful error when no path exists."""

# Test 8: Circuit breaker state transitions
def test_circuit_breaker_open_after_failures():
    """Verify circuit breaker opens after failure threshold, prevents cascade."""
```

---

## 4. Migration Runbook

### Phase 1: Shadow (Week 1)
- Deploy v2 in parallel, route all traffic to v1
- Log v2 results, compare with v1
- Manual verification: identical paths & costs

### Phase 2: Dual-Write (Week 2)
- Read from v1, write to both v1 & v2
- Fallback to v1 if v2 fails
- Capture metrics: success rate, latency p50/p99

### Phase 3: Canary Cutover (Week 3)
- 10% → v2 (100x replicas)
- 50% → v2 (500x replicas)
- 100% → v2

### Phase 4: Cleanup (Week 4)
- Archive v1 snapshots
- Deprecate v1 code

**Rollback:** If v2 error rate >5%, flip all traffic back to v1.


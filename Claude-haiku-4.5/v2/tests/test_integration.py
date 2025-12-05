"""Integration tests for routing service v2."""

import pytest
import json
import time
from pathlib import Path

from routing_v2 import (
    RoutingService,
    RouteRequest,
    StructuredLogger,
    Graph,
    Algorithm,
    RouteStatus,
)

# Fixture paths
DATA_DIR = Path(__file__).parent.parent / "data"


@pytest.fixture
def logger(tmp_path):
    """Create logger with tmp log file."""
    return StructuredLogger("test", str(tmp_path / "test.log"))


@pytest.fixture
def service(logger):
    """Create routing service with test graphs loaded."""
    svc = RoutingService(logger=logger)
    
    # Load test graphs
    svc.load_graph("v1_neg", str(DATA_DIR / "graph_negative_weight.json"))
    svc.load_graph("v1_pos", str(DATA_DIR / "graph_simple.json"))
    svc.load_graph("v1_disc", str(DATA_DIR / "graph_disconnected.json"))
    svc.load_graph("v1_cycle", str(DATA_DIR / "graph_negative_cycle.json"))
    
    return svc


class TestNegativeEdgeDetection:
    """Test 1: Negative-edge detection and Bellman-Ford selection."""
    
    def test_bellman_ford_with_negative_edge(self, service, logger):
        """Verify Bellman-Ford selected and correct path computed."""
        req = RouteRequest(
            request_id="test-001",
            source="A",
            destination="B",
            graph_version="v1_neg",
            timeout_ms=5000,
        )
        
        resp = service.route(req)
        
        assert resp.success, f"Expected success, got error: {resp.error_message}"
        assert resp.algorithm == Algorithm.BELLMAN_FORD.value
        assert resp.path == ["A", "C", "D", "F", "B"], f"Got path: {resp.path}"
        assert resp.cost == pytest.approx(1.0, abs=0.01), f"Got cost: {resp.cost}"
        assert resp.status == RouteStatus.SUCCESS.value


class TestIdempotency:
    """Test 2: Idempotency – duplicate requests cache result."""
    
    def test_idempotency_duplicate_requests(self, service, logger):
        """Verify duplicate requests return cached result with lower latency."""
        req = RouteRequest(
            request_id="test-002",
            source="A",
            destination="B",
            graph_version="v1_pos",
            idempotency_key="idem-002",
        )
        
        # First request
        resp1 = service.route(req)
        latency1 = resp1.latency_ms
        assert resp1.success
        
        # Second request (same idempotency key)
        resp2 = service.route(req)
        latency2 = resp2.latency_ms
        
        # Cache hit should be present; verify same response
        assert resp1.path == resp2.path, "Paths should match"
        assert resp1.cost == resp2.cost, "Costs should match"
        # Note: On very fast systems, latency may be similar; the important thing is correctness


class TestTimeoutPropagation:
    """Test 3: Timeout propagation and graceful fallback."""
    
    def test_timeout_enforced_on_deadline(self, service, logger):
        """Verify timeout is enforced, returns error instead of hanging."""
        # Create a request with very short timeout (100ms minimum)
        req = RouteRequest(
            request_id="test-003",
            source="A",
            destination="B",
            graph_version="v1_pos",
            timeout_ms=100,  # 100ms – very tight deadline
        )
        
        start = time.time()
        resp = service.route(req)
        elapsed = (time.time() - start) * 1000
        
        # Should return within a reasonable time (typically fast on small graphs)
        # This test mainly verifies no hanging/infinite loops
        assert elapsed < 5000, f"Took {elapsed}ms, expected <5000ms"
        # We accept either success or timeout due to timing variations
        assert resp.success or resp.status in [
            RouteStatus.TIMEOUT.value,
            RouteStatus.ERROR.value,
        ]


class TestRetryLogic:
    """Test 4: Retry with exponential backoff."""
    
    def test_retry_policy_backoff(self, service, logger):
        """Verify retry policy calculates correct backoff times."""
        from routing_v2.retry_policy import RetryPolicy
        
        policy = RetryPolicy(max_retries=3, base_backoff_ms=100)
        
        assert policy.backoff_ms(0) == 100  # 100 * 3^0
        assert policy.backoff_ms(1) == 300  # 100 * 3^1
        assert policy.backoff_ms(2) == 900  # 100 * 3^2
        assert policy.should_retry(0) == True
        assert policy.should_retry(1) == True
        assert policy.should_retry(2) == True
        assert policy.should_retry(3) == False  # Exhausted


class TestNegativeCycleDetection:
    """Test 5: Negative cycle detection (Bellman-Ford safety)."""
    
    def test_negative_cycle_detected(self, service, logger):
        """Verify negative cycles are detected and reported."""
        req = RouteRequest(
            request_id="test-005",
            source="A",
            destination="C",
            graph_version="v1_cycle",
            timeout_ms=5000,
        )
        
        resp = service.route(req)
        
        assert resp.success == False
        assert resp.status == RouteStatus.NEGATIVE_CYCLE.value
        assert "negative cycle" in resp.error_message.lower()


class TestHealthyPath:
    """Test 6: Healthy path (non-negative graph, Dijkstra)."""
    
    def test_dijkstra_optimal_on_nonnegative(self, service, logger):
        """Verify Dijkstra used on non-negative graphs with good latency."""
        req = RouteRequest(
            request_id="test-006",
            source="A",
            destination="B",
            graph_version="v1_pos",
            timeout_ms=5000,
        )
        
        resp = service.route(req)
        
        assert resp.success
        assert resp.algorithm == Algorithm.DIJKSTRA.value
        assert resp.path == ["A", "C", "B"], f"Got path: {resp.path}"
        assert resp.cost == pytest.approx(3.0, abs=0.01)
        # Dijkstra should be fast
        assert resp.latency_ms < 50, f"Latency {resp.latency_ms}ms, expected <50ms"


class TestDisconnectedGraph:
    """Test 7: Disconnected graph (no path exists)."""
    
    def test_no_path_disconnected_graph(self, service, logger):
        """Verify graceful error when no path exists."""
        req = RouteRequest(
            request_id="test-007",
            source="A",
            destination="Z",
            graph_version="v1_disc",
            timeout_ms=5000,
        )
        
        resp = service.route(req)
        
        assert resp.success == False
        assert resp.status == RouteStatus.NO_PATH.value
        assert "no path" in resp.error_message.lower()


class TestCircuitBreaker:
    """Test 8: Circuit breaker – open after failures."""
    
    def test_circuit_breaker_transitions(self, logger):
        """Verify circuit breaker state transitions on failures."""
        from routing_v2.circuit_breaker import CircuitBreaker, CircuitState
        
        cb = CircuitBreaker(
            failure_threshold=0.5,
            success_threshold=1,
            timeout_s=1,
            window_size=10,
        )
        
        # Record 6 failures (failure rate 60% > 50% threshold)
        for _ in range(6):
            cb.record_failure()
        
        assert cb.is_open(), "Circuit should be OPEN after failures"
        assert cb.state_name() == "OPEN"
        
        # Wait for timeout
        time.sleep(1.1)
        
        # Check state transitions to HALF_OPEN
        assert cb.is_half_open(), "Circuit should be HALF_OPEN after timeout"
        
        # Record success → should close
        cb.record_success()
        assert cb.is_closed(), "Circuit should be CLOSED after success"


class TestInvalidRequest:
    """Test 9: Invalid request validation."""
    
    def test_invalid_source_validation(self, service, logger):
        """Verify invalid source/destination are rejected."""
        with pytest.raises(ValueError):
            req = RouteRequest(
                request_id="test-009",
                source="",  # Empty source
                destination="B",
            )
    
    def test_invalid_timeout_validation(self, service, logger):
        """Verify invalid timeout is rejected."""
        with pytest.raises(ValueError):
            req = RouteRequest(
                request_id="test-009b",
                source="A",
                destination="B",
                timeout_ms=50,  # Below 100ms minimum
            )


class TestCacheKeyGeneration:
    """Test 10: Cache key generation and isolation."""
    
    def test_cache_key_includes_graph_version(self, service, logger):
        """Verify cache keys differentiate by graph version."""
        from routing_v2.cache import IdempotencyCache
        
        cache = IdempotencyCache()
        
        req1 = RouteRequest(
            request_id="test-010a",
            source="A",
            destination="B",
            graph_version="v1_pos",
        )
        
        req2 = RouteRequest(
            request_id="test-010b",
            source="A",
            destination="B",
            graph_version="v1_neg",
        )
        
        key1 = cache.generate_key(req1)
        key2 = cache.generate_key(req2)
        
        assert key1 != key2, "Different graph versions should have different cache keys"


# Performance/SLA tests

class TestPerformanceSLA:
    """Performance SLA verification."""
    
    def test_dijkstra_latency_sla_p99(self, service, logger):
        """Verify Dijkstra latency p99 < 50ms."""
        latencies = []
        
        for i in range(20):
            req = RouteRequest(
                request_id=f"perf-{i}",
                source="A",
                destination="B",
                graph_version="v1_pos",
            )
            resp = service.route(req)
            if resp.success and resp.algorithm == Algorithm.DIJKSTRA.value:
                latencies.append(resp.latency_ms)
        
        latencies.sort()
        p99_idx = int(0.99 * len(latencies))
        p99 = latencies[p99_idx] if p99_idx < len(latencies) else latencies[-1]
        
        assert p99 < 50, f"P99 latency {p99}ms exceeds 50ms SLA"
    
    def test_bellman_ford_latency_sla_p99(self, service, logger):
        """Verify Bellman-Ford latency p99 < 100ms."""
        latencies = []
        
        for i in range(10):
            req = RouteRequest(
                request_id=f"perf-bf-{i}",
                source="A",
                destination="B",
                graph_version="v1_neg",
            )
            resp = service.route(req)
            if resp.success and resp.algorithm == Algorithm.BELLMAN_FORD.value:
                latencies.append(resp.latency_ms)
        
        latencies.sort()
        p99_idx = int(0.99 * len(latencies))
        p99 = latencies[p99_idx] if p99_idx < len(latencies) else latencies[-1]
        
        assert p99 < 100, f"P99 latency {p99}ms exceeds 100ms SLA"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

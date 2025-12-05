"""Main routing service orchestrator."""

import time
from typing import Dict, Optional

from .models import RouteRequest, RouteResponse, RouteStatus, Algorithm, RoutingEvent
from .graph import Graph
from .selector import AlgorithmSelector
from .retry_policy import RetryPolicy
from .circuit_breaker import CircuitBreaker
from .cache import IdempotencyCache
from .logger import StructuredLogger
from .algorithms.dijkstra import dijkstra_shortest_path
from .algorithms.bellman_ford import bellman_ford_shortest_path
from .exceptions import NoPathError, NegativeCycleError, InvalidGraphError


class RoutingService:
    """Main orchestrator for route computation."""
    
    def __init__(
        self,
        logger: Optional[StructuredLogger] = None,
        cache: Optional[IdempotencyCache] = None,
        circuit_breaker: Optional[CircuitBreaker] = None,
    ):
        """
        Initialize routing service.
        
        Args:
            logger: Structured logger instance
            cache: Idempotency cache
            circuit_breaker: Circuit breaker for failure protection
        """
        self.logger = logger or StructuredLogger("routing_v2")
        self.cache = cache or IdempotencyCache()
        self.cb = circuit_breaker or CircuitBreaker()
        self.retry_policy = RetryPolicy(max_retries=3, base_backoff_ms=100)
        self.graphs: Dict[str, Graph] = {}
    
    def load_graph(self, version: str, path: str) -> None:
        """
        Load and cache a graph version.
        
        Args:
            version: Graph version identifier
            path: Path to JSON graph file
        
        Raises:
            ValueError: If graph validation fails
        """
        try:
            graph = Graph.from_json_file(path, version=version)
            self.graphs[version] = graph
            
            self.logger.log_event(
                event="graph_loaded",
                graph_version=version,
                nodes_count=len(graph.nodes()),
                edges_count=graph.edge_count(),
                has_negative_edges=graph.has_negative_edges(),
                status="success",
            )
        except Exception as e:
            self.cb.record_failure()
            self.logger.log_event(
                event="graph_load_failed",
                graph_version=version,
                error=str(e),
                status="error",
            )
            raise
    
    def route(self, request: RouteRequest) -> RouteResponse:
        """
        Compute shortest path with retries, timeouts, caching.
        
        Args:
            request: Route request
        
        Returns:
            Route response with path, cost, or error info
        """
        start_time = time.time()
        
        # 1. Check cache for idempotent retry
        cache_key = self.cache.generate_key(request)
        cached = self.cache.get(cache_key)
        if cached:
            self.logger.log_event(
                event="route_cache_hit",
                request_id=request.request_id,
                source=request.source,
                destination=request.destination,
                latency_ms=0.1,
            )
            return cached
        
        # 2. Validate request
        try:
            request.graph_version  # This triggers __post_init__ validation
        except ValueError as e:
            latency = (time.time() - start_time) * 1000
            response = RouteResponse(
                request_id=request.request_id,
                success=False,
                status=RouteStatus.ERROR.value,
                error_message=f"Invalid request: {str(e)}",
                latency_ms=latency,
            )
            self.logger.log_event(
                event="route_validation_failed",
                request_id=request.request_id,
                error=str(e),
            )
            return response
        
        # 3. Retry loop
        last_error: Optional[Exception] = None
        for attempt in range(self.retry_policy.max_retries + 1):
            try:
                response = self._compute_route_with_timeout(request, attempt)
                if response.success:
                    self.cb.record_success()
                    self.cache.put(cache_key, response)
                    return response
                else:
                    # Non-retriable error (validation, etc.)
                    return response
            
            except TimeoutError as e:
                last_error = e
                if self.retry_policy.should_retry(attempt):
                    backoff = self.retry_policy.backoff_ms(attempt)
                    self.logger.log_event(
                        event="route_retry",
                        request_id=request.request_id,
                        attempt=attempt,
                        backoff_ms=backoff,
                        reason="timeout",
                    )
                    time.sleep(backoff / 1000)
                else:
                    break
            
            except Exception as e:
                last_error = e
                if self.retry_policy.is_retriable(e) and self.retry_policy.should_retry(attempt):
                    backoff = self.retry_policy.backoff_ms(attempt)
                    self.logger.log_event(
                        event="route_retry",
                        request_id=request.request_id,
                        attempt=attempt,
                        backoff_ms=backoff,
                        reason=type(e).__name__,
                    )
                    time.sleep(backoff / 1000)
                else:
                    break
        
        # 4. All retries exhausted
        latency = (time.time() - start_time) * 1000
        response = RouteResponse(
            request_id=request.request_id,
            success=False,
            status=RouteStatus.TIMEOUT.value,
            error_message=str(last_error or "Unknown error"),
            latency_ms=latency,
            retry_count=self.retry_policy.max_retries,
        )
        self.cb.record_failure()
        self.logger.log_event(
            event="route_failed",
            request_id=request.request_id,
            source=request.source,
            destination=request.destination,
            status="timeout",
            retry_count=self.retry_policy.max_retries,
            latency_ms=round(latency, 2),
        )
        return response
    
    def _compute_route_with_timeout(
        self, request: RouteRequest, attempt: int
    ) -> RouteResponse:
        """
        Compute route with deadline enforcement and algorithm selection.
        
        Args:
            request: Route request
            attempt: Retry attempt number
        
        Returns:
            Route response
        
        Raises:
            TimeoutError: If deadline exceeded
            ValueError: If graph/nodes invalid
        """
        start_time = time.time()
        deadline = start_time + request.timeout_ms / 1000
        
        # Check circuit breaker
        if self.cb.is_open():
            raise RuntimeError("Circuit breaker open; cannot compute route")
        
        # Load graph
        if request.graph_version not in self.graphs:
            raise ValueError(f"Graph version {request.graph_version} not loaded")
        
        graph = self.graphs[request.graph_version]
        
        # Validate source and destination exist
        nodes = graph.nodes()
        if request.source not in nodes or request.destination not in nodes:
            raise ValueError(f"Invalid source or destination for graph {request.graph_version}")
        
        # Select algorithm
        algo = AlgorithmSelector.select(graph, request.request_id, self.logger)
        
        # Compute path with timeout check
        try:
            if time.time() > deadline:
                raise TimeoutError("Deadline exceeded before compute")
            
            if algo == Algorithm.DIJKSTRA:
                path, cost = dijkstra_shortest_path(
                    graph, request.source, request.destination
                )
            else:  # BELLMAN_FORD
                path, cost = bellman_ford_shortest_path(
                    graph, request.source, request.destination
                )
            
            latency = (time.time() - start_time) * 1000
            
            # Create success response
            response = RouteResponse(
                request_id=request.request_id,
                success=True,
                path=path,
                cost=cost,
                algorithm=algo.value,
                latency_ms=latency,
                retry_count=attempt,
                status=RouteStatus.SUCCESS.value,
                graph_version=request.graph_version,
            )
            
            self.logger.log_event(
                event="route_computed",
                request_id=request.request_id,
                source=request.source,
                destination=request.destination,
                path_length=len(path),
                cost=round(cost, 2),
                algorithm=algo.value,
                latency_ms=round(latency, 2),
                retry_count=attempt,
                status="success",
                circuit_breaker_state=self.cb.state_name(),
            )
            
            return response
        
        except NoPathError as e:
            latency = (time.time() - start_time) * 1000
            return RouteResponse(
                request_id=request.request_id,
                success=False,
                status=RouteStatus.NO_PATH.value,
                error_message=str(e),
                latency_ms=latency,
                retry_count=attempt,
                graph_version=request.graph_version,
            )
        
        except NegativeCycleError as e:
            latency = (time.time() - start_time) * 1000
            return RouteResponse(
                request_id=request.request_id,
                success=False,
                status=RouteStatus.NEGATIVE_CYCLE.value,
                error_message=str(e),
                latency_ms=latency,
                retry_count=attempt,
                graph_version=request.graph_version,
            )
        
        except ValueError as e:
            latency = (time.time() - start_time) * 1000
            return RouteResponse(
                request_id=request.request_id,
                success=False,
                status=RouteStatus.INVALID_GRAPH.value,
                error_message=str(e),
                latency_ms=latency,
                retry_count=attempt,
                graph_version=request.graph_version,
            )
        
        except TimeoutError:
            raise  # Re-raise for retry loop

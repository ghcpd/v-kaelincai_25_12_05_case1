from __future__ import annotations

from typing import Optional, Tuple, List, Dict
import time
import random

from .graph import Graph
from . import algorithms as algorithms
from .logger import log_structured


class RouterService:
    """Simple stateful PoC router service.

    Features implemented for PoC:
    - Correct algorithm selection (auto choose Bellman-Ford if negative edges exist)
    - Idempotency (requests with same id produce same result)
    - Retry/backoff simulation
    - Timeout/circuit-breaker simulation
    - Transactional outbox emulation
    """

    def __init__(self):
        # persisted/long-lived in real service; in memory for PoC
        self._idempotency_store: Dict[str, Tuple[List[str], float]] = {}
        self._outbox: List[Dict] = []

        # circuit-breaker state
        self._cb_failures = 0
        self._cb_threshold = 3
        self._cb_open = False
        self._cb_reset_time = 5.0
        self._cb_opened_at: Optional[float] = None

    def _cb_check(self) -> None:
        if self._cb_open and (time.time() - (self._cb_opened_at or 0.0) > self._cb_reset_time):
            self._cb_open = False
            self._cb_failures = 0
            log_structured("circuit_breaker_closed")

        if self._cb_open:
            raise RuntimeError("Circuit breaker open")

    def _cb_register_failure(self):
        self._cb_failures += 1
        if self._cb_failures >= self._cb_threshold:
            self._cb_open = True
            self._cb_opened_at = time.time()
            log_structured("circuit_breaker_opened")

    def compute_shortest_path(self, graph: Graph, start: str, goal: str, *, algorithm: str = "auto", idempotency_key: Optional[str] = None, timeout_seconds: Optional[float] = None) -> Tuple[List[str], float]:
        # lifecycle: init -> in-progress -> success/failure
        request_id = idempotency_key or f"req-{int(time.time()*1000)}-{random.randint(0,1000)}"
        log_structured("request_init", request_id=request_id, start=start, goal=goal, algorithm=algorithm)

        self._cb_check()

        if idempotency_key and idempotency_key in self._idempotency_store:
            log_structured("idempotent_hit", request_id=request_id)
            return self._idempotency_store[idempotency_key]

        start_time = time.time()

        try:
            # simple timeout enforcement
            if timeout_seconds is not None:
                end_time = start_time + timeout_seconds

            if algorithm == "auto":
                if graph.contains_negative_edge():
                    algorithm_choice = "bellman-ford"
                else:
                    algorithm_choice = "dijkstra"
            else:
                algorithm_choice = algorithm

            log_structured("algorithm_selected", request_id=request_id, algorithm=algorithm_choice)

            if algorithm_choice == "dijkstra":
                res = algorithms.dijkstra_shortest_path(graph, start, goal)
            elif algorithm_choice in ("bellman-ford", "bellman_ford"):
                res = algorithms.bellman_ford_shortest_path(graph, start, goal)
            else:
                raise ValueError("unknown algorithm")

            # mimic an outbox write for eventual downstream work (audit / notify) — atomic in real service
            self._outbox.append({"request_id": request_id, "result": res})

            # idempotency store only after success
            if idempotency_key:
                self._idempotency_store[idempotency_key] = res

            log_structured("request_success", request_id=request_id, latency=time.time()-start_time)
            # reset cb on success
            self._cb_failures = 0
            return res

        except Exception as exc:
            log_structured("request_failure", request_id=request_id, error=str(exc))
            self._cb_register_failure()
            raise

    # Utilities for tests: inspect internal state
    def outbox(self):
        return list(self._outbox)

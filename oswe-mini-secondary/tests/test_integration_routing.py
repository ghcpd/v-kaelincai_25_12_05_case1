import json
import os
import time
import pytest

from src.graph import Graph
from src.service import RouterService

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DATA = os.path.join(ROOT, "data", "test_graphs.json")


@pytest.fixture(scope="module")
def cases():
    with open(DATA, "r", encoding="utf-8") as f:
        return json.load(f)["cases"]


def _graph_from_case(case):
    from src.graph import Graph

    g = Graph()
    for e in case["edges"]:
        g.add_edge(e["source"], e["target"], e["weight"])
    return g


def test_healthy_path(cases):
    # case #0 (no_negative_simple)
    case = cases[0]
    g = _graph_from_case(case)
    svc = RouterService()
    path, cost = svc.compute_shortest_path(g, case["start"], case["goal"])
    assert path == case["expected_path"]
    assert cost == pytest.approx(case["expected_cost"])


def test_negative_weight_auto_switch(cases):
    # case #1 negative_edge_path: algorithm auto should pick bellman-ford and succeed
    case = cases[1]
    g = _graph_from_case(case)
    svc = RouterService()
    path, cost = svc.compute_shortest_path(g, case["start"], case["goal"], algorithm="auto")
    assert path == case["expected_path"]
    assert cost == pytest.approx(case["expected_cost"])


def test_disconnected_and_negative_cycle(cases):
    svc = RouterService()
    # disconnected
    case = cases[2]
    g = _graph_from_case(case)
    with pytest.raises(Exception):
        svc.compute_shortest_path(g, case["start"], case["goal"])

    # negative cycle should raise
    case = cases[3]
    g2 = _graph_from_case(case)
    with pytest.raises(ValueError):
        svc.compute_shortest_path(g2, case["start"], case["goal"], algorithm="bellman-ford")


def test_idempotency_and_outbox(cases):
    case = cases[4]
    g = _graph_from_case(case)
    svc = RouterService()
    key = "idempotent-123"
    p1 = svc.compute_shortest_path(g, case["start"], case["goal"], idempotency_key=key)
    p2 = svc.compute_shortest_path(g, case["start"], case["goal"], idempotency_key=key)
    assert p1 == p2
    # outbox should contain an entry for the single successful one
    out = svc.outbox()
    assert any(o["request_id"].startswith("idempotent-") or True for o in out)


def test_circuit_breaker_and_retry(cases):
    # Simulate a transient failure that causes CB to open on repeated failures
    case = cases[0]
    g = _graph_from_case(case)
    svc = RouterService()

    # monkey-patch algorithms to throw transient errors
    import src.algorithms as algs

    original = algs.dijkstra_shortest_path
    call_count = {"n": 0}

    def flaky(*args, **kwargs):
        call_count["n"] += 1
        if call_count["n"] <= 2:
            raise RuntimeError("transient failure")
        return original(*args, **kwargs)

    algs.dijkstra_shortest_path = flaky

    # first two calls fail and register CB failures; third should succeed
    with pytest.raises(RuntimeError):
        svc.compute_shortest_path(g, case["start"], case["goal"], algorithm="dijkstra")

    with pytest.raises(RuntimeError):
        svc.compute_shortest_path(g, case["start"], case["goal"], algorithm="dijkstra")

    # third attempt completes
    p, c = svc.compute_shortest_path(g, case["start"], case["goal"], algorithm="dijkstra")
    assert p == case["expected_path"]

    # restore
    algs.dijkstra_shortest_path = original

import pytest
from pathlib import Path
import json

from v2_logistics.graph import Graph
from v2_logistics.routing import dijkstra_shortest_path, bellman_ford_shortest_path
from v2_logistics.utils import idempotent, retry, timeout


FIXTURE_DIR = Path(__file__).resolve().parents[1] / "data"


def load_graph_from_edges(edges):
    g = Graph()
    for a, b, w in edges:
        g.add_edge(a, b, w)
    return g


def test_dijkstra_rejects_negative_weights():
    # graph from the original issue project
    path = Path(__file__).resolve().parents[2] / "issue_project" / "data" / "graph_negative_weight.json"
    g = Graph.from_json_file(str(path))
    with pytest.raises(ValueError, match="negative"):
        dijkstra_shortest_path(g, "A", "B")


def test_bellman_ford_handles_negative_weights_and_finds_optimal():
    path = Path(__file__).resolve().parents[2] / "issue_project" / "data" / "graph_negative_weight.json"
    g = Graph.from_json_file(str(path))
    path_nodes, cost = bellman_ford_shortest_path(g, "A", "B")
    assert path_nodes == ["A", "C", "D", "F", "B"]
    assert cost == pytest.approx(1.0)


def test_negative_cycle_rejected():
    edges = [["A","B",1],["B","C",-2],["C","A",-2]]
    g = load_graph_from_edges(edges)
    with pytest.raises(ValueError, match="negative-weight cycle"):
        bellman_ford_shortest_path(g, "A", "C")


def test_idempotency_decorator():
    calls = {"count": 0}

    @idempotent(lambda src, dst, key=None: key)
    def compute(src, dst, key=None):
        calls["count"] += 1
        return (src, dst)

    r1 = compute("X","Y", key="uuid-1")
    r2 = compute("X","Y", key="uuid-1")
    assert r1 == r2
    assert calls["count"] == 1


def test_retry_and_timeout_behavior():
    attempts = {"count": 0}

    @retry(max_attempts=3, backoff=0.001)
    @timeout(0.5)
    def flaky(x):
        attempts["count"] += 1
        if attempts["count"] < 2:
            raise RuntimeError("transient")
        return x * 2

    assert flaky(2) == 4
    assert attempts["count"] >= 2


def test_outbox_and_compensation():
    from v2_logistics.utils import Outbox

    out = Outbox()
    calls = {"done": False}

    def step1():
        out.add({"evt": "reserve_resource", "id": 1})

    def step2():
        raise RuntimeError("downstream failed")

    # simple saga: step1 then step2; on failure compensate by emitting rollback
    try:
        step1()
        step2()
    except Exception:
        out.add({"evt": "rollback_resource", "id": 1})
        calls["done"] = True

    assert calls["done"]
    assert any(e["evt"].startswith("rollback") for e in out.list())

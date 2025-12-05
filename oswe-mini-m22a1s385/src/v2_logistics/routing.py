from __future__ import annotations

from typing import Dict, List, Tuple, Optional
import heapq

from .graph import Graph


def dijkstra_shortest_path(graph: Graph, start: str, goal: str) -> Tuple[List[str], float]:
    """Dijkstra with validation: raise ValueError when graph contains negative edges."""
    if graph.has_negative_weight():
        raise ValueError("Graph contains negative weights; Dijkstra is not applicable")

    dist: Dict[str, float] = {start: 0.0}
    prev: Dict[str, Optional[str]] = {start: None}
    heap: List[Tuple[float, str]] = [(0.0, start)]

    visited = set()

    while heap:
        cost, node = heapq.heappop(heap)
        if node in visited:
            continue
        visited.add(node)

        if node == goal:
            return _reconstruct_path(prev, goal), cost

        for neighbor, weight in graph.neighbors(node).items():
            new_cost = cost + weight
            if new_cost < dist.get(neighbor, float("inf")):
                dist[neighbor] = new_cost
                prev[neighbor] = node
                heapq.heappush(heap, (new_cost, neighbor))

    raise ValueError(f"No path found from {start} to {goal}")


def bellman_ford_shortest_path(graph: Graph, start: str, goal: str) -> Tuple[List[str], float]:
    """Bellman-Ford that handles negative weights; raises on negative cycles reachable from start."""
    nodes = list(graph.nodes())
    dist: Dict[str, float] = {n: float("inf") for n in nodes}
    prev: Dict[str, Optional[str]] = {n: None for n in nodes}
    dist[start] = 0.0

    edges = []
    for u in nodes:
        for v, w in graph.neighbors(u).items():
            edges.append((u, v, w))

    for _ in range(len(nodes) - 1):
        updated = False
        for u, v, w in edges:
            if dist[u] + w < dist[v]:
                dist[v] = dist[u] + w
                prev[v] = u
                updated = True
        if not updated:
            break

    # check for negative cycles
    for u, v, w in edges:
        if dist[u] + w < dist[v]:
            raise ValueError("Graph contains a negative-weight cycle")

    if dist.get(goal, float("inf")) == float("inf"):
        raise ValueError(f"No path found from {start} to {goal}")

    return _reconstruct_path(prev, goal), dist[goal]


def _reconstruct_path(prev: Dict[str, Optional[str]], goal: str) -> List[str]:
    path: List[str] = []
    node = goal
    while node is not None:
        path.append(node)
        node = prev.get(node)
    return list(reversed(path))

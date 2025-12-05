from __future__ import annotations

from typing import Dict, List, Tuple, Optional
import heapq

from .graph import Graph


def dijkstra_shortest_path(graph: Graph, start: str, goal: str) -> Tuple[List[str], float]:
    """Correct Dijkstra implementation (requires non-negative weights)."""
    if graph.contains_negative_edge():
        raise ValueError("graph contains negative weight edges — Dijkstra invalid")

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
    """Bellman-Ford that supports negative weights and detects negative cycles."""
    # Initialize distances
    dist: Dict[str, float] = {n: float('inf') for n in graph.nodes()}
    prev: Dict[str, Optional[str]] = {n: None for n in graph.nodes()}
    dist[start] = 0.0

    nodes = list(graph.nodes())
    n = len(nodes)

    # Relax edges up to n-1 times
    for _ in range(n - 1):
        changed = False
        for u in nodes:
            for v, w in graph.neighbors(u).items():
                if dist[u] + w < dist[v]:
                    dist[v] = dist[u] + w
                    prev[v] = u
                    changed = True
        if not changed:
            break

    # Check for negative cycles
    for u in nodes:
        for v, w in graph.neighbors(u).items():
            if dist[u] + w < dist[v]:
                raise ValueError("Negative cycle detected")

    if dist.get(goal, float('inf')) == float('inf'):
        raise ValueError(f"No path found from {start} to {goal}")

    return _reconstruct_path(prev, goal), dist[goal]


def _reconstruct_path(prev: Dict[str, Optional[str]], goal: str) -> List[str]:
    path: List[str] = []
    node = goal
    while node is not None:
        path.append(node)
        node = prev.get(node)
    return list(reversed(path))

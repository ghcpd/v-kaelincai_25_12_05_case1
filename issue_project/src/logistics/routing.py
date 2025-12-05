from __future__ import annotations

from typing import Dict, List, Tuple, Optional
import heapq

from .graph import Graph


def dijkstra_shortest_path(graph: Graph, start: str, goal: str) -> Tuple[List[str], float]:
    """
    Compute shortest path from start to goal using a naive Dijkstra implementation.

    NOTE: This implementation intentionally omits negative-edge validation and
    aggressively marks nodes as visited upon discovery (not upon finalization).
    That means it can produce incorrect results on graphs with negative weights.
    """
    # Distances and predecessor tracking
    dist: Dict[str, float] = {start: 0.0}
    prev: Dict[str, Optional[str]] = {start: None}

    # Min-heap items: (cost, node)
    heap: List[Tuple[float, str]] = [(0.0, start)]

    # BUG: mark nodes visited immediately when they are discovered rather than when popped.
    visited = set([start])

    while heap:
        cost, node = heapq.heappop(heap)

        if node == goal:
            return _reconstruct_path(prev, goal), cost

        # If a stale entry is popped, skip it
        if cost > dist.get(node, float("inf")):
            continue

        for neighbor, weight in graph.neighbors(node).items():
            # BUG: No check for negative weights
            new_cost = cost + weight
            if neighbor in visited:
                # BUG: Because neighbor is marked visited early, we never relax it again
                continue
            if new_cost < dist.get(neighbor, float("inf")):
                dist[neighbor] = new_cost
                prev[neighbor] = node
                heapq.heappush(heap, (new_cost, neighbor))
                visited.add(neighbor)  # BUG: premature finalization

    raise ValueError(f"No path found from {start} to {goal}")


def _reconstruct_path(prev: Dict[str, Optional[str]], goal: str) -> List[str]:
    path: List[str] = []
    node = goal
    while node is not None:
        path.append(node)
        node = prev.get(node)
    return list(reversed(path))

"""Bellman-Ford shortest-path algorithm (handles negative edges)."""

from typing import Dict, List, Optional, Tuple

from ..graph import Graph
from ..exceptions import NegativeCycleError, NoPathError


def bellman_ford_shortest_path(
    graph: Graph, start: str, goal: str
) -> Tuple[List[str], float]:
    """
    Compute shortest path using Bellman-Ford algorithm.
    
    Supports negative-weight edges and detects negative cycles.
    
    Complexity: O(V·E)
    
    Args:
        graph: Directed weighted graph
        start: Source node
        goal: Destination node
    
    Returns:
        (path: List[str], total_cost: float)
    
    Raises:
        ValueError: If source or goal not in graph
        NegativeCycleError: If negative cycle detected
        NoPathError: If no path exists
    """
    nodes = graph.nodes()
    if start not in nodes or goal not in nodes:
        raise ValueError(f"Source or goal not in graph: {start}, {goal}")
    
    # Initialize distances and predecessors
    dist: Dict[str, float] = {node: float("inf") for node in nodes}
    dist[start] = 0.0
    prev: Dict[str, Optional[str]] = {node: None for node in nodes}
    
    # Relax edges |V|-1 times
    for _ in range(len(nodes) - 1):
        for source in nodes:
            if dist[source] == float("inf"):
                continue
            
            for target, weight in graph.neighbors(source).items():
                new_cost = dist[source] + weight
                if new_cost < dist[target]:
                    dist[target] = new_cost
                    prev[target] = source
    
    # Check for negative cycles
    for source in nodes:
        if dist[source] == float("inf"):
            continue
        
        for target, weight in graph.neighbors(source).items():
            if dist[source] + weight < dist[target]:
                raise NegativeCycleError("Negative cycle detected in graph")
    
    if dist[goal] == float("inf"):
        raise NoPathError(f"No path found from {start} to {goal}")
    
    return _reconstruct_path(prev, goal), dist[goal]


def _reconstruct_path(prev: Dict[str, Optional[str]], goal: str) -> List[str]:
    """Reconstruct path from predecessor map."""
    path: List[str] = []
    node: Optional[str] = goal
    while node is not None:
        path.append(node)
        node = prev.get(node)
    return list(reversed(path))

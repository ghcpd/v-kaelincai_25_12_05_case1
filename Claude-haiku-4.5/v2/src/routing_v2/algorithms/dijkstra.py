"""Dijkstra shortest-path algorithm (corrected implementation)."""

from typing import Dict, List, Optional, Tuple
import heapq

from ..graph import Graph
from ..exceptions import NoPathError


def dijkstra_shortest_path(
    graph: Graph, start: str, goal: str
) -> Tuple[List[str], float]:
    """
    Compute shortest path using Dijkstra's algorithm (corrected).
    
    Key fixes from v1:
    1. Mark nodes visited when POPPED (finalized), not when discovered
    2. Skip stale entries in heap
    3. Precondition: graph must have non-negative weights
    
    Complexity: O(E log V)
    
    Args:
        graph: Directed weighted graph
        start: Source node
        goal: Destination node
    
    Returns:
        (path: List[str], total_cost: float)
    
    Raises:
        ValueError: If source or goal not in graph
        NoPathError: If no path exists
    """
    nodes = graph.nodes()
    if start not in nodes or goal not in nodes:
        raise ValueError(f"Source or goal not in graph: {start}, {goal}")
    
    # Initialize distances and predecessors
    dist: Dict[str, float] = {node: float("inf") for node in nodes}
    dist[start] = 0.0
    prev: Dict[str, Optional[str]] = {node: None for node in nodes}
    
    # Min-heap: (cost, node)
    heap: List[Tuple[float, str]] = [(0.0, start)]
    visited = set()
    
    while heap:
        cost, node = heapq.heappop(heap)
        
        # Skip if already visited (finalized)
        if node in visited:
            continue
        
        # Mark as visited (finalized)
        visited.add(node)
        
        if node == goal:
            return _reconstruct_path(prev, goal), cost
        
        # Stale entry check (cost > known distance)
        if cost > dist[node]:
            continue
        
        # Relax neighbors
        for neighbor, weight in graph.neighbors(node).items():
            # Skip already-visited nodes (they're finalized)
            if neighbor in visited:
                continue
            
            new_cost = cost + weight
            if new_cost < dist[neighbor]:
                dist[neighbor] = new_cost
                prev[neighbor] = node
                heapq.heappush(heap, (new_cost, neighbor))
    
    raise NoPathError(f"No path found from {start} to {goal}")


def _reconstruct_path(prev: Dict[str, Optional[str]], goal: str) -> List[str]:
    """Reconstruct path from predecessor map."""
    path: List[str] = []
    node: Optional[str] = goal
    while node is not None:
        path.append(node)
        node = prev.get(node)
    return list(reversed(path))

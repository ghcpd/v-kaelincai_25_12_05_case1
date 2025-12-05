"""Algorithm selector based on graph properties."""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .logger import StructuredLogger

from .models import Algorithm
from .graph import Graph


class AlgorithmSelector:
    """Select optimal algorithm based on graph properties."""
    
    @staticmethod
    def select(graph: Graph, request_id: str, logger: "StructuredLogger") -> Algorithm:
        """
        Determine which algorithm to use.
        
        Logic:
          - If graph has negative edges → Bellman-Ford (general)
          - Otherwise → Dijkstra (faster, O(E log V) vs O(V·E))
        
        Args:
            graph: Directed weighted graph
            request_id: Unique request identifier for logging
            logger: Structured logger
        
        Returns:
            Algorithm enum value
        """
        has_negative = graph.has_negative_edges()
        
        if has_negative:
            logger.info(
                f"[{request_id}] Graph has negative edges → using Bellman-Ford"
            )
            return Algorithm.BELLMAN_FORD
        else:
            logger.info(
                f"[{request_id}] Graph is non-negative → using Dijkstra (faster)"
            )
            return Algorithm.DIJKSTRA

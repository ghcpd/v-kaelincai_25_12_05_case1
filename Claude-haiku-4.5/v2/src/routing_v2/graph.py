"""Enhanced graph data structure with validation."""

from __future__ import annotations
from typing import Dict, List, Optional, Tuple
import json


class Graph:
    """Directed weighted graph with validation and introspection."""
    
    def __init__(self, version: str = "unknown"):
        self._adj: Dict[str, Dict[str, float]] = {}
        self._version = version
        self._has_negative_edges: Optional[bool] = None
    
    def add_edge(self, source: str, target: str, weight: float) -> None:
        """Add directed edge with validation."""
        if not isinstance(weight, (int, float)) or weight != weight:  # NaN check
            raise ValueError(f"Invalid weight {weight} on edge {source}→{target}")
        
        if weight < 0:
            self._has_negative_edges = True
        
        if source not in self._adj:
            self._adj[source] = {}
        self._adj[source][target] = weight
        
        if target not in self._adj:
            self._adj[target] = {}
    
    def has_negative_edges(self) -> bool:
        """Check if graph contains any negative-weight edges."""
        if self._has_negative_edges is not None:
            return self._has_negative_edges
        
        self._has_negative_edges = any(
            weight < 0 
            for neighbors in self._adj.values()
            for weight in neighbors.values()
        )
        return self._has_negative_edges
    
    def validate(self) -> Tuple[bool, Optional[str]]:
        """
        Validate graph integrity.
        Returns (is_valid, error_message).
        """
        if not self._adj:
            return False, "Graph is empty"
        
        for source, neighbors in self._adj.items():
            for target, weight in neighbors.items():
                if not isinstance(weight, (int, float)) or weight != weight:
                    return False, f"Invalid weight {weight} on edge {source}→{target}"
                if target not in self._adj:
                    return False, f"Target {target} not in graph nodes"
        
        return True, None
    
    def neighbors(self, node: str) -> Dict[str, float]:
        """Get neighbors of a node."""
        return self._adj.get(node, {})
    
    def nodes(self) -> List[str]:
        """Get all nodes in graph."""
        return list(self._adj.keys())
    
    def edge_count(self) -> int:
        """Get total number of edges."""
        return sum(len(neighbors) for neighbors in self._adj.values())
    
    def version(self) -> str:
        """Get graph version."""
        return self._version
    
    @classmethod
    def from_json_file(cls, path: str, version: str = "v1") -> Graph:
        """Load graph from JSON file."""
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        g = cls(version=version)
        
        if "edges" not in data:
            raise ValueError("JSON must contain 'edges' key")
        
        for edge in data["edges"]:
            if not all(k in edge for k in ["source", "target", "weight"]):
                raise ValueError("Each edge must have source, target, and weight")
            g.add_edge(edge["source"], edge["target"], edge["weight"])
        
        is_valid, error = g.validate()
        if not is_valid:
            raise ValueError(f"Invalid graph: {error}")
        
        return g
    
    @staticmethod
    def from_edge_list(edges: List[Tuple[str, str, float]], version: str = "v1") -> Graph:
        """Create graph from edge list."""
        g = Graph(version=version)
        for src, dst, weight in edges:
            g.add_edge(src, dst, weight)
        return g

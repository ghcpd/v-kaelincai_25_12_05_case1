from __future__ import annotations

from typing import Dict, Iterable, Tuple, List
import json


class Graph:
    """Directed weighted graph using adjacency dict."""

    def __init__(self) -> None:
        self._adj: Dict[str, Dict[str, float]] = {}

    def add_edge(self, source: str, target: str, weight: float) -> None:
        if source not in self._adj:
            self._adj[source] = {}
        self._adj[source][target] = weight
        # Ensure target exists in adjacency map for node iteration
        if target not in self._adj:
            self._adj[target] = {}

    def neighbors(self, node: str) -> Dict[str, float]:
        return self._adj.get(node, {})

    def nodes(self) -> Iterable[str]:
        return self._adj.keys()

    @staticmethod
    def from_edge_list(edges: Iterable[Tuple[str, str, float]]) -> "Graph":
        g = Graph()
        for src, dst, w in edges:
            g.add_edge(src, dst, w)
        return g

    @classmethod
    def from_json_file(cls, path: str) -> "Graph":
        """Load graph from JSON file with structure:
        {
          "edges": [
            {"source": "A", "target": "B", "weight": 5},
            ...
          ]
        }
        """
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        edges: List[Tuple[str, str, float]] = [
            (e["source"], e["target"], e["weight"]) for e in data["edges"]
        ]
        return cls.from_edge_list(edges)

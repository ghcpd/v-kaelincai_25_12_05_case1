from __future__ import annotations

from typing import Dict, Iterable, Tuple, List
import json


class Graph:
    """Directed weighted graph implementation (immutable after construction for safety)."""

    def __init__(self) -> None:
        self._adj: Dict[str, Dict[str, float]] = {}

    def add_edge(self, source: str, target: str, weight: float) -> None:
        if source not in self._adj:
            self._adj[source] = {}
        self._adj[source][target] = float(weight)
        if target not in self._adj:
            self._adj[target] = {}

    def neighbors(self, node: str) -> Dict[str, float]:
        return dict(self._adj.get(node, {}))

    def nodes(self) -> Iterable[str]:
        return list(self._adj.keys())

    def has_negative_weight(self) -> bool:
        for src in self._adj:
            for _, w in self._adj[src].items():
                if w < 0:
                    return True
        return False

    @staticmethod
    def from_edge_list(edges: Iterable[Tuple[str, str, float]]) -> "Graph":
        g = Graph()
        for src, dst, w in edges:
            g.add_edge(src, dst, w)
        return g

    @classmethod
    def from_json_file(cls, path: str) -> "Graph":
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        edges: List[Tuple[str, str, float]] = [
            (e["source"], e["target"], e["weight"]) for e in data["edges"]
        ]
        return cls.from_edge_list(edges)

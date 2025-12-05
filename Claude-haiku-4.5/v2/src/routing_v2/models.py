"""Data models for routing service."""

from dataclasses import dataclass, field
from typing import List, Optional
from enum import Enum
import uuid
from datetime import datetime


class Algorithm(Enum):
    """Available routing algorithms."""
    DIJKSTRA = "dijkstra"
    BELLMAN_FORD = "bellman_ford"


class RouteStatus(Enum):
    """Possible route computation outcomes."""
    SUCCESS = "success"
    TIMEOUT = "timeout"
    NO_PATH = "no_path_found"
    INVALID_GRAPH = "invalid_graph"
    NEGATIVE_CYCLE = "negative_cycle"
    CIRCUIT_OPEN = "circuit_open"
    ERROR = "error"


@dataclass
class RouteRequest:
    """Route computation request."""
    request_id: str
    source: str
    destination: str
    graph_version: str = "v1"
    timeout_ms: int = 5000
    idempotency_key: Optional[str] = None
    
    def __post_init__(self):
        """Validate request fields."""
        if not (100 <= self.timeout_ms <= 60000):
            raise ValueError("timeout_ms must be between 100 and 60000")
        
        if not (1 <= len(self.source) <= 32):
            raise ValueError("source must be 1-32 characters")
        
        if not (1 <= len(self.destination) <= 32):
            raise ValueError("destination must be 1-32 characters")


@dataclass
class RouteResponse:
    """Route computation response."""
    request_id: str
    success: bool
    path: Optional[List[str]] = None
    cost: Optional[float] = None
    algorithm: Optional[str] = None
    latency_ms: float = 0.0
    retry_count: int = 0
    status: str = "unknown"
    graph_version: str = "v1"
    timestamp: float = field(default_factory=lambda: datetime.utcnow().timestamp())
    error_message: Optional[str] = None
    
    def to_dict(self) -> dict:
        """Convert to dictionary (JSON-serializable)."""
        return {
            "request_id": self.request_id,
            "success": self.success,
            "path": self.path,
            "cost": self.cost,
            "algorithm": self.algorithm,
            "latency_ms": round(self.latency_ms, 2),
            "retry_count": self.retry_count,
            "status": self.status,
            "graph_version": self.graph_version,
            "timestamp": round(self.timestamp, 3),
            "error_message": self.error_message,
        }


@dataclass
class RoutingEvent:
    """Audit event for route computation."""
    event_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    request_id: str = ""
    timestamp: float = field(default_factory=lambda: datetime.utcnow().timestamp())
    graph_version: str = "v1"
    source: str = ""
    destination: str = ""
    algorithm: str = ""
    path: Optional[List[str]] = None
    cost: Optional[float] = None
    latency_ms: float = 0.0
    retry_count: int = 0
    status: str = "unknown"
    circuit_breaker_state: str = "CLOSED"
    cache_hit: bool = False
    error_message: Optional[str] = None
    
    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "event_id": self.event_id,
            "request_id": self.request_id,
            "timestamp": round(self.timestamp, 3),
            "graph_version": self.graph_version,
            "source": self.source,
            "destination": self.destination,
            "algorithm": self.algorithm,
            "path": self.path,
            "cost": self.cost,
            "latency_ms": round(self.latency_ms, 2),
            "retry_count": self.retry_count,
            "status": self.status,
            "circuit_breaker_state": self.circuit_breaker_state,
            "cache_hit": self.cache_hit,
            "error_message": self.error_message,
        }

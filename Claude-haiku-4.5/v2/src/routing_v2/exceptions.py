"""Exceptions for routing service."""


class RoutingError(Exception):
    """Base routing exception."""
    pass


class NegativeWeightError(RoutingError):
    """Graph contains negative-weight edges (invalid for Dijkstra)."""
    pass


class NegativeCycleError(RoutingError):
    """Graph contains a negative-weight cycle."""
    pass


class NoPathError(RoutingError):
    """No path exists between source and destination."""
    pass


class InvalidGraphError(RoutingError):
    """Graph validation failed."""
    pass


class TimeoutError(RoutingError):
    """Route computation exceeded timeout deadline."""
    pass

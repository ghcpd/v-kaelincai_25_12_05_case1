"""Idempotency cache for request deduplication."""

import time
import hashlib
from typing import Dict, Optional, Tuple, TYPE_CHECKING

if TYPE_CHECKING:
    from .models import RouteRequest, RouteResponse


class IdempotencyCache:
    """In-memory cache for idempotent requests."""
    
    def __init__(self, ttl_s: int = 3600):
        """
        Initialize cache.
        
        Args:
            ttl_s: Time-to-live for cache entries (seconds)
        """
        self.cache: Dict[str, Tuple["RouteResponse", float]] = {}
        self.ttl_s = ttl_s
    
    def generate_key(self, req: "RouteRequest") -> str:
        """
        Generate idempotency key from request.
        
        Key structure:
          - If idempotency_key provided: use it
          - Otherwise: hash(graph_version:source:dest:time_bucket)
          
        This ensures duplicate requests within a time window return cached results.
        
        Args:
            req: Route request
        
        Returns:
            Idempotency key (string)
        """
        if req.idempotency_key:
            return req.idempotency_key
        
        # Default: hash with time bucket (1-minute window)
        time_bucket = int(time.time() / 60) * 60
        data = f"{req.graph_version}:{req.source}:{req.destination}:{time_bucket}"
        key_hash = hashlib.sha256(data.encode()).hexdigest()[:16]
        return key_hash
    
    def get(self, key: str) -> Optional["RouteResponse"]:
        """
        Retrieve cached response if not expired.
        
        Args:
            key: Idempotency key
        
        Returns:
            Cached RouteResponse or None if expired/missing
        """
        if key in self.cache:
            response, created_at = self.cache[key]
            if time.time() - created_at < self.ttl_s:
                return response
            else:
                # Expired, remove from cache
                del self.cache[key]
        
        return None
    
    def put(self, key: str, response: "RouteResponse") -> None:
        """
        Store response in cache.
        
        Args:
            key: Idempotency key
            response: Route response to cache
        """
        self.cache[key] = (response, time.time())
    
    def size(self) -> int:
        """Get current cache size."""
        return len(self.cache)
    
    def clear(self) -> None:
        """Clear all cache entries."""
        self.cache.clear()

"""Circuit breaker for failure cascade prevention."""

import time
from enum import Enum


class CircuitState(Enum):
    """Circuit breaker state."""
    CLOSED = "CLOSED"      # Normal operation
    OPEN = "OPEN"          # Failures detected, reject requests
    HALF_OPEN = "HALF_OPEN"  # Testing recovery


class CircuitBreaker:
    """Protect against cascading failures."""
    
    def __init__(
        self,
        failure_threshold: float = 0.5,
        success_threshold: int = 1,
        window_size: int = 100,
        timeout_s: int = 30,
    ):
        """
        Initialize circuit breaker.
        
        Args:
            failure_threshold: Failure rate threshold to open (0.0-1.0)
            success_threshold: Successes needed in HALF_OPEN to close
            window_size: Request window for failure calculation
            timeout_s: Duration to stay OPEN before HALF_OPEN transition
        """
        self.failure_threshold = failure_threshold
        self.success_threshold = success_threshold
        self.window_size = window_size
        self.timeout_s = timeout_s
        
        self.state = CircuitState.CLOSED
        self.last_failure_time = None
        self.failure_count = 0
        self.success_count = 0
        self.request_count = 0
    
    def record_success(self) -> None:
        """Record successful request."""
        self.failure_count = 0
        self.request_count += 1
        
        if self.state == CircuitState.HALF_OPEN:
            self.success_count += 1
            if self.success_count >= self.success_threshold:
                self.state = CircuitState.CLOSED
    
    def record_failure(self) -> None:
        """Record failed request; may trip circuit."""
        self.last_failure_time = time.time()
        self.failure_count += 1
        self.request_count += 1
        
        # Calculate failure rate
        failure_rate = self.failure_count / max(1, self.request_count)
        
        if failure_rate >= self.failure_threshold:
            self.state = CircuitState.OPEN
    
    def check_state(self) -> CircuitState:
        """
        Check current state.
        
        Transition: OPEN → HALF_OPEN if timeout elapsed
        
        Returns:
            Current circuit state
        """
        if self.state == CircuitState.OPEN:
            if self.last_failure_time and time.time() - self.last_failure_time > self.timeout_s:
                self.state = CircuitState.HALF_OPEN
                self.success_count = 0
        
        return self.state
    
    def is_open(self) -> bool:
        """Check if circuit is open (should reject requests)."""
        return self.check_state() == CircuitState.OPEN
    
    def is_half_open(self) -> bool:
        """Check if circuit is half-open (testing recovery)."""
        return self.check_state() == CircuitState.HALF_OPEN
    
    def is_closed(self) -> bool:
        """Check if circuit is closed (normal operation)."""
        return self.check_state() == CircuitState.CLOSED
    
    def state_name(self) -> str:
        """Get current state name."""
        return self.check_state().value

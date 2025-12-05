"""Retry policy with exponential backoff."""


class RetryPolicy:
    """Exponential backoff + max retry logic."""
    
    def __init__(self, max_retries: int = 3, base_backoff_ms: int = 100):
        """
        Initialize retry policy.
        
        Args:
            max_retries: Maximum number of retry attempts
            base_backoff_ms: Base backoff in milliseconds (100ms)
        """
        self.max_retries = max_retries
        self.base_backoff_ms = base_backoff_ms
    
    def is_retriable(self, error: Exception) -> bool:
        """
        Determine if error warrants retry.
        
        Retriable errors: Timeout, connection, IO errors
        Non-retriable: Validation, algorithm-specific errors
        
        Args:
            error: Exception to check
        
        Returns:
            True if should retry, False otherwise
        """
        retriable_types = (TimeoutError, ConnectionError, IOError)
        return isinstance(error, retriable_types)
    
    def backoff_ms(self, attempt: int) -> int:
        """
        Calculate backoff time for retry attempt.
        
        Sequence: 100ms, 300ms, 900ms, 2700ms, ...
        Formula: base * (3^attempt)
        
        Args:
            attempt: Retry attempt number (0-indexed)
        
        Returns:
            Backoff time in milliseconds
        """
        return self.base_backoff_ms * (3 ** attempt)
    
    def should_retry(self, attempt: int) -> bool:
        """
        Check if we should attempt another retry.
        
        Args:
            attempt: Current attempt number (0-indexed)
        
        Returns:
            True if we should retry, False if exhausted
        """
        return attempt < self.max_retries

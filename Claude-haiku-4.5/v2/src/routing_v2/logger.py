"""Structured logging for audit trail."""

import logging
import json
import sys
from datetime import datetime
from typing import Optional


class StructuredLogger:
    """JSON-structured logging for audit trail."""
    
    def __init__(self, name: str, log_file: Optional[str] = None):
        """
        Initialize structured logger.
        
        Args:
            name: Logger name
            log_file: Optional file path to write logs
        """
        self.logger = logging.getLogger(name)
        self.logger.setLevel(logging.INFO)
        
        # Console handler
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(logging.Formatter('%(message)s'))
        self.logger.addHandler(console_handler)
        
        # File handler (if specified)
        if log_file:
            file_handler = logging.FileHandler(log_file, encoding='utf-8')
            file_handler.setFormatter(logging.Formatter('%(message)s'))
            self.logger.addHandler(file_handler)
    
    def log_event(self, **kwargs) -> None:
        """
        Log structured event as JSON.
        
        Automatically adds timestamp if not provided.
        
        Args:
            **kwargs: Event fields
        """
        event = {
            "timestamp": kwargs.get("timestamp", datetime.utcnow().isoformat() + "Z"),
            **{k: v for k, v in kwargs.items() if k != "timestamp"}
        }
        self.logger.info(json.dumps(event))
    
    def info(self, msg: str, **kwargs) -> None:
        """Log info message."""
        self.log_event(level="INFO", message=msg, **kwargs)
    
    def error(self, msg: str, **kwargs) -> None:
        """Log error message."""
        self.log_event(level="ERROR", message=msg, **kwargs)
    
    def warning(self, msg: str, **kwargs) -> None:
        """Log warning message."""
        self.log_event(level="WARNING", message=msg, **kwargs)

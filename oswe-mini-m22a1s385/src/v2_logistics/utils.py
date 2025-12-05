from __future__ import annotations

from functools import wraps
from typing import Callable, Any, Dict
import time
import logging
import functools
import threading

_IDEMPOTENCY_STORE: Dict[str, Any] = {}


def idempotent(key_fn: Callable[..., str]):
    """Simple in-memory idempotency decorator for examples/tests."""

    def decorator(func: Callable):
        @wraps(func)
        def wrapper(*args, **kwargs):
            key = key_fn(*args, **kwargs)
            if key in _IDEMPOTENCY_STORE:
                return _IDEMPOTENCY_STORE[key]
            result = func(*args, **kwargs)
            _IDEMPOTENCY_STORE[key] = result
            return result

        return wrapper

    return decorator


def structured_log(message: str, **fields) -> None:
    data = {"msg": message, "ts": time.time()}
    data.update(fields)
    # Mask sensitive keys
    for k in list(data.keys()):
        if k.lower().endswith("token") or k.lower().endswith("secret"):
            data[k] = "***"
    logging.info(data)


def retry(max_attempts: int = 3, backoff: float = 0.1):
    def decorator(func: Callable):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            attempts = 0
            last_exc = None
            while attempts < max_attempts:
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_exc = e
                    attempts += 1
                    time.sleep(backoff * attempts)
            raise last_exc

        return wrapper

    return decorator


def timeout(seconds: float):
    def decorator(func: Callable):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            result = [Exception("function did not complete in time")]

            def target():
                try:
                    result[0] = func(*args, **kwargs)
                except Exception as e:
                    result[0] = e

            th = threading.Thread(target=target)
            th.daemon = True
            th.start()
            th.join(seconds)
            if isinstance(result[0], BaseException):
                raise result[0]
            return result[0]

        return wrapper

    return decorator


class Outbox:
    """Simple in-memory outbox for transactional event capture and replay in tests."""

    def __init__(self):
        self._store = []

    def add(self, event: dict):
        self._store.append(event)

    def list(self):
        return list(self._store)

    def clear(self):
        self._store.clear()


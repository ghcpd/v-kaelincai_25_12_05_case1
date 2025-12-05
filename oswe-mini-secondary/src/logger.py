import json
import time


def log_structured(event: str, **kwargs):
    rec = {"ts": time.time(), "event": event}
    rec.update(kwargs)
    print(json.dumps(rec))

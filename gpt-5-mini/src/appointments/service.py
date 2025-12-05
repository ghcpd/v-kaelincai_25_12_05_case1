"""Minimal appointments v2 runtime implementing idempotent scheduling and saga/outbox patterns for testing."""
from __future__ import annotations

import json
import time
import uuid
from typing import Dict, Any, Optional

REQUEST_STORE: Dict[str, Dict[str, Any]] = {}
APPOINTMENT_DB: Dict[str, Dict[str, Any]] = {}
OUTBOX: Dict[str, Dict[str, Any]] = {}


def _now_ms() -> int:
    return int(time.time() * 1000)


def schedule_appointment(payload: Dict[str, Any], idempotency_key: Optional[str] = None) -> Dict[str, Any]:
    """Schedule an appointment in an idempotent way.

    Returns a result dict with status and request_id.
    """
    request_id = idempotency_key or str(uuid.uuid4())
    if request_id in REQUEST_STORE:
        # Return stored response for idempotency
        return REQUEST_STORE[request_id]["response"]

    # Basic validation
    if "start" not in payload or "end" not in payload or payload["end"] <= payload["start"]:
        resp = {"status": "error", "error": "invalid_time_range"}
        REQUEST_STORE[request_id] = {"request": payload, "response": resp, "ts": _now_ms()}
        return resp

    # Create appointment record (optimistic)
    appt_id = str(uuid.uuid4())
    appt = {
        "id": appt_id,
        "start": payload["start"],
        "end": payload["end"],
        "subject": payload.get("subject"),
        "created_at": _now_ms(),
        "status": "scheduled",
    }
    APPOINTMENT_DB[appt_id] = appt

    # Place outbox event for downstream processing (e.g., calendar notify)
    out_id = str(uuid.uuid4())
    OUTBOX[out_id] = {"id": out_id, "type": "appointment.created", "payload": appt, "ts": _now_ms(), "sent": False}

    resp = {"status": "ok", "request_id": request_id, "appointment_id": appt_id}
    REQUEST_STORE[request_id] = {"request": payload, "response": resp, "ts": _now_ms()}
    return resp


def process_outbox_once(processor) -> Dict[str, Any]:
    """Process one outbox item using provided processor callable.

    Returns metrics about processing.
    """
    unprocessed = [o for o in OUTBOX.values() if not o["sent"]]
    if not unprocessed:
        return {"processed": 0}
    item = unprocessed[0]
    try:
        processor(item["payload"])  # may raise
        item["sent"] = True
        item["sent_at"] = _now_ms()
        return {"processed": 1, "id": item["id"]}
    except Exception as e:
        # leave unsent for retry
        item.setdefault("attempts", 0)
        item["attempts"] += 1
        item.setdefault("last_error", str(e))
        return {"processed": 0, "error": str(e), "attempts": item["attempts"]}


def reset_state():
    REQUEST_STORE.clear()
    APPOINTMENT_DB.clear()
    OUTBOX.clear()

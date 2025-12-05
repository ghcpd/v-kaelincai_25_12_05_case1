from typing import Dict, Any, Optional
import threading
import time
import uuid

class InMemoryStore:
    def __init__(self):
        self.lock = threading.Lock()
        self.appointments: Dict[str, Dict[str, Any]] = {}
        self.outbox: Dict[str, Dict[str, Any]] = {}

    def create_or_get(self, idempotency_key: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        with self.lock:
            if idempotency_key in self.appointments:
                return self.appointments[idempotency_key]
            entry = {
                "id": str(uuid.uuid4()),
                "state": "created",
                "payload": payload,
                "created_at": time.time(),
            }
            self.appointments[idempotency_key] = entry
            # add outbox event
            self.outbox[entry['id']] = {"event": "appointment.created", "payload": entry}
            return entry

    def mark_confirmed(self, appointment_id: str):
        with self.lock:
            # find in appointments
            for k,v in self.appointments.items():
                if v['id'] == appointment_id:
                    v['state'] = 'confirmed'
                    return v
            raise KeyError('appointment not found')

store = InMemoryStore()

def create_appointment(idempotency_key: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    return store.create_or_get(idempotency_key, payload)

def confirm_appointment(appointment_id: str):
    return store.mark_confirmed(appointment_id)

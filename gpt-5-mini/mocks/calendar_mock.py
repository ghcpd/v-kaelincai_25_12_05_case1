"""Simple calendar downstream processor to simulate transient failures/delays."""
from __future__ import annotations

class CalendarMock:
    def __init__(self, fail_first: bool = False):
        self.calls = 0
        self.fail_first = fail_first

    def notify(self, appt_payload):
        self.calls += 1
        if self.fail_first and self.calls == 1:
            raise RuntimeError("transient calendar error")
        # pretend to accept and return an external id
        return {"external_id": f"cal-{appt_payload['id']}"}

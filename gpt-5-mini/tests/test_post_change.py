from __future__ import annotations

import json
import pytest

from appointments import service
from mocks.calendar_mock import CalendarMock


@pytest.fixture(autouse=True)
def reset():
    service.reset_state()
    yield
    service.reset_state()


def test_invalid_time_rejected():
    payload = {"start": 2000, "end": 1000}
    resp = service.schedule_appointment(payload)
    assert resp["status"] == "error"
    assert resp["error"] == "invalid_time_range"


def test_idempotency_keeps_single_appointment():
    payload = {"start": 3000, "end": 4000}
    key = "idem-key-1"
    r1 = service.schedule_appointment(payload, idempotency_key=key)
    r2 = service.schedule_appointment(payload, idempotency_key=key)
    assert r1 == r2
    # only one appointment exists
    assert len(service.APPOINTMENT_DB) == 1


def test_outbox_retry_and_success():
    payload = {"start": 5000, "end": 6000}
    r = service.schedule_appointment(payload)
    assert r["status"] == "ok"

    mock = CalendarMock(fail_first=True)
    # first attempt fails
    res1 = service.process_outbox_once(lambda p: mock.notify(p))
    assert res1["processed"] == 0
    assert res1["attempts"] == 1

    # second attempt should succeed
    res2 = service.process_outbox_once(lambda p: mock.notify(p))
    assert res2["processed"] == 1
    assert list(service.OUTBOX.values())[0]["sent"] is True


def test_happy_path_creates_appointment_and_outbox():
    payload = {"start": 1000, "end": 2000, "subject": "ok"}
    r = service.schedule_appointment(payload)
    assert r["status"] == "ok"
    assert len(service.APPOINTMENT_DB) == 1
    assert len(service.OUTBOX) == 1


def test_process_outbox_no_items_returns_zero():
    # when outbox is empty, processing should be a no-op
    res = service.process_outbox_once(lambda p: None)
    assert res["processed"] == 0

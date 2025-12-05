import pytest
import time
from src.appointment_service import AppointmentService, DB
from mocks.calendar_mock import CalendarMock


class FlakyCalendar(CalendarMock):
    def __init__(self, fail_times=2):
        super().__init__('flaky')
        self.fail_times = fail_times
        self.attempts = 0

    def create_event(self, appt):
        self.attempts += 1
        if self.attempts <= self.fail_times:
            raise TimeoutError('transient timeout')
        return {'ok': True, 'event_id': 'evt-' + appt['id']}


def test_retry_with_backoff():
    DB['appointments'].clear(); DB['outbox'].clear(); DB['idempotency'].clear()
    cal = FlakyCalendar(fail_times=2)
    svc = AppointmentService(cal, max_retries=3, base_backoff=0.01)
    res = svc.create_appointment('userX', '2025-12-06T09:00:00Z', 'kb-1')
    svc.process_outbox()
    appt = svc.get_appointment(res['appointment_id'])
    assert appt['status'] == 'CONFIRMED'


def test_circuit_breaker_opens_after_consecutive_failures():
    DB['appointments'].clear(); DB['outbox'].clear(); DB['idempotency'].clear()
    cal = FlakyCalendar(fail_times=5)
    svc = AppointmentService(cal, max_retries=1, circuit_breaker_threshold=3)
    res = svc.create_appointment('userY', '2025-12-06T10:00:00Z', 'kb-2')
    # Call process_outbox repeatedly until circuit opens due to consecutive failures
    opened = False
    for _ in range(10):
        try:
            svc.process_outbox()
        except RuntimeError:
            opened = True
            break
        except TimeoutError:
            # transient failure expected during accumulation
            continue
    assert opened
    # Circuit should be open now; subsequent attempts raise immediately
    with pytest.raises(RuntimeError):
        svc.process_outbox()


def test_outbox_reconciliation_backfill():
    DB['appointments'].clear(); DB['outbox'].clear(); DB['idempotency'].clear()
    # calendar down, create appointment
    cal = CalendarMock('timeout')
    svc = AppointmentService(cal)
    res = svc.create_appointment('userZ', '2025-12-07T09:00:00Z', 'kb-3')
    # processing raises
    with pytest.raises(TimeoutError):
        svc.process_outbox()
    # Now set calendar to ok and run reconciliation which should process remaining outbox items
    cal.behavior = 'ok'
    svc.reconcile_outbox()
    appt = svc.get_appointment(res['appointment_id'])
    assert appt['status'] == 'CONFIRMED'


def test_reconciliation_idempotent_after_crash():
    DB['appointments'].clear(); DB['outbox'].clear(); DB['idempotency'].clear()
    cal = CalendarMock('ok')
    svc = AppointmentService(cal)
    res = svc.create_appointment('userCR', '2025-12-07T10:00:00Z', 'kb-4')
    # simulate worker crash after dequeuing but before marking confirmed: move item to a "processing" transient list then crash
    item = DB['outbox'].pop(0)
    # pretend crash, restart and requeue
    DB['outbox'].append(item)
    svc.reconcile_outbox()
    appt = svc.get_appointment(res['appointment_id'])
    assert appt['status'] == 'CONFIRMED'

def test_audit_logging_includes_request_id():
    DB['appointments'].clear(); DB['outbox'].clear(); DB['idempotency'].clear()
    cal = CalendarMock('ok')
    svc = AppointmentService(cal)
    res = svc.create_appointment('userA', '2025-12-08T09:00:00Z', 'kb-4')
    # expect that create_appointment returns appointment with an id and that logs include request id
    assert 'appointment_id' in res
    # look for request_id stored in appointment record
    appt = svc.get_appointment(res['appointment_id'])
    assert 'request_id' in appt

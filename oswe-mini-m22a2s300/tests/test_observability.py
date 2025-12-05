import pytest
from src.appointment_service import AppointmentService, DB
from mocks.calendar_mock import CalendarMock
import time


def test_retry_attempts_recorded():
    DB['appointments'].clear(); DB['outbox'].clear(); DB['idempotency'].clear()
    class LocalFlaky(CalendarMock):
        def __init__(self, fail_times):
            super().__init__('flaky')
            self.fail_times = fail_times
            self.attempts = 0
        def create_event(self, appt):
            self.attempts += 1
            if self.attempts <= self.fail_times:
                raise TimeoutError('transient')
            return {'ok': True}

    cal = LocalFlaky(fail_times=2)
    svc = AppointmentService(cal, max_retries=5, base_backoff=0.001)
    res = svc.create_appointment('obsUser', '2025-12-09T09:00:00Z', 'obs-key')
    svc.process_outbox()
    assert cal.attempts >= 3


def test_logs_mask_sensitive_fields(capsys):
    DB['appointments'].clear(); DB['outbox'].clear(); DB['idempotency'].clear()
    cal = CalendarMock('ok')
    svc = AppointmentService(cal)
    res = svc.create_appointment('sensitive_user@example.com', '2025-12-10T09:00:00Z', 'mask-key')
    # Process and capture logs
    svc.process_outbox()
    captured = capsys.readouterr()
    logs = captured.out
    assert 'sensitive_user@example.com' not in logs
    assert 'user_id' in DB['appointments'][res['appointment_id']]


def test_acceptance_slo_success_rate():
    # simple acceptance: for a batch of 20, expect >=95% success within 3 retries
    DB['appointments'].clear(); DB['outbox'].clear(); DB['idempotency'].clear()
    class SometimesFlaky(CalendarMock):
        def __init__(self):
            super().__init__('sometimes')
            self.calls = 0
        def create_event(self, appt):
            self.calls += 1
            # fail first attempt for every third call
            if (self.calls % 3) == 1:
                raise TimeoutError('transient')
            return {'ok': True}

    cal = SometimesFlaky()
    svc = AppointmentService(cal, max_retries=3, base_backoff=0.001)
    success = 0
    for i in range(20):
        res = svc.create_appointment(f'user{i}', f'2025-12-11T0{i}:00:00Z', f'k{i}')
    try:
        svc.process_outbox()
    except Exception:
        pass
    for appt_id, appt in DB['appointments'].items():
        if appt['status'] == 'CONFIRMED':
            success += 1
    success_rate = success / max(1, len(DB['appointments']))
    assert success_rate >= 0.95

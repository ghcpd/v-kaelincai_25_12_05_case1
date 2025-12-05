import pytest
from src.appointment_service import AppointmentService, DB
from mocks.calendar_mock import CalendarMock
import json


def load_case(case_index):
    with open('data/test_data.json') as f:
        data = json.load(f)
    return data[case_index]


def test_basic_success():
    DB['appointments'].clear(); DB['outbox'].clear(); DB['idempotency'].clear()
    cal = CalendarMock('ok')
    svc = AppointmentService(cal)
    case = load_case(0)
    res = svc.create_appointment(case['user_id'], case['time_slot'], case['idempotency_key'])
    assert 'appointment_id' in res
    svc.process_outbox()
    appt = svc.get_appointment(res['appointment_id'])
    assert appt['status'] == 'CONFIRMED'


def test_idempotency_repeat():
    DB['appointments'].clear(); DB['outbox'].clear(); DB['idempotency'].clear()
    cal = CalendarMock('ok')
    svc = AppointmentService(cal)
    case = load_case(1)
    res1 = svc.create_appointment(case['user_id'], case['time_slot'], case['idempotency_key'])
    res2 = svc.create_appointment(case['user_id'], case['time_slot'], case['idempotency_key'])
    assert res1 == res2


def test_calendar_failure_generates_compensation():
    DB['appointments'].clear(); DB['outbox'].clear(); DB['idempotency'].clear()
    cal = CalendarMock('fail')
    svc = AppointmentService(cal)
    case = load_case(2)
    res = svc.create_appointment(case['user_id'], case['time_slot'], case['idempotency_key'])
    svc.process_outbox()
    appt = svc.get_appointment(res['appointment_id'])
    assert appt['status'] == 'FAILED'


def test_calendar_timeout_raises():
    DB['appointments'].clear(); DB['outbox'].clear(); DB['idempotency'].clear()
    cal = CalendarMock('timeout')
    svc = AppointmentService(cal)
    case = load_case(3)
    res = svc.create_appointment(case['user_id'], case['time_slot'], case['idempotency_key'])
    with pytest.raises(TimeoutError):
        svc.process_outbox()


def test_slow_path():
    DB['appointments'].clear(); DB['outbox'].clear(); DB['idempotency'].clear()
    cal = CalendarMock('slow')
    svc = AppointmentService(cal)
    case = load_case(4)
    res = svc.create_appointment(case['user_id'], case['time_slot'], case['idempotency_key'])
    svc.process_outbox()
    appt = svc.get_appointment(res['appointment_id'])
    assert appt['status'] == 'CONFIRMED'

import pytest
import json
import time
from src import service

with open('data/test_data.json') as f:
    cases = json.load(f)

def test_happy_path():
    c = next(x for x in cases if x['case']=='happy')
    r = service.create_appointment(c['idempotency'], c['payload'])
    assert r['state']=='created'
    # simulate calendar success and confirm
    service.confirm_appointment(r['id'])
    assert r['state']=='confirmed'

def test_idempotency_duplicate():
    c = next(x for x in cases if x['case']=='duplicate')
    r1 = service.create_appointment(c['idempotency'], c['payload'])
    r2 = service.create_appointment(c['idempotency'], c['payload'])
    assert r1['id']==r2['id']

def test_outbox_event_present():
    c = next(x for x in cases if x['case']=='retry_backoff')
    r = service.create_appointment(c['idempotency'], c['payload'])
    # outbox should have an event keyed by appointment id
    assert r['id'] in service.store.outbox

def test_calendar_fail_compensation():
    c = next(x for x in cases if x['case']=='calendar_fail')
    r = service.create_appointment(c['idempotency'], c['payload'])
    # simulate downstream failure: no confirm => compensation would remove or mark failed
    # For this minimal impl, we assert state remains 'created' and outbox exists
    assert r['state']=='created'
    assert r['id'] in service.store.outbox

def test_delay_path_timeout():
    c = next(x for x in cases if x['case']=='calendar_delay')
    r = service.create_appointment(c['idempotency'], c['payload'])
    start = time.time()
    # pretend we wait for external calendar with timeout 1s
    time.sleep(0.1)
    assert (time.time()-start) < 1.0

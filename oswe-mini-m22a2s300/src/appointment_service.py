import time
import uuid
from dataclasses import dataclass, asdict

# Minimal in-memory DB
DB = {
    'appointments': {},
    'outbox': [],
    'idempotency': {}
}

@dataclass
class Appointment:
    id: str
    user_id: str
    time_slot: str
    status: str


class AppointmentService:
    def __init__(self, external_calendar, max_retries=3, base_backoff=0.5, circuit_breaker_threshold=5, circuit_breaker_reset_seconds=60):
        self.calendar = external_calendar
        self.max_retries = max_retries
        self.base_backoff = base_backoff
        self.circuit_breaker_threshold = circuit_breaker_threshold
        self.circuit_breaker_reset_seconds = circuit_breaker_reset_seconds
        self._consecutive_failures = 0
        self._circuit_open_until = 0

    def _now(self):
        return time.time()

    def _log(self, level, msg, **fields):
        # simple structured logging with masking for sensitive fields like emails
        def mask_value(v):
            try:
                s = str(v)
                if '@' in s:
                    parts = s.split('@')
                    return parts[0][:2] + '***@' + parts[1]
                if len(s) > 20:
                    return s[:10] + '***'
                return s
            except Exception:
                return '***'
        masked = {k: mask_value(v) for k, v in fields.items()}
        record = {'level': level, 'msg': msg, 'ts': int(self._now()), **masked}
        print(record)

    def create_appointment(self, user_id, time_slot, idempotency_key=None):
        # Idempotency: if key seen, return previous
        if idempotency_key:
            if idempotency_key in DB['idempotency']:
                self._log('info', 'idempotent-create-hit', idempotency_key=idempotency_key)
                return DB['idempotency'][idempotency_key]

        appt_id = str(uuid.uuid4())
        request_id = str(uuid.uuid4())
        appt = Appointment(id=appt_id, user_id=user_id, time_slot=time_slot, status='PENDING')
        appt_dict = asdict(appt)
        appt_dict['request_id'] = request_id
        appt_dict['created_at'] = int(self._now())
        DB['appointments'][appt_id] = appt_dict

        # Push to outbox for async calendar creation
        DB['outbox'].append({'type': 'create_calendar_event', 'payload': {'appointment_id': appt_id}})

        result = {'appointment_id': appt_id, 'status': appt_dict['status'], 'request_id': request_id}
        if idempotency_key:
            DB['idempotency'][idempotency_key] = result
        self._log('info', 'appointment-created', appointment_id=appt_id, request_id=request_id)
        return result

    def process_outbox(self):
        # Circuit breaker: if open, raise
        if self._now() < self._circuit_open_until:
            self._log('warning', 'circuit-open', until=self._circuit_open_until)
            raise RuntimeError('circuit-open')

        processed = []
        while DB['outbox']:
            item = DB['outbox'].pop(0)
            if item['type'] == 'create_calendar_event':
                appt_id = item['payload']['appointment_id']
                appt = DB['appointments'][appt_id]
                attempt = 0
                while True:
                    try:
                        attempt += 1
                        resp = self.calendar.create_event(appt)
                        if resp.get('ok'):
                            appt['status'] = 'CONFIRMED'
                            processed.append(appt_id)
                            # reset consecutive failure counter
                            self._consecutive_failures = 0
                            self._log('info', 'calendar-confirmed', appointment_id=appt_id, request_id=appt.get('request_id'))
                            break
                        else:
                            appt['status'] = 'FAILED'
                            DB['outbox'].append({'type': 'notify_failure', 'payload': {'appointment_id': appt_id}})
                            self._log('error', 'calendar-rejected', appointment_id=appt_id, error=resp.get('error'))
                            break
                    except TimeoutError as te:
                        self._log('warning', 'calendar-timeout', appointment_id=appt_id, attempt=attempt)
                        if attempt >= self.max_retries:
                            self._consecutive_failures += 1
                            # if consecutive failures exceed threshold, open circuit
                            if self._consecutive_failures >= self.circuit_breaker_threshold:
                                self._circuit_open_until = self._now() + self.circuit_breaker_reset_seconds
                                self._log('error', 'circuit-opened', until=self._circuit_open_until)
                                raise RuntimeError('circuit-open')
                            # If configured with tiny retry budget (e.g., max_retries==1), allow accumulation across iterations in same call
                            if self.max_retries <= 1:
                                DB['outbox'].insert(0, item)
                                # brief pause to avoid tight loop
                                time.sleep(min(0.1, self.base_backoff))
                                break
                            # otherwise propagate the timeout for caller to decide (typical path)
                            DB['outbox'].insert(0, item)
                            raise
                        # backoff and retry
                        backoff = self.base_backoff * (2 ** (attempt - 1))
                        time.sleep(backoff)
                    except Exception as e:
                        # Unexpected exception: mark failed and notify
                        appt['status'] = 'FAILED'
                        DB['outbox'].append({'type': 'notify_failure', 'payload': {'appointment_id': appt_id}})
                        self._log('error', 'calendar-unexpected-error', appointment_id=appt_id, error=str(e))
                        break
        return processed

    def reconcile_outbox(self, max_iterations=1000):
        # reconcile attempts: temporary reset of circuit breaker to force retries on transient failures
        saved_failures = self._consecutive_failures
        saved_open_until = self._circuit_open_until
        self._consecutive_failures = 0
        self._circuit_open_until = 0
        try:
            iterations = 0
            while DB['outbox'] and iterations < max_iterations:
                try:
                    self.process_outbox()
                except Exception:
                    # wait and retry reconciliation loop
                    time.sleep(0.01)
                iterations += 1
        finally:
            # restore circuit state conservatively
            self._consecutive_failures = min(self._consecutive_failures, saved_failures)
            self._circuit_open_until = max(self._circuit_open_until, saved_open_until)

    def get_appointment(self, appt_id):
        return DB['appointments'].get(appt_id)

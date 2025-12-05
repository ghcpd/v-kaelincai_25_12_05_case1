class CalendarMock:
    def __init__(self, behavior='ok'):
        self.behavior = behavior
        self.calls = []

    def create_event(self, appt):
        self.calls.append(appt)
        if self.behavior == 'ok':
            return {'ok': True, 'event_id': 'evt-' + appt['id']}
        elif self.behavior == 'timeout':
            raise TimeoutError('calendar timeout')
        elif self.behavior == 'fail':
            return {'ok': False, 'error': 'declined'}
        elif self.behavior == 'slow':
            import time; time.sleep(1)
            return {'ok': True, 'event_id': 'evt-' + appt['id']}
        else:
            return {'ok': True}

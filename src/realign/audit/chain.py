"""Hash-linked audit events. Payloads come from closed validated runtime records."""
import hashlib
import json


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode('utf-8')


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


class AuditChain:
    def __init__(self):
        self._events = []

    @property
    def head(self):
        return self._events[-1]['hash'] if self._events else '0'*64

    @property
    def events(self):
        return json.loads(canonical(self._events))

    def append(self, kind, payload):
        value = {'sequence':len(self._events), 'kind':kind, 'payload':payload, 'previous':self.head}
        value['hash'] = digest(value)
        self._events.append(value)
        return value['hash']

    @staticmethod
    def verify(events):
        previous = '0'*64
        for i, item in enumerate(events):
            value = dict(item); actual = value.pop('hash')
            if value.get('sequence') != i or value.get('previous') != previous or digest(value) != actual:
                return False
            previous = actual
        return True

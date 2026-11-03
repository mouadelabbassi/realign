"""Public operator progress journal; never scientific admission evidence."""
from datetime import datetime, timezone
import json
from pathlib import Path
from realign.audit.chain import digest


def read_progress(path):
    value = json.loads(Path(path).read_text(encoding='utf-8'))
    parent = None
    for event in value['events']:
        clean = dict(event)
        sha = clean.pop('sha256')
        if clean['parent_sha256'] != parent or digest(clean) != sha:
            raise ValueError('operator progress journal changed')
        parent = sha
    return value


def record_progress(path, state):
    path = Path(path)
    events = read_progress(path)['events'] if path.is_file() else []
    event = {'state': state, 'utc': datetime.now(timezone.utc).isoformat(),
             'parent_sha256': events[-1]['sha256'] if events else None}
    event['sha256'] = digest(event)
    events.append(event)
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps({'scope': 'OPERATOR_PROGRESS_NOT_SCIENTIFIC_ADMISSION', 'events': events}, indent=2)+'\n', encoding='utf-8')
    temporary.replace(path)

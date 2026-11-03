"""Read-only projection of explicitly selected local capture and phone outputs."""
from pathlib import Path
from realign.physical.live_lab import read_catalog
from realign.physical.lab_progress import read_progress
from .closure import validate_phone, validate_independent_report
from .evidence import read_json


def load_lab(library_root, phone_root=None):
    result = read_catalog(library_root)
    result.update(state='IDLE', investigation=None, progress=[],
                  independent_validation={'status': 'NOT_RUN'},
                  execution='READ_ONLY_REPLAY; capture requires scripts/run_live_lab.py')
    if result['recordings']: result['state'] = 'REVIEW_REQUIRED'
    if phone_root is None: return result
    root = Path(phone_root)
    progress = root / 'lab_progress.json'
    if progress.is_file():
        result['progress'] = read_progress(progress)['events']
        if result['progress']: result['state'] = result['progress'][-1]['state']
    path = root / 'phone_status.json'
    if path.is_file():
        phone = read_json(path)
        cp = read_json(root / 'checkpoint.json') if phone.get('status') == 'PENDING_PHYSICAL_ACTION' else None
        trace = read_json(root / 'investigation.json') if phone.get('status') == 'FROZEN' else None
        validate_phone(phone, checkpoint=cp, trace=trace)
        allowed = ('status', 'blockers', 'pending_action', 'model_frozen', 'decision', 'baselines',
                   'checkpoint_sha256', 'trace_sha256', 'calibration_grade', 'physical_admission_history',
                   'actual_api_requests', 'api_accounting_scope')
        result['investigation'] = {k: phone[k] for k in allowed if k in phone}
        if not result['progress'] or result['progress'][-1]['state'] not in ('ADMISSION', 'ANALYSIS_READY', 'INVESTIGATING'):
            result['state'] = 'ABSTAIN' if phone.get('decision', {}).get('outcome') == 'ABSTAIN' else phone['status']
        independent = phone.get('independent_validation', {'status': 'NOT_RUN'})
        if 'commitment' in independent: validate_independent_report(independent)
        result['independent_validation'] = independent
        if trace: result['investigation']['parent_checkpoint_sha256'] = trace.get('parent_checkpoint_sha256')
    return result

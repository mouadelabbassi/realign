"""Offline inspection of saved live sessions; no SDK client, camera or writes."""
from collections import Counter
from pathlib import Path
import json
import re

from realign.audit.chain import AuditChain, digest
from realign.perception.video import probe_video, file_sha256
from realign.perception.workflow import load_sam_cache, _path
from .live_observation import analyze_masks


def inspect_session(path):
    folder = _path(str(path), Path.cwd())
    timeline = folder / 'timeline.jsonl'
    files = {p: file_sha256(p) for p in folder.rglob('*') if p.is_file()}
    events = [json.loads(line) for line in timeline.read_text(encoding='utf-8').splitlines()]
    if not events or not AuditChain.verify(events): raise ValueError('LIVE_AUDIT_INTEGRITY_FAILED')
    finalized = {e['payload']['window_id']: e['payload'] for e in events if e['kind'] == 'WINDOW_FINALIZED'}
    completed = {e['payload']['window_id']: e['payload'] for e in events if e['kind'] == 'SAM_COMPLETED'}
    cancelled = {e['payload']['window_id'] for e in events if e['kind'] == 'SAM_CANCELLED'}
    submitted = {e['payload']['window_id'] for e in events if e['kind'] == 'SAM_PENDING'}
    sources = [e['payload'] for e in events if e['kind'] == 'SOURCE_RECORDING_FINALIZED']
    verified_sources = []
    for source in sources:
        rid = source.get('recording_id', '')
        if not re.fullmatch(r'clip-[a-f0-9]{32}', rid): raise ValueError('LIVE_SOURCE_ID_INVALID')
        original = folder.parent / rid
        for p in original.rglob('*'):
            if p.is_file(): files[p] = file_sha256(p)
        meta = probe_video(original / 'recording.mp4', source_kind='REAL_PHONE')
        if meta.video_sha256 != source['video_sha256']: raise ValueError('ORIGINAL_CAPTURE_HASH_CHANGED')
        arrivals = original / 'arrivals.jsonl'
        if arrivals.exists() and file_sha256(arrivals) != source['capture']['arrivals_sha256']:
            raise ValueError('ORIGINAL_CAPTURE_ARRIVALS_CHANGED')
        verified_sources.append({'video_sha256': meta.video_sha256, 'decoded_pts_count': len(meta.pts),
            'source_size': [meta.width, meta.height], 'time_base': meta.time_base,
            'scope': 'ORIGINAL_BYTES_AND_CONTAINER_PTS_ONLY; NOT_VERIFIED_PHYSICAL_TIME'})
    windows = []
    for manifest_path in sorted(folder.glob('window-*/manifest.json')):
        manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
        window = manifest_path.parent
        if finalized.get(window.name, {}).get('manifest_sha256') != digest(manifest):
            raise ValueError('LIVE_WINDOW_MANIFEST_HASH_CHANGED')
        result_path = window / 'result.json'
        saved = json.loads(result_path.read_text(encoding='utf-8')) if result_path.exists() else None
        if window.name in completed and digest(saved) != completed[window.name]['result_sha256']:
            raise ValueError('LIVE_WINDOW_CONSUMED_RESULT_CHANGED')
        meta = probe_video(window / 'input.mp4', source_kind='REAL_PHONE')
        if manifest['video_sha256'] != meta.video_sha256 or len(meta.pts) != len(manifest['frames']):
            raise ValueError('LIVE_WINDOW_SOURCE_INTEGRITY_FAILED')
        result = {'window_id': window.name, 'video_sha256': meta.video_sha256,
            'manifest_sha256': digest(manifest), 'frames': len(meta.pts),
            'saved_status': saved.get('status') if saved else 'CANCELLED_NO_RESULT_SAVED' if window.name in cancelled
                else 'NOT_SUBMITTED' if window.name not in submitted else 'NO_RESULT_SAVED', 'offline_replay': 'NOT_AVAILABLE'}
        if (window / 'sam.json').exists():
            run = load_sam_cache(window / 'sam', meta)
            track, summary, diagnostic = analyze_masks(run, meta, manifest)
            result.update(offline_replay='ACTUAL_SAM_CACHE_ONLY; NO_NEW_API_CALL', diagnostic=diagnostic,
                replay_valid_frames=summary['valid_frames'], saved_identity_continuity=(saved or {}).get('identity_continuity'),
                api_operations=run.receipt.get('calls', []), actual_api_status=run.receipt['status'])
        windows.append(result)
    attempts = [e['payload'] for e in events if e['kind'] == 'API_ATTEMPT_RESERVED']
    rejections = [e['payload'] for e in events if e['kind'] == 'SCIENCE_EVENT_REJECTED']
    stopped = [e['payload'] for e in events if e['kind'] == 'AI_STOPPED']
    source = [e['payload'] for e in events if e['kind'] == 'SOURCE_RECORDING_FINALIZED']
    for p, sha in files.items():
        if file_sha256(p) != sha: raise ValueError('LIVE_EVIDENCE_CHANGED_DURING_READ_ONLY_INSPECTION')
    return {'scope': 'OFFLINE_FORENSICS; NO_NEW_META_CALLS; NOT_PHYSICAL_VALIDATION',
        'timeline_sha256': files[timeline], 'audit_head': events[-1]['hash'], 'files_verified_unchanged': len(files),
        'event_counts': dict(Counter(e['kind'] for e in events)), 'windows': windows,
        'reserved_attempts': dict(Counter(e['model'] for e in attempts)),
        'last_saved_usage': stopped[-1].get('usage') if stopped else None,
        'capture': sources[-1].get('capture') if sources else None, 'verified_original_captures': verified_sources,
        'science_rejections': [{'kind': e.get('kind'), 'error_type': e.get('error_type'),
            'code': e.get('code', 'LEGACY_DIAGNOSTIC_NOT_RECORDED'),
            'category': e.get('category', 'UNKNOWN; HTTP_VS_PROTOCOL_NOT_PRESERVED'),
            'http_status': e.get('http_status')} for e in rejections],
        'science_drops': 'LEGACY_COUNT_NOT_JOURNALED' if not any(e['kind'] == 'SCIENCE_CONTROL_REJECTED' for e in events) else
            sum(e['kind'] == 'SCIENCE_CONTROL_REJECTED' for e in events),
        'new_meta_requests': 0, 'physical_repair_certified': False}

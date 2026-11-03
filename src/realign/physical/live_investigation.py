"""Bounded local LIVE workers. Hosted SAM receives finalized MP4s, never a camera stream.

No exposure clock is inferred from encoder FPS. Window observations are pixels
only; admission to the existing scientific kernel is a separate fail-closed step.
"""
import asyncio
from collections import deque
from copy import deepcopy
from dataclasses import asdict, dataclass
from decimal import Decimal
import hashlib
import json
import os
from pathlib import Path
import queue
import threading
import time
import uuid

import numpy as np

from realign.audit.chain import AuditChain, digest
from realign.perception.sam_client import SamClient, SamError
from realign.perception.track import extract_track, TrackConfig
from realign.perception.video import file_sha256, probe_video
from realign.perception.workflow import save_sam_cache
from .live_lab import MP4Writer, utc_now, write_json


class AuthorizationError(ValueError):
    pass


@dataclass(frozen=True)
class LiveConfig:
    window_s: float = 4.
    overlap_s: float = .5
    sample_hz: float = 12.
    frame_queue: int = 8
    window_queue: int = 2
    timeout_s: float = 90.
    max_windows: int = 128

    def __post_init__(self):
        values = (self.window_s, self.overlap_s, self.sample_hz, self.timeout_s)
        if any(type(v) not in (float, int) or not np.isfinite(v) for v in values):
            raise ValueError('finite window settings required')
        if not 1 <= self.window_s <= 8 or not 0 <= self.overlap_s < self.window_s / 2:
            raise ValueError('window 1..8 seconds; overlap less than half a window')
        if not 2 <= self.sample_hz <= 24 or not 1 <= self.timeout_s <= 120:
            raise ValueError('sampling/timeout limit')
        for v, upper in ((self.frame_queue, 16), (self.window_queue, 4), (self.max_windows, 128)):
            if type(v) is not int or not 1 <= v <= upper: raise ValueError('queue/window limit')


class RequestLedger:
    """Reserve BEFORE dispatch, including failed attempts and SDK retries.

    Owner-reviewed per-attempt USD reserves bound authorized estimated spending.
    They are not a provider billing guarantee. In-flight requests may still bill.
    """
    def __init__(self, policy, record):
        required = {'consent', 'standard_tier_confirmed', 'sam_requests', 'muse_requests',
                    'ceiling_usd', 'sam_reserve_usd', 'muse_reserve_usd'}
        if set(policy) != required or policy['consent'] is not True or policy['standard_tier_confirmed'] is not True:
            raise AuthorizationError('Explicit upload/spending consent and Standard tier confirmation required')
        for name in ('sam_requests', 'muse_requests'):
            if type(policy[name]) is not int or not 1 <= policy[name] <= 32:
                raise AuthorizationError('Request caps must be integers in 1..32 (SAM uploads count too)')
        self.policy = deepcopy(policy)
        self.ceiling = self._money(policy['ceiling_usd'])
        self.rates = {k: self._money(policy[k + '_reserve_usd']) for k in ('sam', 'muse')}
        self.counts = {'sam': 0, 'muse': 0}
        self.reserved = Decimal('0')
        self.enabled = True
        self.lock = threading.RLock()
        self.record = record

    @staticmethod
    def _money(value):
        if type(value) not in (str, int, float): raise AuthorizationError('USD amount required')
        try: amount = Decimal(str(value))
        except Exception: raise AuthorizationError('USD amount required') from None
        if not amount.is_finite() or not Decimal('0') < amount <= Decimal('100'):
            raise AuthorizationError('USD amounts must be positive and at most 100')
        return amount

    def reserve(self, model, operation):
        with self.lock:
            if (not self.enabled or self.counts[model] >= self.policy[model + '_requests'] or
                    self.reserved + self.rates[model] > self.ceiling):
                raise AuthorizationError('AI_STOPPED_OR_AUTHORIZED_LIMIT_REACHED')
            self.counts[model] += 1
            self.reserved += self.rates[model]
            # Persist synchronously before making a network call. A crash can
            # conservatively overcount a reservation, never refund an unknown call.
            self.record('API_ATTEMPT_RESERVED', {'model': model, 'operation': operation,
                'attempt': self.counts[model], 'reserved_usd': str(self.reserved)})

    def stop(self):
        with self.lock: self.enabled = False

    def snapshot(self):
        with self.lock:
            return {'enabled': self.enabled, 'attempted_requests': dict(self.counts),
                'total_requests': sum(self.counts.values()), 'reserved_usd': str(self.reserved),
                'ceiling_usd': str(self.ceiling), 'policy': deepcopy(self.policy),
                'billing_status': 'UNVERIFIED; owner-supplied reserves; billed costs may differ; in-flight calls may bill'}


class LiveInvestigation:
    def __init__(self, root, policy, *, config=None, source='REAL_PHONE', sam_factory=None,
                 reasoner_factory=None):
        if source not in ('REAL_PHONE', 'TEST_FIXTURE'): raise ValueError('explicit source required')
        self.root = Path(root) / ('live-' + uuid.uuid4().hex)
        self.root.mkdir(parents=True)
        self.source = source
        self.config = config or LiveConfig()
        self.lock = threading.RLock()
        self.audit = AuditChain()
        self.cancel = threading.Event()
        self.frames = queue.Queue(self.config.frame_queue)
        self.windows = queue.Queue(self.config.window_queue)
        self.science = queue.Queue(2)
        self.latest = None
        self.processed_jpeg = None
        self.processed_frames = {}
        self.trajectory = {}
        self.events = deque(maxlen=80)
        self.dropped = {'frames': 0, 'windows': 0, 'science': 0}
        self.finalized = 0
        self.processed = 0
        self.last_sample = None
        self.last_source = None
        self.active_action = None
        self.history = []
        self.pending_action = None
        self.scientific = {'state': 'PRELIMINARY_OBSERVATION', 'hypotheses': [], 'tool_results': [],
                           'blockers': ['INDEPENDENT_TIMING_CALIBRATION_RELEASE_AND_REVIEWS_REQUIRED'],
                           'physical_evidence_accepted': False}
        self.ledger = RequestLedger(policy, self.record)
        self.record('AUTHORIZED', {'source': source, 'models': ['sam-3.1', 'muse-spark-1.3'],
                                  'policy': policy, 'windowing': asdict(self.config)})
        self.sam_factory = sam_factory or self._sam
        self.reasoner_factory = reasoner_factory
        self.threads = [threading.Thread(target=target, daemon=True, name=name)
            for target, name in ((self._encode_loop, 'live-window-encoder'),
                                 (self._sam_loop, 'live-sam'), (self._science_loop, 'live-science'))]
        for thread in self.threads: thread.start()

    def record(self, kind, payload):
        with self.lock:
            body = {'utc': utc_now(), 'monotonic_ns': time.monotonic_ns(), **deepcopy(payload)}
            self.audit.append(kind, body)
            event = self.audit.events[-1]
            # Append-only journal is authoritative, independent of UI history.
            with (self.root / 'timeline.jsonl').open('a', encoding='utf-8') as f:
                f.write(json.dumps(event, allow_nan=False) + '\n')
                f.flush()
                if kind == 'API_ATTEMPT_RESERVED': os.fsync(f.fileno())
            self.events.append(event)

    def _sam(self):
        from realign.local_environment import load_model_key
        load_model_key(Path(__file__).resolve().parents[3] / '.env')
        client = SamClient.from_environment(standard_tier_confirmed=True)
        client.before_request = self.ledger.reserve
        client.max_attempts = 2
        return client

    def offer(self, frame, mapping):
        """Camera hot path: bounded copy and nonblocking enqueue, no network/disk IO."""
        if self.cancel.is_set(): return
        stamp = mapping['arrival_monotonic_ns']
        source = mapping['recording_id']
        if self.last_source == source and self.last_sample is not None and stamp - self.last_sample < 1e9 / self.config.sample_hz:
            return
        self.last_sample, self.last_source = stamp, source
        import cv2
        h, w = frame.shape[:2]
        scale = min(1., 640 / w, 480 / h)
        size = (max(2, int(w * scale) // 2 * 2), max(2, int(h * scale) // 2 * 2))
        small = cv2.resize(frame, size) if size != (w, h) else frame.copy()
        item = (small, {**mapping, 'source_size': [w, h], 'processed_size': list(size),
                        'response_to_request_id': self.active_action})
        try: self.frames.put_nowait(item)
        except queue.Full:
            with self.lock: self.dropped['frames'] += 1

    def boundary(self, reason):
        # Source changes and action IDs also split windows, so a dropped marker
        # cannot combine independent experiments into one observation.
        try: self.frames.put_nowait((None, {'reason': reason}))
        except queue.Full:
            with self.lock: self.dropped['frames'] += 1
        self.record('CAPTURE_BOUNDARY', {'reason': reason})

    def _encode_loop(self):
        buffer = []
        try:
            while not self.cancel.is_set():
                try: frame, mapping = self.frames.get(timeout=.1)
                except queue.Empty: continue
                if frame is None:
                    if len(buffer) >= 2: self._finalize(buffer, partial=True)
                    buffer = []
                    continue
                mapping['processed_frame_sha256'] = hashlib.sha256(frame.tobytes()).hexdigest()
                if buffer and (mapping['recording_id'], mapping['response_to_request_id']) != (
                        buffer[0][1]['recording_id'], buffer[0][1]['response_to_request_id']):
                    if len(buffer) >= 2: self._finalize(buffer, partial=True)
                    buffer = []
                if buffer and mapping['arrival_monotonic_ns'] <= buffer[-1][1]['arrival_monotonic_ns']:
                    self.record('FRAME_REJECTED', {'code': 'NON_MONOTONIC_ARRIVAL', 'mapping': mapping})
                    continue
                buffer.append((frame, mapping))
                elapsed = (mapping['arrival_monotonic_ns'] - buffer[0][1]['arrival_monotonic_ns']) / 1e9
                if elapsed >= self.config.window_s or len(buffer) >= 256:
                    self._finalize(buffer, partial=False)
                    cutoff = mapping['arrival_monotonic_ns'] - self.config.overlap_s * 1e9
                    buffer = [item for item in buffer if item[1]['arrival_monotonic_ns'] >= cutoff]
        except Exception as exc:
            self.record('ENCODER_WORKER_FAILED', {'error_type': type(exc).__name__})

    def _finalize(self, buffer, *, partial):
        if self.finalized >= self.config.max_windows or self.cancel.is_set():
            with self.lock: self.dropped['windows'] += 1
            return
        self.finalized += 1
        folder = self.root / f'window-{self.finalized:04d}'
        folder.mkdir()
        started = time.monotonic()
        frame = buffer[0][0]
        writer = MP4Writer(folder / 'input.mp4', self.config.sample_hz, (frame.shape[1], frame.shape[0]))
        try:
            for image, _ in buffer: writer.write(image)
        finally: writer.release()
        meta = probe_video(folder / 'input.mp4', source_kind='SYNTHETIC_RENDER' if self.source == 'TEST_FIXTURE' else 'REAL_PHONE')
        if len(meta.pts) != len(buffer): raise ValueError('WINDOW_FRAME_COUNT_MISMATCH')
        rows = [{**row, 'window_frame_index': i, 'window_pts': meta.pts[i], 'window_time_base': meta.time_base}
                for i, (_, row) in enumerate(buffer)]
        manifest = {'window_id': folder.name, 'source': self.source, 'video_sha256': meta.video_sha256,
            'created_utc': utc_now(), 'partial_capture_window': partial, 'frames': rows,
            'timing_basis': 'SOFTWARE_CFR_PLAYBACK; HOST_MONOTONIC_ARRIVAL_AFTER_READ',
            'capture_time_scale_verified': False, 'physical_fitting_allowed': False,
            'encoding_latency_s': time.monotonic() - started}
        write_json(folder / 'manifest.json', manifest)
        self.record('WINDOW_FINALIZED', {'window_id': folder.name, 'manifest_sha256': digest(manifest),
                                        'encoding_latency_s': manifest['encoding_latency_s']})
        try: self.windows.put_nowait((folder, meta, manifest, time.monotonic()))
        except queue.Full:
            with self.lock: self.dropped['windows'] += 1
            write_json(folder / 'result.json', {'status': 'BACKPRESSURE_NOT_UPLOADED', 'actual_requests': 0})
            self.record('WINDOW_SKIPPED', {'window_id': folder.name, 'code': 'SAM_QUEUE_FULL'})

    async def _process(self, client, folder, meta, manifest, queued):
        start = time.monotonic()
        self.record('SAM_PENDING', {'window_id': folder.name, 'queue_latency_s': start - queued})
        try:
            run = await asyncio.wait_for(client.segment_video(folder / 'input.mp4', meta), self.config.timeout_s)
            if self.cancel.is_set():
                self.record('SAM_RESULT_AFTER_STOP', {'window_id': folder.name})
                return
            if run.video_sha256 != meta.video_sha256 or run.receipt.get('status') != 'completed':
                raise SamError('partial stream is not a track', code='incomplete')
            save_sam_cache(folder / 'sam', run)
            if self.source == 'REAL_PHONE' and run.source != 'REAL_API':
                raise SamError('fixture cannot be phone evidence', code='provenance')
            cache = self.root / 'sam_cache'
            cache.mkdir(exist_ok=True)
            save_sam_cache(cache / meta.video_sha256, run)
            # CFR playback speed cannot reject a measurement on physical-speed
            # grounds. Contour/identity/area QA still applies to preliminary pixels.
            track = extract_track(run, meta, config=TrackConfig(max_speed_px_per_s=float('inf')))
            object_id = track.summary['object_id']
            rows = []
            for i in np.flatnonzero(track.valid):
                row = manifest['frames'][int(i)]
                rows.append({**row, 'xy_px': track.xy_px[i].tolist(), 'object_id': object_id,
                             'window_id': folder.name, 'window_video_sha256': meta.video_sha256})
            result = {'status': 'PRELIMINARY_OBSERVATION' if rows else 'EMPTY_OR_QUARANTINED',
                'source': self.source, 'window_id': folder.name, 'receipt': run.receipt,
                'track': track.summary, 'rows': rows, 'latency_s': time.monotonic() - start,
                'end_to_end_latency_s': time.monotonic() - queued,
                'latency_scope': 'FINALIZED_WINDOW_QUEUE_TO_RESULT; CAPTURE_AND_ENCODING_EXCLUDED',
                'physical_fitting_allowed': False, 'complete_validated_track': False}
            jpeg = self._render_processed(folder, rows[-1]) if rows else None
            with self.lock:
                # IDs are scoped to each SAM response. Cross-window identity is
                # admitted only through agreeing overlapping source frames.
                overlap = [(self.trajectory[(r['recording_id'], r['capture_sequence'], r['arrival_monotonic_ns'])], r)
                    for r in rows if (r['recording_id'], r['capture_sequence'], r['arrival_monotonic_ns']) in self.trajectory]
                continuity = not self.trajectory or bool(overlap) and all(
                    old['object_id'] == new['object_id'] and np.linalg.norm(np.array(old['xy_px']) - new['xy_px']) <= 3
                    for old, new in overlap)
                result['identity_continuity'] = 'OVERLAP_AGREEMENT' if continuity else 'UNVERIFIED_OR_DISCONTINUOUS'
                result['new_observations'] = 0
                for row in rows:
                    key = (row['recording_id'], row['capture_sequence'], row['arrival_monotonic_ns'])
                    if key not in self.trajectory:
                        self.trajectory[key] = row
                        result['new_observations'] += 1
                # Session capture is bounded by max_windows and finite frame budgets.
                self.latest = result
                if jpeg:
                    self.processed_jpeg = jpeg
                    self.processed_frames[folder.name] = jpeg
                    while len(self.processed_frames) > 2:
                        del self.processed_frames[next(iter(self.processed_frames))]
                self.processed += 1
            write_json(folder / 'result.json', result)
            self.record('SAM_COMPLETED', {**{k: result[k] for k in ('window_id', 'latency_s', 'end_to_end_latency_s', 'new_observations', 'identity_continuity')},
                'result_sha256': digest(result), 'mask_index_sha256': file_sha256(folder / 'sam.json'),
                'mask_arrays_sha256': file_sha256(folder / 'sam.npz')})
            if rows: self.enqueue_science('observation', result)
        except asyncio.CancelledError:
            self.record('SAM_CANCELLED', {'window_id': folder.name})
            raise
        except Exception as exc:
            code = exc.code if isinstance(exc, SamError) else type(exc).__name__
            result = {'status': 'FAILED', 'code': code, 'window_id': folder.name,
                      'latency_s': time.monotonic() - start, 'complete_validated_track': False,
                      'calls': list(exc.calls) if isinstance(exc, SamError) else []}
            write_json(folder / 'result.json', result)
            self.record('SAM_FAILED', result)

    def _render_processed(self, folder, row):
        import cv2
        video = cv2.VideoCapture(str(folder / 'input.mp4'))
        try:
            video.set(cv2.CAP_PROP_POS_FRAMES, row['window_frame_index'])
            ok, image = video.read()
            if ok:
                cv2.circle(image, tuple(round(x) for x in row['xy_px']), 10, (70, 255, 170), 2)
                ok, jpeg = cv2.imencode('.jpg', image)
                if ok: return jpeg.tobytes()
        finally: video.release()

    def _sam_loop(self):
        async def run():
            client = None
            try:
                while not self.cancel.is_set():
                    try: item = self.windows.get_nowait()
                    except queue.Empty:
                        await asyncio.sleep(.05)
                        continue
                    if client is None: client = self.sam_factory()
                    task = asyncio.create_task(self._process(client, *item))
                    while not task.done():
                        if self.cancel.is_set(): task.cancel()
                        await asyncio.wait({task}, timeout=.05)
                    try: await task
                    except asyncio.CancelledError: pass
            except Exception as exc:
                self.record('SAM_WORKER_UNAVAILABLE', {'error_type': type(exc).__name__})
            finally:
                if client is not None: await client.close()
        asyncio.run(run())

    def enqueue_science(self, kind, payload):
        if self.cancel.is_set(): raise ValueError('AI investigation is stopped')
        try: self.science.put_nowait((kind, deepcopy(payload)))
        except queue.Full:
            with self.lock: self.dropped['science'] += 1
            if kind != 'observation': raise ValueError('Scientific worker busy; retry after completion')

    def _science_loop(self):
        reasoner = None
        try:
            from .live_science import LiveScientificSession
            reasoner = self.reasoner_factory(self) if self.reasoner_factory else LiveScientificSession(self)
            while not self.cancel.is_set():
                try: kind, value = self.science.get(timeout=.1)
                except queue.Empty: continue
                try: reasoner.consume(kind, value)
                except Exception as exc:
                    self.record('SCIENCE_EVENT_REJECTED', {'kind': kind, 'error_type': type(exc).__name__})
                    if not self.pending_action and self.scientific['state'] == 'AGENT_INVESTIGATING':
                        self.scientific['state'] = 'CALIBRATED_OBSERVATION' if self.scientific['physical_evidence_accepted'] else 'PRELIMINARY_OBSERVATION'
        finally:
            if reasoner is not None: reasoner.close()

    def confirm_action(self, request_id):
        with self.lock:
            if self.cancel.is_set(): raise ValueError('AI investigation is stopped')
            pending = self.pending_action
            if not pending or pending['request_id'] != request_id or pending.get('confirmed_utc'):
                raise ValueError('Unconfirmed pending physical request required')
            pending['confirmed_utc'] = utc_now()
            self.active_action = request_id
            self.record('OPERATOR_ACTION_CONFIRMED', {'request_id': request_id, 'action': pending['candidate']['action']})

    def stop(self, reason='OPERATOR_STOP'):
        self.ledger.stop()  # Reject new requests before cancellation or IO.
        self.cancel.set()
        self.record('AI_STOPPED', {'reason': reason, 'usage': self.ledger.snapshot()})

    def close(self):
        self.stop('CONTROLLER_SHUTDOWN')
        for thread in self.threads: thread.join(timeout=2)

    def snapshot(self):
        usage = self.ledger.snapshot()
        with self.lock:
            return {'id': self.root.name, 'source': self.source, 'usage': usage,
                'state': 'STOPPED' if self.cancel.is_set() else self.scientific['state'],
                'windowing': asdict(self.config), 'finalized_windows': self.finalized,
                'processed_windows': self.processed, 'queued_frames': self.frames.qsize(),
                'queued_windows': self.windows.qsize(), 'dropped': dict(self.dropped),
                'unique_observations': len(self.trajectory), 'latest': deepcopy(self.latest),
                'scientific': deepcopy(self.scientific), 'pending_action': deepcopy(self.pending_action),
                'experiment_history': deepcopy(self.history), 'events': list(self.events), 'audit_head': self.audit.head}


def inspect_interrupted(root):
    """Read journals without issuing requests, replaying calls or refunding attempts."""
    records = []
    for path in sorted(Path(root).glob('live-*/timeline.jsonl')):
        try:
            events = [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines()]
            if not AuditChain.verify(events): raise ValueError('journal integrity')
            attempts = [e['payload'] for e in events if e['kind'] == 'API_ATTEMPT_RESERVED']
            records.append({'id': path.parent.name, 'state': 'STOPPED' if any(e['kind'] == 'AI_STOPPED' for e in events) else 'INTERRUPTED',
                'reserved_attempts': len(attempts), 'audit_head': events[-1]['hash'],
                'automatic_calls': 0, 'recovery': 'PRESERVE_EVIDENCE_AND_REVIEW; NO_AUTOMATIC_REPLAY'})
        except (OSError, ValueError, KeyError, TypeError):
            records.append({'id': path.parent.name, 'state': 'AUDIT_UNAVAILABLE', 'automatic_calls': 0})
    return records

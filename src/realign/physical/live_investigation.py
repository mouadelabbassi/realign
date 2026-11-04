"""Bounded local LIVE workers. Hosted SAM receives finalized MP4s, never a camera stream.

No exposure clock is inferred from encoder FPS. Window observations are pixels
only; admission to the existing scientific kernel is a separate fail-closed step.
"""
import asyncio
from collections import deque
from copy import deepcopy
from dataclasses import asdict, dataclass, replace
from decimal import Decimal
import hashlib
import json
import os
from pathlib import Path
import queue
import re
import threading
import time
import uuid
from types import SimpleNamespace

import numpy as np

from realign.audit.chain import AuditChain, digest
from realign.audit.terminal import emit
from realign.perception.sam_client import SamClient, SamError
from .live_observation import analyze_masks, summarize_pixel_motion, material_pixel_change
from realign.perception.video import file_sha256, probe_video
from realign.perception.workflow import save_sam_cache
from .live_lab import MP4Writer, utc_now, write_json


class AuthorizationError(ValueError):
    code = 'AUTHORIZED_LIMIT_REACHED'


class LiveJournalTail:
    """Bounded in-memory tail; the complete hash chain is the on-disk journal."""
    def __init__(self):self._events=deque(maxlen=80);self.count=0;self.head='0'*64
    @property
    def events(self):return deepcopy(list(self._events))
    def append(self,kind,payload):
        event={'sequence':self.count,'kind':kind,'payload':deepcopy(payload),'previous':self.head}
        event['hash']=digest(event);self.head=event['hash'];self.count+=1;self._events.append(event)
        return self.head


@dataclass(frozen=True)
class LiveConfig:
    window_s: float = 4.
    overlap_s: float = .5
    sample_hz: float = 12.
    frame_queue: int = 8
    window_queue: int = 2
    timeout_s: float = 90.
    max_windows: int = 128
    analysis_interval_s: float = 0.  # 0 retains explicit overlapping-window cadence.
    processing_width: int = 640
    target_prompt: str = 'the pendulum bob'
    target_confirmed: bool = False
    mode: str = 'MANUAL'
    continuous: bool = False

    def __post_init__(self):
        values = (self.window_s, self.overlap_s, self.sample_hz, self.timeout_s, self.analysis_interval_s)
        if any(type(v) not in (float, int) or not np.isfinite(v) for v in values):
            raise ValueError('finite window settings required')
        if not 1 <= self.window_s <= 8 or not 0 <= self.overlap_s < self.window_s / 2:
            raise ValueError('window 1..8 seconds; overlap less than half a window')
        if not 2 <= self.sample_hz <= 24 or not 1 <= self.timeout_s <= 120:
            raise ValueError('sampling/timeout limit')
        for v, upper in ((self.frame_queue, 16), (self.window_queue, 4), (self.max_windows, 128)):
            if type(v) is not int or not 1 <= v <= upper: raise ValueError('queue/window limit')
        if self.analysis_interval_s != 0 and not self.window_s-self.overlap_s <= self.analysis_interval_s <= 120:
            raise ValueError('Analysis interval must be at least window minus overlap, and at most 120 seconds')
        if type(self.processing_width) is not int or self.processing_width not in (640, 960, 1280):
            raise ValueError('Processing width must be 640, 960 or 1280 pixels')
        if not isinstance(self.target_prompt, str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9 -]{0,79}', self.target_prompt):
            raise ValueError('Select a visual target phrase of 1..80 letters, digits, spaces or hyphens')
        if type(self.target_confirmed) is not bool: raise ValueError('Target confirmation must be boolean')
        if self.mode not in ('MANUAL','AUTO_LIVE'): raise ValueError('Explicit live mode required')
        if type(self.continuous) is not bool or self.continuous and self.mode!='AUTO_LIVE':
            raise ValueError('Continuous mode requires AUTO_LIVE')

    @property
    def cadence_s(self):
        return self.analysis_interval_s or self.window_s-self.overlap_s


class RequestLedger:
    """Reserve BEFORE dispatch, including failed attempts and SDK retries.

    Owner-reviewed per-attempt USD reserves bound authorized estimated spending.
    They are not a provider billing guarantee. In-flight requests may still bill.
    """
    def __init__(self, policy, record, *, continuous=False):
        required = {'consent', 'standard_tier_confirmed', 'sam_requests', 'muse_requests',
                    'ceiling_usd', 'sam_reserve_usd', 'muse_reserve_usd'}
        if set(policy) != required or policy['consent'] is not True or policy['standard_tier_confirmed'] is not True:
            raise AuthorizationError('Explicit upload/spending consent and Standard tier confirmation required')
        for name in ('sam_requests', 'muse_requests'):
            if continuous and policy[name] is None: continue
            if type(policy[name]) is not int or not 1 <= policy[name] <= 32:
                raise AuthorizationError('Request caps must be integers in 1..32 (SAM uploads count too)')
        self.policy = deepcopy(policy)
        self.ceiling = self._money(policy['ceiling_usd'])
        self.rates = {k: self._money(policy[k + '_reserve_usd']) for k in ('sam', 'muse')}
        if continuous:
            # Keep every addition exact at Decimal's default precision. The UI
            # uses a .001 USD minimum; sub-microdollar fractions cannot silently
            # round away after an accumulated reserve grows.
            for amount in (self.ceiling, *self.rates.values()):
                if amount < Decimal('.001') or amount != amount.quantize(Decimal('.000001')):
                    raise AuthorizationError('Continuous USD amounts require at least .001 and at most six decimal places')
        self.counts = {'sam': 0, 'muse': 0}
        self.reserved = Decimal('0')
        self.enabled = True
        self.paused = False
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
            cap = self.policy[model + '_requests']
            if (not self.enabled or self.paused or cap is not None and self.counts[model] >= cap or
                    self.reserved + self.rates[model] > self.ceiling):
                emit('API_REQUEST_BLOCKED',model=model,operation=operation,code='AI_STOPPED_PAUSED_OR_SPENDING_CAP_REACHED')
                raise AuthorizationError('AI_STOPPED_OR_AUTHORIZED_LIMIT_REACHED')
            self.counts[model] += 1
            self.reserved += self.rates[model]
            # Persist synchronously before making a network call. A crash can
            # conservatively overcount a reservation, never refund an unknown call.
            self.record('API_ATTEMPT_RESERVED', {'model': model, 'operation': operation,
                'attempt': self.counts[model], 'reserved_usd': str(self.reserved)})

    def stop(self):
        with self.lock: self.enabled = False

    def pause(self, paused):
        with self.lock:
            if not self.enabled: raise AuthorizationError('Authorization was revoked; it cannot be resumed')
            self.paused = paused

    def snapshot(self):
        with self.lock:
            return {'enabled': self.enabled, 'paused': self.paused, 'attempted_requests': dict(self.counts),
                'total_requests': sum(self.counts.values()), 'reserved_usd': str(self.reserved),
                'ceiling_usd': str(self.ceiling), 'policy': deepcopy(self.policy),
                'remaining_reserve_usd':str(self.ceiling-self.reserved),
                'spending_cap_reached':self.reserved+min(self.rates.values())>self.ceiling,
                'billing_status': 'UNVERIFIED; owner-supplied reserves; billed costs may differ; in-flight calls may bill'}


class LiveInvestigation:
    def __init__(self, root, policy, *, config=None, source='REAL_PHONE', sam_factory=None,
                 reasoner_factory=None):
        if source not in ('REAL_PHONE', 'TEST_FIXTURE'): raise ValueError('explicit source required')
        self.source = source
        self.config = config or LiveConfig()
        if source == 'REAL_PHONE' and not self.config.target_confirmed:
            raise AuthorizationError('Select and confirm the visible target prompt before authorizing uploads')
        self.root = Path(root) / ('live-' + uuid.uuid4().hex)
        self.root.mkdir(parents=True)
        self.lock = threading.RLock()
        self.audit = LiveJournalTail() if self.config.continuous else AuditChain()
        self.cancel = threading.Event()
        self.paused = threading.Event()
        self.request_epoch = 0
        self.startup = queue.Queue(1)
        self.startup_scheduled = False
        self.target_blocked = False
        self.target_revision = 0
        self.overlay = None
        self.overlay_jpeg = None
        self.overlay_revision = 0
        self.source_seen = False
        self.startup_result = None
        self.perception_error = None
        self.frames = queue.Queue(self.config.frame_queue)
        self.windows = queue.Queue(self.config.window_queue)
        self.science = queue.Queue(2)
        self.pending_observation = None
        self.operator_pending = False
        self.science_busy = False
        self.latest = None
        self.processed_jpeg = None
        self.processed_frames = {}
        self.trajectory = {}
        self.observation_count = 0
        self.events = deque(maxlen=80)
        self.dropped = {'frames': 0, 'windows': 0, 'science': 0}
        self.skipped = {}
        self.coalesced_observations = 0
        self.pending_upload_keys = set()
        self.submitted_upload_keys = set()
        self.upload_index = None
        if self.config.continuous:
            import sqlite3
            self.upload_index=sqlite3.connect(self.root/'submitted.sqlite3',check_same_thread=False)
            self.upload_index.execute('CREATE TABLE submitted (hash TEXT, prompt TEXT, PRIMARY KEY(hash,prompt))')
        self.sam_active_window = None
        self.last_sam_latency_s = None
        self.effective_interval_s = self.config.cadence_s
        self.cadence_skipped_frames = 0
        self.finalized = 0
        self.processed = 0
        self.usable_windows = 0
        self.last_sample = None
        self.last_source = None
        self.active_action = None
        self.history = []
        self.pending_action = None
        self.scientific = {'state': 'PRELIMINARY_OBSERVATION', 'hypotheses': [], 'tool_results': [],
                           'blockers': ['INDEPENDENT_TIMING_CALIBRATION_RELEASE_AND_REVIEWS_REQUIRED'],
                           'physical_evidence_accepted': False}
        self.scientific['readiness'] = {'source': 'LOCAL_DETERMINISTIC_READINESS', 'can_reason': False,
            'code': 'NO_USABLE_OBSERVATIONS', 'operator_request': 'Wait for usable SAM masks and review the selected target. No Muse call is needed to explain an empty observation.'}
        self.ledger = RequestLedger(policy, self.record,continuous=self.config.continuous)
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
            fields = dict(payload,session=self.root.name)
            if kind == 'AUTHORIZED':
                fields.update(ceiling_usd=payload['policy']['ceiling_usd'],continuous=self.config.continuous)
            if kind == 'AI_STOPPED':
                fields.update({k:payload['usage'][k] for k in ('total_requests','reserved_usd','ceiling_usd')})
            turn = payload.get('reply',{}).get('turn') or {}
            if turn: fields.update(action=turn.get('action'),outcome=turn.get('outcome'),step=payload.get('step'))
            calls = payload.get('calls') or []
            if calls: fields.update({k:calls[-1].get(k) for k in ('http_status','code','category','error_type')})
            if kind=='SCIENTIFIC_TOOL':fields.update(tool=payload.get('name'),evidence_ref=payload.get('result',{}).get('evidence_ref'))
            emit(kind,**fields)

    def _sam(self):
        from realign.local_environment import load_model_key
        load_model_key(Path(__file__).resolve().parents[3] / '.env')
        client = SamClient.from_environment(standard_tier_confirmed=True, concept=self.config.target_prompt)
        client.before_request = self.ledger.reserve
        client.max_attempts = 2
        return client

    def offer(self, frame, mapping):
        """Camera hot path: bounded copy and nonblocking enqueue, no network/disk IO."""
        if self.cancel.is_set() or self.paused.is_set(): return
        stamp = mapping['arrival_monotonic_ns']
        source = mapping['recording_id']
        if self.last_source == source and self.last_sample is not None and stamp - self.last_sample < 1e9 / self.config.sample_hz:
            return
        self.last_sample, self.last_source = stamp, source
        import cv2
        h, w = frame.shape[:2]
        scale = min(1., self.config.processing_width / w, min(720, self.config.processing_width*.75) / h)
        size = (max(2, int(w * scale) // 2 * 2), max(2, int(h * scale) // 2 * 2))
        small = cv2.resize(frame, size) if size != (w, h) else frame.copy()
        item = (small, {**mapping, 'source_size': [w, h], 'processed_size': list(size),
                        'source_frame_sha256': hashlib.sha256(frame.tobytes()).hexdigest(),
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
        next_start_ns = None
        context = None
        try:
            while not self.cancel.is_set():
                try: frame, mapping = self.frames.get(timeout=.1)
                except queue.Empty: continue
                if frame is None:
                    if len(buffer) >= 2: self._finalize(buffer, partial=True)
                    buffer = []
                    next_start_ns = None
                    continue
                mapping['processed_frame_sha256'] = hashlib.sha256(frame.tobytes()).hexdigest()
                if self.paused.is_set(): continue
                self.source_seen = True
                if self.config.mode == 'AUTO_LIVE' and not self.startup_scheduled and not self.target_blocked:
                    self._startup_frame(frame, mapping)
                new_context = (mapping['recording_id'], mapping['response_to_request_id'])
                if context != new_context:
                    if len(buffer) >= 2: self._finalize(buffer, partial=True)
                    buffer = []
                    next_start_ns = None
                    context = new_context
                if not buffer and next_start_ns is not None and mapping['arrival_monotonic_ns'] < next_start_ns:
                    self.cadence_skipped_frames += 1
                    continue
                if buffer and mapping['arrival_monotonic_ns'] <= buffer[-1][1]['arrival_monotonic_ns']:
                    self.record('FRAME_REJECTED', {'code': 'NON_MONOTONIC_ARRIVAL', 'mapping': mapping})
                    continue
                buffer.append((frame, mapping))
                elapsed = (mapping['arrival_monotonic_ns'] - buffer[0][1]['arrival_monotonic_ns']) / 1e9
                if elapsed >= self.config.window_s or len(buffer) >= 256:
                    next_start_ns = buffer[0][1]['arrival_monotonic_ns'] + self.effective_interval_s*1e9
                    self._finalize(buffer, partial=False)
                    buffer = ([item for item in buffer if item[1]['arrival_monotonic_ns'] >= next_start_ns]
                              if self.config.overlap_s and self.config.cadence_s < self.config.window_s else [])
        except Exception as exc:
            self.record('ENCODER_WORKER_FAILED', {'error_type': type(exc).__name__})

    def _startup_frame(self, frame, mapping):
        import cv2
        folder = self.root / f'startup-{self.target_revision:04d}'
        folder.mkdir()
        path = folder / 'input.png'
        if not cv2.imwrite(str(path),frame): raise ValueError('STARTUP_IMAGE_WRITE_FAILED')
        sha = file_sha256(path)
        meta = SimpleNamespace(width=frame.shape[1],height=frame.shape[0],pts=(0,),t_s=np.array([0.]),video_sha256=sha)
        manifest = {'window_id':folder.name,'media_kind':'image','image_sha256':sha,'source':self.source,
            'target_prompt':self.config.target_prompt,'target_confirmed':self.config.target_confirmed,
            'target_revision':self.target_revision,'created_utc':utc_now(),
            'frames':[{**mapping,'window_frame_index':0}], 'capture_time_scale_verified':False,
            'physical_fitting_allowed':False,'timing_basis':'HOST_ARRIVAL_NOT_EXPOSURE; STILL_IMAGE_HAS_NO_FPS'}
        write_json(folder / 'manifest.json',manifest)
        self.startup_scheduled = True
        self.startup.put_nowait((folder,meta,manifest,time.monotonic()))
        self.record('STARTUP_IMAGE_READY',{'window_id':folder.name,'image_sha256':sha,'manifest_sha256':digest(manifest),
            'recording_id':mapping['recording_id'],'capture_sequence':mapping['capture_sequence']})

    def _finalize(self, buffer, *, partial):
        if (not self.config.continuous and self.finalized >= self.config.max_windows) or self.cancel.is_set():
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
            'media_kind':'video','target_revision':self.target_revision,
            'target_prompt': self.config.target_prompt, 'target_confirmed': self.config.target_confirmed,
            'analysis_interval_s': self.config.cadence_s,
            'created_utc': utc_now(), 'partial_capture_window': partial, 'frames': rows,
            'timing_basis': 'SOFTWARE_CFR_PLAYBACK; HOST_MONOTONIC_ARRIVAL_AFTER_READ',
            'capture_time_scale_verified': False, 'physical_fitting_allowed': False,
            'encoding_latency_s': time.monotonic() - started}
        write_json(folder / 'manifest.json', manifest)
        self.record('WINDOW_FINALIZED', {'window_id': folder.name, 'manifest_sha256': digest(manifest),
                                        'encoding_latency_s': manifest['encoding_latency_s']})
        if self.target_blocked or self.paused.is_set():
            self._skip_window(folder,'TARGET_REVISION_AUTHORIZATION_REQUIRED' if self.target_blocked else 'AI_PAUSED')
            return
        key = (meta.video_sha256, self.config.target_prompt)
        with self.lock:
            submitted = (self.upload_index.execute('SELECT 1 FROM submitted WHERE hash=? AND prompt=?',key).fetchone()
                if self.upload_index else key in self.submitted_upload_keys)
            if submitted or key in self.pending_upload_keys:
                self._skip_window(folder, 'DUPLICATE_CONTENT_AND_PROMPT')
                return
            # One freshest pending clip; never accumulate stale FIFO uploads.
            while True:
                try: old = self.windows.get_nowait()
                except queue.Empty: break
                self.pending_upload_keys.discard((old[1].video_sha256, old[2].get('target_prompt', self.config.target_prompt)))
                self._skip_window(old[0], 'BACKLOG_SUPERSEDED_BY_NEWER_WINDOW')
            self.pending_upload_keys.add(key)
            self.windows.put_nowait((folder, meta, manifest, time.monotonic()))

    def _skip_window(self, folder, code):
        self.dropped['windows'] += 1
        self.skipped[code] = self.skipped.get(code, 0) + 1
        write_json(folder / 'result.json', {'status': 'SKIPPED_NOT_UPLOADED', 'code': code, 'actual_requests': 0})
        self.record('WINDOW_SKIPPED', {'window_id': folder.name, 'code': code})

    async def _process(self, client, folder, meta, manifest, queued):
        start = time.monotonic()
        epoch = self.request_epoch
        image = manifest.get('media_kind') == 'image'
        self.record('SAM_PENDING', {'window_id': folder.name, 'queue_latency_s': start - queued})
        self.perception_error = None
        try:
            if getattr(client, 'concept', self.config.target_prompt) != manifest['target_prompt']:
                raise SamError('SAM prompt does not match authorized window', code='prompt_binding')
            client.on_partial = lambda run: self._partial(run,folder,meta,manifest,epoch,start)
            client.request_confidence = True
            method, path = (client.segment_image, folder/'input.png') if image else (client.segment_video,folder/'input.mp4')
            run = await asyncio.wait_for(method(path,meta), self.config.timeout_s)
            if self.cancel.is_set() or self.paused.is_set() or epoch != self.request_epoch:
                self.record('SAM_RESULT_AFTER_STOP', {'window_id': folder.name})
                return
            if run.video_sha256 != meta.video_sha256 or run.receipt.get('status') != 'completed':
                raise SamError('partial stream is not a track', code='incomplete')
            if run.receipt.get('prompt') != manifest['target_prompt']:
                raise SamError('SAM receipt prompt differs from window', code='prompt_binding')
            save_sam_cache(folder / 'sam', run)
            if self.source == 'REAL_PHONE' and run.source != 'REAL_API':
                raise SamError('fixture cannot be phone evidence', code='provenance')
            if not image:
                cache = self.root / 'sam_cache'
                cache.mkdir(exist_ok=True)
                save_sam_cache(cache / meta.video_sha256, run)
            # CFR playback speed cannot reject a measurement on physical-speed
            # grounds. Contour/identity/area QA still applies to preliminary pixels.
            track, summary, diagnostic = analyze_masks(run, meta, manifest)
            object_id = summary['object_id']
            rows = []
            for i in np.flatnonzero(track.valid) if track is not None else []:
                row = manifest['frames'][int(i)]
                rows.append({**row, 'xy_px': track.xy_px[i].tolist(), 'object_id': object_id,
                             'window_id': folder.name,
                             'image_sha256' if image else 'window_video_sha256': meta.video_sha256})
            result = {'status': 'PRELIMINARY_OBSERVATION' if rows else 'EMPTY_OR_QUARANTINED',
                'media_kind':'image' if image else 'video',
                'source': self.source, 'window_id': folder.name, 'receipt': run.receipt,
                'track': summary, 'diagnostic': diagnostic, 'rows': rows, 'latency_s': time.monotonic() - start,
                'end_to_end_latency_s': time.monotonic() - queued,
                'latency_scope': 'FINALIZED_WINDOW_QUEUE_TO_RESULT; CAPTURE_AND_ENCODING_EXCLUDED',
                'physical_fitting_allowed': False, 'complete_validated_track': False}
            result['pixel_motion'] = summarize_pixel_motion(rows)
            jpeg = self._publish_overlay(run,folder,meta,manifest,completed=True,latency=time.monotonic()-start)
            with self.lock:
                # IDs are scoped to each SAM response. Cross-window identity is
                # admitted only through agreeing overlapping source frames.
                overlap = [(self.trajectory[(r['recording_id'], r['capture_sequence'], r['arrival_monotonic_ns'])], r)
                    for r in rows if (r['recording_id'], r['capture_sequence'], r['arrival_monotonic_ns']) in self.trajectory]
                continuity = bool(overlap) and all(
                    old['object_id'] == new['object_id'] and np.linalg.norm(np.array(old['xy_px']) - new['xy_px']) <= 3
                    for old, new in overlap)
                result['identity_continuity'] = ('NO_OBSERVATIONS' if not rows else 'OVERLAP_AGREEMENT' if continuity
                    else 'FIRST_WINDOW_UNVERIFIED' if not self.trajectory else 'UNVERIFIED_OR_DISCONTINUOUS')
                result['behavior_changed'] = continuity and material_pixel_change(
                    (self.latest or {}).get('pixel_motion'),result['pixel_motion'])
                if result['behavior_changed']:
                    self.record('VISUAL_BEHAVIOR_CHANGED',{'window_id':folder.name,
                        'scope':'PIXEL_SCHEDULING_CUE_ONLY; UNVERIFIED_TIMING'})
                result['new_observations'] = 0
                for row in rows:
                    key = (row['recording_id'], row['capture_sequence'], row['arrival_monotonic_ns'])
                    if key not in self.trajectory:
                        self.trajectory[key] = row
                        result['new_observations'] += 1
                self.observation_count += result['new_observations']
                result['cumulative_unique_observations'] = self.observation_count
                if self.config.continuous:
                    while len(self.trajectory)>2000: del self.trajectory[next(iter(self.trajectory))]
                self.last_sam_latency_s = result['latency_s']
                if self.config.mode == 'AUTO_LIVE':
                    self.effective_interval_s = min(120.,max(self.config.cadence_s,result['latency_s']*1.25))
                # Continuous sessions retain a bounded RAM tail; original evidence stays on disk.
                self.latest = result
                if jpeg:
                    self.processed_jpeg = jpeg
                    self.processed_frames[folder.name] = jpeg
                    while len(self.processed_frames) > 2:
                        del self.processed_frames[next(iter(self.processed_frames))]
                if image: self.startup_result = deepcopy(result)
                else: self.processed += 1
                if rows: self.usable_windows += 1
                if not run.masks and self.config.mode == 'AUTO_LIVE':
                    self.target_blocked = True
                    self.overlay = None
                    self.record('NO_TARGET_OBSERVED',{'window_id':folder.name,
                        'code':'TARGET_REVISION_AUTHORIZATION_REQUIRED','new_automatic_requests':False})
            write_json(folder / 'result.json', result)
            self.record('SAM_COMPLETED', {**{k: result[k] for k in ('window_id', 'media_kind', 'latency_s', 'end_to_end_latency_s', 'new_observations', 'identity_continuity')},
                'result_sha256': digest(result), 'mask_index_sha256': file_sha256(folder / 'sam.json'),
                'mask_arrays_sha256': file_sha256(folder / 'sam.npz')})
            self.enqueue_science('observation', result)
        except asyncio.CancelledError:
            self._invalidate_overlay(folder.name,'CANCELLED')
            self.record('SAM_CANCELLED', {'window_id': folder.name})
            raise
        except Exception as exc:
            self._invalidate_overlay(folder.name,'STREAM_FAILED')
            code = getattr(exc, 'code', type(exc).__name__)
            result = {'status': 'FAILED', 'code': code, 'window_id': folder.name,
                      'latency_s': time.monotonic() - start, 'complete_validated_track': False,
                      'calls': list(exc.calls) if isinstance(exc, SamError) else []}
            write_json(folder / 'result.json', result)
            self.perception_error = result
            self.record('SAM_FAILED', result)
        finally:
            client.on_partial = None

    def _invalidate_overlay(self, window, reason):
        with self.lock:
            if self.overlay and self.overlay['window_id'] == window and not self.overlay['stream_completed']:
                self.overlay['status'] = 'TRACK_LOST'
                self.overlay['invalidated_reason'] = reason

    def _partial(self, run, folder, meta, manifest, epoch, started):
        if self.cancel.is_set() or self.paused.is_set() or epoch != self.request_epoch: return
        if self.source == 'REAL_PHONE' and run.source != 'REAL_API': return
        jpeg = self._publish_overlay(run,folder,meta,manifest,completed=False,latency=time.monotonic()-started)
        if jpeg:
            # Partial masks are presentation-only. Never enqueue science or add trajectory rows.
            self.record('SAM_PARTIAL_RECEIVED',{'window_id':folder.name,'received_masks':len(run.masks),
                'parser_revision':run.receipt['parser_revision'],'completed_scientific_evidence':False,
                'source_frame_index':max(m.frame_index for m in run.masks)})

    def _publish_overlay(self, run, folder, meta, manifest, *, completed, latency):
        if not run.masks: return None
        import cv2
        index = max(m.frame_index for m in run.masks)
        masks = [m for m in run.masks if m.frame_index == index]
        if manifest.get('media_kind') == 'image': image = cv2.imread(str(folder/'input.png'))
        else:
            video = cv2.VideoCapture(str(folder/'input.mp4'))
            try:
                video.set(cv2.CAP_PROP_POS_FRAMES,index)
                ok,image = video.read()
                if not ok: return None
            finally: video.release()
        if image is None: return None
        boxes = []
        for mask in masks:
            h,w = mask.pixels.shape
            region = image[mask.top:mask.top+h,mask.left:mask.left+w]
            tint = np.full_like(region,(175,216,36))
            region[mask.pixels] = (region[mask.pixels]*.55+tint[mask.pixels]*.45).astype(np.uint8)
            cv2.rectangle(image,(mask.left,mask.top),(mask.left+w-1,mask.top+h-1),(180,235,81),1)
            boxes.append({'object_id':mask.object_id,'xyxy_px':[mask.left,mask.top,mask.left+w,mask.top+h],
                'confidence':mask.confidence})
        ok,jpeg = cv2.imencode('.jpg',image)
        if not ok: return None
        with self.lock:
            self.overlay_revision += 1
            self.overlay_jpeg = jpeg.tobytes()
            self.overlay = {'status':'SAM_CONFIRMED','stream_completed':completed,'presentation_only':not completed,
                'window_id':folder.name,'revision':self.overlay_revision,'source':run.source,
                'source_sha256':meta.video_sha256,'source_frame':deepcopy(manifest['frames'][index]),
                'source_frame_index':index,'processed_size':[meta.width,meta.height], 'boxes':boxes,
                'target_identity':'SOURCE_BOUND_SAM_IDS; CROSS_RESPONSE_IDENTITY_UNVERIFIED',
                'processing_latency_s':latency,'timing':'UNVERIFIED_TIMING'}
            return self.overlay_jpeg

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
                    if self.paused.is_set():
                        await asyncio.sleep(.05)
                        continue
                    try:
                        with self.lock:
                            try: item = self.startup.get_nowait()
                            except queue.Empty: item = self.windows.get_nowait()
                            key = (item[1].video_sha256, item[2]['target_prompt'])
                            self.pending_upload_keys.discard(key)
                            if self.target_blocked or item[2]['target_prompt'] != self.config.target_prompt:
                                self._skip_window(item[0],'TARGET_REVISION_AUTHORIZATION_REQUIRED')
                                continue
                            if self.upload_index:
                                self.upload_index.execute('INSERT OR IGNORE INTO submitted VALUES (?,?)',key);self.upload_index.commit()
                            else:self.submitted_upload_keys.add(key)
                            self.sam_active_window = item[0].name
                    except queue.Empty:
                        await asyncio.sleep(.05)
                        continue
                    if client is not None and getattr(client,'concept',self.config.target_prompt) != self.config.target_prompt:
                        await client.close(); client = None
                    if client is None: client = self.sam_factory()
                    task = asyncio.create_task(self._process(client, *item))
                    while not task.done():
                        if self.cancel.is_set() or self.paused.is_set(): task.cancel()
                        await asyncio.wait({task}, timeout=.05)
                    try: await task
                    except asyncio.CancelledError: pass
                    finally: self.sam_active_window = None
            except Exception as exc:
                self.perception_error = {'code':getattr(exc,'code','SAM_WORKER_UNAVAILABLE'),'error_type':type(exc).__name__}
                self.record('SAM_WORKER_UNAVAILABLE', self.perception_error)
            finally:
                if client is not None: await client.close()
        asyncio.run(run())

    def enqueue_science(self, kind, payload):
        if self.cancel.is_set():
            if kind == 'observation': return False
            raise ValueError('AI investigation is stopped')
        with self.lock:
            if kind == 'observation':
                if self.pending_observation is not None:
                    self.coalesced_observations += 1
                    self.record('SCIENCE_OBSERVATION_COALESCED', {'previous_window': self.pending_observation['window_id'],
                        'latest_window': payload['window_id']})
                self.pending_observation = deepcopy(payload)
                return True
            if kind == 'operator' and (self.operator_pending or self.science_busy):
                self.record('SCIENCE_OPERATOR_EVENT_COALESCED', {'code': 'ALREADY_PENDING_OR_RUNNING'})
                return False
            if kind == 'operator': self.operator_pending = True
        try: self.science.put_nowait((kind, deepcopy(payload)))
        except queue.Full:
            with self.lock:
                self.dropped['science'] += 1
                if kind == 'operator': self.operator_pending = False
            self.record('SCIENCE_CONTROL_REJECTED', {'kind': kind, 'code': 'CONTROL_QUEUE_FULL'})
            raise ValueError('Scientific control queue full; retry after completion')
        return True

    def _science_loop(self):
        reasoner = None
        try:
            from .live_science import LiveScientificSession
            reasoner = self.reasoner_factory(self) if self.reasoner_factory else LiveScientificSession(self)
            while not self.cancel.is_set():
                if self.paused.is_set():
                    self.cancel.wait(.05)
                    continue
                # Operator/admission controls cannot starve behind continuous snapshots.
                try: kind, value = self.science.get_nowait()
                except queue.Empty:
                    with self.lock:
                        observation, self.pending_observation = self.pending_observation, None
                    if observation is None:
                        self.cancel.wait(.05)
                        continue
                    kind, value = 'observation', observation
                self.science_busy = True
                if kind == 'operator': self.operator_pending = False
                try: reasoner.consume(kind, value)
                except Exception as exc:
                    from realign.agent.adapters import AdapterFailure
                    diagnostic = (exc.diagnostic() if isinstance(exc, AdapterFailure) else
                        {'code': getattr(exc, 'code', 'EVIDENCE_ADMISSION_REJECTED' if kind == 'admit' else 'SCIENTIFIC_VALIDATION_REJECTED'),
                         'category': 'SCIENTIFIC_VALIDATION', 'http_status': None, 'error_type': type(exc).__name__})
                    adapter = getattr(reasoner, 'adapter', None)
                    receipts = getattr(adapter, 'receipts', [])[-3:]
                    # Closed safe receipt fields only. Never serialize messages or exception bodies.
                    diagnostic['api_receipts'] = [{k: r[k] for k in ('status', 'error_type', 'http_status', 'response_sha256') if k in r} for r in receipts]
                    diagnostic['guidance'] = ('Review the safe HTTP/transport code and account configuration; no automatic retry on unchanged evidence.'
                        if diagnostic['category'] in ('META_HTTP', 'META_TRANSPORT', 'SDK_RUNTIME') else
                        'The response or scientific input was rejected. Inspect the typed code and admission blockers; no physical conclusion was accepted.')
                    self.scientific['last_error'] = diagnostic
                    self.record('SCIENCE_EVENT_REJECTED', {'kind': kind, **diagnostic})
                    if not self.pending_action and self.scientific['state'] == 'AGENT_INVESTIGATING':
                        self.scientific['state'] = 'CALIBRATED_OBSERVATION' if self.scientific['physical_evidence_accepted'] else 'PRELIMINARY_OBSERVATION'
                finally: self.science_busy = False
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

    def pause(self):
        self.ledger.pause(True)  # Request gate closes before cancellation/IO.
        with self.lock:
            self.paused.set()
            self.request_epoch += 1
            self.record('AI_PAUSED',{'budget_preserved':True,'capture_continues':True})

    def resume(self):
        self.ledger.pause(False)
        with self.lock:
            if self.cancel.is_set(): raise ValueError('Revoked authorization cannot be resumed')
            self.paused.clear()
            self.record('AI_RESUMED',{'budget_preserved':True,'automatic_reasoning':'NEW_ELIGIBLE_EVIDENCE_ONLY'})

    def reselect_target(self, prompt, confirmed, consent):
        if consent is not True or confirmed is not True:
            raise AuthorizationError('Explicit consent for additional requests and target confirmation required')
        settings = replace(self.config,target_prompt=prompt,target_confirmed=confirmed)
        with self.lock:
            if self.cancel.is_set() or self.paused.is_set() or not self.target_blocked:
                raise ValueError('An active NO_TARGET_OBSERVED session is required')
            if prompt == self.config.target_prompt:
                raise ValueError('Revise the target description before authorizing additional requests')
            old = self.config.target_prompt
            self.target_revision += 1
            self.config = settings
            self.target_blocked = False
            self.startup_scheduled = False
            self.record('TARGET_REVISION_AUTHORIZED',{'previous_prompt':old,'target_prompt':prompt,
                'target_revision':self.target_revision,'original_budget_preserved':True,
                'authorization_sha256':digest(self.ledger.policy)})

    def stop(self, reason='OPERATOR_STOP'):
        self.ledger.stop()  # Reject new requests before cancellation or IO.
        self.cancel.set()
        self.record('AI_STOPPED', {'reason': reason, 'usage': self.ledger.snapshot()})

    def close(self):
        self.stop('CONTROLLER_SHUTDOWN')
        for thread in self.threads: thread.join(timeout=2)
        if all(not thread.is_alive() for thread in self.threads):
            with self.lock:
                if self.upload_index is not None:
                    self.upload_index.close()
                    self.upload_index = None

    def snapshot(self):
        usage = self.ledger.snapshot()
        with self.lock:
            overlay = deepcopy(self.overlay)
            if overlay:
                overlay['source_frame_age_s'] = max(0.,(time.monotonic_ns()-overlay['source_frame']['arrival_monotonic_ns'])/1e9)
            return {'id': self.root.name, 'source': self.source, 'usage': usage,
                'mode':self.config.mode,'target_revision':self.target_revision,'target_blocked':self.target_blocked,
                'lifecycle':('REVOKED' if self.cancel.is_set() else 'PAUSED' if self.paused.is_set() else
                    'SPENDING_CAP_REACHED' if usage['spending_cap_reached'] else
                    'NO_TARGET_OBSERVED' if self.target_blocked else 'OBSERVING' if self.source_seen else 'AUTHORIZED_WAITING_FOR_CAMERA'),
                'state': 'STOPPED' if self.cancel.is_set() else 'PAUSED' if self.paused.is_set() else self.scientific['state'],
                'windowing': asdict(self.config), 'finalized_windows': self.finalized,
                'processed_windows': self.processed, 'queued_frames': self.frames.qsize(),
                'usable_windows': self.usable_windows,
                'queued_windows': self.windows.qsize(), 'dropped': dict(self.dropped),
                'throughput': {'policy': 'ONE_FRESHEST_PENDING_WINDOW', 'analysis_interval_s': self.config.cadence_s,
                    'effective_analysis_interval_s':self.effective_interval_s,
                    'sam_active_window': self.sam_active_window, 'last_service_latency_s': self.last_sam_latency_s,
                    'service_slower_than_cadence': self.last_sam_latency_s is not None and self.last_sam_latency_s > self.config.cadence_s,
                    'skipped_windows_by_reason': dict(self.skipped), 'cadence_skipped_sampled_frames': self.cadence_skipped_frames,
                    'coalesced_observations': self.coalesced_observations, 'scientific_worker_busy': self.science_busy},
                'unique_observations': self.observation_count, 'latest': deepcopy(self.latest),
                'historical_trajectory':deepcopy(list(self.trajectory.values())[-500:]),
                'startup_result':deepcopy(self.startup_result),'overlay':overlay,
                'perception_error':deepcopy(self.perception_error),
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

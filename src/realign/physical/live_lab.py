"""Local capture/import only. Scientific admission stays in the Task 06 pipeline.

Arrival clocks are software observations, not verified exposure times. OpenCV's
CFR writer does not preserve camera timing; both clocks are explicitly retained.
"""
from copy import deepcopy
from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import threading
import time
import uuid

import numpy as np

from realign.perception.video import file_sha256, probe_video, iter_video_frames, VideoError
from realign.perception.workflow import _path
from realign.physical.ingestion import input_blockers

ROLES = ('pilot', 'stationary', 'free', 'peg', 'requested_experiment')
STATES = ('IDLE', 'CAMERA_CONNECTED', 'RECORDING', 'SAVED', 'ADMISSION',
          'REVIEW_REQUIRED', 'ANALYSIS_READY', 'INVESTIGATING',
          'PENDING_PHYSICAL_ACTION', 'RESPONSE_RECORDED', 'FROZEN', 'ABSTAIN', 'FAILED')


class MP4Writer:
    """Browser-compatible H.264, one encoded frame per arrival, software CFR."""
    def __init__(self, path, fps, size):
        width, height = size
        self.process = subprocess.Popen(['ffmpeg', '-v', 'error', '-nostdin', '-n',
            '-f', 'rawvideo', '-pix_fmt', 'bgr24', '-s', f'{width}x{height}', '-r', str(fps),
            '-i', 'pipe:0', '-an', '-c:v', 'libx264', '-preset', 'ultrafast',
            '-crf', '18', '-pix_fmt', 'yuv420p', '-movflags', '+faststart', str(path)],
            stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    def write(self, frame):
        self.process.stdin.write(frame.tobytes())

    def release(self):
        try:
            self.process.stdin.close()
            if self.process.wait(timeout=20): raise ValueError('MP4_ENCODER_FAILED')
        except (OSError, subprocess.TimeoutExpired) as exc:
            self.process.kill(); self.process.wait()
            raise ValueError('MP4_ENCODER_FAILED') from exc


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def write_json(path, value):
    path = Path(path)
    temporary = path.with_suffix(path.suffix + '.tmp')
    temporary.write_text(json.dumps(value, indent=2, allow_nan=False) + '\n', encoding='utf-8')
    temporary.replace(path)


def interval_summary(arrivals_ns):
    intervals = np.diff(arrivals_ns) / 1e9
    median = float(np.median(intervals)) if len(intervals) else None
    duration = (arrivals_ns[-1] - arrivals_ns[0]) / 1e9 if len(arrivals_ns) > 1 else 0
    return {'frames': len(arrivals_ns), 'elapsed_s': duration,
            'effective_fps': (len(arrivals_ns) - 1) / duration if duration > 0 else None,
            'median_interval_s': median,
            'min_interval_s': float(min(intervals)) if len(intervals) else None,
            'max_interval_s': float(max(intervals)) if len(intervals) else None,
            'nonpositive_intervals': int(np.sum(intervals <= 0)),
            'gap_indicators': int(np.sum(intervals > 1.5 * median)) if median and median > 0 else 0,
            'verified_dropped_frames': None,
            'scope': 'Arrival gaps may reflect camera, driver, scheduling or encoding; hardware frame loss is unknown.'}


class LabLibrary:
    def __init__(self, root):
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def new_folder(self):
        folder = self.root / ('clip-' + uuid.uuid4().hex)
        folder.mkdir()
        return folder

    def draft(self, folder, provenance):
        """Existing phone manifest grammar, deliberately incomplete and offline."""
        rid = folder.name
        # Resolve relative to this draft on both native Windows and WSL.
        record = {'id': rid, 'video': 'recording.mp4',
                  'comparison_group': provenance.get('rig_id') or 'UNASSIGNED_RIG',
                  'release_bracket_pts_s': None, 'analysis_window_pts_s': None}
        return {'schema_version': 1, 'source_kind': 'REAL_PHONE',
                'capture_time_scale_verified': False, 'capture_timing_reference': None,
                'standard_tier_confirmed': False, 'calibration_file': None, 'manual_reviews': None,
                'nominal_params': {'length_m': None, 'g': 9.80665, 'gamma_per_s': .06,
                                   'quadratic_drag_per_m': 0.0},
                'stationary': record if provenance['role'] == 'stationary' else {},
                'exploration': [] if provenance['role'] in ('stationary', 'pilot') else [record],
                'development': [], 'response_to_request_id': provenance.get('response_to_request_id')}

    def analyze(self, folder):
        """Shared original-PTS parser and decoder; no detector or model fallback."""
        folder = Path(folder)
        provenance = json.loads((folder / 'provenance.json').read_text(encoding='utf-8'))
        video = folder / 'recording.mp4'
        sha = file_sha256(video)
        if sha != provenance['video_sha256']:
            raise ValueError('source content changed before analysis')
        draft = self.draft(folder, provenance)
        blockers = input_blockers(draft, folder)
        blockers += ['FRAMING_AND_FIXED_PIVOT_REVIEW_REQUIRED', 'INDEPENDENT_RELEASE_BRACKET_REQUIRED',
                     'MATCHING_REAL_SAM_RECEIPT_REQUIRED', 'TWENTY_HASH_BOUND_HUMAN_REVIEWS_PER_CLIP_REQUIRED']
        if provenance['role'] == 'pilot': blockers.append('PILOT_NOT_A_CONTROLLED_EXPERIMENT')
        others = [p for p in self.root.glob('clip-*/provenance.json') if p.parent != folder]
        if any(json.loads(p.read_text(encoding='utf-8')).get('video_sha256') == sha for p in others):
            blockers.append('DUPLICATE_HASH')
        report = {'schema_version': '1.0', 'id': folder.name, 'observation_source': 'REAL_PHONE',
                  'policy': 'OPERATOR_CAPTURE', 'status': 'BLOCKED_INPUTS', 'state': 'REVIEW_REQUIRED',
                  'state_history': ['SAVED', 'ADMISSION', 'REVIEW_REQUIRED'],
                  'video_sha256': sha, 'provenance': provenance, 'blockers': blockers,
                  'capture_time_scale_verified': False, 'calibration_grade': 'NONE', 'units': ['px'],
                  'timing_basis': 'PTS_ONLY', 'sam': {'status': 'NOT_RUN', 'actual_api_requests': 0},
                  'tracking_candidates': None, 'physical_evidence_accepted': False,
                  'model_comparison': {'status': 'NOT_RUN'},
                  'independent_validation': {'status': 'NOT_RUN', 'physical_G5': 'NOT_PASSED'},
                  'framing': {'status': 'REVIEW_REQUIRED', 'checks': [
                      'Pivot rigidly fixed and visible throughout', 'Complete bob arc within frame with margin',
                      'Camera fixed, calibration board in motion plane', 'Release visible without a push']},
                  'limitations': ['Source domain records the owner-supplied provenance, not physical admission.',
                      'WhatsApp/transcoded footage cannot establish original camera timing.',
                      'No classical detection, SAM tracking or physical model fit has run.']}
        try:
            metadata = probe_video(video, source_kind='REAL_PHONE')
            selected = set(np.linspace(0, len(metadata.pts) - 1, 5, dtype=int).tolist())
            count = 0
            import cv2
            for index, frame in enumerate(iter_video_frames(video, metadata)):
                count += 1
                if index in selected:
                    if not cv2.imwrite(str(folder / f'frame-{index}.png'), cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)):
                        raise VideoError('clean-frame export failed')
            diffs = np.diff(metadata.t_s)
            report['media'] = {'status': 'ADMITTED', 'scope': 'MEDIA_PREFLIGHT_ONLY; NOT_PHYSICAL_VALIDATION',
                'decoded_frames': count, 'width': metadata.width, 'height': metadata.height,
                'original_pts': list(metadata.pts), 'time_base': metadata.time_base,
                'pts_source': 'ORIGINAL_CONTAINER_PTS', 'variable_frame_rate': metadata.variable_frame_rate,
                'first_pts_s': float(metadata.t_s[0]), 'last_pts_s': float(metadata.t_s[-1]),
                'presentation_span_s': float(metadata.t_s[-1] - metadata.t_s[0]),
                'effective_presentation_fps': float((count - 1) / (metadata.t_s[-1] - metadata.t_s[0])),
                'min_interval_s': float(min(diffs)), 'max_interval_s': float(max(diffs)),
                'gap_indicators': int(np.sum(diffs > 1.5 * np.median(diffs))),
                'rotation_deg': metadata.rotation_deg, 'codec': metadata.codec,
                'review_frames': [f'frame-{i}.png' for i in sorted(selected)]}
        except VideoError as exc:
            report['media'] = {'status': 'REJECTED', 'code': exc.code}
            blockers.insert(0, exc.code)
        capture_path = folder / 'capture.json'
        if capture_path.is_file():
            report['capture'] = json.loads(capture_path.read_text(encoding='utf-8'))
            blockers.append('SOFTWARE_CFR_REQUIRES_INDEPENDENT_TIMEBASE_VALIDATION')
            capture_duration = report['capture']['elapsed_s']
            encoded_duration = report.get('media', {}).get('presentation_span_s')
            if capture_duration > 0 and encoded_duration is not None and abs(encoded_duration / capture_duration - 1) > .1:
                blockers.append('ENCODED_ARRIVAL_TIMEBASE_MISMATCH')
            if report['capture']['stop_reason'] != 'MANUAL_STOP': blockers.append(report['capture']['stop_reason'])
            blockers.append('CAMERA_DEVICE_IDENTITY_REQUIRES_OPERATOR_CONFIRMATION')
            if report.get('media', {}).get('decoded_frames') != report['capture']['frames']:
                blockers.append('ENCODED_FRAME_COUNT_MISMATCH')
        write_json(folder / 'phone_manifest.draft.json', draft)
        write_json(folder / 'report.json', report)
        return report

    def import_video(self, path, *, role='pilot', operator='', rig_id='', response_to_request_id=None):
        source = _path(path, Path.cwd())
        if source.suffix.lower() != '.mp4' or not source.is_file():
            raise ValueError('Supply an existing local original MP4 path')
        if role not in ROLES: raise ValueError('invalid recording role')
        folder = self.new_folder()
        before = file_sha256(source)
        shutil.copyfile(source, folder / 'recording.mp4')
        if file_sha256(folder / 'recording.mp4') != before:
            raise ValueError('source changed during import; retry from a stable original')
        write_json(folder / 'provenance.json', {'kind': 'ORIGINAL_FILE_IMPORT', 'source_filename': source.name,
            'source_path': str(source), 'imported_utc': utc_now(), 'video_sha256': before,
            'operator': operator, 'rig_id': rig_id, 'role': role, 'response_to_request_id': response_to_request_id,
            'capture_time_scale_verified': False})
        return self.analyze(folder)

    def catalog(self):
        return read_catalog(self.root)


def read_catalog(root):
    """Read-only catalog: opening the product never creates a library."""
    records = []
    for path in sorted(Path(root).glob('clip-*/report.json'), key=lambda p: p.stat().st_mtime, reverse=True):
        try:
            report = json.loads(path.read_text(encoding='utf-8'))
            changed = file_sha256(path.parent / 'recording.mp4') != report['video_sha256']
            changed |= json.loads((path.parent / 'provenance.json').read_text(encoding='utf-8')) != report['provenance']
            if report.get('capture'):
                changed |= file_sha256(path.parent / 'arrivals.jsonl') != report['capture']['arrivals_sha256']
            if changed:
                records.append({'id': path.parent.name, 'status': 'EVIDENCE_CHANGED'}); continue
            # Local source paths/operator identity never enter the read-only product.
            report['provenance'].pop('source_path', None)
            report['provenance'].pop('operator', None)
            records.append(report)
        except (OSError, ValueError, KeyError):
            records.append({'id': path.parent.name, 'status': 'EVIDENCE_UNAVAILABLE'})
    return {'observation_source': 'REAL_PHONE', 'policy': 'OPERATOR_CAPTURE',
            'status': 'BLOCKED_INPUTS', 'recordings': records, 'new_meta_calls': 0}


class CaptureController:
    """One explicit camera owner. Only the latest preview JPEG is retained."""
    def __init__(self, library, *, camera_factory=None):
        import cv2
        self.cv = cv2
        self.library = library
        self.camera_factory = camera_factory or cv2.VideoCapture
        self.lock = threading.RLock()
        self.camera = None
        self.writer = None
        self.thread = None
        self.stop_event = threading.Event()
        self.state = 'IDLE'
        self.history = ['IDLE']
        self.error = None
        self.frame = None
        self.jpeg = None
        self.last_frame_ns = None
        self.recording = None
        self.latest = None
        self.arrivals = []
        self.device = None

    def move(self, state):
        self.state = state
        self.history.append(state)

    def snapshot(self):
        with self.lock:
            age = (time.monotonic_ns() - self.last_frame_ns) / 1e9 if self.last_frame_ns else None
            return {'state': self.state, 'state_history': self.history[-40:], 'camera': self.device if self.camera is not None else None,
                    'error': self.error, 'latest': deepcopy(self.latest),
                    'capture': interval_summary(self.arrivals), 'preview_age_s': age,
                    'camera_stalled': self.camera is not None and age is not None and age > 3,
                    'capture_time_scale_verified': False, 'new_meta_calls': 0}

    def enumerate_devices(self, maximum=6):
        if not 1 <= maximum <= 16: raise ValueError('device scan limit must be 1..16')
        with self.lock:
            if self.camera is not None: raise ValueError('Disconnect before scanning camera devices')
            devices = []
            for index in range(maximum):
                camera = self.camera_factory(index, self.cv.CAP_DSHOW if os.name == 'nt' else self.cv.CAP_ANY)
                try:
                    if camera.isOpened():
                        devices.append({'index': index, 'backend': camera.getBackendName(),
                                        'label': f'Camera {index} (operator must identify phone)'})
                finally: camera.release()
            return devices

    def connect(self, index, *, threaded=True):
        if type(index) is not int or not 0 <= index <= 15: raise ValueError('camera index must be 0..15')
        with self.lock:
            if self.camera is not None or self.writer is not None: raise ValueError('Disconnect the active camera first')
            if self.thread and self.thread.is_alive(): raise ValueError('Previous camera driver is still stopping; restart controller')
            camera = self.camera_factory(index, self.cv.CAP_DSHOW if os.name == 'nt' else self.cv.CAP_ANY)
            if not camera.isOpened():
                camera.release(); self.move('FAILED'); self.error = 'CAMERA_UNAVAILABLE'
                raise ValueError('Camera unavailable; check Windows camera permissions and phone connection')
            self.camera = camera
            self.device = {'index': index, 'backend': camera.getBackendName()}
            self.error = None
            self.stop_event.clear()
            camera.set(self.cv.CAP_PROP_BUFFERSIZE, 1)  # Driver may ignore this request.
            self.move('CAMERA_CONNECTED')
        self.read_once()
        if threaded and self.camera is not None:
            self.thread = threading.Thread(target=self._loop, daemon=True)
            self.thread.start()

    def _loop(self):
        while not self.stop_event.is_set() and self.camera is not None:
            self.read_once()

    def read_once(self, *, arrival_ns=None):
        camera = self.camera
        if camera is None: return
        try:
            ok, frame = camera.read()
            arrival = time.monotonic_ns() if arrival_ns is None else arrival_ns
            if self.stop_event.is_set(): return
            if not ok or frame is None: raise ValueError('CAMERA_DISCONNECTED')
            with self.lock:
                if self.camera is not camera: return
                self.frame = frame
                self.last_frame_ns = time.monotonic_ns()
                if self.writer is not None:
                    if frame.shape[:2] != self.record_shape: raise ValueError('CAMERA_RESOLUTION_CHANGED')
                    self.writer.write(frame)
                    self.arrival_file.write(json.dumps({'encoded_frame_index': len(self.arrivals),
                        'capture_sequence': self.sequence, 'arrival_monotonic_ns': arrival}) + '\n')
                    self.arrival_file.flush()
                    self.arrivals.append(arrival)
                    if (arrival - self.arrivals[0]) / 1e9 >= 55 or len(self.arrivals) >= int(self.fps * 55):
                        self.stop(reason='RECORDING_LIMIT_REACHED')
                self.sequence = getattr(self, 'sequence', 0) + 1
                # Preview is downscaled for latency; saved recording remains full resolution.
                height, width = frame.shape[:2]
                preview = self.cv.resize(frame, (min(width, 800), max(1, round(height * min(1, 800 / width)))))
                ok, encoded = self.cv.imencode('.jpg', preview, [self.cv.IMWRITE_JPEG_QUALITY, 75])
                if ok: self.jpeg = encoded.tobytes()
        except Exception as exc:
            with self.lock:
                self.error = str(exc) if isinstance(exc, ValueError) else 'CAMERA_OR_WRITE_FAILED'
                try:
                    if self.writer is not None: self.stop(reason=self.error)
                finally:
                    camera.release(); self.camera = None; self.jpeg = None
                    self.move('FAILED'); self.stop_event.set()

    def start(self, *, role='pilot', operator='', rig_id='', response_to_request_id=None):
        if role not in ROLES: raise ValueError('invalid recording role')
        with self.lock:
            if self.camera is None or self.frame is None or self.writer is not None:
                raise ValueError('Connect a working camera before starting a new recording')
            if self.last_frame_ns and (time.monotonic_ns() - self.last_frame_ns) / 1e9 > 3:
                raise ValueError('Camera has stalled; reconnect before recording')
            self.recording = self.library.new_folder()
            self.record_shape = self.frame.shape[:2]
            reported_fps = float(self.camera.get(self.cv.CAP_PROP_FPS))
            self.fps = reported_fps if math.isfinite(reported_fps) and 1 <= reported_fps <= 120 else 30.
            if self.record_shape[0] % 2 or self.record_shape[1] % 2:
                raise ValueError('Camera dimensions must be even for H.264; import the original MP4 instead')
            try:
                writer = MP4Writer(self.recording / 'recording.mp4', self.fps,
                                   (self.record_shape[1], self.record_shape[0]))
            except OSError as exc:
                raise ValueError('Install FFmpeg with libx264 or import an original MP4') from exc
            self.arrival_file = (self.recording / 'arrivals.jsonl').open('w', encoding='utf-8')
            self.arrivals = []
            self.sequence = 0
            self.provenance = {'kind': 'LOCAL_CAMERA_CAPTURE', 'camera': self.device, 'started_utc': utc_now(),
                'operator': operator, 'rig_id': rig_id, 'role': role, 'response_to_request_id': response_to_request_id,
                'capture_time_scale_verified': False}
            write_json(self.recording / 'capture_in_progress.json', self.provenance)
            self.writer = writer
            self.move('RECORDING')
            return self.recording

    def stop(self, *, reason='MANUAL_STOP'):
        with self.lock:
            if self.writer is None: raise ValueError('No recording is active')
            try:
                return self._finalize(reason=reason)
            except Exception as exc:
                self.error = 'RECORDING_FINALIZATION_FAILED'
                self.move('FAILED')
                raise ValueError('Recording finalization failed; preserve the local folder and inspect disk/encoder availability') from exc

    def _finalize(self, *, reason):
        with self.lock:
            writer, self.writer = self.writer, None
            try: writer.release()
            finally: self.arrival_file.close()
            summary = interval_summary(self.arrivals)
            summary.update(stop_reason=reason, stopped_utc=utc_now(), encoded_nominal_fps=self.fps,
                encoded_timing='SOFTWARE_CFR_NOT_PHYSICAL_TIME',
                arrival_clock='HOST_MONOTONIC_NS_AFTER_CAMERA_READ_NOT_EXPOSURE_TIME',
                arrivals_sha256=file_sha256(self.recording / 'arrivals.jsonl'))
            write_json(self.recording / 'capture.json', summary)
            self.provenance['video_sha256'] = file_sha256(self.recording / 'recording.mp4')
            write_json(self.recording / 'provenance.json', self.provenance)
            self.move('SAVED'); self.move('ADMISSION')
            self.latest = self.library.analyze(self.recording)
            self.move('REVIEW_REQUIRED')
            return deepcopy(self.latest)

    def close(self):
        self.stop_event.set()
        # release() can unblock read() on supported camera backends.
        camera = self.camera
        if camera is not None: camera.release()
        if self.thread and self.thread is not threading.current_thread(): self.thread.join(timeout=3)
        with self.lock:
            if self.writer is not None: self.stop(reason='CONTROLLER_SHUTDOWN')
            self.camera = None
            self.frame = None
            self.jpeg = None
            self.move('IDLE')

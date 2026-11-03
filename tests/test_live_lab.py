"""Capture boundary tests: injected camera, actual codec/preflight, no Meta calls."""
import json
from pathlib import Path
import numpy as np
import pytest

from realign.physical.live_lab import CaptureController, LabLibrary, interval_summary


class Camera:
    def __init__(self):
        self.open = True
        self.frames = [np.zeros((64, 96, 3), np.uint8) for _ in range(12)]

    def isOpened(self): return self.open
    def read(self): return (True, self.frames.pop()) if self.frames else (False, None)
    def release(self): self.open = False
    def get(self, key): return 30.
    def set(self, *args): return False
    def getBackendName(self): return 'INJECTED_TEST_CAMERA'


def test_interval_metrics_never_claim_known_drops():
    report = interval_summary([0, 33_000_000, 66_000_000, 170_000_000])
    assert report['gap_indicators'] == 1
    assert report['effective_fps'] == pytest.approx(3 / .17)
    assert report['verified_dropped_frames'] is None


@pytest.fixture
def lab(tmp_path):
    camera = Camera()
    library = LabLibrary(tmp_path)
    controller = CaptureController(library, camera_factory=lambda index, backend: camera)
    controller.connect(0, threaded=False)
    yield controller, library, camera
    controller.close()


def test_recording_preserves_arrivals_separately_and_stays_blocked(lab):
    controller, library, _ = lab
    assert controller.snapshot()['state'] == 'CAMERA_CONNECTED'
    folder = controller.start(role='free', operator='test fixture', rig_id='fixture')
    for i in range(4): controller.read_once(arrival_ns=1_000_000_000 + i * 40_000_000)
    report = controller.stop()
    assert report['status'] == 'BLOCKED_INPUTS'
    assert report['capture_time_scale_verified'] is False
    assert report['sam']['status'] == 'NOT_RUN'
    assert report['media']['decoded_frames'] == 4
    assert report['media']['pts_source'] == 'ORIGINAL_CONTAINER_PTS'
    assert report['capture']['encoded_timing'] == 'SOFTWARE_CFR_NOT_PHYSICAL_TIME'
    arrivals = [json.loads(x) for x in (folder / 'arrivals.jsonl').read_text().splitlines()]
    assert [x['encoded_frame_index'] for x in arrivals] == list(range(4))
    assert arrivals[-1]['arrival_monotonic_ns'] == 1_120_000_000
    assert report['capture']['arrivals_sha256']
    assert json.loads((folder / 'phone_manifest.draft.json').read_text())['exploration'][0]['video'] == 'recording.mp4'
    assert library.catalog()['recordings'][0]['video_sha256'] == report['video_sha256']


def test_disconnection_finalizes_file_but_does_not_admit_it(lab):
    controller, _, camera = lab
    folder = controller.start()
    controller.read_once()
    controller.read_once()
    camera.frames.clear()
    controller.read_once()
    assert controller.snapshot()['state'] == 'FAILED'
    report = json.loads((folder / 'report.json').read_text())
    assert 'CAMERA_DISCONNECTED' in report['blockers']
    assert (folder / 'capture.json').is_file()
    assert not camera.open


def test_import_uses_same_pts_validation_and_copies_original(lab):
    controller, library, _ = lab
    folder = controller.start()
    for _ in range(3): controller.read_once()
    recorded = controller.stop()
    imported = library.import_video(folder / 'recording.mp4')
    assert imported['video_sha256'] == recorded['video_sha256']
    assert imported['media']['original_pts'] == recorded['media']['original_pts']
    assert imported['provenance']['kind'] == 'ORIGINAL_FILE_IMPORT'
    assert 'DUPLICATE_HASH' in imported['blockers']
    assert 'FRAMING_AND_FIXED_PIVOT_REVIEW_REQUIRED' in imported['blockers']
    assert imported['calibration_grade'] == 'NONE'
    assert imported['tracking_candidates'] is None


@pytest.mark.parametrize('name', ['empty.mp4', 'corrupt.mp4'])
def test_bad_media_retains_provenance_and_typed_blocker(tmp_path, name):
    source = tmp_path / name
    source.write_bytes(b'' if name == 'empty.mp4' else b'not an MP4')
    report = LabLibrary(tmp_path / 'library').import_video(source)
    assert report['status'] == 'BLOCKED_INPUTS'
    assert report['media']['status'] == 'REJECTED'
    assert report['media']['code'] in ('ZERO_LENGTH', 'UNREADABLE_CONTAINER')
    assert report['video_sha256']


def test_state_guards_and_sealed_paths(lab, tmp_path):
    controller, library, _ = lab
    with pytest.raises(ValueError): controller.stop()
    controller.start()
    with pytest.raises(ValueError): controller.start()
    with pytest.raises(ValueError): controller.connect(1)
    with pytest.raises(ValueError): library.import_video(tmp_path / 'vault' / 'private.mp4')


def test_tampered_saved_media_is_not_shown_as_original(lab):
    controller, library, _ = lab
    folder = controller.start()
    for _ in range(2): controller.read_once()
    controller.stop()
    with (folder / 'recording.mp4').open('ab') as f: f.write(b'changed')
    assert library.catalog()['recordings'][0]['status'] == 'EVIDENCE_CHANGED'


def test_encoder_failure_closes_sidecar_and_fails_safely(lab):
    controller, _, _ = lab
    controller.start()
    original = controller.writer
    original.release()
    class BrokenEncoder:
        def release(self): raise OSError('injected encoder failure')
    controller.writer = BrokenEncoder()
    with pytest.raises(ValueError, match='finalization failed'): controller.stop()
    assert controller.snapshot()['state'] == 'FAILED'
    assert controller.writer is None and controller.arrival_file.closed


def test_tampered_arrival_sidecar_is_not_displayed_as_verified(lab):
    controller, library, _ = lab
    folder = controller.start()
    controller.read_once(); controller.read_once(); controller.stop()
    with (folder / 'arrivals.jsonl').open('a') as stream: stream.write('{}\n')
    assert library.catalog()['recordings'][0]['status'] == 'EVIDENCE_CHANGED'

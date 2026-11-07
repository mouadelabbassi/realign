"""Task05 external-product checks, entirely offline.

The rendered video and parser events are SYNTHETIC_RENDER /
SIMULATED_API_FIXTURE. Fake clients below are intentionally rejected by the
real-labelled export. They are not API verification or manual physical review.
The stored Task05 external report is separately checked as historical evidence;
reading that report makes no new Meta request.
"""
import asyncio
from dataclasses import asdict
import json
from pathlib import Path

import numpy as np
import pytest

from realign.contracts.external import ExternalVideoSource
from realign.perception.sam_client import SamError, parse_sam_events
from realign.perception.track import TrackFlag, extract_track
from realign.product import external
from realign.product.evidence import EvidenceError, validate_external
from realign.synth.video_fixture import render_fixture


@pytest.fixture(scope='module')
def rendered(tmp_path_factory):
    fixture = render_fixture(tmp_path_factory.mktemp('product-external')/'fixture.mp4',
                             duration_s=.8, variable_rate=True)
    run = asyncio.run(parse_sam_events(fixture['events'], fixture['metadata'],
                                       source='SIMULATED_API_FIXTURE'))
    return fixture, run, extract_track(run, fixture['metadata'])


def _configuration(tmp_path, metadata):
    source = ExternalVideoSource(
        source_page_url='https://example.org/SIMULATED_FIXTURE',
        original_video_url='https://example.org/SIMULATED_FIXTURE.mp4',
        creator='SIMULATED_UNIT_TEST_PROVENANCE', license_id='CC0-1.0',
        license_url='https://creativecommons.org/publicdomain/zero/1.0/',
        attribution='SIMULATED UNIT TEST CONFIGURATION; NOT ACTUAL MEDIA ATTRIBUTION',
        original_sha256=metadata.video_sha256, processed_sha256=metadata.video_sha256,
        modifications='Unit-test configuration only; no real source claim.',
        physical_recording=True)
    path = tmp_path/'manifest.json'
    path.write_text(json.dumps({'source_kind':'REAL_EXTERNAL','provenance':asdict(source)}),
                    encoding='utf-8')
    return path


def _reviews(metadata, track, index=0, delta=(0.,0.)):
    return [{'video_sha256':metadata.video_sha256, 'frame_index':index,
             'center_px':(track.xy_px[index]+delta).tolist(),
             'annotation_sigma_px':.75, 'reviewer':'SIMULATED_UNIT_REFERENCE'}]


def test_rendered_vfr_and_missing_masks_remain_explicit(rendered):
    fixture, run, track = rendered
    metadata = fixture['metadata']
    assert metadata.source_kind == 'SYNTHETIC_RENDER'
    assert run.source == 'SIMULATED_API_FIXTURE'
    assert metadata.variable_frame_rate
    assert len(set(np.diff(metadata.pts))) == 2
    assert len(track.valid) == len(metadata.pts)
    assert not track.valid[13]
    assert track.flags[13] & TrackFlag.MISSING
    assert np.isnan(track.xy_px[13]).all()
    assert np.isnan(track.confidence).all()


def test_real_export_rejects_simulated_masks_before_writing(rendered, tmp_path):
    fixture, run, track = rendered
    output = tmp_path/'must-not-exist'
    with pytest.raises(EvidenceError, match='actual SAM'):
        external.export_tracking(fixture['path'], fixture['metadata'], run, track, output)
    assert not output.exists()


def test_missing_manual_references_do_not_invent_an_accuracy_score(rendered):
    fixture, _, track = rendered
    result = external.compare_manual_reviews([], fixture['metadata'], track)
    assert result == {'status':'NOT_PROVIDED','reviewed_frames':0,
                      'rmse_px':None,'bias_px':None}


def test_supplied_unit_reference_errors_use_original_pts(rendered):
    fixture, _, track = rendered
    metadata = fixture['metadata']
    refs = _reviews(metadata, track, index=15, delta=(3.,4.))
    result = external.compare_manual_reviews(refs, metadata, track)
    assert result['reviewed_frames'] == 1
    assert result['rmse_px'] == pytest.approx(5.)
    assert result['bias_px'] == pytest.approx([-3.,-4.])
    assert result['per_frame'][0]['pts_s'] == metadata.t_s[15]
    assert result['per_frame'][0]['annotation_sigma_px'] == .75


@pytest.mark.parametrize('mutation', ['hash','duplicate','index','bounds','sigma','reviewer'])
def test_invalid_review_identity_and_annotation_metadata_rejected(rendered, mutation):
    fixture, _, track = rendered
    metadata = fixture['metadata']
    rows = _reviews(metadata, track)
    if mutation == 'hash': rows[0]['video_sha256'] = 'f'*64
    elif mutation == 'duplicate': rows.append(dict(rows[0]))
    elif mutation == 'index': rows[0]['frame_index'] = True
    elif mutation == 'bounds': rows[0]['center_px'] = [metadata.width,100.]
    elif mutation == 'sigma': rows[0]['annotation_sigma_px'] = 0.
    elif mutation == 'reviewer': rows[0]['reviewer'] = ''
    with pytest.raises(EvidenceError):
        external.compare_manual_reviews(rows, metadata, track)


def test_manual_annotation_on_missing_mask_is_not_a_zero_error_match(rendered):
    fixture, _, track = rendered
    row = _reviews(fixture['metadata'], track)[0]
    row.update(frame_index=13, center_px=[100.,100.])
    result = external.compare_manual_reviews([row], fixture['metadata'], track)
    assert result['status'] == 'NO_VALID_TRACK_PAIRS'
    assert result['rmse_px'] is None and result['reviewed_frames'] == 0


def test_missing_file_reports_not_run_without_request(rendered, tmp_path, monkeypatch):
    fixture, _, _ = rendered
    monkeypatch.delenv('MODEL_API_KEY', raising=False)
    result = asyncio.run(external.process_external(tmp_path/'missing.mp4',
        _configuration(tmp_path,fixture['metadata']),tmp_path/'report',tmp_path/'cache'))
    assert result['status'] == 'NOT_RUN'
    assert result['blockers'] == ['APPROVED_EXTERNAL_MP4_MISSING']
    assert result['sam']['successful_calls'] == result['sam']['failed_calls'] == 0
    assert (tmp_path/'report'/'external_verification.json').is_file()


def test_no_local_authorization_never_constructs_a_client(rendered, tmp_path, monkeypatch):
    fixture, _, _ = rendered
    monkeypatch.delenv('MODEL_API_KEY', raising=False)
    monkeypatch.setattr(external,'probe_video',lambda *a,**k:fixture['metadata'])
    def forbidden(): raise AssertionError('not authorized to instantiate')
    result = asyncio.run(external.process_external(fixture['path'],
        _configuration(tmp_path,fixture['metadata']),tmp_path/'report',tmp_path/'cache',
        run_api=False,client_factory=forbidden))
    assert result['status'] == 'NOT_RUN'
    assert result['blockers'] == ['LOCAL_AUTHORIZATION_REQUIRED']
    assert result['sam']['successful_calls'] == result['sam']['failed_calls'] == 0
    assert result['physical_comparison_available'] is False
    assert result['phone_g2_passed'] is False


def test_simulated_client_output_cannot_be_cached_or_published_as_real(rendered, tmp_path, monkeypatch):
    fixture, run, _ = rendered
    monkeypatch.delenv('MODEL_API_KEY', raising=False)
    monkeypatch.setattr(external,'probe_video',lambda *a,**k:fixture['metadata'])
    class Fake:
        calls = []
        closed = False
        async def segment_video(self,*args): return run
        async def close(self): self.closed = True
    fake = Fake()
    result = asyncio.run(external.process_external(fixture['path'],
        _configuration(tmp_path,fixture['metadata']),tmp_path/'report',tmp_path/'cache',
        run_api=True,standard_tier_confirmed=True,client_factory=lambda:fake))
    assert result['status'] == 'FAILED'
    assert result['error_type'] == 'EvidenceError'
    assert result['track'] is None
    assert result['sam']['successful_calls'] == result['sam']['failed_calls'] == 0
    assert not (tmp_path/'cache.json').exists()
    assert not (tmp_path/'report'/'tracked_centers.csv').exists()
    assert fake.closed


def test_network_failure_retains_counts_without_exception_body(rendered, tmp_path, monkeypatch):
    fixture, _, _ = rendered
    monkeypatch.setattr(external,'probe_video',lambda *a,**k:fixture['metadata'])
    class Fake:
        calls = [{'operation':'upload','attempt':1,'status':'failed',
                  'error_type':'TimeoutError','http_status':None}]
        closed = False
        async def segment_video(self,*args):
            raise SamError('SENSITIVE_FIXTURE_CANARY',code='upload_failed',calls=self.calls)
        async def close(self): self.closed = True
    fake = Fake()
    result = asyncio.run(external.process_external(fixture['path'],
        _configuration(tmp_path,fixture['metadata']),tmp_path/'report',tmp_path/'cache',
        run_api=True,standard_tier_confirmed=True,client_factory=lambda:fake))
    assert result['status'] == 'FAILED' and result['code'] == 'upload_failed'
    assert result['sam']['successful_calls'] == 0 and result['sam']['failed_calls'] == 1
    assert fake.closed and 'SENSITIVE_FIXTURE_CANARY' not in json.dumps(result)
    assert json.loads((tmp_path/'report'/'external_verification.json').read_text()) == json.loads(json.dumps(result))


def test_client_cleanup_failure_does_not_erase_the_receipt(rendered, tmp_path, monkeypatch):
    fixture, _, _ = rendered
    monkeypatch.setattr(external,'probe_video',lambda *a,**k:fixture['metadata'])
    class Fake:
        calls = [{'operation':'upload','attempt':1,'status':'failed',
                  'error_type':'TimeoutError','http_status':None}]
        async def segment_video(self,*args):
            raise SamError('SENSITIVE_FIXTURE_CANARY',code='upload_failed',calls=self.calls)
        async def close(self): raise RuntimeError('SENSITIVE_CLEANUP_CANARY')
    result = asyncio.run(external.process_external(fixture['path'],
        _configuration(tmp_path,fixture['metadata']),tmp_path/'report',tmp_path/'cache',
        run_api=True,standard_tier_confirmed=True,client_factory=Fake))
    assert result['status'] == 'FAILED' and result['code'] == 'upload_failed'
    assert result['sam']['failed_calls'] == 1
    assert json.loads((tmp_path/'report'/'external_verification.json').read_text()) == json.loads(json.dumps(result))
    assert result['sam']['cleanup_error'] == {'code':'CLIENT_CLOSE_FAILED','error_type':'RuntimeError'}
    assert 'SENSITIVE' not in json.dumps(result)


@pytest.fixture
def stored_external():
    path = Path(__file__).resolve().parents[1]/'artifacts/task05/external_yellow_disc/external_verification.json'
    return json.loads(path.read_text(encoding='utf-8'))


def test_stored_actual_sam_evidence_can_be_checked_offline(stored_external):
    result = validate_external(stored_external)
    assert result['observation_source'] == 'REAL_EXTERNAL'
    assert result['physical_comparison_available'] is False
    assert result['sam']['receipt']['source'] == 'REAL_API'
    assert result['manual_review']['status'] == 'NOT_PROVIDED'
    assert result['phone_g2_passed'] is False
    assert len(result['track']['valid']) == len(result['metadata']['pts'])


@pytest.mark.parametrize('mutation', ['phone','phone_gate','physical_fit','hash','simulated','frames','response',
                                     'valid_without_center','nonboolean_valid','pts','playback_time','receipt_hash','time_base'])
def test_external_evidence_cannot_be_relabelled_or_detached(stored_external, mutation):
    if mutation == 'phone': stored_external['observation_source'] = 'REAL_PHONE'
    elif mutation == 'phone_gate': stored_external['phone_g2_passed'] = True
    elif mutation == 'physical_fit': stored_external['physical_comparison_available'] = True
    elif mutation == 'hash': stored_external['metadata']['video_sha256'] = '0'*64
    elif mutation == 'simulated': stored_external['sam']['receipt']['source'] = 'SIMULATED_API_FIXTURE'
    elif mutation == 'frames': stored_external['track']['xy_px'].pop()
    elif mutation == 'response': stored_external['sam']['receipt']['response_id'] = None
    elif mutation == 'valid_without_center':
        index = stored_external['track']['valid'].index(True)
        stored_external['track']['xy_px'][index] = [None,None]
    elif mutation == 'nonboolean_valid': stored_external['track']['valid'][0] = 'true'
    elif mutation == 'pts': stored_external['metadata']['pts'][1] = stored_external['metadata']['pts'][0]
    elif mutation == 'playback_time': stored_external['metadata']['t_s'][1] += .5
    elif mutation == 'receipt_hash': stored_external['sam']['receipt']['video_sha256'] = '0'*64
    elif mutation == 'time_base': stored_external['metadata']['time_base'] = '1/0'
    with pytest.raises(EvidenceError):
        validate_external(stored_external)

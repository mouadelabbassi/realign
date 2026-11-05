"""Synthetic media/protocol fixtures only; not actual phone or SAM measurements."""
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
import hashlib,json,shutil,wave
import numpy as np
import pytest
from realign.perception.video import metadata_from_ffprobe,VideoError
from realign.perception.manual_review import read_review_json,assess_manual_reviews,verify_locked_annotations,ManualReviewError
from realign.physical.admission import admit_recording,calibration_grade,require_physical_calibration

ROOT=Path(__file__).resolve().parents[2]

def metadata(pts,rotation=0):
    return {'streams':[{'width':64,'height':48,'time_base':'1/100','tags':{'rotate':rotation}}],
            'frames':[{} if p is None else {'pts':p} for p in pts]}

def test_variable_frame_rate_preserves_original_timestamps():
    m=metadata_from_ffprobe(metadata([0,3,8,10]),video_sha256='a'*64,source_kind='SYNTHETIC_RENDER')
    assert m.pts==(0,3,8,10)
    np.testing.assert_array_equal(m.t_s,[0.,.03,.08,.1])

@pytest.mark.parametrize('raw,code',[(metadata([0,None,2]),'MISSING_PTS'),
    (metadata([0,3,3]),'NON_MONOTONIC_PTS'),(metadata([0,3,2]),'NON_MONOTONIC_PTS'),
    (metadata([0,3],17),'ROTATION_UNHANDLED'),({'streams':[]},'NO_VIDEO_STREAM'),
    ({'streams':[{}],'frames':[]},'ZERO_LENGTH')])
def test_typed_metadata_failures(raw,code):
    with pytest.raises(VideoError) as e:metadata_from_ffprobe(raw,video_sha256='a'*64,source_kind='SYNTHETIC_RENDER')
    assert e.value.code==code

@pytest.mark.skipif(shutil.which('ffprobe') is None,reason='FFmpeg required for rendered media fixtures')
def test_actual_generated_malformed_and_valid_media(tmp_path):
    import cv2
    config={'source_kind':'REAL_PHONE','fixture_notice':'SIMULATED_MEDIA_PREFLIGHT_ONLY'}
    empty=tmp_path/'empty.mp4';empty.write_bytes(b'')
    assert admit_recording(empty,config)['code']=='ZERO_LENGTH'
    bad=tmp_path/'truncated.mp4';bad.write_bytes(b'NOT_A_VALID_CONTAINER')
    assert admit_recording(bad,config)['code']=='UNREADABLE_CONTAINER'
    audio=tmp_path/'audio.wav'
    with wave.open(str(audio),'wb') as w:w.setnchannels(1);w.setsampwidth(2);w.setframerate(8000);w.writeframes(b'\x00'*1600)
    assert admit_recording(audio,config)['code']=='NO_VIDEO_STREAM'
    video=tmp_path/'SYNTHETIC_RENDER.mp4';v=cv2.VideoWriter(str(video),cv2.VideoWriter_fourcc(*'mp4v'),20,(64,48))
    for i in range(12):v.write(np.full((48,64,3),i*10,np.uint8))
    v.release();a=admit_recording(video,config)
    assert a['status']=='ADMITTED' and len(a['original_pts'])==12
    assert admit_recording(video,config,seen_hashes=[a['video_sha256']])['code']=='DUPLICATE_HASH'
    assert admit_recording(video,config,track=SimpleNamespace(valid=np.zeros(12,bool)))['code']=='COVERAGE_BELOW_THRESHOLD'
    assert admit_recording(video,{'source_kind':'REAL_EXTERNAL'})['code']=='CONTROLLED_PROVENANCE_REQUIRED'

def test_mm_and_physical_fits_refused_below_sufficient_calibration():
    record={'source_kind':'REAL_PHONE','scale_reference':'MEASURED_FIXTURE','pivot_px':[0.,0.],
        'roll_reference':'MEASURED_FIXTURE','noise_reference':'MEASURED_FIXTURE','capture_timing_reference':'MEASURED_FIXTURE','capture_time_scale_verified':True}
    assert require_physical_calibration(record)['grade']=='SUFFICIENT'
    for k in ['scale_reference','pivot_px','roll_reference','noise_reference','capture_timing_reference']:
        changed=dict(record);changed.pop(k)
        assert calibration_grade(changed)['units']==['px']
        with pytest.raises(ValueError):require_physical_calibration(changed)
    assert calibration_grade(dict(record,source_kind='REAL_EXTERNAL'))['timing_basis']=='PTS_ONLY'

def test_expanded_review_samples_early_acceptance_and_rejections_without_tracker_hints():
    base=ROOT/'artifacts/release/manual_review'
    manifest=read_review_json(base/'reference_manifest.json');report=read_review_json(ROOT/'artifacts/task05/external_yellow_disc/external_verification.json')
    assert manifest['schema_version']==2 and len(manifest['frames'])==40
    early=[f for f in manifest['frames'] if f['pts_s']<4]
    assert len(early)==20
    accepted=[report['track']['valid'][f['frame_index']] for f in early]
    assert any(accepted) and not all(accepted)
    page=(base/'review.html').read_text(encoding='utf-8')
    assert 'track_accepted' not in page and 'xy_px' not in page and 'Lock completed labels locally' in page
    for f in manifest['frames']:assert hashlib.sha256((base/f['file']).read_bytes()).hexdigest()==f['frame_sha256']
    result=assess_manual_reviews(report,manifest)
    assert result['status']=='NOT_VALIDATED' and result['metrics']['rmse_px'] is None

def test_browser_lock_is_required_for_new_reference_set_and_cannot_turn_ai_into_human():
    base=ROOT/'artifacts/release/manual_review';doc=read_review_json(base/'annotations.template.json')
    with pytest.raises(ManualReviewError):verify_locked_annotations(doc)
    doc.update(annotation_source='AI_VISUAL',independent_of_sam=True)
    payload=json.dumps(doc,separators=(',',':'),sort_keys=True);doc['lock']={'payload_json':payload,'sha256':hashlib.sha256(payload.encode()).hexdigest()}
    with pytest.raises(ManualReviewError):verify_locked_annotations(doc)

def test_existing_physical_environment_admission_states_and_expiry():
    import runpy
    from realign.physical.session import PhysicalEnvironment
    from realign.tools.client import candidate
    from realign.contracts.investigation import CameraCheck
    from realign.agent.adapters import AdapterFailure
    factory=runpy.run_path(str(ROOT/'tests/test_physical_investigation.py'))['video_fixture']
    trials=[factory('a'*64),factory('b'*64)];checks={'source':'REAL_MEASURED'}
    action=candidate(CameraCheck(reference_ref='c'*64)).model_dump(mode='json')
    env=PhysicalEnvironment(trials,checks);assert env.perform(action) is None
    assert env.admission_history==['REQUESTED','AWAITING_RECORDING']
    request=env.pending_action['request_id']
    env.responses[request]={'request_id':request,'verified':True,'trials':(), 'checks':checks,'new_reference_video_sha256':'d'*64}
    assert env.perform(action)['receipt']['new_observations']==0
    assert env.admission_history[-2:]==['VALIDATING','ADMITTED'] and env.pending_action is None
    bad=PhysicalEnvironment(trials,checks);bad.perform(action)
    bad.responses[bad.pending_action['request_id']]={'verified':False}
    with pytest.raises(ValueError):bad.perform(action)
    assert bad.admission_history[-1]=='REJECTED'
    expired=PhysicalEnvironment(trials,checks,deadline_utc='2000-01-01T00:00:00Z')
    with pytest.raises(AdapterFailure) as error:expired.perform(action)
    assert error.value.code=='EXPERIMENT_BUDGET_EXPIRED' and expired.admission_history[-1]=='EXPIRED'

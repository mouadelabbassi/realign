"""Offline contracts, official parser, camera, timing and uncertainty tests.

Every event fixture is SIMULATED_API_FIXTURE, never evidence of a Meta call.
"""
import asyncio
from dataclasses import replace
import json
from pathlib import Path
import numpy as np
import pytest

from realign.contracts.video import VideoObservation, ReleaseEstimate, VideoTrial
from realign.perception.video import metadata_from_ffprobe, probe_video, iter_video_frames, VideoError
from realign.perception.sam_client import parse_sam_events, SamClient, SamError
from realign.perception.track import extract_track, TrackFlag
from realign.perception.calibration import fit_planar_calibration
from realign.perception.timing import estimate_release
from realign.perception.uncertainty import stationary_noise, reviewed_noise, combine_noise, repeatability
from realign.observation.camera import project, unproject, camera_jacobian
from realign.fit.robust_fit import fit_free, predict_free, FitOptions
from realign.fit.baselines import compare_baselines
from realign.physics import PendulumParams
from realign.synth.video_fixture import fixture_events, render_fixture, fixture_calibration


def metadata(pts=(100, 140, 220, 260), width=640, height=480):
    return metadata_from_ffprobe({
        'streams': [{'width': width, 'height': height, 'time_base': '1/1000',
                     'codec_name': 'h264', 'tags': {'creation_time': '2026-10-31T10:00:00Z'}}],
        'frames': [{'pts': t} for t in pts], 'format': {'format_name': 'mov,mp4'},
    }, video_sha256='a'*64, source_kind='SYNTHETIC_RENDER')


def test_pts_are_original_and_variable_frame_rate():
    m = metadata()
    assert m.pts == (100, 140, 220, 260)
    np.testing.assert_array_equal(m.t_s, [.1, .14, .22, .26])
    assert m.variable_frame_rate
    assert m.container_creation_utc == '2026-10-31T10:00:00Z'
    assert m.recording_start_utc is None
    assert m.time_base == '1/1000'


@pytest.mark.parametrize('pts', [(0, 0, 10), (1, 0, 10), (0,), (0, 'N/A', 40)])
def test_malformed_pts_rejected_without_fps_fallback(pts):
    with pytest.raises(VideoError):
        metadata(pts)


def test_missing_pts_not_replaced_by_best_effort():
    with pytest.raises(VideoError, match='PTS'):
        metadata_from_ffprobe({'streams': [{'width':640,'height':480,'time_base':'1/1000'}],
                              'frames': [{'best_effort_timestamp':0},{'pts':40}]},
                             video_sha256='a'*64, source_kind='REAL_PHONE')


def test_official_stream_parser_uses_content_part_done():
    m = metadata((0, 40, 80))
    run = asyncio.run(parse_sam_events(fixture_events(frames=[0, 2]), m,
                                      source='SIMULATED_API_FIXTURE'))
    assert run.source == 'SIMULATED_API_FIXTURE'
    assert len(run.masks) == 2
    assert run.masks[0].pixels.sum() == 197
    track = extract_track(run, m)
    assert track.valid.tolist() == [True, False, True]
    assert track.flags[1] & TrackFlag.MISSING
    assert np.isnan(track.xy_px[1]).all()


@pytest.mark.parametrize('kind', ['incomplete', 'failed', 'refusal', 'malformed', 'frame_mismatch', 'eof'])
def test_bad_api_streams_fail_explicitly(kind):
    events = fixture_events(frames=[0, 2], failure=kind)
    with pytest.raises(SamError):
        asyncio.run(parse_sam_events(events, metadata((0,40,80)), source='SIMULATED_API_FIXTURE'))


def test_empty_match_is_not_an_api_successful_track():
    run = asyncio.run(parse_sam_events(fixture_events(frames=[]), metadata(), source='SIMULATED_API_FIXTURE'))
    assert run.receipt['status'] == 'completed'
    track = extract_track(run, metadata())
    assert not track.valid.any()
    assert track.summary['quality'] == 'quarantined'


def test_no_identity_fallback():
    m = metadata((0,40,80))
    run = asyncio.run(parse_sam_events(fixture_events(frames=[0,1,2]), m, source='SIMULATED_API_FIXTURE'))
    changed = replace(run, masks=(run.masks[0], replace(run.masks[1], object_id='7'), run.masks[2]))
    with pytest.raises(SamError, match='identity'):
        extract_track(changed, m)
    track = extract_track(changed, m, object_id='0')
    assert not track.valid[1]
    assert track.flags[1] & TrackFlag.IDENTITY


def test_live_client_missing_key_never_calls_network(monkeypatch):
    monkeypatch.delenv('MODEL_API_KEY', raising=False)
    with pytest.raises(SamError, match='MODEL_API_KEY'):
        SamClient.from_environment(standard_tier_confirmed=True)


def test_homography_gravity_pivot_roundtrip_and_check_error():
    cal = fixture_calibration()
    points = np.array([[0.,0.],[.2,-.7],[-.35,-.6],[.4,-.5]])
    raw = project(points, cal)
    np.testing.assert_allclose(unproject(raw, cal), points, atol=1e-8)
    assert cal.check_rms_px < 1e-5
    np.testing.assert_allclose(unproject(np.array([cal.pivot_px]), cal), [[0.,0.]], atol=1e-8)
    j = camera_jacobian(raw[1:2], cal)[0]
    delta = np.array([.0001,0.])
    np.testing.assert_allclose((unproject(raw[1:2]+delta,cal)-unproject(raw[1:2]-delta,cal))[0]/.0002,
                               j[:,0], rtol=1e-5, atol=1e-10)


def test_distortion_roundtrip():
    cal = replace(fixture_calibration(), camera_matrix=((700.,0.,320.),(0.,710.,240.),(0.,0.,1.)),
                  distortion=(-.10,.025,.001,-.002,0.), intrinsics_id='fixture_intrinsics')
    points = np.array([[.2,-.4],[-.3,-.55],[0.,-.72]])
    np.testing.assert_allclose(unproject(project(points, cal), cal), points, atol=2e-7)


def test_collinear_calibration_rejected():
    pts=np.column_stack([np.arange(6),np.zeros(6)])
    with pytest.raises(ValueError, match='degenerate'):
        fit_planar_calibration(pts,pts,pivot_px=(0.,0.),hanging_px=(0.,10.),
                               image_size=(640,480),calibration_id='bad',source='SYNTHETIC_FIXTURE')


def test_covariance_stationary_manual_and_repeat_variation_separated():
    rng=np.random.default_rng(42)
    positions=rng.multivariate_normal([200.,300.],[[.4,.1],[.1,.8]],size=5000)
    noise=stationary_noise(positions,np.ones(5000,bool),source_ids=('stationary',),provenance='SYNTHETIC')
    np.testing.assert_allclose(noise.covariance_px2,[[.4,.1],[.1,.8]],atol=.06)
    reference=rng.normal(size=(1000,2))
    tracked=reference+[2.,-1.]+rng.normal(0,.3,size=(1000,2))
    reviewed=reviewed_noise(tracked,reference,source_ids=('reviewed',),provenance='SYNTHETIC')
    np.testing.assert_allclose(reviewed.bias_px,[2.,-1.],atol=.04)
    assert np.max(np.linalg.eigvalsh(reviewed.covariance_px2)) < .12
    combined=combine_noise([noise,reviewed])
    assert np.linalg.eigvalsh(np.array(combined.covariance_px2)-noise.covariance_px2).min() >= -1e-10


def test_release_estimated_from_observations_and_bracketed():
    t=np.arange(0.,1.,.02)+3.5
    rng=np.random.default_rng(7)
    xy=np.array([200.,300.])+np.maximum(t-3.88,0)[:,None]**2*np.array([400.,100.])
    xy+=rng.normal(0,.08,xy.shape)
    release=estimate_release(t,xy,np.ones(len(t),bool),np.eye(2)*.08**2)
    assert abs(release.time_s-3.88) < .04
    assert release.lower_s <= 3.88 <= release.upper_s
    assert release.sigma_s > 0


def test_static_recording_has_no_invented_release():
    t=np.arange(40)*.04
    with pytest.raises(ValueError,match='release'):
        estimate_release(t,np.ones((40,2))*200,np.ones(40,bool),np.eye(2))


@pytest.fixture(scope='module')
def rendered(tmp_path_factory):
    folder=tmp_path_factory.mktemp('rendered')
    return render_fixture(folder/'synthetic.mp4',duration_s=3.)


def test_actual_rendered_video_decode_and_frame_mapping(rendered):
    m=probe_video(rendered['path'],source_kind='SYNTHETIC_RENDER')
    frames=list(iter_video_frames(rendered['path'],m))
    assert len(frames)==len(m.pts)
    assert frames[0].shape==(m.height,m.width,3)
    np.testing.assert_array_equal(m.t_s,rendered['metadata'].t_s)
    run=asyncio.run(parse_sam_events(rendered['events'],m,source='SIMULATED_API_FIXTURE'))
    track=extract_track(run,m)
    error=np.linalg.norm(track.xy_px[track.valid]-rendered['reference_px'][track.valid],axis=1)
    assert error.max() < 1.


def test_actual_variable_frame_rate_clip_preserves_frame_pts(tmp_path):
    fixture=render_fixture(tmp_path/'vfr.mp4',duration_s=.8,variable_rate=True)
    m=probe_video(fixture['path'],source_kind='SYNTHETIC_RENDER')
    assert m.variable_frame_rate
    assert len(set(np.diff(m.pts)))==2
    assert len(list(iter_video_frames(fixture['path'],m)))==len(m.pts)


def test_lens_calibration_from_distinct_synthetic_checkerboard_views():
    import cv2
    from realign.perception.calibration import calibrate_lens
    grid=np.mgrid[0:7,0:6].T.reshape(-1,2)*.025
    board=np.c_[grid,np.zeros(len(grid))]
    k=np.array([[700.,0.,320.],[0.,710.,240.],[0.,0.,1.]])
    obj=[]; image=[]
    for i in range(7):
        projected=cv2.projectPoints(board,np.array([.06*i-.18,.03*i-.1,.04*i]),
                                   np.array([-.1+.015*i,-.08+.005*i,.65+.035*i]),k,np.zeros(5))[0].reshape(-1,2)
        obj.append(board); image.append(projected)
    fitted=calibrate_lens(obj,image,(640,480))
    assert fitted['lens_rms_px']<.001
    np.testing.assert_allclose(np.asarray(fitted['camera_matrix'])[:2,:2],k[:2,:2],atol=.05)


def test_release_covariance_is_common_not_independent_per_frame(rendered):
    from realign.perception.pipeline import make_video_trial
    from realign.observation.noise import whiten_video
    m=rendered['metadata']
    run=asyncio.run(parse_sam_events(rendered['events'],m,source='SIMULATED_API_FIXTURE'))
    track=extract_track(run,m)
    noise=stationary_noise(track.xy_px[:8],track.valid[:8],source_ids=('fixture_stationary',),provenance='SYNTHETIC')
    trial=make_video_trial('render',m,run,track,fixture_calibration(),noise)
    prediction=predict_free(PendulumParams(.72),trial)
    velocity=np.gradient(prediction,m.t_s,axis=0)
    residual=velocity[track.valid]*trial.release.sigma_s
    z=whiten_video(residual,trial,prediction)
    assert np.sum(z*z)<=1.+1e-8


def test_live_sdk_contract_and_bounded_retry_are_mocked_only(rendered):
    from types import SimpleNamespace
    class RateLimit(RuntimeError):
        status_code=429
    class Stream:
        async def __aenter__(self): return self
        async def __aexit__(self,*args): return False
        def __aiter__(self):
            async def generate():
                for event in rendered['events']: yield event
            return generate()
    class Files:
        def __init__(self): self.n=0
        async def create(self,**kwargs):
            self.n+=1
            assert kwargs['purpose']=='user_data' and kwargs['file'][2]=='video/mp4'
            if self.n==1: raise RateLimit('SENSITIVE_MOCK_SENTINEL')
            return SimpleNamespace(id='file-SIMULATED_FIXTURE')
    class Responses:
        async def create(self,**kwargs):
            assert kwargs['model']=='sam-3.1' and kwargs['stream'] is True
            assert kwargs['input'][0]['content']==[
                {'type':'input_text','text':'the pendulum bob'},
                {'type':'input_video','file_id':'file-SIMULATED_FIXTURE'}]
            return Stream()
    class FakeAPI:
        files=Files(); responses=Responses()
        async def close(self): pass
    client=SamClient(FakeAPI(),source='SIMULATED_API_FIXTURE',retry_delay=0)
    run=asyncio.run(client.segment_video(rendered['path'],rendered['metadata']))
    assert run.source=='SIMULATED_API_FIXTURE'
    assert len(client.calls)==3
    assert client.calls[0]['status']=='failed'
    assert 'SENSITIVE_MOCK_SENTINEL' not in json.dumps(run.receipt)


def test_failed_upload_stops_after_three_attempts(rendered):
    class ServerError(RuntimeError):
        status_code=503
    class Fake:
        def __init__(self): self.n=0; self.files=self
        async def create(self,**kwargs):
            self.n+=1
            raise ServerError('SENSITIVE_MOCK_SENTINEL')
    api=Fake(); client=SamClient(api,source='SIMULATED_API_FIXTURE',retry_delay=0)
    with pytest.raises(SamError) as caught:
        asyncio.run(client.segment_video(rendered['path'],rendered['metadata']))
    assert api.n==3 and len(caught.value.calls)==3
    assert 'SENSITIVE_MOCK_SENTINEL' not in str(caught.value)


def test_fixture_cache_cannot_be_replayed_as_real(rendered,tmp_path):
    from realign.perception.workflow import save_sam_cache,load_sam_cache
    run=asyncio.run(parse_sam_events(rendered['events'],rendered['metadata'],source='SIMULATED_API_FIXTURE'))
    save_sam_cache(tmp_path/'fixture',run)
    with pytest.raises(SamError,match='actual SAM'):
        load_sam_cache(tmp_path/'fixture',rendered['metadata'])


def test_missing_real_inputs_produce_not_run_readiness(tmp_path):
    from realign.perception.workflow import process_manifest
    config={'schema_version':1,'source_kind':'REAL_PHONE','stationary':{'id':'stationary','video':'missing.mp4'},
            'calibration_file':'missing.json','exploration':[],'development':[]}
    path=tmp_path/'manifest.json'; path.write_text(json.dumps(config))
    result=asyncio.run(process_manifest(path,tmp_path/'report'))
    assert result['g2_passed'] is False and result['real_measurements']==[]
    assert result['actual_api']['status']=='not_run'
    assert result['actual_api']['successful_calls']==result['actual_api']['failed_calls']==0
    assert result['blockers']


def test_real_workflow_cannot_read_sealed_paths(tmp_path):
    from realign.perception.workflow import process_manifest
    config={'schema_version':1,'source_kind':'REAL_PHONE','stationary':{'id':'stationary','video':'sealed/hidden.mp4'},
            'calibration_file':'points.json'}
    path=tmp_path/'manifest.json'; path.write_text(json.dumps(config))
    result=asyncio.run(process_manifest(path,tmp_path/'report'))
    assert not result['g2_passed']
    assert result['failures'][0]['error_type']=='ValueError'


def test_no_synthetic_truth_imports_in_real_workflow():
    import ast
    root=Path(__file__).resolve().parents[1]/'src'/'realign'/'perception'
    for path in root.glob('*.py'):
        for node in ast.walk(ast.parse(path.read_text(encoding='utf-8'))):
            if isinstance(node,(ast.Import,ast.ImportFrom)):
                names=[n.name for n in node.names]+[getattr(node,'module','') or '']
                assert not any('synth' in n or 'truth' in n or 'vault' in n for n in names),path


def test_real_contract_requires_actual_api_and_real_media(rendered):
    from realign.perception.pipeline import make_video_trial
    m=rendered['metadata']
    run=asyncio.run(parse_sam_events(rendered['events'],m,source='SIMULATED_API_FIXTURE'))
    track=extract_track(run,m)
    noise=stationary_noise(track.xy_px[:8],track.valid[:8],source_ids=('fixture_stationary',),provenance='SYNTHETIC')
    trial=make_video_trial('render',m,run,track,fixture_calibration(),noise)
    assert trial.observation.provenance=='SYNTHETIC'
    np.testing.assert_array_equal(trial.observation.t_s,m.t_s)
    with pytest.raises(ValueError):
        replace(trial.observation,provenance='REAL_SAM')
    with pytest.raises(ValueError):
        replace(trial.observation,covariance_unit='px')
    with pytest.raises(ValueError):
        replace(trial.observation,frame_covariance_px2=np.zeros((2,2)))


def test_full_offline_g2_pipeline_and_report(tmp_path):
    from realign.synth.g2_verification import verify_offline_g2
    result=verify_offline_g2(tmp_path)
    assert result['offline_passed']
    assert result['g2_passed'] is False
    assert result['actual_api']['successful_calls']==0
    assert result['actual_api']['failed_calls']==0
    assert result['actual_api']['status']=='not_run'
    assert result['real_measurements']==[]
    assert result['synthetic_fixture']['baseline']['B1']['heldout']['rmse_xy_px'] < 10.
    assert (tmp_path/'G2_READINESS.md').exists()
    assert (tmp_path/'g2_fixture_comparison.png').stat().st_size>10000

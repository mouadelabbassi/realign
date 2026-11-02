"""Offline contract/continuation fixtures, not phone recordings or SAM verification."""
import asyncio,json,os
from copy import deepcopy
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace as NS
import numpy as np
import pytest
from realign.audit.chain import canonical,digest
from realign.contracts import Experiment
from realign.contracts.video import VideoMetadata,VideoObservation,VideoTrial,NoiseEstimate,PlanarCalibration,ReleaseEstimate
from realign.physics import PendulumParams
from realign.synth.generator import generate_trial
from realign.physical.ingestion import analysis_window,input_blockers,independent_rows
from realign.physical.session import PhysicalEnvironment,PhysicalValidator,PrefixReplayAdapter,phone_trial,validate_checkpoint
from realign.physical.orchestration import investigate_phone,baseline_summary
from realign.agent.investigator import Investigator
from realign.agent.adapters import DeterministicAdapter
from realign.tools.sandbox import WorkerClient
from realign.tools.client import ScientificSession,candidate
from realign.contracts.investigation import CameraCheck
from realign.synth.investigation_fixtures import case,NOMINAL


def video_fixture(sha='e'*64,n=81):
    """SIMULATED real-shaped protocol fixture only. No experimental claim."""
    meta=VideoMetadata(sha,'REAL_PHONE',1280,720,1280,720,tuple(range(n)),'1/100','SIMULATED_CONTRACT_ONLY')
    noise=NoiseEstimate(((.25,0.),(0.,.25)),(0.,0.),0.,.01,('SIMULATED_STATIONARY',),'REAL_SAM','SIMULATED_CONTRACT_ONLY')
    cal=PlanarCalibration('TEST_ONLY',((600.,0.,640.),(0.,-600.,160.),(0.,0.,1.)),(1280,720),(640.,160.),.1,.1,'REAL_MEASURED',6,4)
    o=VideoObservation('TEST_ONLY',meta,np.tile([700.,550.],(n,1)),np.ones(n,bool),
        np.tile(np.eye(2)*.25,(n,1,1)),np.zeros(n,dtype=np.uint32),noise,cal.calibration_id,'REAL_SAM','REAL_API')
    return VideoTrial('TEST_ONLY',Experiment(.4,float(meta.t_s[-1]-.075),100.),o,cal,ReleaseEstimate(.075,.01,.05,.1,'SIMULATED_CONTRACT_ONLY'))


def test_window_preserves_absolute_original_pts_covariance_and_missing_rows():
    t=video_fixture(n=301)
    with pytest.raises(ValueError,match='explicit'):analysis_window(t)
    selected,mapping=analysis_window(t,[0.,1.6])
    assert selected.observation.metadata.pts==t.observation.metadata.pts[:161]
    assert mapping['original_frame_indices']==list(range(161))
    assert selected.observation.metadata.video_sha256==t.observation.metadata.video_sha256
    np.testing.assert_array_equal(selected.observation.frame_covariance_px2,t.observation.frame_covariance_px2[:161])
    assert selected.release==t.release and selected.experiment.duration_s==pytest.approx(1.525)
    with pytest.raises(ValueError):analysis_window(t,[.2,.8])


@pytest.mark.parametrize('source',['REAL_EXTERNAL','SYNTHETIC_RENDER','SYNTHETIC'])
def test_phone_entrypoint_rejects_other_source_kinds(tmp_path,source):
    assert input_blockers({'source_kind':source},tmp_path)==['CONTROLLED_REAL_PHONE_MANIFEST_REQUIRED']


def test_missing_calibration_recordings_reviews_timing_fail_before_worker_or_api(tmp_path,monkeypatch):
    import realign.physical.orchestration as module
    def forbidden(*a,**kw):raise AssertionError('No runtime or API may start without independently supplied inputs')
    monkeypatch.setattr(module,'WorkerClient',forbidden)
    p=tmp_path/'manifest.json';p.write_text(json.dumps({'source_kind':'REAL_PHONE','stationary':{'id':'a','video':'absent.mp4'},
        'exploration':[],'development':[{'video':'data/sealed/DO_NOT_READ.mp4'}]}))
    result=asyncio.run(investigate_phone(p,tmp_path/'out'))
    assert result['status']=='BLOCKED_INPUTS' and result['actual_api_requests']==0
    assert 'MEASURED_CALIBRATION_NOT_SUPPLIED' in result['blockers']
    assert 'INDEPENDENT_MANUAL_REVIEWS_NOT_SUPPLIED' in result['blockers']
    assert result['full_G2_passed'] is False and result['pending_action'] is None
    assert 'DO_NOT_READ' not in canonical(result).decode()


def test_synthetic_observations_and_unattested_references_cannot_become_real():
    t=generate_trial(PendulumParams(.72),Experiment(.3,.5,20.),seed=68501,trial_id='SYNTHETIC_UNIT_FIXTURE')[0]
    with pytest.raises(ValueError):phone_trial(t)
    for doc in [[],{'annotation_source':'SYNTHETIC_TEST_REFERENCE','rows':[]},
                {'annotation_source':'INDEPENDENT_HUMAN','independent_of_sam':False}]:
        with pytest.raises(ValueError):independent_rows(doc)


def test_physical_structural_acceptance_never_uses_a_synthetic_null_gate():
    decision=NS(outcome='REPAIR_STRUCTURE')
    accepted,reasons=PhysicalValidator().assess(decision,NS(comparison={'status':'OK','calibrated_support':'PEG_PREDICTIVE_DIFFERENCE'}),coverage=.65,receipt=None)
    assert not accepted and reasons==('UNCALIBRATED',)


def test_baseline_export_uses_current_actual_tool_results_without_invented_errors():
    def call(name,result,**arguments):
        return {'name':name,'arguments':arguments,'result':result}
    result={'status':'OK','trajectory_rmse_px':1.25}
    fit={'status':'OK','fitted_model_ref':'free','robust_cost':3.5}
    score={'candidate':'FREE','model_ref':'free','trial_cv_mse_px2':2.}
    trace={'tool_results':[
        call('inspect_discrepancy',{'trajectory_rmse_px':99.},trial_refs=['old'],model_ref='nominal'),
        call('inspect_discrepancy',result,trial_refs=['current'],model_ref='nominal'),
        call('fit_candidate_model',fit,trial_refs=['current'],candidate='FREE'),
        call('compare_candidate_models',{'status':'AMBIGUOUS','scores':[score]},trial_refs=['current'])]}
    summary=baseline_summary(trace,['current'],'nominal',{'radial_rmse_m':.001})
    assert summary['B0']==result
    assert summary['B1']['fit']==fit and summary['B1']['exploration_cross_validation']==score
    assert summary['B3']=={'status':'NOT_RUN'}
    assert summary['B2']=={'radial_rmse_m':.001}
    # Later failed fits cannot inherit an earlier model's cross-validation score.
    trace['tool_results'].append(call('fit_candidate_model',{'status':'FAILED','fitted_model_ref':None},
                                     trial_refs=['current'],candidate='FREE'))
    assert 'exploration_cross_validation' not in baseline_summary(trace,['current'],'nominal',{})['B1']


def test_physical_request_waits_for_hash_bound_new_validated_recording():
    trials=[video_fixture('a'*64),video_fixture('b'*64)]
    checks={'source':'REAL_MEASURED'};c=candidate(CameraCheck(reference_ref='c'*64)).model_dump(mode='json')
    waiting=PhysicalEnvironment(trials,checks)
    assert waiting.perform(c) is None
    p=waiting.pending_action
    assert p['action_completed'] is False and p['observation_source']=='REAL_PHONE'
    response={'request_id':p['request_id'],'verified':True,'trials':(), 'checks':checks,'new_reference_video_sha256':'d'*64}
    supplied=PhysicalEnvironment(trials,checks,responses={p['request_id']:response})
    result=supplied.perform(c)
    assert result['receipt']=={'kind':'CAMERA_CALIBRATION','source':'APPROVED_RECORDING_LIBRARY','new_observations':0}
    response['new_reference_video_sha256']='a'*64
    with pytest.raises(ValueError):PhysicalEnvironment(trials,checks,responses={p['request_id']:response}).perform(c)


class WaitingSyntheticControl:
    """Explicit synthetic controller test; never used by the real entrypoint."""
    def __init__(self,base,ready=False):
        self.base=base;self.initial=base.initial;self.checks=base.checks;self.ready=ready;self.pending_action=None
    def perform(self,c):
        if self.ready:return self.base.perform(c)
        p={'schema_version':'1.0','observation_source':'SYNTHETIC_CONTINUATION_TEST','candidate':c,
           'state':'WAITING_FOR_VALIDATED_RECORDINGS','action_completed':False}
        p['request_id']=digest(p);self.pending_action=p;return None


@pytest.mark.skipif(os.name=='nt',reason='Actual isolated numerical continuation runs in Linux/WSL')
def test_actual_pending_checkpoint_replays_numeric_actions_and_freezes_only_after_response():
    with WorkerClient(timeout_s=120) as worker:
        first=WaitingSyntheticControl(case('measurement_problem',seed=68500))
        s=ScientificSession(worker,first.initial,NOMINAL,first.checks)
        checkpoint=Investigator(s,DeterministicAdapter(),first).run()
        assert validate_checkpoint(checkpoint) and checkpoint['model_frozen'] is False
        assert 'freeze' not in checkpoint and checkpoint['state_history'][-1]=='REQUEST_EVIDENCE'
        altered=deepcopy(checkpoint);altered['pending_action']['action_completed']=True
        with pytest.raises(ValueError):validate_checkpoint(altered)
        second=WaitingSyntheticControl(case('measurement_problem',seed=68500),ready=True)
        s=ScientificSession(worker,second.initial,NOMINAL,second.checks)
        adapter=PrefixReplayAdapter(checkpoint,DeterministicAdapter())
        result=Investigator(s,adapter,second).run()
        assert result['freeze']['rounds']==2 and result['freeze']['experiments']==1
        assert result['freeze']['outcome']=='CORRECT_MEASUREMENT'
        payload=canonical([x['context'] for x in result['steps']]).decode()
        assert all(x not in payload for x in ('hidden_parameters','sealed_measurements','reveal_nonce','development'))

"""Unit/adversarial fixtures; mocked evidence is never benchmark evidence."""
from copy import deepcopy
from dataclasses import asdict, replace
import json
from types import SimpleNamespace as NS
import numpy as np
import pytest
from pydantic import TypeAdapter, ValidationError
from openai.types.chat import ChatCompletion
from realign.audit.chain import AuditChain, canonical, digest
from realign.contracts.investigation import (Budget, Release, Repeat, Stationary, CameraCheck,
    ExperimentAction, AgentTurn, Hypothesis, ToolCall, DiscrepancyOutput)
from realign.agent.adapters import MuseAdapter, AdapterFailure
from realign.agent.investigator import StateMachine, ScientificValidator
from realign.tools.registry import ToolRegistry
from realign.tools.resources import encode_trial, ResourceStore, AccessDenied
from realign.synth.investigation_fixtures import case,NOMINAL


@pytest.fixture
def registry():
    env=case('no_fault',seed=71000)
    return ToolRegistry([encode_trial(t) for t in env.initial],asdict(NOMINAL),checks=env.checks)


@pytest.mark.parametrize('action', [
    {'kind':'RELEASE','release_angle_rad':.65},
    {'kind':'REPEAT','source_trial_ref':'a'*64},
    {'kind':'STATIONARY_REFERENCE'},
    {'kind':'CAMERA_CALIBRATION','reference_ref':'b'*64},
])
def test_strict_discriminated_experiment_union(action):
    result=TypeAdapter(ExperimentAction).validate_json(canonical(action))
    assert result.kind==action['kind']
    bad=dict(action, instructions='UNSAFE_ACTION')
    with pytest.raises(ValidationError):
        TypeAdapter(ExperimentAction).validate_json(canonical(bad))


@pytest.mark.parametrize('bad', [
    {'kind':'RELEASE','release_angle_rad':.9},
    {'kind':'RELEASE','release_angle_rad':-.2},
    {'kind':'RELEASE','release_angle_rad':True},
    {'kind':'EXECUTE','python':'print(1)'},
    {'kind':'REPEAT','source_trial_ref':'../../sealed/private'},
])
def test_unsafe_or_unapproved_action_shapes_rejected(bad):
    with pytest.raises(ValidationError):
        TypeAdapter(ExperimentAction).validate_json(canonical(bad))


@pytest.mark.parametrize('field', ['path','hidden_parameters','ground_truth','sealed_data','code'])
def test_adversarial_tool_fields_are_rejected_and_scrubbed(registry,field):
    raw={'trial_refs':registry.trial_refs,'model_ref':registry.nominal_ref,field:'PRIVATE_CANARY_9382'}
    r=registry.dispatch('inspect_discrepancy',raw)
    assert r['status']=='FAILED' and r['code']=='INVALID_INPUT'
    assert 'PRIVATE_CANARY_9382' not in json.dumps(registry.audit.events)


def test_resource_capabilities_types_and_immutability(registry):
    r=registry.dispatch('inspect_discrepancy',{'trial_refs':['f'*64],'model_ref':registry.nominal_ref})
    assert r['code']=='ACCESS_DENIED'
    r=registry.dispatch('inspect_discrepancy',{'trial_refs':registry.trial_refs,'model_ref':registry.trial_refs[0]})
    assert r['code']=='ACCESS_DENIED'
    store=ResourceStore(); source={'n':[1,2]}
    ref=store.put('TEST',source); source['n'][0]=999
    value=store.get(ref,'TEST'); value['n'][0]=888
    assert store.get(ref,'TEST')=={'n':[1,2]}


def test_development_and_atomic_admission_rejected(registry):
    env=case('no_fault',seed=72000)
    with pytest.raises(AccessDenied):
        encode_trial(replace(env.initial[0],zone='development'))
    first=encode_trial(env.initial[0]); second=encode_trial(env.initial[1])
    second['trial']['zone']='development'
    before=list(registry.trial_refs)
    with pytest.raises(AccessDenied):
        registry.admit([first,second])
    assert registry.trial_refs==before


def test_references_cannot_change_registered_comparison_order(registry):
    r=registry.dispatch('compare_candidate_models',{'trial_refs':list(reversed(registry.trial_refs)),
        'fitted_model_refs':[registry.nominal_ref,registry.nominal_ref],'protocol_ref':registry.protocol_ref})
    assert r['code']=='ACCESS_DENIED'


def test_quality_checks_use_reference_measurements_and_missing_metrics(registry):
    from realign.tools.client import candidate
    check=candidate(Stationary()).model_dump(mode='json')
    registry.register_candidates([check])
    r=registry.dispatch('score_candidate_experiment',{'fitted_model_refs':[],'candidate':check,
        'feasibility_protocol_ref':registry.protocol_ref})
    assert r['expected_information_gain_nat'] is None and r['predictive_discrimination_sigma'] is None
    assert r['method']=='REFERENCE_CHECK_PRIORITY'
    registry.admit([],{'source':'SYNTHETIC','reference_px':[[0,0],[1,0],[1,1],[0,1]],
                       'observed_px':[[8,0],[9,0],[9,1],[8,1]]})
    assert registry.checks['reference_reprojection_rms_px']==8.
    assert registry.checks['stationary_sd_px'] is None and not registry.checks['quality_ok']


def test_unavailable_fit_metric_and_hard_budget_are_not_invented(monkeypatch):
    from realign.tools import registry as module
    from realign.fit.robust_fit import FitError
    env=case('no_fault',seed=73000)
    r=ToolRegistry([encode_trial(t) for t in env.initial],asdict(NOMINAL),budget=Budget(max_fit_jobs=1),checks=env.checks)
    monkeypatch.setattr(module,'fit_free',lambda *a,**k: (_ for _ in ()).throw(FitError('injected failure')))
    args={'trial_refs':r.trial_refs,'candidate':'FREE','budget_ref':r.budget_ref,'nominal_model_ref':r.nominal_ref}
    first=r.dispatch('fit_candidate_model',args)
    assert first['status']=='FAILED' and first['robust_cost'] is None and first['fitted_model_ref'] is None
    second=r.dispatch('fit_candidate_model',args)
    assert second['code']=='BUDGET' and r.used['fit_jobs']==1


def test_frozen_registry_does_not_append_evidence(registry):
    registry.frozen=True
    head=registry.audit.head
    with pytest.raises(AccessDenied):
        registry.dispatch('inspect_discrepancy',{})
    assert registry.audit.head==head


def test_state_machine_and_audit_tamper_detection():
    a=AuditChain(); m=StateMachine(a)
    for s in ('HYPOTHESIZE','TEST','REQUEST_EVIDENCE','OBSERVE','HYPOTHESIZE','TEST','DECIDE','FREEZE'):
        m.move(s)
    assert AuditChain.verify(a.events)
    with pytest.raises(ValueError):
        m.move('OBSERVE')
    corrupted=a.events; corrupted[0]['payload']['to']='FREEZE'
    assert not AuditChain.verify(corrupted) and AuditChain.verify(a.events)


def proposal(outcome='REPAIR_STRUCTURE',model='b'*64):
    return AgentTurn(action='DECIDE',hypotheses=(Hypothesis(family='PEG_ONE_SIDE',status='UNRESOLVED',evidence_refs=('a'*64,)),),
                     experiment_ref=None,outcome=outcome,model_ref=model,evidence_refs=('a'*64,),reasons=())


def test_low_training_loss_does_not_grant_structural_acceptance():
    # Protocol fixture only: no scientific fit or empirical score is claimed.
    s=NS(results=[{'result':{'evidence_ref':'a'*64}}],discrepancy={'quality_ok':True},
         comparison=None,fits={'PEG_ONE_SIDE':{'robust_cost':0.,'fitted_model_ref':'b'*64}})
    ok,reason=ScientificValidator().assess(proposal(),s,coverage=.65,receipt=None)
    assert not ok and reason==('UNCALIBRATED',)


@pytest.mark.parametrize('p,local,free_ratio',[(.1,True,10.),(.01,False,10.),(.01,True,1.)])
def test_validator_rejects_inconsistent_or_unidentified_repairs(p,local,free_ratio):
    c={'evidence_ref':'a'*64,'status':'OK','calibrated_support':'PEG_PREDICTIVE_DIFFERENCE',
       'empirical_tail_probability':p,'scores':[{'candidate':'FREE','noise_ratio':free_ratio}]}
    s=NS(results=[{'result':{'evidence_ref':'a'*64}}],discrepancy={'quality_ok':True},comparison=c,
         identifiability={'locally_identifiable':local,'evidence_ref':'a'*64},
         fits={'PEG_ONE_SIDE':{'fitted_model_ref':'b'*64}})
    assert not ScientificValidator().assess(proposal(),s,coverage=.65,receipt=None)[0]


def test_null_gate_rejects_short_or_wrong_budget_calibration(registry):
    gate={'protocol_ref':registry.protocol_ref,'budget_ref':registry.budget_ref,
          'scores':[0.]*19,'sample_count':19,'failed_comparisons':0,
          'scope':'SYNTHETIC_REGISTERED_PREDICTIVE_MODEL_COMPARISON'}
    with pytest.raises(ValueError):
        registry._validate_gate(gate)
    gate.update(scores=[0.]*20,sample_count=20,budget_ref='e'*64)
    with pytest.raises(ValueError):
        registry._validate_gate(gate)


def sdk_response(*,calls=None,content=None):
    return ChatCompletion(id='resp_FIXTURE',created=0,model='muse-spark-1.3',object='chat.completion',
        choices=[{'index':0,'finish_reason':'tool_calls' if calls else 'stop',
                  'message':{'role':'assistant','content':content,'tool_calls':calls}}])


def call_fixture(name='inspect_discrepancy',arguments=None):
    return {'id':'call_FIXTURE','type':'function','function':{'name':name,'arguments':arguments or json.dumps(
        {'trial_refs':['a'*64],'model_ref':'b'*64})}}


def discrepancy_fixture():
    return DiscrepancyOutput(evidence_ref='c'*64,status='OK',valid_samples=66,
        trajectory_rmse_px=.7,innovation_mean_square=1.,lag1_x=0.,
        localization_floor_mse_px2=.5,missing_fraction=0.,reference_reprojection_rms_px=.1,
        stationary_sd_px=.5,quality_ok=True,predictively_adequate=True).model_dump(mode='json')


def test_muse_structured_multi_turn_real_tool_protocol_fixture():
    responses=[sdk_response(calls=[call_fixture()]),sdk_response(content=proposal('ABSTAIN',None).model_dump_json())]
    requests=[]
    def create(**kwargs):
        requests.append(deepcopy(kwargs)); return responses.pop(0)
    a=MuseAdapter(NS(chat=NS(completions=NS(create=create))),budget=Budget(),source='SIMULATED_API_FIXTURE',retry_delay=0)
    first=a.next({'stage':'TEST'})
    a.deliver(first.calls,[discrepancy_fixture()])
    second=a.next({'stage':'TEST'})
    assert second.turn.outcome=='ABSTAIN'
    messages=requests[-1]['messages']
    assistant=next(m for m in messages if m.get('tool_calls'))
    tool=next(m for m in messages if m['role']=='tool')
    assert assistant['tool_calls'][0]['id']==tool['tool_call_id']
    assert json.loads(tool['content'])==discrepancy_fixture()
    assert requests[0]['tool_choice']=='auto' and requests[0]['response_format']['type']=='json_schema'
    assert a.stats['actual_api_requests']==0 and a.stats['fixture_requests']==2


@pytest.mark.parametrize('call',[
    call_fixture(name='open_file'),
    call_fixture(arguments='{"trial_refs":[],"path":"../sealed/secret"}'),
    call_fixture(arguments='{"trial_refs":["'+('a'*64)+'"],"model_ref":"'+('b'*64)+'","model_ref":"'+('c'*64)+'"}'),
])
def test_muse_rejects_malformed_or_unapproved_calls_before_execution(call):
    client=NS(chat=NS(completions=NS(create=lambda **k:sdk_response(calls=[call]))))
    a=MuseAdapter(client,budget=Budget(),source='SIMULATED_API_FIXTURE')
    with pytest.raises(AdapterFailure):
        a.next({'stage':'TEST'})
    assert not a._pending


def test_transient_api_retry_is_bounded_and_sanitized():
    class Transient(RuntimeError):
        status_code=503
    def fail(**k):
        raise Transient('PRIVATE_API_SENTINEL_8732')
    a=MuseAdapter(NS(chat=NS(completions=NS(create=fail))),budget=Budget(max_api_requests=2),
                  source='SIMULATED_API_FIXTURE',retry_delay=0)
    with pytest.raises(AdapterFailure):
        a.next({'stage':'TEST'})
    assert a.stats['fixture_requests']==2 and a.stats['actual_api_requests']==0
    assert 'PRIVATE_API_SENTINEL' not in json.dumps(a.receipts)


def test_model_turn_cannot_mix_hypothesis_and_physical_execution():
    value=proposal().model_dump(mode='json'); value['action']='HYPOTHESIZE'
    with pytest.raises(ValidationError):
        AgentTurn.model_validate_json(canonical(value))


def test_current_decision_views_cannot_be_rebound_to_other_model_or_subset():
    # Plumbing fixture only: validates capability binding, not numerical claims.
    from realign.tools.client import ScientificSession
    s=ScientificSession.__new__(ScientificSession)
    s.nominal_model_ref='a'*64; s.trial_refs=['b'*64,'c'*64]; s.results=[]
    s._round_clear()
    s.fits={'PEG_ONE_SIDE':{'fitted_model_ref':'d'*64}}
    s.worker=NS(call=lambda *a:{'status':'OK'})
    s.call('inspect_discrepancy',{'trial_refs':s.trial_refs,'model_ref':'d'*64})
    assert s.discrepancy is None
    s.call('inspect_identifiability',{'trial_refs':s.trial_refs,'fitted_model_ref':'e'*64})
    assert s.identifiability is None
    s.call('fit_candidate_model',{'trial_refs':[s.trial_refs[0]],'candidate':'FREE'})
    assert 'FREE' not in s.fits
    s.comparison={'status':'OK'}; s.identifiability={'status':'OK'}
    s.call('fit_candidate_model',{'trial_refs':s.trial_refs,'candidate':'FREE'})
    assert s.comparison is None and s.identifiability is None


def test_failed_null_fit_cannot_make_structural_tail_more_significant():
    from realign.tools.registry import empirical_tail
    # Formula fixture, not an empirical calibration or benchmark score.
    assert empirical_tail([0.]*20,1.)==1/21
    assert empirical_tail([0.]*19+[None],1.)==2/21
    assert empirical_tail([0.]*19+[None],1.)>.05

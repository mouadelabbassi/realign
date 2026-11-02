"""Actual isolated numerical integration. No Meta network calls are made."""
from copy import deepcopy
import json
import os
from pathlib import Path
import pytest
from realign.audit.chain import canonical, digest
from realign.tools.sandbox import WorkerClient
from realign.tools.client import ScientificSession
from realign.synth.investigation_fixtures import case,NOMINAL
from realign.agent.investigator import Investigator
from realign.agent.adapters import MockAdapter, ReplayAdapter, AdapterFailure
from realign.report.investigator_run import execute,verify_replay


@pytest.fixture(scope='module')
def worker():
    if os.name=='nt':
        pytest.skip('Numerical integration runs under Linux/WSL; native LPAC fails the registry-isolation probe.')
    with WorkerClient(timeout_s=600) as value:
        yield value


@pytest.mark.skipif(os.name!='nt',reason='Native Windows fail-closed test')
def test_native_windows_does_not_weaken_failed_registry_isolation():
    from realign.tools.sandbox import IsolationUnavailable
    with pytest.raises(IsolationUnavailable,match='user_environment_registry_denied'):
        WorkerClient(timeout_s=90)


def test_os_backed_isolation_denies_real_files_network_memory_and_credentials(worker):
    assert worker.isolation in ('WINDOWS_LPAC_JOB','LINUX_LANDLOCK_SECCOMP')
    assert all(worker.probe['filesystem_denied'])
    for key,value in worker.probe.items():
        if key!='filesystem_denied':
            assert value,key


def test_unknown_file_and_unapproved_capability_cannot_be_queried(worker):
    env=case('no_fault',seed=81000)
    s=ScientificSession(worker,env.initial,NOMINAL,env.checks)
    r=s.call('inspect_discrepancy',{'trial_refs':['e'*64],'model_ref':s.nominal_model_ref})
    assert r['code']=='ACCESS_DENIED'
    r=s.call('inspect_discrepancy',{'trial_refs':s.trial_refs,'model_ref':s.nominal_model_ref,
                                  'path':'data/sealed/PRIVATE_CANARY_FILE'})
    assert r['code']=='INVALID_INPUT'
    assert 'PRIVATE_CANARY_FILE' not in json.dumps(s.audit())
    s.freeze()
    before=s.audit()
    with pytest.raises(ValueError):
        s.call('inspect_discrepancy',{'trial_refs':s.trial_refs,'model_ref':s.nominal_model_ref})
    assert s.audit()==before


class FailAdapter(MockAdapter):
    source='MOCK_API_ERROR'
    def next(self, context):
        raise AdapterFailure('PRIVATE_SDK_ERROR_SENTINEL')


def test_api_protocol_error_results_in_explicit_sanitized_abstention(worker):
    r=execute('no_fault',worker=worker,adapter=FailAdapter(),seed=82000)
    assert r['freeze']['outcome']=='ABSTAIN' and 'API_ERROR' in r['freeze']['reasons']
    assert 'PRIVATE_SDK_ERROR_SENTINEL' not in json.dumps(r)
    assert verify_replay(r)


def test_missing_experiment_receipt_is_not_counted_as_an_executed_experiment(worker):
    env=case('measurement_problem',seed=83000)
    env.perform=lambda candidate:None
    s=ScientificSession(worker,env.initial,NOMINAL,env.checks)
    r=Investigator(s,MockAdapter(),env).run()
    assert r['freeze']['outcome']=='ABSTAIN'
    assert r['freeze']['experiment_requests']==1 and r['freeze']['experiments']==0
    assert r['freeze']['reasons']==['NO_NEW_EVIDENCE']


def test_missing_api_key_never_silently_runs_a_mock(monkeypatch):
    monkeypatch.delenv('MODEL_API_KEY',raising=False)
    r=execute('off_vertical_peg',arm='live',standard_tier_confirmed=True)
    assert r['status']=='NOT_RUN' and r['actual_api_requests']==0 and r['source']=='LIVE_MUSE'


def test_unavailable_isolation_abstains_without_fallback(monkeypatch):
    from realign.report import investigator_run as module
    from realign.tools.sandbox import IsolationUnavailable
    def unavailable(**kwargs):
        raise IsolationUnavailable('PRIVATE_HOST_SENTINEL')
    monkeypatch.setattr(module,'WorkerClient',unavailable)
    r=execute('no_fault')
    assert r['status']=='FAILED' and r['outcome']=='ABSTAIN'
    assert r['actual_api_requests']==0 and 'PRIVATE_HOST_SENTINEL' not in json.dumps(r)


@pytest.fixture(scope='module')
def two_round_trace(worker):
    # No empirical gate is supplied in CI. Actual fits and requested evidence run,
    # but structural acceptance MUST remain unavailable rather than using a fake gate.
    return execute('off_vertical_peg',arm='mock',gate=None,seed=84000,worker=worker)


def test_genuine_two_round_observation_only_investigation(two_round_trace):
    r=two_round_trace
    assert r['status']=='COMPLETED' and r['freeze']['rounds']==2 and r['freeze']['experiments']==1
    assert r['freeze']['outcome']=='ABSTAIN' and 'UNCALIBRATED' in r['freeze']['reasons']
    assert r['state_history']==['OBSERVE','HYPOTHESIZE','TEST','REQUEST_EVIDENCE','OBSERVE',
                                'HYPOTHESIZE','TEST','DECIDE','FREEZE']
    contexts=[s['context'] for s in r['steps']]
    assert any(len(c['trial_refs'])==2 for c in contexts) and any(len(c['trial_refs'])==4 for c in contexts)
    initial=[x for x in r['tool_results'] if x['name']=='inspect_identifiability'][0]['result']
    final=[x for x in r['tool_results'] if x['name']=='inspect_identifiability'][-1]['result']
    assert not initial['globally_identified'] and not final['globally_identified']
    # The human post-freeze label/evaluation never appear in an agent context.
    text=json.dumps(contexts)
    assert 'off_vertical_peg' not in text and 'development' not in text
    assert 'hidden_parameters' not in text and 'label_post_freeze_only' not in text
    assert r['adapter_stats']['actual_api_requests']==0 and verify_replay(r)


def test_audit_replay_detects_changed_decisions_contexts_and_state_history(two_round_trace):
    for mutator in (
        lambda r:r['freeze'].update(outcome='REPAIR_STRUCTURE'),
        lambda r:r['steps'][0]['context'].update(stage='FREEZE'),
        lambda r:r['state_history'].insert(1,'FREEZE'),
    ):
        value=deepcopy(two_round_trace); mutator(value)
        assert not verify_replay(value)
    assert not verify_replay({'status':'COMPLETED'})


def test_recorded_actions_reexecute_fresh_numerical_tools(worker,two_round_trace):
    r=execute('off_vertical_peg',worker=worker,gate=None,seed=84000,adapter=ReplayAdapter(two_round_trace))
    assert r['source']=='RECORDED_RESPONSE_REPLAY' and verify_replay(r)
    assert r['freeze']['freeze_sha256']==two_round_trace['freeze']['freeze_sha256']
    assert r['numerical_audit']['head']==two_round_trace['numerical_audit']['head']

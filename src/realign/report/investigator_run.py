"""Host orchestration/reporting. Development scoring happens only after FREEZE."""
import hashlib
import json
import os
from pathlib import Path
import platform
import time
import numpy as np
import scipy
from realign.audit.chain import canonical, digest, AuditChain
from realign.contracts.investigation import Budget
from realign.tools.sandbox import WorkerClient
from realign.tools.client import ScientificSession
from realign.tools.registry import parameters
from realign.fit.robust_fit import predict_free
from realign.fit.peg_fit import predict_peg
from realign.agent.adapters import DeterministicAdapter, MockAdapter, MuseAdapter, NotAuthorized
from realign.agent.investigator import Investigator
from realign.synth.investigation_fixtures import case, NOMINAL

ROOT=Path(__file__).resolve().parents[3]


def science_signature():
    h=hashlib.sha256()
    for folder in ('physics','fit','observation'):
        for p in sorted((ROOT/'src/realign'/folder).glob('*.py')):
            h.update(p.relative_to(ROOT).as_posix().encode()); h.update(p.read_bytes())
    for name in ('contracts/investigation.py','tools/registry.py','tools/resources.py',
                 'synth/investigation_fixtures.py','report/investigator_calibration.py'):
        h.update(name.encode()); h.update((ROOT/'src/realign'/name).read_bytes())
    h.update(canonical({'numpy':np.__version__,'scipy':scipy.__version__,'protocol':'task04-pilot-1',
                        'python':platform.python_version(),'system':platform.system(),'machine':platform.machine()}))
    return h.hexdigest()


def load_gate(path):
    path=Path(path).resolve()
    allowed=(ROOT/'artifacts/task04').resolve()
    if not path.is_relative_to(allowed):
        raise ValueError('calibration file must be in the approved task04 evidence directory')
    value=json.loads(path.read_text(encoding='utf-8'))
    if not value.get('valid') or value.get('alpha_target')!=.05:
        raise ValueError('valid predeclared calibration required')
    if value.get('science_signature')!=science_signature():
        raise ValueError('calibration numerical implementation/version mismatch')
    if len(value.get('rows',[]))!=20 or value['gate']['sample_count']!=20:
        raise ValueError('all 20 calibration replicates required')
    return value['gate']


def execute(label, *, arm='deterministic', gate=None, seed=51000, sigma=.5,
            standard_tier_confirmed=False, worker=None, adapter=None):
    budget=Budget()
    if arm=='live' and adapter is None:
        try:
            adapter=MuseAdapter.from_environment(budget=budget,standard_tier_confirmed=standard_tier_confirmed)
        except NotAuthorized:
            return {'status':'NOT_RUN','source':'LIVE_MUSE','actual_api_requests':0,
                    'successful_requests':0,'failed_requests':0,'reason':'local API authorization or Standard tier unavailable'}
    if adapter is None:
        adapter=MockAdapter() if arm=='mock' else DeterministicAdapter()
    env=case(label,seed=seed,sigma=sigma)
    own=worker is None
    if own:
        from realign.tools.sandbox import IsolationUnavailable
        try:
            worker=WorkerClient(timeout_s=budget.worker_timeout_s)
        except IsolationUnavailable:
            if hasattr(adapter,'close'):
                adapter.close()
            return {'status':'FAILED','source':adapter.source,'outcome':'ABSTAIN',
                    'error_type':'IsolationUnavailable','actual_api_requests':0,
                    'reason':'Required OS isolation unavailable; no weaker fallback'}
    try:
        s=ScientificSession(worker,env.initial,NOMINAL,env.checks,budget=budget,gate=gate,
                            release_angles=env.allowed_release_angles)
        start=time.monotonic()
        result=Investigator(s,adapter,env).run()
        elapsed=time.monotonic()-start
        assert result['state_history'][-1]=='FREEZE' and AuditChain.verify(result['audit'])
        # No development trial exists until after the frozen result above.
        final=result['numerical_details']['model']
        development=env.development_after_freeze()
        error=None
        if final:
            p=parameters(final['params'])
            predict=predict_peg if p.peg else predict_free
            error=float(np.mean([np.mean(np.sum((predict(p,t)[t.observation.valid]-
                t.observation.xy_px[t.observation.valid])**2,axis=1)) for t in development]))
        result['post_freeze_evaluation']={'scope':'SYNTHETIC DISJOINT DEVELOPMENT; NEVER AN AGENT TOOL INPUT',
            'trial_ids':[t.trial_id for t in development],
            'trajectory_rmse_px':float(np.sqrt(error)) if error is not None else None}
        result['status']='COMPLETED'
        result['host_elapsed_s']=elapsed
        result['fixture_provenance']={'seed':seed,'noise_sd_px':sigma,'source':'SYNTHETIC_ONLY',
            'label_post_freeze_only':label}
        result['science_signature']=science_signature()
        return result
    finally:
        if hasattr(adapter,'close'):
            adapter.close()
        if own:
            worker.close()


def verify_replay(trace):
    """Audit/state replay, explicitly not recomputation of numerical fits."""
    try:
        return _verify_replay(trace)
    except (KeyError,TypeError,ValueError):
        return False


def _verify_replay(trace):
    if trace.get('status')!='COMPLETED':
        return False
    if not AuditChain.verify(trace['audit']) or not AuditChain.verify(trace['numerical_audit']['events']):
        return False
    from realign.agent.investigator import TRANSITIONS
    history=trace['state_history']
    if not history or history[0]!='OBSERVE' or history[-1]!='FREEZE':
        return False
    if any(b not in TRANSITIONS[a] for a,b in zip(history,history[1:])):
        return False
    if history!=['OBSERVE']+[e['payload']['to'] for e in trace['audit'] if e['kind']=='TRANSITION']:
        return False
    frozen=dict(trace['freeze']); expected=frozen.pop('freeze_sha256')
    numerical=trace['numerical_audit']
    if not trace['audit'] or trace['audit'][-1]['kind']!='FREEZE' or trace['audit'][-1]['payload']!=trace['freeze']:
        return False
    if numerical['head']!=(numerical['events'][-1]['hash'] if numerical['events'] else '0'*64):
        return False
    if frozen['numerical_audit_head']!=numerical['head']:
        return False
    if any(digest(s['context'])!=s['context_sha256'] for s in trace['steps']):
        return False
    return digest(frozen)==expected and trace['audit_head']==trace['audit'][-1]['hash']


def write_run(path, result):
    path=Path(path); path.parent.mkdir(parents=True,exist_ok=True)
    path.write_bytes(canonical(result))


def format_summary(result):
    if result['status']!='COMPLETED':
        return result['status']
    f=result['freeze']
    return f"{result['source']}: {f['outcome']}; rounds={f['rounds']}; experiments={f['experiments']}"

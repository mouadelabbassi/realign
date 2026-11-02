"""Build portable, observation-bound presentation artifacts without fitting."""
from pathlib import Path
from .evidence import EvidenceError,read_json
from .presentation import materialize
from .store import publish,write_json

ROOT=Path(__file__).resolve().parents[3]
CASES=(('off_vertical_peg','off-vertical'),('no_fault','nominal'),('parameter_mismatch','parameters'),
       ('vertical_peg','vertical'),('unexcited_peg','limited'),('measurement_problem','measurement'),('insufficient','insufficient'))


def live_verification(trace):
    if trace.get('status')!='COMPLETED':
        return {'status':trace.get('status','FAILED'),'successful_calls':trace.get('successful_requests',0),
            'failed_calls':trace.get('failed_requests',0),'checks':{},'blocker':trace.get('reason','No completed investigation')}
    from .evidence import validate_record
    checked=validate_record(trace,'LIVE_MUSE'); stats=checked['stats']; steps=trace['steps']
    checks={'structured_outputs':any(s['reply']['turn'] for s in steps),
        'scientific_tools':any(s['reply']['calls'] for s in steps),
        'multi_turn_tools':any(s['reply']['calls'] and i+1<len(steps) for i,s in enumerate(steps)),
        'two_rounds':trace['freeze']['rounds']==2,
        'experiment_received':trace['freeze']['experiments']>=1,
        'accepted_or_scientific_abstention':trace['freeze']['proposal_accepted'] is True,
        'audit_integrity':True,'request_budget':stats['actual_api_requests']<=24,
        'logical_budgets':trace['numerical_audit']['used']['fit_jobs']<=10 and trace['numerical_audit']['used']['tool_calls']<=24}
    return {'status':'PASS' if all(checks.values()) else 'PARTIAL','source':'LIVE_MUSE',
        'successful_calls':stats['successful_requests'],'failed_calls':stats['failed_requests'],
        'actual_api_requests':stats['actual_api_requests'],'input_tokens':stats['input_tokens'],
        'output_tokens':stats['output_tokens'],'api_latency_s':stats['api_latency_s'],'token_cost_usd':None,
        'outcome':trace['freeze']['outcome'],'accepted':trace['freeze']['proposal_accepted'],
        'checks':checks,'receipts':checked['receipts'],
        'execution_failures':[e['payload'] for e in trace['audit'] if e['kind']=='EXECUTION_FAILURE']}


def prepare_demo(output_dir=None,*,evidence_dir=None,include_mock=True,progress=None):
    output=Path(output_dir or ROOT/'artifacts/task05/demo')
    evidence=Path(evidence_dir or ROOT/'artifacts/task05'); evidence.mkdir(parents=True,exist_ok=True)
    bundles=[]
    for arm,policy in (('deterministic','DETERMINISTIC'),('mock','MOCK_POLICY')):
        if arm=='mock' and not include_mock:continue
        prefix='det' if arm=='deterministic' else 'mock'
        for label,suffix in CASES:
            path=ROOT/'artifacts/task04/traces'/f'{arm}_{label}.json'
            bundle=materialize(path,run_id=prefix+'-'+suffix,expected_policy=policy)
            bundles.append(bundle)
            if progress:progress('Bound recorded evidence: '+bundle['id'])
    live={'status':'NOT_RUN','successful_calls':0,'failed_calls':0,'actual_api_requests':0,
          'blocker':'No live investigation recording available; no mock substitution'}
    attempts=[]
    for path in sorted(evidence.glob('live_investigation_attempt_[0-9][0-9].json')):
        trace=read_json(path); result=live_verification(trace)
        result['artifact']=path.name; attempts.append(result)
        if trace.get('status')=='COMPLETED':
            bundle=materialize(path,run_id='live-'+path.stem[-2:],expected_policy='LIVE_MUSE')
            bundle['title']='Live Muse investigation · attempt '+path.stem[-2:]
            bundles.append(bundle)
        live=result
    live=dict(live,attempts=attempts)
    write_json(evidence/'live_meta_verification.json',live)
    external_paths=(evidence/'external_yellow_disc/external_verification.json',evidence/'external/external_verification.json')
    external=next((read_json(p) for p in external_paths if p.is_file()),{
        'status':'NOT_RUN','observation_source':'REAL_EXTERNAL','media_url':None,'track':None,
        'sam':{'status':'NOT_RUN','successful_calls':0,'failed_calls':0},
        'manual_review':{'status':'NOT_PROVIDED','rmse_px':None},'physical_comparison_available':False,
        'limitations':['No approved external tracking evidence prepared.']})
    status={'live_muse':live,'sam':external['sam'],'phone':{'status':'NOT_PROVIDED','source':'REAL_PHONE'},
        'limitations':['Synthetic investigations and external SAM tracking are separate evidence sources.',
                       'No controlled real-phone trial or blind structural discovery is demonstrated.',
                       'Measurement correction is required where flagged; it has not been applied or verified.']}
    store=publish(output,bundles,status,external)
    live_runs=[b for b in bundles if b['policy']=='LIVE_MUSE']
    deterministic=next(b for b in bundles if b['id']=='det-off-vertical')
    comparison={'scope':'MATCHED INITIAL SYNTHETIC OBSERVATIONS AND TOOL/SEARCH/EXPERIMENT BUDGETS; NO SUPERIORITY CLAIM',
        'deterministic':{'outcome':deterministic['decision']['outcome'],'prediction_rmse_px':deterministic['evaluation']['rmse_px'],
            'budget':deterministic['budget'],'experiments':int(bool(deterministic['experiment']['receipt']))},'live_attempts':[],'agentic_superiority_demonstrated':False}
    for b in live_runs:
        matched=(b['rounds'][0]['trial_refs']==deterministic['rounds'][0]['trial_refs'])
        comparison['live_attempts'].append({'id':b['id'],'matched_initial_observations':matched,
            'outcome':b['decision']['outcome'],'accepted':b['decision']['accepted'],
            'prediction_rmse_px':b['evaluation']['rmse_px'],'budget':b['budget'],'api':b['api'],
            'experiment_requested':b['experiment']['requested'],'experiment_received':bool(b['experiment']['receipt'])})
    write_json(evidence/'matched_live_comparison.json',comparison)
    return store

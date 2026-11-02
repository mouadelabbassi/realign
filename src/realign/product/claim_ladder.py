"""Per-domain evidence claims from pinned public artifacts; no scientific work."""
from pathlib import Path
from .evidence import EvidenceError,read_json,sha256_file

ROOT=Path(__file__).resolve().parents[3]
RESOURCES={'g1':'artifacts/g1_verification.json','b01':'artifacts/poc0_baselines.json',
 'b3':'artifacts/b3_baselines.json','matched':'artifacts/task05/matched_live_comparison.json',
 'muse':'artifacts/task05/demo/live-02.json','sam':'artifacts/task05/external_yellow_disc/external_verification.json',
 'fixed':'artifacts/task06/g5_positive_control/validation.json','randomized':'artifacts/task06/g5_demo/validation.json',
 'random_trace':'artifacts/task06/g5_demo/investigation.json'}

def post_mortem(artifacts):
    trace=artifacts.get('random_trace',{});report=artifacts.get('randomized',{})
    ref=trace.get('freeze',{}).get('model_ref')
    from realign.audit.chain import digest
    model=next((m for m in trace.get('numerical_details',{}).get('fitted_models',[]) if digest({'kind':'MODEL','value':m})==ref),None)
    return {'scope':'POST_MORTEM; ARCHIVED_EXPLORATION_DIAGNOSTICS_ONLY','classification':'UNDETERMINED',
        'original_verdict':report.get('independent_verdict'),'identifiability':model['fit']['identifiability'] if model else None,
        'profile_uncertainty_range':'NOT_RUN','credible_interval':'NOT_AVAILABLE',
        'precise_geometry_claim_allowed':False,'new_predictions':0,'fit_calls':0,'heldout_evaluations':0,
        'limitation':'Local full rank does not prove precise geometry or uniqueness. No consumed heldout is rescored or tuned.'}

def agent_value(matched):
    accepted=[r for r in matched.get('live_attempts',[]) if r.get('accepted') and r.get('matched_initial_observations')]
    if not accepted:return {'status':'UNAVAILABLE','label':'Matched comparison unavailable','billed_cost_status':'UNVERIFIED'}
    live=accepted[-1];det=matched['deterministic'];difference=live['prediction_rmse_px']-det['prediction_rmse_px']
    # Fixed descriptive display rule, not a retrospective significance test or
    # a prospective registration made before these historical results existed.
    return {'status':'DESCRIPTIVE_MATCHED_CASE','label':'No predictive advantage demonstrated',
        'difference_px':difference,'equality_tolerance_px':1e-9,'within_display_tolerance':abs(difference)<=1e-9,
        'scope':matched['scope'],'live_run_id':live['id'],'live_rmse_px':live['prediction_rmse_px'],
        'deterministic_rmse_px':det['prediction_rmse_px'],'live_fit_jobs':live['budget']['fit_jobs'],
        'deterministic_fit_jobs':det['budget']['fit_jobs'],'billed_cost_status':'UNVERIFIED',
        'limitation':'One recorded matched synthetic case; no causal, statistical or general superiority inference.'}

def compute_ladder(artifacts):
    g1=artifacts.get('g1',{}).get('passed') is True
    baseline=g1 and all(artifacts.get(k,{}).get('acceptance_passed') is True for k in ('b01','b3'))
    muse=artifacts.get('muse',{})
    live=baseline and muse.get('policy')=='LIVE_MUSE' and muse.get('decision',{}).get('accepted') is True and muse.get('api',{}).get('actual_api_requests',0)>0
    sam=artifacts.get('sam',{})
    tracking=sam.get('observation_source')=='REAL_EXTERNAL' and sam.get('track') is not None and sam.get('sam',{}).get('source')=='REAL_API'
    # Some historic reports call the receipt source REAL_API inside receipt.
    tracking=tracking or (sam.get('observation_source')=='REAL_EXTERNAL' and sam.get('track') is not None and
        sam.get('sam',{}).get('receipt',{}).get('source')=='REAL_API')
    manual=artifacts.get('manual',{})
    human=tracking and manual.get('status')=='VALIDATED_MANUAL_REFERENCES' and manual.get('attestation_status')=='SELF_DECLARED_INDEPENDENCE' and manual.get('reference_set_version')==2 and manual.get('review_locked') is True
    ceiling='C3b' if human else 'C3a' if tracking else 'C2' if live else 'C1' if baseline else 'C0' if g1 else 'UNVERIFIED'
    controls={k:artifacts[k]['independent_verdict'] for k in ('fixed','randomized') if k in artifacts}
    return {'overall_claim_ceiling':ceiling,'branches':{
        'SYNTHETIC':{'physics':g1,'classical_baselines':bool(baseline),'live_muse':bool(live),
                     'g5_outcomes':controls,'g5_is_physical_validation':False},
        'REAL_EXTERNAL':{'sam_tracking':bool(tracking),'human_accuracy': 'VALIDATED' if human else 'NOT_VALIDATED',
                         'timing_basis':'PTS_ONLY','scale':'UNKNOWN'},
        'REAL_PHONE':{'status':'BLOCKED_INPUTS','physical_G2':'NOT_PASSED','physical_G5':'NOT_PASSED'}},
        'next_unmet_prerequisites':['Independent human references including early tracking failures',
            'Controlled recordings, measured calibration and verified physical timing',
            'Independent custodian and fresh real heldouts'],
        'negative_results':[{'kind':'SYNTHETIC_G5_WORKFLOW','status':controls.get('randomized','MISSING')},
                            {'kind':'SYNTHETIC_AGENT_COMPARISON','status':agent_value(artifacts.get('matched',{}))['label']} ]}

def release_evidence(root=ROOT):
    root=Path(root);path=root/'artifacts/release/evidence_manifest.json';items={};issues=[]
    if not path.is_file():return {'ladder':compute_ladder({}),'artifacts':{},'issues':['Release evidence manifest missing']}
    manifest=read_json(path)
    for key,entry in manifest['entries'].items():
        if key not in RESOURCES or entry['file']!=RESOURCES[key]:raise EvidenceError('unapproved release evidence resource')
        p=root/entry['file']
        if not p.is_file() or sha256_file(p)!=entry['sha256']:
            issues.append('Missing or changed: '+entry['file']);continue
        value=read_json(p)
        if key in ('fixed','randomized'):
            from .closure import validate_independent_report
            validate_independent_report(value)
        items[key]=value
    release_root=root/'artifacts/release'
    if (release_root/'closure_manifest.json').is_file():
        from .closure import load_closure
        items['manual']=load_closure(release_root)['manual']
    return {'ladder':compute_ladder(items),'artifacts':items,'issues':issues}

def api_header(value,endpoint,ladder):
    domain=value.get('observation_source')
    run=endpoint.startswith('/api/runs/')
    aggregate=domain not in ('SYNTHETIC','REAL_EXTERNAL','REAL_PHONE')
    return {'schema_version':'1.0','source_domain':'AGGREGATE' if aggregate else domain,
        'source_domains':['SYNTHETIC','REAL_EXTERNAL','REAL_PHONE'] if aggregate else [domain],
        'policy':value.get('policy','AGGREGATE' if aggregate else 'RECORDED_EVIDENCE'),
        'run_id':value.get('id',endpoint.rsplit('/',1)[-1] or 'response'),
        'stage':'POST_FREEZE_REPLAY' if run else 'PUBLIC_EVIDENCE_REPLAY',
        'ladder_level':ladder['overall_claim_ceiling']}

def release_view(root=ROOT,*,review_root=None):
    evidence=release_evidence(root);a=evidence['artifacts']
    from .closure import load_closure
    from realign.physical.admission import calibration_grade
    review=load_closure(review_root or Path(root)/'artifacts/release')
    return {'ladder':evidence['ladder'],'issues':evidence['issues'],'agent_value':agent_value(a.get('matched',{})),
        'review':review,
        'calibration_grades':{d:calibration_grade({'source_kind':d}) for d in ('REAL_EXTERNAL','REAL_PHONE')},
        'historical_g5':{k:a[k] for k in ('fixed','randomized') if k in a},
        'post_mortem':post_mortem(a),
        'execution':'READ_ONLY_REPLAY','new_meta_calls':0,'billed_cost_status':'UNVERIFIED',
        'run_locally':{'replay':'python scripts/run_realign.py --port 8766 --no-browser',
            'physical':'python scripts/investigate_recordings.py configs/phone_investigation.example.json',
            'review':'python scripts/review_external.py evaluate --annotations data/reviews/external_independent.json',
            'live_opt_in':'python scripts/verify_task05.py --run-live --standard-tier-confirmed --env-file .env',
            'warning':'Paid model execution is CLI-only and requires separate explicit authorization. No browser endpoint starts it.'}}

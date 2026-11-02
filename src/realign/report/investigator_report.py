"""Matched deterministic/mock investigations and post-freeze scientific evaluation."""
import gzip
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from scipy.stats import beta
from realign.audit.chain import canonical, digest
from realign.tools.sandbox import WorkerClient
from realign.agent.adapters import ReplayAdapter
from .investigator_run import execute,load_gate,write_run,verify_replay,science_signature,ROOT
from .investigator_calibration import run_calibration

CASES=('no_fault','parameter_mismatch','vertical_peg','off_vertical_peg',
       'unexcited_peg','measurement_problem','insufficient')
EXPECTED={'no_fault':'KEEP_UNCHANGED','parameter_mismatch':'CALIBRATE_PARAMETERS',
          'vertical_peg':'REPAIR_STRUCTURE','off_vertical_peg':'REPAIR_STRUCTURE',
          'unexcited_peg':'ABSTAIN','measurement_problem':'CORRECT_MEASUREMENT','insufficient':'ABSTAIN'}


def interval(k,n):
    if not n:
        return None
    return [float(beta.ppf(.025,k,n-k+1)) if k else 0.,
            float(beta.ppf(.975,k+1,n-k)) if k<n else 1.]


def row(label,result):
    if result.get('status')!='COMPLETED':
        return {'case':label,'status':result.get('status'),'outcome':'ABSTAIN','correct_supported_decision':False,
                'predictive_rmse_px':None,'failed':result.get('status')=='FAILED',
                'actual_api_requests':result.get('actual_api_requests'),
                'successful_requests':result.get('successful_requests'),'failed_requests':result.get('failed_requests')}
    f=result['freeze']; stats=result['adapter_stats']
    return {'case':label,'status':result['status'],'outcome':f['outcome'],
            'proposal_accepted':f['proposal_accepted'],'correct_supported_decision':f['outcome']==EXPECTED[label],
            'experiments':f['experiments'],'experiment_requests':f['experiment_requests'],'rounds':f['rounds'],
            'predictive_rmse_px':result['post_freeze_evaluation']['trajectory_rmse_px'],
            'tool_calls':result['numerical_audit']['used']['tool_calls'],
            'fit_jobs':result['numerical_audit']['used']['fit_jobs'],
            'api_latency_s':stats.get('api_latency_s'),'input_tokens':stats.get('input_tokens'),
            'actual_api_requests':stats.get('actual_api_requests'),
            'successful_requests':stats.get('successful_requests'),'failed_requests':stats.get('failed_requests'),
            'output_tokens':stats.get('output_tokens'),'token_cost_usd':stats.get('token_cost_usd'),
            'freeze_sha256':f['freeze_sha256'],'failed':False,'reasons':f['reasons']}


def _safe_execute(label, **kwargs):
    try:
        return execute(label,**kwargs)
    except Exception as exc:
        return {'status':'FAILED','outcome':'ABSTAIN','error_type':type(exc).__name__,
                'scope':'No unsupported backend fallback; failed attempt retained'}


def _runs(specs, arm, gate, progress, standard_tier_confirmed=False):
    # Independent study replicates: one investigator/session in each, no shared
    # evidence or extra compute within any investigation. Live runs stay serial.
    with WorkerClient(timeout_s=90):
        pass  # Warm immutable runtime before concurrent read-only launches.
    with ThreadPoolExecutor(max_workers=1 if arm=='live' else 4) as pool:
        pending={pool.submit(_safe_execute,s['label'],arm=arm,gate=gate,
                    seed=s['seed'],sigma=s['sigma'],
                    standard_tier_confirmed=standard_tier_confirmed):(i,s)
                 for i,s in enumerate(specs)}
        for future in as_completed(pending):
            i,s=pending[future]; result=future.result()
            if progress:
                progress(arm+' completed: '+s['label']+' seed='+str(s['seed']))
            yield i,s,result


def build_report(output_dir, *, calibrate=False, progress=None, run_live=False,
                 standard_tier_confirmed=False):
    output=Path(output_dir); output.mkdir(parents=True,exist_ok=True)
    cal_path=output/'null_calibration.json'
    if calibrate:
        run_calibration(output,progress=progress)
    gate=load_gate(cal_path)
    cal=json.loads(cal_path.read_text(encoding='utf-8'))
    benchmark={}; traces={}
    arms=('deterministic','mock','live') if run_live else ('deterministic','mock')
    for arm in arms:
        collected={}
        specs=[{'label':label,'seed':51000+100*i,'sigma':.5} for i,label in enumerate(CASES)]
        for i,s,r in _runs(specs,arm,gate,progress,standard_tier_confirmed):
            label=s['label']
            write_run(output/'traces'/f'{arm}_{label}.json',r)
            collected[i]=row(label,r); traces[(arm,label)]=r
        rows=[collected[i] for i in range(len(specs))]
        benchmark[arm]={'source':{'deterministic':'DETERMINISTIC','mock':'MOCK_POLICY','live':'LIVE_MUSE'}[arm],
            'rows':rows,'correct_supported_decisions':sum(x['correct_supported_decision'] for x in rows),
            'abstentions':sum(x['outcome']=='ABSTAIN' for x in rows),
            'false_repairs':sum(x['outcome']=='REPAIR_STRUCTURE' for x in rows if x['case'] in ('no_fault','parameter_mismatch')),
            'completed_runs':sum(x['status']=='COMPLETED' for x in rows),
            'not_run_runs':sum(x['status']=='NOT_RUN' for x in rows),
            'failed_runs':sum(x['failed'] for x in rows)}
    # These seeds are disjoint from the calibration seeds. Labels are consulted
    # only here, after every individual investigation has frozen.
    specs=[]
    for family_index,label in enumerate(('no_fault','parameter_mismatch','vertical_peg','off_vertical_peg')):
        seeds=(41000,42000) if label in ('no_fault','parameter_mismatch') else (43000,)
        for seed in seeds:
            for sigma in (.5,1.5):
                actual_seed=seed+1000000*(family_index+1)+(200000 if sigma==1.5 else 0)
                specs.append({'label':label,'seed':actual_seed,'base_seed':seed,'sigma':sigma})
    collected={}
    for i,s,r in _runs(specs,'deterministic',gate,progress):
        write_run(output/'traces'/f"validation_{s['label']}_{s['seed']}_{s['sigma']}.json",r)
        entry=row(s['label'],r); entry.update(seed=s['seed'],base_seed=s['base_seed'],noise_sd_px=s['sigma'])
        collected[i]=entry
    validation=[collected[i] for i in range(len(specs))]
    negatives=[x for x in validation if x['case'] in ('no_fault','parameter_mismatch')]
    positives=[x for x in validation if x['case'] in ('vertical_peg','off_vertical_peg')]
    fp=sum(x['outcome']=='REPAIR_STRUCTURE' for x in negatives)
    tp=sum(x['outcome']=='REPAIR_STRUCTURE' for x in positives)
    agreement=all(a.get('freeze_sha256')==b.get('freeze_sha256') for a,b in zip(
                  benchmark['deterministic']['rows'],benchmark['mock']['rows']))
    original=traces[('deterministic','off_vertical_peg')]
    replay=None
    if original.get('status')=='COMPLETED':
        if progress:
            progress('Fresh numerical replay: off_vertical_peg')
        try:
            replay=_safe_execute('off_vertical_peg',gate=gate,seed=51300,adapter=ReplayAdapter(original))
        except Exception as exc:
            replay={'status':'FAILED','outcome':'ABSTAIN','error_type':type(exc).__name__}
        write_run(output/'replay.json',replay)
    replay_ok=bool(replay and replay.get('status')=='COMPLETED' and verify_replay(replay) and
                   replay['freeze']['freeze_sha256']==original['freeze']['freeze_sha256'])
    live=traces.get(('live','off_vertical_peg')) if run_live else {
        'status':'NOT_RUN','source':'LIVE_MUSE','actual_api_requests':0,
        'successful_requests':0,'failed_requests':0,'reason':'Live matched benchmark not requested'}
    write_run(output/'live_meta_status.json',live)
    prior={}
    prior_path=ROOT/'artifacts/meta_smoke.json'
    if prior_path.exists():
        p=json.loads(prior_path.read_text(encoding='utf-8'))
        prior={'scope':'PREEXISTING LOCAL CAPABILITY REPORT; not this investigator run',
               'report_sha256':digest(p),'status':p.get('status'),'successful_calls':p.get('successful_calls'),
               'failed_calls':p.get('failed_calls'),'checks':p.get('checks')}
    result={'scope':'SYNTHETIC SCIENTIFIC INVESTIGATIONS; MOCK IS NOT MUSE EVIDENCE',
        'science_signature':science_signature(),'calibration':{'alpha_target':.05,'replicates':20,
            'threshold':cal['threshold'],'failed_comparisons':gate['failed_comparisons'],'science_signature':cal['science_signature']},
        'benchmark':benchmark,'offline_batch_concurrency':4,'mock_deterministic_freeze_agreement':agreement,
        'post_calibration_validation':{'rows':validation,'negative_count':len(negatives),'positive_count':len(positives),
            'false_repairs':fp,'specificity':(len(negatives)-fp)/len(negatives),
            'specificity_95_interval':interval(len(negatives)-fp,len(negatives)),
            'sensitivity':tp/len(positives),'sensitivity_95_interval':interval(tp,len(positives)),
            'abstentions':sum(x['outcome']=='ABSTAIN' for x in validation),
            'failed_runs':sum(x['failed'] for x in validation)},
        'replay_matches':replay_ok,'live_investigator':live,'prior_capability_report':prior,
        'full_G2_passed':False,'full_G3_passed':False,'agentic_superiority_demonstrated':False}
    checks=[
        {'name':'all seven deterministic investigations complete','passed':benchmark['deterministic']['completed_runs']==7},
        {'name':'all seven mock investigations complete','passed':benchmark['mock']['completed_runs']==7},
        {'name':'off-vertical investigation actually requests and receives a second round','passed':
            original.get('status')=='COMPLETED' and original['freeze']['rounds']==2 and original['freeze']['experiments']==1},
        {'name':'state/evidence replay reproduces the frozen numerical decision','passed':replay_ok},
        {'name':'mock and deterministic policies have matched frozen outcomes','passed':agreement},
        {'name':'no false structural repairs in independent null validation','passed':fp==0},
        {'name':'at least one supported predefined structural selection','passed':tp>0},
        {'name':'measurement problem yields a measurement action','passed':
            benchmark['deterministic']['rows'][5]['outcome']=='CORRECT_MEASUREMENT'},
        {'name':'limited/insufficient evidence does not force structural repair','passed':
            all(benchmark['deterministic']['rows'][i]['outcome']=='ABSTAIN' for i in (4,6))},
    ]
    result['checks']=checks; result['offline_acceptance_passed']=all(x['passed'] for x in checks)
    (output/'investigator_results.json').write_bytes(canonical(result))
    (output/'INVESTIGATOR_REPORT.md').write_text(markdown(result),encoding='utf-8')
    return result


def markdown(r):
    lines=['# First executable investigator evidence','',
           '**SYNTHETIC ONLY. Deterministic and mock results are separate from live Muse.**','',
           '| Case | Deterministic outcome | Mock outcome | Experiments | Post-freeze prediction RMS px |',
           '|---|---|---|---:|---:|']
    for a,b in zip(r['benchmark']['deterministic']['rows'],r['benchmark']['mock']['rows']):
        error='unavailable' if a.get('predictive_rmse_px') is None else f"{a['predictive_rmse_px']:.5f}"
        lines.append(f"| {a['case']} | {a['outcome']} | {b['outcome']} | {a.get('experiments','unavailable')} | {error} |")
    v=r['post_calibration_validation']
    lines+=['','## Scientific acceptance and ambiguity','',
        f"Null calibration: {r['calibration']['replicates']} predeclared independent synthetic datasets, "
        f"two noise levels and no-fault/parameter-fault strata. Target false repair rate 0.05. Threshold {r['calibration']['threshold']}.",
        f"Independent validation: {v['false_repairs']}/{v['negative_count']} false repairs; "
        f"specificity {v['specificity']:.4f}, 95% Clopper-Pearson interval {v['specificity_95_interval']}.",
        f"Sensitivity {v['sensitivity']:.4f} on {v['positive_count']} excited-peg cases, "
        f"95% interval {v['sensitivity_95_interval']}; abstentions {v['abstentions']}; failed runs {v['failed_runs']}.",'',
        'The empirical tail rank uses (1 + number of null statistics unavailable or at least as large)/(N + 1). '
        'The threshold is the maximum of all 20 null replicate scores, floored at zero. '
        'Unavailable null fits count as worst-case exceedances; at N=20, any such failure blocks 5% repair acceptance. '
        'One formal test is permitted only after the registered four-trial design (0.2, 0.32, 0.65, 0.65 rad; 1.6 s; 20 Hz; IID assumed SD 0.5 or 1.5 px). '
        'The statistic is the minimum of the two whole-trial-fold improvements normalized by localization MSE floor. '
        'Off-protocol designs, missing data, other noise models and real observations remain uncalibrated.', '',
        'The 5% figure is a predefined pilot target, not a proven uniform false-repair guarantee. '
        'Twenty calibration datasets and a small validation set provide limited tail/power evidence. '
        'Calibration null parameter mismatches cover a finite grid; the 0.76 m benchmark is an additional stress case. '
        'The wide validation intervals must not be hidden.', '',
        'KEEP_UNCHANGED means predictive adequacy inside the tested operating envelope. It does not rule out an inactive peg or another observationally equivalent mechanism. '
        'The limited-angle unexcited case cannot cover the operating envelope and abstains. '
        'REPAIR_STRUCTURE accepts the existing predefined peg model for prediction; it is not open-ended equation discovery or proof of causal uniqueness. '
        'All causal-identification flags remain false. Independent geometry/interventions and full G2/G3 are pending.','',
        '## Experiment planning','',
        'Release, repeat, stationary-reference and camera-calibration actions form a closed discriminated union. '
        'Only allowlisted bounded candidates can be requested. Physical execution here is a synthetic replay environment, not a robot or a live rig. '
        'Release/repeat score is the 75th percentile of noise-normalized trajectory separation over near-optimal multistart parameter alternatives. '
        'The reported ensemble interquartile spread is a heuristic uncertainty diagnostic, not a calibrated posterior. '
        'Every sampled candidate must integrate without unsupported dynamics. Reference checks use fixed, declared quality-trigger priorities. '
        'Expected information gain remains null; no Bayesian information gains are fabricated.','',
        '## Matched comparison and Meta status','',
        'Both offline arms receive the same observations, candidate catalog, numerical tools and logical budgets. '
        'The mock adapter uses the deterministic policy through the production interface to verify plumbing. '
        'Matching mock outcomes are not evidence that Muse reasons successfully or outperforms a planner. '
        'Each trace records requested/completed experiments, fit jobs, tool calls and post-freeze prediction error. '
        'API latency, token use and monetary cost remain unavailable for offline arms; token prices are not guessed.','',
        'Live investigator status: '+r['live_investigator']['status']+'. '
        'No end-to-end live Muse investigation is claimed. A preexisting capability report, if present, is recorded separately with its hash and scope. '
        'It does not validate the expanded agent schemas or full investigation.','',
        '## Checks','']
    lines+=['- '+('PASS' if x['passed'] else 'FAIL')+': '+x['name'] for x in r['checks']]
    lines+=['','Source/numerical signature: '+r['science_signature']+'.',
        'Reproduce with python scripts/verify_investigator.py --calibrate. Exact traces, all failed fits, '
        'calibration restarts and post-freeze validation records accompany the report.','']
    return '\n'.join(lines)

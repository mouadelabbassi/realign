"""Registered null calibration with independent, individually bounded workers."""
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import replace
import gzip
from pathlib import Path
import platform
import numpy as np
import scipy
from realign.audit.chain import canonical
from realign.contracts.investigation import Budget, Release
from realign.tools.client import ScientificSession, candidate
from realign.tools.sandbox import WorkerClient
from realign.synth.investigation_fixtures import NOMINAL, SyntheticEnvironment

SEEDS=(31000,32000,33000,34000,35000)
SIGMAS=(.5,1.5)


def _replicate(index, parameter_fault, seed, sigma):
    budget=Budget()
    p=NOMINAL if not parameter_fault else replace(NOMINAL,
        length_m=.75+.002*(seed//1000%3),gamma_per_s=.10+.02*(seed//1000%2),
        quadratic_drag_per_m=.035+.005*(seed//1000%3))
    actual_seed=seed+(100000 if parameter_fault else 0)+(200000 if sigma==1.5 else 0)
    env=SyntheticEnvironment(p,seed=actual_seed,sigma=sigma)
    more=env.perform(candidate(Release(release_angle_rad=.65)).model_dump(mode='json'))
    row={'replicate':index,'seed':actual_seed,'noise_sd_px':sigma,
         'null_kind':'parameter_fault' if parameter_fault else 'no_fault',
         'statistic':None,'comparison':None,'observation_refs':[],'budget_used':None}
    try:
        with WorkerClient(timeout_s=budget.worker_timeout_s) as worker:
            session=ScientificSession(worker,env.initial+more['trials'],NOMINAL,env.checks,budget=budget)
            fits=[session.fit(f) for f in ('FREE','PEG_ONE_SIDE')]
            comparison=session.compare() if all(f.get('fitted_model_ref') for f in fits) else None
            audit=session.audit(); frozen=session.freeze()
            row.update(statistic=comparison.get('statistic') if comparison else None,
                comparison=comparison,observation_refs=list(session.trial_refs),budget_used=audit['used'])
            details={'replicate':index,'fits':frozen['fitted_models'],
                     'comparisons':frozen['comparisons'],'audit':audit}
            return row,details,session.protocol_ref,session.budget_ref
    except Exception as exc:
        row['error_type']=type(exc).__name__
        return row,{'replicate':index,'error_type':type(exc).__name__},None,None


def run_calibration(output_dir, *, progress=None):
    output=Path(output_dir); output.mkdir(parents=True,exist_ok=True)
    # Prepare the immutable runtime once before concurrent read-only launches.
    with WorkerClient(timeout_s=90) as worker:
        isolation=worker.isolation; isolation_probe=worker.probe
    specs=[(fault,seed,sigma) for fault in (False,True) for seed in SEEDS for sigma in SIGMAS]
    completed={}
    with ThreadPoolExecutor(max_workers=4) as pool:
        futures={pool.submit(_replicate,i,*spec):i for i,spec in enumerate(specs)}
        for future in as_completed(futures):
            index=futures[future]; completed[index]=future.result()
            row=completed[index][0]
            checkpoint={'valid':False,'scope':'INCOMPLETE CALIBRATION; NOT A GATE',
                        'completed':len(completed),'planned':20,
                        'rows':[completed[i][0] for i in sorted(completed)]}
            (output/'null_calibration_progress.json').write_bytes(canonical(checkpoint))
            if progress:
                progress('Null replicate '+str(len(completed))+'/20 (index '+str(index)+'): '+str(row['statistic']))
    rows=[completed[i][0] for i in range(20)]
    details=[completed[i][1] for i in range(20)]
    refs={(x[2],x[3]) for x in completed.values() if x[2] is not None}
    if len(refs)!=1:
        raise ValueError('calibration protocol/budget mismatch or no evaluable session')
    protocol_ref,budget_ref=next(iter(refs))
    scores=[r['statistic'] for r in rows]
    valid=sum(x is not None for x in scores)>=16
    threshold=max(0.,max(x for x in scores if x is not None)) if valid else None
    gate={'protocol_ref':protocol_ref,'budget_ref':budget_ref,'scores':scores,
          'sample_count':20,'failed_comparisons':sum(x is None for x in scores),
          'scope':'SYNTHETIC_REGISTERED_PREDICTIVE_MODEL_COMPARISON'}
    from .investigator_run import science_signature
    result={'scope':'SYNTHETIC NULL CALIBRATION ONLY; no Meta or real measurement evidence',
        'valid':valid,'alpha_target':.05,'threshold':threshold,'gate':gate,'rows':rows,
        'science_signature':science_signature(),'isolation':isolation,'isolation_probe':isolation_probe,
        'concurrency':4,'versions':{'python':platform.python_version(),'numpy':np.__version__,'scipy':scipy.__version__},
        'protocol_note':'One formal comparison after four registered exploration trials; two whole-trial folds. Unavailable null results count as worst-case tail exceedances. The rank is not a universal guarantee outside this pilot population.'}
    (output/'null_calibration.json').write_bytes(canonical(result))
    (output/'null_calibration_details.json.gz').write_bytes(gzip.compress(canonical(details),mtime=0))
    return result

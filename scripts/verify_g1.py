from __future__ import annotations
import json
import time
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
import numpy as np
from realign.physics import (PendulumParams, PegParams, simulate,
                             energy_per_mass, period_exact, vertical_peg_period)

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT / 'artifacts'
OUT.mkdir(exist_ok=True)


def main():
    rng=np.random.default_rng(20261031)
    t=np.linspace(0,5.0,1201)
    attempts=250
    failures=[]
    max_energy=0.0
    max_cont=0.0
    max_speed=0.0
    event_count=0
    begin=time.monotonic()
    for i in range(attempts):
        L=float(rng.uniform(.58,.90))
        r=float(rng.uniform(.06,min(.22,.35*L)))
        phi=float(rng.uniform(-.18,.18))
        theta=float(rng.uniform(.38,.70))
        p=PendulumParams(L, peg=PegParams(r,phi,contact_side=-1))
        try:
            out=simulate(p,theta,0,t)
            E=energy_per_mass(p,out)
            e=float(np.max(np.abs(E-E[0])))
            max_energy=max(max_energy,e)
            for ev in out.events:
                event_count+=1
                c=float(np.linalg.norm(np.array(ev.xy_pre_m)-ev.xy_post_m))
                v=abs(ev.speed_post_mps-ev.speed_pre_mps)
                max_cont=max(max_cont,c)
                max_speed=max(max_speed,v)
            if e>2e-7 or len(out.events)==0:
                failures.append({'case':i, 'error':'energy threshold or no contact','energy':e,'events':len(out.events)})
        except Exception as exc:
            failures.append({'case':i,'error':type(exc).__name__+': '+str(exc)})
    p=PendulumParams(.72,peg=PegParams(.14,0))
    out=simulate(p,.44,0,np.linspace(0,13,10001))
    starts=[ev.time_s for ev in out.events if ev.to_mode=='contact']
    period_ref=vertical_peg_period(.72,.14,.44)
    period_err=float(max(abs((np.diff(starts)-period_ref)))) if len(starts)>1 else None
    result={
        'scope':'G1 synthetic numerical verification only; not real experiments or Meta API validation',
        'seed':20261031,
        'randomized_cases':attempts,
        'case_failures':len(failures),
        'failure_examples':failures[:15],
        'total_mode_transitions':event_count,
        'max_absolute_energy_drift_j_per_kg':max_energy,
        'max_position_jump_m':max_cont,
        'max_speed_jump_m_per_s':max_speed,
        'vertical_peg_period_reference_s':period_ref,
        'vertical_peg_period_abs_error_s':None if period_err is None else float(period_err),
        'elapsed_seconds':round(time.monotonic()-begin,3),
        'passed':bool(len(failures)==0 and (period_err is not None and period_err<2e-7))
    }
    (OUT/'g1_verification.json').write_text(json.dumps(result, indent=2),encoding='utf-8')
    report=f'''# REALIGN G1 — Physics Verification Report

**Status:** {'PASS' if result['passed'] else 'FAIL'} (tested synthetic physics only)

## Evidence

| Check | Result |
|---|---:|
| Randomized ideal peg configurations | {attempts} |
| Failures | {len(failures)} |
| Total contact/free transitions | {event_count} |
| Maximum absolute energy drift, J/kg | {max_energy:.3e} |
| Maximum Cartesian position jump at contact, m | {max_cont:.3e} |
| Maximum Cartesian speed jump (lossless), m/s | {max_speed:.3e} |
| Vertical peg period error against elliptic-integral oracle, s | {period_err if period_err is not None else 'n/a'} |

## Assumptions

- Point-mass bob, inextensible string, one planar degree of freedom.
- Point-like, fixed peg; a single designated wrapped side (not contact on both sides).
- Contact transition is ideal and lossless for this randomized suite.
- String remains taut; unsupported slack conditions cause explicit failure.
- The initial release is on the free side of the peg.
- These simulations use *synthetic* states and do not prove experimental identifiability.

## Next gates

- **G2:** Obtain real SAM video masks, calibrated bob tracking and measured camera uncertainty.
- **G3:** Fit baseline models to separate exploration data and evaluate detectability.
- **Meta smoke test:** Requires a local `MODEL_API_KEY`; it has NOT been executed here.

Reproduce with `python scripts/verify_g1.py` from the repository root after installing the package.
'''
    (OUT/'G1_REPORT.md').write_text(report,encoding='utf-8')
    # Self-contained CSV comparisons: conceptual discrepancy, not a fitted repair.
    t2=np.linspace(0,6,601)
    truth=simulate(PendulumParams(.72,peg=PegParams(.14,0)),.44,0,t2)
    initial=simulate(PendulumParams(.72),.44,0,t2)
    np.savetxt(OUT/'synthetic_trajectory_comparison.csv',
               np.column_stack([t2,truth.xy_m,initial.xy_m,np.linalg.norm(truth.xy_m-initial.xy_m,axis=1)]),
               delimiter=',',comments='',header='time_s,peg_true_x_m,peg_true_y_m,original_x_m,original_y_m,original_error_m')
    try:
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        fig,ax=plt.subplots(2,1,figsize=(10,7),sharex=True,constrained_layout=True)
        ax[0].plot(t2,truth.xy_m[:,0],label='Synthetic contact-mode reference')
        ax[0].plot(t2,initial.xy_m[:,0],label='Original fixed-pivot model',ls='--')
        ax[0].set_ylabel('Horizontal bob position (m)');ax[0].legend()
        ax[1].plot(t2,np.linalg.norm(truth.xy_m-initial.xy_m,axis=1))
        ax[1].set_ylabel('Position discrepancy (m)');ax[1].set_xlabel('Time (s)')
        fig.suptitle('REALIGN POC-0: synthetic structural discrepancy (NOT real video)')
        fig.savefig(OUT/'synthetic_discrepancy.png',dpi=155)
        plt.close(fig)
    except ImportError:
        pass
    print(json.dumps({k:v for k,v in result.items() if k!='failure_examples'}, indent=2))
    if not result['passed']:
        raise SystemExit(1)


if __name__=='__main__': main()

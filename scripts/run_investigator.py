"""Execute the bounded investigator. Live mode never falls back to a mock."""
from realign.investigator_platform import delegate
delegate('run_investigator.py')
import argparse
from pathlib import Path
from realign.report.investigator_run import execute, load_gate, write_run, format_summary

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--mode',choices=('deterministic','mock','live'),default='deterministic')
    p.add_argument('--case',choices=('no_fault','parameter_mismatch','vertical_peg','off_vertical_peg',
                                   'unexcited_peg','measurement_problem','insufficient'),default='off_vertical_peg')
    p.add_argument('--gate',type=Path,default=Path('artifacts/task04/null_calibration.json'))
    p.add_argument('--uncalibrated',action='store_true',help='Run tools with repair acceptance unavailable')
    p.add_argument('--seed',type=int,default=51000)
    p.add_argument('--noise-sd-px',type=float,choices=(.5,1.5),default=.5)
    p.add_argument('--standard-tier-confirmed',action='store_true')
    p.add_argument('--output',type=Path,default=Path('artifacts/task04/investigation.json'))
    args=p.parse_args()
    import os
    if args.mode=='live' and (not os.environ.get('MODEL_API_KEY') or not args.standard_tier_confirmed):
        result=execute(args.case,arm='live',standard_tier_confirmed=args.standard_tier_confirmed)
    else:
        gate=None if args.uncalibrated else load_gate(args.gate)
        result=execute(args.case,arm=args.mode,gate=gate,seed=args.seed,sigma=args.noise_sd_px,
                       standard_tier_confirmed=args.standard_tier_confirmed)
    write_run(args.output,result)
    print(format_summary(result))
    raise SystemExit(2 if result['status']=='NOT_RUN' else 0 if result['status']=='COMPLETED' else 1)

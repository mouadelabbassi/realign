"""Reproduce all registered Task 04 investigation and comparison evidence."""
from realign.investigator_platform import delegate
delegate('verify_investigator.py')
import argparse
from pathlib import Path
from realign.report.investigator_report import build_report

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--calibrate',action='store_true',help='Recompute all 20 registered null datasets first')
    p.add_argument('--output-dir',type=Path,default=Path('artifacts/task04'))
    p.add_argument('--run-live',action='store_true',help='Also execute the matched seven-case live Muse arm')
    p.add_argument('--standard-tier-confirmed',action='store_true')
    args=p.parse_args()
    r=build_report(args.output_dir,calibrate=args.calibrate,progress=lambda s:print(s,flush=True),
                   run_live=args.run_live,standard_tier_confirmed=args.standard_tier_confirmed)
    for c in r['checks']:
        print(('PASS: ' if c['passed'] else 'FAIL: ')+c['name'])
    raise SystemExit(0 if r['offline_acceptance_passed'] else 1)

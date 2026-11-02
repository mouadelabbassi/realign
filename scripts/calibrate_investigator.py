"""Run all 20 predeclared synthetic null replicates in an isolated worker."""
from realign.investigator_platform import delegate
delegate('calibrate_investigator.py')
import argparse
from pathlib import Path
from realign.report.investigator_calibration import run_calibration

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output-dir',type=Path,default=Path('artifacts/task04'))
    args=p.parse_args()
    result=run_calibration(args.output_dir,progress=lambda s:print(s,flush=True))
    print('Calibration:', 'PASS' if result['valid'] else 'FAILED', 'threshold:',result['threshold'])
    raise SystemExit(0 if result['valid'] else 1)

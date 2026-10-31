"""Reproduce offline G2 evidence; never uploads media or calls an API."""
import argparse
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from realign.synth.g2_verification import verify_offline_g2


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir',type=Path,default=ROOT/'artifacts')
    args=parser.parse_args()
    result=verify_offline_g2(args.output_dir)
    print('Offline G2 checks:', 'PASS' if result['offline_passed'] else 'FAIL')
    print('Actual API calls: 0; actual real recordings: 0; G2: NOT PASSED')
    for c in result['synthetic_fixture']['checks']:
        print(('PASS: ' if c['passed'] else 'FAIL: ')+c['name'])
    if not result['offline_passed']:
        raise SystemExit(1)


if __name__=='__main__':
    main()

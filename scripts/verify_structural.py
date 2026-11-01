"""Reproduce the fixed B0/B1/B2/B3 synthetic comparison, including failures."""
import argparse
from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))
from realign.report.structural_report import build_structural_report


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--seed', type=int, default=20261101)
    p.add_argument('--output-dir', type=Path, default=ROOT/'artifacts')
    args = p.parse_args()
    result = build_structural_report(args.output_dir, seed=args.seed, progress=lambda s: print(s, flush=True))
    for c in result['checks']:
        print(('PASS: ' if c['passed'] else 'FAIL: ')+c['name'])
    raise SystemExit(0 if result['acceptance_passed'] else 1)


if __name__ == '__main__':
    main()

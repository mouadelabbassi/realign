"""Reproduce all fixed-seed POC-0 classical baseline evidence (no network calls)."""
import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))
from realign.report.baseline_report import build_report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--seed', type=int, default=20261031)
    parser.add_argument('--output-dir', type=Path, default=ROOT/'artifacts')
    args = parser.parse_args()
    result = build_report(args.output_dir, seed=args.seed, progress=lambda msg: print(msg, flush=True))
    print(f"{result['scope']}: {'PASS' if result['acceptance_passed'] else 'FAIL'}")
    for check in result['checks']:
        print(f"{'PASS' if check['passed'] else 'FAIL'}: {check['name']}")
    if not result['acceptance_passed']:
        raise SystemExit(1)


if __name__ == '__main__':
    main()

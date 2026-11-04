"""Replay saved SAM masks and diagnose a live session without any model calls."""
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from realign.physical.live_forensics import inspect_session


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('session', type=Path)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    if args.output and args.output.resolve().is_relative_to(args.session.resolve().parent):
        parser.error('Write forensic output outside the original recording library')
    result = inspect_session(args.session)
    data = json.dumps(result, indent=2, allow_nan=False) + '\n'
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(data, encoding='utf-8')
    else: print(data, end='')
    return 0


if __name__ == '__main__': raise SystemExit(main())

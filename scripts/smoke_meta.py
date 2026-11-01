"""Separately executable Muse capability check; no credentials means NOT_RUN."""
import argparse
import json
import os
from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))
from realign.perception.meta_validation import probe_muse, MODEL


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--standard-tier-confirmed', action='store_true')
    parser.add_argument('--output-dir', type=Path, default=ROOT/'artifacts')
    args = parser.parse_args()
    key = os.environ.get('MODEL_API_KEY')
    report = {'status': 'NOT_RUN', 'source': 'REAL_API', 'model': MODEL,
              'successful_calls': 0, 'failed_calls': 0, 'calls': [], 'blockers': [],
              'documentation_mismatch': 'NOT_ASSESSED: no live request'}
    if not key:
        report['blockers'].append('MODEL_API_KEY is not configured locally')
    if not args.standard_tier_confirmed:
        report['blockers'].append('Standard tier not confirmed')
    if not report['blockers']:
        from openai import OpenAI
        with OpenAI(base_url='https://api.meta.ai/v1', api_key=key, timeout=45, max_retries=0) as client:
            report = probe_muse(client, source='REAL_API')
    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir/'meta_smoke.json').write_text(json.dumps(report, indent=2, allow_nan=False)+'\n', encoding='utf-8')
    print('Muse:', report['status'], 'successful calls:', report['successful_calls'], 'failed calls:', report['failed_calls'])
    raise SystemExit(0 if report['status'] == 'PASS' else 2 if report['status'] == 'NOT_RUN' else 1)


if __name__ == '__main__':
    main()

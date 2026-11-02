"""Verify/export the product slice. Live operations require explicit flags.

Examples: python scripts/verify_task05.py
          python scripts/verify_task05.py --env-file .env --run-live --run-sam --standard-tier-confirmed
"""
import argparse
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--env-file',type=Path)
    p.add_argument('--run-live',action='store_true')
    p.add_argument('--run-sam',action='store_true')
    p.add_argument('--standard-tier-confirmed',action='store_true')
    p.add_argument('--concept',default='yellow disc')
    p.add_argument('--object-id')
    p.add_argument('--manual-reviews',type=Path)
    p.add_argument('--output-dir',type=Path,default=ROOT/'artifacts/task05')
    args=p.parse_args()
    if args.env_file and (args.run_live or args.run_sam):
        from realign.local_environment import load_model_key
        load_model_key(args.env_file)
    from realign.investigator_platform import delegate
    delegate('verify_task05.py')
    import asyncio
    from realign.product.demo import prepare_demo
    from realign.product.evidence import read_json,validate_bundle
    from realign.product.store import write_json
    from realign.product.external import process_external
    output=args.output_dir; output.mkdir(parents=True,exist_ok=True)
    if args.run_live:
        from realign.report.investigator_run import execute,load_gate,write_run
        count=len(list(output.glob('live_investigation_attempt_[0-9][0-9].json')))+1
        gate=load_gate(ROOT/'artifacts/task04/null_calibration.json')
        result=execute('off_vertical_peg',arm='live',seed=51300,gate=gate,
                       standard_tier_confirmed=args.standard_tier_confirmed)
        write_run(output/f'live_investigation_attempt_{count:02d}.json',result)
        print('Actual live attempt:',result['status'],flush=True)
    if args.run_sam:
        result=asyncio.run(process_external(ROOT/'data/raw/external/blocked-pendulum.mp4',
            ROOT/'artifacts/external_source_verified.json',output/'external_yellow_disc',
            ROOT/'data/processed/task05/sam_yellow_disc',run_api=True,
            standard_tier_confirmed=args.standard_tier_confirmed,concept=args.concept,
            object_id=args.object_id,manual_reviews=args.manual_reviews))
        print('External SAM:',result['status'],flush=True)
    store=prepare_demo(output/'demo',evidence_dir=output,progress=lambda s:print(s,flush=True))
    bundles=[store.run(ident) for ident in store.entries]
    checks=[{'name':'all presentation artifacts pass hashes, shape and freeze checks','passed':all(validate_bundle(b) for b in bundles)},
        {'name':'default demonstration is a complete two-round frozen prediction','passed':
            len(store.run('det-off-vertical')['rounds'])==2 and store.run('det-off-vertical')['decision']['accepted']},
        {'name':'measurement check never claims applied or verified correction','passed':
            all(not b['decision']['correction_applied'] and not b['decision']['correction_verified'] for b in bundles)},
        {'name':'live policy never relabels synthetic observations as real','passed':all(b['observation_source']=='SYNTHETIC' for b in bundles)},
        {'name':'external physical comparison remains unavailable without independent calibration','passed':store.external().get('physical_comparison_available') is False}]
    result={'scope':'POST_FREEZE PRODUCT INTEGRATION; SOURCE DOMAINS REMAIN SEPARATE',
        'checks':checks,'offline_passed':all(c['passed'] for c in checks),'recorded_runs':len(bundles),
        'live_muse':store.status()['live_muse'],'external_sam':store.external()['status'],
        'real_phone_measurements':'NOT_PROVIDED','full_G2_passed':False,'blind_discovery_demonstrated':False,
        'calibration_recomputed':False}
    write_json(output/'product_verification.json',result)
    for check in checks:print(('PASS: ' if check['passed'] else 'FAIL: ')+check['name'],flush=True)
    raise SystemExit(0 if result['offline_passed'] else 1)


if __name__=='__main__':main()

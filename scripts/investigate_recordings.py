"""Ingest controlled phone recordings, pause for physical responses, freeze and evaluate."""
import argparse,asyncio
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('manifest',type=Path);p.add_argument('--output-dir',type=Path,default=ROOT/'data/processed/task06_phone')
    p.add_argument('--run-api',action='store_true');p.add_argument('--live',action='store_true')
    p.add_argument('--standard-tier-confirmed',action='store_true');p.add_argument('--env-file',type=Path)
    p.add_argument('--resume',type=Path);p.add_argument('--response-manifest',type=Path)
    p.add_argument('--vault-dir',type=Path);p.add_argument('--challenge-id')
    args=p.parse_args()
    if args.env_file and (args.run_api or args.live):
        from realign.local_environment import load_model_key
        load_model_key(args.env_file)
    from realign.investigator_platform import delegate
    delegate('investigate_recordings.py')
    from realign.physical.orchestration import investigate_phone
    r=asyncio.run(investigate_phone(args.manifest,args.output_dir,run_api=args.run_api,live=args.live,
        standard_tier_confirmed=args.standard_tier_confirmed,resume=args.resume,response_manifest=args.response_manifest,
        vault_directory=args.vault_dir,challenge_id=args.challenge_id))
    print(r['status']);print('\n'.join(r['blockers']))
    raise SystemExit(0 if r['status']=='FROZEN' else 2 if r['status'] in ('BLOCKED_INPUTS','PENDING_PHYSICAL_ACTION','NOT_RUN') else 1)

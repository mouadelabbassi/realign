"""Process a real-recording manifest or report pending inputs, without inventing data."""
import argparse
import asyncio
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from realign.perception.workflow import process_manifest


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('manifest',type=Path)
    parser.add_argument('--output-dir',type=Path,default=ROOT/'data'/'processed'/'g2')
    parser.add_argument('--run-api',action='store_true',help='upload missing MP4s using local MODEL_API_KEY and confirmed Standard tier')
    args=parser.parse_args()
    result=asyncio.run(process_manifest(args.manifest,args.output_dir,run_api=args.run_api))
    print('G2:', 'PASS' if result['g2_passed'] else 'NOT PASSED')
    for reason in result['blockers']:
        print('PENDING:',reason)
    if not result['g2_passed']:
        raise SystemExit(1 if result.get('failures') else 2)


if __name__=='__main__':
    main()

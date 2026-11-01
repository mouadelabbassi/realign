"""Separate live SAM smoke test. No-key/no-footage is NOT_RUN, not a success."""
import argparse
import asyncio
from pathlib import Path
import sys
import json
import os
from dataclasses import asdict
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from realign.perception.video import probe_video
from realign.perception.sam_client import SamClient,SamError
from realign.perception.track import extract_track
from realign.perception.workflow import save_sam_cache
from realign.contracts.external import ExternalVideoSource


async def smoke(args):
    report={'scope':'ACTUAL SAM API VERIFICATION ONLY; fixtures excluded','status':'not_run',
            'successful_calls':0,'failed_calls':0,'blockers':[]}
    metadata=None
    if args.video is not None and args.video.is_file():
        try:
            external_path=getattr(args,'external_source',None)
            source=ExternalVideoSource(**json.loads(external_path.read_text(encoding='utf-8'))['provenance']) if external_path else None
            metadata=probe_video(args.video,source_kind='REAL_EXTERNAL' if source else 'REAL_PHONE',external_source=source)
            report['video_metadata']=asdict(metadata)
        except Exception as exc:
            report.update(status='failed',error_type=type(exc).__name__,code='invalid_video_or_provenance')
            return report
    if not os.environ.get('MODEL_API_KEY'):
        report['blockers'].append('MODEL_API_KEY is not configured locally')
    if args.video is None or not args.video.is_file():
        report['blockers'].append('actual local MP4 not supplied')
    if not args.standard_tier_confirmed:
        report['blockers'].append('Standard tier has not been confirmed')
    if report['blockers']:
        return report
    client=SamClient.from_environment(standard_tier_confirmed=True)
    try:
        run=await client.segment_video(args.video,metadata)
        track=extract_track(run,metadata,object_id=args.object_id)
        save_sam_cache(args.output_dir/'sam_smoke_cache',run)
        report.update(status='completed' if track.valid.any() else 'completed_empty_track',
                      video_metadata=asdict(metadata),quality=track.summary,receipt=run.receipt)
    except Exception as exc:
        report.update(status='failed',error_type=type(exc).__name__,code=getattr(exc,'code','processing_failed'))
    finally:
        report.update(successful_calls=sum(c['status']=='completed' for c in client.calls),
                      failed_calls=sum(c['status']=='failed' for c in client.calls),calls=client.calls)
        await client.close()
    return report


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('video',nargs='?',type=Path)
    p.add_argument('--standard-tier-confirmed',action='store_true')
    p.add_argument('--object-id')
    p.add_argument('--external-source',type=Path,help='Verified REAL_EXTERNAL source manifest; never label this footage REAL_PHONE')
    p.add_argument('--output-dir',type=Path,default=ROOT/'artifacts')
    args=p.parse_args(); args.output_dir.mkdir(parents=True,exist_ok=True)
    report=asyncio.run(smoke(args))
    (args.output_dir/'sam_api_verification.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print('SAM API:',report['status'],'successful calls:',report['successful_calls'],'failed calls:',report['failed_calls'])
    raise SystemExit(0 if report['status']=='completed' else 2 if report['status']=='not_run' else 1)


if __name__=='__main__':
    main()

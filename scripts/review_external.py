"""Prepare independent clean-frame review, or assess supplied annotation JSON.

No API requests are made. Task05 inputs are read-only. Annotation output must
be supplied by the user; the program never manufactures reference centers.
"""
import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))
from realign.perception.manual_review import (ManualReviewError, assess_manual_reviews,
    prepare_review_package, read_review_json, write_review_json)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command',required=True)
    for name in ('prepare','evaluate'):
        sub = commands.add_parser(name)
        sub.add_argument('--external-dir',type=Path,default=ROOT/'artifacts/task05/external_yellow_disc')
        sub.add_argument('--output-dir',type=Path,default=ROOT/'artifacts/task06/manual_review')
        if name=='prepare':
            sub.add_argument('--expanded',action='store_true');sub.add_argument('--video',type=Path)
        if name == 'evaluate':
            sub.add_argument('--annotations',type=Path)
            sub.add_argument('--reference-manifest',type=Path)
            sub.add_argument('--interval-s',type=float,default=2.)
            sub.add_argument('--second-annotations',type=Path)
    args = parser.parse_args(argv)
    try:
        if args.command == 'prepare':
            manifest=prepare_review_package(args.external_dir,args.output_dir,video_path=args.video,expanded=args.expanded)
            print('Clean annotation page:',args.output_dir/'review.html')
            print(str(len(manifest['frames']))+' blank references. No SAM predictions or synthetic annotations supplied.')
            return 0
        manifest_path = args.reference_manifest or args.output_dir/'reference_manifest.json'
        report = assess_manual_reviews(
            read_review_json(args.external_dir/'external_verification.json'),
            read_review_json(manifest_path),
            read_review_json(args.annotations) if args.annotations else None,
            interval_s=args.interval_s)
        write_review_json(args.output_dir/'measurement_validation.json',report,archive_previous=True)
        if args.annotations:
            write_review_json(args.output_dir/'supplied_annotations.json',read_review_json(args.annotations),archive_previous=True)
        if args.second_annotations:
            from realign.perception.manual_review import reviewer_repeatability
            result=reviewer_repeatability(read_review_json(args.annotations),read_review_json(args.second_annotations),
                read_review_json(args.external_dir/'external_verification.json'),read_review_json(manifest_path))
            write_review_json(args.output_dir/'reviewer_repeatability.json',result,archive_previous=True)
        print(report['status']+':',args.output_dir/'measurement_validation.json')
        return 0 if report['status'] == 'VALIDATED_MANUAL_REFERENCES' else 2
    except (ManualReviewError,OSError,ValueError,TypeError) as exc:
        print('Review workflow rejected input ('+type(exc).__name__+').',file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())

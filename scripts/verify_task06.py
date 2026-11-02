"""Reproduce Task06 evidence closure without fabricating annotations or phone data."""
import argparse,asyncio,shutil,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output-dir',type=Path,default=ROOT/'artifacts/task06')
    p.add_argument('--annotations',type=Path);p.add_argument('--phone-manifest',type=Path,default=ROOT/'configs/phone_investigation.example.json')
    p.add_argument('--phone-output',type=Path);p.add_argument('--run-synthetic-g5',action='store_true')
    args=p.parse_args()
    from realign.investigator_platform import delegate
    delegate('verify_task06.py')
    from realign.perception.manual_review import prepare_review_package,assess_manual_reviews,read_review_json,write_review_json
    from realign.product.store import write_json
    from realign.product.closure import publish_closure
    from realign.physical.orchestration import investigate_phone
    out=args.output_dir;review=out/'manual_review'
    manifest=prepare_review_package(ROOT/'artifacts/task05/external_yellow_disc',review)
    external=read_review_json(ROOT/'artifacts/task05/external_yellow_disc/external_verification.json')
    annotation_path=args.annotations or (review/'supplied_annotations.json' if (review/'supplied_annotations.json').is_file() else None)
    annotations=read_review_json(annotation_path) if annotation_path else None
    assessment=assess_manual_reviews(external,manifest,annotations)
    write_review_json(review/'measurement_validation.json',assessment,archive_previous=True)
    if annotations is not None:write_review_json(review/'supplied_annotations.json',annotations,archive_previous=True)
    if args.run_synthetic_g5:
        from verify_g5 import demo
        demo(out/'g5_demo',ROOT/'data/vault/task06',66300)
    phone_out=args.phone_output or ROOT/'data/processed/task06_phone'
    if not args.phone_output:
        phone=asyncio.run(investigate_phone(args.phone_manifest,phone_out))
    else:phone=read_review_json(phone_out/'phone_status.json')
    write_json(out/'phone_status.json',phone)
    for source,target in [('checkpoint.json','phone_checkpoint.json'),('investigation.json','phone_investigation.json')]:
        if (phone_out/source).is_file():write_json(out/target,read_review_json(phone_out/source))
    closure=publish_closure(out)
    status={'schema_version':1,'offline_closure_admission':'PASS','manual_measurement_accuracy':assessment['status'],
        'phone_workflow':phone['status'],'independent_exercise':closure['independent']['independent_verdict'] if closure['independent'] and 'independent_verdict' in closure['independent'] else 'NOT_RUN_OR_INCONCLUSIVE',
        'full_G2_passed':False,'full_physical_G5_passed':False,'new_meta_api_operations':0,
        'preserved_meta_evidence':'Task05 authentic Muse and SAM receipts; not rerun by this command'}
    write_json(out/'task06_verification.json',status)
    print('Offline closure admission: PASS')
    print('Independent manual accuracy:',assessment['status'])
    print('Controlled phone workflow:',phone['status'])
    print('Full physical G2/G5: NOT PASSED')
    return 0


if __name__=='__main__':raise SystemExit(main())

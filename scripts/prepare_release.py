"""Pin existing public evidence; never refit or call models."""
import json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from realign.product.claim_ladder import RESOURCES,release_view,evidence_sha
from realign.product.evidence import sha256_file
from realign.product.store import write_json

if __name__=='__main__':
    write_json(ROOT/'artifacts/release/evidence_manifest.json',{'schema_version':1,'entries':{
        k:{'file':p,'sha256':evidence_sha(ROOT/p),'hash_mode':'LF_TRANSPORT'} for k,p in RESOURCES.items()}})
    review=ROOT/'artifacts/release/manual_review'
    if (review/'reference_manifest.json').is_file():
        from realign.perception.manual_review import assess_manual_reviews,read_review_json,write_review_json
        from realign.product.closure import publish_closure
        annotations=read_review_json(review/'supplied_annotations.json') if (review/'supplied_annotations.json').is_file() else None
        assessment=assess_manual_reviews(read_review_json(ROOT/RESOURCES['sam']),read_review_json(review/'reference_manifest.json'),annotations)
        write_review_json(review/'measurement_validation.json',assessment,archive_previous=True)
        publish_closure(ROOT/'artifacts/release')
    view=release_view();write_json(ROOT/'artifacts/release/evidence_summary.json',view)
    print(view['ladder']['overall_claim_ceiling']);print('Fits: 0; Meta calls: 0')

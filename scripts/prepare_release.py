"""Pin existing public evidence; never refit or call models."""
import json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from realign.product.claim_ladder import RESOURCES,release_view
from realign.product.evidence import sha256_file
from realign.product.store import write_json

if __name__=='__main__':
    write_json(ROOT/'artifacts/release/evidence_manifest.json',{'schema_version':1,'entries':{
        k:{'file':p,'sha256':sha256_file(ROOT/p)} for k,p in RESOURCES.items()}})
    view=release_view();write_json(ROOT/'artifacts/release/evidence_summary.json',view)
    print(view['ladder']['overall_claim_ceiling']);print('Fits: 0; Meta calls: 0')

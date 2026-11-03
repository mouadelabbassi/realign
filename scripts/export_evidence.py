"""Read-only public evidence export/verification. Never extracts a supplied ZIP."""
import argparse,hashlib,json,subprocess,sys,zipfile
from pathlib import Path,PurePosixPath
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))

def verify_bundle(path):
    with zipfile.ZipFile(path) as z:
        names=z.namelist()
        if len(names)!=len(set(names)):raise ValueError('duplicate bundle member')
        for name in names:
            p=PurePosixPath(name)
            if p.is_absolute() or '..' in p.parts or '\\' in name or ':' in name or any(x in p.parts for x in ('vault','sealed','secrets','keys')):
                raise ValueError('unapproved bundle path')
        if sum(x.file_size for x in z.infolist())>200_000_000:raise ValueError('bundle exceeds size budget')
        m=json.loads(z.read('MANIFEST.json'))
        if set(names)!=set(m['files'])|{'MANIFEST.json'}:raise ValueError('bundle manifest membership mismatch')
        for name,sha in m['files'].items():
            if hashlib.sha256(z.read(name)).hexdigest()!=sha:raise ValueError('first mismatching hash: '+name)
    return {'status':'PASS','files_verified':len(m['files']),'source_sha':m['source_sha'],
        'scope':'LOCAL_HASH_INTEGRITY; NOT_EXTERNAL_AUTHENTICITY_OR_PHYSICAL_VALIDATION'}

def export_bundle(output):
    from realign.product.claim_ladder import release_evidence
    from realign.product.evidence import read_json
    evidence=release_evidence(ROOT)
    if evidence['issues']:raise ValueError(evidence['issues'][0])
    files=set()
    for folder in ('artifacts/task05/demo','artifacts/task06/g5_demo','artifacts/task06/g5_positive_control'):
        files.update(p.relative_to(ROOT).as_posix() for p in (ROOT/folder).glob('*.json'))
    for name in ('README.md','LICENSE','THIRD_PARTY_NOTICES.md','licenses/EXTERNAL_MEDIA.md',
                 'docs/RELEASE_READINESS.md','docs/G5_FAILURE_ANALYSIS.md','docs/SUBMISSION_CHECKLIST.md',
                 'artifacts/release/evidence_manifest.json','artifacts/release/evidence_summary.json',
                 'artifacts/release/meta_evidence_index.md'):
        if (ROOT/name).is_file():files.add(name)
    # No external pixels by default: source data/metrics retain attribution.
    payload={p:(ROOT/p).read_bytes() for p in sorted(files)}
    manifest={'schema_version':1,'source_sha':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
        'ladder':evidence['ladder'],'contains_external_pixels':False,
        'files':{p:hashlib.sha256(v).hexdigest() for p,v in payload.items()},
        'limitation':'Pinned local hashes do not provide organizer permission or third-party timestamp attestation.'}
    output=Path(output);output.parent.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(output,'w',compression=zipfile.ZIP_DEFLATED) as z:
        for name,data in payload.items():z.writestr(name,data)
        z.writestr('MANIFEST.json',json.dumps(manifest,sort_keys=True,separators=(',',':')))
    return verify_bundle(output)

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,default=ROOT/'data/processed/REALIGN_evidence.zip')
    p.add_argument('--verify',type=Path);args=p.parse_args()
    try:result=verify_bundle(args.verify) if args.verify else export_bundle(args.output)
    except (ValueError,KeyError,OSError,zipfile.BadZipFile) as exc:
        print('Evidence bundle refused: '+str(exc));raise SystemExit(1)
    print(json.dumps(result,indent=2))

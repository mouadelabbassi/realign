"""Conservative tracked-tree/history credential scan; never print matched values."""
import argparse,json,re,subprocess
from pathlib import Path

PATTERNS=(re.compile(rb'(?i)(?:MODEL_API_KEY|OPENAI_API_KEY)\s*[=:]\s*[\x22\x27]?([A-Za-z0-9_\-]{24,})'),
          re.compile(rb'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----'),
          re.compile(rb'\b(?:ghp_|github_pat_)[A-Za-z0-9_]{30,}'))

def scan(root):
    def git(*args):return subprocess.check_output(['git','-C',str(root),*args])
    findings=[];count=0
    tracked=git('ls-files','-z').decode().split('\0')
    for path in filter(None,tracked):
        if Path(path).name=='.env':findings.append({'resource':path,'reason':'TRACKED_ENV_FILE'})
    blobs={row.split(b' ',1)[0] for row in git('rev-list','--objects','--all').splitlines()}
    batch=subprocess.run(['git','-C',str(root),'cat-file','--batch'],input=b'\n'.join(sorted(blobs))+b'\n',capture_output=True,check=True).stdout
    cursor=0
    for oid in sorted(blobs):
        end=batch.index(b'\n',cursor);header=batch[cursor:end].split();size=int(header[2])
        data=batch[end+1:end+1+size];cursor=end+size+2
        if header[1]!=b'blob':continue
        count+=1
        if any(p.search(data) for p in PATTERNS):
            # Test fixtures and implementation references are checked as data,
            # rather than excluding every tests/scripts path from the scanner.
            matches=PATTERNS[0].findall(data)
            placeholders=all(m.lower().startswith((b'test_',b'fake_',b'example_',b'placeholder')) for m in matches)
            if not (matches and placeholders and not any(p.search(data) for p in PATTERNS[1:])):
                findings.append({'blob_sha':oid.decode(),'reason':'CREDENTIAL_PATTERN'})
    return {'status':'PASS' if not findings else 'FAIL','scope':'TRACKED_TREE_AND_ALL_REACHABLE_HISTORY',
            'blobs_scanned':count,'findings':findings,'limitation':'Pattern scan cannot prove absence of every possible credential encoding.'}

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path);args=p.parse_args()
    result=scan(Path(__file__).resolve().parents[1])
    if args.output:args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2));raise SystemExit(0 if result['status']=='PASS' else 1)

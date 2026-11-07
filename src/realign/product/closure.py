"""Admit Task06 public evidence; private vault files are never product resources."""
import base64,hashlib,re
from pathlib import Path
from realign.audit.chain import digest
from .evidence import EvidenceError,read_json,sha256_file
from .store import write_json

ROOT=Path(__file__).resolve().parents[3]
FILES={'manual':'manual_review/measurement_validation.json','references':'manual_review/reference_manifest.json',
       'annotations':'manual_review/supplied_annotations.json','review_html':'manual_review/review.html',
       'g5':'g5_demo/validation.json','phone':'phone_status.json','checkpoint':'phone_checkpoint.json',
       'phone_trace':'phone_investigation.json'}


def publish_closure(directory):
    directory=Path(directory)
    entries={k:{'file':p,'sha256':sha256_file(directory/p)} for k,p in FILES.items() if (directory/p).is_file()}
    write_json(directory/'closure_manifest.json',{'schema_version':1,'scope':'PUBLIC_HUMAN_EVIDENCE_ONLY','entries':entries})
    return load_closure(directory)


def _documents(directory):
    directory=Path(directory).resolve();index=read_json(directory/'closure_manifest.json')
    if index.get('schema_version')!=1 or index.get('scope')!='PUBLIC_HUMAN_EVIDENCE_ONLY':raise EvidenceError('invalid evidence closure manifest')
    documents={}
    for key,e in index['entries'].items():
        if key not in FILES or e['file']!=FILES[key]:raise EvidenceError('unapproved closure document')
        path=(directory/e['file']).resolve()
        if not path.is_relative_to(directory) or sha256_file(path)!=e['sha256']:raise EvidenceError('closure document changed')
        if key!='review_html':documents[key]=read_json(path)
    return index,documents


def validate_independent_report(report):
    from realign.audit.public_validation import verify_reveal
    if report.get('status')=='INCONCLUSIVE' and 'commitment' in report:
        if report.get('domain')!='SYNTHETIC' or report.get('full_physical_G5_passed') is not False:raise EvidenceError('invalid inconclusive exercise')
        return report
    try:
        c=report['commitment'];e=report['evaluation'];f=report['frozen_model'];r=report['reveal']
        clean=dict(e);sha=clean.pop('evaluation_sha256')
        if (not verify_reveal(c,r) or digest(clean)!=sha or sha!=r['evaluation_sha256'] or
            f['content_sha256']!=e['frozen_model_sha256'] or c['challenge_id']!=e['challenge_id'] or
            c['domain']!=e['domain'] or r['domain']!=c['domain'] or
            f['commitment_sha256']!=c['commitment_sha256'] or
            report['independent_verdict']!=r['verdict'] or report['full_physical_G5_passed'] is not False or
            r['full_physical_G5_passed'] is not False):raise ValueError
        if c['domain']=='SYNTHETIC' and r['verdict'] not in ('SYNTHETIC_EXERCISE_PASS','SYNTHETIC_VALIDATION_FAIL','INCONCLUSIVE'):raise ValueError
    except (KeyError,ValueError,TypeError):raise EvidenceError('independent validation evidence failed admission') from None
    return report


def load_closure(directory):
    directory=Path(directory)
    if not (directory/'closure_manifest.json').is_file():
        return {'schema_version':1,'status':'NOT_PREPARED','manual':None,'independent':None,'phone':None,'review_url':None}
    index,docs=_documents(directory)
    result={'schema_version':1,'status':'ADMITTED_PUBLIC_EVIDENCE','manual':None,'independent':None,'phone':None,
            'review_url':'/review' if 'review_html' in index['entries'] else None,'full_physical_G5_passed':False}
    if 'manual' in docs:
        from realign.perception.manual_review import verify_assessment
        external=read_json(ROOT/'artifacts/task05/external_yellow_disc/external_verification.json')
        annotations=docs.get('annotations') if docs['manual'].get('annotations_sha256') is not None else None
        result['manual']=verify_assessment(docs['manual'],external,docs['references'],annotations)
        frames=docs['references']['frames']
        result['review_sample']={'first_frame_index':min(f['frame_index'] for f in frames),
            'first_pts_s':min(f['pts_s'] for f in frames),'frames':len(frames)}
    if 'g5' in docs:result['independent']=validate_independent_report(docs['g5'])
    if 'phone' in docs:
        result['phone']=validate_phone(docs['phone'],checkpoint=docs.get('checkpoint'),trace=docs.get('phone_trace'))
    return result


def validate_phone(phone, *, checkpoint=None, trace=None):
    """Same Task 06 admission for closure bundles and explicit local outputs."""
    if phone.get('observation_source')!='REAL_PHONE' or phone.get('full_G2_passed') is not False:
        raise EvidenceError('controlled phone evidence boundary failed')
    if phone['status']=='PENDING_PHYSICAL_ACTION':
        from realign.physical.session import validate_checkpoint
        cp=validate_checkpoint(checkpoint)
        if cp['pending_action']!=phone['pending_action'] or cp['checkpoint_sha256']!=phone['checkpoint_sha256']:
            raise EvidenceError('pending action differs from checkpoint')
    if phone['status']=='FROZEN':
        from realign.report.investigator_run import verify_replay
        if not trace or not verify_replay(trace) or trace['freeze']!=phone['decision'] or digest(trace)!=phone['trace_sha256']:
            raise EvidenceError('physical freeze/audit integrity failed')
    return phone


def review_page(directory):
    index,_=_documents(directory)
    if 'review_html' not in index['entries']:raise EvidenceError('clean review package not prepared')
    data=(Path(directory)/FILES['review_html']).read_bytes()
    if len(data)>32_000_000:raise EvidenceError('review package too large')
    scripts=re.findall(rb'<script>(.*?)</script>',data,re.S)
    if len(scripts)!=1:raise EvidenceError('unexpected annotation page script structure')
    script=scripts[0].replace(b'\r\n',b'\n').replace(b'\r',b'\n')
    signature=base64.b64encode(hashlib.sha256(script).digest()).decode()
    policy="default-src 'none'; script-src 'sha256-"+signature+"'; style-src 'unsafe-inline'; img-src data:; connect-src 'none'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'"
    return data,policy

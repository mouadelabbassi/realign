"""Read-only catalog. Playback performs no fits, regeneration or network calls."""
import re
from pathlib import Path
from realign.audit.chain import canonical
from .evidence import EvidenceError,read_json,sha256_file,validate_bundle,validate_external


class ProductStore:
    def __init__(self,root):
        self.root=Path(root).resolve()
        self.index=read_json(self.root/'catalog.json')
        if type(self.index) is not dict or self.index.get('schema_version')!=1 or not isinstance(self.index.get('runs'),list):
            raise EvidenceError('invalid presentation catalog')
        self.entries={}
        for entry in self.index['runs']:
            if type(entry) is not dict:
                raise EvidenceError('invalid catalog entry')
            ident=entry.get('id','')
            if not isinstance(ident,str) or not re.fullmatch(r'[a-z0-9-]{1,64}',ident) or ident in self.entries:
                raise EvidenceError('invalid or duplicate catalog identity')
            if entry.get('observation_source')!='SYNTHETIC' or entry.get('policy') not in ('DETERMINISTIC','MOCK_POLICY','LIVE_MUSE'):
                raise EvidenceError('unapproved catalog provenance')
            self._path(entry['file']); self.entries[ident]=entry

    def _path(self,name):
        if not isinstance(name,str) or not re.fullmatch(r'[a-zA-Z0-9_-]+\.json',name):
            raise EvidenceError('unapproved presentation resource')
        p=(self.root/name).resolve()
        if p.parent!=self.root:
            raise EvidenceError('resource outside approved catalog directory')
        return p

    def run(self,ident):
        if ident not in self.entries:
            raise EvidenceError('unknown recorded investigation')
        entry=self.entries[ident]; p=self._path(entry['file'])
        if sha256_file(p)!=entry['sha256']:
            raise EvidenceError('presentation hash mismatch; refusing altered evidence')
        value=validate_bundle(read_json(p))
        if (value['id']!=ident or value['policy']!=entry['policy'] or value['observation_source']!=entry['observation_source'] or
            value['title']!=entry['title'] or value['decision']['label']!=entry['outcome_label'] or entry['status']!='COMPLETED'):
            raise EvidenceError('catalog and presentation provenance disagree')
        return value

    def catalog(self):
        return {'schema_version':1,'default_run_id':'det-off-vertical',
            'runs':[{k:e[k] for k in ('id','title','policy','observation_source','status','outcome_label')} for e in self.entries.values()],
            'live':self.status().get('live_muse',{}),'external':self.external(),
            'phone':{'status':'NOT_PROVIDED','observation_source':'REAL_PHONE'}}

    def _document(self,key,default):
        entry=self.index.get(key)
        if not entry:
            return default
        if type(entry) is not dict:
            raise EvidenceError('invalid status catalog entry')
        p=self._path(entry['file'])
        if sha256_file(p)!=entry['sha256']:
            raise EvidenceError('presentation status hash mismatch')
        value=read_json(p)
        if type(value) is not dict:
            raise EvidenceError('invalid presentation status document')
        return value

    def status(self):
        return self._document('status',{'live_muse':{'status':'NOT_RUN'},'sam':{'status':'NOT_RUN'},'phone':{'status':'NOT_PROVIDED'}})

    def external(self):
        return validate_external(self._document('external',{'status':'NOT_RUN','observation_source':'REAL_EXTERNAL','track':None,
            'sam':{'status':'NOT_RUN'},'manual_review':{'status':'NOT_PROVIDED','rmse_px':None},
            'physical_comparison_available':False,'media_url':None,'limitations':['External video evidence not prepared.']}))


def write_json(path,value):
    p=Path(path); p.parent.mkdir(parents=True,exist_ok=True)
    temporary=p.with_suffix(p.suffix+'.tmp')
    temporary.write_bytes(canonical(value)); temporary.replace(p)


def publish(root,bundles,status,external):
    root=Path(root); root.mkdir(parents=True,exist_ok=True)
    entries=[]
    for bundle in bundles:
        validate_bundle(bundle); name=bundle['id']+'.json'; write_json(root/name,bundle)
        entries.append({'id':bundle['id'],'file':name,'sha256':sha256_file(root/name),
            'title':bundle['title'],'policy':bundle['policy'],'observation_source':bundle['observation_source'],
            'status':'COMPLETED','outcome_label':bundle['decision']['label']})
    write_json(root/'status.json',status); write_json(root/'external.json',external)
    index={'schema_version':1,'runs':entries,'status':{'file':'status.json','sha256':sha256_file(root/'status.json')},
           'external':{'file':'external.json','sha256':sha256_file(root/'external.json')}}
    write_json(root/'catalog.json',index)
    return ProductStore(root)

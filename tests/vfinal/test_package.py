import importlib.util,json,zipfile
from pathlib import Path
import pytest

ROOT=Path(__file__).resolve().parents[2]

def module():
    spec=importlib.util.spec_from_file_location('export_evidence',ROOT/'scripts/export_evidence.py')
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m

def test_public_bundle_verifies_and_identifies_first_tamper(tmp_path):
    m=module();out=tmp_path/'evidence.zip'
    assert m.export_bundle(out)['status']=='PASS'
    with zipfile.ZipFile(out) as z:payload={n:z.read(n) for n in z.namelist()}
    name=next(n for n in payload if n!='MANIFEST.json');payload[name]+=b'altered'
    bad=tmp_path/'tampered.zip'
    with zipfile.ZipFile(bad,'w') as z:
        for n,data in payload.items():z.writestr(n,data)
    with pytest.raises(ValueError,match='first mismatching hash'):m.verify_bundle(bad)

def test_bundle_never_extracts_private_paths(tmp_path):
    p=tmp_path/'unsafe.zip'
    with zipfile.ZipFile(p,'w') as z:z.writestr('../vault/private.json','not opened or extracted')
    with pytest.raises(ValueError,match='unapproved bundle path'):module().verify_bundle(p)

def test_judge_copy_avoids_affirmative_unsupported_claims():
    import re
    forbidden=re.compile(r'REALIGN\s+(?:outperforms|discovers the true|repaired a real)',re.I)
    for p in [ROOT/'README.md',ROOT/'src/realign/product/static/app.js']:
        assert not forbidden.search(p.read_text(encoding='utf-8'))
    assert forbidden.search('REALIGN outperforms the deterministic comparator')

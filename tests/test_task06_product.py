"""Public product closure admission; no real annotations or physical claims."""
from copy import deepcopy
from pathlib import Path
import http.client,json,threading
import pytest
from realign.product.closure import load_closure,publish_closure,validate_independent_report,review_page
from realign.product.evidence import read_json,EvidenceError
from realign.product.store import write_json
from realign.product.server import make_server

ROOT=Path(__file__).resolve().parents[1]


def test_prepared_closure_keeps_domains_and_missing_manual_accuracy_separate():
    closure=load_closure(ROOT/'artifacts/task06')
    assert closure['manual']['status']=='NOT_VALIDATED' and closure['manual']['metrics']['rmse_px'] is None
    assert closure['manual']['metrics']['bias_px'] is None
    assert closure['phone']['status']=='BLOCKED_INPUTS' and closure['phone']['pending_action'] is None
    assert closure['phone']['full_G2_passed'] is False
    if closure['independent']:
        assert closure['independent']['commitment']['domain']=='SYNTHETIC'
        assert closure['independent']['full_physical_G5_passed'] is False
    assert closure['review_sample']['first_frame_index']==157


@pytest.mark.parametrize('change',['nonce','domain','score','model','physical_pass'])
def test_independent_product_report_cannot_detach_from_commitment_and_freeze(change):
    r=read_json(ROOT/'artifacts/task06/g5_positive_control/validation.json')
    if change=='nonce':r['reveal']['nonce_hex']='0'*64
    elif change=='domain':r['evaluation']['domain']='REAL_PHONE'
    elif change=='score':r['evaluation']['trajectory_rmse_px']=0.
    elif change=='model':r['frozen_model']['content_sha256']='e'*64
    else:r['full_physical_G5_passed']=True
    with pytest.raises(EvidenceError):validate_independent_report(r)


def test_missing_or_tampered_closure_does_not_generate_results(tmp_path):
    assert load_closure(tmp_path)['status']=='NOT_PREPARED'
    write_json(tmp_path/'closure_manifest.json',{'schema_version':1,'scope':'PUBLIC_HUMAN_EVIDENCE_ONLY',
        'entries':{'private':{'file':'../../data/vault/private.json','sha256':'0'*64}}})
    with pytest.raises(EvidenceError):load_closure(tmp_path)


def test_review_route_is_hash_bound_and_has_no_network_or_unsafe_eval():
    page,csp=review_page(ROOT/'artifacts/task06')
    assert b'__REVIEW_DATA__' not in page and b'center_px":null' in page
    assert "connect-src 'none'" in csp and "'sha256-" in csp and "unsafe-eval" not in csp
    assert b'xy_px' not in page and b'track_accepted' not in page


def test_closure_http_is_readonly_and_exposes_no_vault_routes():
    s=make_server(ROOT/'artifacts/task05/demo',port=0,closure_root=ROOT/'artifacts/task06')
    thread=threading.Thread(target=s.serve_forever,daemon=True);thread.start()
    try:
        for path in ['/api/closure','/review']:
            c=http.client.HTTPConnection('127.0.0.1',s.server_port,timeout=15);c.request('GET',path)
            response=c.getresponse();body=response.read();assert response.status==200
            if path=='/review':assert "connect-src 'none'" in response.headers['Content-Security-Policy']
            c.close()
        c=http.client.HTTPConnection('127.0.0.1',s.server_port);c.request('GET','/data/vault/task06/ledger.jsonl')
        response=c.getresponse();response.read();assert response.status==404;c.close()
    finally:s.shutdown();s.server_close();thread.join(timeout=5)

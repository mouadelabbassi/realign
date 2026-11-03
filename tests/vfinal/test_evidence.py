"""Release claims are descriptive, source separated and read-only."""
from copy import deepcopy
from pathlib import Path
import http.client,json,threading
import pytest
from realign.product.claim_ladder import release_evidence,release_view,compute_ladder,agent_value
from realign.product.server import make_server

ROOT=Path(__file__).resolve().parents[2]

def test_duplicate_loopback_listener_is_refused():
    first=make_server(ROOT/'artifacts/task05/demo',port=0)
    try:
        with pytest.raises(OSError):make_server(ROOT/'artifacts/task05/demo',port=first.server_port)
    finally:first.server_close()

def test_ladder_golden_current_state():
    evidence=release_evidence(ROOT);ladder=evidence['ladder']
    assert not evidence['issues']
    assert ladder['overall_claim_ceiling']=='C3a'
    assert ladder['branches']['REAL_EXTERNAL']['human_accuracy']=='NOT_VALIDATED'
    assert ladder['branches']['REAL_PHONE']['status']=='BLOCKED_INPUTS'
    assert ladder['branches']['SYNTHETIC']['g5_outcomes']=={'fixed':'SYNTHETIC_EXERCISE_PASS','randomized':'SYNTHETIC_VALIDATION_FAIL'}

def test_ladder_drops_when_artifact_removed():
    a=release_evidence(ROOT)['artifacts'];a.pop('sam')
    assert compute_ladder(a)['overall_claim_ceiling']=='C2'
    a.pop('muse');assert compute_ladder(a)['overall_claim_ceiling']=='C1'
    a.pop('b3');assert compute_ladder(a)['overall_claim_ceiling']=='C0'
    a.pop('g1');assert compute_ladder(a)['overall_claim_ceiling']=='UNVERIFIED'

def test_agent_value_label_on_recorded_case():
    value=release_view(ROOT)['agent_value']
    assert value['label']=='No predictive advantage demonstrated'
    assert value['difference_px']==0 and value['live_fit_jobs']==value['deterministic_fit_jobs']==8
    assert value['billed_cost_status']=='UNVERIFIED'

def test_no_superiority_inference_from_one_better_error():
    a=deepcopy(release_evidence(ROOT)['artifacts']['matched'])
    a['live_attempts'][-1]['prediction_rmse_px']=.1
    assert agent_value(a)['label']=='No predictive advantage demonstrated'

def test_every_endpoint_has_evidence_header_and_no_endpoint_can_start_paid_call(monkeypatch):
    def forbidden(*a,**kw):raise AssertionError('Product started computation or paid execution')
    from realign.agent.adapters import MuseAdapter
    monkeypatch.setattr(MuseAdapter,'from_environment',forbidden)
    from realign.fit import robust_fit,peg_fit
    monkeypatch.setattr(robust_fit,'fit_free',forbidden);monkeypatch.setattr(peg_fit,'fit_peg',forbidden)
    server=make_server(ROOT/'artifacts/task05/demo',port=0)
    t=threading.Thread(target=server.serve_forever,daemon=True);t.start()
    try:
        for method,path in [('GET',p) for p in ['/api/catalog','/api/status','/api/external','/api/closure','/api/release','/api/runs/live-02','/api/unknown']]+[('POST','/api/run'),('PUT','/review'),('DELETE','/api/closure')]:
            c=http.client.HTTPConnection('127.0.0.1',server.server_port);c.request(method,path)
            r=c.getresponse();body=json.loads(r.read());c.close()
            h=body['evidence_header']
            assert all(h.get(k) for k in ['source_domain','source_domains','policy','run_id','stage','ladder_level'])
            if method!='GET':assert r.status==405
            if path=='/api/runs/live-02':assert h['source_domain']=='SYNTHETIC' and h['policy']=='LIVE_MUSE'
            if path=='/api/closure':assert h['source_domain']=='AGGREGATE'
    finally:server.shutdown();server.server_close();t.join(timeout=5)

def test_ai_labels_never_ground_truth():
    from realign.perception.manual_review import assess_manual_reviews,read_review_json
    report=read_review_json(ROOT/'artifacts/task05/external_yellow_disc/external_verification.json')
    manifest=read_review_json(ROOT/'artifacts/task06/manual_review/reference_manifest.json')
    for source in ['AI_VISUAL','SYNTHETIC_TEST_REFERENCE']:
        result=assess_manual_reviews(report,manifest,{'annotation_source':source})
        assert result['status']=='NOT_VALIDATED' and result['metrics']['rmse_px'] is None

"""Local HTTP boundary and existing admission integration, without hardware/API."""
import asyncio
import json
import threading
import urllib.error
import urllib.request

import pytest

from realign.physical.live_lab import LabLibrary, CaptureController
from realign.physical.lab_server import make_lab_server
from realign.physical.orchestration import investigate_phone
from realign.physical.lab_progress import read_progress
from realign.product.lab import load_lab
from realign.product.server import make_server


@pytest.fixture
def lab_http(tmp_path):
    controller = CaptureController(LabLibrary(tmp_path / 'library'))
    server = make_lab_server(controller, port=0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield controller, 'http://127.0.0.1:' + str(server.server_port)
    server.shutdown(); server.server_close(); controller.close(); thread.join(timeout=5)


def request(url, path, body=None, headers=None):
    req = urllib.request.Request(url + path, data=json.dumps(body).encode() if body is not None else None,
                                 headers={'Content-Type': 'application/json', **(headers or {})})
    try: response = urllib.request.urlopen(req, timeout=10)
    except urllib.error.HTTPError as exc: response = exc
    with response: return response.status, json.loads(response.read())


def test_controls_require_same_origin_and_unpredictable_token(lab_http):
    _, url = lab_http
    code, status = request(url, '/api/status')
    assert code == 200 and status['state'] == 'IDLE'
    assert request(url, '/api/connect', {'index': 0})[0] == 403
    token = status['control_token']
    auth = {'X-Live-Lab-Token': token}
    assert request(url, '/api/connect', {'index': 0}, {**auth, 'Origin': 'https://foreign.example'})[0] == 403
    assert request(url, '/api/status', headers={'Host': 'evil.example'})[0] == 403
    assert request(url, '/api/stop', {}, auth)[0] == 409
    assert request(url, '/api/run-api', {}, auth)[0] == 404
    assert request(url, '/files/../../.env')[0] == 404


def test_camera_discovery_endpoint_is_authorized_local_only_and_reports_detected_inputs(lab_http):
    controller,url=lab_http
    probes=[]
    class Probe:
        def __init__(self,index):self.index=index
        def isOpened(self):return self.index in (2,5)
        def getBackendName(self):return 'INJECTED_TEST_CAMERA'
        def release(self):probes.append(self.index)
    controller.camera_factory=lambda index,*args:Probe(index)
    assert request(url,'/api/scan',{'maximum':8})[0]==403
    assert probes==[]
    token=request(url,'/api/status')[1]['control_token']
    code,result=request(url,'/api/scan',{'maximum':8},{'X-Live-Lab-Token':token})
    assert code==200 and [d['index'] for d in result['devices']]==[2,5]
    assert probes==list(range(8)) and result['scan']['new_meta_requests']==0
    assert controller.camera is None and controller.writer is None and controller.live is None


def test_import_endpoint_and_read_only_projection_share_blockers(lab_http, tmp_path):
    controller, url = lab_http
    source = tmp_path / 'WhatsApp-pilot.mp4'; source.write_bytes(b'invalid pilot')
    token = request(url, '/api/status')[1]['control_token']
    code, report = request(url, '/api/import', {'path': str(source)}, {'X-Live-Lab-Token': token})
    assert code == 200 and report['status'] == 'BLOCKED_INPUTS'
    assert report['media']['status'] == 'REJECTED'
    product = load_lab(controller.library.root)
    assert product['recordings'][0]['blockers'] == report['blockers']
    assert 'source_path' not in product['recordings'][0]['provenance']
    assert product['independent_validation']['status'] == 'NOT_RUN'
    assert product['state'] == 'REVIEW_REQUIRED'


def test_blocked_phone_run_retains_status_history_and_reports_progress(tmp_path):
    manifest = tmp_path / 'manifest.json'; manifest.write_text('{"source_kind":"REAL_PHONE"}')
    out = tmp_path / 'phone'
    result = asyncio.run(investigate_phone(manifest, out))
    assert result['status'] == 'BLOCKED_INPUTS' and result['actual_api_requests'] == 0
    events = read_progress(out / 'lab_progress.json')['events']
    assert [e['state'] for e in events] == ['ADMISSION', 'REVIEW_REQUIRED']
    assert len(list((out / 'history').glob('status-*.json'))) == 1
    projection = load_lab(tmp_path / 'absent-library', out)
    assert projection['investigation']['blockers'] == result['blockers']
    assert not (tmp_path / 'absent-library').exists()
    events[0]['state'] = 'FROZEN'
    (out / 'lab_progress.json').write_text(json.dumps({'events': events}))
    with pytest.raises(ValueError): load_lab(tmp_path / 'absent-library', out)


def test_pending_status_cannot_exist_without_valid_checkpoint(tmp_path):
    out = tmp_path / 'phone'; out.mkdir()
    (out / 'phone_status.json').write_text(json.dumps({'status': 'PENDING_PHYSICAL_ACTION',
        'observation_source': 'REAL_PHONE', 'full_G2_passed': False, 'pending_action': {}}))
    (out / 'checkpoint.json').write_text('{}')
    with pytest.raises(ValueError): load_lab(tmp_path / 'library', out)


def test_product_lab_endpoint_is_read_only_and_missing_library_stays_absent(tmp_path):
    root = tmp_path / 'library'
    server = make_server(tmp_path / 'unused', port=0, lab_root=root)
    thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
    url = 'http://127.0.0.1:' + str(server.server_port)
    try:
        code, result = request(url, '/api/lab')
        assert code == 200 and result['evidence_header']['source_domain'] == 'REAL_PHONE'
        assert result['state'] == 'IDLE' and not root.exists()
        assert request(url, '/api/lab', {})[0] == 405
    finally: server.shutdown(); server.server_close(); thread.join(timeout=5)

"""Portable, offline product evidence tests. No fit, API or real key is used."""
from copy import deepcopy
import http.client
import json
from pathlib import Path
import threading

import pytest

from realign.audit.chain import canonical, digest
from realign.product.evidence import (
    EvidenceError, read_json, sha256_file, validate_bundle, validate_external,
    validate_record,
)
from realign.product.semantics import decision_view
from realign.product.server import make_server
from realign.product.store import ProductStore, publish, write_json


ROOT = Path(__file__).resolve().parents[1]
DEMO = ROOT / "artifacts/task05/demo"
IDS = ("det-off-vertical", "det-measurement", "mock-off-vertical")


def unavailable_external():
    return {
        "status": "NOT_RUN", "observation_source": "REAL_EXTERNAL", "media_url": None,
        "track": None, "sam": {"status": "NOT_RUN", "successful_calls": 0, "failed_calls": 0},
        "manual_review": {"status": "NOT_PROVIDED", "rmse_px": None},
        "physical_comparison_available": False,
        "limitations": ["OFFLINE TEST FIXTURE; no real processing is claimed."],
    }


@pytest.fixture(scope="module")
def demo_bundles():
    # These are portable recorded artifacts, not recomputed generator output.
    return {ident: read_json(DEMO / (ident + ".json")) for ident in IDS}


@pytest.fixture
def product_root(tmp_path, demo_bundles):
    status = {
        "live_muse": {"status": "NOT_RUN", "successful_calls": 0, "failed_calls": 0},
        "sam": {"status": "NOT_RUN"}, "phone": {"status": "NOT_PROVIDED"},
        "limitations": ["OFFLINE TEST FIXTURE"],
    }
    root = tmp_path / "portable"
    publish(root, [deepcopy(value) for value in demo_bundles.values()], status, unavailable_external())
    return root


def repin_document(root, ident, value):
    """Reach semantic validation after updating the enclosing test-catalog pin."""
    path = root / (ident + ".json")
    write_json(path, value)
    index = read_json(root / "catalog.json")
    for entry in index["runs"]:
        if entry["id"] == ident:
            entry["sha256"] = sha256_file(path)
    write_json(root / "catalog.json", index)


def test_portable_playback_uses_no_numerical_or_network_work(product_root, monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("Playback attempted fitting, regeneration, a worker or a network request")
    import realign.fit.robust_fit as free
    import realign.fit.peg_fit as peg
    import realign.synth.investigation_fixtures as fixtures
    import realign.tools.sandbox as sandbox
    import realign.agent.adapters as adapters
    monkeypatch.setattr(free, "fit_free", forbidden)
    monkeypatch.setattr(peg, "fit_peg", forbidden)
    monkeypatch.setattr(fixtures, "case", forbidden)
    monkeypatch.setattr(sandbox, "WorkerClient", forbidden)
    monkeypatch.setattr(adapters.MuseAdapter, "from_environment", forbidden)
    store = ProductStore(product_root)
    catalog = store.catalog()
    assert len(catalog["runs"]) == len(IDS)
    for ident in IDS:
        bundle = store.run(ident)
        assert bundle["playback"] == "RECORDED_ARTIFACT"
        assert bundle["audit"]["verified"] is True
        assert bundle["observation_source"] == "SYNTHETIC"
    assert store.external()["observation_source"] == "REAL_EXTERNAL"
    assert store.status()["live_muse"]["status"] == "NOT_RUN"


def test_backend_to_ui_has_disjoint_rounds_and_frozen_evaluation(product_root):
    value = ProductStore(product_root).run("det-off-vertical")
    assert value["view_scope"] == "POST_FREEZE_HUMAN_ONLY"
    assert [row["round"] for row in value["rounds"]] == [1, 2]
    assert len(value["rounds"][0]["trial_ids"]) == 2
    assert len(value["rounds"][1]["trial_ids"]) == 4
    assert value["experiment"]["requested"] is True
    assert value["experiment"]["received_new_trials"] == 2
    assert value["experiment"]["receipt"]["source"] == "SYNTHETIC_ENVIRONMENT"
    exploration = {t["id"] for t in value["trials"] if t["zone"] == "exploration"}
    development = {t["id"] for t in value["trials"] if t["zone"] == "development"}
    assert exploration and development and exploration.isdisjoint(development)
    assert value["evaluation"]["scope"] == "POST_FREEZE_DEVELOPMENT"
    assert value["evaluation"]["rmse_px"] == pytest.approx(value["baseline"]["B3"])
    for trial in value["trials"]:
        n = len(trial["t_s"])
        assert n == len(trial["xy_px"]) == len(trial["valid"])
        for number, models in trial["round_predictions"].items():
            if trial["zone"] == "exploration":
                assert trial["admitted_round"] <= int(number)
            for name, model in models.items():
                assert len(model["xy_px"]) == n
                assert model["fitted_round"] == (0 if name == "B0" else int(number))


def test_measurement_check_is_never_claimed_as_completed_correction(product_root):
    value = ProductStore(product_root).run("det-measurement")
    decision = value["decision"]
    assert decision["outcome"] == "CORRECT_MEASUREMENT"
    assert decision["label"] == "Measurement correction required"
    assert decision["correction_applied"] is decision["correction_verified"] is False
    assert decision["model_ref"] is None
    assert "still required" in decision["explanation"]
    assert value["experiment"]["receipt"]["kind"] in ("CAMERA_CALIBRATION", "STATIONARY_REFERENCE")
    for field in ("correction_applied", "correction_verified"):
        altered = deepcopy(value)
        altered["decision"][field] = True
        with pytest.raises(EvidenceError, match="correction"):
            validate_bundle(altered)


def test_independent_validator_wording_preserves_contract_outcome(demo_bundles):
    freeze = demo_bundles["det-measurement"]["audit"]["events"][-1]["payload"]
    original = deepcopy(freeze)
    assert decision_view(freeze)["label"] == "Measurement correction required"
    assert freeze == original


@pytest.mark.parametrize("field", ["label", "explanation"])
def test_unverified_measurement_success_wording_is_rejected(demo_bundles, field):
    value = deepcopy(demo_bundles["det-measurement"])
    value["decision"][field] = "Measurement corrected successfully"
    with pytest.raises(EvidenceError):
        validate_bundle(value)


def test_file_hash_detects_observation_changes_before_display(product_root):
    path = product_root / "det-off-vertical.json"
    value = read_json(path)
    value["trials"][0]["xy_px"][0][0] += 1
    write_json(path, value)
    with pytest.raises(EvidenceError, match="hash mismatch"):
        ProductStore(product_root).run("det-off-vertical")


@pytest.mark.parametrize("case", ["audit", "freeze", "model", "sealed", "private", "real", "length", "timestamp", "prediction"])
def test_semantic_tampering_is_rejected_even_with_updated_file_pin(product_root, case):
    value = ProductStore(product_root).run("det-off-vertical")
    if case == "audit": value["audit"]["events"][0]["payload"]["round"] = 99
    elif case == "freeze": value["decision"]["outcome"] = "KEEP_UNCHANGED"
    elif case == "model": value["models"]["B3"]["params"]["length_m"] += .01
    elif case == "sealed": value["trials"][0]["zone"] = "sealed"
    elif case == "private": value["rounds"][0]["ground_truth"] = "PRIVATE_TEST_CANARY"
    elif case == "real": value["observation_source"] = "REAL_PHONE"
    elif case == "length": value["trials"][0]["valid"].pop()
    elif case == "timestamp": value["trials"][0]["t_s"][1] = value["trials"][0]["t_s"][0]
    elif case == "prediction": value["trials"][0]["predictions"]["B0"]["xy_px"].pop()
    repin_document(product_root, "det-off-vertical", value)
    with pytest.raises(EvidenceError):
        ProductStore(product_root).run("det-off-vertical")


def test_offline_policy_cannot_be_relabelled_as_another_policy(product_root):
    value = ProductStore(product_root).run("det-off-vertical")
    value["policy"] = "MOCK_POLICY"
    repin_document(product_root, "det-off-vertical", value)
    index = read_json(product_root / "catalog.json")
    index["runs"][0]["policy"] = "MOCK_POLICY"
    write_json(product_root / "catalog.json", index)
    with pytest.raises(EvidenceError):
        ProductStore(product_root).run("det-off-vertical")


def test_catalog_cannot_relabel_synthetic_observations_as_phone(product_root):
    index = read_json(product_root / "catalog.json")
    index["runs"][0]["observation_source"] = "REAL_PHONE"
    write_json(product_root / "catalog.json", index)
    with pytest.raises(EvidenceError):
        ProductStore(product_root).run("det-off-vertical")


def test_self_consistent_model_rebinding_still_must_match_audited_fit(demo_bundles):
    value = deepcopy(demo_bundles["det-off-vertical"])
    model = value["models"]["B3"]
    model["params"]["length_m"] += .01
    model["resource_content"]["params"] = deepcopy(model["params"])
    model["model_ref"] = digest({"kind": "MODEL", "value": model["resource_content"]})
    # The replacement has a valid self-hash, but no audited fitting output named it.
    with pytest.raises(EvidenceError):
        validate_bundle(value)


@pytest.mark.parametrize("content", ["[]", "null", '{"x":1,"x":2}', '{"x":NaN}', '{"x":1e999}', "{broken"])
def test_malformed_or_nonfinite_json_is_rejected(tmp_path, content):
    path = tmp_path / "evidence.json"
    path.write_text(content, encoding="utf-8")
    if content in ("[]", "null"):
        with pytest.raises(EvidenceError): validate_bundle(read_json(path))
    else:
        with pytest.raises(EvidenceError): read_json(path)


def test_sealed_file_is_denied_before_contents_are_opened(tmp_path, monkeypatch):
    path = tmp_path / "sealed" / "evidence.json"
    def forbidden(*args, **kwargs): raise AssertionError("A sealed resource was read")
    monkeypatch.setattr(Path, "read_text", forbidden)
    with pytest.raises(EvidenceError, match="unapproved"):
        read_json(path)


@pytest.mark.parametrize("name", ["../private.json", "sealed/evidence.json", "C:/private.json", ".env", "missing.txt"])
def test_catalog_paths_are_closed_and_do_not_open_arbitrary_files(product_root, name):
    index = read_json(product_root / "catalog.json")
    index["runs"][0]["file"] = name
    write_json(product_root / "catalog.json", index)
    with pytest.raises(EvidenceError, match="unapproved"):
        ProductStore(product_root)


def test_unknown_and_missing_records_fail_explicitly(product_root):
    store = ProductStore(product_root)
    with pytest.raises(EvidenceError, match="unknown"):
        store.run("unregistered")
    (product_root / "det-off-vertical.json").unlink()
    with pytest.raises(FileNotFoundError):
        store.run("det-off-vertical")


@pytest.mark.parametrize('entry',[None,[], 'invalid',{'id':False}])
def test_malformed_catalog_entries_are_evidence_errors(product_root,entry):
    index=read_json(product_root/'catalog.json'); index['runs']=[entry]
    write_json(product_root/'catalog.json',index)
    with pytest.raises(EvidenceError):ProductStore(product_root)


def test_original_agent_payloads_exclude_hidden_and_evaluation_data():
    trace = read_json(ROOT / "artifacts/task04/traces/deterministic_off_vertical_peg.json")
    validate_record(trace, "DETERMINISTIC")
    contexts = canonical([step["context"] for step in trace["steps"]]).decode()
    for marker in ("hidden_parameters", "ground_truth", "sealed_data", "label_post_freeze_only", "development"):
        assert marker not in contexts
    altered = deepcopy(trace)
    altered["tool_results"][0]["result"]["trajectory_rmse_px"] += .1
    with pytest.raises(EvidenceError): validate_record(altered, "DETERMINISTIC")
    altered = deepcopy(trace)
    altered["source"] = "LIVE_MUSE"
    with pytest.raises(EvidenceError): validate_record(altered, "DETERMINISTIC")


def test_external_source_is_distinct_and_not_a_physical_comparison():
    external = unavailable_external()
    assert validate_external(external)["track"] is None
    for field, value in (("observation_source", "REAL_PHONE"), ("physical_comparison_available", True)):
        altered = deepcopy(external); altered[field] = value
        with pytest.raises(EvidenceError): validate_external(altered)


@pytest.fixture
def http_server(product_root, tmp_path):
    media = tmp_path / "approved.mp4"
    media.write_bytes(b"SIMULATED_MEDIA_TEST_BYTES_ONLY")
    server = make_server(product_root, port=0, media={"external.mp4": media})
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try: yield server, media
    finally:
        server.shutdown(); server.server_close(); thread.join(timeout=3)
        assert not thread.is_alive()


def http_get(server, path, method="GET", headers=None):
    connection = http.client.HTTPConnection("127.0.0.1", server.server_port, timeout=5)
    try:
        connection.request(method, path, headers=headers or {})
        response = connection.getresponse()
        return response.status, dict(response.getheaders()), response.read()
    finally: connection.close()


def test_http_serves_verified_ui_and_evidence_without_starting_work(http_server):
    server, _ = http_server
    for path, expected in (("/", b"REALIGN"), ("/static/app.js", b"RECORDED_ARTIFACT"), ("/static/app.css", b"--ink")):
        status, headers, body = http_get(server, path)
        assert status == 200 and expected in body
        assert headers["X-Content-Type-Options"] == "nosniff"
        assert "connect-src 'self'" in headers["Content-Security-Policy"]
        assert headers["Cache-Control"] == "no-store"
    for path in ("/api/catalog", "/api/status", "/api/external", "/api/runs/det-off-vertical"):
        status, headers, body = http_get(server, path)
        assert status == 200 and "application/json" in headers["Content-Type"]
        assert isinstance(json.loads(body), dict)
    assert json.loads(http_get(server, "/api/external")[2])["observation_source"] == "REAL_EXTERNAL"


@pytest.mark.parametrize("path", ["/.env", "/api/runs/../../sealed/private", "/api/runs/%2e%2e%2fprivate", "/media/unapproved.mp4", "/unknown"])
def test_http_unknown_or_private_paths_never_expose_files(http_server, path):
    status, _, body = http_get(http_server[0], path)
    assert status == 404
    assert json.loads(body)["status"] == "NOT_FOUND"


def test_http_is_read_only_and_rejects_foreign_origins(http_server):
    server, _ = http_server
    assert http_get(server, "/api/catalog", method="POST")[0] == 405
    assert http_get(server, "/api/catalog", headers={"Host": "foreign.example"})[0] == 403
    assert http_get(server, "/api/catalog", headers={"Origin": "https://foreign.example"})[0] == 403


def test_http_missing_or_tampered_evidence_is_an_explicit_failure(http_server, product_root):
    server, _ = http_server
    path = product_root / "det-off-vertical.json"
    path.write_bytes(b"{}")
    status, _, body = http_get(server, "/api/runs/det-off-vertical")
    assert status == 422
    result = json.loads(body)
    assert result["status"] == "EVIDENCE_UNAVAILABLE"
    assert str(product_root) not in body.decode()
    path.unlink()
    assert http_get(server, "/api/runs/det-off-vertical")[0] == 422


def test_http_media_range_and_pinned_media_integrity(http_server):
    server, media = http_server
    status, headers, body = http_get(server, "/media/external.mp4", headers={"Range": "bytes=0-8"})
    assert status == 206 and body == b"SIMULATED"
    assert headers["Content-Range"].startswith("bytes 0-8/")
    assert http_get(server, "/media/external.mp4", headers={"Range": "bytes=99999-"})[0] == 416
    media.write_bytes(b"ALTERED_TEST_MEDIA")
    assert http_get(server, "/media/external.mp4")[0] == 422

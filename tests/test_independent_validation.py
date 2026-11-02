"""G5 synthetic fixtures and actual OS isolation. No API or real measurement.

Real-video shaped records below are explicitly protocol fixtures, not claimed
SAM outputs or physical observations. They test source/qualification rejection.
"""
from copy import deepcopy
from dataclasses import asdict, replace
import json
import os
from pathlib import Path

import numpy as np
import pytest
from pydantic import ValidationError as ContractError

from realign.audit.chain import canonical, digest
from realign.contracts import Experiment, NoiseConfig
from realign.contracts.video import (VideoMetadata, VideoObservation, VideoTrial, NoiseEstimate,
                                     PlanarCalibration, ReleaseEstimate)
from realign.fit.baselines import observation_fingerprint
from realign.physics import PendulumParams, PegParams
from realign.synth.generator import generate_trial
from realign.tools.resources import encode_trial, AccessDenied
from realign.tools.sandbox import WorkerClient, IsolationUnavailable
from realign.validation import (ValidationVault, ValidationError, GeometryMeasurements,
                                EvaluationProtocol, FrozenModel, verify_reveal)


PARAMS=PendulumParams(.72,gamma_per_s=.06,quadratic_drag_per_m=.02)


@pytest.fixture
def heldout():
    return tuple(generate_trial(PARAMS,Experiment(angle,.8,20.),seed=62000+i,
        trial_id="private-synthetic-"+str(i),noise=NoiseConfig(((.01,0.),(0.,.01))),zone="development")[0]
        for i,angle in enumerate((.45,.55)))


def geometry(params=PARAMS,method="SYNTHETIC_FIXTURE"):
    peg=params.peg
    return GeometryMeasurements(string_length_m=params.length_m,string_length_sigma_m=.001,
        peg_xy_m=(peg.distance_m*np.sin(peg.angle_rad),-peg.distance_m*np.cos(peg.angle_rad)) if peg else None,
        peg_sigma_m=(.001,.001) if peg else None,method=method,reference_ids=("INDEPENDENT_TEST_REFERENCE",))


def model_fixture(params=PARAMS,start=None):
    """Closed, hash-bound freeze fixture, not a claim of an executed agent fit."""
    resource={"family":"FREE" if params.peg is None else "PEG_ONE_SIDE","params":asdict(params),
              "role":"FITTED","training_refs":["a"*64],"budget_ref":"b"*64}
    freeze={"outcome":"CALIBRATE_PARAMETERS" if params.peg is None else "REPAIR_STRUCTURE",
            "model_ref":digest({"kind":"MODEL","value":resource}),"trial_refs":["a"*64],
            "protocol_ref":"c"*64,"proposal_accepted":True,"causal_mechanism_identified":False,
            "numerical_audit_head":"d"*64,"scope":"SYNTHETIC_TYPED_FREEZE_FIXTURE"}
    if start is not None:freeze['independent_start_receipt_sha256']=start['start_receipt_sha256']
    freeze["freeze_sha256"]=digest(freeze)
    return freeze,resource


def prepared(tmp_path,heldout,*,name="challenge",protocol=None):
    vault=ValidationVault(tmp_path/"vault")
    commitment=vault.prepare_challenge(name,heldout,geometry(),protocol=protocol)
    return vault,commitment


def frozen(vault,name="challenge"):
    start=vault.start_investigation(name)
    freeze,resource=model_fixture(start=start)
    return vault.freeze_model(name,freeze,resource,start_receipt=start)


def test_precommit_nonce_is_random_private_and_geometry_has_units(tmp_path,heldout,monkeypatch):
    import realign.validation.vault as module
    actual=module.secrets.token_bytes; requests=[]
    def recording(size): requests.append(size); return actual(size)
    monkeypatch.setattr(module.secrets,"token_bytes",recording)
    vault,commitment=prepared(tmp_path,heldout)
    secret=json.loads((vault.directory/"challenge.private.json").read_bytes())
    assert requests==[32] and len(bytes.fromhex(secret["nonce_hex"]))>=32
    public=canonical(commitment).decode()
    assert secret["nonce_hex"] not in public
    assert "string_length_m" not in public and "peg_xy_m" not in public
    assert "records" not in commitment and "geometry" not in commitment
    assert secret["geometry"]["length_unit"]=="m"
    if os.name!="nt":
        assert (vault.directory.stat().st_mode & 0o777)==0o700
        assert ((vault.directory/"challenge.private.json").stat().st_mode & 0o777)==0o600
    with pytest.raises(ValidationError): vault.reveal("challenge")
    with pytest.raises(ValidationError): vault.final_report("challenge")


def test_freeze_requires_start_and_hash_bound_original_model_resource(tmp_path,heldout):
    vault,_=prepared(tmp_path,heldout)
    freeze,resource=model_fixture()
    with pytest.raises(ValidationError,match="start"): vault.freeze_model("challenge",freeze,resource)
    start=vault.start_investigation("challenge")
    freeze,resource=model_fixture(start=start)
    wrong=deepcopy(resource); wrong["params"]["length_m"]+=.01
    with pytest.raises(ValidationError,match="freeze"): vault.freeze_model("challenge",freeze,wrong,start_receipt=start)
    bad=deepcopy(start); bad["start_receipt_sha256"]="f"*64
    with pytest.raises(ValidationError,match="receipt"): vault.freeze_model("challenge",freeze,resource,start_receipt=bad)
    model=vault.freeze_model("challenge",freeze,resource,start_receipt=start)
    assert model.public_receipt()["investigation_freeze_sha256"]==freeze["freeze_sha256"]
    exported=model.to_dict(); exported["model_resource"]["params"]["length_m"]=999
    assert model.to_dict()["model_resource"]["params"]["length_m"]==PARAMS.length_m
    with pytest.raises(Exception): model.canonical_payload=b"{}"
    with pytest.raises(ValidationError): vault.freeze_model("challenge",freeze,resource)
    with pytest.raises(ValidationError): vault.start_investigation("challenge")


def test_one_shot_predictive_scoring_then_valid_and_invalid_reveal(tmp_path,heldout):
    vault,commitment=prepared(tmp_path,heldout)
    model=frozen(vault)
    with pytest.raises(ValidationError): vault.reveal("challenge")
    result=vault.evaluate("challenge",model)
    assert result["status"]=="COMPLETED" and result["prediction_status"]=="PASS"
    assert 0<result["trajectory_rmse_px"]<.3
    assert result["domain"]=="SYNTHETIC" and result["causal_mechanism_identified"] is False
    assert result["position_unit"]=="px" and result["time_unit"]=="s"
    assert result["valid_samples"]==sum(int(t.observation.valid.sum()) for t in heldout)
    with pytest.raises(ValidationError,match="one-shot"): vault.evaluate("challenge",model)
    reveal=vault.reveal("challenge")
    assert verify_reveal(commitment,reveal)
    assert reveal["verdict"]=="SYNTHETIC_EXERCISE_PASS"
    assert reveal["full_physical_G5_passed"] is False
    for name in ("nonce","geometry","challenge","domain"):
        altered=deepcopy(reveal)
        if name=="nonce": altered["nonce_hex"]="0"*64
        elif name=="geometry": altered["geometry"]["string_length_m"]+=.01
        elif name=="challenge": altered["challenge_id"]="different"
        else: altered["domain"]="REAL_PHONE"
        assert not verify_reveal(commitment,altered)
    assert vault.final_report("challenge")["independent_verdict"]=="SYNTHETIC_EXERCISE_PASS"
    with pytest.raises(ValidationError): vault.reveal("challenge")


def test_spent_registry_blocks_aliases_overlaps_and_retuning_across_challenge_ids(tmp_path,heldout):
    vault,_=prepared(tmp_path,heldout,name="first")
    renamed=tuple(replace(t,trial_id="renamed-"+str(i)) for i,t in enumerate(heldout))
    # Register before the first evaluation to exercise the evaluate-time global guard.
    vault.prepare_challenge("second",renamed,geometry())
    first=frozen(vault,"first"); second=frozen(vault,"second")
    vault.evaluate("first",first)
    with pytest.raises(ValidationError,match="overlapping"): vault.evaluate("second",second)
    with pytest.raises(ValidationError,match="spent"): vault.prepare_challenge("third",renamed,geometry())
    assert [observation_fingerprint(t) for t in renamed]==[observation_fingerprint(t) for t in heldout]


def test_failed_prediction_is_sanitized_and_still_spends_holdout(tmp_path,heldout,monkeypatch):
    vault,_=prepared(tmp_path,heldout); model=frozen(vault)
    import realign.validation.vault as module
    def failure(*args): raise RuntimeError("PRIVATE_TEST_FAILURE_BODY")
    monkeypatch.setattr(module,"score_predictions",failure)
    result=vault.evaluate("challenge",model)
    assert result["status"]=="FAILED" and result["verdict"]=="INCONCLUSIVE"
    assert result["trajectory_rmse_px"] is None
    assert "PRIVATE_TEST_FAILURE_BODY" not in canonical(result).decode()
    with pytest.raises(ValidationError): vault.evaluate("challenge",model)
    assert vault.reveal("challenge")["verdict"]=="INCONCLUSIVE"


@pytest.mark.parametrize("negative,minimum",[(True,.3),(False,.7)])
def test_negative_controls_and_inadequate_excitation_are_inconclusive(tmp_path,heldout,negative,minimum):
    protocol=EvaluationProtocol(negative_control=negative,minimum_release_angle_rad=minimum)
    vault,_=prepared(tmp_path,heldout,protocol=protocol)
    result=vault.evaluate("challenge",frozen(vault))
    assert result["verdict"]=="INCONCLUSIVE"
    assert vault.reveal("challenge")["verdict"]=="INCONCLUSIVE"


def test_independent_scores_reproduce_from_same_frozen_params_without_refitting(tmp_path,heldout,monkeypatch):
    import realign.fit.robust_fit as free
    import realign.fit.peg_fit as peg
    def forbidden(*args,**kwargs): raise AssertionError("Independent evaluation must not fit")
    monkeypatch.setattr(free,"fit_free",forbidden); monkeypatch.setattr(peg,"fit_peg",forbidden)
    results=[]
    for name in ("first","second"):
        vault=ValidationVault(tmp_path/name/"vault")
        vault.prepare_challenge(name,heldout,geometry())
        results.append(vault.evaluate(name,frozen(vault,name)))
    # Distinct vaults are independent local exercises, not a loophole within a
    # trusted deployment. A hostile operator replacing its vault is out of scope.
    assert results[0]["trajectory_rmse_px"]==results[1]["trajectory_rmse_px"]
    assert results[0]["per_trial"]==results[1]["per_trial"]


@pytest.mark.parametrize("target",["private","frozen","ledger","evaluation"])
def test_tampering_fails_closed_at_each_immutable_boundary(tmp_path,heldout,target):
    vault,_=prepared(tmp_path,heldout); model=frozen(vault)
    if target=="ledger":
        rows=vault.ledger_path.read_text().splitlines(); item=json.loads(rows[0]); item["payload"]["utc_ns"]+=1
        rows[0]=json.dumps(item); vault.ledger_path.write_text("\n".join(rows)+"\n")
    elif target=="evaluation":
        vault.evaluate("challenge",model)
        path=vault.directory/"challenge.evaluation.json"; item=json.loads(path.read_bytes()); item["trajectory_rmse_px"]=0.
        path.write_bytes(canonical(item))
    else:
        path=vault.directory/("challenge."+target+".json"); item=json.loads(path.read_bytes())
        if target=="private": item["nonce_hex"]="0"*64
        else: item["model_resource"]["params"]["length_m"]+=.01
        path.write_bytes(canonical(item))
    with pytest.raises(ValidationError):
        vault.reveal("challenge") if target=="evaluation" else vault.evaluate("challenge",model)


def test_development_never_enters_agent_capabilities_and_exploration_overlap_rejected(tmp_path,heldout):
    for trial in heldout:
        with pytest.raises(AccessDenied): encode_trial(trial)
    vault=ValidationVault(tmp_path/"vault")
    with pytest.raises(ValidationError,match="overlap"):
        vault.prepare_challenge("overlap",heldout,geometry(),exploration_fingerprints=(observation_fingerprint(heldout[0]),))
    with pytest.raises(ValidationError,match="development"):
        vault.prepare_challenge("wrong-zone",[replace(t,zone="exploration") for t in heldout],geometry())
    with pytest.raises(ValidationError,match="domain"):
        vault.prepare_challenge("fake-phone",heldout,geometry(method="INDEPENDENT_PHYSICAL_MEASUREMENT"),domain="REAL_PHONE")


def real_video_contract_fixture(trial):
    """REAL-shaped schema fixture ONLY; no actual API or physical claim is made."""
    n=len(trial.observation.t_s)
    metadata=VideoMetadata("e"*64,"REAL_PHONE",1280,720,1280,720,tuple(range(n)),"1/20","PROTOCOL_FIXTURE")
    noise=NoiseEstimate(((.01,0.),(0.,.01)),(0.,0.),0.,.05,("SIMULATED_SCHEMA_STATIONARY",),"REAL_SAM","PROTOCOL_FIXTURE_ONLY")
    calibration=PlanarCalibration("SCHEMA_FIXTURE",((600.,0.,640.),(0.,-600.,160.),(0.,0.,1.)),(1280,720),(640.,160.),0.,0.,"REAL_MEASURED",4,4)
    observation=VideoObservation("SCHEMA_FIXTURE_RECORDING",metadata,trial.observation.xy_px,trial.observation.valid,
        np.tile(np.eye(2)*.01,(n,1,1)),np.zeros(n,dtype=np.uint32),noise,calibration.calibration_id,"REAL_SAM","REAL_API")
    return VideoTrial(observation.recording_id,trial.experiment,observation,calibration,ReleaseEstimate(.075,.01,.05,.1,"PROTOCOL_FIXTURE"),"development")


def test_real_phone_contracts_cannot_be_mixed_with_synthetic_and_need_independent_qualification(tmp_path,heldout):
    video=real_video_contract_fixture(heldout[0]); vault=ValidationVault(tmp_path/"vault")
    with pytest.raises(ValidationError,match="domain"):
        vault.prepare_challenge("mixed",(heldout[0],video),geometry())
    vault.prepare_challenge("real-schema",(video,),geometry(method="INDEPENDENT_PHYSICAL_MEASUREMENT"),domain="REAL_PHONE",
                            protocol=EvaluationProtocol(minimum_trials=1))
    result=vault.evaluate("real-schema",frozen(vault,"real-schema"))
    assert result["verdict"]=="INCONCLUSIVE"
    assert "INDEPENDENT_MANUAL_REVIEW_VERIFIED" in result["blockers"]
    assert "STATIONARY_NOISE_MEASURED" in result["blockers"]
    assert vault.reveal("real-schema")["full_physical_G5_passed"] is False


def test_geometry_contract_rejects_implicit_units_unknown_truth_and_zero_physical_uncertainty():
    base=geometry().model_dump(mode="json")
    for extra in ({"length_unit":"px"},{"ground_truth":{}},{"method":"INDEPENDENT_PHYSICAL_MEASUREMENT","string_length_sigma_m":0.}):
        with pytest.raises(ContractError): GeometryMeasurements.model_validate_json(canonical(dict(base,**extra)))


def test_preexisting_freeze_cannot_be_relabelled_as_new_blind_investigation(tmp_path,heldout):
    vault,_=prepared(tmp_path,heldout)
    old_freeze,old_resource=model_fixture()
    start=vault.start_investigation('challenge')
    with pytest.raises(ValidationError,match='bound'):
        vault.freeze_model('challenge',old_freeze,old_resource,start_receipt=start)


def test_synthetic_reproduction_records_are_unavailable_until_reveal(tmp_path,heldout):
    vault,_=prepared(tmp_path,heldout)
    with pytest.raises(ValidationError):vault.export_revealed_synthetic_records('challenge')
    vault.evaluate('challenge',frozen(vault))
    with pytest.raises(ValidationError):vault.export_revealed_synthetic_records('challenge')
    vault.reveal('challenge')
    records=vault.export_revealed_synthetic_records('challenge')
    assert records and all(r['trial']['zone']=='development' for r in records)
    with pytest.raises(ValidationError):vault.evaluate('challenge',frozen(vault))


def test_video_source_reuse_is_rejected_even_after_changed_windows_or_centers(tmp_path,heldout):
    vault=ValidationVault(tmp_path/'vault')
    original=real_video_contract_fixture(heldout[0])
    changed=replace(original,observation=replace(original.observation,xy_px=original.observation.xy_px+1.))
    for ident,t in [('first',original),('second',changed)]:
        vault.prepare_challenge(ident,[t],geometry(method='INDEPENDENT_PHYSICAL_MEASUREMENT'),domain='REAL_PHONE',
                                protocol=EvaluationProtocol(minimum_trials=1))
    with pytest.raises(ValidationError,match='recording'):
        vault.assert_exploration_disjoint('first',[replace(changed,zone='exploration')])
    vault.evaluate('first',frozen(vault,'first'))
    with pytest.raises(ValidationError,match='overlapping'):
        vault.evaluate('second',frozen(vault,'second'))


@pytest.mark.skipif(os.name=="nt",reason="Actual vault denial uses existing Linux/WSL Landlock runtime; native Windows fails closed")
def test_actual_worker_cannot_read_nonce_geometry_heldout_or_ledger(tmp_path,heldout):
    vault,commitment=prepared(tmp_path,heldout)
    with WorkerClient(timeout_s=120) as worker:
        proof=vault.prove_agent_file_isolation("challenge",worker)
        assert proof["status"]=="PASS"
        assert proof["private_nonce_geometry_file_denied"] and proof["private_heldout_file_denied"]
        assert all(proof["checks"]["filesystem_denied"])
        # A path supplied as a scientific call cannot become a file-read tool.
        with pytest.raises(ValueError):
            worker.request({"command":"open_file","path":str(vault.directory/"challenge.private.json")})
    assert "nonce_hex" not in canonical(commitment).decode()


@pytest.mark.skipif(os.name!="nt",reason="Native Windows isolation fail-closed branch")
def test_native_windows_cannot_substitute_an_unisolated_worker():
    with pytest.raises(IsolationUnavailable): WorkerClient(timeout_s=1)

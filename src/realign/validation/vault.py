"""Local independent-validation custodian, outside the investigator/tool API.

This is one application module, not an additional agent or service. The trusted
host owns the vault and invokes evaluation only after freeze. Existing Landlock/
seccomp workers cannot read its files, import this package, or request evaluation.
Local sequence/hash records do not provide external timestamp attestation or
protection against a host administrator deleting/replacing the whole vault.
"""
from contextlib import contextmanager
from dataclasses import asdict, replace
import hmac
import json
import math
import os
from pathlib import Path
import re
import secrets
import time

from realign.audit.chain import canonical, digest, AuditChain
from realign.contracts import Trial
from realign.contracts.video import VideoTrial
from realign.fit.baselines import observation_fingerprint
from realign.tools.registry import parameters
from realign.tools.resources import encode_trial
from .contracts import GeometryMeasurements, EvaluationProtocol, RealQualification, FrozenModel
from .scoring import serialize_heldout, deserialize_heldout, score_predictions


class ValidationError(ValueError):
    pass


def _typed(cls, value):
    try:
        return value if type(value) is cls else cls.model_validate_json(canonical(value))
    except (TypeError, ValueError):
        raise ValidationError("invalid typed independent-validation contract") from None


def _domain(trial):
    if type(trial) is Trial and trial.observation.provenance=="SYNTHETIC": return "SYNTHETIC"
    if type(trial) is VideoTrial:
        o=trial.observation; source=o.metadata.source_kind
        if source=="SYNTHETIC_RENDER" and o.provenance=="SYNTHETIC": return "SYNTHETIC"
        if (source in ("REAL_PHONE","REAL_EXTERNAL") and o.provenance=="REAL_SAM" and
                o.sam_source=="REAL_API" and trial.projection.source=="REAL_MEASURED" and
                o.noise.provenance=="REAL_SAM" and trial.release.sigma_s>0): return source
    raise ValidationError("heldout lacks compatible physical/synthetic provenance")


from realign.audit.public_validation import _commitment,verify_reveal


class ValidationVault:
    def __init__(self, directory):
        self.directory=Path(directory).resolve()
        if any(part.startswith("realign-numerics-") for part in self.directory.parts):
            raise ValidationError("vault must be outside the numerical worker runtime")
        self.directory.mkdir(parents=True,exist_ok=True,mode=0o700)
        if os.name!="nt": self.directory.chmod(0o700)
        self.ledger_path=self.directory/"ledger.jsonl"

    @staticmethod
    def _id(value):
        if not isinstance(value,str) or not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,63}",value):
            raise ValidationError("bounded opaque challenge identity required")
        return value

    def _path(self, ident, suffix):
        return self.directory/(self._id(ident)+suffix)

    @contextmanager
    def _locked(self):
        path=self.directory/"ledger.lock"
        try: descriptor=os.open(path,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
        except FileExistsError: raise ValidationError("validation ledger is busy; no concurrent evaluation permitted") from None
        try:
            os.close(descriptor)
            yield
        finally: path.unlink(missing_ok=True)

    def _events(self):
        if not self.ledger_path.exists(): return []
        try:
            events=[json.loads(line) for line in self.ledger_path.read_text(encoding="utf-8").splitlines()]
            if not AuditChain.verify(events): raise ValueError
            head=self.directory/'ledger.head.json'
            if head.exists():
                expected=json.loads(head.read_text(encoding='utf-8'))
                if expected!={'events':len(events),'hash':events[-1]['hash'] if events else '0'*64}:raise ValueError
            return events
        except (KeyError,TypeError,ValueError):
            raise ValidationError("independent validation ledger integrity failed") from None

    def _append(self, kind, ident, payload):
        events=self._events()
        event={"sequence":len(events),"kind":kind,"payload":{"challenge_id":ident,"utc_ns":time.time_ns(),**payload},
               "previous":events[-1]["hash"] if events else "0"*64}
        event["hash"]=digest(event)
        descriptor=os.open(self.ledger_path,os.O_WRONLY|os.O_APPEND|os.O_CREAT,0o600)
        with os.fdopen(descriptor,"ab") as file:
            file.write(canonical(event)+b"\n"); file.flush(); os.fsync(file.fileno())
        # New sidecar detects prefix truncation, which a valid hash chain alone
        # cannot detect. Legacy v1 ledgers without it remain readable. A crash
        # between writes fails closed; the trusted custodian must investigate.
        head=self.directory/'ledger.head.json';temporary=head.with_suffix('.tmp')
        descriptor=os.open(temporary,os.O_WRONLY|os.O_CREAT|os.O_TRUNC,0o600)
        with os.fdopen(descriptor,'wb') as file:
            file.write(canonical({'events':len(events)+1,'hash':event['hash']}));file.flush();os.fsync(file.fileno())
        os.replace(temporary,head)
        return event

    @staticmethod
    def _write_new(path, value):
        try: descriptor=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
        except FileExistsError: raise ValidationError("immutable validation resource already exists") from None
        with os.fdopen(descriptor,"wb") as file:
            file.write(canonical(value)); file.flush(); os.fsync(file.fileno())

    def _read(self, ident, suffix):
        try:
            value=json.loads(self._path(ident,suffix).read_text(encoding="utf-8"))
            canonical(value)
            return value
        except (FileNotFoundError,TypeError,ValueError):
            raise ValidationError("required private validation resource is missing or malformed") from None

    def _challenge_events(self, ident):
        return [e for e in self._events() if e["payload"]["challenge_id"]==ident]

    def _prepared(self, ident):
        rows=self._challenge_events(self._id(ident))
        if not rows or rows[0]["kind"]!="PREPARED": raise ValidationError("challenge was not committed before investigation")
        return rows

    def prepare_challenge(self, challenge_id, heldout_trials, geometry, *, domain="SYNTHETIC", protocol=None,
                          exploration_fingerprints=(), qualification=None):
        ident=self._id(challenge_id); geometry=_typed(GeometryMeasurements,geometry)
        protocol=_typed(EvaluationProtocol,protocol or EvaluationProtocol())
        qualification=_typed(RealQualification,qualification or RealQualification())
        trials=tuple(heldout_trials)
        if domain not in ("SYNTHETIC","REAL_PHONE","REAL_EXTERNAL") or not trials or len(trials)>32:
            raise ValidationError("explicit domain and bounded nonempty heldout set required")
        if any(_domain(t)!=domain for t in trials): raise ValidationError("challenge domain differs from heldout provenance")
        expected="SYNTHETIC_FIXTURE" if domain=="SYNTHETIC" else "INDEPENDENT_PHYSICAL_MEASUREMENT"
        if geometry.method!=expected: raise ValidationError("geometry measurement source differs from challenge domain")
        fingerprints=[observation_fingerprint(t) for t in trials]
        video_hashes=[t.observation.metadata.video_sha256 for t in trials if type(t) is VideoTrial]
        if len(set(video_hashes))!=len(video_hashes):
            raise ValidationError('heldout must contain disjoint source recordings')
        if len(set(fingerprints))!=len(fingerprints) or set(fingerprints).intersection(exploration_fingerprints):
            raise ValidationError("heldout observations overlap exploration or one another")
        try:
            records=[serialize_heldout(t) for t in trials]
        except ValueError as exc:
            raise ValidationError(str(exc)) from None
        agent_refs=[digest({"kind":"TRIAL","value":encode_trial(replace(t,zone="exploration"))}) for t in trials]
        dataset=digest(sorted(fingerprints)); nonce=secrets.token_bytes(32).hex()
        public={"schema_version":"1.0","challenge_id":ident,"domain":domain,
                "heldout_dataset_sha256":dataset,"protocol":protocol.model_dump(mode="json"),
                "commitment_sha256":_commitment(ident,domain,dataset,protocol.model_dump(mode="json"),geometry.model_dump(mode="json"),nonce),
                "scope":"SYNTHETIC_BLIND_WORKFLOW_EXERCISE" if domain=="SYNTHETIC" else "REAL_INDEPENDENT_VALIDATION_PENDING",
                "chronology":"LOCAL_ORDER_ENFORCED; NOT EXTERNAL TIMESTAMP ATTESTATION"}
        private={"public":public,"geometry":geometry.model_dump(mode="json"),"nonce_hex":nonce,
                 "records":records,"fingerprints":fingerprints,"agent_refs":agent_refs,
                 "source_video_hashes":video_hashes,"consumption_tokens":fingerprints+['video:'+x for x in video_hashes],
                 "qualification":qualification.model_dump(mode="json")}
        with self._locked():
            if self._challenge_events(ident): raise ValidationError("challenge identity already committed")
            used={fp for event in self._events() if event["kind"]=="EVALUATION_SPENT" for fp in event["payload"]["heldout_fingerprints"]}
            if used.intersection(private['consumption_tokens']): raise ValidationError("heldout was already spent by another challenge")
            self._write_new(self._path(ident,".private.json"),private)
            self._append("PREPARED",ident,{"commitment":public,"private_sha256":digest(private)})
        return json.loads(canonical(public))

    def assert_exploration_disjoint(self,challenge_id,trials):
        """Custodian-only check before admitting observations; returns no heldout content."""
        rows=self._prepared(challenge_id);private=self._private(challenge_id,rows)
        for t in trials:
            if observation_fingerprint(t) in private['fingerprints']:
                raise ValidationError('exploration overlaps the committed holdout')
            if type(t) is VideoTrial and t.observation.metadata.video_sha256 in private.get('source_video_hashes',[]):
                raise ValidationError('exploration reuses a committed source recording, including a different window')
        return {'disjoint':True,'scope':'CUSTODIAN_SOURCE_AND_OBSERVATION_CHECK; NO HELDOUT_CONTENT'}

    def start_investigation(self, challenge_id):
        with self._locked():
            rows=self._prepared(challenge_id)
            if len(rows)!=1: raise ValidationError("investigation start is one-shot and must precede model freeze")
            event=self._append("INVESTIGATION_STARTED",challenge_id,{"commitment_sha256":rows[0]["payload"]["commitment"]["commitment_sha256"]})
        return {"challenge_id":challenge_id,"commitment_sha256":event["payload"]["commitment_sha256"],
                "start_receipt_sha256":event["hash"],"sequence":event["sequence"],"scope":"PUBLIC_PRE_INVESTIGATION_RECEIPT"}

    def _private(self, ident, rows):
        value=self._read(ident,".private.json")
        if digest(value)!=rows[0]["payload"]["private_sha256"]: raise ValidationError("private challenge content changed after commitment")
        return value

    def _frozen(self, ident, rows):
        value=self._read(ident,".frozen.json")
        expected=next((e["payload"]["content_sha256"] for e in rows if e["kind"]=="MODEL_FROZEN"),None)
        if expected is None or FrozenModel(canonical(value)).content_sha256!=expected:
            raise ValidationError("immutable frozen model content changed")
        return value

    def freeze_model(self, challenge_id, investigation_freeze, model_resource, *, start_receipt=None):
        # The full original MODEL capability is mandatory. A parameter dictionary
        # alone cannot prove which model the investigation actually froze.
        try:
            frozen=json.loads(canonical(investigation_freeze)); resource=json.loads(canonical(model_resource))
            expected=frozen.pop("freeze_sha256")
            if digest(frozen)!=expected: raise ValueError
            frozen["freeze_sha256"]=expected
            if (frozen["proposal_accepted"] is not True or frozen["outcome"] not in ("KEEP_UNCHANGED","CALIBRATE_PARAMETERS","REPAIR_STRUCTURE") or
                    frozen["causal_mechanism_identified"] is not False or resource["family"] not in ("FREE","PEG_ONE_SIDE") or
                    digest({"kind":"MODEL","value":resource})!=frozen["model_ref"]): raise ValueError
            params=parameters(resource["params"])
            if any(type(resource["params"][name]) not in (int,float) for name in
                   ("length_m","g","gamma_per_s","quadratic_drag_per_m")): raise ValueError
            if asdict(params)!=resource["params"] or (params.peg is None)!=(resource["family"]=="FREE"): raise ValueError
            if params.peg is not None and (params.peg.contact_side!=-1 or params.peg.kappa_in!=1 or params.peg.kappa_out!=1): raise ValueError
            if set(resource["training_refs"])-set(frozen["trial_refs"]): raise ValueError
        except (KeyError,TypeError,ValueError): raise ValidationError("model export does not match immutable investigation freeze") from None
        with self._locked():
            rows=self._prepared(challenge_id)
            if [e["kind"] for e in rows]!=["PREPARED","INVESTIGATION_STARTED"]:
                raise ValidationError("model freeze requires a fresh precommitted investigation start")
            if start_receipt is None or start_receipt.get("start_receipt_sha256")!=rows[1]["hash"]:
                raise ValidationError("investigation start receipt mismatch")
            if frozen.get('independent_start_receipt_sha256')!=rows[1]['hash']:
                raise ValidationError('investigation freeze is not bound to this pre-investigation start receipt')
            private=self._private(challenge_id,rows)
            if set(private["agent_refs"]).intersection(set(frozen["trial_refs"])|set(resource["training_refs"])):
                raise ValidationError("frozen model training references include heldout observations")
            payload={"schema_version":"1.0","challenge_id":challenge_id,
                     "commitment_sha256":private["public"]["commitment_sha256"],"start_receipt_sha256":rows[1]["hash"],
                     "investigation_freeze":frozen,"model_resource":resource}
            model=FrozenModel(canonical(payload))
            self._write_new(self._path(challenge_id,".frozen.json"),payload)
            self._append("MODEL_FROZEN",challenge_id,{"content_sha256":model.content_sha256,"freeze_sha256":expected})
        return model

    def evaluate(self, challenge_id, frozen_model):
        if type(frozen_model) is not FrozenModel: raise ValidationError("immutable FrozenModel required")
        with self._locked():
            rows=self._prepared(challenge_id)
            if [e["kind"] for e in rows]!=["PREPARED","INVESTIGATION_STARTED","MODEL_FROZEN"]:
                raise ValidationError("heldout evaluation is one-shot, after model freeze only")
            private=self._private(challenge_id,rows); saved=self._frozen(challenge_id,rows)
            if (frozen_model.to_dict()!=saved or frozen_model.content_sha256!=rows[-1]["payload"]["content_sha256"]):
                raise ValidationError("frozen model was altered or belongs to another challenge")
            used={fp for e in self._events() if e["kind"]=="EVALUATION_SPENT" for fp in e["payload"]["heldout_fingerprints"]}
            tokens=private.get('consumption_tokens',private['fingerprints'])
            if used.intersection(tokens): raise ValidationError("overlapping holdout already evaluated; no retuning or re-evaluation")
            # Persist consumption BEFORE predictions. Failures/crashes also spend
            # the set and cannot become an adaptive second look.
            spent=self._append("EVALUATION_SPENT",challenge_id,{"heldout_fingerprints":tokens,
                                "model_content_sha256":frozen_model.content_sha256})
        protocol=_typed(EvaluationProtocol,private["public"]["protocol"])
        domain=private["public"]["domain"]
        try:
            trials=[deserialize_heldout(record) for record in private["records"]]
            result=score_predictions(parameters(saved["model_resource"]["params"]),trials,protocol)
            result.update(status="COMPLETED")
        except Exception as exc:
            result={"status":"FAILED","prediction_status":"INCONCLUSIVE","trajectory_rmse_px":None,
                    "innovation_mean_square":None,"blockers":["PREDICTION_FAILED"],"error_type":type(exc).__name__}
        blockers=list(result["blockers"])
        if protocol.negative_control: blockers.append("NEGATIVE_CONTROL_NO_DISCOVERY_VERDICT")
        if domain!="SYNTHETIC": blockers.extend(_typed(RealQualification,private["qualification"]).blockers())
        if domain=="REAL_EXTERNAL": blockers.append("EXTERNAL_RECORDING_NOT_CONTROLLED_PHONE_VALIDATION")
        result.update(schema_version="1.0",challenge_id=challenge_id,domain=domain,
                      frozen_model_sha256=frozen_model.content_sha256,holdout_spent_receipt=spent["hash"],
                      blockers=sorted(set(blockers)),causal_mechanism_identified=False,
                      verdict="INCONCLUSIVE" if blockers else domain+"_PREDICTIVE_"+result["prediction_status"],
                      scope="INDEPENDENT_ONE_SHOT_POST_FREEZE_PREDICTION; NO FITTING")
        result["evaluation_sha256"]=digest(result)
        with self._locked():
            self._write_new(self._path(challenge_id,".evaluation.json"),result)
            self._append("EVALUATION_RECORDED",challenge_id,{"evaluation_sha256":result["evaluation_sha256"]})
        return json.loads(canonical(result))

    def reveal(self, challenge_id):
        with self._locked():
            rows=self._prepared(challenge_id)
            if rows[-1]["kind"]!="EVALUATION_RECORDED":
                raise ValidationError("nonce/geometry reveal requires completed one-shot evaluation after freeze")
            private=self._private(challenge_id,rows)
            result=self._read(challenge_id,".evaluation.json")
            evaluation_hash=result.pop("evaluation_sha256")
            if digest(result)!=evaluation_hash or evaluation_hash!=rows[-1]["payload"]["evaluation_sha256"]:
                raise ValidationError("independent evaluation content changed")
            result["evaluation_sha256"]=evaluation_hash
            saved=self._frozen(challenge_id,rows)
            model=parameters(saved["model_resource"]["params"])
            geometry=_typed(GeometryMeasurements,private["geometry"])
            protocol=_typed(EvaluationProtocol,private["public"]["protocol"])
            length_error=abs(model.length_m-geometry.string_length_m)
            peg_error=None
            if model.peg is not None and geometry.peg_xy_m is not None:
                xy=(model.peg.distance_m*math.sin(model.peg.angle_rad),-model.peg.distance_m*math.cos(model.peg.angle_rad))
                peg_error=math.dist(xy,geometry.peg_xy_m)
            same_structure=(model.peg is None)==(geometry.peg_xy_m is None)
            consistent=same_structure and length_error<=protocol.length_tolerance_m and (peg_error is None or peg_error<=protocol.peg_position_tolerance_m)
            inconclusive=bool(result["blockers"]) or result["prediction_status"]=="INCONCLUSIVE"
            domain=private["public"]["domain"]
            verdict="INCONCLUSIVE" if inconclusive else ("SYNTHETIC_EXERCISE_PASS" if domain=="SYNTHETIC" else "REAL_PHONE_CONSISTENCY_PASS") if consistent and result["prediction_status"]=="PASS" else domain+"_VALIDATION_FAIL"
            reveal={"schema_version":"1.0","challenge_id":challenge_id,"domain":domain,
                    "nonce_hex":private["nonce_hex"],"geometry":private["geometry"],
                    "evaluation_sha256":evaluation_hash,"geometry_comparison":{"length_error_m":length_error,
                    "peg_position_error_m":peg_error,"structure_consistent":same_structure,"within_preregistered_tolerances":consistent},
                    "verdict":verdict,"causal_mechanism_identified":False,
                    "full_physical_G5_passed":False,
                    "limitation":"Local ordering only; consistency does not establish unique physical discovery."}
            if not verify_reveal(private["public"],reveal): raise ValidationError("blind reveal does not match original commitment")
            self._write_new(self._path(challenge_id,".reveal.json"),reveal)
            self._append("REVEALED",challenge_id,{"reveal_sha256":digest(reveal)})
        return json.loads(canonical(reveal))

    def final_report(self, challenge_id):
        rows=self._prepared(challenge_id)
        if rows[-1]["kind"]!="REVEALED": raise ValidationError("public final report requires gated reveal")
        reveal=self._read(challenge_id,".reveal.json")
        if digest(reveal)!=rows[-1]["payload"]["reveal_sha256"]: raise ValidationError("revealed report changed")
        saved=self._frozen(challenge_id,rows)
        evaluation=self._read(challenge_id,".evaluation.json")
        value=dict(evaluation); expected=value.pop("evaluation_sha256")
        if digest(value)!=expected or expected!=reveal["evaluation_sha256"]:
            raise ValidationError("independent evaluation content changed")
        return {"schema_version":"1.0","scope":"POST_FREEZE_POST_EVALUATION_PUBLIC_REPORT",
                "commitment":rows[0]["payload"]["commitment"],
                "frozen_model":FrozenModel(canonical(saved)).public_receipt(),
                "evaluation":evaluation,"reveal":reveal,
                "independent_verdict":reveal["verdict"],"full_physical_G5_passed":False,
                "ledger_head":rows[-1]["hash"]}

    def prove_agent_file_isolation(self, challenge_id, worker):
        """Actual existing-worker OS probe, not a Python filename convention.

        The probe attempts open/read on the real private nonce/geometry file and
        ledger, plus the existing network/memory/write/environment assertions.
        It returns booleans only, never file content, nonce or geometry.
        """
        self._prepared(challenge_id)
        from realign.tools.sandbox import WorkerClient
        if type(worker) is not WorkerClient: raise ValidationError("existing isolated WorkerClient required")
        outcome=worker.request({"command":"probe","paths":[str(self._path(challenge_id,".private.json")),str(self.ledger_path)]})
        if not all(outcome["filesystem_denied"]) or not all(v for k,v in outcome.items() if k!="filesystem_denied"):
            raise ValidationError("vault is accessible to the investigator numerical worker")
        return {"status":"PASS","isolation":worker.isolation,"private_nonce_geometry_file_denied":True,
                "private_heldout_file_denied":True,"ledger_denied":True,"checks":outcome,
                "scope":"ACTUAL_OS_FILE_ACCESS_PROBE; NO SECRET CONTENT RETURNED"}

    def export_revealed_synthetic_records(self, challenge_id):
        """Optional public reproduction material, only after the gated reveal.

        Real recordings are never released by this convenience method. Export
        cannot change, repeat, or undo the spent evaluation.
        """
        report=self.final_report(challenge_id)
        if report['commitment']['domain']!='SYNTHETIC':
            raise ValidationError('automatic reproduction export is synthetic only')
        return self._private(challenge_id,self._prepared(challenge_id))['records']

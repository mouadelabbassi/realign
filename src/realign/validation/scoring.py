"""Independent forward prediction only. No optimizer, model selection or tuning."""
from dataclasses import asdict, replace
import numpy as np
from realign.audit.chain import digest
from realign.contracts import Trial
from realign.contracts.video import VideoTrial
from realign.fit.robust_fit import predict_free, residuals_free
from realign.fit.peg_fit import predict_peg, residuals_peg
from realign.tools.registry import parameters
from realign.tools.resources import _clean, decode_trial


def serialize_heldout(trial):
    if type(trial) not in (Trial, VideoTrial) or trial.zone != "development":
        raise ValueError("only dedicated development contracts may enter the private heldout vault")
    if len(trial.observation.t_s)>256 or trial.experiment.duration_s>4:
        raise ValueError("heldout exceeds the existing bounded trajectory domain")
    return {"kind": "VIDEO" if type(trial) is VideoTrial else "DIRECT", "trial": _clean(asdict(trial))}


def deserialize_heldout(record):
    """Compatibility adapter, used only inside the post-freeze evaluator.

    Existing trial decoding accepts exploration envelopes only. A private copy
    is decoded and immediately restored to development; it is never registered
    with ScientificSession, ResourceStore, or an agent-facing tool.
    """
    from copy import deepcopy
    value = deepcopy(record)
    if value.get("trial", {}).get("zone") != "development":
        raise ValueError("private heldout zone required")
    value["trial"]["zone"] = "exploration"
    return replace(decode_trial(value), zone="development")


def score_predictions(params, trials, protocol):
    predict = predict_peg if params.peg is not None else predict_free
    residuals = residuals_peg if params.peg is not None else residuals_free
    rows=[]; squared=[]; all_valid=0; all_samples=0; blockers=[]
    for trial in trials:
        observation=trial.observation; valid=observation.valid
        prediction=predict(params, trial)
        count=int(valid.sum()); n=len(valid); all_valid+=count; all_samples+=n
        error=np.sum((prediction[valid]-observation.xy_px[valid])**2, axis=1)
        if not np.isfinite(prediction).all() or not np.isfinite(error).all():
            raise ValueError("nonfinite independent prediction")
        squared.extend(error.tolist())
        rows.append({"trial_id":trial.trial_id,"valid_samples":count,"samples":n,
                     "trajectory_rmse_px":float(np.sqrt(np.mean(error))) if count else None,
                     "prediction_sha256":digest(prediction.tolist()),
                     "timestamps_sha256":digest(observation.t_s.tolist())})
        if count<protocol.minimum_valid_samples_per_trial: blockers.append("INSUFFICIENT_VALID_SAMPLES")
    if len(trials)<protocol.minimum_trials: blockers.append("INSUFFICIENT_HELDOUT_TRIALS")
    missing=1-all_valid/all_samples if all_samples else 1.
    if missing>protocol.maximum_missing_fraction: blockers.append("EXCESS_MISSING_OBSERVATIONS")
    if max((abs(t.experiment.release_angle_rad) for t in trials),default=0)<protocol.minimum_release_angle_rad:
        blockers.append("INSUFFICIENT_EXCITATION")
    rms=float(np.sqrt(np.mean(squared))) if squared else None
    innovations=residuals(params, trials) if all_valid else np.array([])
    return {"trajectory_rmse_px":rms,"innovation_mean_square":float(np.mean(innovations**2)) if len(innovations) else None,
            "aggregation":"POOLED_VALID_XY_EUCLIDEAN_RMS","position_unit":"px","time_unit":"s",
            "valid_samples":all_valid,"missing_fraction":missing,"per_trial":rows,
            "prediction_status":"INCONCLUSIVE" if blockers or rms is None else "PASS" if rms<=protocol.max_trajectory_rmse_px else "FAIL",
            "blockers":sorted(set(blockers))}

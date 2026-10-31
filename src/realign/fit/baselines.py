"""Disjoint whole-trial comparison. Development scores never enter fitting."""
from dataclasses import asdict
import hashlib
import numpy as np
from realign.observation.noise import whiten,whiten_video
from realign.observation.camera import unproject
from realign.contracts.video import VideoTrial
from .robust_fit import FitError, FitOptions, fit_free, predict_free
from .circle_fit import fit_geometry, score_geometry


def observation_fingerprint(trial):
    h = hashlib.sha256()
    for a in (trial.observation.t_s, trial.observation.xy_px, trial.observation.valid):
        h.update(np.ascontiguousarray(a).tobytes())
    return h.hexdigest()


def check_split(training, heldout):
    if not training or not heldout:
        raise ValueError('nonempty disjoint training and development trials required')
    all_trials = tuple(training)+tuple(heldout)
    if len({t.observation.provenance for t in all_trials})!=1:
        raise ValueError('cannot mix synthetic and real comparisons')
    if any(isinstance(t,VideoTrial) for t in all_trials):
        if not all(isinstance(t,VideoTrial) for t in all_trials):
            raise ValueError('video and direct synthetic observations require separate comparisons')
        if any(t.zone!='exploration' for t in training) or any(t.zone!='development' for t in heldout):
            raise ValueError('video fitting uses exploration; heldout scoring uses disjoint development recordings')
        if len({t.observation.metadata.video_sha256 for t in all_trials})!=len(all_trials):
            raise ValueError('training/development must be disjoint source recordings, including renamed videos')
        heldout_ids={t.trial_id for t in heldout}
        if any(heldout_ids.intersection(t.observation.noise.source_ids) for t in training):
            raise ValueError('development annotations/noise references must not enter training')
    if len({t.trial_id for t in all_trials}) != len(all_trials) or len({observation_fingerprint(t) for t in all_trials}) != len(all_trials):
        raise ValueError('training and heldout must be disjoint whole trials (including renamed copies)')


def score_free(params, trials, nominal_length_m):
    if trials and isinstance(trials[0],VideoTrial):
        return _score_video(params,trials,nominal_length_m)
    errors, innovations, normalized, floors, pairs, excess = [], [], [], [], [], []
    for trial in trials:
        obs = trial.observation
        indices = np.flatnonzero(obs.valid)
        if not len(indices):
            raise ValueError('no valid observations to score')
        e = predict_free(params, trial)[indices]-obs.xy_px[indices]
        errors.extend(np.sum(e**2, axis=1))
        normalized.extend(np.sum(e**2, axis=1)/(nominal_length_m*trial.projection.scale_px_per_m)**2)
        floor = float(np.trace(obs.covariance_px2))
        floors.extend([floor]*len(indices))
        excess.extend((np.sum(e**2, axis=1)-floor)/(nominal_length_m*trial.projection.scale_px_per_m)**2)
        innovations.extend(whiten(e, indices, obs.covariance_px2, obs.ar1_phi).ravel())
        adjacent = np.diff(indices) == 1
        pairs.extend(zip(e[:-1, 0][adjacent], e[1:, 0][adjacent]))
    lag = None
    if len(pairs) > 2:
        pair_array = np.array(pairs)
        if np.all(pair_array.std(axis=0) > 0):
            lag = float(np.corrcoef(pair_array.T)[0, 1])
    mse, floor = float(np.mean(errors)), float(np.mean(floors))
    # Every trial has its own known pixel scale; excess is normalized per sample.
    return {'rmse_xy_px': float(np.sqrt(mse)), 'mse_xy_px2': mse,
            'assumed_noise_floor_mse_px2': floor, 'nrmse': float(np.sqrt(np.mean(normalized))),
            'excess_nrmse': float(np.sqrt(max(np.mean(excess), 0.))),
            'innovation_mean_square_per_coordinate': float(np.mean(np.square(innovations))),
            'lag1_x': lag, 'valid_samples': len(errors)}


def _score_video(params,trials,nominal_length_m):
    errors=[]; metric_errors=[]; innovations=[]; normalized=[]; floors=[]; pairs=[]
    for t in trials:
        obs=t.observation; indices=np.flatnonzero(obs.valid)
        if not len(indices):
            raise ValueError('no valid video observations to score')
        prediction=predict_free(params,t)
        e=prediction[indices]-obs.xy_px[indices]
        errors.extend(np.sum(e**2,axis=1))
        metric=unproject(prediction[indices],t.projection)-unproject(obs.xy_px[indices],t.projection)
        metric_errors.extend(np.sum(metric**2,axis=1))
        normalized.extend(np.sum(e**2,axis=1)/(nominal_length_m*t.projection.scale_px_per_m)**2)
        innovations.extend(whiten_video(e,t,prediction).ravel())
        floors.extend(np.trace(obs.frame_covariance_px2[indices],axis1=1,axis2=2))
        adjacent=np.diff(indices)==1
        pairs.extend(zip(e[:-1,0][adjacent],e[1:,0][adjacent]))
    lag=None
    if len(pairs)>2 and np.all(np.std(pairs,axis=0)>0):
        lag=float(np.corrcoef(np.asarray(pairs).T)[0,1])
    mse=float(np.mean(errors))
    return {'rmse_xy_px':float(np.sqrt(mse)),'mse_xy_px2':mse,
            'rmse_metric_m':float(np.sqrt(np.mean(metric_errors))),
            'localization_floor_mse_px2':float(np.mean(floors)),
            'assumed_noise_floor_mse_px2':None,'excess_nrmse':None,
            'nrmse':float(np.sqrt(np.mean(normalized))),'valid_samples':len(errors),
            'innovation_mean_square_per_coordinate':float(np.mean(np.square(innovations))),'lag1_x':lag,
            'uncertainty_model':'per-frame covariance, independent PTS quantization, common rank-one release timing',
            'limitation':'local pivot scale normalizes NRMSE; systematic calibration errors and initial-condition uncertainty are not independent frame noise'}


def compare_baselines(training, heldout, nominal, options=FitOptions()):
    training, heldout = tuple(training), tuple(heldout)
    check_split(training, heldout)
    result = {'training_trial_ids': [t.trial_id for t in training],
              'heldout_trial_ids': [t.trial_id for t in heldout],
              'B0': {'params': asdict(nominal), 'training': score_free(nominal, training, nominal.length_m),
                     'heldout': score_free(nominal, heldout, nominal.length_m)}}
    try:
        fit = fit_free(training, nominal, options)
        result['B1'] = asdict(fit)
        result['B1']['training'] = score_free(fit.params, training, nominal.length_m)
        result['B1']['heldout'] = score_free(fit.params, heldout, nominal.length_m)
    except FitError as exc:
        result['B1'] = {'success': False, 'failure': str(exc), 'starts': list(exc.starts),
                        'training': None, 'heldout': None}
    geometry = fit_geometry(training)
    result['B2'] = asdict(geometry)
    result['B2']['training'] = score_geometry(geometry, training)
    result['B2']['heldout'] = score_geometry(geometry, heldout)
    return result

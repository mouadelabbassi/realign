"""Frozen predefined candidates; development observations never choose a model."""
from dataclasses import asdict
import numpy as np
from realign.physics import PendulumParams
from .baselines import compare_baselines, check_split, score_free
from .robust_fit import FitError, FitOptions, fit_free, predict_free
from .peg_fit import PegFitOptions, fit_peg, score_peg, predict_peg


def _paired(b1, b3, trials, seed):
    differences = []
    null_mse = []
    for t in trials:
        o = t.observation; v = o.valid
        e1 = predict_free(b1, t)[v]-o.xy_px[v]
        e3 = predict_peg(b3, t)[v]-o.xy_px[v]
        m1 = float(np.mean(np.sum(e1**2, axis=1)))
        m3 = float(np.mean(np.sum(e3**2, axis=1)))
        null_mse.append(m1); differences.append(m1-m3)
    differences = np.array(differences)
    # Resample whole paired trials, never individual correlated frames.
    rng = np.random.default_rng(seed)
    bootstrap = differences[rng.integers(0, len(trials), (2000, len(trials)))].mean(axis=1)
    disagreement = np.concatenate([np.sum((predict_free(b1, t)[t.observation.valid]-
                                          predict_peg(b3, t)[t.observation.valid])**2, axis=1) for t in trials])
    return {'trial_mse_improvements_px2': differences.tolist(), 'mean_mse_improvement_px2': float(differences.mean()),
            'paired_trial_bootstrap_95_interval_px2': np.quantile(bootstrap, [.025, .975]).tolist() if len(trials) >= 3 else None,
            'trial_count': len(trials), 'bootstrap_resamples': 2000,
            'B1_trial_mse_standard_error_px2': float(np.std(null_mse, ddof=1)/np.sqrt(len(trials))) if len(trials) > 1 else None,
            'prediction_disagreement_rmse_px': float(np.sqrt(np.mean(disagreement))),
            'interpretation': 'descriptive development comparison, conditional on fixed exploration fits; not a null-calibrated structural decision'}


def compare_structural(training, development, nominal, *, free_options=FitOptions(), peg_options=PegFitOptions(),
                       cross_validate=True, bootstrap_seed=20261101):
    training, development = tuple(training), tuple(development)
    check_split(training, development)
    if any(t.zone != 'exploration' for t in training) or any(t.zone != 'development' for t in development):
        raise ValueError('structural comparison requires frozen exploration/development zones')
    result = compare_baselines(training, development, nominal, free_options)
    result['comparison_scope'] = 'predefined FREE versus ideal one-peg dynamics; no automatic repair/discovery claim'
    b1 = PendulumParams(**result['B1']['params']) if result['B1']['success'] else None
    try:
        fit = fit_peg(training, nominal, peg_options, initializer=b1)
        result['B3'] = asdict(fit)
        result['B3']['training'] = score_peg(fit.params, training)
        try:
            result['B3']['heldout'] = score_peg(fit.params, development)
            result['B3']['prediction_status'] = 'completed'
            if b1 is not None:
                result['paired_development'] = _paired(b1, fit.params, development, bootstrap_seed)
        except (RuntimeError, ValueError, FloatingPointError) as exc:
            result['B3'].update(heldout=None, prediction_status='failed', prediction_error_type=type(exc).__name__)
    except FitError as exc:
        result['B3'] = {'success': False, 'failure': str(exc), 'starts': list(exc.starts), 'training': None, 'heldout': None}
    folds = []
    if cross_validate and len(training) >= 2:
        for i, held in enumerate(training):
            allowed = training[:i]+training[i+1:]
            row = {'held_exploration_trial': held.trial_id}
            initial = None
            try:
                f = fit_free(allowed, nominal, free_options)
                initial = f.params
                row['B1_mse_px2'] = score_free(f.params, [held], nominal.length_m)['mse_xy_px2']
            except FitError as exc:
                row['B1_failure'] = str(exc)
            try:
                f = fit_peg(allowed, nominal, peg_options, initializer=initial)
                row['B3_mse_px2'] = score_peg(f.params, [held])['mse_xy_px2']
            except (FitError, RuntimeError, ValueError) as exc:
                row['B3_failure'] = str(exc)
            folds.append(row)
    result['exploration_leave_one_trial_out'] = folds
    result['structural_decision'] = 'NOT_ASSESSED: Monte Carlo null calibration and mechanism interventions remain pending'
    return result

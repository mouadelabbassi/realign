"""Observation-only B3 dynamics, failure handling and whole-trial prediction."""
from dataclasses import replace, asdict
import json
import numpy as np
import pytest
from realign.contracts import Experiment, NoiseConfig
from realign.physics import PendulumParams, PegParams, simulate
from realign.synth.generator import generate_trial
from realign.fit.peg_fit import fit_peg, predict_peg, score_peg, PegFitOptions, _sensitivity
from realign.fit.robust_fit import FitError
from realign.fit.structural_comparison import compare_structural

NOMINAL = PendulumParams(.72, gamma_per_s=.06, quadratic_drag_per_m=.02)


def data(params, *, angles=(.42, .64, .53), sigma=.5, duration=2.5, dropout=0.):
    return [generate_trial(params, Experiment(a, duration, 25), seed=800+i, trial_id=f'obs-{i}',
            noise=NoiseConfig(((sigma*sigma, 0.), (0., sigma*sigma)), .2 if dropout else 0., dropout),
            zone='exploration' if i < 2 else 'development')[0] for i, a in enumerate(angles)]


@pytest.mark.parametrize('phi,side', [(0., -1), (-.18, -1), (.18, 1)])
def test_excited_peg_fits_full_disjoint_trajectory(phi, side):
    p = replace(NOMINAL, peg=PegParams(.16, phi, side))
    angles = (.42, .64, .53) if side == -1 else (-.42, -.64, -.53)
    trials = data(p, angles=angles)
    fitted = fit_peg(trials[:2], NOMINAL, PegFitOptions(contact_side=side))
    assert fitted.success and len(fitted.starts) == 8
    assert score_peg(fitted.params, trials[2:])['rmse_xy_px'] < 1.5
    assert abs(fitted.params.peg.distance_m-.16) < .01
    assert abs(fitted.params.peg.angle_rad-phi) < .02
    assert fitted.identifiability['numerical_rank'] == 5
    assert fitted.identifiability['conditional_gaussian_std'] is not None
    assert all(s['residual_calls'] <= 7*60+1 for s in fitted.starts)
    # A frozen model makes the entire temporal prediction without seeing positions.
    corrupt = replace(trials[2], observation=replace(trials[2].observation, xy_px=trials[2].observation.xy_px+100.))
    np.testing.assert_array_equal(predict_peg(fitted.params, trials[2]), predict_peg(fitted.params, corrupt))


@pytest.mark.parametrize('params', [NOMINAL, replace(NOMINAL, length_m=.76, gamma_per_s=.11),
                                   replace(NOMINAL, peg=PegParams(.16, -.8))])
def test_negative_controls_are_predictable_without_proving_a_peg(params):
    trials = data(params, angles=(.22, .32, .27))
    f = fit_peg(trials[:2], NOMINAL)
    assert score_peg(f.params, trials[2:])['rmse_xy_px'] < 1.5
    # The constrained peg fit can choose an unexcited geometry or hit a bound;
    # either way this is not independent mechanism evidence.
    assert not f.identifiability['locally_identifiable']
    assert f.identifiability['conditional_gaussian_std'] is None


def test_noisy_missing_observations_fit_without_filling_missing_rows():
    trials = data(replace(NOMINAL, peg=PegParams(.16, -.18)), sigma=2.5, dropout=.15)
    f = fit_peg(trials[:2], NOMINAL)
    assert score_peg(f.params, trials[2:])['rmse_xy_px'] < 6.
    assert np.isnan(trials[0].observation.xy_px[~trials[0].observation.valid]).all()


def test_unexcited_prediction_and_sensitivity_do_not_use_event_truth():
    trials = data(NOMINAL, angles=(.2, .3, .25))
    p = replace(NOMINAL, peg=PegParams(.16, -.8))
    from realign.fit.robust_fit import predict_free
    np.testing.assert_allclose(predict_peg(p, trials[2]), predict_free(NOMINAL, trials[2]), atol=1e-8)
    x = np.zeros(5); lo = -np.ones(5); hi = np.ones(5)
    diagnostic = _sensitivity(lambda v: np.r_[v[:3], v[:3]], x, lo, hi)
    assert diagnostic['numerical_rank'] == 3
    assert not diagnostic['locally_identifiable'] and diagnostic['conditional_gaussian_std'] is None


@pytest.mark.parametrize('kwargs', [{'duration': .3}, {'angles': (.01, .02, .015)}])
def test_insufficient_data_and_excitation_fail(kwargs):
    with pytest.raises(FitError, match='insufficient'):
        fit_peg(data(NOMINAL, **kwargs)[:2], NOMINAL)


def test_solver_failure_and_exhaustion_are_explicit(monkeypatch):
    from realign.fit import peg_fit
    trials = data(NOMINAL)
    with pytest.raises(FitError) as caught:
        fit_peg(trials[:2], NOMINAL, PegFitOptions(max_nfev=1))
    assert len(caught.value.starts) == 8
    monkeypatch.setattr(peg_fit, 'least_squares', lambda *a, **k: (_ for _ in ()).throw(RuntimeError('injected solver failure')))
    with pytest.raises(FitError) as caught:
        fit_peg(trials[:2], NOMINAL)
    assert len(caught.value.starts) == 8 and all(not s['success'] for s in caught.value.starts)


@pytest.mark.parametrize('kwargs', [{'peg_fraction_bounds': (.1, .98)}, {'gamma_bounds_per_s': (-1., .1)},
                                    {'length_bounds_m': (0., 1.)}, {'contact_side': 0}, {'n_starts': 7},
                                    {'peg_angle_bounds_rad': (-2., .4)}])
def test_invalid_physical_search_domains_rejected(kwargs):
    with pytest.raises(ValueError):
        PegFitOptions(**kwargs)


def test_event_rollout_matches_validated_kernel_and_slack_is_rejected():
    p = replace(NOMINAL, peg=PegParams(.16, -.18))
    t = data(p)[0]
    from realign.observation.camera import project
    direct = simulate(p, t.experiment.release_angle_rad, 0., t.observation.t_s)
    np.testing.assert_array_equal(predict_peg(p, t), project(direct.xy_m, t.projection))
    assert len(direct.events) > 0
    invalid = replace(t, experiment=Experiment(1.4, 2.5, 25.))
    with pytest.raises(ValueError, match='SLACK'):
        predict_peg(replace(NOMINAL, peg=PegParams(.30)), invalid)


def test_training_zones_and_duplicates_rejected():
    t = data(NOMINAL)
    with pytest.raises(FitError, match='exploration'):
        fit_peg(t, NOMINAL)
    with pytest.raises(FitError, match='duplicate'):
        fit_peg([t[0], replace(t[0], trial_id='renamed')], NOMINAL)
    with pytest.raises(ValueError, match='disjoint'):
        compare_structural(t[:2], [t[0]], NOMINAL)


def test_structural_report_reproducible_integration(tmp_path):
    from realign.report.structural_report import build_structural_report
    first = build_structural_report(tmp_path, case_names={'vertical_peg', 'insufficient_data'})
    saved = {p.name: p.read_bytes() for p in tmp_path.iterdir()}
    second = build_structural_report(tmp_path, case_names={'vertical_peg', 'insufficient_data'})
    assert first == second and first['acceptance_passed']
    assert all((tmp_path/n).read_bytes() == b for n, b in saved.items())
    row = first['cases'][0]
    assert len(row['exploration_leave_one_trial_out']) == 2
    assert len(row['B3']['heldout']['per_trial']) == 5
    assert row['structural_decision'].startswith('NOT_ASSESSED')
    assert row['paired_development']['paired_trial_bootstrap_95_interval_px2'][0] > 0
    assert not first['g2_passed'] and not first['full_g3_passed']


def test_video_prediction_preserves_pts_release_offset_and_common_uncertainty():
    from realign.contracts.video import VideoMetadata, VideoObservation, NoiseEstimate, VideoTrial, ReleaseEstimate
    from realign.synth.video_fixture import fixture_calibration
    from realign.fit.peg_fit import residuals_peg
    from realign.observation.camera import project
    pts = tuple(range(3000, 6040, 40))
    m = VideoMetadata('f'*64, 'SYNTHETIC_RENDER', 640, 480, 640, 480, pts, '1/1000', 'FIXTURE')
    n = len(pts)
    cal = fixture_calibration()
    noise = NoiseEstimate(((.25, 0.), (0., .25)), (0., 0.), .2, .04, ('fixture_stationary',), 'SYNTHETIC', 'FIXTURE')
    o = VideoObservation('video-fixture', m, np.zeros((n, 2)), np.ones(n, bool),
                         np.tile(np.eye(2)*.25, (n, 1, 1)), np.zeros(n, np.uint32), noise,
                         cal.calibration_id, 'SYNTHETIC', 'SIMULATED_API_FIXTURE')
    t = VideoTrial('video-fixture', Experiment(.45, 2.6, 25.), o, cal, ReleaseEstimate(3.4, .01, 3.38, 3.42, 'FIXTURE'))
    p = replace(NOMINAL, peg=PegParams(.16, -.18))
    y = predict_peg(p, t)
    relative = m.t_s-3.4
    pre = relative < 0
    initial = project(np.array([[p.length_m*np.sin(.45), -p.length_m*np.cos(.45)]]), cal)
    np.testing.assert_allclose(y[pre], np.tile(initial, (pre.sum(), 1)))
    post = relative >= 0
    times = np.unique(np.r_[0., relative[post]])
    expected = project(simulate(p, .45, 0., times).xy_m, cal)
    np.testing.assert_array_equal(y[post], expected[np.searchsorted(times, relative[post])])
    t = replace(t, observation=replace(o, xy_px=y))
    np.testing.assert_allclose(residuals_peg(p, [t]), 0., atol=1e-10)
    assert t.observation.metadata.pts == pts and t.observation.t_s[0] == 3.

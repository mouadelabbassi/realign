"""POC-0 acceptance tests: inference receives observations, never synthetic truth."""
from dataclasses import replace
import ast
import json
from pathlib import Path
import subprocess
import sys

import numpy as np
import pytest

from realign.contracts import Experiment, NoiseConfig, Observation, PlaneProjection
from realign.observation.camera import project, unproject
from realign.observation.noise import sample_noise, whiten
from realign.physics import PendulumParams, PegParams
from realign.synth.generator import generate_trial
from realign.fit.robust_fit import FitError, FitOptions, fit_free, predict_free
from realign.fit.circle_fit import CircleFitError, fit_circle, fit_geometry
from realign.fit.baselines import compare_baselines


def trials(params, angles=(.4, .65, .52), sigma=.4, duration=4., **noise):
    return [generate_trial(
        params, Experiment(a, duration, 30), seed=1230+i, trial_id=f'trial_{i}',
        noise=NoiseConfig(((sigma*sigma, 0.), (0., sigma*sigma)), **noise),
    )[0] for i, a in enumerate(angles)]


def test_seed_projection_and_truth_separation():
    p = PendulumParams(.72, peg=PegParams(.14, -.15))
    kwargs = dict(seed=12, trial_id='opaque', noise=NoiseConfig(ar1_phi=.6, dropout_probability=.2))
    a, truth = generate_trial(p, Experiment(.5, 3., 60), **kwargs)
    b, _ = generate_trial(p, Experiment(.5, 3., 60), **kwargs)
    np.testing.assert_array_equal(a.observation.xy_px, b.observation.xy_px)
    np.testing.assert_array_equal(a.observation.valid, b.observation.valid)
    assert 0 < a.observation.valid.sum() < len(a.observation.valid)
    assert np.isnan(a.observation.xy_px[~a.observation.valid]).all()
    assert not hasattr(a, 'truth') and not hasattr(a, 'params')
    assert len(truth.events) > 0
    xy = np.array([[0., -.72], [.2, -.6]])
    np.testing.assert_allclose(unproject(project(xy, a.projection), a.projection), xy)
    assert not a.observation.xy_px.flags.writeable


@pytest.mark.parametrize('change', [
    {'position_unit': 'm'}, {'time_unit': 'ms'}, {'covariance_unit': 'px'},
    {'frame': 'world'}, {'covariance_px2': ((1., 2.), (0., 1.))},
    {'covariance_px2': ((1., 2.), (2., 1.))},
    {'t_s': np.array([0., 0., 1.])}, {'valid': np.array([1, 1, 1])},
])
def test_bad_observation_contracts(change):
    args = dict(t_s=np.array([0., .5, 1.]), xy_px=np.ones((3, 2)), valid=np.ones(3, dtype=bool))
    args.update(change)
    with pytest.raises(ValueError):
        Observation(**args)


def test_missing_and_finite_rules():
    with pytest.raises(ValueError, match='finite'):
        Observation(np.array([0., 1.]), np.array([[np.nan, 1.], [1., 1.]]), np.ones(2, bool))
    with pytest.raises(ValueError):
        PlaneProjection(scale_px_per_m=-1.)
    with pytest.raises(ValueError):
        NoiseConfig(ar1_phi=1.)
    # Zero covariance is meaningful for a clean geometry experiment, not whitening.
    with pytest.raises(ValueError, match='positive definite'):
        whiten(np.ones((3, 2)), np.arange(3), np.zeros((2, 2)), 0.)


def test_ar1_covariance_and_gap_aware_whitening():
    cov = np.array([[2., .6], [.6, 1.]])
    config = NoiseConfig(tuple(map(tuple, cov)), ar1_phi=.7)
    noise = sample_noise(80000, config, np.random.default_rng(71))
    np.testing.assert_allclose(np.cov(noise.T), cov, atol=.06)
    keep = np.arange(80000)[np.random.default_rng(72).random(80000) > .25]
    innovations = whiten(noise[keep], keep, cov, .7)
    np.testing.assert_allclose(np.cov(innovations.T), np.eye(2), atol=.035)
    assert np.max(np.abs(innovations.mean(axis=0))) < .02
    assert abs(np.corrcoef(innovations[:-1, 0], innovations[1:, 0])[0, 1]) < .02


@pytest.fixture(scope='module')
def no_fault_fit():
    p = PendulumParams(.735, gamma_per_s=.09, quadratic_drag_per_m=.04)
    data = trials(p, duration=5., ar1_phi=.4, dropout_probability=.1)
    return data, fit_free(data[:2], PendulumParams(.70))


def test_no_fault_recovers_parameters_and_predicts_whole_trial(no_fault_fit):
    data, fit = no_fault_fit
    assert fit.success and len(fit.starts) == 8
    assert abs(fit.params.length_m - .735) < .001
    assert abs(fit.params.gamma_per_s - .09) < .025
    assert abs(fit.params.quadratic_drag_per_m - .04) < .035
    predicted = predict_free(fit.params, data[2])
    keep = data[2].observation.valid
    rmse = np.sqrt(np.mean(np.sum((predicted[keep] - data[2].observation.xy_px[keep])**2, axis=1)))
    assert rmse < 1.0
    # Changing held-out observed positions must not change a rollout prediction.
    shifted = replace(data[2], observation=replace(data[2].observation, xy_px=data[2].observation.xy_px + 10.))
    np.testing.assert_array_equal(predicted, predict_free(fit.params, shifted))


def test_fixed_structure_leaves_excited_peg_discrepancy():
    data = trials(PendulumParams(.72, gamma_per_s=.04, peg=PegParams(.16)), sigma=.3)
    result = compare_baselines(data[:2], data[2:], PendulumParams(.72, gamma_per_s=.04))
    assert result['B1']['heldout']['rmse_xy_px'] > 8.
    assert result['B1']['heldout']['lag1_x'] > .8
    assert result['B2']['decision'] == 'two_circle'
    np.testing.assert_allclose(result['B2']['second_circle']['center_m'], [0., -.16], atol=.015)


def test_clean_off_vertical_geometry_without_labels():
    data = trials(PendulumParams(.72, peg=PegParams(.15, -.17)), sigma=0.)
    result = fit_geometry(data[:2])
    assert result.decision == 'two_circle'
    expected = [.15*np.sin(-.17), -.15*np.cos(-.17)]
    np.testing.assert_allclose(result.second_circle.center_m, expected, atol=2e-7)
    assert abs(result.second_circle.radius_m - .57) < 2e-7


@pytest.mark.parametrize('peg', [None, PegParams(.15, -.8)])
def test_no_peg_or_no_contact_never_forces_second_circle(peg):
    data = trials(PendulumParams(.72, peg=peg), angles=(.35, .45, .4))
    result = fit_geometry(data[:2])
    assert result.decision == 'one_circle_only'
    assert result.second_circle is None


def test_unexcited_peg_is_observationally_equivalent_to_free_model():
    kwargs = dict(seed=432, trial_id='opaque', noise=NoiseConfig(ar1_phi=.5, dropout_probability=.2))
    free, _ = generate_trial(PendulumParams(.72), Experiment(.3), **kwargs)
    unexcited, truth = generate_trial(PendulumParams(.72, peg=PegParams(.16, -.8)), Experiment(.3), **kwargs)
    assert not truth.events
    np.testing.assert_allclose(free.observation.xy_px, unexcited.observation.xy_px, atol=1e-10)


def test_all_missing_data_are_not_interpolated_into_a_fit():
    data = trials(PendulumParams(.72), dropout_probability=1.)
    with pytest.raises(FitError, match='insufficient valid'):
        fit_free(data[:2], PendulumParams(.72))
    assert fit_geometry(data[:2]).decision == 'ambiguous'


def test_degenerate_arcs_and_insufficient_trials_abstain():
    x = np.linspace(-.01, .01, 40)
    with pytest.raises(CircleFitError):
        fit_circle(np.column_stack([x, np.zeros_like(x)]), sigma_m=.001)
    data = trials(PendulumParams(.72), angles=(.01, .012, .011), sigma=.5, duration=1.)
    assert fit_geometry(data[:2]).decision == 'ambiguous'
    assert fit_geometry(data[:1]).decision == 'ambiguous'


def test_fit_failure_explicit_and_all_starts_reported(monkeypatch):
    from realign.fit import robust_fit
    def fail(*args, **kwargs):
        raise RuntimeError('injected solver failure')
    monkeypatch.setattr(robust_fit, 'least_squares', fail)
    with pytest.raises(FitError) as caught:
        fit_free(trials(PendulumParams(.72))[:2], PendulumParams(.72))
    assert len(caught.value.starts) == 8
    assert all(not s['success'] for s in caught.value.starts)


def test_circle_solver_failure_explicit(monkeypatch):
    from realign.fit import circle_fit
    monkeypatch.setattr(circle_fit, 'least_squares', lambda *a, **k: (_ for _ in ()).throw(RuntimeError('failed')))
    angle = np.linspace(-.6, .6, 60)
    with pytest.raises(CircleFitError, match='solver'):
        fit_circle(.7*np.column_stack([np.sin(angle), -np.cos(angle)]), sigma_m=.001)


def test_exhausted_fit_budget_is_not_reported_as_convergence():
    data = trials(PendulumParams(.72), duration=1.)
    with pytest.raises(FitError) as caught:
        fit_free(data[:2], PendulumParams(.5), FitOptions(max_nfev=1))
    assert len(caught.value.starts) == 8
    assert all(not s['success'] and s['status'] == 0 for s in caught.value.starts)


def test_heldout_values_cannot_change_fitted_models():
    data = trials(PendulumParams(.72, gamma_per_s=.07), duration=2.)
    options = FitOptions(fit_quadratic_drag=False)
    first = compare_baselines(data[:2], data[2:], PendulumParams(.7), options)
    corrupt = replace(data[2], observation=replace(data[2].observation, xy_px=data[2].observation.xy_px+50.))
    second = compare_baselines(data[:2], [corrupt], PendulumParams(.7), options)
    assert first['B1']['params'] == second['B1']['params']
    assert first['B1']['starts'] == second['B1']['starts']
    assert first['B2']['decision'] == second['B2']['decision']
    assert first['B2']['first_circle'] == second['B2']['first_circle']
    assert first['B2']['cv_one_score'] == second['B2']['cv_one_score']
    assert first['B1']['heldout']['rmse_xy_px'] != second['B1']['heldout']['rmse_xy_px']


def test_whole_trial_split_rejects_overlap_and_copies():
    data = trials(PendulumParams(.72))
    with pytest.raises(ValueError, match='disjoint'):
        compare_baselines(data[:2], data[1:], PendulumParams(.72))
    copy = replace(data[0], trial_id='renamed')
    with pytest.raises(ValueError, match='disjoint'):
        compare_baselines(data[:2], [copy], PendulumParams(.72))
    copy = replace(copy, experiment=replace(copy.experiment, release_angle_rad=.5))
    with pytest.raises(ValueError, match='disjoint'):
        compare_baselines(data[:2], [copy], PendulumParams(.72))


def test_fitters_have_no_truth_imports_or_file_reads(tmp_path):
    root = Path(__file__).resolve().parents[1]
    for package in ('contracts', 'observation', 'fit', 'physics'):
        for path in (root/'src'/'realign'/package).glob('*.py'):
            tree = ast.parse(path.read_text(encoding='utf-8'))
            for node in ast.walk(tree):
                if isinstance(node, (ast.Import, ast.ImportFrom)):
                    names = [n.name for n in node.names] + [getattr(node, 'module', '') or '']
                    assert not any('synth' in n or 'truth' in n or 'vault' in n for n in names), path
                if isinstance(node, ast.Call):
                    assert getattr(node.func, 'id', '') not in ('open', '__import__', 'eval', 'exec'), path
                    assert getattr(node.func, 'attr', '') not in ('read_text', 'read_bytes', 'load', 'import_module'), path
    # Inference still runs in a fresh process where importing synthetic truth is denied.
    data = trials(PendulumParams(.72), duration=1.)[0]
    file = tmp_path/'observation.npz'
    np.savez(file, t=data.observation.t_s, xy=data.observation.xy_px, valid=data.observation.valid)
    code = '''
import importlib.abc, sys, numpy as np
class DenyTruth(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, *args):
        if fullname.startswith(('realign.synth', 'realign.vault')):
            raise ImportError('truth unavailable to inference')
sys.meta_path.insert(0, DenyTruth())
def deny_truth_reads(event, args):
    if event == 'open' and 'poc0_truth' in str(args[0]):
        raise PermissionError('truth file unavailable to inference')
sys.addaudithook(deny_truth_reads)
try:
    open(sys.argv[2]).read()
    raise AssertionError('truth read was allowed')
except PermissionError:
    pass
from realign.contracts import Observation, Trial, Experiment, PlaneProjection
from realign.fit.robust_fit import fit_free, FitOptions
from realign.physics import PendulumParams
with np.load(sys.argv[1]) as d:
    o = Observation(d['t'], d['xy'], d['valid'], covariance_px2=((.16,0.),(0.,.16)))
t = Trial('opaque', Experiment(.4, 1., 30), o, PlaneProjection())
assert fit_free([t], PendulumParams(.72), FitOptions(fit_quadratic_drag=False)).success
assert not any(n.startswith('realign.synth') for n in sys.modules)
'''
    canary = tmp_path/'poc0_truth_evaluation.json'
    canary.write_text('{"canary":"SYNTHETIC_TRUTH_CANARY"}')
    result = subprocess.run([sys.executable, '-c', code, str(file), str(canary)], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert 'SYNTHETIC_TRUTH_CANARY' not in result.stdout+result.stderr


def test_report_integration_and_reproducibility(tmp_path):
    from realign.report.baseline_report import build_report
    first = build_report(tmp_path, seed=20261031)
    json_bytes = (tmp_path/'poc0_baselines.json').read_bytes()
    markdown_bytes = (tmp_path/'POC0_BASELINES.md').read_bytes()
    plot_bytes = (tmp_path/'poc0_baselines.png').read_bytes()
    observations_bytes = (tmp_path/'poc0_observations.npz').read_bytes()
    second = build_report(tmp_path, seed=20261031)
    assert first == second and first['acceptance_passed']
    assert json_bytes == (tmp_path/'poc0_baselines.json').read_bytes()
    assert markdown_bytes == (tmp_path/'POC0_BASELINES.md').read_bytes()
    assert plot_bytes == (tmp_path/'poc0_baselines.png').read_bytes()
    assert observations_bytes == (tmp_path/'poc0_observations.npz').read_bytes()
    assert (tmp_path/'poc0_baselines.png').stat().st_size > 10000
    for case in first['cases']:
        assert not set(case['training_trial_ids']) & set(case['heldout_trial_ids'])
        assert len(case['B1']['starts']) == 8
    truth = json.loads((tmp_path/'poc0_truth_evaluation.json').read_text())
    assert truth['scope'].startswith('POST-FIT')

"""Fixed synthetic B0/B1/B2/B3 protocol. No development-based tuning."""
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import platform
import numpy as np
import scipy
from realign.contracts import Experiment, NoiseConfig
from realign.physics import PendulumParams, PegParams
from realign.synth.generator import generate_trial
from realign.fit.baselines import observation_fingerprint
from realign.fit.robust_fit import FitOptions, predict_free
from realign.fit.peg_fit import PegFitOptions, predict_peg
from realign.fit.structural_comparison import compare_structural

ROOT = Path(__file__).resolve().parents[3]
SCOPE = 'SYNTHETIC ONLY - NO LIVE META OR REAL DYNAMICS VALIDATION'


def protocol():
    nominal = PendulumParams(.72, gamma_per_s=.06, quadratic_drag_per_m=.02)
    return nominal, [
        ('no_fault', nominal, (.42, .64), NoiseConfig(), 2.5),
        ('parameter_fault', PendulumParams(.76, gamma_per_s=.11, quadratic_drag_per_m=.05), (.42, .64), NoiseConfig(), 2.5),
        ('vertical_peg', PendulumParams(.72, gamma_per_s=.06, quadratic_drag_per_m=.02, peg=PegParams(.16)), (.42, .64), NoiseConfig(), 2.5),
        ('off_vertical_peg', PendulumParams(.72, gamma_per_s=.06, quadratic_drag_per_m=.02, peg=PegParams(.16, -.18)), (.42, .64), NoiseConfig(dropout_probability=.1), 2.5),
        ('unexcited_peg', PendulumParams(.72, gamma_per_s=.06, quadratic_drag_per_m=.02, peg=PegParams(.16, -.8)), (.22, .32), NoiseConfig(), 2.5),
        ('noisy_peg', PendulumParams(.72, gamma_per_s=.06, quadratic_drag_per_m=.02, peg=PegParams(.16, -.18)), (.42, .64), NoiseConfig(((6.25, 0.), (0., 6.25)), .35, .15), 2.5),
        ('short_arc', nominal, (.012, .018), NoiseConfig(), 2.5),
        ('insufficient_data', nominal, (.42, .64), NoiseConfig(), .3),
    ]


def source_hash():
    h = hashlib.sha256()
    for p in sorted((ROOT/'src/realign').rglob('*.py'))+[ROOT/'scripts/verify_structural.py']:
        h.update(p.relative_to(ROOT).as_posix().encode()); h.update(p.read_bytes())
    return h.hexdigest()


def _decode(data):
    p = dict(data)
    if p.get('peg'):
        p['peg'] = PegParams(**p['peg'])
    return PendulumParams(**p)


def _plot(path, trial, row):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig, axes = plt.subplots(2, 1, figsize=(10, 7), layout='constrained')
    o = trial.observation; v = o.valid
    axes[0].scatter(o.t_s[v], o.xy_px[v, 0], c='black', s=9, label='Synthetic observations')
    for name, predict in [('B0', predict_free), ('B1', predict_free), ('B3', predict_peg)]:
        if not row[name].get('params'):
            continue
        y = predict(_decode(row[name]['params']), trial)
        axes[0].plot(o.t_s, y[:, 0], label=name)
        axes[1].plot(o.t_s[v], np.linalg.norm(y[v]-o.xy_px[v], axis=1), label=name)
    axes[0].set(ylabel='Image x (px)', title='Frozen exploration fits: disjoint vertical-peg development release')
    axes[1].set(xlabel='Seconds after prescribed release', ylabel='Trajectory residual norm (px)')
    for ax in axes:
        ax.legend()
    fig.suptitle(SCOPE)
    fig.savefig(path, dpi=140, metadata={'Software': 'REALIGN Task03'})
    plt.close(fig)


def _markdown(result):
    lines = ['# B3 structural dynamics evidence', '', '**'+SCOPE+'**', '',
             'Reproduce: python scripts/verify_structural.py. Seed: '+str(result['seed'])+'.', '',
             'Two exploration releases; five disjoint development releases per case. '
             'All candidate structures, bounds, starts, controls, noise levels and splits are fixed in code before scoring. '
             'Leave-one-exploration-trial-out refits are reported separately. Development data never choose parameters or structures.', '',
             '| Case | B0 trajectory RMS px | B1 trajectory RMS px | B3 trajectory RMS px | B2 radial RMS px (different statistic) | B3 local rank |',
             '|---|---:|---:|---:|---:|---:|']
    def number(x):
        return 'failed/unavailable' if x is None else f'{x:.4f}'
    for c in result['cases']:
        val = lambda b: (c[b].get('heldout') or {}).get('rmse_xy_px')
        lines.append('| '+c['case']+' | '+number(val('B0'))+' | '+number(val('B1'))+' | '+number(val('B3'))+' | '+
                     number(c['B2']['heldout'].get('radial_rmse_px'))+' | '+str(c['B3'].get('identifiability', {}).get('numerical_rank', 'failed'))+' |')
    lines += ['', 'B2 radial reconstruction is conditioned on each observed point; it is never ranked against a trajectory prediction.', '',
              '| Case | Mean B1 minus B3 trial MSE px² | Paired whole-trial bootstrap 95% interval | Prediction disagreement RMS px |',
              '|---|---:|---|---:|']
    for c in result['cases']:
        p = c.get('paired_development')
        if p:
            ci = p['paired_trial_bootstrap_95_interval_px2']
            lines.append('| '+c['case']+' | '+number(p['mean_mse_improvement_px2'])+' | '+str(ci)+' | '+number(p['prediction_disagreement_rmse_px'])+' |')
    lines += ['', '## Algorithms and uncertainty', '',
              '- B0/B1/B2 implementations are preserved. B1 and B3 fit the same L, viscous drag and quadratic drag. '
              'B3 additionally fits peg distance fraction and angle, for a declared wrap side and ideal lossless contact.',
              '- B3: eight deterministic starts, bounded TRF soft-L1 least squares, complete directed-event G1 rollouts. '
              'The common robust scale is computed from nominal exploration residual MAD. Observation-only B2 geometry initializes one start; '
              'remaining starts cover the permitted peg geometry. No modes, event times or hidden parameters enter fitting.',
              '- Bounds: L [0.4,1.1] m, gamma and quadratic [0,0.6] in s^-1 and m^-1, peg distance/L [0.005,0.55], '
              'peg angle [-0.9,0.9] rad intersected with the declared free-side training controls. '
              'Maximum 60 solver evaluations and 420 residual calls per start, including numerical finite differences. '
              'Preprocessing has a fixed 50-candidate geometry search; final sensitivity adds ten residual evaluations. '
              'A domain/slack/event failure aborts that start and is recorded; budget exhaustion is not convergence.',
              '- Local uncertainty uses an independent central-difference whitened-residual Jacobian scaled by search ranges. '
              'A relative singular-value cutoff of 1e-5 flags numerical rank deficiency. Conditional Gaussian standard deviations '
              'are emitted only at interior full-rank fits; these ignore model misspecification and are not coverage-validated CIs. '
              'Near-optimal multistart spread is a diagnostic, not a posterior or profile likelihood.',
              '- Synthetic projection is known (600 px/m). Requested sampling rate is 25 Hz. '
              'The preserved adapter rounds duration times rate: 63 timestamps over 2.5 s give an actual 24.8 Hz grid; '
              'the insufficient case has 9 timestamps over 0.3 s (26.6667 Hz). Actual timestamps drive every rollout. '
              'Release controls/time are prescribed, not fitted from hidden truth. Ordinary covariance is diag(0.25,0.25) px²; '
              'noisy case diag(6.25,6.25) px² with AR(1) phi=0.35 and 15% dropouts. '
              'These are assumed noise models, not measured SAM accuracy. JSON contains exact trials, hashes, fit failures and CV folds.',
              '- The 2000-resample paired bootstrap resamples five whole development trials, conditional on the exploration fit. '
              'It does not integrate training-fit variability. This small design is descriptive; a positive interval is not a calibrated structural-repair test.', '',
              '## Acceptance checks', '']
    lines += ['- '+('PASS' if c['passed'] else 'FAIL')+': '+c['name'] for c in result['checks']]
    lines += ['', '## Limits and pending evidence', '',
              'No structural decision or discovery is claimed. An unexcited peg can be observationally equivalent to the free model; '
              'small prediction differences at the assumed noise floor do not establish different mechanisms. '
              'Short arcs and insufficient data explicitly fail the B3 excitation/sample gate. '
              'A locally full-rank fit is not global or causal identification.', '',
              'The full Architecture v1.1 B3 selection gate still requires Monte Carlo null calibration, broader seed/effect/noise sweeps, '
              'CI coverage/power, profile uncertainty, and peg-removal interventions. No uncalibrated threshold is promoted to REPAIR_STRUCTURE. '
              'Fixed library comparison is classical model fitting, with no claim about Muse value.', '',
              'Real phone G2, live SAM, live Muse structured outputs/tool calling, metric external-video dynamics and sealed evaluation are NOT demonstrated here. '
              'The separately ingested external slow-motion clip has no verified physical time scale or measured camera calibration.', '',
              '![Synthetic held-out trajectory comparison](b3_trajectories.png)', '',
              'Source SHA-256: '+result['source_sha256']+'. Environment: '+json.dumps(result['versions'], sort_keys=True)+'.', '']
    return '\n'.join(lines)


def build_structural_report(output_dir, *, seed=20261101, case_names=None, progress=None):
    output = Path(output_dir); output.mkdir(parents=True, exist_ok=True)
    nominal, cases = protocol()
    rows = []; observations = {}; evaluations = []; plot_data = None
    for i, (name, params, train_angles, noise, duration) in enumerate(cases):
        if case_names is not None and name not in case_names:
            continue
        if progress:
            progress('Fitting '+name)
        dev_angles = tuple(np.linspace(train_angles[0]+.025, train_angles[1]-.025, 5))
        trials = []; truths = []
        for j, angle in enumerate(train_angles+dev_angles):
            t, truth = generate_trial(params, Experiment(float(angle), duration, 25.), seed=seed+100*i+j,
                                      trial_id=f'obs-{i}-{j}', noise=noise, zone='exploration' if j < 2 else 'development')
            trials.append(t); truths.append(truth)
            observations[t.trial_id+'_t_s'] = t.observation.t_s
            observations[t.trial_id+'_xy_px'] = t.observation.xy_px
            observations[t.trial_id+'_valid'] = t.observation.valid
        row = compare_structural(trials[:2], trials[2:], nominal, free_options=FitOptions(max_nfev=80),
                                 peg_options=PegFitOptions(), bootstrap_seed=seed+i)
        row['case'] = name
        row['observation_sha256'] = {t.trial_id: observation_fingerprint(t) for t in trials}
        row['noise_assumptions'] = asdict(noise)
        rows.append(row)
        evaluations.append({'case': name, 'parameters': asdict(params), 'events_per_trial': [len(t.events) for t in truths]})
        if name == 'vertical_peg':
            plot_data = (trials[4], row)
    checks = []
    def check(name, ok):
        checks.append({'name': name, 'passed': bool(ok)})
    for c in rows:
        b3 = c['B3']; name = c['case']
        if name in ('vertical_peg', 'off_vertical_peg', 'noisy_peg'):
            threshold = 6. if name == 'noisy_peg' else 1.5
            check(name+': full held-out B3 trajectory improves over B1', b3.get('heldout') is not None and
                  b3['heldout']['rmse_xy_px'] < threshold and c['B1'].get('heldout') is not None and
                  c['B1']['heldout']['rmse_xy_px'] > b3['heldout']['rmse_xy_px']*3)
        if name in ('no_fault', 'parameter_fault', 'unexcited_peg'):
            check(name+': B1 explains observations at the assumed floor', c['B1']['success'] and c['B1']['heldout']['rmse_xy_px'] < 1.5)
        if name == 'unexcited_peg':
            check('unexcited peg: no mechanism identification claimed', not b3.get('identifiability', {}).get('locally_identifiable', False))
        if name in ('short_arc', 'insufficient_data'):
            check(name+': B3 explicitly rejects insufficient evidence', not b3['success'])
    result = {'scope': SCOPE, 'seed': seed, 'source_sha256': source_hash(),
              'versions': {'python': platform.python_version(), 'numpy': np.__version__, 'scipy': scipy.__version__},
              'cases': rows, 'checks': checks, 'acceptance_passed': all(c['passed'] for c in checks),
              'g2_passed': False, 'full_g3_passed': False, 'actual_api_calls': 0}
    (output/'b3_baselines.json').write_text(json.dumps(result, indent=2, allow_nan=False)+'\n', encoding='utf-8')
    (output/'B3_BASELINES.md').write_text(_markdown(result), encoding='utf-8')
    (output/'b3_post_fit_evaluation.json').write_text(json.dumps({'scope': 'SYNTHETIC POST-FIT EVALUATION ONLY; never fitter input', 'cases': evaluations}, indent=2)+'\n', encoding='utf-8')
    np.savez_compressed(output/'b3_observations.npz', **observations)
    if plot_data:
        _plot(output/'b3_trajectories.png', *plot_data)
    return result

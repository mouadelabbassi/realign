"""Fixed POC-0 protocol. Truth is consulted only AFTER observation-only fitting."""
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import platform
import numpy as np
import scipy
from realign.contracts import Experiment, NoiseConfig
from realign.synth.generator import generate_trial
from realign.physics import PendulumParams, PegParams
from realign.fit.baselines import compare_baselines, observation_fingerprint
from realign.fit.robust_fit import FitOptions, predict_free
from realign.observation.camera import unproject


SCOPE = 'SYNTHETIC ONLY — NO META API / REAL-WORLD VALIDATION'
ROOT = Path(__file__).resolve().parents[3]


def _protocol():
    nominal = PendulumParams(.72, gamma_per_s=.06, quadratic_drag_per_m=.02)
    return [
        ('no_fault', nominal, (.42, .64, .53), NoiseConfig()),
        ('parameter_fault', PendulumParams(.76, gamma_per_s=.11, quadratic_drag_per_m=.05),
         (.42, .64, .53), NoiseConfig()),
        ('vertical_peg', PendulumParams(.72, gamma_per_s=.06, quadratic_drag_per_m=.02, peg=PegParams(.16)),
         (.42, .64, .53), NoiseConfig()),
        ('off_vertical_peg', PendulumParams(.72, gamma_per_s=.06, quadratic_drag_per_m=.02, peg=PegParams(.16, -.18)),
         (.42, .64, .53), NoiseConfig(dropout_probability=.1)),
        ('unexcited_peg', PendulumParams(.72, gamma_per_s=.06, quadratic_drag_per_m=.02, peg=PegParams(.16, -.8)),
         (.22, .32, .27), NoiseConfig()),
        ('short_arc', nominal, (.012, .018, .015), NoiseConfig()),
    ]


def _source_hash():
    digest = hashlib.sha256()
    paths = sorted((ROOT/'src'/'realign').rglob('*.py')) + [ROOT/'scripts'/'verify_baselines.py']
    for p in paths:
        digest.update(p.relative_to(ROOT).as_posix().encode())
        digest.update(p.read_bytes())
    return digest.hexdigest()


def _plot(path, trial, result):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.patches import Circle as CirclePatch
    obs = trial.observation
    p0 = PendulumParams(**result['B0']['params'])
    p1 = PendulumParams(**result['B1']['params'])
    y0, y1 = predict_free(p0, trial), predict_free(p1, trial)
    fig = plt.figure(figsize=(12, 9), layout='constrained')
    gs = fig.add_gridspec(2, 2)
    ax = fig.add_subplot(gs[0, :])
    keep = obs.valid
    ax.scatter(obs.t_s[keep], obs.xy_px[keep, 0], s=7, color='black', alpha=.6, label='Synthetic noisy observations')
    ax.plot(obs.t_s, y0[:, 0], label='B0 nominal rollout', color='#d95f02')
    ax.plot(obs.t_s, y1[:, 0], label='B1 fitted rollout (training trials only)', color='#1b9e77')
    ax.set(xlabel='Time since prescribed release (s)', ylabel='Image x (px)', title='Unseen development trial: vertical peg')
    ax.legend(loc='upper right', fontsize=9)
    ax = fig.add_subplot(gs[1, 0])
    points = unproject(obs.xy_px[keep], trial.projection)
    ax.scatter(*points.T, s=6, color='black', alpha=.55, label='Synthetic observations')
    for name, color in [('first_circle', '#1b9e77'), ('second_circle', '#7570b3')]:
        circle = result['B2'][name]
        if circle:
            ax.add_patch(CirclePatch(circle['center_m'], circle['radius_m'], fill=False, color=color, ls='--',
                                    label='B2 fitted '+name.replace('_', ' ')))
            ax.scatter(*circle['center_m'], marker='+', color=color, s=80)
    ax.set(xlabel='Plane x (m)', ylabel='Plane y up (m)', title='B2 geometry: radial reconstruction, not time prediction',
           xlim=(-.55, .55), ylim=(-.82, .10))
    ax.set_aspect('equal'); ax.legend(fontsize=7, loc='upper right')
    ax = fig.add_subplot(gs[1, 1])
    for label, prediction, color in [('B0', y0, '#d95f02'), ('B1', y1, '#1b9e77')]:
        error = np.linalg.norm(prediction[keep]-obs.xy_px[keep], axis=1)
        ax.plot(obs.t_s[keep], error, label=label, color=color)
    ax.axhline(np.sqrt(np.trace(obs.covariance_px2)), ls=':', color='gray', label='Assumed RMS noise floor')
    ax.set(xlabel='Time (s)', ylabel='Euclidean position residual (px)', title='Full trajectory discrepancy')
    ax.legend(fontsize=8)
    fig.suptitle(SCOPE, fontsize=13, fontweight='bold')
    fig.savefig(path, dpi=140, metadata={'Software': 'REALIGN POC-0'})
    plt.close(fig)


def _number(value):
    return 'unavailable' if value is None else f'{value:.4f}'


def _markdown(result):
    lines = ['# POC-0 Classical Scientific Baselines', '', f'**{SCOPE}**', '',
        f"Protocol seed: `{result['seed']}`. Acceptance checks: **{'PASS' if result['acceptance_passed'] else 'FAIL'}**.", '',
        'Reproduce: `python scripts/verify_baselines.py` (install with `python -m pip install -e ".[dev]"`).', '',
        '## Measured baseline results', '',
        'Each case uses two exploration training releases and one disjoint development release. '
        'These development trials are ordinary synthetic checks, **not sealed validation**. '
        'Scores below are on the unseen whole trial. B2 does not predict time trajectories; '
        'its radial reconstruction RMSE is a different statistic.', '',
        '| Case | B0 xy RMSE (px) | B1 xy RMSE (px) | B1 excess NRMSE | B2 result | B2 radial RMSE (px) | Peg error after fit (mm) |',
        '|---|---:|---:|---:|---|---:|---:|']
    for c in result['cases']:
        b1 = c['B1']['heldout'] or {}
        lines.append(f"| {c['case']} | {_number(c['B0']['heldout']['rmse_xy_px'])} | "
                     f"{_number(b1.get('rmse_xy_px'))} | {_number(b1.get('excess_nrmse'))} | "
                     f"{c['B2']['decision']} | {_number(c['B2']['heldout']['radial_rmse_px'])} | "
                     f"{_number(c['post_fit_truth_evaluation']['peg_error_mm'])} |")
    lines += ['', '## Conditions, algorithms and units', '',
        '- All observations are simulated. Duration 4 s; full grid 60 Hz; known scale 600 px/m; '
        'image pivot (640,160) px. Plane x right/y up, image x right/y down. Gravity 9.80665 m/s².',
        '- IID Gaussian localization noise has marginal covariance diag(0.25,0.25) px² '
        '(0.5 px SD per coordinate). Off-vertical trials drop 10% of samples independently; '
        'invalid rows remain NaN and are excluded. AR(1) generation and gap-aware whitening are unit-tested; '
        'this report uses phi=0. None of these noise levels was measured from a phone or SAM.',
        '- Nominal B0: L=0.72 m, gamma=0.06 s⁻¹, quadratic drag=0.02 m⁻¹. '
        'Release angle, release velocity=0 and release time=0 are prescribed and known. '
        'Projection, gravity and initial conditions are not inferred from the test trial.',
        '- B1: shared L, gamma and quadratic drag fitted to both training trials with eight '
        'deterministic starts, bounded SciPy TRF least-squares and soft-L1 loss. '
        'L uses log coordinates; nonnegative drag coefficients use direct coordinates to include exact zero. '
        'Bounds: L [0.4,1.1] m; gamma [0,0.6] s⁻¹; quadratic drag [0,0.6] m⁻¹. '
        'No tape prior is invented. Loss scale=max(1,1.4826*MAD) on whitened nominal training residuals. '
        'Every start, cost, bound hit, warning and failure appears in JSON.',
        '- Each B0/B1 prediction is one complete simulator rollout from release, with no resets to observations. '
        'Whitening uses spatial Cholesky covariance and phi^(sample-index gap) AR innovations. '
        'NRMSE divides Euclidean xy RMS by nominal length in pixels. The floor is the '
        '**assumed synthetic** trace(covariance), not a repeat-estimated real noise floor. '
        'Excess NRMSE subtracts that expectation before taking a square root.',
        '- B2: known original pivot, free first radius; search a polar-bearing boundary and either side; '
        'fit a free second center/radius with algebraic initialization followed by robust geometric least-squares. '
        'No hidden mode, event time or peg coordinate enters fitting. Short arcs fail minimum sample, '
        'span and noise-relative sagitta checks. Candidate geometry is compared by leave-one-whole-training-trial-out '
        'CV and a fixed conservative search/complexity penalty. The rule is a design diagnostic, '
        'not a null-calibrated p-value or a G3 decision gate. JSON gives both CV scores and penalty.',
        '- B2 uses observed bearing to assign a point to an arc. This is an observation-conditioned '
        'distance-to-geometry evaluation; it must not be compared numerically as a trajectory-prediction win over B1.', '',
        '## Fitted parameters and residual diagnostics', '',
        '| Case | L (m) | gamma (s⁻¹) | quadratic drag (m⁻¹) | B1 train xy RMSE (px) | Held-out innovation mean square / coordinate | Held-out lag-1 x |',
        '|---|---:|---:|---:|---:|---:|---:|']
    for c in result['cases']:
        b = c['B1']; p = b.get('params', {}); s = b['heldout'] or {}
        lines.append(f"| {c['case']} | {_number(p.get('length_m'))} | {_number(p.get('gamma_per_s'))} | "
                     f"{_number(p.get('quadratic_drag_per_m'))} | {_number((b['training'] or {}).get('rmse_xy_px'))} | "
                     f"{_number(s.get('innovation_mean_square_per_coordinate'))} | {_number(s.get('lag1_x'))} |")
    lines += ['', '## Negative controls, failures and limitations', '']
    for check in result['checks']:
        lines.append(f"- {'PASS' if check['passed'] else 'FAIL'}: {check['name']}")
    for c in result['cases']:
        lines.append(f"- `{c['case']}` B2: {c['B2']['reason']}. Rejected candidate fits: {c['B2']['failed_candidates']}.")
        for w in c['B1'].get('warnings', []):
            lines.append(f"  B1: {w}.")
        if not c['B1']['success']:
            lines.append(f"  B1 FAILED: {c['B1']['failure']}.")
    lines += ['',
        'A single observed circle cannot distinguish an absent peg from an unexcited peg. '
        'The short-arc case intentionally abstains geometrically. Peg cases leave systematic '
        'fixed-structure residuals; B2 localizes a second center but does not identify a unique causal mechanism.', '',
        'This small fixed-seed matrix is not an MDE/power study, false-positive calibration, '
        'CI-coverage experiment or real-world benchmark. No 300-trial coverage claim, bootstrap CI, '
        'SAM result, Muse result, sealed evaluation, structural dynamics fit or repair is claimed. '
        'B2 assumes one recurring bearing boundary and a known pivot/projection; arbitrary partial occlusion, '
        'multiple pegs, outliers, camera errors and correlated radial likelihood calibration remain limitations. '
        'B1 checks solver convergence/rank and reports bounds, but provides no calibrated parameter CIs.', '',
        '## Provenance and phase readiness', '',
        'Observations are exported separately to `poc0_observations.npz`, with public metadata and per-trial '
        'SHA-256 fingerprints in JSON. Synthetic truth is written to `poc0_truth_evaluation.json` '
        'only for post-fit evaluation. Inference packages have no truth imports or file reads; '
        'tests also run fitting in a subprocess denying synthetic imports. This is a dependency/input '
        'boundary, not the future OS-enforced sealed vault.', '',
        f"Source SHA-256: `{result['source_sha256']}`.", '',
        f"Environment: `{json.dumps(result['versions'], sort_keys=True)}`.", '',
        'G1 physics source is unchanged. Phase 1 acceptance is checked here; G2 and full G3 are **not passed**. '
        'Next: actual Meta access/structured-tool smoke tests, separate SAM MP4 tracking, PTS extraction, '
        'stationary and dynamic noise measurement, camera calibration and real recording QA (Phase 2). '
        'Real media and account access remain external blockers.', '',
        'Method reference: [SciPy least_squares documentation]'
        '(https://docs.scipy.org/doc/scipy/reference/generated/scipy.optimize.least_squares.html).', '',
        '![Synthetic held-out observations and model predictions](poc0_baselines.png)', '']
    return '\n'.join(lines)


def build_report(output_dir, *, seed=20261031, progress=None):
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    cases, private_records, public_metadata, arrays = [], [], [], {}
    nominal = PendulumParams(.72, gamma_per_s=.06, quadratic_drag_per_m=.02)
    plot_inputs = None
    for i, (name, params, angles, noise) in enumerate(_protocol()):
        if progress:
            progress(f'Fitting {name} (two training trials; one untouched development trial)')
        public, private = [], []
        for j, angle in enumerate(angles):
            trial_seed = int(np.random.SeedSequence([seed, i, j]).generate_state(1)[0])
            trial, truth = generate_trial(params, Experiment(angle), seed=trial_seed,
                trial_id=f'trial_{3*i+j:03d}', noise=noise, zone='exploration' if j < 2 else 'development')
            public.append(trial); private.append(truth)
            prefix = trial.trial_id
            arrays[prefix+'_t_s'] = trial.observation.t_s
            arrays[prefix+'_xy_px'] = trial.observation.xy_px
            arrays[prefix+'_valid'] = trial.observation.valid
            public_metadata.append({'trial_id': prefix, 'zone': trial.zone, 'experiment': asdict(trial.experiment),
                'projection': asdict(trial.projection), 'noise': asdict(noise),
                'observation_sha256': observation_fingerprint(trial)})
        # Freeze observation-only results BEFORE consulting any evaluation-only values.
        comparison = compare_baselines(public[:2], public[2:], nominal, FitOptions())
        peg = private[0].params.peg
        inferred = comparison['B2']['second_circle']
        error = None
        if peg is not None and inferred is not None:
            true_center = peg.distance_m*np.array([np.sin(peg.angle_rad), -np.cos(peg.angle_rad)])
            error = float(1000*np.linalg.norm(np.array(inferred['center_m'])-true_center))
        evaluation = {'peg_error_mm': error, 'contact_event_counts': [len(t.events) for t in private]}
        comparison.update(case=name, post_fit_truth_evaluation=evaluation)
        cases.append(comparison)
        private_records.append({'case': name, 'params': asdict(params),
            'trial_ids': [t.trial_id for t in public], 'seeds': [t.seed for t in private], **evaluation})
        if name == 'vertical_peg' and comparison['B1']['success']:
            plot_inputs = public[2], comparison
    by_name = {c['case']: c for c in cases}
    checks = []
    def check(name, passed):
        checks.append({'name': name, 'passed': bool(passed)})
    check('B1 solver converged on every attempted case', all(c['B1']['success'] for c in cases))
    for name in ('no_fault', 'parameter_fault'):
        c = by_name[name]
        check(name+': B1 held-out xy RMSE < 1.2 px', c['B1']['success'] and c['B1']['heldout']['rmse_xy_px'] < 1.2)
        true_l = private_records[[c['case'] for c in cases].index(name)]['params']['length_m']
        check(name+': fitted L within 2 mm', c['B1']['success'] and abs(c['B1']['params']['length_m']-true_l) < .002)
        check(name+': no spurious second pivot', c['B2']['decision'] == 'one_circle_only')
    for name in ('vertical_peg', 'off_vertical_peg'):
        c = by_name[name]
        check(name+': B1 leaves >8 px held-out discrepancy', c['B1']['success'] and c['B1']['heldout']['rmse_xy_px'] > 8.)
        check(name+': B2 supports second circle with <20 mm post-fit peg error',
              c['B2']['decision'] == 'two_circle' and c['post_fit_truth_evaluation']['peg_error_mm'] < 20.)
    check('unexcited peg has no contact or invented second pivot',
        by_name['unexcited_peg']['B2']['decision'] == 'one_circle_only' and
        not any(by_name['unexcited_peg']['post_fit_truth_evaluation']['contact_event_counts']))
    check('short noisy arcs produce an explicit ambiguous geometry result', by_name['short_arc']['B2']['decision'] == 'ambiguous')
    import matplotlib
    result = {'scope': SCOPE, 'seed': seed, 'source_sha256': _source_hash(),
        'versions': {'python': platform.python_version(), 'numpy': np.__version__, 'scipy': scipy.__version__,
                     'matplotlib': matplotlib.__version__},
        'protocol': {'duration_s': 4., 'sample_rate_hz': 60., 'training_trials_per_case': 2,
            'heldout_trials_per_case': 1, 'nominal_params': asdict(nominal),
            'fit_options': asdict(FitOptions()), 'heldout_role': 'non-sealed synthetic development only'},
        'observations': public_metadata, 'cases': cases, 'checks': checks,
        'acceptance_passed': all(c['passed'] for c in checks)}
    # JSON normalization makes the returned record identical to its persisted form.
    result = json.loads(json.dumps(result, allow_nan=False))
    (output/'poc0_baselines.json').write_text(json.dumps(result, indent=2, allow_nan=False)+'\n', encoding='utf-8')
    (output/'POC0_BASELINES.md').write_text(_markdown(result), encoding='utf-8')
    np.savez_compressed(output/'poc0_observations.npz', **arrays)
    (output/'poc0_truth_evaluation.json').write_text(json.dumps({
        'scope': 'POST-FIT SYNTHETIC TRUTH EVALUATION ONLY; never an inference input',
        'cases': private_records}, indent=2)+'\n', encoding='utf-8')
    if plot_inputs is not None:
        _plot(output/'poc0_baselines.png', *plot_inputs)
    else:
        raise RuntimeError('vertical-peg B1 failed; no valid comparison plot can be produced')
    return result

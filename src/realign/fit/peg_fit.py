"""B3: bounded, observation-only fitting of the existing one-peg dynamics.

No event labels are inputs. Every residual integrates the directed-event G1
kernel from release. A failed physical rollout terminates that start; it is
never replaced by a constant penalty that can look like convergence.
"""
from dataclasses import dataclass, asdict
import math
import numpy as np
from scipy.optimize import least_squares
from realign.contracts.video import VideoTrial
from realign.observation.camera import project, unproject
from realign.observation.noise import whiten, whiten_video
from realign.physics import PendulumParams, PegParams, simulate
from .robust_fit import FitError, residuals_free
from .circle_fit import _fit_two


@dataclass(frozen=True)
class PegFitOptions:
    n_starts: int = 8
    max_nfev: int = 60
    length_bounds_m: tuple = (.4, 1.1)
    gamma_bounds_per_s: tuple = (0., .6)
    quadratic_bounds_per_m: tuple = (0., .6)
    peg_fraction_bounds: tuple = (.005, .55)
    peg_angle_bounds_rad: tuple = (-.9, .9)
    contact_side: int = -1

    def __post_init__(self):
        if type(self.n_starts) is not int or type(self.max_nfev) is not int or not 8 <= self.n_starts <= 32 or not 1 <= self.max_nfev <= 300:
            raise ValueError('bounded budget requires 8..32 starts and 1..300 evaluations')
        for pair in (self.length_bounds_m, self.gamma_bounds_per_s, self.quadratic_bounds_per_m,
                     self.peg_fraction_bounds, self.peg_angle_bounds_rad):
            if len(pair) != 2 or not np.isfinite(pair).all() or pair[0] >= pair[1]:
                raise ValueError('finite ordered physical bounds required')
        if self.length_bounds_m[0] <= 0 or min(self.gamma_bounds_per_s[0], self.quadratic_bounds_per_m[0]) < 0:
            raise ValueError('positive length and nonnegative drag required')
        if not 0 < self.peg_fraction_bounds[0] < self.peg_fraction_bounds[1] <= .95:
            raise ValueError('peg fraction must preserve the supported contact radius')
        if max(abs(x) for x in self.peg_angle_bounds_rad) >= math.pi/2 or self.contact_side not in (-1, 1):
            raise ValueError('unsupported peg angle/wrap side')


@dataclass(frozen=True)
class PegFit:
    success: bool
    params: PendulumParams
    starts: tuple
    robust_cost: float
    f_scale: float
    identifiability: dict
    warnings: tuple
    options: dict


def predict_peg(params, trial):
    """Full pixel trajectory, including held pose before uncertain video release."""
    if params.peg is None:
        raise ValueError('B3 requires an explicit peg candidate')
    exp = trial.experiment
    relative = trial.observation.t_s - trial.release.time_s if isinstance(trial, VideoTrial) else trial.observation.t_s
    initial = params.length_m*np.array([np.sin(exp.release_angle_rad), -np.cos(exp.release_angle_rad)])
    xy = np.tile(initial, (len(relative), 1))
    post = relative >= 0
    times = np.unique(np.r_[0., relative[post]])
    if len(times) > 1:
        out = simulate(params, exp.release_angle_rad, exp.release_velocity_rad_per_s, times)
        xy[post] = out.xy_m[np.searchsorted(times, relative[post])]
    return project(xy, trial.projection)


def residuals_peg(params, trials):
    residuals = []
    for t in trials:
        obs = t.observation
        indices = np.flatnonzero(obs.valid)
        prediction = predict_peg(params, t)
        residual = prediction[indices] - obs.xy_px[indices]
        residuals.append((whiten_video(residual, t, prediction) if isinstance(t, VideoTrial)
                          else whiten(residual, indices, obs.covariance_px2, obs.ar1_phi)).ravel())
    return np.concatenate(residuals)


def _sensitivity(residual, x, lo, hi):
    columns = []
    for j in range(len(x)):
        a, b = x.copy(), x.copy()
        step = (hi[j]-lo[j])*1e-5
        a[j] = max(lo[j], x[j]-step); b[j] = min(hi[j], x[j]+step)
        columns.append((residual(b)-residual(a))/(b[j]-a[j])*(hi[j]-lo[j]))
    jac = np.array(columns).T
    _, sv, vt = np.linalg.svd(jac, full_matrices=False)
    rank = int(np.sum(sv > max(sv[0]*1e-5, 1e-8)))
    near_bound = bool(np.any(np.minimum(x-lo, hi-x)/(hi-lo) < 1e-4))
    std = None
    if rank == len(x) and not near_bound:
        cov_scaled = (vt.T / sv**2) @ vt
        cov_x = (hi-lo)[:, None]*cov_scaled*(hi-lo)[None, :]
        transform = np.eye(5)
        length = math.exp(x[0])
        transform[0, 0] = length
        transform[3] = [length*x[3], 0., 0., length, 0.]
        std = np.sqrt(np.diag(transform@cov_x@transform.T)).tolist()
    return {'parameter_coordinates': ['log_length', 'gamma_per_s', 'quadratic_per_m', 'peg_fraction', 'peg_angle_rad'],
            'scaled_singular_values': sv.tolist(), 'numerical_rank': rank,
            'rank_threshold_relative': 1e-5, 'condition_number': float(sv[0]/sv[-1]) if sv[-1] > 1e-12 else None,
            'weakest_scaled_direction': vt[-1].tolist(), 'near_bound': near_bound,
            'conditional_gaussian_std': std,
            'std_parameter_units': ['m', 's^-1', 'm^-1', 'm', 'rad'],
            'locally_identifiable': bool(rank == len(x) and not near_bound),
            'uncertainty_scope': 'local linear sensitivity only; no calibrated confidence interval or global uniqueness claim'}


def fit_peg(trials, nominal, options=PegFitOptions(), *, initializer=None):
    trials = tuple(trials)
    if not trials or nominal.peg is not None or any(t.zone != 'exploration' for t in trials):
        raise FitError('B3 requires exploration trials and a nominal free model')
    from .baselines import observation_fingerprint
    if len({t.trial_id for t in trials}) != len(trials) or len({observation_fingerprint(t) for t in trials}) != len(trials):
        raise FitError('duplicate exploration observations')
    if len({(t.observation.provenance, isinstance(t, VideoTrial), getattr(getattr(t.observation, 'metadata', None), 'source_kind', None)) for t in trials}) != 1:
        raise FitError('cannot mix observation provenances')
    if isinstance(trials[0], VideoTrial) and len({t.observation.metadata.video_sha256 for t in trials}) != len(trials):
        raise FitError('duplicate source video recordings')
    if any(t.observation.valid.sum() < 24 for t in trials):
        raise FitError('insufficient valid observations: minimum 24 per exploration trial')
    if max(abs(t.experiment.release_angle_rad) for t in trials) < .03:
        raise FitError('insufficient angular excitation for a structural fit')
    low_angle, high_angle = options.peg_angle_bounds_rad
    angles = [t.experiment.release_angle_rad for t in trials]
    if options.contact_side == -1:
        high_angle = min(high_angle, min(angles)-1e-3)
    else:
        low_angle = max(low_angle, max(angles)+1e-3)
    if low_angle >= high_angle:
        raise FitError('no peg angle permits the declared free-side releases')
    lo = np.array([math.log(options.length_bounds_m[0]), options.gamma_bounds_per_s[0], options.quadratic_bounds_per_m[0], options.peg_fraction_bounds[0], low_angle])
    hi = np.array([math.log(options.length_bounds_m[1]), options.gamma_bounds_per_s[1], options.quadratic_bounds_per_m[1], options.peg_fraction_bounds[1], high_angle])

    def decode(x):
        length = math.exp(x[0])
        return PendulumParams(length, g=nominal.g, gamma_per_s=float(x[1]), quadratic_drag_per_m=float(x[2]),
                              peg=PegParams(length*float(x[3]), float(x[4]), options.contact_side))

    def raw(x):
        return residuals_peg(decode(x), trials)

    null = residuals_free(nominal, trials)
    f_scale = max(1., float(1.4826*np.median(np.abs(null-np.median(null)))))
    initial = initializer or nominal
    if initial.peg is not None:
        raise FitError('initializer must be a free-model exploration fit')
    base = np.array([math.log(initial.length_m), initial.gamma_per_s, initial.quadratic_drag_per_m, .22, 0.])
    geometric, _ = _fit_two(trials)
    if geometric is not None:
        _, first, second, _, side = geometric
        center = np.array(second.center_m)
        radius = np.linalg.norm(center)
        if side == options.contact_side and radius > 0 and first.radius_m > 0:
            base[0] = math.log(first.radius_m)
            base[3:] = [radius/first.radius_m, math.atan2(center[0], -center[1])]
    starts, solutions = [], []
    for i in range(options.n_starts):
        x0 = base.copy()
        if i:
            x0[3] = lo[3]+(hi[3]-lo[3])*((i*.61803398875) % 1)
            x0[4] = lo[4]+(hi[4]-lo[4])*((i*.41421356237) % 1)
        x0 = np.clip(x0, lo+1e-8, hi-1e-8)
        entry = {'initial': asdict(decode(x0)), 'success': False, 'residual_calls': 0}

        def bounded(x):
            if entry['residual_calls'] >= 7*options.max_nfev:
                raise RuntimeError('residual evaluation budget exhausted')
            entry['residual_calls'] += 1
            return raw(x)

        try:
            sol = least_squares(bounded, x0, bounds=(lo, hi), method='trf', loss='soft_l1', f_scale=f_scale,
                                x_scale=hi-lo, diff_step=1e-5, max_nfev=options.max_nfev,
                                ftol=1e-8, xtol=1e-8, gtol=1e-6)
            ok = bool(sol.success and np.isfinite(sol.cost) and np.isfinite(sol.x).all())
            entry.update(success=ok, status=int(sol.status), nfev=int(sol.nfev), cost=float(sol.cost),
                         active_bounds=sol.active_mask.astype(int).tolist(), fitted_params=asdict(decode(sol.x)))
            if ok:
                solutions.append(sol)
        except (RuntimeError, ValueError, FloatingPointError, np.linalg.LinAlgError) as exc:
            entry.update(error_type=type(exc).__name__, message=str(exc))
        starts.append(entry)
    if not solutions:
        raise FitError('all B3 starts failed or exhausted their budgets', starts)
    best = min(solutions, key=lambda s: s.cost)
    warnings = []
    try:
        ident = _sensitivity(raw, best.x, lo, hi)
    except (RuntimeError, ValueError, FloatingPointError, np.linalg.LinAlgError):
        ident = {'locally_identifiable': False, 'numerical_rank': None,
                 'conditional_gaussian_std': None, 'failure': 'sensitivity rollout failed',
                 'uncertainty_scope': 'unavailable: perturbed physical rollout failed; no confidence interval claim'}
    if not ident['locally_identifiable']:
        warnings.append('peg mechanism/parameters not identified by this local fit')
    near = [s.x for s in solutions if s.cost <= best.cost+2.3]
    ident['near_optimal_multistart_coordinate_range'] = (np.ptp(near, axis=0)/(hi-lo)).tolist()
    ident['near_optimal_starts'] = len(near)
    ident['profile_likelihood'] = 'NOT_RUN; multistart spread is not a confidence interval'
    if any(not s['success'] for s in starts):
        warnings.append('some deterministic starts failed; all attempts retained')
    return PegFit(True, decode(best.x), tuple(starts), float(best.cost), f_scale, ident, tuple(warnings), asdict(options))


def score_peg(params, trials):
    squared, metric_squared, floor = [], [], []
    per_trial = []
    for t in trials:
        obs = t.observation; valid = obs.valid
        if not valid.any():
            raise ValueError('no valid observations to score')
        prediction = predict_peg(params, t)
        e = prediction[valid]-obs.xy_px[valid]
        m = unproject(prediction[valid], t.projection)-unproject(obs.xy_px[valid], t.projection)
        squared.extend(np.sum(e*e, axis=1)); metric_squared.extend(np.sum(m*m, axis=1))
        c = obs.frame_covariance_px2[valid] if isinstance(t, VideoTrial) else np.array([obs.covariance_px2])
        floor.extend(np.broadcast_to(np.trace(c, axis1=-2, axis2=-1), (int(valid.sum()),)))
        per_trial.append({'trial_id': t.trial_id, 'mse_xy_px2': float(np.mean(np.sum(e*e, axis=1)))})
    return {'rmse_xy_px': float(np.sqrt(np.mean(squared))), 'mse_xy_px2': float(np.mean(squared)),
            'rmse_xy_m': float(np.sqrt(np.mean(metric_squared))), 'assumed_localization_floor_mse_px2': float(np.mean(floor)),
            'valid_samples': len(squared), 'per_trial': per_trial}

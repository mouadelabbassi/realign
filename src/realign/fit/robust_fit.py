"""B1: joint full-trajectory free-pendulum fitting on allowed whole trials."""
from dataclasses import dataclass, field
import math
import numpy as np
from scipy.optimize import least_squares
from realign.contracts import Trial
from realign.observation.camera import project
from realign.observation.noise import whiten
from realign.physics import PendulumParams, simulate


class FitError(RuntimeError):
    def __init__(self, message, starts=()):
        super().__init__(message)
        self.starts = tuple(starts)


@dataclass(frozen=True)
class FitOptions:
    n_starts: int = 8
    max_nfev: int = 120
    length_bounds_m: tuple = (.4, 1.1)
    gamma_bounds_per_s: tuple = (0., .6)
    quadratic_bounds_per_m: tuple = (0., .6)
    fit_quadratic_drag: bool = True

    def __post_init__(self):
        if self.n_starts < 8 or self.max_nfev < 1:
            raise ValueError('at least eight starts and positive max_nfev required')
        for bounds in (self.length_bounds_m, self.gamma_bounds_per_s, self.quadratic_bounds_per_m):
            if len(bounds) != 2 or not np.isfinite(bounds).all() or not 0 <= bounds[0] < bounds[1]:
                raise ValueError('invalid physical parameter bounds')
        if self.length_bounds_m[0] <= 0:
            raise ValueError('length must be positive')


@dataclass(frozen=True)
class FreeFit:
    success: bool
    params: PendulumParams
    starts: tuple
    robust_cost: float
    f_scale: float
    jacobian_singular_values: tuple
    warnings: tuple = field(default_factory=tuple)


def predict_free(params: PendulumParams, trial: Trial):
    if params.peg is not None:
        raise ValueError('B0/B1 require the original fixed free-pendulum structure')
    exp = trial.experiment
    out = simulate(params, exp.release_angle_rad, exp.release_velocity_rad_per_s, trial.observation.t_s)
    return project(out.xy_m, trial.projection)


def residuals_free(params, trials):
    residuals = []
    for trial in trials:
        obs = trial.observation
        indices = np.flatnonzero(obs.valid)
        residual = predict_free(params, trial)[indices]-obs.xy_px[indices]
        residuals.append(whiten(residual, indices, obs.covariance_px2, obs.ar1_phi).ravel())
    return np.concatenate(residuals)


def fit_free(trials, nominal: PendulumParams, options: FitOptions = FitOptions()):
    trials = tuple(trials)
    if not trials or nominal.peg is not None:
        raise FitError('B1 needs exploration trials and a nominal free model')
    if len({t.trial_id for t in trials}) != len(trials):
        raise FitError('duplicate training trial IDs')
    if any(t.observation.valid.sum() < 12 for t in trials):
        raise FitError('insufficient valid observations (minimum 12 per trial)')
    if max(abs(t.experiment.release_angle_rad) + abs(t.experiment.release_velocity_rad_per_s) for t in trials) < 1e-5:
        raise FitError('unexcited dynamics: drag parameters are not identifiable')
    lo = [math.log(options.length_bounds_m[0]), options.gamma_bounds_per_s[0]]
    hi = [math.log(options.length_bounds_m[1]), options.gamma_bounds_per_s[1]]
    if options.fit_quadratic_drag:
        lo.append(options.quadratic_bounds_per_m[0]); hi.append(options.quadratic_bounds_per_m[1])
    lo, hi = np.array(lo), np.array(hi)

    def decode(x):
        return PendulumParams(math.exp(x[0]), g=nominal.g, gamma_per_s=float(x[1]),
            quadratic_drag_per_m=float(x[2]) if options.fit_quadratic_drag else nominal.quadratic_drag_per_m)

    def residual(x):
        return residuals_free(decode(x), trials)

    # The scale is derived ONLY from the nominal training residuals, never test data.
    null_residual = residuals_free(nominal, trials)
    f_scale = max(1., float(1.4826*np.median(np.abs(null_residual-np.median(null_residual)))))
    base = np.array([math.log(nominal.length_m), nominal.gamma_per_s] +
                    ([nominal.quadratic_drag_per_m] if options.fit_quadratic_drag else []))
    attempts, solutions = [], []
    for i in range(options.n_starts):
        if i == 0:
            x0 = base.copy()
        else:
            # Deterministic coverage of bounds plus a nominal start. No hidden labels.
            fractions = np.mod(np.array([.61803398875, .41421356237, .73205080757])[:len(lo)]*i, 1.)
            x0 = lo + (hi-lo)*fractions
        x0 = np.clip(x0, lo+1e-9, hi-1e-9)
        entry = {'initial': decode(x0).__dict__, 'success': False, 'cost': None, 'nfev': 0}
        try:
            result = least_squares(residual, x0, bounds=(lo, hi), method='trf', loss='soft_l1',
                f_scale=f_scale, x_scale='jac', max_nfev=options.max_nfev, ftol=1e-8, xtol=1e-8, gtol=1e-7)
            entry.update(success=bool(result.success and np.isfinite(result.cost) and np.isfinite(result.x).all()),
                cost=float(result.cost) if np.isfinite(result.cost) else None, nfev=int(result.nfev),
                status=int(result.status), message=str(result.message),
                active_bounds=[int(x) for x in result.active_mask],
                fitted_params=decode(result.x).__dict__ if np.isfinite(result.x).all() else None)
            if entry['success']:
                solutions.append(result)
        except (RuntimeError, ValueError, FloatingPointError, np.linalg.LinAlgError) as exc:
            entry['message'] = f'{type(exc).__name__}: {exc}'
        attempts.append(entry)
    if not solutions:
        raise FitError('all multistart fits failed', attempts)
    best = min(solutions, key=lambda s: s.cost)
    sv = np.linalg.svd(best.jac, compute_uv=False)
    if sv[-1] <= 1e-10*sv[0]:
        raise FitError('rank-deficient parameter fit', attempts)
    warnings = []
    if np.any(best.active_mask) or np.any(np.minimum(best.x-lo, hi-best.x)/(hi-lo) < 1e-5):
        warnings.append('best fit is at or near physical bounds; no unconstrained parameter/CI claim')
    if any(not s['success'] for s in attempts):
        warnings.append('some starts failed; see every attempt below')
    return FreeFit(True, decode(best.x), tuple(attempts), float(best.cost), f_scale,
                   tuple(float(v) for v in sv), tuple(warnings))

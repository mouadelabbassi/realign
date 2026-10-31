"""B2: spatial arc segmentation and whole-trial CV, without mode/event labels.

Known calibrated original pivot is O. Fit radius of the O circle; search a
polar-bearing threshold and side for a second free-center circle. Repeated
passes share the same geometry. This is geometric reconstruction, not dynamics.
"""
from dataclasses import dataclass
import numpy as np
from scipy.optimize import least_squares
from realign.observation.camera import unproject


class CircleFitError(RuntimeError):
    pass


@dataclass(frozen=True)
class Circle:
    center_m: tuple
    radius_m: float
    arc_span_rad: float
    radial_rmse_m: float


@dataclass(frozen=True)
class GeometryFit:
    decision: str
    reason: str
    first_circle: Circle | None = None
    second_circle: Circle | None = None
    threshold_rad: float | None = None
    second_side: int | None = None
    cv_one_score: float | None = None
    cv_two_score: float | None = None
    complexity_penalty: float | None = None
    failed_candidates: int = 0


def _arc_span(points, center):
    delta = points-np.asarray(center)
    angles = np.sort(np.mod(np.arctan2(delta[:, 1], delta[:, 0]), 2*np.pi))
    return float(2*np.pi - np.max(np.diff(np.r_[angles, angles[0]+2*np.pi])))


def fit_circle(points_m, *, sigma_m: float, fixed_center=None):
    points = np.asarray(points_m, dtype=float)
    if points.ndim != 2 or points.shape[1:] != (2,) or len(points) < 12 or not np.isfinite(points).all():
        raise CircleFitError('at least 12 finite xy samples required')
    if not np.isfinite(sigma_m) or sigma_m < 0:
        raise CircleFitError('invalid metric localization noise')
    centered = points-points.mean(axis=0)
    singular = np.linalg.svd(centered, compute_uv=False)
    if singular[-1] < max(1e-10, singular[0]*1e-4):
        raise CircleFitError('degenerate collinear or stationary arc')
    scale = max(sigma_m, 1e-10)
    try:
        if fixed_center is not None:
            center = np.asarray(fixed_center, dtype=float)
            radii = np.linalg.norm(points-center, axis=1)
            sol = least_squares(lambda x: (radii-x[0])/scale, [np.median(radii)],
                bounds=([1e-6], [10.]), method='trf', loss='soft_l1', f_scale=1.)
            radius = float(sol.x[0])
        else:
            # Center before algebraic initialization to avoid translation sensitivity.
            A = np.column_stack([2*centered, np.ones(len(points))])
            v, _, rank, _ = np.linalg.lstsq(A, np.sum(centered**2, axis=1), rcond=None)
            if rank < 3:
                raise CircleFitError('degenerate algebraic circle')
            center0 = points.mean(axis=0)+v[:2]
            radius0 = float(np.mean(np.linalg.norm(points-center0, axis=1)))
            if not 1e-6 < radius0 < 10.:
                raise CircleFitError('degenerate initial radius')
            sol = least_squares(lambda x: (np.linalg.norm(points-x[:2], axis=1)-x[2])/scale,
                np.r_[center0, radius0], bounds=([-10., -10., 1e-6], [10., 10., 10.]),
                method='trf', loss='soft_l1', f_scale=1., max_nfev=100)
            center, radius = sol.x[:2], float(sol.x[2])
        if not sol.success or not np.isfinite(sol.x).all():
            raise CircleFitError('circle solver failed to converge')
    except (RuntimeError, ValueError, FloatingPointError, np.linalg.LinAlgError) as exc:
        raise CircleFitError(f'circle solver failed: {exc}') from exc
    span = _arc_span(points, center)
    sagitta = radius*(1-np.cos(min(span, np.pi)/2))
    if span < .20 or sagitta < max(4*sigma_m, 1e-8):
        raise CircleFitError('degenerate short arc: curvature below localization uncertainty')
    residual = np.linalg.norm(points-center, axis=1)-radius
    return Circle(tuple(float(v) for v in center), radius, span, float(np.sqrt(np.mean(residual**2))))


def _points(trials):
    points, scales, sigmas = [], [], []
    for trial in trials:
        obs = trial.observation
        points.append(unproject(obs.xy_px[obs.valid], trial.projection))
        scales.extend([trial.projection.scale_px_per_m]*int(obs.valid.sum()))
        # Conservative largest localization standard deviation for anisotropic noise.
        sigma = np.sqrt(max(0., np.linalg.eigvalsh(obs.covariance_px2).max()))/trial.projection.scale_px_per_m
        sigmas.extend([max(float(sigma), 1e-9)]*int(obs.valid.sum()))
    return np.concatenate(points), np.array(scales), np.array(sigmas)


def _mask(points, threshold, side):
    bearing = np.arctan2(points[:, 0], -points[:, 1])
    return side*(bearing-threshold) >= 0


def _distances(points, first, second=None, threshold=None, side=None):
    distance = np.linalg.norm(points-first.center_m, axis=1)-first.radius_m
    if second is not None:
        m = _mask(points, threshold, side)
        distance[m] = np.linalg.norm(points[m]-second.center_m, axis=1)-second.radius_m
    return distance


def _fit_two(trials):
    points, _, sigmas = _points(trials)
    bearings = np.arctan2(points[:, 0], -points[:, 1])
    # Hypothesis family fixed in advance: 25 thresholds x 2 wrap sides.
    thresholds = np.quantile(bearings, np.linspace(.18, .82, 25))
    best, failed = None, 0
    for threshold in thresholds:
        for side in (-1, 1):
            mask = _mask(points, threshold, side)
            try:
                first = fit_circle(points[~mask], sigma_m=float(np.median(sigmas[~mask])), fixed_center=(0., 0.))
                second = fit_circle(points[mask], sigma_m=float(np.median(sigmas[mask])))
                score = float(np.sum((_distances(points, first, second, threshold, side)/sigmas)**2))
                if best is None or score < best[0]:
                    best = score, first, second, float(threshold), side
            except CircleFitError:
                failed += 1
    return best, failed


def fit_geometry(trials):
    trials = tuple(trials)
    if not trials or any(t.observation.valid.sum() < 24 for t in trials):
        return GeometryFit('ambiguous', 'insufficient valid geometry samples')
    if len({t.trial_id for t in trials}) != len(trials):
        raise ValueError('duplicate training trial IDs')
    points, _, sigmas = _points(trials)
    try:
        one = fit_circle(points, sigma_m=float(np.median(sigmas)), fixed_center=(0., 0.))
    except CircleFitError as exc:
        return GeometryFit('ambiguous', str(exc))
    if len(trials) < 2:
        return GeometryFit('ambiguous', 'need at least two whole trials for geometric selection', one)
    cv_one, cv_two, failed = 0., 0., 0
    complete = True
    for i, held_trial in enumerate(trials):
        training = trials[:i]+trials[i+1:]
        train_points, _, train_sigmas = _points(training)
        test_points, _, test_sigmas = _points([held_trial])
        try:
            fold_one = fit_circle(train_points, sigma_m=float(np.median(train_sigmas)), fixed_center=(0., 0.))
            two, count = _fit_two(training)
            failed += count
            cv_one += float(np.sum((_distances(test_points, fold_one)/test_sigmas)**2))
            if two is None:
                complete = False
            else:
                _, c0, c1, threshold, side = two
                cv_two += float(np.sum((_distances(test_points, c0, c1, threshold, side)/test_sigmas)**2))
        except CircleFitError:
            complete = False
    two, count = _fit_two(trials)
    failed += count
    # Explicit conservative design penalty, NOT a calibrated p-value/LRT or G3 gate.
    # 1 vs 5 continuous parameters, plus the fixed 50-candidate search cost.
    # Correlated localization reduces effective evidence; raw CV scores are scaled.
    n_eff = sum(t.observation.valid.sum()*(1-abs(t.observation.ar1_phi))/(1+abs(t.observation.ar1_phi)) for t in trials)
    factor = n_eff/len(points)
    cv_one *= factor; cv_two *= factor
    penalty = float(4*np.log(max(n_eff, 2)) + 2*np.log(50))
    if not complete or two is None:
        return GeometryFit('ambiguous', 'second-circle candidate failed arc/solver checks in at least one CV fold',
                           one, cv_one_score=cv_one, complexity_penalty=penalty, failed_candidates=failed)
    if cv_one-cv_two <= penalty:
        return GeometryFit('one_circle_only', 'no supported second pivot; unexcited mechanisms remain possible', one,
                           cv_one_score=cv_one, cv_two_score=cv_two, complexity_penalty=penalty, failed_candidates=failed)
    _, c0, c1, threshold, side = two
    return GeometryFit('two_circle', 'two recurring arcs improve whole-trial CV beyond the design penalty',
                       c0, c1, threshold, side, cv_one, cv_two, penalty, failed)


def score_geometry(fit: GeometryFit, trials):
    if fit.first_circle is None:
        return {'radial_rmse_px': None, 'valid_samples': 0}
    points, scales, _ = _points(trials)
    distance_px = _distances(points, fit.first_circle, fit.second_circle, fit.threshold_rad, fit.second_side)*scales
    return {'radial_rmse_px': float(np.sqrt(np.mean(distance_px**2))), 'valid_samples': len(points)}

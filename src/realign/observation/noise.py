import numpy as np
from realign.contracts import NoiseConfig, covariance


def sample_noise(n: int, config: NoiseConfig, rng: np.random.Generator):
    c = np.asarray(config.covariance_px2)
    values, vectors = np.linalg.eigh(c)
    root = vectors @ np.diag(np.sqrt(np.maximum(values, 0.)))
    draws = rng.standard_normal((n, 2)) @ root.T
    if config.ar1_phi:
        innovation_scale = np.sqrt(1-config.ar1_phi**2)
        for i in range(1, n):
            draws[i] = config.ar1_phi*draws[i-1] + innovation_scale*draws[i]
    return draws


def whiten(residual_px, sample_indices, covariance_px2, ar1_phi):
    """Spatial Cholesky whitening, then stationary gap-aware AR(1) innovations.

    Sample indices refer to the original full grid, not the compressed valid rows.
    Each trial starts with its marginal distribution, independently of other trials.
    """
    c = np.asarray(covariance(covariance_px2))
    if np.linalg.eigvalsh(c).min() <= 0:
        raise ValueError('whitening requires positive definite localization covariance')
    indices = np.asarray(sample_indices)
    r = np.asarray(residual_px)
    if r.shape != (len(indices), 2) or not np.isfinite(r).all() or np.any(np.diff(indices) <= 0):
        raise ValueError('finite residual pairs and increasing sample indices required')
    if not np.isfinite(ar1_phi) or not -.95 < ar1_phi < .95:
        raise ValueError('invalid AR(1) coefficient')
    z = np.linalg.solve(np.linalg.cholesky(c), r.T).T
    innovations = z.copy()
    if len(indices) > 1 and ar1_phi:
        a = ar1_phi**np.diff(indices)
        innovations[1:] = (z[1:]-a[:, None]*z[:-1])/np.sqrt(1-a[:, None]**2)
    return innovations

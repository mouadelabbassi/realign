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


def whiten_video(residual_px,trial,prediction_px):
    """Heteroscedastic localization + PTS rounding + COMMON release-time error.

    Release covariance is a rank-one term across the entire recording, not N
    independent timing errors. This is a linearized uncertainty calculation.
    """
    obs=trial.observation
    indices=np.flatnonzero(obs.valid)
    velocity=np.gradient(prediction_px,obs.t_s,axis=0)[indices]
    c=obs.frame_covariance_px2[indices].copy()
    c+=obs.timestamp_sigma_s**2*velocity[:,:,None]*velocity[:,None,:]
    roots=np.linalg.cholesky(c)
    z=np.linalg.solve(roots,np.asarray(residual_px)[...,None])[...,0]
    a=np.linalg.solve(roots,(-velocity*trial.release.sigma_s)[...,None])[...,0]
    if obs.ar1_phi and len(indices)>1:
        correlation=obs.ar1_phi**(np.diff(obs.t_s[indices])/obs.noise.reference_dt_s)
        def innovations(value):
            v=value.copy()
            v[1:]=(value[1:]-correlation[:,None]*value[:-1])/np.sqrt(1-correlation[:,None]**2)
            return v
        z=innovations(z); a=innovations(a)
    flat=z.ravel(); sensitivity=a.ravel()
    norm=float(sensitivity@sensitivity)
    if norm>1e-20:
        flat=flat-(1-1/np.sqrt(1+norm))*sensitivity*(sensitivity@flat)/norm
    return flat.reshape(-1,2)

"""Empirical tracking uncertainty; release variability is reported separately."""
import numpy as np
from realign.contracts.video import NoiseEstimate


def stationary_noise(xy_px,valid,*,source_ids,provenance,t_s=None):
    xy=np.asarray(xy_px,dtype=float); valid=np.asarray(valid,dtype=bool)
    points=xy[valid]
    if len(points)<5 or not np.isfinite(points).all():
        raise ValueError('at least five valid stationary reference centers required')
    cov=np.cov(points.T)
    # Explicit conservative digitization floor, not claimed measured SAM jitter.
    eig,vec=np.linalg.eigh(cov)
    cov=vec@np.diag(np.maximum(eig,1/12))@vec.T
    residual=xy-np.median(points,axis=0)
    pair=valid[:-1]&valid[1:]
    phi=0.
    if pair.sum()>10:
        values=[]
        for axis in range(2):
            a=residual[:-1,axis][pair]; b=residual[1:,axis][pair]
            if min(a.std(),b.std())>1e-8:
                values.append(float(np.corrcoef(a,b)[0,1]))
        phi=float(np.clip(max(values,default=0.),0.,.94))
    dt=float(np.median(np.diff(t_s))) if t_s is not None else .04
    return NoiseEstimate(tuple(map(tuple,cov)),(0.,0.),phi,dt,tuple(source_ids),provenance,'stationary_center_covariance',
        ('stationary motion/camera drift can inflate noise','eigenvalues floored at 1/12 px² for digitization',
         'nonnegative common-axis AR(1) approximation; dynamic correlation requires real checks'))


def reviewed_noise(tracked_px,reviewed_px,*,source_ids,provenance):
    error=np.asarray(tracked_px,dtype=float)-np.asarray(reviewed_px,dtype=float)
    if error.ndim!=2 or error.shape[1:]!=(2,) or len(error)<5 or not np.isfinite(error).all():
        raise ValueError('at least five paired reviewed frame centers required')
    bias=error.mean(axis=0)
    cov=np.cov(error.T)
    return NoiseEstimate(tuple(map(tuple,cov)),tuple(bias),0.,.04,tuple(source_ids),provenance,
                         'paired_manual_review_residuals',
                         ('review annotation error is included; bias is systematic and is not silently corrected',))


def combine_noise(estimates):
    estimates=tuple(estimates)
    if not estimates or len({e.provenance for e in estimates})!=1:
        raise ValueError('cannot mix real and synthetic uncertainty estimates')
    variance=max(max(np.linalg.eigvalsh(e.covariance_px2)) for e in estimates)
    variance=max(variance,1/12)
    ids=tuple(dict.fromkeys(i for e in estimates for i in e.source_ids))
    bias=max((e.bias_px for e in estimates),key=lambda x:np.linalg.norm(x))
    return NoiseEstimate(((variance,0.),(0.,variance)),bias,max(e.ar1_phi for e in estimates),
        estimates[0].reference_dt_s,ids,estimates[0].provenance,'conservative_covariance_envelope',
        tuple(dict.fromkeys(s for e in estimates for s in e.limitations)))


def repeatability(trials):
    """Whole-release variation is not identified as tracker noise from repeats."""
    if len(trials)<2:
        return {'status':'insufficient_repeats','n_trials':len(trials)}
    provenance={t.observation.provenance for t in trials}
    if len(provenance)!=1:
        raise ValueError('cannot mix real and synthetic repeats')
    angles=[t.experiment.release_angle_rad for t in trials]
    return {'status':'release_variability_reported_separately','n_trials':len(trials),
            'release_angle_sd_rad':float(np.std(angles,ddof=1)),
            'release_offsets_pts_s':[t.release.time_s for t in trials],
            'release_timing_sigma_s':[t.release.sigma_s for t in trials],
            'limitation':'repeat trajectory dispersion combines physical release variation and tracking error; no pure dynamic-noise claim'}

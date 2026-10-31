"""Minimal validated POC-0 contracts; deliberately no hidden-mechanism fields."""
from dataclasses import dataclass, field
import math
import numpy as np


def covariance(value):
    c = np.array(value, dtype=float, copy=True)
    if c.shape != (2, 2) or not np.isfinite(c).all():
        raise ValueError('covariance must be a finite 2x2 matrix in px²')
    if not np.allclose(c, c.T, rtol=0., atol=1e-12):
        raise ValueError('covariance must be symmetric')
    if np.linalg.eigvalsh(c).min() < -1e-12:
        raise ValueError('covariance must be positive semidefinite')
    return tuple(map(tuple, .5*(c+c.T)))


@dataclass(frozen=True)
class PlaneProjection:
    """Known synthetic similarity map: plane x right/y up -> image x right/y down."""
    scale_px_per_m: float = 600.
    pivot_px: tuple[float, float] = (640., 160.)

    def __post_init__(self):
        if not math.isfinite(self.scale_px_per_m) or self.scale_px_per_m <= 0:
            raise ValueError('scale_px_per_m must be finite and positive')
        if np.asarray(self.pivot_px).shape != (2,) or not np.isfinite(self.pivot_px).all():
            raise ValueError('pivot_px must be a finite pair')
        object.__setattr__(self, 'pivot_px', tuple(self.pivot_px))


@dataclass(frozen=True)
class Experiment:
    release_angle_rad: float
    duration_s: float = 4.
    sample_rate_hz: float = 60.
    release_velocity_rad_per_s: float = 0.

    def __post_init__(self):
        if not all(math.isfinite(x) for x in (self.release_angle_rad, self.duration_s,
                    self.sample_rate_hz, self.release_velocity_rad_per_s)):
            raise ValueError('experiment values must be finite')
        if abs(self.release_angle_rad) >= math.pi/2 or not 0 < self.duration_s <= 60:
            raise ValueError('unsupported release angle or duration')
        if not 1 <= self.sample_rate_hz <= 1000 or self.duration_s*self.sample_rate_hz < 1:
            raise ValueError('experiment needs at least two samples')

    def times(self):
        return np.linspace(0., self.duration_s, int(round(self.duration_s*self.sample_rate_hz))+1)


@dataclass(frozen=True)
class NoiseConfig:
    """Assumed stationary localization covariance, NOT measured SAM performance.

    Common AR(1) coefficient per sample; covariance is marginal (not innovation).
    Timestamp jitter, rolling shutter and calibration errors are outside this slice.
    """
    covariance_px2: tuple = ((.25, 0.), (0., .25))
    ar1_phi: float = 0.
    dropout_probability: float = 0.

    def __post_init__(self):
        object.__setattr__(self, 'covariance_px2', covariance(self.covariance_px2))
        if not math.isfinite(self.ar1_phi) or not -.95 < self.ar1_phi < .95:
            raise ValueError('ar1_phi must be in (-.95,.95)')
        if not math.isfinite(self.dropout_probability) or not 0 <= self.dropout_probability <= 1:
            raise ValueError('dropout_probability must be in [0,1]')


@dataclass(frozen=True)
class Observation:
    t_s: np.ndarray
    xy_px: np.ndarray
    valid: np.ndarray
    covariance_px2: tuple = ((.25, 0.), (0., .25))
    ar1_phi: float = 0.
    position_unit: str = 'px'
    covariance_unit: str = 'px^2'
    time_unit: str = 's'
    frame: str = 'image_x_right_y_down'
    provenance: str = 'SYNTHETIC'

    def __post_init__(self):
        if (self.position_unit, self.covariance_unit, self.time_unit, self.frame) != (
                'px', 'px^2', 's', 'image_x_right_y_down'):
            raise ValueError('unsupported units or reference frame')
        if self.provenance != 'SYNTHETIC':
            raise ValueError('POC-0 accepts explicitly SYNTHETIC observations only')
        t = np.array(self.t_s, dtype=float, copy=True)
        xy = np.array(self.xy_px, dtype=float, copy=True)
        valid = np.array(self.valid, copy=True)
        if t.ndim != 1 or len(t) < 2 or t[0] != 0. or not np.isfinite(t).all() or np.any(np.diff(t) <= 0):
            raise ValueError('timestamps must be finite, increasing seconds beginning at release t=0')
        if xy.shape != (len(t), 2) or valid.shape != t.shape or valid.dtype != np.bool_:
            raise ValueError('positions need shape (N,2); validity must be Boolean (N,)')
        if not np.isfinite(xy[valid]).all():
            raise ValueError('valid positions must be finite')
        # Invalid data never become measurements through interpolation.
        xy[~valid] = np.nan
        for name, value in [('t_s', t), ('xy_px', xy), ('valid', valid)]:
            value.flags.writeable = False
            object.__setattr__(self, name, value)
        object.__setattr__(self, 'covariance_px2', covariance(self.covariance_px2))
        NoiseConfig(self.covariance_px2, self.ar1_phi)
        if self.ar1_phi and not np.allclose(np.diff(t), np.diff(t)[0], rtol=1e-8, atol=1e-12):
            raise ValueError('AR(1) contract requires the full uniform grid; retain invalid samples')


@dataclass(frozen=True)
class Trial:
    trial_id: str
    experiment: Experiment
    observation: Observation
    projection: PlaneProjection = field(default_factory=PlaneProjection)
    zone: str = 'exploration'

    def __post_init__(self):
        if not self.trial_id or self.zone not in ('exploration', 'development'):
            raise ValueError('nonempty opaque id and allowed non-sealed zone required')
        if not np.isclose(self.observation.t_s[-1], self.experiment.duration_s, rtol=0, atol=1e-10):
            raise ValueError('observation duration disagrees with experiment')

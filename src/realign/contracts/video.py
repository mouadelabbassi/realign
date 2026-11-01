"""Video contracts alongside the unchanged Task 01 synthetic records.

Original PTS are recording coordinates. Release uncertainty is common to a
whole trial and must never be added as independent localization noise.
"""
from dataclasses import dataclass
from fractions import Fraction
import math
from datetime import datetime
import numpy as np
from . import Experiment, covariance
from .external import ExternalVideoSource


def readonly(value, dtype=float):
    a=np.array(value,dtype=dtype,copy=True)
    a.flags.writeable=False
    return a


@dataclass(frozen=True)
class VideoMetadata:
    video_sha256: str
    source_kind: str
    width: int
    height: int
    coded_width: int
    coded_height: int
    pts: tuple
    time_base: str
    codec: str
    rotation_deg: int = 0
    recording_start_utc: str | None = None
    container_creation_utc: str | None = None
    external_source: ExternalVideoSource | None = None

    def __post_init__(self):
        if self.source_kind not in ('REAL_PHONE','REAL_EXTERNAL','SYNTHETIC_RENDER'):
            raise ValueError('explicit video source kind required')
        if self.source_kind == 'REAL_EXTERNAL':
            if not isinstance(self.external_source, ExternalVideoSource) or self.external_source.processed_sha256 != self.video_sha256:
                raise ValueError('external video requires attribution and matching processed hash')
        elif self.external_source is not None:
            raise ValueError('external attribution must not masquerade as phone/synthetic provenance')
        if len(self.video_sha256)!=64 or any(x not in '0123456789abcdef' for x in self.video_sha256):
            raise ValueError('SHA-256 required')
        if min(self.width,self.height,self.coded_width,self.coded_height)<=0 or max(self.width,self.height)>4096:
            raise ValueError('unsupported video size')
        if self.rotation_deg not in (0,90,180,270):
            raise ValueError('only right-angle display rotations supported')
        pts=tuple(self.pts)
        if len(pts)<2 or len(pts)>10000 or any(type(v) is not int for v in pts):
            raise ValueError('integer presentation timestamps required')
        if any(b<=a for a,b in zip(pts,pts[1:])) or Fraction(self.time_base)<=0:
            raise ValueError('strictly increasing PTS and positive time base required')
        if (pts[-1]-pts[0])*float(Fraction(self.time_base))>60.1:
            raise ValueError('clips must be <=60 seconds')
        object.__setattr__(self,'pts',pts)
        for value in (self.recording_start_utc,self.container_creation_utc):
            if value is not None:
                parsed=datetime.fromisoformat(value.replace('Z','+00:00'))
                if parsed.tzinfo is None:
                    raise ValueError('recording/creation metadata must include a timezone')

    @property
    def t_s(self):
        return readonly(np.array(self.pts)*float(Fraction(self.time_base)))

    @property
    def variable_frame_rate(self):
        return len(set(np.diff(self.pts)))>1


@dataclass(frozen=True)
class PlanarCalibration:
    calibration_id: str
    H_plane_to_undistorted_px: tuple
    image_size: tuple
    pivot_px: tuple
    reprojection_rms_px: float
    check_rms_px: float | None
    source: str
    n_fit_points: int
    n_check_points: int
    camera_matrix: tuple | None = None
    distortion: tuple | None = None
    intrinsics_id: str | None = None
    lens_rms_px: float | None = None
    limitations: tuple = ()

    def __post_init__(self):
        h=np.asarray(self.H_plane_to_undistorted_px,dtype=float)
        if not self.calibration_id or h.shape!=(3,3) or not np.isfinite(h).all() or abs(np.linalg.det(h))<1e-12:
            raise ValueError('invertible calibrated homography required')
        if self.source not in ('REAL_MEASURED','SYNTHETIC_FIXTURE'):
            raise ValueError('explicit calibration source required')
        if len(self.image_size)!=2 or min(self.image_size)<=0 or len(self.pivot_px)!=2 or not np.isfinite(self.pivot_px).all():
            raise ValueError('invalid image size or pivot')
        for x in (self.reprojection_rms_px,self.check_rms_px,self.lens_rms_px):
            if x is not None and (not math.isfinite(x) or x<0):
                raise ValueError('finite nonnegative reprojection errors required')
        if self.n_fit_points<4 or self.n_check_points<0:
            raise ValueError('insufficient calibration correspondences')
        if (self.camera_matrix is None)!=(self.distortion is None):
            raise ValueError('camera matrix and distortion must be provided together')
        if self.camera_matrix is not None:
            k=np.asarray(self.camera_matrix,dtype=float)
            d=np.asarray(self.distortion,dtype=float)
            if k.shape!=(3,3) or not np.isfinite(k).all() or min(k[0,0],k[1,1])<=0 or not np.isfinite(d).all() or d.size not in (4,5,8,12,14):
                raise ValueError('invalid lens calibration')
            if not self.intrinsics_id:
                raise ValueError('lens calibration reference required')
        object.__setattr__(self,'H_plane_to_undistorted_px',tuple(map(tuple,h)))
        for name in ('image_size','pivot_px','limitations'):
            object.__setattr__(self,name,tuple(getattr(self,name)))
        if self.camera_matrix is not None:
            object.__setattr__(self,'camera_matrix',tuple(map(tuple,self.camera_matrix)))
            object.__setattr__(self,'distortion',tuple(self.distortion))

    @property
    def scale_px_per_m(self):
        # Area-equivalent local scale at the pivot. Actual transforms remain projective.
        h=np.asarray(self.H_plane_to_undistorted_px)
        j=(h[:2,:2]*h[2,2]-h[:2,2,None]*h[2,:2])/h[2,2]**2
        return float(np.sqrt(abs(np.linalg.det(j))))


@dataclass(frozen=True)
class ReleaseEstimate:
    time_s: float
    sigma_s: float
    lower_s: float
    upper_s: float
    method: str

    def __post_init__(self):
        if not all(math.isfinite(v) for v in (self.time_s,self.sigma_s,self.lower_s,self.upper_s)):
            raise ValueError('finite release timing required')
        if self.sigma_s<=0 or not self.lower_s<=self.time_s<=self.upper_s or self.lower_s>=self.upper_s:
            raise ValueError('release uncertainty/bracket invalid')
        if not self.method:
            raise ValueError('release timing method required')


@dataclass(frozen=True)
class NoiseEstimate:
    covariance_px2: tuple
    bias_px: tuple
    ar1_phi: float
    reference_dt_s: float
    source_ids: tuple
    provenance: str
    method: str
    limitations: tuple = ()

    def __post_init__(self):
        object.__setattr__(self,'covariance_px2',covariance(self.covariance_px2))
        if self.provenance not in ('SYNTHETIC','REAL_SAM') or not self.source_ids:
            raise ValueError('noise provenance and reference recording IDs required')
        if not 0<=self.ar1_phi<.95 or not math.isfinite(self.reference_dt_s) or self.reference_dt_s<=0:
            raise ValueError('invalid noise correlation/time base')
        if len(self.bias_px)!=2 or not np.isfinite(self.bias_px).all():
            raise ValueError('finite review bias required')
        object.__setattr__(self,'bias_px',tuple(self.bias_px))
        object.__setattr__(self,'source_ids',tuple(self.source_ids))
        object.__setattr__(self,'limitations',tuple(self.limitations))


@dataclass(frozen=True)
class VideoObservation:
    recording_id: str
    metadata: VideoMetadata
    xy_px: np.ndarray
    valid: np.ndarray
    frame_covariance_px2: np.ndarray
    flags: np.ndarray
    noise: NoiseEstimate
    calibration_id: str
    provenance: str
    sam_source: str
    covariance_unit: str = 'px^2'
    position_unit: str = 'px'
    time_unit: str = 's'
    frame: str = 'raw_display_image_x_right_y_down'
    timestamp_sigma_s: float = 0.

    def __post_init__(self):
        n=len(self.metadata.pts)
        if (self.covariance_unit,self.position_unit,self.time_unit,self.frame)!=(
                'px^2','px','s','raw_display_image_x_right_y_down'):
            raise ValueError('unsupported units/frame')
        actual=self.metadata.source_kind in ('REAL_PHONE','REAL_EXTERNAL') and self.sam_source=='REAL_API'
        if self.metadata.source_kind in ('REAL_PHONE','REAL_EXTERNAL') and not actual:
            raise ValueError('physical video observations require actual SAM output')
        if self.provenance!=('REAL_SAM' if actual else 'SYNTHETIC') or self.noise.provenance!=self.provenance:
            raise ValueError('real, synthetic and simulated-API provenance cannot be mixed')
        if not self.calibration_id or not self.recording_id:
            raise ValueError('recording and calibration references required')
        xy=np.asarray(self.xy_px,dtype=float); valid=np.asarray(self.valid)
        c=np.asarray(self.frame_covariance_px2,dtype=float); flags=np.asarray(self.flags)
        if xy.shape!=(n,2) or valid.shape!=(n,) or valid.dtype!=np.bool_ or flags.shape!=(n,):
            raise ValueError('per-frame positions, Boolean validity and quality flags required')
        if c.shape!=(n,2,2) or not np.isfinite(c).all() or not np.allclose(c,c.transpose(0,2,1),atol=1e-12):
            raise ValueError('per-frame covariance must be symmetric (N,2,2) px²')
        if np.linalg.eigvalsh(c).min()<=0 or not np.isfinite(xy[valid]).all():
            raise ValueError('positive definite covariance and finite valid centers required')
        if not math.isfinite(self.timestamp_sigma_s) or self.timestamp_sigma_s<0:
            raise ValueError('timestamp uncertainty must be nonnegative seconds')
        xy=xy.copy(); xy[~valid]=np.nan
        for name,value,dtype in [('xy_px',xy,float),('valid',valid,bool),
                                  ('frame_covariance_px2',c,float),('flags',flags,np.uint32)]:
            object.__setattr__(self,name,readonly(value,dtype))

    @property
    def t_s(self):
        return self.metadata.t_s

    @property
    def covariance_px2(self):
        return self.noise.covariance_px2

    @property
    def ar1_phi(self):
        return self.noise.ar1_phi


@dataclass(frozen=True)
class VideoTrial:
    trial_id: str
    experiment: Experiment
    observation: VideoObservation
    projection: PlanarCalibration
    release: ReleaseEstimate
    zone: str = 'exploration'

    def __post_init__(self):
        if self.zone not in ('exploration','development') or self.trial_id!=self.observation.recording_id:
            raise ValueError('allowed non-sealed recording zone and matching opaque ID required')
        if self.projection.calibration_id!=self.observation.calibration_id:
            raise ValueError('calibration reference mismatch')
        if self.observation.provenance=='REAL_SAM' and self.projection.source!='REAL_MEASURED':
            raise ValueError('real observations require measured calibration')
        if self.observation.metadata.source_kind == 'REAL_EXTERNAL' and not self.observation.metadata.external_source.capture_time_scale_verified:
            raise ValueError('external dynamics require verified physical capture time scale')
        t=self.observation.t_s
        if not t[0]<self.release.lower_s<=self.release.time_s<=self.release.upper_s<t[-1]:
            raise ValueError('release must be bracketed inside recording')

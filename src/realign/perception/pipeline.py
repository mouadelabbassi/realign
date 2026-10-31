"""Turn a SAM mask track into a calibrated, timestamp-preserving trial."""
from fractions import Fraction
import numpy as np
from realign.contracts import Experiment
from realign.contracts.video import VideoObservation,VideoTrial
from realign.observation.camera import unproject
from .timing import estimate_release


def make_video_trial(recording_id,metadata,run,track,calibration,noise,*,zone='exploration',manual_release_bracket=None):
    if metadata.source_kind=='REAL_PHONE' and run.source!='REAL_API':
        raise ValueError('real phone recordings require actual SAM processing, not simulated masks')
    if run.video_sha256!=metadata.video_sha256 or tuple(calibration.image_size)!=(metadata.width,metadata.height):
        raise ValueError('recording/calibration frame mismatch')
    provenance='REAL_SAM' if metadata.source_kind=='REAL_PHONE' and run.source=='REAL_API' else 'SYNTHETIC'
    if provenance!=noise.provenance:
        raise ValueError('noise and recording provenance differ')
    release=estimate_release(metadata.t_s,track.xy_px,track.valid,noise.covariance_px2,
                             manual_bracket=manual_release_bracket)
    pre=track.valid&(metadata.t_s<=release.lower_s)
    if pre.sum()<3:
        raise ValueError('insufficient visible held bob before release')
    initial_xy=unproject(np.median(track.xy_px[pre],axis=0)[None,:],calibration)[0]
    angle=float(np.arctan2(initial_xy[0],-initial_xy[1]))
    base=np.asarray(noise.covariance_px2)
    inflation=1+np.nan_to_num(track.contour_rmse_px,nan=0.)**2/.5**2
    frame_cov=inflation[:,None,None]*base[None,:,:]
    observation=VideoObservation(recording_id,metadata,track.xy_px,track.valid,frame_cov,track.flags,
        noise,calibration.calibration_id,provenance,run.source,
        timestamp_sigma_s=float(Fraction(metadata.time_base))/np.sqrt(12))
    duration=float(metadata.t_s[-1]-release.time_s)
    experiment=Experiment(angle,duration,1/float(np.median(np.diff(metadata.t_s))))
    return VideoTrial(recording_id,experiment,observation,calibration,release,zone)

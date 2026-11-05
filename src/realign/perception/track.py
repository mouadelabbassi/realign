"""Bob contour centers and explicit tracking QA. Never detects objects from RGB."""
from dataclasses import dataclass
from enum import IntFlag
import numpy as np
from scipy.optimize import least_squares
from realign.contracts.video import readonly
from .sam_client import SamError


class TrackFlag(IntFlag):
    MISSING=1
    EMPTY=2
    IDENTITY=4
    SHAPE=8
    AREA=16
    SPEED=32
    CONFIDENCE=64
    BOUNDARY=128


@dataclass(frozen=True)
class TrackConfig:
    min_area_px: int = 12
    min_confidence: float = .3
    min_inlier_fraction: float = .55
    max_contour_rmse_px: float = 2.
    max_area_ratio: float = 2.
    min_translated_iou: float = .3
    max_speed_px_per_s: float = 3000.
    max_missing_fraction: float = .1


@dataclass(frozen=True)
class Track:
    xy_px: np.ndarray
    valid: np.ndarray
    flags: np.ndarray
    area_px: np.ndarray
    contour_rmse_px: np.ndarray
    translated_iou: np.ndarray
    confidence: np.ndarray
    summary: dict


def _circle_center(mask,seed):
    import cv2
    contours,_=cv2.findContours(mask.pixels.astype(np.uint8),cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_NONE)
    if not contours:
        raise ValueError('empty contour')
    points=max(contours,key=cv2.contourArea).reshape(-1,2).astype(float)
    if len(points)<12:
        raise ValueError('too few boundary points')
    rng=np.random.default_rng(seed)
    best=None
    for _ in range(96):
        a,b,c=points[rng.choice(len(points),3,replace=False)]
        matrix=2*np.stack([b-a,c-a])
        if abs(np.linalg.det(matrix))<1e-6:
            continue
        center=np.linalg.solve(matrix,np.array([b@b-a@a,c@c-a@a]))
        radius=np.linalg.norm(a-center)
        if not 1.<radius<150.:
            continue
        error=np.abs(np.linalg.norm(points-center,axis=1)-radius)
        inliers=error<1.2
        score=(int(inliers.sum()),-float(np.median(error)))
        if best is None or score>best[0]:
            best=(score,center,radius,inliers)
    if best is None:
        raise ValueError('no circular contour')
    _,center,radius,inliers=best
    sol=least_squares(lambda x:np.linalg.norm(points[inliers]-x[:2],axis=1)-x[2],
                      np.r_[center,radius],loss='soft_l1',f_scale=.5,max_nfev=60)
    if not sol.success or not np.isfinite(sol.x).all():
        raise ValueError('contour fit did not converge')
    residual=np.linalg.norm(points[inliers]-sol.x[:2],axis=1)-sol.x[2]
    return sol.x[:2]+[mask.left,mask.top],float(np.sqrt(np.mean(residual**2))),float(inliers.mean())


def _translated_iou(a,b):
    def pixels(mask):
        y,x=np.nonzero(mask.pixels)
        if not len(x):
            return set()
        x=x-int(round(x.mean())); y=y-int(round(y.mean()))
        return set(zip(x.tolist(),y.tolist()))
    pa,pb=pixels(a),pixels(b)
    return len(pa&pb)/max(len(pa|pb),1)


def extract_track(run,metadata,*,object_id=None,config=TrackConfig()):
    if run.video_sha256!=metadata.video_sha256:
        raise SamError('SAM output belongs to another recording',code='input_changed')
    identities={m.object_id for m in run.masks}
    if object_id is None and len(identities)>1:
        raise SamError('ambiguous bob identity; explicitly review/select the track ID',code='identity')
    selected=object_id if object_id is not None else next(iter(identities),None)
    by_frame={m.frame_index:m for m in run.masks if m.object_id==selected}
    other_frames={m.frame_index for m in run.masks if m.object_id!=selected}
    n=len(metadata.pts)
    xy=np.full((n,2),np.nan); valid=np.zeros(n,bool); flags=np.zeros(n,np.uint32)
    area=np.zeros(n); rmse=np.full(n,np.nan); iou=np.full(n,np.nan); confidence=np.full(n,np.nan)
    previous=None; previous_index=None; previous_center=None
    for i in range(n):
        mask=by_frame.get(i)
        if mask is None:
            flags[i]=int(TrackFlag.IDENTITY if i in other_frames else TrackFlag.MISSING)
            continue
        area[i]=mask.pixels.sum()
        if area[i]<config.min_area_px:
            flags[i]|=int(TrackFlag.EMPTY); continue
        if mask.confidence is not None:
            confidence[i]=mask.confidence
            if mask.confidence<config.min_confidence:
                flags[i]|=int(TrackFlag.CONFIDENCE)
        if mask.left==0 or mask.top==0 or mask.left+mask.pixels.shape[1]>=metadata.width or mask.top+mask.pixels.shape[0]>=metadata.height:
            flags[i]|=int(TrackFlag.BOUNDARY)
        try:
            center,rmse[i],fraction=_circle_center(mask,i)
        except (ValueError,np.linalg.LinAlgError):
            flags[i]|=int(TrackFlag.SHAPE); continue
        if rmse[i]>config.max_contour_rmse_px or fraction<config.min_inlier_fraction:
            flags[i]|=int(TrackFlag.SHAPE)
        if previous is not None:
            ratio=max(area[i]/area[previous_index],area[previous_index]/area[i])
            if ratio>config.max_area_ratio:
                flags[i]|=int(TrackFlag.AREA)
            iou[i]=_translated_iou(previous,mask)
            if iou[i]<config.min_translated_iou:
                flags[i]|=int(TrackFlag.SHAPE)
            speed=np.linalg.norm(center-previous_center)/(metadata.t_s[i]-metadata.t_s[previous_index])
            if speed>config.max_speed_px_per_s:
                flags[i]|=int(TrackFlag.SPEED)
        if flags[i]==0:
            xy[i]=center; valid[i]=True
            previous=mask; previous_index=i; previous_center=center
    fraction_missing=float(1-valid.mean())
    summary={'frames':n,'valid_frames':int(valid.sum()),'missing_or_rejected_fraction':fraction_missing,
             'object_id':selected,'unknown_confidence_frames':int(np.isnan(confidence).sum()),
             'quality':'ok' if fraction_missing<=config.max_missing_fraction else 'quarantined',
             'flag_counts':{f.name:int(np.count_nonzero(flags&int(f))) for f in TrackFlag}}
    return Track(*(readonly(a,dtype) for a,dtype in [(xy,float),(valid,bool),(flags,np.uint32),(area,float),
                 (rmse,float),(iou,float),(confidence,float)]),summary)

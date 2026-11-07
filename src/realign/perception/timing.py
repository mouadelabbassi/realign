"""Release onset estimated independently of the subsequent full trajectory fit."""
import numpy as np
from realign.contracts.video import ReleaseEstimate


def estimate_release(t_s,xy_px,valid,covariance_px2,*,manual_bracket=None):
    t=np.asarray(t_s,dtype=float); xy=np.asarray(xy_px,dtype=float); valid=np.asarray(valid,dtype=bool)
    if manual_bracket is not None:
        lo,hi=map(float,manual_bracket)
        if not t[0]<lo<hi<t[-1]:
            raise ValueError('manual release bracket must lie inside recording PTS')
        return ReleaseEstimate((lo+hi)/2,(hi-lo)/np.sqrt(12),lo,hi,'manual_frame_bracket')
    indices=np.flatnonzero(valid)
    if len(indices)<12:
        raise ValueError('insufficient observations for release estimation')
    t=t[indices]; xy=xy[indices]
    dt=float(np.median(np.diff(t)))
    anchor=np.median(xy[:5],axis=0)
    sigma=np.sqrt(max(np.linalg.eigvalsh(covariance_px2).max(),1/12))
    threshold=max(1.,4*sigma)
    if np.max(np.linalg.norm(xy[:5]-anchor,axis=1))>threshold:
        raise ValueError('release cannot be estimated: no stationary lead-in')
    distance=np.linalg.norm(xy-anchor,axis=1)
    crossing=next((i for i in range(5,len(t)-2) if np.all(distance[i:i+3]>threshold)),None)
    if crossing is None:
        raise ValueError('no observed release onset; stationary or insufficient motion')
    end=min(t[crossing]+.20,t[-1])
    used=t<=end
    grid=np.linspace(t[4],t[crossing],81)
    costs=[]
    for onset in grid:
        basis=np.maximum(t[used]-onset,0.)**2
        coefficient=(basis[:,None]*(xy[used]-anchor)).sum(axis=0)/max(basis@basis,1e-20)
        residual=(xy[used]-anchor)-basis[:,None]*coefficient
        costs.append(float(np.sum(residual**2)/sigma**2))
    best=int(np.argmin(costs)); onset=float(grid[best])
    supported=grid[np.array(costs)<=costs[best]+4.]
    lo=max(float(t[0]+dt/4),min(float(supported.min()),onset-dt))
    hi=min(float(t[-1]-dt/4),max(float(supported.max()),onset+dt))
    if hi-lo>.35 or best==0:
        raise ValueError('release onset unresolved; review a tighter manual frame bracket')
    return ReleaseEstimate(onset,max(dt/np.sqrt(12),(hi-lo)/np.sqrt(12)),lo,hi,'local_quadratic_onset_profile')

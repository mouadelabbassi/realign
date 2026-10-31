import numpy as np
from realign.contracts import PlaneProjection
from realign.contracts.video import PlanarCalibration


def _homography(points, h):
    p=np.asarray(points,dtype=float)
    shape=p.shape
    q=np.c_[p.reshape(-1,2),np.ones(p.size//2)] @ np.asarray(h).T
    if np.any(np.abs(q[:,2])<1e-12):
        raise ValueError('point lies on projective horizon')
    return (q[:,:2]/q[:,2,None]).reshape(shape)


def _undistort(points, calibration):
    if calibration.camera_matrix is None:
        return np.asarray(points,dtype=float)
    import cv2
    p=np.asarray(points,dtype=float)
    if p.size==0:
        return p.copy()
    k=np.asarray(calibration.camera_matrix)
    return cv2.undistortPoints(p.reshape(-1,1,2),k,np.asarray(calibration.distortion),P=k).reshape(p.shape)


def _distort(points, calibration):
    if calibration.camera_matrix is None:
        return np.asarray(points,dtype=float)
    import cv2
    p=np.asarray(points,dtype=float)
    if p.size==0:
        return p.copy()
    k=np.asarray(calibration.camera_matrix)
    norm=_homography(p,np.linalg.inv(k))
    xyz=np.c_[norm.reshape(-1,2),np.ones(p.size//2)]
    return cv2.projectPoints(xyz,np.zeros(3),np.zeros(3),k,np.asarray(calibration.distortion))[0].reshape(p.shape)


def project(xy_m, projection: PlaneProjection):
    if isinstance(projection,PlanarCalibration):
        return _distort(_homography(xy_m,projection.H_plane_to_undistorted_px),projection)
    return np.asarray(xy_m)*[projection.scale_px_per_m, -projection.scale_px_per_m] + projection.pivot_px


def unproject(xy_px, projection: PlaneProjection):
    if isinstance(projection,PlanarCalibration):
        return _homography(_undistort(xy_px,projection),np.linalg.inv(projection.H_plane_to_undistorted_px))
    return (np.asarray(xy_px)-projection.pivot_px)/[projection.scale_px_per_m, -projection.scale_px_per_m]


def camera_jacobian(xy_px, calibration):
    """d(metric xy)/d(raw displayed px), including lens correction."""
    p=np.asarray(xy_px,dtype=float).reshape(-1,2)
    jac=np.empty((len(p),2,2))
    for axis in range(2):
        step=np.zeros(2); step[axis]=.001
        jac[:,:,axis]=(unproject(p+step,calibration)-unproject(p-step,calibration))/.002
    return jac

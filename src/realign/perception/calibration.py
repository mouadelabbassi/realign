"""Measured plane correspondences, gravity/pivot localization and optional lens fit."""
import numpy as np
from realign.contracts.video import PlanarCalibration
from realign.observation.camera import _homography, _undistort, _distort, project


def fit_planar_calibration(board_xy_m, image_xy_px, *, pivot_px, hanging_px,
                           image_size, calibration_id, source, check_board_xy_m=None,
                           check_image_xy_px=None, camera_matrix=None, distortion=None,
                           intrinsics_id=None,lens_rms_px=None,unit='m'):
    import cv2
    board=np.asarray(board_xy_m,dtype=float); image=np.asarray(image_xy_px,dtype=float)
    if unit!='m' or board.ndim!=2 or board.shape[1:]!=(2,) or image.shape!=board.shape or len(board)<4:
        raise ValueError('at least four corresponding finite metric/px calibration points required')
    if not np.isfinite(board).all() or not np.isfinite(image).all():
        raise ValueError('nonfinite calibration')
    if len(image_size)!=2 or any(not isinstance(x,(int,np.integer)) or x<=0 for x in image_size):
        raise ValueError('displayed image dimensions must be positive integers')
    controls_px=np.asarray([pivot_px,hanging_px],dtype=float)
    if controls_px.shape!=(2,2) or not np.isfinite(controls_px).all():
        raise ValueError('finite pivot and hanging reference pixel pairs required')
    for pixels in (image,controls_px):
        if np.any(pixels<0) or np.any(pixels>=np.array(image_size)):
            raise ValueError('calibration pixels outside the displayed source frame')
    if np.linalg.matrix_rank(np.c_[board,np.ones(len(board))])<3 or np.linalg.matrix_rank(np.c_[image,np.ones(len(image))])<3:
        raise ValueError('degenerate collinear calibration points')
    temporary=PlanarCalibration(calibration_id,tuple(map(tuple,np.eye(3))),tuple(image_size),tuple(pivot_px),
        0.,None,source,len(board),0,camera_matrix,distortion,intrinsics_id,lens_rms_px)
    corrected=_undistort(image,temporary)
    h,_=cv2.findHomography(board,corrected,method=0)
    if h is None or not np.isfinite(h).all() or abs(np.linalg.det(h))<1e-12:
        raise ValueError('degenerate homography')
    controls=_homography(_undistort(np.array([pivot_px,hanging_px]),temporary),np.linalg.inv(h))
    origin,hang=controls
    down=hang-origin
    if np.linalg.norm(down)<.03:
        raise ValueError('hanging stationary reference must resolve gravity direction')
    up=-down/np.linalg.norm(down)
    right=np.array([up[1],-up[0]])
    basis=np.column_stack([right,up])
    plane_to_board=np.eye(3); plane_to_board[:2,:2]=basis; plane_to_board[:2,2]=origin
    final_h=h@plane_to_board
    fit_error=_distort(_homography(board,h),temporary)-image
    rms=float(np.sqrt(np.mean(np.sum(fit_error**2,axis=1))))
    n_check=0; check_rms=None
    if (check_board_xy_m is None)!=(check_image_xy_px is None):
        raise ValueError('both held-out checkpoint arrays required')
    if check_board_xy_m is not None:
        cb=np.asarray(check_board_xy_m,dtype=float); ci=np.asarray(check_image_xy_px,dtype=float)
        if cb.ndim!=2 or cb.shape[1:]!=(2,) or ci.shape!=cb.shape or len(cb)<1 or not np.isfinite(cb).all() or not np.isfinite(ci).all():
            raise ValueError('invalid held-out checkpoint arrays')
        if np.any(ci<0) or np.any(ci>=np.array(image_size)):
            raise ValueError('checkpoint pixels outside displayed source frame')
        if any(np.any(np.linalg.norm(board-p,axis=1)<1e-8) for p in cb):
            raise ValueError('calibration check points must be disjoint from fit points')
        n_check=len(cb)
        error=_distort(_homography(cb,h),temporary)-ci
        check_rms=float(np.sqrt(np.mean(np.sum(error**2,axis=1))))
    limitations=['single planar scene; scale/pivot/gravity measurement errors are systematic, not independent frame noise',
                 'rolling shutter, stabilization and out-of-plane motion are not corrected']
    if camera_matrix is None:
        limitations.append('lens distortion not measured; homography alone does not remove lens distortion')
    return PlanarCalibration(calibration_id,tuple(map(tuple,final_h)),tuple(image_size),tuple(pivot_px),
        rms,check_rms,source,len(board),n_check,camera_matrix,distortion,intrinsics_id,lens_rms_px,tuple(limitations))


def calibrate_lens(object_points_m, image_points_px, image_size):
    """Checkerboard corners from >=5 distinct views, in the displayed image frame."""
    import cv2
    if len(object_points_m)<5 or len(object_points_m)!=len(image_points_px):
        raise ValueError('at least five checkerboard views required')
    objects=[]; images=[]
    for obj,img in zip(object_points_m,image_points_px):
        obj=np.asarray(obj,dtype=np.float32); img=np.asarray(img,dtype=np.float32)
        if obj.ndim!=2 or obj.shape[1]!=3 or img.shape!=(len(obj),2) or len(obj)<12 or not np.isfinite(obj).all() or not np.isfinite(img).all():
            raise ValueError('invalid measured checkerboard corners')
        objects.append(obj); images.append(img)
    rms,k,d,_,_=cv2.calibrateCamera(objects,images,tuple(image_size),None,None)
    if not np.isfinite(k).all() or not np.isfinite(d).all() or not np.isfinite(rms):
        raise ValueError('lens calibration failed')
    return {'camera_matrix':k.tolist(),'distortion':d.ravel().tolist(),'lens_rms_px':float(rms),
            'n_views':len(objects),'image_size':list(image_size)}

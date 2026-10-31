import numpy as np
from realign.contracts import PlaneProjection


def project(xy_m, projection: PlaneProjection):
    return np.asarray(xy_m)*[projection.scale_px_per_m, -projection.scale_px_per_m] + projection.pivot_px


def unproject(xy_px, projection: PlaneProjection):
    return (np.asarray(xy_px)-projection.pivot_px)/[projection.scale_px_per_m, -projection.scale_px_per_m]

"""Media preflight reuses the existing original-PTS parser; no tracking fallback."""
from pathlib import Path
from realign.perception.video import probe_video,VideoError

def admit_recording(path,manifest,*,seen_hashes=(),track=None):
    if manifest.get('source_kind')!='REAL_PHONE':return {'status':'REJECTED','code':'CONTROLLED_PROVENANCE_REQUIRED'}
    try:
        metadata=probe_video(path,source_kind='REAL_PHONE')
    except VideoError as exc:return {'status':'REJECTED','code':exc.code}
    if metadata.video_sha256 in seen_hashes:return {'status':'REJECTED','code':'DUPLICATE_HASH'}
    if track is not None and (len(track.valid)!=len(metadata.pts) or float(track.valid.mean())<.75):
        return {'status':'REJECTED','code':'COVERAGE_BELOW_THRESHOLD'}
    return {'status':'ADMITTED','scope':'MEDIA_PREFLIGHT_ONLY; NOT_PHYSICAL_VALIDATION',
        'video_sha256':metadata.video_sha256,'original_pts':list(metadata.pts),'time_base':metadata.time_base,
        'rotation_deg':metadata.rotation_deg,'variable_frame_rate_allowed':True}

def calibration_grade(record):
    required=('scale_reference','pivot_px','roll_reference','noise_reference','capture_timing_reference')
    missing=[k for k in required if not record.get(k)]
    if record.get('source_kind')!='REAL_PHONE' or record.get('capture_time_scale_verified') is not True:
        missing.append('VERIFIED_CONTROLLED_CAPTURE_TIMING')
    grade='SUFFICIENT' if not missing else 'PARTIAL' if any(record.get(k) for k in required) else 'NONE'
    return {'grade':grade,'missing':missing,'units':['px','m','mm'] if grade=='SUFFICIENT' else ['px'],
        'timing_basis':'VERIFIED_CAPTURE' if grade=='SUFFICIENT' else 'PTS_ONLY',
        'scale':'MEASURED_PLANE' if grade=='SUFFICIENT' else 'UNKNOWN'}

def require_physical_calibration(record):
    grade=calibration_grade(record)
    if grade['grade']!='SUFFICIENT':raise ValueError('INSUFFICIENT_CALIBRATION: physical fitting refused')
    return grade

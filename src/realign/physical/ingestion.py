"""Existing SAM/calibration ingestion, restricted to controlled exploration data."""
from dataclasses import replace
from pathlib import Path
import json
import numpy as np
from realign.audit.chain import canonical,digest
from realign.contracts import Experiment
from realign.contracts.video import VideoMetadata
from realign.observation.camera import _undistort,_distort,_homography
from realign.perception.workflow import process_manifest,_path
from realign.product.evidence import read_json
from realign.product.store import write_json


def analysis_window(trial,window=None):
    """Contiguous observation window retaining original integer PTS and frame map."""
    o=trial.observation; n=len(o.metadata.pts)
    if window is None:
        if n>256 or trial.experiment.duration_s>4:
            raise ValueError('explicit analysis_window_pts_s required for clips exceeding 256 samples / 4 post-release seconds')
        return trial,{'original_frame_indices':list(range(n)),'original_pts':list(o.metadata.pts)}
    if len(window)!=2 or not all(type(x) in (int,float) and np.isfinite(x) for x in window) or window[0]>=window[1]:
        raise ValueError('finite increasing absolute PTS-seconds analysis window required')
    indices=np.flatnonzero((o.t_s>=window[0])&(o.t_s<=window[1]))
    if len(indices)<6 or len(indices)>256 or o.t_s[indices[-1]]-trial.release.time_s>4:
        raise ValueError('analysis window violates the existing observation budget')
    if o.t_s[indices[0]]>=trial.release.lower_s or o.t_s[indices[-1]]<=trial.release.upper_s:
        raise ValueError('analysis window must retain the independent release bracket')
    meta=replace(o.metadata,pts=tuple(o.metadata.pts[i] for i in indices))
    obs=replace(o,metadata=meta,xy_px=o.xy_px[indices],valid=o.valid[indices],
                frame_covariance_px2=o.frame_covariance_px2[indices],flags=o.flags[indices])
    exp=replace(trial.experiment,duration_s=float(meta.t_s[-1]-trial.release.time_s))
    return replace(trial,observation=obs,experiment=exp),{'original_frame_indices':indices.tolist(),'original_pts':list(meta.pts)}


def input_blockers(config,root):
    blockers=[]
    if config.get('source_kind')!='REAL_PHONE':return ['CONTROLLED_REAL_PHONE_MANIFEST_REQUIRED']
    if config.get('capture_time_scale_verified') is not True or not config.get('capture_timing_reference'):
        blockers.append('INDEPENDENT_CAPTURE_TIMING_REFERENCE_REQUIRED')
    for label,value in [('MEASURED_CALIBRATION',config.get('calibration_file')),('INDEPENDENT_MANUAL_REVIEWS',config.get('manual_reviews'))]:
        if not value or not _path(value,root).is_file():blockers.append(label+'_NOT_SUPPLIED')
    nominal=config.get('nominal_params',{})
    if type(nominal.get('length_m')) not in (float,int) or nominal['length_m']<=0:blockers.append('MEASURED_NOMINAL_LENGTH_REQUIRED')
    records=[config.get('stationary',{})]+list(config.get('exploration',[]))
    if len(config.get('exploration',[]))<2:blockers.append('TWO_EXPLORATION_RECORDINGS_REQUIRED')
    for r in records:
        if not r.get('video') or not _path(r['video'],root).is_file():blockers.append('RECORDING_NOT_SUPPLIED:'+str(r.get('id','stationary')))
    if len({r.get('comparison_group','setup_01') for r in records[1:]})>1:blockers.append('ONE_FIXED_RIG_COMPARISON_GROUP_REQUIRED')
    return blockers


def independent_rows(document):
    if (type(document) is not dict or document.get('annotation_source')!='INDEPENDENT_HUMAN' or
        document.get('independent_of_sam') is not True or not document.get('reviewer') or not document.get('rows')):
        raise ValueError('independently reviewed human annotations and attestation required')
    result=[];seen=set()
    for raw in document['rows']:
        row=dict(raw); key=(row.get('recording_id'),row.get('frame_index'))
        if key in seen or type(key[1]) is not int or not row.get('video_sha256') or not row.get('center_px'):
            raise ValueError('unique hash-bound manual frame references required')
        seen.add(key); row.setdefault('reviewer',document['reviewer']);result.append(row)
    return result


async def ingest_phone(manifest,output,*,run_api=False,cache_dir=None):
    """Never opens development/sealed paths; the independent custodian owns them."""
    manifest=Path(manifest).resolve();root=manifest.parent;out=Path(output);out.mkdir(parents=True,exist_ok=True)
    config=read_json(manifest);blockers=input_blockers(config,root)
    if blockers:return {'status':'BLOCKED_INPUTS','blockers':blockers,'trials':[],'config':config}
    document=read_json(_path(config['manual_reviews'],root))
    try:rows=independent_rows(document)
    except ValueError:return {'status':'BLOCKED_INPUTS','blockers':['INDEPENDENT_MANUAL_ANNOTATIONS_NOT_VALIDATED'],'trials':[],'config':config}
    selected=[config['stationary'],*config['exploration']];ids={r['id'] for r in selected}
    rows=[r for r in rows if r.get('recording_id') in ids]
    clean=dict(config,development=[],exploration=[dict(r,video=str(_path(r['video'],root))) for r in config['exploration']],
               stationary=dict(config['stationary'],video=str(_path(config['stationary']['video'],root))),
               calibration_file=str(_path(config['calibration_file'],root)),manual_reviews=str((out/'approved_reviews.json').resolve()))
    if cache_dir is not None:clean['sam_cache_dir']=str(Path(cache_dir).resolve())
    write_json(out/'approved_reviews.json',rows);write_json(out/'ingestion_manifest.json',clean)
    capture={};report=await process_manifest(out/'ingestion_manifest.json',out/'perception',run_api=run_api,
                                          capture=capture,ingest_only=True)
    if report['blockers'] or report['failures'] or len(capture.get('trials',[]))!=len(config['exploration']):
        return {'status':'BLOCKED_INPUTS','blockers':report['blockers'] or ['PERCEPTION_OR_RELEASE_VALIDATION_FAILED'],
                'trials':[],'config':config,'perception':report}
    for rid,meta in capture['metadata'].items():
        reviewed=[r for r in rows if r['recording_id']==rid]
        if len(reviewed)<20 or any(r['video_sha256']!=meta.video_sha256 or not 0<=r['frame_index']<len(meta.pts) for r in reviewed):
            return {'status':'BLOCKED_INPUTS','blockers':['TWENTY_HASH_BOUND_REVIEWS_REQUIRED:'+rid],'trials':[],'config':config}
    cal=capture['calibration'];cfg=capture['calibration_config']
    if cal.n_check_points<4 or cal.check_rms_px is None or cal.check_rms_px>1:
        return {'status':'BLOCKED_INPUTS','blockers':['INDEPENDENT_CALIBRATION_CHECKPOINTS_REQUIRED'],'trials':[],'config':config}
    import cv2
    h,_=cv2.findHomography(np.asarray(cfg['board_xy_m'],float),_undistort(np.asarray(cfg['image_xy_px'],float),cal),method=0)
    reference=_distort(_homography(np.asarray(cfg['check_board_xy_m'],float),h),cal)
    stationary=capture['tracks'][capture['stationary_id']]
    xy=stationary.xy_px[stationary.valid]
    if not 16<=len(xy):raise ValueError('stationary measurement count insufficient')
    # The tool's reference arrays are measured checkpoint pairs, not invented RMS surrogates.
    checks={'source':'REAL_MEASURED','reference_px':reference.tolist(),'observed_px':cfg['check_image_xy_px'],
            'stationary_xy_px':xy[np.linspace(0,len(xy)-1,min(256,len(xy)),dtype=int)].tolist()}
    trials=[];windows={};receipts={}
    for trial in capture['trials']:
        record=next(r for r in config['exploration'] if r['id']==trial.trial_id)
        trial,window=analysis_window(trial,record.get('analysis_window_pts_s'))
        trials.append(trial);windows[trial.trial_id]=window
        receipt=capture['runs'][trial.trial_id].receipt
        if receipt.get('source')!='REAL_API' or receipt.get('status')!='completed' or not receipt.get('response_id'):
            raise ValueError('actual SAM receipt required')
        receipts[trial.observation.metadata.video_sha256]=receipt
    return {'status':'READY','trials':trials,'checks':checks,'config':config,'windows':windows,
            'sam_receipts':receipts,'perception':report,'input_manifest_sha256':digest(config)}

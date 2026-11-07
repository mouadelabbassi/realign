"""Actual external-video SAM evidence, separated from synthetic investigations.

No physical trajectory fitting, scale, acceleration or peg geometry is inferred.
Actual masks are cached BEFORE tracking QA, retaining failed/ambiguous attempts.
"""
import csv
from dataclasses import asdict
import json
import os
from pathlib import Path
import numpy as np
from realign.contracts.external import ExternalVideoSource
from realign.perception.sam_client import SamClient,SamError
from realign.perception.video import probe_video,iter_video_frames,file_sha256
from realign.perception.track import extract_track,TrackFlag
from realign.perception.workflow import save_sam_cache,load_sam_cache,export_review_frames
from .evidence import EvidenceError,read_json
from .store import write_json


def finite_array(value):
    a=np.asarray(value)
    if a.ndim==0:return float(a) if np.isfinite(a) else None
    return [finite_array(v) for v in a]


def compare_manual_reviews(rows,metadata,track):
    if not rows:
        return {'status':'NOT_PROVIDED','reviewed_frames':0,'rmse_px':None,'bias_px':None}
    error=[]; seen=set(); frame_rows=[]
    for row in rows:
        index=row.get('frame_index'); center=row.get('center_px'); sigma=row.get('annotation_sigma_px')
        if (row.get('video_sha256')!=metadata.video_sha256 or type(index) is not int or
            not 0<=index<len(metadata.pts) or index in seen or not row.get('reviewer') or
            type(sigma) not in (float,int) or not np.isfinite(sigma) or sigma<=0):
            raise EvidenceError('review metadata or frame identity invalid')
        c=np.asarray(center,dtype=float)
        if c.shape!=(2,) or not np.isfinite(c).all() or not (0<=c[0]<metadata.width and 0<=c[1]<metadata.height):
            raise EvidenceError('review requires an independent in-frame pixel center')
        seen.add(index)
        if track.valid[index]:
            delta=track.xy_px[index]-c; error.append(delta)
            frame_rows.append({'frame_index':index,'pts_s':float(metadata.t_s[index]),
                'error_px':delta.tolist(),'annotation_sigma_px':sigma})
    if not error:
        return {'status':'NO_VALID_TRACK_PAIRS','reviewed_frames':0,'rmse_px':None,'bias_px':None}
    return {'status':'COMPARED_SUPPLIED_HUMAN_REFERENCES','reviewed_frames':len(error),
        'rmse_px':float(np.sqrt(np.mean(np.sum(np.array(error)**2,axis=1)))),
        'bias_px':np.mean(error,axis=0).tolist(),'per_frame':frame_rows,
        'limitation':'Human annotations have their own uncertainty; this is not physical calibration.'}


def export_tracking(video,metadata,run,track,output,*,reviews=None):
    import cv2
    if run.source!='REAL_API' or metadata.source_kind!='REAL_EXTERNAL' or run.video_sha256!=metadata.video_sha256:
        raise EvidenceError('external tracking export requires matching actual SAM output')
    output=Path(output); output.mkdir(parents=True,exist_ok=True)
    rows=[]
    for i in range(len(metadata.pts)):
        rows.append({'frame_index':i,'pts':metadata.pts[i],'pts_s':float(metadata.t_s[i]),
            'valid':bool(track.valid[i]),'x_px':float(track.xy_px[i,0]) if track.valid[i] else None,
            'y_px':float(track.xy_px[i,1]) if track.valid[i] else None,'flags':int(track.flags[i]),
            'mask_area_px':float(track.area_px[i]),'contour_rmse_px':finite_array(track.contour_rmse_px[i]),
            'sam_confidence':finite_array(track.confidence[i])})
    with (output/'tracked_centers.csv').open('w',newline='',encoding='utf-8') as f:
        writer=csv.DictWriter(f,fieldnames=list(rows[0])); writer.writeheader(); writer.writerows(rows)
    write_json(output/'tracked_centers.json',{'source':'REAL_EXTERNAL','perception':'REAL_API','units':'display px; original playback PTS s',
        'video_sha256':metadata.video_sha256,'rows':rows})
    selected=set(np.linspace(0,len(metadata.pts)-1,min(18,len(metadata.pts)),dtype=int).tolist())
    frames=output/'overlay_frames'; frames.mkdir(exist_ok=True)
    overlay_index=[]
    selected_id=track.summary['object_id']
    masks={m.frame_index:m for m in run.masks if m.object_id==selected_id}
    for index,rgb in enumerate(iter_video_frames(video,metadata)):
        if index not in selected:continue
        bgr=cv2.cvtColor(rgb,cv2.COLOR_RGB2BGR); mask=masks.get(index)
        if mask is not None:
            crop=bgr[mask.top:mask.top+mask.pixels.shape[0],mask.left:mask.left+mask.pixels.shape[1]]
            tint=np.full_like(crop,[70,190,120]); crop[mask.pixels]=cv2.addWeighted(crop,.6,tint,.4,0)[mask.pixels]
        if track.valid[index]:cv2.circle(bgr,tuple(np.rint(track.xy_px[index]).astype(int)),6,(20,240,240),2)
        text=f'REAL_EXTERNAL / SAM 3.1 / playback PTS {metadata.t_s[index]:.3f}s / flags {int(track.flags[index])}'
        cv2.rectangle(bgr,(0,0),(metadata.width,25),(20,28,20),-1)
        cv2.putText(bgr,text,(7,17),cv2.FONT_HERSHEY_SIMPLEX,.38,(240,250,240),1)
        name=f'frame_{index:06d}.png'; cv2.imwrite(str(frames/name),bgr)
        overlay_index.append({'file':name,'frame_index':index,'pts':metadata.pts[index],'pts_s':float(metadata.t_s[index])})
    write_json(output/'overlay_index.json',{'source':'REAL_EXTERNAL','perception':'REAL_API','frames':overlay_index})
    templates=export_review_frames(video,metadata,track,output/'review_frames','external',n=20)
    for row in templates:row.update(video_sha256=metadata.video_sha256)
    write_json(output/'manual_reviews.template.json',templates)
    review=compare_manual_reviews(reviews or [],metadata,track)
    write_json(output/'manual_review_comparison.json',review)
    write_json(output/'quality.json',{'summary':track.summary,'flags':{f.name:int(f) for f in TrackFlag},
        'unknown_confidence_is_unavailable':True})
    return review


async def process_external(video,manifest_path,output,cache,*,run_api=False,standard_tier_confirmed=False,
                           object_id=None,manual_reviews=None,client_factory=None,concept='the pendulum bob'):
    output=Path(output); output.mkdir(parents=True,exist_ok=True); cache=Path(cache)
    result={'status':'NOT_RUN','observation_source':'REAL_EXTERNAL','media_url':None,'metadata':None,
        'provenance':None,'sam':{'status':'NOT_RUN','source':'REAL_API','successful_calls':0,'failed_calls':0,'calls':[]},
        'track':None,'manual_review':{'status':'NOT_PROVIDED','reviewed_frames':0,'rmse_px':None},
        'physical_comparison_available':False,'phone_g2_passed':False,
        'limitations':['Third-party physical footage, not our controlled phone experiment.',
                       'Playback timestamps are not independently verified physical capture time.',
                       'No physical scale/pivot calibration: no acceleration, geometry or dynamics inference.'],
        'blockers':[]}
    client=None
    try:
        config=read_json(manifest_path)
        if config.get('source_kind')!='REAL_EXTERNAL':raise EvidenceError('external provenance required')
        source=ExternalVideoSource(**config['provenance'])
        result['provenance']=asdict(source)
        if not Path(video).is_file():
            result['blockers'].append('APPROVED_EXTERNAL_MP4_MISSING'); return result
        metadata=probe_video(video,source_kind='REAL_EXTERNAL',external_source=source)
        result.update(metadata=dict(asdict(metadata),t_s=metadata.t_s.tolist()),media_url='/media/external.mp4')
        write_json(output/'video_metadata.json',result['metadata'])
        write_json(output/'video_provenance.json',asdict(source))
        (output/'LICENSE_EXTERNAL_MEDIA.txt').write_text(source.attribution+'\n'+source.license_url+
            '\nDerived overlay/review images retain '+source.license_id+'.\n'+source.modifications+'\n',encoding='utf-8')
        if cache.with_suffix('.json').is_file():
            run=load_sam_cache(cache,metadata)
            result['sam']['execution']='REPLAYED_REAL_API_CACHE'
        elif run_api and standard_tier_confirmed and (os.environ.get('MODEL_API_KEY') or client_factory):
            client=(client_factory() if client_factory else SamClient.from_environment(standard_tier_confirmed=True,concept=concept))
            run=await client.segment_video(video,metadata)
            if run.source!='REAL_API':raise EvidenceError('simulated API masks cannot become real SAM evidence')
            save_sam_cache(cache,run)
            result['sam']['execution']='LIVE_META_API'
        else:
            result['blockers'].append('LOCAL_AUTHORIZATION_REQUIRED' if not os.environ.get('MODEL_API_KEY') else 'EXPLICIT_API_RUN_REQUIRED')
            return result
        result['sam'].update(status='COMPLETED',receipt=run.receipt)
        track=extract_track(run,metadata,object_id=object_id)
        reviewed=read_json(manual_reviews) if manual_reviews else []
        review=export_tracking(video,metadata,run,track,output,reviews=reviewed)
        result.update(status='COMPLETED' if track.valid.any() and track.summary['quality']=='ok' else 'TRACKING_QUARANTINED',
            track={'xy_px':finite_array(track.xy_px),'valid':track.valid.tolist(),'flags':track.flags.tolist(),
                'quality':track.summary,'contour_rmse_px':finite_array(track.contour_rmse_px),
                'confidence':finite_array(track.confidence)},manual_review=review)
    except Exception as exc:
        result.update(status='FAILED',error_type=type(exc).__name__,code=getattr(exc,'code','EXTERNAL_EVIDENCE_REJECTED'))
    finally:
        if client is not None:
            result['sam'].update(successful_calls=sum(c['status']=='completed' for c in client.calls),
                failed_calls=sum(c['status']=='failed' for c in client.calls),calls=client.calls)
            try:
                await client.close()
            except Exception as exc:
                result['sam']['cleanup_error']={'code':'CLIENT_CLOSE_FAILED','error_type':type(exc).__name__}
        write_json(output/'external_verification.json',result)
    return result

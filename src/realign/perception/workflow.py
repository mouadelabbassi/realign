"""Local manifest-driven real recording workflow. Never reads synthetic truth."""
import asyncio
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import numpy as np
from realign.physics import PendulumParams
from realign.fit.baselines import compare_baselines
from realign.fit.robust_fit import predict_free
from realign.observation.camera import unproject
from realign.report.g2_report import assess_g2,write_g2_report
from .video import probe_video,iter_video_frames,file_sha256
from .sam_client import SamClient,SamRun,SamMask,SamError
from .track import extract_track
from .calibration import fit_planar_calibration
from .uncertainty import stationary_noise,reviewed_noise,combine_noise,repeatability
from .pipeline import make_video_trial


def _path(value,root):
    p=Path(value)
    p=(root/p).resolve() if not p.is_absolute() else p.resolve()
    if any(part.lower() in ('sealed','vault','secrets','keys') for part in p.parts):
        raise ValueError('sealed/vault/secret resources are not allowed in perception')
    return p


def save_sam_cache(path,run):
    path=Path(path); path.parent.mkdir(parents=True,exist_ok=True)
    arrays={f'mask_{i}':m.pixels for i,m in enumerate(run.masks)}
    np.savez_compressed(path.with_suffix('.npz'),**arrays)
    index={'source':run.source,'video_sha256':run.video_sha256,'receipt':run.receipt,
        'array_sha256':file_sha256(path.with_suffix('.npz')),
        'masks':[{'frame_index':m.frame_index,'object_id':m.object_id,'left':m.left,'top':m.top,
                  'confidence':m.confidence,'array':f'mask_{i}'} for i,m in enumerate(run.masks)]}
    path.with_suffix('.json').write_text(json.dumps(index,indent=2)+'\n',encoding='utf-8')


def load_sam_cache(path,metadata):
    path=Path(path)
    index=json.loads(path.with_suffix('.json').read_text(encoding='utf-8'))
    if index['video_sha256']!=metadata.video_sha256 or index['source']!='REAL_API':
        raise SamError('cache is not actual SAM output for this recording',code='cache_origin')
    if file_sha256(path.with_suffix('.npz'))!=index['array_sha256']:
        raise SamError('SAM cache content hash mismatch',code='cache_hash')
    receipt=index['receipt']
    if receipt.get('status')!='completed' or receipt.get('source')!='REAL_API' or receipt.get('model')!='sam-3.1' or not receipt.get('response_id'):
        raise SamError('cache has no completed live SAM receipt',code='cache_receipt')
    masks=[]
    with np.load(path.with_suffix('.npz'),allow_pickle=False) as arrays:
        for m in index['masks']:
            if not 0<=m['frame_index']<len(metadata.pts):
                raise SamError('cached frame mismatch',code='frame_mismatch')
            pixels=arrays[m['array']]
            if pixels.ndim!=2 or m['left']<0 or m['top']<0 or m['left']+pixels.shape[1]>metadata.width or m['top']+pixels.shape[0]>metadata.height:
                raise SamError('cached mask bounds mismatch',code='frame_mismatch')
            masks.append(SamMask(m['frame_index'],m['object_id'],m['left'],m['top'],pixels,m['confidence']))
    return SamRun(tuple(masks),'REAL_API',metadata.video_sha256,receipt)


def export_review_frames(video,metadata,track,output_dir,recording_id,n=20):
    import cv2
    output=Path(output_dir); output.mkdir(parents=True,exist_ok=True)
    valid=np.flatnonzero(track.valid)
    rng=np.random.default_rng(int(metadata.video_sha256[:8],16))
    selected=set(rng.choice(valid,size=min(n,len(valid)),replace=False)) if len(valid) else set()
    rows=[]
    for i,frame in enumerate(iter_video_frames(video,metadata)):
        if i in selected:
            cv2.imwrite(str(output/f'{recording_id}_{i:06d}.png'),cv2.cvtColor(frame,cv2.COLOR_RGB2BGR))
            rows.append({'recording_id':recording_id,'frame_index':i,'pts_s':float(metadata.t_s[i]),
                         'center_px':None,'annotation_sigma_px':None,'reviewer':None})
    (output/f'{recording_id}_annotations.template.json').write_text(json.dumps(rows,indent=2)+'\n',encoding='utf-8')
    return rows


def _review_pairs(annotations,tracks,allowed_ids):
    predicted=[]; reviewed=[]; ids=[]
    seen=set()
    for row in annotations:
        rid=row.get('recording_id')
        if rid not in allowed_ids or row.get('center_px') is None:
            continue
        index=row.get('frame_index')
        if not isinstance(index,int) or not 0<=index<len(tracks[rid].valid):
            raise ValueError('manual annotation frame does not match recording')
        if (rid,index) in seen:
            raise ValueError('duplicate reviewed frame')
        seen.add((rid,index))
        annotation_sigma=row.get('annotation_sigma_px')
        if not row.get('reviewer') or not isinstance(annotation_sigma,(float,int)) or not np.isfinite(annotation_sigma) or annotation_sigma<=0:
            raise ValueError('reviewer and positive annotation uncertainty required')
        center=np.asarray(row['center_px'],dtype=float)
        if center.shape!=(2,) or not np.isfinite(center).all():
            raise ValueError('manual annotation needs finite raw display-pixel center')
        if tracks[rid].valid[index]:
            predicted.append(tracks[rid].xy_px[index]); reviewed.append(center); ids.append(rid)
    return np.array(predicted),np.array(reviewed),tuple(dict.fromkeys(ids))


def _real_plot(path,trial,comparison):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    o=trial.observation
    fig,ax=plt.subplots(figsize=(10,5),layout='constrained')
    ax.scatter(o.t_s[o.valid],o.xy_px[o.valid,0],s=8,color='black',label='REAL_SAM measured bob centers')
    for name in ('B0','B1'):
        if 'params' in comparison[name]:
            predicted=predict_free(PendulumParams(**comparison[name]['params']),trial)
            ax.plot(o.t_s,predicted[:,0],label=name+' simulated full rollout')
    ax.axvspan(trial.release.lower_s,trial.release.upper_s,alpha=.2,color='gray',label='Measured release bracket')
    ax.set(xlabel='Original recording PTS (s)',ylabel='Raw display x (px)',
           title='REAL SAM OBSERVATIONS vs SIMULATION — no mechanism/repair claim')
    ax.legend(); fig.savefig(path,dpi=140); plt.close(fig)


async def _process_manifest(manifest_path,output_dir,result,*,run_api=False,export_reviews=True,capture=None,ingest_only=False):
    """Process existing caches or explicitly invoke SAM; absent inputs yield readiness."""
    manifest_path=Path(manifest_path).resolve(); root=manifest_path.parent
    output=Path(output_dir); output.mkdir(parents=True,exist_ok=True)
    config=json.loads(manifest_path.read_text(encoding='utf-8'))
    if config.get('schema_version')!=1 or config.get('source_kind')!='REAL_PHONE':
        raise ValueError('real manifest schema_version=1 and source_kind=REAL_PHONE required')
    records=[dict(config['stationary'],zone='calibration')]
    records+=[dict(r,zone='exploration') for r in config.get('exploration',[])]
    records+=[dict(r,zone='development') for r in config.get('development',[])]
    ids=[r['id'] for r in records]
    if len(set(ids))!=len(ids) or any(not rid.replace('_','').replace('-','').isalnum() for rid in ids):
        raise ValueError('unique simple opaque recording IDs required')
    paths={r['id']:_path(r['video'],root) for r in records}
    calibration_path=_path(config['calibration_file'],root)
    missing=[rid for rid,p in paths.items() if not p.is_file()]
    if missing:
        result['blockers'].append('recordings not supplied: '+', '.join(missing))
    if not calibration_path.is_file():
        result['blockers'].append('measured calibration correspondences/pivot/hanging reference not supplied')
    if result['blockers']:
        return write_g2_report(output,result)
    calibration_config=json.loads(calibration_path.read_text(encoding='utf-8'))
    if calibration_config.get('source')!='REAL_MEASURED':
        result['blockers'].append('calibration must contain actual REAL_MEASURED points')
        return write_g2_report(output,result)
    cal=fit_planar_calibration(**calibration_config)
    metadata={r['id']:probe_video(paths[r['id']],source_kind='REAL_PHONE',recording_start_utc=r.get('recording_start_utc')) for r in records}
    if len({m.video_sha256 for m in metadata.values()})!=len(metadata):
        raise ValueError('stationary, exploration and development must use disjoint source recordings')
    client=None
    if run_api:
        try:
            client=SamClient.from_environment(standard_tier_confirmed=config.get('standard_tier_confirmed') is True)
        except SamError as exc:
            result['blockers'].append(str(exc))
            return write_g2_report(output,result)
    runs={}; tracks={}
    try:
        for record in records:
            rid=record['id']
            cache=(_path(config['sam_cache_dir'],root)/metadata[rid].video_sha256
                   if config.get('sam_cache_dir') else output/'sam_cache'/rid)
            try:
                if cache.with_suffix('.json').is_file():
                    run=load_sam_cache(cache,metadata[rid])
                elif client is not None:
                    run=await client.segment_video(paths[rid],metadata[rid])
                    save_sam_cache(cache,run)
                else:
                    result['blockers'].append(f'{rid}: no actual SAM cache; use --run-api after configuring local access')
                    continue
                runs[rid]=run
                tracks[rid]=extract_track(run,metadata[rid],object_id=record.get('object_id'))
                if export_reviews:
                    export_review_frames(paths[rid],metadata[rid],tracks[rid],output/'review_frames',rid)
            except (SamError,ValueError) as exc:
                result['failures'].append({'recording_id':rid,'error_type':type(exc).__name__,
                                           'code':getattr(exc,'code','measurement_failed')})
                result['blockers'].append(rid+': perception failed; inspect local masks/quality')
    finally:
        if client is not None:
            result['actual_api'].update(
                status='executed',successful_calls=sum(c['status']=='completed' for c in client.calls),
                failed_calls=sum(c['status']=='failed' for c in client.calls),calls=client.calls)
            await client.close()
        elif runs:
            result['actual_api']['status']='replayed_real_api_cache'
    if len(tracks)!=len(records):
        return write_g2_report(output,result)
    annotations=[]
    if config.get('manual_reviews'):
        annotations_path=_path(config['manual_reviews'],root)
        if annotations_path.is_file():
            annotations=json.loads(annotations_path.read_text(encoding='utf-8'))
    stationary_id=records[0]['id']
    base=stationary_noise(tracks[stationary_id].xy_px,tracks[stationary_id].valid,
        source_ids=(stationary_id,),provenance='REAL_SAM',t_s=metadata[stationary_id].t_s)
    stationary_track=tracks[stationary_id]
    mean_stationary=np.mean(stationary_track.xy_px[stationary_track.valid],axis=0)
    result['stationary_reference']={'recording_id':stationary_id,'metadata':asdict(metadata[stationary_id]),
        'mean_center_px':mean_stationary.tolist(),'quality':stationary_track.summary,
        'gravity_alignment_plane_x_m':float(unproject(mean_stationary[None,:],cal)[0,0]),
        'sam_receipt':runs[stationary_id].receipt}
    np.savez_compressed(output/(stationary_id+'_track.npz'),t_s=metadata[stationary_id].t_s,
        xy_px=stationary_track.xy_px,valid=stationary_track.valid,flags=stationary_track.flags,
        mask_area_pixels=stationary_track.area_px,contour_rmse_px=stationary_track.contour_rmse_px,
        translated_iou=stationary_track.translated_iou,confidence=stationary_track.confidence)
    train_ids={r['id'] for r in records if r['zone']=='exploration'}
    predicted,reviewed,review_ids=_review_pairs(annotations,tracks,train_ids|{stationary_id})
    estimates=[base]
    if len(predicted)>=5:
        estimates.append(reviewed_noise(predicted,reviewed,source_ids=review_ids,provenance='REAL_SAM'))
    combined=combine_noise(estimates)
    trials=[]
    for r in records[1:]:
        rid=r['id']
        try:
            if tracks[rid].summary['quality']=='quarantined':
                raise ValueError('recording quarantined by tracking quality')
            trial=make_video_trial(rid,metadata[rid],runs[rid],tracks[rid],cal,combined,
                                  zone=r['zone'],manual_release_bracket=r.get('release_bracket_pts_s'))
            trials.append(trial)
            o=trial.observation
            np.savez_compressed(output/(rid+'_observation.npz'),pts=np.array(o.metadata.pts),t_s=o.t_s,
                xy_px=o.xy_px,xy_m=unproject(o.xy_px,cal),
                valid=o.valid,flags=o.flags,covariance_px2=o.frame_covariance_px2,
                mask_area_pixels=tracks[rid].area_px,contour_rmse_px=tracks[rid].contour_rmse_px,
                translated_iou=tracks[rid].translated_iou,confidence=tracks[rid].confidence)
            result['real_measurements'].append(dict(recording_id=rid,video_sha256=o.metadata.video_sha256,
                provenance=o.provenance,metadata=asdict(o.metadata),release=asdict(trial.release),
                release_sigma_s=trial.release.sigma_s,**tracks[rid].summary,sam_receipt=runs[rid].receipt))
        except ValueError as exc:
            result['failures'].append({'recording_id':rid,'error_type':type(exc).__name__,'code':'trial_rejected'})
            result['blockers'].append(rid+': release/quality validation failed; review recording')
    training=[t for t in trials if t.zone=='exploration']
    heldout=[t for t in trials if t.zone=='development']
    if capture is not None:
        capture.update(trials=trials,calibration=cal,fitting_noise=combined,tracks=tracks,metadata=metadata,
                       runs=runs,calibration_config=calibration_config,stationary_id=stationary_id)
    if ingest_only:
        result.update(calibration=asdict(cal),fitting_noise=asdict(combined),
                      scope='REAL PHONE observation ingestion only; fitting and evaluation deferred',
                      g2_passed=False)
        return write_g2_report(output,result)
    baseline=None; baselines={}
    try:
        nominal=PendulumParams(**config['nominal_params'])
        group_of={r['id']:r.get('comparison_group','setup_01') for r in records[1:]}
        for group in sorted(set(group_of.values())):
            train_group=[t for t in training if group_of[t.trial_id]==group]
            test_group=[t for t in heldout if group_of[t.trial_id]==group]
            if len(train_group)<2 or not test_group:
                result['blockers'].append('comparison group '+group+': needs two exploration and one disjoint development recording')
                continue
            comparison=compare_baselines(train_group,test_group,nominal)
            baselines[group]=comparison
            if baseline is None:
                baseline=comparison
                if comparison['B1']['success']:
                    _real_plot(output/'g2_real_comparison.png',test_group[0],comparison)
    except (ValueError,TypeError,KeyError):
        result['blockers'].append('measured nominal parameters or disjoint comparison inputs incomplete')
    all_pred,all_review,_=_review_pairs(annotations,tracks,{r['id'] for r in records})
    per_recording={}
    for rid in tracks:
        rp,rr,_=_review_pairs(annotations,tracks,{rid})
        per_recording[rid]={'reviewed_frames':len(rp),
            'rmse_px':float(np.sqrt(np.mean(np.sum((rp-rr)**2,axis=1)))) if len(rp) else None}
    review={'reviewed_frames':len(all_pred),'rmse_px':float(np.sqrt(np.mean(np.sum((all_pred-all_review)**2,axis=1)))) if len(all_pred) else None,
            'per_recording':per_recording}
    repeats=[t for t in training if next(r for r in records if r['id']==t.trial_id).get('repeat_group')]
    groups={}
    for t in repeats:
        record=next(r for r in records if r['id']==t.trial_id)
        group=record.get('comparison_group','setup_01')+'/'+record['repeat_group']
        groups.setdefault(group,[]).append(t)
    repeat_results={key:repeatability(value) for key,value in groups.items()}
    repeat_assessment=max(repeat_results.values(),key=lambda r:r['n_trials'],default=None)
    passed,blockers=assess_g2(result['real_measurements'],asdict(cal),review,repeat_assessment,baseline)
    result.update(g2_passed=passed and not result['failures'] and not result['blockers']
                  and all(c['B1']['success'] for c in baselines.values()),calibration=asdict(cal),
        stationary_noise=asdict(base),fitting_noise=asdict(combined),manual_review=review,
        repeatability=repeat_results,baseline=baseline,baselines=baselines)
    result['blockers']+=blockers
    return write_g2_report(output,result)


async def process_manifest(manifest_path,output_dir,*,run_api=False,export_reviews=True,capture=None,ingest_only=False):
    result={'scope':'REAL PHONE G2 processing; no synthetic inputs permitted','offline_passed':None,
        'g2_passed':False,'actual_api':{'status':'not_run','successful_calls':0,'failed_calls':0},
        'real_measurements':[],'synthetic_fixture':None,'blockers':[],'failures':[]}
    try:
        return await _process_manifest(manifest_path,output_dir,result,run_api=run_api,export_reviews=export_reviews,
                                       capture=capture,ingest_only=ingest_only)
    except Exception as exc:
        result['g2_passed']=False
        result['failures'].append({'error_type':type(exc).__name__,'code':getattr(exc,'code','processing_failed')})
        result['blockers'].append('processing failed; inspect input schema/calibration and retained API receipts')
        return write_g2_report(output_dir,result)

"""Executable offline integration evidence. This module is never a real-data path."""
import asyncio
from dataclasses import asdict
from pathlib import Path
import numpy as np
from realign.physics import PendulumParams
from realign.fit.baselines import compare_baselines
from realign.fit.robust_fit import FitOptions,predict_free
from realign.perception.sam_client import parse_sam_events
from realign.perception.track import extract_track
from realign.perception.uncertainty import stationary_noise,reviewed_noise,combine_noise,repeatability
from realign.perception.pipeline import make_video_trial
from realign.report.g2_report import write_g2_report,assess_g2
from .video_fixture import render_fixture,fixture_calibration


def verify_offline_g2(output_dir):
    output=Path(output_dir); output.mkdir(parents=True,exist_ok=True)
    media=output/'synthetic_fixture_media'
    cal=fixture_calibration()
    stationary=render_fixture(media/'SYNTHETIC_stationary.mp4',duration_s=1.2,stationary=True)
    stationary_run=asyncio.run(parse_sam_events(stationary['events'],stationary['metadata'],source='SIMULATED_API_FIXTURE'))
    stationary_track=extract_track(stationary_run,stationary['metadata'])
    noise=stationary_noise(stationary_track.xy_px,stationary_track.valid,source_ids=('fixture_stationary',),
                           provenance='SYNTHETIC',t_s=stationary['metadata'].t_s)
    trials=[]; center_errors=[]; records=[]
    for i,angle in enumerate((.42,.64,.53)):
        f=render_fixture(media/f'SYNTHETIC_swing_{i}.mp4',angle_rad=angle)
        run=asyncio.run(parse_sam_events(f['events'],f['metadata'],source='SIMULATED_API_FIXTURE'))
        track=extract_track(run,f['metadata'])
        review=reviewed_noise(track.xy_px[track.valid],f['reference_px'][track.valid],
            source_ids=(f'fixture_annotations_{i}',),provenance='SYNTHETIC')
        combined=combine_noise([noise,review])
        trial=make_video_trial(f'fixture_{i}',f['metadata'],run,track,cal,combined,
                               zone='exploration' if i<2 else 'development')
        trials.append(trial); records.append((f,run,track))
        center_errors.extend(np.sum((track.xy_px[track.valid]-f['reference_px'][track.valid])**2,axis=1))
    baseline=compare_baselines(trials[:2],trials[2:],PendulumParams(.70,gamma_per_s=.04),
                               FitOptions())
    checks=[]
    def check(name,passed): checks.append({'name':name,'passed':bool(passed)})
    tracking_rmse=float(np.sqrt(np.mean(center_errors)))
    check('rendered mask centers within 1 px RMS',tracking_rmse<1.)
    check('all original PTS retained in trial observations',
          all(np.array_equal(t.observation.t_s,r[0]['metadata'].t_s) for t,r in zip(trials,records)))
    check('two deliberate missing masks stay invalid in each recording',
          all(not t.observation.valid[13] and not t.observation.valid[37] for t in trials))
    check('release offset estimated within 40 ms of rendered onset',
          all(abs(t.release.time_s-.4)<.04 for t in trials))
    check('synthetic checkpoint calibration RMS below 0.001 px',cal.check_rms_px<.001)
    check('B1 converges using exploration recordings only',baseline['B1']['success'])
    check('unseen B1 rollout within 10 px timing/measurement design allowance',
          baseline['B1']['success'] and baseline['B1']['heldout']['rmse_xy_px']<10.)
    check('no fabricated second pivot on a free pendulum',baseline['B2']['decision']=='one_circle_only')
    _,blockers=assess_g2([],None,None,None,None)
    result={'scope':'G2 READINESS; offline fixtures and actual measurements reported separately',
        'offline_passed':all(c['passed'] for c in checks),'g2_passed':False,
        'actual_api':{'status':'not_run','successful_calls':0,'failed_calls':0,
            'reason':'offline verifier never calls Meta; real phone recordings and local authorization pending'},
        'real_measurements':[],'blockers':blockers,
        'synthetic_fixture':{'scope':'SYNTHETIC_RENDER + SIMULATED_API_FIXTURE','checks':checks,
            'tracking_rmse_px':tracking_rmse,'calibration_check_rms_px':cal.check_rms_px,
            'baseline':baseline,'repeatability':repeatability(trials),
            'noise':asdict(noise),'fit_options':asdict(FitOptions()),
            'recordings':[{'id':t.trial_id,'metadata':asdict(t.observation.metadata),
            'release':asdict(t.release),'quality':r[2].summary,'sam_receipt':r[1].receipt} for t,r in zip(trials,records)]}}
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    t=trials[2]; o=t.observation
    fig,ax=plt.subplots(2,1,figsize=(10,7),layout='constrained',sharex=True)
    ax[0].scatter(o.t_s[o.valid],o.xy_px[o.valid,0],s=9,color='black',label='Rendered-video fixture observations')
    for name,color in [('B0','#d95f02'),('B1','#1b9e77')]:
        p=PendulumParams(**baseline[name]['params'])
        pred=predict_free(p,t)
        ax[0].plot(o.t_s,pred[:,0],label=name+' full rollout',color=color)
        ax[1].plot(o.t_s[o.valid],np.linalg.norm(pred[o.valid]-o.xy_px[o.valid],axis=1),label=name,color=color)
    for a in ax:
        a.axvspan(t.release.lower_s,t.release.upper_s,color='gray',alpha=.2,label='Estimated release bracket')
        a.legend(fontsize=8)
    ax[0].set_ylabel('Raw image x (px)'); ax[1].set_ylabel('xy residual (px)')
    ax[1].set_xlabel('Original video presentation time (s)')
    fig.suptitle('SYNTHETIC RENDER + SIMULATED SAM EVENTS — NOT API OR REAL-WORLD VALIDATION')
    fig.savefig(output/'g2_fixture_comparison.png',dpi=140); plt.close(fig)
    return write_g2_report(output,result)

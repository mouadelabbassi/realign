"""G2 assessment keeps actual API, real measurements and fixtures disjoint."""
from pathlib import Path
import json
import hashlib
from importlib.metadata import version,PackageNotFoundError
import platform


def assess_g2(real_measurements,calibration,review,repeatability,baseline):
    reasons=[]
    if len(real_measurements)<3 or any(r.get('provenance')!='REAL_SAM' or
            r.get('metadata',{}).get('source_kind')!='REAL_PHONE' or
            r.get('sam_receipt',{}).get('source')!='REAL_API' or
            not r.get('sam_receipt',{}).get('response_id') for r in real_measurements):
        reasons.append('actual SAM-processed exploration/development phone recordings not validated')
    if not calibration or calibration.get('source')!='REAL_MEASURED' or calibration.get('n_check_points',0)<4:
        reasons.append('measured calibration with at least four disjoint checkpoints pending')
    elif calibration.get('check_rms_px') is None or calibration['check_rms_px']>1.:
        reasons.append('calibration checkpoint RMS exceeds the 1 px design budget')
    if not review or review.get('reviewed_frames',0)<20 or review.get('rmse_px') is None or review['rmse_px']>2.:
        reasons.append('at least 20 manual frame checks within a 2 px design budget pending')
    if review:
        for r in real_measurements:
            per=review.get('per_recording',{}).get(r['recording_id'],{})
            if per.get('reviewed_frames',0)<20 or per.get('rmse_px') is None or per['rmse_px']>2.:
                reasons.append('20 independently reviewed frames per recording within design budget pending')
    if not repeatability or repeatability.get('n_trials',0)<3:
        reasons.append('three repeat releases and separation of release variability pending')
    if not baseline or not baseline.get('B1',{}).get('success'):
        reasons.append('disjoint real B0/B1/B2 comparison pending')
    for r in real_measurements:
        if r.get('missing_or_rejected_fraction',1.)>.1 or r.get('release_sigma_s',1.)>.05:
            reasons.append('recording quality or release timing exceeds declared design budget')
    return not reasons,list(dict.fromkeys(reasons))


def write_g2_report(output_dir,result):
    output=Path(output_dir); output.mkdir(parents=True,exist_ok=True)
    root=Path(__file__).resolve().parents[3]
    digest=hashlib.sha256()
    for path in sorted((root/'src'/'realign').rglob('*.py'))+sorted((root/'scripts').glob('*.py')):
        digest.update(path.relative_to(root).as_posix().encode())
        digest.update(path.read_bytes())
    versions={'python':platform.python_version()}
    for package in ('numpy','scipy','opencv-python-headless','meta-sam-parser','openai'):
        try: versions[package]=version(package)
        except PackageNotFoundError: versions[package]='not installed'
    result['implementation_provenance']={'source_sha256':digest.hexdigest(),'versions':versions}
    # No completed offline test is promoted into a real-world gate.
    if not result.get('real_measurements'):
        result['g2_passed']=False
    (output/'g2_readiness.json').write_text(json.dumps(result,indent=2,allow_nan=False)+'\n',encoding='utf-8')
    lines=['# G2 Perception Readiness', '',
           '**G2: '+('PASS' if result['g2_passed'] else 'NOT PASSED — real-world checks pending')+'**','',
           '## Implemented and verified offline','',
           'Original integer video PTS/time base, display-frame mapping, official SAM parser, '
           'mask-contour centers and tracking QA, planar/lens calibration, release-time estimation, '
           'stationary/manual uncertainty, common timing uncertainty, and B0/B1/B2 integration.','',
           'Offline verification: **'+('PASS' if result.get('offline_passed') else 'not established in this command')+'**.','',
           '## Actual Meta API verification','',
           f"Status: **{result['actual_api']['status']}**. Successful calls: "
           f"{result['actual_api']['successful_calls']}; failed calls: {result['actual_api']['failed_calls']}.",
           '', 'API fixture tests are not counted as network calls. No raw SDK errors, headers or keys are persisted.','',
           '## Actual real recordings','']
    if result.get('real_measurements'):
        lines+=['| Recording | Source SHA-256 | Valid frames | Rejected fraction | Release sigma (s) |',
                '|---|---|---:|---:|---:|']
        for r in result['real_measurements']:
            lines.append(f"| {r['recording_id']} | {r['video_sha256']} | {r['valid_frames']} | "
                         f"{r['missing_or_rejected_fraction']:.4f} | {r['release_sigma_s']:.5f} |")
        lines+=['','Measured calibration, noise, review diagnostics, repeat variability and baseline '
                'scores are recorded separately in g2_readiness.json.']
        if result.get('calibration'):
            cal=result['calibration']
            lines+=['',f"Measured plane-fit RMS: {cal['reprojection_rms_px']:.5f} px; "
                    f"independent checkpoint RMS: {cal['check_rms_px']} px."]
        if result.get('fitting_noise'):
            lines+=['','Measured fitting-noise covariance (px²): '+json.dumps(result['fitting_noise']['covariance_px2'])+
                    '. Systematic review bias is reported separately.']
        lines+=['','| Configuration | B0 held-out xy RMS (px) | B1 held-out xy RMS (px) | B2 |',
                '|---|---:|---:|---|']
        for name,c in result.get('baselines',{}).items():
            b1=c['B1']['heldout']
            lines.append(f"| {name} | {c['B0']['heldout']['rmse_xy_px']:.5f} | "
                         f"{b1['rmse_xy_px'] if b1 else 'failed'} | {c['B2']['decision']} |")
        if (result.get('baseline') or {}).get('B1',{}).get('success'):
            lines+=['','![Real SAM observations and simulated predictions](g2_real_comparison.png)']
    else:
        lines+=['**None supplied or validated.** No physical measurements, measured camera errors, '
                'real tracking noise or real baseline scores are claimed.']
    lines+=['','## Synthetic rendered video / simulated API fixture','',
            '**SYNTHETIC ONLY — SIMULATED API EVENTS; NO META API VERIFICATION**','']
    fixture=result.get('synthetic_fixture')
    if fixture:
        for check in fixture.get('checks',[]):
            lines.append(f"- {'PASS' if check['passed'] else 'FAIL'}: {check['name']}")
        lines+=['',f"Tracking center RMS: {fixture['tracking_rmse_px']:.6f} px against known rendered centers.",
                f"Calibration checkpoint RMS: {fixture['calibration_check_rms_px']:.6g} px (synthetic correspondences).",
                '', '| Baseline | Training xy RMS (px) | Unseen recording xy RMS (px) |',
                '|---|---:|---:|']
        for b in ('B0','B1'):
            x=fixture['baseline'][b]
            if x.get('training') and x.get('heldout'):
                lines.append(f"| {b} | {x['training']['rmse_xy_px']:.4f} | {x['heldout']['rmse_xy_px']:.4f} |")
        lines+=['', 'B2: '+fixture['baseline']['B2']['decision']+
                '. Radial geometry is an observation-conditioned diagnostic, not a trajectory prediction.',
                '', '![Synthetic fixture comparison](g2_fixture_comparison.png)']
    else:
        lines+=['No synthetic results were generated by this processing command.']
    lines+=['','## Acceptance blockers and limitations','']
    lines+=['- '+s for s in result.get('blockers',[])]
    lines+=['', 'Release-onset profiling assumes a visible stationary from-rest lead-in; its uncertainty '
            'is approximate until manually checked on real clips. Release-time covariance is common across '
            'frames. Repeat trajectory dispersion is not automatically treated as tracker noise.',
            '', 'Lens distortion is corrected only with measured intrinsics. Plane/pivot/scale/gravity errors, '
            'rolling shutter, stabilization, nonplanarity, contour bias and annotation uncertainty remain '
            'systematic limitations. Quality budgets (1 px calibration, 2 px manual tracking, 10% rejection, '
            '50 ms timing sigma) are declared engineering targets, not measured SAM performance. '
            'Full G3 power/MDE and causal claims remain outside this phase.',
            '', 'Source SHA-256: '+result['implementation_provenance']['source_sha256']+'.',
            'Environment: '+json.dumps(versions,sort_keys=True)+'.',
            '', 'Follow docs/REAL_DATA_COLLECTION_PROTOCOL.md and docs/G2_IMPLEMENTATION.md for inputs and commands.',
            '', 'Official contracts: [Meta SAM cookbook](https://dev.meta.ai/docs/cookbook/sam-api-basics), '
            '[Meta parser](https://dev.meta.ai/docs/sam/client-libraries), '
            '[OpenCV calibration](https://docs.opencv.org/4.x/d9/d0c/group__calib3d.html), '
            '[ffprobe](https://ffmpeg.org/ffprobe.html).','']
    (output/'G2_READINESS.md').write_text('\n'.join(lines),encoding='utf-8')
    return result

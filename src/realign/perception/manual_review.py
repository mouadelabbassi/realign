"""Independent clean-frame annotation and external SAM localization assessment.

This module never proposes reference centers. Independence is a named person's
self-attestation, not a cryptographic proof of authorship. Pixel agreement does
not establish camera calibration, capture-time scale or physical contact truth.
"""
import base64
from datetime import datetime
import hashlib
import json
import math
from pathlib import Path
import struct

import numpy as np

from realign.audit.chain import canonical, digest
from realign.contracts.external import ExternalVideoSource
from realign.contracts.video import VideoMetadata
from realign.perception.meta_validation import strict_json


CONTEXTS = ('reversal', 'occlusion', 'apparent_contact')
ATTESTATION = ('I placed these centers independently on the clean reference images, '
               'without viewing or copying SAM masks, centers or overlays.')


class ManualReviewError(ValueError):
    pass


def read_review_json(path):
    p = Path(path).resolve()
    if (p.suffix.lower() != '.json' or
        any(x.lower() in ('sealed', 'vault', 'secrets', 'keys') for x in p.parts) or
        p.stat().st_size > 12_000_000):
        raise ManualReviewError('unapproved review JSON resource')
    try:
        value = strict_json(p.read_text(encoding='utf-8-sig'))
        canonical(value)
        return value
    except (TypeError, ValueError, UnicodeError, RecursionError):
        raise ManualReviewError('finite, unique-key review JSON required') from None


def write_review_json(path, value, *, archive_previous=False):
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    data = canonical(value)
    if p.exists() and p.read_bytes() != data:
        if not archive_previous:
            raise ManualReviewError('review output already exists with different content; use a new output directory')
        previous = p.read_bytes()
        history = p.parent/'history'/(p.stem+'.'+hashlib.sha256(previous).hexdigest()+'.json')
        history.parent.mkdir(exist_ok=True)
        if history.exists() and history.read_bytes() != previous:
            raise ManualReviewError('prior review archive differs from recorded digest')
        history.write_bytes(previous)
    temporary = p.with_suffix(p.suffix+'.tmp')
    temporary.write_bytes(data)
    temporary.replace(p)


def _metadata(report):
    try:
        if report['observation_source'] != 'REAL_EXTERNAL':
            raise ManualReviewError('external review cannot be classified as controlled phone evidence')
        source = ExternalVideoSource(**report['provenance'])
        raw = dict(report['metadata'])
        t_s = raw.pop('t_s')
        if raw['external_source'] != report['provenance']:
            raise ManualReviewError('external metadata attribution mismatch')
        raw['external_source'] = source
        metadata = VideoMetadata(**raw)
        if metadata.source_kind != 'REAL_EXTERNAL' or metadata.t_s.tolist() != t_s:
            raise ManualReviewError('original external presentation timestamps required')
        return metadata
    except ManualReviewError:
        raise
    except (KeyError, TypeError, ValueError, ArithmeticError):
        raise ManualReviewError('malformed external metadata') from None


def _validate_manifest(manifest, metadata):
    try:
        if (manifest['schema_version'] != 1 or manifest['observation_source'] != 'REAL_EXTERNAL' or
            manifest['video_sha256'] != metadata.video_sha256 or
            manifest['time_base'] != metadata.time_base or
            manifest['width'] != metadata.width or manifest['height'] != metadata.height):
            raise ManualReviewError('reference manifest belongs to another video or coordinate frame')
        frames = manifest['frames']
        if not isinstance(frames, list) or len(frames) != 20:
            raise ManualReviewError('the existing twenty clean reference frames are required')
        seen = set()
        for frame in frames:
            index = frame['frame_index']
            if (type(index) is not int or not 0 <= index < len(metadata.pts) or index in seen or
                frame['pts'] != metadata.pts[index] or type(frame['pts']) is not int or
                not math.isclose(frame['pts_s'], float(metadata.t_s[index]), rel_tol=0, abs_tol=1e-12) or
                len(frame['frame_sha256']) != 64 or
                any(c not in '0123456789abcdef' for c in frame['frame_sha256'])):
                raise ManualReviewError('reference frame identity, hash or original PTS invalid')
            seen.add(index)
        return {f['frame_index']: f for f in frames}
    except ManualReviewError:
        raise
    except (KeyError, TypeError, ValueError, ArithmeticError):
        raise ManualReviewError('malformed clean-frame manifest') from None


def _png_dimensions(data):
    if len(data) < 24 or data[:8] != b'\x89PNG\r\n\x1a\n' or data[12:16] != b'IHDR':
        raise ManualReviewError('clean reference must be a PNG')
    return struct.unpack('>II', data[16:24])


def prepare_review_package(external_dir, output_dir):
    """Copy clean images and blank references; never read tracking coordinates."""
    external_dir, output_dir = Path(external_dir).resolve(), Path(output_dir).resolve()
    if output_dir == external_dir or external_dir in output_dir.parents:
        raise ManualReviewError('keep review files separate from preserved SAM evidence')
    report = read_review_json(external_dir/'external_verification.json')
    metadata = _metadata(report)
    rows = read_review_json(external_dir/'manual_reviews.template.json')
    if not isinstance(rows, list) or len(rows) != 20:
        raise ManualReviewError('expected the twenty exported clean-frame references')
    output_dir.mkdir(parents=True, exist_ok=True)
    frames_dir = output_dir/'frames'
    frames_dir.mkdir(exist_ok=True)
    frames = []
    image_data = []
    for row in rows:
        index = row.get('frame_index')
        if type(index) is not int or not 0 <= index < len(metadata.pts):
            raise ManualReviewError('clean-frame index invalid')
        if row.get('video_sha256') != metadata.video_sha256:
            raise ManualReviewError('clean-frame template video hash mismatch')
        source = external_dir/'review_frames'/f'external_{index:06d}.png'
        if source.resolve().parent != (external_dir/'review_frames').resolve():
            raise ManualReviewError('reference image outside clean-frame directory')
        data = source.read_bytes()
        if _png_dimensions(data) != (metadata.width, metadata.height):
            raise ManualReviewError('clean reference image dimensions differ from video')
        target = frames_dir/source.name
        if target.exists() and target.read_bytes() != data:
            raise ManualReviewError('review image already exists with different content')
        target.write_bytes(data)
        frame = {'frame_index':index, 'pts':metadata.pts[index],
                 'pts_s':float(metadata.t_s[index]), 'file':'frames/'+source.name,
                 'frame_sha256':hashlib.sha256(data).hexdigest()}
        frames.append(frame)
        image_data.append('data:image/png;base64,'+base64.b64encode(data).decode('ascii'))
    manifest = {'schema_version':1, 'observation_source':'REAL_EXTERNAL',
        'video_sha256':metadata.video_sha256, 'width':metadata.width, 'height':metadata.height,
        'time_base':metadata.time_base, 'frames':frames, 'provenance':report['provenance'],
        'selection':'Existing Task05 clean reference export; twenty frames, not a random full-video accuracy sample.',
        'physical_capture_time_verified':metadata.external_source.capture_time_scale_verified,
        'reference_image_type':'CLEAN_RGB_NO_SAM_HINTS'}
    _validate_manifest(manifest, metadata)
    annotations = {'schema_version':1, 'annotation_source':'INDEPENDENT_HUMAN',
        'observation_source':'REAL_EXTERNAL', 'video_sha256':metadata.video_sha256,
        'reference_manifest_sha256':digest(manifest), 'reviewer':None, 'reviewed_utc':None,
        'independent_of_sam':False, 'independence_attestation':ATTESTATION,
        'rows':[dict(frame, center_px=None, annotation_sigma_px=None, contexts=[])
                for frame in frames]}
    # Package input contains no SAM center, mask, acceptance or error information.
    page_data = {'manifest':manifest, 'annotations':annotations, 'images':image_data}
    template = Path(__file__).resolve().parents[1]/'product/static/review.html'
    page = template.read_text(encoding='utf-8').replace('__REVIEW_DATA__',
        json.dumps(page_data, separators=(',',':')).replace('<','\\u003c'))
    write_review_json(output_dir/'reference_manifest.json', manifest)
    write_review_json(output_dir/'annotations.template.json', annotations)
    html = output_dir/'review.html'
    if html.exists() and html.read_text(encoding='utf-8') != page:
        raise ManualReviewError('review page already exists with different content')
    html.write_text(page, encoding='utf-8')
    attribution = metadata.external_source.attribution+'\n'+metadata.external_source.license_url+'\n'
    (output_dir/'LICENSE_EXTERNAL_MEDIA.txt').write_text(attribution, encoding='utf-8')
    return manifest


def localization_metrics(error_xy):
    """Numerical scorer, also testable with explicitly synthetic reference errors."""
    errors = np.asarray(error_xy, dtype=float)
    if not errors.size:
        return {'paired_frames':0, 'rmse_px':None, 'bias_px':None,
                'median_error_px':None, 'p95_error_px':None}
    if errors.ndim != 2 or errors.shape[1] != 2 or not np.isfinite(errors).all():
        raise ManualReviewError('finite two-dimensional errors required')
    distance = np.linalg.norm(errors, axis=1)
    return {'paired_frames':len(errors), 'rmse_px':float(np.sqrt(np.mean(distance**2))),
            'bias_px':errors.mean(axis=0).tolist(), 'median_error_px':float(np.median(distance)),
            'p95_error_px':float(np.percentile(distance,95,method='linear'))}


def assess_manual_reviews(external_report, reference_manifest, annotations=None, *, interval_s=2.0):
    """Assess supplied independent references, retaining honest missing-evidence states."""
    from realign.product.evidence import validate_external
    validate_external(external_report)
    metadata = _metadata(external_report)
    frames = _validate_manifest(reference_manifest, metadata)
    if type(interval_s) not in (int,float) or not math.isfinite(interval_s) or interval_s <= 0:
        raise ManualReviewError('positive finite playback interval required')
    try:
        annotation_digest = digest(annotations) if annotations is not None else None
    except (ValueError,TypeError,RecursionError):
        raise ManualReviewError('annotations must contain finite, canonical JSON values') from None
    result = {'schema_version':1, 'status':'NOT_VALIDATED', 'observation_source':'REAL_EXTERNAL',
        'video_sha256':metadata.video_sha256, 'reference_manifest_sha256':digest(reference_manifest),
        'source_report_sha256':digest(external_report),
        'annotations_sha256':annotation_digest,
        'attestation_status':'NOT_PROVIDED', 'reviewer':None, 'reviewed_utc':None,
        'expected_reference_frames':len(frames), 'annotated_frames':0,
        'tracking_interval_s':float(interval_s),
        'metrics':localization_metrics([]), 'frame_errors':[],
        'contexts':{key:localization_metrics([]) for key in CONTEXTS},
        'tracking_intervals':[], 'blockers':[], 'phone_g2_passed':False,
        'limitations':[
            'Independence and authorship are reviewer self-declarations, not externally proven identity.',
            'Twenty previously exported frames are not a random accuracy sample of the entire video.',
            'Rejected or missing SAM centers cannot receive invented localization errors.',
            'Playback PTS are not independently established physical capture time.',
            'Reversal, occlusion and apparent_contact are reviewer visual labels, not physical event ground truth.',
            'Pixel localization agreement does not establish metric calibration or a physical dynamics claim.']}
    track = external_report.get('track')
    if track is None:
        result['blockers'].append('ACTUAL_SAM_TRACK_REQUIRED')
        return result
    times = metadata.t_s
    origin = float(times[0])
    bins = np.floor((times-origin)/interval_s).astype(int)
    for number in np.unique(bins):
        indices = np.flatnonzero(bins == number)
        accepted = sum(track['valid'][int(i)] for i in indices)
        result['tracking_intervals'].append({
            'start_pts_s':origin+int(number)*interval_s,
            'end_pts_s':origin+(int(number)+1)*interval_s,
            'interval_convention':'start inclusive, end exclusive',
            'first_frame_index':int(indices[0]), 'last_frame_index':int(indices[-1]),
            'total_frames':len(indices), 'accepted_frames':accepted,
            'rejected_frames':len(indices)-accepted, 'acceptance_fraction':accepted/len(indices)})
    if annotations is None:
        result['blockers'].append('INDEPENDENT_HUMAN_ANNOTATIONS_REQUIRED')
        return result
    if not isinstance(annotations, dict):
        raise ManualReviewError('a provenance-bearing annotation document is required, not unverified rows')
    if annotations.get('annotation_source') == 'SYNTHETIC_TEST_REFERENCE':
        result['attestation_status'] = 'SYNTHETIC_REFERENCE_NOT_REAL_VALIDATION'
        result['blockers'].append('SYNTHETIC_ANNOTATIONS_CANNOT_VALIDATE_REAL_SAM')
        return result
    if (annotations.get('annotation_source') != 'INDEPENDENT_HUMAN' or
        annotations.get('independent_of_sam') is not True or
        annotations.get('independence_attestation') != ATTESTATION):
        result['attestation_status'] = 'UNVERIFIED'
        result['blockers'].append('INDEPENDENT_REVIEW_ATTESTATION_REQUIRED')
        return result
    reviewer, reviewed_utc = annotations.get('reviewer'), annotations.get('reviewed_utc')
    if not isinstance(reviewer,str) or not reviewer.strip() or len(reviewer)>128:
        raise ManualReviewError('named reviewer required')
    try:
        reviewed = datetime.fromisoformat(reviewed_utc.replace('Z','+00:00'))
        if reviewed.tzinfo is None: raise ValueError()
    except (AttributeError,ValueError,TypeError):
        raise ManualReviewError('timezone-aware review time required') from None
    if (annotations.get('schema_version') != 1 or annotations.get('observation_source') != 'REAL_EXTERNAL' or
        annotations.get('video_sha256') != metadata.video_sha256 or
        annotations.get('reference_manifest_sha256') != digest(reference_manifest)):
        raise ManualReviewError('annotation document video or clean-reference manifest mismatch')
    result.update(attestation_status='SELF_DECLARED_INDEPENDENCE',reviewer=reviewer.strip(),reviewed_utc=reviewed_utc)
    rows = annotations.get('rows')
    if not isinstance(rows,list) or len(rows)>len(frames):
        raise ManualReviewError('one row per exported clean reference is permitted')
    seen = set()
    errors = []
    context_errors = {key:[] for key in CONTEXTS}
    context_counts = {key:{'annotated_frames':0,'rejected_track_frames':0} for key in CONTEXTS}
    for row in rows:
        if not isinstance(row,dict): raise ManualReviewError('annotation row must be an object')
        index = row.get('frame_index')
        if type(index) is not int or index not in frames or index in seen:
            raise ManualReviewError('annotation frame identity invalid or repeated')
        seen.add(index)
        ref = frames[index]
        if (row.get('frame_sha256') != ref['frame_sha256'] or row.get('pts') != ref['pts'] or
            type(row.get('pts')) is not int or
            not isinstance(row.get('pts_s'),(int,float)) or
            not math.isclose(row['pts_s'],ref['pts_s'],rel_tol=0,abs_tol=1e-12)):
            raise ManualReviewError('annotation frame hash or original PTS mismatch')
        center = row.get('center_px')
        if center is None: continue
        sigma = row.get('annotation_sigma_px')
        contexts = row.get('contexts',[])
        if (not isinstance(center,list) or len(center)!=2 or
            any(type(x) not in (int,float) or not math.isfinite(x) for x in center) or
            not 0<=center[0]<metadata.width or not 0<=center[1]<metadata.height or
            type(sigma) not in (int,float) or not math.isfinite(sigma) or sigma<=0 or
            not isinstance(contexts,list) or any(type(key) is not str or key not in CONTEXTS for key in contexts) or
            len(contexts)!=len(set(contexts))):
            raise ManualReviewError('independent center, positive uncertainty and valid visual contexts required')
        result['annotated_frames'] += 1
        accepted = track['valid'][index]
        error = (np.asarray(track['xy_px'][index])-center).tolist() if accepted else None
        result['frame_errors'].append({'frame_index':index, 'pts':metadata.pts[index],
            'pts_s':float(times[index]), 'frame_sha256':ref['frame_sha256'],
            'reference_center_px':center, 'annotation_sigma_px':sigma, 'contexts':contexts,
            'track_accepted':accepted, 'error_xy_px':error,
            'euclidean_error_px':float(np.linalg.norm(error)) if error is not None else None})
        if error is not None: errors.append(error)
        for context in contexts:
            context_counts[context]['annotated_frames'] += 1
            if error is None: context_counts[context]['rejected_track_frames'] += 1
            else: context_errors[context].append(error)
    result['metrics'] = localization_metrics(errors)
    result['contexts'] = {key:dict(localization_metrics(context_errors[key]), **context_counts[key])
                          for key in CONTEXTS}
    if result['annotated_frames'] == len(frames) and errors:
        result['status'] = 'VALIDATED_MANUAL_REFERENCES'
    elif result['annotated_frames']:
        result['status'] = 'PARTIAL_REFERENCES'
        result['blockers'].append('COMPLETE_ALL_TWENTY_REFERENCE_FRAMES')
    else:
        result['blockers'].append('INDEPENDENT_HUMAN_ANNOTATIONS_REQUIRED')
    if not errors and result['annotated_frames']:
        result['blockers'].append('NO_ACCEPTED_SAM_REFERENCE_PAIRS')
    return result


def verify_assessment(assessment, external_report, reference_manifest, annotations=None):
    """Recompute cached metrics and provenance before admitting a product display."""
    if not isinstance(assessment,dict):
        raise ManualReviewError('assessment must be a computed document')
    expected = assess_manual_reviews(external_report,reference_manifest,annotations,
                                    interval_s=assessment.get('tracking_interval_s',2.))
    if digest(assessment) != digest(expected):
        raise ManualReviewError('cached measurement assessment differs from independently recomputed evidence')
    return assessment

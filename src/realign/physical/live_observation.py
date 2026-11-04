"""Read-only SAM observation diagnostics. Never detects targets from RGB."""
from copy import deepcopy
import numpy as np

from realign.perception.sam_client import SamError
from realign.perception.track import extract_track, TrackConfig, TrackFlag


def analyze_masks(run, metadata, manifest):
    """Retain the scientific QA thresholds, including circular contour fitting."""
    ids = sorted({m.object_id for m in run.masks})
    try:
        track = extract_track(run, metadata, config=TrackConfig(max_speed_px_per_s=float('inf')))
        summary = deepcopy(track.summary)
        valid = track.valid
        flags = track.flags
    except SamError as exc:
        if exc.code != 'identity': raise
        track = None
        valid = np.zeros(len(metadata.pts), bool)
        flags = np.full(len(metadata.pts), int(TrackFlag.MISSING), np.uint32)
        for mask in run.masks: flags[mask.frame_index] = int(TrackFlag.IDENTITY)
        summary = {'frames': len(metadata.pts), 'valid_frames': 0, 'object_id': None,
            'quality': 'quarantined', 'missing_or_rejected_fraction': 1.,
            'flag_counts': {f.name: int(np.count_nonzero(flags & int(f))) for f in TrackFlag}}
    mask_frames = {m.frame_index for m in run.masks}
    if not run.masks:
        code = 'SAM_NO_MASKS'
        guidance = ('SAM completed with zero masks; no contour was rejected. Review the selected visual prompt, '
            'target size, contrast, blur and framing. Increase the reviewed processing resolution or improve the scene '
            'before separately authorizing another request. Do not lower circular-target QA.')
        identity = 'NO_TARGET_OBSERVED'
    elif len(ids) != 1:
        code = 'SAM_TARGET_AMBIGUOUS'
        guidance = 'Several SAM object IDs were returned. Review the masks and use a more specific visual prompt; no identity was selected automatically.'
        identity = 'AMBIGUOUS_RETURNED_IDS'
    elif not valid.any():
        code = 'SAM_MASKS_REJECTED_BY_QA'
        guidance = 'SAM returned masks, but all centers failed QA. Inspect frame rejection flags; a circular, unoccluded target is required. Scientific shape criteria remain unchanged.'
        identity = 'SINGLE_SAM_CANDIDATE_NOT_VALIDATED'
    else:
        code = 'PRELIMINARY_PIXELS_ONLY'
        guidance = 'SAM pixel centers are provisional. Independently verify target identity, timing, geometry and reviews before physical fitting.'
        identity = 'SINGLE_SAM_CANDIDATE_SEMANTICS_UNVERIFIED'
    mapping = manifest.get('frames', [])
    first = mapping[0] if mapping else {}
    source_size = first.get('source_size', [metadata.width, metadata.height])
    size = [metadata.width, metadata.height]
    areas = [int(m.pixels.sum()) for m in run.masks]
    diagnostics = {'code': code, 'guidance': guidance, 'returned_mask_count': len(run.masks),
        'returned_object_ids': ids, 'mask_frame_count': len(mask_frames),
        'valid_frame_count': int(valid.sum()), 'invalid_or_missing_frame_count': int((~valid).sum()),
        'qa_rejected_mask_frames': sum(not valid[i] for i in mask_frames),
        'rejection_reasons': summary['flag_counts'], 'target_identity_status': identity,
        'target_prompt': run.receipt.get('prompt'),
        'prompt_binding': 'MATCHED_MANIFEST' if manifest.get('target_prompt') == run.receipt.get('prompt') else 'LEGACY_MANIFEST_PROMPT_UNBOUND',
        'preprocessing': {'source_size': source_size, 'processed_size': size,
            'scale_xy': [size[0] / source_size[0], size[1] / source_size[1]],
            'crop': 'NONE; source padding preserved', 'visibility': 'NO_MASK_BASED_SIZE_ESTIMATE' if not areas else 'MASK_SIZE_ONLY; OPERATOR_MUST_REVIEW_VISIBILITY',
            'mask_area_range_px': [min(areas), max(areas)] if areas else None},
        'frame_flags': [int(f) for f in flags]}
    diagnostics['qa_rejected_mask_frames'] = int(diagnostics['qa_rejected_mask_frames'])
    return track, summary, diagnostics

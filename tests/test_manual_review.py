"""Independent review contracts and analytic scorer; no API or human accuracy claim.

Mock reviewer declarations below exercise document parsing only. They are never
persisted as real annotations. Synthetic-labeled reference documents explicitly
cannot validate the historical external SAM report.
"""
from copy import deepcopy
import hashlib
import json
from pathlib import Path

import numpy as np
import pytest

from realign.audit.chain import digest
from realign.perception.manual_review import (ATTESTATION, ManualReviewError,
    assess_manual_reviews, localization_metrics, prepare_review_package,
    read_review_json, verify_assessment, write_review_json)

ROOT = Path(__file__).resolve().parents[1]
EXTERNAL = ROOT/'artifacts/task05/external_yellow_disc'


@pytest.fixture(scope='module')
def prepared(tmp_path_factory):
    output = tmp_path_factory.mktemp('independent-review')
    manifest = prepare_review_package(EXTERNAL,output)
    report = read_review_json(EXTERNAL/'external_verification.json')
    return output, manifest, report


def unit_declaration(prepared, *, count=20):
    """A mock declaration for parsing tests, not a human annotation dataset."""
    output, _, _ = prepared
    doc = read_review_json(output/'annotations.template.json')
    doc.update(reviewer='SIMULATED_ATTESTATION_PARSER_TEST', reviewed_utc='2026-11-03T10:00:00Z',
               independent_of_sam=True)
    for row in doc['rows'][:count]:
        row.update(center_px=[100.,100.],annotation_sigma_px=1.5,contexts=['reversal'])
    return doc


def test_prepare_exports_twenty_blank_hash_bound_clean_references(prepared):
    output, manifest, report = prepared
    assert len(manifest['frames']) == 20
    assert manifest['observation_source'] == 'REAL_EXTERNAL'
    assert manifest['video_sha256'] == report['metadata']['video_sha256']
    assert manifest['reference_image_type'] == 'CLEAN_RGB_NO_SAM_HINTS'
    doc = read_review_json(output/'annotations.template.json')
    assert doc['reference_manifest_sha256'] == digest(manifest)
    assert doc['independent_of_sam'] is False and doc['reviewer'] is None
    assert all(row['center_px'] is None and row['annotation_sigma_px'] is None for row in doc['rows'])
    for ref in manifest['frames']:
        assert hashlib.sha256((output/ref['file']).read_bytes()).hexdigest() == ref['frame_sha256']
        assert ref['pts'] == report['metadata']['pts'][ref['frame_index']]
        assert ref['pts_s'] == report['metadata']['t_s'][ref['frame_index']]


def test_annotation_page_contains_no_predicted_centers_or_track_hints(prepared):
    output, _, _ = prepared
    page = (output/'review.html').read_text(encoding='utf-8')
    embedded = page.split('const REVIEW_DATA=',1)[1].split(';\nconst annotation=',1)[0]
    data = json.loads(embedded)
    assert len(data['images']) == 20
    assert all(image.startswith('data:image/png;base64,') for image in data['images'])
    assert all(row['center_px'] is None for row in data['annotations']['rows'])
    def keys(value):
        if isinstance(value,dict):
            return set(value).union(*(keys(v) for v in value.values()))
        if isinstance(value,list):
            return set().union(*(keys(v) for v in value))
        return set()
    assert not {'xy_px','masks','valid_frames','track','quality'}.intersection(keys(data))
    assert ATTESTATION in embedded


def test_prepare_is_idempotent_and_preserves_task05(prepared):
    output, manifest, _ = prepared
    source_hash = hashlib.sha256((EXTERNAL/'external_verification.json').read_bytes()).hexdigest()
    assert prepare_review_package(EXTERNAL,output) == manifest
    assert hashlib.sha256((EXTERNAL/'external_verification.json').read_bytes()).hexdigest() == source_hash
    with pytest.raises(ManualReviewError,match='separate'):
        prepare_review_package(EXTERNAL,EXTERNAL/'forbidden-review-output')


def test_absent_annotations_leave_all_accuracy_values_unvalidated(prepared):
    _, manifest, report = prepared
    value = assess_manual_reviews(report,manifest)
    assert value['status'] == 'NOT_VALIDATED'
    assert value['metrics'] == localization_metrics([])
    assert value['attestation_status'] == 'NOT_PROVIDED'
    assert all(context['rmse_px'] is None for context in value['contexts'].values())
    assert value['annotations_sha256'] is None
    assert value['reference_manifest_sha256'] == digest(manifest)
    assert value['source_report_sha256'] == digest(report)
    assert value['phone_g2_passed'] is False


def test_tracking_acceptance_is_reported_even_without_reference_centers(prepared):
    _, manifest, report = prepared
    value = assess_manual_reviews(report,manifest,interval_s=2.)
    intervals = value['tracking_intervals']
    assert sum(row['total_frames'] for row in intervals) == 600
    assert sum(row['accepted_frames'] for row in intervals) == 550
    assert sum(row['rejected_frames'] for row in intervals) == 50
    assert intervals[0]['start_pts_s'] == 0.
    assert intervals[-1]['last_frame_index'] == 599
    assert all(row['accepted_frames']+row['rejected_frames']==row['total_frames'] for row in intervals)


def test_cached_assessment_metrics_and_identity_are_recomputed(prepared):
    _, manifest, report = prepared
    result = assess_manual_reviews(report,manifest)
    assert verify_assessment(result,report,manifest) is result
    result['metrics']['rmse_px'] = 0.
    with pytest.raises(ManualReviewError,match='recomputed'):
        verify_assessment(result,report,manifest)


def test_analytic_euclidean_errors_bias_percentiles_and_empty_state():
    result = localization_metrics([[3.,4.],[0.,0.],[-3.,4.]])
    assert result['rmse_px'] == pytest.approx(np.sqrt(50./3.))
    assert result['bias_px'] == pytest.approx([0.,8./3.])
    assert result['median_error_px'] == 5. and result['p95_error_px'] == 5.
    assert localization_metrics([])['rmse_px'] is None
    with pytest.raises(ManualReviewError): localization_metrics([[np.nan,0.]])


@pytest.mark.parametrize('source', ['SYNTHETIC_TEST_REFERENCE','SAM_PREDICTION','UNKNOWN'])
def test_synthetic_or_unverified_references_cannot_validate_real_sam(prepared, source):
    _, manifest, report = prepared
    doc = unit_declaration(prepared)
    doc['annotation_source'] = source
    value = assess_manual_reviews(report,manifest,doc)
    assert value['status'] == 'NOT_VALIDATED'
    assert value['metrics']['rmse_px'] is None
    assert value['frame_errors'] == []


@pytest.mark.parametrize('field,value', [('independent_of_sam',False),('independence_attestation','')])
def test_independence_not_assumed_from_center_presence(prepared,field,value):
    _, manifest, report = prepared
    doc = unit_declaration(prepared)
    doc[field] = value
    result = assess_manual_reviews(report,manifest,doc)
    assert result['status'] == 'NOT_VALIDATED'
    assert result['attestation_status'] == 'UNVERIFIED'
    assert result['metrics']['rmse_px'] is None


def test_partial_reference_contract_retains_scope_and_self_declaration(prepared):
    _, manifest, report = prepared
    doc = unit_declaration(prepared,count=2)
    result = assess_manual_reviews(report,manifest,doc)
    assert result['status'] == 'PARTIAL_REFERENCES'
    assert result['attestation_status'] == 'SELF_DECLARED_INDEPENDENCE'
    assert result['annotated_frames'] == 2 and result['metrics']['paired_frames'] == 2
    assert result['contexts']['reversal']['paired_frames'] == 2
    assert result['contexts']['apparent_contact']['rmse_px'] is None
    assert result['annotations_sha256'] == digest(doc)
    assert result['frame_errors'][0]['annotation_sigma_px'] == 1.5


def test_complete_document_requires_twenty_and_never_passes_phone_gate(prepared):
    _, manifest, report = prepared
    result = assess_manual_reviews(report,manifest,unit_declaration(prepared))
    assert result['status'] == 'VALIDATED_MANUAL_REFERENCES'
    assert result['annotated_frames'] == 20 and result['metrics']['paired_frames'] == 20
    assert result['phone_g2_passed'] is False
    assert 'threshold' not in result


@pytest.mark.parametrize('mutation', ['video','manifest','frame_hash','pts','playback_time','duplicate',
                                     'unknown_frame','sigma','center','context','reviewer','date'])
def test_malformed_or_wrong_identity_annotation_rejected(prepared,mutation):
    _, manifest, report = prepared
    doc = unit_declaration(prepared,count=1)
    if mutation == 'video': doc['video_sha256'] = '0'*64
    elif mutation == 'manifest': doc['reference_manifest_sha256'] = '0'*64
    elif mutation == 'frame_hash': doc['rows'][0]['frame_sha256'] = '0'*64
    elif mutation == 'pts': doc['rows'][0]['pts'] += 1
    elif mutation == 'playback_time': doc['rows'][0]['pts_s'] += .01
    elif mutation == 'duplicate': doc['rows'] = [doc['rows'][0],deepcopy(doc['rows'][0])]
    elif mutation == 'unknown_frame': doc['rows'][0]['frame_index'] = 0
    elif mutation == 'sigma': doc['rows'][0]['annotation_sigma_px'] = False
    elif mutation == 'center': doc['rows'][0]['center_px'] = [np.inf,0.]
    elif mutation == 'context': doc['rows'][0]['contexts'] = ['physical_contact_truth']
    elif mutation == 'reviewer': doc['reviewer'] = ''
    elif mutation == 'date': doc['reviewed_utc'] = '2026-11-03T12:00:00'
    with pytest.raises(ManualReviewError):
        assess_manual_reviews(report,manifest,doc)


def test_reference_manifest_cannot_relabel_synthetic_or_phone_as_external(prepared):
    _, manifest, report = prepared
    for source in ('REAL_PHONE','SYNTHETIC_RENDER'):
        altered = deepcopy(manifest)
        altered['observation_source'] = source
        with pytest.raises(ManualReviewError): assess_manual_reviews(report,altered)


def test_rejected_track_pair_has_no_invented_zero_error(prepared):
    _, manifest, report = prepared
    report = deepcopy(report)
    first = manifest['frames'][0]['frame_index']
    report['track']['valid'][first] = False
    report['track']['xy_px'][first] = [None,None]
    report['track']['flags'][first] = 8
    result = assess_manual_reviews(report,manifest,unit_declaration(prepared,count=1))
    assert result['annotated_frames'] == 1 and result['metrics']['paired_frames'] == 0
    assert result['frame_errors'][0]['euclidean_error_px'] is None
    assert result['contexts']['reversal']['rejected_track_frames'] == 1
    assert result['contexts']['reversal']['rmse_px'] is None


def test_changed_assessments_archive_prior_content_without_overwriting_references(tmp_path):
    path = tmp_path/'measurement_validation.json'
    write_review_json(path,{'status':'NOT_VALIDATED'})
    prior = path.read_bytes()
    with pytest.raises(ManualReviewError): write_review_json(path,{'status':'PARTIAL_REFERENCES'})
    write_review_json(path,{'status':'PARTIAL_REFERENCES'},archive_previous=True)
    history = tmp_path/'history'/('measurement_validation.'+hashlib.sha256(prior).hexdigest()+'.json')
    assert history.read_bytes() == prior
    assert read_review_json(path)['status'] == 'PARTIAL_REFERENCES'


@pytest.mark.parametrize('text', ['{"a":1,"a":2}','{"a":NaN}','{"a":1e999}'])
def test_review_json_rejects_ambiguous_or_nonfinite_payloads(tmp_path,text):
    path = tmp_path/'review.json'
    path.write_text(text,encoding='utf-8')
    with pytest.raises(ManualReviewError): read_review_json(path)


def test_review_json_cannot_read_sealed_data(tmp_path):
    path = tmp_path/'sealed'/'review.json'
    path.parent.mkdir()
    path.write_text('{}')
    with pytest.raises(ManualReviewError): read_review_json(path)

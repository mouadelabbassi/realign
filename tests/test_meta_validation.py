"""SIMULATED API FIXTURES ONLY. No network calls or credentials in this file."""
import json
from dataclasses import replace, asdict
from types import SimpleNamespace as NS
from pathlib import Path
import pytest
from openai.types.chat import ChatCompletionMessage
from pydantic import ValidationError
from realign.perception.meta_validation import probe_muse, sum_finite, MODEL
from realign.contracts.external import ExternalVideoSource
from realign.contracts.investigator_tools import SCHEMAS, tool_json_schemas
from realign.perception.video import metadata_from_ffprobe, VideoError
from realign.report.g2_report import assess_g2


def fake_client(*, error=False, tool_name='sum_finite', no_tool=False, arguments='{"values":[17,29]}', final=46):
    requests = []
    def create(**kw):
        requests.append(json.loads(json.dumps(kw)))
        if error:
            raise RuntimeError('SENSITIVE_SERVER_CONTENT_MUST_NOT_BE_SAVED')
        if len(requests) == 1:
            m = ChatCompletionMessage(role='assistant', content='{"value":14}')
        elif len(requests) == 2 and not no_tool:
            m = ChatCompletionMessage(role='assistant', tool_calls=[{'id': 'call_fixture', 'type': 'function',
                'function': {'name': tool_name, 'arguments': arguments}}])
        else:
            m = ChatCompletionMessage(role='assistant', content=json.dumps({'value': final}))
        return NS(choices=[NS(message=m)])
    client = NS(models=NS(list=lambda: NS(data=[NS(id=MODEL)])), chat=NS(completions=NS(create=create)))
    return client, requests


def test_structured_and_genuine_local_tool_round_trip_fixture():
    client, requests = fake_client()
    report = probe_muse(client)
    assert report['status'] == 'PASS' and report['source'] == 'SIMULATED_API_FIXTURE'
    assert report['successful_calls'] == 0 and report['failed_calls'] == 0
    assert report['checks']['tool_round_trip']['executed_local_tools'] == 1
    final_messages = requests[-1]['messages']
    assert final_messages[-2]['role'] == 'assistant'
    assert final_messages[-2]['tool_calls'][0]['id'] == final_messages[-1]['tool_call_id']
    assert json.loads(final_messages[-1]['content']) == {'value': 46.}
    assert requests[-1]['tool_choice'] == 'auto'
    assert requests[0]['response_format']['type'] == 'json_schema'


@pytest.mark.parametrize('kwargs', [{'no_tool': True}, {'tool_name': 'unapproved'}, {'arguments': '{bad'},
                                    {'arguments': '{"values":[1,2]}'}, {'final': 45}])
def test_failed_tool_round_trips_not_promoted_to_api_success(kwargs):
    client, _ = fake_client(**kwargs)
    r = probe_muse(client)
    assert r['status'] == 'FAIL' and r['checks']['tool_round_trip']['status'] == 'FAIL'
    assert r['successful_calls'] == 0


def test_api_errors_are_sanitized_and_counted_separately():
    client, _ = fake_client(error=True)
    r = probe_muse(client, source='REAL_API')  # transport is still a TEST DOUBLE
    assert r['status'] == 'FAIL' and r['failed_calls'] == 2
    assert 'SENSITIVE_SERVER_CONTENT' not in json.dumps(r)


@pytest.mark.parametrize('args', ['{"values":[true]}', '{"values":[NaN]}', '{"values":[1],"extra":0}',
                                  '{"values":[1],"values":[2]}', '{"values":[10001]}', '{"values":[]}'])
def test_malformed_tool_arguments_rejected(args):
    with pytest.raises(ValueError):
        sum_finite(args)


def source():
    return ExternalVideoSource('https://example.org/source', 'https://example.org/video.mp4', 'fixture author',
            'CC0-1.0', 'https://creativecommons.org/publicdomain/zero/1.0/', 'EXPLICIT PROVENANCE CONTRACT FIXTURE',
            'a'*64, 'b'*64, 'Unchanged fixture bytes', True, False)


def metadata(kind='REAL_EXTERNAL', external=None, digest='b'*64):
    return metadata_from_ffprobe({'streams': [{'width': 640, 'height': 480, 'time_base': '1/1000'}],
              'frames': [{'pts': p} for p in (100, 140, 200)]},
              video_sha256=digest, source_kind=kind, external_source=external)


def test_external_video_requires_license_attribution_and_matching_hash():
    m = metadata(external=source())
    assert m.source_kind == 'REAL_EXTERNAL' and m.pts == (100, 140, 200)
    assert m.external_source.original_sha256 != m.video_sha256
    assert not m.external_source.capture_time_scale_verified
    with pytest.raises(VideoError):
        metadata(external=None)
    with pytest.raises(VideoError):
        metadata(external=source(), digest='a'*64)
    with pytest.raises(VideoError):
        metadata(kind='REAL_PHONE', external=source())
    with pytest.raises(ValueError):
        replace(source(), physical_recording=False)
    with pytest.raises(ValueError):
        replace(source(), license_id='ALL_RIGHTS_RESERVED')


def test_external_processing_cannot_satisfy_phone_gate():
    r = {'recording_id': 'opaque', 'provenance': 'REAL_SAM',
         'metadata': {'source_kind': 'REAL_EXTERNAL'}, 'sam_receipt': {'source': 'REAL_API', 'response_id': 'fixture'},
         'missing_or_rejected_fraction': 0., 'release_sigma_s': .01}
    passed, reasons = assess_g2([r]*3, None, None, None, None)
    assert not passed and any('phone' in s for s in reasons)


def test_external_unverified_time_scale_cannot_enter_real_fitting_pipeline():
    from realign.perception.pipeline import make_video_trial
    m = metadata(external=source())
    run = NS(source='REAL_API', video_sha256=m.video_sha256)
    cal = NS(image_size=(m.width, m.height))
    with pytest.raises(ValueError, match='time'):
        make_video_trial('opaque', m, run, None, cal, None)
    run.source = 'SIMULATED_API_FIXTURE'
    with pytest.raises(ValueError, match='actual SAM'):
        make_video_trial('opaque', m, run, None, cal, None)


@pytest.mark.parametrize('name', list(SCHEMAS))
def test_tool_schemas_closed_and_truth_sealed_fields_rejected(name):
    inp, out = SCHEMAS[name]
    schema = tool_json_schemas()[name]
    assert schema['implementation_status'] == 'SCHEMA_ONLY'
    for model in (inp, out):
        assert model.model_json_schema()['additionalProperties'] is False
        with pytest.raises(ValidationError):
            model.model_validate({'hidden_parameters': {'peg': .16}, 'sealed_measurements': [1, 2], 'truth_label': 'peg'})
    assert not any(s in json.dumps(schema).lower() for s in ('ground_truth', 'sealed_trial', 'hidden_parameter'))


def test_opaque_refs_and_exploration_zone_required_by_handoff():
    cls = SCHEMAS['inspect_discrepancy'][0]
    value = cls(trial_refs=('a'*64,), model_ref='b'*64)
    assert value.zone == 'exploration'
    with pytest.raises(ValidationError):
        cls(trial_refs=('a'*64,), model_ref='b'*64, zone='sealed')
    with pytest.raises(ValidationError):
        cls(trial_refs=('../../sealed/secret',), model_ref='b'*64)
    assert cls.model_validate_json(value.model_dump_json()) == value

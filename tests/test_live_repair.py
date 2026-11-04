"""Task 09.1 TEST_FIXTURE contracts; no physical camera or Meta request."""
import asyncio
from copy import deepcopy
import json
import threading
from types import SimpleNamespace as NS

import numpy as np
import pytest

from realign.agent.adapters import AdapterFailure, MuseAdapter
from realign.audit.chain import digest
from realign.contracts.investigation import Budget
from realign.contracts.investigation import AgentTurn, Hypothesis
from realign.contracts.video import VideoMetadata
from realign.perception.sam_client import SamRun, SamMask, parse_sam_events
from realign.physical.live_investigation import LiveConfig, LiveInvestigation, AuthorizationError
from realign.physical.live_observation import analyze_masks
from realign.physical.live_science import LiveScientificSession
from realign.physical.live_science import ScientificGateRejection
from realign.physical.live_forensics import inspect_session
from realign.synth.video_fixture import fixture_events, protocol_line
from test_live_investigation import POLICY, MockMeta, MockStream, NoReasoning, ScriptedAdapter, eligible_snapshot, frames, until, live_factory


def parsed_run(*, empty=False):
    meta = VideoMetadata('a'*64, 'SYNTHETIC_RENDER', 96, 64, 96, 64, (0, 100, 200), '1/1000', 'TEST_FIXTURE')
    text = '' if empty else ''.join(protocol_line(i,20,20,width=96,height=64) for i in range(3))
    run = asyncio.run(parse_sam_events(fixture_events(text=text),meta,source='SIMULATED_API_FIXTURE'))
    manifest = {'target_prompt': run.receipt['prompt'], 'frames': [{'source_size':[192,128]} for _ in meta.pts]}
    return run, meta, manifest


def test_empty_response_reports_zero_masks_not_shape_rejections():
    run, meta, manifest = parsed_run(empty=True)
    track, summary, diagnostic = analyze_masks(run, meta, manifest)
    assert diagnostic['code'] == 'SAM_NO_MASKS'
    assert diagnostic['returned_mask_count'] == 0 and diagnostic['valid_frame_count'] == 0
    assert diagnostic['qa_rejected_mask_frames'] == 0
    assert diagnostic['rejection_reasons']['MISSING'] == 3
    assert diagnostic['rejection_reasons']['SHAPE'] == 0
    assert diagnostic['target_identity_status'] == 'NO_TARGET_OBSERVED'
    assert diagnostic['preprocessing']['scale_xy'] == [.5, .5]
    assert diagnostic['preprocessing']['mask_area_range_px'] is None


def test_real_parser_circular_masks_pass_and_invalid_masks_stay_rejected():
    run, meta, manifest = parsed_run()
    track, _, diagnostic = analyze_masks(run, meta, manifest)
    assert track.valid.all() and diagnostic['returned_mask_count'] == 3
    bad = SamRun((SamMask(0,'0',20,20,np.ones((1,1),bool)),),run.source,meta.video_sha256,run.receipt)
    track, _, diagnostic = analyze_masks(bad, meta, manifest)
    assert not track.valid.any()
    assert diagnostic['code'] == 'SAM_MASKS_REJECTED_BY_QA'
    assert diagnostic['rejection_reasons']['EMPTY'] == 1
    noncircular = SamRun((SamMask(0,'0',20,20,np.ones((4,30),bool)),),run.source,meta.video_sha256,run.receipt)
    track, _, diagnostic = analyze_masks(noncircular, meta, manifest)
    assert not track.valid.any() and diagnostic['rejection_reasons']['SHAPE'] == 1
    ambiguous = SamRun(run.masks + (SamMask(0,'1',20,20,run.masks[0].pixels),),run.source,meta.video_sha256,run.receipt)
    track, _, diagnostic = analyze_masks(ambiguous, meta, manifest)
    assert track is None and diagnostic['code'] == 'SAM_TARGET_AMBIGUOUS'
    assert diagnostic['returned_object_ids'] == ['0','1']


def test_empty_live_window_has_no_overlap_agreement_or_paid_muse(live_factory):
    transport = MockMeta()
    async def empty(**kwargs): return MockStream(fixture_events(frames=[]),transport)
    transport.responses.create = empty
    live, _ = live_factory(transport, LiveConfig(window_s=1.,overlap_s=0.),
        reasoner_factory=lambda owner: LiveScientificSession(owner,adapter_factory=ScriptedAdapter))
    frames(live,12)
    until(lambda: live.latest is not None)
    assert live.latest['identity_continuity'] == 'NO_OBSERVATIONS'
    until(lambda: live.scientific['readiness']['code']=='NO_USABLE_OBSERVATIONS')
    for _ in range(5): live.enqueue_science('operator',{})
    until(lambda: not live.science_busy and live.science.empty())
    assert live.ledger.snapshot()['attempted_requests']['muse'] == 0
    assert live.pending_action is None and live.scientific['hypotheses'] == []
    assert 'LOCAL_READINESS' in (live.root/'timeline.jsonl').read_text()


def test_no_muse_on_unchanged_or_empty_evidence_after_protocol_failure(live_factory):
    class Broken(ScriptedAdapter):
        def next(self, context):
            self.before_request('muse','reasoning')
            raise AdapterFailure('TEST_FIXTURE_REDACTED',code='INVALID_STRUCTURED_RESPONSE')
    live, _ = live_factory()
    science = LiveScientificSession(live,adapter_factory=Broken)
    for _ in range(5): science.consume('operator',{})
    assert science.adapter is None
    with pytest.raises(AdapterFailure): science.consume('observation',eligible_snapshot())
    for _ in range(5): science.consume('operator',{})
    assert live.ledger.snapshot()['attempted_requests']['muse'] == 1
    science.consume('observation',{**eligible_snapshot(), 'window_id':'empty', 'rows':[], 'track':{'valid_frames':0},'new_observations':0})
    science.consume('operator',{})
    assert live.ledger.snapshot()['attempted_requests']['muse'] == 1
    science.consume('observation',eligible_snapshot('new-window',2))
    with pytest.raises(AdapterFailure): science.consume('operator',{})
    assert live.ledger.snapshot()['attempted_requests']['muse'] == 2
    science.close()


def test_refused_tool_round_does_not_lock_muse_after_new_eligible_evidence(live_factory):
    from openai.types.chat import ChatCompletion
    requests=[]
    def respond(**kwargs):
        requests.append(kwargs)
        context=json.loads(kwargs['messages'][-1]['content'])
        if len(requests)==1:
            message={'role':'assistant','tool_calls':[{'id':'remote_TEST_FIXTURE','type':'function',
                'function':{'name':'fit_candidate_model','arguments':json.dumps({'trial_refs':['a'*64],
                    'candidate':'FREE','nominal_model_ref':'b'*64,'budget_ref':'c'*64})}}]}
            finish='tool_calls'
        else:
            action='HYPOTHESIZE' if context['stage']=='HYPOTHESIZE' else 'REQUEST_EVIDENCE'
            turn=AgentTurn(action=action,hypotheses=(Hypothesis(family='MEASUREMENT',status='UNRESOLVED',evidence_refs=()),),
                experiment_ref=context['candidates'][0]['experiment_ref'] if action=='REQUEST_EVIDENCE' else None,
                outcome=None,model_ref=None,evidence_refs=tuple(context['evidence_refs']),reasons=())
            message={'role':'assistant','content':turn.model_dump_json()};finish='stop'
        return ChatCompletion(id='chatcmpl_TEST_FIXTURE',object='chat.completion',created=0,model='muse-spark-1.3',
            choices=[{'index':0,'message':message,'finish_reason':finish}])
    class Client:
        chat=NS(completions=NS(create=respond))
        def close(self): pass
    live,_=live_factory()
    science=LiveScientificSession(live,adapter_factory=lambda budget:MuseAdapter(Client(),budget=budget,source='SIMULATED_API_FIXTURE'))
    with pytest.raises(ScientificGateRejection) as failure:
        science.consume('observation',eligible_snapshot())
    assert failure.value.code=='SCIENTIFIC_TOOLS_UNAVAILABLE'
    assert science.adapter._pending==() and science.agent is None and live.scientific['tool_results']==[]
    feedback=json.loads(science.adapter.messages[-1]['content'])
    assert feedback=={'error':{'code':'SCIENTIFIC_TOOLS_UNAVAILABLE','source':'LOCAL_CONTROLLER_GATE','executed':False}}
    for _ in range(3): science.consume('operator',{})
    assert len(requests)==1
    science.last_reasoning=float('inf')
    science.consume('observation',eligible_snapshot('new-data',2))
    science.consume('operator',{})
    assert len(requests)==3 and live.pending_action is not None
    assert science.adapter._pending==() and live.scientific['tool_results']==[]
    science.close()


@pytest.mark.parametrize('http_status', [400,401,429])
def test_safe_muse_http_diagnostic_retains_status_without_response_body(http_status):
    class HttpFailure(RuntimeError): status_code=http_status
    def request(**kwargs): raise HttpFailure('TEST_FIXTURE_SENSITIVE_CONTENT_DO_NOT_SAVE')
    adapter=MuseAdapter(NS(chat=NS(completions=NS(create=request))),budget=Budget(),retry_delay=0)
    with pytest.raises(AdapterFailure) as failure: adapter.next({'stage':'HYPOTHESIZE'})
    assert failure.value.code=='META_HTTP_ERROR' and failure.value.category=='META_HTTP'
    assert failure.value.http_status==http_status
    assert 'SENSITIVE_CONTENT' not in json.dumps([failure.value.diagnostic(),adapter.receipts])


def test_safe_protocol_failure_is_distinct_from_unsuccessful_http():
    class Message:
        content='TEST_FIXTURE_INVALID_JSON_SENSITIVE'; tool_calls=None
        def model_dump(self, **kwargs): return {'role':'assistant','content':self.content}
    response=NS(choices=[NS(message=Message(),finish_reason='stop')],usage=None)
    adapter=MuseAdapter(NS(chat=NS(completions=NS(create=lambda **kw:response))),budget=Budget())
    with pytest.raises(AdapterFailure) as failure: adapter.next({'stage':'HYPOTHESIZE'})
    assert failure.value.code=='INVALID_STRUCTURED_RESPONSE'
    assert failure.value.category=='MODEL_PROTOCOL' and adapter.receipts[-1]['status']=='completed'
    assert 'SENSITIVE' not in json.dumps([failure.value.diagnostic(),adapter.receipts])


def test_worker_persists_typed_failure_and_only_closed_receipt_fields(live_factory):
    class Rejector(NoReasoning):
        adapter=NS(receipts=[{'status':'completed','response_sha256':'a'*64,'body':'TEST_FIXTURE_SENSITIVE_BODY'}])
        def consume(self, *args): raise AdapterFailure('TEST_FIXTURE_SENSITIVE_MESSAGE',code='INVALID_STRUCTURED_RESPONSE')
    live,_=live_factory(reasoner_factory=Rejector)
    live.enqueue_science('operator',{})
    until(lambda:'last_error' in live.scientific)
    error=live.scientific['last_error']
    assert error['category']=='MODEL_PROTOCOL' and error['code']=='INVALID_STRUCTURED_RESPONSE'
    assert error['api_receipts'][0]['status']=='completed'
    assert 'SENSITIVE' not in (live.root/'timeline.jsonl').read_text()


def test_scientific_gate_rejection_is_distinct_from_model_protocol(live_factory):
    class Rejector(NoReasoning):
        def consume(self,*args): raise ValueError('TEST_FIXTURE_SENSITIVE_GATE_INPUT')
    live,_=live_factory(reasoner_factory=Rejector)
    live.enqueue_science('admit',{'manifest':'TEST_FIXTURE.json'})
    until(lambda:'last_error' in live.scientific)
    assert live.scientific['last_error']['category']=='SCIENTIFIC_VALIDATION'
    assert live.scientific['last_error']['code']=='EVIDENCE_ADMISSION_REJECTED'
    assert 'SENSITIVE' not in (live.root/'timeline.jsonl').read_text()


def test_config_rejects_unconfirmed_real_target_without_starting_workers(tmp_path):
    with pytest.raises(AuthorizationError): LiveInvestigation(tmp_path,POLICY)
    for kwargs in [{'analysis_interval_s':1.},{'target_prompt':'<unreviewed>'},{'processing_width':4096}]:
        with pytest.raises(ValueError): LiveConfig(**kwargs)


def test_selected_prompt_and_preprocessing_bind_manifest_and_receipt(live_factory):
    config=LiveConfig(window_s=1.,overlap_s=0.,target_prompt='grey circular weight',target_confirmed=True,processing_width=1280)
    live,_=live_factory(config=config)
    frames(live,12)
    until(lambda:live.latest is not None)
    manifest=json.loads(next(live.root.glob('window-*/manifest.json')).read_text())
    assert manifest['target_prompt']==live.latest['receipt']['prompt']=='grey circular weight'
    assert manifest['target_confirmed'] is True
    assert live.latest['diagnostic']['prompt_binding']=='MATCHED_MANIFEST'


def test_less_frequent_nonoverlapping_windows_keep_original_source_indices(live_factory):
    live,_=live_factory(config=LiveConfig(window_s=1.,overlap_s=0.,analysis_interval_s=3.))
    frames(live,12); until(lambda:live.processed==1)
    frames(live,18,start=12)
    until(lambda:live.frames.empty())
    assert live.finalized==1
    frames(live,12,start=30); until(lambda:live.processed==2)
    windows=[json.loads(p.read_text()) for p in sorted(live.root.glob('window-*/manifest.json'))]
    a,b=[{r['capture_sequence'] for r in w['frames']} for w in windows]
    assert not a & b and min(b)>=30
    assert live.cadence_skipped_frames>0


def test_identical_content_with_same_prompt_is_never_uploaded_twice(live_factory):
    transport=MockMeta();transport.hold.set()
    live,_=live_factory(transport)
    def buffer(offset):
        return [(np.full((64,96,3),80,np.uint8),{'recording_id':'TEST_FIXTURE',
            'capture_sequence':offset+i,'encoded_frame_index':offset+i,'arrival_monotonic_ns':int(1e9+(offset+i)*1e8),
            'source_size':[96,64],'processed_size':[96,64],'response_to_request_id':None}) for i in range(12)]
    live._finalize(buffer(0),partial=False);until(transport.entered.is_set)
    live._finalize(buffer(100),partial=False)
    assert live.skipped['DUPLICATE_CONTENT_AND_PROMPT']==1
    assert transport.dispatches==['upload','segmentation']
    assert live.finalized==2 and live.frames.empty()
    transport.hold.clear()


def test_busy_science_worker_coalesces_snapshots_without_silent_observation_loss(live_factory):
    entered, release = threading.Event(), threading.Event()
    consumed=[]
    class Held(NoReasoning):
        def consume(self, kind, value):
            if kind=='operator': entered.set(); release.wait(timeout=5)
            elif kind=='admit': consumed.append('CONTROL_ADMIT')
            else: consumed.append(value['window_id'])
    live,_=live_factory(reasoner_factory=Held)
    live.enqueue_science('operator',{})
    assert entered.wait(timeout=5)
    live.enqueue_science('admit',{'manifest':'TEST_FIXTURE.json'})
    live.enqueue_science('observation',eligible_snapshot('first',1))
    live.enqueue_science('observation',eligible_snapshot('latest',2))
    assert live.coalesced_observations==1 and live.dropped['science']==0
    release.set();until(lambda:consumed==['CONTROL_ADMIT','latest'])
    assert 'SCIENCE_OBSERVATION_COALESCED' in (live.root/'timeline.jsonl').read_text()


def test_forensic_reader_is_offline_and_never_rewrites_saved_files(live_factory,monkeypatch):
    import realign.physical.live_forensics as module
    from realign.perception.video import file_sha256
    from realign.perception.sam_client import SamClient
    transport=MockMeta()
    async def empty(**kwargs): return MockStream(fixture_events(frames=[]),transport)
    transport.responses.create=empty
    live,_=live_factory(transport,LiveConfig(window_s=1.,overlap_s=0.))
    frames(live,12);until(lambda:live.processed==1);live.close()
    def forbidden(*args,**kwargs): raise AssertionError('Forensics must never construct a Meta client')
    monkeypatch.setattr(SamClient,'from_environment',forbidden)
    monkeypatch.setattr(MuseAdapter,'from_environment',forbidden)
    def cached(path,meta):
        index=json.loads(path.with_suffix('.json').read_text())
        assert index['source']=='SIMULATED_API_FIXTURE'
        assert index['video_sha256']==meta.video_sha256
        return SamRun((),'SIMULATED_API_FIXTURE',meta.video_sha256,index['receipt'])
    monkeypatch.setattr(module,'load_sam_cache',cached)
    before={p:file_sha256(p) for p in live.root.rglob('*') if p.is_file()}
    report=inspect_session(live.root)
    assert report['new_meta_requests']==0 and report['windows'][0]['replay_valid_frames']==0
    assert all(file_sha256(p)==sha for p,sha in before.items())
    manifest=next(live.root.glob('window-*/manifest.json'))
    doc=json.loads(manifest.read_text());doc['target_prompt']='tampered TEST_FIXTURE'
    manifest.write_text(json.dumps(doc))
    with pytest.raises(ValueError,match='MANIFEST_HASH_CHANGED'): inspect_session(live.root)

"""Task 09.2: TEST_FIXTURE camera and mocked Meta; never paid API evidence."""
import asyncio
from copy import deepcopy
import json
from pathlib import Path
import threading
import time
from types import SimpleNamespace as NS

import numpy as np
import pytest

from realign.audit.chain import AuditChain
from realign.perception.sam_client import SamClient, SamError, parse_sam_events
from realign.physical.live_investigation import LiveConfig, LiveInvestigation, AuthorizationError
from realign.physical.live_lab import CaptureController, LabLibrary
from realign.physical.live_science import LiveScientificSession
from realign.synth.video_fixture import fixture_events, protocol_line
from test_live_investigation import POLICY, MockMeta, MockStream, ScriptedAdapter, frames, until


def feed_fixture_windows(live,count,*,start=0):
    """Wait for the local encoder, never for SAM. Avoid timing-based test drops."""
    for i in range(start,start+count):
        frames(live,1,start=i,pause=0)
        until(live.frames.empty)


class AutoMeta(MockMeta):
    def __init__(self, *, empty=False, partial_hold=False, fail_terminal=False):
        super().__init__()
        self.empty=empty
        self.partial_hold=threading.Event()
        if partial_hold: self.partial_hold.set()
        self.fail_terminal=fail_terminal
        self.requests=[]

    async def respond(self, **kwargs):
        self.dispatches.append('segmentation')
        self.requests.append(kwargs)
        self.entered.set()
        image=kwargs['input'][0]['content'][1]['type']=='input_image'
        text='' if self.empty else ''.join(protocol_line(i,20+i%5,20,width=96,height=64) for i in range(1 if image else self.frame_count))
        events=fixture_events(text=text,failure='failed' if self.fail_terminal else None)
        owner=self
        class Stream(MockStream):
            async def __aiter__(self):
                for i,event in enumerate(self.events):
                    if i:
                        while owner.partial_hold.is_set(): await asyncio.sleep(.01)
                    while owner.hold.is_set(): await asyncio.sleep(.01)
                    yield event
        return Stream(events,self)


@pytest.fixture
def auto_factory(tmp_path):
    sessions=[]
    def build(transport=None, *, adapter_factory=ScriptedAdapter, config=None):
        transport=transport or AutoMeta()
        holder={}
        class Client(SamClient):
            async def segment_video(self,path,metadata):
                transport.frame_count=len(metadata.pts)
                return await super().segment_video(path,metadata)
        def sam():
            return Client(transport,source='SIMULATED_API_FIXTURE',concept=holder['live'].config.target_prompt,
                before_request=holder['live'].ledger.reserve,max_attempts=1)
        def factory(root,policy,**kwargs):
            live=LiveInvestigation(root,policy,source='TEST_FIXTURE',sam_factory=sam,
                reasoner_factory=lambda owner:LiveScientificSession(owner,adapter_factory=adapter_factory),**kwargs)
            holder['live']=live;sessions.append(live);return live
        settings=config or LiveConfig(mode='AUTO_LIVE',window_s=1,overlap_s=0,analysis_interval_s=1,
            target_prompt='circular test weight',target_confirmed=True)
        return factory,transport,settings
    yield build
    for live in sessions: live.close()


def test_image_parser_uses_image_format_and_preserves_unknown_confidence():
    meta=NS(width=96,height=64,pts=(0,),video_sha256='a'*64)
    run=asyncio.run(parse_sam_events(fixture_events(text=protocol_line(0,20,20,width=96,height=64)),meta,
        source='SIMULATED_API_FIXTURE',media_kind='image'))
    assert run.receipt['media_kind']=='image'
    assert run.masks[0].frame_index==0 and run.masks[0].confidence is None
    with pytest.raises(SamError,match='parser'):
        asyncio.run(parse_sam_events(fixture_events(text=protocol_line(1,20,20,width=96,height=64)),meta,
            source='SIMULATED_API_FIXTURE',media_kind='image'))


def test_authorize_before_connect_first_frame_automatically_observes_and_reasons(auto_factory,tmp_path):
    from test_live_lab import Camera
    factory,transport,settings=auto_factory()
    camera=Camera();camera.frames=[np.full((64,96,3),80,np.uint8) for _ in range(80)]
    owner=CaptureController(LabLibrary(tmp_path/'TEST_FIXTURE'),camera_factory=lambda *a:camera,live_factory=factory)
    try:
        armed=owner.authorize_auto_live(deepcopy(POLICY),settings.__dict__)
        assert armed['lifecycle']=='AUTHORIZED_WAITING_FOR_CAMERA' and not transport.requests
        owner.connect(0,threaded=False)
        assert owner.writer is not None and owner.state=='RECORDING'
        for i in range(8):
            owner.read_once(arrival_ns=1_000_000_000+i*100_000_000)
            time.sleep(.02)
        until(lambda:owner.live.pending_action is not None)
        live=owner.live
        assert transport.requests[0]['input'][0]['content'][1]['type']=='input_image'
        assert transport.requests[0]['input'][0]['content'][1]['image_url'].startswith('data:image/png;base64,')
        assert live.startup_result['track']['valid_frames']==1
        assert live.ledger.snapshot()['attempted_requests']=={'sam':1,'muse':2}
        assert live.pending_action['candidate']['action']['kind']=='STATIONARY_REFERENCE'
        original=deepcopy(live.pending_action)
        clip=owner.recording.name
        owner.confirm_action(original['request_id'])
        assert owner.recording.name!=clip and owner.writer is not None
        assert live.pending_action['request_id']==original['request_id']
        assert owner.provenance['response_to_request_id']==original['request_id']
        for i in range(10):owner.read_once(arrival_ns=3_000_000_000+i*100_000_000)
        assert live.ledger.snapshot()['attempted_requests']['muse']==2
        journal=[json.loads(line) for line in (live.root/'timeline.jsonl').read_text().splitlines()]
        assert AuditChain.verify(journal)
        manifest=json.loads((live.root/'startup-0000/manifest.json').read_text())
        assert manifest['frames'][0]['recording_id']==clip
        assert not (live.root/'sam_cache'/manifest['image_sha256']).with_suffix('.json').exists()
        assert live.snapshot()['overlay']['timing']=='UNVERIFIED_TIMING'
    finally:owner.close()


def test_partial_stream_is_visible_but_never_scientific_evidence(auto_factory,tmp_path):
    factory,transport,settings=auto_factory(AutoMeta(partial_hold=True))
    live=factory(tmp_path,POLICY,config=settings)
    frames(live,2)
    until(lambda:live.overlay is not None)
    assert not live.overlay['stream_completed'] and live.overlay['presentation_only']
    assert live.overlay_jpeg and not live.trajectory and live.latest is None
    assert live.ledger.snapshot()['attempted_requests']['muse']==0
    # Capture and window encoding continue while the SAM terminal event is held.
    feed_fixture_windows(live,30,start=2)
    until(lambda:live.finalized>=2)
    assert live.frames.qsize()<=settings.frame_queue
    transport.partial_hold.clear()
    until(lambda:live.startup_result is not None)
    assert live.startup_result['track']['valid_frames']==1
    until(lambda:live.pending_action is not None)


def test_failed_terminal_invalidates_presented_partial_without_admitting_it(auto_factory,tmp_path):
    factory,transport,settings=auto_factory(AutoMeta(partial_hold=True,fail_terminal=True))
    live=factory(tmp_path,POLICY,config=settings)
    frames(live,2)
    until(lambda:live.overlay is not None)
    transport.partial_hold.clear()
    until(lambda:(live.root/'startup-0000/result.json').is_file())
    assert live.overlay['status']=='TRACK_LOST'
    assert live.latest is None and not live.trajectory and live.pending_action is None
    assert live.ledger.snapshot()['attempted_requests']['muse']==0


def test_zero_target_blocks_more_paid_requests_until_explicit_revised_target_consent(auto_factory,tmp_path):
    factory,transport,settings=auto_factory(AutoMeta(empty=True))
    live=factory(tmp_path,POLICY,config=settings)
    frames(live,2)
    until(lambda:live.target_blocked)
    feed_fixture_windows(live,45,start=2)
    until(lambda:live.finalized>=3)
    assert live.latest['identity_continuity']=='NO_OBSERVATIONS'
    assert live.latest['diagnostic']['code']=='SAM_NO_MASKS'
    assert live.ledger.snapshot()['attempted_requests']=={'sam':1,'muse':0}
    with pytest.raises(AuthorizationError):live.reselect_target('blue circular weight',True,False)
    with pytest.raises(ValueError,match='Revise'):live.reselect_target(settings.target_prompt,True,True)
    transport.empty=False
    live.reselect_target('blue circular weight',True,True)
    frames(live,3,start=50)
    until(lambda:live.pending_action is not None)
    assert sum(r['input'][0]['content'][1]['type']=='input_image' for r in transport.requests)==2
    assert live.ledger.snapshot()['attempted_requests']['sam']==len(transport.dispatches)
    manifest=json.loads((live.root/'startup-0001/manifest.json').read_text())
    assert manifest['target_prompt']=='blue circular weight'
    assert live.startup_result['receipt']['prompt']==manifest['target_prompt']
    assert live.ledger.policy==POLICY


def test_pause_and_revoke_preserve_capture_and_budget_and_refuse_further_calls(auto_factory,tmp_path):
    factory,transport,settings=auto_factory(AutoMeta(partial_hold=True))
    live=factory(tmp_path,POLICY,config=settings)
    frames(live,2)
    until(lambda:live.overlay is not None)
    live.pause();count=live.ledger.snapshot()['total_requests']
    transport.partial_hold.clear();frames(live,30,start=2)
    time.sleep(.1)
    assert live.ledger.snapshot()['total_requests']==count
    assert live.latest is None
    live.resume()
    frames(live,16,start=40)
    until(lambda:live.processed>=1)
    assert live.ledger.policy==POLICY
    live.stop();count=live.ledger.snapshot()['total_requests']
    frames(live,20,start=70);time.sleep(.1)
    assert live.ledger.snapshot()['total_requests']==count
    with pytest.raises(ValueError):live.resume()


def test_startup_source_and_consumed_result_are_verified_read_only(auto_factory,tmp_path,monkeypatch):
    from realign.physical import live_forensics as module
    from realign.perception.sam_client import SamRun
    from realign.perception.video import file_sha256
    factory,transport,settings=auto_factory(AutoMeta(empty=True))
    live=factory(tmp_path,POLICY,config=settings)
    frames(live,2);until(lambda:live.target_blocked);live.close()
    def fixture_cache(path,meta):
        # Only this explicit test boundary accepts a fixture; the real forensic
        # loader and physical admission still reject non-REAL_API receipts.
        index=json.loads(path.with_suffix('.json').read_text())
        assert index['source']=='SIMULATED_API_FIXTURE'
        return SamRun((),'SIMULATED_API_FIXTURE',meta.video_sha256,index['receipt'])
    monkeypatch.setattr(module,'load_sam_cache',fixture_cache)
    before={p:file_sha256(p) for p in live.root.rglob('*') if p.is_file()}
    report=module.inspect_session(live.root)
    assert report['windows'][0]['media_kind']=='image'
    assert report['windows'][0]['replay_valid_frames']==0
    assert report['new_meta_requests']==0
    assert all(file_sha256(p)==sha for p,sha in before.items())
    result=live.root/'startup-0000/result.json'
    result.write_text('{}')
    with pytest.raises(ValueError,match='CONSUMED_RESULT_CHANGED'):module.inspect_session(live.root)


def test_material_pixel_change_is_a_source_scoped_cue_without_physical_time():
    from realign.physical.live_observation import summarize_pixel_motion, material_pixel_change
    def samples(points,recording='TEST_FIXTURE'):
        return summarize_pixel_motion([{'xy_px':p,'capture_sequence':i,'recording_id':recording,
            'processed_size':[96,64],'arrival_monotonic_ns':1_000_000_000+i*100_000_000} for i,p in enumerate(points)])
    a=samples([[20,20],[24,20],[28,20]])
    b=samples([[28,20],[28,24],[28,28]])
    assert material_pixel_change(a,b)
    assert not material_pixel_change(a,samples([[20,20],[24,20],[28,20]],'OTHER_SOURCE'))
    assert not material_pixel_change(a,a)
    assert 'UNVERIFIED_TIMING' in a['scope'] and 'velocity' not in a
    large=samples([[i,i] for i in range(100)])
    assert len(large['source_samples'])==32 and large['source_samples'][-1]['xy_px']==[99.,99.]


def test_new_material_change_automatically_reasons_below_regular_sample_threshold(auto_factory,tmp_path):
    from realign.agent.adapters import AdapterFailure
    from test_live_investigation import eligible_snapshot
    class Broken(ScriptedAdapter):
        def next(self,context):
            self.contexts.append(context)
            self.before_request('muse','reasoning')
            raise AdapterFailure('TEST_FIXTURE protocol rejection',code='INVALID_STRUCTURED_RESPONSE')
    factory,transport,settings=auto_factory()
    live=factory(tmp_path,POLICY,config=settings)
    science=LiveScientificSession(live,adapter_factory=Broken)
    with pytest.raises(AdapterFailure):science.consume('observation',eligible_snapshot())
    science.last_reasoning-=3
    plain={**eligible_snapshot('small-update',2),'identity_continuity':'OVERLAP_AGREEMENT'}
    science.consume('observation',plain)
    assert live.ledger.snapshot()['attempted_requests']['muse']==1
    changed={**eligible_snapshot('changed',3),'identity_continuity':'OVERLAP_AGREEMENT','behavior_changed':True}
    with pytest.raises(AdapterFailure):science.consume('observation',changed)
    assert live.ledger.snapshot()['attempted_requests']['muse']==2
    assert science.adapter.contexts[-1]['live_observation']['pixel_motion']['source_samples'][0]['xy_px']==[28.,28.]
    science.close()

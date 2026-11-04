"""TEST_FIXTURE only: injected frames, mocked Meta transport, real MP4/parser.

No camera is opened and no request leaves this process. These results establish
software concurrency and integrity, never physical G2/G5 or hosted throughput.
"""
import asyncio
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import json
from pathlib import Path
import threading
import time
from types import SimpleNamespace as NS

import numpy as np
import pytest

from realign.agent.adapters import MuseAdapter
from realign.audit.chain import AuditChain
from realign.contracts.investigation import AdapterReply, AgentTurn, Budget, Hypothesis
from realign.perception.sam_client import SamClient, SamError
from realign.physical.live_investigation import LiveConfig, LiveInvestigation, RequestLedger, AuthorizationError, inspect_interrupted
from realign.physical.live_science import LiveScientificSession, verify_window_timing
from realign.synth.video_fixture import fixture_events, protocol_line


POLICY = {'consent': True, 'standard_tier_confirmed': True, 'sam_requests': 32, 'muse_requests': 8,
          'ceiling_usd': '1', 'sam_reserve_usd': '.01', 'muse_reserve_usd': '.02'}


def until(check, timeout=15):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if check(): return
        time.sleep(.01)
    raise AssertionError('deterministic worker did not reach expected condition')


class NoReasoning:
    def __init__(self, live): self.live = live
    def consume(self, kind, value): self.live.record('TEST_FIXTURE_SNAPSHOT', {'kind': kind})
    def close(self): pass


class MockStream:
    def __init__(self, events, transport): self.events, self.transport = events, transport
    async def __aenter__(self): return self
    async def __aexit__(self, *args): pass
    async def __aiter__(self):
        for event in self.events:
            while self.transport.hold.is_set(): await asyncio.sleep(.01)
            yield event


class MockMeta:
    def __init__(self, *, fail_upload=False, failure=None, object_id='0'):
        self.files = NS(create=self.upload)
        self.responses = NS(create=self.respond)
        self.hold = threading.Event()
        self.entered = threading.Event()
        self.fail_upload, self.failure, self.object_id = fail_upload, failure, object_id
        self.dispatches = []
    async def upload(self, **kwargs):
        self.dispatches.append('upload')
        if self.fail_upload: raise OSError('TEST_FIXTURE_UPLOAD_FAILURE')
        return NS(id='file-TEST_FIXTURE')
    async def respond(self, **kwargs):
        self.dispatches.append('segmentation')
        self.entered.set()
        events = fixture_events(text=''.join(protocol_line(i, 20, 20, width=96, height=64, object_id=self.object_id)
                              for i in range(self.frame_count)), failure=self.failure)
        return MockStream(events, self)
    async def close(self): pass


@pytest.fixture
def live_factory(tmp_path):
    sessions = []
    def build(transport=None, config=None, reasoner_factory=NoReasoning):
        transport = transport or MockMeta()
        holder = {}
        class Client(SamClient):
            async def segment_video(self, path, metadata):
                transport.frame_count = len(metadata.pts)
                return await super().segment_video(path, metadata)
        def client():
            return Client(transport, source='SIMULATED_API_FIXTURE', retry_delay=0,
                          before_request=holder['live'].ledger.reserve, max_attempts=2, concept=holder['live'].config.target_prompt)
        live = LiveInvestigation(tmp_path, deepcopy(POLICY), config=config, source='TEST_FIXTURE',
                                sam_factory=client, reasoner_factory=reasoner_factory)
        holder['live'] = live
        sessions.append(live)
        return live, transport
    yield build
    for live in sessions: live.close()


def frames(live, count, *, start=0, recording='clip-TEST_FIXTURE', pause=.002):
    for i in range(start, start + count):
        frame = np.full((64, 96, 3), 80 + i % 64, dtype=np.uint8)
        live.offer(frame, {'recording_id': recording, 'encoded_frame_index': i,
            'capture_sequence': i, 'arrival_monotonic_ns': 1_000_000_000 + i * 100_000_000})
        if pause: time.sleep(pause)


def test_authorization_caps_are_atomic_and_stop_never_refunds_failed_attempts():
    events = []
    ledger = RequestLedger({**POLICY, 'ceiling_usd': '.05'}, lambda *e: events.append(e))
    def attempt(_):
        try: ledger.reserve('sam', 'upload'); return True
        except AuthorizationError: return False
    with ThreadPoolExecutor(max_workers=8) as pool: assert sum(pool.map(attempt, range(40))) == 5
    assert ledger.snapshot()['total_requests'] == 5
    assert ledger.snapshot()['reserved_usd'] == '0.05'
    ledger.stop()
    with pytest.raises(AuthorizationError): ledger.reserve('muse', 'reasoning')
    assert len(events) == 5


@pytest.mark.parametrize('patch', [{'consent': False}, {'standard_tier_confirmed': False},
    {'sam_requests': 1000}, {'ceiling_usd': 'NaN'}, {'muse_reserve_usd': 0}, {'extra': True}])
def test_invalid_authorization_cannot_start_workers(patch):
    with pytest.raises(AuthorizationError): RequestLedger({**POLICY, **patch}, lambda *a: None)


def test_four_second_overlapping_windows_under_slow_sam_keep_accepting_frames(live_factory):
    transport = MockMeta(); transport.hold.set()
    live, _ = live_factory(transport)
    frames(live, 43)
    until(transport.entered.is_set)
    before = live.finalized
    # SAM is still blocked, yet encoding/capture continue on independent workers.
    frames(live, 90, start=43)
    until(lambda: live.finalized > before)
    assert live.processed == 0
    assert live.frames.qsize() <= live.config.frame_queue
    transport.hold.clear()
    until(lambda: live.processed >= 2)
    manifests = [json.loads(p.read_text()) for p in sorted(live.root.glob('window-*/manifest.json'))]
    assert manifests[0]['frames'][-1]['arrival_monotonic_ns'] - manifests[0]['frames'][0]['arrival_monotonic_ns'] >= 4e9
    keys = lambda m: {r['capture_sequence'] for r in m['frames']}
    assert keys(manifests[0]) & keys(manifests[1])
    assert live.latest['complete_validated_track'] is False
    assert live.latest['physical_fitting_allowed'] is False
    assert live.latest['latency_s'] >= 0
    assert live.ledger.snapshot()['total_requests'] == len(transport.dispatches)
    assert 'TEST_FIXTURE' in (live.root / 'timeline.jsonl').read_text()


def test_queue_saturation_stop_cancellation_and_no_calls_after_stop(live_factory):
    transport = MockMeta(); transport.hold.set()
    live, _ = live_factory(transport, LiveConfig(window_s=1., overlap_s=.2, window_queue=1))
    frames(live, 12)
    until(transport.entered.is_set)
    frames(live, 12, start=12)
    until(lambda: live.finalized >= 2 and live.windows.qsize() == 1)
    frames(live, 12, start=24)
    until(lambda: live.dropped['windows'] > 0)
    count = live.ledger.snapshot()['total_requests']
    live.stop()
    transport.hold.clear()
    frames(live, 50, start=80)
    until(lambda: not live.threads[1].is_alive())
    assert live.ledger.snapshot()['total_requests'] == count
    assert live.latest is None
    assert list(live.root.glob('window-*/result.json'))


@pytest.mark.parametrize('failure', ['upload', 'incomplete', 'eof', 'empty'])
def test_failed_upload_partial_empty_stream_preserved_without_valid_track(live_factory, failure):
    transport = MockMeta(fail_upload=failure == 'upload', failure=None if failure in ('upload', 'empty') else failure)
    if failure == 'empty':
        async def empty(**kwargs):
            transport.dispatches.append('segmentation')
            return MockStream(fixture_events(frames=[]), transport)
        transport.responses.create = empty
    live, _ = live_factory(transport, LiveConfig(window_s=1., overlap_s=.2))
    frames(live, 12)
    until(lambda: list(live.root.glob('window-*/result.json')))
    result = json.loads(next(live.root.glob('window-*/result.json')).read_text())
    assert result['status'] in ('FAILED', 'EMPTY_OR_QUARANTINED')
    assert result['complete_validated_track'] is False
    assert not live.trajectory
    assert live.ledger.snapshot()['total_requests'] == len(transport.dispatches)
    assert not live.cancel.is_set()


def test_overlap_dedup_keeps_consumed_coordinates_and_flags_id_discontinuity(live_factory):
    live, transport = live_factory(config=LiveConfig(window_s=1., overlap_s=.3))
    frames(live, 12)
    until(lambda: live.processed == 1)
    original = deepcopy(live.trajectory)
    transport.object_id = '1'
    frames(live, 10, start=12)
    until(lambda: live.processed >= 2)
    assert live.latest['identity_continuity'] == 'UNVERIFIED_OR_DISCONTINUOUS'
    assert live.latest['new_observations'] < len(live.latest['rows'])
    assert all(live.trajectory[k] == row for k, row in original.items())
    manifests = [json.loads(p.read_text()) for p in live.root.glob('window-*/manifest.json')]
    assert all(m['capture_time_scale_verified'] is False for m in manifests)
    assert all('window_pts' in r and 'processed_frame_sha256' in r for m in manifests for r in m['frames'])


def test_timeout_is_a_preserved_failure_and_capture_can_continue(live_factory):
    transport = MockMeta(); transport.hold.set()
    live, _ = live_factory(transport, LiveConfig(window_s=1., overlap_s=.2, timeout_s=1.))
    frames(live, 12)
    until(lambda: list(live.root.glob('window-*/result.json')))
    result = json.loads(next(live.root.glob('window-*/result.json')).read_text())
    assert result['code'] == 'TimeoutError'
    assert not live.cancel.is_set()


def test_interrupted_journal_recovery_is_offline_and_tampering_is_rejected(live_factory):
    live, _ = live_factory()
    live.ledger.reserve('sam', 'upload')
    recovered = inspect_interrupted(live.root.parent)[0]
    assert recovered['state'] == 'INTERRUPTED' and recovered['reserved_attempts'] == 1
    assert recovered['automatic_calls'] == 0
    events = [json.loads(x) for x in (live.root / 'timeline.jsonl').read_text().splitlines()]
    assert AuditChain.verify(events)
    events[0]['payload']['source'] = 'REAL_PHONE'
    (live.root / 'timeline.jsonl').write_text('\n'.join(json.dumps(e) for e in events))
    assert inspect_interrupted(live.root.parent)[0]['state'] == 'AUDIT_UNAVAILABLE'


class ScriptedAdapter:
    source = 'SIMULATED_API_FIXTURE'
    def __init__(self, budget): self.contexts = []; self.before_request = None
    def next(self, context):
        self.contexts.append(deepcopy(context))
        self.before_request('muse', 'reasoning')
        action = 'HYPOTHESIZE' if context['stage'] == 'HYPOTHESIZE' else 'REQUEST_EVIDENCE'
        return AdapterReply(turn=AgentTurn(action=action,
            hypotheses=(Hypothesis(family='MEASUREMENT', status='UNRESOLVED', evidence_refs=()),),
            experiment_ref=context['candidates'][0]['experiment_ref'] if action == 'REQUEST_EVIDENCE' else None,
            outcome=None, model_ref=None, evidence_refs=tuple(context['evidence_refs']), reasons=()))
    def close(self): pass


def eligible_snapshot(window='window-TEST_FIXTURE', sequence=1):
    return {'source': 'TEST_FIXTURE', 'window_id': window, 'new_observations': 1,
        'cumulative_unique_observations': sequence, 'identity_continuity': 'FIRST_WINDOW_UNVERIFIED',
        'track': {'valid_frames': 1}, 'rows': [{'capture_sequence': sequence, 'xy_px': [28., 28.]}],
        'diagnostic': {'code': 'PRELIMINARY_PIXELS_ONLY', 'guidance': 'TEST_FIXTURE observation; calibration still required.'}}


def test_live_muse_requests_exact_operator_action_and_cannot_fit_pixels(live_factory, tmp_path):
    live, _ = live_factory(reasoner_factory=NoReasoning)
    science = LiveScientificSession(live, adapter_factory=ScriptedAdapter)
    science.consume('observation', eligible_snapshot())
    pending = live.pending_action
    assert pending['candidate']['action']['kind'] == 'STATIONARY_REFERENCE'
    assert live.scientific['state'] == 'PENDING_PHYSICAL_ACTION'
    assert science.agent is None
    with pytest.raises(ValueError): live.confirm_action('wrong')
    live.confirm_action(pending['request_id'])
    frames(live, 2)
    live.boundary('TEST_FIXTURE_STOP')
    until(lambda: live.finalized == 1)
    until(lambda: list(live.root.glob('window-*/manifest.json')))
    manifest = json.loads(next(live.root.glob('window-*/manifest.json')).read_text())
    assert all(r['response_to_request_id'] == pending['request_id'] for r in manifest['frames'])
    # Confirming an action never bypasses calibration admission or resets budget.
    path = tmp_path / 'missing-calibration.json'; path.write_text('{"source_kind":"REAL_PHONE"}')
    science.consume('admit', {'manifest': str(path)})
    assert science.agent is None and live.pending_action['request_id'] == pending['request_id']
    assert live.ledger.snapshot()['attempted_requests']['muse'] == 2
    assert 'INDEPENDENT_CAPTURE_TIMING_REFERENCE_REQUIRED' in live.scientific['blockers']
    science.close()


def test_sam_and_muse_guards_count_every_retry_and_prevent_sdk_dispatch(tmp_path):
    # SAM's real SDK boundary is also exercised by all MockMeta pipeline tests.
    ledger = RequestLedger({**POLICY, 'muse_requests': 1}, lambda *a: None)
    dispatched = []
    def failure(**kwargs): dispatched.append(1); raise OSError('TEST_FIXTURE')
    sdk = NS(chat=NS(completions=NS(create=failure)))
    adapter = MuseAdapter(sdk, budget=Budget(), before_request=ledger.reserve)
    with pytest.raises(OSError): adapter._request()
    with pytest.raises(AuthorizationError): adapter._request()
    assert len(dispatched) == 1
    assert ledger.snapshot()['attempted_requests']['muse'] == 1
    assert adapter.stats['actual_api_requests'] == 1


def test_known_admitted_observations_enter_existing_tools_in_same_live_session(live_factory, monkeypatch):
    """TEST_FIXTURE ingestion boundary; actual deterministic registry, no network.

    Real admission itself is independently exercised by test_physical_investigation.
    """
    from test_physical_investigation import video_fixture
    from realign.tools.registry import ToolRegistry
    from realign.contracts.investigation import ToolCall
    from realign.audit.chain import canonical
    from realign.synth.investigation_fixtures import NOMINAL
    from dataclasses import asdict, replace
    import realign.physical.live_science as module
    trials = [video_fixture('a' * 64), video_fixture('b' * 64)]
    trials[1] = replace(trials[1], observation=replace(trials[1].observation, xy_px=trials[1].observation.xy_px + [4., 0.]))
    config = {'nominal_params': asdict(NOMINAL)}
    ingestions = []
    async def admitted(*args, **kwargs):
        ingestions.append(1)
        return {'status': 'READY', 'trials': trials, 'checks': {'source': 'REAL_MEASURED'},
            'config': config, 'windows': {}, 'sam_receipts': {}, 'input_manifest_sha256': 'c' * 64,
            'calibration_grade': 'TEST_FIXTURE', 'perception': {'stationary_reference': {'metadata': {'video_sha256': ('d' if len(ingestions) == 1 else 'e') * 64}}}}
    monkeypatch.setattr(module, 'ingest_phone', admitted)
    class FixtureWorker:
        isolation = 'TEST_FIXTURE_IN_PROCESS_ONLY'; probe = {}
        def __init__(self, **kwargs): pass
        def request(self, value):
            if value['command'] == 'reset':
                self.registry = ToolRegistry(value['records'], value['nominal'], budget=Budget(), checks=value['checks'], gate=None)
                r = self.registry
                return {'nominal_model_ref': r.nominal_ref, 'trial_refs': list(r.trial_refs),
                    'budget_ref': r.budget_ref, 'protocol_ref': r.protocol_ref, 'checks_ref': r.checks_ref}
            if value['command'] == 'candidates': self.registry.register_candidates(value['candidates']); return {}
            if value['command'] == 'audit': return {'events': self.registry.audit.events, 'head': self.registry.audit.head}
            if value['command'] == 'admit':
                self.registry.admit(value['records'], value['checks'])
                return {'trial_refs': list(self.registry.trial_refs), 'checks_ref': self.registry.checks_ref}
            raise AssertionError('Unexpected fixture command')
        def call(self, name, arguments): return self.registry.dispatch(name, arguments)
        def close(self): pass
    live, _ = live_factory()
    science = LiveScientificSession(live, adapter_factory=ScriptedAdapter, worker_factory=FixtureWorker)
    science._admit({'manifest': 'TEST_FIXTURE.json'})
    assert science.agent.session.discrepancy is not None
    assert science.agent.machine.stage == 'HYPOTHESIZE'
    assert live.scientific['physical_evidence_accepted'] is True
    assert live.scientific['trajectory_comparison']['scope'].startswith('ADMITTED_EXPLORATION')
    # Approved references belong to the unchanged existing scientific kernel.
    context = science._context()
    assert context['trial_refs'] == science.agent.session.trial_refs
    assert len(context['trial_refs']) == 2 and context['evidence_refs']
    original_agent = science.agent
    with pytest.raises(ValueError, match='approved experiment'):
        science._admit({'manifest': 'TEST_FIXTURE.json'})
    assert science.agent is original_agent
    # Resume the SAME numerical session through the original physical admission
    # contract, preserving its validated transition history and one-action budget.
    from realign.contracts.investigation import CameraCheck
    from realign.tools.client import candidate
    selected = candidate(CameraCheck(reference_ref=science.agent.session.checks_ref)).model_dump(mode='json')
    env = science.agent.environment
    assert env.perform(selected) is None
    live.pending_action = deepcopy(env.pending_action)
    live.confirm_action(live.pending_action['request_id'])
    config['response_to_request_id'] = live.pending_action['request_id']
    science.agent.machine.move('TEST'); science.agent.machine.move('REQUEST_EVIDENCE')
    science.experiments = science.agent.experiments = 1
    science._admit({'manifest': 'TEST_FIXTURE_RESPONSE.json'})
    assert science.agent is original_agent and science.agent.round == 2
    assert science.agent.experiments == 1
    assert env.admission_history == ['REQUESTED', 'AWAITING_RECORDING', 'VALIDATING', 'ADMITTED']
    assert live.pending_action is None and live.history[-1]['state'] == 'ADMITTED'
    assert live.scientific['physical_evidence_accepted'] is True
    science.close()


def test_software_cfr_cannot_establish_physical_time_from_arrivals_or_fps():
    from realign.audit.chain import digest
    trial = NS(observation=NS(metadata=NS(video_sha256='a' * 64)))
    window = {'frames': [{'capture_sequence': i, 'window_pts': i * 100, 'window_time_base': '1/1000'} for i in range(10)]}
    measured = {'source': 'INDEPENDENT_EXPOSURE_MEASUREMENT', 'instrument': 'TEST_FIXTURE_REFERENCE_CLOCK',
        'independent_of_encoded_fps': True, 'video_sha256': 'a' * 64, 'window_manifest_sha256': digest(window),
        'uncertainty_s': .001, 'frames': [{'capture_sequence': i, 'exposure_time_s': 10 + i * .1} for i in range(10)]}
    assert verify_window_timing(trial, window, measured)['reference_sha256'] == digest(measured)
    for source in ('HOST_MONOTONIC_ARRIVAL', 'NOMINAL_FPS'):
        with pytest.raises(ValueError): verify_window_timing(trial, window, {**measured, 'source': source})
    mismatch = deepcopy(measured)
    mismatch['frames'] = [{'capture_sequence': i, 'exposure_time_s': 10 + i * .04} for i in range(10)]
    with pytest.raises(ValueError, match='TIMEBASE_MISMATCH'): verify_window_timing(trial, window, mismatch)
    with pytest.raises(ValueError): verify_window_timing(trial, window, {**measured, 'window_manifest_sha256': 'b' * 64})


def test_actual_capture_controller_keeps_recording_under_slow_sam_and_disconnect_stops_ai(live_factory, tmp_path):
    from test_live_lab import Camera
    from realign.physical.live_lab import CaptureController, LabLibrary
    camera = Camera()
    camera.frames = [np.full((64, 96, 3), 80, np.uint8) for _ in range(100)]
    controller = CaptureController(LabLibrary(tmp_path / 'TEST_FIXTURE_CAPTURE'), camera_factory=lambda *a: camera)
    transport = MockMeta(); transport.hold.set()
    live, _ = live_factory(transport)
    controller.connect(0, threaded=False)
    controller.live = live
    folder = controller.start(operator='TEST_FIXTURE')
    try:
        for i in range(43): controller.read_once(arrival_ns=1_000_000_000 + i * 100_000_000)
        until(transport.entered.is_set)
        for i in range(43, 65): controller.read_once(arrival_ns=1_000_000_000 + i * 100_000_000)
        assert len(controller.arrivals) == 65 and live.processed == 0
        camera.frames.clear()
        controller.read_once()
        assert controller.state == 'FAILED' and live.cancel.is_set()
        report = json.loads((folder / 'report.json').read_text())
        assert 'ENCODED_ARRIVAL_TIMEBASE_MISMATCH' in report['blockers']
        assert report['physical_evidence_accepted'] is False
        assert report['media']['decoded_frames'] == 65
    finally:
        transport.hold.clear()
        controller.close()


def test_muse_result_arriving_after_stop_cannot_change_hypotheses_or_request_action(live_factory):
    entered, release = threading.Event(), threading.Event()
    class HeldAdapter(ScriptedAdapter):
        def next(self, context):
            reply = super().next(context)
            entered.set(); release.wait(timeout=5)
            return reply
    live, _ = live_factory()
    science = LiveScientificSession(live, adapter_factory=HeldAdapter)
    thread = threading.Thread(target=lambda: science.consume('observation', eligible_snapshot()))
    thread.start()
    assert entered.wait(timeout=5)
    live.stop(); release.set(); thread.join(timeout=5)
    assert not thread.is_alive()
    assert live.pending_action is None and live.scientific['hypotheses'] == []
    assert live.ledger.snapshot()['attempted_requests']['muse'] == 1
    assert any(e['kind'] == 'MUSE_RESULT_AFTER_STOP' for e in live.audit.events)
    assert inspect_interrupted(live.root.parent)[0]['state'] == 'STOPPED'
    science.close()

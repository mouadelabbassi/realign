"""Continuous Live and terminal telemetry: injected inputs only, no paid calls."""
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
import json
import logging
from types import SimpleNamespace as NS

import numpy as np
import pytest

from realign.agent.adapters import MuseAdapter, NotAuthorized
from realign.audit.chain import AuditChain
from realign.audit.terminal import emit
from realign.contracts.investigation import Budget
from realign.physical.live_investigation import AuthorizationError, RequestLedger
from realign.physical.live_lab import CaptureController, LabLibrary
from test_auto_live import auto_factory, AutoMeta
from test_live_investigation import POLICY, until
from test_live_lab import Camera


def policy(**patch):
    return {**POLICY, 'sam_requests': None, 'muse_requests': None, **patch}


def test_continuous_spending_gate_has_no_request_count_cutoff_and_is_atomic():
    events = []
    ledger = RequestLedger(policy(ceiling_usd='0.80'), lambda *e: events.append(e), continuous=True)
    def attempt(_):
        try: ledger.reserve('sam', 'upload'); return True
        except AuthorizationError: return False
    with ThreadPoolExecutor(max_workers=8) as pool:
        assert sum(pool.map(attempt, range(100))) == 80
    assert len(events) == 80
    assert ledger.snapshot()['spending_cap_reached']
    assert ledger.snapshot()['reserved_usd'] == '0.80'
    assert ledger.snapshot()['remaining_reserve_usd'] == '0.00'
    with pytest.raises(AuthorizationError): ledger.reserve('muse', 'reasoning')
    with pytest.raises(AuthorizationError): RequestLedger(policy(), lambda *e: None)


def test_continuous_muse_uses_session_gate_and_retains_bounded_receipts():
    calls = []
    client = NS(chat=NS(completions=NS(create=lambda **kw: calls.append(kw) or NS())))
    adapter = MuseAdapter(client, budget=Budget(max_api_requests=1), source='SIMULATED_API_FIXTURE')
    adapter.external_request_gate = True
    with pytest.raises(NotAuthorized): adapter._request()
    assert not calls
    ledger = RequestLedger(policy(ceiling_usd='1.70'), lambda *e: None, continuous=True)
    adapter.before_request = ledger.reserve
    for _ in range(85): adapter._request()
    assert len(calls) == 85 and len(adapter.receipts) == 80
    with pytest.raises(AuthorizationError): adapter._request()
    assert len(calls) == 85 and adapter.stats['fixture_requests'] == 85


def test_continuous_journal_retains_full_verified_chain_with_bounded_memory(auto_factory, tmp_path):
    factory, _, config = auto_factory()
    live = factory(tmp_path, policy(), config=replace(config, continuous=True))
    for i in range(150): live.record('TEST_FIXTURE_EVENT', {'step': i})
    events = [json.loads(line) for line in (live.root / 'timeline.jsonl').read_text(encoding='utf-8').splitlines()]
    assert len(events) == 151 and AuditChain.verify(events)
    assert len(live.audit.events) == 80 and len(live.snapshot()['events']) == 80
    assert live.audit.head == events[-1]['hash']
    assert live.upload_index is not None
    live.close()
    assert live.upload_index is None


def test_continuous_windows_ignore_session_window_cutoff_but_deduplicate_uploads(auto_factory, tmp_path):
    factory, transport, config = auto_factory(AutoMeta(partial_hold=True))
    live = factory(tmp_path, policy(), config=replace(config, continuous=True, max_windows=1))
    image = np.full((64, 96, 3), 80, dtype=np.uint8)
    row = {'recording_id': 'clip-TEST_FIXTURE', 'encoded_frame_index': 0,
           'capture_sequence': 0, 'arrival_monotonic_ns': 1_000_000_000}
    buffer = [(image, row), (image, {**row, 'capture_sequence': 1,
              'encoded_frame_index': 1, 'arrival_monotonic_ns': 1_100_000_000})]
    live._finalize(buffer, partial=True)
    until(lambda: live.sam_active_window is not None)
    live._finalize(buffer, partial=True)
    assert live.finalized == 2
    assert live.skipped['DUPLICATE_CONTENT_AND_PROMPT'] == 1
    assert live.upload_index.execute('SELECT COUNT(*) FROM submitted').fetchone()[0] == 1
    transport.partial_hold.clear()


def test_go_live_connects_once_and_keeps_rotating_after_sixteen_source_clips(auto_factory, tmp_path, monkeypatch):
    factory, transport, config = auto_factory(AutoMeta(partial_hold=True))
    camera = Camera()
    owner = CaptureController(LabLibrary(tmp_path / 'TEST_FIXTURE'), camera_factory=lambda *a: camera, live_factory=factory)
    connect = owner.connect
    monkeypatch.setattr(owner, 'connect', lambda index: connect(index, threaded=False))
    try:
        assert owner.live is None and not transport.dispatches
        state = owner.go_live(POLICY, config.__dict__, index=2)
        assert state['state'] == 'RECORDING' and owner.device['index'] == 2
        assert owner.live.config.continuous and owner.auto_capture
        assert owner.live.ledger.policy['sam_requests'] is None
        owner.auto_clips = 16
        owner.read_once(arrival_ns=1_000_000_000)
        first = owner.recording
        owner.read_once(arrival_ns=57_000_000_000)
        assert owner.auto_clips == 17 and owner.recording != first
        assert owner.writer is not None and owner.auto_capture
        assert (first / 'recording.mp4').is_file()
    finally: owner.close()


def test_terminal_logs_report_safe_diagnostics_without_raw_contents(caplog):
    with caplog.at_level(logging.INFO, logger='realign.live'):
        emit('SAM_HTTP_FAILED', model='sam-3.1', operation='segment', http_status=429,
             error_type='APIStatusError', api_key='SENSITIVE_TEST_FIXTURE',
             body='SENSITIVE_TEST_FIXTURE', target_prompt='SENSITIVE_TEST_FIXTURE',
             reply={'raw': 'SENSITIVE_TEST_FIXTURE'})
    assert 'SAM_HTTP_FAILED' in caplog.text and '429' in caplog.text
    assert 'SENSITIVE_TEST_FIXTURE' not in caplog.text
    assert 'APIStatusError' in caplog.text


def test_muse_failure_logs_exception_type_without_exception_body(caplog):
    def fail(**kwargs): raise RuntimeError('SENSITIVE_TEST_FIXTURE_RESPONSE_BODY')
    adapter = MuseAdapter(NS(chat=NS(completions=NS(create=fail))), budget=Budget(), source='SIMULATED_API_FIXTURE')
    with caplog.at_level(logging.INFO, logger='realign.live'):
        with pytest.raises(RuntimeError): adapter._request()
    assert 'MUSE_HTTP_STARTED' in caplog.text and 'MUSE_HTTP_FAILED' in caplog.text
    assert 'RuntimeError' in caplog.text and 'SENSITIVE_TEST_FIXTURE' not in caplog.text

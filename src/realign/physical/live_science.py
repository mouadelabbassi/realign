"""Incremental scheduling around the existing single Muse/scientific runtime.

Pixel snapshots never become numerical trials. Only ingest_phone's independent
admission can grant references to the bounded numerical tools.
"""
from copy import deepcopy
import asyncio
import time
import uuid

from realign.agent.adapters import MuseAdapter
from realign.agent.investigator import Investigator
from realign.audit.chain import canonical, digest
from realign.audit.exposure import assert_public_context
from realign.contracts.investigation import Budget, CameraCheck, Stationary, TOOLS
from realign.perception.meta_validation import strict_json
from realign.physics import PendulumParams
from realign.tools.client import ScientificSession, candidate
from realign.tools.sandbox import WorkerClient
from .ingestion import ingest_phone
from .session import PhysicalEnvironment, PhysicalValidator


class ScientificGateRejection(ValueError):
    def __init__(self,message,*,code):
        super().__init__(message)
        self.code=code


def verify_window_timing(trial, window, reference):
    """Independent exposure samples must agree with playback, within their error.

    This is an admission check, not a replacement clock inferred from FPS or
    camera arrival. Mismatched software CFR windows remain pixel-only.
    """
    import numpy as np
    rows = reference.get('frames', [])
    sigma = reference.get('uncertainty_s')
    if (reference.get('source') != 'INDEPENDENT_EXPOSURE_MEASUREMENT' or
            reference.get('independent_of_encoded_fps') is not True or
            reference.get('video_sha256') != trial.observation.metadata.video_sha256 or
            reference.get('window_manifest_sha256') != digest(window) or
            not reference.get('instrument') or type(sigma) not in (float, int) or
            not np.isfinite(sigma) or sigma <= 0 or len(rows) != len(window['frames'])):
        raise ValueError('INDEPENDENT_HASH_BOUND_EXPOSURE_TIMELINE_REQUIRED')
    if [r.get('capture_sequence') for r in rows] != [r['capture_sequence'] for r in window['frames']]:
        raise ValueError('EXPOSURE_SOURCE_FRAME_MAPPING_MISMATCH')
    measured = np.asarray([r.get('exposure_time_s') for r in rows], dtype=float)
    if not np.isfinite(measured).all() or np.any(np.diff(measured) <= 0) or sigma > np.min(np.diff(measured)) / 10:
        raise ValueError('EXPOSURE_TIMING_UNCERTAINTY_OR_ORDER_INVALID')
    # analysis_window preserves absolute integer PTS, including a nonzero origin.
    from fractions import Fraction
    encoded = np.array([r['window_pts'] for r in window['frames']]) * float(Fraction(window['frames'][0]['window_time_base']))
    if np.max(np.abs((measured - measured[0]) - (encoded - encoded[0]))) > 2 * sigma:
        raise ValueError('ENCODED_EXPOSURE_TIMEBASE_MISMATCH')
    return {'video_sha256': reference['video_sha256'], 'reference_sha256': digest(reference),
            'window_manifest_sha256': digest(window), 'uncertainty_s': sigma}


class LiveScientificSession:
    def __init__(self, live, *, adapter_factory=None, worker_factory=None):
        self.live = live
        self.budget = Budget(max_api_requests=live.ledger.policy['muse_requests'])
        self.adapter_factory = adapter_factory
        self.worker_factory = worker_factory or WorkerClient
        self.adapter = None
        self.worker = None
        self.agent = None
        self.seen = set()
        self.new_points = 0
        self.last_reasoning = -float('inf')
        self.stage = 'HYPOTHESIZE'
        self.steps = 0
        self.experiments = 0
        self.terminal = False
        self.snapshot = None
        self.latest_diagnostic = None
        self.consumed_unique = 0
        self.last_reasoning_basis = None
        self.admission_ref = None
        self.pixel_candidates = [candidate(Stationary()).model_dump(mode='json'),
            candidate(CameraCheck(reference_ref=digest({'live_session': live.root.name}))).model_dump(mode='json')]

    def consume(self, kind, value):
        if self.terminal or self.live.cancel.is_set(): return
        if kind == 'admit':
            self._admit(value)
        elif kind == 'observation':
            ref = digest(value)
            if ref in self.seen: return
            self.seen.add(ref)
            self.latest_diagnostic = value.get('diagnostic')
            total = value.get('cumulative_unique_observations', self.consumed_unique+value['new_observations'])
            self.new_points += max(0, total-self.consumed_unique)
            self.consumed_unique = max(self.consumed_unique, total)
            if not value['track']['valid_frames'] or not value['rows']:
                self._readiness('NO_USABLE_OBSERVATIONS')
                return
            if not value['new_observations']:
                self._readiness('NO_NEW_ELIGIBLE_EVIDENCE')
                return
            first_detection = self.snapshot is None
            self.snapshot = {'snapshot_sha256': ref, 'source': self.live.source,
                'observation_grade': 'PRELIMINARY_PIXELS', 'units': 'px',
                'window_id': value['window_id'], 'valid_samples': value['track']['valid_frames'],
                'identity_continuity': value['identity_continuity'], 'physical_fitting_allowed': False,
                'target_prompt': (self.latest_diagnostic or {}).get('target_prompt'),
                'target_identity_status': (self.latest_diagnostic or {}).get('target_identity_status', 'UNVERIFIED'),
                'timing': 'SOFTWARE_CFR_PLAYBACK_IS_NOT_PHYSICAL_TIME'}
            # Source identity changes are informative but never silently merge tracks.
            informative = first_detection or value['identity_continuity'] == 'UNVERIFIED_OR_DISCONTINUOUS'
            if not informative and self.new_points < 20: return
            if time.monotonic() - self.last_reasoning < 2: return
        elif kind != 'operator':
            raise ValueError('unknown scientific event')
        if self.live.pending_action: return
        if self.agent is None and self.snapshot is None:
            self._readiness('NO_USABLE_OBSERVATIONS')
            return
        basis = digest({'observation': self.snapshot, 'admission': self.admission_ref,
            'tool_evidence': [r['result']['evidence_ref'] for r in self.agent.session.results] if self.agent else []})
        if basis == self.last_reasoning_basis:
            self._readiness('NO_NEW_ELIGIBLE_EVIDENCE')
            return
        self.last_reasoning_basis = basis  # Failed protocol attempts also consume this evidence basis.
        self.new_points = 0
        self.last_reasoning = time.monotonic()
        self.live.scientific['readiness'] = {'source': 'LOCAL_DETERMINISTIC_READINESS',
            'can_reason': True, 'code': 'NEW_ELIGIBLE_EVIDENCE', 'evidence_basis_sha256': basis,
            'operator_request': 'New visual or admitted scientific evidence is available. Any Muse call remains subject to authorized limits.'}
        self._advance()

    def _readiness(self, code):
        guidance = ((self.latest_diagnostic or {}).get('guidance') or
            'Review target visibility and the selected visual prompt; wait for usable SAM observations. Do not spend Muse requests to explain unchanged empty evidence.')
        value = {'source': 'LOCAL_DETERMINISTIC_READINESS', 'code': code, 'can_reason': False,
            'operator_request': guidance, 'diagnostic_code': (self.latest_diagnostic or {}).get('code'),
            'muse_response': False, 'physical_repair_certified': False}
        if value != self.live.scientific.get('readiness'):
            self.live.scientific['readiness'] = value
            self.live.record('LOCAL_READINESS', value)

    def _adapter(self):
        if self.adapter is None:
            if self.adapter_factory is None:
                from pathlib import Path
                from realign.local_environment import load_model_key
                load_model_key(Path(__file__).resolve().parents[3] / '.env')
            self.adapter = (self.adapter_factory(self.budget) if self.adapter_factory else
                MuseAdapter.from_environment(budget=self.budget, standard_tier_confirmed=True))
            self.adapter.before_request = self.live.ledger.reserve
        return self.adapter

    def _context(self):
        if self.agent:
            context = self.agent._context()
        else:
            context = {'stage': self.stage, 'round': 1, 'max_rounds': self.budget.max_rounds,
                'experiments_remaining': max(0, self.budget.max_experiments - self.experiments),
                'trial_refs': [], 'nominal_model_ref': None, 'budget_ref': digest(self.budget.model_dump(mode='json')),
                'protocol_ref': None, 'candidates': self.pixel_candidates, 'fits': {}, 'comparison': None,
                'identifiability': None, 'discrepancy': None, 'scores': {}, 'coverage_max_rad': None,
                'last_receipt': None, 'evidence_refs': [self.snapshot['snapshot_sha256']] if self.snapshot else []}
        context['live_observation'] = self.snapshot
        context['live_policy'] = ('Use only approved trial_refs in scientific tools. Preliminary pixels cannot support a physical '
            'fit or a repair. With no trial_refs, suggest one supplied reference action, or ABSTAIN. '
            'A human confirms and performs actions; no actuator exists. Prior hypotheses and budgets persist. '
            'Preliminary evidence_refs bind visual snapshots or the unavailable-calibration status only, not metric evidence.')
        assert_public_context(context)
        return context

    def _advance(self):
        live = self.live
        if self.agent is None and self.snapshot is None:
            self._readiness('NO_USABLE_OBSERVATIONS')
            return
        live.scientific['state'] = 'AGENT_INVESTIGATING'
        for _ in range(4):  # Bounded burst, never one request per frame.
            if live.cancel.is_set() or self.steps >= self.budget.max_steps: break
            context = self._context()
            reply = self._adapter().next(deepcopy(context))
            if live.cancel.is_set():
                live.record('MUSE_RESULT_AFTER_STOP', {'context_sha256': digest(context), 'applied': False})
                return
            self.steps += 1
            live.record('MUSE_REASONING', {'context_sha256': digest(context), 'context': context,
                'reply': reply.model_dump(mode='json'), 'step': self.steps})
            if reply.calls:
                if self.agent is None or self.agent.machine.stage != 'TEST':
                    code='SCIENTIFIC_TOOLS_UNAVAILABLE' if self.agent is None else 'TOOL_STAGE_NOT_ALLOWED'
                    if hasattr(self.adapter,'reject_pending'): self.adapter.reject_pending(reply.calls,code=code)
                    live.record('SCIENTIFIC_TOOL_REFUSED', {'code':code,'tools':[c.name for c in reply.calls],
                        'executed':False,'source':'LOCAL_CONTROLLER_GATE'})
                    raise ScientificGateRejection('Metric tools blocked until calibrated admission and the allowed tool stage',code=code)
                results = []
                for call in reply.calls:
                    arguments = TOOLS[call.name][0].model_validate_json(canonical(strict_json(call.arguments))).model_dump(mode='json')
                    result = self.agent.session.call(call.name, arguments)
                    results.append(result)
                    live.record('SCIENTIFIC_TOOL', {'name': call.name, 'arguments': arguments, 'result': result})
                self.adapter.deliver(reply.calls, results)
                live.scientific['tool_results'] = deepcopy(self.agent.session.results)
                continue
            turn = reply.turn
            approved_refs = set(context['evidence_refs'])
            if (not set(turn.evidence_refs).issubset(approved_refs) or
                    any(not set(h.evidence_refs).issubset(approved_refs) for h in turn.hypotheses)):
                raise ValueError('unapproved evidence citation')
            live.scientific['hypotheses'] = [h.model_dump(mode='json') for h in turn.hypotheses]
            stage = self.agent.machine.stage if self.agent else self.stage
            if turn.action == 'HYPOTHESIZE' and stage == 'HYPOTHESIZE':
                if self.agent: self.agent.machine.move('TEST')
                else: self.stage = 'TEST'
                continue
            if turn.action == 'REQUEST_EVIDENCE' and stage == 'TEST':
                if self.experiments >= self.budget.max_experiments: raise ValueError('experiment budget exhausted')
                selected = next((c for c in context['candidates'] if c['experiment_ref'] == turn.experiment_ref), None)
                if selected is None: raise ValueError('unapproved experiment')
                if self.agent:
                    if self.agent.session.scores.get(turn.experiment_ref, {}).get('feasible') is not True:
                        raise ValueError('experiment has no feasible deterministic score')
                    self.agent.environment.perform(selected)
                    pending = deepcopy(self.agent.environment.pending_action)
                    self.agent.machine.move('REQUEST_EVIDENCE')
                else:
                    pending = {'candidate': selected, 'state': 'WAITING_FOR_VALIDATED_RECORDINGS',
                        'context_sha256': digest(context), 'original_hypotheses': live.scientific['hypotheses'],
                        'physical_actuator_used': False, 'action_completed': False}
                    pending['request_id'] = digest(pending)
                self.experiments += 1
                live.pending_action = pending
                live.record('PHYSICAL_ACTION_PENDING', pending)
                live.scientific['state'] = 'PENDING_PHYSICAL_ACTION'
                return
            if turn.action == 'DECIDE' and stage == 'TEST':
                if self.agent:
                    accepted, reasons = PhysicalValidator().assess(turn, self.agent.session,
                        coverage=self.agent.coverage, receipt=self.agent.last_receipt)
                    if not accepted:
                        live.record('DECISION_REJECTED', {'turn': turn.model_dump(mode='json'), 'reasons': list(reasons)})
                        break
                    self.agent.machine.move('DECIDE')
                    details = self.agent.session.freeze(turn.model_ref if turn.outcome not in ('ABSTAIN', 'CORRECT_MEASUREMENT') else None)
                    self.agent.machine.move('FREEZE')
                    live.record('SCIENTIFIC_FREEZE', {'turn': turn.model_dump(mode='json'),
                                                     'numerical_details': details, 'numerical_audit': self.agent.session.audit()})
                elif turn.outcome != 'ABSTAIN':
                    raise ValueError('Physical acceptance blocked for preliminary observations')
                live.scientific.update(state='ABSTAIN' if turn.outcome == 'ABSTAIN' else 'FROZEN',
                    decision=turn.model_dump(mode='json'), independent_validation='NOT_RUN',
                    physical_G2=False, physical_G5=False)
                self.terminal = True
                return
            raise ValueError('invalid live investigation transition')
        live.scientific['state'] = 'CALIBRATED_OBSERVATION' if self.agent else 'PRELIMINARY_OBSERVATION'

    def _admit(self, value):
        live = self.live
        pending = live.pending_action
        if pending and not pending.get('confirmed_utc'):
            raise ValueError('Confirm and perform the physical action before admitting its response')
        data = asyncio.run(ingest_phone(value['manifest'], live.root / ('admission-' + uuid.uuid4().hex),
                                      run_api=False, cache_dir=live.root / 'sam_cache'))
        if data['status'] != 'READY':
            live.scientific['blockers'] = data['blockers']
            live.record('ADMISSION_BLOCKED', {'blockers': data['blockers']})
            return
        # Overlapping windows from a single recording are never independent trials.
        source_groups = {}
        live_windows = {}
        for path in live.root.glob('window-*/manifest.json'):
            import json
            doc = json.loads(path.read_text(encoding='utf-8'))
            source_groups[doc['video_sha256']] = doc['frames'][0]['recording_id']
            live_windows[doc['video_sha256']] = doc
        hashes = [t.observation.metadata.video_sha256 for t in data['trials']]
        if len(set(source_groups.get(h, h) for h in hashes)) != len(hashes):
            raise ValueError('Independent exploration recordings required; overlapping windows are one source')
        for trial in data['trials']:
            sha = trial.observation.metadata.video_sha256
            if sha in live_windows:
                from pathlib import Path
                from realign.perception.workflow import _path
                ref = data['config'].get('live_window_timing', {}).get(sha)
                if not ref: raise ValueError('LIVE_CFR_REQUIRES_INDEPENDENT_EXPOSURE_TIMELINE')
                reference = json.loads(_path(ref, Path(value['manifest']).resolve().parent).read_text(encoding='utf-8'))
                timing = verify_window_timing(trial, live_windows[sha], reference)
                live.record('WINDOW_EXPOSURE_TIMING_VERIFIED', timing)
        if pending and data['config'].get('response_to_request_id') != pending['request_id']:
            raise ValueError('Response manifest must bind the exact pending request')
        if pending:
            reference_hash = data['perception']['stationary_reference']['metadata']['video_sha256']
            for sha in [*hashes, reference_hash]:
                if sha in live_windows and any(row['response_to_request_id'] != pending['request_id']
                                               for row in live_windows[sha]['frames']):
                    raise ValueError('Response window contains evidence captured before action confirmation')
        if self.agent:
            env = self.agent.environment
            kind = pending['candidate']['action']['kind'] if pending else None
            if not pending: raise ValueError('Additional physical evidence requires an approved experiment')
            response = {'request_id': pending['request_id'], 'verified': True,
                'trials': data['trials'] if kind in ('RELEASE', 'REPEAT') else (), 'checks': data['checks'],
                'new_reference_video_sha256': data['perception']['stationary_reference']['metadata']['video_sha256']}
            env.responses[pending['request_id']] = response
            received = env.perform(pending['candidate'])
            if received is None: raise ValueError('Physical response was not admitted')
            self.agent.session.admit(received['trials'], received['checks'])
            self.agent.last_receipt = received['receipt']
            self.agent.round += 1
            self.agent.completed_experiments += 1
            for trial in received['trials']:
                self.agent.coverage = max(self.agent.coverage, abs(trial.experiment.release_angle_rad))
            self.agent.machine.move('OBSERVE')
            self.agent._observe()
        else:
            # Native Windows numerical isolation intentionally fails closed. Use
            # the supported WSL bridge; the camera remains owned by Windows.
            from .live_worker import scientific_worker
            self.worker = scientific_worker(self.worker_factory, timeout_s=self.budget.worker_timeout_s)
            env = PhysicalEnvironment(data['trials'], data['checks'], deadline_utc=data['config'].get('experiment_deadline_utc'))
            env.seen.add(data['perception']['stationary_reference']['metadata']['video_sha256'])
            session = ScientificSession(self.worker, data['trials'], PendulumParams(**data['config']['nominal_params']),
                                        data['checks'], budget=self.budget, gate=None)
            self.agent = Investigator(session, self._adapter(), env, validator=PhysicalValidator())
            self.agent.experiments = self.experiments
            if pending:
                self.agent.round = 2
                self.agent.completed_experiments = 1
                self.agent.last_receipt = {'kind': pending['candidate']['action']['kind'],
                    'source': 'APPROVED_RECORDING_LIBRARY', 'new_observations': 0}
            self.agent._observe()
        live.record('CALIBRATED_OBSERVATION_ADMITTED', {'manifest_sha256': data['input_manifest_sha256'],
            'trial_refs': list(self.agent.session.trial_refs), 'windows': data['windows'], 'sam_receipts': data['sam_receipts']})
        self.admission_ref = data['input_manifest_sha256']
        if pending:
            live.history.append({**deepcopy(pending), 'response_manifest_sha256': data['input_manifest_sha256'], 'state': 'ADMITTED'})
            live.pending_action = None
            live.active_action = None
        live.scientific.update(state='CALIBRATED_OBSERVATION', blockers=[], physical_evidence_accepted=True,
                               calibration_grade=data['calibration_grade'])
        # Reuse the validated free-model predictor solely for an admitted nominal
        # overlay. No optimization, model selection, or holdout access occurs here.
        from realign.fit.robust_fit import predict_free
        nominal = PendulumParams(**data['config']['nominal_params'])
        trial = data['trials'][0]
        simulated = predict_free(nominal, trial)
        valid = trial.observation.valid
        live.scientific['trajectory_comparison'] = {
            'scope': 'ADMITTED_EXPLORATION_NOMINAL_PREDICTION; NOT_INDEPENDENT_VALIDATION',
            'trial_id': trial.trial_id, 'measured_px': trial.observation.xy_px[valid].tolist(),
            'simulated_px': simulated[valid].tolist(),
            'image_size': [trial.observation.metadata.width, trial.observation.metadata.height]}

    def close(self):
        if self.adapter is not None: self.adapter.close()
        if self.worker is not None: self.worker.close()

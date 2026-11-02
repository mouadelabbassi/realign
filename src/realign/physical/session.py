"""Pending physical experiments and exact replay of an unfinished investigation."""
from copy import deepcopy
from dataclasses import asdict
from realign.audit.chain import canonical,digest,AuditChain
from realign.contracts.video import VideoTrial
from realign.contracts.investigation import AdapterReply,ExperimentCandidate,TOOLS
from realign.tools.resources import encode_trial
from realign.agent.investigator import ScientificValidator


def phone_trial(trial):
    if type(trial) is not VideoTrial or trial.zone!='exploration':
        raise ValueError('controlled exploration VideoTrial required')
    o=trial.observation
    if (o.metadata.source_kind!='REAL_PHONE' or o.provenance!='REAL_SAM' or o.sam_source!='REAL_API' or
        o.noise.provenance!='REAL_SAM' or trial.projection.source!='REAL_MEASURED'):
        raise ValueError('actual SAM, measured calibration and controlled phone provenance required')
    encode_trial(trial)  # Enforce the existing bounded numerical contract.
    return trial


class PhysicalValidator(ScientificValidator):
    def assess(self,turn,session,**kwargs):
        # No real-data structural null calibration has been registered. Neither
        # a strong synthetic statistic nor geometric circles can authorize it.
        if turn.outcome=='REPAIR_STRUCTURE':return False,('UNCALIBRATED',)
        return super().assess(turn,session,**kwargs)


class PhysicalEnvironment:
    def __init__(self,trials,checks,*,responses=None):
        self.initial=tuple(phone_trial(t) for t in trials)
        if len(self.initial)<2:raise ValueError('at least two independent exploration recordings required')
        self.checks=deepcopy(checks)
        if checks.get('source')!='REAL_MEASURED':raise ValueError('real reference measurements required')
        hashes=[t.observation.metadata.video_sha256 for t in self.initial]
        if len(set(hashes))!=len(hashes):raise ValueError('duplicate controlled recording')
        self.seen=set(hashes); self.responses=responses or {}; self.pending_action=None

    def perform(self,candidate):
        candidate=ExperimentCandidate.model_validate_json(canonical(candidate)).model_dump(mode='json')
        pending={'schema_version':'1.0','state':'WAITING_FOR_VALIDATED_RECORDINGS','observation_source':'REAL_PHONE',
                 'candidate':candidate,'prior_trial_refs':[digest({'kind':'TRIAL','value':encode_trial(t)}) for t in self.initial],
                 'required_inputs':['new original phone recording(s)','matching actual SAM receipt',
                    'measured camera calibration','independent reviewed centers and uncertainty','release timing when dynamic'],
                 'action_completed':False,'physical_actuator_used':False}
        pending['request_id']=digest(pending)
        response=self.responses.get(pending['request_id'])
        if response is None:
            self.pending_action=pending; return None
        kind=candidate['action']['kind']; trials=tuple(response.get('trials',()))
        if response.get('request_id')!=pending['request_id'] or response.get('verified') is not True:
            raise ValueError('response must bind the requested action and validated ingestion')
        required=candidate['action'].get('repeats',0) if kind in ('RELEASE','REPEAT') else 0
        if len(trials)!=required:raise ValueError('physical response recording count differs from requested action')
        for t in trials:
            phone_trial(t); sha=t.observation.metadata.video_sha256
            if sha in self.seen:raise ValueError('physical response reuses an existing recording')
            self.seen.add(sha)
            if kind=='RELEASE' and abs(t.experiment.release_angle_rad-candidate['action']['release_angle_rad'])>.08:
                raise ValueError('measured release differs from requested angle tolerance (0.08 rad)')
        checks=response.get('checks')
        if kind in ('STATIONARY_REFERENCE','CAMERA_CALIBRATION'):
            if not checks or checks.get('source')!='REAL_MEASURED' or not response.get('new_reference_video_sha256'):
                raise ValueError('reference action requires a new independently validated reference recording')
            if response['new_reference_video_sha256'] in self.seen:raise ValueError('reference recording already used')
            self.seen.add(response['new_reference_video_sha256'])
        return {'trials':trials,'checks':checks,'receipt':{'kind':kind,'source':'APPROVED_RECORDING_LIBRARY','new_observations':len(trials)}}


def validate_checkpoint(value):
    try:
        body=deepcopy(value); expected=body.pop('checkpoint_sha256')
        if (digest(body)!=expected or body['status']!='PENDING_PHYSICAL_ACTION' or body['model_frozen'] is not False or
            body['state_history'][-1]!='REQUEST_EVIDENCE' or not AuditChain.verify(body['audit']) or
            not AuditChain.verify(body['numerical_audit']['events']) or body['audit'][-1]['kind']!='PHYSICAL_ACTION_PENDING' or
            body['audit'][-1]['payload']!=body['pending_action'] or body['audit'][-1]['hash']!=body['audit_head']):
            raise ValueError
        pending=deepcopy(body['pending_action']); request=pending.pop('request_id')
        if digest(pending)!=request:raise ValueError
        from realign.agent.investigator import TRANSITIONS
        history=body['state_history']
        if history!=['OBSERVE']+[e['payload']['to'] for e in body['audit'] if e['kind']=='TRANSITION']:
            raise ValueError
        if any(b not in TRANSITIONS.get(a,set()) for a,b in zip(history,history[1:])):raise ValueError
        identities=[e['payload'] for e in body['audit'] if e['kind']=='ADAPTER_STATUS']
        if len(identities)!=1 or identities[0]!={'source':body['source'],'stats':body['adapter_stats'],'receipts':body['adapter_receipts']}:raise ValueError
        last=body['steps'][-1]
        if (last['reply']['turn']['action']!='REQUEST_EVIDENCE' or
            last['reply']['turn']['experiment_ref']!=pending['candidate']['experiment_ref'] or
            pending['candidate'] not in last['context']['candidates'] or
            last['context']['scores'][pending['candidate']['experiment_ref']]['feasible'] is not True):raise ValueError
        for step in body['steps']:
            if digest(step['context'])!=step['context_sha256']:raise ValueError
            AdapterReply.model_validate_json(canonical(step['reply']))
        events=body['numerical_audit']['events']
        if len(events)!=len(body['tool_results']):raise ValueError
        for event,item in zip(events,body['tool_results']):
            p=event['payload']; args=TOOLS[item['name']][0].model_validate_json(canonical(item['arguments'])).model_dump(mode='json')
            if p['name']!=item['name'] or p['input_sha256']!=digest(args) or p['output']!=item['result']:raise ValueError
        forbidden=('hidden_parameters','sealed_measurements','reveal_nonce','final_holdout_scores')
        if any(x in canonical([s['context'] for s in body['steps']]).decode() for x in forbidden):raise ValueError
        return value
    except (KeyError,TypeError,ValueError):raise ValueError('pending checkpoint integrity or scope failed') from None


class PrefixReplayAdapter:
    """Recompute recorded numerical actions, then continue with a fresh conversation.

    This is recorded-action replay, not a second execution of the original Meta
    requests. New live requests retain the earlier accounting/budget and see only
    the current approved context. Raw historical remote call IDs are not invented.
    """
    def __init__(self,checkpoint,delegate):
        validate_checkpoint(checkpoint)
        if checkpoint['source']!=delegate.source:raise ValueError('resume must preserve investigation policy')
        self.delegate=delegate; self.source=delegate.source; self.steps=checkpoint['steps']; self.index=0; self.replayed=False
        delegate.stats=deepcopy(checkpoint['adapter_stats'])
        if hasattr(delegate,'receipts'):delegate.receipts=deepcopy(checkpoint['adapter_receipts'])
        if hasattr(delegate,'_seen_ids'):
            delegate._seen_ids.update(c['call_id'] for s in self.steps for c in s['reply']['calls'])
        if hasattr(delegate,'counter'):
            delegate.counter=sum(len(s['reply']['calls']) for s in self.steps)

    @property
    def stats(self):return self.delegate.stats
    @property
    def receipts(self):return getattr(self.delegate,'receipts',[])
    def next(self,context):
        self.replayed=self.index<len(self.steps)
        if self.replayed:
            step=self.steps[self.index];self.index+=1
            if digest(context)!=step['context_sha256']:raise ValueError('resume observations or numerical evidence changed')
            return AdapterReply.model_validate_json(canonical(step['reply']))
        return self.delegate.next(context)
    def deliver(self,calls,results):
        if not self.replayed:self.delegate.deliver(calls,results)
    def close(self):
        if hasattr(self.delegate,'close'):self.delegate.close()

"""State transitions, conservative acceptance and immutable freeze.

Agent proposals never overrule numerical/quality/resource validation.
"""
import json
import math
from realign.audit.chain import AuditChain, canonical, digest
from realign.contracts.investigation import CANONICAL_OUTCOME, AgentTurn, AdapterReply, EvidenceReceipt, TOOLS, ToolCall
from realign.perception.meta_validation import strict_json
from .adapters import AdapterFailure

TRANSITIONS={
    'OBSERVE':{'HYPOTHESIZE','DECIDE'}, 'HYPOTHESIZE':{'TEST','DECIDE'},
    'TEST':{'REQUEST_EVIDENCE','DECIDE'}, 'REQUEST_EVIDENCE':{'OBSERVE','DECIDE'},
    'DECIDE':{'FREEZE'}, 'FREEZE':set(),
}


class StateMachine:
    def __init__(self,audit):
        self.stage='OBSERVE'; self.audit=audit
        self.history=['OBSERVE']

    def move(self,target):
        if target not in TRANSITIONS[self.stage]:
            raise ValueError('invalid state transition')
        self.audit.append('TRANSITION',{'from':self.stage,'to':target})
        self.stage=target; self.history.append(target)


class ScientificValidator:
    def assess(self,turn,session,*,coverage,receipt):
        supported={r['result']['evidence_ref'] for r in session.results}
        if not set(turn.evidence_refs).issubset(supported):
            return False,('ACCESS_DENIED',)
        if any(not set(h.evidence_refs).issubset(supported) for h in turn.hypotheses):
            return False,('ACCESS_DENIED',)
        if turn.outcome=='ABSTAIN':
            return True,tuple(turn.reasons)
        d=session.discrepancy
        if not d or d.get('code'):
            return False,('INSUFFICIENT_DATA',)
        if turn.outcome=='CORRECT_MEASUREMENT':
            ok=not d['quality_ok'] and bool(receipt) and receipt['kind'] in ('CAMERA_CALIBRATION','STATIONARY_REFERENCE')
            return ok,('QUALITY_FAILURE',) if ok else ('UNSUPPORTED_PROPOSAL',)
        if not d['quality_ok']:
            return False,('QUALITY_FAILURE',)
        c=session.comparison
        if not c or c.get('code') or c['status']!='OK':
            return False,('UNCALIBRATED',)
        if c['evidence_ref'] not in turn.evidence_refs:
            return False,('UNSUPPORTED_PROPOSAL',)
        scores={x['candidate']:x for x in c['scores']}
        for family in ('FREE','PEG_ONE_SIDE'):
            if scores.get(family,{}).get('model_ref')!=session.fits.get(family,{}).get('fitted_model_ref'):
                return False,('UNSUPPORTED_PROPOSAL',)
        if turn.outcome=='REPAIR_STRUCTURE':
            i=session.identifiability
            fit=session.fits.get('PEG_ONE_SIDE',{})
            ok=(c['calibrated_support']=='PEG_PREDICTIVE_DIFFERENCE' and
                i is not None and not i.get('code') and i['locally_identifiable'] and
                i['evidence_ref'] in turn.evidence_refs and turn.model_ref==fit.get('fitted_model_ref') and
                c['empirical_tail_probability'] is not None and c['empirical_tail_probability']<=.05 and
                scores['FREE']['noise_ratio'] is not None and scores['FREE']['noise_ratio']>3.)
            return bool(ok),() if ok else ('UNSUPPORTED_PROPOSAL',)
        if coverage<.6 or c['calibrated_support']=='PEG_PREDICTIVE_DIFFERENCE':
            return False,('UNEXCITED',)
        free=scores['FREE']
        if free['noise_ratio'] is None or free['noise_ratio']>4.:
            return False,('UNSUPPORTED_PROPOSAL',)
        if turn.outcome=='KEEP_UNCHANGED':
            ok=d['predictively_adequate'] and turn.model_ref==session.nominal_model_ref
            return bool(ok),('OPERATING_ENVELOPE_ONLY',) if ok else ('UNSUPPORTED_PROPOSAL',)
        if turn.outcome=='CALIBRATE_PARAMETERS':
            fit=session.fits.get('FREE',{})
            ok=(not d['predictively_adequate'] and d['trajectory_rmse_px']**2>4*free['trial_cv_mse_px2'] and
                turn.model_ref==fit.get('fitted_model_ref'))
            return bool(ok),('OPERATING_ENVELOPE_ONLY',) if ok else ('UNSUPPORTED_PROPOSAL',)
        return False,('UNSUPPORTED_PROPOSAL',)


class Investigator:
    def __init__(self,session,adapter,environment):
        self.session=session; self.adapter=adapter; self.environment=environment
        self.audit=AuditChain(); self.machine=StateMachine(self.audit)
        self.round=1; self.experiments=0; self.completed_experiments=0; self.last_receipt=None; self.steps=[]
        self.coverage=max(abs(t.experiment.release_angle_rad) for t in environment.initial)
        self.validator=ScientificValidator()

    def _context(self):
        s=self.session
        return {'stage':self.machine.stage,'round':self.round,'max_rounds':s.budget.max_rounds,
            'experiments_remaining':max(0,s.budget.max_experiments-self.experiments),
            'trial_refs':list(s.trial_refs),'nominal_model_ref':s.nominal_model_ref,
            'budget_ref':s.budget_ref,'protocol_ref':s.protocol_ref,'candidates':s.candidates,
            'fits':s.fits,'comparison':s.comparison,'identifiability':s.identifiability,
            'discrepancy':s.discrepancy,'scores':s.scores,'coverage_max_rad':self.coverage,
            'last_receipt':self.last_receipt,
            'evidence_refs':[r['result']['evidence_ref'] for r in s.results]}

    def _observe(self):
        result=self.session.call('inspect_discrepancy',{'trial_refs':list(self.session.trial_refs),
                                                       'model_ref':self.session.nominal_model_ref})
        self.audit.append('OBSERVATION',{'round':self.round,'trial_refs':list(self.session.trial_refs),'evidence':result})
        if result.get('code'):
            raise ValueError('observation unavailable')
        self.machine.move('HYPOTHESIZE')

    def run(self):
        proposal=None; accepted=False; reasons=(); failure=None
        try:
            self._observe()
            for _ in range(self.session.budget.max_steps):
                # Snapshot mutable session dictionaries before recording a step.
                # Later fits/scores must not rewrite previously hashed evidence.
                context=json.loads(canonical(self._context()))
                proposed_reply=self.adapter.next(json.loads(canonical(context)))
                reply=AdapterReply.model_validate_json(canonical(proposed_reply.model_dump(mode='json')))
                if reply.calls:
                    checked=[]
                    for call in reply.calls:
                        args=TOOLS[call.name][0].model_validate_json(canonical(strict_json(call.arguments)))
                        checked.append(ToolCall(call_id=call.call_id,name=call.name,arguments=args.model_dump_json()))
                    reply=AdapterReply(calls=tuple(checked))
                self.steps.append({'context':context,'context_sha256':digest(context),'reply':reply.model_dump(mode='json')})
                if reply.calls:
                    if self.machine.stage!='TEST':
                        raise ValueError('tools only allowed in TEST')
                    results=[]
                    for call in reply.calls:
                        args=strict_json(call.arguments)
                        result=self.session.call(call.name,args)
                        results.append(result)
                        if result.get('code') or result['status']=='FAILED':
                            failure=result.get('code') or next(iter(result.get('flags',())), 'SOLVER_FAILURE')
                    self.adapter.deliver(reply.calls,results)
                    self.audit.append('TOOL_ROUND',{'calls':[c.model_dump(mode='json') for c in reply.calls],
                                                    'results':results})
                    if failure:
                        raise ValueError('numerical/tool failure')
                    continue
                turn=reply.turn
                self.audit.append('PROPOSAL',turn.model_dump(mode='json'))
                if turn.action=='HYPOTHESIZE':
                    if self.machine.stage!='HYPOTHESIZE':
                        raise ValueError('hypothesis stage required')
                    known={r['result']['evidence_ref'] for r in self.session.results}
                    if not set(turn.evidence_refs).issubset(known):
                        raise ValueError('unapproved evidence citation')
                    self.machine.move('TEST')
                elif turn.action=='REQUEST_EVIDENCE':
                    if self.machine.stage!='TEST' or self.round>=self.session.budget.max_rounds or self.experiments>=self.session.budget.max_experiments:
                        failure='BUDGET'; raise ValueError('experiment budget')
                    candidates={x['experiment_ref']:x for x in self.session.candidates}
                    candidate=candidates.get(turn.experiment_ref)
                    score=self.session.scores.get(turn.experiment_ref)
                    if candidate is None or score is None or score.get('feasible') is not True:
                        failure='ACCESS_DENIED'; raise ValueError('unapproved or unscored experiment')
                    self.machine.move('REQUEST_EVIDENCE'); self.experiments+=1
                    received=self.environment.perform(candidate)
                    if received is None:
                        failure='NO_NEW_EVIDENCE'; raise ValueError('environment has no approved observation')
                    receipt=EvidenceReceipt.model_validate_json(canonical(received['receipt']))
                    if receipt.kind!=candidate['action']['kind'] or receipt.new_observations!=len(received['trials']):
                        raise ValueError('receipt/observation mismatch')
                    self.last_receipt=receipt.model_dump(mode='json')
                    self.completed_experiments+=1
                    self.audit.append('EVIDENCE_RECEIPT',{'experiment_ref':turn.experiment_ref,**self.last_receipt})
                    self.session.admit(received['trials'],received['checks'])
                    for t in received['trials']:
                        self.coverage=max(self.coverage,abs(t.experiment.release_angle_rad))
                    self.round+=1; self.machine.move('OBSERVE'); self._observe()
                elif turn.action=='DECIDE':
                    if self.machine.stage!='TEST':
                        raise ValueError('decision stage required')
                    proposal=turn
                    accepted,reasons=self.validator.assess(turn,self.session,coverage=self.coverage,receipt=self.last_receipt)
                    self.machine.move('DECIDE')
                    break
            else:
                failure='BUDGET'
        except Exception as exc:
            failure=failure or ('API_ERROR' if isinstance(exc,AdapterFailure) else 'INVALID_INPUT')
        if self.machine.stage!='DECIDE':
            self.machine.move('DECIDE')
        outcome=proposal.outcome if proposal is not None and accepted else 'ABSTAIN'
        model_ref=proposal.model_ref if proposal is not None and accepted and outcome not in ('ABSTAIN','CORRECT_MEASUREMENT') else None
        self.audit.append('ADAPTER_STATUS',{'source':self.adapter.source,'stats':self.adapter.stats,
                                          'receipts':getattr(self.adapter,'receipts',[])})
        self.audit.append('VALIDATION',{'proposed_outcome':proposal.outcome if proposal else None,
            'proposal_accepted':accepted,'accepted_outcome':outcome,'reasons':list(reasons or ((failure,) if failure else ()))})
        numerical=self.session.audit()
        if not AuditChain.verify(numerical['events']):
            raise ValueError('numerical audit integrity failure')
        frozen=self.session.freeze(model_ref)
        self.machine.move('FREEZE')
        freeze={'outcome':outcome,'canonical_outcome':CANONICAL_OUTCOME[outcome],
                'model_ref':model_ref,'trial_refs':list(self.session.trial_refs),'protocol_ref':self.session.protocol_ref,
                'proposal_accepted':accepted,'rounds':self.round,'experiments':self.completed_experiments,
                'experiment_requests':self.experiments,
                'reasons':list(reasons or ((failure,) if failure else ())),
                'scope':'PREDEFINED_PREDICTIVE_MODEL_IN_TESTED_ENVELOPE','causal_mechanism_identified':False,
                'numerical_audit_head':numerical['head']}
        freeze['freeze_sha256']=digest(freeze)
        self.audit.append('FREEZE',freeze)
        return {'source':self.adapter.source,'freeze':freeze,'state_history':self.machine.history,
                'steps':self.steps,'tool_results':self.session.results,'audit':self.audit.events,
                'audit_head':self.audit.head,'numerical_audit':numerical,'numerical_details':frozen,
                'adapter_stats':self.adapter.stats,'isolation':self.session.worker.isolation,
                'adapter_receipts':getattr(self.adapter,'receipts',[]),
                'isolation_probe':self.session.worker.probe}

"""Documented Muse tool/structured protocol and explicitly labelled offline policy.

No numerical tool result is produced by these adapters. All results come from
the isolated deterministic backend and are supplied with matching call IDs.
"""
import json
import os
import time
from realign.audit.chain import canonical, digest
from realign.contracts.investigation import AgentTurn, AdapterReply, ToolCall, tool_definitions
from realign.perception.meta_validation import strict_json


class AdapterFailure(RuntimeError):
    def __init__(self,message,*,code='MODEL_PROTOCOL_REJECTED',category='MODEL_PROTOCOL',http_status=None,error_type=None):
        super().__init__(message)
        self.code=code
        self.category='SCIENTIFIC_VALIDATION' if code=='EXPERIMENT_BUDGET_EXPIRED' else category
        self.http_status=http_status if type(http_status) is int and 100<=http_status<=599 else None
        self.error_type=error_type

    def diagnostic(self):
        return {'code':self.code,'category':self.category,'http_status':self.http_status,
                'error_type':self.error_type or type(self).__name__}


class NotAuthorized(AdapterFailure):
    pass


def hypotheses(context, selected=None):
    evidence=tuple(context['evidence_refs'][-8:])
    return [{'family':f,'status':'PREDICTIVELY_SUPPORTED' if f==selected else 'UNRESOLVED',
             'evidence_refs':evidence} for f in ('NOMINAL_FREE','PARAMETER_FREE','PEG_ONE_SIDE','MEASUREMENT')]


class DeterministicAdapter:
    source='DETERMINISTIC'
    def __init__(self):
        self.counter=0
        self.stats={'source':self.source,'actual_api_requests':0,'api_latency_s':None,
                    'input_tokens':None,'output_tokens':None,'token_cost_usd':None}

    def _call(self,name,args):
        self.counter+=1
        return AdapterReply(calls=(ToolCall(call_id='call_'+str(self.counter),name=name,
                                            arguments=canonical(args).decode()),))

    def _turn(self,c,action,*,outcome=None,model=None,experiment=None,selected=None,reasons=()):
        return AdapterReply(turn=AgentTurn(action=action,hypotheses=tuple(hypotheses(c,selected)),
            experiment_ref=experiment,outcome=outcome,model_ref=model,
            evidence_refs=tuple(c['evidence_refs'][-16:]),reasons=tuple(reasons)))

    def next(self,c):
        if c['stage']=='HYPOTHESIZE':
            return self._turn(c,'HYPOTHESIZE')
        d=c['discrepancy']; fits=c['fits']; comp=c['comparison']; ident=c['identifiability']
        if d and not d['quality_ok']:
            requested_kind='STATIONARY_REFERENCE' if d['stationary_sd_px'] is None else 'CAMERA_CALIBRATION'
            cameras=[x for x in c['candidates'] if x['action']['kind']==requested_kind]
            if c['last_receipt'] and c['last_receipt']['kind'] in ('CAMERA_CALIBRATION','STATIONARY_REFERENCE'):
                return self._turn(c,'DECIDE',outcome='CORRECT_MEASUREMENT',selected='MEASUREMENT',reasons=('QUALITY_FAILURE',))
            if cameras and c['experiments_remaining']:
                x=cameras[0]
                if x['experiment_ref'] not in c['scores']:
                    return self._call('score_candidate_experiment',{'fitted_model_refs':[],
                        'candidate':x,'feasibility_protocol_ref':c['protocol_ref']})
                return self._turn(c,'REQUEST_EVIDENCE',experiment=x['experiment_ref'],selected='MEASUREMENT')
            return self._turn(c,'DECIDE',outcome='ABSTAIN',reasons=('QUALITY_FAILURE',))
        for f in ('FREE','PEG_ONE_SIDE'):
            if f not in fits:
                return self._call('fit_candidate_model',{'trial_refs':c['trial_refs'],'candidate':f,
                    'nominal_model_ref':c['nominal_model_ref'],'budget_ref':c['budget_ref']})
        valid=all(fits[f].get('fitted_model_ref') for f in ('FREE','PEG_ONE_SIDE'))
        if valid and comp is None:
            return self._call('compare_candidate_models',{'trial_refs':c['trial_refs'],
                'fitted_model_refs':[fits[f]['fitted_model_ref'] for f in ('FREE','PEG_ONE_SIDE')],
                'protocol_ref':c['protocol_ref']})
        if valid and ident is None:
            return self._call('inspect_identifiability',{'trial_refs':c['trial_refs'],
                'fitted_model_ref':fits['PEG_ONE_SIDE']['fitted_model_ref']})
        if valid and comp and comp['status']=='OK':
            if comp['calibrated_support']=='PEG_PREDICTIVE_DIFFERENCE' and ident and ident['locally_identifiable']:
                return self._turn(c,'DECIDE',outcome='REPAIR_STRUCTURE',
                    model=fits['PEG_ONE_SIDE']['fitted_model_ref'],selected='PEG_ONE_SIDE')
            free=next(x for x in comp['scores'] if x['candidate']=='FREE')
            if free['noise_ratio'] is not None and free['noise_ratio']<=4. and c['coverage_max_rad']>=.6:
                if d['predictively_adequate']:
                    return self._turn(c,'DECIDE',outcome='KEEP_UNCHANGED',model=c['nominal_model_ref'],
                                      selected='NOMINAL_FREE',reasons=('OPERATING_ENVELOPE_ONLY',))
                if d['trajectory_rmse_px']**2>4*free['trial_cv_mse_px2']:
                    return self._turn(c,'DECIDE',outcome='CALIBRATE_PARAMETERS',
                        model=fits['FREE']['fitted_model_ref'],selected='PARAMETER_FREE',reasons=('OPERATING_ENVELOPE_ONLY',))
        if c['experiments_remaining'] and c['round']<c['max_rounds']:
            for x in c['candidates']:
                if x['experiment_ref'] not in c['scores']:
                    return self._call('score_candidate_experiment',{'fitted_model_refs':
                        [fits[f]['fitted_model_ref'] for f in ('FREE','PEG_ONE_SIDE')] if valid else [],
                        'candidate':x,'feasibility_protocol_ref':c['protocol_ref']})
            feasible=[x for x in c['candidates'] if c['scores'][x['experiment_ref']]['feasible']]
            # Same finite candidate set and numerical score as the mock/live arm.
            if feasible:
                def key(x):
                    s=c['scores'][x['experiment_ref']]
                    return (s['diagnostic_priority'],s['predictive_discrimination_sigma'] or 0.,
                            x['action']['kind']=='RELEASE')
                best=max(feasible,key=key)
                return self._turn(c,'REQUEST_EVIDENCE',experiment=best['experiment_ref'])
        reason='UNCALIBRATED' if comp and 'UNCALIBRATED' in comp.get('flags',()) else 'UNEXCITED' if valid else 'SOLVER_FAILURE'
        return self._turn(c,'DECIDE',outcome='ABSTAIN',reasons=(reason,))

    def deliver(self,calls,results):
        if len(calls)!=len(results):
            raise AdapterFailure('incomplete tool delivery')


class MockAdapter(DeterministicAdapter):
    """CI plumbing double; this is not simulated evidence of Muse reasoning."""
    source='MOCK_POLICY'


class ReplayAdapter(DeterministicAdapter):
    """Recorded actions with fresh deterministic numerical execution, not live Muse."""
    source='RECORDED_RESPONSE_REPLAY'
    def __init__(self, trace):
        from realign.report.investigator_run import verify_replay, science_signature
        if not verify_replay(trace) or trace.get('science_signature')!=science_signature():
            raise AdapterFailure('invalid replay evidence')
        super().__init__()
        self.steps=trace['steps']; self.index=0

    def next(self, context):
        if self.index>=len(self.steps):
            raise AdapterFailure('replay exhausted')
        step=self.steps[self.index]; self.index+=1
        if digest(context)!=step['context_sha256']:
            raise AdapterFailure('replay input/evidence mismatch')
        return AdapterReply.model_validate_json(canonical(step['reply']))


class MuseAdapter:
    source='LIVE_MUSE'
    def __init__(self,client,*,budget,source='LIVE_MUSE',retry_delay=.2,before_request=None):
        if source not in ('LIVE_MUSE','SIMULATED_API_FIXTURE'):
            raise ValueError('explicit adapter provenance required')
        self.source=source; self.client=client; self.budget=budget; self.retry_delay=retry_delay
        self.before_request=before_request
        self.messages=[{'role':'developer','content':
            'You are REALIGN, one bounded scientific investigator. Use only the five supplied scientific tools and opaque approved references. '
            'Do not invent numerical results, fault labels, posterior probabilities or tool replies. Hypothesize, test, request one approved '
            'experiment if evidence is insufficient, then propose a supported decision or ABSTAIN. A separate validator accepts decisions. '
            'KEEP is predictive adequacy within the tested operating envelope, never proof that no hidden mechanism exists. '
            'REPAIR_STRUCTURE means selection of the predefined PEG_ONE_SIDE dynamics only, never equation discovery or causal uniqueness. '
            'Return a closed AgentTurn JSON object when not calling a tool. Cite supplied evidence references. '
            'In HYPOTHESIZE return action HYPOTHESIZE. In TEST use tools, REQUEST_EVIDENCE or DECIDE. '
            'Use exactly the current trial_refs in the supplied order; never select a subset or reorder comparison folds. '
            'Call at most TWO tools in one response. Keep replies concise: at most two evidence refs per hypothesis and six overall. '
            'An initial two-trial comparison has no calibrated structural support: fit FREE and PEG_ONE_SIDE, compare, inspect PEG identifiability, '
            'then score the approved experiment candidates and request informative evidence when needed. '
            'Keep/recalibrate require the tested release-angle envelope to reach at least 0.6 rad; use the supplied scores and do not infer an outcome from training loss. '
            'CORRECT_MEASUREMENT means correction REQUIRED, not applied or verified. A reference check alone does not repair measurements. '
            'Raw frames, development observations, sealed data, file paths and generator parameters are unavailable.'}]
        self.stats={'source':source,'actual_api_requests':0,'fixture_requests':0,'successful_requests':0,
                    'failed_requests':0,'api_latency_s':0. if source=='LIVE_MUSE' else None,
                    'input_tokens':None,'output_tokens':None,'token_cost_usd':None}
        self.receipts=[]
        self._pending=()
        self._seen_ids=set()
        self._raw_ids={}

    @classmethod
    def from_environment(cls,*,budget,standard_tier_confirmed=False):
        key=os.environ.get('MODEL_API_KEY')
        if not key or not standard_tier_confirmed:
            raise NotAuthorized('local authorization and Standard tier are required',code='LOCAL_AUTHORIZATION_REQUIRED',category='AUTHORIZATION')
        from openai import OpenAI
        return cls(OpenAI(base_url='https://api.meta.ai/v1',api_key=key,timeout=45,max_retries=0),budget=budget)

    def _request(self):
        count=self.stats['actual_api_requests']+self.stats['fixture_requests']
        if count>=self.budget.max_api_requests:
            raise AdapterFailure('API request budget exhausted',code='API_BUDGET',category='BUDGET')
        if self.before_request is not None: self.before_request('muse','reasoning')
        self.stats['actual_api_requests' if self.source=='LIVE_MUSE' else 'fixture_requests']+=1
        start=time.monotonic()
        try:
            r=self.client.chat.completions.create(model='muse-spark-1.3',messages=self.messages,
                tools=tool_definitions(),tool_choice='auto',reasoning_effort='low',
                response_format={'type':'json_schema','json_schema':{'name':'realign_turn','schema':AgentTurn.model_json_schema()}},
                max_completion_tokens=3072)
            self.stats['successful_requests']+=1
            usage=getattr(r,'usage',None)
            if usage is not None:
                for attr,key in (('prompt_tokens','input_tokens'),('completion_tokens','output_tokens')):
                    value=getattr(usage,attr,None)
                    if type(value) is int and value>=0:
                        self.stats[key]=(self.stats[key] or 0)+value
            self.receipts.append({'status':'completed','response_sha256':digest(r.model_dump() if hasattr(r,'model_dump') else {'type':type(r).__name__})})
            return r
        except Exception as exc:
            self.stats['failed_requests']+=1
            status=getattr(exc,'status_code',None)
            self.receipts.append({'status':'failed','error_type':type(exc).__name__,
                                  'http_status':status if type(status) is int and 100<=status<=599 else None})
            raise
        finally:
            if self.source=='LIVE_MUSE':
                self.stats['api_latency_s']+=time.monotonic()-start

    def next(self,context):
        if self._pending:
            raise AdapterFailure('tool results must be delivered before the next request')
        self.messages.append({'role':'user','content':canonical(context).decode()})
        if len(canonical(self.messages))>250000:
            raise AdapterFailure('context size budget exhausted',code='CONTEXT_BUDGET',category='BUDGET')
        response=None
        for i in range(3):
            try:
                response=self._request()
                break
            except AdapterFailure:
                raise
            except Exception as exc:
                if getattr(exc,'code',None)=='AUTHORIZED_LIMIT_REACHED':
                    raise AdapterFailure('Authorized live request or spending limit reached',code='AUTHORIZED_LIMIT_REACHED',category='BUDGET') from None
                status=getattr(exc,'status_code',None)
                retryable=status in (408,429) or isinstance(status,int) and status>=500 or type(exc).__name__ in ('APIConnectionError','APITimeoutError')
                if not retryable or i==2:
                    category='META_HTTP' if type(status) is int else 'META_TRANSPORT' if type(exc).__name__ in ('APIConnectionError','APITimeoutError') else 'SDK_RUNTIME'
                    code='META_HTTP_ERROR' if category=='META_HTTP' else 'META_TRANSPORT_ERROR' if category=='META_TRANSPORT' else 'SDK_RUNTIME_ERROR'
                    raise AdapterFailure('Meta request failed; inspect safe diagnostic code',code=code,
                        category=category,http_status=status,error_type=type(exc).__name__) from None
                time.sleep(self.retry_delay*(2**i))
        try:
            choice=response.choices[0]; message=choice.message
            if getattr(choice,'finish_reason',None) in ('length','content_filter'):
                raise AdapterFailure('incomplete/refused model response',code='INCOMPLETE_MODEL_RESPONSE')
            raw=message.model_dump(exclude_none=True)
            if message.tool_calls:
                if len(message.tool_calls)>2:
                    raise AdapterFailure('model tool batch exceeds bound',code='TOOL_BATCH_LIMIT')
                calls=[]
                for tc in message.tool_calls:
                    if tc.type!='function':
                        raise AdapterFailure('unsupported tool type')
                    parsed=strict_json(tc.function.arguments)
                    from realign.contracts.investigation import TOOLS
                    if tc.function.name not in TOOLS:
                        raise AdapterFailure('unapproved tool name',code='UNAPPROVED_TOOL')
                    # Validate the entire batch BEFORE any numerical execution.
                    try:
                        TOOLS[tc.function.name][0].model_validate_json(canonical(parsed))
                    except ValueError:
                        raise AdapterFailure('tool arguments rejected',code='INVALID_TOOL_ARGUMENTS') from None
                    if not isinstance(tc.id,str) or not 1<=len(tc.id)<=128:
                        raise AdapterFailure('invalid tool call identifier')
                    local_id='call_'+digest({'remote_call_id':tc.id})[:32]
                    self._raw_ids[local_id]=tc.id
                    calls.append(ToolCall(call_id=local_id,name=tc.function.name,arguments=canonical(parsed).decode()))
                if len({x.call_id for x in calls})!=len(calls):
                    raise AdapterFailure('duplicate tool call IDs',code='DUPLICATE_TOOL_ID')
                if any(x.call_id in self._seen_ids for x in calls):
                    raise AdapterFailure('reused tool call ID',code='REUSED_TOOL_ID')
                self._seen_ids.update(x.call_id for x in calls)
                self._pending=tuple(calls)
                self.messages.append(raw)
                return AdapterReply(calls=tuple(calls))
            value=strict_json(message.content)
            turn=AgentTurn.model_validate_json(canonical(value))
            self.messages.append(raw)
            return AdapterReply(turn=turn)
        except AdapterFailure:
            raise
        except Exception as exc:
            raise AdapterFailure('invalid structured model response',code='INVALID_STRUCTURED_RESPONSE',error_type=type(exc).__name__) from None

    def deliver(self,calls,results):
        if len(calls)!=len(results) or [(c.call_id,c.name) for c in calls]!=[(c.call_id,c.name) for c in self._pending]:
            raise AdapterFailure('incomplete tool round trip')
        for call,result in zip(calls,results):
            from realign.contracts.investigation import TOOLS, ToolFailure
            cls=ToolFailure if 'code' in result else TOOLS[call.name][1]
            validated=cls.model_validate_json(canonical(result)).model_dump(mode='json')
            self.messages.append({'role':'tool','tool_call_id':self._raw_ids[call.call_id],'content':canonical(validated).decode()})
        self._pending=()

    def close(self):
        self.client.close()

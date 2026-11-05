"""Trusted post-freeze synthetic presentation export, with NO parameter fitting.

Task04 stored hashes, not raw trajectory arrays. Regeneration is explicit and
accepted only when every exploration observation matches its original capability.
Real measurements NEVER pass through this synthetic materializer.
"""
from dataclasses import asdict
from pathlib import Path
import numpy as np
from realign.audit.chain import canonical,digest
from realign.tools.resources import encode_trial
from realign.tools.registry import parameters,predict
from realign.synth.investigation_fixtures import case,NOMINAL
from .evidence import EvidenceError,read_json,sha256_file,validate_record,validate_bundle
from .semantics import decision_view

TITLES={'off_vertical_peg':'Two-round pendulum investigation','no_fault':'Nominal-model control',
    'parameter_mismatch':'Parameter calibration control','vertical_peg':'Contact-dynamics comparison',
    'unexcited_peg':'Limited-excitation control','measurement_problem':'Measurement quality check',
    'insufficient':'Insufficient-evidence control'}


def _ref(trial):
    return digest({'kind':'TRIAL','value':encode_trial(trial)})


def _array(value):
    a=np.asarray(value)
    if a.ndim==0:
        return float(a) if np.isfinite(a) else None
    return [_array(row) for row in a]


def _prediction(params,trial,label,round_number):
    xy=predict(parameters(params),trial)
    valid=trial.observation.valid
    error=float(np.sqrt(np.mean(np.sum((xy[valid]-trial.observation.xy_px[valid])**2,axis=1)))) if valid.any() else None
    return {'xy_px':_array(xy),'rmse_px':error,'label':label,'fitted_round':round_number}


def materialize(trace_path,*,run_id,expected_policy):
    trace=read_json(trace_path); checked=validate_record(trace,expected_policy)
    provenance=trace['fixture_provenance']
    if provenance.get('source')!='SYNTHETIC_ONLY' or provenance.get('label_post_freeze_only') not in TITLES:
        raise EvidenceError('only declared synthetic fixtures can be reconstructed')
    env=case(provenance['label_post_freeze_only'],seed=provenance['seed'],sigma=provenance['noise_sd_px'])
    observations=list(env.initial); admitted=[1]*len(observations)
    first=trace['steps'][0]['context']
    if [_ref(t) for t in observations]!=first['trial_refs']:
        raise EvidenceError('reconstructed initial observations differ from recorded evidence')
    nominal={'family':'FREE','params':asdict(NOMINAL),'training_refs':[],
             'budget_ref':first['budget_ref'],'role':'NOMINAL'}
    nominal_ref=digest({'kind':'MODEL','value':nominal})
    if nominal_ref!=first['nominal_model_ref']:
        raise EvidenceError('nominal simulator differs from recorded public model')
    if trace['freeze']['model_ref'] not in (None,nominal_ref,*checked['models']):
        raise EvidenceError('unknown frozen model capability')
    if trace['freeze']['model_ref']==nominal_ref and trace['numerical_details']['model']!={'family':'FREE','params':asdict(NOMINAL)}:
        raise EvidenceError('nominal frozen model export was altered')
    contexts={}; hypotheses={}; experiment={'requested':False,'action':None,'score':None,'receipt':None,'received_new_trials':0}
    receipt_events=[e['payload'] for e in trace['audit'] if e['kind']=='EVIDENCE_RECEIPT']
    receipt_index=0
    for step in trace['steps']:
        c=step['context']; contexts[c['round']]=c
        turn=step['reply']['turn']
        if turn:
            hypotheses[c['round']]=turn['hypotheses']
        if turn and turn['action']=='REQUEST_EVIDENCE':
            candidates={x['experiment_ref']:x for x in c['candidates']}
            candidate=candidates.get(turn['experiment_ref'])
            if candidate is None or experiment['requested']:
                raise EvidenceError('unapproved or repeated experiment in bounded replay')
            experiment.update(requested=True,action=candidate['action'],score=c['scores'].get(candidate['experiment_ref']))
            if receipt_index<len(receipt_events):
                receipt=receipt_events[receipt_index]; receipt_index+=1
                if receipt['experiment_ref']!=candidate['experiment_ref'] or receipt['source']!='SYNTHETIC_ENVIRONMENT':
                    raise EvidenceError('experiment receipt provenance mismatch')
                received=env.perform(candidate)
                if received is None or len(received['trials'])!=receipt['new_observations']:
                    raise EvidenceError('reconstructed experiment differs from recorded receipt')
                observations.extend(received['trials']); admitted.extend([c['round']+1]*len(received['trials']))
                experiment.update(receipt=receipt,received_new_trials=len(received['trials']))
    refs=[_ref(t) for t in observations]
    if refs!=trace['freeze']['trial_refs'] or receipt_index!=len(receipt_events):
        raise EvidenceError('reconstructed exploration set differs from frozen evidence')
    for number,c in contexts.items():
        expected=[ref for ref,r in zip(refs,admitted) if r<=number]
        if c['trial_refs']!=expected:
            raise EvidenceError('round observes unadmitted or future evidence')
    round_models={}
    rounds=[]
    for number,c in sorted(contexts.items()):
        selected={'B0':(asdict(NOMINAL),'B0 · nominal free model')}
        for family,label in (('FREE','B1'),('PEG_ONE_SIDE','B3')):
            fit=c['fits'].get(family,{})
            ref=fit.get('fitted_model_ref')
            if ref:
                model=checked['models'].get(ref)
                if model is None or model['training_refs']!=c['trial_refs']:
                    raise EvidenceError('display model uses a different exploration set')
                selected[label]=(model['params'],label+' · '+('parameter-only free model' if family=='FREE' else 'predefined peg dynamics'))
        round_models[number]=selected
        rounds.append({'round':number,'trial_ids':['trial-'+str(i+1) for i,r in enumerate(admitted) if r<=number],
            'trial_refs':c['trial_refs'],'hypotheses':hypotheses.get(number,[]),
            'comparison':c['comparison'],'identifiability':c['identifiability'],'discrepancy':c['discrepancy']})
    final_round=max(round_models); trials=[]; failures=[]
    def convert(t,ident,zone,when):
        predictions={}; by_round={}
        for number,models in round_models.items():
            if zone=='exploration' and when>number:
                continue
            if zone=='development' and number!=final_round:
                continue
            current={}
            for label,(params,description) in models.items():
                try:
                    current[label]=_prediction(params,t,description,0 if label=='B0' else number)
                except (ValueError,RuntimeError,FloatingPointError):
                    failures.append({'trial_id':ident,'model':label,'round':number,'status':'PREDICTION_UNAVAILABLE'})
            by_round[str(number)]=current
        predictions=by_round.get(str(when),by_round.get(str(final_round),{}))
        return {'id':ident,'zone':zone,'admitted_round':when,'release_angle_rad':t.experiment.release_angle_rad,
            't_s':_array(t.observation.t_s),'xy_px':_array(t.observation.xy_px),
            'valid':t.observation.valid.tolist(),'covariance_px2':_array(t.observation.covariance_px2),
            'predictions':predictions,'round_predictions':by_round}
    for i,(t,when) in enumerate(zip(observations,admitted)):
        trials.append(convert(t,'trial-'+str(i+1),'exploration',when))
    development=env.development_after_freeze()
    for i,t in enumerate(development):
        trials.append(convert(t,'development-'+str(i+1),'development',None))
    baseline={}
    for label in ('B0','B1','B3'):
        errors=[t['predictions'][label]['rmse_px'] for t in trials if t['zone']=='development' and label in t['predictions']]
        baseline[label]=float(np.sqrt(np.mean(np.array(errors)**2))) if len(errors)==len(development) else None
    outcome=trace['freeze']['outcome']; chosen='B0' if outcome=='KEEP_UNCHANGED' else 'B1' if outcome=='CALIBRATE_PARAMETERS' else 'B3' if outcome=='REPAIR_STRUCTURE' else None
    evaluated=baseline.get(chosen)
    recorded=trace['post_freeze_evaluation']['trajectory_rmse_px']
    if (evaluated is None)!=(recorded is None) or evaluated is not None and not np.isclose(evaluated,recorded,rtol=1e-7,atol=1e-7):
        raise EvidenceError('post-freeze evaluation differs from reconstructed frozen prediction')
    calls=[]
    for item in checked['results']:
        result=item['result']; args=item['arguments']
        round_number=item['round']
        metrics={k:v for k,v in result.items() if k in ('trajectory_rmse_px','innovation_mean_square','missing_fraction',
            'robust_cost','attempted_starts','converged_starts','statistic','empirical_tail_probability',
            'numerical_rank','locally_identifiable','predictive_discrimination_sigma','ensemble_spread_sigma','method','code')}
        calls.append({'name':item['name'],'status':result['status'],'flags':result.get('flags',[]),
            'metrics':metrics,'evidence_ref':result['evidence_ref'],'round':round_number})
    model_view={}
    for label,(params,description) in round_models[final_round].items():
        if label=='B0': ref=nominal_ref; content=nominal
        else:
            family='FREE' if label=='B1' else 'PEG_ONE_SIDE'
            ref=contexts[final_round]['fits'][family]['fitted_model_ref']; content=checked['models'][ref]
        model_view[label]={'params':params,'label':description,'model_ref':ref,'resource_content':content}
    bundle={'schema_version':1,'view_scope':'POST_FREEZE_HUMAN_ONLY','id':run_id,
        'title':TITLES[provenance['label_post_freeze_only']],'policy':checked['policy'],
        'observation_source':'SYNTHETIC','perception_source':'SYNTHETIC_GENERATOR','playback':'RECORDED_ARTIFACT',
        'integrity':{'status':'VERIFIED','artifact_sha256':sha256_file(trace_path),'audit_verified':True,
                     'observation_capabilities_matched':len(refs)},
        'decision':decision_view(trace['freeze']),'rounds':rounds,'trials':trials,'models':model_view,
        'experiment':experiment,'tool_calls':calls,'evaluation':{'scope':'POST_FREEZE_DEVELOPMENT','rmse_px':recorded},
        'baseline':baseline,'budget':trace['numerical_audit']['used'],
        'audit':{'head':trace['audit_head'],'verified':True,'event_count':len(trace['audit']),
                 'events':trace['audit'],'numerical_events':trace['numerical_audit']['events']},
        'api':checked['stats'],'prediction_failures':failures,
        'provenance':{'materialization':'EXPLICIT_SYNTHETIC_RECONSTRUCTION_WITH_EXACT_OBSERVATION_REF_CHECK',
            'physical_units':'px; time s; covariance px^2','synthetic_noise_sd_px':provenance['noise_sd_px'],
            'science_signature':trace['science_signature']},
        'caveats':['Synthetic physical observations; not SAM or phone measurements.',
            'Localization uncertainty is an assumed synthetic noise model, not measured SAM accuracy.',
            'Recorded hypotheses and tool results are played back; no model API call or fit occurs in the viewer.',
            'Independent development data are presented only after freeze and never used for selection.',
            'Predefined predictive model selection does not establish a unique physical mechanism.']}
    return validate_bundle(bundle)

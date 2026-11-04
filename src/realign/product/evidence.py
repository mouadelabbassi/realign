"""Strict post-freeze artifact admission. This is never an investigator tool.

Hash chains are integrity checks, not signatures. Display models must also match
the model capabilities named by audited tool outputs. A trusted catalog pins the
entire resulting presentation document, including its observation arrays.
"""
import hashlib
import math
from pathlib import Path
from realign.audit.chain import canonical,digest,AuditChain
from realign.contracts.investigation import TOOLS,AdapterReply
from realign.perception.meta_validation import strict_json


class EvidenceError(ValueError):
    pass


def read_json(path,limit=12_000_000):
    p=Path(path)
    if p.suffix.lower()!='.json' or any(x.lower() in ('sealed','vault','secrets','keys') for x in p.resolve().parts):
        raise EvidenceError('unapproved evidence resource')
    if p.stat().st_size>limit:
        raise EvidenceError('artifact exceeds presentation size limit')
    try:
        result=strict_json(p.read_text(encoding='utf-8-sig'))
        canonical(result)
        return result
    except (TypeError,ValueError,UnicodeError,RecursionError):
        raise EvidenceError('invalid finite JSON artifact') from None


def sha256_file(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def validate_record(trace,expected_policy=None):
    try:
        return _validate_record(trace,expected_policy)
    except EvidenceError:
        raise
    except (KeyError,TypeError,ValueError,AttributeError,IndexError):
        raise EvidenceError('malformed investigation evidence') from None


def _validate_record(t,expected_policy):
    from realign.report.investigator_run import verify_replay
    if type(t) is not dict or not verify_replay(t):
        raise EvidenceError('investigation audit, context or freeze integrity failed')
    identity=[e['payload'] for e in t['audit'] if e['kind']=='ADAPTER_STATUS']
    if len(identity)!=1:
        raise EvidenceError('one audited adapter identity required')
    identity=identity[0]; policy=identity['source']
    if policy not in ('DETERMINISTIC','MOCK_POLICY','LIVE_MUSE'):
        raise EvidenceError('unsupported presentation investigation policy')
    if expected_policy is not None and policy!=expected_policy:
        raise EvidenceError('investigation policy differs from approved catalog')
    if (t['source']!=policy or t['adapter_stats']!=identity['stats'] or
        t['adapter_receipts']!=identity['receipts']):
        raise EvidenceError('unbound adapter identity or receipts')
    stats=identity['stats']
    if policy=='LIVE_MUSE':
        if type(stats.get('actual_api_requests')) is not int or stats['actual_api_requests']<1:
            raise EvidenceError('live label requires actual request receipts')
        if len(identity['receipts'])!=stats['actual_api_requests']:
            raise EvidenceError('live request count/receipt mismatch')
    elif stats.get('actual_api_requests')!=0:
        raise EvidenceError('offline policy cannot claim live requests')
    numerical=t['numerical_audit']['events']
    if len(numerical)!=len(t['tool_results']):
        raise EvidenceError('tool evidence count mismatch')
    results=[]
    for event,item in zip(numerical,t['tool_results']):
        p=event['payload']; name=p['name']
        if event['kind']!='TOOL' or name not in TOOLS or name!=item['name']:
            raise EvidenceError('unknown or mismatched scientific tool')
        args=TOOLS[name][0].model_validate_json(canonical(item['arguments'])).model_dump(mode='json')
        if digest(args)!=p['input_sha256'] or item['result']!=p['output']:
            raise EvidenceError('tool display differs from numerical audit')
        results.append({'name':name,'arguments':args,'result':p['output']})
    audit_outputs=[]; audit_rounds=[]; replies=[]; current_round=1
    for event in t['audit']:
        p=event['payload']
        if event['kind']=='OBSERVATION':
            current_round=p['round']; audit_outputs.append(p['evidence']); audit_rounds.append(current_round)
        elif event['kind']=='TOOL_ROUND':
            audit_outputs.extend(p['results']); audit_rounds.extend([current_round]*len(p['results'])); replies.append(('calls',p['calls']))
        elif event['kind']=='PROPOSAL':
            replies.append(('turn',p))
    if audit_outputs!=[x['result'] for x in results] or len(replies)!=len(t['steps']):
        raise EvidenceError('agent and numerical evidence disagree')
    for item,number in zip(results,audit_rounds):
        item['round']=number
    for (kind,payload),step in zip(replies,t['steps']):
        reply=AdapterReply.model_validate_json(canonical(step['reply'])).model_dump(mode='json')
        if reply[kind]!=payload:
            raise EvidenceError('recorded model action differs from audit')
    model_refs={x['result'].get('fitted_model_ref') for x in results if x['name']=='fit_candidate_model'}
    model_refs.discard(None)
    models={}
    for model in t['numerical_details']['fitted_models']:
        ref=digest({'kind':'MODEL','value':model})
        if ref in model_refs:
            if model.get('role')!='FITTED' or model['family'] not in ('FREE','PEG_ONE_SIDE'):
                raise EvidenceError('invalid fitted model capability')
            models[ref]=model
    if set(models)!=model_refs:
        raise EvidenceError('fitted model does not match audited content reference')
    frozen=t['freeze']; exported=t['numerical_details']['model']
    if frozen['model_ref'] in models:
        model=models[frozen['model_ref']]
        if exported!={'family':model['family'],'params':model['params']}:
            raise EvidenceError('frozen model export differs from accepted model')
    elif frozen['model_ref'] is None:
        if exported is not None:
            raise EvidenceError('abstention cannot export an accepted model')
    return {'policy':policy,'results':results,'models':models,'stats':stats,
            'receipts':identity['receipts']}


def validate_bundle(bundle):
    """Validate cached presentation without loading a generator, fitter or worker."""
    try:
        if type(bundle) is not dict or bundle['schema_version']!=1 or bundle['view_scope']!='POST_FREEZE_HUMAN_ONLY':
            raise EvidenceError('unsupported presentation document')
        if bundle['observation_source']!='SYNTHETIC' or bundle['perception_source']!='SYNTHETIC_GENERATOR':
            raise EvidenceError('synthetic presentation cannot be relabelled as real measurements')
        if bundle['policy'] not in ('DETERMINISTIC','MOCK_POLICY','LIVE_MUSE'):
            raise EvidenceError('unknown investigation provenance')
        if bundle['playback']!='RECORDED_ARTIFACT' or bundle['audit']['verified'] is not True:
            raise EvidenceError('unverified evidence cannot be shown as replay')
        events=bundle['audit']['events']; numerical=bundle['audit']['numerical_events']
        if not events or not AuditChain.verify(events) or not AuditChain.verify(numerical) or events[-1]['kind']!='FREEZE':
            raise EvidenceError('cached audit linkage invalid')
        identity=[e['payload'] for e in events if e['kind']=='ADAPTER_STATUS']
        if len(identity)!=1 or identity[0]['source']!=bundle['policy'] or identity[0]['stats']!=bundle['api']:
            raise EvidenceError('cached policy or API accounting differs from audited identity')
        frozen=dict(events[-1]['payload']); frozen_hash=frozen.pop('freeze_sha256')
        if (digest(frozen)!=frozen_hash or frozen_hash!=bundle['decision']['freeze_sha256'] or
            frozen['outcome']!=bundle['decision']['outcome'] or frozen['model_ref']!=bundle['decision']['model_ref'] or
            events[-1]['hash']!=bundle['audit']['head'] or
            frozen['numerical_audit_head']!=(numerical[-1]['hash'] if numerical else '0'*64)):
            raise EvidenceError('cached decision differs from frozen audit')
        from .semantics import decision_view
        if bundle['decision']!=decision_view(events[-1]['payload']):
            raise EvidenceError('cached decision wording or correction claim differs from verified semantics')
        fitted_refs={e['payload']['output'].get('fitted_model_ref') for e in numerical
                     if e['kind']=='TOOL' and e['payload']['name']=='fit_candidate_model'}
        for name,model in bundle['models'].items():
            if (digest({'kind':'MODEL','value':model['resource_content']})!=model['model_ref'] or
                model['params']!=model['resource_content']['params']):
                raise EvidenceError('cached fitted model resource was altered')
            if name!='B0' and model['model_ref'] not in fitted_refs:
                raise EvidenceError('cached model was never produced by an audited fit')
        nominal=bundle['models']['B0']
        initial=next(e['payload']['trial_refs'] for e in events if e['kind']=='OBSERVATION')
        nominal_args=TOOLS['inspect_discrepancy'][0].model_validate_json(canonical(
            {'trial_refs':initial,'model_ref':nominal['model_ref']})).model_dump(mode='json')
        if (nominal['resource_content']['role']!='NOMINAL' or not numerical or
            numerical[0]['payload']['name']!='inspect_discrepancy' or
            digest(nominal_args)!=numerical[0]['payload']['input_sha256']):
            raise EvidenceError('nominal model differs from initial audited simulator')
        if frozen['model_ref'] is not None and frozen['model_ref'] not in {m['model_ref'] for m in bundle['models'].values()}:
            raise EvidenceError('frozen model missing from cached model resources')
        if not bundle['decision']['freeze_sha256'] or bundle['decision']['correction_applied'] or bundle['decision']['correction_verified']:
            raise EvidenceError('this evidence contains no verified measurement correction')
        if bundle['policy']=='LIVE_MUSE' and bundle['api']['actual_api_requests']<1:
            raise EvidenceError('no live requests for live-labelled investigation')
        for trial in bundle['trials']:
            n=len(trial['t_s'])
            if n<2 or n>256 or len(trial['xy_px'])!=n or len(trial['valid'])!=n:
                raise EvidenceError('trajectory/frame length mismatch')
            if any(b<=a for a,b in zip(trial['t_s'],trial['t_s'][1:])):
                raise EvidenceError('nonmonotone presentation timestamps')
            if any(type(x) not in (int,float) or not math.isfinite(x) for x in trial['t_s']):
                raise EvidenceError('invalid presentation timestamp')
            if trial['zone'] not in ('exploration','development'):
                raise EvidenceError('unapproved evidence zone')
            cov=trial['covariance_px2']
            if (len(cov)!=2 or any(len(row)!=2 for row in cov) or
                any(type(x) not in (int,float) or not math.isfinite(x) for row in cov for x in row) or
                abs(cov[0][1]-cov[1][0])>1e-10 or min(cov[0][0],cov[1][1])<0 or
                cov[0][0]*cov[1][1]-cov[0][1]**2 < -1e-10):
                raise EvidenceError('invalid pixel-squared localization covariance')
            for p,valid in zip(trial['xy_px'],trial['valid']):
                if len(p)!=2 or type(valid) is not bool or valid and any(type(x) not in (int,float) or not math.isfinite(x) for x in p):
                    raise EvidenceError('invalid observed coordinate')
            for predictions in [trial['predictions'],*trial.get('round_predictions',{}).values()]:
                if any(len(m['xy_px'])!=n for m in predictions.values()):
                    raise EvidenceError('prediction/frame mismatch')
                if any(len(p)!=2 or any(type(x) not in (float,int) or not math.isfinite(x) for x in p)
                       for m in predictions.values() for p in m['xy_px']):
                    raise EvidenceError('invalid full-trajectory prediction')
        forbidden={'hidden_parameters','ground_truth','sealed_data','reveal_nonce','label_post_freeze_only'}
        def inspect(value):
            if isinstance(value,dict):
                if forbidden.intersection(value):
                    raise EvidenceError('private investigation data cannot enter presentation')
                for v in value.values(): inspect(v)
            elif isinstance(value,list):
                for v in value: inspect(v)
        inspect(bundle); canonical(bundle)
        return bundle
    except EvidenceError:
        raise
    except (KeyError,TypeError,ValueError,AttributeError,IndexError,RecursionError,StopIteration):
        raise EvidenceError('malformed presentation artifact') from None


def validate_external(value):
    try:
        if value['observation_source']!='REAL_EXTERNAL' or value['physical_comparison_available'] is not False:
            raise EvidenceError('external tracking cannot become phone measurements or calibrated physics')
        if value.get('phone_g2_passed',False) is not False:
            raise EvidenceError('external footage cannot pass the controlled phone gate')
        if value.get('metadata'):
            from realign.contracts.external import ExternalVideoSource
            from realign.contracts.video import VideoMetadata
            source=ExternalVideoSource(**value['provenance'])
            metadata=value['metadata']
            if metadata['source_kind']!='REAL_EXTERNAL' or metadata['video_sha256']!=source.processed_sha256:
                raise EvidenceError('external video provenance mismatch')
            parsed=dict(metadata); times=parsed.pop('t_s')
            if parsed['external_source']!=value['provenance']:
                raise EvidenceError('metadata attribution differs from external source')
            parsed['external_source']=source
            original=VideoMetadata(**parsed)
            if times!=original.t_s.tolist():
                raise EvidenceError('display times differ from original presentation timestamps')
            track=value.get('track')
            if track is not None:
                receipt=value['sam'].get('receipt',{})
                if (receipt.get('source')!='REAL_API' or receipt.get('model')!='sam-3.1' or
                    receipt.get('status')!='completed' or not receipt.get('response_id') or
                    receipt.get('video_sha256')!=metadata['video_sha256']):
                    raise EvidenceError('real-labelled tracking requires actual completed SAM receipt')
                n=len(metadata['pts'])
                if len(track['xy_px'])!=n or len(track['valid'])!=n or len(track['flags'])!=n:
                    raise EvidenceError('external tracking/PTS mismatch')
                for point,valid,flags in zip(track['xy_px'],track['valid'],track['flags']):
                    if type(valid) is not bool or type(flags) is not int or flags<0 or len(point)!=2:
                        raise EvidenceError('invalid external frame quality fields')
                    if valid and (any(type(x) not in (int,float) or not math.isfinite(x) for x in point) or
                                  not 0<=point[0]<metadata['width'] or not 0<=point[1]<metadata['height']):
                        raise EvidenceError('valid external frame requires an in-frame finite center')
                for name in ('confidence','contour_rmse_px'):
                    if len(track[name])!=n:
                        raise EvidenceError('external diagnostic/frame mismatch')
        canonical(value); return value
    except EvidenceError:raise
    except (KeyError,TypeError,ValueError,AttributeError,ArithmeticError):
        raise EvidenceError('malformed external tracking presentation') from None

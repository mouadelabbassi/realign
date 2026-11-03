"""Controlled-video entrypoint, using the existing bounded scientific runtime.

Only exploration records enter tools/contexts. Independent holdouts are owned by
ValidationVault. Missing inputs and requested but unsupplied recordings produce
honest replayable partial records, never synthetic replacements.
"""
from dataclasses import asdict
from pathlib import Path
from realign.audit.chain import canonical,digest
from realign.contracts.investigation import Budget
from realign.physics import PendulumParams
from realign.agent.adapters import DeterministicAdapter,MuseAdapter,NotAuthorized
from realign.agent.investigator import Investigator
from realign.tools.client import ScientificSession
from realign.tools.sandbox import WorkerClient
from realign.fit.circle_fit import fit_geometry,CircleFitError
from realign.product.evidence import read_json
from realign.product.store import write_json
from .ingestion import ingest_phone
from .session import PhysicalEnvironment,PhysicalValidator,PrefixReplayAdapter,validate_checkpoint


def model_resource(trace,nominal):
    ref=trace['freeze']['model_ref']
    if ref is None:return None
    candidates=trace['numerical_details']['fitted_models']
    first=trace['steps'][0]['context']
    candidates=candidates+[{'family':'FREE','params':asdict(nominal),'training_refs':[],
                           'budget_ref':first['budget_ref'],'role':'NOMINAL'}]
    return next((m for m in candidates if digest({'kind':'MODEL','value':m})==ref),None)


def baseline_summary(trace,trial_refs,nominal_ref,geometry):
    """Export measured tool outputs, without an additional fit or heldout access.

    Only the current exploration set qualifies. Robust fit costs remain costs;
    cross-validation MSE and B2 radial error have separate names and units.
    """
    refs=list(trial_refs)
    current=[r for r in trace['tool_results'] if r['arguments'].get('trial_refs')==refs]
    def latest(name,**arguments):
        return next((r['result'] for r in reversed(current) if r['name']==name and
                     all(r['arguments'].get(k)==v for k,v in arguments.items())),None)
    discrepancy=latest('inspect_discrepancy',model_ref=nominal_ref)
    summary={'B0':{'status':'NOT_RUN'} if discrepancy is None else discrepancy,
             'B2':geometry,'trial_refs':refs,
             'comparison_scope':'EXPLORATION_ONLY; B2 radial error is not trajectory RMSE; real structural selection remains uncalibrated'}
    comparison=latest('compare_candidate_models')
    for key,family in [('B1','FREE'),('B3','PEG_ONE_SIDE')]:
        fit=latest('fit_candidate_model',candidate=family)
        summary[key]={'status':'NOT_RUN'} if fit is None else {'fit':fit,'status':fit['status']}
        if fit and fit.get('fitted_model_ref') and comparison:
            score=next((s for s in comparison.get('scores',[]) if
                        s['candidate']==family and s['model_ref']==fit['fitted_model_ref']),None)
            if score is not None:summary[key]['exploration_cross_validation']=score
    summary['comparison']=comparison or {'status':'NOT_RUN'}
    return summary


async def investigate_phone(manifest,output,*,run_api=False,live=False,standard_tier_confirmed=False,
                            resume=None,response_manifest=None,vault_directory=None,challenge_id=None,worker=None):
    out=Path(output);out.mkdir(parents=True,exist_ok=True)
    status={'schema_version':'1.0','observation_source':'REAL_PHONE','status':'BLOCKED_INPUTS',
            'blockers':[],'pending_action':None,'model_frozen':False,'full_G2_passed':False,
            'full_physical_G5_passed':False,'actual_api_requests':0,'sam_api':{},
            'limitations':['No synthetic observations substitute for controlled recordings.',
                'Synthetic null calibration cannot authorize real structural repair.',
                'A supplied recording receipt is not proof of a physical actuator or an independently timestamped intervention.']}
    original=None;adapter=None;env=None;own=worker is None
    def save():
        muse=adapter.stats['actual_api_requests'] if adapter is not None else 0
        status['actual_api_requests']=muse+sum(p.get('successful_calls',0)+p.get('failed_calls',0)
                                              for p in status['sam_api'].values())
        status['api_accounting_scope']='CURRENT_SAM_OPERATIONS_PLUS_CUMULATIVE_MUSE_ATTEMPTS; cached SAM calls excluded'
        if env is not None:status['physical_admission_history']=list(env.admission_history)
        write_json(out/'phone_status.json',status);return status
    try:
        if resume:
            original=validate_checkpoint(read_json(resume))
            if response_manifest is None:
                status.update(status='PENDING_PHYSICAL_ACTION',pending_action=original['pending_action'],
                              blockers=['REQUESTED_RECORDINGS_NOT_SUPPLIED'],checkpoint_sha256=original['checkpoint_sha256'])
                return save()
        ingested=await ingest_phone(manifest,out/'initial',run_api=run_api,cache_dir=out/'sam_cache')
        if 'perception' in ingested:status['sam_api']['initial']=ingested['perception']['actual_api']
        if ingested['status']!='READY':status['blockers']=ingested['blockers'];return save()
        config=ingested['config'];nominal=PendulumParams(**config['nominal_params']);status['calibration_grade']=ingested['calibration_grade']
        if nominal.peg is not None:raise ValueError('public nominal model must be free')
        responses={};response_data=None
        if original:
            if original.get('input_manifest_sha256')!=ingested['input_manifest_sha256']:
                raise ValueError('resume cannot change original observation configuration')
            response_data=await ingest_phone(response_manifest,out/'response',run_api=run_api,cache_dir=out/'sam_cache')
            if 'perception' in response_data:status['sam_api']['response']=response_data['perception']['actual_api']
            if response_data['status']!='READY':status['blockers']=response_data['blockers'];return save()
            pending=original['pending_action'];kind=pending['candidate']['action']['kind']
            response_config=response_data['config']
            if response_config.get('response_to_request_id')!=pending['request_id']:
                raise ValueError('response manifest is not bound to the pending action')
            responses[pending['request_id']]={'request_id':pending['request_id'],'verified':True,
                'trials':response_data['trials'] if kind in ('RELEASE','REPEAT') else (),
                'checks':response_data['checks'],
                'new_reference_video_sha256':response_data['perception']['stationary_reference']['metadata']['video_sha256']}
        env=PhysicalEnvironment(ingested['trials'],ingested['checks'],responses=responses,deadline_utc=config.get('experiment_deadline_utc'))
        env.seen.add(ingested['perception']['stationary_reference']['metadata']['video_sha256'])
        budget=Budget()
        adapter=MuseAdapter.from_environment(budget=budget,standard_tier_confirmed=standard_tier_confirmed) if live else DeterministicAdapter()
        if original:adapter=PrefixReplayAdapter(original,adapter)
        start=original.get('independent_start') if original else None
        vault=None
        if vault_directory is not None or challenge_id is not None:
            if not vault_directory or not challenge_id:raise ValueError('both custodian vault and challenge identity required')
            from realign.validation import ValidationVault
            vault=ValidationVault(vault_directory)
            vault.assert_exploration_disjoint(challenge_id,list(env.initial)+(response_data['trials'] if response_data else []))
            if start is None:start=vault.start_investigation(challenge_id)
        if worker is None:worker=WorkerClient(timeout_s=budget.worker_timeout_s)
        if vault:status['holdout_isolation']=vault.prove_agent_file_isolation(challenge_id,worker)
        session=ScientificSession(worker,env.initial,nominal,env.checks,budget=budget,gate=None)
        trace=Investigator(session,adapter,env,independent_start=start,validator=PhysicalValidator()).run()
        trace['observation_source']='REAL_PHONE'
        trace['input_manifest_sha256']=ingested['input_manifest_sha256']
        trace['observation_windows']=ingested['windows']
        trace['sam_receipts']=ingested['sam_receipts']
        if original:
            trace['parent_checkpoint_sha256']=original['checkpoint_sha256']
            trace['resume_mode']='RECORDED_ACTION_REEXECUTION_THEN_NEW_MODEL_CONVERSATION' if live else 'RECORDED_ACTION_REEXECUTION_THEN_POLICY_CONTINUATION'
        if trace.get('status')=='PENDING_PHYSICAL_ACTION':
            trace.pop('checkpoint_sha256');trace['checkpoint_sha256']=digest(trace)
            write_json(out/'checkpoint.json',trace)
            status.update(status=trace['status'],pending_action=trace['pending_action'],
                          checkpoint_sha256=trace['checkpoint_sha256'],blockers=['REQUESTED_RECORDINGS_NOT_SUPPLIED'])
        else:
            trace['status']='COMPLETED';write_json(out/'investigation.json',trace)
            status.update(status='FROZEN',model_frozen=True,decision=trace['freeze'],
                          trace_sha256=digest(trace),policy=trace['source'])
            selected=model_resource(trace,nominal)
            if selected is not None and vault is not None:
                frozen=vault.freeze_model(challenge_id,trace['freeze'],selected,start_receipt=start)
                vault.evaluate(challenge_id,frozen);vault.reveal(challenge_id)
                independent=vault.final_report(challenge_id);write_json(out/'independent_validation.json',independent)
                status['independent_validation']=independent
            else:status['independent_validation']={'status':'INCONCLUSIVE','blockers':[
                'NO_ACCEPTED_PREDICTIVE_MODEL' if selected is None else 'INDEPENDENT_PRECOMMITTED_CHALLENGE_NOT_SUPPLIED']}
        status['actual_api_requests']=adapter.stats['actual_api_requests']
        status['api']=adapter.stats
        all_trials=list(env.initial)
        if response_data:
            for t in response_data['trials']:
                if t.observation.metadata.video_sha256 in env.seen and t.observation.metadata.video_sha256 not in {x.observation.metadata.video_sha256 for x in all_trials}:all_trials.append(t)
        try:geometry=asdict(fit_geometry(all_trials))
        except (CircleFitError,ValueError,RuntimeError):geometry={'status':'UNAVAILABLE','reason':'INSUFFICIENT_GEOMETRIC_EVIDENCE'}
        status['baselines']=baseline_summary(trace,session.trial_refs,session.nominal_model_ref,geometry)
        return save()
    except NotAuthorized:
        status.update(status='NOT_RUN',blockers=['LOCAL_META_AUTHORIZATION_AND_STANDARD_TIER_REQUIRED']);return save()
    except Exception as exc:
        status.update(status='FAILED',error_type=type(exc).__name__,blockers=['CONTROLLED_RECORDING_OR_RUNTIME_VALIDATION_FAILED'])
        if adapter is not None:status['actual_api_requests']=adapter.stats['actual_api_requests']
        return save()
    finally:
        if adapter is not None and hasattr(adapter,'close'):adapter.close()
        if own and worker is not None:worker.close()

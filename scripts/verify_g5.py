"""Independent custodian CLI. Synthetic exercises are never physical discoveries."""
import argparse
from dataclasses import asdict
from pathlib import Path
import secrets,sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))


def demo(output,vault_dir,seed):
    from realign.physics import PendulumParams,PegParams
    from realign.contracts import Experiment,NoiseConfig
    from realign.synth.generator import generate_trial
    from realign.synth.investigation_fixtures import SyntheticEnvironment,NOMINAL
    from realign.validation import ValidationVault,GeometryMeasurements,EvaluationProtocol
    from realign.agent.adapters import DeterministicAdapter
    from realign.agent.investigator import Investigator
    from realign.tools.sandbox import WorkerClient
    from realign.tools.client import ScientificSession
    from realign.report.investigator_run import load_gate,verify_replay
    from realign.physical.orchestration import model_resource
    from realign.product.store import write_json
    from realign.audit.chain import digest
    import math
    output.mkdir(parents=True,exist_ok=True)
    private_random=secrets.SystemRandom()
    truth=PendulumParams(.72,gamma_per_s=.06,quadratic_drag_per_m=.02,
        peg=PegParams(private_random.uniform(.14,.18),private_random.uniform(-.45,-.35)))
    heldout=[generate_trial(truth,Experiment(a,1.6,20.),seed=seed+10000+i,
        trial_id='holdout-'+str(i),noise=NoiseConfig(),zone='development')[0] for i,a in enumerate((.4,.56,.62))]
    geometry=GeometryMeasurements(string_length_m=truth.length_m,string_length_sigma_m=0.,
        peg_xy_m=(truth.peg.distance_m*math.sin(truth.peg.angle_rad),-truth.peg.distance_m*math.cos(truth.peg.angle_rad)),
        peg_sigma_m=(0.,0.),method='SYNTHETIC_FIXTURE',reference_ids=('SYNTHETIC_CHALLENGE_SETUP',))
    vault=ValidationVault(vault_dir);ident='run-'+secrets.token_hex(8)
    commitment=vault.prepare_challenge(ident,heldout,geometry,protocol=EvaluationProtocol())
    write_json(output/'commitment.json',commitment)
    start=vault.start_investigation(ident);write_json(output/'investigation_start.json',start)
    env=SyntheticEnvironment(truth,seed=seed,sigma=.5)
    gate=load_gate(ROOT/'artifacts/task04/null_calibration.json')
    with WorkerClient(timeout_s=600) as worker:
        proof=vault.prove_agent_file_isolation(ident,worker);write_json(output/'isolation.json',proof)
        session=ScientificSession(worker,env.initial,NOMINAL,env.checks,gate=gate,release_angles=env.allowed_release_angles)
        trace=Investigator(session,DeterministicAdapter(),env,independent_start=start).run()
    trace.update(status='COMPLETED',observation_source='SYNTHETIC',scope='FRESH_SYNTHETIC_G5_EXERCISE',seed=seed,
                 challenge_design='PRIVATE_RANDOMIZED_PEG_GEOMETRY; PUBLISHED ONLY AFTER EVALUATION')
    assert verify_replay(trace)
    write_json(output/'investigation.json',trace)
    resource=model_resource(trace,NOMINAL)
    if resource is None:
        write_json(output/'validation.json',{'status':'INCONCLUSIVE','domain':'SYNTHETIC',
            'blockers':['NO_ACCEPTED_PREDICTIVE_MODEL'],'full_physical_G5_passed':False,'commitment':commitment})
        return 2
    frozen=vault.freeze_model(ident,trace['freeze'],resource,start_receipt=start)
    write_json(output/'frozen_model.json',frozen.public_receipt())
    vault.evaluate(ident,frozen)
    vault.reveal(ident)
    report=vault.final_report(ident);write_json(output/'validation.json',report)
    assert report['full_physical_G5_passed'] is False
    print(report['independent_verdict'],flush=True)
    return 0 if report['independent_verdict']=='SYNTHETIC_EXERCISE_PASS' else 2


def reproduce(output,vault_dir=None):
    """Recompute an already revealed synthetic score; no fitting or new look."""
    from realign.product.evidence import read_json
    from realign.product.store import write_json
    from realign.product.closure import validate_independent_report
    from realign.validation import ValidationVault,EvaluationProtocol,FrozenModel
    from realign.validation.scoring import deserialize_heldout,score_predictions
    from realign.physical.orchestration import model_resource
    from realign.synth.investigation_fixtures import NOMINAL
    from realign.tools.registry import parameters
    from realign.audit.chain import canonical,digest
    from realign.fit.baselines import observation_fingerprint
    report=read_json(output/'validation.json');validate_independent_report(report)
    if report['commitment']['domain']!='SYNTHETIC':raise ValueError('synthetic reproduction only')
    records_path=output/'heldout_post_reveal.json'
    if not records_path.is_file():
        if vault_dir is None:raise ValueError('original custodian vault required for first post-reveal export')
        records=ValidationVault(vault_dir).export_revealed_synthetic_records(report['commitment']['challenge_id'])
        write_json(records_path,records)
    records=read_json(records_path)
    trials=[deserialize_heldout(r) for r in records]
    if digest(sorted(observation_fingerprint(t) for t in trials))!=report['commitment']['heldout_dataset_sha256']:
        raise ValueError('public heldout records differ from the pre-investigation commitment')
    trace=read_json(output/'investigation.json');start=read_json(output/'investigation_start.json')
    resource=model_resource(trace,NOMINAL)
    payload={'schema_version':'1.0','challenge_id':report['commitment']['challenge_id'],
        'commitment_sha256':report['commitment']['commitment_sha256'],
        'start_receipt_sha256':start['start_receipt_sha256'],
        'investigation_freeze':trace['freeze'],'model_resource':resource}
    if FrozenModel(canonical(payload)).content_sha256!=report['frozen_model']['content_sha256']:
        raise ValueError('public frozen model does not match the evaluated content hash')
    result=score_predictions(parameters(resource['params']),trials,
        EvaluationProtocol.model_validate_json(canonical(report['commitment']['protocol'])))
    if any(result[k]!=report['evaluation'][k] for k in result):
        raise ValueError('post-reveal reproduction differs from the spent evaluation')
    write_json(output/'reproduction.json',{'status':'PASS','scope':'PUBLIC_POST_REVEAL_REPRODUCTION; NOT_NEW_EVALUATION',
        'domain':'SYNTHETIC','frozen_model_sha256':report['frozen_model']['content_sha256'],
        'trajectory_rmse_px':result['trajectory_rmse_px'],'prediction_digests_match':True,
        'independent_verdict':report['independent_verdict'],'fit_calls':0,'meta_api_calls':0})
    print('Post-reveal reproduction: PASS (original verdict: '+report['independent_verdict']+')')
    return 0


if __name__=='__main__':
    from realign.investigator_platform import delegate
    delegate('verify_g5.py')
    p=argparse.ArgumentParser(description=__doc__)
    sub=p.add_subparsers(dest='command',required=True)
    d=sub.add_parser('demo');d.add_argument('--seed',type=int,default=66300)
    d.add_argument('--output-dir',type=Path,default=ROOT/'artifacts/task06/g5_demo')
    d.add_argument('--vault-dir',type=Path,default=ROOT/'data/vault/task06')
    replay=sub.add_parser('reproduce');replay.add_argument('public_directory',type=Path)
    replay.add_argument('--vault-dir',type=Path)
    c=sub.add_parser('prepare');c.add_argument('private_bundle',type=Path)
    c.add_argument('--vault-dir',type=Path,required=True);c.add_argument('--challenge-id',required=True)
    c.add_argument('--public-output',type=Path,required=True)
    real=sub.add_parser('prepare-recordings')
    real.add_argument('private_manifest',type=Path);real.add_argument('--vault-dir',type=Path,required=True)
    real.add_argument('--challenge-id',required=True);real.add_argument('--geometry-file',type=Path,required=True)
    real.add_argument('--private-output-dir',type=Path,default=ROOT/'data/processed/task06_custodian')
    real.add_argument('--public-output',type=Path,required=True);real.add_argument('--run-api',action='store_true')
    args=p.parse_args()
    if args.command=='demo':raise SystemExit(demo(args.output_dir,args.vault_dir,args.seed))
    if args.command=='reproduce':raise SystemExit(reproduce(args.public_directory,args.vault_dir))
    from realign.validation import ValidationVault
    from realign.validation.scoring import deserialize_heldout
    from realign.perception.meta_validation import strict_json
    from realign.product.store import write_json
    if args.command=='prepare-recordings':
        import asyncio
        from dataclasses import replace
        from realign.physical.ingestion import ingest_phone
        from realign.validation import RealQualification
        ingested=asyncio.run(ingest_phone(args.private_manifest,args.private_output_dir,run_api=args.run_api))
        if ingested['status']!='READY':
            print('NOT_PREPARED: '+', '.join(ingested['blockers']));raise SystemExit(2)
        geometry=strict_json(args.geometry_file.read_text(encoding='utf-8-sig'))
        q=RealQualification(independent_manual_review_verified=True,camera_calibration_verified=True,
            capture_timing_verified=True,release_conditions_measured=all(r.get('release_bracket_pts_s') is not None for r in ingested['config']['exploration']),
            stationary_noise_measured=True,independent_geometry_measured=geometry.get('method')=='INDEPENDENT_PHYSICAL_MEASUREMENT',
            reference_ids=tuple(geometry['reference_ids']))
        c=ValidationVault(args.vault_dir).prepare_challenge(args.challenge_id,
            [replace(t,zone='development') for t in ingested['trials']],geometry,domain='REAL_PHONE',qualification=q)
        write_json(args.public_output,c);print('COMMITTED: '+c['commitment_sha256']);raise SystemExit(0)
    bundle=strict_json(args.private_bundle.read_text(encoding='utf-8-sig'))
    commitment=ValidationVault(args.vault_dir).prepare_challenge(args.challenge_id,
        [deserialize_heldout(r) for r in bundle['records']],bundle['geometry'],domain=bundle['domain'],
        protocol=bundle.get('protocol'),qualification=bundle.get('qualification'),
        exploration_fingerprints=bundle.get('exploration_fingerprints',()))
    write_json(args.public_output,commitment)
    print('COMMITTED: '+commitment['commitment_sha256'])

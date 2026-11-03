"""Adversarial checks complement the existing G5 suite; synthetic fixtures only."""
import ast,json,subprocess
from pathlib import Path
import pytest
from realign.audit.chain import canonical,digest
from realign.audit.exposure import assert_public_context
from realign.audit.public_validation import verify_reveal,_commitment
from realign.validation import ValidationVault,ValidationError,GeometryMeasurements

ROOT=Path(__file__).resolve().parents[2]

def test_legitimate_peg_hypotheses_survive_precise_guard():
    assert_public_context({'candidate':'PEG_ONE_SIDE','params':{'peg':{'distance_m':.16}},'registered_threshold':1.,'fault':'candidate'})

@pytest.mark.parametrize('payload',[{'nonce_hex':'private'},{'nested':[{'groundTruth':{}}]},
    {'heldout_observations':[]},{'path':'data/vault/private.json'},{'hidden_geometry':{}},{'NONCE_HEX':'private'},{'ground-truth':{}}])
def test_private_fields_and_paths_never_enter_model_context(payload):
    with pytest.raises(ValueError):assert_public_context(payload)

def test_product_and_agent_have_no_import_of_custodian():
    # Audit public verifier is a shared data-only module, not a vault wrapper.
    for directory in ['agent','product','audit']:
        for p in (ROOT/'src/realign'/directory).rglob('*.py'):
            for n in ast.walk(ast.parse(p.read_text(encoding='utf-8'))):
                if isinstance(n,ast.ImportFrom):assert not (n.module or '').startswith('realign.validation'),p
                elif isinstance(n,ast.Import):assert not any(x.name.startswith('realign.validation') for x in n.names),p

def test_v1_historical_records_and_commitment_encoding_remain_authentic():
    for folder in ['g5_demo','g5_positive_control']:
        relative='artifacts/task06/'+folder+'/validation.json';path=ROOT/relative
        assert path.read_bytes()==subprocess.check_output(['git','show','88b1e13:'+relative],cwd=ROOT)
        report=json.loads(path.read_bytes());assert verify_reveal(report['commitment'],report['reveal'])
        typed=dict(report['reveal'],geometry=GeometryMeasurements.model_validate_json(canonical(report['reveal']['geometry'])))
        assert verify_reveal(report['commitment'],typed)
        c=report['commitment'];r=report['reveal']
        assert _commitment(c['challenge_id'],c['domain'],c['heldout_dataset_sha256'],c['protocol'],r['geometry'],r['nonce_hex'])==c['commitment_sha256']
        bad=dict(r,challenge_id='another');assert not verify_reveal(c,bad)

def test_postmortem_cannot_change_acceptance_or_claim_a_precise_interval(monkeypatch):
    from realign.product.claim_ladder import release_view
    def forbidden(*a,**kw):raise AssertionError('Post-mortem attempted a new heldout evaluation')
    monkeypatch.setattr(ValidationVault,'evaluate',forbidden)
    result=release_view(ROOT)['post_mortem']
    assert result['original_verdict']=='SYNTHETIC_VALIDATION_FAIL'
    assert result['heldout_evaluations']==result['fit_calls']==result['new_predictions']==0
    assert result['precise_geometry_claim_allowed'] is False and result['credible_interval']=='NOT_AVAILABLE'

@pytest.fixture
def new_vault(tmp_path):
    from realign.synth.generator import generate_trial
    from realign.physics import PendulumParams
    from realign.contracts import Experiment
    p=PendulumParams(.72)
    trials=[generate_trial(p,Experiment(a,.8,20.),seed=90100+i,trial_id='synthetic-'+str(i),zone='development')[0] for i,a in enumerate((.4,.5))]
    vault=ValidationVault(tmp_path/'vault')
    vault.prepare_challenge('challenge',trials,GeometryMeasurements(string_length_m=.72,string_length_sigma_m=0.,method='SYNTHETIC_FIXTURE',reference_ids=('SYNTHETIC_UNIT',)))
    vault.start_investigation('challenge');return vault

@pytest.mark.parametrize('kind',['truncate','delete','reorder','protocol','reuse_id','before_commitment'])
def test_missing_adversarial_cases_fail_closed(new_vault,kind):
    v=new_vault
    with pytest.raises(ValidationError):
        if kind=='delete':
            v.ledger_path.unlink();v.start_investigation('challenge')
        elif kind in ('truncate','reorder'):
            lines=v.ledger_path.read_bytes().splitlines(keepends=True)
            v.ledger_path.write_bytes(b''.join(lines[:-1] if kind=='truncate' else list(reversed(lines))))
            v.start_investigation('challenge')
        elif kind=='protocol':
            path=v.directory/'challenge.private.json';x=json.loads(path.read_bytes())
            x['public']['protocol']['peg_position_tolerance_m']=1.;path.write_bytes(canonical(x))
            v.assert_exploration_disjoint('challenge',[])
        elif kind=='reuse_id':v.start_investigation('challenge')
        else:v.start_investigation('never-committed')
